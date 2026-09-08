from sysnode.network.protocol import ActionType
"""
SysNode - Cliente TCP para Conexiones Salientes

Permite establecer conexiones síncronas a otros nodos en la LAN para enviar
mensajes de texto (Shared Board) y solicitudes de comandos remotos usando el protocolo de framing.
"""

import os
import socket
import logging
from typing import Dict, Any, Tuple

from sysnode.config import SOCKET_TIMEOUT_SEC
from sysnode.network.framing import send_framed_message, receive_framed_message
from sysnode.network.file_transfer import calculate_file_sha256, stream_file_bytes

logger = logging.getLogger(__name__)


class TCPClient:
    """
    Cliente TCP encargada de conectarse a pares remotos y transmitir tramas con framing.
    """

    @staticmethod
    def send_text(peer_ip: str, peer_port: int, sender_id: str, sender_name: str, text: str, msg_uuid: str = None) -> Tuple[bool, str]:
        """Envía un texto al Shared Board de un nodo remoto."""
        payload: Dict[str, Any] = {
            "action": ActionType.SHARE_TEXT,
            "sender_id": sender_id,
            "sender_name": sender_name,
            "payload": text
        }
        if msg_uuid:
            payload["msg_uuid"] = msg_uuid
            
        return TCPClient._connect_and_send(peer_ip, peer_port, payload)

    @staticmethod
    def ping_node(peer_ip: str, peer_port: int, sender_id: str, sender_name: str) -> Tuple[bool, Dict[str, Any]]:
        """Pings a remote node to retrieve its identity info."""
        payload: Dict[str, Any] = {
            "action": ActionType.PING_NODE,
            "sender_id": sender_id,
            "sender_name": sender_name
        }
        # Modified _connect_and_send behavior since we expect a JSON dictionary response back
        # Actually _connect_and_send returns (success, error_msg_or_status), but we need the dict.
        # Let's write a custom connection block.
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(SOCKET_TIMEOUT_SEC)
                sock.connect((peer_ip, peer_port))
                send_framed_message(sock, payload)
                response = receive_framed_message(sock)
                if response and response.get("status") == "OK":
                    return True, response
                return False, {}
        except Exception as e:
            return False, {}

    @staticmethod
    def edit_text(peer_ip: str, peer_port: int, sender_id: str, sender_name: str, msg_uuid: str, new_text: str) -> Tuple[bool, str]:
        """Solicita la edición de un mensaje previamente enviado al nodo remoto."""
        payload: Dict[str, Any] = {
            "action": ActionType.EDIT_MSG,
            "sender_id": sender_id,
            "sender_name": sender_name,
            "msg_uuid": msg_uuid,
            "new_text": new_text
        }
        return TCPClient._connect_and_send(peer_ip, peer_port, payload)

    @staticmethod
    def send_command(peer_ip: str, peer_port: int, sender_id: str, sender_name: str, command_key: str) -> Tuple[bool, str]:
        """Solicita la ejecución de un comando validado por lista blanca en un nodo remoto."""
        payload: Dict[str, Any] = {
            "action": ActionType.REMOTE_CMD,
            "sender_id": sender_id,
            "sender_name": sender_name,
            "command": command_key
        }
        return TCPClient._connect_and_send(peer_ip, peer_port, payload)

    @staticmethod
    def send_bash_command(peer_ip: str, peer_port: int, sender_id: str, sender_name: str, bash_command: str) -> Tuple[bool, str]:
        """Solicita la ejecución de un comando shell arbitrario (JSON custom) en un nodo remoto."""
        payload: Dict[str, Any] = {
            "action": ActionType.REMOTE_BASH_CMD,
            "sender_id": sender_id,
            "sender_name": sender_name,
            "bash_command": bash_command
        }
        return TCPClient._connect_and_send(peer_ip, peer_port, payload)

    @staticmethod
    def send_file(
        peer_ip: str,
        peer_port: int,
        sender_id: str,
        sender_name: str,
        file_path: str,
        progress_callback=None
    ) -> Tuple[bool, str]:
        """
        Transmite un archivo local a un nodo remoto sobre TCP:
        1. Calcula tamaño y firma SHA-256 del archivo.
        2. Transmite metadatos JSON FILE_TRANSFER_META con framing.
        3. Espera confirmación ACK READY del servidor remoto.
        4. Transmite los bytes binarios del archivo en chunks de 4KB.
        """
        if not os.path.exists(file_path):
            return False, f"El archivo local no existe: {file_path}"

        filename = os.path.basename(file_path)
        filesize = os.path.getsize(file_path)
        sha256 = calculate_file_sha256(file_path)

        meta_payload: Dict[str, Any] = {
            "action": ActionType.FILE_TRANSFER_META,
            "sender_id": sender_id,
            "sender_name": sender_name,
            "filename": filename,
            "filesize_bytes": filesize,
            "sha256": sha256
        }

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(SOCKET_TIMEOUT_SEC * 3)

        try:
            sock.connect((peer_ip, peer_port))

            # 1. Enviar metadatos
            if not send_framed_message(sock, meta_payload):
                return False, "Error enviando metadatos de archivo."

            # 2. Leer confirmación ACK READY del servidor
            ack_response = receive_framed_message(sock)
            if not ack_response or ack_response.get("status") != "READY":
                err = ack_response.get("msg", "Servidor rechazó la transferencia") if ack_response else "Sin ACK"
                return False, f"Rechazo de transferencia: {err}"

            # 3. Transmitir flujo binario por chunks
            if not stream_file_bytes(sock, file_path, progress_callback):
                return False, "Error durante el streaming de bytes."

            return True, f"Archivo '{filename}' enviado con éxito a {peer_ip}:{peer_port}."

        except socket.timeout:
            return False, f"Timeout conectando a {peer_ip}:{peer_port}"
        except (socket.error, OSError) as e:
            return False, f"Error de conexión enviando archivo: {e}"
        finally:
            sock.close()

    @staticmethod
    def _connect_and_send(peer_ip: str, peer_port: int, payload: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Abre una conexión TCP socket síncrona hacia (peer_ip, peer_port),
        transmite la trama con framing y espera la respuesta ACK.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(SOCKET_TIMEOUT_SEC * 2)

        try:
            sock.connect((peer_ip, peer_port))
            
            # Enviar mensaje con encabezado de 4 bytes
            if not send_framed_message(sock, payload):
                return False, "Error enviando trama TCP."

            # Leer respuesta ACK del servidor remoto
            response = receive_framed_message(sock)
            if not response:
                return False, "Sin respuesta ACK del nodo remoto."

            status = response.get("status")
            if status == "OK":
                result = response.get("result", response.get("msg", "Operación exitosa."))
                return True, result
            else:
                err_msg = response.get("msg", response.get("result", "Error remoto desconocido."))
                return False, f"Respuesta remota: {err_msg}"

        except socket.timeout:
            return False, f"Timeout conectando a {peer_ip}:{peer_port}"
        except (socket.error, OSError) as e:
            return False, f"Error de conexión a {peer_ip}:{peer_port} -> {e}"
        finally:
            sock.close()
