from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from Capa_4.audit_oos_stability_30001 import metrics_for_trades, session_label, write_table
from Capa_4.tick_backtest import TickDataStore


POINT = 0.01
TICK_SIZE = 0.01
TICK_VALUE = 1.0


def pnl_money(price_diff: float, lot: float) -> float:
    return price_diff * lot * (TICK_VALUE / TICK_SIZE)


def add_entry_features(trades: pd.DataFrame, signals: pd.DataFrame) -> pd.DataFrame:
    sig = signals.reset_index()
    idx = trades["entry_i"].astype(int).clip(0, len(sig) - 1)
    features = sig.loc[
        idx,
        [
            "timestamp",
            "HMM_Prob_Bull",
            "ML_Master_Strength",
            "Vol_Projected_Sigma",
            "Regime_Buffer_18",
            "Raw_Confidence",
            "Raw_Vol_Ratio",
            "Raw_Slope_Mag",
            "Raw_Accel_Mag",
        ],
    ].reset_index(drop=True)
    out = pd.concat([trades.reset_index(drop=True), features], axis=1)
    out["hour"] = out["entry_time"].dt.hour
    out["weekday"] = out["entry_time"].dt.day_name()
    out["session"] = out["hour"].map(session_label)
    out["duration_bucket"] = pd.cut(
        out["bars_held"],
        bins=[-1, 8, 24, 48, 96, 10_000],
        labels=["0_8", "9_24", "25_48", "49_96", "97_plus"],
    ).astype(str)
    out["strength_bucket"] = pd.qcut(
        out["ML_Master_Strength"].rank(method="first"),
        q=4,
        labels=["Q1_strength", "Q2_strength", "Q3_strength", "Q4_strength"],
    ).astype(str)
    out["vol_bucket"] = pd.qcut(
        out["Vol_Projected_Sigma"].rank(method="first"),
        q=4,
        labels=["Q1_vol", "Q2_vol", "Q3_vol", "Q4_vol"],
    ).astype(str)
    return out


def bars_since_regime_change(signals: pd.DataFrame) -> pd.Series:
    regime = signals["Regime_Buffer_18"].fillna(0).astype(int)
    changed = regime.ne(regime.shift(1).fillna(regime.iloc[0]))
    last_change = np.full(len(regime), 0, dtype=int)
    current = 0
    for i, flag in enumerate(changed.to_numpy()):
        if flag:
            current = i
        last_change[i] = current
    return pd.Series(np.arange(len(regime)) - last_change, index=signals.index, name="bars_since_regime_change")


def compute_mae_mfe(trades: pd.DataFrame, tick_root: Path) -> pd.DataFrame:
    store = TickDataStore(tick_root)
    rows = []
    for row in trades.itertuples(index=False):
        ticks = store.window(pd.Timestamp(row.entry_time), pd.Timestamp(row.exit_time))
        if ticks.empty:
            rows.append({"mae_money": np.nan, "mfe_money": np.nan, "mae_points": np.nan, "mfe_points": np.nan})
            continue
        lot = float(row.initial_lot)
        entry = float(row.entry_price)
        if row.side == "BUY":
            adverse = entry - ticks["bid"].astype(float)
            favorable = ticks["bid"].astype(float) - entry
        else:
            adverse = ticks["ask"].astype(float) - entry
            favorable = entry - ticks["ask"].astype(float)
        mae_price = max(0.0, float(adverse.max()))
        mfe_price = max(0.0, float(favorable.max()))
        rows.append({
            "mae_money": pnl_money(mae_price, lot),
            "mfe_money": pnl_money(mfe_price, lot),
            "mae_points": mae_price / POINT,
            "mfe_points": mfe_price / POINT,
        })
    return pd.DataFrame(rows)


def grouped_metrics(trades: pd.DataFrame, column: str) -> pd.DataFrame:
    return pd.DataFrame([metrics_for_trades(g.copy(), str(k)) for k, g in trades.groupby(column, sort=True)])


def main() -> None:
    source = ROOT / "Capa_4" / "comparacion_oos_30001_40001_accel18"
    outdir = ROOT / "Capa_7" / "edge_diagnostics_50001"
    outdir.mkdir(parents=True, exist_ok=True)

    trades = pd.read_csv(source / "tick_trades_oos_40001.csv", parse_dates=["entry_time", "exit_time"])
    signals = pd.read_parquet(source / "signals_oos_40001.parquet")
    enriched = add_entry_features(trades, signals)
    bsrc = bars_since_regime_change(signals).reset_index(drop=True)
    idx = enriched["entry_i"].astype(int).clip(0, len(bsrc) - 1)
    enriched["bars_since_regime_change"] = bsrc.loc[idx].to_numpy()
    enriched["regime_distance_bucket"] = pd.cut(
        enriched["bars_since_regime_change"],
        bins=[-1, 4, 12, 48, 10_000],
        labels=["0_4", "5_12", "13_48", "49_plus"],
    ).astype(str)

    mae_mfe = compute_mae_mfe(enriched, ROOT / "gold_data_parquet")
    enriched = pd.concat([enriched.reset_index(drop=True), mae_mfe], axis=1)
    enriched["mfe_to_mae"] = enriched["mfe_money"] / enriched["mae_money"].replace(0.0, np.nan)
    enriched.to_csv(outdir / "tick_trades_50001_enriched_mae_mfe.csv", index=False)

    specs = {
        "weekday_metrics_50001.csv": "weekday",
        "side_metrics_50001.csv": "side",
        "session_metrics_50001.csv": "session",
        "vol_bucket_metrics_50001.csv": "vol_bucket",
        "strength_bucket_metrics_50001.csv": "strength_bucket",
        "duration_metrics_50001.csv": "duration_bucket",
        "regime_distance_metrics_50001.csv": "regime_distance_bucket",
    }
    outputs = {}
    for filename, column in specs.items():
        df = grouped_metrics(enriched, column)
        df.to_csv(outdir / filename, index=False)
        outputs[filename] = df

    mae_summary = enriched.groupby("exit_reason").agg(
        trades=("pnl", "size"),
        avg_pnl=("pnl", "mean"),
        avg_mae_money=("mae_money", "mean"),
        avg_mfe_money=("mfe_money", "mean"),
        median_mfe_to_mae=("mfe_to_mae", "median"),
    ).reset_index()
    mae_summary.to_csv(outdir / "mae_mfe_by_exit_reason_50001.csv", index=False)

    cols = [
        "segment",
        "trades",
        "return_pct_on_initial",
        "win_rate_pct",
        "profit_factor",
        "max_drawdown_pct",
        "max_consecutive_losses",
        "sharpe_trade",
    ]
    report = f"""# Diagnostico profundo de edge 50001

Base: trades tick bid/ask del 50001 equivalente al 40001 actual.

##Dia de semana

{write_table(outputs['weekday_metrics_50001.csv'], cols)}

##Direccion

{write_table(outputs['side_metrics_50001.csv'], cols)}

##Sesion

{write_table(outputs['session_metrics_50001.csv'], cols)}

##Volatilidad

{write_table(outputs['vol_bucket_metrics_50001.csv'], cols)}

##Fuerza HMM/ML

{write_table(outputs['strength_bucket_metrics_50001.csv'], cols)}

##Duracion

{write_table(outputs['duration_metrics_50001.csv'], cols)}

##Distancia al cambio de regimen

{write_table(outputs['regime_distance_metrics_50001.csv'], cols)}

##MAE/MFE por salida

{write_table(mae_summary, ['exit_reason', 'trades', 'avg_pnl', 'avg_mae_money', 'avg_mfe_money', 'median_mfe_to_mae'])}

##Uso

Este reporte define los candidatos para Capa 9: salidas por deterioro, reversa de regimen, TP adaptativo, trailing volatilidad, stop temporal y politica de break-even.
"""
    (outdir / "REPORTE_EDGE_DIAGNOSTICS_50001.md").write_text(report, encoding="utf-8")
    print(f"OK: {outdir}")


if __name__ == "__main__":
    main()
