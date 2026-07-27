import sys
import os
import asyncio
import pandas as pd
import numpy as np

#Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend", "bloomberg"))

import master_orchestrator

#Mock functions to avoid external API calls
master_orchestrator.gather_all_sources = lambda: []
master_orchestrator.fetch_prices = lambda: {
    "OIL": 0.01,
    "USD": -0.005,
    "GOLD": 0.02,
    "SP500": 0.005,
    "BOND10Y": 0.001
}

#Mock run_swarm to avoid calling LLM
async def mock_run_swarm(feed_to_send):
    return {
        "narrative": "Swarm sees moderate volatility risk in macro landscape.",
        "confidence": 0.88,
        "dominant_theme": "Transition",
        "R_narr": 0.05,
        "omega_narr": 0.2
    }
master_orchestrator.run_swarm = mock_run_swarm

#Mock the API update request
import requests
def mock_post(url, *args, **kwargs):
    print(f"\n>>> [MOCK POST] url={url}")
    print(f">>> [MOCK POST] payload={kwargs.get('json')}")
    class Res:
        status_code = 200
        def json(self): return {"status": "success"}
    return Res()
requests.post = mock_post

async def main():
    print("Starting master_orchestrator.run_cycle()...")
    await master_orchestrator.run_cycle()
    print("Done!")

if __name__ == "__main__":
    asyncio.run(main())
