# SysNode - Sistema P2P de Administración y Transferencia en Redes Locales

**SysNode** es un sistema peer-to-peer (P2P) híbrido desarrollado en Python puro sobre la capa de transporte de sockets (`socket`, `threading`, `queue`, `struct`).

---

## 📚 Estructura de la Documentación

Toda la documentación operativa, arquitectónica y de defensa del examen está organizada en la carpeta [docs/](file:///home/jorcas/Documentos/2025-2doCuatrimestre/Sockets/codigo/SysNode/docs):

1. **[00_REGLAS_Y_NORMAS.md](file:///home/jorcas/Documentos/2025-2doCuatrimestre/Sockets/codigo/SysNode/docs/00_REGLAS_Y_NORMAS.md):** Reglas estrictas de código, prohibición de abstracciones de red, y explicación pedagógica de `threading` vs `asyncio`.
2. **[01_ARQUITECTURA_Y_RED.md](file:///home/jorcas/Documentos/2025-2doCuatrimestre/Sockets/codigo/SysNode/docs/01_ARQUITECTURA_Y_RED.md):** Modelo de hilos, topología P2P, protocolos UDP Broadcast y TCP Framing.
3. **[02_DESARROLLO_Y_FASE_MVP.md](file:///home/jorcas/Documentos/2025-2doCuatrimestre/Sockets/codigo/SysNode/docs/02_DESARROLLO_Y_FASE_MVP.md):** Estructura del proyecto y guía paso a paso de las 5 fases del MVP.
4. **[03_INFRAESTRUCTURA_Y_SEGURIDAD.md](file:///home/jorcas/Documentos/2025-2doCuatrimestre/Sockets/codigo/SysNode/docs/03_INFRAESTRUCTURA_Y_SEGURIDAD.md):** Medidas de ciberseguridad, prevención de Command Injection (Lista blanca) y Path Traversal.
5. **[04_DEFENSA_EXAMEN_Y_REDES.md](file:///home/jorcas/Documentos/2025-2doCuatrimestre/Sockets/codigo/SysNode/docs/04_DEFENSA_EXAMEN_Y_REDES.md):** Guía de estudio para el examen final con el profesor de redes (Kurose, framing, multiplexación, preguntas trampa).
6. **[05_EXPLICACION_FASE_1.md](file:///home/jorcas/Documentos/2025-2doCuatrimestre/Sockets/codigo/SysNode/docs/05_EXPLICACION_FASE_1.md):** Explicación didáctica y pedagógica paso a paso del código de la Fase 1 (UDP Discovery, hilos, llamadas al sistema).
7. **[06_EXPLICACION_FASE_2.md](file:///home/jorcas/Documentos/2025-2doCuatrimestre/Sockets/codigo/SysNode/docs/06_EXPLICACION_FASE_2.md):** Explicación didáctica y pedagógica del código de la Fase 2 (TCP Framing, `struct`, Shared Board y Lista Blanca).
8. **[07_EXPLICACION_FASE_3.md](file:///home/jorcas/Documentos/2025-2doCuatrimestre/Sockets/codigo/SysNode/docs/07_EXPLICACION_FASE_3.md):** Explicación didáctica y pedagógica del código de la Fase 3 (Transferencia binaria de archivos, streaming de 4KB, SHA-256 y Anti-Path Traversal).
9. **[dudas_implementacion.md](file:///home/jorcas/Documentos/2025-2doCuatrimestre/Sockets/codigo/SysNode/dudas_implementacion.md):** Preguntas de diseño e inconsistencias técnicas a considerar durante el desarrollo.

---

## 🚀 Guía Rápida de Uso

1. **Instalar dependencias:**
   ```bash
   pip install -r requirements.txt
   ```
2. **Ejecutar la Interfaz Gráfica (Desktop UI):**
   ```bash
   python3 main.py --name "MiPC"
   ```
3. **Ejecutar en modo Consola (CLI):**
   ```bash
   python3 main.py --cli --name "Consola" --tcp-port 50002
   ```
4. **Ejecutar la App Móvil (React Native):**
   ```bash
   cd mobile_app
   npm install
   npx expo start -c
   ```

*(El proyecto fue defendido con éxito en la materia de Redes. Ahora es mantenido como herramienta funcional para uso diario).*
