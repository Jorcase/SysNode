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

    def start(self):
        if self.server is not None:
            logger.warning("El servidor HTTP ya está corriendo.")
            return True
            
        class CustomHandler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, directory=None, **kwargs):
                super().__init__(*args, directory=directory, **kwargs)
                
            def log_message(self, format, *args):
                logger.info(f"[HTTP Server] {self.client_address[0]} - - {format%args}")

            def do_GET(self):
                if self.path == '/sysnode' and getattr(sys, 'frozen', False):
                    try:
                        with open(sys.executable, 'rb') as f:
                            fs = os.fstat(f.fileno())
                            self.send_response(200)
                            self.send_header("Content-Type", "application/octet-stream")
                            self.send_header("Content-Disposition", 'attachment; filename="sysnode"')
                            self.send_header("Content-Length", str(fs.st_size))
                            self.end_headers()
                            self.copyfile(f, self.wfile)
                        return
                    except IOError:
                        self.send_error(404, "File not found")
                        return
                super().do_GET()

        try:
            # Change to the web directory so we serve its contents directly
            os.chdir(self.web_dir)
            
            # Setup server
            self.server = socketserver.TCPServer(("", self.port), CustomHandler)
            
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
