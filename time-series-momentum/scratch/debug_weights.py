import os
import sys
import torch
import pandas as pd
import numpy as np

#Set up paths
BASE_DIR = r"c:\Users\YOUR_USERNAME\Desktop\Trading\TSMOM\TSMOM_Bot"
sys.path.append(BASE_DIR)

from src.features import generar_features_tensor
from src.models.dmn import DeepMomentumNetwork

#Load model
lstm_path = os.path.join(BASE_DIR, "lstm_model_dynamic.pt")
features_list_ml = ["Z_21d", "Z_126d", "MACD_2", "xi_3"]
lstm_model = DeepMomentumNetwork(input_dim=1, num_features=len(features_list_ml), hidden_dim=64, use_attention=False)
lstm_model.load_state_dict(torch.load(lstm_path, map_location=torch.device('cpu')))
lstm_model.eval()

#Load SPX500 CSV
csv_path = os.path.join(BASE_DIR, "data", "SPX500.csv")
df = pd.read_csv(csv_path)
df["Date"] = pd.to_datetime(df["Date"])
df = df.sort_values("Date").reset_index(drop=True)

df, _ = generar_features_tensor(df)

print(f"SPX500 features on last 5 rows:")
print(df[["Date", "Close"] + features_list_ml].tail(5))

#Generate sequence for the last row
L_t = 126
seq = df[features_list_ml].tail(L_t).values
seq = np.nan_to_num(seq)

#Print a summary of the sequence (mean, std)
print(f"\nSequence shape: {seq.shape}")
print(f"Sequence means: {np.mean(seq, axis=0)}")
print(f"Sequence stds: {np.std(seq, axis=0)}")

#Run model prediction
t_seq = torch.tensor(seq, dtype=torch.float32).unsqueeze(0)
with torch.no_grad():
    pred = lstm_model(t_seq).item()

print(f"\nRaw model prediction: {pred:.6f}")
print(f"Prediction absolute value: {abs(pred):.6f}")
print(f"Would it survive Dead-Zone threshold (0.25)? {'YES' if abs(pred) >= 0.25 else 'NO'}")
