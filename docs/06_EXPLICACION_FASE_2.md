# SysNode - Explicación Detallada y Pedagógica de la Fase 2

Este documento explica de forma clara y didáctica todo lo desarrollado en la **Fase 2 (Conexión TCP, Framing de Mensajes, Shared Board y Comandos SysAdmin)**. Te ayudará a entender exactamente cómo viajan los datos sobre TCP a bajo nivel y cómo defender estos conceptos ante el profesor de redes.

---

## 1. El Problema del TCP Framing (Crucial para el Examen)

### El problema: TCP no preserva límites de mensajes (*Byte Stream*)
A diferencia de UDP (donde cada llamada a `sendto()` envía un datagrama independiente), **TCP es un protocolo basado en un flujo continuo de bytes (*Byte Stream*)**.

Si tu programa envía dos mensajes JSON seguidos por la red:
```json
{"action": "SHARE_TEXT", "payload": "Hola"}
{"action": "REMOTE_CMD", "command": "CMD_PING"}
```
El sistema operativo (kernel) puede juntar ambos paquetes en el mismo buffer de salida para optimizar el tráfico de red (Algoritmo de Nagle). El receptor, al hacer un `recv(1024)`, podría recibir los dos JSON pegados en un solo string:
`{"action": "SHARE_TEXT"...}{"action": "REMOTE_CMD"...}`.
Esto rompe el parser de JSON (`json.JSONDecodeError`).

---

### La Solución: Protocolo con Header de Longitud Fija (Length-Prefixed Framing)

Para solucionar esto, en `src/network/framing.py` implementamos un encabezado binario de **4 bytes fija** en orden de red **Big-Endian** (`struct.pack('>I', payload_length)`).

#### Estructura de la Trama TCP en SysNode:
```
+-----------------------------------+---------------------------------------+
|  Header de Tamaño (4 bytes)       |  Cuerpo del Mensaje UTF-8 (L bytes)   |
|   struct.pack('>I', L)            |     {"action": "SHARE_TEXT", ...}     |
+-----------------------------------+---------------------------------------+
```

#### ¿Cómo lee el receptor?
1. Hace una lectura exacta de los primeros **4 bytes** usando `recv(4)`.
2. Convierte esos 4 bytes a un entero usando `struct.unpack('>I', header)[0]`. Eso le da la longitud exacta `L` del mensaje.
3. Entra en un bucle que realiza lecturas continuas con `recv()` hasta acumular exactamente `L` bytes.
4. Recién ahí convierte los bytes a JSON. De esta forma, **nunca se leen bytes de más ni mensajes pegados**.

---

## 2. El Modelo de Servidor TCP Multihilo

Para la recepción TCP implementamos el patrón de servidor concurrente clásico:

```
[Main Thread / CLI]
        |
[TCPServer Thread] (Escucha en puerto TCP 50001, bloqueado en accept())
        |
        +-- (Conexión Cliente A) --> Spawns [TCPClientHandlerThread A]
        +-- (Conexión Cliente B) --> Spawns [TCPClientHandlerThread B]
```

1. **`TCPServerThread`:** Hilo secundario en bucle con `server_sock.accept()`. Cuando un nodo remoto se conecta, acepta la conexión y crea un nuevo hilo dedicado.
2. **`TCPClientHandlerThread`:** Hilo de vida corta que atiende exclusivamente esa conexión, lee la trama con framing, procesa la acción y responde un mensaje de confirmación (ACK) antes de cerrar el socket.

---

## 3. Hardening y Seguridad (Ciberseguridad - Blue Team)

Para prevenir la vulnerabilidad **Command Injection (CWE-77)**, implementamos la lista blanca en `src/core/security.py`.

* **Regla estricta:** Ningún texto enviado desde la red se pasa a una shell de comandos (`shell=False` obligatorio).
* **Mapeo por Tokens:** La red envía únicamente una clave (ej. `"CMD_LOCK_SCREEN"` o `"CMD_PING"`).
* **Compatibilidad Cross-Platform:**
  * En **Windows:** Llama a la API nativa del sistema operativo `ctypes.windll.user32.LockWorkStation()`.
  * En **Linux:** Ejecuta de forma segura `xdg-screensaver lock`.

Si alguien intenta enviar un comando no registrado (ej. `"CMD_MALICIOUS"`), el servidor rechaza la solicitud al instante devolviendo `"ACCESO DENEGADO"`.

---

## 4. Desglose del Código Creado en la Fase 2

* **[src/network/framing.py](file:///home/jorcas/Documentos/2025-2doCuatrimestre/Sockets/codigo/SysNode/src/network/framing.py):** Contiene `send_framed_message()` y `receive_framed_message()`. Maneja la conversión binaria con `struct`.
* **[src/core/security.py](file:///home/jorcas/Documentos/2025-2doCuatrimestre/Sockets/codigo/SysNode/src/core/security.py):** Define `COMMAND_WHITELIST` y la función `execute_whitelisted_command()`.
* **[src/network/tcp_server.py](file:///home/jorcas/Documentos/2025-2doCuatrimestre/Sockets/codigo/SysNode/src/network/tcp_server.py):** Servidor TCP concurrente y manejador de trabajadores.
* **[src/network/tcp_client.py](file:///home/jorcas/Documentos/2025-2doCuatrimestre/Sockets/codigo/SysNode/src/network/tcp_client.py):** Cliente TCP para realizar peticiones salientes síncronas.
* **[src/core/sysnode_core.py](file:///home/jorcas/Documentos/2025-2doCuatrimestre/Sockets/codigo/SysNode/src/core/sysnode_core.py):** Métodos de alto nivel `send_text_to_peer()` y `send_command_to_peer()`.
* **[src/ui/cli.py](file:///home/jorcas/Documentos/2025-2doCuatrimestre/Sockets/codigo/SysNode/src/ui/cli.py):** Menú interactivo con tablero de mensajes recibidos (Shared Board) y selección de comandos remotos.

---

## 🎯 Preguntas Clave para el Profesor de Redes

Si el profesor te pregunta: **"¿Cómo resolviste la entrega de mensajes sobre TCP?"**

> *"Profesor, como TCP es un protocolo orientado a flujos continuos de bytes (byte stream) y no preserva los límites de los mensajes, diseñamos un protocolo de aplicación con header de longitud fija. Cada mensaje TCP comienza con 4 bytes binarios en formato Big-Endian (unsigned int) codificados con la librería `struct`. El servidor realiza una lectura previa de 4 bytes con `recv(4)`, calcula el tamaño exacto `L` del payload JSON y luego realiza lecturas iterativas en bucle acumulando exactamente `L` bytes antes de decodificar. Esto garantiza que las tramas nunca se fragmenten ni se mezclen en el búfer."*
