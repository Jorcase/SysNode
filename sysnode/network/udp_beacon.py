import json
import time
import socket
import threading
import logging
from typing import Dict, Any

from sysnode.config import (
    UDP_DISCOVERY_PORT,
    BROADCAST_IP,
    BEACON_INTERVAL_SEC,
    HOST_NAME,
    SYSTEM_OS,
    PROTOCOL_TYPE_ANNOUNCE,
    PROTOCOL_TYPE_GOODBYE,
)

logger = logging.getLogger(__name__)

class UDPBeacon(threading.Thread):
    # Hilo de segundo plano(daemon) encargado de emitir periódicamente un
    # datagrama UDP Broadcast anunciando la presencia del nodo en la LAN.

    def __init__(self, node_id: str, tcp_port: int, custom_name: str = None):
        super().__init__(daemon=True, name="UDPBeaconThread")
        self.node_id = node_id
        self.tcp_port = tcp_port
        self.hostname = custom_name or HOST_NAME
        self.running = False
        self.stealth_mode = False
        self._stop_event = threading.Event()

    def run(self) -> None:
        self.running = True
        logger.info(f"UDPBeacon iniciado -> Anunciando en {BROADCAST_IP}:{UDP_DISCOVERY_PORT} cada {BEACON_INTERVAL_SEC}s")

        # Creación del socket UDP para emisión broadcast
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1) #sock.setsockopt(NIVEL, OPCIÓN, VALOR)

        while not self._stop_event.is_set():
            try:
                if not self.stealth_mode:
                    payload: Dict[str, Any] = {
                        "type": PROTOCOL_TYPE_ANNOUNCE,
                        "node_id": self.node_id,
                        "hostname": self.hostname,
                        "os": SYSTEM_OS,
                        "tcp_port": self.tcp_port,
                        "timestamp": time.time(),
                    }
                    data = json.dumps(payload).encode("utf-8")
                    sock.sendto(data, (BROADCAST_IP, UDP_DISCOVERY_PORT))
            except Exception as e:
                logger.error(f"Error emitiendo UDP Beacon: {e}")

            self._stop_event.wait(BEACON_INTERVAL_SEC)

        try:
            goodbye_payload = {
                "type": PROTOCOL_TYPE_GOODBYE,
                "node_id": self.node_id,
            }
            sock.sendto(json.dumps(goodbye_payload).encode("utf-8"), (BROADCAST_IP, UDP_DISCOVERY_PORT))
        except Exception:
            pass

        sock.close()
        self.running = False
        logger.info("UDPBeacon detenido.")

    def stop(self) -> None:
        # Solicita la detención segura del hilo.
        self._stop_event.set()
