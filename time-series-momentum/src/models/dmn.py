import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import pandas as pd
from src.loss import e_var_softmin_loss
from src.models.markov import estimar_regimen_msssm

#Listas de tickers por categoría para cálculo de triple swaps
FX_TICKERS = ["EURUSD", "USDJPY", "GBPUSD", "AUDUSD", "USDCHF", "USDCAD"]
INDEX_TICKERS = ["SPX500", "NAS100", "DJI30", "GER30", "EU50", "UK100", "JPN225"]


#Variable Selection Network (VSN) using Gated Linear Units (GLU)
class GatedLinearUnit(nn.Module):
    def __init__(self, input_dim, output_dim):
        super(GatedLinearUnit, self).__init__()
        self.fc = nn.Linear(input_dim, output_dim * 2)
        
    def forward(self, x):
        # x shape: [Batch, Seq, Dim] or [Batch, Dim]
        out = self.fc(x)
        val, gate = torch.chunk(out, 2, dim=-1)
        return val * torch.sigmoid(gate)

class VSN(nn.Module):
    def __init__(self, input_dim, num_features, hidden_dim):
        super(VSN, self).__init__()
        self.num_features = num_features
        self.hidden_dim = hidden_dim
        
        # GLU for each individual feature
        self.feature_glu = nn.ModuleList([
            GatedLinearUnit(input_dim, hidden_dim) for _ in range(num_features)
        ])
        
        # Flattened VSN GLU for weighing features
        self.weight_fc = nn.Linear(input_dim * num_features, num_features)
        self.softmax = nn.Softmax(dim=-1)
        
    def forward(self, x):
        # x shape: [Batch, Seq, NumFeatures * InputDim] -> e.g. [Batch, L, 12 * 1]
        batch_size, seq_len, _ = x.shape
        
        # Split features
        feature_inputs = torch.chunk(x, self.num_features, dim=-1) # Tuple of 12 tensors of shape [Batch, Seq, 1]
        
        # Process each feature individual GLU
        feature_outputs = []
        for i in range(self.num_features):
            feat_out = self.feature_glu[i](feature_inputs[i]) # Shape: [Batch, Seq, hidden_dim]
            feature_outputs.append(feat_out)
            
        # Concat outputs for weight computation
        stacked_features = torch.stack(feature_outputs, dim=-2) # Shape: [Batch, Seq, NumFeatures, hidden_dim]
        
        # Compute weights
        flattened_x = x # Shape: [Batch, Seq, NumFeatures]
        weights = self.softmax(self.weight_fc(flattened_x)) # Shape: [Batch, Seq, NumFeatures]
        weights = weights.unsqueeze(-1) # Shape: [Batch, Seq, NumFeatures, 1]
        
        # Weighted sum of features
        weighted_out = torch.sum(weights * stacked_features, dim=-2) # Shape: [Batch, Seq, hidden_dim]
        return weighted_out

#Deep Momentum Network Class
class DeepMomentumNetwork(nn.Module):
    def __init__(self, input_dim=1, num_features=12, hidden_dim=64, use_attention=False):
        super(DeepMomentumNetwork, self).__init__()
        if use_attention:
            raise NotImplementedError("Capa 8 Attention has been completely dismantled and is no longer supported.")
        self.use_attention = False
        
        # 1. Feature selection (VSN)
        self.vsn = VSN(input_dim, num_features, hidden_dim)
        
        # 2. LSTM layer
        self.lstm = nn.LSTM(hidden_dim, hidden_dim, batch_first=True, num_layers=1)
        
        # 3. Output layer
        self.fc = nn.Linear(hidden_dim, 1)
        self.tanh = nn.Tanh()
        
    def forward(self, x):
        # x shape: [Batch, Seq, NumFeatures]
        # VSN expects features to be separate, here we pass shape [Batch, Seq, NumFeatures]
        vsn_out = self.vsn(x) # Shape: [Batch, Seq, hidden_dim]
        
        # LSTM forward pass
        lstm_out, _ = self.lstm(vsn_out) # Shape: [Batch, Seq, hidden_dim]
        
        # Output prediction (we take the last timestep prediction as the position signal)
        last_step_out = lstm_out[:, -1, :] # Shape: [Batch, hidden_dim]
        pred_signal = self.tanh(self.fc(last_step_out)) # Shape: [Batch, 1]
        
        return pred_signal.squeeze(-1)

#Training loop
def train_dmn_model(raw_data, tickers, features_list, start_date, end_date, use_attention=False, epochs=15):
    """
    Entrena el modelo DMN (LSTM) utilizando la pérdida unificada EVaR y Sharpe corregido de Bailey-López de Prado.
    """
    device = torch.device("cpu")
    model = DeepMomentumNetwork(input_dim=1, num_features=len(features_list), hidden_dim=64, use_attention=use_attention).to(device)
    optimizer = optim.Adam(model.parameters(), lr=0.001, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-5)
    
    # 1. Preparar las secuencias de datos para todos los activos
    print("Preparando secuencias temporales para el entrenamiento DMN...")
    
    # Queremos alinear todas las fechas
    # Obtenemos los dataframes recortados al rango [start_date, end_date]
    subset_data = {}
    for t in tickers:
        df = raw_data[t]
        subset = df.loc[start_date:end_date]
        if len(subset) > 126:
            subset_data[t] = subset
            
    if len(subset_data) == 0:
        return None
        
    dates_train = sorted(list(set().union(*[df.index for df in subset_data.values()])))
    L_max = 126  # lookback sequence length máximo
    
    # Crear lotes (batches) de entrenamiento por fechas
    # Para cada fecha t (empezando desde L_max), tomamos la secuencia de features de t-L_t+1 a t
    # para todos los activos activos en t, sus volatilidades, swaps y retornos en t+1
    epochs_data = []
    
    # Para acelerar, pre-armamos los tensores
    for i in range(L_max, len(dates_train) - 1):
        date_t = dates_train[i]
        date_next = dates_train[i + 1]
        
        # Calcular prob_crisis a partir del M-SSSM sectorial jerárquico
        prob_crisis = estimar_regimen_msssm(raw_data, tickers, date_t)
        L_t = 126
        
        active_assets = []
        for t in subset_data.keys():
            df = subset_data[t]
            if date_t in df.index and date_next in df.index:
                # Comprobar que toda la secuencia de L_t días exista en el índice
                date_idx = df.index.get_loc(date_t)
                if date_idx >= L_t - 1:
                    active_assets.append(t)
                    
        if len(active_assets) < 5:
            continue
            
        # Armar inputs
        features_batch = []
        vols_batch = []
        ret_batch = []
        spread_batch = []
        swap_long_batch = []
        swap_short_batch = []
        
        for t in active_assets:
            df = subset_data[t]
            idx_t = df.index.get_loc(date_t)
            
            # Secuencia de features de t-L_t+1 a t
            seq_features = df.iloc[idx_t - L_t + 1 : idx_t + 1][features_list].values
            seq_features = np.nan_to_num(seq_features, nan=0.0) # Robustez frente a NaNs iniciales
            # Fuzzy Gating: decaimiento lineal continuo para evitar discontinuidades
            L_seq = seq_features.shape[0]
            decay_len = L_seq - 21
            w_decay = np.ones((L_seq, 1))
            w_decay[:decay_len, 0] = (1.0 - prob_crisis) + prob_crisis * np.arange(decay_len) / decay_len
            seq_features = seq_features * w_decay
            features_batch.append(seq_features)
            
            # Volatilidad en t (ex-ante para t+1)
            vol = df.loc[date_t, "Vol_YZ_21"]
            if pd.isna(vol) or vol <= 0:
                vol = 0.15
            vol_diaria = vol / np.sqrt(252)
            vols_batch.append(vol_diaria)
            
            # Retorno del activo en t+1
            p_today = df.loc[date_next, "Close"]
            p_yesterday = df.loc[date_t, "Close"]
            if pd.isna(p_today) or pd.isna(p_yesterday) or p_yesterday <= 0:
                ret_asset = 0.0
            else:
                ret_asset = (p_today - p_yesterday) / p_yesterday
            ret_batch.append(ret_asset)
            
            # Fricciones en t
            spread = df.loc[date_t, "Spread"]
            spread = spread if not pd.isna(spread) else 0.0
            p_yesterday_val = p_yesterday if (not pd.isna(p_yesterday) and p_yesterday > 0) else 1.0
            spread_batch.append(spread / (2 * p_yesterday_val))
            
            swap_l = df.loc[date_t, "SwapLong"]
            swap_s = df.loc[date_t, "SwapShort"]
            swap_l = swap_l if not pd.isna(swap_l) else 0.0
            swap_s = swap_s if not pd.isna(swap_s) else 0.0
            swap_long_batch.append(swap_l)
            swap_short_batch.append(swap_s)
            
        # Convertir a tensores
        t_features = torch.tensor(np.array(features_batch), dtype=torch.float32) # [Assets, L_t, 12]
        t_vols = torch.tensor(np.array(vols_batch), dtype=torch.float32) # [Assets]
        t_ret = torch.tensor(np.array(ret_batch), dtype=torch.float32) # [Assets]
        t_spread = torch.tensor(np.array(spread_batch), dtype=torch.float32) # [Assets]
        t_swap_long = torch.tensor(np.array(swap_long_batch), dtype=torch.float32) # [Assets]
        t_swap_short = torch.tensor(np.array(swap_short_batch), dtype=torch.float32) # [Assets]
        
        # Guardar día de la semana de date_t para los swaps triples
        dayofweek = date_t.dayofweek
        
        epochs_data.append({
            "ticker_names": active_assets,
            "features": t_features,
            "vols": t_vols,
            "returns": t_ret,
            "spread_tc": t_spread,
            "swap_long": t_swap_long,
            "swap_short": t_swap_short,
            "dayofweek": dayofweek
        })
        
    if len(epochs_data) == 0:
        return None
        
    print(f"Total de secuencias de entrenamiento preparadas: {len(epochs_data)}")
    
    # Bucle de entrenamiento
    model.train()
    target_vol_efectivo = 0.40
    comm_rate = 0.00005
    slippage_rate = 0.00005
    batch_size = 64
    
    for epoch in range(epochs):
        prev_w = {}
        epoch_losses = []
        epoch_sharpes = []
        
        # Procesar en mini-lotes (batches de días) para evitar desbordamiento de memoria (bad allocation)
        for start_idx in range(0, len(epochs_data), batch_size):
            batch_data = epochs_data[start_idx : start_idx + batch_size]
            port_returns = []
            port_weights_list = []
            
            for step, data in enumerate(batch_data):
                features = data["features"] # Shape: [Assets, L, len(features_list)]
                predictions = model(features) # Shape: [Assets] (valores entre -1 y 1)
                
                # Sizing por volatilidad objetivo coordinada
                vols = data["vols"]
                ratios = torch.abs(predictions) / vols
                ratios_sum = torch.sum(ratios)
                denom = torch.clamp(ratios_sum, min=0.5)
                
                # Pesos de la cartera hoy (decisión en t)
                weights = (predictions / vols) * (target_vol_efectivo / denom)
                
                # Alinear pesos del día en el grid global de tickers para calcular la rotación en e_var_softmin_loss
                weights_aligned = torch.zeros(len(tickers), device=device)
                for j, ticker in enumerate(data["ticker_names"]):
                    ticker_idx = tickers.index(ticker)
                    weights_aligned[ticker_idx] = weights[j]
                port_weights_list.append(weights_aligned)
                
                # Calcular retornos del día de mañana (t+1)
                returns = data["returns"]
                gross_returns = weights * returns
                
                # Fricciones netas
                spread_tc = data["spread_tc"]
                tc_rates = spread_tc + comm_rate + slippage_rate
                
                # Costos de rebalanceo
                tc_costs = torch.zeros_like(weights)
                for j, ticker in enumerate(data["ticker_names"]):
                    w_prev = prev_w.get(ticker, torch.tensor(0.0, device=device))
                    w_curr = weights[j]
                    tc_costs[j] = torch.abs(w_curr - w_prev) * tc_rates[j]
                    # Detach para evitar retropropagar a lo largo de toda la historia
                    prev_w[ticker] = w_curr.detach()
                    
                # Costos de swap
                swap_long = data["swap_long"]
                swap_short = data["swap_short"]
                day = data["dayofweek"]
                
                # Multiplicador de swap triple
                m_mult = torch.ones_like(weights)
                for j, ticker in enumerate(data["ticker_names"]):
                    if ticker in FX_TICKERS and day == 2:
                        m_mult[j] = 3.0
                    elif ticker in INDEX_TICKERS and day == 4:
                        m_mult[j] = 3.0
                        
                swap_rates = torch.where(weights > 0, swap_long, swap_short)
                swap_costs = torch.abs(weights) * (swap_rates / 360.0) * m_mult
                
                # Retorno neto diario de la cartera hoy
                net_returns = gross_returns - tc_costs + swap_costs
                port_returns.append(torch.sum(net_returns))
                
            if len(port_returns) < 5:
                continue
                
            # Convertir lista de retornos diarios a tensor para el lote actual
            port_returns_tensor = torch.stack(port_returns)
            weights_tensor = torch.stack(port_weights_list) # [batch_size, len(tickers)]
            
            # Annealing de alpha progresivo: de 0.5 en época 0 a 2.0 en época final
            alpha_val = 0.5 + (1.5 * (epoch / epochs))
            
            # Pérdida EVaR unificada (Soft-Min Sharpe)
            loss = e_var_softmin_loss(
                port_returns_tensor, 
                window_size=30, 
                step_size=10, 
                alpha=alpha_val, 
                lambda_cost=2.5, 
                weights_history=weights_tensor
            )
            
            # Optimización por lote con gradiente recortado para evitar saturación/explosión
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            
            # Calcular Sharpe del lote solo para reportar progreso
            mean_ret = torch.mean(port_returns_tensor)
            std_ret = torch.std(port_returns_tensor)
            sharpe = (mean_ret / (std_ret + 1e-6)) * np.sqrt(252)
            
            epoch_losses.append(loss.item())
            epoch_sharpes.append(sharpe.item())
            
        scheduler.step()
        mean_loss = np.mean(epoch_losses) if len(epoch_losses) > 0 else 0.0
        mean_sharpe = np.mean(epoch_sharpes) if len(epoch_sharpes) > 0 else 0.0
        print(f"Época {epoch+1:02d}/{epochs:02d}  Loss Lote Promedio: {mean_loss:.4f}  Sharpe Neto Promedio: {mean_sharpe:.4f}")
        
    model.eval()
    return model
