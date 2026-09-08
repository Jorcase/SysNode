# Guía de Uso del Ejecutable de SysNode (Linux)

¡Bienvenido a SysNode! Esta guía explica cómo ejecutar la aplicación una vez descargado el archivo `sysnode` en tu sistema Linux (Kali, Ubuntu, Fedora, Mint, Pop!_OS, etc.).

## Paso 1: Descargar el archivo
1. Asegúrate de haber descargado el archivo **`sysnode`** desde el servidor compartido en tu red local (por ejemplo: `http://192.168.x.x:8080/sysnode`).
2. El archivo se guardará típicamente en tu carpeta de **Descargas** (Downloads).

## Paso 2: Otorgar permisos de ejecución
Por seguridad, los sistemas Linux no permiten ejecutar programas recién descargados de internet hasta que el usuario se lo permita explícitamente.

1. Abre una **Terminal**.
2. Navega hasta la carpeta donde descargaste el archivo:
   ```bash
   cd ~/Descargas
   # o cd ~/Downloads
   ```
3. Ejecuta el siguiente comando para darle permisos de ejecución:
   ```bash
   chmod +x sysnode
   ```

## Paso 3: Ejecutar SysNode
Puedes ejecutar SysNode de dos maneras:

### Opción A: Ejecución directa (Rápida)
Simplemente corre el archivo en la terminal estando en la misma carpeta:
```bash
./sysnode
```
La interfaz gráfica se abrirá automáticamente.

### Opción B: Instalación global (Recomendada)
Si quieres poder abrir SysNode desde cualquier parte escribiendo `sysnode` en la terminal (como cualquier otro comando del sistema):

1. Mueve el archivo a la carpeta de binarios locales (requiere contraseña de administrador):
   ```bash
   sudo mv sysnode /usr/local/bin/sysnode
   ```
2. ¡Listo! Ahora solo abre tu terminal en cualquier momento y escribe:
   ```bash
   sysnode
   ```

---

## Solución de problemas comunes

- **El programa arranca pero no veo la ventana:**
  Asegúrate de que estás corriendo el programa en un entorno gráfico (Desktop Environment como GNOME, XFCE o KDE). SysNode no funciona en modo consola pura (tty) a menos que se configure en modo *headless*.

- **"No such file or directory" al intentar ejecutar:**
  Asegúrate de estar en la misma carpeta donde descargaste el archivo antes de hacer `./sysnode`, o verifica que el archivo no haya cambiado de nombre al descargarse (por ejemplo `sysnode(1)`).

- **La aplicación advierte sobre puertos ocupados:**
  SysNode usa los puertos `50000` (UDP) y `50001` (TCP). Asegúrate de no tener otra instancia de SysNode corriendo en segundo plano o algún firewall estricto que bloquee estos puertos locales.
