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
import logging
from typing import Dict, Any, Optional

from src.config import TCP_HEADER_SIZE, BUFFER_SIZE

logger = logging.getLogger(__name__)


def send_framed_message(sock: socket.socket, payload: Dict[str, Any]) -> bool:
    """
    Empaca un diccionario Python como JSON UTF-8, calcula su tamaño en bytes,
    genera el encabezado binario de 4 bytes (struct.pack('>I', payload_length))
    y transmite la trama completa a través del socket TCP.
    """
    try:
        raw_json = json.dumps(payload).encode("utf-8")
        payload_length = len(raw_json)

        # Encabezado binario de 4 bytes (Big-Endian unsigned int)
        header = struct.pack(">I", payload_length)

        # Enviar encabezado + payload
        sock.sendall(header + raw_json)
        return True
    except (socket.error, OSError) as e:
        logger.error(f"Error enviando trama TCP con framing: {e}")
        return False


def receive_framed_message(sock: socket.socket) -> Optional[Dict[str, Any]]:
    """
    Lee una trama de un socket TCP respetando el protocolo Length-Prefixed:
    1. Lee exactamente 4 bytes para obtener el encabezado con el tamaño L.
    2. Realiza lecturas iterativas en bucle hasta acumular los L bytes exactos.
    3. Decodifica el JSON UTF-8 y lo devuelve como diccionario.
    
    Devuelve None si la conexión se cerró limpiamente o ocurrió un error.
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

        # 3. Decodificar JSON
        payload = json.loads(raw_payload.decode("utf-8"))
        return payload

    except (socket.error, OSError) as e:
        logger.debug(f"Error de socket al recibir trama con framing: {e}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Error decodificando payload JSON recibido: {e}")
        return None


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
