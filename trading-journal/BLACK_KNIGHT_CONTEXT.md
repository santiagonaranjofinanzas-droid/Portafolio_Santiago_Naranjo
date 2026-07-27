# CONTEXTO GENERAL DEL ECOSISTEMA: BLACK KNIGHT SAAS

Este documento sirve como la fuente centralizada de verdad y contexto técnico completo para desarrolladores y asistentes de IA (Gems/GPTs) sobre el ecosistema **Black Knight SaaS**. Describe con lujo de detalles la arquitectura del sistema, el stack tecnológico, los modelos de base de datos, el flujo de procesamiento de operaciones financieras y los componentes de IA / modelado cuantitativo incorporados.

---

##1. RESUMEN EJECUTIVO
**Black Knight SaaS** es una plataforma comercial multi-tenant de grado institucional diseñada para traders cuantitativos. Su propósito fundamental es:
1. Sincronizar en tiempo real el historial de operaciones y telemetría de cuentas desde terminales **MetaTrader 5 (MT5)**.
2. Calcular métricas avanzadas de física del trade en milisegundos (MAE/MFE, múltiplos R dinámicos, múltiplos R ajustados por volatilidad de régimen, pérdidas de eficiencia, y simulaciones predictivas "What-If").
3. Integrar un motor de inteligencia macroeconómica (**Bloomberg Sentinel / MiroFish Swarm**) que utiliza modelos estadísticos ocultos de Markov (**HMM**), **XGBoost** y enjambres de LLMs para diagnosticar regímenes de mercado en tiempo real y sugerir coberturas u optimización de carteras (Black-Litterman).
4. Ofrecer un panel web (Dashboard) interactivo de alto rendimiento para el análisis cuantitativo, registro diario emocional y técnico de operaciones.

---

##2. ARQUITECTURA TÉCNICA DEL ECOSISTEMA

El sistema está dividido en cuatro grandes capas que se comunican de forma asíncrona y segura:

```mermaid
graph TD
    A[MetaTrader 5 Terminal] -->1. Evento de Trade B(EA: Black Knight Quant Reporter)
    B -->2. Escribe JSON local C[Outbox Agent Daemon / Socket TCP]
    C -->3. Firma HMAC SHA256 D[FastAPI Backend Cloud]
    D -->4. Almacena PostgreSQL/SQLite E[(Database: SQLModel)]
    F[Bloomberg / Market Feeds] -->5. Ingesta 15m G[Sentinel Master Orchestrator]
    G -->6. Inferencia HMM + XGBoost G
    G -->7. Enjambre MiroFish Swarm LLM G
    G -->8. Push API /update D
    H[Frontend: Next.js 16 / React 19] -->9. GET /api/v1/metrics D
```

###A. Frontend (Next.js & React 19)
Localizado en la carpeta `/frontend`. Diseñado bajo el tema oscuro ultra-premium **Cronos-Obsidian** para terminales profesionales y de inversión.
*   **Stack Tecnológico:**
    *   **Core:** Next.js 16 (App Router), React 19 y TypeScript.
    *   **Estilos:** TailwindCSS v4 con variables HSL personalizadas (`--bg-void`, `--bg-base`, etc.) basadas en bismuto y grafito profundo para mitigar la fatiga visual.
    *   **Animaciones:** Framer Motion para transiciones de datos y paneles interactivos.
    *   **Gráficos:** ECharts 6 y `echarts-for-react` v3.
    *   **Tablas:** TanStack React Table v8.
    *   **Consumo de API:** TanStack React Query v5.
*   **Optimizaciones de Visualización y Rendimiento (Cero Canvas Thrashing):**
    *   `EquityChart.tsx` y `TradeM1Chart.tsx` están vectorizados mediante renderizado **SVG** (`opts={{ renderer: 'svg' }}`) para lograr máxima nitidez en pantallas 4K y pantallas de alta densidad de pixeles.
    *   Ambos componentes gráficos están aislados del flujo global mediante `React.memo` para evitar re-renderizados innecesarios causados por el stream asíncrono en tiempo real.
*   **Componentes Clave (16 archivos en `/frontend/src/components/`):**
    *   `MacroNewsPanel.tsx`: Panel macroeconómico en tiempo real. Visualiza los estados de régimen de mercado HMM usando opacidades sutiles y gradientes degradados en vez de alertas sólidas estridentes (clases `.hmm-bg-quiet`, `.hmm-bg-volatile`, `.hmm-bg-transition`).
    *   `TradeDetailDrawer.tsx`: Panel lateral con físicas de resorte (spring) rígidas (`stiffness: 300, damping: 30`) que emulan el comportamiento dinámico de terminales profesionales como Bloomberg o Reuters Eikon. Carga de manera asíncrona la bitácora cualitativa del trade (`/journal/{position_id}`) con un efecto *stagger* de Framer Motion mientras los datos analíticos duros ya están renderizados. Muestra visualmente la pérdida de eficiencia (Execution Slippage) y el múltiplo R ajustado.
    *   `AIAnalystPanel.tsx`: Pestaña "Analista IA" que conecta con el backend de IA (Ollama local, Groq cloud, o NVIDIA API) para generar insights cuantitativos sobre la cuenta.
    *   `BloombergSentinel.tsx`: Visualización del estado del orquestador macroeconómico.
    *   `ControlCenter.tsx`: Centro de control principal del dashboard.
    *   `RiskAnalytics.tsx`: Panel de analíticas de riesgo avanzadas (VaR, CVaR, Kelly, Montecarlo).
    *   `TradeCalendar.tsx`: Calendario visual de operaciones por día.
    *   `TradingJournal.tsx`: Editor de bitácora emocional y técnica por trade.
    *   `MT5StatusIndicator.tsx`: Indicador de conexión MT5 en tiempo real.
    *   `EquityChart.tsx`: Curva de equity vectorizada SVG.
    *   `TradeM1Chart.tsx`: Gráfico de velas M1 con MAE/MFE overlay.
    *   `DataJournal.tsx`, `DataTable.tsx`, `KPIHero.tsx`, `MetricCard.tsx`, `TradeHistory.tsx`.
*   **Estructura de la App (`/frontend/src/app/`):**
    *   `page.tsx` – Página principal del dashboard (26KB).
    *   `layout.tsx` – Layout raíz con fuentes Geist.
    *   `globals.css` – Sistema de diseño Cronos-Obsidian completo (23KB) con variables HSL, animaciones y clases HMM.
    *   `providers.tsx` – Providers de React Query.
    *   `mobile/` – Subdirectorio para layout móvil.

###B. Backend (FastAPI & SQLModel)
Localizado en la carpeta `/backend/app`. Construido en Python, optimizado para latencia ultra-baja y aislamiento de datos.
*   **Archivos principales del backend:**
    *   `main.py` (67KB) – Aplicación FastAPI completa con todos los endpoints REST.
    *   `engine.py` (62KB) – Motor de cálculo cuantitativo: estadísticas, trade physics, Montecarlo, Kelly, GARCH.
    *   `models.py` (6KB) – Modelos SQLModel (TradeArchive, TradeJournal, BloombergSnapshot, AccountSnapshot, etc.).
    *   `settings.py` (6KB) – Configuración centralizada con dataclass frozen (puertos, CORS, HMAC, AI provider).
    *   `database.py` (4KB) – Inicialización de la base de datos (SQLite local / PostgreSQL cloud).
    *   `auth.py` (3KB) – Autenticación HMAC y tenant isolation.
    *   `ai.py` (16KB) – Capa de abstracción multi-provider de IA (Ollama, Groq, NVIDIA).
    *   `macro_service.py` (7KB) – Servicio de datos macroeconómicos (Finnhub, AlphaVantage, FRED, NewsData).
*   **Handshake & Ingesta:** Ingesta directa de MetaTrader 5 `/api/v1/ingest/mql5` protegida por firma criptográfica HMAC SHA256, o mediante un socket de bypass TCP nativo en el puerto `6380`.
*   **Capa de Caché de Alto Rendimiento (Multi-tenant Performance):**
    *   Para evitar colapsar la base de datos de MT5 o servicios externos con consultas concurrentes de series temporales de 1 minuto (M1) de múltiples organizaciones, el backend implementa una caché basada en archivos JSON estructurados en `_journal_data/cache_m1/`.
    *   Una vez que un trade es marcado como cerrado y se realiza la consulta inicial de su gráfico de ticks M1 para MAE/MFE, el array se almacena localmente y se consume de forma instantánea de la caché en posteriores peticiones de `/api/v1/trade/chart`.

###C. Outbox Agent Daemon
Localizado en `/scratch/phase2_outbox_agent.py` (15KB). Daemon que corre en segundo plano y:
1.  Escanea el directorio `_journal_data/outbox_queue/` cada 30 segundos buscando JSONs nuevos escritos por el EA de MT5.
2.  Firma cada payload con HMAC SHA256 usando el secret de `PHASE2_CREDENTIALS.local.md`.
3.  Envía el payload firmado al endpoint de ingesta del backend (local o cloud).
4.  Registra el estado de cada envío en `_journal_data/outbox.db` (SQLite local de control).

###D. Bloomberg Sentinel Orchestrator
Localizado en `/backend/bloomberg/`. Subsistema de inteligencia macroeconómica que incluye:
*   `quant-service/` – Microservicio FastAPI (puerto 8001) para cálculos cuantitativos.
*   `decision-engine/` – Microservicio FastAPI (puerto 8002) para decisiones de cobertura.
*   `master_orchestrator.py` – Orquestador maestro que coordina los microservicios.
*   `launch_platform.ps1` / `stop_platform.ps1` – Scripts de ciclo de vida.

---

##3. MODELO DE DATOS DETALLADO & AUDITORÍA DE RIESGO

La persistencia del ecosistema está definida en `/backend/app/models.py` y calculada analíticamente en `backend/app/engine.py`.

###A. Fórmulas de Riesgo Agregado y Trade Physics
*   **Sortino Condicional (Downside Deviation):**
    El dashboard principal reporta el Sortino Condicional anualizado en base a la desviación condicional inferior (penalizando solo los retornos diarios negativos respecto a la tasa libre de riesgo $R_f = 0$):
    $$\sigma_d = \sqrt{\frac{1}{N} \sum_{t=1}^{N} \min(0, R_t)^2}$$
    $$\text{Sortino Condicional} = \frac{\text{Retorno Promedio Diario}}{\sigma_d} \times \sqrt{252}$$
*   **Múltiplo R Ajustado por Volatilidad de Régimen ($R_{\text{adj}}$):**
    Para mitigar distorsiones por regímenes de mercado agresivos, se estima la volatilidad condicional diaria $\sigma_t$ de la cuenta (usando un modelo GARCH(1,1) o fallback móvil de 20 días). El múltiplo R de cada trade se ajusta respecto a la volatilidad histórica promedio del sistema ($\sigma_{\text{avg}}$):
    $$\text{R-Multiple}_{\text{adj}} = \frac{\text{R-Multiple}}{\sigma_t / \sigma_{\text{avg}}}$$
*   **Pérdida de Eficiencia (Execution Slippage):**
    Mide la ineficiencia entre la ejecución real y la proyección What-If sin salidas parciales:
    $$\text{Slippage (Cash)} = \max(0, \text{what\_if\_pnl} - \text{netpnl})$$
    $$\text{Slippage (R)} = \max(0, \text{what\_if\_r} - \text{r\_multiple})$$

###B. Estructura de Entidades
*   `TradeArchive` *(Primary Keys: organization_id, position_id)*: Contiene el precio promedio ponderado de entrada y salidas parciales, volumen, comisión, swaps, MAE/MFE reales, eficiencias y simulación What-If (`what_if_result`, `what_if_pnl`, `what_if_r`).
*   `TradeJournal` *(Unique Index: position_id)*: Bitácora del trader. Almacena el `emotional_state` (1-10), `emotional_tags` (FOMO, Greed, Calm, etc.) y notas textuales (`notes_pre`, `notes_during`, `notes_post`, `notes_general`).
*   `BloombergSnapshot`: Estado del macroentorno capturado por el orquestador (`stress_prob`, `entropy`, `confidence`, `dominant_theme`, `narrative`, y ponderación óptima de activos `weights_json`).
*   `AccountSnapshot`: Snapshots periódicos de balance/equity capturados en tiempo real por el EA de MT5.

---

##4. ESTRUCTURA DEL PROYECTO (ÁRBOL COMPLETO)

```
Journal_py_original/
├── .venv/                          # Entorno virtual Python (dependencias backend)
├── backend/
│   ├── .env                        # Variables de entorno backend (DB, AI, API keys)
│   ├── app/
│   │   ├── main.py                 # FastAPI app principal (~1600 líneas, todos los endpoints)
│   │   ├── engine.py               # Motor cuantitativo (stats, physics, GARCH, Montecarlo)
│   │   ├── models.py               # SQLModel entities
│   │   ├── settings.py             # Configuración centralizada (frozen dataclass)
│   │   ├── database.py             # Inicialización DB (SQLite/PostgreSQL)
│   │   ├── auth.py                 # HMAC auth & tenant isolation
│   │   ├── ai.py                   # Multi-provider AI abstraction
│   │   └── macro_service.py        # Datos macro (Finnhub, FRED, AlphaVantage, NewsData)
│   ├── bloomberg/                  # Subsistema de inteligencia macroeconómica
│   │   ├── quant-service/          # Microservicio FastAPI (puerto 8001)
│   │   ├── decision-engine/        # Microservicio FastAPI (puerto 8002)
│   │   ├── master_orchestrator.py  # Orquestador central
│   │   ├── launch_platform.ps1     # Launcher ecosistema Bloomberg
│   │   └── stop_platform.ps1       # Shutdown ecosistema Bloomberg
│   ├── requirements.txt            # Dependencias Python del backend
│   └── black_knight_quant_journal.db  # Base de datos SQLite local
├── frontend/
│   ├── .env                        # BACKEND_API_BASE_URL=http://127.0.0.1:8080/api/v1
│   ├── next.config.ts              # Rewrite proxy /api/v1/* → backend
│   ├── package.json                # Next.js 16, React 19, ECharts 6, Framer Motion
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx            # Dashboard principal
│   │   │   ├── layout.tsx          # Layout raíz
│   │   │   ├── globals.css         # Sistema de diseño Cronos-Obsidian (23KB)
│   │   │   ├── providers.tsx       # React Query providers
│   │   │   └── mobile/             # Layout móvil
│   │   ├── components/             # 16 componentes React
│   │   ├── hooks/                  # Custom hooks
│   │   └── lib/                    # Utilidades
│   └── node_modules/
├── scratch/                        # Scripts de utilidad y agentes
│   ├── phase2_outbox_agent.py      # Daemon de sincronización MT5 → Backend (15KB)
│   ├── run_local_dashboard.ps1     # Launcher local (WMI detached processes)
│   ├── run_phase2_outbox.ps1       # Runner del outbox agent
│   ├── run_phase2_outbox_from_md.ps1  # Runner con credenciales desde .md
│   ├── stop_phase2_outbox.ps1      # Shutdown + port cleanup (8080, 3000)
│   ├── test_quantitative_math.py   # Tests de fórmulas cuantitativas
│   ├── verify_apis.py              # Verificación de API keys externas
│   └── ...                         # Otros scripts de debug y utilidad
├── _journal_data/                  # Datos de runtime
│   ├── outbox_queue/               # JSONs pendientes del EA MT5
│   ├── outbox.db                   # SQLite de control del outbox agent
│   ├── logs/                       # Logs (backend_out.log, frontend_out.log, etc.)
│   ├── pids/                       # PIDs de procesos activos (backend.pid, frontend.pid)
│   └── cache_m1/                   # Caché de series temporales M1
├── mql5/                           # Código fuente MQL5
├── Black_Knight_Quant_Reporter.mq5 # Expert Advisor MT5 (fuente)
├── Black_Knight_Quant_Reporter.ex5 # Expert Advisor MT5 (compilado)
│
│── ═══ SCRIPTS DE LANZAMIENTO ═══
├── Dashboard.bat                   # Lanza outbox agent + abre dashboard CLOUD (Vercel)
├── Dashboard_Local.bat             # Lanza backend + frontend + outbox LOCALMENTE
├── LAUNCH_LOCAL_DASHBOARD.vbs      # Launcher VBS para ejecución desacoplada
├── RUN_MT5_OUTBOX.bat              # Solo outbox agent (sin dashboard)
├── STOP_TERMINAL.bat               # Detiene TODOS los procesos + libera puertos
├── SETUP_MT5_AND_LAUNCH.bat        # Setup inicial MT5
├── CHECK_MT5_STATUS.ps1            # Diagnóstico del sistema completo
├── MONITOR_MT5_OUTBOX.ps1          # Monitoreo en tiempo real del outbox
│
│── ═══ CONFIGURACIÓN Y CREDENCIALES ═══
├── PHASE2_CREDENTIALS.local.md     # Credenciales locales (HMAC, endpoints) — NO COMMITEAR
├── PHASE2_CREDENTIALS.md           # Template de credenciales
├── render.yaml                     # Configuración de despliegue en Render
├── BLACK_KNIGHT_CONTEXT.md         # Este archivo de contexto
├── SETUP_INSTRUCTIONS_ES.md        # Guía de activación MT5 ↔ Dashboard
└── MT5_EA_INTEGRATION.md           # Documentación de integración del EA
```

---

##5. CONFIGURACIÓN DE PUERTOS Y ENTORNOS

 Servicio              Puerto  Entorno    Configuración                      
-----------------------------------------------------------------------------
 FastAPI Backend       8080    Local      `BK_API_PORT` en `backend/.env`    
 Next.js Frontend      3000    Local      `npm run dev` en `frontend/`       
 Bloomberg Quant Svc   8001    Local      `backend/bloomberg/quant-service/` 
 Bloomberg Decision    8002    Local      `backend/bloomberg/decision-engine/` 
 TCP Socket (bypass)   6380    Opcional   `BK_ENABLE_SOCKET_SERVER=true`     
 Render Backend        $PORT   Cloud      `render.yaml`                      
 Vercel Frontend       443     Cloud      `black-knight-saas.vercel.app`     

**Variables de entorno del backend (`backend/.env`):**
```env
DATABASE_URL=sqlite:///black_knight_quant_journal.db
AI_PROVIDER=nvidia                     # ollama  groq  nvidia  auto
NVIDIA_API_KEY=nvapi-...
NVIDIA_MODEL=moonshotai/kimi-k2.6
INGEST_REQUIRE_HMAC=False
DEFAULT_ORG_ID=1
FINNHUB_API_KEY=...
ALPHAVANTAGE_API_KEY=...
FRED_API_KEY=...
NEWSDATA_API_KEY=...
```

**Variables de entorno del frontend (`frontend/.env`):**
```env
BACKEND_API_BASE_URL=http://127.0.0.1:8080/api/v1
```

**Proxy Rewrite de Next.js (`next.config.ts`):**
El frontend redirige todas las peticiones `/api/v1/*` al backend configurado en `BACKEND_API_BASE_URL`. Si la variable no está definida, apunta por defecto al backend cloud en Render.

---

##6. COMANDOS PRINCIPALES

 Comando                     Acción                                                     
-----------------------------------------------------------------------------------------
 `Dashboard_Local.bat`        Inicia backend + frontend + outbox agent **LOCAL**       
 `Dashboard.bat`              Inicia outbox agent + abre dashboard **CLOUD** (Vercel)  
 `STOP_TERMINAL.bat`          Detiene todos los procesos + libera puertos 8080 y 3000  
 `RUN_MT5_OUTBOX.bat`         Solo outbox agent (sin frontend ni backend)              
 `CHECK_MT5_STATUS.ps1`       Diagnóstico completo del sistema                        
 `MONITOR_MT5_OUTBOX.ps1`     Monitoreo real-time del outbox                           

---

##7. CÓMO USAR ESTE CONTEXTO CON ASISTENTES DE IA
Este archivo es óptimo para inicializar cualquier sesión de desarrollo o configurar las instrucciones del sistema de un Gem en Google Gemini. Puedes usar prompts de inicio como:

> *"Utiliza el contexto de `BLACK_KNIGHT_CONTEXT.md` para entender el ecosistema de Black Knight. A partir de ahora, todo código de frontend que te pida debe respetar Next.js 16 (React 19), TailwindCSS v4 con la paleta Cronos-Obsidian HSL y las dependencias descritas. Si te pido optimizaciones financieras del backend, utiliza los modelos definidos en `models.py` y las fórmulas de riesgo cuantitativo."*

---
*   **Versión del Contexto:** 2.0.0
*   **Última Actualización del Repositorio:** Junio 2, 2026
*   **Estado de Sincronización:** Listo para producción 
*   **Dashboard Local verificado:** Backend (8080)  + Frontend (3000)  + Outbox Agent 
