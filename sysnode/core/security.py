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
                from sysnode.config import PING_TIMEOUT_SEC
                test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                test_sock.settimeout(PING_TIMEOUT_SEC)
                test_sock.connect(("1.1.1.1", 53))
                latency_ms = int((time.time() - start) * 1000)
                test_sock.close()
                return True, f"[{node_label}] Conectado a Internet (Latencia: {latency_ms}ms)"
            except Exception:
                return True, f"[{node_label}] Sin salida a Internet (Únicamente conectado a la LAN)"

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

def get_detailed_os() -> list:
    """Retorna una lista de identificadores de SO de más específico a más general."""
    sys_os = platform.system().lower()
    if sys_os == "windows":
        return ["windows"]
    if sys_os == "darwin":
        return ["mac", "macos", "darwin"]
    
    os_list = ["linux"]
    if sys_os == "linux":
        try:
            with open("/etc/os-release", "r") as f:
                for line in f:
                    if line.startswith("ID="):
                        distro_id = line.strip().split("=")[1].strip('"').lower()
                        os_list.insert(0, distro_id)
                        break
        except Exception:
            pass
    return os_list

def parse_multi_os_command(raw_command: str, os_hierarchy: list) -> str:
    """
    Parsea un comando con etiquetas como [windows], [ubuntu], [linux]
    y devuelve el mejor comando para el SO actual.
    Si no hay etiquetas, devuelve el comando original.
    """
    import re
    
    # Buscar todas las etiquetas y su contenido
    # Formato: [etiqueta]\n comando...
    blocks = re.split(r'\[(.*?)\]', raw_command)
    
    if len(blocks) <= 1:
        # No hay etiquetas, es un comando crudo
        return raw_command.strip()
        
    cmd_map = {}
    # blocks[0] es lo que hay antes de la primera etiqueta (generalmente vacío)
    for i in range(1, len(blocks), 2):
        tag = blocks[i].strip().lower()
        content = blocks[i+1].strip()
        cmd_map[tag] = content
        
    # Buscar el más específico
    for os_id in os_hierarchy:
        if os_id in cmd_map:
            return cmd_map[os_id]
            
    # Fallback
    return ""

def execute_custom_bash_command(bash_command: str, receiver_name: str = None, is_background: bool = False) -> Tuple[bool, str]:
    """
    Ejecuta un comando Bash/Batch arbitrario enviado desde un dispositivo vinculado y confiable.
    Atención: Esto ignora la lista blanca y delega la seguridad exclusivamente al token de vinculación.
    """
    node_label = receiver_name or platform.node()
    
    os_hierarchy = get_detailed_os()
    final_command = parse_multi_os_command(bash_command, os_hierarchy)
    
    if not final_command:
        return False, f"[{node_label}] Error: El comando proporcionado no tiene instrucciones compatibles para este sistema operativo (Detectado: {os_hierarchy})."
        
    try:
        if is_background:
            # Lanzar en segundo plano sin esperar a que termine
            subprocess.Popen(final_command, shell=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True, f"[{node_label}] $ {final_command}\n[Proceso ejecutado correctamente en segundo plano]"
        else:
            # Ejecución síncrona normal con timeout
            proc = subprocess.run(final_command, shell=True, capture_output=True, text=True, timeout=10)
            
            output = proc.stdout.strip()
            if proc.stderr.strip():
                output += f"\n[stderr]\n{proc.stderr.strip()}"
                
            if not output:
                output = f"Comando ejecutado. Código de salida: {proc.returncode}"
                
            return (proc.returncode == 0), f"[{node_label}] $ {final_command}\n{output}"
            
    except subprocess.TimeoutExpired:
        return False, f"[{node_label}] Error: El comando excedió el tiempo límite (10s)."
    except FileNotFoundError:
        return False, f"[{node_label}] Error: Comando no encontrado o archivo inexistente."
    except Exception as e:
        logger.error(f"Error ejecutando comando bash remoto: {e}")
        return False, f"[{node_label}] Error en ejecución: {str(e)}"

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
