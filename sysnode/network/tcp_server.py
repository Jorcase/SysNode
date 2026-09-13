from sysnode.network.protocol import ActionType
"""
SysNode - Servidor TCP Multihilo (Shared Board y Comandos Remotos)

Escucha en el puerto TCP 50001 (configurable) y lanza un hilo secundario por cada
conexión entrante (Worker Thread). Implementa el protocolo de framing para recibir
mensajes JSON seguros sin fragmentación.
"""

import os
import socket
import queue
import threading
import logging
from typing import Dict, Any

from sysnode.config import BIND_ALL_IP, DEFAULT_TCP_PORT, SOCKET_TIMEOUT_SEC
from sysnode.network.framing import receive_framed_message, send_framed_message
from sysnode.core.security import execute_whitelisted_command, sanitize_filename
from sysnode.network.file_transfer import receive_file_bytes

logger = logging.getLogger(__name__)


class TCPServer(threading.Thread):
    """
    Servidor TCP multihilo que escucha peticiones entrantes de otros pares en la LAN.
    Por cada cliente aceptado, delega la atención a un hilo TCPClientHandlerThread.
    """

    def __init__(self, tcp_port: int, event_callback, node_id: str = "unknown", node_name: str = None, download_dir_getter=None):
        super().__init__(daemon=True, name="TCPServerThread")
        self.tcp_port = tcp_port
        self.event_callback = event_callback
        self.node_id = node_id
        self.node_name = node_name
        self.download_dir_getter = download_dir_getter
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

                # Lanzar worker thread para atentar a este cliente específico
                worker = TCPClientHandlerThread(
                    client_sock=client_sock,
                    peer_ip=peer_ip,
                    event_callback=self.event_callback,
                    node_id=self.node_id,
                    node_name=self.node_name,
                    download_dir_getter=self.download_dir_getter
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
        """Solicita la detención del servidor TCP."""
        self._stop_event.set()


class TCPClientHandlerThread(threading.Thread):
    """
    Hilo worker que atiende la comunicación con una conexión TCP entrante específica.
    Recibe la trama con framing, determina la acción y responde si corresponde.
    """

    def __init__(self, client_sock: socket.socket, peer_ip: str, event_callback, node_id: str = "unknown", node_name: str = None, download_dir_getter=None):
        super().__init__(daemon=True, name=f"TCPWorker-{peer_ip}")
        self.client_sock = client_sock
        self.peer_ip = peer_ip
        self.event_callback = event_callback
        self.node_id = node_id
        self.node_name = node_name
        self.download_dir_getter = download_dir_getter

    def run(self) -> None:
        keep_socket_open = False
        active_session_id = None
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

                logger.info(f"Mensaje TCP Recibido | Acción: '{action}' | Emisor: {sender_name} ({self.peer_ip})")

                # Caso 0: Ping Node (para conexiones manuales)
                if action == ActionType.PING_NODE:
                    from sysnode.network.udp_beacon import SYSTEM_OS
                    response = {
                        "status": "OK",
                        "node_id": self.node_id,
                        "hostname": self.node_name,
                        "os": SYSTEM_OS,
                    }
                    send_framed_message(self.client_sock, response)
                    break

                # Caso 1: Compartir Texto (Shared Board)
                elif action == ActionType.SHARE_TEXT:
                    text_content = payload.get("payload", "")
                    msg_uuid = payload.get("msg_uuid", None)
                    self.event_callback({
                        "event": "TEXT_RECEIVED",
                        "sender_id": sender_id,
                        "sender_name": sender_name,
                        "peer_ip": self.peer_ip,
                        "text": text_content,
                        "msg_uuid": msg_uuid
                    })
                    # Responder ACK al cliente
                    send_framed_message(self.client_sock, {"status": "OK", "msg": f"Texto recibido por {self.node_name}."})
                    break

                # Caso 1.5: Editar Texto
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

                # Caso 2: Ejecución de Comando Remoto (SysAdmin)
                elif action == ActionType.REMOTE_CMD:
                    command_key = payload.get("command", "")
                    logger.info(f"Solicitud de comando remoto: '{command_key}' enviado por {sender_name}")

                    success, result_msg = execute_whitelisted_command(command_key, receiver_name=self.node_name)

                    # Notificar a la cola de eventos interna
                    self.event_callback({
                        "event": "COMMAND_RECEIVED",
                        "command": command_key,
                        "sender_id": sender_id,
                        "sender_name": sender_name,
                        "peer_ip": self.peer_ip,
                        "success": success,
                        "result": result_msg
                    })

                    # Responder al cliente emisor
                    send_framed_message(self.client_sock, {
                        "status": "OK" if success else "ERROR",
                        "command": command_key,
                        "result": result_msg
                    })
                    break

                elif action == ActionType.REMOTE_BASH_CMD:
                    logger.warning(f"🚨 ACCESO DENEGADO: Intento de ejecución BASH no autenticada desde {self.peer_ip} ({sender_name}).")
                    result_msg = "ACCESO DENEGADO: La ejecución de comandos shell arbitrarios está deshabilitada por políticas de seguridad de SysNode."
                    self.event_callback({
                        "event": "COMMAND_RECEIVED",
                        "command": "REMOTE_BASH_BLOCKED",
                        "sender_id": sender_id,
                        "sender_name": sender_name,
                        "peer_ip": self.peer_ip,
                        "success": False,
                        "result": result_msg
                    })
                    send_framed_message(self.client_sock, {
                        "status": "ERROR",
                        "command": "REMOTE_BASH_BLOCKED",
                        "result": result_msg
                    })
                    break

                # Caso 3: Transferencia de Archivo (File Drop)
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

                # Caso 4: Terminal Remota (SSH-Style PTY)
                elif action == ActionType.TERM_INIT:
                    self.client_sock.settimeout(120.0)  # Ampliar timeout a 2 minutos para el flujo de PIN/terminal
                    from sysnode.network.terminal_server import terminal_manager
                    cols = payload.get("cols", 80)
                    rows = payload.get("rows", 24)
                    session_id, pin = terminal_manager.create_session(self.client_sock, cols, rows)
                    active_session_id = session_id
                    keep_socket_open = True
                    
                    self.event_callback({
                        "event": "TERMINAL_PIN_REQUEST",
                        "session_id": session_id,
                        "pin": pin,
                        "sender_name": sender_name,
                        "peer_ip": self.peer_ip
                    })
                    
                    send_framed_message(self.client_sock, {
                        "status": "PIN_REQUIRED",
                        "session_id": session_id,
                        "msg": f"Ingresá el código PIN desplegado en {self.node_name} para habilitar la terminal."
                    })

                elif action == ActionType.TERM_AUTH:
                    from sysnode.network.terminal_server import terminal_manager
                    session_id = payload.get("session_id", "")
                    pin = payload.get("pin", "")
                    success = terminal_manager.authenticate_session(session_id, pin)
                    send_framed_message(self.client_sock, {
                        "status": "OK" if success else "ERROR",
                        "session_id": session_id,
                        "msg": "Sesión Terminal autenticada e iniciada." if success else "PIN inválido."
                    })
                    if success:
                        keep_socket_open = True
                        active_session_id = session_id
                    else:
                        break

                elif action == ActionType.TERM_STDIN:
                    from sysnode.network.terminal_server import terminal_manager
                    session_id = payload.get("session_id", "")
                    data = payload.get("data", "")
                    terminal_manager.handle_stdin(session_id, data)

                elif action == ActionType.TERM_RESIZE:
                    from sysnode.network.terminal_server import terminal_manager
                    session_id = payload.get("session_id", "")
                    cols = payload.get("cols", 80)
                    rows = payload.get("rows", 24)
                    terminal_manager.handle_resize(session_id, cols, rows)

                elif action == ActionType.TERM_CLOSE:
                    from sysnode.network.terminal_server import terminal_manager
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
                    from sysnode.network.terminal_server import terminal_manager
                    terminal_manager.close_session(active_session_id)
                except Exception:
                    pass
            if not keep_socket_open:
                try:
                    self.client_sock.close()
                except Exception:
                    pass
