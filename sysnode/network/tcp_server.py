from sysnode.network.protocol import ActionType
import os
import socket
import queue
import threading
import logging
from typing import Dict, Any
from sysnode.config import BIND_ALL_IP, DEFAULT_TCP_PORT, SOCKET_TIMEOUT_SEC, SYSTEM_OS
from sysnode.network.framing import receive_framed_message, send_framed_message
from sysnode.core.security import execute_whitelisted_command, sanitize_filename
from sysnode.network.file_transfer import receive_file_bytes
from sysnode.network.terminal_server import terminal_manager

logger = logging.getLogger(__name__)


class TCPServer(threading.Thread):
    # Servidor TCP multihilo que escucha peticiones entrantes de otros pares en la LAN.
    # Por cada cliente aceptado, delega la atención a un hilo TCPClientHandlerThread.
    def __init__(self, tcp_port: int, event_callback, node_id: str = "unknown", node_name: str = None, download_dir_getter=None, is_paired_checker=None):
        super().__init__(daemon=True, name="TCPServerThread")
        self.tcp_port = tcp_port
        self.event_callback = event_callback
        self.node_id = node_id
        self.node_name = node_name
        self.download_dir_getter = download_dir_getter
        self.is_paired_checker = is_paired_checker
        self._stop_event = threading.Event()
        self.running = False
        self.server_sock = None

    def run(self) -> None:
        self.running = True
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.settimeout(SOCKET_TIMEOUT_SEC)

        try:
            self.server_sock.bind((BIND_ALL_IP, self.tcp_port))
            self.server_sock.listen(5)
            logger.info(f"TCPServer escuchando en {BIND_ALL_IP}:{self.tcp_port}")
        except Exception as e:
            logger.error(f"Error al bindear TCPServer en puerto {self.tcp_port}: {e}")
            self.running = False
            return

        while not self._stop_event.is_set():
            try:
                client_sock, addr = self.server_sock.accept()
                peer_ip = addr[0]
                logger.debug(f"Nueva conexión TCP aceptada desde {peer_ip}:{addr[1]}")

                # Lanza worker thread para atender a este cliente específico
                worker = TCPClientHandlerThread(
                    client_sock=client_sock,
                    peer_ip=peer_ip,
                    event_callback=self.event_callback,
                    node_id=self.node_id,
                    node_name=self.node_name,
                    download_dir_getter=self.download_dir_getter,
                    is_paired_checker=self.is_paired_checker
                )
                worker.start()

            except socket.timeout:
                pass
            except Exception as e:
                if not self._stop_event.is_set():
                    logger.error(f"Excepción en TCPServer accept: {e}")

        if self.server_sock:
            self.server_sock.close()
        self.running = False
        logger.info("TCPServer detenido.")

    def stop(self) -> None:
        #Solicita la detención del servidor TCP.
        self._stop_event.set()


class TCPClientHandlerThread(threading.Thread):
    #Hilo worker que atiende la comunicación con una conexión TCP entrante específica.
    #Recibe la trama con framing, determina la acción y responde si corresponde.

    def __init__(self, client_sock: socket.socket, peer_ip: str, event_callback, node_id: str = "unknown", node_name: str = None, download_dir_getter=None, is_paired_checker=None):
        super().__init__(daemon=True, name=f"TCPWorker-{peer_ip}")
        self.client_sock = client_sock
        self.peer_ip = peer_ip
        self.event_callback = event_callback
        self.node_id = node_id
        self.node_name = node_name
        self.download_dir_getter = download_dir_getter
        self.is_paired_checker = is_paired_checker

    def run(self) -> None:
        keep_socket_open = False
        active_session_id = None
        socket_authenticated = False
        try:
            self.client_sock.settimeout(10.0)  # Timeout de inactividad por socket
            while True:
                try:
                    payload = receive_framed_message(self.client_sock)
                except socket.timeout:
                    if keep_socket_open:
                        continue
                    break
                except Exception:
                    break

                if not payload:
                    break

                action = payload.get("action")
                sender_id = payload.get("sender_id", "unknown")
                sender_name = payload.get("sender_name", "Desconocido")
                sender_tcp_port = payload.get("sender_tcp_port")

                logger.info(f"Mensaje TCP Recibido | Acción: '{action}' | Emisor: {sender_name} ({self.peer_ip})")

                # Verificar pairing para todas las acciones excepto PING, PAIRING_REQ, PAIRING_RESP, UNPAIR_REQ
                if not socket_authenticated and action not in [ActionType.PING_NODE, ActionType.PAIRING_REQ, ActionType.PAIRING_RESP, ActionType.UNPAIR_REQ]:
                    trust_token = payload.get("trust_token", "")
                    if self.is_paired_checker and not self.is_paired_checker(sender_id, trust_token):
                        logger.warning(f"ACCESO DENEGADO: Intento de acción '{action}' desde nodo no emparejado {sender_name} ({sender_id}).")
                        send_framed_message(self.client_sock, {"status": "ERROR", "msg": "NOT_PAIRED"})
                        break
                    else:
                        socket_authenticated = True

                # Caso Ping Node (conexiones manuales)
                if action == ActionType.PING_NODE:
                    response = {
                        "status": "OK",
                        "node_id": self.node_id,
                        "hostname": self.node_name,
                        "os": SYSTEM_OS,
                    }
                    send_framed_message(self.client_sock, response)
                    break

                # PAIRING: Solicitud de Emparejamiento
                elif action == ActionType.PAIRING_REQ:
                    trust_token = payload.get("trust_token", "")
                    self.event_callback({
                        "event": "PAIRING_REQUEST_RECEIVED",
                        "sender_id": sender_id,
                        "sender_name": sender_name,
                        "peer_ip": self.peer_ip,
                        "sender_tcp_port": sender_tcp_port,
                        "trust_token": trust_token
                    })
                    send_framed_message(self.client_sock, {"status": "OK", "msg": "Pairing request received."})
                    break

                # PAIRING: Respuesta de Emparejamiento
                elif action == ActionType.PAIRING_RESP:
                    trust_token = payload.get("trust_token", "")
                    accepted = payload.get("accepted", False)
                    self.event_callback({
                        "event": "PAIRING_RESPONSE_RECEIVED",
                        "sender_id": sender_id,
                        "sender_name": sender_name,
                        "peer_ip": self.peer_ip,
                        "sender_tcp_port": sender_tcp_port,
                        "trust_token": trust_token,
                        "accepted": accepted
                    })
                    send_framed_message(self.client_sock, {"status": "OK", "msg": "Pairing response acknowledged."})
                    break

                # UNPAIR: Solicitud de Desvinculación
                elif action == ActionType.UNPAIR_REQ:
                    self.event_callback({
                        "event": "UNPAIR_REQUEST_RECEIVED",
                        "sender_id": sender_id,
                        "sender_name": sender_name,
                        "peer_ip": self.peer_ip,
                        "sender_tcp_port": sender_tcp_port
                    })
                    send_framed_message(self.client_sock, {"status": "OK", "msg": "Unpaired."})
                    break

                # Caso Compartir Texto
                elif action == ActionType.SHARE_TEXT:
                    text_content = payload.get("payload", "")
                    msg_uuid = payload.get("msg_uuid", None)
                    self.event_callback({
                        "event": "TEXT_RECEIVED",
                        "sender_id": sender_id,
                        "sender_name": sender_name,
                        "peer_ip": self.peer_ip,
                        "sender_tcp_port": sender_tcp_port,
                        "text": text_content,
                        "msg_uuid": msg_uuid
                    })
                    # Responder ACK al cliente
                    send_framed_message(self.client_sock, {"status": "OK", "msg": f"Texto recibido por {self.node_name}."})
                    break

                # Caso Editar Texto
                elif action == ActionType.EDIT_MSG:
                    msg_uuid = payload.get("msg_uuid", "")
                    new_text = payload.get("new_text", "")
                    self.event_callback({
                        "event": "MSG_EDITED",
                        "sender_id": sender_id,
                        "sender_name": sender_name,
                        "peer_ip": self.peer_ip,
                        "msg_uuid": msg_uuid,
                        "new_text": new_text
                    })
                    send_framed_message(self.client_sock, {"status": "OK", "msg": f"Mensaje editado por {self.node_name}."})
                    break

                # Caso Ejecución de Comando Remoto
                elif action == ActionType.REMOTE_CMD:
                    command_key = payload.get("command", "")
                    logger.info(f"Solicitud de comando remoto: '{command_key}' enviado por {sender_name}")

                    success, result_msg = execute_whitelisted_command(command_key, receiver_name=self.node_name)
                    self.event_callback({
                        "event": "COMMAND_RECEIVED",
                        "command": command_key,
                        "sender_id": sender_id,
                        "sender_name": sender_name,
                        "peer_ip": self.peer_ip,
                        "sender_tcp_port": sender_tcp_port,
                        "success": success,
                        "result": result_msg
                    })
                    send_framed_message(self.client_sock, {
                        "status": "OK" if success else "ERROR",
                        "command": command_key,
                        "result": result_msg
                    })
                    break

                elif action == ActionType.REMOTE_BASH_CMD:
                    bash_command = payload.get("bash_command", "")
                    is_bg = payload.get("is_background", False)
                    logger.info(f"Solicitud de comando BASH: '{bash_command}' enviado por {sender_name} (Background: {is_bg})")
                    from sysnode.core.security import execute_custom_bash_command
                    success, result_msg = execute_custom_bash_command(bash_command, receiver_name=self.node_name, is_background=is_bg)

                    self.event_callback({
                        "event": "COMMAND_RECEIVED",
                        "command": bash_command,
                        "sender_id": sender_id,
                        "sender_name": sender_name,
                        "peer_ip": self.peer_ip,
                        "sender_tcp_port": sender_tcp_port,
                        "success": success,
                        "result": result_msg
                    })

                    send_framed_message(self.client_sock, {
                        "status": "OK" if success else "ERROR",
                        "command": bash_command,
                        "result": result_msg
                    })
                    break

                # Caso Transferencia de Archivo
                elif action == ActionType.FILE_TRANSFER_META:
                    raw_filename = payload.get("filename", "unknown_file")
                    filesize_bytes = payload.get("filesize_bytes", 0)
                    sha256 = payload.get("sha256", "")

                    clean_filename = sanitize_filename(raw_filename)
                    received_dir = self.download_dir_getter() if self.download_dir_getter else os.path.abspath("SysNode_Received")
                    os.makedirs(received_dir, exist_ok=True)
                    temp_path = os.path.join(received_dir, f"{clean_filename}.tmp")
                    final_path = os.path.join(received_dir, clean_filename)

                    logger.info(f"Solicitud de archivo: '{clean_filename}' ({filesize_bytes} bytes) desde {sender_name}")

                    # Responder ACK de que el servidor está listo para recibir el flujo binario
                    send_framed_message(self.client_sock, {
                        "action": "FILE_TRANSFER_ACK",
                        "status": "READY"
                    })
                    # Callback para actualizar el progreso en vivo
                    def progress_cb(received_bytes, total):
                        self.event_callback({
                            "event": "FILE_PROGRESS",
                            "direction": "RECEIVING",
                            "filename": clean_filename,
                            "current": received_bytes,
                            "total": total
                        })
                    # Iniciar lectura del flujo binario en chunks de 4KB
                    success, result_msg = receive_file_bytes(
                        sock=self.client_sock,
                        temp_path=temp_path,
                        final_path=final_path,
                        total_bytes=filesize_bytes,
                        expected_sha256=sha256,
                        progress_callback=progress_cb
                    )

                    self.event_callback({
                        "event": "FILE_RECEIVED",
                        "sender_id": sender_id,
                        "sender_name": sender_name,
                        "peer_ip": self.peer_ip,
                        "filename": clean_filename,
                        "filepath": final_path,
                        "success": success,
                        "msg": result_msg
                    })
                    break

                # Caso Terminal Remota 
                elif action == ActionType.TERM_INIT:
                    cols = payload.get("cols", 80)
                    rows = payload.get("rows", 24)
                    session_id, _ = terminal_manager.create_session(self.client_sock, cols, rows)
                    
                    session = terminal_manager.sessions.get(session_id)
                    if session:
                        session.authenticated = True
                        success = session.start_shell()
                        send_framed_message(self.client_sock, {
                            "status": "OK" if success else "ERROR",
                            "session_id": session_id,
                            "msg": "Sesión Terminal autenticada e iniciada." if success else "Error iniciando PTY."
                        })
                        if success:
                            keep_socket_open = True
                            active_session_id = session_id
                        else:
                            break
                    else:
                        send_framed_message(self.client_sock, {"status": "ERROR", "msg": "Error interno al crear sesión PTY."})
                        break

                elif action == ActionType.TERM_STDIN:
                    session_id = payload.get("session_id", "")
                    data = payload.get("data", "")
                    terminal_manager.handle_stdin(session_id, data)

                elif action == ActionType.TERM_RESIZE:
                    session_id = payload.get("session_id", "")
                    cols = payload.get("cols", 80)
                    rows = payload.get("rows", 24)
                    terminal_manager.handle_resize(session_id, cols, rows)

                elif action == ActionType.TERM_CLOSE:
                    session_id = payload.get("session_id", "")
                    terminal_manager.close_session(session_id)
                    break

                else:
                    logger.warning(f"Acción TCP no reconocida: {action}")
                    send_framed_message(self.client_sock, {"status": "ERROR", "msg": f"Acción '{action}' no soportada."})
                    break

        except Exception as e:
            logger.error(f"Error procesando solicitud TCP desde {self.peer_ip}: {e}")
        finally:
            if active_session_id:
                try:
                    terminal_manager.close_session(active_session_id)
                except Exception:
                    pass
            if not keep_socket_open:
                try:
                    self.client_sock.close()
                except Exception:
                    pass
