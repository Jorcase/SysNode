"""
SysNode - Interfaz de Línea de Comandos (CLI Radar LAN)
"""

import os
import sys
import time
import queue
import logging
from typing import Dict, Any

from src.core.sysnode_core import SysNodeCore

logger = logging.getLogger(__name__)


def clear_screen():
    """Limpia la pantalla de la terminal en Windows o Linux."""
    os.system("cls" if os.name == "nt" else "clear")


def run_cli(node_core: SysNodeCore):
    """
    Ejecuta el bucle de la interfaz de consola mostrando el estado del nodo
    y la lista dinámica de pares descubiertos en la LAN (Radar LAN).
    """
    node_core.start()
    print("Iniciando Radar LAN... Presioná Ctrl+C para salir.\n")
    time.sleep(1)

    try:
        while node_core.is_running():
            # Consumir eventos pendientes de la cola de red
            while True:
                try:
                    event = node_core.event_queue.get_nowait()
                    # Eventos opcionales de log
                except queue.Empty:
                    break

            active_peers = node_core.get_active_peers()

            # Renderizar interfaz de consola
            clear_screen()
            print("=" * 65)
            print("         🌐 SYSNODE P2P - RADAR LAN (Fase 1: UDP Core) 🌐")
            print("=" * 65)
            print(f"  Nodo Local   : {node_core.node_name}")
            print(f"  ID de Nodo   : {node_core.node_id}")
            print(f"  IP en LAN    : {node_core.local_ip}")
            print(f"  Puerto TCP   : {node_core.tcp_port}")
            print("=" * 65)
            print(f"  NODOS ACTIVOS DESCUBIERTOS ({len(active_peers)}):")
            print("-" * 65)

            if not active_peers:
                print("  [ Buscando otros nodos en la red LAN via UDP Broadcast... ]")
            else:
                print(f"  {'HOSTNAME':<18} {'IP ADDRESS':<16} {'SO':<10} {'PUERTO TCP':<10}")
                print("  " + "-" * 61)
                now = time.time()
                for peer_id, peer in active_peers.items():
                    elapsed = int(now - peer['last_seen'])
                    status = f"({elapsed}s ago)"
                    print(f"  {peer['hostname']:<18} {peer['ip']:<16} {peer['os']:<10} {peer['tcp_port']:<10}")

            print("=" * 65)
            print("  Presione Ctrl+C en cualquier momento para salir.")

            time.sleep(1.0)

    except KeyboardInterrupt:
        print("\n\nSaliendo de SysNode...")
    finally:
        node_core.stop()
        print("Nodo cerrado. ¡Hasta luego!")
