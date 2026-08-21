# SysNode - Guía de Defensa para el Examen de Redes

Este documento está diseñado específicamente para preparar la **presentación oral y defensa técnica** ante el profesor de la materia Redes de Computadoras. 

> **Nota Clave:** El profesor evalúa **conceptos de redes, protocolos y comportamiento de sockets a bajo nivel**, no la sintaxis del código de programación. La demo debe enfocar la atención en cómo viajan los datos en la red, la gestión del socket y la arquitectura P2P.

---

## 1. Mapeo de Conceptos Teóricos (Libro Kurose & Ross) aplicados en SysNode

| Concepto Teórico (Kurose) | Capítulo / Sección | Implementación Práctica en SysNode |
| :--- | :--- | :--- |
| **Arquitectura P2P vs. Cliente-Servidor** | Cap. 2.1 | Cada nodo ejecuta simultáneamente un Servidor TCP/UDP y actúa como Cliente al iniciar transferencias o emitir beacones. |
| **Multiplexación y Demultiplexación** | Cap. 3.2 | SysNode utiliza múltiples puertos de transporte simultáneos (`50000 UDP`, `50001 TCP`, `8000 HTTP`) en la misma dirección IP. El kernel demultiplexa los segmentos entrantes según la tupla `(IP Origen, Puerto Origen, IP Destino, Puerto Destino)`. |
| **Datagramas UDP sin Conexión** | Cap. 3.3 | Utilizado en el Radar LAN (`50000 UDP Broadcast`). No requiere handshake (`SYN-ACK`), es ligero y permite descubrir pares sin conocer sus direcciones IP previamente. |
| **Flujo Continuo TCP (Byte Stream) y Framing** | Cap. 3.5 | Solución al problema de falta de límites de mensaje en TCP mediante **Length-Prefixed Framing** (`struct.pack('>I', size)`). |
| **Llamadas al Sistema de Sockets (Beej's Guide)** | Sección 5 | Uso explícito de `socket()`, `bind()`, `listen()`, `accept()`, `connect()`, `send()`, `recv()`, `sendto()`, `recvfrom()`. |

---

## 2. Preguntas Probables del Profesor y Respuestas Estratégicas

### Pregunta 1: "¿Por qué usaste UDP para el descubrimiento y TCP para los archivos y comandos?"
* **Respuesta Esperada:**
  * **UDP:** Para el descubrimiento necesitamos un mecanismo de *difusión* (Broadcast) a toda la subred (`255.255.255.255`). TCP es estrictamente punto a punto y requiere un 3-Way Handshake previo, por lo que no permite Broadcast ni Multicast. Si se pierde un paquete de latido (Heartbeat UDP), no importa, el siguiente llegará en 3 segundos.
  * **TCP:** Para transferir archivos y ejecutar comandos necesitamos **entrega confiable y ordenada** de datos (Garantías de orden, control de flujo mediante ventana deslizante y retransmisión por pérdidas). Un solo byte corrupto en un ejecutable o archivo binario inutilizaría el archivo.

---

### Pregunta 2: "¿Cómo resolvieron el problema de delimitar los mensajes sobre el stream de TCP?"
* **Respuesta Esperada:**
  * TCP entrega bytes en un flujo continuo sin frontera de datagrama. Si enviamos un JSON de metadatos y luego el contenido de un archivo, el buffer del receptor podría leer ambos juntos.
  * Lo resolvimos implementando un protocolo de capa de aplicación con **Header de Tamaño Fijo (Length-Prefixed Protocol)**. Precedemos cada mensaje con 4 bytes binarios en orden de red (Big-Endian) que indican la longitud exactamente en bytes del payload. El servidor lee primero 4 bytes con `recv(4)`, calcula el tamaño `L`, e invoca `recv()` repetidamente hasta acumular los `L` bytes exactos.

---

### Pregunta 3: "¿Qué sucede con los recursos de red cuando un nodo se desconecta abruptamente (Power off)?"
* **Respuesta Esperada:**
  * En **UDP**, el receptor mantiene un temporizador por nodo (*Time To Live - TTL*). Si no se recibe un datagrama `SYSNODE_ANNOUNCE` en un lapso de 10 segundos, el hilo UDP Listener remueve al nodo de la lista activa.
  * En **TCP**, las conexiones activas detectarán la desconexión abrupta cuando la llamada `recv()` devuelva 0 bytes (cierre limpio `FIN`) o lance la excepción `ConnectionResetError` (paquete `RST`). En ese punto, el hilo worker cierra el socket con `sock.close()` para no dejar descriptores de archivo (*file descriptors*) colgados.

---

### Pregunta 4: "¿Por qué no usaron asyncio y optaron por hilos (threading) con colas (Queue)?"
* **Respuesta Esperada:**
  * Para reflejar fielmente las operaciones bloqueantes de entrada/salida de la capa de transporte del SO. Cada hilo maneja un socket bloqueante específico (`accept()` o `recv()`), permitiendo observar de forma explícita cómo el Kernel suspende la ejecución del hilo hasta que la placa de red interrumpe al sistema operativo con nuevos bytes en el buffer de recepción.
  * Para comunicar los hilos de red con el hilo de la UI, utilizamos el patrón *Producer-Consumer* con `queue.Queue` que es thread-safe.

---

## 3. Script para la Demostración en Vivo (Demo Day)

1. **Escenario Inicial (Radar LAN):**
   * Abrir dos terminales / instancias de SysNode en la máquina del profesor/alumno (o entre la laptop y otra PC en la LAN).
   * Mostrar cómo el **Radar LAN** detecta automáticamente la presencia de la segunda máquina sin configurar IPs manualmente (Gracia a UDP Broadcast).

2. **Demostración de Transferencia Confiable (File Drop):**
   * Enviar un archivo grande (ej. 100 MB).
   * Mostrar el avance en la barra de progreso y abrir Wireshark si el profesor lo solicita para observar los segmentos TCP intercambiados.
   * Verificar la firma SHA-256 en el receptor.

4. **Plan de Contingencia ante Restricciones de Red Universitaria (AP Isolation):**
   * Explicar al profesor: *"Si el router Wi-Fi de la universidad tiene activado el aislamiento de AP (que bloquea los datagramas UDP Broadcast `255.255.255.255`), SysNode incluye una función de Fallback por Conexión Directa TCP mediante ingreso de IP o escaneo de código QR."*
   * Esto demuestra prevención de fallas de infraestructura en sistemas distribuidos.

5. **Portabilidad Multiplataforma (Windows y Linux):**
   - El código es ejecutable mediante `git clone` y `python main.py` en cualquier laptop Windows o máquina Linux de la facultad sin requerir recompilar ni cambiar la sintaxis de sockets.

