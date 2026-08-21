#!/usr/bin/env python3
"""
SysNode - Punto de Entrada Principal
"""

import sys
import logging
import argparse

from src.config import DEFAULT_TCP_PORT
from src.core.sysnode_core import SysNodeCore
from src.ui.cli import run_cli


def setup_logging(verbose: bool = False):
    """Configura el formato del sistema de logs."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] (%(threadName)s) %(message)s",
        datefmt="%H:%M:%S"
    )


def main():
    parser = argparse.ArgumentParser(description="SysNode P2P Network Tool")
    parser.add_argument("--name", type=str, help="Nombre del nodo para mostrar en la red", default=None)
    parser.add_argument("--tcp-port", type=int, help="Puerto TCP de escucha para conexiones", default=DEFAULT_TCP_PORT)
    parser.add_argument("--verbose", action="store_true", help="Habilitar mensajes detallados de depuración")

    args = parser.parse_args()

    setup_logging(args.verbose)

    # Crear instancia del núcleo SysNodeCore
    node_core = SysNodeCore(node_name=args.name, tcp_port=args.tcp_port)

    # Iniciar interfaz CLI por defecto para la Fase 1
    run_cli(node_core)


if __name__ == "__main__":
    main()
