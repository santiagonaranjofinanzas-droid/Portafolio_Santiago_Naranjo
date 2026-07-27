import json
import hashlib
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone, date as dt_date
from scipy.stats import skew, kurtosis, jarque_bera, norm
from scipy.special import ndtr  # Normal CDF for PSR
from sqlmodel import Session, select
from sqlalchemy import and_, or_
from .database import engine as db_engine
from .models import TradeArchive, CapitalLog
from .settings import settings

try:
    import MetaTrader5 as mt5
except Exception:
    mt5 = None

try:
    from arch import arch_model  # For GARCH(1,1)
except Exception:
    arch_model = None

try:
    from hmmlearn.hmm import GaussianHMM
except Exception:
    GaussianHMM = None

try:
    from statsmodels.sandbox.stats.runs import runstest_1samp
except Exception:
    runstest_1samp = None


def _json_safe_value(value):
    if value is None:
        return None

    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()

    if isinstance(value, np.integer):
        return int(value)

    if isinstance(value, np.floating):
        if np.isnan(value) or np.isinf(value):
            return None
        return float(value)

    if isinstance(value, float):
        if np.isnan(value) or np.isinf(value):
            return None
        return value

    try:
        if pd.isna(value):
            return None
    except Exception:
        pass

    return value


def _history_records(df: pd.DataFrame) -> list[dict]:
    safe_df = df.replace([np.inf, -np.inf], np.nan)
    records: list[dict] = []
    for row in safe_df.to_dict(orient='records'):
        item = {k: _json_safe_value(v) for k, v in row.items()}
        magic = item.get('magic_number')
        item['magic_number'] = _json_safe_value(magic)
        item['bot_id'] = _json_safe_value(magic)
        records.append(item)
    return records

#--- CORE LOGIC (Decoupled from Streamlit) ---

def _account_scope_condition(account_login: str  None, server_name: str  None, include_unscoped: bool = True):
    scoped_terms = []
    if account_login:
        scoped_terms.append(TradeArchive.account_login == account_login)
    if server_name:
        scoped_terms.append(TradeArchive.server_name == server_name)

    if not scoped_terms:
        return None

    scoped_condition = and_(*scoped_terms)
    if not include_unscoped:
        return scoped_condition

    legacy_condition = and_(
        or_(TradeArchive.account_login.is_(None), TradeArchive.account_login == ""),
        or_(TradeArchive.server_name.is_(None), TradeArchive.server_name == ""),
    )
    return or_(scoped_condition, legacy_condition)

def calculate_trade_physics(row, rates_list=None):
    """Calculate auditable MAE/MFE from M1 candles within the trade lifetime."""
    names = [
        'mae', 'mfe', 'mae_r', 'mfe_r', 'tw_mae_r', 'tw_mfe_r', 'efficiency',
        'excursion_source', 'excursion_timeframe', 'excursion_samples',
        'excursion_coverage', 'risk_basis'
    ]
    unavailable = [np.nan] * 7 + ['unavailable', 'M1', 0, 0.0, 'unavailable']
    if pd.isna(row['entrytime']) or pd.isna(row['exittime']):
        return pd.Series(unavailable, index=names)

    if rates_list is None:
        rates_list = get_trade_m1_data(row['symbol'], row['entrytime'], row['exittime'])
    if not rates_list:
        return pd.Series(unavailable, index=names)

    df_rates = pd.DataFrame(rates_list)
    if not {'time', 'high', 'low'}.issubset(df_rates.columns):
        return pd.Series(unavailable, index=names)

    entry_t = pd.to_datetime(row['entrytime'], utc=True).tz_convert(None)
    exit_t = pd.to_datetime(row['exittime'], utc=True).tz_convert(None)
    df_rates['time'] = pd.to_datetime(df_rates['time'], errors='coerce', utc=True, format='mixed').dt.tz_convert(None)
    df_rates['high'] = pd.to_numeric(df_rates['high'], errors='coerce')
    df_rates['low'] = pd.to_numeric(df_rates['low'], errors='coerce')
    bar_end = df_rates['time'] + pd.Timedelta(minutes=1)
    trade_rates = df_rates[
        (df_rates['time'] <= exit_t) & (bar_end > entry_t)
    ].dropna(subset=['time', 'high', 'low'])
    if trade_rates.empty:
        return pd.Series(unavailable, index=names)

    entry_price = float(row['entryprice'])
    exit_price = float(row['exitprice'])
    trade_high = max(float(trade_rates['high'].max()), entry_price, exit_price)
    trade_low = min(float(trade_rates['low'].min()), entry_price, exit_price)

    if int(row['type_op']) == 0:
        mfe = max(0.0, trade_high - entry_price)
        mae = min(0.0, trade_low - entry_price)
        favorable_path = (trade_rates['high'] - entry_price).clip(lower=0)
        adverse_path = (trade_rates['low'] - entry_price).clip(upper=0)
        realized_price = exit_price - entry_price
    else:
        mfe = max(0.0, entry_price - trade_low)
        mae = min(0.0, entry_price - trade_high)
        favorable_path = (entry_price - trade_rates['low']).clip(lower=0)
        adverse_path = (entry_price - trade_rates['high']).clip(upper=0)
        realized_price = entry_price - exit_price

    tw_mfe = float(favorable_path.mean())
    tw_mae = float(adverse_path.mean())
    sl = float(row.get('sl') or 0.0)
    risk_price = abs(entry_price - sl) if sl > 0 else np.nan
    valid_risk = bool(np.isfinite(risk_price) and risk_price > 0)
    mae_r = mae / risk_price if valid_risk else np.nan
    mfe_r = mfe / risk_price if valid_risk else np.nan
    tw_mae_r = tw_mae / risk_price if valid_risk else np.nan
    tw_mfe_r = tw_mfe / risk_price if valid_risk else np.nan
    efficiency = float(np.clip(realized_price / mfe, 0.0, 1.0)) if mfe > 0 else 0.0
    samples = int(len(trade_rates))
    expected_samples = max(1, int((exit_t.floor('min') - entry_t.floor('min')).total_seconds() // 60) + 1)
    coverage = float(min(1.0, samples / expected_samples))

    return pd.Series(
        [mae, mfe, mae_r, mfe_r, tw_mae_r, tw_mfe_r, efficiency,
         'verified_m1', 'M1', samples, coverage, 'initial_stop' if valid_risk else 'price_only'],
        index=names
    )

def determine_session(dt):
    h = dt.hour
    if 22 <= h or h < 8: return "TK (Tokyo)"
    elif 8 <= h < 13: return "LD (London)"
    elif 13 <= h < 22: return "NY (New York)"
    return "Other"

def get_day_name_es(dt):
    days = {0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves", 4: "Viernes", 5: "Sábado", 6: "Domingo"}
    return days.get(dt.weekday(), "")

def get_mt5_data(days_back=365):
    """Sovereign Node MT5 Fetcher"""
    if mt5 is None:
        return None, None, None, "MetaTrader5 package not available in this environment."

    if not mt5.initialize(): 
        return None, None, None, f"Error MT5: {mt5.last_error()}"
    
    acc = mt5.account_info()
    current_bal = acc.balance if acc else 0
    
    to_date = datetime.now() + timedelta(days=1)
    from_date = datetime.now() - timedelta(days=days_back)
    
    deals = mt5.history_deals_get(from_date, to_date)
    if deals is None or len(deals) == 0: 
        return None, None, None, "No historical data found."
    
    df_deals = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
    
    # Orders buffer for SL/TP recovery
    from_date_orders = from_date - timedelta(days=180) 
    orders = mt5.history_orders_get(from_date_orders, to_date)
    df_orders = pd.DataFrame(list(orders), columns=orders[0]._asdict().keys()) if orders else pd.DataFrame()
    
    df_deposits = df_deals[df_deals['type'] == 2].copy()
    if not df_deposits.empty:
        df_deposits['time'] = pd.to_datetime(df_deposits['time'], unit='s')
        # Preserve ticket for uniqueness in sync
        df_deposits = df_deposits[['ticket', 'time', 'profit', 'comment']].rename(columns={'time':'Fecha', 'profit':'Monto', 'comment': 'Nota'})


    df_trades = df_deals[(df_deals['entry'].isin([0, 1])) & (df_deals['type'].isin([0, 1])) & (df_deals['symbol'].notna())].copy()
    if df_trades.empty: 
        return pd.DataFrame(), df_deposits, current_bal, "No executed trades."

    for c in ['commission', 'swap', 'fee']: 
        if c not in df_trades.columns: df_trades[c] = 0.0
        else: df_trades[c] = df_trades[c].fillna(0.0)

    # Detect Partials/Add-ons
    # We look for positions that have more than 2 deals (1 entry, 1 exit)
    # or that have deals with entry/exit volumes that don't match the initial volume.
    
    # We'll create a dictionary of partials per position
    partials_map = {}
    for pid, group in df_trades.groupby('position_id'):
        # Sort by time
        sorted_deals = group.sort_values('time')
        p_list = []
        for _, deal in sorted_deals.iterrows():
            entry_type = int(deal.get('entry', 0))
            if entry_type in (1, 2):  # DEAL_ENTRY_OUT = 1, DEAL_ENTRY_INOUT = 2
                dt = datetime.fromtimestamp(deal['time'], timezone.utc)
                iso_time = dt.replace(tzinfo=None).isoformat() + "Z"
                p_list.append({
                    'ticket': int(deal.get('ticket', 0)),
                    'volume': float(deal['volume']),
                    'price': float(deal['price']),
                    'commission': float(deal.get('commission', 0.0)),
                    'profit': float(deal['profit']),
                    'time': iso_time
                })
        if p_list:
            partials_map[pid] = json.dumps(p_list)

    trades = df_trades.groupby('position_id').agg({
        'symbol': 'first', 'time': ['first', 'last'], 'price': ['first', 'last'],
        'profit': 'sum', 'commission': 'sum', 'swap': 'sum', 'volume': 'first', 'type': 'first',
        'reason': 'last', 'magic': 'first'
    })
    
    trades.columns = ['symbol', 'entrytime', 'exittime', 'entryprice', 'exitprice', 'gross_pnl', 'commission', 'swap', 'volume', 'type_op', 'exit_reason', 'magic_number']
    trades = trades.reset_index()
    trades['netpnl'] = trades['gross_pnl'] + trades['commission'] + trades['swap']
    
    # Map partials
    trades['partials'] = trades['position_id'].map(partials_map).fillna("[]")

    # --- SL RECOVERY ---
    candidates = []
    if not df_orders.empty and 'position_id' in df_orders.columns and 'sl' in df_orders.columns:
        temp_o = df_orders[['position_id', 'sl']].copy()
        temp_o['sl'] = pd.to_numeric(temp_o['sl'], errors='coerce').fillna(0.0)
        temp_o = temp_o[temp_o['sl'] > 0]
        temp_o['position_id'] = temp_o['position_id'].astype('int64')
        candidates.append(temp_o)
        
    if not df_deals.empty and 'position_id' in df_deals.columns and 'sl' in df_deals.columns:
        temp_d = df_deals[['position_id', 'sl']].copy()
        temp_d['sl'] = pd.to_numeric(temp_d['sl'], errors='coerce').fillna(0.0)
        temp_d = temp_d[temp_d['sl'] > 0]
        temp_d['position_id'] = temp_d['position_id'].astype('int64')
        candidates.append(temp_d)

    if candidates:
        all_sl = pd.concat(candidates, ignore_index=True)
        trades_subset = trades[['position_id', 'entryprice']].copy()
        trades_subset['position_id'] = trades_subset['position_id'].astype('int64')
        merged_sl = all_sl.merge(trades_subset, on='position_id', how='left').dropna(subset=['entryprice'])
        if not merged_sl.empty:
            merged_sl['dist'] = (merged_sl['entryprice'] - merged_sl['sl']).abs()
            merged_sl = merged_sl.sort_values(['position_id', 'dist'], ascending=[True, False])
            best_sl = merged_sl.drop_duplicates('position_id')[['position_id', 'sl']]
            sl_map = best_sl.set_index('position_id')['sl']
            trades['temp_id'] = trades['position_id'].astype('int64')
            trades['sl'] = trades['temp_id'].map(sl_map).fillna(0.0)
            trades.drop(columns=['temp_id'], inplace=True)
        else: trades['sl'] = 0.0
    else: trades['sl'] = 0.0
        
    sl_hit_mask = (trades['exit_reason'] == 2)
    trades['sl'] = np.where((trades['sl'] == 0) & sl_hit_mask, trades['exitprice'], trades['sl'])

    trades['entrytime'] = pd.to_datetime(trades['entrytime'], unit='s')
    trades['exittime'] = pd.to_datetime(trades['exittime'], unit='s')
    trades = trades.sort_values('entrytime')

    # Optional outlier filtering via BK_EXCLUDE_TRADE_DATES (YYYY-MM-DD,...)
    if settings.exclude_trade_dates:
        try:
            mask_excl = trades['entrytime'].dt.date.isin(settings.exclude_trade_dates)
            pnl_excluded = trades.loc[mask_excl, 'netpnl'].sum()
            current_bal -= pnl_excluded
            trades = trades[~mask_excl]
        except Exception:
            pass

    trades['day_name'] = trades['entrytime'].apply(get_day_name_es)
    trades['session'] = trades['entrytime'].apply(determine_session)
    trades['hour'] = trades['entrytime'].dt.hour
    trades['direction'] = trades['type_op'].apply(lambda x: 'Sell' if x == 1 else 'Buy')
    trades['dir_mult'] = trades['type_op'].apply(lambda x: -1 if x == 1 else 1)
    
    trades['risk_price'] = abs(trades['entryprice'] - trades['sl'])
    trades['valid_sl'] = (trades['sl'] > 0) & (trades['risk_price'] > 0)
    trades['r_multiple'] = trades.apply(lambda r: (r['dir_mult'] * (r['exitprice'] - r['entryprice'])) / r['risk_price'] if r['valid_sl'] else np.nan, axis=1)
    
    physics = trades.apply(calculate_trade_physics, axis=1)
    physics.columns = [
        'mae', 'mfe', 'mae_r', 'mfe_r', 'tw_mae_r', 'tw_mfe_r', 'efficiency',
        'excursion_source', 'excursion_timeframe', 'excursion_samples',
        'excursion_coverage', 'risk_basis'
    ]
    trades = pd.concat([trades, physics], axis=1)
    
    # --- REFACTORED CAPITAL & EQUITY ACCOUNTING ---
    # Initial capital = Live Balance - Sum(Trade PnL) - Sum(Deposits/Adjustments)
    # type == 2 is DEAL_TYPE_BALANCE (Deposits/Withdrawals)
    all_deposits = df_deals[df_deals['type'] == 2].copy() if not df_deals.empty else pd.DataFrame()
    total_deposits = all_deposits['profit'].sum() if not all_deposits.empty else 0.0
    
    # We estimate starting capital based on the current state and backtracking.
    # Note: current_bal is the current MT5 account balance provided by initialize.
    start_cap = float(current_bal - trades['netpnl'].sum() - total_deposits)
    
    # To build a TRUE equity curve, we must merge deposits and trades chronologically.
    # Otherwise, the graph "jumps" or ROI is calculated on a wrong base.
    trades_ev = trades[['entrytime', 'netpnl']].rename(columns={'entrytime': 'time', 'netpnl': 'amount'})
    trades_ev['type'] = 'trade'
    
    dep_ev = pd.DataFrame()
    if not all_deposits.empty:
        dep_ev = all_deposits[['time', 'profit']].rename(columns={'profit': 'amount'})
        dep_ev['time'] = pd.to_datetime(dep_ev['time'], unit='s')
        dep_ev['type'] = 'deposit'
    
    full_timeline = pd.concat([trades_ev, dep_ev]).sort_values('time')
    full_timeline['cum_pnl'] = full_timeline.apply(lambda x: x['amount'] if x['type'] == 'trade' else 0, axis=1).cumsum()
    full_timeline['cum_dep'] = full_timeline.apply(lambda x: x['amount'] if x['type'] == 'deposit' else 0, axis=1).cumsum()
    
    # Map back to trades for the 'equity' column
    # We use merge_asof to find the state of deposits at each trade entry
    trades = trades.sort_values('entrytime')
    if not dep_ev.empty:
        dep_ev = dep_ev.sort_values('time')
        trades = pd.merge_asof(trades, dep_ev[['time', 'amount']].rename(columns={'amount': 'dep_at_time'}), 
                              left_on='entrytime', right_on='time', direction='backward')
        trades['cum_dep'] = trades['dep_at_time'].fillna(0).cumsum() # This is a simplification
        # Better: calculate cumulative deposits up to each trade
        temp_dep = dep_ev.copy().sort_values('time')
        temp_dep['cum_dep_real'] = temp_dep['amount'].cumsum()
        trades = pd.merge_asof(trades, temp_dep[['time', 'cum_dep_real']], left_on='entrytime', right_on='time', direction='backward')
        trades['cum_dep_real'] = trades['cum_dep_real'].fillna(0)
    else:
        trades['cum_dep_real'] = 0

    trades['equity'] = start_cap + trades['cum_dep_real'] + trades['netpnl'].cumsum()
    trades['equity_gross'] = start_cap + trades['cum_dep_real'] + trades['gross_pnl'].cumsum() 
    
    return trades, df_deposits, start_cap, None

def calculate_psr(sharpe, n, skew_val, kurt_val, benchmark_sharpe=0.0):
    """
    Probabilistic Sharpe Ratio (Marcos López de Prado)
    Measures the probability that the estimated Sharpe exceeds a benchmark hurdle.
    """
    if n < 5 or np.isnan(sharpe) or np.isinf(sharpe):
        return 0.0
    
    # Standard deviation of the Sharpe Ratio estimate
    # SigmaSR = sqrt((1 - γ3 * SR + (γ4 - 1)/4 * SR^2) / (N - 1))
    # where γ3 is skew and γ4 is kurtosis (NOT excess kurtosis)
    kurt_raw = kurt_val + 3.0 # convert excess kurtosis back to raw
    
    denom = 1 - skew_val * sharpe + ((kurt_raw - 1) / 4.0) * (sharpe**2)
    if denom <= 0: return 0.0 # Numerical stability
    
    sigma_sr = np.sqrt(max(denom, 0)) / np.sqrt(n - 1)
    
    # PSR = Phi((SR - SR*) / SigmaSR)
    t_stat = (sharpe - benchmark_sharpe) / sigma_sr
    return float(ndtr(t_stat))

_GARCH_CACHE = {}

def calculate_garch_var(returns, confidence=0.05):
    """
    Conditional VaR using GARCH(1,1) with caching for speed.
    """
    if arch_model is None:
        vol = returns.std()
        return float(vol), float(norm.ppf(confidence) * vol)

    if len(returns) < 30: 
        vol = returns.rolling(window=10).std().iloc[-1] if len(returns) > 10 else returns.std()
        return float(vol), float(norm.ppf(confidence) * vol)
    
    # Simple hash of returns for caching
    data_hash = hashlib.md5(returns.to_numpy().tobytes()).hexdigest()
    if data_hash in _GARCH_CACHE:
        return _GARCH_CACHE[data_hash]

    try:
        rescale = 100.0
        am = arch_model(returns * rescale, vol='Garch', p=1, q=1, dist='normal')
        res = am.fit(disp='off', show_warning=False)
        forecasts = res.forecast(horizon=1, reindex=False)
        
        f_vol = np.sqrt(forecasts.variance.values[-1, -1]) / rescale
        var_val = norm.ppf(confidence) * f_vol
        
        # Cleanup cache if large
        if len(_GARCH_CACHE) > 50: _GARCH_CACHE.clear()
        _GARCH_CACHE[data_hash] = (float(f_vol), float(var_val))
        
        return float(f_vol), float(var_val)
    except:
        vol = returns.std()
        return float(vol), float(norm.ppf(confidence) * vol)

_HMM_CACHE = {}

def calculate_hmm_regime(returns):
    """
    On-The-Fly Hidden Markov Model (HMM) for Market Regime Detection.
    Classifies the market into Bull-Quiet (Low Volatility) or Bear-Volatile (High Volatility).
    """
    if GaussianHMM is None or len(returns) < 30:
        return "Insufficient Data"

    try:
        # Use only the last 100 periods for fast on-the-fly training
        tail_data = returns.tail(100)
        data_hash = hashlib.md5(tail_data.to_numpy().tobytes()).hexdigest()
        
        if data_hash in _HMM_CACHE:
            return _HMM_CACHE[data_hash]

        X = tail_data.to_numpy().reshape(-1, 1)
        # 2 states: Quiet vs Volatile. Limit iterations for speed.
        hmm = GaussianHMM(n_components=2, covariance_type="full", n_iter=20, random_state=42)
        hmm.fit(X)
        
        hidden_states = hmm.predict(X)
        current_state = hidden_states[-1]
        
        # Determine which state is which based on variance
        var_0 = hmm.covars_[0][0][0]
        var_1 = hmm.covars_[1][0][0]
        
        if var_0 > var_1:
            regimes = {0: "Bear-Volatile", 1: "Bull-Quiet"}
        else:
            regimes = {0: "Bull-Quiet", 1: "Bear-Volatile"}
            
        res = regimes[current_state]
        
        # Cleanup cache if it grows too large
        if len(_HMM_CACHE) > 50: _HMM_CACHE.clear()
            
        _HMM_CACHE[data_hash] = res
        return res
    except Exception as e:
        return f"HMM Error"

def calculate_behavioral_matrix(df):
    """
    Behavioral Analytics: Correlation matrix between Emotive Tags and R-Multiples.
    """
    if 'tags' not in df.columns or 'r_multiple' not in df.columns:
        return []

    try:
        tags_df = df[['tags', 'r_multiple', 'netpnl']].copy()
        tags_df['r_multiple'] = pd.to_numeric(tags_df['r_multiple'], errors='coerce')
        tags_df = tags_df.dropna(subset=['r_multiple', 'tags'])
        
        # Explode tags (comma separated)
        tags_df['tag_list'] = tags_df['tags'].str.split(',')
        tags_df = tags_df.explode('tag_list')
        tags_df['tag_list'] = tags_df['tag_list'].str.strip()
        tags_df = tags_df[tags_df['tag_list'] != '']
        
        if tags_df.empty:
            return []

        summary = tags_df.groupby('tag_list').agg(
            count=('r_multiple', 'count'),
            avg_r=('r_multiple', 'mean'),
            win_rate=('netpnl', lambda x: (x > 0).mean())
        ).reset_index()
        
        # Only consider tags used at least 3 times for statistical relevance
        summary = summary[summary['count'] >= 3]
        summary = summary.sort_values('avg_r', ascending=False)
        
        # Round the values
        summary['avg_r'] = summary['avg_r'].round(2)
        summary['win_rate'] = summary['win_rate'].round(4)
        
        return summary.to_dict(orient='records')
    except Exception:
        return []

def clean_ticker(symbol: str) -> str:
    """Removes broker suffixes like .pro, .m, etc."""
    s = symbol.split('.')[0].upper()
    mapping = {
        "GOLD": "XAUUSD",
        "SILVER": "XAGUSD",
        "OIL": "WTI",
        "US30": "DJI",
        "NAS100": "NDX"
    }
    return mapping.get(s, s)

#get_trade_m1_data movida abajo para consistencia


def calculate_survival_stats(df):
    """
    Custom estimate for trade life.
    """
    if len(df) < 5: return None
    df['duration_m'] = (df['exittime'] - df['entrytime']).dt.total_seconds() / 60.0
    return {
        "avg_duration": float(df['duration_m'].mean()),
        "median_duration": float(df['duration_m'].median())
    }

def calculate_stats(df, start_cap, df_deposits, capital_start_time=None):
    """Quantitative Stats Refactored for API consumption"""
    if df is None or df.empty:
        return None

    df = df.copy()

    # Enforce required columns for robust math on partial payloads.
    if 'valid_sl' not in df.columns:
        df['valid_sl'] = False
    if 'r_multiple' not in df.columns:
        df['r_multiple'] = np.nan
    if 'commission' not in df.columns:
        df['commission'] = 0.0
    if 'mae_r' not in df.columns:
        df['mae_r'] = np.nan
    if 'mfe_r' not in df.columns:
        df['mfe_r'] = np.nan

    df['entrytime'] = pd.to_datetime(df['entrytime'], errors='coerce')
    df['exittime'] = pd.to_datetime(df['exittime'], errors='coerce')
    df['netpnl'] = pd.to_numeric(df['netpnl'], errors='coerce').fillna(0.0)
    df = df[df['entrytime'].notna()].sort_values('entrytime')

    if df.empty:
        return None

    try:
        safe_start_cap = float(start_cap)
    except Exception:
        safe_start_cap = 0.0
    capital_verified = bool(np.isfinite(safe_start_cap) and safe_start_cap > 0)
    # Keep cash-only analytics available when capital history is missing, but do
    # not expose ratios calculated from an invented account balance.
    if not capital_verified:
        safe_start_cap = 1.0

    def _safe_abs_mean(series: pd.Series) -> float:
        values = pd.to_numeric(series, errors='coerce').replace([np.inf, -np.inf], np.nan).dropna()
        if values.empty:
            return 0.0
        return float(abs(values.mean()))

    # --- R-MULTIPLE BLEND (SL-based when valid, cash-risk proxy otherwise) ---
    losses_real = df[(df['valid_sl'].fillna(False)) & (df['netpnl'] < 0)]
    losses_proxy = df[(~df['valid_sl'].fillna(False)) & (df['netpnl'] < 0)]
    risk_real_cash = _safe_abs_mean(losses_real['netpnl'])
    risk_proxy_cash = _safe_abs_mean(losses_proxy['netpnl'])

    if risk_real_cash <= 0:
        risk_real_cash = risk_proxy_cash
    if risk_proxy_cash <= 0:
        risk_proxy_cash = risk_real_cash
    if risk_real_cash <= 0:
        risk_real_cash = max(safe_start_cap * 0.01, 1e-6)
    if risk_proxy_cash <= 0:
        risk_proxy_cash = risk_real_cash

    n_valid_sl = int(df['valid_sl'].fillna(False).sum())
    w_proxy = max(0.15, np.exp(-n_valid_sl / 20.0))
    effective_risk_cash = max((w_proxy * risk_proxy_cash) + ((1 - w_proxy) * risk_real_cash), 1e-6)

    existing_r = pd.to_numeric(df['r_multiple'], errors='coerce')
    keep_r = df['valid_sl'].fillna(False) & existing_r.notna() & np.isfinite(existing_r)
    proxy_r = df['netpnl'] / effective_risk_cash
    df['r_multiple'] = existing_r.where(keep_r)
    df['r_multiple_estimated'] = proxy_r.where(~keep_r)
    df['r_multiple_source'] = np.where(keep_r, 'verified_sl', 'estimated_loss_proxy')

    # --- REFACTORED DAILY SERIES (TWR Chronological Algorithm) ---
    # Reconstrucción cronológica para TWR Puro que subdivide el periodo ante cada flujo externo
    events_list = []
    
    # 1. Agregar salidas de trades
    for idx, row in df.iterrows():
        ex_time = row['exittime'] if pd.notna(row['exittime']) else row['entrytime']
        events_list.append({
            'time': pd.to_datetime(ex_time),
            'amount': float(row['netpnl']),
            'type': 'trade'
        })
        
    # 2. Agregar flujos de caja (depósitos/retiros)
    if df_deposits is not None and not df_deposits.empty:
        for idx, row in df_deposits.iterrows():
            dep_time = pd.to_datetime(row['Fecha'])
            events_list.append({
                'time': dep_time,
                'amount': float(row['Monto']),
                'type': 'deposit'
            })
            
    if events_list:
        events = pd.DataFrame(events_list)
        # Priorizar depósitos sobre trades si ocurren exactamente al mismo segundo
        events['type_priority'] = np.where(events['type'] == 'deposit', 0, 1)
        events = events.sort_values(by=['time', 'type_priority']).reset_index(drop=True)
    else:
        events = pd.DataFrame(columns=['time', 'amount', 'type'])

    # Calcular equidad y factores de crecimiento paso a paso
    equity = float(safe_start_cap)
    equities = []
    g_factors = []
    
    for i, row in events.iterrows():
        prev_equity = equity
        amount = row['amount']
        
        if row['type'] == 'trade':
            equity = prev_equity + amount
            if prev_equity > 0:
                g_factor = max(0.0, equity / prev_equity)
            else:
                g_factor = 0.0
        else:  # deposit / withdrawal
            equity = prev_equity + amount
            g_factor = 1.0  # El flujo externo no altera el rendimiento del trader
            
        equities.append(equity)
        g_factors.append(g_factor)
        
    if not events.empty:
        events['equity'] = equities
        events['g_factor'] = g_factors
        
        # Resample a escala diaria
        events['date'] = events['time'].dt.date
        daily_groups = events.groupby('date')
        
        first_event_date = events['time'].min().date()
        baseline_time = pd.to_datetime(capital_start_time, errors='coerce') if capital_start_time is not None else pd.NaT
        baseline_date = baseline_time.date() if pd.notna(baseline_time) else first_event_date
        start_date = min(baseline_date, first_event_date)
        end_date = events['time'].max().date()
        if start_date >= first_event_date:
            start_date = start_date - timedelta(days=1)
        all_dates = pd.date_range(start=start_date, end=end_date, freq='D').date
        
        events_by_date = {d: group for d, group in daily_groups}
        daily_data = []
        current_equity = float(safe_start_cap)
        
        for d in all_dates:
            if d in events_by_date:
                day_events = events_by_date[d]
                pnl = day_events[day_events['type'] == 'trade']['amount'].sum()
                dep = day_events[day_events['type'] == 'deposit']['amount'].sum()
                current_equity = day_events.iloc[-1]['equity']
                daily_twr = day_events['g_factor'].prod() - 1.0
            else:
                pnl = 0.0
                dep = 0.0
                daily_twr = 0.0
                
            daily_data.append({
                'date': pd.to_datetime(d),
                'pnl': pnl,
                'dep': dep,
                'equity': current_equity,
                'ret': daily_twr
            })
            
        daily = pd.DataFrame(daily_data).set_index('date')
    else:
        daily = pd.DataFrame(columns=['pnl', 'dep', 'equity', 'ret'])
        daily.index.name = 'date'
        
    # Drawdown
    daily['peak'] = daily['equity'].cummax()
    daily['drawdown_abs'] = daily['equity'] - daily['peak']
    with np.errstate(divide='ignore', invalid='ignore'):
        daily['dd'] = np.where(daily['peak'] > 0, daily['drawdown_abs'] / daily['peak'], 0.0)
    daily['dd'] = pd.to_numeric(daily['dd'], errors='coerce').replace([np.inf, -np.inf], np.nan).fillna(0.0)
    
    # --- SEGREGACIÓN DE RETORNOS (FAT TAILS) ---
    daily_rets_raw = daily['ret'].replace([np.inf, -np.inf], np.nan).dropna()
    if not capital_verified:
        daily_rets_raw = pd.Series(dtype=float)
    daily_ret_series_raw = daily_rets_raw.to_numpy(dtype=float) if len(daily_rets_raw) > 0 else np.array([0.0], dtype=float)
    
    # Winsorización para estabilidad de modelos
    daily_rets_clean = daily_rets_raw.copy()
    if len(daily_rets_clean) >= 5:
        p01 = float(np.percentile(daily_rets_clean, 1))
        p99 = float(np.percentile(daily_rets_clean, 99))
        daily_rets_clean = pd.Series(np.clip(daily_rets_clean.to_numpy(), p01, p99), index=daily_rets_clean.index)
    daily_ret_series_clean = daily_rets_clean.to_numpy(dtype=float) if len(daily_rets_clean) > 0 else np.array([0.0], dtype=float)

    # --- METRICS ---
    valid_r_raw = pd.to_numeric(df['r_multiple'], errors='coerce').replace([np.inf, -np.inf], np.nan).dropna().to_numpy(dtype=float)
    valid_r = valid_r_raw

    mu_r = float(np.mean(valid_r)) if valid_r.size else None
    sigma_r = float(np.std(valid_r, ddof=1)) if valid_r.size > 1 else 0.0

    span = df['entrytime'].max() - df['entrytime'].min()
    time_span_days = max(float(span.total_seconds() / 86400.0), 1.0)
    trades_per_year = float(len(df) * (365.25 / time_span_days))

    daily_ret_mean = float(daily_rets_raw.mean()) if len(daily_rets_raw) > 0 else 0.0
    daily_ret_std = float(daily_rets_raw.std(ddof=1)) if len(daily_rets_raw) > 1 else 0.0
    robust_sharpe = float((daily_ret_mean / daily_ret_std) * np.sqrt(252)) if daily_ret_std > 0 else 0.0
    sqn = float(np.sqrt(valid_r.size) * (mu_r / sigma_r)) if mu_r is not None and sigma_r > 0 else None

    # Porcentajes de riesgo relativos al capital invertido total
    total_invested_cap = max(safe_start_cap + daily['dep'].sum(), 1.0)
    avg_risk_pct = float(effective_risk_cash / total_invested_cap)
    max_loss_cash = abs(min(float(df['netpnl'].min()), 0.0))
    max_risk_pct = float(max_loss_cash / total_invested_cap)

    # VaR y CVaR históricos al 99% de confianza (Basel Standard)
    var_99 = float(np.percentile(daily_ret_series_raw, 1)) if daily_ret_series_raw.size > 0 else 0.0
    cvar_tail = daily_ret_series_raw[daily_ret_series_raw <= var_99]
    cvar_99 = float(cvar_tail.mean()) if cvar_tail.size > 0 else var_99
    var_99_pct = min(abs(var_99), 1.0)
    cvar_99_pct = min(abs(cvar_99), 1.0)

    # Performance
    wins = df.loc[df['netpnl'] > 0, 'netpnl']
    losses = df.loc[df['netpnl'] < 0, 'netpnl']
    win_rate = float(len(wins) / len(df)) if len(df) > 0 else 0.0
    avg_w = float(wins.mean()) if not wins.empty else 0.0
    avg_l = float(abs(losses.mean())) if not losses.empty else 0.0
    payoff = float(avg_w / avg_l) if avg_l > 0 else 0.0

    gross_profit = float(wins.sum()) if not wins.empty else 0.0
    gross_loss = float(abs(losses.sum())) if not losses.empty else 0.0
    pf = float(gross_profit / gross_loss) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)

    end_equity = float(daily['equity'].iloc[-1]) if not daily.empty else float(safe_start_cap)
    
    # ROI
    total_ret = float((end_equity / total_invested_cap) - 1)
    
    years = max(time_span_days / 365.25, 1.0 / 365.25)
    if end_equity > 0:
        cagr_geo = float((end_equity / total_invested_cap) ** (1 / years) - 1)
    else:
        cagr_geo = total_ret

    max_dd = abs(float(daily['dd'].min())) if not daily.empty else 0.0
    max_dd_abs = abs(float(daily['drawdown_abs'].min())) if not daily.empty else 0.0
    calmar = float(cagr_geo / max_dd) if max_dd > 0 else 0.0

    # --- ADVANCED QUANT BLOCK ---
    ret_skew = float(skew(daily_ret_series_raw)) if daily_ret_series_raw.size >= 3 else 0.0
    ret_kurtosis = float(kurtosis(daily_ret_series_raw, fisher=True)) if daily_ret_series_raw.size >= 4 else 0.0

    if daily_ret_series_raw.size >= 8:
        jb_result = jarque_bera(daily_ret_series_raw)
        if hasattr(jb_result, 'statistic') and hasattr(jb_result, 'pvalue'):
            jb_stat = float(jb_result.statistic)
            jb_pvalue = float(jb_result.pvalue)
        else:
            jb_stat = float(jb_result[0])
            jb_pvalue = float(jb_result[1])
    else:
        jb_stat, jb_pvalue = 0.0, 1.0
    is_normal = bool(jb_pvalue > 0.05)

    # Cornish-Fisher VaR al 99% de confianza (Basel)
    z_99 = norm.ppf(0.01)
    S, K = ret_skew, ret_kurtosis
    z_cf = (
        z_99
        + (1 / 6) * (z_99**2 - 1) * S
        + (1 / 24) * (z_99**3 - 3 * z_99) * K
        - (1 / 36) * (2 * z_99**3 - 5 * z_99) * S**2
    )
    cf_var_r = float(daily_ret_mean + (daily_ret_std * z_cf)) if daily_ret_std > 0 else float(daily_ret_mean)
    cf_var_pct = min(abs(cf_var_r), 1.0)  # Capped at 100%

    if len(daily_rets_clean) > 1:
        g_vol, g_var = calculate_garch_var(daily_rets_clean, confidence=0.01)
        # ret_std es la volatilidad del reporte (mantenemos la raw para riesgo real)
        ret_std = float(daily_ret_std)
    else:
        g_vol, g_var = 0.0, 0.0
        ret_std = 0.0
    g_var_pct = min(abs(float(g_var)), 1.0)

    obs_sharpe = float(daily_ret_mean / daily_ret_std) if daily_ret_std > 0 else 0.0
    psr_val = calculate_psr(obs_sharpe, int(max(daily_ret_series_raw.size, 1)), ret_skew, ret_kurtosis)

    # Runs test (sin cambios)
    win_seq = (df['netpnl'].to_numpy(dtype=float) > 0).astype(int)
    if win_seq.size >= 2:
        n_wins = int(win_seq.sum())
        n_losses = int(win_seq.size - n_wins)
        runs = int(1 + np.sum(win_seq[:-1] != win_seq[1:]))
        if n_wins > 0 and n_losses > 0 and win_seq.size > 1:
            n = float(win_seq.size)
            expected_runs = (2 * n_wins * n_losses / n) + 1
            var_runs = (2 * n_wins * n_losses * (2 * n_wins * n_losses - n)) / (n**2 * (n - 1))
            runs_zscore = float((runs - expected_runs) / np.sqrt(max(var_runs, 1e-10)))
        else:
            runs_zscore = 0.0
    else:
        runs_zscore = 0.0
    serial_independent = bool(abs(runs_zscore) < 1.96)

    # Moving-block bootstrap on percentage returns. This preserves local serial
    # dependence without assuming a fixed cash position size.
    n_observations = len(daily_ret_series_raw)
    if capital_verified and n_observations >= 2:
        return_observations = daily_ret_series_raw
        n_mc = 1000
        block_size = min(max(3, n_observations // 10), n_observations)
        max_dds = np.empty(n_mc, dtype=float)
        rng = np.random.default_rng(42)
        for i in range(n_mc):
            n_blocks = int(np.ceil(n_observations / block_size))
            starts = rng.integers(0, max(1, n_observations - block_size + 1), size=n_blocks)
            sampled = np.concatenate([return_observations[s:s + block_size] for s in starts])[:n_observations]
            eq = safe_start_cap * np.cumprod(1.0 + np.clip(sampled, -0.999, None))
            peak = np.maximum.accumulate(eq)
            denom = np.where(peak > 0, peak, np.nan)
            dd_path = (eq - peak) / denom
            min_dd = np.nanmin(dd_path)
            max_dds[i] = float(max(min_dd, -1.0)) if np.isfinite(min_dd) else 0.0
    else:
        max_dds = np.array([0.0], dtype=float)

    mc_dd_10pct = float(np.percentile(max_dds, 10))
    mc_dd_1pct = float(np.percentile(max_dds, 1))
    prob_ruin_10pct = float(np.mean(max_dds < -0.10))
    prob_ruin_20pct = float(np.mean(max_dds < -0.20))

    verified_excursions = df.get('excursion_source', pd.Series(index=df.index, dtype=object)).eq('verified_m1')
    excursion_verified_count = int(verified_excursions.sum())
    excursion_coverage = float(excursion_verified_count / len(df)) if len(df) else 0.0

    # E-Ratio uses only verified M1 excursions with a valid initial-stop R basis.
    if 'entrytime' in df.columns and 'exittime' in df.columns:
        dur_hours = (df['exittime'] - df['entrytime']).dt.total_seconds() / 3600.0
        dur_hours_capped = np.maximum(dur_hours, 1.0 / 60.0)
        mae_norm = df['mae_r'].where(verified_excursions) / np.sqrt(dur_hours_capped)
        mfe_norm = df['mfe_r'].where(verified_excursions) / np.sqrt(dur_hours_capped)
        
        mae_norm_clean = pd.to_numeric(mae_norm, errors='coerce').replace([np.inf, -np.inf], np.nan).dropna()
        mfe_norm_clean = pd.to_numeric(mfe_norm, errors='coerce').replace([np.inf, -np.inf], np.nan).dropna()
        
        if not mae_norm_clean.empty and not mfe_norm_clean.empty:
            mae_abs_mean = float(mae_norm_clean.abs().mean())
            mfe_mean = float(mfe_norm_clean.mean())
            e_ratio = float(mfe_mean / mae_abs_mean) if mae_abs_mean > 0 else None
        else:
            e_ratio = None
    else:
        e_ratio = None

    total_commission = float(pd.to_numeric(df['commission'], errors='coerce').fillna(0.0).sum())
    commission_drag_pct = abs(total_commission) / total_invested_cap

    p95 = float(np.percentile(daily_ret_series_raw, 95)) if daily_ret_series_raw.size > 0 else 0.0
    p05 = float(np.percentile(daily_ret_series_raw, 5)) if daily_ret_series_raw.size > 0 else 0.0
    tail_ratio = float(abs(p95) / abs(p05)) if p05 != 0 else 999.0

    recovery_factor = float(df['netpnl'].sum() / max_dd_abs) if max_dd_abs > 0 else 0.0

    pos_r = valid_r_raw[valid_r_raw > 0]
    verified_r_coverage = float(valid_r_raw.size / len(df)) if len(df) else 0.0
    win_rate_val = win_rate

    # Criterio de Kelly Continuo: f* = mu / var
    daily_ret_var = float(np.var(daily_ret_series_raw, ddof=1)) if daily_ret_series_raw.size > 1 else 0.0
    if capital_verified and daily_ret_var > 1e-8 and daily_ret_mean > 0 and daily_ret_series_raw.size >= 30:
        raw_kelly = daily_ret_mean / daily_ret_var
        sample_shrinkage = daily_ret_series_raw.size / (daily_ret_series_raw.size + 60.0)
        kelly_pct = raw_kelly * sample_shrinkage
    else:
        kelly_pct = 0.0
    kelly_pct = float(np.clip(kelly_pct, 0.0, 0.25))

    def sanitize(v):
        if v is None:
            return None
        if isinstance(v, (np.floating, float)) and (np.isnan(v) or np.isinf(v)):
            return 0.0
        if isinstance(v, (np.floating, float)):
            return round(float(v), 6)
        return v

    avg_trade_pnl = float(df['netpnl'].mean()) if len(df) > 0 else 0.0
    avg_duration = calculate_survival_stats(df) or {}

    # === INSIGHT ENGINE (Backend Analytics) ===
    insights = []
    
    # 1. R-Multiple Distribution (Skewness)
    if valid_r.size > 10:
        r_skew = float(skew(valid_r))
        if r_skew < -1.0:
            insights.append({
                "type": "warning",
                "metric": "r_skewness",
                "text": f"Distribución de R-Multiples sesgada negativamente (Skew: {r_skew:.2f}).",
                "actionable": "Estás cortando ganancias temprano y dejando correr pérdidas. Ajusta tus Take Profits."
            })
        elif r_skew > 1.0:
            insights.append({
                "type": "success",
                "metric": "r_skewness",
                "text": f"Excelente asimetría positiva en retornos (Skew: {r_skew:.2f}).",
                "actionable": "Tu edge matemático es fuerte. Mantén la gestión de riesgo actual."
            })
            
    # 2. Drawdown Percentile
    if max_dd_abs > 0 and len(max_dds) > 0:
        worse_dds = np.sum(max_dds < -max_dd)
        dd_percentile = float((worse_dds / len(max_dds)) * 100)
        
        if dd_percentile < 15: # Worst 15% of possible drawdowns
            insights.append({
                "type": "warning",
                "metric": "drawdown_percentile",
                "text": f"Tu Drawdown actual está en el percentil {100 - dd_percentile:.0f} de estrés histórico.",
                "actionable": "Considera reducir el tamaño de posición (Risk Budget) un 25% hasta salir de la racha perdedora."
            })
            
    # 3. Contextual Breakdown (Sessions)
    if 'session' in df.columns:
        session_perf = df.groupby('session')['netpnl'].agg(['sum', 'count']).reset_index()
        if not session_perf.empty and len(session_perf) > 1:
            worst_session = session_perf.loc[session_perf['sum'].idxmin()]
            best_session = session_perf.loc[session_perf['sum'].idxmax()]
            
            if worst_session['sum'] < 0 and worst_session['count'] >= 5:
                insights.append({
                    "type": "danger" if worst_session['sum'] < (total_invested_cap * -0.05) else "warning",
                    "metric": "session_degradation",
                    "text": f"Fuga de capital detectada en la sesión {worst_session['session']} ({worst_session['sum']:.2f} PnL).",
                    "actionable": f"Evita operar en {worst_session['session']} o reduce tu riesgo a la mitad durante estas horas."
                })
                
            if best_session['sum'] > 0 and best_session['count'] >= 5:
                insights.append({
                    "type": "success",
                    "metric": "session_edge",
                    "text": f"Tu mayor ventaja estadística ocurre en {best_session['session']} ({best_session['sum']:.2f} PnL).",
                    "actionable": "Concentra tu capital y esfuerzo mental en esta ventana horaria."
                })
            
    # 4. Market Regime / Volatility
    if g_vol > 0 and daily_ret_std > 0:
        vol_ratio = g_vol / daily_ret_std
        if vol_ratio > 1.5:
            insights.append({
                "type": "warning",
                "metric": "regime_volatility",
                "text": "Régimen de ALTA volatilidad detectado (GARCH forecast elevado).",
                "actionable": "Aumenta la distancia de tus Stop Loss y reduce el apalancamiento para evitar 'whipsaws'."
            })
        elif vol_ratio < 0.5:
            insights.append({
                "type": "info",
                "metric": "regime_volatility",
                "text": "Régimen de BAJA volatilidad detectado.",
                "actionable": "Estrategias de 'Trend Following' pueden fallar. Prioriza operaciones de rango (Mean Reversion)."
            })

    # Behavior Matrix
    behavior_matrix = calculate_behavioral_matrix(df)
    
    # HMM Regime
    hmm_regime = calculate_hmm_regime(daily_rets_clean) if len(daily_rets_clean) > 0 else "Insufficient Data"

    if len(insights) == 0:
         insights.append({
            "type": "info",
            "metric": "baseline",
            "text": "Tu sistema se encuentra operando dentro de los parámetros estadísticos esperados.",
            "actionable": "Mantén la disciplina en la ejecución."
         })

    if daily_ret_series_raw.size < 30:
        significance = "Insufficient Data"
    elif psr_val >= 0.95 and serial_independent:
        significance = "High"
    elif psr_val >= 0.80:
        significance = "Moderate"
    else:
        significance = "Low (Noise)"

    res = {
        "methodology": {
            "version": "2.0",
            "capital_verified": capital_verified,
            "risk_confidence": 0.99,
            "return_method": "event-level TWR aggregated daily",
            "monte_carlo_method": "moving-block bootstrap on daily percentage returns",
            "verified_r_coverage": sanitize(verified_r_coverage),
        },
        "insights": insights,
        "summary": {
            "sqn": sanitize(sqn),
            "expectancy": sanitize(mu_r),
            "expectancy_cash": sanitize(avg_trade_pnl),
            "sharpe": sanitize(robust_sharpe),
            "net_profit": sanitize(df['netpnl'].sum()),
            "start_cap": sanitize(safe_start_cap) if capital_verified else None,
            "total_return": sanitize(total_ret) if capital_verified else None,
            "end_equity": sanitize(end_equity) if capital_verified else None,
            "trade_count": sanitize(len(df)),
        },
        "perf": {
            "cagr": sanitize(cagr_geo) if capital_verified else None,
            "pf": sanitize(pf),
            "profit_factor": sanitize(pf),
            "payoff": sanitize(payoff),
            "avg_win": sanitize(avg_w),
            "avg_loss": sanitize(avg_l),
            "avg_duration_min": sanitize(avg_duration.get("avg_duration")),
            "calmar": sanitize(calmar) if capital_verified else None,
            "max_drawdown": sanitize(max_dd) if capital_verified else None,
            "max_drawdown_cash": sanitize(max_dd_abs) if capital_verified else None,
            "win_rate": sanitize(win_rate_val),
            "recovery_factor": sanitize(recovery_factor),
            "optimal_risk_kelly": sanitize(kelly_pct) if capital_verified else None,
            "suggested_risk_half_kelly": sanitize(kelly_pct / 2.0) if capital_verified else None,
            "trades_per_year": sanitize(trades_per_year),
            "tail_ratio": sanitize(tail_ratio),
        },
        "risk": {
            "avg_risk": sanitize(avg_risk_pct),
            "max_risk": sanitize(max_risk_pct),
            "var": sanitize(var_99_pct) if capital_verified else None,
            "cvar": sanitize(cvar_99_pct) if capital_verified else None,
            "cf_var": sanitize(cf_var_pct) if capital_verified else None,
            "garch_var": sanitize(g_var_pct) if capital_verified else None,
            "daily_vol": sanitize(ret_std),
            "downside_vol": sanitize(float(daily_rets_raw[daily_rets_raw < 0].std(ddof=1)) if len(daily_rets_raw[daily_rets_raw < 0]) > 1 else 0.0),
            "vol_regime": "High" if ret_std > 0 and g_vol > (ret_std * 1.5) else "Stable",
        },
        "quant": {
            "skewness": sanitize(ret_skew),
            "kurtosis": sanitize(ret_kurtosis),
            "jarque_bera_stat": sanitize(jb_stat),
            "jarque_bera_pvalue": sanitize(jb_pvalue),
            "is_normal": is_normal,
            "psr": sanitize(psr_val),
            "significance": significance,
            "verified_r_count": int(valid_r_raw.size),
            "verified_r_coverage": sanitize(verified_r_coverage),
            "runs_zscore": sanitize(runs_zscore),
            "serial_independent": serial_independent,
            "hmm_regime": hmm_regime,
            "mc_dd_p10": sanitize(mc_dd_10pct),
            "mc_dd_p1": sanitize(mc_dd_1pct),
            "prob_ruin_10pct": sanitize(prob_ruin_10pct),
            "prob_ruin_20pct": sanitize(prob_ruin_20pct),
            "e_ratio": sanitize(e_ratio),
            "excursion_verified_count": excursion_verified_count,
            "excursion_coverage": sanitize(excursion_coverage),
            "commission_drag_pct": sanitize(commission_drag_pct),
        },
        "behavior": behavior_matrix,
        "history": _history_records(df),
        "equity_curve": [
            {
                'date': _json_safe_value(k),
                'pnl': sanitize(v['pnl']),
                'equity': sanitize(v['equity']),
                'drawdown': sanitize(v['dd']),
                'return': sanitize(v['ret']),
            }
            for k, v in daily[['pnl', 'equity', 'dd', 'ret']].to_dict(orient='index').items()
        ],
    }
    return res

def get_live_positions_data(account_login: str  None = None, server_name: str  None = None):
    """Obtiene posiciones abiertas y calcula riesgo vivo"""
    if mt5 is None or not mt5.initialize(): return None
    account = mt5.account_info()
    if account_login and account and str(account.login) != str(account_login):
        return pd.DataFrame()
    if server_name and account and str(account.server) != str(server_name):
        return pd.DataFrame()
    positions = mt5.positions_get()
    if positions is None or len(positions) == 0:
        return pd.DataFrame()
    
    df_live = pd.DataFrame(list(positions), columns=positions[0]._asdict().keys())

    # Attach broker specifications required for defensible notional exposure.
    contract_sizes = {}
    conversion_rates = {}
    account_currency = str(account.currency or "USD") if account else "USD"
    for symbol in df_live['symbol'].dropna().unique():
        info = mt5.symbol_info(symbol)
        contract_sizes[symbol] = float(info.trade_contract_size or 0.0) if info else 0.0
        profit_currency = str(info.currency_profit or account_currency) if info else account_currency
        conversion_rates[symbol] = 1.0 if profit_currency == account_currency else 0.0
    df_live['contract_size'] = df_live['symbol'].map(contract_sizes).fillna(0.0)
    df_live['currency_conversion_rate'] = df_live['symbol'].map(conversion_rates).fillna(0.0)
    
    # Enriquecer data viva
    df_live['type_str'] = df_live['type'].apply(lambda x: 'Buy' if x == 0 else 'Sell')
    df_live['dist_sl_price'] = df_live.apply(lambda r: abs(r['price_current'] - r['sl']) if r['sl'] > 0 else np.nan, axis=1)
    
    return df_live

def _resolve_terminal_symbol(symbol: str) -> str:
    """
    Checks if the symbol exists in the active MT5 terminal.
    If it doesn't, attempts to find an equivalent symbol with a different suffix.
    E.g. XAUUSD.pro -> XAUUSD.pa
    """
    if mt5 is None or not mt5.initialize():
        return symbol
        
    # Check if exact symbol exists
    info = mt5.symbol_info(symbol)
    if info is not None:
        if not info.visible:
            mt5.symbol_select(symbol, True)
        return symbol
        
    # If not found, try to strip suffixes
    root = symbol.split('.')[0]
    root_upper = root.upper()
    
    all_symbols = mt5.symbols_get()
    if not all_symbols:
        return symbol
        
    # First pass: look for exact match of root
    for s in all_symbols:
        s_upper = s.name.upper()
        if s_upper == root_upper:
            if not s.visible:
                mt5.symbol_select(s.name, True)
            return s.name
            
    # Second pass: look for symbol starting with root (e.g. XAUUSD.pa)
    for s in all_symbols:
        s_upper = s.name.upper()
        if s_upper.startswith(root_upper):
            if not s.visible:
                mt5.symbol_select(s.name, True)
            return s.name
            
    # Third pass: fuzzy match
    for s in all_symbols:
        s_upper = s.name.upper()
        if root_upper in s_upper:
            if not s.visible:
                mt5.symbol_select(s.name, True)
            return s.name
            
    return symbol


def get_trade_m1_data(symbol: str, entry_time: datetime, exit_time: datetime):
    """
    Fetches M1 candles for a specific trade directly from local MT5 (no external API fallbacks).
    Queries in chunks of 1 day to ensure MT5 handles historical downloads robustly.
    """
    if mt5 is not None and mt5.initialize():
        try:
            resolved_symbol = _resolve_terminal_symbol(symbol)
            # MT5 expects UTC datetimes. Passing naive values makes Python apply
            # the workstation timezone and shifts the requested candle window.
            entry_utc = entry_time.replace(tzinfo=timezone.utc) if entry_time.tzinfo is None else entry_time.astimezone(timezone.utc)
            exit_utc = exit_time.replace(tzinfo=timezone.utc) if exit_time.tzinfo is None else exit_time.astimezone(timezone.utc)
            start = entry_utc - timedelta(minutes=5)
            end = exit_utc + timedelta(minutes=5)
            
            if start >= end:
                return []
                
            chunk_size = timedelta(days=1)
            current_start = start
            dfs = []
            
            while current_start < end:
                current_end = min(current_start + chunk_size, end)
                rates = mt5.copy_rates_range(resolved_symbol, mt5.TIMEFRAME_M1, current_start, current_end)
                if rates is not None and len(rates) > 0:
                    dfs.append(pd.DataFrame(rates))
                current_start = current_end
                
            if dfs:
                df = pd.concat(dfs, ignore_index=True)
                df = df.drop_duplicates(subset=['time'])
                df['time'] = pd.to_datetime(df['time'], unit='s', utc=True).dt.strftime('%Y-%m-%dT%H:%M:%SZ')
                # Pandas' JSON encoder also converts numpy scalar types into
                # plain Python values, keeping this payload safe for DB caching.
                return json.loads(df.to_json(orient='records'))
        except Exception as e:
            print(f"Error fetching M1 data in chunks from MT5 for {symbol}: {e}", flush=True)
            
    return []

def sync_mt5_to_db(days_back=365):
    """
    Black_Knight_Quant Task: Fetches data from MT5 and syncs it into PostgreSQL/SQLite.
    This is the core of the decoupled SaaS pattern.
    """
    df_trades, df_deposits, start_cap, err = get_mt5_data(days_back)
    
    if err and "No historical data" not in err:
        return {"status": "error", "message": err}

    # Initialize variables for syncing deposits and balance operations
    organization_id = settings.default_org_id
    account_login = None
    server_name = None
    if mt5 is not None and mt5.initialize():
        acc = mt5.account_info()
        if acc:
            account_login = str(acc.login)
            server_name = acc.server

    if df_trades is None:
        df_trades = pd.DataFrame()

    if df_trades.empty and (df_deposits is None or df_deposits.empty):
        return {"status": "success", "message": "No new trades or deposits to sync", "synced": 0}
        
    synced_count = 0
    with Session(db_engine) as session:
        for _, row in df_trades.iterrows():
            # Check if trade exists
            existing = session.get(TradeArchive, (settings.default_org_id, int(row['position_id'])))
            if not existing:
                try:
                    trade = TradeArchive(
                        organization_id=settings.default_org_id,
                        position_id=int(row['position_id']),
                        symbol=str(row['symbol']),
                        entrytime=row['entrytime'].to_pydatetime(),
                        exittime=row['exittime'].to_pydatetime(),
                        entryprice=float(row['entryprice']),
                        exitprice=float(row['exitprice']),
                        gross_pnl=float(row['gross_pnl']),
                        commission=float(row['commission']),
                        swap=float(row['swap']),
                        volume=float(row['volume']),
                        type_op=int(row['type_op']),
                        direction=str(row['direction']),
                        exit_reason=int(row['exit_reason']),
                        netpnl=float(row['netpnl']),
                        sl=float(row['sl']),
                        risk_price=float(row['risk_price']),
                        valid_sl=bool(row['valid_sl']),
                        r_multiple=float(row['r_multiple']) if pd.notna(row['r_multiple']) else None,
                        mae=float(row['mae']) if pd.notna(row['mae']) else None,
                        mfe=float(row['mfe']) if pd.notna(row['mfe']) else None,
                        mae_r=float(row['mae_r']) if pd.notna(row['mae_r']) else None,
                        mfe_r=float(row['mfe_r']) if pd.notna(row['mfe_r']) else None,
                        tw_mae_r=float(row['tw_mae_r']) if pd.notna(row['tw_mae_r']) else None,
                        tw_mfe_r=float(row['tw_mfe_r']) if pd.notna(row['tw_mfe_r']) else None,
                        efficiency=float(row['efficiency']) if pd.notna(row['efficiency']) else None,
                        excursion_source=str(row['excursion_source']) if pd.notna(row['excursion_source']) else 'unavailable',
                        excursion_timeframe=str(row['excursion_timeframe']) if pd.notna(row['excursion_timeframe']) else 'M1',
                        excursion_samples=int(row['excursion_samples']) if pd.notna(row['excursion_samples']) else 0,
                        excursion_coverage=float(row['excursion_coverage']) if pd.notna(row['excursion_coverage']) else 0.0,
                        excursion_calculated_at=datetime.now(timezone.utc).replace(tzinfo=None),
                        risk_basis=str(row['risk_basis']) if pd.notna(row['risk_basis']) else 'unavailable',
                        magic_number=int(row['magic_number']) if 'magic_number' in row and pd.notna(row['magic_number']) else None,
                        partials=str(row['partials']) if 'partials' in row and pd.notna(row['partials']) else None
                    )
                    session.add(trade)
                    synced_count += 1
                except Exception as e:
                    print(f"Error syncing {row['position_id']}: {e}", flush=True)
            else:
                # Update magic number if missing for existing trade
                if getattr(existing, 'magic_number', None) is None and 'magic_number' in row and pd.notna(row['magic_number']):
                    existing.magic_number = int(row['magic_number'])
                    session.add(existing)
                    synced_count += 1

        # 2. Sync Deposits/Withdrawals (Balance operations)

        if df_deposits is not None and not df_deposits.empty:
            for _, d_row in df_deposits.iterrows():
                # For deposits, use ticket as position_id (since they don't have one in MT5)
                # This matches the MQL5 bridge fallback logic.
                pos_id = int(d_row['ticket'])
                existing_dep = session.exec(select(TradeArchive).where(
                    TradeArchive.organization_id == organization_id,
                    TradeArchive.position_id == pos_id
                )).first()
                
                if not existing_dep:
                    new_dep = TradeArchive(
                        organization_id=organization_id,
                        position_id=pos_id,
                        symbol="BALANCE",
                        entrytime=d_row['Fecha'].to_pydatetime(),
                        exittime=d_row['Fecha'].to_pydatetime(),
                        entryprice=0.0,
                        exitprice=0.0,
                        gross_pnl=float(d_row['Monto']),
                        commission=0.0,
                        swap=0.0,
                        volume=0.0,
                        type_op=2, # Balance
                        direction="Deposit" if d_row['Monto'] >= 0 else "Withdrawal",
                        exit_reason=0,
                        netpnl=float(d_row['Monto']),
                        sl=0.0,
                        risk_price=0.0,
                        valid_sl=False,
                        user_notes=str(d_row['Nota']),
                        account_login=account_login,
                        server_name=server_name
                    )
                    session.add(new_dep)
                    synced_count += 1

        session.commit()
    
    return {"status": "success", "synced": synced_count}


def get_db_data_for_metrics(
    organization_id: int,
    bot_id: int = None,
    account_login: str  None = None,
    server_name: str  None = None,
    days: int  None = None,
    include_unscoped: bool = True,
):
    """Reads from SQL completely decoupled from MT5 to compute metrics in ms."""
    with Session(db_engine) as session:
        # Solo incluir operaciones de trading reales, no de balance (type_op != 2)
        statement = select(TradeArchive).where(
            TradeArchive.organization_id == organization_id,
            TradeArchive.type_op != 2
        )
        scope_condition = _account_scope_condition(account_login, server_name, include_unscoped=include_unscoped)
        if scope_condition is not None:
            statement = statement.where(scope_condition)
        if bot_id is not None:
            statement = statement.where(TradeArchive.magic_number == bot_id)
        if days is not None and days > 0:
            cutoff = datetime.utcnow() - timedelta(days=days)
            statement = statement.where(TradeArchive.entrytime >= cutoff)
        results = session.exec(statement).all()
        
        if not results:
            return pd.DataFrame()
            
        # Convert models to dicts and construct df
        dicts = [r.model_dump() for r in results]
        df = pd.DataFrame(dicts)
        
        # Ensure correct types for calculate_stats
        if not df.empty:
            df['entrytime'] = pd.to_datetime(df['entrytime'])
            df['exittime'] = pd.to_datetime(df['exittime'])
            df.sort_values('entrytime', inplace=True)
            
        return df
