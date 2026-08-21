# SysNode - Infraestructura y Ciberseguridad (Hardening)

Este documento detalla las medidas de seguridad implementadas en SysNode para evitar que el software se convierta en una vulnerabilidad de red (Backdoor o RCE).

---

## 1. Prevención de Inyección de Comandos (Command Injection - CWE-77)

Dado que SysNode permite a otros nodos en la LAN solicitar la ejecución de acciones remotas (Botonera SysAdmin), se deben aplicar reglas estrictas:

### Regla 1: Mapeo Estricto por Lista Blanca (Whitelist)
No se envían ni se reciben cadenas de terminal directas (`"bash -c ..."`). Se envían **Tokens de Comando**.

```python
# src/core/security.py

COMMAND_WHITELIST = {
    "CMD_LOCK_SCREEN": {
        "linux": ["xdg-screensaver", "lock"],
        "windows": ["rundll32.exe", "user32.dll,LockWorkStation"],
        "description": "Bloquear la pantalla de la computadora"
    },
    "CMD_PING": {
        "linux": ["echo", "pong"],
        "windows": ["cmd.exe", "/c", "echo", "pong"],
        "description": "Test de conectividad y estado"
    }
}

def execute_whitelisted_command(command_key: str) -> bool:
    if command_key not in COMMAND_WHITELIST:
        logger.warning(f"Intento de ejecución no autorizada o no reconocida: {command_key}")
        return False

    current_os = "windows" if sys.platform.startswith("win") else "linux"
    cmd_args = COMMAND_WHITELIST[command_key].get(current_os)
    
    if not cmd_args:
        return False

    # NUNCA usar shell=True
    subprocess.Popen(cmd_args, shell=False)
    return True
```

---

## 2. Prevención de Path Traversal (CWE-22)

Al recibir archivos por la red TCP, un nodo atacante podría enviar una cabecera con nombres maliciosos como:
`../../../../home/user/.bashrc` o `..\..\Windows\System32\cmd.exe`.

### Regla 2: Sanitización de Rutas y Aislamiento de Archivos
* Todo nombre de archivo entrante pasa por `os.path.basename()`.
* Los archivos se guardan obligatoriamente dentro de un directorio seguro configurado (ej. `~/Downloads/SysNode_Received/`).

```python
import os

def sanitize_filename(incoming_filename: str) -> str:
    # Extrae únicamente el nombre final del archivo, descartando rutas relativas o absolutas
    safe_name = os.path.basename(incoming_filename)
    # Reemplaza caracteres no seguros si fuera necesario
    return safe_name
```

---

## 3. Seguridad en la Red y Multiplexación en Linux (Fedora)

* **Opciones de Socket (`SO_REUSEADDR` / `SO_REUSEPORT`):** Garantizan el reinicio rápido del servidor sin quedar bloqueado en estado `TIME_WAIT` de TCP.
* **Binding Local vs Broad Network:** El servidor HTTP embebido para la interfaz móvil escucha únicamente en la interfaz IP de la red local (`192.168.X.X`), previniendo accesos indeseados fuera de la LAN.
