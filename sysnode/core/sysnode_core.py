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
from sysnode.network.http_server import SharingHTTPServer
from sysnode.core.database import SysNodeDatabase
import os

logger = logging.getLogger(__name__)


class SysNodeCore:
    """
    Clase central que administra el ciclo de vida del nodo P2P.
    Coordina los hilos de red UDP y TCP, expone colas de eventos (Event Broker)
    y mantiene desacoplada la lógica de red de cualquier interfaz (UI, CLI o Web).
    """

    def __init__(self, node_name: str = None, tcp_port: int = DEFAULT_TCP_PORT, db_path: str = None):
        self.tcp_port = tcp_port
        self.local_ip = get_local_lan_ip()
        
        # Database para persistencia de chat y configuraciones (Inicializar primero)
        target_db_path = db_path or os.path.join(os.getcwd(), "SysNode_Received", "history.db")
        self.db = SysNodeDatabase(target_db_path)

        # Identidad Persistente del Nodo
        self.node_id = self.db.get_or_create_device_uuid()
        
        # Nombre del nodo (si no se provee, ver si la DB tiene uno guardado, sino HOST_NAME)
        db_name = self.db.get_local_username()
        self.node_name = node_name or db_name or HOST_NAME

        # Broker de Eventos (Permite múltiples listeners como Desktop UI y Mobile WS)
        self.event_queues = []
        self._broker_lock = threading.Lock()

        # Hilos de descubrimiento UDP
        self.udp_beacon = UDPBeacon(
            node_id=self.node_id,
            tcp_port=self.tcp_port,
            custom_name=self.node_name
        )
        self.udp_beacon.stealth_mode = True  # Silent by default until user confirms
        
        self.udp_listener = UDPListener(
            my_node_id=self.node_id,
            event_callback=self.broadcast_event
        )
        
        # Default to True so it doesn't process beacons while in login screen
        self.udp_listener.stealth_mode = True

        # Servidor TCP para recepción de texto y comandos
        self.tcp_server = TCPServer(
            tcp_port=self.tcp_port,
            event_callback=self.broadcast_event,
            node_id=self.node_id,
            node_name=self.node_name,
            download_dir_getter=self.get_downloads_dir,
            is_paired_checker=self.db.verify_device_trust
        )
        
        # Servidor HTTP de compartición (inicia apagado)
        self.http_server = SharingHTTPServer()

        self.http_server = SharingHTTPServer()

        self._running = False
        self._temp_manual_peers = {}
        
        # Cargar nodos manuales en hilos separados para no bloquear
        threading.Thread(target=self._load_manual_peers, daemon=True).start()
        
    def _load_manual_peers(self):
        manual_peers = self.db.get_manual_peers()
        for node_id, ip, tcp_port in manual_peers:
            self.add_manual_peer(ip, tcp_port)

    def get_downloads_dir(self):
        saved = self.db.get_downloads_path()
        return saved if saved else os.path.abspath("SysNode_Received")

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
            node_id = event_dict.get("sender_id", "unknown")
            text = event_dict.get("text", "")
            msg_uuid = event_dict.get("msg_uuid")
            peer_ip = event_dict.get("peer_ip")
            sender_tcp_port = event_dict.get("sender_tcp_port")
            
            # Registrar dispositivo de paso si no existe o actualizar nombre
            sender_name = event_dict.get("sender_name", "Desconocido")
            self.db.register_device(node_id, sender_name, "Unknown", ip=peer_ip, port=sender_tcp_port)
            if peer_ip and sender_tcp_port:
                self.add_manual_peer(peer_ip, sender_tcp_port)
            
            self.db.save_message(node_id, text, "IN", msg_uuid=msg_uuid)
            
        elif event_dict.get("event") == "MSG_EDITED":
            msg_uuid = event_dict.get("msg_uuid")
            new_text = event_dict.get("new_text", "")
            if msg_uuid and new_text:
                self.db.update_message_text(msg_uuid, new_text)
            
        elif event_dict.get("event") == "FILE_RECEIVED":
            node_id = event_dict.get("sender_id", "unknown")
            filepath = event_dict.get("filepath", "")
            success = event_dict.get("success", False)
            
            if success and filepath:
                # El texto que se guarda en la base de datos es la ruta al archivo con el prefijo FILE:
                self.db.save_message(node_id, f"FILE:{filepath}", "IN")
                
        elif event_dict.get("event") == "COMMAND_RECEIVED":
            node_id = event_dict.get("sender_id", "unknown")
            cmd = event_dict.get("command", "")
            result = event_dict.get("result", "")
            success = event_dict.get("success", False)
            
            # Registrar dispositivo si no existe
            sender_name = event_dict.get("sender_name", "Desconocido")
            peer_ip = event_dict.get("peer_ip")
            sender_tcp_port = event_dict.get("sender_tcp_port")
            self.db.register_device(node_id, sender_name, "Unknown", ip=peer_ip, port=sender_tcp_port)
            if peer_ip and sender_tcp_port:
                self.add_manual_peer(peer_ip, sender_tcp_port)
            
            # Guardamos el comando y su resultado como mensaje IN
            status_text = "[OK]" if success else "[FAIL]"
            self.db.save_message(node_id, f"CMD_RES:{status_text} Comando ejecutado: {cmd}\nResultado:\n{result}", "IN")

        elif event_dict.get("event") == "PAIRING_RESPONSE_RECEIVED":
            node_id = event_dict.get("sender_id", "unknown")
            accepted = event_dict.get("accepted", False)
            trust_token = event_dict.get("trust_token", "")
            
            if accepted and trust_token:
                self.db.set_device_paired(node_id, True, trust_token)
                logger.info(f"Dispositivo {node_id} aceptó la vinculación.")
            else:
                self.db.set_device_paired(node_id, False, None)
                logger.warning(f"Dispositivo {node_id} rechazó la vinculación.")

        elif event_dict.get("event") == "UNPAIR_REQUEST_RECEIVED":
            node_id = event_dict.get("sender_id", "unknown")
            sender_name = event_dict.get("sender_name", "unknown")
            logger.info(f"El dispositivo {node_id} ({sender_name}) ha solicitado la desvinculación.")
            self.db.set_device_paired(node_id, False, None)
            
        event_name = event_dict.get("event")
        if event_name in ["PEER_DISCOVERED", "PEER_UPDATED"]:
            node_id = event_dict.get("node_id", "")
            peer = event_dict.get("peer", {})
            if not node_id and peer:
                node_id = peer.get("node_id")
                
            if node_id:
                if peer:
                    self.db.register_device(
                        node_id, 
                        peer.get("hostname", "Unknown"), 
                        peer.get("os", "Unknown"), 
                        peer.get("ip"), 
                        peer.get("tcp_port")
                    )
                if event_name == "PEER_DISCOVERED":
                    threading.Thread(target=self.sync_pending_messages, args=(node_id,), daemon=True).start()

        with self._broker_lock:
            for q in self.event_queues:
                q.put(event_dict)

    def sync_pending_messages(self, node_id: str):
        """Intenta enviar los mensajes pendientes a un nodo recién conectado."""
        pending = self.db.get_pending_messages(node_id)
        if not pending:
            return
            
        logger.info(f"Sincronizando {len(pending)} mensajes pendientes para {node_id}")
        peers = self.get_active_peers()
        peer = peers.get(node_id)
        if not peer:
            return
            
        for msg_id, text, msg_uuid in pending:
            trust_token = self.db.get_device_trust_token(node_id) or ""
            success, response = TCPClient.send_text(
                peer_ip=peer["ip"],
                peer_port=peer["tcp_port"],
                sender_id=self.node_id,
                sender_name=self.node_name,
                trust_token=trust_token,
                text=text,
                msg_uuid=msg_uuid
            )
            if success:
                self.db.mark_message_delivered(msg_id)
                # Notificar a la UI
                self.broadcast_event({"event": "MESSAGE_DELIVERED", "node_id": node_id, "msg_id": msg_id})
            elif "NOT_PAIRED" in str(response):
                logger.warning(f"Sincronización falló por falta de emparejamiento con {node_id}. Solicitando emparejamiento.")
                self.request_pairing(node_id)
                break  # Stop syncing if not paired

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
        if hasattr(self, 'http_server') and self.http_server:
            self.http_server.stop()

        self._running = False
        logger.info("SysNodeCore detenido exitosamente.")

    def get_active_peers(self) -> Dict[str, Dict[str, Any]]:
        """Obtiene la lista actual de nodos descubiertos en la LAN."""
        return self.udp_listener.get_active_peers()

    def add_manual_peer(self, ip: str, port: int) -> None:
        """Añade manualmente un nodo a la red, intentando PING TCP para descubrirlo."""
        def ping_worker():
            success, response = TCPClient.ping_node(ip, port, self.node_id, self.node_name, sender_tcp_port=self.tcp_port)
            if success:
                remote_node_id = response.get("node_id")
                remote_hostname = response.get("hostname", f"Manual_{ip}")
                remote_os = response.get("os", "Unknown")
                self.udp_listener.add_manual_peer(ip, port, remote_node_id, remote_hostname, remote_os)
                # No guardamos en BD todavía, solo en memoria, hasta que interactuemos con él.
            else:
                # Guardar temporalmente en memoria para que la UI lo muestre como offline
                import uuid
                synthetic_id = f"manual_{uuid.uuid4().hex[:8]}"
                self._temp_manual_peers[synthetic_id] = {
                    "node_id": synthetic_id,
                    "hostname": f"Offline ({ip})",
                    "os": "unknown",
                    "ip": ip,
                    "tcp_port": port,
                    "last_seen": 0, # 0 indicates offline
                    "manual": True
                }
                
        threading.Thread(target=ping_worker, daemon=True).start()

    def send_text_to_peer(self, node_id: str, text: str) -> Tuple[bool, str, str]:
        """Envía un texto al Shared Board de un nodo activo, o lo encola si está offline."""
        import uuid
        msg_uuid = str(uuid.uuid4())
        
        peers = self.get_active_peers()
        peer = peers.get(node_id)
        
        if not peer:
            # El nodo está offline, lo guardamos como pending
            self.db.save_message(node_id, text, "OUT", status="pending", msg_uuid=msg_uuid)
            logger.info(f"Nodo {node_id} offline. Mensaje guardado como pendiente.")
            return True, "Mensaje guardado como pendiente (Nodo Offline).", msg_uuid

        trust_token = self.db.get_device_trust_token(node_id) or ""
        success, response = TCPClient.send_text(
            peer_ip=peer["ip"],
            peer_port=peer["tcp_port"],
            sender_id=self.node_id,
            sender_name=self.node_name,
            trust_token=trust_token,
            text=text,
            msg_uuid=msg_uuid,
            sender_tcp_port=self.tcp_port
        )
        if success:
            self.db.register_device(node_id, peer["hostname"], peer.get("os", "Unknown"))
            if peer.get("manual"):
                self.db.save_manual_peer(node_id, peer["ip"], peer["tcp_port"])
            self.db.save_message(node_id, text, "OUT", status="delivered", msg_uuid=msg_uuid)
        else:
            if "NOT_PAIRED" in str(response):
                self.request_pairing(node_id)
                self.db.save_message(node_id, text, "OUT", status="pending", msg_uuid=msg_uuid)
                return False, "Requiere vinculación previa. Solicitud enviada.", msg_uuid
            else:
                self.db.save_message(node_id, text, "OUT", status="pending", msg_uuid=msg_uuid)
            
        return success, response, msg_uuid

    def edit_remote_message(self, node_id: str, msg_uuid: str, new_text: str) -> Tuple[bool, str]:
        """Envía una petición para editar un mensaje enviado."""
        self.db.update_message_text(msg_uuid, new_text)
        
        peers = self.get_active_peers()
        peer = peers.get(node_id)
        if not peer:
            return True, "Mensaje local actualizado (el nodo está offline, no se propagó)."
            
        trust_token = self.db.get_device_trust_token(node_id) or ""
        success, response = TCPClient.edit_text(
            peer_ip=peer["ip"],
            peer_port=peer["tcp_port"],
            sender_id=self.node_id,
            sender_name=self.node_name,
            trust_token=trust_token,
            msg_uuid=msg_uuid,
            new_text=new_text
        )
        if not success and "NOT_PAIRED" in str(response):
            self.request_pairing(node_id)
        return success, response
        
    def start_sharing_server(self, port: int = 8080) -> str:
        """Inicia el servidor HTTP y devuelve la URL local."""
        self.http_server.start(port=port)
        return f"http://{self.local_ip}:{self.http_server.port}"
        
    def stop_sharing_server(self):
        """Detiene el servidor HTTP."""
        self.http_server.stop()

    def send_command_to_peer(self, node_id: str, command_key: str) -> Tuple[bool, str]:
        """Envía una solicitud de ejecución remota a un nodo activo específico."""
        peers = self.get_active_peers()
        if node_id not in peers:
            return False, f"Nodo con ID '{node_id}' no encontrado en la lista activa."

        peer = peers[node_id]
        
        # Save request to DB
        self.db.save_message(node_id, f"CMD_REQ:{command_key}", "OUT", status="delivered")
        
        trust_token = self.db.get_device_trust_token(node_id) or ""
        success, msg = TCPClient.send_command(
            peer_ip=peer["ip"],
            peer_port=peer["tcp_port"],
            sender_id=self.node_id,
            sender_name=self.node_name,
            trust_token=trust_token,
            command_key=command_key
        )
        
        if not success and "NOT_PAIRED" in str(msg):
            self.request_pairing(node_id)
            msg = "Requiere vinculación previa. Solicitud enviada."
        
        # Save response to DB
        status_text = "[OK]" if success else "[FAIL]"
        self.db.save_message(node_id, f"CMD_RES:{status_text} {msg}", "IN", status="delivered")
        
        return success, msg

    def send_bash_command_to_peer(self, node_id: str, bash_command: str) -> Tuple[bool, str]:
        """Envía una solicitud de ejecución de comando custom a un nodo activo."""
        peers = self.get_active_peers()
        if node_id not in peers:
            return False, f"Nodo con ID '{node_id}' no encontrado en la lista activa."

        peer = peers[node_id]
        
        # Save request to DB
        self.db.save_message(node_id, f"CMD_REQ:Bash -> {bash_command}", "OUT", status="delivered")
        
        trust_token = self.db.get_device_trust_token(node_id) or ""
        success, msg = TCPClient.send_bash_command(
            peer_ip=peer["ip"],
            peer_port=peer["tcp_port"],
            sender_id=self.node_id,
            sender_name=self.node_name,
            trust_token=trust_token,
            bash_command=bash_command
        )
        
        if not success and "NOT_PAIRED" in str(msg):
            self.request_pairing(node_id)
            msg = "Requiere vinculación previa. Solicitud enviada."

        # Save response to DB
        status_text = "[OK]" if success else "[FAIL]"
        self.db.save_message(node_id, f"CMD_RES:{status_text} {msg}", "IN", status="delivered")
        
        return success, msg

    def send_file_to_peer(self, node_id: str, file_path: str, progress_callback=None) -> Tuple[bool, str]:
        """Transmite un archivo binario local al nodo remoto activo sobre TCP."""
        peers = self.get_active_peers()
        if node_id not in peers:
            return False, f"Nodo con ID '{node_id}' no encontrado en la lista activa."

        peer = peers[node_id]
        trust_token = self.db.get_device_trust_token(node_id) or ""
        success, msg = TCPClient.send_file(
            peer_ip=peer["ip"],
            peer_port=peer["tcp_port"],
            sender_id=self.node_id,
            sender_name=self.node_name,
            trust_token=trust_token,
            file_path=file_path,
            progress_callback=progress_callback
        )
        if success:
            self.db.save_message(node_id, f"FILE:{file_path}", "OUT", status="delivered")
        elif "NOT_PAIRED" in str(msg):
            self.request_pairing(node_id)
            msg = "Requiere vinculación previa. Solicitud enviada."
        return success, msg

    def request_pairing(self, node_id: str) -> bool:
        """Envía una solicitud de vinculación a un nodo."""
        peers = self.get_active_peers()
        if node_id not in peers:
            return False
            
        import secrets
        # Generar un token único y robusto
        new_token = secrets.token_hex(32)
        # Guardarlo localmente como temporal o actualizar el token directamente
        # The true pairing only happens when the other accepts, but we need to send OUR token
        # so they can save it.
        # Enviar solicitud
        peer = peers[node_id]
        success, response = TCPClient.send_pairing_request(
            peer_ip=peer["ip"],
            peer_port=peer["tcp_port"],
            sender_id=self.node_id,
            sender_name=self.node_name,
            trust_token=new_token,
            sender_tcp_port=self.tcp_port
        )
        
        if success:
            # We save our generated token to use it later if they accept
            # Actually, the logic is: we trust them using a token they give us, or we give them a token to trust us?
            # It's better if they generate a token for us, or we just generate one and both use it.
            # Let's use a single shared token for the pair.
            # Save it temporarily or just save it directly (not fully paired yet until they respond).
            # To avoid complexity, we can just save it with is_paired=False.
            self.db.set_device_paired(node_id, False, new_token)
            logger.info(f"Solicitud de vinculación enviada a {node_id}")
            return True
        return False

    def respond_pairing(self, node_id: str, accepted: bool, peer_token: str) -> Tuple[bool, str]:
        """Responde a una solicitud de vinculación."""
        peers = self.get_active_peers()
        if node_id not in peers:
            return False, "Nodo no encontrado."
        
        sender_id = node_id
        peer = peers[node_id]
        peer_ip = peer["ip"]
        peer_port = peer["tcp_port"]
        
        from sysnode.network.tcp_client import TCPClient
        
        trust_token = None
        if accepted:
            import uuid
            trust_token = str(uuid.uuid4())
            self.db.set_device_paired(sender_id, True, trust_token)
        else:
            self.db.set_device_paired(sender_id, False, None)
            
        success, msg = TCPClient.send_pairing_response(
            peer_ip=peer_ip,
            peer_port=peer_port,
            sender_id=self.node_id,
            sender_name=self.node_name,
            trust_token=trust_token if accepted else "",
            accepted=accepted,
            sender_tcp_port=self.tcp_port
        )
        return success, msg

    def unpair_device(self, peer_id: str) -> Tuple[bool, str]:
        """Desvincula un dispositivo localmente y le notifica para que haga lo mismo."""
        # 1. Desvincular localmente
        self.db.set_device_paired(peer_id, False, None)
        
        # 2. Notificar al otro dispositivo si está online
        peer_info = self.get_active_peers().get(peer_id)
        if peer_info:
            peer_ip = peer_info.get("ip")
            peer_port = peer_info.get("tcp_port", 50001)
            
            from sysnode.network.tcp_client import TCPClient
            success, msg = TCPClient.send_unpair_request(
                peer_ip=peer_ip,
                peer_port=peer_port,
                sender_id=self.node_id,
                sender_name=self.node_name,
                sender_tcp_port=self.tcp_port
            )
            return success, msg
        return True, "Desvinculado localmente (dispositivo no estaba online)."

    def is_running(self) -> bool:
        return self._running
