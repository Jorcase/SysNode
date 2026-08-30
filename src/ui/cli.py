"""
SysNode - Interfaz de Línea de Comandos Interactivas (CLI Fase 2)
"""

import os
import sys
import time
import queue
import threading
import logging
from typing import Dict, Any, List

from src.core.sysnode_core import SysNodeCore
from src.core.security import COMMAND_WHITELIST

logger = logging.getLogger(__name__)


class SysNodeCLI:
    """
    CLI interactiva multihilo.
    Renderiza el Radar LAN, el historial de mensajes recibidos (Shared Board)
    y procesa comandos del usuario en un menú interactivo sin bloquear los eventos de red.
    """

    def __init__(self, node_core: SysNodeCore):
        self.core = node_core
        self.event_queue = self.core.register_event_queue()
        self.message_history: List[str] = []
        self.max_history = 10
        self.running = False

    def start(self):
        self.core.start()
        self.running = True

        # Hilo para procesar eventos provenientes de la cola del Core
        event_thread = threading.Thread(target=self._process_events_loop, daemon=True)
        event_thread.start()

        self._main_menu_loop()

    def _process_events_loop(self):
        """Procesa continuamente notificaciones recibidas por TCP/UDP."""
        while self.running:
            try:
                event = self.event_queue.get(timeout=0.5)
                event_type = event.get("event")

                if event_type == "TEXT_RECEIVED":
                    sender = event.get("sender_name")
                    ip = event.get("peer_ip")
                    text = event.get("text")
                    msg = f"📩 [TEXTO DE {sender} ({ip})]: {text}"
                    self._add_to_history(msg)

                elif event_type == "COMMAND_RECEIVED":
                    sender = event.get("sender_name")
                    cmd = event.get("command")
                    success = event.get("success")
                    result = event.get("result")
                    status_icon = "✅" if success else "❌"
                    msg = f"{status_icon} [COMANDO REMOTO DE {sender}]: {cmd} -> {result}"
                    self._add_to_history(msg)

                elif event_type == "FILE_RECEIVED":
                    sender = event.get("sender_name")
                    filename = event.get("filename")
                    success = event.get("success")
                    msg_text = event.get("msg")
                    status_icon = "📁" if success else "❌"
                    msg = f"{status_icon} [ARCHIVO RECIBIDO DE {sender}]: '{filename}' -> {msg_text}"
                    self._add_to_history(msg)

            except queue.Empty:
                pass

    def _add_to_history(self, msg: str):
        timestamp = time.strftime("%H:%M:%S")
        entry = f"[{timestamp}] {msg}"
        self.message_history.append(entry)
        if len(self.message_history) > self.max_history:
            self.message_history.pop(0)

    def _clear_screen(self):
        os.system("cls" if os.name == "nt" else "clear")

    def _render_dashboard(self):
        active_peers = self.core.get_active_peers()

        print("=" * 70)
        print("    🌐 SYSNODE P2P - RADAR, SHARED BOARD & FILE DROP (Fase 3) 🌐")
        print("=" * 70)
        print(f"  Nodo Local   : {self.core.node_name}")
        print(f"  IP en LAN    : {self.core.local_ip}")
        print(f"  Puerto TCP   : {self.core.tcp_port}")
        print("=" * 70)
        print(f"  NODOS ACTIVOS EN LA LAN ({len(active_peers)}):")
        print("-" * 70)

        peer_list = list(active_peers.values())
        if not peer_list:
            print("  [ Buscando otros nodos en la red LAN via UDP Broadcast... ]")
        else:
            print(f"  {'#':<3} {'HOSTNAME':<18} {'IP ADDRESS':<16} {'SO':<10} {'PUERTO TCP':<10}")
            print("  " + "-" * 64)
            for idx, peer in enumerate(peer_list, 1):
                print(f"  [{idx}] {peer['hostname']:<18} {peer['ip']:<16} {peer['os']:<10} {peer['tcp_port']:<10}")

        print("=" * 70)
        print("  HISTORIAL DE EVENTOS / MENSAJES / ARCHIVOS (Shared Board):")
        print("-" * 70)

        if not self.message_history:
            print("  (Sin mensajes, archivos o eventos recibidos recientemente)")
        else:
            for item in self.message_history[-6:]:
                print(f"  {item}")

        print("=" * 70)

    def _main_menu_loop(self):
        try:
            while self.running:
                self._clear_screen()
                self._render_dashboard()

                print("\n  OPCIONES:")
                print("  [1] Enviar Texto (Shared Board) a un nodo")
                print("  [2] Enviar Comando Remoto (SysAdmin) a un nodo")
                print("  [3] Enviar Archivo (File Drop) a un nodo")
                print("  [4] Añadir Nodo por IP Manual (Fallback TCP)")
                print("  [r] Refrescar pantalla")
                print("  [q] Salir")
                
                try:
                    choice = input("\n  Seleccioná una opción > ").strip()
                except (EOFError, KeyboardInterrupt):
                    break

                if choice == "1":
                    self._action_send_text()
                elif choice == "2":
                    self._action_send_command()
                elif choice == "3":
                    self._action_send_file()
                elif choice == "4":
                    self._action_add_manual_peer()
                elif choice.lower() == "q":
                    break
                elif choice.lower() == "r":
                    continue

        finally:
            self.running = False
            self.core.stop()
            print("\nNodo detenido exitosamente.")

    def _select_peer(self) -> Any:
        active_peers = list(self.core.get_active_peers().values())
        if not active_peers:
            print("\n⚠️ No hay otros nodos activos en la red LAN para seleccionar.")
            input("Presioná Enter para volver al menú...")
            return None

        print("\nSeleccioná el número de nodo destino:")
        for idx, peer in enumerate(active_peers, 1):
            print(f"  [{idx}] {peer['hostname']} ({peer['ip']}:{peer['tcp_port']})")

        try:
            selection = int(input("\nNúmero de nodo > ").strip())
            if 1 <= selection <= len(active_peers):
                return active_peers[selection - 1]
            else:
                print("⚠️ Selección inválida.")
                input("Presioná Enter para continuar...")
                return None
        except ValueError:
            print("⚠️ Entrada no válida.")
            input("Presioná Enter para continuar...")
            return None

    def _action_send_text(self):
        peer = self._select_peer()
        if not peer:
            return

        text = input(f"\nIngresá el texto para enviar a {peer['hostname']} > ").strip()
        if not text:
            return

        print(f"Enviando a {peer['ip']}:{peer['tcp_port']}...")
        success, msg = self.core.send_text_to_peer(peer["node_id"], text)

        if success:
            print(f"✅ ¡Texto entregado con éxito!: {msg}")
        else:
            print(f"❌ Error entregando texto: {msg}")

        input("\nPresioná Enter para volver al menú...")

    def _action_send_command(self):
        peer = self._select_peer()
        if not peer:
            return

        print("\nComandos disponibles en la Lista Blanca:")
        cmd_keys = list(COMMAND_WHITELIST.keys())
        for idx, key in enumerate(cmd_keys, 1):
            desc = COMMAND_WHITELIST[key]["description"]
            print(f"  [{idx}] {key} -> {desc}")

        try:
            cmd_choice = int(input("\nSeleccioná comando > ").strip())
            if 1 <= cmd_choice <= len(cmd_keys):
                selected_cmd = cmd_keys[cmd_choice - 1]
            else:
                print("⚠️ Opción no válida.")
                input("Presioná Enter para continuar...")
                return
        except ValueError:
            print("⚠️ Entrada no válida.")
            input("Presioná Enter para continuar...")
            return

        print(f"Enviando comando '{selected_cmd}' a {peer['hostname']}...")
        success, result = self.core.send_command_to_peer(peer["node_id"], selected_cmd)

        if success:
            print(f"✅ Respuesta remota del nodo: {result}")
        else:
            print(f"❌ Error al ejecutar comando remoto: {result}")

        input("\nPresioná Enter para volver al menú...")

    def _action_send_file(self):
        peer = self._select_peer()
        if not peer:
            return

        file_path = input(f"\nIngresá la ruta del archivo local a enviar a {peer['hostname']} > ").strip()
        # Limpiar comillas si el usuario arrastró un archivo a la terminal
        file_path = file_path.strip("'\"")

        if not file_path or not os.path.exists(file_path):
            print("⚠️ El archivo ingresado no existe.")
            input("Presioná Enter para continuar...")
            return

        print(f"\nIniciando transferencia de '{os.path.basename(file_path)}' ({os.path.getsize(file_path)} bytes)...")

        def print_ascii_progress(sent, total):
            percent = int((sent / total) * 100) if total > 0 else 100
            bar_len = 30
            filled_len = int(bar_len * sent // total) if total > 0 else bar_len
            bar = '█' * filled_len + '░' * (bar_len - filled_len)
            sys.stdout.write(f"\r  Progreso: [{bar}] {percent}% ({sent}/{total} bytes)")
            sys.stdout.flush()

        success, result = self.core.send_file_to_peer(
            peer["node_id"],
            file_path,
            progress_callback=print_ascii_progress
        )

        print("\n")
        if success:
            print(f"✅ {result}")
        else:
            print(f"❌ Error enviando archivo: {result}")

        input("\nPresioná Enter para volver al menú...")

    def _action_add_manual_peer(self):
        print("\n--- Añadir Nodo por IP Manual ---")
        ip = input("Ingresá la IP local del nodo (ej: 192.168.0.10) > ").strip()
        if not ip:
            return
            
        port_str = input("Ingresá el puerto TCP (Enter para 50001) > ").strip()
        port = 50001
        if port_str:
            try:
                port = int(port_str)
            except ValueError:
                print("⚠️ Puerto inválido. Se usará 50001.")
        
        self.core.add_manual_peer(ip, port)
        print(f"✅ Nodo {ip}:{port} añadido manualmente. Ahora podés seleccionarlo en el menú de envío.")
        input("\nPresioná Enter para volver al menú...")

def run_cli(node_core: SysNodeCore):
    cli = SysNodeCLI(node_core)
    cli.start()
