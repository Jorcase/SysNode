import TcpSocket from 'react-native-tcp-socket';
import { Buffer } from 'buffer';
import * as FileSystem from 'expo-file-system/legacy';

export class TcpClient {
  /**
   * Conecta al nodo remoto, envía un mensaje JSON empaquetado con Framing (4 bytes BE length),
   * espera la respuesta ACK del servidor y cierra la conexión.
   */
  static sendFramedMessage(ip, port, payload, onResult, onError) {
    let receiveBuffer = Buffer.alloc(0);
    let expectedLength = null;
    let resolved = false;

    const client = TcpSocket.createConnection({ port, host: ip, timeout: 5000 }, () => {
      try {
        const payloadStr = JSON.stringify(payload);
        const payloadBuf = Buffer.from(payloadStr, 'utf8');
        
        const lengthBuf = Buffer.alloc(4);
        lengthBuf.writeUInt32BE(payloadBuf.length, 0);
        
        const finalBuf = Buffer.concat([lengthBuf, payloadBuf]);
        client.write(finalBuf);
      } catch (err) {
        if (!resolved) {
          resolved = true;
          if (onError) onError("Error al serializar el mensaje: " + err.message);
        }
        client.destroy();
      }
    });

    client.on('data', (data) => {
      receiveBuffer = Buffer.concat([receiveBuffer, data]);

      if (expectedLength === null && receiveBuffer.length >= 4) {
        expectedLength = receiveBuffer.readUInt32BE(0);
        receiveBuffer = receiveBuffer.slice(4);
      }

      if (expectedLength !== null && receiveBuffer.length >= expectedLength) {
        const payloadBuf = receiveBuffer.slice(0, expectedLength);
        const payloadStr = payloadBuf.toString('utf8');
        try {
          const response = JSON.parse(payloadStr);
          if (!resolved) {
            resolved = true;
            if (onResult) onResult(response);
          }
        } catch (e) {
          if (!resolved) {
            resolved = true;
            if (onError) onError("Error parseando respuesta JSON: " + e.message);
          }
        }
        client.destroy();
      }
    });

    client.on('error', (error) => {
      if (!resolved) {
        resolved = true;
        if (onError) onError("Error TCP: " + error.message);
      }
      client.destroy();
    });
    
    client.on('timeout', () => {
      if (!resolved) {
        resolved = true;
        if (onError) onError("Timeout en la conexión TCP");
      }
      client.destroy();
    });
  }

  static sendText(peerIp, peerPort, senderId, senderName, text, onResult, onError) {
    const payload = {
      action: "SHARE_TEXT",
      sender_id: senderId,
      sender_name: senderName,
      payload: text
    };
    
    TcpClient.sendFramedMessage(peerIp, peerPort, payload, 
      (response) => {
        if (response.status === "OK") {
          onResult(true, response.msg || response.result || "Mensaje enviado exitosamente");
        } else {
          onResult(false, response.msg || response.result || "Error remoto desconocido");
        }
      },
      (errorMsg) => {
        if (onError) onError(errorMsg);
      }
    );
  }

  /**
   * Transmite un archivo binario nativo (por chunks) hacia otro nodo P2P.
   */
  static async sendFile(peerIp, peerPort, senderId, senderName, fileUri, filename, filesize, sha256, onProgress, onResult, onError) {
    let resolved = false;

    const metaPayload = {
      action: "FILE_TRANSFER_META",
      sender_id: senderId,
      sender_name: senderName,
      filename: filename,
      filesize_bytes: filesize,
      sha256: sha256
    };

    const client = TcpSocket.createConnection({ port: peerPort, host: peerIp, timeout: 5000 }, () => {
      // 1. Enviar metadata
      try {
        const payloadStr = JSON.stringify(metaPayload);
        const payloadBuf = Buffer.from(payloadStr, 'utf8');
        const lengthBuf = Buffer.alloc(4);
        lengthBuf.writeUInt32BE(payloadBuf.length, 0);
        client.write(Buffer.concat([lengthBuf, payloadBuf]));
      } catch (err) {
        if (!resolved) { resolved = true; onError("Error enviando metadata: " + err.message); }
        client.destroy();
      }
    });

    let receiveBuffer = Buffer.alloc(0);
    let expectedLength = null;

    client.on('data', async (data) => {
      // Leer respuesta ACK READY
      receiveBuffer = Buffer.concat([receiveBuffer, data]);
      if (expectedLength === null && receiveBuffer.length >= 4) {
        expectedLength = receiveBuffer.readUInt32BE(0);
        receiveBuffer = receiveBuffer.slice(4);
      }

      if (expectedLength !== null && receiveBuffer.length >= expectedLength) {
        const payloadBuf = receiveBuffer.slice(0, expectedLength);
        try {
          const response = JSON.parse(payloadBuf.toString('utf8'));
          if (response.status === "READY") {
            // El servidor remoto aceptó, comenzar a streamear bytes crudos
            await TcpClient._streamFileBytes(client, fileUri, filesize, onProgress, onResult, onError, () => {
              if (!resolved) { resolved = true; }
            });
          } else {
            if (!resolved) { resolved = true; onError("Servidor rechazó el archivo: " + response.msg); client.destroy(); }
          }
        } catch (e) {
          if (!resolved) { resolved = true; onError("Error JSON ACK: " + e.message); client.destroy(); }
        }
        
        // Evitamos que vuelva a procesar data si se envían más ACKs
        expectedLength = null;
        receiveBuffer = Buffer.alloc(0);
      }
    });

    client.on('error', (error) => {
      if (!resolved) { resolved = true; onError("Error TCP Archivo: " + error.message); }
      client.destroy();
    });
    
    client.on('timeout', () => {
      if (!resolved) { resolved = true; onError("Timeout enviando archivo"); }
      client.destroy();
    });
  }

  static async _streamFileBytes(client, fileUri, totalSize, onProgress, onResult, onError, resolveCallback) {
    const CHUNK_SIZE = 16384; // 16KB por ciclo para no congelar la UI de React Native
    let offset = 0;

    try {
      while (offset < totalSize) {
        const lengthToRead = Math.min(CHUNK_SIZE, totalSize - offset);
        
        // Leer chunk como Base64 desde el sistema de archivos nativo
        const base64Chunk = await FileSystem.readAsStringAsync(fileUri, {
          encoding: FileSystem.EncodingType.Base64,
          position: offset,
          length: lengthToRead
        });

        // Escribir bytes puros en el socket
        const binChunk = Buffer.from(base64Chunk, 'base64');
        client.write(binChunk);

        offset += lengthToRead;
        if (onProgress) onProgress(offset, totalSize);
      }
      
      onResult(true, "Archivo transferido al nodo remoto.");
      resolveCallback();
      client.destroy();
      
    } catch (e) {
      onError("Error leyendo o enviando chunks: " + e.message);
      resolveCallback();
      client.destroy();
    }
  }
}
