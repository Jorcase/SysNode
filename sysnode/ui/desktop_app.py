"""
sysnode/ui/desktop_app.py
Interfaz Gráfica de Escritorio usando CustomTkinter.
Implementa un diseño Split-View moderno (tipo chat) y persistencia en DB normalizada.
"""

import sys
import queue
import logging
import os
import tempfile
import datetime
from tkinter import filedialog, messagebox

try:
    import qrcode
    from PIL import Image
except ImportError:
    pass

try:
    import customtkinter as ctk
except ImportError:
    print("[ERROR] La biblioteca 'customtkinter' no está instalada.")
    print("Instalala usando: pip install -r requirements.txt")
    sys.exit(1)

logger = logging.getLogger("SysNode.DesktopApp")

class SysNodeDesktopApp(ctk.CTk):
    def __init__(self, node_core):
        super().__init__()
        
        self.core = node_core
        self.selected_node_id = None
        self.event_queue = self.core.register_event_queue()
        
        # Configuración de Ventana
        self.title(f"SysNode")
        self.geometry("950x650")
        self.minsize(800, 500)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Validar Perfil de Usuario
        self.check_user_profile()
        
        self.build_ui()
        
        # Iniciar polling thread-safe de eventos
        self.after(100, self.poll_event_queue)
        
    def check_user_profile(self):
        username = self.core.db.get_local_username()
        if not username:
            dialog = ctk.CTkInputDialog(text="Bienvenido a SysNode.\nIngresá tu nombre de usuario para continuar:", title="Crear Perfil")
            user_input = dialog.get_input()
            if user_input and user_input.strip():
                username = user_input.strip()
                self.core.db.set_local_username(username)
                self.core.node_name = username
                # Hay que actualizar el beacon si cambió el nombre
                self.core.udp_beacon.custom_name = username
            else:
                messagebox.showwarning("Atención", "No ingresaste un nombre. Se usará el nombre por defecto del sistema.")
                self.core.db.set_local_username(self.core.node_name)
        else:
            self.core.node_name = username
            self.core.udp_beacon.custom_name = username
            
    def build_ui(self):
        # Grid layout principal: 1 fila, 2 columnas (Sidebar y Main Chat)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        
        # --- PANEL IZQUIERDO (SIDEBAR - Dispositivos) ---
        self.sidebar_frame = ctk.CTkFrame(self, width=250, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(2, weight=1) 
        
        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="SysNode", font=ctk.CTkFont(size=24, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))
        
        local_info = f"👤 {self.core.node_name}\nIP: {self.core.local_ip}:{self.core.tcp_port}"
        self.info_label = ctk.CTkLabel(self.sidebar_frame, text=local_info, justify="left", text_color="gray70")
        self.info_label.grid(row=1, column=0, padx=10, pady=5)
        
        # Lista de dispositivos
        self.nodes_frame = ctk.CTkScrollableFrame(self.sidebar_frame, label_text="Dispositivos:")
        self.nodes_frame.grid(row=2, column=0, padx=10, pady=10, sticky="nsew")
        self.node_buttons = {} # ip -> ctk.CTkButton
        
        self.btn_add_manual = ctk.CTkButton(self.sidebar_frame, text="[+] Añadir por IP", command=self.prompt_manual_ip)
        self.btn_add_manual.grid(row=3, column=0, padx=20, pady=(0, 10), sticky="ew")
        
        self.btn_show_qr = ctk.CTkButton(self.sidebar_frame, text="[QR] Mostrar Mi QR", command=self.show_qr_code, fg_color="#8E44AD", hover_color="#732D91")
        self.btn_show_qr.grid(row=4, column=0, padx=20, pady=(0, 20), sticky="ew")
        
        # --- PANEL DERECHO (MAIN CHAT) ---
        self.main_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.main_frame.grid_rowconfigure(1, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)
        
        # Cabecera del chat
        self.chat_header = ctk.CTkFrame(self.main_frame, height=50, corner_radius=8)
        self.chat_header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        
        self.chat_title = ctk.CTkLabel(self.chat_header, text="Seleccioná un dispositivo para chatear", font=ctk.CTkFont(size=16, weight="bold"))
        self.chat_title.pack(side="left", padx=15, pady=10)
        
        self.btn_open_folder = ctk.CTkButton(self.chat_header, text="[📁] Descargas", width=100, command=self.open_downloads_folder)
        self.btn_open_folder.pack(side="right", padx=10, pady=10)
        
        # Área de mensajes (Textbox)
        self.chat_textbox = ctk.CTkTextbox(self.main_frame, state="disabled", wrap="word", font=ctk.CTkFont(size=14))
        self.chat_textbox.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        
        # Barra inferior (Input + Botones)
        self.input_frame = ctk.CTkFrame(self.main_frame, corner_radius=8)
        self.input_frame.grid(row=2, column=0, sticky="ew")
        self.input_frame.grid_columnconfigure(0, weight=1)
        
        self.msg_entry = ctk.CTkEntry(self.input_frame, placeholder_text="Escribí un mensaje...", height=40)
        self.msg_entry.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        self.msg_entry.bind("<Return>", lambda e: self.send_text_message())
        
        self.btn_send = ctk.CTkButton(self.input_frame, text="Enviar", width=80, command=self.send_text_message)
        self.btn_send.grid(row=0, column=1, padx=(0, 10), pady=10)
        
        self.btn_attach = ctk.CTkButton(self.input_frame, text="[📎] Archivo", width=80, fg_color="#2c3e50", command=self.select_and_send_file)
        self.btn_attach.grid(row=0, column=2, padx=(0, 10), pady=10)
        
        self.btn_cmd = ctk.CTkButton(self.input_frame, text="[⚡] Comando", width=80, fg_color="#C0392B", hover_color="#922B21", command=self.open_command_menu)
        self.btn_cmd.grid(row=0, column=3, padx=(0, 10), pady=10)

        # Progress bar oculta por defecto
        self.progress_bar = ctk.CTkProgressBar(self.main_frame)
        self.progress_bar.set(0)
        
    def load_chat_history(self, node_id):
        self.chat_textbox.configure(state="normal")
        self.chat_textbox.delete("1.0", "end") # Limpiar chat actual
        self.chat_textbox.configure(state="disabled")
        
        recent_messages = self.core.db.get_chat_history(node_id, 50)
        if not recent_messages:
            self.append_to_chat("--- No hay mensajes previos con este dispositivo ---", add_timestamp=False)
            return
            
        for ts, text, direction in recent_messages:
            time_only = ts.split(" ")[1]
            if direction == "IN":
                self.append_to_chat(f"[{time_only}] [Remoto]: {text}", add_timestamp=False)
            else:
                self.append_to_chat(f"[{time_only}] [Yo]: {text}", add_timestamp=False)
        self.append_to_chat("--- Historial cargado ---", add_timestamp=False)
        
    def append_to_chat(self, text, add_timestamp=True):
        self.chat_textbox.configure(state="normal")
        if add_timestamp:
            now_time = datetime.datetime.now().strftime("%H:%M:%S")
            text = f"[{now_time}] {text}"
        self.chat_textbox.insert("end", text + "\n")
        self.chat_textbox.see("end")
        self.chat_textbox.configure(state="disabled")

    def on_node_select(self, node_id, hostname):
        self.selected_node_id = node_id
        logger.info(f"[UI] Dispositivo seleccionado: {hostname} ({node_id[:8]})")
        
        self.chat_title.configure(text=f"Chat con: {hostname}")
        
        for n_id, btn in self.node_buttons.items():
            if n_id == node_id:
                btn.configure(fg_color="#2ECC71", text_color="black")
            else:
                btn.configure(fg_color=["#3a7ebf", "#1f538d"], text_color=["gray10", "#DCE4EE"])
                
        self.load_chat_history(node_id)

    def prompt_manual_ip(self):
        dialog = ctk.CTkInputDialog(text="Ingresá IP:Puerto (ej: 192.168.0.10:50001):", title="Añadir Manual")
        user_input = dialog.get_input()
        if user_input:
            parts = user_input.strip().split(":")
            ip = parts[0]
            port = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 50001
            self.core.add_manual_peer(ip, port)
            messagebox.showinfo("Añadido", f"IP {ip}:{port} añadida a la lista.")

    def open_downloads_folder(self):
        import platform
        import subprocess
        downloads_path = os.path.join(os.getcwd(), "SysNode_Received")
        os.makedirs(downloads_path, exist_ok=True)
        
        try:
            if platform.system() == "Windows":
                os.startfile(downloads_path)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", downloads_path])
            else:
                subprocess.Popen(["xdg-open", downloads_path])
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir la carpeta: {e}")

    def show_qr_code(self):
        try:
            import qrcode
            from PIL import Image
        except ImportError:
            messagebox.showerror("Error", "Faltan librerías. Ejecutá: pip install qrcode Pillow")
            return
            
        qr_data = f"sysnode://{self.core.local_ip}:{self.core.tcp_port}"
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(qr_data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        temp_path = os.path.join(tempfile.gettempdir(), "sysnode_qr.png")
        img.save(temp_path)
        
        qr_window = ctk.CTkToplevel(self)
        qr_window.title("Mi Código QR")
        qr_window.geometry("350x400")
        qr_window.attributes("-topmost", True)
        qr_window.resizable(False, False)
        
        lbl_info = ctk.CTkLabel(qr_window, text="Escaneá este QR con tu dispositivo móvil", font=ctk.CTkFont(weight="bold"))
        lbl_info.pack(pady=10)
        
        my_image = ctk.CTkImage(light_image=Image.open(temp_path), size=(250, 250))
        image_label = ctk.CTkLabel(qr_window, image=my_image, text="")
        image_label.pack(pady=10)
        
        lbl_uri = ctk.CTkLabel(qr_window, text=qr_data, text_color="gray50")
        lbl_uri.pack()

    def send_text_message(self):
        if not self.selected_node_id:
            messagebox.showwarning("Atención", "Seleccioná un dispositivo primero.")
            return
            
        msg = self.msg_entry.get().strip()
        if not msg: return
        
        peers = self.core.get_active_peers()
        node = peers.get(self.selected_node_id)
        if not node: return
        
        success, err_msg = self.core.send_text_to_peer(self.selected_node_id, msg)
        if success:
            self.append_to_chat(f"[Yo]: {msg}")
            self.msg_entry.delete(0, "end")
        else:
            self.append_to_chat(f"[ERROR] No se pudo enviar: {err_msg}")
            
    def open_command_menu(self):
        if not self.selected_node_id:
            messagebox.showwarning("Atención", "Seleccioná un dispositivo primero.")
            return
            
        menu_window = ctk.CTkToplevel(self)
        menu_window.title("Comandos Remotos")
        menu_window.geometry("300x250")
        menu_window.attributes("-topmost", True)
        
        lbl = ctk.CTkLabel(menu_window, text="Seleccioná un comando a ejecutar:")
        lbl.pack(pady=10)
        
        cmds = [
            ("Test de Conectividad", "CMD_PING"),
            ("Información de Sistema", "CMD_SYS_INFO"),
            ("Bloquear Pantalla", "CMD_LOCK_SCREEN")
        ]
        
        for name, cmd_key in cmds:
            btn = ctk.CTkButton(menu_window, text=name, command=lambda c=cmd_key: [self.send_sysadmin_cmd(c), menu_window.destroy()])
            btn.pack(pady=5, fill="x", padx=20)

    def send_sysadmin_cmd(self, command):
        if not self.selected_node_id: return
        peers = self.core.get_active_peers()
        node = peers.get(self.selected_node_id)
        if not node: return
        
        self.append_to_chat(f"[EXEC] Enviando comando: {command}...")
        success, result_msg = self.core.send_command_to_peer(self.selected_node_id, command)
        if not success:
            self.append_to_chat(f"[ERROR] Falló comando: {result_msg}")
            
    def select_and_send_file(self):
        if not self.selected_node_id:
            messagebox.showwarning("Atención", "Seleccioná un dispositivo primero.")
            return
            
        peers = self.core.get_active_peers()
        node = peers.get(self.selected_node_id)
        if not node: return
        
        filepath = filedialog.askopenfilename(title="Seleccionar archivo")
        if not filepath: return
        
        self.progress_bar.grid(row=3, column=0, sticky="ew", padx=10, pady=5)
        self.progress_bar.set(0)
        
        def progress_cb(current, total):
            self.after(0, lambda: self.progress_bar.set(current/total))

        success, err_msg = self.core.send_file_to_peer(self.selected_node_id, filepath, progress_cb)
        
        if success:
            self.progress_bar.set(1.0)
            self.append_to_chat(f"[INFO] Archivo enviado exitosamente: {os.path.basename(filepath)}")
        else:
            self.progress_bar.set(0)
            self.append_to_chat(f"[ERROR] Error al enviar archivo: {err_msg}")
        
        self.after(2000, lambda: self.progress_bar.grid_forget()) # Ocultar barra despues de 2s
            
    def poll_event_queue(self):
        current_peers = self.core.get_active_peers()
        
        # Limpiar desconectados
        for node_id in list(self.node_buttons.keys()):
            if node_id not in current_peers:
                self.node_buttons[node_id].destroy()
                del self.node_buttons[node_id]
                if self.selected_node_id == node_id:
                    self.selected_node_id = None
                    self.chat_title.configure(text="Dispositivo desconectado.")
                    
        # Agregar/Actualizar
        for node_id, info in current_peers.items():
            icon_os = "[PC]" if "Desktop" in info['os'] or "Windows" in info['os'] or "Linux" in info['os'] else "[Móvil]"
            display_text = f"{icon_os} {info['hostname']} ({info['ip']})"
            if node_id not in self.node_buttons:
                btn = ctk.CTkButton(self.nodes_frame, text=display_text, anchor="w",
                                    command=lambda nid=node_id, hname=info['hostname']: self.on_node_select(nid, hname))
                btn.pack(pady=2, padx=2, fill="x")
                self.node_buttons[node_id] = btn
            else:
                if self.node_buttons[node_id].cget("text") != display_text:
                    self.node_buttons[node_id].configure(text=display_text)
                    
        while True:
            try:
                event = self.event_queue.get_nowait()
                self.handle_network_event(event)
            except queue.Empty:
                break
                
        self.after(100, self.poll_event_queue)
        
    def handle_network_event(self, event):
        etype = event.get('event')
        
        if etype not in ["TEXT_RECEIVED", "COMMAND_RECEIVED", "FILE_RECEIVED", "FILE_PROGRESS"]:
            return
            
        sender_id = event.get('sender_id')
        sender_name = event.get('sender_name', 'Desconocido')
        
        # Si el evento es para el chat activo, lo mostramos. Si no, quizá mostrar una notificación
        if etype == "TEXT_RECEIVED":
            msg = event.get('text', '')
            if sender_id == self.selected_node_id:
                self.append_to_chat(f"[Remoto]: {msg}")
            else:
                # Opcional: mostrar un popup o marcador de "nuevo mensaje"
                pass
            
        elif etype == "COMMAND_RECEIVED":
            response = event.get('result', '')
            success = event.get('success', False)
            icon = "[OK]" if success else "[FAIL]"
            if sender_id == self.selected_node_id:
                self.append_to_chat(f"[SysAdmin] {icon}: {response}")
            
        elif etype == "FILE_RECEIVED":
            filepath = event.get('filepath', '')
            success = event.get('success', False)
            if sender_id == self.selected_node_id:
                if success:
                    self.append_to_chat(f"[DOWNLOAD] Archivo guardado en:\n{filepath}")
                else:
                    self.append_to_chat(f"[ERROR] Error al recibir archivo: {event.get('msg')}")
                
        elif etype == "FILE_PROGRESS":
            direction = event.get('direction')
            if direction == "RECEIVING":
                current = event.get('current', 0)
                total = event.get('total', 1)
                self.progress_bar.grid(row=3, column=0, sticky="ew", padx=10, pady=5)
                self.progress_bar.set(current / total)
                if current >= total:
                    self.after(2000, lambda: self.progress_bar.grid_forget())

    def on_closing(self):
        logger.info("[UI] Cerrando la interfaz de escritorio...")
        self.core.stop()
        self.destroy()
        
def run_desktop_app(node_core):
    app = SysNodeDesktopApp(node_core)
    app.mainloop()
