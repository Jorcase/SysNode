"""
Test de Integración Automatizado para la Fase 2 (TCP Framing, Shared Board y Comandos SysAdmin)
"""

import time
import unittest
from sysnode.core.sysnode_core import SysNodeCore


class TestTCPFramingAndCommands(unittest.TestCase):

    def test_tcp_framing_and_messaging(self):
        print("\n--- INICIANDO TEST DE INTEGRACIÓN TCP FRAMING & COMANDOS ---")

        import tempfile
        db1 = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
        db2 = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name

        # Instanciar dos nodos en distintos puertos TCP y bases de datos aisladas
        node1 = SysNodeCore(node_name="NodeAlpha", tcp_port=50005, db_path=db1)
        node2 = SysNodeCore(node_name="NodeBeta", tcp_port=50006, db_path=db2)

        try:
            node1.start()
            node2.start()

            print("Esperando 3.5 segundos al descubrimiento UDP...")
            time.sleep(3.5)

            peers_n1 = node1.get_active_peers()
            peers_n2 = node2.get_active_peers()

            self.assertIn(node2.node_id, peers_n1)
            self.assertIn(node1.node_id, peers_n2)

            # Test 1: Enviar Texto (Shared Board) desde Node1 hacia Node2
            print("Probando envío de texto desde NodeAlpha a NodeBeta...")
            text_to_send = "Mensaje de prueba con framing TCP: https://github.com/jorcas/sysnode"
            node2_q = node2.register_event_queue()
            success, response_msg, _ = node1.send_text_to_peer(node2.node_id, text_to_send)

            self.assertTrue(success, f"Error en envío de texto: {response_msg}")
            print(f"✅ Respuesta ACK del servidor: {response_msg}")

            # Esperar procesamiento de evento en queue
            time.sleep(0.5)

            # Verificar que Node2 recibió el evento TEXT_RECEIVED
            received_event = None
            while not node2_q.empty():
                evt = node2_q.get_nowait()
                if evt.get("event") == "TEXT_RECEIVED":
                    received_event = evt
                    break

            self.assertIsNotNone(received_event)
            self.assertEqual(received_event["text"], text_to_send)
            self.assertEqual(received_event["sender_name"], "NodeAlpha")
            print("✅ ¡Verificación de Shared Board exitosa!")

            # Test 2: Enviar Comando Remoto (CMD_PING) desde Node2 hacia Node1
            print("Probando envío de comando remoto CMD_PING desde NodeBeta a NodeAlpha...")
            success_cmd, result_cmd = node2.send_command_to_peer(node1.node_id, "CMD_PING")

            self.assertTrue(success_cmd, f"Error en comando: {result_cmd}")
            self.assertTrue("Internet" in result_cmd, f"Respuesta inesperada en ping: {result_cmd}")
            print(f"✅ Resultado del comando de conectividad: {result_cmd}")

            # Test 3: Probar rechazo de comando no autorizado (Inyección)
            print("Probando rechazo de comando NO autorizado 'CMD_MALICIOUS'...")
            success_bad, result_bad = node2.send_command_to_peer(node1.node_id, "CMD_MALICIOUS")
            self.assertFalse(success_bad)
            self.assertIn("ACCESO DENEGADO", result_bad)
            print("✅ ¡Comando malicioso rechazado correctamente por la Lista Blanca!")

            print("✅ ¡TEST EXITOSO! Todas las pruebas de TCP Framing y Seguridad pasaron limpiamente.")

        finally:
            node1.stop()
            node2.stop()


if __name__ == "__main__":
    unittest.main()
