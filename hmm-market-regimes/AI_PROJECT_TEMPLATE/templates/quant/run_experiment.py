import os
import json
import numpy as np
import pandas as pd
from quant_utils import initialize_random_seeds, calculate_financial_metrics, temporal_train_test_split

def load_config():
    config_path = "backtest_config.json"
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            return json.load(f)
    return {}

def main():
    # 1. Initialize random seeds for reproducibility
    config = load_config()
    seed = config.get("parameters", {}).get("random_seed", 42)
    initialize_random_seeds(seed)
    
    print(f"--- Running Quantitative Experiment: {config.get('backtest_name', 'Unnamed')} ---")
    
    # 2. Generate synthetic return data for demonstration
    # In a real scenario, you would load histdata from data/raw/
    n_days = 500
    dates = pd.date_range(end=pd.Timestamp.now(), periods=n_days)
    synthetic_returns = np.random.normal(loc=0.0003, scale=0.01, size=n_days) # mean 0.03%, std 1%
    df = pd.DataFrame(data={"returns": synthetic_returns}, index=dates)
    
    # 3. Chronological Train-Test Split (avoid data leakage)
    train_df, test_df = temporal_train_test_split(df, train_ratio=0.8)
    print(f"Dataset split: Train shape={train_df.shape}, Test shape={test_df.shape}")
    
    # 4. Evaluate Financial Metrics
    metrics = calculate_financial_metrics(test_df["returns"])
    
    print("\nTest Set Results:")
    for k, v in metrics.items():
        print(f"  {k.replace('_', ' ').title()}: {v:.4f}")
        
    # Save experiment metrics to experiments/
    os.makedirs("experiments", exist_ok=True)
    results_path = os.path.join("experiments", "latest_metrics.json")
    with open(results_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"\n[SUCCESS] Metrics saved to {results_path}")

if __name__ == "__main__":
    main()
