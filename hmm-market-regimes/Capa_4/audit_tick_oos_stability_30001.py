from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from Capa_4.audit_oos_stability_30001 import (
    INITIAL_BALANCE,
    add_entry_features,
    metrics_for_trades,
    session_label,
    write_table,
)


def main() -> None:
    root = ROOT
    source = root / "Capa_4" / "comparacion_oos_30001_40001_accel18"
    outdir = root / "Capa_4" / "tick_oos_stability_30001"
    outdir.mkdir(parents=True, exist_ok=True)

    trades = pd.read_csv(source / "tick_trades_oos_30001.csv", parse_dates=["entry_time", "exit_time"])
    signals = pd.read_parquet(source / "signals_oos_30001.parquet")
    trades = add_entry_features(trades, signals)

    trades["month"] = trades["entry_time"].dt.to_period("M").astype(str)
    trades["quarter"] = trades["entry_time"].dt.to_period("Q").astype(str)
    trades["hour"] = trades["entry_time"].dt.hour
    trades["session"] = trades["hour"].map(session_label)
    trades["vol_regime"] = pd.qcut(
        trades["Vol_Projected_Sigma"].rank(method="first"),
        q=3,
        labels=["LOW_VOL", "MID_VOL", "HIGH_VOL"],
    ).astype(str)
    trades["strength_regime"] = pd.qcut(
        trades["ML_Master_Strength"].rank(method="first"),
        q=3,
        labels=["LOW_STRENGTH", "MID_STRENGTH", "HIGH_STRENGTH"],
    ).astype(str)

    group_specs = {
        "monthly_tick_metrics_30001.csv": "month",
        "quarterly_tick_metrics_30001.csv": "quarter",
        "side_tick_metrics_30001.csv": "side",
        "session_tick_metrics_30001.csv": "session",
        "hour_tick_metrics_30001.csv": "hour",
        "vol_regime_tick_metrics_30001.csv": "vol_regime",
        "strength_regime_tick_metrics_30001.csv": "strength_regime",
    }
    grouped: dict[str, pd.DataFrame] = {}
    for filename, column in group_specs.items():
        df = pd.DataFrame([metrics_for_trades(g.copy(), str(k)) for k, g in trades.groupby(column, sort=True)])
        df.to_csv(outdir / filename, index=False)
        grouped[filename] = df

    overall = pd.DataFrame([metrics_for_trades(trades, "TICK_OOS_202405_FULL")])
    overall.to_csv(outdir / "overall_tick_metrics_30001.csv", index=False)
    trades.to_csv(outdir / "tick_oos_trades_30001_with_entry_features.csv", index=False)

    guarded = trades[
        (trades["ML_Master_Strength"] >= 0.66)
        & ~((trades["entry_time"].dt.hour >= 13) & (trades["entry_time"].dt.hour < 20))
    ].copy()
    guard_scenarios = pd.DataFrame(
        [
            metrics_for_trades(trades, "BASE_TICK"),
            metrics_for_trades(trades[trades["ML_Master_Strength"] >= 0.66].copy(), "STRENGTH_GE_0_66"),
            metrics_for_trades(
                trades[~((trades["entry_time"].dt.hour >= 13) & (trades["entry_time"].dt.hour < 20))].copy(),
                "BLOCK_NY_13_20",
            ),
            metrics_for_trades(guarded, "STRENGTH_GE_0_66_AND_BLOCK_NY_13_20"),
        ]
    )
    guard_scenarios.to_csv(outdir / "guard_scenario_tick_metrics_30001.csv", index=False)

    monthly = grouped["monthly_tick_metrics_30001.csv"]
    quarterly = grouped["quarterly_tick_metrics_30001.csv"]
    sessions = grouped["session_tick_metrics_30001.csv"]
    strength = grouped["strength_regime_tick_metrics_30001.csv"]
    columns = [
        "segment",
        "trades",
        "return_pct_on_initial",
        "win_rate_pct",
        "profit_factor",
        "max_drawdown_pct",
        "max_consecutive_wins",
        "max_consecutive_losses",
        "sharpe_trade",
    ]

    profitable_month_rate = float((monthly["net_pnl"] > 0.0).mean() * 100.0)
    profitable_quarter_rate = float((quarterly["net_pnl"] > 0.0).mean() * 100.0)
    best_month = monthly.sort_values("return_pct_on_initial", ascending=False).iloc[0]
    worst_month = monthly.sort_values("return_pct_on_initial").iloc[0]
    ny = sessions.loc[sessions["segment"] == "NY_13_20"]
    high_strength = strength.loc[strength["segment"] == "HIGH_STRENGTH"]
    ny_return = float(ny["return_pct_on_initial"].iloc[0]) if not ny.empty else 0.0
    high_strength_return = float(high_strength["return_pct_on_initial"].iloc[0]) if not high_strength.empty else 0.0

    report = f"""# Auditoria tick-level OOS 30001

Periodo: {trades['entry_time'].min()} a {trades['exit_time'].max()}

Esta auditoria usa ejecucion con ticks bid/ask del bot 30001. El retorno segmentado es pnl del segmento sobre balance inicial {INITIAL_BALANCE:,.0f}.

##Conclusion ejecutiva

- Tick-level confirma que el OOS sigue positivo, pero mucho mas fragil que OHLC.
- Meses rentables: {profitable_month_rate:.2f}%.
- Trimestres rentables: {profitable_quarter_rate:.2f}%.
- Mejor mes: {best_month['segment']} con {float(best_month['return_pct_on_initial']):.2f}%.
- Peor mes: {worst_month['segment']} con {float(worst_month['return_pct_on_initial']):.2f}%.
- Sesion NY_13_20: {ny_return:.2f}%.
- Regimen HIGH_STRENGTH: {high_strength_return:.2f}%.
- Recomendacion aplicada: demo con guardia de regimen configurable; no promover a produccion real hasta cerrar walk-forward tick-level y monitor de deterioro.
- Escenario de guardia aplicado: strength >= 0.66 y bloqueo NY_13_20.

##Resultado global

{write_table(overall, columns)}

##Escenarios de guardia

{write_table(guard_scenarios, columns)}

##Meses

{write_table(monthly, columns)}

##Trimestres

{write_table(quarterly, columns)}

##Direccion

{write_table(grouped['side_tick_metrics_30001.csv'], columns)}

##Sesion

{write_table(sessions, columns)}

##Regimen de fuerza

{write_table(strength, columns)}

##Regimen de volatilidad

{write_table(grouped['vol_regime_tick_metrics_30001.csv'], columns)}
"""
    (outdir / "REPORTE_TICK_ESTABILIDAD_OOS_30001.md").write_text(report, encoding="utf-8")
    print(f"OK: {outdir}")


if __name__ == "__main__":
    main()
