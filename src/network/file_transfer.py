"""
SysNode - Módulo de Transferencia Binaria de Archivos (File Transfer & Integrity)

Maneja la transmisión y recepción de archivos en bloques (chunks) de 4096 bytes (4KB) sobre TCP,
calcula la firma digital SHA-256 en fragmentos de 64KB y administra archivos temporales (.tmp)
para garantizar que las descargas interrumpidas no corrompan el sistema.
"""

import os
import hashlib
import socket
import logging
from typing import Dict, Any, Tuple, Callable, Optional

from src.config import BUFFER_SIZE

logger = logging.getLogger(__name__)

# Tamaño de bloque para cálculo de SHA-256 (64KB)
HASH_CHUNK_SIZE = 65536


def calculate_file_sha256(file_path: str) -> str:
    """Calcula la firma de integridad SHA-256 de un archivo local en bloques de 64KB."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(HASH_CHUNK_SIZE), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def stream_file_bytes(
    sock: socket.socket,
    file_path: str,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> bool:
    """
    Lee un archivo local en fragmentos de 4096 bytes y los transmite secuencialmente por el socket TCP.
    Invoca opcionalmente un callback de progreso (sent_bytes, total_bytes).
    """
    try:
        total_size = os.path.getsize(file_path)
        sent_bytes = 0

        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(BUFFER_SIZE)
                if not chunk:
                    break
                sock.sendall(chunk)
                sent_bytes += len(chunk)

                if progress_callback:
                    progress_callback(sent_bytes, total_size)

        return True
    except (socket.error, OSError) as e:
        logger.error(f"Error transmitiendo streaming de archivo: {e}")
        return False


def receive_file_bytes(
    sock: socket.socket,
    temp_path: str,
    final_path: str,
    total_bytes: int,
    expected_sha256: str,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> Tuple[bool, str]:
    """
    Lee exactamente total_bytes del socket TCP en fragmentos de 4096 bytes y los escribe en temp_path (.tmp).
    Al completar los bytes, verifica el hash SHA-256:
    - Si coincide: Renombra el archivo a final_path y retorna (True, "OK").
    - Si no coincide: Elimina temp_path y retorna (False, "Error de firma SHA-256").
    """
    received_bytes = 0
    sha256_hash = hashlib.sha256()

    # Asegurar que el directorio contenedor exista
    os.makedirs(os.path.dirname(os.path.abspath(temp_path)), exist_ok=True)

    try:
        with open(temp_path, "wb") as f:
            while received_bytes < total_bytes:
                bytes_to_read = min(BUFFER_SIZE, total_bytes - received_bytes)
                chunk = sock.recv(bytes_to_read)
                if not chunk:
                    break

                f.write(chunk)
                sha256_hash.update(chunk)
                received_bytes += len(chunk)

                if progress_callback:
                    progress_callback(received_bytes, total_bytes)

        # Verificar si se recibió la cantidad esperada de bytes
        if received_bytes < total_bytes:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return False, f"Transmisión truncada: Se recibieron {received_bytes} de {total_bytes} bytes."

        # Verificar integridad SHA-256
        calculated_sha256 = sha256_hash.hexdigest()
        if expected_sha256 and calculated_sha256 != expected_sha256:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            logger.error(f"Falla de Integridad: Esperado={expected_sha256}, Calculado={calculated_sha256}")
            return False, "Error de verificación de integridad (Firma SHA-256 no coincide)."

        # Renombrar de .tmp a archivo final
        if os.path.exists(final_path):
            os.remove(final_path)
        os.rename(temp_path, final_path)

        logger.info(f"Archivo recibido e íntegro: '{os.path.basename(final_path)}' ({received_bytes} bytes)")
        return True, f"Archivo guardado exitosamente en: {final_path}"

    except Exception as e:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
        logger.error(f"Excepción durante recepción de archivo: {e}")
        return False, f"Error al guardar el archivo: {str(e)}"
