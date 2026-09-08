# Documento de Mejoras y Requisitos - SysNode

**Regla General:** Eliminar todo el uso de emojis en el código y en el front visual. Utilizar íconos modernos y minimalistas.

## 1. Identidad y Usuarios (Repensado)
- Cada dispositivo debe tener su propio "usuario" / identidad permanente para que la comunicación sea fluida.
- Se debe resolver el problema de los nodos duplicados: un dispositivo físico debe mantener su identidad sin importar si cambia su IP local o su puerto.
- A futuro en configuración: poder cambiar el nombre de usuario asociado a este dispositivo.

## 2. Pantalla de Inicio (Welcome Screen) y Configuraciones
- **Menú de Inicio:** Al abrir la app de escritorio, no debe mostrarse directamente un chat vacío. Debe haber un menú de inicio visualmente cómodo que presente las funcionalidades principales hasta que se elija un nodo para interactuar.
- **Apartado de Configuración (Settings):** Un menú dedicado donde se pueda:
  - Cambiar el nombre del usuario.
  - Administrar configuraciones por módulo (ej. elegir o abrir la carpeta de descargas).
  - Administrar y crear nuevos comandos.
- **Compartir App:** En el menú de inicio, agregar un botón para crear un servidor HTTP local que muestre una URL. Si otro dispositivo ingresa a la URL, se le debe ofrecer descargar el APK (Android) o el ejecutable (PC).

## 3. Gestor de Comandos
- **Comandos vía JSON:** Posibilidad de crear y administrar comandos mediante formato JSON.
- **Ejemplos en la UI:** Mostrar de forma visual ejemplos de cómo se debe escribir el JSON para crear comandos.
- **Limitación de Móviles:** Se reafirma que los comandos no se enviarán hacia celulares. El sistema inteligente ya detecta cuando se habla con un móvil. Los celulares sí podrán mandar comandos a la PC.

## 4. Edición de Mensajes y Portapapeles (Core de chat)
- **Copiado rápido:** Los mensajes deben tener un botón para ser copiados de un dispositivo a otro rápidamente (Funcionalidad base del portapapeles). *(Implementado parcialmente)*
- **Edición de mensajes:** Los mensajes enviados deben poder editarse con un botón. Al editar, el cambio debe viajar por la red y actualizarse en el otro dispositivo.

## 5. Diseño y Visualización
- **Archivos:** Mostrar diseño y previsualización de archivos para cualquier extensión (no solo imágenes), estilo tarjetas modernas. *(Implementado)*
- **Notificaciones / Offline:** Si se envían archivos o textos y no estoy mirando el nodo, debe haber un aviso o indicador claro. El esquema debe ser de mensajería asíncrona ("Store & Forward"). *(Implementado)*
- **Íconos de OS:** Los nodos deben mostrar con un ícono claro y minimalista si son PC o Móvil. *(Implementado)*

*Nota técnica:* El sistema fue diseñado para funcionar en una red LAN y **no necesita internet**. Se autodescubre al estar conectado al mismo router o switch. 

## 6. Rediseño Estructural de Interfaz (V2) - Correcciones
- **Íconos Modernos:** Se implementó una librería de íconos en `assets/icons/`. Continuar utilizándolos para organizar la información (ej. en el Perfil).
- **Navegación / Sidebar (Estilo WhatsApp):** Correctamente implementado.
- **Pantalla de Inicio y Perfil (Refinamiento):** 
  - Limpiar la Pantalla de Inicio: Reevaluar si "Añadir IP manual" y "Compartir App" deben ser los protagonistas si el UDP funciona bien. (A discutir si se mueven o se ocultan).
  - El botón "Compartir App (HTTP)" no debe usar un ícono de QR, ya que es para compartir el instalador de PC también.
  - **Nueva Vista de Perfil:** Crear una sección separada (accesible desde el menú) donde se muestre la información del dispositivo de forma ordenada usando íconos, se permita **editar el nombre de usuario**, y se muestre el **Código QR** directamente para que otros lo escaneen.
- **Configuración Modular:**
  - Remover la edición de nombre de usuario de aquí (movida a Perfil).
  - Corregir el layout responsivo en "Archivos y Descargas" para que las rutas largas no empujen los botones fuera de la pantalla.
  - **Comandos:** Permitir **editar** (no solo borrar) los comandos existentes.
  - **Creación de Comando:** El cuadro de texto izquierdo debe estar vacío con un texto de ayuda (placeholder "Escribe aquí..."). La plantilla derecha debe mostrarse sin la aclaración explícita "(No Editable)".