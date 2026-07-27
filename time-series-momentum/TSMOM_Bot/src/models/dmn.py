import torch
import torch.nn as nn

#Gated Linear Unit (GLU)
class GatedLinearUnit(nn.Module):
    def __init__(self, input_dim, output_dim):
        super(GatedLinearUnit, self).__init__()
        self.fc = nn.Linear(input_dim, output_dim * 2)
        
    def forward(self, x):
        # x shape: [Batch, Seq, Dim] or [Batch, Dim]
        out = self.fc(x)
        val, gate = torch.chunk(out, 2, dim=-1)
        return val * torch.sigmoid(gate)

#Variable Selection Network (VSN)
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
        # x shape: [Batch, Seq, NumFeatures * InputDim] -> e.g. [Batch, L, 4 * 1]
        batch_size, seq_len, _ = x.shape
        
        # Split features
        feature_inputs = torch.chunk(x, self.num_features, dim=-1)
        
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
    def __init__(self, input_dim=1, num_features=4, hidden_dim=64, use_attention=False):
        super(DeepMomentumNetwork, self).__init__()
        if use_attention:
            raise NotImplementedError("Attention is dismantled and not supported in v0.9.6 production.")
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
        vsn_out = self.vsn(x) # Shape: [Batch, Seq, hidden_dim]
        
        # LSTM forward pass
        lstm_out, _ = self.lstm(vsn_out) # Shape: [Batch, Seq, hidden_dim]
        
        # Output prediction (we take the last timestep prediction as the position signal)
        last_step_out = lstm_out[:, -1, :] # Shape: [Batch, hidden_dim]
        pred_signal = self.tanh(self.fc(last_step_out)) # Shape: [Batch, 1]
        
        return pred_signal.squeeze(-1)
