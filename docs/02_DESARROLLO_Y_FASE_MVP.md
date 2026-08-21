# SysNode - Hoja de Ruta de Desarrollo y Fases MVP

Este documento define la secuencia modular incremental para construir SysNode. **No se debe avanzar a la siguiente fase sin verificar empíricamente mediante pruebas la fase anterior.**

---

## 1. Estructura de Directorios Recomendada

```
SysNode/
│
├── docs/                           # Documentación y guías del proyecto
│   ├── 00_REGLAS_Y_NORMAS.md
│   ├── 01_ARQUITECTURA_Y_RED.md
│   ├── 02_DESARROLLO_Y_FASE_MVP.md
│   ├── 03_INFRAESTRUCTURA_Y_SEGURIDAD.md
│   └── 04_DEFENSA_EXAMEN_Y_REDES.md
│
├── dudas_implementacion.md         # Registro de preguntas y decisiones
│
├── src/                            # Código fuente del Motor de Red en Python
│   ├── __init__.py
│   ├── config.py                   # Constantes de red (Puertos, Buffer sizes, TTL)
│   ├── network/
│   │   ├── __init__.py
│   │   ├── framing.py              # Protocolo de encapsulado TCP (struct.pack/unpack)
│   │   ├── udp_beacon.py           # Emisor UDP Broadcast
│   │   ├── udp_listener.py         # Receptor UDP Broadcast y Radar LAN
│   │   ├── tcp_server.py           # Servidor TCP multihilo
│   │   └── tcp_client.py           # Cliente TCP para transferencia/mensajes
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── sysnode_core.py         # Orquestador principal del nodo P2P
│   │   └── security.py             # Sanitización de rutas y lista blanca de comandos
│   │
│   ├── gateway/
│   │   ├── __init__.py
│   │   └── http_server.py          # HTTP Server nativo para la web móvil (React)
│   │
│   └── ui/
│       ├── cli.py                  # Interfaz de línea de comandos para testing
│       └── desktop_app.py          # Interfaz gráfica CustomTkinter
│
├── web_mobile/                     # Frontend móvil en React + Tailwind
│   └── dist/                       # Build estático servido por http_server.py
│
├── tests/                          # Tests unitarios y de integración de Sockets
│   ├── test_framing.py
│   └── test_udp_discovery.py
│
├── main.py                         # Punto de entrada principal
└── README.md
```

---

## 2. Secuencia Incremental de Fases MVP

```
Fase 1: Core Base (UDP Beacon & Listener + Radar LAN CLI)
   ↓
Fase 2: Conexión TCP & Protocolo de Framing (Shared Board & Comandos)
   ↓
Fase 3: Transferencia de Archivos Binarios (File Drop + Progress Bar)
   ↓
Fase 4: Desktop UI (CustomTkinter)
   ↓
Fase 5: Mobile Web Gateway (HTTP Server + React + Código QR)
```

---

### Fase 1: Core Base (Descubrimiento UDP)
* **Objetivo:** Lograr que dos consolas en la misma PC se descubran mutuamente.
* **Componentes:** `src/network/udp_beacon.py`, `src/network/udp_listener.py`, `src/core/sysnode_core.py`.
* **Prueba de Verificación:**
  Ejecutar en Terminal 1: `python -m src.ui.cli --node-name NodoA --port 50001`
  Ejecutar en Terminal 2: `python -m src.ui.cli --node-name NodoB --port 50002`
  *Ambos nodos deben imprimir en consola la aparición del otro en el Radar LAN dentro de los 3 segundos.*

---

### Fase 2: Conexión TCP y Framing
* **Objetivo:** Enviar mensajes de texto e instrucciones SysAdmin de un nodo a otro usando el módulo de framing `struct.pack('>I', len)`.
* **Componentes:** `src/network/framing.py`, `src/network/tcp_server.py`, `src/network/tcp_client.py`.
* **Prueba de Verificación:**
  Desde la consola de NodoA, enviar un comando de texto o de lista blanca a NodoB y verificar la recepción limpia sin fragmentación ni corrupción.

---

### Fase 3: Transferencia Binaria de Archivos (File Drop)
* **Objetivo:** Enviar un archivo de 50MB-500MB entre nodos registrando el avance en bytes y verificando la suma de comprobación SHA-256.
* **Componentes:** `src/network/tcp_client.py` (streaming chunks de 4KB), `src/network/tcp_server.py`.
* **Prueba de Verificación:**
  Transmitir un archivo de prueba. Comparar la firma SHA-256 del archivo original con la del archivo recibido.

---

### Fase 4: Desktop UI (CustomTkinter)
* **Objetivo:** Conectar `SysNodeCore` con `desktop_app.py`.
* **Componentes:** `src/ui/desktop_app.py`.
* **Regla de Integración:** La UI lee eventos periódicamente de `queue.Queue` usando `root.after(100, poll_queue)`. Se prohíbe actualizar la UI directamente desde los hilos de red.

---

### Fase 5: Mobile Web Gateway
* **Objetivo:** Servir la carpeta `web_mobile/dist` en la LAN e integrar la generación de código QR en la UI de escritorio usando la IP local (`socket.gethostbyname`).
* **Componentes:** `src/gateway/http_server.py`.
