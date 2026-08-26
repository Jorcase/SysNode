# SysNode - Explicación Detallada y Pedagógica de la Fase 3

Este documento explica de forma clara, técnica y conceptual todo lo desarrollado en la **Fase 3 (Transferencia Binaria de Archivos / File Drop, Chunks de 4KB, Firma SHA-256 y Sanitización Anti-Path Traversal)**.

---

## 1. El Desafío Técnico de Transferir Archivos Pesados en Redes

Transferir un archivo pesado (ej. de 50MB a 5GB) sobre un socket TCP requiere resolver tres grandes problemas:

1. **Memoria RAM limitada:** No se puede cargar un archivo de 5GB entero en la RAM para enviarlo de un solo golpe. Hay que leerlo y transmitirlo en **fragmentos pequeños (*chunks*) de 4096 bytes (4KB)**.
2. **Delimitación de Archivo en TCP:** El servidor debe saber exactamente cuándo termina el archivo para dejar de leer el socket y cerrar el archivo en disco.
3. **Archivos Corruptos por Caídas de Red:** Si la red se corta a la mitad de la transferencia, no se debe dejar un archivo incompleto que sobrescriba el archivo original.

---

## 2. El Protocolo en 3 Fases sobre TCP

SysNode resuelve la transferencia mediante un protocolo en 3 fases secuenciales sobre la conexión TCP:

```
[Cliente / Emisor]                                       [Servidor / Receptor]
        |                                                          |
        |--- (Fase 1: METADATA JSON con framing TCP) ------------->| (Valida nombre con os.path.basename)
        |    {"filename": "foto.png", "size": 1048576, ...}        | (Prepara archivo .tmp)
        |                                                          |
        |<-- (Fase 2: ACK READY JSON con framing TCP) -------------| (Servidor listo)
        |                                                          |
        |=== (Fase 3: STREAMING BINARIO en Chunks de 4KB) ========>| (Escribe en foto.png.tmp)
        |    Chunk 1 (4096 bytes)                                  | (Calcula SHA-256 en vivo)
        |    Chunk 2 (4096 bytes)                                  |
        |    ...                                                   |
        |                                                          | (Verifica hash SHA-256)
        |<-- (Respuesta final OK / ERROR) -------------------------| (Renombra .tmp -> foto.png)
```

---

## 3. Ciberseguridad: Sanitización contra Path Traversal (CWE-22)

### El Ataque
Un usuario malintencionado o nodo malicioso podría enviar una cabecera con un nombre de archivo manipulado como:
`../../../../etc/passwd` o `..\..\Windows\System32\cmd.exe`.

Si el servidor abre ciegamente `open(filename, "wb")`, escribiría fuera de la carpeta de descargas sobrescribiendo archivos críticos del sistema operativo.

### La Solución (`src/core/security.py`)
Implementamos la función `sanitize_filename()`:
```python
def sanitize_filename(incoming_filename: str) -> str:
    clean_name = os.path.basename(incoming_filename.strip())
    clean_name = clean_name.replace("..", "").replace("/", "").replace("\\", "")
    return clean_name or "unnamed_file"
```
`os.path.basename()` descarta automáticamente cualquier ruta previa, garantizando que el archivo únicamente se guarde dentro del directorio aislado `SysNode_Received/`.

---

## 4. Protección contra Archivos Corruptos (Archivos `.tmp` + SHA-256)

### Archivos Temporales `.tmp`
Durante el streaming de bytes, los datos recibidos se escriben en `SysNode_Received/nombre_archivo.tmp`.

### Verificación de Firma SHA-256 (`src/network/file_transfer.py`)
Antes de enviar el archivo, el emisor calcula su firma única SHA-256 usando bloques de 64KB (`HASH_CHUNK_SIZE = 65536`).

Al terminar de recibir los bytes exactos:
1. El servidor calcula la firma SHA-256 del archivo `.tmp` recibido.
2. Si coincide al 100% con la firma esperada: Renombra `nombre_archivo.tmp` -> `nombre_archivo`.
3. Si no coincide o se cortó la red: Elimina el archivo `.tmp` y notifica el error.

---

## 5. Desglose del Código Creado en la Fase 3

* **[src/network/file_transfer.py](file:///home/jorcas/Documentos/2025-2doCuatrimestre/Sockets/codigo/SysNode/src/network/file_transfer.py):**
  * `calculate_file_sha256()`: Firma de integridad en bloques de 64KB.
  * `stream_file_bytes()`: Lectura del disco y `sock.sendall()` en fragmentos de 4KB.
  * `receive_file_bytes()`: Escritura en disco de bytes recibidos del socket TCP, actualización de SHA-256 en vivo y renombrado de `.tmp`.
* **[src/core/security.py](file:///home/jorcas/Documentos/2025-2doCuatrimestre/Sockets/codigo/SysNode/src/core/security.py):** `sanitize_filename()`.
* **[src/network/tcp_server.py](file:///home/jorcas/Documentos/2025-2doCuatrimestre/Sockets/codigo/SysNode/src/network/tcp_server.py):** Manejador de la acción `FILE_TRANSFER_META`.
* **[src/network/tcp_client.py](file:///home/jorcas/Documentos/2025-2doCuatrimestre/Sockets/codigo/SysNode/src/network/tcp_client.py):** Método `send_file()`.
* **[src/ui/cli.py](file:///home/jorcas/Documentos/2025-2doCuatrimestre/Sockets/codigo/SysNode/src/ui/cli.py):** Opción de menú `[3] Enviar Archivo` y barra de progreso ASCII (`[████████░░] 80%`).

---

## 🎯 Preguntas Clave para el Profesor de Redes

Si el profesor te pregunta: **"¿Cómo envías archivos grandes sin agotar la memoria ni corromper datos?"**

> *"Profesor, la transferencia de archivos se realiza en fragmentos (chunks) de 4096 bytes a través del socket TCP. Para evitar agotar la memoria RAM o enviar archivos corruptos, implementamos un protocolo en 3 fases: primero el emisor envía un paquete JSON con los metadatos (nombre, tamaño en bytes y la firma SHA-256). El servidor valida el nombre descartando rutas con `os.path.basename` para prevenir Path Traversal y responde con un ACK de confirmación. Luego el emisor transmite el flujo binario por chunks. El servidor escribe los bytes en un archivo temporal `.tmp` y va calculando el hash SHA-256 en vivo. Una vez alcanzado el tamaño total de bytes, se compara el hash SHA-256 calculado con el esperado: si coincide, se renombra al archivo final; si no, se borra el archivo incompleto."*
