"""
src/ui/desktop_app.py
Interfaz Gráfica de Escritorio usando CustomTkinter.
Implementa el paradigma Thread-Safe consultando la event_queue del SysNodeCore.
"""

import sys
import queue
import logging
from tkinter import filedialog, messagebox

try:
    import qrcode
    from PIL import Image
except ImportError:
    pass

try:
    import customtkinter as ctk
except ImportError:
    print("❌ ERROR: La biblioteca 'customtkinter' no está instalada.")
    print("👉 Instalala usando: pip install -r requirements.txt")
    sys.exit(1)

logger = logging.getLogger("SysNode.DesktopApp")

class SysNodeDesktopApp(ctk.CTk):
    def __init__(self, node_core):
        super().__init__()
        
        self.core = node_core
        self.selected_node_id = None
        self.event_queue = self.core.register_event_queue()
        
        # Configuración de Ventana
        self.title(f"SysNode - {self.core.node_name}")
        self.geometry("900x600")
        self.minsize(800, 500)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.build_ui()
        self.load_chat_history()
        
        # Iniciar polling thread-safe de eventos
        self.after(100, self.poll_event_queue)
        
    def load_chat_history(self):
        recent_messages = self.core.db.get_recent_messages(50)
        if recent_messages:
            self.append_to_chat("--- Historial de Mensajes ---", add_timestamp=False)
            for ts, sender, text, direction in recent_messages:
                # Extraer solo HH:MM:SS del timestamp (Y-m-d H:M:S)
                time_only = ts.split(" ")[1]
                if direction == "IN":
                    self.append_to_chat(f"[{time_only}] [{sender}]: {text}", add_timestamp=False)
                else:
                    self.append_to_chat(f"[{time_only}] [{self.core.node_name} -> {sender}]: {text}", add_timestamp=False)
            self.append_to_chat("--- Fin del Historial ---", add_timestamp=False)
        
    def build_ui(self):
        # Grid layout principal: 1 fila, 2 columnas (Sidebar y Main)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        
        # --- PANEL IZQUIERDO (SIDEBAR - Radar LAN) ---
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(2, weight=1) # Espacio para la lista
        
        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="SysNode P2P", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))
        
        # Datos del nodo local
        local_info = f"Nodo: {self.core.node_name}\nIP: {self.core.local_ip}\nPuerto TCP: {self.core.tcp_port}"
        self.info_label = ctk.CTkLabel(self.sidebar_frame, text=local_info, justify="left", text_color="gray70")
        self.info_label.grid(row=1, column=0, padx=10, pady=10)
        
        self.radar_label = ctk.CTkLabel(self.sidebar_frame, text="Radar LAN (Nodos Activos):", font=ctk.CTkFont(weight="bold"))
        self.radar_label.grid(row=2, column=0, padx=20, pady=(20, 5), sticky="sw")
        
        # Scrollable Frame para la lista de nodos
        self.nodes_frame = ctk.CTkScrollableFrame(self.sidebar_frame, label_text="Descubiertos")
        self.nodes_frame.grid(row=3, column=0, padx=10, pady=10, sticky="nsew")
        self.node_buttons = {} # ip -> ctk.CTkButton
        
        self.btn_add_manual = ctk.CTkButton(self.sidebar_frame, text="[+] Añadir Nodo (IP)", command=self.prompt_manual_ip)
        self.btn_add_manual.grid(row=4, column=0, padx=20, pady=(0, 10), sticky="ew")
        
        self.btn_show_qr = ctk.CTkButton(self.sidebar_frame, text="[QR] Ver Mi QR", command=self.show_qr_code, fg_color="#8E44AD", hover_color="#732D91")
        self.btn_show_qr.grid(row=5, column=0, padx=20, pady=(0, 20), sticky="ew")
        
        # --- PANEL DERECHO (MAIN - Pestañas) ---
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        
        self.tabview.add("Shared Board")
        self.tabview.add("File Drop")
        self.tabview.add("SysAdmin")
        
        self.build_tab_shared_board()
        self.build_tab_file_drop()
        self.build_tab_sysadmin()
        
    def build_tab_shared_board(self):
        tab = self.tabview.tab("Shared Board")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)
        
        self.chat_textbox = ctk.CTkTextbox(tab, state="disabled")
        self.chat_textbox.grid(row=0, column=0, columnspan=2, padx=10, pady=10, sticky="nsew")
        
        self.msg_entry = ctk.CTkEntry(tab, placeholder_text="Escribe un mensaje para el nodo seleccionado...")
        self.msg_entry.grid(row=1, column=0, padx=10, pady=10, sticky="ew")
        self.msg_entry.bind("<Return>", lambda e: self.send_text_message())
        
        self.send_btn = ctk.CTkButton(tab, text="Enviar Texto", command=self.send_text_message)
        self.send_btn.grid(row=1, column=1, padx=10, pady=10)
        
    def build_tab_file_drop(self):
        tab = self.tabview.tab("File Drop")
        tab.grid_columnconfigure(0, weight=1)
        
        title = ctk.CTkLabel(tab, text="Transferencia de Archivos (P2P)", font=ctk.CTkFont(size=18, weight="bold"))
        title.grid(row=0, column=0, pady=(20, 10))
        
        desc = ctk.CTkLabel(tab, text="Seleccioná un archivo para enviarlo directamente al nodo destino.")
        desc.grid(row=1, column=0, pady=10)
        
        self.btn_select_file = ctk.CTkButton(tab, text="Seleccionar Archivo y Enviar", command=self.select_and_send_file)
        self.btn_select_file.grid(row=2, column=0, pady=20)
        
        self.progress_bar = ctk.CTkProgressBar(tab)
        self.progress_bar.grid(row=3, column=0, padx=40, pady=10, sticky="ew")
        self.progress_bar.set(0) # Inicializado en 0
        
        self.progress_label = ctk.CTkLabel(tab, text="")
        self.progress_label.grid(row=4, column=0)
        
    def build_tab_sysadmin(self):
        tab = self.tabview.tab("SysAdmin")
        
        title = ctk.CTkLabel(tab, text="Panel de Administración Remota", font=ctk.CTkFont(size=18, weight="bold"))
        title.pack(pady=20)
        
        desc = ctk.CTkLabel(tab, text="Envía comandos de forma segura (validados por lista blanca) al nodo destino.")
        desc.pack(pady=10)
        
        btn_lock = ctk.CTkButton(tab, text="Bloquear Pantalla (CMD_LOCK_SCREEN)", fg_color="#C0392B", hover_color="#922B21", 
                                 command=lambda: self.send_sysadmin_cmd("CMD_LOCK_SCREEN"))
        btn_lock.pack(pady=10)
        
        btn_ping = ctk.CTkButton(tab, text="Test de Internet (CMD_PING)", 
                                 command=lambda: self.send_sysadmin_cmd("CMD_PING"))
        btn_ping.pack(pady=10)
        
        btn_info = ctk.CTkButton(tab, text="Información del Sistema (CMD_SYS_INFO)", 
                                 command=lambda: self.send_sysadmin_cmd("CMD_SYS_INFO"))
        btn_info.pack(pady=10)
        
    # --- LOGICA E INTERACCION ---
    
    def prompt_manual_ip(self):
        dialog = ctk.CTkInputDialog(text="Ingresá IP:Puerto (ej: 192.168.0.10 o 192.168.0.33:41849):", title="Añadir Nodo Manual")
        user_input = dialog.get_input()
        if user_input:
            parts = user_input.strip().split(":")
            ip = parts[0]
            port = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 50001
            self.core.add_manual_peer(ip, port)
            self.append_to_chat(f"[INFO] Nodo manual añadido: {ip}:{port}")

    def show_qr_code(self):
        try:
            import qrcode
            from PIL import Image
        except ImportError:
            messagebox.showerror("Error", "Faltan librerías para generar el QR. Ejecutá: pip install qrcode Pillow")
            return
            
        qr_data = f"sysnode://{self.core.local_ip}:{self.core.tcp_port}"
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(qr_data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Guardamos en un archivo temporal
        import tempfile
        import os
        temp_path = os.path.join(tempfile.gettempdir(), "sysnode_qr.png")
        img.save(temp_path)
        
        # Mostrar en ventana flotante
        qr_window = ctk.CTkToplevel(self)
        qr_window.title("Código QR de Conexión")
        qr_window.geometry("350x400")
        qr_window.attributes("-topmost", True)
        qr_window.resizable(False, False)
        
        lbl_info = ctk.CTkLabel(qr_window, text="Escaneá este QR con el celular", font=ctk.CTkFont(weight="bold"))
        lbl_info.pack(pady=10)
        
        my_image = ctk.CTkImage(light_image=Image.open(temp_path), size=(250, 250))
        image_label = ctk.CTkLabel(qr_window, image=my_image, text="")
        image_label.pack(pady=10)
        
        lbl_uri = ctk.CTkLabel(qr_window, text=qr_data, text_color="gray50")
        lbl_uri.pack()

    def append_to_chat(self, text, add_timestamp=True):
        self.chat_textbox.configure(state="normal")
        if add_timestamp:
            import datetime
            now_time = datetime.datetime.now().strftime("%H:%M:%S")
            text = f"[{now_time}] {text}"
        self.chat_textbox.insert("end", text + "\n")
        self.chat_textbox.see("end")
        self.chat_textbox.configure(state="disabled")

    def on_node_select(self, node_id, hostname):
        self.selected_node_id = node_id
        logger.info(f"[UI] Nodo destino seleccionado: {hostname} ({node_id[:8]})")
        # Actualizar colores de los botones para marcar el activo
        for n_id, btn in self.node_buttons.items():
            if n_id == node_id:
                btn.configure(fg_color="#2ECC71", text_color="black") # Verde activo
            else:
                btn.configure(fg_color=["#3a7ebf", "#1f538d"], text_color=["gray10", "#DCE4EE"]) # Default CTk
                
        self.append_to_chat(f"--- Seleccionaste el nodo destino: {hostname} ---", add_timestamp=False)

    def send_text_message(self):
        if not self.selected_node_id:
            messagebox.showwarning("Atención", "Debes seleccionar un nodo en el Radar LAN primero.")
            return
            
        msg = self.msg_entry.get().strip()
        if not msg: return
        
        peers = self.core.get_active_peers()
        node = peers.get(self.selected_node_id)
        if not node: return
        
        success, err_msg = self.core.send_text_to_peer(self.selected_node_id, msg)
        if success:
            self.append_to_chat(f"[{self.core.node_name} -> {node['hostname']}]: {msg}")
            self.msg_entry.delete(0, "end")
        else:
            self.append_to_chat(f"[ERROR] Error al enviar mensaje a {node['hostname']}: {err_msg}")
            
    def send_sysadmin_cmd(self, command):
        if not self.selected_node_id:
            messagebox.showwarning("Atención", "Debes seleccionar un nodo en el Radar LAN primero.")
            return
            
        peers = self.core.get_active_peers()
        node = peers.get(self.selected_node_id)
        if not node: return
        
        self.append_to_chat(f"[EXEC] Ejecutando {command} en {node['hostname']}...")
        success, result_msg = self.core.send_command_to_peer(self.selected_node_id, command)
        if not success:
            self.append_to_chat(f"[ERROR] Error al conectar con {node['hostname']} para comando: {result_msg}")
            
    def select_and_send_file(self):
        if not self.selected_node_id:
            messagebox.showwarning("Atención", "Debes seleccionar un nodo en el Radar LAN primero.")
            return
            
        peers = self.core.get_active_peers()
        node = peers.get(self.selected_node_id)
        if not node: return
        
        filepath = filedialog.askopenfilename(title="Seleccionar archivo para enviar")
        if not filepath: return
        
        self.progress_label.configure(text=f"Enviando archivo a {node['hostname']}...")
        self.progress_bar.set(0)
        
        def progress_cb(current, total):
            # Usar after para no bloquear si lo llama el hilo TCP
            self.after(0, lambda: self.progress_bar.set(current/total))

        success, err_msg = self.core.send_file_to_peer(self.selected_node_id, filepath, progress_cb)
        
        if success:
            self.progress_bar.set(1.0)
            self.progress_label.configure(text="[SUCCESS] Archivo enviado con éxito!")
            self.append_to_chat(f"[INFO] Archivo enviado exitosamente a {node['hostname']}.")
        else:
            self.progress_bar.set(0)
            self.progress_label.configure(text="[ERROR] Error en la transferencia.")
            self.append_to_chat(f"[ERROR] Error al enviar archivo a {node['hostname']}: {err_msg}")
            
    def poll_event_queue(self):
        """Consume eventos de SysNodeCore de forma segura (Thread-Safe) para actualizar la UI."""
        
        # 1. Actualizar Radar LAN desde shared_state
        current_peers = self.core.get_active_peers()
        
        # Remover botones de nodos que ya no están
        for node_id in list(self.node_buttons.keys()):
            if node_id not in current_peers:
                self.node_buttons[node_id].destroy()
                del self.node_buttons[node_id]
                if self.selected_node_id == node_id:
                    self.selected_node_id = None
                    self.append_to_chat("--- El nodo destino seleccionado se ha desconectado. ---")
                    
        # Agregar/Actualizar botones de nodos activos
        for node_id, info in current_peers.items():
            display_text = f"{info['hostname']} ({info['ip']})\n{info['os']}"
            if node_id not in self.node_buttons:
                btn = ctk.CTkButton(self.nodes_frame, text=display_text, 
                                    command=lambda nid=node_id, hname=info['hostname']: self.on_node_select(nid, hname))
                btn.pack(pady=5, padx=5, fill="x")
                self.node_buttons[node_id] = btn
            else:
                # Actualizar el texto por si cambió el nombre
                if self.node_buttons[node_id].cget("text") != display_text:
                    self.node_buttons[node_id].configure(text=display_text)
                    
        # 2. Consumir la cola de eventos de red
        while True:
            try:
                event = self.event_queue.get_nowait()
                self.handle_network_event(event)
            except queue.Empty:
                break
                
        # Programar la próxima llamada en 100ms
        self.after(100, self.poll_event_queue)
        
    def handle_network_event(self, event):
        etype = event.get('event')
        
        # Ignorar eventos puramente UDP si no se necesitan en chat (PEER_DISCOVERED, etc)
        if etype not in ["TEXT_RECEIVED", "COMMAND_RECEIVED", "FILE_RECEIVED", "FILE_PROGRESS"]:
            return
            
        sender_name = event.get('sender_name', 'Desconocido')
        
        if etype == "TEXT_RECEIVED":
            msg = event.get('text', '')
            self.append_to_chat(f"[{sender_name}]: {msg}")
            
        elif etype == "COMMAND_RECEIVED":
            response = event.get('result', '')
            success = event.get('success', False)
            icon = "[OK]" if success else "[FAIL]"
            self.append_to_chat(f"[SysAdmin {sender_name}] {icon}: {response}")
            
        elif etype == "FILE_RECEIVED":
            filepath = event.get('filepath', '')
            success = event.get('success', False)
            if success:
                self.append_to_chat(f"[DOWNLOAD] Archivo recibido de {sender_name} guardado en:\n{filepath}")
            else:
                self.append_to_chat(f"[ERROR] Error al recibir archivo de {sender_name}: {event.get('msg')}")
                
        elif etype == "FILE_PROGRESS":
            direction = event.get('direction')
            if direction == "RECEIVING":
                current = event.get('current', 0)
                total = event.get('total', 1)
                self.progress_bar.set(current / total)
                self.progress_label.configure(text=f"Recibiendo de {sender_name}: {int((current/total)*100)}%")
                if current >= total:
                    self.progress_label.configure(text="[SUCCESS] Archivo recibido con éxito!")

    def on_closing(self):
        logger.info("[UI] Cerrando la interfaz de escritorio...")
        self.core.stop()
        self.destroy()
        
def run_desktop_app(node_core):
    app = SysNodeDesktopApp(node_core)
    app.mainloop()
