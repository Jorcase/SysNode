import json
import struct
import socket
import hmac
import hashlib
import logging
from typing import Dict, Any, Optional
from sysnode.config import TCP_HEADER_SIZE, BUFFER_SIZE

logger = logging.getLogger(__name__)

# Token de prueba
try:
    from sysnode.config import AUTH_TOKEN
except ImportError:
    AUTH_TOKEN = "sysnode_secret_123"
# Autenticidad e Integridad
def send_framed_message(sock: socket.socket, payload: Dict[str, Any]) -> bool:
    #Wire Format: [4 bytes Length] [64 bytes HMAC Hex] [JSON Payload]
    try:
        raw_json = json.dumps(payload).encode("utf-8")
        # Calcular HMAC del payload crudo
        signature = hmac.new(AUTH_TOKEN.encode('utf-8'), raw_json, hashlib.sha256).hexdigest().encode('utf-8')
        # Length incluye la firma (64 bytes) y el JSON
        payload_length = len(signature) + len(raw_json)
        # Encabezado binario de 4 bytes
        header = struct.pack(">I", payload_length)
        sock.sendall(header + signature + raw_json)
        return True
    except (socket.error, OSError) as e:
        logger.error(f"Error enviando trama TCP con framing: {e}")
        return False

def receive_framed_message(sock: socket.socket) -> Optional[Dict[str, Any]]:
    try:
        # Lee los 4 bytes del encabezado de tamaño
        header_data = _read_exact_bytes(sock, TCP_HEADER_SIZE)
        if not header_data:
            return None
        payload_length = struct.unpack(">I", header_data)[0]
        # Lee exactamente payload_length bytes del cuerpo del mensaje
        raw_payload = _read_exact_bytes(sock, payload_length)
        if not raw_payload or len(raw_payload) < payload_length:
            logger.warning(f"Incompletitud en trama TCP: se esperaban {payload_length} bytes, se recibieron {len(raw_payload) if raw_payload else 0}")
            return None
        if payload_length < 64:
            logger.warning("Mensaje rechazado: Tamaño insuficiente para incluir firma HMAC.")
            return None
        # Separa la firma
        received_hmac = raw_payload[:64]
        raw_json = raw_payload[64:]
        # Verifica la firma
        expected_hmac = hmac.new(AUTH_TOKEN.encode('utf-8'), raw_json, hashlib.sha256).hexdigest().encode('utf-8')
        if not hmac.compare_digest(received_hmac, expected_hmac):
            logger.warning("ACCESO DENEGADO: Firma HMAC inválida. Se rechaza la trama de red.")
            return None

        # Decodifica el JSON
        payload = json.loads(raw_json.decode("utf-8"))
        return payload

    except socket.timeout:
        raise
    except (socket.error, OSError) as e:
        logger.debug(f"Error de socket al recibir trama con framing: {e}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Error decodificando payload JSON recibido: {e}")
        return None
# Alias para compatibilidad de invocación
recv_framed_message = receive_framed_message

def _read_exact_bytes(sock: socket.socket, num_bytes: int) -> Optional[bytes]:
    buf = bytearray()
    while len(buf) < num_bytes:
        chunk = sock.recv(min(num_bytes - len(buf), BUFFER_SIZE))
        if not chunk:
            return None
        buf.extend(chunk)
    return bytes(buf)
