# Directrices del Proyecto (Project Guidelines)

## 1. Filosofía de Desarrollo: Calidad y Eficiencia
- **Sin Restricciones de Librerías**: Se pueden y deben utilizar todas las librerías y herramientas de terceros necesarias para resolver problemas complejos (ej: previsualización de archivos PDF/Video, UI, red) siempre que aporten valor, calidad y eficiencia al sistema.
- **Empaquetado Profesional**: El objetivo final es un producto óptimo y fácil de instalar para el usuario final. En Desktop (Windows/Linux) esto implica generar un ejecutable (`.exe` o AppImage) usando herramientas como `PyInstaller`. En móviles, generar un `.apk` nativo. La arquitectura debe contemplar que la app será empaquetada.

## 2. Experiencia Multiplataforma Inteligente
- **Conciencia del Dispositivo (Context-Awareness)**: La interfaz gráfica debe adaptarse dinámicamente al tipo de sistema operativo del nodo destino. 
  - Si el destino es un **Móvil** (Android/iOS): Se ocultan funcionalidades restrictivas (como comandos remotos invasivos).
  - Si el destino es una **PC** (Windows/Linux): Se habilitan funciones completas de SysAdmin.

## 3. Mensajería P2P Asíncrona (Store & Forward)
- Dado que no existe un servidor central, los mensajes enviados a nodos desconectados no se descartan. Se guardan localmente en estado "Pendiente" (`pending`).
- Al detectar que el nodo destino vuelve a conectarse a la red LAN (vía UDP Beacon), el sistema debe sincronizar y entregar automáticamente la cola de mensajes pendientes en segundo plano.
