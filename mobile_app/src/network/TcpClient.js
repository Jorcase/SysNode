import TcpSocket from 'react-native-tcp-socket';
import { createFramedMessage } from './Protocol';

export class TcpClient {
  constructor(ip, port) {
    this.ip = ip;
    this.port = port;
    this.client = null;
    this.isConnected = false;
  }

  // Se conecta al nodo destino
  connect(onConnect, onError, onClose) {
    if (this.client) {
      this.client.destroy();
    }

    this.client = TcpSocket.createConnection({
      port: this.port,
      host: this.ip,
      timeout: 5000,
    }, () => {
      this.isConnected = true;
      if (onConnect) onConnect();
    });

    this.client.on('error', (error) => {
      console.log(`[TCP Client] Error conectando a ${this.ip}:${this.port} ->`, error);
      this.isConnected = false;
      if (onError) onError(error);
    });

    this.client.on('close', () => {
      this.isConnected = false;
      this.client = null;
      if (onClose) onClose();
    });
  }

  // Envía un objeto JSON empaquetado con Framing y HMAC
  sendMessage(payloadObj) {
    return new Promise((resolve, reject) => {
      if (!this.isConnected || !this.client) {
        reject(new Error("No hay conexión TCP activa"));
        return;
      }

      try {
        if (global.myTcpPort && typeof payloadObj === 'object') {
          payloadObj.sender_tcp_port = global.myTcpPort;
        }
        const framedBuffer = createFramedMessage(payloadObj);
        this.client.write(framedBuffer, (err) => {
          if (err) {
            console.log(`[TCP Client] Error escribiendo en el socket:`, err);
            reject(err);
          } else {
            resolve();
          }
        });
      } catch (e) {
        console.error("[TCP Client] Error al empaquetar el mensaje:", e);
        reject(e);
      }
    });
  }

  // Envía un mensaje y espera la respuesta JSON del servidor remoto (p.ej. resultados de comandos)
  sendMessageWithResponse(payloadObj) {
    return new Promise((resolve, reject) => {
      if (!this.isConnected || !this.client) {
        reject(new Error("No hay conexión TCP activa"));
        return;
      }

      const { parseFramedMessage } = require('./Protocol');
      const { Buffer } = require('buffer');
      let responseBuffer = Buffer.alloc(0);

      const onData = (data) => {
        responseBuffer = Buffer.concat([responseBuffer, data]);
        const parsed = parseFramedMessage(responseBuffer);
        if (parsed && !parsed.error) {
          if (this.client) this.client.removeListener('data', onData);
          resolve(parsed.message);
        }
      };

      this.client.on('data', onData);

      try {
        if (global.myTcpPort && typeof payloadObj === 'object') {
          payloadObj.sender_tcp_port = global.myTcpPort;
        }
        const framedBuffer = createFramedMessage(payloadObj);
        this.client.write(framedBuffer, (err) => {
          if (err) {
            if (this.client) this.client.removeListener('data', onData);
            reject(err);
          }
        });
      } catch (e) {
        if (this.client) this.client.removeListener('data', onData);
        reject(e);
      }
    });
  }

  // Transmite un archivo binario (foto, documento) a un nodo remoto con FILE_TRANSFER_META + streaming
  sendFile(fileUri, filename, senderId, senderName) {
    return new Promise(async (resolve, reject) => {
      try {
        const FileSystem = require('expo-file-system/legacy');
        const { Buffer } = require('buffer');
        const { createFramedMessage, parseFramedMessage } = require('./Protocol');

        const CryptoJS = require('crypto-js');
        const base64Content = await FileSystem.readAsStringAsync(fileUri, {
          encoding: FileSystem.EncodingType.Base64
        });
        const fileBuffer = Buffer.from(base64Content, 'base64');
        const filesize = fileBuffer.length;

        // Calcular firma de integridad SHA-256 en formato hex
        const wordArr = CryptoJS.enc.Base64.parse(base64Content);
        const fileSha256 = CryptoJS.SHA256(wordArr).toString(CryptoJS.enc.Hex);

        this.connect(
          () => {
            let responseBuffer = Buffer.alloc(0);

            const onData = (data) => {
              responseBuffer = Buffer.concat([responseBuffer, data]);
              const parsed = parseFramedMessage(responseBuffer);
              if (parsed && !parsed.error) {
                const payload = parsed.message;
                if (payload && (payload.status === 'READY' || payload.action === 'FILE_TRANSFER_ACK')) {
                  if (this.client) this.client.removeListener('data', onData);
                  // Servidor listo! Enviar el buffer binario
                  this.client.write(fileBuffer, (err) => {
                    if (err) {
                      reject(err);
                    } else {
                      resolve({ success: true, filename, filesize, sha256: fileSha256 });
                    }
                  });
                }
              }
            };

            this.client.on('data', onData);

            const metaPayload = {
              action: "FILE_TRANSFER_META",
              sender_id: senderId,
              sender_name: senderName,
              filename: filename,
              filesize_bytes: filesize,
              sha256: fileSha256
            };

            const framedMeta = createFramedMessage(metaPayload);
            this.client.write(framedMeta, (err) => {
              if (err) {
                if (this.client) this.client.removeListener('data', onData);
                reject(err);
              }
            });
          },
          (err) => reject(err)
        );
      } catch (e) {
        reject(e);
      }
    });
  }

  disconnect() {
    if (this.client) {
      this.client.destroy();
      this.client = null;
      this.isConnected = false;
    }
  }
}
