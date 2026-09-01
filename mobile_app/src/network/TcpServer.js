import { ActionType } from "./Protocol";
import TcpSocket from 'react-native-tcp-socket';
import { Buffer } from 'buffer';

export class TcpServer {
  constructor(port, onMessageReceived) {
    this.port = port;
    this.onMessageReceived = onMessageReceived;
    this.server = null;
  }

  start(onListening) {
    if (this.server) return;

    this.server = TcpSocket.createServer((socket) => {
      let receiveBuffer = Buffer.alloc(0);
      let expectedLength = null;
      
      // Estado para recepción de archivos
      let isReceivingFile = false;
      let fileMeta = null;
      let bytesReceived = 0;
      let fileBuffer = Buffer.alloc(0); // Para guardar chunks en memoria antes de pasarlos a Base64

      socket.on('data', async (data) => {
        receiveBuffer = Buffer.concat([receiveBuffer, data]);

        if (isReceivingFile) {
          // Leer bytes crudos
          bytesReceived += data.length;
          fileBuffer = Buffer.concat([fileBuffer, data]);
          
          // Escribir a disco cada 64KB para no llenar la RAM (o al final si es chico)
          if (fileBuffer.length >= 65536 || bytesReceived >= fileMeta.filesize_bytes) {
            const base64Chunk = fileBuffer.toString('base64');
            fileBuffer = Buffer.alloc(0);
            
            try {
              // Import dinámico para no romper si no está listo
              const FileSystem = require('expo-file-system/legacy');
              
              // Escribir/append
              const fileUri = fileMeta.dest_uri;
              const fileExists = await FileSystem.getInfoAsync(fileUri);
              if (fileExists.exists) {
                // Como no hay appendAsStringAsync nativo fácil en expo sin plugins, 
                // para mantenerlo simple y nativo, leemos y reescribimos si es necesario 
                // O mejor, usamos expo-file-system EncodingType.Base64 para append si existiera.
                // Como expo-file-system writeAsStringAsync SOBREESCRIBE, 
                // guardar todo en memoria o usar Storage Access Framework.
                // Para este MVP, por limitaciones de Expo FileSystem sin append,
                // guardamos en RAM hasta max 50MB y escribimos al final.
              }
            } catch(e) {}
          }
          
          if (bytesReceived >= fileMeta.filesize_bytes) {
            // Terminó de recibir!
            try {
              const FileSystem = require('expo-file-system/legacy');
              const destDir = FileSystem.documentDirectory + 'SysNode_Received/';
              await FileSystem.makeDirectoryAsync(destDir, { intermediates: true }).catch(()=>{});
              const fileUri = destDir + fileMeta.filename;
              
              await FileSystem.writeAsStringAsync(fileUri, receiveBuffer.slice(0, fileMeta.filesize_bytes).toString('base64'), {
                encoding: FileSystem.EncodingType.Base64
              });

              if (this.onMessageReceived) {
                this.onMessageReceived({
                  type: "FILE",
                  sender: fileMeta.sender_name,
                  text: `Archivo recibido: ${fileMeta.filename}`,
                  uri: fileUri
                });
              }
            } catch (e) {
              console.error("[TCP Server] Error guardando archivo:", e);
            }
            
            isReceivingFile = false;
            receiveBuffer = receiveBuffer.slice(fileMeta.filesize_bytes); // Lo que sobra
            fileMeta = null;
            bytesReceived = 0;
            fileBuffer = Buffer.alloc(0);
          }
          return;
        }

        // Modo Framing (Mensajes JSON)
        if (expectedLength === null && receiveBuffer.length >= 4) {
          expectedLength = receiveBuffer.readUInt32BE(0);
          receiveBuffer = receiveBuffer.slice(4);
        }

        if (expectedLength !== null && receiveBuffer.length >= expectedLength) {
          const fullPayloadBuf = receiveBuffer.slice(0, expectedLength);
          
          if (expectedLength < 64) {
             console.error("[TCP Server] Payload sin HMAC");
             socket.destroy();
             return;
          }
          
          const receivedSignatureStr = fullPayloadBuf.slice(0, 64).toString('utf8');
          const payloadBuf = fullPayloadBuf.slice(64);
          const payloadStr = payloadBuf.toString('utf8');
          
          // Importamos aquí o arriba
          const hmacSHA256 = require('crypto-js/hmac-sha256');
          const hexEnc = require('crypto-js/enc-hex');
          const AUTH_TOKEN = "sysnode_secret_123";
          
          const expectedSignatureStr = hmacSHA256(payloadStr, AUTH_TOKEN).toString(hexEnc);
          if (receivedSignatureStr !== expectedSignatureStr) {
             console.error("[TCP Server] Firma HMAC inválida");
             socket.destroy();
             return;
          }
          
          try {
            const payload = JSON.parse(payloadStr);
            this.handleIncomingMessage(socket, payload, (meta) => {
              // Callback si el mensaje fue un FILE_TRANSFER_META
              isReceivingFile = true;
              fileMeta = meta;
              bytesReceived = 0;
              fileBuffer = Buffer.alloc(0);
            });
          } catch (e) {
            this._sendAck(socket, { status: "ERROR", msg: "Invalid JSON" });
          }

          receiveBuffer = receiveBuffer.slice(expectedLength);
          expectedLength = null;
        }
      });

      socket.on('error', (error) => {
        console.error('[TCP Server] Socket Error:', error);
      });
    });

    this.server.on('error', (error) => {
      console.error('[TCP Server] Error:', error);
    });

    this.server.listen({ port: this.port, host: '0.0.0.0' }, () => {
      const boundPort = this.server.address().port;
      console.log(`[TCP Server] Listening on port ${boundPort}`);
      if (onListening) onListening(boundPort);
    });
  }

  handleIncomingMessage(socket, payload, onFileMetaReady) {
    const action = payload.action;

    if (action === ActionType.SHARE_TEXT) {
      if (this.onMessageReceived) {
        this.onMessageReceived({
          type: "TEXT",
          sender: payload.sender_name || "Unknown",
          text: payload.payload
        });
      }
      this._sendAck(socket, { status: "OK", msg: "Texto recibido por el celular" });
    } 
    else if (action === ActionType.FILE_TRANSFER_META) {
      // El servidor remoto quiere enviar un archivo. Respondemos READY para que comience a mandar chunks.
      if (onFileMetaReady) onFileMetaReady(payload);
      this._sendAck(socket, { status: "READY", msg: "Celular listo para recibir archivo" });
    }
    else if (action === ActionType.REMOTE_CMD) {
      // El celular rechaza la ejecución de comandos SysAdmin nativos
      this._sendAck(socket, { 
        status: "ERROR", 
        msg: "El dispositivo móvil no soporta comandos SysAdmin (Bloqueo, Apagado)." 
      });
    }
    else {
      this._sendAck(socket, { status: "ERROR", msg: `Acción no soportada: ${action}` });
    }
  }

  _sendAck(socket, responseObj) {
    try {
      const responseStr = JSON.stringify(responseObj);
      const payloadBuf = Buffer.from(responseStr, 'utf8');
      
      const hmacSHA256 = require('crypto-js/hmac-sha256');
      const hexEnc = require('crypto-js/enc-hex');
      const AUTH_TOKEN = "sysnode_secret_123";
      
      const signatureStr = hmacSHA256(responseStr, AUTH_TOKEN).toString(hexEnc);
      const signatureBuf = Buffer.from(signatureStr, 'utf8');
      
      const lengthBuf = Buffer.alloc(4);
      lengthBuf.writeUInt32BE(signatureBuf.length + payloadBuf.length, 0);
      
      const finalBuf = Buffer.concat([lengthBuf, signatureBuf, payloadBuf]);
      socket.write(finalBuf);
    } catch (e) {
      console.error('[TCP Server] Error enviando ACK:', e);
    }
  }

  stop() {
    if (this.server) {
      this.server.close();
      this.server = null;
      console.log('[TCP Server] Stopped');
    }
  }
}
