import random
import numpy as np
import pandas as pd

def initialize_random_seeds(seed=42):
    """
    Initialize random seeds for reproducibility across numpy, random, and optionally torch.
    """
    random.seed(seed)
    np.random.seed(seed)
    
    # Try initializing PyTorch seeds if installed
    try:
        import torch
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
        print(f"[INFO] Seeds initialized to {seed} (including PyTorch).")
    except ImportError:
        print(f"[INFO] Seeds initialized to {seed} (numpy/random only).")

def calculate_financial_metrics(returns: pd.Series, risk_free_rate: float = 0.0, annualization_factor: int = 252) -> dict:
    """
    Calculate core trading/financial metrics from daily returns:
    Cumulative Return, Sharpe Ratio, Sortino Ratio, Max Drawdown, CAGR, and Win Rate.
    """
    if len(returns) == 0:
        return {}
        
    cum_returns = (1 + returns).cumprod()
    total_return = cum_returns.iloc[-1] - 1
    
    # Annualized mean and std dev
    mean_return = returns.mean()
    std_return = returns.std()
    
    # Sharpe Ratio
    sharpe = np.nan
    if std_return > 0:
        sharpe = ((mean_return - risk_free_rate / annualization_factor) / std_return) * np.sqrt(annualization_factor)
        
    # Sortino Ratio (downside deviation only)
    downside_returns = returns[returns < 0]
    std_downside = downside_returns.std()
    sortino = np.nan
    if std_downside > 0:
        sortino = ((mean_return - risk_free_rate / annualization_factor) / std_side) * np.sqrt(annualization_factor) if 'std_side' in locals() else ((mean_return - risk_free_rate / annualization_factor) / std_downside) * np.sqrt(annualization_factor)
        
    # Max Drawdown
    peaks = cum_returns.cummax()
    drawdowns = (cum_returns - peaks) / peaks
    max_dd = drawdowns.min()
    
    # CAGR (Compound Annual Growth Rate)
    years = len(returns) / annualization_factor
    cagr = np.nan
    if years > 0 and cum_returns.iloc[-1] > 0:
        cagr = (cum_returns.iloc[-1]) ** (1 / years) - 1
        
    # Win Rate
    win_rate = len(returns[returns > 0]) / len(returns) if len(returns) > 0 else 0
    
    return {
        "cumulative_return": float(total_return),
        "sharpe_ratio": float(sharpe),
        "sortino_ratio": float(sortino),
        "max_drawdown": float(max_dd),
        "cagr": float(cagr),
        "win_rate": float(win_rate)
    }

def temporal_train_test_split(data: pd.DataFrame, train_ratio: float = 0.8) -> tuple:
    """
    Split a pandas DataFrame chronologically into train and test sets to avoid data leakage.
    Assumes data is sorted chronologically.
    """
    split_idx = int(len(data) * train_ratio)
    train = data.iloc[:split_idx]
    test = data.iloc[split_idx:]
    return train, test

def temporal_kfold_split(data: pd.DataFrame, n_splits: int = 5):
    """
    Generates time-series walk-forward splits for cross-validation.
    Each split i has train index from 0 to (i * split_size) and test from (i * split_size) to ((i + 1) * split_size).
    """
    total_len = len(data)
    split_size = int(total_len / (n_splits + 1))
    
    for i in range(1, n_splits + 1):
        train_end = i * split_size
        test_end = train_end + split_size
        if test_end > total_len:
            test_end = total_len
            
        train = data.iloc[:train_end]
        test = data.iloc[train_end:test_end]
        yield train, test
