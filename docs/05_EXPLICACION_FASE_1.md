# SysNode - Explicación Detallada y Pedagógica de la Fase 1

Este documento explica de forma clara, didáctica y conceptual todo lo desarrollado en la **Fase 1 (Core Base: Descubrimiento UDP y Radar LAN)**. Está diseñado para ayudarte a comprender a fondo qué hace cada línea de código y dominar la teoría ante las preguntas del profesor de redes.

---

## 1. El Problema que Resuelve la Fase 1

En una arquitectura **Cliente-Servidor tradicional** (como una página web normal), hay un servidor central con una dirección IP fija conocida por todos. En una **Red P2P (Peer-to-Peer) Híbrida** como SysNode, **no hay un servidor central**.

Cuando abrís SysNode en tu notebook, ¿cómo sabe tu computadora qué otros dispositivos (PCs, notebooks, celulares) están conectados en la misma red Wi-Fi/LAN sin que tengas que escribir sus direcciones IP manualmente?

**La respuesta es el Descubrimiento Automático por UDP Broadcast (Radar LAN).**

---

## 2. Conceptos de Sockets y Redes Utilizados

### A. ¿Por qué usamos UDP y no TCP para el descubrimiento?
* **UDP (`socket.SOCK_DGRAM`):** Es un protocolo sin conexión y ligero. Permite enviar un paquete a una dirección especial llamada **Broadcast (`255.255.255.255`)**. Todos los dispositivos conectados al mismo switch o router Wi-Fi reciben ese paquete automáticamente. Comentario: claro recuerdo entender esto del broadcast que lo use para un proyecto en el cual se hacia una deteccion de dispositivos en la red, enviando paquete arp para que detecte cuales respondian y les pedia su informacion(ip y mac) pero creo que solia pasar que aveces habian dispositivos conectados a la red pero que no respondian por ejemplo un celular que se encuentra con la pantalla bloqueada, esto me generaba dudas porque en el celular si me llega un whatsapp si me llega la notificacion, como esque en un caso si recibe señales y en otra no. Cuestion que esta forma que se implemento es para que los dispositivos se detecten entre si ya que todos son clientes y servidores a la vez que no? Que nos asegura de que detecte correctamente a todos?
* **TCP:** Requiere establecer una conexión punto a punto previa (*3-Way Handshake: SYN, SYN-ACK, ACK*). TCP no permite enviar mensajes a "todos" a la vez.

### B. ¿Qué es `SO_REUSEADDR` y `SO_REUSEPORT`?
Normalmente, el sistema operativo prohíbe que dos programas escuchen en el mismo puerto al mismo tiempo (lanza el error `Address already in use`).
Para poder probar dos o más consolas de SysNode en la misma computadora (para desarrollo o pruebas), le indicamos al Kernel del sistema operativo mediante `setsockopt` que permita **compartir el puerto UDP 50000** entre múltiples procesos.
Comentario: que hace la funcion setsockopt? el so_reuseaddr y port si lo entendi
### C. El Modelo de Hilos y Concurrencia
SysNode utiliza 3 hilos de ejecución en esta fase:

```
[Main Thread] ----------> Ejecuta la CLI / UI (no se congela al esperar la red)
   |
   +--> [UDP Beacon Thread] ----> Emite un paquete JSON cada 3 segundos (Broadcast)
   +--> [UDP Listener Thread] --> Escucha en el puerto 50000 y limpia nodos inactivos
```

1. **`MainThread`:** Controla la interfaz de usuario. Si pusiéramos la red a escuchar aquí, la pantalla se congelaría esperando paquetes.
2. **`UDPBeaconThread` (Productor):** Hilo secundario que late periódicamente informando la existencia del nodo.
3. **`UDPListenerThread` (Consumidor):** Hilo secundario que escucha paquetes de otros nodos y actualiza el mapa en memoria de dispositivos activos.
comentario general: que se puedan ejecutar 3 hilos es porque mi pc tiene esa capacidad o porque? que pasa si una pc no tiene esa capaciada?
comentario 2: que significa beacon? a que se le llama nodo? yo estudie estructura de datos y algoritmos y se que es un nodo pero en un sistema operativo no lo entiendo, mejor dicho en este conexto no entiendo como funciona por debajo la pc realmente.

---

## 3. Explicación Código por Código (Archivos en `src/`)

### 🛠️ 1. `src/config.py` - Constantes del Protocolo
[Ver archivo `src/config.py`](file:///home/jorcas/Documentos/2025-2doCuatrimestre/Sockets/codigo/SysNode/src/config.py)

Este archivo centraliza los parámetros de red para no tener números mágicos sueltos en el código:
* `UDP_DISCOVERY_PORT = 50000`: El puerto de transporte acordado para el Radar LAN.
* `BEACON_INTERVAL_SEC = 3.0`: Cada cuántos segundos nuestro nodo emite un latido.
* `PEER_TTL_SEC = 10.0`: **Time To Live (Tiempo de Vida).** Si un nodo no envía un latido por más de 10 segundos, se asume que se desconectó o apagó y se elimina de la lista.
Comentario: que pasa si quiero que este sistema se utilize como en segundo plano por si decir, es decir no lo voy a necesitar en todo momento pero me sirve tenerlo abierto en segundo plano y cuando necesito pasar un archivo o usar sus funcionalidades, podria simplemente abrirlo e interactuar con los dispositivos que esten en la misma situacion? supongamos que estoy trabajando en la pc y necesito pasarme un link del celular a la pc y como no quiero utilizar wppweb utilizo esta app entonces lo copio en mi celular y busco abrir la app para dejarlo pegado asi desde la pc abro la app y copio, esto se puede hacer sin problema o siempre tendre que prender el servidor compartir el qr y que recien el celular pase? como funcionaria en la practicidad del dia a dia esto?
---

### 🌐 2. `src/network/utils.py` - Detección de IP y Opciones de Socket
[Ver archivo `src/network/utils.py`](file:///home/jorcas/Documentos/2025-2doCuatrimestre/Sockets/codigo/SysNode/src/network/utils.py)

#### ¿Cómo detectamos la IP real en la LAN?
En Linux (Fedora/Ubuntu), la función nativa `socket.gethostbyname()` suele devolver `127.0.0.1` porque el archivo `/etc/hosts` asocia el nombre de la máquina con la interfaz local de loopback.

Para solucionar esto, creamos la función `get_local_lan_ip()`:
```python
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.connect(("8.8.8.8", 80))
ip = s.getsockname()[0]
```
* **¿Qué hace esto?** Abre un socket UDP hacia una IP externa (Google DNS `8.8.8.8`). No llega a enviar ningún paquete real por internet; simplemente obliga al sistema operativo a determinar cuál de sus placas de red (Wi-Fi o Ethernet) tiene la ruta de salida. Luego consultamos `getsockname()[0]` para obtener la dirección IP real asignada en la LAN (ej. `192.168.0.10`).

---

### 📡 3. `src/network/udp_beacon.py` - El Emisor de Latidos (Beacon)
[Ver archivo `src/network/udp_beacon.py`](file:///home/jorcas/Documentos/2025-2doCuatrimestre/Sockets/codigo/SysNode/src/network/udp_beacon.py)

Es una clase que hereda de `threading.Thread`:

```python
class UDPBeacon(threading.Thread):
```

#### Paso a Paso de su funcionamiento:
1. **Creación del Socket:**
   ```python
   sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
   sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
   ```
   * `AF_INET`: Dominio IPv4.
   * `SOCK_DGRAM`: Protocolo UDP por datagramas.
   * `SO_BROADCAST`: Activa la opción especial en la placa de red para permitir enviar paquetes a direcciones de difusión (`255.255.255.255`).

2. **Bucle de Emisión:**
   Dentro del método `run()`, emite un mensaje en formato **JSON** codificado en bytes (`utf-8`):
   ```json
   {
     "type": "SYSNODE_ANNOUNCE",
     "node_id": "50a40200-4cf5-4b24-8552-c0bcaf0216f4",
     "hostname": "FedoraPC",
     "os": "linux",
     "tcp_port": 50001,
     "timestamp": 1724241600.5
   }
   ```
3. **Llamada al Sistema `sendto()`:**
   ```python
   sock.sendto(data, ("255.255.255.255", 50000))
   ```
   Envía el datagrama UDP a toda la subred local y luego duerme 3 segundos (`BEACON_INTERVAL_SEC`).

---

### 👂 4. `src/network/udp_listener.py` - El Receptor y Gestor del Radar
[Ver archivo `src/network/udp_listener.py`](file:///home/jorcas/Documentos/2025-2doCuatrimestre/Sockets/codigo/SysNode/src/network/udp_listener.py)

Este hilo se encarga de escuchar los paquetes que otros nodos emiten y mantener la lista de dispositivos vivos.

#### Paso a Paso de su funcionamiento:
1. **Binding (Vincularse al Puerto):**
   ```python
   sock.bind(("0.0.0.0", 50000))
   ```
   `0.0.0.0` significa *"escuchar en todas las interfaces de red disponibles en esta máquina"*.

2. **Recepción con `recvfrom()`:**
   ```python
   data, addr = sock.recvfrom(4096)
   peer_ip = addr[0]
   ```
   El método `recvfrom()` se bloquea a la espera de que llegue un datagrama UDP. Devuelve tanto los bytes del mensaje (`data`) como la tupla de origen `(IP_origen, Puerto_origen)`.

3. **Filtro de Auto-Identificación:**
   Cuando recibe un mensaje, compara el `node_id` del JSON con su propio `my_node_id`. Si es su propio paquete broadcast (que dio la vuelta en la red y volvió), lo ignora.

4. **Diccionario de Nodos y Control de Concurrencia (`threading.Lock`):**
   Mantiene el diccionario `active_peers`. Como dos hilos podrían intentar leer o modificar este diccionario al mismo tiempo, se utiliza un cerrojo (Mutex) mediante `with self.peers_lock:` para evitar corrupción de memoria (*Race Conditions*).

5. **Expiración por TTL (Time To Live Cleanup):**
   Cada 1 segundo, el listener revisa todos los nodos guardados. Si la diferencia entre la hora actual (`time.time()`) y la última vez que vimos al nodo (`last_seen`) es **mayor a 10 segundos**, lo elimina del diccionario y notifica la desconexión.

---

### 🧠 5. `src/core/sysnode_core.py` - El Orquestador Principal
[Ver archivo `src/core/sysnode_core.py`](file:///home/jorcas/Documentos/2025-2doCuatrimestre/Sockets/codigo/SysNode/src/core/sysnode_core.py)

Es el "cerebro" que une todo:
* Genera un identificador único universal (UUID v4) para el nodo con `uuid.uuid4()`.
* Inicializa el `UDPBeacon` y el `UDPListener`.
* Contiene la cola de eventos thread-safe `queue.Queue()`.
* Expone los métodos `start()` y `stop()` para encender y apagar todos los hilos de red de forma limpia al presionar `Ctrl+C`.

---

### 🖥️ 6. `src/ui/cli.py` y `main.py` - La Interfaz y Punto de Entrada
[Ver archivo `src/ui/cli.py`](file:///home/jorcas/Documentos/2025-2doCuatrimestre/Sockets/codigo/SysNode/src/ui/cli.py) | [Ver archivo `main.py`](file:///home/jorcas/Documentos/2025-2doCuatrimestre/Sockets/codigo/SysNode/main.py)

* **`main.py`:** Parsea los argumentos enviados por la terminal (`--name`, `--tcp-port`), configura el sistema de logs y arranca el programa.
* **`cli.py`:** Contiene el bucle visual. Cada 1 segundo limpia la pantalla (`clear` o `cls`) y consulta a `SysNodeCore.get_active_peers()`, imprimiendo la tabla formateada con los nodos activos en el Radar LAN.

---

## 🎯 Resumen para la Defensa Oral ante el Profesor

 Si el profesor te pregunta: **"¿Cómo funciona el descubrimiento en tu sistema?"**

> *"Profesor, implementamos un protocolo de descubrimiento dinámico de capa de aplicación sobre UDP. Cada nodo ejecuta un hilo emisor (Beacon) que envía un datagrama JSON en Broadcast a la dirección 255.255.255.255 en el puerto 50000 cada 3 segundos. Simultáneamente, un hilo receptor (Listener) escucha en el puerto 50000 y mantiene una tabla de pares activos en memoria. Para manejar las desconexiones abruptas, implementamos un temporizador TTL de 10 segundos: si un nodo deja de emitir latidos por más de 10 segundos, el hilo Listener lo remueve automáticamente del Radar LAN."*
