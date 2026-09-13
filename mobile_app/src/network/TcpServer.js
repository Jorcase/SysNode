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
            fileBuffer = Buffer.alloc(0);
            console.log(`[TCP Server] Preparando recepción de archivo: ${fileMeta.filename || 'unknown'} (${fileMeta.filesize_bytes || 0} bytes)`);
            this.handleIncomingMessage(socket, payload, () => {});
            continue; // Esperar los bytes crudos
          }

          // Si es un mensaje de texto normal u otro comando
          this.handleIncomingMessage(socket, payload, null);
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

    if (action === "SHARE_TEXT") {
      if (this.onMessageReceived) {
        this.onMessageReceived({
          type: "TEXT",
          sender: payload.sender_name || "Unknown",
          text: payload.payload,
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
