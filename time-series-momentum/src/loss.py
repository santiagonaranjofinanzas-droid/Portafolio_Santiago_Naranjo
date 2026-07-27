import torch
import numpy as np

def calcular_bailey_sharpe_diferenciable(returns, epsilon=1e-6):
    """
    Calcula el Ratio de Sharpe de Bailey-López de Prado (2012) exacto y diferenciable.
    returns: Tensor de PyTorch de forma [T] con los retornos netos del portafolio.
    """
    T = float(len(returns))
    if T < 4:
        # Fallback si la secuencia es muy corta
        mean = torch.mean(returns)
        std = torch.clamp(torch.std(returns), min=epsilon)
        return (mean / std) * np.sqrt(252)
        
    mean = torch.mean(returns)
    diffs = returns - mean
    
    var = torch.clamp(torch.sum(diffs ** 2) / (T - 1), min=epsilon)
    std = torch.sqrt(var)
    
    # Momentos superiores
    skew = torch.sum(diffs ** 3) / (T * (std ** 3))
    kurt = torch.sum(diffs ** 4) / (T * (std ** 4)) # Curtosis estándar
    
    # Sharpe clásico diario anualizado
    sr = (mean / std) * np.sqrt(252)
    
    # Exceso de curtosis (gamma_4) en la fórmula de Bailey es la curtosis estándar
    # Termino de sesgo: (gamma_3 / 6) * SR * (1 / sqrt(T))
    bias_term = (skew / 6.0) * sr * (1.0 / np.sqrt(T))
    
    # Termino de curtosis: (gamma_4 / 4 - 1/3) * (SR^2 / 4T)
    # Nota: la curtosis en PyTorch es la curtosis total (no el exceso de curtosis).
    # La fórmula original utiliza la curtosis estándar (donde normal = 3).
    kurt_term = (kurt / 4.0 - 1.0 / 3.0) * (sr ** 2) / (4.0 * T)
    
    # Denominador de corrección de Bailey-López de Prado
    # SR_corr = SR * [1 - bias_term + kurt_term]^-1
    correction_factor = 1.0 - bias_term + kurt_term
    # Suavizar el denominador para evitar divisiones por cero o valores negativos
    correction_factor = torch.clamp(correction_factor, min=0.1)
    
    sr_corr = sr / correction_factor
    return sr_corr

def e_var_softmin_loss(returns, window_size=63, step_size=21, alpha=1.0, lambda_cost=2.5, weights_history=None):
    """
    Función de pérdida de Soft-Min robusta sobre Sharpe (Log-Sum-Exp Sharpe Aggregation).
    returns: Tensor de PyTorch de forma [T] con los retornos netos diarios de la cartera.
    weights_history: Tensor de PyTorch de forma [T, Assets] with los pesos de cartera diarios.
    """
    T = len(returns)
    if T < window_size:
        return -calcular_bailey_sharpe_diferenciable(returns)
        
    sharpe_list = []
    
    # Ventanas rodantes
    for start in range(0, T - window_size + 1, step_size):
        end = start + window_size
        win_returns = returns[start:end]
        
        # Sharpe Bailey-Prado corregido
        sr_corr = calcular_bailey_sharpe_diferenciable(win_returns)
        
        # Penalización por rotación (Turnover) en la ventana
        turnover_penalty = 0.0
        if weights_history is not None:
            win_weights = weights_history[start:end] # [window_size, Assets]
            # Turnover diario promedio de la ventana
            turnover = torch.mean(torch.sum(torch.abs(win_weights[1:] - win_weights[:-1]), dim=1))
            turnover_penalty = lambda_cost * turnover + 1.5 * torch.pow(turnover, 2)
            
        sharpe_list.append(sr_corr - turnover_penalty)
        
    if len(sharpe_list) == 0:
        return -calcular_bailey_sharpe_diferenciable(returns)
        
    stacked_sharpe = torch.stack(sharpe_list)
    
    # Loss = (1 / alpha) * ln( (1 / W) * sum_w exp( -alpha * (SR_w - penalty_w) ) )
    # Para estabilidad numérica, restamos el máximo (log-sum-exp trick)
    max_val = torch.max(-alpha * stacked_sharpe)
    sum_exp = torch.sum(torch.exp(-alpha * stacked_sharpe - max_val))
    loss = (max_val + torch.log(sum_exp / len(sharpe_list))) / alpha
    
    return loss
