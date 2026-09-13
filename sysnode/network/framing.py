"""
SysNode - Módulo de Encapsulado y Desencapsulado TCP (Length-Prefixed Framing)

Solución al problema de 'Message Boundaries' en TCP:
TCP es un protocolo orientado a flujo continuo de bytes (Byte Stream). Para evitar
que dos mensajes JSON o datos de red se peguen en el búfer de recepción, este módulo
precede cada mensaje de un encabezado de 4 bytes en orden de red Big-Endian (unsigned int)
que indica la longitud exacta en bytes del contenido que le sigue.
"""

import json
import struct
import socket
import hmac
import hashlib
import logging
from typing import Dict, Any, Optional

from sysnode.config import TCP_HEADER_SIZE, BUFFER_SIZE

logger = logging.getLogger(__name__)

# Token de prueba (luego será dinámico en Sprint 3)
try:
    from sysnode.config import AUTH_TOKEN
except ImportError:
    AUTH_TOKEN = "sysnode_secret_123"

def send_framed_message(sock: socket.socket, payload: Dict[str, Any]) -> bool:
    """
    Empaca un diccionario Python como JSON UTF-8, le calcula un HMAC-SHA256,
    genera el encabezado binario de 4 bytes con la longitud total,
    y transmite la trama completa a través del socket TCP.
    Wire Format: [4 bytes Length] [64 bytes HMAC Hex] [JSON Payload]
    """
    try:
        raw_json = json.dumps(payload).encode("utf-8")
        
        # Calcular HMAC del payload crudo
        signature = hmac.new(AUTH_TOKEN.encode('utf-8'), raw_json, hashlib.sha256).hexdigest().encode('utf-8')
        
        # Length incluye la firma (64 bytes) y el JSON
        payload_length = len(signature) + len(raw_json)

        # Encabezado binario de 4 bytes (Big-Endian unsigned int)
        header = struct.pack(">I", payload_length)

        # Enviar encabezado + firma + payload
        sock.sendall(header + signature + raw_json)
        return True
    except (socket.error, OSError) as e:
        logger.error(f"Error enviando trama TCP con framing: {e}")
        return False


def receive_framed_message(sock: socket.socket) -> Optional[Dict[str, Any]]:
    """
    Lee una trama de un socket TCP respetando el protocolo Length-Prefixed:
    1. Lee exactamente 4 bytes para obtener el encabezado con el tamaño L.
    2. Lee exactamente L bytes del cuerpo.
    3. Extrae los primeros 64 bytes (Firma HMAC).
    4. Verifica que el HMAC corresponda al JSON restante.
    5. Decodifica el JSON UTF-8 y lo devuelve.
    """
    try:
        # 1. Leer los 4 bytes del encabezado de tamaño
        header_data = _read_exact_bytes(sock, TCP_HEADER_SIZE)
        if not header_data:
            return None  # Cierre de conexión por el par (0 bytes / FIN)

        payload_length = struct.unpack(">I", header_data)[0]

        # 2. Leer exactamente payload_length bytes del cuerpo del mensaje
        raw_payload = _read_exact_bytes(sock, payload_length)
        if not raw_payload or len(raw_payload) < payload_length:
            logger.warning(f"Incompletitud en trama TCP: se esperaban {payload_length} bytes, se recibieron {len(raw_payload) if raw_payload else 0}")
            return None
            
        if payload_length < 64:
            logger.warning("Mensaje rechazado: Tamaño insuficiente para incluir firma HMAC.")
            return None

        # 3. Separar Firma (64 bytes) y JSON
        received_hmac = raw_payload[:64]
        raw_json = raw_payload[64:]
        
        # 4. Verificar Firma
        expected_hmac = hmac.new(AUTH_TOKEN.encode('utf-8'), raw_json, hashlib.sha256).hexdigest().encode('utf-8')
        if not hmac.compare_digest(received_hmac, expected_hmac):
            logger.warning("🚨 ACCESO DENEGADO: Firma HMAC inválida. Se rechaza la trama de red.")
            return None

        # 5. Decodificar JSON
        payload = json.loads(raw_json.decode("utf-8"))
        return payload

    except (socket.error, OSError) as e:
        logger.debug(f"Error de socket al recibir trama con framing: {e}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Error decodificando payload JSON recibido: {e}")
        return None

# Alias para compatibilidad de invocación
recv_framed_message = receive_framed_message


def _read_exact_bytes(sock: socket.socket, num_bytes: int) -> Optional[bytes]:
    """
    Helper interno que realiza lecturas continuas del socket TCP
    hasta acumular exactamente num_bytes.
    Garantiza que lecturas parciales en la red no corten el mensaje.
    """
    buf = bytearray()
    while len(buf) < num_bytes:
        chunk = sock.recv(min(num_bytes - len(buf), BUFFER_SIZE))
        if not chunk:
            # El socket se cerró antes de completar la lectura requerida
            return None
        buf.extend(chunk)
    return bytes(buf)
