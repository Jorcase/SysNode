import os
import sys
import random
import string
import select
import socket
import struct
import logging
import threading
import subprocess
from typing import Dict, Any, Optional, Tuple, Callable

from sysnode.network.framing import send_framed_message

logger = logging.getLogger(__name__)

# Comprobar disponibilidad de pty y termios (Linux/macOS)
HAS_PTY = False
try:
    import pty
    import termios
    import fcntl
    HAS_PTY = True
except ImportError:
    HAS_PTY = False


class PTYSession:
    #Representa una sesión interactiva PTY activa.

    def __init__(self, session_id: str, client_sock: socket.socket, pin: str, cols: int = 80, rows: int = 24):
        self.session_id = session_id
        self.client_sock = client_sock
        self.pin = pin
        self.cols = cols
        self.rows = rows
        self.authenticated = False
        self.running = False
        
        self.master_fd: Optional[int] = None
        self.slave_fd: Optional[int] = None
        self.proc: Optional[subprocess.Popen] = None
        self.reader_thread: Optional[threading.Thread] = None

    def start_shell(self):
        #Inicia el proceso shell (/bin/bash o cmd.exe) atado a la PTY.
        shell_cmd = os.environ.get("SHELL") or ("/bin/bash" if sys.platform != "win32" else "cmd.exe")
        
        if HAS_PTY and sys.platform != "win32":
            try:
                master, slave = pty.openpty()
                self.master_fd = master
                self.slave_fd = slave

                # Configurar dimensiones iniciales de la PTY
                self.set_winsize(self.cols, self.rows)

                env = os.environ.copy()
                env["TERM"] = "xterm-256color"

                self.proc = subprocess.Popen(
                    [shell_cmd],
                    preexec_fn=os.setsid,
                    stdin=slave,
                    stdout=slave,
                    stderr=slave,
                    env=env,
                    close_fds=True
                )
                self.running = True
                self.reader_thread = threading.Thread(target=self._read_master_loop, daemon=True)
                self.reader_thread.start()
                logger.info(f"Sesión PTY Linux iniciada ({shell_cmd}) | ID: {self.session_id}")
                return True
            except Exception as e:
                logger.error(f"Error iniciando PTY en Linux: {e}")
                return False
        else:
            # Fallback para Windows o entornos sin pty nativo
            try:
                env = os.environ.copy()
                env["TERM"] = "xterm-256color"
                self.proc = subprocess.Popen(
                    [shell_cmd],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    env=env,
                    bufsize=0,
                    text=False
                )
                self.running = True
                self.reader_thread = threading.Thread(target=self._read_pipe_loop, daemon=True)
                self.reader_thread.start()
                logger.info(f"Sesión Shell Windows iniciada ({shell_cmd}) | ID: {self.session_id}")
                return True
            except Exception as e:
                logger.error(f"Error iniciando Shell en Windows: {e}")
                return False

    def write_stdin(self, data_str: str):
        #Escribe datos de entrada (teclado/stdin) hacia la shell.
        if not self.running:
            return
        
        try:
            data_bytes = data_str.encode("utf-8")
            if self.master_fd is not None:
                os.write(self.master_fd, data_bytes)
            elif self.proc and self.proc.stdin:
                self.proc.stdin.write(data_bytes)
                self.proc.stdin.flush()
        except Exception as e:
            logger.error(f"Error escribiendo en stdin PTY: {e}")

    def set_winsize(self, cols: int, rows: int):
        #Ajusta las dimensiones de la ventana PTY (cols, rows).
        self.cols = cols
        self.rows = rows
        if HAS_PTY and self.master_fd is not None:
            try:
                s = struct.pack("HHHH", rows, cols, 0, 0)
                fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, s)
            except Exception:
                pass

    def _read_master_loop(self):
        #Hilo lector continuo desde la PTY master hacia el socket TCP del cliente.
        while self.running and self.master_fd is not None:
            try:
                r, _, _ = select.select([self.master_fd], [], [], 0.1)
                if self.master_fd in r:
                    output = os.read(self.master_fd, 4096)
                    if not output:
                        break
                    
                    output_str = output.decode("utf-8", errors="replace")
                    send_framed_message(self.client_sock, {
                        "action": "TERM_STDOUT",
                        "session_id": self.session_id,
                        "data": output_str
                    })
            except (OSError, socket.error):
                break
        
        self.close()

    def _read_pipe_loop(self):
        #Hilo lector continuo para pipes de Windows.
        while self.running and self.proc and self.proc.stdout:
            try:
                chunk = self.proc.stdout.read(1024)
                if not chunk:
                    break
                
                output_str = chunk.decode("utf-8", errors="replace")
                send_framed_message(self.client_sock, {
                    "action": "TERM_STDOUT",
                    "session_id": self.session_id,
                    "data": output_str
                })
            except Exception:
                break

        self.close()

    def close(self):
        #Cierra la sesión PTY y libera procesos/descriptores.
        if not self.running:
            return
        
        self.running = False
        logger.info(f"Cerrando sesión PTY {self.session_id}...")

        if self.proc:
            try:
                self.proc.terminate()
            except Exception:
                pass

        if self.master_fd is not None:
            try:
                os.close(self.master_fd)
            except Exception:
                pass

        if self.slave_fd is not None:
            try:
                os.close(self.slave_fd)
            except Exception:
                pass

        # Notificar al cliente el cierre de sesión
        try:
            send_framed_message(self.client_sock, {
                "action": "TERM_CLOSE",
                "session_id": self.session_id
            })
        except Exception:
            pass


class TerminalManager:
    #Administrador global de sesiones de terminal en el nodo.

    def __init__(self):
        self.sessions: Dict[str, PTYSession] = {}
        self.lock = threading.Lock()

    def create_session(self, client_sock: socket.socket, cols: int = 80, rows: int = 24) -> Tuple[str, str]:
        #Genera una nueva sesión con un PIN de 6 dígitos.
        session_id = f"term_{random.randint(100000, 999999)}"
        pin = f"{random.randint(100000, 999999)}"
        
        session = PTYSession(session_id, client_sock, pin, cols, rows)
        with self.lock:
            self.sessions[session_id] = session
            
        return session_id, pin

    def authenticate_session(self, session_id: str, pin: str) -> bool:
        #Verifica el PIN de autorización para iniciar la shell.
        with self.lock:
            session = self.sessions.get(session_id)
            if not session:
                logger.warning(f"Intento de autenticar sesión PTY inexistente: {session_id}")
                return False
            
            clean_rec = str(pin).strip()
            clean_exp = str(session.pin).strip()
            
            if clean_rec == clean_exp:
                session.authenticated = True
                success = session.start_shell()
                logger.info(f"Autenticación PTY EXITOSA para sesión {session_id}")
                return success
            else:
                logger.warning(f"PIN PTY incorrecto para sesión {session_id}: Recibido '{clean_rec}', Esperado '{clean_exp}'")
                return False

    def handle_stdin(self, session_id: str, data: str):
        with self.lock:
            session = self.sessions.get(session_id)
            if session and session.authenticated:
                session.write_stdin(data)

    def handle_resize(self, session_id: str, cols: int, rows: int):
        with self.lock:
            session = self.sessions.get(session_id)
            if session and session.authenticated:
                session.set_winsize(cols, rows)

    def close_session(self, session_id: str):
        with self.lock:
            session = self.sessions.pop(session_id, None)
            if session:
                session.close()


# Instancia global del administrador de terminales
terminal_manager = TerminalManager()
