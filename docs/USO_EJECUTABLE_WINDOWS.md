# Guía de Uso del Ejecutable de SysNode (Windows)

¡Bienvenido a SysNode! Esta guía te ayudará a ejecutar la aplicación en tu computadora con Windows (10/11) después de descargarla.

## Paso 1: Descargar el archivo
1. Asegúrate de haber descargado el archivo **`sysnode.exe`** desde el servidor de SysNode.
2. El archivo se guardará normalmente en tu carpeta de **Descargas** (Downloads).

## Paso 2: Ejecutar la aplicación
En Windows, SysNode es una aplicación portátil (no requiere instalación), lo que significa que puedes ejecutarla directamente.

1. Abre el **Explorador de Archivos** y ve a tu carpeta de **Descargas**.
2. Haz **doble clic** en el archivo `sysnode.exe` (o `sysnode` si tienes las extensiones de archivo ocultas).

> **Aviso de SmartScreen de Windows Defender:**
> Al ser una aplicación descargada directamente por red local (y no firmada por un certificado comercial de Microsoft), es muy probable que Windows lance una pantalla azul que dice: *"Windows protegió su PC"*.
> 
> **Para continuar:**
> 1. Haz clic en **"Más información"** (debajo del texto).
> 2. Haz clic en el botón **"Ejecutar de todas formas"** que aparecerá en la parte inferior derecha.

## Paso 3: Permisos del Firewall
SysNode necesita conectarse con otras computadoras en tu red local (LAN) para enviar y recibir mensajes/archivos.

La primera vez que abras la aplicación, el **Firewall de Windows Defender** mostrará una alerta preguntando si permites que `sysnode.exe` se comunique por la red.

1. Asegúrate de marcar **Redes privadas** (como la red de tu casa o trabajo).
2. Haz clic en **Permitir acceso**.
*(Si no haces esto, SysNode no podrá encontrar ni conectarse con otras computadoras en la red).*

---

## Solución de problemas comunes

- **El programa tarda un poco en abrir la primera vez:**
  Esto es normal. El sistema empaquetador de Windows necesita descomprimir unos archivos temporales en memoria durante la primera ejecución. Las siguientes veces se abrirá más rápido.

- **No veo a otros usuarios en el chat:**
  Lo más probable es que el Firewall de Windows esté bloqueando la conexión. Puedes ir a:
  `Panel de control > Sistema y seguridad > Firewall de Windows Defender > Permitir una aplicación a través del Firewall`
  Busca "sysnode" y asegúrate de que la casilla "Privada" esté marcada.

- **El Antivirus borró el archivo:**
  Algunos antivirus estrictos (como Avast o McAfee) pueden borrar los archivos `.exe` nuevos por "falsos positivos". Si esto ocurre, simplemente restaura el archivo desde la cuarentena del antivirus y añade una excepción para él.
