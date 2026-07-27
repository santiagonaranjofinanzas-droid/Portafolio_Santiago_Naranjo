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

#Scoped Path Injection for sub-services to avoid collisions
def scoped_import(service_name, module_path, obj_name):
    # Clear "app" modules from cache to avoid namespace collisions between microservices
    for key in list(sys.modules.keys()):
        if key == "app" or key.startswith("app."):
            del sys.modules[key]
            
    path = os.path.join(BASE_DIR, service_name)
    sys.path.insert(0, path)
    try:
        mod = __import__(module_path, fromlist=[obj_name])
        return getattr(mod, obj_name)
    finally:
        sys.path.pop(0)

gather_all_sources = scoped_import("collector-service", "app.fetchers", "gather_all_sources")
fetch_prices = scoped_import("collector-service", "app.fetchers", "fetch_prices")
fetch_ticker_bar = scoped_import("collector-service", "app.fetchers", "fetch_ticker_bar")
fetch_historical_returns = scoped_import("collector-service", "app.fetchers", "fetch_historical_returns")
HybridPreprocessor = scoped_import("collector-service", "app.preprocessor", "HybridPreprocessor")

swarm_func = scoped_import("mirofish", "app.main", "run_swarm")

QuantEngine = scoped_import("quant-service", "app.predict", "DecisionEngine")
PredictionRequest = scoped_import("quant-service", "app.schemas", "PredictionRequest")

run_decision_engine = scoped_import("decision-engine", "app.engine", "run_decision_engine")

import joblib
import pickle

#Config
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [CLOUD-MASTER] - %(levelname)s - %(message)s')
BK_API_URL = os.getenv("BK_API_URL", "http://localhost:8080")
SENTINEL_TOKEN = os.getenv("BK_SENTINEL_INTERNAL_TOKEN") or os.getenv("BK_HMAC_SECRET") or ""

def _internal_headers():
    return {"X-Sentinel-Token": SENTINEL_TOKEN} if SENTINEL_TOKEN else {}

def fetch_canonical_context():
    try:
        response = requests.get(f"{BK_API_URL}/api/v1/sentinel/context", headers=_internal_headers(), timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        logging.error(f"No se pudo obtener SentinelContext: {exc}")
        return None

#Redis Mock
try:
    REDIS_CLIENT = redis.Redis(host=os.getenv("REDIS_HOST", "localhost"), port=int(os.getenv("REDIS_PORT", 6380)), decode_responses=True)
    REDIS_CLIENT.ping()
except Exception:
    logging.warning("Redis no disponible. Usando MockRedis.")
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

#Initialize Quant Engine
def init_quant_engine():
    models_dir = os.path.join(BASE_DIR, "quant-service", "models")
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

quant_engine = init_quant_engine()
preprocessor = HybridPreprocessor()

async def run_cycle():
    logging.info("--- INICIANDO CICLO OPERATIVO CLOUD ---")
    
    try:
        sentinel_context = fetch_canonical_context()
        # 1. INGESTA
        logging.info("Paso 1: Ingesta...")
        raw_feed = gather_all_sources()
        processed_feed = preprocessor.process(raw_feed)
        
        # 2. CUANTITATIVO (Directo)
        logging.info("Paso 2: Inferencia Cuántica...")
        real_features = fetch_prices()
        state_vector_str = REDIS_CLIENT.get("quant:state_vector")
        state_vector = json.loads(state_vector_str) if state_vector_str else [0.33, 0.33, 0.34]

        quant_req = PredictionRequest(
            features=real_features,
            state_vector=state_vector,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        q_res = quant_engine.predict(quant_req)
        q_res_dict = q_res.model_dump()
        
        REDIS_CLIENT.set("quant:state_vector", json.dumps(q_res_dict.get("state_vector", state_vector)))
        stress_prob = q_res_dict.get("stress_probability_t5", 0)
        
        # 3. NARRATIVO
        miro_res = None
        if stress_prob >= 0.0: # Always on for now
            logging.info(f"Paso 3: Activando MiroFish...")
            feed_to_send = sentinel_context or ({"data": processed_feed, "timestamp": datetime.now(timezone.utc).isoformat()} if processed_feed else "NO_CANONICAL_CONTEXT_AVAILABLE")
            miro_res = await swarm_func(feed_to_send)
            
        # 4. DECISIÓN (Directo)
        logging.info("Paso 4: Optimización de Portafolio...")
        account_context = sentinel_context.get("account") if sentinel_context else None
        nav_fallback = account_context is None or account_context.get("equity") is None
        nav = float(account_context.get("equity")) if not nav_fallback else float(REDIS_CLIENT.get("portfolio:nav") or 3000.0)
        old_weights = json.loads(REDIS_CLIENT.get("portfolio:weights") or '{"QQQ": 0.5, "GLD": 0.2, "CASH": 0.3}')
        
        hist_df = fetch_historical_returns()
        
        d_res = run_decision_engine(
            current_nav=nav,
            quant_output=q_res_dict,
            mirofish_output=miro_res,
            old_weights=old_weights,
            market_state="normal" if stress_prob < 0.5 else "stressed",
            historical_returns_df=hist_df,
            redis_client=REDIS_CLIENT
        )
        
        # 5. SYNC CLOUD
        logging.info("Paso 5: Sincronización con Dashboard...")
        payload = {
            "stress_prob": stress_prob,
            "narrative": miro_res.get("reasoning", miro_res.get("narrative", "Estabilidad detectada")) if miro_res else "Institutional Standby",
            "weights": d_res.get("weights", {}),
            "organization_id": 0,
            "context_id": sentinel_context.get("context_id") if sentinel_context else None,
            "health_status": "degraded" if nav_fallback or not sentinel_context else sentinel_context.get("health_status", "degraded"),
            "source_health": sentinel_context.get("source_health", {}) if sentinel_context else {},
            "model_version": q_res_dict.get("model_version"),
            "feature_version": q_res_dict.get("feature_version"),
            "account_login": (sentinel_context.get("scope") or {}).get("account_login") if sentinel_context else None,
            "server_name": (sentinel_context.get("scope") or {}).get("server_name") if sentinel_context else None,
            "fallback_active": bool(nav_fallback or not sentinel_context),
            "quant_prediction": {
                "prediction_id": f"{(sentinel_context or {}).get('context_id', 'no-context')}-{int(datetime.now(timezone.utc).timestamp())}",
                "horizon_minutes": 5,
                "regime_probabilities": q_res_dict.get("regime_probabilities", {}),
                "model_health": q_res_dict.get("model_health", {}),
            }
        }
        try:
            requests.post(f"{BK_API_URL}/api/v1/bloomberg/update", json=payload, headers=_internal_headers(), timeout=10).raise_for_status()
            logging.info("Sync OK.")
        except Exception as e:
            logging.error(f"Sync FAIL: {e}")

    except Exception as e:
        logging.error("ERROR EN EL CICLO CLOUD", exc_info=True)

async def main():
    while True:
        await run_cycle()
        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
