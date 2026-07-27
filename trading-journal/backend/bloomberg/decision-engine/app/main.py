import redis
import pandas as pd
import json
import logging
from fastapi import FastAPI, HTTPException
from app.schemas import DecisionRequest, DecisionResponse
from app.engine import run_decision_engine
from app.config import REDIS_HOST, REDIS_PORT

logging.basicConfig(level=logging.INFO)
app = FastAPI(title="Decision Engine API", version="1.0.0")

#Cliente Redis para persistencia de HWM y constraints
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

@app.post("/decide", response_model=DecisionResponse)
async def decide(request: DecisionRequest):
    try:
        # Convertir historical_returns_df si viene en JSON
        df_returns = None
        if request.historical_returns_df_json:
            df_returns = pd.read_json(request.historical_returns_df_json)

        # Ejecutar el motor central
        result = run_decision_engine(
            current_nav=request.current_nav,
            quant_output=request.quant_output,
            mirofish_output=request.mirofish_output,
            old_weights=request.old_weights,
            market_state=request.market_state,
            historical_r_quant=request.historical_r_quant,
            historical_r_narr=request.historical_r_narr,
            historical_returns_df=df_returns,
            redis_client=redis_client
        )
        
        return result
    except Exception as e:
        logging.error(f"Error en Decision Engine API: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health():
    try:
        connected = redis_client.ping()
    except Exception:
        connected = False
    return {"status": "ok", "redis_connected": connected}
