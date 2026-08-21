SYSNODE: Architecture & Development Blueprint
1. Contexto y Reglas Estrictas para el Asistente de IA
Usuario: Estudiante de Tecnicatura en Programación, perfil orientado a Ciberseguridad e Infraestructura (SysAdmin/Linux).
Objetivo del Proyecto: Aprobar un examen final universitario de Redes (22 de septiembre) demostrando dominio de Sockets a bajo nivel, y construir una herramienta útil para su portafolio profesional.

REGLAS DE ORO PARA LA GENERACIÓN DE CÓDIGO (LEER CON ATENCIÓN):

Cero Abstracciones en Redes: PROHIBIDO usar librerías de alto nivel para la red (como HTTP requests para transferir archivos, o frameworks que oculten el socket). Todo el motor de red debe construirse usando la librería nativa socket de Python.

Concurrencia Clásica: PROHIBIDO usar asyncio. El manejo de concurrencia debe realizarse estrictamente con el módulo threading y la comunicación entre hilos con queue.Queue. (Para el agente que lea esto, me gustaria que me expliquen el porque a esto, yo como humano no entiendo el porque a esta regla)

Desacoplamiento Absoluto: La lógica de red (Motor Sockets) debe estar 100% separada de la Interfaz Gráfica (UI). Si la UI falla o se quita, el nodo debe poder seguir operando desde la consola.

Seguridad Básica (Hardening): Cualquier ejecución remota de comandos debe estar validada contra una "Lista Blanca" estricta en el servidor. Nunca pasar strings crudos a una shell.

2. Stack Tecnológico Definido
Lenguaje Core: Python 3.11+ 

Motor de Red: socket, threading, queue, json, struct (Librerías estándar de Python).

Interfaz de Escritorio (Windows/Linux - Fedora): CustomTkinter (Recomendado por su facilidad de integración con hilos estándar de Python y aspecto moderno) o Flet.

Interfaz Mobile (Android/iOS): Frontend web creado con React + Tailwind CSS. Se compilará a estático (HTML/JS/CSS) y será servido localmente por un hilo daemon en Python usando http.server. El celular interactúa escaneando un código QR, sin necesidad de instalar un .apk.

3. Arquitectura del Sistema (P2P Híbrido)
SysNode no tiene un servidor central. Cada instancia ejecutada actúa como Cliente y Servidor simultáneamente.

Modelo de Hilos (Threading Model):
Main Thread (UI): Renderiza la interfaz gráfica y lee constantemente eventos de la queue.Queue provenientes de la red.

Thread 1 (UDP Broadcast): Emite un Heartbeat (latido) cada 3 segundos anunciando su existencia en la LAN.

Thread 2 (UDP Listener): Escucha permanentemente en el puerto UDP los latidos de otros nodos para mantener actualizada la lista de dispositivos activos. Remueve nodos que no envían latidos por más de 10 segundos (TTL).

Thread 3 (TCP Server): Escucha conexiones entrantes para recibir Archivos, Textos/Enlaces (Shared Board) o Comandos (Remote Exec).

Thread 4 (HTTP Web Server): Levanta un servidor web ligero (ej. puerto 8000) que sirve la carpeta estática de React para la interfaz del celular.

4. Especificación del Protocolo de Red
Todas las comunicaciones (excepto los datos binarios de archivos) utilizan payloads en formato JSON.

A. Protocolo de Descubrimiento (UDP - Puerto 50000)
Datagramas enviados mediante 255.255.255.255 (Broadcast).
{
  "type": "SYSNODE_ANNOUNCE",
  "node_id": "UUID-UNICO-DEL-NODO",
  "hostname": "fedora-jorcas",
  "os": "linux",
  "tcp_port": 50001
}
B. Protocolo de Datos (TCP - Puerto 50001)
Cuando un nodo se conecta a otro, el primer mensaje define la acción.

Caso 1: Enviar Texto (Shared Board)
{
  "action": "SHARE_TEXT",
  "payload": "https://github.com/..."
}
Caso 2: Ejecución Remota (Botonera SysAdmin)
{
  "action": "REMOTE_CMD",
  "command": "CMD_LOCK_SCREEN",
  "auth_token": "token-opcional-para-el-futuro"
}
Caso 3: Transferencia de Archivos (El desafío principal)

Fase 1 (Metadata): El emisor envía un JSON con los datos del archivo.
{
  "action": "FILE_TRANSFER_META",
  "filename": "documento.pdf",
  "filesize_bytes": 1048576,
  "hash_sha256": "opcional-para-integridad"
}
Fase 2 (ACK): El receptor responde con un string "ACK_READY".

Fase 3 (Streaming Binario): El emisor envía el archivo leyendo en fragmentos (Chunks) de 4096 bytes (4KB). El receptor recibe los chunks y los escribe en disco hasta alcanzar el filesize_bytes definido.

5. Módulos / Funcionalidades a Desarrollar
Módulo 1: Radar LAN. Descubrimiento dinámico de nodos. UI: Una lista visual de quién está conectado.

Módulo 2: Shared Board. Una sala de chat de un solo sentido para compartir portapapeles, texto y enlaces rápidamente entre la PC y el celular/otras PCs.

Módulo 3: File Drop. Transferencia de archivos pesados de punto a punto en la LAN. UI: Barra de progreso.

Módulo 4: Remote Shell / SysAdmin Actions. Botones para ejecutar scripts básicos (bloquear, apagar, alertar). Validación estricta por lista blanca.

Módulo 5: Mobile Web Gateway. Generación de código QR en la PC. El usuario lo escanea con la cámara del celular y accede a la interfaz React que controla al nodo PC.

6. Secuencia de Desarrollo MVP (Para la IA)
IA, por favor sigue estrictamente este orden de construcción. No pases al siguiente paso sin probar el anterior:

Fase 1 (Core Base): Crear la clase SysNodeCore en Python con los hilos UDP para descubrimiento. Probar ejecutando dos consolas en la misma PC (con distintos puertos).

Fase 2 (Conexión TCP): Implementar el servidor y cliente TCP para enviar JSON básicos (Shared Board y Comandos).

Fase 3 (Transferencia de Archivos): Implementar la lógica de envío/recepción de chunks binarios con control de tamaño.

Fase 4 (Desktop UI): Conectar SysNodeCore con una interfaz hecha en CustomTkinter.

Fase 5 (Mobile Web): Crear el mini servidor HTTP, la app en React y el generador de QR.


PARA MI:
1. Para defender la Red (El núcleo del examen)
El profesor te va a hacer preguntas trampa sobre cómo viajan los datos. Tenés que dominar esto para que no te agarre desprevenido.

El problema del "Framing" en TCP (Crucial):

Qué investigar: TCP es un protocolo orientado a flujos continuos (streams), no a mensajes. Si mandás un JSON y después un archivo binario, TCP los pega. El receptor no sabe dónde termina el JSON y dónde empieza la foto.

Qué leer: Buscá en Google o preguntale a la IA sobre "TCP Packet Framing" o "Message Boundary in TCP". La solución que vamos a usar es enviar el tamaño exacto del archivo (en bytes) justo antes de enviar el archivo.

Kurose - Redes de Computadoras (Tu libro):

Capítulo 2: Leé atentamente la sección de Arquitecturas P2P (Peer-to-Peer) y cómo se diferencia de Cliente-Servidor. Leé también la parte de Sockets UDP y TCP.

Capítulo 3: Leé Multiplexación y Demultiplexación. Es exactamente lo que hace tu sistema al tener varios puertos abiertos al mismo tiempo.

Beej's Guide to Network Programming:

Leé la Sección 5 (System Calls) y la Sección 7 (Advanced Techniques), específicamente la parte de enviar paquetes de datos completos (handling partial sends).

2. Para dominar el Motor de Python (Evitar cuelgues)
Cuando empieces a usar hilos, el programa se puede congelar o corromper datos si dos procesos intentan leer lo mismo.

Manejo seguro de Hilos y Colas:

Qué investigar: La librería threading (específicamente qué es un daemon thread y qué es un Lock o Mutex) y la librería queue.Queue de Python.

Por qué: La cola (Queue) es la única forma segura de pasar un archivo recibido desde el hilo de red (que está en segundo plano) a la interfaz gráfica sin que todo explote.

Manejo Binario (Librería struct):

Qué investigar: Cómo empacar enteros a bytes usando struct.pack.

Por qué: Para enviarle al receptor el tamaño exacto del archivo en un formato que la red entienda, antes de mandar los "chunks" (fragmentos) del archivo real.

3. Para el perfil de Ciberseguridad (Hardening)
Si vas a crear una aplicación que permite ejecutar comandos de forma remota en tu computadora, tenés que asegurarla, sino estás creando una vulnerabilidad gigante (un Backdoor).

Command Injection (Inyección de Comandos):

Qué investigar: Buscá qué es la vulnerabilidad CWE-77 (Command Injection) y cómo prevenirla en Python al usar el módulo subprocess.

La regla a aplicar: Jamás pases directamente por la terminal un string que te llegó por la red. Diseñá un diccionario estricto: Si por la red llega el string "CMD_LOCK", tu código de Python ejecuta la función local para bloquear la pantalla. Si llega "CMD_REBOOT", la rechaza. Esto demuestra mentalidad de Blue Team.

Validación de Rutas (Path Traversal):

Qué investigar: Cómo evitar que un usuario te envíe un archivo llamado ../../../etc/passwd y te sobrescriba un archivo crítico del sistema. Tu código debe limpiar siempre el nombre del archivo recibido (os.path.basename).

4. Para la Integración Web (El Celular)
Dado que usaremos React para la interfaz móvil y Python para el motor, necesitamos que hablen entre sí.

API REST vs. Long Polling:

Qué investigar: Cómo levantar un servidor web básico con el módulo nativo http.server de Python que, además de servir el HTML/JS estático de React, pueda recibir peticiones GET o POST desde el celular (ej. el celular hace un POST a la PC diciendo "enviá este texto al profesor").

Nota: No uses WebSockets para la comunicación entre el celular y tu PC por ahora; mantenelo simple con HTTP REST local. Los sockets puros guardalos para la comunicación de PC a PC en la red LAN.

Tu misión para los próximos 2 días
Lee el concepto de Framing en TCP.

Repasa el Capítulo 2 de Kurose.

Entiende cómo funciona queue.Queue() en Python.
