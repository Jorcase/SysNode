"""
SysNode - Configuración y Constantes Globales de Red
"""

import os
import platform

# Puertos por defecto
UDP_DISCOVERY_PORT = 50000
DEFAULT_TCP_PORT = 50001

# Direcciones IP y Broadcast
BROADCAST_IP = "255.255.255.255"
BIND_ALL_IP = "0.0.0.0"

# Temporizadores (segundos)
BEACON_INTERVAL_SEC = 3.0
PEER_TTL_SEC = 10.0
SOCKET_TIMEOUT_SEC = 2.0
PING_TIMEOUT_SEC = 2.0
FILE_TRANSFER_TIMEOUT_SEC = 30.0
AUTH_TIMEOUT_SEC = 5.0

# Tamaños de búfer y framing (bytes)
BUFFER_SIZE = 4096
TCP_HEADER_SIZE = 4  # 4 bytes Big-Endian unsigned int (struct format '>I')

# Nombre y plataforma del sistema
HOST_NAME = platform.node() or "sysnode-host"
SYSTEM_OS = platform.system().lower()

# Mensaje de identificación del protocolo
PROTOCOL_TYPE_ANNOUNCE = "SYSNODE_ANNOUNCE"
PROTOCOL_TYPE_GOODBYE = "SYSNODE_GOODBYE"
