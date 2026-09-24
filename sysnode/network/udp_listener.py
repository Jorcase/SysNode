import json
import time
import socket
import queue
import threading
import logging
from typing import Dict, Any

from sysnode.config import (
    UDP_DISCOVERY_PORT,
    BIND_ALL_IP,
    PEER_TTL_SEC,
    BUFFER_SIZE,
    PROTOCOL_TYPE_ANNOUNCE,
    PROTOCOL_TYPE_GOODBYE,
)
from sysnode.network.utils import configure_udp_reuse

logger = logging.getLogger(__name__)


class UDPListener(threading.Thread):
    def __init__(self, my_node_id: str, event_callback):
        super().__init__(daemon=True, name="UDPListenerThread")
        self.my_node_id = my_node_id
        self.event_callback = event_callback
        self.running = False
        self.stealth_mode = False
        self.active_peers: Dict[str, Dict[str, Any]] = {}
        self.peers_lock = threading.Lock()
        self._stop_event = threading.Event()

    def run(self) -> None:
        self.running = True
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        
        # Configurar reutilización de socket para pruebas locales simultáneas
        configure_udp_reuse(sock)
        
        # Timeout para permitir revisar el evento _stop_event periódicamente
        sock.settimeout(1.0)
        
        try:
            sock.bind((BIND_ALL_IP, UDP_DISCOVERY_PORT))
            logger.info(f"UDPListener bindeado en {BIND_ALL_IP}:{UDP_DISCOVERY_PORT}")
        except Exception as e:
            logger.error(f"Error al bindear UDPListener en puerto {UDP_DISCOVERY_PORT}: {e}")
            self.running = False
            return

        last_cleanup_time = time.time()

        while not self._stop_event.is_set():
            # 1. Intentar recibir datagramas UDP
            try:
                data, addr = sock.recvfrom(BUFFER_SIZE)
                peer_ip = addr[0]
                self._process_datagram(data, peer_ip)
            except socket.timeout:
                pass
            except Exception as e:
                if not self._stop_event.is_set():
                    logger.error(f"Excepción en UDPListener recv: {e}")

            # 2. Cada 1 segundo, verificar expiración de nodos (TTL)
            now = time.time()
            if now - last_cleanup_time >= 1.0:
                self._cleanup_expired_peers(now)
                last_cleanup_time = now

        sock.close()
        self.running = False
        logger.info("UDPListener detenido.")

    def _process_datagram(self, data: bytes, peer_ip: str) -> None:
        """Parsea el JSON entrante e ignora el propio nodo. Si el modo oculto está activo, ignora todo."""
        if self.stealth_mode:
            return
            
        try:
            payload = json.loads(data.decode("utf-8"))
            node_id = payload.get("node_id")

            # Ignorar latidos emitidos por este mismo proceso
            if not node_id or node_id == self.my_node_id:
                return

            msg_type = payload.get("type")

            if msg_type == PROTOCOL_TYPE_ANNOUNCE:
                now = time.time()
                hostname = payload.get("hostname", "unknown")
                peer_os = payload.get("os", "unknown")
                tcp_port = payload.get("tcp_port", 50001)

                is_new = False
                with self.peers_lock:
                    if node_id not in self.active_peers:
                        is_new = True
                    
                    self.active_peers[node_id] = {
                        "node_id": node_id,
                        "hostname": hostname,
                        "os": peer_os,
                        "ip": peer_ip,
                        "tcp_port": tcp_port,
                        "last_seen": now,
                    }

                if is_new:
                    logger.info(f"NUEVO NODO DESCUBIERTO: {hostname} ({peer_ip}:{tcp_port}) - ID: {node_id[:8]}")
                    self.event_callback({
                        "event": "PEER_DISCOVERED",
                        "peer": self.active_peers[node_id]
                    })
                else:
                    self.event_callback({
                        "event": "PEER_UPDATED",
                        "peer": self.active_peers[node_id]
                    })

            elif msg_type == PROTOCOL_TYPE_GOODBYE:
                with self.peers_lock:
                    removed = self.active_peers.pop(node_id, None)
                if removed:
                    logger.info(f"NODO DESCONECTADO (Goodbye): {removed['hostname']} ({removed['ip']})")
                    self.event_callback({
                        "event": "PEER_REMOVED",
                        "node_id": node_id,
                        "peer": removed
                    })

        except (json.JSONDecodeError, UnicodeDecodeError):
            pass

    def add_manual_peer(self, ip: str, port: int, node_id: str, hostname: str, os_type: str) -> None:
        """Añade un peer de forma manual (verificado por TCP)."""
        with self.peers_lock:
            self.active_peers[node_id] = {
                "node_id": node_id,
                "hostname": hostname,
                "os": os_type,
                "ip": ip,
                "tcp_port": port,
                "last_seen": time.time(),
                "manual": True
            }
            
        logger.info(f"NUEVO NODO MANUAL AÑADIDO: {hostname} ({ip}:{port}) - ID: {node_id[:8]}")
        self.event_callback({
            "event": "PEER_DISCOVERED",
            "peer": self.active_peers[node_id]
        })

    def _cleanup_expired_peers(self, now: float) -> None:
        """Elimina del diccionario de peers los nodos que no hayan enviado latido por más de PEER_TTL_SEC."""
        expired_ids = []

        with self.peers_lock:
            for node_id, peer_info in list(self.active_peers.items()):
                if peer_info.get("manual", False):
                    continue  # Nodos manuales no expiran nunca
                if now - peer_info["last_seen"] > PEER_TTL_SEC:
                    expired_ids.append(node_id)
                    del self.active_peers[node_id]

        for node_id in expired_ids:
            logger.info(f"NODO EXPIRADO por TTL (>{PEER_TTL_SEC}s sin respuesta): ID {node_id[:8]}")
            self.event_callback({
                "event": "PEER_EXPIRED",
                "node_id": node_id
            })

    def get_active_peers(self) -> Dict[str, Dict[str, Any]]:
        """Devuelve una copia thread-safe de la lista de nodos activos."""
        with self.peers_lock:
            return dict(self.active_peers)

    def stop(self) -> None:
        """Solicita la detención del hilo receptor."""
        self._stop_event.set()
