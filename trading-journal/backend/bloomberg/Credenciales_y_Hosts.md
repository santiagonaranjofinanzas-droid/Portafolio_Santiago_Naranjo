#Registro de Credenciales y Hosts del Sistema

Este documento mantiene un registro centralizado de todos los puertos, hosts, claves de API y credenciales de bases de datos generados durante la construcción de la arquitectura Bloomberg + Palantir.

##Fase 1: Microservicio Cuantitativo (FastAPI)
*   **Servicio:** Quant Decision Engine (HMM-XGBoost)
*   **Host Local:** `http://localhost:8000`
*   **Documentación API (Swagger):** `http://localhost:8000/docs`
*   **Endpoints Activos:**
    *   `POST /predict` (Inferencia Online)
    *   `GET /health` (Estado de Infraestructura)
    *   `GET /model-info` (Metadata de Modelos)
*   **Notas de Seguridad:** El endpoint corre localmente y sin autenticación en modo desarrollo. En producción deberá estar protegido por el API Gateway.
