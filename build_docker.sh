#!/bin/bash
set -e

echo "============================================================"
echo "    COMPILACIÓN DE MÁXIMA COMPATIBILIDAD (Ubuntu 22.04)    "
echo "============================================================"
echo "Iniciando compilación en contenedor Docker (Ubuntu 22.04)..."
echo "Esto asegurará que el binario funcione en cualquier Linux moderno."
echo ""

# El comando docker monta el directorio actual (-v "$PWD":/app) y corre adentro del contenedor
docker run --rm -v "$PWD":/app -w /app ubuntu:22.04 bash -c "
    echo '[Contenedor] Actualizando repositorios e instalando Python 3...'
    apt-get update -y && DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-pip python3-tk
    
    echo '[Contenedor] Instalando dependencias del proyecto...'
    pip3 install -r requirements.txt
    
    echo '[Contenedor] Limpiando builds anteriores...'
    rm -rf build dist sysnode.spec
    
    echo '[Contenedor] Empaquetando con PyInstaller...'
    pyinstaller --onefile --noconsole \\
        --name sysnode \\
        --hidden-import PIL._tkinter_finder \\
        --add-data 'sysnode/ui/assets/icons:sysnode/ui/assets/icons' \\
        --add-data 'sysnode/web:sysnode/web' \\
        main.py
        
    echo '[Contenedor] Compilación finalizada exitosamente.'
"

echo ""
echo "¡Proceso terminado! Tu binario ultra-compatible se encuentra en la carpeta 'dist/' de tu host."
echo "Este archivo 'sysnode' se puede correr en Kali, Ubuntu 22.04+, Debian, Fedora, etc."
