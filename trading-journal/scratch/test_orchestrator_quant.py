import sys
import os
import pandas as pd
import numpy as np

#Inject paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "backend"))

#Import master_orchestrator modules
sys.path.insert(0, os.path.join(BASE_DIR, "backend", "bloomberg"))

import logging
logging.basicConfig(level=logging.INFO)

from master_orchestrator import scoped_import

SystemicUniverseAdapter = scoped_import("collector-service", "app.fetchers", "SystemicUniverseAdapter")
TopologyEngine = scoped_import("../Correlaciones", "TopologyEngine", "TopologyEngine")

print("SystemicUniverseAdapter:", SystemicUniverseAdapter)
print("TopologyEngine:", TopologyEngine)

if SystemicUniverseAdapter:
    print("Fetching systemic returns...")
    systemic_data = SystemicUniverseAdapter.fetch_returns(days=120)
    print("Status:", systemic_data.get("status"))
    df_returns = systemic_data["df"]
    print("Returns shape:", df_returns.shape)
    print("Assets:", systemic_data.get("assets"))
    
    if len(df_returns) >= 60 and len(systemic_data.get("assets", [])) > 0:
        from sklearn.covariance import LedoitWolf
        df_base = df_returns.iloc[:60]
        df_curr = df_returns.iloc[60:]
        
        print("Fitting Ledoit-Wolf...")
        lw_base = LedoitWolf().fit(df_base)
        cov_base = lw_base.covariance_
        
        lw_curr = LedoitWolf().fit(df_curr)
        cov_curr = lw_curr.covariance_
        
        std_curr = np.sqrt(np.diag(cov_curr))
        corr_curr = cov_curr / np.outer(std_curr, std_curr)
        
        H = np.zeros((1, len(df_returns.columns), len(df_returns.columns)))
        R = np.zeros((1, len(df_returns.columns), len(df_returns.columns)))
        H[0] = cov_curr
        R[0] = corr_curr
        
        from datetime import datetime
        dates_dummy = pd.Index([datetime.now().date()])
        
        if TopologyEngine:
            print("Running TopologyEngine...")
            try:
                t_engine = TopologyEngine(H, R, list(df_returns.columns), dates_dummy)
                df_spect = t_engine.compute_spectral_features(k=3)
                df_dist = t_engine.compute_kld_and_frobenius(stable_window=cov_base)
                df_net = t_engine.compute_network_features()
                
                lambda_dominant = float(df_spect["lambda_dominant"].iloc[0])
                entropy_spectral = float(df_spect["entropy_spectral"].iloc[0])
                kld = float(df_dist["kld"].iloc[0])
                mtl = float(df_net["mtl"].iloc[0])
                
                print(f"SUCCESS: lambda_dominant={lambda_dominant}, entropy={entropy_spectral}, KLD={kld}, MTL={mtl}")
            except Exception as e:
                import traceback
                traceback.print_exc()
        else:
            print("TopologyEngine is None!")
    else:
        print("Data conditions not met!")
else:
    print("SystemicUniverseAdapter is None!")
