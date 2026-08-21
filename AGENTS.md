# Instructions for AI Agents (SysNode Project)

Welcome to **SysNode**. Before making any code edits or additions, you **MUST** read and adhere to the project documentation located in the `docs/` directory.

## Critical Rules for AI Agents

1. **Read Documentation First:**
   - [00_REGLAS_Y_NORMAS.md](file:///home/jorcas/Documentos/2025-2doCuatrimestre/Sockets/codigo/SysNode/docs/00_REGLAS_Y_NORMAS.md): Strict networking rules (raw Python `socket` module only, `threading` + `queue.Queue`, prohibited abstractions).
   - [01_ARQUITECTURA_Y_RED.md](file:///home/jorcas/Documentos/2025-2doCuatrimestre/Sockets/codigo/SysNode/docs/01_ARQUITECTURA_Y_RED.md): P2P topology, threading model, TCP Length-Prefixed Framing (`struct.pack('>I', len)`), UDP Broadcast protocol.
   - [02_DESARROLLO_Y_FASE_MVP.md](file:///home/jorcas/Documentos/2025-2doCuatrimestre/Sockets/codigo/SysNode/docs/02_DESARROLLO_Y_FASE_MVP.md): MVP roadmap phases (Phase 1 to Phase 5) and file structure inside `src/`.
   - [03_INFRAESTRUCTURA_Y_SEGURIDAD.md](file:///home/jorcas/Documentos/2025-2doCuatrimestre/Sockets/codigo/SysNode/docs/03_INFRAESTRUCTURA_Y_SEGURIDAD.md): Cross-platform rules (Windows/Linux) and Command Injection Whitelist (Blue Team).
   - [04_DEFENSA_EXAMEN_Y_REDES.md](file:///home/jorcas/Documentos/2025-2doCuatrimestre/Sockets/codigo/SysNode/docs/04_DEFENSA_EXAMEN_Y_REDES.md): Exam presentation requirements for the Networks professor.

2. **Strict Code & Architecture Constraints:**
   - **No High-Level Network Wrappers for P2P:** Build core P2P features strictly using Python's native `socket` library.
   - **No `asyncio`:** Concurrency must use `threading.Thread` and `queue.Queue` for thread-safe UI/Core separation.
   - **Cross-Platform First (Windows & Linux):** Never hardcode Linux-only or Windows-only system calls without checking `sys.platform`.
   - **TCP Framing Obligation:** Always prefix TCP message payloads with a 4-byte Big-Endian length header (`struct.pack('>I', payload_len)`).
   - **Clean & Modular Code:** Keep files under 300 lines. Avoid dead code or dummy placeholders.

3. **Incremental Verification:**
   - Always run empirical verification (e.g. running multiple CLI instances on local ports) after completing each Phase before moving to the next.
