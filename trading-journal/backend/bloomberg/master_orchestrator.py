import time
import json
import redis
import requests
import logging
import asyncio
import sys
import os
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

#Scoped Path Injection logic to import from sub-services directly
def scoped_import(service_name, module_path, obj_name):
    # Clear "app" modules from cache to avoid namespace collisions between microservices
    for key in list(sys.modules.keys()):
        if key == "app" or key.startswith("app."):
            del sys.modules[key]
            
    path = os.path.join(BASE_DIR, service_name)
    if path not in sys.path:
        sys.path.insert(0, path)
    try:
        # Use importlib for cleaner dynamic imports if needed, but __import__ works here
        mod = __import__(module_path, fromlist=[obj_name])
        return getattr(mod, obj_name)
    except Exception as e:
        import traceback
        traceback.print_exc()
        logging.error(f"Failed to import {obj_name} from {service_name}: {e}")
        return None
    finally:
        if path in sys.path:
            sys.path.remove(path)

#Direct Imports (Bypassing HTTP microservices for Render stability)
gather_all_sources = scoped_import("collector-service", "app.fetchers", "gather_all_sources")
fetch_prices = scoped_import("collector-service", "app.fetchers", "fetch_prices")
fetch_ticker_bar = scoped_import("collector-service", "app.fetchers", "fetch_ticker_bar")
fetch_historical_features = scoped_import("collector-service", "app.fetchers", "fetch_historical_features")
fetch_historical_returns = scoped_import("collector-service", "app.fetchers", "fetch_historical_returns")
HybridPreprocessor = scoped_import("collector-service", "app.preprocessor", "HybridPreprocessor")

run_swarm = scoped_import("mirofish", "app.main", "run_swarm")

QuantEngine = scoped_import("quant-service", "app.predict", "DecisionEngine")
PredictionRequest = scoped_import("quant-service", "app.schemas", "PredictionRequest")
SystemicUniverseAdapter = scoped_import("collector-service", "app.fetchers", "SystemicUniverseAdapter")


run_decision_engine = scoped_import("decision-engine", "app.engine", "run_decision_engine")
TopologyEngine = scoped_import("../Correlaciones", "TopologyEngine", "TopologyEngine")

import pandas as pd
import numpy as np
from sklearn.covariance import LedoitWolf
import joblib
import pickle

#Configuración
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [MASTER] - %(levelname)s - %(message)s')
BK_API_URL = os.getenv("BK_API_URL", "http://localhost:8080")
SENTINEL_TOKEN = os.getenv("BK_SENTINEL_INTERNAL_TOKEN") or os.getenv("BK_HMAC_SECRET") or ""

def _internal_headers():
    return {"X-Sentinel-Token": SENTINEL_TOKEN} if SENTINEL_TOKEN else {}

def get_top_correlations(corr_matrix, assets, num=5):
    pairs = []
    N = len(assets)
    for i in range(N):
        for j in range(i + 1, N):
            pairs.append(((assets[i], assets[j]), float(corr_matrix[i, j])))
    pairs.sort(key=lambda x: x[1])
    top_lowest = [{"asset_a": p[0][0], "asset_b": p[0][1], "corr": round(p[1], 4)} for p in pairs[:num]]
    top_highest = [{"asset_a": p[0][0], "asset_b": p[0][1], "corr": round(p[1], 4)} for p in pairs[-num:][::-1]]
    return top_highest, top_lowest


def build_integrated_brief(context, quant, decision, topology, narrative=None):
    """Build a deterministic operational brief when the external LLM is unavailable."""
    stress = float(quant.get("stress_probability_t5", 0.0) or 0.0)
    regimes = quant.get("regime_probabilities", {}) or {}
    dominant_regime = max(regimes, key=regimes.get) if regimes else "unavailable"
    events = (context or {}).get("events", [])
    released = [event for event in events if event.get("status") == "released" and float(event.get("impact_score") or 0) >= 5]
    upcoming = [event for event in events if event.get("status") == "scheduled" and float(event.get("impact_score") or 0) >= 5]
    next_event = upcoming[0] if upcoming else None
    weights = decision.get("weights", {}) or {"CASH": 1.0}
    allocation = ", ".join(f"{asset} {float(weight) * 100:.0f}%" for asset, weight in weights.items())
    coupling = float(topology.get("lambda_dominant", 0.0) or 0.0)
    data_status = topology.get("data_status", "unavailable")
    parts = [
        f"Riesgo de crisis a 5 minutos: {stress * 100:.1f}% con regimen dominante {dominant_regime}.",
        f"Acoplamiento sistemico lambda {coupling:.2f}; datos de mercado {data_status}.",
        f"Asignacion sombra: {allocation}.",
    ]
    if released:
        parts.append(f"Catalizadores publicados de impacto: {', '.join(event.get('title', 'Evento') for event in released[:3])}.")
    if next_event:
        parts.append(f"Proximo catalizador: {next_event.get('title', 'Evento')} ({next_event.get('currency', 'N/D')}).")
    if narrative:
        parts.append(str(narrative).strip())
    return " ".join(parts)

def fetch_canonical_context(account_login=None, server_name=None):
    try:
        params = {}
        if account_login:
            params["account_login"] = account_login
        if server_name:
            params["server_name"] = server_name
        response = requests.get(
            f"{BK_API_URL}/api/v1/sentinel/context",
            params=params,
            headers=_internal_headers(),
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        logging.error(f"No se pudo obtener SentinelContext: {exc}")
        return None

#Redis / MockRedis
try:
    REDIS_CLIENT = redis.Redis(host=os.getenv("REDIS_HOST", "localhost"), port=int(os.getenv("REDIS_PORT", 6380)), decode_responses=True)
    REDIS_CLIENT.ping()
except Exception:
    logging.warning("Redis no disponible. Usando memoria local (MockRedis).")
    class MockRedis:
        def __init__(self): self.data = {}
        def get(self, k): return self.data.get(k)
        def set(self, k, v, *args, **kwargs): self.data[k] = v
        def setex(self, k, t, v): self.data[k] = v
        def exists(self, k): return k in self.data
        def delete(self, k): self.data.pop(k, None)
        def lpush(self, k, v): pass
        def ltrim(self, k, s, e): pass
        def ping(self): return True
    REDIS_CLIENT = MockRedis()

#Inicializar Engine Cuántico (Carga de modelos .pkl)
def init_quant_engine():
    models_dir = os.path.join(BASE_DIR, "quant-service", "models")
    try:
        scaler_params = joblib.load(os.path.join(models_dir, "scaler_params.pkl"))
        xgb_model = joblib.load(os.path.join(models_dir, "xgb.pkl"))
        with open(os.path.join(models_dir, "hmm.pkl"), "rb") as f:
            hmm_model = pickle.load(f)
        hmm_prior = joblib.load(os.path.join(models_dir, "hmm_prior.pkl"))
        pca_loadings = joblib.load(os.path.join(models_dir, "pca_loadings.pkl"))
        
        return QuantEngine(
            xgb_model=xgb_model,
            hmm_model=hmm_model,
            hmm_prior=hmm_prior,
            scaler_params=scaler_params,
            pca_loadings=pca_loadings
        )
    except Exception as e:
        logging.error(f"Error cargando modelos HMM/XGB: {e}")
        return None

quant_engine = init_quant_engine()
preprocessor = HybridPreprocessor() if HybridPreprocessor else None
LAST_CALIBRATION_DATE = None

async def calibrate_engine():
    """Ejecuta la recalibración ligera del HMM."""
    global LAST_CALIBRATION_DATE
    logging.info("Iniciando recalibración del motor HMM...")
    try:
        hist_df = fetch_historical_features(period="2y")
        if not hist_df.empty:
            res = quant_engine.calibrate(hist_df)
            if res["status"] == "success":
                LAST_CALIBRATION_DATE = datetime.now()
                logging.info(f"Recalibración exitosa: {res['message']}")
            else:
                logging.warning(f"Fallo en recalibración: {res['message']}")
        else:
            logging.warning("No se pudo obtener data histórica para calibrar.")
    except Exception as e:
        logging.error(f"Error crítico en calibrate_engine: {e}")

async def run_cycle(account_login=None, server_name=None, run_narrative=True):
    import pandas as pd
    import numpy as np
    scope_label = account_login or "auto"
    logging.info(f"--- INICIANDO CICLO OPERATIVO (CUENTA {scope_label}) ---")
    global LAST_CALIBRATION_DATE
    
    # Verificación de recalibración (Cada 24 horas)
    now = datetime.now()
    auto_calibrate = os.getenv("BK_SENTINEL_AUTO_CALIBRATE", "false").strip().lower() in {"1", "true", "yes", "on"}
    if auto_calibrate and (LAST_CALIBRATION_DATE is None or (now - LAST_CALIBRATION_DATE).total_seconds() > 86400):
        await calibrate_engine()

    try:
        sentinel_context = fetch_canonical_context(account_login, server_name)
        context_id = sentinel_context.get("context_id") if sentinel_context else None
        context_health = sentinel_context.get("health_status", "degraded") if sentinel_context else "offline"
        account_context = sentinel_context.get("account") if sentinel_context else None

        # 1. INGESTA (Collector)
        logging.info("Paso 1: Ingesta de datos reales...")
        raw_feed = gather_all_sources() if gather_all_sources else []
        processed_feed = preprocessor.process(raw_feed) if preprocessor else []
        
        # 2. CUANTITATIVO (Inferencia Directa)
        logging.info("Paso 2: Inferencia de estrés HMM-XGBoost...")
        real_features = fetch_prices() if fetch_prices else {}
        
        # Recuperar estado bayesiano
        state_vector_str = REDIS_CLIENT.get("quant:state_vector")
        state_vector = json.loads(state_vector_str) if state_vector_str else [0.33, 0.33, 0.34]

        stress_prob = 0.0
        q_res_dict = {}
        xi = 0.0
        
        if quant_engine and PredictionRequest:
            try:
                quant_req = PredictionRequest(
                    features=real_features,
                    state_vector=state_vector,
                    timestamp=datetime.now(timezone.utc).isoformat()
                )
                q_res = quant_engine.predict(quant_req)
                q_res_dict = q_res.model_dump()
                REDIS_CLIENT.set("quant:latest", json.dumps(q_res_dict))
                REDIS_CLIENT.set("quant:state_vector", json.dumps(q_res_dict.get("state_vector", state_vector)))
            except Exception as quant_error:
                logging.error(f"Inferencia cuantitativa degradada: {quant_error}")
                cached_quant = REDIS_CLIENT.get("quant:latest")
                q_res_dict = json.loads(cached_quant) if cached_quant else {
                    "status": "fallback",
                    "regime_probabilities": {"low": state_vector[0], "transition": state_vector[1], "high": state_vector[2]},
                    "state_vector": state_vector,
                    "stress_probability_t5": state_vector[-1],
                    "confidence_score": 0.0,
                    "regime_entropy": 1.0,
                    "omega_quant": 1.0,
                    "model_health": {"status": "DEGRADED", "reason": str(quant_error)},
                }

            stress_prob = float(q_res_dict.get("stress_probability_t5", 0.0) or 0.0)
            try:
                s_vec = q_res_dict.get("state_vector", state_vector)
                means = quant_engine.hmm_model.means_.flatten()
                high_vol_idx = int(np.argsort(means)[-1])
                xi = float(s_vec[high_vol_idx])
            except Exception as hmm_err:
                logging.error(f"Error extracting xi from HMM: {hmm_err}")
        
        # 3. NARRATIVO (MiroFish Swarm)
        miro_res = None
        if run_swarm and run_narrative:
            logging.info(f"Paso 3: Ejecutando Enjambre MiroFish (Stress: {stress_prob:.2f})...")
            feed_to_send = sentinel_context or ({"data": processed_feed, "timestamp": datetime.now(timezone.utc).isoformat()} if processed_feed else "NO_CANONICAL_CONTEXT_AVAILABLE")
            try:
                miro_res = await asyncio.wait_for(run_swarm(feed_to_send), timeout=float(os.getenv("BK_MIROFISH_TIMEOUT_SECONDS", "20")))
            except asyncio.TimeoutError:
                logging.warning("MiroFish excedio el tiempo operativo; se usara sintesis local/cached.")
            except Exception as exc:
                logging.warning(f"MiroFish no disponible: {exc}")
            if miro_res:
                REDIS_CLIENT.setex("mirofish:latest", 3600, json.dumps(miro_res))
        if not miro_res and run_narrative:
            cached_miro = REDIS_CLIENT.get("mirofish:latest")
            try:
                miro_res = json.loads(cached_miro) if cached_miro else None
            except Exception:
                miro_res = None

        # 4. DECISIÓN (Black-Litterman) & RISK CALCULATION
        logging.info("Paso 4: Calculando métricas espectrales y optimizando pesos...")
        nav_fallback = account_context is None or account_context.get("equity") is None
        nav = float(account_context.get("equity")) if not nav_fallback else float(REDIS_CLIENT.get("portfolio:nav") or 5000.0)
        scope_key = str((sentinel_context.get("scope") or {}).get("account_login") or "global") if sentinel_context else "global"
        weights_key = f"portfolio:weights:{scope_key}"
        decision_key = f"decision:latest:{scope_key}"
        old_weights = json.loads(REDIS_CLIENT.get(weights_key) or '{"CASH": 1.0}')

        # Dynamic risk calculations via SystemicUniverseAdapter
        lambda_dominant = 0.0
        entropy_spectral = 0.0
        kld = 0.0
        mtl = 0.0
        top_highest_corr = []
        top_lowest_corr = []
        dataset_hash = None
        systemic_data = None
        universe_version = "2.0-systemic-eod"
        pct_imputed = None
        cobertura = 0.0

        try:
            if SystemicUniverseAdapter:
                systemic_data = SystemicUniverseAdapter.fetch_returns(days=120)
                if systemic_data and systemic_data.get("status") != "error":
                    df_returns = systemic_data["df"]
                    dataset_hash = systemic_data.get("dataset_hash")
                    universe_version = systemic_data.get("universe_version", "1.0-systemic")
                    pct_imputed = float(systemic_data.get("pct_imputed", 0.0))
                    cobertura = float(systemic_data.get("cobertura", 100.0))
                    assets = systemic_data.get("assets", [])
                    
                    if len(df_returns) >= 60 and len(assets) > 0:
                        # Split: base window (0 to 60) and current window (60 to 120)
                        df_base = df_returns.iloc[:60]
                        df_curr = df_returns.iloc[60:]
                        
                        # Fit Ledoit-Wolf
                        lw_base = LedoitWolf().fit(df_base)
                        cov_base = lw_base.covariance_
                        
                        lw_curr = LedoitWolf().fit(df_curr)
                        cov_curr = lw_curr.covariance_
                        
                        std_curr = np.sqrt(np.diag(cov_curr))
                        corr_curr = cov_curr / np.outer(std_curr, std_curr)
                        
                        # 3D Tensors for TopologyEngine
                        H = np.zeros((1, len(assets), len(assets)))
                        R = np.zeros((1, len(assets), len(assets)))
                        H[0] = cov_curr
                        R[0] = corr_curr
                        
                        dates_dummy = pd.Index([datetime.now().date()])
                        
                        if TopologyEngine:
                            t_engine = TopologyEngine(H, R, assets, dates_dummy)
                            df_spect = t_engine.compute_spectral_features(k=3)
                            df_dist = t_engine.compute_kld_and_frobenius(stable_window=cov_base)
                            df_net = t_engine.compute_network_features()
                            
                            lambda_dominant = float(df_spect["lambda_dominant"].iloc[0])
                            entropy_spectral = float(df_spect["entropy_spectral"].iloc[0])
                            kld = float(df_dist["kld"].iloc[0])
                            mtl = float(df_net["mtl"].iloc[0])
                            
                            top_highest_corr, top_lowest_corr = get_top_correlations(corr_curr, assets)
                            logging.info(f"Spectral features calculated: lambda_dominant={lambda_dominant:.4f}, entropy={entropy_spectral:.4f}, KLD={kld:.4f}")
        except Exception as risk_err:
            logging.error(f"Error computing dynamic risk metrics: {risk_err}", exc_info=True)

        # MT5 stale checks
        is_mt5_stale = (context_health in ("stale", "offline")) or (sentinel_context is None)
        positions = sentinel_context.get("positions", []) if sentinel_context else []
        portfolio_limits = sentinel_context.get("portfolio_limits") if sentinel_context else None
        
        margin = float(account_context.get("margin") or 0.0) if account_context else 0.0
        equity = float(account_context.get("equity") or 0.0) if account_context else 0.0
        margin_risk = margin / equity if equity > 0.0 else 0.0

        hist_df = fetch_historical_returns() if fetch_historical_returns else None

        d_res_dict = {}
        if run_decision_engine:
            d_res_dict = run_decision_engine(
                current_nav=nav,
                quant_output=q_res_dict,
                mirofish_output=miro_res,
                old_weights=old_weights,
                market_state="normal" if stress_prob < 0.5 else "stressed",
                historical_returns_df=hist_df,
                redis_client=REDIS_CLIENT,
                is_mt5_stale=is_mt5_stale,
                positions=positions,
                margin_risk=margin_risk,
                portfolio_limits=portfolio_limits
            )
            REDIS_CLIENT.set(decision_key, json.dumps(d_res_dict))
            if "weights" in d_res_dict:
                REDIS_CLIENT.set(weights_key, json.dumps(d_res_dict["weights"]))

        topology_summary = {
            "lambda_dominant": lambda_dominant,
            "entropy_spectral": entropy_spectral,
            "mtl": mtl,
            "kld": kld,
            "data_status": systemic_data.get("data_status", "unavailable") if systemic_data else "unavailable",
        }
        integrated_narrative = build_integrated_brief(
            sentinel_context,
            q_res_dict,
            d_res_dict,
            topology_summary,
            miro_res.get("reasoning", miro_res.get("narrative")) if miro_res else None,
        )

        # 5. PUSH A LA API SaaS
        logging.info("Paso 5: Sincronizando con el Dashboard Cloud...")
        
        payload = {
            "stress_prob": stress_prob,
            "narrative": integrated_narrative,
            "weights": d_res_dict.get("weights", {}),
            "entropy": entropy_spectral if entropy_spectral > 0 else q_res_dict.get("regime_entropy", 0.42),
            "confidence": miro_res.get("confidence", q_res_dict.get("confidence_score", 0.0)) if miro_res else q_res_dict.get("confidence_score", 0.0),
            "dominant_theme": miro_res.get("dominant_theme", "Stability") if miro_res else "Neutral",
            "xi": xi,
            "lambda_dominant": lambda_dominant,
            "entropy_spectral": entropy_spectral,
            "mtl": mtl,
            "kld": kld,
            "top_highest_corr": top_highest_corr,
            "top_lowest_corr": top_lowest_corr,
            "context_id": context_id,
            "health_status": "stale" if is_mt5_stale else ("degraded" if nav_fallback or context_health != "healthy" else "healthy"),
            "source_health": sentinel_context.get("source_health", {}) if sentinel_context else {},
            "model_version": q_res_dict.get("model_version"),
            "feature_version": q_res_dict.get("feature_version"),
            "account_login": (sentinel_context.get("scope") or {}).get("account_login") if sentinel_context else None,
            "server_name": (sentinel_context.get("scope") or {}).get("server_name") if sentinel_context else None,
            "fallback_active": bool(nav_fallback or d_res_dict.get("fallback_active", False) or not sentinel_context),
            "quant_prediction": {
                "prediction_id": f"{context_id or 'no-context'}-{int(datetime.now(timezone.utc).timestamp())}",
                "horizon_minutes": 5,
                "regime_probabilities": q_res_dict.get("regime_probabilities", {}),
                "model_health": q_res_dict.get("model_health", {}),
            },
            # Reproducibility & data quality metadata
            "universe_version": universe_version,
            "dataset_hash": dataset_hash,
            "pct_imputed": pct_imputed,
            "data_coverage": cobertura,
            "data_provider": systemic_data.get("provider") if systemic_data else None,
            "data_frequency": systemic_data.get("frequency") if systemic_data else None,
            "observations": systemic_data.get("observations") if systemic_data else None,
            "data_status": systemic_data.get("data_status", "unavailable") if systemic_data else "unavailable",
            "decision": d_res_dict,
            "stress_tests": d_res_dict.get("stress_tests", {}),
            "shadow_mode": True,
            "approval_status": d_res_dict.get("approval_status", "pending"),
            "alternative_scenario": miro_res.get("alternative_scenario") if miro_res else None,
            "invalidation_conditions": miro_res.get("invalidation_conditions") if miro_res else None,
            "evidence": json.dumps(miro_res.get("evidence")) if miro_res and not isinstance(miro_res.get("evidence"), str) else (miro_res.get("evidence") if miro_res else None),
            "account_implications": miro_res.get("account_implications") if miro_res else None,
            # MiroFish LLM Metadata
            "llm_model": miro_res.get("llm_model") if miro_res else None,
            "prompt_version": miro_res.get("prompt_version") if miro_res else None,
            "context_sent": miro_res.get("context_sent") if miro_res else None,
            "sources_used": miro_res.get("sources_used") if miro_res else None,
            "api_latency_ms": miro_res.get("api_latency_ms") if miro_res else None,
            "call_cost_usd": miro_res.get("call_cost_usd") if miro_res else None,
            "prompt_hash": miro_res.get("prompt_hash") if miro_res else None,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        try:
            # Autenticación interna para actualizar el dashboard
            requests.post(f"{BK_API_URL}/api/v1/bloomberg/update", json=payload, headers=_internal_headers(), timeout=10).raise_for_status()
            logging.info("Sincronización exitosa con el Terminal.")
        except Exception as e:
            logging.error(f"Error sincronizando con API: {e}")

    except Exception as e:
        logging.error("ERROR CRÍTICO EN EL CICLO OPERATIVO", exc_info=True)

async def main():
    logging.info("SENTINEL ORCHESTRATOR INICIADO (CLOUD-NATIVE MODE)")
    while True:
        try:
            response = requests.get(f"{BK_API_URL}/api/v1/accounts", timeout=10)
            response.raise_for_status()
            scopes = [
                (row.get("account_login"), row.get("server_name"))
                for row in response.json()
                if row.get("account_login")
            ]
        except Exception as exc:
            logging.warning(f"No se pudieron enumerar cuentas Sentinel: {exc}")
            scopes = [(None, None)]

        if not scopes:
            scopes = [(None, None)]

        for index, (account_login, server_name) in enumerate(scopes):
            # Run the costly narrative swarm once per round. The remaining
            # accounts still receive deterministic account-scoped synthesis.
            await run_cycle(account_login, server_name, run_narrative=index == 0)

        logging.info(f"Ronda completada para {len(scopes)} cuenta(s). Esperando 60 segundos...")
        await asyncio.sleep(60)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Sentinel detenido.")
