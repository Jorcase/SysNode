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
        self.selected_node_ip = None
        
        # Configuración de Ventana
        self.title(f"SysNode - {self.core.node_name}")
        self.geometry("900x600")
        self.minsize(800, 500)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.build_ui()
        
        # Iniciar polling thread-safe de eventos
        self.after(100, self.poll_event_queue)
        
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
    
    def append_to_chat(self, text):
        self.chat_textbox.configure(state="normal")
        self.chat_textbox.insert("end", text + "\n")
        self.chat_textbox.see("end")
        self.chat_textbox.configure(state="disabled")

    def on_node_select(self, ip, name):
        self.selected_node_ip = ip
        logger.info(f"[UI] Nodo destino seleccionado: {name} ({ip})")
        # Actualizar colores de los botones para marcar el activo
        for node_ip, btn in self.node_buttons.items():
            if node_ip == ip:
                btn.configure(fg_color="#2ECC71", text_color="black") # Verde activo
            else:
                btn.configure(fg_color=["#3a7ebf", "#1f538d"], text_color=["gray10", "#DCE4EE"]) # Default CTk
                
        self.append_to_chat(f"--- Seleccionaste el nodo destino: {name} ({ip}) ---")

    def send_text_message(self):
        if not self.selected_node_ip:
            messagebox.showwarning("Atención", "Debes seleccionar un nodo en el Radar LAN primero.")
            return
            
        msg = self.msg_entry.get().strip()
        if not msg: return
        
        node = self.core.get_node_info(self.selected_node_ip)
        if not node: return
        
        success = self.core.send_text_message(self.selected_node_ip, node['tcp_port'], msg)
        if success:
            self.append_to_chat(f"[{self.core.node_name} -> {node['name']}]: {msg}")
            self.msg_entry.delete(0, "end")
        else:
            self.append_to_chat(f"❌ Error al enviar mensaje a {node['name']}.")
            
    def send_sysadmin_cmd(self, command):
        if not self.selected_node_ip:
            messagebox.showwarning("Atención", "Debes seleccionar un nodo en el Radar LAN primero.")
            return
            
        node = self.core.get_node_info(self.selected_node_ip)
        if not node: return
        
        self.append_to_chat(f"⚡ Ejecutando {command} en {node['name']}...")
        success = self.core.send_command(self.selected_node_ip, node['tcp_port'], command)
        if not success:
            self.append_to_chat(f"❌ Error al conectar con {node['name']} para comando.")
            
    def select_and_send_file(self):
        if not self.selected_node_ip:
            messagebox.showwarning("Atención", "Debes seleccionar un nodo en el Radar LAN primero.")
            return
            
        node = self.core.get_node_info(self.selected_node_ip)
        if not node: return
        
        filepath = filedialog.askopenfilename(title="Seleccionar archivo para enviar")
        if not filepath: return
        
        self.progress_label.configure(text=f"Enviando archivo a {node['name']}...")
        self.progress_bar.set(0)
        
        # Enviar el archivo. (Nota: En una implementación 100% no bloqueante, 
        # file_transfer.py debería notificar progreso por cola. Por ahora en Phase 3 
        # el print_progress imprime en consola. Veremos la consola o actualizamos a 1 al finalizar).
        success = self.core.send_file(self.selected_node_ip, node['tcp_port'], filepath)
        
        if success:
            self.progress_bar.set(1.0)
            self.progress_label.configure(text="✅ ¡Archivo enviado con éxito!")
            self.append_to_chat(f"✅ Archivo enviado exitosamente a {node['name']}.")
        else:
            self.progress_bar.set(0)
            self.progress_label.configure(text="❌ Error en la transferencia.")
            self.append_to_chat(f"❌ Error al enviar archivo a {node['name']}.")
            
    def poll_event_queue(self):
        """Consume eventos de SysNodeCore de forma segura (Thread-Safe) para actualizar la UI."""
        
        # 1. Actualizar Radar LAN desde shared_state
        current_peers = self.core.get_active_peers()
        
        # Remover botones de nodos que ya no están
        for ip in list(self.node_buttons.keys()):
            if ip not in current_peers:
                self.node_buttons[ip].destroy()
                del self.node_buttons[ip]
                if self.selected_node_ip == ip:
                    self.selected_node_ip = None
                    self.append_to_chat("--- El nodo destino seleccionado se ha desconectado. ---")
                    
        # Agregar/Actualizar botones de nodos activos
        for ip, info in current_peers.items():
            display_text = f"{info['name']} ({ip})\n{info['os']}"
            if ip not in self.node_buttons:
                btn = ctk.CTkButton(self.nodes_frame, text=display_text, 
                                    command=lambda ip=ip, name=info['name']: self.on_node_select(ip, name))
                btn.pack(pady=5, padx=5, fill="x")
                self.node_buttons[ip] = btn
            else:
                # Actualizar el texto por si cambió el nombre
                if self.node_buttons[ip].cget("text") != display_text:
                    self.node_buttons[ip].configure(text=display_text)
                    
        # 2. Consumir la cola de eventos de red
        while True:
            try:
                event = self.core.event_queue.get_nowait()
                self.handle_network_event(event)
            except queue.Empty:
                break
                
        # Programar la próxima llamada en 100ms
        self.after(100, self.poll_event_queue)
        
    def handle_network_event(self, event):
        etype = event.get('type')
        data = event.get('data', {})
        sender_ip = event.get('sender_ip', 'Desconocido')
        
        if etype == "TEXT_MSG":
            msg = data.get('content', '')
            # Buscamos el nombre del remitente si está en el radar
            peer = self.core.get_node_info(sender_ip)
            sender_name = peer['name'] if peer else sender_ip
            self.append_to_chat(f"[{sender_name}]: {msg}")
            
        elif etype == "CMD_RESPONSE":
            response = data.get('response', '')
            peer = self.core.get_node_info(sender_ip)
            sender_name = peer['name'] if peer else sender_ip
            self.append_to_chat(f"[SysAdmin {sender_name}]: {response}")
            
        elif etype == "FILE_RECEIVED":
            filepath = data.get('filepath', '')
            peer = self.core.get_node_info(sender_ip)
            sender_name = peer['name'] if peer else sender_ip
            self.append_to_chat(f"📥 Archivo recibido de {sender_name} guardado en:\n{filepath}")
            
        elif etype == "ERROR":
            self.append_to_chat(f"❌ Error de {sender_ip}: {data.get('message', 'Error desconocido')}")

    def on_closing(self):
        logger.info("[UI] Cerrando la interfaz de escritorio...")
        self.core.stop()
        self.destroy()
        
def run_desktop_app(node_core):
    app = SysNodeDesktopApp(node_core)
    app.mainloop()
