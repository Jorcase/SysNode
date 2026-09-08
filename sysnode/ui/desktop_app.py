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
    import threading
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
        self.title(f"SysNode - {self.core.node_name}")
        self.geometry("950x650")
        self.minsize(800, 500)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        # Single Instance Lock
        self.single_instance_sock = None
        if not self.setup_single_instance():
            import sys
            logger.info("SysNode ya está corriendo. Despertando instancia previa...")
            sys.exit(0)
            
        # Iniciar hilo de bandeja de sistema (System Tray)
        
        self.build_ui()
        
        # Iniciar polling thread-safe de eventos
        self.after(100, self.poll_event_queue)
        
    def load_icons(self):
        from PIL import Image
        import os
        self.icons = {}
        
        if getattr(sys, 'frozen', False):
            icons_dir = os.path.join(sys._MEIPASS, "sysnode", "ui", "assets", "icons")
        else:
            icons_dir = os.path.join(os.path.dirname(__file__), "assets", "icons")
            
        if not os.path.exists(icons_dir): return
        
        try:
            self.icons['home'] = ctk.CTkImage(light_image=Image.open(os.path.join(icons_dir, "home.png")), size=(20, 20))
            self.icons['settings'] = ctk.CTkImage(light_image=Image.open(os.path.join(icons_dir, "settings.png")), size=(20, 20))
            self.icons['qr'] = ctk.CTkImage(light_image=Image.open(os.path.join(icons_dir, "qr.png")), size=(20, 20))
            self.icons['smartphone'] = ctk.CTkImage(light_image=Image.open(os.path.join(icons_dir, "smartphone.png")), size=(24, 24))
            self.icons['laptop'] = ctk.CTkImage(light_image=Image.open(os.path.join(icons_dir, "laptop.png")), size=(24, 24))
            self.icons['add'] = ctk.CTkImage(light_image=Image.open(os.path.join(icons_dir, "add.png")), size=(20, 20))
            self.icons['file'] = ctk.CTkImage(light_image=Image.open(os.path.join(icons_dir, "file.png")), size=(20, 20))
            self.icons['profile'] = ctk.CTkImage(light_image=Image.open(os.path.join(icons_dir, "profile.png")), size=(20, 20))
            self.icons['network'] = ctk.CTkImage(light_image=Image.open(os.path.join(icons_dir, "network.png")), size=(20, 20))
            self.icons['plug'] = ctk.CTkImage(light_image=Image.open(os.path.join(icons_dir, "plug.png")), size=(20, 20))
            self.icons['os'] = ctk.CTkImage(light_image=Image.open(os.path.join(icons_dir, "os.png")), size=(20, 20))
            self.icons['edit'] = ctk.CTkImage(light_image=Image.open(os.path.join(icons_dir, "edit.png")), size=(18, 18))
            self.icons['copy'] = ctk.CTkImage(light_image=Image.open(os.path.join(icons_dir, "copy.png")), size=(18, 18))
            self.icons['folder'] = ctk.CTkImage(light_image=Image.open(os.path.join(icons_dir, "folder.png")), size=(18, 18))
            self.icons['terminal'] = ctk.CTkImage(light_image=Image.open(os.path.join(icons_dir, "terminal.png")), size=(18, 18))
            self.icons['lock'] = ctk.CTkImage(light_image=Image.open(os.path.join(icons_dir, "lock.png")), size=(18, 18))
        except Exception as e:
            logger.error(f"Error cargando iconos: {e}")

    def setup_single_instance(self):
        import socket
        try:
            self.single_instance_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.single_instance_sock.bind(('127.0.0.1', 50505))
            self.single_instance_sock.listen(1)
            threading.Thread(target=self.single_instance_listener, daemon=True).start()
            return True
        except OSError:
            # Ya hay una instancia corriendo. Enviamos señal WAKEUP
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect(('127.0.0.1', 50505))
                s.send(b'WAKEUP')
                s.close()
            except: pass
            return False
            
    def single_instance_listener(self):
        while True:
            try:
                conn, _ = self.single_instance_sock.accept()
                data = conn.recv(1024)
                if data == b'WAKEUP':
                    self.show_window(None, None)
                conn.close()
            except:
                break
                
    def build_ui(self):
        self.load_icons()
        
        # Grid layout principal: 1 fila, 2 columnas (Sidebar y Main Chat)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        
        # --- PANEL IZQUIERDO (SIDEBAR - Dispositivos) ---
        self.sidebar_frame = ctk.CTkFrame(self, width=280, corner_radius=0, fg_color=("gray95", "gray13"))
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(1, weight=1) 
        
        # Header del Sidebar
        sidebar_header = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        sidebar_header.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        
        self.logo_label = ctk.CTkLabel(sidebar_header, text="SysNode", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.pack(side="left", padx=10)
        
        # Profile Button
        self.btn_profile = ctk.CTkButton(sidebar_header, image=self.icons.get('profile'), text="", width=30, height=30, fg_color="transparent", hover_color=("gray85", "gray25"), command=self.show_profile)
        self.btn_profile.pack(side="right")
        
        self.btn_home = ctk.CTkButton(sidebar_header, image=self.icons.get('home'), text="", width=30, height=30, fg_color="transparent", hover_color=("gray85", "gray25"), command=self.show_welcome)
        self.btn_home.pack(side="right", padx=5)
        
        # Lista de dispositivos
        self.nodes_frame = ctk.CTkScrollableFrame(self.sidebar_frame, label_text="Contactos en Red", fg_color="transparent", scrollbar_button_color=("gray85", "gray25"))
        self.nodes_frame.grid(row=1, column=0, padx=5, pady=0, sticky="nsew")
        self.node_buttons = {} # ip -> ctk.CTkButton
        
        # Footer del Sidebar
        sidebar_footer = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        sidebar_footer.grid(row=2, column=0, padx=10, pady=10, sticky="ew")
        
        self.btn_add_device = ctk.CTkButton(sidebar_footer, image=self.icons.get('add'), text=" Añadir IP Manual", anchor="w", fg_color="transparent", hover_color=("gray85", "gray25"), text_color=("gray10", "gray90"), command=self.prompt_manual_ip)
        self.btn_add_device.pack(fill="x", pady=(0, 2))
        
        self.btn_settings = ctk.CTkButton(sidebar_footer, image=self.icons.get('settings'), text=" Configuración", anchor="w", fg_color="transparent", hover_color=("gray85", "gray25"), text_color=("gray10", "gray90"), command=self.show_settings)
        self.btn_settings.pack(fill="x")
        
        # --- PANEL DERECHO (CONTENEDOR PRINCIPAL) ---
        self.content_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.content_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.content_frame.grid_rowconfigure(0, weight=1)
        self.content_frame.grid_columnconfigure(0, weight=1)
        
        # Construir Vistas
        self.build_welcome_view()
        self.build_profile_view()
        self.build_settings_view()
        self.build_share_view()
        self.build_chat_view()
        
        # Mostrar Bienvenida por defecto
        self.show_welcome()
        
    def build_welcome_view(self):
        self.view_welcome = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.view_welcome.grid_rowconfigure(0, weight=1)
        self.view_welcome.grid_rowconfigure(4, weight=1)
        self.view_welcome.grid_columnconfigure(0, weight=1)
        
        lbl_title = ctk.CTkLabel(self.view_welcome, text="Bienvenido a SysNode", font=ctk.CTkFont(size=28, weight="bold"))
        lbl_title.grid(row=1, column=0, pady=(0, 10))
        
        lbl_subtitle = ctk.CTkLabel(self.view_welcome, text="Seleccioná un dispositivo en el panel izquierdo para comenzar a chatear.", font=ctk.CTkFont(size=14), text_color="gray70")
        lbl_subtitle.grid(row=2, column=0, pady=(0, 30))
        
        # --- ACCIONES PRINCIPALES ---
        actions_frame = ctk.CTkFrame(self.view_welcome, fg_color="transparent")
        actions_frame.grid(row=3, column=0, pady=10)
        
        btn_add = ctk.CTkButton(actions_frame, image=self.icons.get('add'), text=" Añadir IP Manual", width=200, height=45, font=ctk.CTkFont(size=14), command=self.prompt_manual_ip)
        btn_add.pack(side="left", padx=10)
        
        btn_share = ctk.CTkButton(actions_frame, text=" 🌐 Compartir App (HTTP)", width=240, height=45, font=ctk.CTkFont(size=14), fg_color="#27AE60", hover_color="#1E8449", command=self.start_sharing_server)
        btn_share.pack(side="left", padx=10)
        
    def build_profile_view(self):
        self.view_profile = ctk.CTkFrame(self.content_frame)
        self.view_profile.grid_columnconfigure(0, weight=1)
        
        header = ctk.CTkLabel(self.view_profile, text="Mi Perfil en Red", font=ctk.CTkFont(size=24, weight="bold"))
        header.grid(row=0, column=0, padx=20, pady=20, sticky="w")
        
        # Nombre de Usuario
        frame_name = ctk.CTkFrame(self.view_profile, fg_color="transparent")
        frame_name.grid(row=1, column=0, padx=20, pady=5, sticky="ew")
        ctk.CTkLabel(frame_name, text="Nombre de Usuario:").pack(side="left", padx=(0, 10))
        self.entry_username = ctk.CTkEntry(frame_name, width=200)
        self.entry_username.insert(0, self.core.node_name)
        self.entry_username.pack(side="left", padx=(0, 10))
        btn_save_name = ctk.CTkButton(frame_name, text="Guardar", width=80, command=self.save_username)
        btn_save_name.pack(side="left")
        
        import platform
        from sysnode.config import SYSTEM_OS
        
        info_frame = ctk.CTkFrame(self.view_profile, fg_color=("gray90", "gray15"))
        info_frame.grid(row=2, column=0, padx=20, pady=20, sticky="ew")
        
        is_desktop = "Desktop" in platform.system() or "Windows" in platform.system() or "Linux" in platform.system() or "darwin" in platform.system().lower()
        dev_icon = self.icons.get('laptop') if is_desktop else self.icons.get('smartphone')
        
        info_list_frame = ctk.CTkFrame(info_frame, fg_color="transparent")
        info_list_frame.pack(padx=20, pady=20, side="left", fill="both", expand=True)
        
        def add_info_row(parent, icon, text):
            row = ctk.CTkFrame(parent, fg_color="transparent")
            row.pack(fill="x", pady=5)
            ctk.CTkLabel(row, text="", image=icon, width=24).pack(side="left", padx=(0, 10))
            ctk.CTkLabel(row, text=text, font=ctk.CTkFont(size=14)).pack(side="left")

        add_info_row(info_list_frame, self.icons.get('network'), f"IP: {self.core.local_ip}")
        add_info_row(info_list_frame, self.icons.get('plug'), f"Puerto: {self.core.tcp_port}")
        add_info_row(info_list_frame, dev_icon, "Dispositivo: Desktop" if is_desktop else "Dispositivo: Móvil")
        add_info_row(info_list_frame, self.icons.get('os'), f"SO: {SYSTEM_OS.capitalize()}")
        
        import qrcode
        from PIL import Image
        qr = qrcode.QRCode(version=1, box_size=5, border=2)
        qr_data = f'{{"ip": "{self.core.local_ip}", "port": {self.core.tcp_port}}}'
        qr.add_data(qr_data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white").get_image()
        ctk_img = ctk.CTkImage(light_image=img, size=(120, 120))
        
        qr_lbl = ctk.CTkLabel(info_frame, text="", image=ctk_img)
        qr_lbl.pack(padx=20, pady=20, side="right")
        
        ctk.CTkLabel(info_frame, text="Escaneá para añadir nodo", text_color="gray60").pack(side="right", padx=10)
        
    def build_remote_profile_view(self):
        # Ahora es hijo de view_chat para mostrarse al costado
        self.view_remote_profile = ctk.CTkFrame(self.view_chat, width=280, corner_radius=0, border_width=1, border_color=("gray85", "gray20"))
        
        header_frame = ctk.CTkFrame(self.view_remote_profile, fg_color="transparent")
        header_frame.pack(fill="x", padx=10, pady=15)
        
        btn_close = ctk.CTkButton(header_frame, text="X", width=30, fg_color="transparent", hover_color="#C0392B", command=self.hide_remote_profile)
        btn_close.pack(side="left")
        
        header = ctk.CTkLabel(header_frame, text="Info. del contacto", font=ctk.CTkFont(size=16, weight="bold"))
        header.pack(side="left", padx=10)
        
        # Contenedor central
        info_frame = ctk.CTkFrame(self.view_remote_profile, fg_color="transparent")
        info_frame.pack(fill="both", expand=True, pady=20)
        
        # Avatar (grande)
        self.lbl_rp_avatar = ctk.CTkLabel(info_frame, text="", image=self.icons.get('laptop'))
        self.lbl_rp_avatar.pack(pady=(0, 15))
        
        # Nombre grande
        self.lbl_rp_hostname = ctk.CTkLabel(info_frame, text="Hostname", font=ctk.CTkFont(size=20, weight="bold"))
        self.lbl_rp_hostname.pack(pady=5)
        
        # Recuadro de Info adicional
        details_frame = ctk.CTkFrame(info_frame, fg_color=("gray90", "gray15"), corner_radius=10)
        details_frame.pack(fill="x", pady=20, padx=15)
        
        self.lbl_rp_os = ctk.CTkLabel(details_frame, text="Disponible", font=ctk.CTkFont(size=14))
        self.lbl_rp_os.pack(anchor="w", padx=15, pady=(15, 5))
        
        self.lbl_rp_ip = ctk.CTkLabel(details_frame, text="", font=ctk.CTkFont(size=14), text_color="gray60")
        self.lbl_rp_ip.pack(anchor="w", padx=15, pady=(0, 15))
        
    def hide_remote_profile(self):
        if hasattr(self, 'view_remote_profile'):
            self.view_remote_profile.grid_remove()

    def show_remote_profile(self):
        if not self.selected_node_id:
            return
            
        # Mostrar panel al costado del chat
        self.view_remote_profile.grid(row=0, rowspan=4, column=1, sticky="nsew", padx=(5, 0))
        
        # Rellenar información
        peers = self.core.get_active_peers()
        peer_info = peers.get(self.selected_node_id, {})
        
        hostname = peer_info.get("hostname", "Desconocido")
        os_type = peer_info.get("os", "Unknown")
        ip = peer_info.get("ip", "Desconocida")
        port = peer_info.get("tcp_port", "-")
        
        # Fallback a DB
        if not peer_info:
            for p_id, p_name, p_os, p_last_ip, p_last_port in self.core.db.get_all_devices():
                if p_id == self.selected_node_id:
                    hostname = p_name
                    os_type = p_os
                    if p_last_ip:
                        ip = p_last_ip
                        port = p_last_port
                    break
            
            # Buscar si es manual para mostrar IP
            for p_id, p_ip, p_port in self.core.db.get_manual_peers():
                if p_id == self.selected_node_id:
                    ip = p_ip
                    port = p_port
                    break
        
        # Mostrar avatar según OS
        is_desktop = "Desktop" in os_type or "Windows" in os_type or "Linux" in os_type or "darwin" in os_type.lower()
        self.lbl_rp_avatar.configure(image=self.icons.get('laptop') if is_desktop else self.icons.get('smartphone'))
        
        self.lbl_rp_hostname.configure(text=hostname)
        self.lbl_rp_os.configure(text=f"SO: {os_type}")
        
        if ip != "Desconocida":
            self.lbl_rp_ip.configure(text=f"IP: {ip}:{port}")
        else:
            self.lbl_rp_ip.configure(text="")
        
    def build_settings_view(self):
        self.view_settings = ctk.CTkFrame(self.content_frame)
        self.view_settings.grid_columnconfigure(0, weight=1)
        
        header = ctk.CTkLabel(self.view_settings, text="Configuración del Sistema", font=ctk.CTkFont(size=24, weight="bold"))
        header.grid(row=0, column=0, padx=20, pady=20, sticky="w")
        
        # --- Módulo: Archivos ---
        lbl_mod_files = ctk.CTkLabel(self.view_settings, text="Archivos y Descargas", font=ctk.CTkFont(size=16, weight="bold"))
        lbl_mod_files.grid(row=1, column=0, padx=20, pady=(10, 5), sticky="w")
        
        frame_dl = ctk.CTkFrame(self.view_settings, fg_color="transparent")
        frame_dl.grid(row=2, column=0, padx=20, pady=5, sticky="ew")
        frame_dl.grid_columnconfigure(0, weight=1)
        
        current_dl = self.core.get_downloads_dir()
        self.lbl_dl_path = ctk.CTkLabel(frame_dl, text=current_dl, text_color="gray70", anchor="w", wraplength=400)
        self.lbl_dl_path.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        
        btn_frame_dl = ctk.CTkFrame(frame_dl, fg_color="transparent")
        btn_frame_dl.grid(row=0, column=1, sticky="e")
        
        btn_open_dl = ctk.CTkButton(btn_frame_dl, text="Abrir Carpeta", width=100, fg_color="#34495E", text_color="white", hover_color="#2C3E50", command=lambda: self.open_file_default_app(self.core.get_downloads_dir()))
        btn_open_dl.pack(side="left", padx=5)
        
        btn_change_dl = ctk.CTkButton(btn_frame_dl, text="Cambiar Ruta", width=100, fg_color="#2C3E50", hover_color="#1A252F", command=self.change_downloads_folder)
        btn_change_dl.pack(side="left", padx=5)
        
        # --- Módulo: Comandos ---
        lbl_cmds = ctk.CTkLabel(self.view_settings, text="Comandos Personalizados (JSON)", font=ctk.CTkFont(size=16, weight="bold"))
        lbl_cmds.grid(row=3, column=0, padx=20, pady=(20, 5), sticky="w")
        
        # Scrollable Frame para la lista de comandos
        self.cmds_frame = ctk.CTkScrollableFrame(self.view_settings, height=200)
        self.cmds_frame.grid(row=4, column=0, padx=20, pady=5, sticky="nsew")
        self.view_settings.grid_rowconfigure(4, weight=1)
        
        # Botón para añadir nuevo comando
        btn_add_cmd = ctk.CTkButton(self.view_settings, image=self.icons.get('add'), text=" Nuevo Comando", fg_color="#2C3E50", hover_color="#1A252F", command=self.prompt_new_command)
        btn_add_cmd.grid(row=5, column=0, padx=20, pady=10, sticky="w")
        
        self.load_custom_commands_ui()
        
        # Botón Volver (Removido porque ahora está fijo en el sidebar)
        
    def load_custom_commands_ui(self):
        for widget in self.cmds_frame.winfo_children():
            widget.destroy()
            
        cmds = self.core.db.get_custom_commands()
        if not cmds:
            ctk.CTkLabel(self.cmds_frame, text="No hay comandos personalizados.", text_color="gray50").pack(pady=20)
            return
            
        for cmd_id, name, payload in cmds:
            frame = ctk.CTkFrame(self.cmds_frame, fg_color=("gray80", "gray15"))
            frame.pack(fill="x", pady=2)
            
            ctk.CTkLabel(frame, text=name, font=ctk.CTkFont(weight="bold")).pack(side="left", padx=10, pady=5)
            
            btn_del = ctk.CTkButton(frame, text="Borrar", width=60, fg_color="#922B21", text_color="white", hover_color="#7B241C", 
                                    command=lambda c=cmd_id: self.delete_custom_command_ui(c))
            btn_del.pack(side="right", padx=10, pady=5)
            
            btn_edit = ctk.CTkButton(frame, text="Editar", width=60, fg_color="#34495E", text_color="white", hover_color="#2C3E50", 
                                     command=lambda c=cmd_id, n=name, p=payload: self.prompt_new_command(c, n, p))
            btn_edit.pack(side="right", padx=5, pady=5)
            
    def delete_custom_command_ui(self, cmd_id):
        self.core.db.delete_custom_command(cmd_id)
        self.load_custom_commands_ui()
        
    def prompt_new_command(self, edit_id=None, edit_name="", edit_payload=""):
        modal = ctk.CTkToplevel(self)
        modal.title("Editar Comando JSON" if edit_id else "Nuevo Comando JSON")
        modal.geometry("800x450")
        modal.attributes('-topmost', True)
        
        # Frame superior para nombre
        top_frame = ctk.CTkFrame(modal, fg_color="transparent")
        top_frame.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(top_frame, text="Nombre del Comando:", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(0, 10))
        entry_name = ctk.CTkEntry(top_frame, width=300)
        entry_name.pack(side="left")
        if edit_name:
            entry_name.insert(0, edit_name)
        
        # Contenedor dividido
        split_frame = ctk.CTkFrame(modal, fg_color="transparent")
        split_frame.pack(fill="both", expand=True, padx=20, pady=10)
        split_frame.grid_columnconfigure(0, weight=1)
        split_frame.grid_columnconfigure(1, weight=1)
        
        # Columna Izquierda: Editor
        left_col = ctk.CTkFrame(split_frame, fg_color="transparent")
        left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        ctk.CTkLabel(left_col, text="Tu JSON Payload:").pack(anchor="w", pady=(0, 5))
        txt_json = ctk.CTkTextbox(left_col, font=ctk.CTkFont(family="monospace", size=12))
        txt_json.pack(fill="both", expand=True)
        
        # Columna Derecha: Plantilla de Referencia
        right_col = ctk.CTkFrame(split_frame, fg_color=("gray90", "gray15"))
        right_col.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        ctk.CTkLabel(right_col, text="Plantilla de Referencia", text_color="gray60").pack(anchor="w", padx=10, pady=(10, 5))
        
        template = '''{
  "platforms": {
    "windows": "mkdir C:\\\\PruebaSysNode",
    "fedora": "mkdir ~/PruebaSysNode",
    "ubuntu": "mkdir ~/PruebaSysNode",
    "linux": "mkdir ~/PruebaSysNode"
  }
}'''
        if edit_payload:
            txt_json.insert("1.0", edit_payload)
        else:
            txt_json.insert("1.0", "// Escribe tu JSON aquí...\n")
        
        txt_template = ctk.CTkTextbox(right_col, font=ctk.CTkFont(family="monospace", size=12), text_color="gray50", fg_color="transparent")
        txt_template.insert("1.0", template)
        txt_template.configure(state="disabled")
        txt_template.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        def save_cmd():
            name = entry_name.get().strip()
            payload = txt_json.get("1.0", "end").strip()
            if payload.startswith("//"):
                payload = "" # Limpiar placeholder si el usuario no lo hizo
                
            if not name or not payload:
                messagebox.showerror("Error", "Nombre y payload son obligatorios.", parent=modal)
                return
            try:
                import json
                json.loads(payload) # Validar sintaxis
            except json.JSONDecodeError as e:
                messagebox.showerror("JSON Inválido", f"El JSON tiene un error de sintaxis:\n{e}", parent=modal)
                return
                
            if edit_id is not None:
                self.core.db.update_custom_command(edit_id, name, payload)
            else:
                self.core.db.add_custom_command(name, payload)
                
            self.load_custom_commands_ui()
            modal.destroy()
            
        ctk.CTkButton(modal, text="Guardar Comando", command=save_cmd).pack(pady=20)
        
    def build_share_view(self):
        self.view_share = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.view_share.grid_rowconfigure(0, weight=1)
        self.view_share.grid_rowconfigure(5, weight=1)
        self.view_share.grid_columnconfigure(0, weight=1)
        
        lbl_title = ctk.CTkLabel(self.view_share, text="Compartir SysNode", font=ctk.CTkFont(size=24, weight="bold"))
        lbl_title.grid(row=1, column=0, pady=(0, 10))
        
        lbl_desc = ctk.CTkLabel(self.view_share, text="Escaneá el QR o ingresá a esta dirección web:", font=ctk.CTkFont(size=14), text_color="gray70")
        lbl_desc.grid(row=2, column=0, pady=(0, 20))
        
        self.lbl_share_url = ctk.CTkEntry(self.view_share, font=ctk.CTkFont(size=16, weight="bold"), width=300, justify="center")
        self.lbl_share_url.grid(row=3, column=0, pady=(0, 20))
        
        self.lbl_share_qr = ctk.CTkLabel(self.view_share, text="")
        self.lbl_share_qr.grid(row=4, column=0, pady=(0, 30))
        
        btn_close = ctk.CTkButton(self.view_share, text="Detener y Volver", fg_color="#C0392B", hover_color="#922B21", command=self.stop_sharing_server)
        btn_close.grid(row=5, column=0, pady=20)
        
    def build_chat_view(self):
        self.view_chat = ctk.CTkFrame(self.content_frame, corner_radius=0, fg_color="transparent")
        self.view_chat.grid_rowconfigure(1, weight=1)
        self.view_chat.grid_columnconfigure(0, weight=1)
        self.view_chat.grid_columnconfigure(1, weight=0) # Perfil ocupa solo su ancho
        
        # Construir perfil aquí para que sea hijo de view_chat
        self.build_remote_profile_view()
        self.hide_remote_profile()
        
        # Cabecera del chat
        self.chat_header = ctk.CTkFrame(self.view_chat, height=50, corner_radius=8)
        self.chat_header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        
        self.chat_title = ctk.CTkLabel(self.chat_header, text="Seleccioná un dispositivo para chatear", font=ctk.CTkFont(size=16, weight="bold"), cursor="hand2")
        self.chat_title.pack(side="left", padx=15, pady=10)
        self.chat_title.bind("<Button-1>", lambda e: self.show_remote_profile())
        
        # En la cabecera del chat, botón para abrir descargas
        btn_header_frame = ctk.CTkFrame(self.chat_header, fg_color="transparent")
        btn_header_frame.pack(side="right", padx=10)
        
        btn_clear_chat = ctk.CTkButton(btn_header_frame, text=" Limpiar Chat", width=120, fg_color="#C0392B", hover_color="#922B21", 
                                        command=self.clear_current_chat)
        btn_clear_chat.pack(side="left", padx=2)
        
        btn_open_folder = ctk.CTkButton(btn_header_frame, image=self.icons.get('folder'), text=" Abrir Descargas", width=120, fg_color="#34495E", hover_color="#2C3E50", 
                                        command=self.open_downloads_folder)
        btn_open_folder.pack(side="left", padx=2)
        
        # Área de mensajes (Textbox)
        self.chat_scroll = ctk.CTkScrollableFrame(self.view_chat, fg_color="transparent")
        self.chat_scroll.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        
        # Barra inferior (Input + Botones)
        self.input_frame = ctk.CTkFrame(self.view_chat, corner_radius=8)
        self.input_frame.grid(row=2, column=0, sticky="ew")
        self.input_frame.grid_columnconfigure(0, weight=1)
        
        # Banner de edición (oculto por defecto)
        self.edit_banner_frame = ctk.CTkFrame(self.input_frame, fg_color="#333333", corner_radius=5)
        self.edit_banner_label = ctk.CTkLabel(self.edit_banner_frame, text="Editando mensaje...", text_color="#AAAAAA")
        self.edit_banner_label.pack(side="left", padx=10, pady=2)
        self.edit_banner_cancel = ctk.CTkButton(self.edit_banner_frame, text="X", width=20, height=20, fg_color="transparent", hover_color="#C0392B", command=self.cancel_edit_mode)
        self.edit_banner_cancel.pack(side="right", padx=5)
        
        self.msg_entry = ctk.CTkEntry(self.input_frame, placeholder_text="Escribí un mensaje...", height=40)
        self.msg_entry.grid(row=1, column=0, padx=10, pady=(5, 10), sticky="ew")
        self.msg_entry.bind("<Return>", lambda e: self.send_text_message())
        
        self.btn_send = ctk.CTkButton(self.input_frame, text="Enviar", width=80, command=self.send_text_message)
        self.btn_send.grid(row=1, column=1, padx=(0, 10), pady=(5, 10))
        
        self.btn_attach = ctk.CTkButton(self.input_frame, image=self.icons.get('file'), text=" Archivo", width=90, fg_color="#34495E", hover_color="#2C3E50", command=self.select_and_send_file)
        self.btn_attach.grid(row=1, column=2, padx=(0, 10), pady=(5, 10))
        
        self.btn_cmd = ctk.CTkButton(self.input_frame, image=self.icons.get('terminal'), text=" Comandos", width=90, fg_color="#922B21", hover_color="#7B241C", command=self.open_command_menu)
        self.btn_cmd.grid(row=1, column=3, padx=(0, 10), pady=(5, 10))

        # Progress bar oculta por defecto
        self.progress_bar = ctk.CTkProgressBar(self.view_chat)
        self.progress_bar.set(0)
        
    def hide_all_views(self):
        self.view_welcome.grid_remove()
        self.view_chat.grid_remove()
        self.view_share.grid_remove()
        self.view_settings.grid_remove()
        self.view_profile.grid_remove()
        if hasattr(self, 'view_remote_profile'):
            self.view_remote_profile.grid_remove()

    def show_welcome(self):
        self.selected_node_id = None
        self.hide_all_views()
        self.view_welcome.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
    def show_profile(self):
        self.selected_node_id = None
        self.hide_all_views()
        self.view_profile.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
    def show_settings(self):
        self.selected_node_id = None
        self.hide_all_views()
        self.view_settings.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
    def show_share(self):
        self.selected_node_id = None
        self.hide_all_views()
        self.view_share.grid(row=0, column=0, sticky="nsew")
        
    def show_chat(self):
        self.hide_all_views()
        self.view_chat.grid(row=0, column=0, sticky="nsew")
        
    def save_username(self):
        new_name = self.entry_username.get().strip()
        if new_name:
            self.core.node_name = new_name
            self.core.db.set_local_username(new_name)
            self.core.udp_beacon.custom_name = new_name
            messagebox.showinfo("Guardado", "Nombre de usuario actualizado.")
            
    def start_sharing_server(self):
        url = self.core.start_sharing_server()
        if not url:
            messagebox.showerror("Error", "No se pudo iniciar el servidor HTTP local.")
            return
            
        self.lbl_share_url.configure(state="normal")
        self.lbl_share_url.delete(0, "end")
        self.lbl_share_url.insert(0, url)
        self.lbl_share_url.configure(state="readonly")
        
        try:
            import qrcode
            qr = qrcode.QRCode(box_size=8, border=2)
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Extract PIL Image from qrcode image wrapper
            pil_img = img.get_image()
            
            ctk_img = ctk.CTkImage(light_image=pil_img, size=(200, 200))
            self.lbl_share_qr.configure(image=ctk_img, text="")
        except ImportError:
            self.lbl_share_qr.configure(text="(Librería 'qrcode' o 'Pillow' no instalada)")
            
        self.show_share()
        
    def stop_sharing_server(self):
        self.core.stop_sharing_server()
        self.show_welcome()
        
    def clear_current_chat(self):
        if not self.selected_node_id:
            return
            
        if messagebox.askyesno("Limpiar Chat", "¿Estás seguro de que querés borrar toda la conversación con este dispositivo?"):
            self.core.db.clear_chat_history(self.selected_node_id)
            self.load_chat_history(self.selected_node_id)
            
    def delete_single_message(self, msg_uuid):
        if not msg_uuid: return
        if messagebox.askyesno("Borrar Mensaje", "¿Seguro que querés borrar este mensaje?"):
            self.core.db.delete_message(msg_uuid)
            self.load_chat_history(self.selected_node_id)

    def load_chat_history(self, node_id):
        # Limpiar chat actual
        for widget in self.chat_scroll.winfo_children():
            widget.destroy()
            
        recent_messages = self.core.db.get_chat_history(node_id, limit=50)
        if not recent_messages:
            self.append_to_chat("--- No hay mensajes previos con este dispositivo ---", add_timestamp=False)
            return
            
        info = self.known_devices.get(node_id, {})
        remote_name = info.get("hostname", "Remoto")
            
        for msg_uuid, ts, text, direction in recent_messages:
            time_only = ts.split(" ")[1]
            sender_str = remote_name if direction == "IN" else "Yo"
            
            if text.startswith("FILE:"):
                filepath = text.split("FILE:")[1]
                ext = os.path.splitext(filepath)[1].lower()
                if ext in ['.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp']:
                    self.append_image_to_chat(filepath, sender=sender_str, add_timestamp=False)
                else:
                    self.append_generic_file_to_chat(filepath, sender=sender_str, add_timestamp=False)
            elif text.startswith("CMD_REQ:"):
                cmd_txt = text.split("CMD_REQ:")[1]
                if direction == "OUT":
                    self.append_to_chat(f"[SysAdmin] Yo envié comando: {cmd_txt}", add_timestamp=False, raw_msg=text, msg_uuid=msg_uuid, direction=direction)
                else:
                    self.append_to_chat(f"[SysAdmin] {sender_str} te envió un comando: {cmd_txt}", add_timestamp=False, raw_msg=text, msg_uuid=msg_uuid, direction=direction)
            elif text.startswith("CMD_RES:"):
                res_txt = text.split("CMD_RES:")[1]
                if direction == "IN":
                    self.append_to_chat(f"[SysAdmin] Resultado de {sender_str}: {res_txt}", add_timestamp=False, raw_msg=text, msg_uuid=msg_uuid, direction=direction)
                else:
                    self.append_to_chat(f"[SysAdmin] Resultado enviado a {remote_name}: {res_txt}", add_timestamp=False, raw_msg=text, msg_uuid=msg_uuid, direction=direction)
            else:
                self.append_to_chat(f"[{sender_str}]: {text}", add_timestamp=False, raw_msg=text, msg_uuid=msg_uuid, direction=direction)
                
        self.append_to_chat("--- Historial cargado ---", add_timestamp=False)
        
    def append_to_chat(self, text, add_timestamp=True, raw_msg="", msg_uuid=None, direction=None):
        if not raw_msg:
            raw_msg = text
            
        msg_frame = ctk.CTkFrame(self.chat_scroll, fg_color=("gray85", "gray20"))
        msg_frame.pack(fill="x", pady=2, padx=5)
        
        if add_timestamp:
            now_time = datetime.datetime.now().strftime("%H:%M:%S")
            text = f"[{now_time}] {text}"
            
        lbl_msg = ctk.CTkLabel(msg_frame, text=text, justify="left", wraplength=450, anchor="w")
        lbl_msg.pack(side="left", fill="x", expand=True, padx=5, pady=5)
        
        # Botón Copiar si hay mensaje (omitir para notificaciones de sistema p.ej "Historial cargado")
        if add_timestamp or "[Remoto]" in text or "[Yo]" in text:
            import tkinter as tk
            
            btn_options = ctk.CTkButton(msg_frame, text="⋮", width=30, height=30, fg_color="transparent", 
                                        hover_color=("gray75", "gray30"), font=("Arial", 18, "bold"))
            btn_options.pack(side="right", padx=2)
            
            def show_options_menu(e, u=msg_uuid, m=raw_msg, d=direction):
                menu = tk.Menu(self, tearoff=0)
                if d == "OUT":
                    menu.add_command(label="Editar", command=lambda: self.prompt_edit_message(u, m))
                menu.add_command(label="Borrar", command=lambda: self.delete_single_message(u))
                menu.tk_popup(e.x_root, e.y_root)
                
            if msg_uuid:
                btn_options.bind("<Button-1>", show_options_menu)
            else:
                btn_options.configure(state="disabled")
            
            btn_copy = ctk.CTkButton(msg_frame, image=self.icons.get('copy'), text="", width=30, height=30, fg_color="transparent", 
                                     hover_color=("gray75", "gray30"),
                                     command=lambda m=raw_msg: self.copy_to_clipboard(m))
            btn_copy.pack(side="right", padx=5)
            
        # Scroll al fondo (hack en customtkinter)
        self.chat_scroll._parent_canvas.yview_moveto(1.0)
        
    def prompt_edit_message(self, msg_uuid, old_text):
        self.editing_msg_uuid = msg_uuid
        self.msg_entry.delete(0, "end")
        self.msg_entry.insert(0, old_text)
        self.msg_entry.focus_set()
        
        # Mostrar banner
        preview = old_text[:30] + "..." if len(old_text) > 30 else old_text
        self.edit_banner_label.configure(text=f"Editando mensaje: {preview}")
        self.edit_banner_frame.grid(row=0, column=0, columnspan=4, sticky="ew", padx=10, pady=(10, 0))
        
        # Cambiar el botón Enviar a Guardar
        self.btn_send.configure(text="Guardar", fg_color="#E67E22", hover_color="#D35400")
        
    def cancel_edit_mode(self):
        self.editing_msg_uuid = None
        self.edit_banner_frame.grid_forget()
        self.btn_send.configure(text="Enviar", fg_color=["#3B8ED0", "#1F6AA5"], hover_color=["#36719F", "#144870"])
        self.msg_entry.delete(0, "end")
        
    def copy_to_clipboard(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update() # Necesario en tkinter para registrar el clipboard

    def append_image_to_chat(self, filepath, sender="Remoto", add_timestamp=True):
        from PIL import Image
        
        msg_frame = ctk.CTkFrame(self.chat_scroll, fg_color=("gray85", "gray20"))
        msg_frame.pack(fill="x", pady=2, padx=5)
        
        prefix = f"[{datetime.datetime.now().strftime('%H:%M:%S')}] [{sender}]: " if add_timestamp else ""
        
        # Header del mensaje
        lbl_header = ctk.CTkLabel(msg_frame, text=prefix + "Imagen compartida:", anchor="w")
        lbl_header.pack(fill="x", padx=5, pady=(5, 0))
        
        try:
            pil_img = Image.open(filepath)
            # Redimensionar para miniatura manteniendo el aspect ratio
            pil_img.thumbnail((300, 300))
            my_image = ctk.CTkImage(light_image=pil_img, size=pil_img.size)
            
            image_label = ctk.CTkLabel(msg_frame, image=my_image, text="")
            image_label.pack(pady=5, padx=5, anchor="w")
        except Exception as e:
            err_lbl = ctk.CTkLabel(msg_frame, text=f"[Error al cargar imagen: {e}]", text_color="red")
            err_lbl.pack(pady=5)
            
        # Botón para abrir la imagen
        btn_open = ctk.CTkButton(msg_frame, image=self.icons.get('file'), text=" Abrir Imagen", width=120, fg_color="#34495E", hover_color="#2C3E50",
                                 command=lambda f=filepath: self.open_file_default_app(f))
        btn_open.pack(side="left", padx=5, pady=(0, 5))
        
        self.chat_scroll._parent_canvas.yview_moveto(1.0)
        
    def open_file_default_app(self, filepath):
        import platform, subprocess, os
        clean_env = os.environ.copy()
        if "LD_LIBRARY_PATH_ORIG" in clean_env:
            clean_env["LD_LIBRARY_PATH"] = clean_env["LD_LIBRARY_PATH_ORIG"]
        else:
            clean_env.pop("LD_LIBRARY_PATH", None)
            
        try:
            if platform.system() == "Windows":
                os.startfile(filepath)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", filepath], env=clean_env)
            else:
                subprocess.Popen(["xdg-open", filepath], env=clean_env)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir el archivo: {e}")

    def open_file_location(self, filepath):
        import platform, subprocess, os
        folder = os.path.dirname(filepath)
        clean_env = os.environ.copy()
        if "LD_LIBRARY_PATH_ORIG" in clean_env:
            clean_env["LD_LIBRARY_PATH"] = clean_env["LD_LIBRARY_PATH_ORIG"]
        else:
            clean_env.pop("LD_LIBRARY_PATH", None)
            
        try:
            if platform.system() == "Windows":
                subprocess.Popen(['explorer', '/select,', filepath])
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", "-R", filepath], env=clean_env)
            else:
                subprocess.Popen(["xdg-open", folder], env=clean_env)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir la ubicación: {e}")

    def append_generic_file_to_chat(self, filepath, sender="Remoto", add_timestamp=True):
        from PIL import Image, ImageDraw, ImageFont
        
        msg_frame = ctk.CTkFrame(self.chat_scroll, fg_color=("gray85", "gray20"))
        msg_frame.pack(fill="x", pady=2, padx=5)
        
        prefix = f"[{datetime.datetime.now().strftime('%H:%M:%S')}] [{sender}]: " if add_timestamp else ""
        lbl_header = ctk.CTkLabel(msg_frame, text=prefix + "Archivo compartido:", anchor="w")
        lbl_header.pack(fill="x", padx=5, pady=(5, 0))
        
        filename = os.path.basename(filepath)
        ext = os.path.splitext(filename)[1].upper() or "FILE"
        if len(ext) > 1 and ext.startswith("."): ext = ext[1:]
        
        try:
            img = Image.new('RGBA', (80, 80), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            color = "#E74C3C" if ext == "PDF" else ("#2980B9" if ext in ["DOC", "DOCX"] else "#7F8C8D")
            draw.rectangle((15, 10, 65, 70), fill=color)
            draw.polygon([(50, 10), (65, 10), (65, 25)], fill="white")
            my_image = ctk.CTkImage(light_image=img, size=(50, 50))
            
            file_info_frame = ctk.CTkFrame(msg_frame, fg_color="transparent")
            file_info_frame.pack(fill="x", padx=10, pady=5)
            lbl_icon = ctk.CTkLabel(file_info_frame, image=my_image, text="")
            lbl_icon.pack(side="left", padx=(0, 10))
            lbl_name = ctk.CTkLabel(file_info_frame, text=filename, font=ctk.CTkFont(weight="bold"))
            lbl_name.pack(side="left")
        except Exception:
            lbl_name = ctk.CTkLabel(msg_frame, text=f"[DOCUMENTO] {filename}", font=ctk.CTkFont(weight="bold"))
            lbl_name.pack(padx=10, pady=5, anchor="w")
        
        btn_frame = ctk.CTkFrame(msg_frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=5, pady=(0, 5))
        btn_open = ctk.CTkButton(btn_frame, image=self.icons.get('file'), text=" Abrir Archivo", width=120, fg_color="#34495E", hover_color="#2C3E50",
                                 command=lambda f=filepath: self.open_file_default_app(f))
        btn_open.pack(side="left", padx=5)
        
        btn_folder = ctk.CTkButton(btn_frame, image=self.icons.get('folder'), text=" Ver en Carpeta", width=130, fg_color="#34495E", hover_color="#2C3E50",
                                   command=lambda f=filepath: self.open_file_location(f))
        btn_folder.pack(side="left", padx=5)
        
        self.chat_scroll._parent_canvas.yview_moveto(1.0)

    def on_node_select(self, node_id, hostname):
        self.show_chat()
        self.selected_node_id = node_id
        logger.info(f"[UI] Dispositivo seleccionado: {hostname} ({node_id[:8]})")
        
        self.chat_title.configure(text=f"Chat con: {hostname}")
        
        # Remove unread badge if any
        if node_id in getattr(self, 'unread_badges', {}):
            self.unread_badges[node_id] = False
            
        for n_id, frame in self.node_buttons.items():
            if n_id == node_id:
                frame._select_btn.configure(fg_color="#2ECC71", text_color="black")
            else:
                frame._select_btn.configure(fg_color=["#3a7ebf", "#1f538d"], text_color=["gray10", "#DCE4EE"])
                
        # Ocultar o mostrar botón de comandos según el SO
        if node_id in getattr(self, 'known_devices', {}):
            os_type = self.known_devices[node_id].get('os_type', '')
            if 'Android' in os_type or 'iOS' in os_type:
                self.btn_cmd.grid_remove() # Ocultar Comandos
            else:
                self.btn_cmd.grid() # Mostrar Comandos
                
        self.load_chat_history(node_id)

    def remove_manual_node(self, node_id):
        self.core.udp_listener.remove_manual_peer(node_id)
        if node_id in self.node_buttons:
            self.node_buttons[node_id].destroy()
            del self.node_buttons[node_id]
        if self.selected_node_id == node_id:
            self.selected_node_id = None
            self.chat_title.configure(text="Dispositivo eliminado.")

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
        import subprocess, os
        downloads_path = self.core.get_downloads_dir()
        if not os.path.exists(downloads_path):
            os.makedirs(downloads_path, exist_ok=True)
            
        clean_env = os.environ.copy()
        if "LD_LIBRARY_PATH_ORIG" in clean_env:
            clean_env["LD_LIBRARY_PATH"] = clean_env["LD_LIBRARY_PATH_ORIG"]
        else:
            clean_env.pop("LD_LIBRARY_PATH", None)
            
        try:
            if platform.system() == "Windows":
                os.startfile(downloads_path)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", downloads_path], env=clean_env)
            else:
                subprocess.Popen(["xdg-open", downloads_path], env=clean_env)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir la carpeta de descargas: {e}")

    def get_modern_file_dialog(self, mode="file", title="Seleccionar archivo", initialdir=None):
        import platform, subprocess
        if not initialdir:
            initialdir = self.core.get_downloads_dir()
            
        old_cwd = os.getcwd()
        try:
            if platform.system() == "Linux":
                try:
                    cmd = ["zenity", "--file-selection", f"--title={title}", f"--filename={initialdir}/"]
                    if mode == "directory": cmd.append("--directory")
                    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
                    return res.stdout.strip()
                except (subprocess.CalledProcessError, FileNotFoundError):
                    try:
                        cmd = ["kdialog", "--getexistingdirectory" if mode == "directory" else "--getopenfilename", initialdir, f"--title={title}"]
                        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
                        return res.stdout.strip()
                    except (subprocess.CalledProcessError, FileNotFoundError): pass
            if mode == "directory":
                return filedialog.askdirectory(title=title, initialdir=initialdir)
            return filedialog.askopenfilename(title=title, initialdir=initialdir)
        finally:
            # Tkinter filedialog on Windows/Linux sometimes changes the CWD! We MUST restore it
            os.chdir(old_cwd)

    def change_downloads_folder(self):
        new_dir = self.get_modern_file_dialog("directory", title="Seleccionar Carpeta de Descargas")
        if new_dir:
            self.core.db.set_downloads_path(new_dir)
            if hasattr(self, 'lbl_dl_path'):
                self.lbl_dl_path.configure(text=new_dir)
            logger.info(f"[UI] Nuevo directorio de descargas: {new_dir}")
            messagebox.showinfo("Actualizado", f"Las futuras transferencias se guardarán en:\n{new_dir}")
            
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
        
        if hasattr(self, 'editing_msg_uuid') and self.editing_msg_uuid:
            # Modo edición
            success, err_msg = self.core.edit_remote_message(self.selected_node_id, self.editing_msg_uuid, msg)
            
            # Restaurar estado del input
            self.cancel_edit_mode()
            
            # Siempre recargamos el historial porque la base local se actualiza pase lo que pase
            self.load_chat_history(self.selected_node_id)
            
            if not success:
                import logging
                logging.getLogger(__name__).warning(f"Edición local exitosa, pero error remoto: {err_msg}")
            return
            
        # Modo envío normal
        success, err_msg, msg_uuid = self.core.send_text_to_peer(self.selected_node_id, msg)
        if success:
            self.append_to_chat(f"[Yo]: {msg}", raw_msg=msg, msg_uuid=msg_uuid, direction="OUT")
            self.msg_entry.delete(0, "end")
        else:
            self.append_to_chat(f"[ERROR] No se pudo enviar: {err_msg}")
            
    def open_command_menu(self):
        if not self.selected_node_id:
            messagebox.showwarning("Atención", "Seleccioná un dispositivo primero.")
            return
            
        peers = self.core.get_active_peers()
        node = peers.get(self.selected_node_id)
        if not node: return
        
        remote_os = node.get("os", "unknown").lower()
        if remote_os == "android":
            messagebox.showinfo("Comandos", "Los comandos remotos no están soportados en dispositivos Android.")
            return
            
        menu_window = ctk.CTkToplevel(self)
        menu_window.title(f"Comandos ({remote_os.capitalize()})")
        menu_window.geometry("300x400")
        menu_window.attributes("-topmost", True)
        
        lbl = ctk.CTkLabel(menu_window, text="Seleccioná un comando a ejecutar:")
        lbl.pack(pady=10)
        
        scroll = ctk.CTkScrollableFrame(menu_window)
        scroll.pack(fill="both", expand=True, padx=10, pady=5)
        
        import json
        cmds = self.core.db.get_custom_commands()
        valid_cmds = []
        
        for cmd_id, name, payload in cmds:
            try:
                data = json.loads(payload)
                platforms = data.get("platforms", {})
                
                # Buscar match exacto de OS
                if remote_os in platforms:
                    valid_cmds.append((name, platforms[remote_os], True))
                # Fallback genérico a "linux"
                elif remote_os not in ["windows", "darwin"] and "linux" in platforms:
                    valid_cmds.append((name, platforms["linux"], True))
            except json.JSONDecodeError:
                continue
                
        # Comandos estáticos del sistema
        static_cmds = [
            ("Test de Conectividad", "CMD_PING"),
            ("Información de Sistema", "CMD_SYS_INFO"),
            ("Bloquear Pantalla", "CMD_LOCK_SCREEN")
        ]
        
        for name, cmd_key in static_cmds:
            btn = ctk.CTkButton(scroll, image=self.icons.get('lock'), text=f" {name}", fg_color="#34495E", hover_color="#2C3E50", command=lambda c=cmd_key: [self.send_sysadmin_cmd(c), menu_window.destroy()])
            btn.pack(pady=5, fill="x", padx=10)
            
        if valid_cmds:
            ctk.CTkLabel(scroll, text="Personalizados:", font=ctk.CTkFont(size=12, weight="bold"), text_color="gray60").pack(pady=(10, 5), anchor="w", padx=10)
            
        for name, bash_cmd, is_custom in valid_cmds:
            btn = ctk.CTkButton(scroll, image=self.icons.get('terminal'), text=f" {name}", fg_color="#2C3E50", hover_color="#1A252F", command=lambda c=bash_cmd: [self.send_bash_cmd(c), menu_window.destroy()])
            btn.pack(pady=5, fill="x", padx=10)

    def send_bash_cmd(self, bash_cmd):
        if not self.selected_node_id: return
        self.append_to_chat(f"[SysAdmin] Yo envié comando: {bash_cmd}")
        success, result_msg = self.core.send_bash_command_to_peer(self.selected_node_id, bash_cmd)
        
        status_icon = "[OK]" if success else "[FAIL]"
        info = self.known_devices.get(self.selected_node_id, {})
        remote_name = info.get("hostname", "Remoto")
        self.append_to_chat(f"[SysAdmin] Resultado de {remote_name}: {status_icon} {result_msg}")

    def send_sysadmin_cmd(self, command):
        if not self.selected_node_id: return
        self.append_to_chat(f"[SysAdmin] Yo envié comando: {command}")
        success, result_msg = self.core.send_command_to_peer(self.selected_node_id, command)
        
        status_icon = "[OK]" if success else "[FAIL]"
        info = self.known_devices.get(self.selected_node_id, {})
        remote_name = info.get("hostname", "Remoto")
        self.append_to_chat(f"[SysAdmin] Resultado de {remote_name}: {status_icon} {result_msg}")
            
    def select_and_send_file(self):
        if not self.selected_node_id:
            messagebox.showwarning("Atención", "Seleccioná un dispositivo primero.")
            return
            
        peers = self.core.get_active_peers()
        node = peers.get(self.selected_node_id)
        if not node: return
        
        filepath = self.get_modern_file_dialog(mode="file", title="Seleccionar archivo")
        if not filepath: return
        
        self.progress_bar.grid(row=3, column=0, sticky="ew", padx=10, pady=5)
        self.progress_bar.set(0)
        
        def progress_cb(current, total):
            self.after(0, lambda: self.progress_bar.set(current/total))

        success, err_msg = self.core.send_file_to_peer(self.selected_node_id, filepath, progress_cb)
        
        if success:
            self.progress_bar.set(1.0)
            ext = os.path.splitext(filepath)[1].lower()
            if ext in ['.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp']:
                self.append_image_to_chat(filepath, sender="Yo")
            else:
                self.append_generic_file_to_chat(filepath, sender="Yo")
        else:
            self.progress_bar.set(0)
            self.append_to_chat(f"[ERROR] Error al enviar archivo: {err_msg}")
        
        self.after(2000, lambda: self.progress_bar.grid_forget()) # Ocultar barra despues de 2s
            
    def show_node_context_menu(self, event, node_id):
        import tkinter as tk
        
        info = self.known_devices.get(node_id, {})
        is_manual = info.get("manual", False) or node_id.startswith("manual_")
        is_online = node_id in self.core.get_active_peers()
        
        menu = tk.Menu(self, tearoff=0, bg="#2B2B2B", fg="white", activebackground="#34495E", activeforeground="white")
        
        items_added = False
        if is_manual:
            menu.add_command(label="Editar IP/Puerto", command=lambda: self.edit_manual_device(node_id))
            items_added = True
            
        if not is_online:
            menu.add_command(label="Borrar", command=lambda: self.delete_device(node_id, is_manual))
            items_added = True
            
        if items_added:
            menu.tk_popup(event.x_root, event.y_root)

    def delete_device(self, node_id, is_manual):
        if messagebox.askyesno("Confirmar", "¿Seguro que querés borrar este dispositivo?"):
            if is_manual:
                self.core.db.delete_manual_peer(node_id)
                if hasattr(self.core, '_temp_manual_peers') and node_id in self.core._temp_manual_peers:
                    del self.core._temp_manual_peers[node_id]
                    
            self.core.db.delete_device(node_id)
            
            # También borrarlo de la caché local para que desaparezca
            if node_id in self.known_devices:
                del self.known_devices[node_id]
            if node_id in self.node_buttons:
                self.node_buttons[node_id].destroy()
                del self.node_buttons[node_id]
            if self.selected_node_id == node_id:
                self.show_welcome()

    def edit_manual_device(self, node_id):
        # Encontrar IP/Puerto actual si es posible
        current_ip = ""
        current_port = 50001
        for p_id, p_ip, p_port in self.core.db.get_manual_peers():
            if p_id == node_id:
                current_ip = p_ip
                current_port = p_port
                break
                
        dialog = ctk.CTkInputDialog(text="Ingresá IP:Puerto (ej: 192.168.0.10:50001):", title="Editar Manual")
        # No se puede setear el valor inicial fácilmente en CTkInputDialog, pero el usuario puede reescribirlo.
        user_input = dialog.get_input()
        if user_input:
            parts = user_input.strip().split(":")
            ip = parts[0]
            port = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 50001
            
            # Borrar viejo
            self.core.db.delete_manual_peer(node_id)
            
            # Agregar nuevo (esto disparará un ping_worker y lo inyectará)
            self.core.add_manual_peer(ip, port)
            messagebox.showinfo("Actualizado", f"IP {ip}:{port} actualizada.")
            
    def poll_event_queue(self):
        current_peers = self.core.get_active_peers()
        
        try:
            all_db_devices = self.core.db.get_all_devices()
        except Exception as e:
            logger.error(f"[UI] DB query failed, attempting recovery... {e}")
            try:
                self.core.db._init_db()
                all_db_devices = self.core.db.get_all_devices()
            except Exception as e2:
                logger.error(f"[UI] Unrecoverable DB error: {e2}")
                all_db_devices = []
        
        if not hasattr(self, 'unread_badges'):
            self.unread_badges = {}
        if not hasattr(self, 'known_devices'):
            self.known_devices = {}
            
        # Generar íconos de estado en memoria (para no usar emojis)
        from PIL import Image, ImageDraw
        def create_circle_icon(color):
            img = Image.new('RGBA', (20, 20), (255, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            draw.ellipse((4, 4, 16, 16), fill=color)
            return ctk.CTkImage(light_image=img, size=(12, 12))
            
        if not hasattr(self, 'icon_online'):
            self.icon_online = create_circle_icon("#2ECC71") # Verde
            self.icon_offline = create_circle_icon("#95A5A6") # Gris
            self.icon_unread = create_circle_icon("#E74C3C") # Rojo
            self.icon_empty = create_circle_icon((0,0,0,0)) # Transparente

        # Actualizar dispositivos conocidos
        for node_id, hostname, os_type, last_ip, last_port in all_db_devices:
            self.known_devices[node_id] = {'hostname': hostname, 'os_type': os_type, 'ip': last_ip, 'tcp_port': last_port}
        for node_id, info in current_peers.items():
            self.known_devices[node_id] = {'hostname': info['hostname'], 'os_type': info.get('os', 'Unknown'), 'manual': info.get('manual', False), 'ip': info.get('ip'), 'tcp_port': info.get('tcp_port')}
            
        # Añadir temporal manual peers que aún no conectaron
        if hasattr(self.core, '_temp_manual_peers'):
            for node_id, info in self.core._temp_manual_peers.items():
                self.known_devices[node_id] = {'hostname': info['hostname'], 'os_type': info.get('os', 'Unknown'), 'manual': True}
            
        # Renderizar en la UI
        for node_id, info in self.known_devices.items():
            is_online = node_id in current_peers
            
            is_desktop = "Desktop" in info['os_type'] or "Windows" in info['os_type'] or "Linux" in info['os_type'] or "darwin" in info['os_type'].lower()
            
            # Si es manual y está offline, usar icono de red genérico en vez de móvil
            is_manual = info.get('manual', False) or (node_id.startswith("manual_"))
            if is_manual and not is_online:
                device_icon = self.icons.get('network')
            else:
                device_icon = self.icons.get('laptop') if is_desktop else self.icons.get('smartphone')
                
            display_text = info['hostname']
            
            if node_id not in self.node_buttons:
                node_frame = ctk.CTkFrame(self.nodes_frame, fg_color="transparent")
                node_frame.pack(pady=2, padx=2, fill="x")
                
                # Indicador de estado
                status_lbl = ctk.CTkLabel(node_frame, text="", image=self.icon_online if is_online else self.icon_offline, width=15)
                status_lbl.pack(side="left", padx=(5, 0))
                
                # Botón principal
                btn = ctk.CTkButton(node_frame, text=display_text, image=device_icon, anchor="w", fg_color="transparent",
                                    command=lambda nid=node_id, hname=info['hostname']: self.on_node_select(nid, hname))
                btn.pack(side="left", fill="x", expand=True, padx=(5, 2))
                
                # Click derecho para menú contextual
                btn.bind("<Button-3>", lambda e, nid=node_id: self.show_node_context_menu(e, nid))
                if os.name == 'posix': # Mac support for right click
                    btn.bind("<Button-2>", lambda e, nid=node_id: self.show_node_context_menu(e, nid))
                
                # Indicador de no leído
                unread_lbl = ctk.CTkLabel(node_frame, text="", image=self.icon_unread if self.unread_badges.get(node_id) else self.icon_empty, width=15)
                unread_lbl.pack(side="left", padx=(0, 5))
                    
                self.node_buttons[node_id] = node_frame
                self.node_buttons[node_id]._select_btn = btn
                self.node_buttons[node_id]._status_lbl = status_lbl
                self.node_buttons[node_id]._unread_lbl = unread_lbl
            else:
                self.node_buttons[node_id]._select_btn.configure(text=display_text, image=device_icon)
                self.node_buttons[node_id]._status_lbl.configure(image=self.icon_online if is_online else self.icon_offline)
                self.node_buttons[node_id]._unread_lbl.configure(image=self.icon_unread if self.unread_badges.get(node_id) else self.icon_empty)
                    
        while True:
            try:
                event = self.event_queue.get_nowait()
                self.handle_network_event(event)
            except queue.Empty:
                break
                
        self.after(100, self.poll_event_queue)
        
    def handle_network_event(self, event):
        etype = event.get('event')
        
        if etype not in ["TEXT_RECEIVED", "MSG_EDITED", "COMMAND_RECEIVED", "FILE_RECEIVED", "FILE_PROGRESS"]:
            return
            
        sender_id = event.get('sender_id')
        sender_name = event.get('sender_name', 'Desconocido')
        
        if etype == "TEXT_RECEIVED":
            msg = event.get('text', '')
            if sender_id == self.selected_node_id:
                self.append_to_chat(f"[{sender_name}]: {msg}", raw_msg=msg, direction="IN")
                if hasattr(self, 'unread_badges') and sender_id in self.unread_badges:
                    del self.unread_badges[sender_id]
            else:
                if not hasattr(self, 'unread_badges'):
                    self.unread_badges = {}
                self.unread_badges[sender_id] = True
                
        elif etype == "MSG_EDITED":
            if sender_id == self.selected_node_id:
                self.load_chat_history(self.selected_node_id)
            
        elif etype == "COMMAND_RECEIVED":
            response = event.get('result', '')
            cmd = event.get('command', '')
            success = event.get('success', False)
            icon = "[OK]" if success else "[FAIL]"
            if sender_id == self.selected_node_id:
                self.append_to_chat(f"[SysAdmin] {sender_name} te envió un comando: {cmd}")
                self.append_to_chat(f"[SysAdmin] Resultado enviado a {sender_name}: {icon} Comando ejecutado: {cmd}\nResultado:\n{response}")
            
        elif etype == "FILE_RECEIVED":
            filepath = event.get('filepath', '')
            success = event.get('success', False)
            if sender_id == self.selected_node_id:
                if success:
                    ext = os.path.splitext(filepath)[1].lower()
                    if ext in ['.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp']:
                        self.append_image_to_chat(filepath, sender=sender_name)
                    else:
                        self.append_generic_file_to_chat(filepath, sender=sender_name)
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

    def hide_window(self):
        if self.tray_icon:
            self.withdraw()
            try:
                self.tray_icon.notify("SysNode sigue corriendo en segundo plano", "Minimizado")
            except: pass
        else:
            self.on_closing()
            
    def show_window(self, icon, item):
        self.after(0, self.deiconify)
        
    def quit_app(self, icon, item):
        if self.tray_icon:
            self.tray_icon.stop()
        self.after(0, self.on_closing)
        
    def setup_tray(self):
        try:
            import pystray
            from PIL import Image, ImageDraw
            
            image = Image.new('RGB', (64, 64), color=(31, 83, 141))
            draw = ImageDraw.Draw(image)
            draw.ellipse((16, 16, 48, 48), fill=(46, 204, 113))
            
            menu = pystray.Menu(
                pystray.MenuItem("Mostrar SysNode", self.show_window, default=True),
                pystray.MenuItem("Salir", self.quit_app)
            )
            
            self.tray_icon = pystray.Icon("SysNode", image, "SysNode P2P", menu)
            self.tray_icon.run()
        except Exception as e:
            logger.error(f"No se pudo iniciar el System Tray: {e}")

    def on_closing(self):
        logger.info("[UI] Cerrando la interfaz de escritorio...")
        if hasattr(self, 'single_instance_sock') and self.single_instance_sock:
            try: self.single_instance_sock.close()
            except: pass
        self.core.stop()
        self.destroy()
        
def run_desktop_app(node_core):
    app = SysNodeDesktopApp(node_core)
    app.mainloop()
