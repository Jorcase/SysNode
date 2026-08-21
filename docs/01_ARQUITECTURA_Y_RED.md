# SysNode - Arquitectura de Sistema y Protocolos de Red

Este documento especifica la topología de la red P2P híbrida, la arquitectura interna de hilos y las especificaciones exactas de los protocolos de capa de aplicación construidos sobre UDP y TCP.

---

## 1. Topología de Red: P2P Híbrido

SysNode no requiere un servidor central ni infraestructura previa en Internet. Funciona en una **Red de Área Local (LAN)** donde cada dispositivo ejecutando SysNode actúa simultáneamente como **Cliente** y **Servidor** (*Peer*).

```
+------------------------+                  +------------------------+
|      Nodo A (PC)       |                  |      Nodo B (PC)       |
|  - UDP Listener (50000)|  <-- UDP Bcast-- |  - UDP Listener (50000)|
|  - UDP Beacon (50000)  |  -- UDP Bcast -->|  - UDP Beacon (50000)  |
|  - TCP Server (50001)  |  <=== TCP ======>|  - TCP Server (50001)  |
|  - HTTP/WS Gateway (8000)|                |                        |
+------------------------+                  +------------------------+
            ^
            | (HTTP REST / Pure WebSocket RFC 6455 over Socket)
            v
+------------------------+
|   Celular (Navegador)  |
+------------------------+
```

---

## 2. Modelo de Hilos Interno (Threading Model)

El núcleo de SysNode (`SysNodeCore`) administra los siguientes hilos de ejecución paralela:

```
[Main Thread] ---> UI (CustomTkinter / CLI) <--- Queue.Queue ---+
                                                                |
[Thread 1] ------> UDP Beacon (Broadcast cada 3s) --------------+
[Thread 2] ------> UDP Listener (Escucha 50000 + TTL cleanup) --+
[Thread 3] ------> TCP Server (Escucha 50001, spawns worker) ---+
[Thread 4] ------> HTTP Web Gateway (Servidor estático + REST) -+
```

1. **Main Thread (UI / CLI):** Controla el ciclo de eventos visuales y consume mensajes de `queue.Queue`.
2. **UDP Beacon Thread (Daemon):** Emite periódicamente la presencia del nodo en la LAN.
3. **UDP Listener Thread (Daemon):** Mantiene en memoria el diccionario de nodos activos (`active_peers`). Si un nodo no responde en más de 10s (TTL), se elimina.
4. **TCP Server Thread (Daemon):** Atiende conexiones entrantes de otros nodos para recepción de datos y transferencias de archivos. Cada conexión genera o delega a un *worker thread*.
5. **HTTP Gateway Thread (Daemon):** Servidor HTTP embebido que expone la UI React estática y un endpoint `/api` para interactuar con dispositivos móviles sin app.

---

## 3. Protocolos de Red de Capa de Aplicación

### 3.1 Protocolo de Descubrimiento (UDP Broadcast - Puerto `50000`)
* **Mecanismo:** Envío en broadcast a `255.255.255.255`.
* **Frecuencia:** Cada 3 segundos.
* **Payload JSON:**
```json
{
  "type": "SYSNODE_ANNOUNCE",
  "node_id": "550e8400-e29b-41d4-a716-446655440000",
  "hostname": "fedora-jorcas",
  "os": "linux",
  "tcp_port": 50001,
  "timestamp": 1724241600
}
```

---

### 3.2 Protocolo de Datos y Transferencias (TCP - Puerto `50001`)

Para solucionar el problema de **TCP Framing** (delimitación de mensajes), todas las tramas TCP utilizan un encabezado binario fijo de 4 bytes (Big-Endian) que representa el tamaño exacto en bytes del paquete que le sigue.

#### Formato de la Trama TCP (Length-Prefixed Framing):
```
+-------------------------+-----------------------------------+
|  Length Header (4 bytes)|          Payload (JSON/Binary)    |
|   struct.pack('>I', L)  |               L bytes             |
+-------------------------+-----------------------------------+
```

#### Tipos de Acción en TCP Payload:

##### Acción 1: Compartir Texto (Shared Board)
```json
{
  "action": "SHARE_TEXT",
  "sender_id": "UUID",
  "payload": "https://github.com/jorcas/sysnode"
}
```

##### Acción 2: Ejecución Remota (SysAdmin Commands)
```json
{
  "action": "REMOTE_CMD",
  "sender_id": "UUID",
  "command": "CMD_LOCK_SCREEN",
  "auth_token": "token-opcional"
}
```

##### Acción 3: Transferencia de Archivos (File Drop) - Protocolo en 3 Fases

* **Fase 1: Solicitud / Metadata (Cliente -> Servidor)**
```json
{
  "action": "FILE_TRANSFER_META",
  "transfer_id": "TX-9876",
  "filename": "backup_config.tar.gz",
  "filesize_bytes": 10485760,
  "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
}
```

* **Fase 2: Confirmación ACK (Servidor -> Cliente)**
```json
{
  "action": "FILE_TRANSFER_ACK",
  "transfer_id": "TX-9876",
  "status": "READY"
}
```

* **Fase 3: Streaming Binario (Cliente -> Servidor)**
El cliente lee el archivo local en bloques de `4096` bytes (4KB) y los transmite secuencialmente sobre el socket TCP hasta completar los `filesize_bytes`. El servidor escribe los bloques en un archivo temporal hasta verificar el total y validar la integridad con el hash SHA-256.
