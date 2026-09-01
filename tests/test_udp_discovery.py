"""
Test de Integración para la Fase 1: Descubrimiento UDP entre 2 Nodos SysNodeCore
"""

import time
import unittest
from sysnode.core.sysnode_core import SysNodeCore


class TestUDPDiscovery(unittest.TestCase):

    def test_two_nodes_discovery(self):
        print("\n--- INICIANDO TEST DE INTEGRACIÓN UDP DISCOVERY ---")
        
        # Instanciar dos nodos en la misma PC con distintos nombres y puertos TCP
        node1 = SysNodeCore(node_name="TestNode_Alpha", tcp_port=50001)
        node2 = SysNodeCore(node_name="TestNode_Beta", tcp_port=50002)

        try:
            node1.start()
            node2.start()

            print("Esperando 3.5 segundos a la propagación del UDP Broadcast...")
            time.sleep(3.5)

            peers_node1 = node1.get_active_peers()
            peers_node2 = node2.get_active_peers()

            print(f"Nodos descubiertos por Node1 (Alpha): {len(peers_node1)}")
            print(f"Nodos descubiertos por Node2 (Beta): {len(peers_node2)}")

            # Verificaciones:
            # Node1 debe haber descubierto a Node2
            self.assertIn(node2.node_id, peers_node1)
            self.assertEqual(peers_node1[node2.node_id]["hostname"], "TestNode_Beta")
            self.assertEqual(peers_node1[node2.node_id]["tcp_port"], 50002)

            # Node2 debe haber descubierto a Node1
            self.assertIn(node1.node_id, peers_node2)
            self.assertEqual(peers_node2[node1.node_id]["hostname"], "TestNode_Alpha")
            self.assertEqual(peers_node2[node1.node_id]["tcp_port"], 50001)

            print("✅ ¡TEST EXITOSO! Los 2 nodos se descubrieron mutuamente vía UDP Broadcast.")

        finally:
            node1.stop()
            node2.stop()


if __name__ == "__main__":
    unittest.main()
