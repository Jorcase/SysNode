#!/bin/bash
set -e

echo "Instalando dependencias de Python..."
pip install -r requirements.txt

echo "Limpiando compilaciones previas..."
rm -rf build dist sysnode.spec

echo "Compilando SysNode Desktop con PyInstaller..."
# --onefile: Crear un solo ejecutable
# --noconsole: No mostrar terminal negra en Windows/Linux
# --add-data: Incluir iconos y carpeta web
pyinstaller --onefile --noconsole \
    --name sysnode \
    --add-data "sysnode/ui/assets/icons:sysnode/ui/assets/icons" \
    --add-data "sysnode/web:sysnode/web" \
    main.py

echo "¡Compilación exitosa! El binario está en la carpeta 'dist/'."
