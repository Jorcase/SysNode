# SysNode

**SysNode** es un sistema de comunicación P2P y transferencia de archivos enfocado en redes locales (LAN/Wi-Fi). No requiere servidores centrales, funciona 100% offline, detecta dispositivos en tu red automáticamente y ofrece una interfaz moderna y fluida.

## 🚀 Características
- **Descubrimiento Automático**: Encuentra a otros dispositivos ejecutando SysNode instantáneamente vía UDP.
- **Chat P2P Cifrado**: Comunicación directa vía TCP sin intermediarios.
- **Transferencia de Archivos Rápida**: Comparte archivos pesados a velocidad de LAN sin consumir datos de internet.
- **Multiplataforma**: Funciona en Windows, Linux, macOS y Android.
- **Servidor HTTP Integrado**: Puedes levantar un servidor web temporal desde el panel de configuración para que otros dispositivos de la red descarguen el cliente sin necesidad de usar USB o internet.
- **Conexiones Manuales**: ¿Estás en subredes distintas o VPNs? Ingresa la IP de tu compañero manualmente.

---

## 🛠️ Cómo compilar y empaquetar

SysNode está escrito en Python y utiliza **CustomTkinter** para la UI moderna de escritorio. Para distribuir la aplicación sin que los usuarios tengan que instalar Python, utilizamos **PyInstaller**.

### 1. Clonar el repositorio
```bash
git clone https://github.com/tu-usuario/SysNode.git
cd SysNode
```

### 2. Ejecutar desde el código fuente
Si solo deseas correr el programa usando tu propio entorno Python:
```bash
pip install -r requirements.txt
python3 main.py
```

### 3. Crear el Ejecutable (Binario)
El script de compilación `build.sh` automatiza todo el proceso, empaqueta los íconos, la carpeta web y compila un ejecutable de un solo archivo.

```bash
# Dar permisos de ejecución
chmod +x build.sh

# Ejecutar el empaquetado
./build.sh
```
Al finalizar, encontrarás tu ejecutable en la carpeta `dist/`.

> **Nota para Windows**: Puedes correr `pip install -r requirements.txt` y luego ejecutar el comando de PyInstaller manualmente en PowerShell:
> `pyinstaller --onefile --noconsole --name sysnode --add-data "sysnode/ui/assets/icons;sysnode/ui/assets/icons" --add-data "sysnode/web;sysnode/web" main.py`

---

## 📱 Servidor de Descargas Integrado
Si tienes amigos o compañeros en tu red que no tienen SysNode instalado:
1. Abre SysNode.
2. Ve a **Configuración** y activa el **Servidor HTTP**.
3. Pídeles que ingresen a `http://[Tu-IP-Local]:8080` desde su navegador.
4. Podrán descargar directamente la versión para Linux, Windows o Android.

*Nota: Para que el botón de descarga del servidor integrado devuelva tu ejecutable empaquetado, simplemente cópialo a la carpeta `sysnode/web/` antes o después de generarlo, o el servidor interceptará la ruta `/sysnode` y servirá su propio binario en ejecución.*
