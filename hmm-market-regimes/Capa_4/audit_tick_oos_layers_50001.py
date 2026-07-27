from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from Capa_4.audit_oos_stability_30001 import metrics_for_trades, session_label, write_table


MIN_STRENGTH = 0.50
SIGMA_MIN = 0.0008412616967549172
SIGMA_MAX = 0.0032338662645819277


def main() -> None:
    source = ROOT / "Capa_4" / "comparacion_oos_30001_40001_accel18"
    outdir = ROOT / "Capa_4" / "tick_oos_layers_50001"
    outdir.mkdir(parents=True, exist_ok=True)

    trades = pd.read_csv(source / "tick_trades_oos_40001.csv", parse_dates=["entry_time", "exit_time"])
    signals = pd.read_parquet(source / "signals_oos_40001.parquet").reset_index()
    idx = trades["entry_i"].astype(int).clip(0, len(signals) - 1)
    features = signals.loc[
        idx,
        [
            "timestamp",
            "HMM_Prob_Bull",
            "ML_Master_Strength",
            "Vol_Projected_Sigma",
            "Regime_Buffer_18",
            "Raw_Accel_Mag",
        ],
    ].reset_index(drop=True)
    trades = pd.concat([trades.reset_index(drop=True), features], axis=1)
    trades["hour"] = trades["entry_time"].dt.hour
    trades["session"] = trades["hour"].map(session_label)
    trades["month"] = trades["entry_time"].dt.to_period("M").astype(str)
    trades["quarter"] = trades["entry_time"].dt.to_period("Q").astype(str)

    layered_mask = (
        ((trades["hour"] >= 7) & (trades["hour"] < 13)  ((trades["hour"] >= 20) & (trades["hour"] < 24)))
        & (trades["ML_Master_Strength"] >= MIN_STRENGTH)
        & (trades["Vol_Projected_Sigma"] >= SIGMA_MIN)
        & (trades["Vol_Projected_Sigma"] <= SIGMA_MAX)
    )
    layered = trades[layered_mask].copy()

    scenarios = pd.DataFrame(
        [
            metrics_for_trades(trades, "BASE_50001_EQ_40001_TICK"),
            metrics_for_trades(
                trades[(trades["hour"] >= 7) & (trades["hour"] < 13)  ((trades["hour"] >= 20) & (trades["hour"] < 24))].copy(),
                "SESSION_LONDON_LATE",
            ),
            metrics_for_trades(
                trades[
                    ((trades["hour"] >= 7) & (trades["hour"] < 13)  ((trades["hour"] >= 20) & (trades["hour"] < 24)))
                    & (trades["ML_Master_Strength"] >= MIN_STRENGTH)
                ].copy(),
                "SESSION_PLUS_STRENGTH_GE_0_50",
            ),
            metrics_for_trades(layered, "LAYERED_SESSION_STRENGTH_SIGMA"),
        ]
    )
    scenarios.to_csv(outdir / "layer_scenario_tick_metrics_50001.csv", index=False)
    trades.to_csv(outdir / "tick_oos_trades_50001_with_entry_features.csv", index=False)

    monthly = pd.DataFrame([metrics_for_trades(g.copy(), str(k)) for k, g in layered.groupby("month", sort=True)])
    quarterly = pd.DataFrame([metrics_for_trades(g.copy(), str(k)) for k, g in layered.groupby("quarter", sort=True)])
    session = pd.DataFrame([metrics_for_trades(g.copy(), str(k)) for k, g in layered.groupby("session", sort=True)])
    monthly.to_csv(outdir / "monthly_layered_tick_metrics_50001.csv", index=False)
    quarterly.to_csv(outdir / "quarterly_layered_tick_metrics_50001.csv", index=False)
    session.to_csv(outdir / "session_layered_tick_metrics_50001.csv", index=False)

    cols = [
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
    report = f"""# Auditoria capas tick-level 50001

Base usada: 50001 hereda parametros del 40001 actual, por eso la auditoria parte de `tick_trades_oos_40001.csv`.

##Capas activadas

- Sesion: solo London 07:00-12:59 y Late 20:00-23:59 hora servidor.
- Fuerza minima: {MIN_STRENGTH:.2f}.
- Sigma proyectada: [{SIGMA_MIN:.12f}, {SIGMA_MAX:.12f}].
- En MQL se agregan ademas filtro de spread, pausa por racha de perdidas, salida por flip de regimen y stop temporal.

##Escenarios

{write_table(scenarios, cols)}

##Trimestres layered

{write_table(quarterly, cols)}

##Meses layered

{write_table(monthly, cols)}

##Sesion layered

{write_table(session, cols)}

##Decision

El escenario layered mejora PF y DD frente al 50001 base, pero sigue siendo demo/paper. La capa no se considera robusta final hasta validarse con walk-forward tick-level y forward posterior al periodo usado para decidir estas reglas.
"""
    (outdir / "REPORTE_CAPAS_TICK_50001.md").write_text(report, encoding="utf-8")
    print(f"OK: {outdir}")


if __name__ == "__main__":
    main()
