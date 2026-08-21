# SysNode - Reglas y Normas del Proyecto

Este documento establece las reglas estrictas de desarrollo y el marco normativo que cualquier agente de IA o desarrollador humano **debe cumplir sin excepción** al contribuir al proyecto SysNode.

---

## 1. Reglas de Oro Técnicas

### 1.1 Cero Abstracciones en Redes
* **Prohibido:** Usar librerías de alto nivel como `requests`, `urllib3`, `aiohttp`, `twisted` o frameworks de WebSockets para la comunicación P2P del motor de red.
* **Permitido exclusivamente:** El módulo nativo `socket` de la librería estándar de Python (`import socket`).
* **Objetivo pedagógico:** Demostrar dominio de llamadas al sistema operativo (`socket()`, `bind()`, `listen()`, `accept()`, `send()`, `recv()`, `setsockopt()`).

---

### 1.2 Concurrencia Clásica mediante `threading` y `queue.Queue`
* **Prohibido:** Usar `asyncio`, `twisted` o `gevent`.
* **Permitido exclusivamente:** `threading.Thread` para la ejecución concurrente y `queue.Queue` para el intercambio thread-safe de mensajes entre hilos de red y la interfaz de usuario (UI).

<a id="por-qué-threading-y-no-asyncio-explicación-pedagógica"></a>
#### Explicación Pedagógica: ¿Por qué `threading` y no `asyncio`?
> *Inquietud expresada por el usuario en [SYSNODE Architecture.md](file:///home/jorcas/Documentos/2025-2doCuatrimestre/Sockets/codigo/SysNode/SYSNODE%20Architecture.md#L10).*

1. **Mapeo directo con los conceptos del Modelo OSI y Sistemas Operativos:**
   En una materia de Redes (basada en Kurose & Ross), los sockets se enseñan como los puntos finales (*endpoints*) de un canal IPC/Red administrados por el Kernel mediante descriptores de archivo. `threading` mapea 1-a-1 esta mentalidad:
   * **Hilo 1:** Bloqueado en `recvfrom()` esperando un datagrama UDP.
   * **Hilo 2:** Bloqueado en `accept()` esperando una llamada entrante TCP.
   * **Hilo 3:** Bloqueado en `recv()` leyendo bytes de un flujo de archivo TCP.
   Cada hilo tiene un flujo de control síncrono e intuitivo que evidencia exactamente dónde la llamada al sistema se bloquea esperando física o lógicamente a la red.
2. **Abstracción Oculta de `asyncio`:**
   `asyncio` abstrae este comportamiento usando un **Event Loop** basado en `select()`, `poll()` o `epoll()`, junto con corrutinas y la sintaxis `async/await`. Aunque es altamente escalable para miles de conexiones concurrentes en producción, para los fines de un examen final universitario de Redes **oculta la mecánica interna del socket**, ya que la entrada/salida no bloqueante y los callbacks son manejados de forma transparente por la biblioteca.
3. **Seguridad en la UI:**
   Las bibliotecas de UI (como CustomTkinter/Tkinter) no soportan llamadas desde hilos secundarios. La combinación `threading` + `queue.Queue` demuestra cómo desacoplar de forma profesional un motor de red de segundo plano de la UI del hilo principal mediante el patrón *Producer-Consumer*.

---

### 1.3 Desacoplamiento Absoluto (Core vs UI)
* La clase `SysNodeCore` debe ser totalmente independiente de CustomTkinter o React.
* El núcleo debe ser ejecutable y operable al 100% desde la terminal de comandos (Modo Headless / CLI).
* Si la UI gráfica falla o se cierra, el nodo de red debe continuar funcionando en segundo plano sin lanzar excepciones no capturadas.

---

### 1.4 Hardening y Seguridad (Ciberseguridad)
* **Lista Blanca Obligatoria:** Ningún string entrante desde la red se enviará a una consola de comandos (`os.system` o `subprocess` con `shell=True` está **estrictamente prohibido**).
* **Sanitización de Archivos:** Todo nombre de archivo entrante debe limpiarse mediante `os.path.basename()` para prevenir ataques de **Path Traversal** (`../../../etc/passwd`).

---

## 3. Portabilidad Multiplataforma y Preparación para GitHub (Open Source)

SysNode está diseñado para ser un proyecto público de portafolio en GitHub y debe ser 100% portable para ejecutarse tanto en **Linux (Fedora/Ubuntu)** como en **Windows 10/11** sin requerir modificaciones en el código.

### 3.1 Detección de IP Confiable en Redes Universitarias
* **Problema:** `socket.gethostbyname(socket.gethostname())` en Linux devuelve frecuentemente `127.0.0.1` debido a la configuración de `/etc/hosts`.
* **Solución Estándar:** Usar la función de detección activa mediante un socket UDP temporal:
  ```python
  def get_local_lan_ip() -> str:
      s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
      try:
          # No envía paquetes reales a la red externa, sólo determina la interfaz activa
          s.connect(("8.8.8.8", 80))
          ip = s.getsockname()[0]
      except Exception:
          ip = "127.0.0.1"
      finally:
          s.close()
      return ip
  ```

### 3.2 Plan de Contingencia para Wi-Fi Universitario (AP Isolation)
* **El Peligro en la Universidad:** Muchas redes Wi-Fi universitarias o públicas tienen activado **AP Isolation (Aislamiento de Punto de Acceso)** o filtran el tráfico UDP Broadcast (`255.255.255.255`).
* **Regla de Diseño:** El Radar LAN usará UDP Broadcast como método principal, **pero se implementará una opción de Conexión Directa por IP/QR (Fallback)** en la UI/CLI. Si el broadcast es bloqueado por el router de la facultad, el estudiante podrá ingresar manualmente la IP del otro dispositivo (ej. `192.168.1.45`) o escanear el QR y conectarse por TCP al instante. **Esto garantiza que la presentación en vivo sea un éxito garantizado.**

### 3.3 Comandos Nativos Multiplataforma
Las funciones del sistema usarán condicionales explícitos `sys.platform` utilizando APIs nativas:
* **Bloqueo en Windows:** `ctypes.windll.user32.LockWorkStation()` (sin requerir ejecutables externos).
* **Bloqueo en Linux:** `subprocess.Popen(["xdg-screensaver", "lock"])`.

---

## 4. Guía para Agentes de IA (Anti-Código Basura)

Para mantener la elegancia, mantenibilidad y legibilidad del código:

1. **Módulos Concretos y Concisos:** Evitar archivos de más de 300 líneas. Separar responsabilidades en archivos legibles (`udp_beacon.py`, `tcp_server.py`, `file_transfer.py`, `core.py`).
2. **Sin Código Muerto ni Placeholders Impracticables:** No agregar funciones vacías o comentarios `TODO` sin implementación. Todo código añadido debe ser funcional y estar probado.
3. **Manejo Explicito de Excepciones:** No usar `except Exception: pass`. Capturar específicamente `socket.error`, `socket.timeout`, `ConnectionResetError` y registrar el evento adecuadamente en los logs.
4. **Comentarios Orientados a Redes:** Explicar el *por qué* de las opciones de sockets (`SO_REUSEADDR`, `TCP_NODELAY`, buffers), no lo trivial.

