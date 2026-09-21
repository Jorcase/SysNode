import os
import threading
import http.server
import socketserver
import logging
import sys

logger = logging.getLogger(__name__)

class SharingHTTPServer:
    def __init__(self, port=8080):
        self.port = port
        self.server = None
        self.thread = None
        
        # El directorio web está dentro de sysnode/web
        if getattr(sys, 'frozen', False):
            self.web_dir = os.path.join(sys._MEIPASS, 'sysnode', 'web')
        else:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            self.web_dir = os.path.join(os.path.dirname(current_dir), 'web')

    def start(self, port=None):
        if port is not None:
            self.port = port
        if self.server is not None:
            logger.warning("El servidor HTTP ya está corriendo.")
            return True
            
        class CustomHandler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, directory=None, **kwargs):
                super().__init__(*args, directory=directory, **kwargs)
                
            def log_message(self, format, *args):
                logger.info(f"[HTTP Server] {self.client_address[0]} - - {format%args}")

            def handle(self):
                try:
                    super().handle()
                except (ConnectionResetError, BrokenPipeError):
                    pass
                except OSError as e:
                    # Ignore common connection drop errors
                    if e.errno in (104, 32, 10054, 10053):
                        pass
                    else:
                        logger.debug(f"[HTTP Server] OS Error in handle: {e}")

            def do_GET(self):
                if getattr(sys, 'frozen', False):
                    # Only serve the host's executable if the correct OS button is clicked
                    target_path = '/sysnode-installer.exe' if os.name == 'nt' else '/sysnode'
                    
                    if self.path == target_path:
                        try:
                            with open(sys.executable, 'rb') as f:
                                fs = os.fstat(f.fileno())
                                self.send_response(200)
                                self.send_header("Content-Type", "application/octet-stream")
                                filename = os.path.basename(sys.executable)
                                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
                                self.send_header("Content-Length", str(fs.st_size))
                                self.end_headers()
                                self.copyfile(f, self.wfile)
                            return
                        except IOError:
                            self.send_error(404, "File not found")
                            return
                super().do_GET()

        import functools
        try:
            # Use functools.partial to pass the directory to the handler without changing CWD
            Handler = functools.partial(CustomHandler, directory=self.web_dir)
            
            # Setup server
            self.server = socketserver.TCPServer(("", self.port), Handler)
            
            # Start in a daemon thread
            self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.thread.start()
            
            logger.info(f"Servidor HTTP iniciado en el puerto {self.port} sirviendo {self.web_dir}")
            return True
        except OSError as e:
            logger.error(f"Error al iniciar el servidor HTTP en el puerto {self.port}: {e}")
            if e.errno == 98: # Address already in use
                self.port += 1
                return self.start()
            return False

    def stop(self):
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
            if self.thread:
                self.thread.join(timeout=1.0)
                self.thread = None
            logger.info("Servidor HTTP detenido.")
