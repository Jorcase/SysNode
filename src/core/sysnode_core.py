"""
SysNode - Orquestador Principal del Nodo P2P (Core Manager)
"""

import uuid
import queue
import logging
from typing import Dict, Any

from src.config import DEFAULT_TCP_PORT, HOST_NAME
from src.network.utils import get_local_lan_ip
from src.network.udp_beacon import UDPBeacon
from src.network.udp_listener import UDPListener

logger = logging.getLogger(__name__)


class SysNodeCore:
    """
    Clase central que administra el ciclo de vida del nodo P2P.
    Coordina los hilos de red UDP, expone la cola de eventos thread-safe
    y mantiene desacoplada la lógica de red de cualquier interfaz gráfica (UI) o CLI.
    """

    def __init__(self, node_name: str = None, tcp_port: int = DEFAULT_TCP_PORT):
        self.node_id = str(uuid.uuid4())
        self.node_name = node_name or HOST_NAME
        self.tcp_port = tcp_port
        self.local_ip = get_local_lan_ip()

        # Cola de eventos thread-safe compartida con la UI / CLI
        self.event_queue = queue.Queue()

        # Hilos de descubrimiento UDP
        self.udp_beacon = UDPBeacon(
            node_id=self.node_id,
            tcp_port=self.tcp_port,
            custom_name=self.node_name
        )
        self.udp_listener = UDPListener(
            my_node_id=self.node_id,
            event_queue=self.event_queue
        )

        self._running = False

    def start(self) -> None:
        """Inicia los componentes de red del nodo."""
        if self._running:
            return

        logger.info("=" * 60)
        logger.info(f"INICIANDO SYSNODE CORE: [{self.node_name}]")
        logger.info(f"ID del Nodo: {self.node_id}")
        logger.info(f"IP Local LAN: {self.local_ip}")
        logger.info(f"Puerto TCP: {self.tcp_port}")
        logger.info("=" * 60)

        # Iniciar hilos de descubrimiento UDP
        self.udp_listener.start()
        self.udp_beacon.start()

        self._running = True

    def stop(self) -> None:
        """Detiene de forma limpia todos los hilos del nodo."""
        if not self._running:
            return

        logger.info(f"Deteniendo SysNodeCore [{self.node_name}]...")
        
        # Detener hilos de red
        self.udp_beacon.stop()
        self.udp_listener.stop()

        self._running = False
        logger.info("SysNodeCore detenido exitosamente.")

    def get_active_peers(self) -> Dict[str, Dict[str, Any]]:
        """Obtiene la lista actual de nodos descubiertos en la LAN."""
        return self.udp_listener.get_active_peers()

    def is_running(self) -> bool:
        return self._running
