"""
Test de Integración Automatizado para la Fase 3 (Transferencia Binaria de Archivos e Integridad SHA-256)
"""

import os
import time
import unittest
from src.core.sysnode_core import SysNodeCore
from src.network.file_transfer import calculate_file_sha256


class TestFileTransfer(unittest.TestCase):

    def setUp(self):
        self.test_filename = "test_dummy_5mb.bin"
        self.test_filepath = os.path.abspath(self.test_filename)
        self.received_dir = os.path.abspath("SysNode_Received")

        # Crear un archivo de prueba binario aleatorio de 5MB
        file_size_bytes = 5 * 1024 * 1024  # 5 MB
        with open(self.test_filepath, "wb") as f:
            f.write(os.urandom(file_size_bytes))

        self.original_sha256 = calculate_file_sha256(self.test_filepath)

    def tearDown(self):
        # Limpiar archivo de prueba local y archivos recibidos
        if os.path.exists(self.test_filepath):
            try:
                os.remove(self.test_filepath)
            except Exception:
                pass

        received_file = os.path.join(self.received_dir, self.test_filename)
        if os.path.exists(received_file):
            try:
                os.remove(received_file)
            except Exception:
                pass

        temp_file = os.path.join(self.received_dir, f"{self.test_filename}.tmp")
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except Exception:
                pass

    def test_file_transfer_integrity(self):
        print("\n--- INICIANDO TEST DE INTEGRACIÓN DE TRANSFERENCIA DE ARCHIVOS (5MB) ---")

        node1 = SysNodeCore(node_name="SenderNode", tcp_port=50007)
        node2 = SysNodeCore(node_name="ReceiverNode", tcp_port=50008)

        try:
            node1.start()
            node2.start()

            print("Esperando 3.5 segundos al descubrimiento UDP...")
            time.sleep(3.5)

            peers_n1 = node1.get_active_peers()
            self.assertIn(node2.node_id, peers_n1)

            print(f"Transmitiendo archivo de 5MB ({self.test_filename}) a ReceiverNode...")
            success, result_msg = node1.send_file_to_peer(node2.node_id, self.test_filepath)

            self.assertTrue(success, f"Error en envío de archivo: {result_msg}")
            print(f"✅ Resultado del envío: {result_msg}")

            # Esperar escritura en disco y verificación SHA-256 en el servidor
            time.sleep(1.0)

            expected_received_file = os.path.join(self.received_dir, self.test_filename)
            self.assertTrue(os.path.exists(expected_received_file), f"El archivo recibido no existe en {expected_received_file}")

            # Verificar que el hash SHA-256 coincida exactamente al 100%
            received_sha256 = calculate_file_sha256(expected_received_file)
            self.assertEqual(received_sha256, self.original_sha256)
            print(f"✅ ¡Verificación de SHA-256 exitosa! ({received_sha256[:16]}...)")

            print("✅ ¡TEST EXITOSO! El archivo de 5MB fue transmitido, recibido e inspeccionado íntegramente.")

        finally:
            node1.stop()
            node2.stop()


if __name__ == "__main__":
    unittest.main()
