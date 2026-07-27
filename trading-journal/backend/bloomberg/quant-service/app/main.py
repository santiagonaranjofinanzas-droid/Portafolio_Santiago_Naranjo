import os
import joblib
import pickle
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.schemas import PredictionRequest, PredictionResponse, FallbackResponse
from app.predict import DecisionEngine
from app.health import router as health_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    models_dir = os.path.join(os.path.dirname(__file__), "..", "models")
    
    print("Cargando artefactos del modelo en memoria...")
    app.state.scaler_params = joblib.load(os.path.join(models_dir, "scaler_params.pkl"))
    app.state.xgb_model = joblib.load(os.path.join(models_dir, "xgb.pkl"))
    
    with open(os.path.join(models_dir, "hmm.pkl"), "rb") as f:
        app.state.hmm_model = pickle.load(f)
        
    app.state.hmm_prior = joblib.load(os.path.join(models_dir, "hmm_prior.pkl"))
    app.state.pca_loadings = joblib.load(os.path.join(models_dir, "pca_loadings.pkl"))

    # Inicializar el Decision Engine
    app.state.engine = DecisionEngine(
        xgb_model=app.state.xgb_model,
        hmm_model=app.state.hmm_model,
        hmm_prior=app.state.hmm_prior,
        scaler_params=app.state.scaler_params,
        pca_loadings=app.state.pca_loadings
    )
    print("Artefactos cargados y Engine inicializado con éxito.")
    
    yield

app = FastAPI(title="Quant Decision Engine API", version="1.0.0", lifespan=lifespan)

app.include_router(health_router)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    FALLBACK POLICY (Context-Aware Safe Mode):
    Si el microservicio HMM-XGBoost colapsa internamente, devuelve un nulo controlado
    en vez de crashear, para que el Decision Engine en Fase 3 active Safe Mode.
    """
    print(f"[CRITICAL ERROR] Fallback activado debido a: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content=FallbackResponse(
            status="fallback",
            reason=str(exc),
            regime_probabilities=None
        ).model_dump()
    )

@app.post("/predict", response_model=PredictionResponse)
def predict(request: PredictionRequest):
    start_time = time.time()
    
    # Ejecuta el engine. Cualquier excepción activará el fallback_handler
    response = app.state.engine.predict(request)
    
    response.inference_time_ms = int((time.time() - start_time) * 1000)
    return response

@app.post("/predict-batch")
def predict_batch():
    # Placeholder para recalibración masiva (Fase 1.b)
    return {"status": "not_implemented_yet"}
