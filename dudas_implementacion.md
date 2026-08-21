# SysNode - Dudas y Decisiones de Implementación

Este documento recopila el estado de las decisiones técnicas y arquitectónicas tomadas a partir del análisis de [SYSNODE Architecture.md](file:///home/jorcas/Documentos/2025-2doCuatrimestre/Sockets/codigo/SysNode/SYSNODE%20Architecture.md) y las confirmaciones del usuario.

---

## 1. Delimitación de Mensajes TCP (TCP Framing Problem)
* **Estado:** ✅ DECIDIDO Y CONFIRMADO
* **Decisión:** Se adopta el estándar de **Length-Prefixed Framing (Header de 4 bytes)**.
* **Detalle técnico:** Cada trama TCP iniciará con 4 bytes binarios en orden de red Big-Endian (`struct.pack('>I', payload_length)`). El receptor lee primero 4 bytes, extrae el tamaño exacto `L`, y luego realiza lecturas en bucle hasta acumular los `L` bytes.
* **Beneficio:** Garantiza que los metadatos JSON y los bloques de archivos binarios nunca se mezclen ni se corrompan en el buffer del socket TCP.

---

## 2. Descubrimiento UDP Broadcast y Reutilización de Puertos
* **Estado:** ✅ DECIDIDO Y CONFIRMADO
* **Decisión:** Aplicar obligatoriamente `SO_REUSEADDR` y `SO_REUSEPORT` en el socket UDP.
* **Detalle técnico:** Permite ejecutar múltiples instancias del nodo en la misma computadora/VM para pruebas locales sin conflicto de bind en el puerto `50000`.

---

## 3. Integración Móvil: Polling vs. WebSockets Puros (RFC 6455)
* **Estado:** 💡 PROPUESTA TÉCNICA APROBADA (WebSockets sobre Sockets Puros)
* **Contexto:** Los navegadores en celulares no permiten abrir sockets TCP/UDP crudos por seguridad de la sandbox web.
* **Decisión:** Para ofrecer tiempo real al celular sin dependencias de terceros ni `asyncio`, implementaremos el Handshake y Encapsulado de **WebSockets (RFC 6455) en Python puro usando `socket` + `struct` + `hashlib`**.
* **Detalle técnico:** 
  1. El celular hace un HTTP GET con la cabecera `Upgrade: websocket`.
  2. Nuestro servidor en socket puro responde el Handshake de `101 Switching Protocols` con la clave SHA-1 computada.
  3. El socket TCP permanece abierto transmitiendo tramas binarias de WebSocket parseadas a bajo nivel.
* **Impacto académico:** Demuestra al profesor cómo funciona el protocolo WebSocket internamente sobre un socket TCP nativo.

---

## 4. Lista Blanca de Comandos Remotos (SysAdmin)
* **Estado:** 🟡 EN DEFINICIÓN (Revisión progresiva)
* **Decisiones iniciales:**
  * `CMD_LOCK_SCREEN`: Bloqueo de sesión (`xdg-screensaver lock` en Linux / `rundll32.exe user32.dll,LockWorkStation` en Windows).
  * `CMD_NOTIFY`: Notificación visual de escritorio.
  * `CMD_PING`: Test de respuesta entre nodos.
  * `CMD_SYS_INFO`: Métricas de carga de sistema (CPU / RAM).

---

## 5. Control de Transferencias e Integridad de Archivos
* **Estado:** ✅ DECIDIDO Y CONFIRMADO
* **Decisión:** Al recibir un archivo por TCP, se guardará en un archivo temporal con extensión `.tmp` dentro del directorio `SysNode_Received/`.
* **Verificación:** Al finalizar la recepción total de bytes, se valida la firma hash SHA-256 informada en los metadatos iniciales. Si coincide, se renombra a su nombre original; si falla, se elimina para evitar archivos corruptos.
