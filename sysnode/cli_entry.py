#!/usr/bin/env python3

import sys
import logging
import argparse

from sysnode.config import DEFAULT_TCP_PORT
from sysnode.core.sysnode_core import SysNodeCore
from sysnode.ui.cli import run_cli


def setup_logging(verbose: bool = False):
    """configura el formato del sistema de logs."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] (%(threadName)s) %(message)s",
        datefmt="%H:%M:%S"
    )


def main():
    parser = argparse.ArgumentParser(description="SysNode P2P Network Tool")
    parser.add_argument("--name", type=str, default=None, help="Nombre lógico del nodo en la red")
    parser.add_argument("--tcp-port", type=int, default=50001, help="Puerto TCP para transferencias (default: 50001)")
    parser.add_argument("--cli", action="store_true", help="Ejecutar en modo consola (CLI) sin interfaz gráfica")
    parser.add_argument("--verbose", action="store_true", help="Habilitar mensajes detallados de depuración")
    args = parser.parse_args()

    setup_logging(args.verbose)

    # Instanciar el core
    core = SysNodeCore(node_name=args.name, tcp_port=args.tcp_port)
    # Iniciar servicios de red en hilos secundarios
    core.start()
    # Lanzar la UI
    try:
        if args.cli:
            logging.info("Iniciando en modo Consola (CLI)...")
            from sysnode.ui.cli import run_cli
            run_cli(core)
        else:
            logging.info("Iniciando en modo Escritorio (GUI)...")
            from sysnode.ui.desktop_app import run_desktop_app
            run_desktop_app(core)
    except KeyboardInterrupt:
        logging.info("Interrupción manual recibida. Cerrando nodo...")
        core.stop()
        sys.exit(0)


if __name__ == "__main__":
    main()
