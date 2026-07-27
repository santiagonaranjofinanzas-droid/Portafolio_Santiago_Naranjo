#Plan Maestro Arquitectónico Definitivo: Sistema de Gestión Híbrido (Quant + Narrativa)

Este plan maestro documenta la arquitectura de grado institucional para el Decision Engine. Esta versión final incluye los contratos de API a nivel de producción, parametrización de variables libres, mecanismos estrictos de auditoría de datos y una política de Fallback dinámica orientada al contexto (Context-Aware Safe Mode).

---

##1. Roadmap Modular y Mapa de Dependencias

###Mapa de Dependencias Arquitectónicas
```mermaid
graph TD
    A[FUENTES EXTERNAS<br>NewsAPI, Reddit, FRED] -->raw_feed B[FASE 2: Collector Service<br>Redis Buffer]
    B -->processed_feed C[FASE 4: MiroFish<br>Enjambre LLM]
    B -->feature_data D[FASE 1: Quant Service<br>HMM-XGBoost]
    C -->JSON: R_narr E[FASE 3: Decision Engine<br>Fusión + B-L]
    D -->JSON: stress_prob E
    E --> F[FASE 5: Dashboard UI]
```
*Dependencia Crítica:* La Fase 3 (Decision Engine) depende estrictamente de las salidas de la Fase 1 y Fase 2. La Fase 4 (MiroFish) puede construirse en paralelo a la Fase 3, pues su interfaz es un JSON con contrato ya definido.

###FASE 1: Core Cuantitativo (Microservicio de Producción)
*   **Objetivo:** Exponer el motor HMM-XGBoost como un microservicio escalable e independiente, con protecciones de integridad y monitoreo.
*   **Endpoints de Producción:**
    1.  `POST /predict` (Inferencia online en vivo).
    2.  `POST /predict-batch` (Para backtesting y recalibración masiva).
    3.  `GET /health` (Estado de la infraestructura).
    4.  `GET /model-info` (Metadata y versiones).
*   **Reglas de Input (Time Alignment & Normalization):**
    *   Solo aceptar datos con timestamp cerrado (vela confirmada).
    *   Rechazar datos parciales y validar orden temporal estricto.
    *   **Normalización Estricta:** Aplicar exactamente la misma winsorización y escalado Z-score (con $\mu$ y $\sigma$ fijos) usados en entrenamiento. Esto requiere serializar `scaler_params.pkl` junto al modelo.
*   **Contratos de Inferencia (`POST /predict`):**
    El microservicio es *stateless*, pero el HMM necesita el estado anterior. El cliente (scheduler) debe persistir el `state_vector` y enviarlo en cada petición.
    **INPUT:**
    ```json
    {
      "features": { "isri": 0.73, "vol_20d": 0.18, "ret_5d": 0.021 },
      "state_vector": [0.62, 0.13, 0.25],
      "timestamp": "2026-04-27T10:00:00Z"
    }
    ```
    **OUTPUT:**
    ```json
    {
      "regime_probabilities": { "low": 0.58, "high": 0.17, "transition": 0.25 },
      "state_vector": [0.58, 0.17, 0.25],
      "stress_probability_t5": 0.41,
      "confidence_score": 0.78,
      "regime_entropy": 0.52,
      "omega_quant": 0.31,
      "model_health": { 
          "psi": 0.05, 
          "kl_div": 0.02, 
          "status": "OK",
          "psi_trend": "STABLE"
      },
      "timestamp": "2026-04-27T10:00:00Z",
      "model_version": "v1.3.2",
      "feature_version": "fv_1.0.3",
      "inference_time_ms": 42
    }
    ```
    *Nota HMM:* Si el gap temporal entre inferencias es `> MAX_STATE_GAP_BARS` (ej. 3 velas), el scheduler reiniciará `state_vector` usando el prior estacionario del HMM (`hmm_prior.pkl`).
*   **Contrato Fallback (En caso de error crítico):**
    ```json
    {
      "status": "fallback",
      "reason": "model_error",
      "regime_probabilities": null
    }
    ```

###FASE 2: Data & Feature Engineering Centralizado
*   **Objetivo:** Memoria unificada (ISRI, volatilidades, retornos) usando TimescaleDB (frío) y Redis (caliente) para eliminar discrepancias.
*   **Ingesta Unificada (Collector Service):** Diseño de un servicio en background (`cron` cada 15-30 min) que consume fuentes macro y narrativas (APIs, Reddit, FRED) y nutre un pipeline de preprocesamiento (`raw_feed` $\to$ `processed_feed` en Redis con TTL). Así se garantiza que modelos Quant y Narrativos compartan la misma información fresca.

###FASE 3: El Decision Engine (Fusión, B-L y Constraints)
*   **Objetivo:** El traductor probabilístico a capital. Implementa Fusión Bayesiana Jerárquica y Black-Litterman Dinámico.

###FASE 4: El Acelerador Narrativo (MiroFish)
*   **Objetivo:** Orquestación de agentes LLM bajo triggers estrictos y decaimiento temporal.
*   **Pipeline de Enjambre (Swarm):** Los agentes (Macro, Sentimiento, Eventos) no consumen *raw data*, consumen el `processed_feed` de Redis. Sus outputs individuales convergen en un **Agente de Síntesis** que genera la convicción direccional ($R_{narr}$) y la incertidumbre ($\Omega_{narr}$, calculada como varianza entre agentes), protegiendo la ventana de contexto y el costo de inferencia.

###FASE 5: UI & Terminal Frontend (Dashboard Bloomberg)
*   **Objetivo:** Visualización operativa (Next.js), integrando un panel interno de **Auditoría Supervisada** y log de decisiones del algoritmo.

---

##2. Diseño Formal del Decision Engine (Resolución Matemática)

###2.1 Fusión Bayesiana Jerárquica (Quant vs Narrativa)
**Paso 1: Estructura Bayesiana (Peso Base)**
$$ w_{narr}^* = \frac{1/\Omega_{narr}}{1/\Omega_{narr} + 1/\Omega_{quant}} $$

**Paso 2: Comportamiento (Modulación de Asimetría)**
$$ w_{narr} = w_{narr}^* \cdot \left[ 0.15 + 0.25 \cdot \sigma\left(\frac{R_{narr} - R_{quant}}{\tau}\right) \right] $$
*Deuda Técnica:* $\tau = \text{std}(R_{quant} - R_{narr})$ calibrado sobre los últimos 252 días.

**Decaimiento Narrativo (Narrative Decay):**
$$ w_{narr}(t) = w_{narr}(0) \times e^{-\lambda t} $$
*Deuda Técnica:* Inicializar $\lambda = \ln(2)/3$ (vida media de 3 días), sujeto a calibración empírica.

###2.2 Black-Litterman: Escala de Convicción y Vistas Relativas
*   **Base:** Paridad de Riesgo (Risk Parity).
*   **Vistas ($Q$):** Retornos esperados relativos (ej. "QQQ superará al Oro en X%").
*   **Incertidumbre de las Vistas ($\Omega$):** $\Omega = f(\Omega_{quant}, \Omega_{narr})$. Altas entropías o PSI fuerzan una regresión a Risk Parity.

###2.3 Confidence $\to$ Capital Mapping (Con Límites)
$$ Exposure = \text{clip}\left(Base\_Exposure \times Confidence\_Score \times Regime\_Stability,\ E_{min},\ E_{max}\right) $$

---

##3. Portfolio Constraint Engine & Fail-Safes

###3.1 Cobertura Dinámica Protegida (Anti-Correlación)
*   **Regla:** El límite de XAU se expande a **70%** en estrés **SOLO SI** la correlación rodante de 20 días QQQ-XAU es *negativa*.
*   Si la correlación es positiva, el límite se mantiene en **40%** y el capital va a *Cash*.

###3.2 Filtro TCA (Churn Limit)
*   Operar **SOLO SI** $W_{new} - W_{old} > threshold$.

###3.3 Fail-Safe Escalonado (Max Drawdown)
*   **Drawdown $-5\%$:** Reducción del 30% de la exposición.
*   **Drawdown $-8\%$:** Reducción del 70% de la exposición.
*   **Drawdown $-10\%$:** Halt (liquidación total).
*   **Cooldown:** Bloqueo de reentradas por `COOLDOWN_BARS = 2` tras alertas críticas.

###3.4 Fallback Policy (Context-Aware Safe Mode)
Si el microservicio HMM-XGBoost colapsa (devuelve `regime_probabilities: null`), el sistema no debe hacer "crash" silencioso ni reaccionar con pánico ciego. Se adopta la configuración `FALLBACK_POLICY = CONTEXT_AWARE_SAFE_MODE`.
El Decision Engine leerá el *market_state* desde fuentes externas puramente estadísticas (ej. VIX, volatilidad rodante de 20 días, retornos crudos):
*   **Si `market_state == "calm"` $\to$ `HOLD_AND_ALERT`:** No rebalancear, mantener pesos, enviar alerta.
*   **Si `market_state == "uncertain"` $\to$ `REDUCE_EXPOSURE_20`:** Reducir exposición entre 10% y 30%, bloquear nuevas entradas.
*   **Si `market_state == "stress"` $\to$ `MOVE_TO_SAFE_BASE`:** Mover todo el capital a Risk Parity o Cash y cancelar todas las señales activas.
*   **Fallback Timeout:** Si `fallback_duration > X`, se escala automáticamente a `SAFE_MODE` (un fallo prolongado equivale a riesgo estructural).
*   **Registro Obligatorio:** Todo evento de fallback se guarda en el log:
    ```json
    { "event": "fallback_triggered", "reason": "model_error", "market_state": "stress", "action_taken": "MOVE_TO_SAFE_BASE", "timestamp": "..." }
    ```

---

##4. Orquestación y Prevención de Degradación

###4.1 Trigger de MiroFish Adaptativo
Activo si la probabilidad de estrés supera el **percentil 75 histórico** (ventana rodante de 252 días).

###4.2 Monitor de Degradación de Modelo (PSI Gradual)
Divergencia progresiva de KL/PSI eleva $\Omega_{quant}$, reduciendo la exposición al modelo y migrando suavemente al benchmark pasivo.

---

##5. Arquitectura de Ingesta de Datos (Collector & Enjambre)

La calidad de $R_{narr}$ y $\Omega_{narr}$ depende estrictamente del pipeline de ingesta. Para evitar saturación de contexto y altos costos, la arquitectura se divide en tres capas asíncronas:

###Capa 1: Fuentes de Información
*   **Sentimiento (Retail/Corto plazo):** Reddit (Pushshift API para r/investing, r/wallstreetbets), StockTwits, X/Twitter, Fear & Greed Index.
*   **Estructural (Macro):** NewsAPI / GDELT (tiempo real), FRED (Tasas, CPI), SEC EDGAR (institucional) y Scraping de calendarios económicos.

###Capa 2: Pipeline de Ingesta (El *Collector Service*)
Este servicio se diseña en **Fase 2** y corre en background de forma independiente a los LLMs:
1.  **Collector Service:** `Cron` de 15-30 min extrae data bruta hacia el buffer `raw_feed` (Redis, TTL=2h).
2.  **Preprocessor (Scoring de Relevancia Híbrido):** Deduplica, limpia y aplica un filtro por capas para equilibrar costo y latencia (*Deuda Técnica documentada*):
    *   **Capa A (Keywords):** Filtro determinista ultra-rápido (ej. "QQQ", "Fed", "CPI") que descarta el 80% del ruido sin costo de cómputo.
    *   **Capa B (Embeddings):** Solo las noticias que superan la Capa A pasan a un modelo de *embeddings* locales para validar relevancia semántica fina (evitando falsos positivos del lenguaje indirecto).
3.  **Processed Feed:** Envía los datos listos al buffer `processed_feed` en Redis con un score de frescura. Data obsoleta (ej. > `MAX_FEED_AGE_HOURS=4`) es rechazada.

###Capa 3: El Enjambre LLM y Síntesis Final
Activado solo cuando la probabilidad de estrés supera el percentil 75. 
*   **Agentes de Contexto:** Agentes paralelos independientes leen el `processed_feed` para sus dominios: Agente de Noticias Macro, Agente de Sentimiento Social, y Agente de Eventos de Riesgo.
*   **Agente de Síntesis (El único que habla con el Decision Engine):** 
    Recibe los resúmenes de los Agentes de Contexto (evitando la saturación por artículos crudos) y emite un payload final JSON.
    *   $\Omega_{narr}$ es orgánicamente la varianza/desacuerdo entre los agentes base.

**Ejemplo Output del Agente de Síntesis:**
```json
{
  "R_narr": -0.32,
  "omega_narr": 0.61,
  "dominant_theme": "fed_hawkish_surprise",
  "confidence": 0.74,
  "sources_used": 12,
  "timestamp": "..."
}
```
