"""
SysNode - Orquestador Principal del Nodo P2P (Core Manager)
"""

import uuid
import queue
import logging
import threading
from typing import Dict, Any, Tuple

from sysnode.config import DEFAULT_TCP_PORT, HOST_NAME
from sysnode.network.utils import get_local_lan_ip
from sysnode.network.udp_beacon import UDPBeacon
from sysnode.network.udp_listener import UDPListener
from sysnode.network.tcp_server import TCPServer
from sysnode.network.tcp_client import TCPClient
from sysnode.core.database import SysNodeDatabase
import os

logger = logging.getLogger(__name__)


class SysNodeCore:
    """
    Clase central que administra el ciclo de vida del nodo P2P.
    Coordina los hilos de red UDP y TCP, expone colas de eventos (Event Broker)
    y mantiene desacoplada la lógica de red de cualquier interfaz (UI, CLI o Web).
    """

    def __init__(self, node_name: str = None, tcp_port: int = DEFAULT_TCP_PORT):
        self.node_id = str(uuid.uuid4())
        self.node_name = node_name or HOST_NAME
        self.tcp_port = tcp_port
        self.local_ip = get_local_lan_ip()

        # Broker de Eventos (Permite múltiples listeners como Desktop UI y Mobile WS)
        self.event_queues = []
        self._broker_lock = threading.Lock()

        # Database para persistencia de chat
        db_path = os.path.join(os.getcwd(), "SysNode_Received", "history.db")
        self.db = SysNodeDatabase(db_path)

        # Hilos de descubrimiento UDP
        self.udp_beacon = UDPBeacon(
            node_id=self.node_id,
            tcp_port=self.tcp_port,
            custom_name=self.node_name
        )
        self.udp_listener = UDPListener(
            my_node_id=self.node_id,
            event_callback=self.broadcast_event
        )

        # Servidor TCP para recepción de texto y comandos
        self.tcp_server = TCPServer(
            tcp_port=self.tcp_port,
            event_callback=self.broadcast_event,
            node_name=self.node_name
        )

        self._running = False

    def register_event_queue(self) -> queue.Queue:
        """Registra una nueva cola de eventos para un suscriptor y la devuelve."""
        new_q = queue.Queue()
        with self._broker_lock:
            self.event_queues.append(new_q)
        return new_q

    def broadcast_event(self, event_dict: Dict[str, Any]) -> None:
        """Inyecta un evento de red en TODAS las colas suscritas y persiste el historial si es un mensaje de texto."""
        # Interceptar mensajes entrantes para persistencia
        if event_dict.get("event") == "TEXT_RECEIVED":
            sender = event_dict.get("sender_name", "Desconocido")
            text = event_dict.get("text", "")
            self.db.save_message(sender, text, "IN")

        with self._broker_lock:
            for q in self.event_queues:
                q.put(event_dict)

    def start(self) -> None:
        """Inicia los componentes de red del nodo (UDP y TCP)."""
        if self._running:
            return

        logger.info("=" * 60)
        logger.info(f"INICIANDO SYSNODE CORE: [{self.node_name}]")
        logger.info(f"ID del Nodo: {self.node_id}")
        logger.info(f"IP Local LAN: {self.local_ip}")
        logger.info(f"Puerto TCP: {self.tcp_port}")
        logger.info("=" * 60)

        # Iniciar servidor TCP
        self.tcp_server.start()

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
        self.tcp_server.stop()

        self._running = False
        logger.info("SysNodeCore detenido exitosamente.")

    def get_active_peers(self) -> Dict[str, Dict[str, Any]]:
        """Obtiene la lista actual de nodos descubiertos en la LAN."""
        return self.udp_listener.get_active_peers()

    def add_manual_peer(self, ip: str, port: int) -> None:
        """Añade manualmente un nodo a la red, evadiendo bloqueos UDP."""
        self.udp_listener.add_manual_peer(ip, port)

    def send_text_to_peer(self, node_id: str, text: str) -> Tuple[bool, str]:
        """Envía un texto al Shared Board de un nodo activo específico."""
        peers = self.get_active_peers()
        if node_id not in peers:
            return False, f"Nodo con ID '{node_id}' no encontrado en la lista activa."

        peer = peers[node_id]
        return TCPClient.send_text(
            peer_ip=peer["ip"],
            peer_port=peer["tcp_port"],
            sender_id=self.node_id,
            sender_name=self.node_name,
            text=text
        )

    def send_command_to_peer(self, node_id: str, command_key: str) -> Tuple[bool, str]:
        """Envía una solicitud de ejecución remota a un nodo activo específico."""
        peers = self.get_active_peers()
        if node_id not in peers:
            return False, f"Nodo con ID '{node_id}' no encontrado en la lista activa."

        peer = peers[node_id]
        return TCPClient.send_command(
            peer_ip=peer["ip"],
            peer_port=peer["tcp_port"],
            sender_id=self.node_id,
            sender_name=self.node_name,
            command_key=command_key
        )

    def send_file_to_peer(self, node_id: str, file_path: str, progress_callback=None) -> Tuple[bool, str]:
        """Transmite un archivo binario local al nodo remoto activo sobre TCP."""
        peers = self.get_active_peers()
        if node_id not in peers:
            return False, f"Nodo con ID '{node_id}' no encontrado en la lista activa."

        peer = peers[node_id]
        return TCPClient.send_file(
            peer_ip=peer["ip"],
            peer_port=peer["tcp_port"],
            sender_id=self.node_id,
            sender_name=self.node_name,
            file_path=file_path,
            progress_callback=progress_callback
        )

    def is_running(self) -> bool:
        return self._running
