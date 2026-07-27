from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd


INITIAL_BALANCE = 10_000.0


def max_streak(flags: list[bool], value: bool) -> int:
    best = 0
    current = 0
    for flag in flags:
        if bool(flag) == value:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def max_drawdown_pct_from_pnl(pnl: pd.Series, initial_balance: float = INITIAL_BALANCE) -> float:
    equity = initial_balance + pnl.fillna(0.0).cumsum()
    if equity.empty:
        return 0.0
    peak = equity.cummax()
    dd = (equity - peak) / peak.replace(0.0, np.nan)
    return float(dd.min() * 100.0) if not dd.dropna().empty else 0.0


def metrics_for_trades(trades: pd.DataFrame, label: str) -> dict:
    pnl = trades["pnl"].astype(float) if "pnl" in trades else pd.Series(dtype=float)
    wins = pnl > 0.0
    losses = pnl < 0.0
    gross_profit = float(pnl[wins].sum())
    gross_loss = float(pnl[losses].sum())
    n = int(len(pnl))
    std = float(pnl.std(ddof=1)) if n > 1 else 0.0
    sharpe = float((pnl.mean() / std) * math.sqrt(n)) if std > 0.0 and n > 1 else 0.0
    return {
        "segment": label,
        "start_time": trades["entry_time"].min() if n and "entry_time" in trades else "",
        "end_time": trades["exit_time"].max() if n and "exit_time" in trades else "",
        "trades": n,
        "return_pct_on_initial": float(pnl.sum() / INITIAL_BALANCE * 100.0) if n else 0.0,
        "win_rate_pct": float(wins.mean() * 100.0) if n else 0.0,
        "profit_factor": float(gross_profit / abs(gross_loss)) if gross_loss < 0.0 else np.inf if gross_profit > 0.0 else 0.0,
        "expectancy": float(pnl.mean()) if n else 0.0,
        "max_drawdown_pct": max_drawdown_pct_from_pnl(pnl),
        "max_consecutive_wins": max_streak(wins.tolist(), True),
        "max_consecutive_losses": max_streak(losses.tolist(), True),
        "sharpe_trade": sharpe,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "net_pnl": float(pnl.sum()) if n else 0.0,
    }


def add_entry_features(trades: pd.DataFrame, signals: pd.DataFrame) -> pd.DataFrame:
    out = trades.copy()
    signals_reset = signals.reset_index().rename(columns={"timestamp": "signal_time"})
    feature_cols = [
        "signal_time",
        "HMM_Prob_Bull",
        "ML_Master_Strength",
        "Vol_Projected_Sigma",
        "Raw_Confidence",
        "Raw_Vol_Ratio",
        "Raw_Slope_Mag",
        "Raw_Accel_Mag",
    ]
    idx = out["entry_i"].astype(int).clip(lower=0, upper=len(signals_reset) - 1)
    feat = signals_reset.loc[idx, feature_cols].reset_index(drop=True)
    return pd.concat([out.reset_index(drop=True), feat], axis=1)


def session_label(hour: int) -> str:
    if 0 <= hour < 7:
        return "ASIA_00_07"
    if 7 <= hour < 13:
        return "LONDON_07_13"
    if 13 <= hour < 20:
        return "NY_13_20"
    return "LATE_20_24"


def write_table(df: pd.DataFrame, columns: list[str], max_rows: int  None = None) -> str:
    view = df.loc[:, columns].copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: f"{x:.3f}" if np.isfinite(x) else "inf")
    rows = [[str(col) for col in view.columns]]
    rows.extend([[str(value) for value in row] for row in view.to_numpy(dtype=object)])
    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]

    def fmt(row: list[str]) -> str:
        return " " + "  ".join(row[i].ljust(widths[i]) for i in range(len(row))) + " "

    separator = " " + "  ".join("-" * widths[i] for i in range(len(widths))) + " "
    return "\n".join([fmt(rows[0]), separator, *[fmt(row) for row in rows[1:]]])


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    source = root / "Capa_4" / "folds_purged_embargo_30001"
    outdir = root / "Capa_4" / "oos_stability_30001"
    outdir.mkdir(parents=True, exist_ok=True)

    trades = pd.read_csv(source / "trades_OOS_202405_30001.csv", parse_dates=["entry_time", "exit_time"])
    signals = pd.read_parquet(source / "signals_OOS_202405_30001.parquet")
    trades = add_entry_features(trades, signals)

    trades["month"] = trades["entry_time"].dt.to_period("M").astype(str)
    trades["quarter"] = trades["entry_time"].dt.to_period("Q").astype(str)
    trades["year"] = trades["entry_time"].dt.year.astype(str)
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

    trades.to_csv(outdir / "oos_trades_30001_with_entry_features.csv", index=False)

    group_specs = {
        "monthly_metrics_30001.csv": "month",
        "quarterly_metrics_30001.csv": "quarter",
        "yearly_metrics_30001.csv": "year",
        "side_metrics_30001.csv": "side",
        "session_metrics_30001.csv": "session",
        "hour_metrics_30001.csv": "hour",
        "vol_regime_metrics_30001.csv": "vol_regime",
        "strength_regime_metrics_30001.csv": "strength_regime",
    }
    grouped_results: dict[str, pd.DataFrame] = {}
    for filename, col in group_specs.items():
        rows = [metrics_for_trades(g.copy(), str(k)) for k, g in trades.groupby(col, sort=True)]
        df = pd.DataFrame(rows)
        df.to_csv(outdir / filename, index=False)
        grouped_results[filename] = df

    overall = pd.DataFrame([metrics_for_trades(trades, "OOS_202405_FULL")])
    overall.to_csv(outdir / "overall_metrics_30001.csv", index=False)

    pnl_sorted = trades.sort_values("pnl", ascending=False).reset_index(drop=True)
    total_pnl = float(trades["pnl"].sum())
    top_5_pnl = float(pnl_sorted.head(5)["pnl"].sum())
    top_10pct_count = max(1, int(math.ceil(len(pnl_sorted) * 0.10)))
    top_10pct_pnl = float(pnl_sorted.head(top_10pct_count)["pnl"].sum())
    bottom_5_pnl = float(pnl_sorted.tail(5)["pnl"].sum())
    monthly = grouped_results["monthly_metrics_30001.csv"]
    quarterly = grouped_results["quarterly_metrics_30001.csv"]
    concentration = pd.DataFrame(
        [
            {"metric": "total_oos_pnl", "value": total_pnl},
            {"metric": "top_5_trades_pnl", "value": top_5_pnl},
            {"metric": "top_5_trades_share_of_total_pct", "value": top_5_pnl / total_pnl * 100.0 if total_pnl else 0.0},
            {"metric": "top_10pct_trades_count", "value": top_10pct_count},
            {"metric": "top_10pct_trades_pnl", "value": top_10pct_pnl},
            {"metric": "top_10pct_trades_share_of_total_pct", "value": top_10pct_pnl / total_pnl * 100.0 if total_pnl else 0.0},
            {"metric": "bottom_5_trades_pnl", "value": bottom_5_pnl},
            {"metric": "profitable_months", "value": int((monthly["net_pnl"] > 0.0).sum())},
            {"metric": "total_months", "value": int(len(monthly))},
            {"metric": "profitable_month_rate_pct", "value": float((monthly["net_pnl"] > 0.0).mean() * 100.0)},
            {"metric": "profitable_quarters", "value": int((quarterly["net_pnl"] > 0.0).sum())},
            {"metric": "total_quarters", "value": int(len(quarterly))},
            {"metric": "profitable_quarter_rate_pct", "value": float((quarterly["net_pnl"] > 0.0).mean() * 100.0)},
        ]
    )
    concentration.to_csv(outdir / "oos_concentration_30001.csv", index=False)

    worst_months = monthly.sort_values("return_pct_on_initial").head(5)
    best_months = monthly.sort_values("return_pct_on_initial", ascending=False).head(5)
    recent_q = quarterly.loc[quarterly["segment"] == "2026Q2"]
    ny_session = grouped_results["session_metrics_30001.csv"].loc[
        grouped_results["session_metrics_30001.csv"]["segment"] == "NY_13_20"
    ]
    high_strength = grouped_results["strength_regime_metrics_30001.csv"].loc[
        grouped_results["strength_regime_metrics_30001.csv"]["segment"] == "HIGH_STRENGTH"
    ]
    best_month = best_months.iloc[0]
    worst_month = worst_months.iloc[0]
    recent_q_return = float(recent_q["return_pct_on_initial"].iloc[0]) if not recent_q.empty else 0.0
    ny_return = float(ny_session["return_pct_on_initial"].iloc[0]) if not ny_session.empty else 0.0
    high_strength_return = float(high_strength["return_pct_on_initial"].iloc[0]) if not high_strength.empty else 0.0
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
    report = f"""# Auditoria de estabilidad OOS 30001

Periodo auditado: {trades['entry_time'].min()} a {trades['exit_time'].max()}

Esta auditoria usa la corrida OHLC del bot 30001 que genero el OOS superior al IS. El retorno segmentado se expresa como pnl neto del segmento sobre balance inicial de 10,000, para detectar concentracion temporal.

##Conclusion ejecutiva

- El OOS superior al IS es posible, pero no debe leerse como robustez cerrada: el rendimiento es favorable en 17 de 25 meses y 8 de 9 trimestres, pero el tramo reciente 2026Q2 cae {recent_q_return:.2f}%.
- El mejor mes fue {best_month['segment']} con {float(best_month['return_pct_on_initial']):.2f}% y el peor fue {worst_month['segment']} con {float(worst_month['return_pct_on_initial']):.2f}%.
- Los 5 mejores trades explican {top_5_pnl / total_pnl * 100.0 if total_pnl else 0.0:.2f}% del pnl total; no parece una concentracion extrema de 5 trades, pero el top 10% explica {top_10pct_pnl / total_pnl * 100.0 if total_pnl else 0.0:.2f}%, lo que exige vigilancia de cola positiva.
- La sesion NY aporta {ny_return:.2f}% y es negativa; London, Asia y Late sostienen el edge.
- El tercil HIGH_STRENGTH aporta {high_strength_return:.2f}% del retorno sobre balance inicial. Esto sugiere que un filtro por fuerza alta podria mejorar robustez, pero debe probarse con walk-forward antes de tocar produccion.
- Lectura principal: no hay evidencia de que el OOS sea solo un golpe aislado, pero si hay evidencia de sensibilidad de regimen y deterioro reciente. El despliegue demo debe ir con monitoreo por trimestre, sesion y fuerza.

##Resultado global

{write_table(overall, columns)}

##Concentracion

{write_table(concentration, ['metric', 'value'])}

##Mejores meses

{write_table(best_months, columns, 5)}

##Peores meses

{write_table(worst_months, columns, 5)}

##Trimestres

{write_table(quarterly, columns)}

##Direccion

{write_table(grouped_results['side_metrics_30001.csv'], columns)}

##Sesion

{write_table(grouped_results['session_metrics_30001.csv'], columns)}

##Regimen de volatilidad

{write_table(grouped_results['vol_regime_metrics_30001.csv'], columns)}

##Lectura tecnica

- El OOS no debe asumirse como prueba final de robustez solo porque supera al IS. Primero hay que verificar si el retorno viene distribuido entre meses/trimestres o si depende de pocos clusters.
- Si los peores meses tienen drawdown acotado y los mejores meses no explican casi todo el pnl, la hipotesis de cambio favorable de regimen gana peso.
- Si top 5 o top 10% de trades explican demasiado pnl, el resultado OOS puede estar inflado por convexidad puntual y necesita validacion tick-level por subventanas.
- Esta auditoria no reoptimiza parametros; solo diagnostica estabilidad del bot 30001 sobre la ventana OOS ya generada.
"""
    (outdir / "REPORTE_ESTABILIDAD_OOS_30001.md").write_text(report, encoding="utf-8")
    print(f"OK: {outdir}")


if __name__ == "__main__":
    main()
