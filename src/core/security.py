"""
SysNode - Módulo de Seguridad y Hardening (Ciberseguridad - Blue Team)

Previene vulnerabilidades de Command Injection (CWE-77) y ejecución remota no autorizada.
Los comandos que llegan por la red TCP se validan estrictamente contra un mapa estático
de listas blancas (COMMAND_WHITELIST). Ningún string enviado por un cliente se ejecuta
directamente en una shell de sistema.
"""

import os
import sys
import time
import socket
import ctypes
import logging
import subprocess
import platform
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

# Definición de la Lista Blanca de Comandos Permitidos por Sistema Operativo
COMMAND_WHITELIST: Dict[str, Dict[str, Any]] = {
    "CMD_LOCK_SCREEN": {
        "description": "Bloquear la sesión/pantalla de la computadora",
        "linux": ["xdg-screensaver", "lock"],
        "windows": "NATIVE_CTYPES_LOCK",  # ctypes.windll.user32.LockWorkStation()
    },
    "CMD_PING": {
        "description": "Verificar si el nodo remoto tiene conectividad a Internet y medir latencia",
        "linux": None,
        "windows": None,
    },
    "CMD_SYS_INFO": {
        "description": "Obtener métricas básicas de carga y sistema",
        "linux": None,    # Se procesa mediante función interna segura
        "windows": None,  # Se procesa mediante función interna segura
    }
}


def is_command_allowed(command_key: str) -> bool:
    """Verifica si la clave de comando enviada por la red existe en la lista blanca."""
    return command_key in COMMAND_WHITELIST


def execute_whitelisted_command(command_key: str, receiver_name: str = None) -> Tuple[bool, str]:
    """
    Ejecuta de forma segura un comando validado contra la lista blanca.
    Devuelve una tupla (éxito: bool, mensaje_resultado: str).
    """
    if not is_command_allowed(command_key):
        msg = f"ACCESO DENEGADO: El comando '{command_key}' no está registrado en la lista blanca."
        logger.warning(msg)
        return False, msg

    current_os = "windows" if sys.platform.startswith("win") else "linux"
    cmd_info = COMMAND_WHITELIST[command_key]

    node_label = receiver_name or platform.node()

    try:
        # Caso especial 1: Bloqueo de sesión
        if command_key == "CMD_LOCK_SCREEN":
            if current_os == "windows":
                # Usar API nativa ctypes de Windows sin crear procesos externos
                ctypes.windll.user32.LockWorkStation()
                return True, f"[{node_label}] Pantalla bloqueada mediante API nativa de Windows (user32.dll)."
            else:
                # Sistema Inteligente de Reconocimiento de Entorno Linux
                desktop_env = os.environ.get("XDG_CURRENT_DESKTOP", "").upper()
                logger.debug(f"Detectado entorno de escritorio Linux: {desktop_env}")
                
                # Lista priorizada según el entorno detectado
                lock_commands = []
                if "XFCE" in desktop_env:
                    lock_commands.append(["xflock4"])
                elif "GNOME" in desktop_env:
                    lock_commands.append(["gnome-screensaver-command", "-l"])
                elif "KDE" in desktop_env:
                    lock_commands.append(["loginctl", "lock-session"])
                elif "X-CINNAMON" in desktop_env or "CINNAMON" in desktop_env:
                    lock_commands.append(["cinnamon-screensaver-command", "-l"])
                elif "MATE" in desktop_env:
                    lock_commands.append(["mate-screensaver-command", "-l"])
                
                # Comandos de fallback generales por si falla el específico o no se detectó
                lock_commands.extend([
                    ["loginctl", "lock-session"],             # SystemD genérico (muy confiable)
                    ["dm-tool", "lock"],                      # LightDM (usado por Kali Linux por defecto)
                    ["xdg-screensaver", "lock"],
                    ["xflock4"],
                    ["gnome-screensaver-command", "-l"],
                    ["cinnamon-screensaver-command", "-l"],
                    ["mate-screensaver-command", "-l"],
                ])
                
                for lock_cmd in lock_commands:
                    try:
                        proc = subprocess.run(lock_cmd, capture_output=True, text=True)
                        if proc.returncode == 0:
                            return True, f"[{node_label}] Pantalla bloqueada en Linux ({desktop_env or 'Genérico'}) usando {lock_cmd[0]}."
                        else:
                            logger.debug(f"Comando {lock_cmd[0]} falló con código {proc.returncode}.")
                    except FileNotFoundError:
                        continue
                return False, f"[{node_label}] No se pudo bloquear la pantalla. Ningún gestor compatible funcionó."

        # Caso especial 2: Información del sistema
        elif command_key == "CMD_SYS_INFO":
            info_str = f"[{node_label}] OS: {platform.system()} {platform.release()} | Python: {platform.python_version()}"
            return True, info_str

        # Caso especial 3: Ping / Test de Conectividad a Internet real
        elif command_key == "CMD_PING":
            start = time.time()
            try:
                from src.config import PING_TIMEOUT_SEC
                test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                test_sock.settimeout(PING_TIMEOUT_SEC)
                test_sock.connect(("1.1.1.1", 53))
                latency_ms = int((time.time() - start) * 1000)
                test_sock.close()
                return True, f"[{node_label}] 🌐 Conectado a Internet (Latencia: {latency_ms}ms)"
            except Exception:
                return True, f"[{node_label}] ⚠️ Sin salida a Internet (Únicamente conectado a la LAN)"

        # Ejecución genérica basada en argumentos sin shell=True
        cmd_args = cmd_info.get(current_os)
        if not cmd_args:
            return False, f"Comando {command_key} no implementado para la plataforma {current_os}."

        proc = subprocess.run(cmd_args, capture_output=True, text=True, timeout=5, shell=False)
        output = proc.stdout.strip() or f"Comando ejecutado con código de salida {proc.returncode}."
        return True, output

    except Exception as e:
        logger.error(f"Error ejecutando comando {command_key}: {e}")
        return False, f"Error durante la ejecución: {str(e)}"


def sanitize_filename(incoming_filename: str) -> str:
    r"""
    Sanitiza nombres de archivos entrantes desde la red para evitar ataques de Path Traversal (CWE-22).
    Extrae únicamente el nombre base descartando rutas relativas (../) o absolutas (/etc/passwd, C:\...).
    """
    if not incoming_filename:
        return "unnamed_file"
    
    # Extraer únicamente el nombre base del archivo
    clean_name = os.path.basename(incoming_filename.strip())
    
    # Limpiar caracteres prohibidos en nombres de archivo (Windows/Linux)
    for char in '<>:"/\\|?*\0':
        clean_name = clean_name.replace(char, "")
        
    # Prevenir que el nombre sea exactamente ".." o "."
    if clean_name in (".", ".."):
        return "unnamed_file"
    
    return clean_name or "unnamed_file"
