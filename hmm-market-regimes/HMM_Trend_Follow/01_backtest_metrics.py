import math
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import norm, skew, kurtosis

from Capa_4.sovereign_execution import CFinancialEngine


@dataclass(frozen=True)
class BacktestAssumptions:
    initial_balance: float = 10_000.0
    risk_percent: float = 1.0
    min_strength: float = 0.35
    vol_multiplier: float = 2.5
    reward_risk: float = 2.0
    use_partials: bool = True
    max_lot: float = 10.0
    point: float = 0.01
    tick_size: float = 0.01
    tick_value: float = 1.0
    spread_price: float = 0.0
    slippage_price: float = 0.0
    periods_per_year: int = 24 * 4 * 252
    commission_per_lot: float = 0.0
    min_lot: float = 0.01
    lot_step: float = 0.01
    intrabar_mode: str = "pessimistic"
    trade_direction: str = "both"
    trading_session: str = "all"
    volatility_regime: str = "all"
    volatility_regime_mode: str = "ex_ante"
    volatility_median_is: float = 0.0
    source_timezone: str = "UTC"
    session_timezone: str = "America/New_York"



def _pnl_money(price_diff: float, lot: float, tick_value: float, tick_size: float) -> float:
    return price_diff * lot * (tick_value / tick_size)


def _max_streak(flags: list[bool], value: bool) -> int:
    best = 0
    current = 0
    for flag in flags:
        if bool(flag) == value:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def _drawdown_stats(equity: pd.Series) -> dict:
    if equity.empty:
        return {
            "max_drawdown_money": 0.0,
            "max_drawdown_pct": 0.0,
            "max_drawdown_bars": 0,
        }
    peak = equity.cummax()
    dd_money = equity - peak
    dd_pct = dd_money / peak.replace(0.0, np.nan)
    underwater = dd_money < 0
    max_duration = 0
    current = 0
    for flag in underwater:
        if flag:
            current += 1
            max_duration = max(max_duration, current)
        else:
            current = 0
    return {
        "max_drawdown_money": float(dd_money.min()),
        "max_drawdown_pct": float(dd_pct.min() * 100.0) if not dd_pct.dropna().empty else 0.0,
        "max_drawdown_bars": int(max_duration),
    }


def deflated_sharpe_ratio(
    returns: np.ndarray,
    sharpe: float,
    trials: int = 1,
    benchmark_sharpe: float = 0.0,
) -> tuple[float, float]:
    """Bailey-Lopez de Prado style DSR probability and z-statistic."""
    clean = np.asarray(returns, dtype=float)
    clean = clean[np.isfinite(clean)]
    n = len(clean)
    if n < 3 or not np.isfinite(sharpe):
        return 0.0, 0.0

    trials = max(1, int(trials))
    sr_std = math.sqrt(max((1.0 - skew(clean) * sharpe + ((kurtosis(clean, fisher=False) - 1.0) / 4.0) * sharpe * sharpe) / (n - 1), 1e-12))
    if trials == 1:
        sr_star = benchmark_sharpe
    else:
        gamma_euler = 0.5772156649015329
        sr_star = benchmark_sharpe + sr_std * (
            (1.0 - gamma_euler) * norm.ppf(1.0 - 1.0 / trials)
            + gamma_euler * norm.ppf(1.0 - 1.0 / (trials * math.e))
        )
    z_stat = (sharpe - sr_star) / sr_std
    return float(norm.cdf(z_stat)), float(z_stat)


def run_backtest(signals: pd.DataFrame, assumptions: BacktestAssumptions  None = None) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    cfg = assumptions or BacktestAssumptions()
    
    # Calcular mediana de volatilidad proyectada para la segmentación de volatilidad
    if cfg.volatility_regime_mode == "ex_ante":
        median_vol = cfg.volatility_median_is
    else:
        vtv_sigma_vals = signals["Vol_Projected_Sigma"].to_numpy(dtype=float) if "Vol_Projected_Sigma" in signals.columns else np.zeros(len(signals))
        valid_vols = vtv_sigma_vals[vtv_sigma_vals > 1e-8]
        median_vol = np.median(valid_vols) if len(valid_vols) > 0 else 0.0

    open_prices = signals["open"].to_numpy(dtype=float)
    close_prices = signals["close"].to_numpy(dtype=float)
    high_prices = signals["high"].to_numpy(dtype=float)
    low_prices = signals["low"].to_numpy(dtype=float)
    regime = signals["Regime_Buffer_18"].shift(1).fillna(0).to_numpy(dtype=int)
    vtv_sigma = signals["Vol_Projected_Sigma"].shift(1).fillna(0).to_numpy(dtype=float)
    ml_strength = signals["ML_Master_Strength"].shift(1).fillna(0).to_numpy(dtype=float)

    balance = cfg.initial_balance
    position = None
    entry_price = 0.0
    entry_time = None
    entry_i = 0
    initial_lot = 0.0
    current_lot = 0.0
    stop_loss = 0.0
    take_profit = 0.0
    partial_done = False
    side = 0

    cashflows = []
    trades = []
    equity_values = []

    for i in range(1, len(signals)):
        ts = signals.index[i]
        close_t = close_prices[i]
        high_t = high_prices[i]
        low_t = low_prices[i]

        if position is None:
            if regime[i] != 0 and ml_strength[i] >= cfg.min_strength:
                # 1. Dirección
                if cfg.trade_direction == "buy" and regime[i] != 1:
                    continue
                if cfg.trade_direction == "sell" and regime[i] != -1:
                    continue
                    
                # 2. Sesión
                if cfg.trading_session != "all":
                    ts_ts = pd.Timestamp(ts)
                    if ts_ts.tzinfo is None:
                        ts_ts = ts_ts.tz_localize(cfg.source_timezone)
                    ts_ny = ts_ts.tz_convert(cfg.session_timezone)
                    hour = ts_ny.hour
                    if cfg.trading_session == "london" and not (3 <= hour < 11):
                        continue
                    if cfg.trading_session == "ny" and not (8 <= hour < 17):
                        continue
                    if cfg.trading_session == "asia" and not (hour >= 17 or hour < 3):
                        continue
                        
                # 3. Régimen de Volatilidad
                if cfg.volatility_regime != "all":
                    is_high_vol = vtv_sigma[i] > median_vol
                    if cfg.volatility_regime == "low" and is_high_vol:
                        continue
                    if cfg.volatility_regime == "high" and not is_high_vol:
                        continue

                side = 1 if regime[i] == 1 else -1
                entry_price = open_prices[i]
                entry_time = ts
                entry_i = i
                sl_dist = CFinancialEngine.calculate_volatility_stop(
                    entry_price, vtv_sigma[i], cfg.vol_multiplier, cfg.spread_price
                )
                sl_pts = int(sl_dist / cfg.point)
                initial_lot = CFinancialEngine.calculate_adaptive_lot(
                    balance, cfg.risk_percent, sl_pts, cfg.tick_value, cfg.tick_size, cfg.point, cfg.max_lot,
                    min_lot=cfg.min_lot, lot_step=cfg.lot_step
                )
                current_lot = initial_lot
                partial_done = False
                if side == 1:
                    position = "BUY"
                    # Compramos al ASK (más caro)
                    entry_price = entry_price + (cfg.spread_price / 2.0)
                    stop_loss = entry_price - sl_dist
                    take_profit = entry_price + sl_dist * cfg.reward_risk
                else:
                    position = "SELL"
                    # Vendemos al BID (más barato)
                    entry_price = entry_price - (cfg.spread_price / 2.0)
                    stop_loss = entry_price + sl_dist
                    take_profit = entry_price - sl_dist * cfg.reward_risk
            
            equity_values.append((ts, balance))
            continue

        trade_cashflows = []
        closed = False
        exit_reason = None
        exit_price = None

        if position == "BUY":
            initial_risk_price = abs(entry_price - stop_loss)
            if cfg.use_partials and initial_risk_price >= cfg.point and not partial_done:
                partial_target = entry_price + initial_risk_price * (cfg.reward_risk / 1.5)
                
                # Caso pesimista: si en la misma vela toca SL y parcial
                if cfg.intrabar_mode == "pessimistic" and low_t <= stop_loss and high_t >= partial_target:
                    fill = stop_loss - cfg.slippage_price
                    result = _pnl_money(fill - entry_price, initial_lot, cfg.tick_value, cfg.tick_size)
                    comm = initial_lot * 2.0 * cfg.commission_per_lot
                    result -= comm
                    balance += result
                    trade_cashflows.append(result)
                    cashflows.append({"time": ts, "bar_i": i, "type": "final", "side": position, "pnl": result, "balance": balance})
                    closed = True
                    exit_reason = "SL"
                    exit_price = fill
                else:
                    if high_t >= partial_target:
                        closed_lot = round((initial_lot * 0.70) / cfg.lot_step) * cfg.lot_step
                        closed_lot = round(closed_lot, 4)
                        remaining_lot = initial_lot - closed_lot
                        remaining_lot = round(remaining_lot, 4)
                        
                        if closed_lot >= cfg.min_lot and remaining_lot >= cfg.min_lot:
                            fill = partial_target - cfg.slippage_price
                            result = _pnl_money(fill - entry_price, closed_lot, cfg.tick_value, cfg.tick_size)
                            comm = closed_lot * 2.0 * cfg.commission_per_lot
                            result -= comm
                            balance += result
                            trade_cashflows.append(result)
                            cashflows.append({"time": ts, "bar_i": i, "type": "partial", "side": position, "pnl": result, "balance": balance})
                            current_lot = remaining_lot
                            stop_loss = entry_price
                            partial_done = True
                            
                            # Si en la misma vela después de parcial toca breakeven
                            if low_t <= stop_loss:
                                fill = stop_loss - cfg.slippage_price
                                result = _pnl_money(fill - entry_price, current_lot, cfg.tick_value, cfg.tick_size)
                                comm = current_lot * 2.0 * cfg.commission_per_lot
                                result -= comm
                                balance += result
                                trade_cashflows.append(result)
                                cashflows.append({"time": ts, "bar_i": i, "type": "final", "side": position, "pnl": result, "balance": balance})
                                closed = True
                                exit_reason = "SL"
                                exit_price = fill
            
            if not closed:
                if cfg.intrabar_mode == "pessimistic" and low_t <= stop_loss and high_t >= take_profit:
                    fill = stop_loss - cfg.slippage_price
                    result = _pnl_money(fill - entry_price, current_lot, cfg.tick_value, cfg.tick_size)
                    comm = current_lot * 2.0 * cfg.commission_per_lot
                    result -= comm
                    balance += result
                    trade_cashflows.append(result)
                    cashflows.append({"time": ts, "bar_i": i, "type": "final", "side": position, "pnl": result, "balance": balance})
                    closed = True
                    exit_reason = "SL"
                    exit_price = fill
                else:
                    if low_t <= stop_loss:
                        fill = stop_loss - cfg.slippage_price
                        result = _pnl_money(fill - entry_price, current_lot, cfg.tick_value, cfg.tick_size)
                        comm = current_lot * 2.0 * cfg.commission_per_lot
                        result -= comm
                        balance += result
                        trade_cashflows.append(result)
                        cashflows.append({"time": ts, "bar_i": i, "type": "final", "side": position, "pnl": result, "balance": balance})
                        closed = True
                        exit_reason = "SL"
                        exit_price = fill
                    elif high_t >= take_profit:
                        fill = take_profit - cfg.slippage_price
                        result = _pnl_money(fill - entry_price, current_lot, cfg.tick_value, cfg.tick_size)
                        comm = current_lot * 2.0 * cfg.commission_per_lot
                        result -= comm
                        balance += result
                        trade_cashflows.append(result)
                        cashflows.append({"time": ts, "bar_i": i, "type": "final", "side": position, "pnl": result, "balance": balance})
                        closed = True
                        exit_reason = "TP"
                        exit_price = fill

        elif position == "SELL":
            initial_risk_price = abs(stop_loss - entry_price)
            if cfg.use_partials and initial_risk_price >= cfg.point and not partial_done:
                partial_target = entry_price - initial_risk_price * (cfg.reward_risk / 1.5)
                
                # Caso pesimista: si en la misma vela toca SL y parcial
                if cfg.intrabar_mode == "pessimistic" and high_t >= stop_loss and low_t <= partial_target:
                    fill = stop_loss + cfg.slippage_price
                    result = _pnl_money(entry_price - fill, initial_lot, cfg.tick_value, cfg.tick_size)
                    comm = initial_lot * 2.0 * cfg.commission_per_lot
                    result -= comm
                    balance += result
                    trade_cashflows.append(result)
                    cashflows.append({"time": ts, "bar_i": i, "type": "final", "side": position, "pnl": result, "balance": balance})
                    closed = True
                    exit_reason = "SL"
                    exit_price = fill
                else:
                    if low_t <= partial_target:
                        closed_lot = round((initial_lot * 0.70) / cfg.lot_step) * cfg.lot_step
                        closed_lot = round(closed_lot, 4)
                        remaining_lot = initial_lot - closed_lot
                        remaining_lot = round(remaining_lot, 4)
                        
                        if closed_lot >= cfg.min_lot and remaining_lot >= cfg.min_lot:
                            fill = partial_target + cfg.slippage_price
                            result = _pnl_money(entry_price - fill, closed_lot, cfg.tick_value, cfg.tick_size)
                            comm = closed_lot * 2.0 * cfg.commission_per_lot
                            result -= comm
                            balance += result
                            trade_cashflows.append(result)
                            cashflows.append({"time": ts, "bar_i": i, "type": "partial", "side": position, "pnl": result, "balance": balance})
                            current_lot = remaining_lot
                            stop_loss = entry_price
                            partial_done = True
                            
                            # Si en la misma vela después de parcial toca breakeven
                            if high_t >= stop_loss:
                                fill = stop_loss + cfg.slippage_price
                                result = _pnl_money(entry_price - fill, current_lot, cfg.tick_value, cfg.tick_size)
                                comm = current_lot * 2.0 * cfg.commission_per_lot
                                result -= comm
                                balance += result
                                trade_cashflows.append(result)
                                cashflows.append({"time": ts, "bar_i": i, "type": "final", "side": position, "pnl": result, "balance": balance})
                                closed = True
                                exit_reason = "SL"
                                exit_price = fill
            
            if not closed:
                if cfg.intrabar_mode == "pessimistic" and high_t >= stop_loss and low_t <= take_profit:
                    fill = stop_loss + cfg.slippage_price
                    result = _pnl_money(entry_price - fill, current_lot, cfg.tick_value, cfg.tick_size)
                    comm = current_lot * 2.0 * cfg.commission_per_lot
                    result -= comm
                    balance += result
                    trade_cashflows.append(result)
                    cashflows.append({"time": ts, "bar_i": i, "type": "final", "side": position, "pnl": result, "balance": balance})
                    closed = True
                    exit_reason = "SL"
                    exit_price = fill
                else:
                    if high_t >= stop_loss:
                        fill = stop_loss + cfg.slippage_price
                        result = _pnl_money(entry_price - fill, current_lot, cfg.tick_value, cfg.tick_size)
                        comm = current_lot * 2.0 * cfg.commission_per_lot
                        result -= comm
                        balance += result
                        trade_cashflows.append(result)
                        cashflows.append({"time": ts, "bar_i": i, "type": "final", "side": position, "pnl": result, "balance": balance})
                        closed = True
                        exit_reason = "SL"
                        exit_price = fill
                    elif low_t <= take_profit:
                        fill = take_profit + cfg.slippage_price
                        result = _pnl_money(entry_price - fill, current_lot, cfg.tick_value, cfg.tick_size)
                        comm = current_lot * 2.0 * cfg.commission_per_lot
                        result -= comm
                        balance += result
                        trade_cashflows.append(result)
                        cashflows.append({"time": ts, "bar_i": i, "type": "final", "side": position, "pnl": result, "balance": balance})
                        closed = True
                        exit_reason = "TP"
                        exit_price = fill

        if closed:
            trade_pnl = sum(cf["pnl"] for cf in cashflows if entry_time is not None and cf["bar_i"] >= entry_i and cf["bar_i"] <= i and cf["type"] in {"partial", "final"})
            # Use final balance deltas since entry by summing recent cashflows can include only this trade while single-position.
            trade_pnl = sum(trade_cashflows)
            if partial_done:
                prior_partials = [cf["pnl"] for cf in cashflows if cf["bar_i"] >= entry_i and cf["bar_i"] <= i and cf["type"] == "partial"]
                trade_pnl += sum(prior_partials[-1:]) if prior_partials and not any(abs(x - trade_cashflows[0]) < 1e-9 for x in prior_partials[-1:]) else 0.0
            # Rebuild trade pnl from cashflows in the interval for clarity.
            interval_pnl = sum(cf["pnl"] for cf in cashflows if entry_i <= cf["bar_i"] <= i)
            trades.append({
                "entry_time": entry_time,
                "exit_time": ts,
                "entry_i": entry_i,
                "exit_i": i,
                "side": position,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "exit_reason": exit_reason,
                "initial_lot": initial_lot,
                "bars_held": i - entry_i,
                "partial_done": partial_done,
                "pnl": interval_pnl,
                "return_on_initial_balance": interval_pnl / cfg.initial_balance,
                "balance": balance,
            })
            position = None
            equity_values.append((ts, balance))
        else:
            # Mark-to-Market para DD Flotante usando close_t
            if position == "BUY":
                floating_pnl = _pnl_money((close_t - (cfg.spread_price/2.0)) - entry_price, current_lot, cfg.tick_value, cfg.tick_size)
            elif position == "SELL":
                floating_pnl = _pnl_money(entry_price - (close_t + (cfg.spread_price/2.0)), current_lot, cfg.tick_value, cfg.tick_size)
            else:
                floating_pnl = 0.0
            
            equity_values.append((ts, balance + floating_pnl))

    cashflows_df = pd.DataFrame(cashflows)
    trades_df = pd.DataFrame(trades)
    equity = pd.Series([v for _, v in equity_values], index=[t for t, _ in equity_values], name="equity")
    return trades_df, cashflows_df, equity


def compute_backtest_metrics(
    trades: pd.DataFrame,
    cashflows: pd.DataFrame,
    equity: pd.Series,
    assumptions: BacktestAssumptions  None = None,
    dsr_trials: int = 1,
) -> dict:
    cfg = assumptions or BacktestAssumptions()
    pnl = trades["pnl"].to_numpy(dtype=float) if not trades.empty else np.array([], dtype=float)
    flow_pnl = cashflows["pnl"].to_numpy(dtype=float) if not cashflows.empty else np.array([], dtype=float)
    wins = pnl[pnl > 0]
    losses = pnl[pnl <= 0]
    flags = [x > 0 for x in pnl]

    bar_returns = equity.pct_change().dropna().to_numpy(dtype=float)
    if len(bar_returns) > 1 and np.std(bar_returns, ddof=1) > 0:
        period_sharpe = float(np.mean(bar_returns) / np.std(bar_returns, ddof=1))
        sharpe = float(period_sharpe * math.sqrt(cfg.periods_per_year))
    else:
        period_sharpe = 0.0
        sharpe = 0.0
    downside = bar_returns[bar_returns < 0]
    sortino = float(np.mean(bar_returns) / np.std(downside, ddof=1) * math.sqrt(cfg.periods_per_year)) if len(downside) > 1 and np.std(downside, ddof=1) > 0 else 0.0
    dsr_prob, dsr_z = deflated_sharpe_ratio(bar_returns, period_sharpe, trials=dsr_trials)

    dd = _drawdown_stats(equity)
    total_return_pct = ((equity.iloc[-1] / cfg.initial_balance) - 1.0) * 100.0 if not equity.empty else 0.0
    profit_factor = float(np.sum(wins) / abs(np.sum(losses))) if len(losses) and abs(np.sum(losses)) > 0 else np.inf if len(wins) else 0.0
    expectancy = float(np.mean(pnl)) if len(pnl) else 0.0
    avg_win = float(np.mean(wins)) if len(wins) else 0.0
    avg_loss = float(np.mean(losses)) if len(losses) else 0.0
    payoff_ratio = float(avg_win / abs(avg_loss)) if avg_loss < 0 else np.inf if avg_win > 0 else 0.0
    recovery_factor = float((equity.iloc[-1] - cfg.initial_balance) / abs(dd["max_drawdown_money"])) if dd["max_drawdown_money"] < 0 else np.inf

    return {
        "initial_balance": cfg.initial_balance,
        "final_balance": float(equity.iloc[-1]) if not equity.empty else cfg.initial_balance,
        "net_profit": float(equity.iloc[-1] - cfg.initial_balance) if not equity.empty else 0.0,
        "total_return_pct": float(total_return_pct),
        "closed_trades": int(len(trades)),
        "cashflows": int(len(cashflows)),
        "win_rate_pct": float(len(wins) / len(pnl) * 100.0) if len(pnl) else 0.0,
        "loss_rate_pct": float(len(losses) / len(pnl) * 100.0) if len(pnl) else 0.0,
        "profit_factor": profit_factor,
        "expectancy": expectancy,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "payoff_ratio": payoff_ratio,
        "largest_win": float(np.max(wins)) if len(wins) else 0.0,
        "largest_loss": float(np.min(losses)) if len(losses) else 0.0,
        "max_consecutive_wins": int(_max_streak(flags, True)),
        "max_consecutive_losses": int(_max_streak(flags, False)),
        "max_drawdown_money": dd["max_drawdown_money"],
        "max_drawdown_pct": dd["max_drawdown_pct"],
        "max_drawdown_bars": dd["max_drawdown_bars"],
        "sharpe_ratio": sharpe,
        "period_sharpe_ratio": period_sharpe,
        "sortino_ratio": sortino,
        "deflated_sharpe_probability": dsr_prob,
        "deflated_sharpe_z": dsr_z,
        "dsr_trials": int(max(1, dsr_trials)),
        "recovery_factor": recovery_factor,
        "mean_cashflow": float(np.mean(flow_pnl)) if len(flow_pnl) else 0.0,
        "std_cashflow": float(np.std(flow_pnl, ddof=1)) if len(flow_pnl) > 1 else 0.0,
    }
