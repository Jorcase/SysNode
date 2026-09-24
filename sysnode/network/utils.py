import socket
import logging

logger = logging.getLogger(__name__)


def get_local_lan_ip() -> str:
    """
    Obtiene la dirección IP real de la interfaz de red local conectada a la LAN.
    A diferencia de socket.gethostbyname(socket.gethostname()), este método no sufre
    del problema común en linux donde el hostname apunta a 127.0.0.1 en /etc/hosts.
    
    Funciona creando un socket UDP temporal y consultando la interfaz activa sin enviar paquetes reales.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # 8.8.8.8:80 se usa como referencia de enrutamiento de la interfaz de salida
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        # Fallback si no hay conexión externa disponible
        try:
            ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def configure_udp_reuse(sock: socket.socket) -> None:
    """
    Configura las opciones de socket SO_REUSEADDR y SO_REUSEPORT (si está disponible en el SO)
    para permitir que múltiples instancias locales del nodo escuchen en el mismo puerto UDP Broadcast (50000).
    """
    # SO_REUSEADDR para reutilizar el puerto inmediatamente
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # SO_REUSEPORT permite a múltiples procesos en Linux/macOS el bind en el mismo puerto
    if hasattr(socket, "SO_REUSEPORT"):
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except OSError as e:
            logger.debug(f"SO_REUSEPORT no soportado en esta plataforma: {e}")
