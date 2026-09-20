import TcpSocket from 'react-native-tcp-socket';
import { createFramedMessage } from './Protocol';
import { Buffer } from 'buffer';
import { parseFramedMessage } from './Protocol';

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
      let tempFilePath = null;
      let fileWritePromise = Promise.resolve();
      const RNFS = require('react-native-fs');

      socket.on('data', async (data) => {
        receiveBuffer = Buffer.concat([receiveBuffer, data]);

        if (isReceivingFile) {
          const bytesNeeded = fileMeta.filesize_bytes - bytesReceived;
          const bytesToExtract = Math.min(bytesNeeded, receiveBuffer.length);
          const fileData = receiveBuffer.slice(0, bytesToExtract);
          
          bytesReceived += fileData.length;
          receiveBuffer = receiveBuffer.slice(bytesToExtract);
          
          const currentMeta = fileMeta;
          const currentTempPath = tempFilePath;
          const isLastChunk = (bytesReceived >= fileMeta.filesize_bytes);
          
          fileWritePromise = fileWritePromise.then(async () => {
            try {
              if (fileData.length > 0) {
                await RNFS.appendFile(currentTempPath, fileData.toString('base64'), 'base64');
              }
              
              if (isLastChunk) {
                const destDir = RNFS.DocumentDirectoryPath + '/SysNode_Received';
                await RNFS.mkdir(destDir);
                const finalPath = destDir + '/' + currentMeta.filename;
                
                if (await RNFS.exists(finalPath)) {
                  await RNFS.unlink(finalPath);
                }
                await RNFS.moveFile(currentTempPath, finalPath);

                if (this.onMessageReceived) {
                  this.onMessageReceived({
                    type: "FILE",
                    sender: currentMeta.sender_name,
                    text: `Archivo recibido: ${currentMeta.filename}`,
                    uri: 'file://' + finalPath
                  });
                }
              }
            } catch(e) {
              console.error("[TCP Server] Error escribiendo chunk:", e);
            }
          });
          
          if (isLastChunk) {
            isReceivingFile = false;
            fileMeta = null;
            bytesReceived = 0;
            tempFilePath = null;
          }
          
          if (receiveBuffer.length === 0) return;
        }

        // Modo Framing (Mensajes JSON)
        let parsed;
        while ((parsed = parseFramedMessage(receiveBuffer)) !== null) {
          if (parsed.error) {
            console.error("[TCP Server] Error parseando trama:", parsed.error);
            // Si hay un error fatal de framing (ej. mal HMAC), en el protocolo original 
            // cerramos el socket por seguridad o limpiamos el buffer
            receiveBuffer = Buffer.alloc(0);
            break;
          }

          // Mensaje parseado correctamente!
          const payload = parsed.message;
          receiveBuffer = parsed.remainingBuffer; // Lo que sobra para la sig. vuelta

          if (payload.type === 'FILE_METADATA' || payload.action === 'FILE_TRANSFER_META') {
            isReceivingFile = true;
            fileMeta = payload;
            bytesReceived = 0;
            tempFilePath = RNFS.CachesDirectoryPath + '/temp_receive_' + Date.now() + '.tmp';
            // Crear el archivo vacio para asegurarnos que appendFile no falle si es la primera vez
            await RNFS.writeFile(tempFilePath, '', 'utf8');
            console.log(`[TCP Server] Preparando recepción de archivo: ${fileMeta.filename || 'unknown'} (${fileMeta.filesize_bytes || 0} bytes)`);
            this.handleIncomingMessage(socket, payload, () => {});
            continue; // Esperar los bytes crudos
          }

          // Si es un mensaje de texto normal u otro comando
          await this.handleIncomingMessage(socket, payload, null);
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

  async handleIncomingMessage(socket, payload, onFileMetaReady) {
    const action = payload.action;
    const senderId = payload.sender_id || "unknown";
    const senderName = payload.sender_name || "Unknown";
    const { MessageStorage } = require('./MessageStorage');

    if (action !== "PING_NODE" && action !== "PAIRING_REQ" && action !== "PAIRING_RESP" && action !== "UNPAIR_REQ") {
      const trustToken = payload.trust_token || "";
      const isTrusted = await MessageStorage.verifyDeviceTrust(senderId, trustToken);
      if (!isTrusted) {
        console.warn(`[TCP Server] 🚨 ACCESO DENEGADO: Intento de acción '${action}' desde nodo no emparejado ${senderName} (${senderId}).`);
        this._sendAck(socket, { status: "ERROR", msg: "NOT_PAIRED" });
        return;
      }
    }

    if (action === "PAIRING_REQ") {
      if (this.onMessageReceived) {
        this.onMessageReceived({
          type: "PAIRING_REQ",
          sender: senderName,
          sender_id: senderId,
          peer_ip: socket.remoteAddress,
          trust_token: payload.trust_token || "",
          ...payload
        });
      }
      this._sendAck(socket, { status: "OK", msg: "Pairing request received." });
    }
    else if (action === "PAIRING_RESP") {
      const accepted = payload.accepted || false;
      const trustToken = payload.trust_token || "";
      
      if (accepted && trustToken) {
        await MessageStorage.setDevicePaired(senderId, true, trustToken);
        console.log(`[TCP Server] Dispositivo ${senderId} aceptó la vinculación.`);
      } else {
        await MessageStorage.setDevicePaired(senderId, false, null);
        console.log(`[TCP Server] Dispositivo ${senderId} rechazó la vinculación.`);
      }
      
      if (this.onMessageReceived) {
        this.onMessageReceived({
          type: "PAIRING_RESP",
          sender: senderName,
          sender_id: senderId,
          peer_ip: socket.remoteAddress,
          accepted: accepted,
          ...payload
        });
      }
      this._sendAck(socket, { status: "OK", msg: "Pairing response acknowledged." });
    }
    else if (action === "UNPAIR_REQ") {
      await MessageStorage.setDevicePaired(senderId, false, null);
      console.log(`[TCP Server] El dispositivo ${senderId} ha revocado la vinculación.`);
      
      if (this.onMessageReceived) {
        this.onMessageReceived({
          type: "UNPAIR_REQ",
          sender: senderName,
          sender_id: senderId,
          peer_ip: socket.remoteAddress,
          ...payload
        });
      }
      this._sendAck(socket, { status: "OK", msg: "Unpaired." });
    }
    else if (action === "SHARE_TEXT") {
      if (this.onMessageReceived) {
        this.onMessageReceived({
          type: "TEXT",
          sender: senderName,
          text: payload.payload,
          peer_ip: socket.remoteAddress,
          ...payload
        });
      }
      this._sendAck(socket, { status: "OK", msg: "Texto recibido por el celular" });
    } 
    else if (action === "EDIT_MSG") {
      const { MessageStorage } = require('./MessageStorage');
      const senderId = payload.sender_id || "unknown";
      const msgUuid = payload.msg_uuid;
      const newText = payload.new_text;
      
      if (msgUuid && newText) {
        MessageStorage.updateMessageText(senderId, msgUuid, newText);
      }
      
      if (this.onMessageReceived) {
        this.onMessageReceived({
          type: "MSG_EDITED",
          sender_id: senderId,
          sender: payload.sender_name || "Unknown",
          msg_uuid: msgUuid,
          new_text: newText,
          ...payload
        });
      }
      this._sendAck(socket, { status: "OK", msg: "Mensaje editado en el celular." });
    } 
    else if (action === "FILE_TRANSFER_META") {
      // El servidor remoto quiere enviar un archivo. Respondemos READY para que comience a mandar chunks.
      if (onFileMetaReady) onFileMetaReady(payload);
      this._sendAck(socket, { status: "READY", msg: "Celular listo para recibir archivo" });
    }
    else if (action === "REMOTE_CMD") {
      // El celular rechaza la ejecución de comandos SysAdmin nativos
      this._sendAck(socket, { 
        status: "ERROR", 
        msg: "El dispositivo móvil no soporta comandos SysAdmin (Bloqueo, Apagado)." 
      });
    }
    else if (action === "REMOTE_BASH_CMD") {
      this._sendAck(socket, { 
        status: "ERROR", 
        msg: "El dispositivo móvil no soporta comandos bash." 
      });
    }
    else if (action === "PING_NODE") {
      const { getIdentity } = require('./MyIdentity');
      const identity = getIdentity();
      
      this._sendAck(socket, { 
        status: "OK", 
        node_id: identity.node_id,
        hostname: identity.node_name,
        os: "Android"
      });
    }
    else {
      // Si es otro comando o formato viejo
      if (payload.type === "TEXT" && !action) {
        if (this.onMessageReceived) this.onMessageReceived(payload);
        this._sendAck(socket, { status: "OK", msg: "Recibido" });
      } else {
        console.warn(`[TCP Server] Acción no reconocida: ${action}`);
        this._sendAck(socket, { status: "ERROR", msg: `Acción no soportada por el celular: ${action}` });
      }
    }
  }

  _sendAck(socket, payloadObj) {
    try {
      const framedBuffer = createFramedMessage(payloadObj);
      socket.write(framedBuffer);
    } catch (e) {
      console.error("[TCP Server] Error enviando ACK:", e);
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
