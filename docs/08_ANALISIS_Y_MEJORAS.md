# SysNode — Análisis Técnico y Hoja de Ruta de Mejoras

> Documento de análisis independiente (revisión de código + documentación).
> Fecha: 2026-08-29. Alcance: carpeta `SysNode/` (motor Python, UI de escritorio, CLI, app móvil RN).
>
> **Principio rector de este análisis:** SysNode es, ante todo, un proyecto pedagógico de **sockets crudos** para la materia de Redes. Ninguna recomendación de aquí propone reemplazar el motor `socket` + `threading` + `struct` por abstracciones de alto nivel (eso rompería el objetivo académico y las [reglas](00_REGLAS_Y_NORMAS.md)). El foco es: **corregir lo que está roto, endurecer lo justo, y dejar la base lista para mantener y usar a diario a largo plazo** sin sacrificar eficiencia ni claridad.

---

## 0. Veredicto rápido

El proyecto está **sorprendentemente bien estructurado** para su categoría: separación limpia núcleo/UI, framing correcto de longitud-prefijo, descubrimiento UDP con TTL, transferencia binaria con verificación SHA-256 y archivos `.tmp`, lista blanca de comandos sin `shell=True`, y hasta una app móvil nativa que habla el mismo protocolo. La documentación es de nivel poco común en trabajos de materia.

Dicho eso, hay **una regresión que rompe el modo CLI y un test**, varias asperezas de robustez, un requisito documentado que nunca se implementó (conexión directa por IP/QR), y trabajo de higiene de repositorio pendiente. Nada de esto es estructural: son mejoras incrementales sobre una base sólida.

**Prioridad máxima → §1 (bug del broker de eventos) y §7.1 (2.8 GB de artefactos de build sin ignorar).**

---

## 1. 🔴 Bugs y correcciones urgentes

### 1.1 Regresión: `core.event_queue` ya no existe (rompe CLI y un test)
El núcleo migró de una única cola a un **broker multi-suscriptor** (`register_event_queue()` / `event_queues`), pero dos consumidores quedaron sin migrar y siguen accediendo al atributo viejo `event_queue`, que **ya no existe**. Verificado en runtime: `hasattr(core, "event_queue") == False`.

- `src/ui/cli.py:46` → `self.core.event_queue.get(...)` lanza `AttributeError`. **El modo `--cli` crashea apenas llega el primer evento** (o nunca procesa nada).
- `tests/test_tcp_framing.py:45-46` → `node2.event_queue` hace **fallar el test de integración de la Fase 2**.

**Fix:** en la CLI, registrar una cola propia en `__init__` y consumirla:
```python
# src/ui/cli.py  (SysNodeCLI.__init__)
self.event_queue = self.core.register_event_queue()
# ... y en _process_events_loop:
event = self.event_queue.get(timeout=0.5)
```
En el test, reemplazar `node2.event_queue` por una cola registrada antes de enviar (`q = node2.register_event_queue()` y drenar `q`).

> La UI de escritorio ya usa `register_event_queue()` correctamente (`desktop_app.py:27`); solo quedaron atrás la CLI y el test.

### 1.2 La CLI no muestra progreso ni recepción de archivos
Aun arreglando 1.1, `_process_events_loop` no maneja `FILE_PROGRESS` (sí lo hace la GUI). Al recibir un archivo por CLI no se ve avance. Menor, pero conviene manejar el evento o al menos loguearlo.

### 1.3 `sanitize_filename` puede mutilar nombres legítimos
`security.py` hace `clean_name.replace("..", "")` **global**, no solo al inicio. Un archivo legítimo `informe..final.pdf` se convierte en `informefinal.pdf`. Como `os.path.basename()` ya neutraliza el path traversal, el `replace("..","")` y los `replace("/"/"\\")` posteriores son redundantes y dañinos. Sugerido: quedarse con `os.path.basename()` + filtrado de caracteres de control, y rechazar (no “limpiar”) nombres vacíos o reservados.

### 1.4 Recepción de archivos sin límite de tamaño ni consentimiento
`file_transfer.receive_file_bytes` confía en el `filesize_bytes` declarado por el emisor y escribe hasta completarlo, sobrescribiendo cualquier archivo homónimo en `SysNode_Received/` sin preguntar. Riesgos: llenado de disco y sobrescritura silenciosa. Recomendado: tope configurable (`MAX_FILE_SIZE`), y en la UI un diálogo *aceptar/rechazar* antes del ACK `READY` (ver §4.2).

### 1.5 Deriva documentación ↔ código
- `docs/03_INFRAESTRUCTURA_Y_SEGURIDAD.md` muestra `CMD_PING` como `["echo","pong"]` y el lock de Windows con `rundll32`, pero el código real usa un test TCP a `1.1.1.1:53` y `ctypes.windll.user32.LockWorkStation()`. Actualizar el doc para que refleje la implementación vigente.
- `requirements.txt` incluye `websockets==13.0` y `config.py` define `HTTP_GATEWAY_PORT = 8000`, pero **el gateway WebSocket nunca se construyó** (la estrategia móvil pasó a app nativa RN con sockets crudos). Es dependencia y config muerta → eliminar o marcar como “reservado/no usado”.

---

## 2. 🏗️ Arquitectura y calidad de código (sin tocar el motor de sockets)

Todo lo de esta sección respeta la regla de oro: el engine sigue siendo `socket` + `threading` + `struct`. Son mejoras de organización, no de tecnología de red.

### 2.1 Protocolo con versión y constantes tipadas
Hoy las acciones son strings sueltos repartidos (`"SHARE_TEXT"`, `"REMOTE_CMD"`, `"FILE_TRANSFER_META"`…) tanto en Python como en JS. Un typo es un bug silencioso. Propuesta:
- Un módulo `src/network/protocol.py` con `Enum`/constantes para acciones y tipos, y un campo `"v": 1` en cada trama para compatibilidad futura (permite evolucionar el protocolo sin romper nodos viejos).
- Documentar el esquema de cada mensaje en un único lugar (hoy hay un `docs/` de fase, pero no un “protocol spec” canónico consumible por Python y por la app móvil).

### 2.2 Empaquetado como paquete instalable
El código usa imports absolutos `from src....`, lo que obliga a ejecutar siempre desde la raíz y ensucia el namespace con `src`. Para uso “a largo plazo / día a día”:
- Renombrar `src/` → `sysnode/` y añadir `pyproject.toml` con un *console script* (`sysnode = "sysnode.__main__:main"`). Así se instala con `pip install -e .` y se lanza con `sysnode --cli` desde cualquier carpeta.
- Beneficio colateral: la carpeta `SysNode_Received/` podría vivir en `~/.local/share/sysnode/` en vez de la CWD.

### 2.3 Centralizar timeouts y “números mágicos”
Hay timeouts hardcodeados fuera de `config.py`: `10.0` en `TCPClientHandlerThread.run`, `SOCKET_TIMEOUT_SEC*2/*3` en el cliente, `2.0` en el ping. Llevarlos a `config.py` mejora legibilidad y permite ajustarlos para redes lentas.

### 2.4 Configuración por archivo + persistencia liviana
Para uso diario conviene un `~/.config/sysnode/config.toml` (nombre de nodo, puerto, carpeta de descargas, apps permitidas para `CMD_LAUNCH_APP`, peers “favoritos”). Se lee con `tomllib` (stdlib, sin dependencias nuevas).

### 2.5 Deduplicación menor
`TCPClient._connect_and_send` y `TCPClient.send_file` repiten el patrón conectar/timeout/finally. Extraíble a un helper de contexto (`with _open_conn(ip, port) as sock:`), opcional.

---

## 3. 🔐 Seguridad (proporcional al contexto, pero pensando en uso real)

El diseño ya evita RCE arbitrario (lista blanca, `shell=False`, sanitización de path). El punto débil de fondo es que **no hay autenticación**: cualquier nodo en la LAN puede bloquearte la pantalla o dejarte archivos.

### 3.1 Emparejamiento / token compartido (pedagógicamente valioso)
Añadir un **secreto de sesión** y firmar cada trama con `HMAC-SHA256` (`hashlib`/`hmac`, ambos stdlib → no viola “cero abstracciones de red”). El receptor rechaza tramas sin HMAC válido. Esto:
- Cierra el agujero de comandos/archivos no autenticados.
- Es una demo excelente para el examen: “así se autentica sobre un socket crudo”.
- El pairing puede ser el mismo QR de §4.1 (que transporta IP+puerto+token).

### 3.2 Confirmación explícita de acciones sensibles
`CMD_LOCK_SCREEN` (y los futuros `CMD_SUSPEND`/`CMD_SHUTDOWN`) deberían requerir confirmación local **o** estar detrás del pairing de 3.1. Un “apagar remoto sin auth” en una red universitaria es una travesura garantizada.

### 3.3 Endurecer recepción
Ver §1.4 (tope de tamaño + consentimiento). Además: validar que `final_path` quede efectivamente dentro de `SysNode_Received/` con `os.path.realpath(...).startswith(base)` como segunda barrera al `basename`.

---

## 4. ✨ Mejoras de funcionalidad

### 4.1 Conexión directa por IP / QR — *requisito documentado no implementado* ⭐
`docs/00` §3.2 promete un **fallback de conexión directa por IP o QR** para redes con AP Isolation / broadcast UDP filtrado (típico en Wi-Fi de facultad). **No existe en el código.** Es la mejora de mayor valor:
- Añadir en UI/CLI “Conectar a IP manual” → se agrega un peer sintético a la lista y se puede enviar por TCP directo aunque el radar UDP esté bloqueado.
- Generar/mostrar un QR (`qrcode` ya está en `requirements.txt`) que codifique `sysnode://<ip>:<puerto>?token=<...>`; la app móvil lo escanea. Esto **garantiza la demo en vivo** aunque el broadcast falle.

### 4.2 Diálogo de aceptación de archivos entrantes (UI)
Antes de mandar el ACK `READY`, la GUI debería preguntar “¿Aceptar `foto.jpg` (2.3 MB) de NodeBeta?”. Mejora seguridad y UX.

### 4.3 Envío a todos (broadcast de texto) y multi-selección
El “Shared Board” hoy es 1-a-1. Un botón “enviar a todos los nodos activos” lo vuelve un mini-chat de sala útil de verdad.

### 4.4 Completar el roadmap de comandos ya previsto
`dudas_implementacion.md` §4 ya lista `CMD_SUSPEND`, `CMD_SHUTDOWN` (con confirmación) y `CMD_LAUNCH_APP` (lanzador configurable por el usuario). Buenos candidatos, todos detrás del pairing de §3.1.

### 4.5 Servidor TCP en el móvil
`mobile_app` hoy tiene `TcpClient`/`TcpServer`/`UdpDiscovery`; conviene verificar que el móvil también **reciba** texto/archivos (no solo envíe), para paridad con el escritorio.

### 4.6 Historial persistente + logging a archivo
Para uso diario: guardar historial de mensajes/transferencias (SQLite stdlib) y logs rotados a `~/.local/share/sysnode/logs/`. Hace el proyecto “usable a largo plazo” sin agregar dependencias de red.

---

## 5. 🎨 Mejoras visuales / UX (escritorio)

- **Timestamps y auto-scroll** en el Shared Board (hoy la GUI no marca hora; la CLI sí).
- **Notificaciones de escritorio** al recibir texto/archivo (plyer o toast nativo) + minimizar a bandeja para dejarlo corriendo todo el día.
- **Barra de progreso separada** para envío vs recepción (hoy comparten `self.progress_bar`; una transferencia simultánea en ambos sentidos las pisa).
- **Tarjeta del “nodo local”** y toggle claro/oscuro (CustomTkinter lo soporta con `set_appearance_mode`).
- **Estado de conexión por peer** (último visto, latencia) y feedback visual cuando un peer expira.
- **Manejo de errores visible**: si el bind del puerto TCP falla (`tcp_server.run`), hoy solo se loguea; la GUI debería avisar “puerto ocupado, probá otro”.

---

## 6. 🧪 Testing y CI

- **Migrar a `pytest`** y separar **tests unitarios puros** (rápidos, sin red) de los de integración: `framing` (round-trip de bytes), `sanitize_filename`, `is_command_allowed`, verificación SHA-256. Hoy casi todo es integración con `sleep(3.5)` y puertos reales → lento y con riesgo de choque de puertos en CI.
- Arreglar `test_tcp_framing.py` (§1.1) para que vuelva a pasar.
- **GitHub Actions** mínimo: `ruff` (lint) + `black --check` (formato) + `pytest` de la suite unitaria en cada push. Barato y da señal de portafolio.
- Añadir `mypy` gradual apoyándose en los type hints ya presentes.

---

## 7. 🧹 Higiene de repositorio / DevOps

### 7.1 🔴 2.8 GB de artefactos de build versionados
`mobile_app/android/` pesa **~2.8 GB** e incluye `.gradle/`, `.cxx/`, `build/`, `app-debug.apk`, `.expo/`. El `.gitignore` de la raíz ignora `web_mobile/node_modules` (ruta del gateway abandonado) pero **no** `mobile_app/`. Hay que añadir un `.gitignore` para la app RN:
```
mobile_app/node_modules/
mobile_app/android/.gradle/
mobile_app/android/.cxx/
mobile_app/android/build/
mobile_app/android/app/build/
mobile_app/android/app/.cxx/
mobile_app/.expo/
mobile_app/**/*.apk
```
También `SysNode_Received/` contiene imágenes recibidas versionadas (ya está en `.gitignore`, pero conviene sacarlas del histórico si se subieron).

### 7.2 El repo raíz no es un repositorio git
`Is a git repository: false`. Todo el trabajo (materiales de clase + SysNode + app móvil) vive sin control de versiones. Recomendado: `git init` en `SysNode/` (o en la raíz con un `.gitignore` que excluya los ejercicios pesados), commits por fase, y publicar como portafolio (ya es un objetivo declarado en `docs/00` §3).

### 7.3 README ejecutable
Añadir al README un bloque de arranque rápido real: `pip install -r requirements.txt`, `python main.py --name Nodo1`, `python main.py --cli --tcp-port 50002`, cómo correr dos nodos en la misma PC, y cómo lanzar la app móvil. La fecha de presentación (“22 de Septiembre”) ya pasó → reencuadrar el README de “entregable de examen” a “herramienta mantenida”.

---

## 8. 🧭 Sobre “mejores tecnologías” (qué cambiar y qué NO)

| Área | Recomendación | ¿Por qué (sin perder el foco)? |
|---|---|---|
| **Motor de red (P2P)** | **NO cambiar.** Seguir con `socket`+`threading`+`struct`+`queue`. | Es el objetivo pedagógico y funciona bien. `asyncio` ocultaría justo lo que hay que demostrar. |
| **Auth** | `hmac`+`hashlib` (stdlib) | Cierra el agujero de no-autenticación sin agregar libs de red. |
| **Empaquetado** | `pyproject.toml` + console script | Uso diario e instalación limpia a largo plazo. |
| **Config/persistencia** | `tomllib` + `sqlite3` (stdlib) | Cero dependencias nuevas; habilita historial y favoritos. |
| **Calidad** | `pytest` + `ruff` + `black` + `mypy` + CI | Mantenibilidad de portafolio. |
| **Móvil** | Mantener Expo/RN + `react-native-tcp-socket`/`udp` | Ya habla el protocolo nativo; es la decisión correcta. Considerar EAS Build para distribuir el APK. |
| **Gateway WebSocket** | Descartar formalmente | Reemplazado por la app nativa; limpiar `requirements`/`config`. |

---

## 9. Hoja de ruta priorizada

**Sprint 1 — Estabilizar (medio día)**
1. Arreglar `core.event_queue` en CLI y test (§1.1). 🔴
2. `.gitignore` para `mobile_app/` y purgar artefactos de build (§7.1). 🔴
3. `git init` + README ejecutable (§7.2, §7.3).
4. Limpiar dependencia/config muertas del gateway (§1.5).

**Sprint 2 — Robustez y seguridad (2–3 días)**
5. Diálogo de aceptación + tope de tamaño de archivos (§1.4, §4.2).
6. Pairing con HMAC + confirmación de comandos sensibles (§3.1, §3.2).
7. Timeouts a `config.py`, `sanitize_filename` corregido (§2.3, §1.3).

**Sprint 3 — Valor de uso diario (1 semana)**
8. **Conexión directa por IP/QR** (§4.1). ⭐ Alto impacto.
9. Broadcast de texto + servidor TCP móvil (§4.3, §4.5).
10. Historial persistente + notificaciones + UX de la GUI (§4.6, §5).

**Sprint 4 — Profesionalización**
11. Empaquetado `pyproject.toml` + módulo `protocol.py` versionado (§2.1, §2.2).
12. Suite `pytest` unitaria + CI (§6).
13. Nuevos comandos del roadmap (§4.4).

---

### Cierre
No hay que “rehacer” nada: la arquitectura núcleo/UI y el protocolo son correctos. El camino a “herramienta útil a diario y mantenible a largo plazo” es **incremental**: primero destapar el bug del broker y la higiene del repo, después autenticación + consentimiento, y finalmente la conexión directa por IP/QR que ya estaba prometida en la documentación y es la que más habilita el uso real en cualquier red.
