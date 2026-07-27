import asyncio
import json
import os
import sys
import requests
from datetime import datetime, timezone

#Setup paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
miro_dir = os.path.join(BASE_DIR, "backend", "bloomberg", "mirofish")
sys.path.insert(0, miro_dir)

from dotenv import load_dotenv
load_dotenv(os.path.join(miro_dir, ".env"))

from app.main import run_swarm

async def trigger_once():
    print("--- Starting Force Sync Cycle ---")
    
    # 1. Load advanced metrics from market_status.json
    market_status_path = os.path.join(BASE_DIR, "backend", "Correlaciones", "market_status.json")
    print(f"Reading study metrics from {market_status_path}...")
    if not os.path.exists(market_status_path):
        print(f"Error: {market_status_path} not found!")
        return
        
    with open(market_status_path, "r", encoding="utf-8") as f:
        study = json.load(f)
    print("Study loaded successfully.")
    
    # 2. Run Mirofish Swarm to generate narrative
    print("Calling Mirofish Swarm for market narrative...")
    # Feed the core metrics as context to Mirofish
    feed_context = (
        f"ESTUDIO DE VOLATILIDAD Y TDA:\n"
        f"Filtro TVTP-HMM (xi): {study.get('xi'):.6f}\n"
        f"Eigenvalue Dominante (lambda_max): {study.get('lambda_dominant'):.4f}\n"
        f"Entropía Espectral: {study.get('entropy_spectral'):.4f}\n"
        f"Longitud de Red (MTL): {study.get('mtl'):.4f}\n"
        f"Divergencia KLD: {study.get('kld'):.4f}\n"
        f"Estrés del MetaClasificador: {study.get('prob') * 100:.1f}%\n"
    )
    
    miro_res = await run_swarm(feed_context)
    if not miro_res:
        print("Warning: Mirofish Swarm returned None, using default narrative.")
        miro_res = {
            "narrative": "Transición de régimen bajo análisis cuantitativo. Estabilidad espectral y contracción topológica estables.",
            "dominant_theme": "Neutral",
            "confidence": 0.85
        }
    else:
        print("Mirofish Swarm generated narrative:")
        print(miro_res)
        
    # 3. Allocation Weights (Mock/Decision engine outputs)
    # Using study results to assign weights: if stress is high, weight gold/cash.
    stress_prob = study.get("prob", 0.39)
    if stress_prob > 0.5:
        weights = {"QQQ": 0.2, "GLD": 0.5, "CASH": 0.3}
    else:
        weights = {"QQQ": 0.5, "GLD": 0.2, "CASH": 0.3}
        
    # 4. Construct payload
    payload = {
        "organization_id": 0,
        "stress_prob": stress_prob,
        "narrative": miro_res.get("reasoning", miro_res.get("narrative", "")),
        "weights": weights,
        "entropy": study.get("entropy_spectral", 0.42),
        "confidence": miro_res.get("confidence", 0.85),
        "dominant_theme": miro_res.get("dominant_theme", "Stable"),
        "xi": study.get("xi", 0.0),
        "lambda_dominant": study.get("lambda_dominant", 0.0),
        "entropy_spectral": study.get("entropy_spectral", 0.0),
        "mtl": study.get("mtl", 0.0),
        "kld": study.get("kld", 0.0),
        "top_highest_corr": study.get("top_highest_corr", []),
        "top_lowest_corr": study.get("top_lowest_corr", []),
        "status": "online",
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    # 5. Push to API
    api_url = "http://localhost:8080/api/v1/bloomberg/update"
    print(f"Pushing payload to local API: {api_url}...")
    try:
        r = requests.post(api_url, json=payload, timeout=10)
        print(f"API Response: {r.status_code} - {r.json()}")
    except Exception as e:
        print(f"API request failed: {e}")

if __name__ == "__main__":
    asyncio.run(trigger_once())
