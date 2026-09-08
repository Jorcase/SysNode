# Guía de Compilación y Distribución (SysNode)

Esta guía explica paso a paso cómo compilar SysNode para convertirlo en un ejecutable portátil (`.exe` o binario de Linux) que no requiere que el usuario final instale Python ni librerías adicionales. También detalla cómo instalar la aplicación en Linux para que funcione como una aplicación nativa.

---

## 1. Reglas Generales de PyInstaller
PyInstaller empaqueta tu código y el intérprete de Python en un solo archivo.
* **No hay compilación cruzada:** Para obtener un `sysnode.exe` de Windows, **debes compilar en Windows**. Para obtener un binario de Linux, **debes compilar en Linux**.
* **Compatibilidad de Linux (GLIBC):** Los ejecutables de Linux heredan las librerías base (como glibc) del sistema donde se compilan. Si compilas en un sistema *muy* nuevo (ej. Fedora 40), podría no funcionar en un servidor de Ubuntu 18.04 que tiene librerías más antiguas.
  * **Solución 1:** Compila normalmente en tu Kali o Fedora. Funcionará excelente en cualquier sistema moderno.
  * **Solución 2 (Profesional):** Si quieres máxima compatibilidad, usa Docker para compilar. Levantando un contenedor viejo (`docker run -it ubuntu:20.04 bash`) y corriendo el script `build.sh` allí adentro, te asegurarás de que funcione en cualquier sistema del 2020 en adelante.

---

## 2. Compilación en Linux (Fedora / Kali / Ubuntu)

1. Abre una terminal en la carpeta raíz del proyecto.
2. Da permisos de ejecución al script y córrelo:
   ```bash
   chmod +x build.sh
   ./build.sh
   ```
3. El compilador instalará las dependencias y creará un archivo único llamado **`sysnode`** dentro de la carpeta `dist/`.

### Cómo instalarlo globalmente para usar el comando `sysnode`
Para poder abrir una terminal en cualquier parte del sistema y simplemente escribir `sysnode` (como lo haces en Fedora):

```bash
# Mueve el ejecutable a la carpeta de binarios del usuario local (o /usr/local/bin)
sudo cp dist/sysnode /usr/local/bin/sysnode

# Asegúrate de que tenga permisos
sudo chmod +x /usr/local/bin/sysnode
```

### Cómo crear un Acceso Directo (Icono de App) en Linux
Para que "SysNode" aparezca en el menú de aplicaciones del sistema (junto a Chrome, Firefox, etc.) y tenga su propio icono:

1. Crea un archivo llamado `sysnode.desktop` en `~/.local/share/applications/`:
   ```bash
   nano ~/.local/share/applications/sysnode.desktop
   ```
2. Pega el siguiente contenido (ajustando las rutas según dónde tengas guardado el ejecutable y el icono si no lo copiaste a un directorio general):
   ```ini
   [Desktop Entry]
   Version=1.0
   Type=Application
   Name=SysNode
   Comment=Sistema de Comunicación de Red Local
   Exec=/usr/local/bin/sysnode
   Icon=/ruta/absoluta/a/tu/proyecto/SysNode/sysnode/ui/assets/icons/home.png
   Terminal=false
   Categories=Network;Utility;
   ```
3. Guarda el archivo. El sistema lo detectará automáticamente y podrás buscar "SysNode" en tu menú de inicio de Linux.

---

## 3. Compilación en Windows

1. Descarga o clona el repositorio en una computadora con Windows.
2. Haz doble clic en el archivo **`build.bat`**.
3. Se abrirá una terminal negra que instalará todas las dependencias mediante `pip` y comenzará el empaquetado.
4. Al terminar, tendrás el archivo **`sysnode.exe`** en la carpeta `dist\`.

Este `.exe` es completamente portátil. Puedes enviarlo por pendrive o red a cualquier otra PC con Windows 10/11 y funcionará con doble clic, sin pedir que instalen absolutamente nada.
