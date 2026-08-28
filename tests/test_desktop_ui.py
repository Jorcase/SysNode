import unittest
import sys
from unittest.mock import MagicMock

# Mockear customtkinter y tkinter antes de importar el módulo de UI
# para evitar errores en entornos CI (headless) sin dependencias gráficas.
sys.modules['customtkinter'] = MagicMock()
sys.modules['tkinter'] = MagicMock()

from src.ui.desktop_app import SysNodeDesktopApp
from src.core.sysnode_core import SysNodeCore

class TestDesktopUI(unittest.TestCase):
    def test_ui_instantiation(self):
        """Verifica que la app de escritorio pueda instanciarse sin errores fatales"""
        # Crear un core dummy
        mock_core = MagicMock(spec=SysNodeCore)
        mock_core.node_name = "MockNode"
        mock_core.local_ip = "127.0.0.1"
        mock_core.tcp_port = 50001
        
        # Instanciar la UI (con customtkinter mockeado)
        try:
            app = SysNodeDesktopApp(mock_core)
            self.assertIsNotNone(app)
        except Exception as e:
            self.fail(f"SysNodeDesktopApp falló al instanciarse: {e}")

if __name__ == '__main__':
    unittest.main()
