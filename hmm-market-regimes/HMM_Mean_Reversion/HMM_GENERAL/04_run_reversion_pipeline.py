import os
import sys

import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from Capa_4.backtest_metrics import BacktestAssumptions, compute_backtest_metrics, run_backtest as run_trend_backtest
from SUB_RAMA_MEAN_REVERSION.analisis_coexistencia import run_coexistence_analysis
from SUB_RAMA_MEAN_REVERSION.backtest_mean_reversion import run_mean_reversion_backtest
from SUB_RAMA_MEAN_REVERSION.mean_reversion_signal import calculate_z_dev_in_memory, generate_mean_reversion_signals


ASSETS = {
    "NSXUSD": {
        "point": 1.0,
        "tick_size": 0.01,
        "tick_value": 1.0,
        "spread": 1.0,
        "slippage": 0.1,
        "commission": 3.0,
        "min_lot": 0.01,
        "lot_step": 0.01,
        "periods_per_year": 24 * 4 * 252,
    },
    "XAGUSD": {
        "point": 0.01,
        "tick_size": 0.001,
        "tick_value": 1.0,
        "spread": 0.02,
        "slippage": 0.005,
        "commission": 3.0,
        "min_lot": 0.01,
        "lot_step": 0.01,
        "periods_per_year": 24 * 4 * 252,
    },
    "XAUUSD": {
        "point": 0.01,
        "tick_size": 0.01,
        "tick_value": 1.0,
        "spread": 0.15,
        "slippage": 0.05,
        "commission": 3.0,
        "min_lot": 0.01,
        "lot_step": 0.01,
        "periods_per_year": 24 * 4 * 252,
    },
}

TREND_PARAMS = {
    "NSXUSD": {"min_strength": 0.35, "vol_multiplier": 2.5, "reward_risk": 1.5},
    "XAGUSD": {"min_strength": 0.40, "vol_multiplier": 3.0, "reward_risk": 2.0},
    "XAUUSD": {"min_strength": 0.30, "vol_multiplier": 2.5, "reward_risk": 2.5},
}


def build_assumptions(specs: dict, **overrides) -> BacktestAssumptions:
    params = {
        "initial_balance": 10000.0,
        "risk_percent": 1.0,
        "min_strength": 0.30,
        "vol_multiplier": 2.5,
        "reward_risk": 2.0,
        "use_partials": True,
        "max_lot": 10.0,
        "point": specs["point"],
        "tick_size": specs["tick_size"],
        "tick_value": specs["tick_value"],
        "spread_price": specs["spread"],
        "slippage_price": specs["slippage"],
        "commission_per_lot": specs["commission"],
        "min_lot": specs["min_lot"],
        "lot_step": specs["lot_step"],
        "periods_per_year": specs["periods_per_year"],
    }
    params.update(overrides)
    return BacktestAssumptions(**params)


def save_series(series: pd.Series, path: str, column: str = "equity") -> None:
    series.rename(column).to_frame().to_csv(path)


def _time_folds(df: pd.DataFrame, n_folds: int = 4) -> list[pd.DataFrame]:
    fold_size = len(df) // n_folds
    folds = []
    for fold in range(n_folds):
        start = fold * fold_size
        end = (fold + 1) * fold_size if fold < n_folds - 1 else len(df)
        folds.append(df.iloc[start:end].copy())
    return [fold for fold in folds if len(fold) > 100]


def optimize_mr_params(df_is: pd.DataFrame, assumptions: BacktestAssumptions) -> tuple[float, float, float, float, pd.DataFrame]:
    z_long_entries = [2.25, 2.50, 2.75, 3.00]
    z_short_entries = [2.50, 2.75, 3.00, 3.25]
    sl_multipliers = [2.50, 3.00, 3.50]
    total_trials = len(z_long_entries) * len(z_short_entries) * len(sl_multipliers)
    folds = _time_folds(df_is, n_folds=4)
    rows = []

    for z_l in z_long_entries:
        for z_s in z_short_entries:
            for sl_m in sl_multipliers:
                fold_scores = []
                fold_returns = []
                fold_dd = []
                fold_trades = []
                fold_pf = []

                for fold_df in folds:
                    cf, trades, equity = run_mean_reversion_backtest(fold_df, assumptions, z_l, z_s, sl_m)
                    metrics = compute_backtest_metrics(trades, cf, equity, assumptions, dsr_trials=total_trials)
                    fold_scores.append(metrics["deflated_sharpe_probability"])
                    fold_returns.append(metrics["total_return_pct"])
                    fold_dd.append(metrics["max_drawdown_pct"])
                    fold_trades.append(metrics["closed_trades"])
                    fold_pf.append(metrics["profit_factor"] if metrics["profit_factor"] != float("inf") else 10.0)

                min_trades = min(fold_trades) if fold_trades else 0
                median_dsr = float(pd.Series(fold_scores).median()) if fold_scores else 0.0
                median_return = float(pd.Series(fold_returns).median()) if fold_returns else -100.0
                worst_dd = float(pd.Series(fold_dd).min()) if fold_dd else -100.0
                median_pf = float(pd.Series(fold_pf).median()) if fold_pf else 0.0
                robust_score = median_dsr + (median_return / 100.0) + min(median_pf - 1.0, 0.50) + (worst_dd / 200.0)
                if min_trades < 10:
                    robust_score -= 1.0

                rows.append({
                    "z_entry_long": z_l,
                    "z_entry_short": z_s,
                    "mr_sl_atr_mult": sl_m,
                    "median_dsr_probability": median_dsr,
                    "median_return_pct": median_return,
                    "worst_drawdown_pct": worst_dd,
                    "median_profit_factor": median_pf,
                    "min_fold_trades": min_trades,
                    "robust_score": robust_score,
                })

    ranking = pd.DataFrame(rows).sort_values("robust_score", ascending=False).reset_index(drop=True)
    best = ranking.iloc[0]
    return (
        float(best["z_entry_long"]),
        float(best["z_entry_short"]),
        float(best["mr_sl_atr_mult"]),
        float(best["robust_score"]),
        ranking,
    )


def main():
    print("=========================================================")
    print("=== PIPELINE CORREGIDO: HMM + MEAN REVERSION ===")
    print("=========================================================")

    dir_resultados_raiz = os.path.join(ROOT, "Universo de activos", "resultados")
    dir_salida_mr = os.path.join(ROOT, "SUB_RAMA_MEAN_REVERSION", "resultados")
    os.makedirs(dir_salida_mr, exist_ok=True)

    report_data = []
    summary_rows = []

    for asset, specs in ASSETS.items():
        print(f"\n[*] Procesando activo: {asset}")
        asset_out = os.path.join(dir_salida_mr, asset)
        os.makedirs(asset_out, exist_ok=True)

        csv_is_base = os.path.join(dir_resultados_raiz, asset, f"{asset}_signals_IS.csv")
        csv_oos_base = os.path.join(dir_resultados_raiz, asset, f"{asset}_signals_OOS.csv")

        if not os.path.exists(csv_is_base) or not os.path.exists(csv_oos_base):
            print(f"[-] Saltando {asset}: faltan señales IS/OOS.")
            continue

        df_is = calculate_z_dev_in_memory(pd.read_csv(csv_is_base, index_col=0, parse_dates=True))
        df_oos_raw = pd.read_csv(csv_oos_base, index_col=0, parse_dates=True)

        assumptions_mr = build_assumptions(specs)
        z_l, z_s, sl_m, robust_score, ranking = optimize_mr_params(df_is, assumptions_mr)
        best_params = (z_l, z_s, sl_m)
        ranking.to_csv(os.path.join(asset_out, f"{asset}_mr_walkforward_dsr_ranking.csv"), index=False)
        print(f"   [+] MR robust best: z_long={z_l}, z_short={z_s}, sl_mult={sl_m}, score={robust_score:.4f}")

        csv_is_mr = os.path.join(dir_salida_mr, f"{asset}_mr_signals_IS.csv")
        csv_oos_mr = os.path.join(dir_salida_mr, f"{asset}_mr_signals_OOS.csv")
        generate_mean_reversion_signals(csv_is_base, z_l, z_s, csv_is_mr)
        generate_mean_reversion_signals(csv_oos_base, z_l, z_s, csv_oos_mr)

        df_oos = pd.read_csv(csv_oos_mr, index_col=0, parse_dates=True)
        oos_start = str(df_oos.index.min())
        oos_end = str(df_oos.index.max())

        cf_mr, tr_mr, eq_mr = run_mean_reversion_backtest(df_oos, assumptions_mr, z_l, z_s, sl_m)
        metrics_mr = compute_backtest_metrics(tr_mr, cf_mr, eq_mr, assumptions_mr)

        trend_cfg = TREND_PARAMS[asset]
        assumptions_trend = build_assumptions(specs, **trend_cfg)
        tr_tr, cf_tr, eq_tr = run_trend_backtest(df_oos, assumptions_trend)
        metrics_tr = compute_backtest_metrics(tr_tr, cf_tr, eq_tr, assumptions_trend)

        coex = run_coexistence_analysis(
            df_oos,
            assumptions_trend,
            tr_tr,
            eq_tr,
            tr_mr,
            eq_mr,
        )

        df_equity = pd.DataFrame(
            {
                "Trend_Only": eq_tr.reindex(df_oos.index).ffill(),
                "MR_Only": eq_mr.reindex(df_oos.index).ffill(),
                "Parallel_Coex_50_50": coex["portfolio_equity_series"],
                "Exclusive_Coex_Ledger": coex["exclusive_equity_series"],
            }
        )
        df_equity.to_csv(os.path.join(dir_salida_mr, f"{asset}_coexistence_equity.csv"))

        tr_tr.to_csv(os.path.join(asset_out, f"{asset}_trend_trades_OOS.csv"), index=False)
        cf_tr.to_csv(os.path.join(asset_out, f"{asset}_trend_cashflows_OOS.csv"), index=False)
        save_series(eq_tr, os.path.join(asset_out, f"{asset}_trend_equity_OOS.csv"))
        tr_mr.to_csv(os.path.join(asset_out, f"{asset}_mr_trades_OOS.csv"), index=False)
        cf_mr.to_csv(os.path.join(asset_out, f"{asset}_mr_cashflows_OOS.csv"), index=False)
        save_series(eq_mr, os.path.join(asset_out, f"{asset}_mr_equity_OOS.csv"))
        coex["exclusive_trades"].to_csv(os.path.join(asset_out, f"{asset}_exclusive_coex_trades_OOS.csv"), index=False)

        row = {
            "asset": asset,
            "oos_start": oos_start,
            "oos_end": oos_end,
            "z_entry_long": z_l,
            "z_entry_short": z_s,
            "mr_sl_atr_mult": sl_m,
            "mr_robust_score": robust_score,
            "mr_is_median_dsr_probability": float(ranking.iloc[0]["median_dsr_probability"]),
            "mr_is_median_return_pct": float(ranking.iloc[0]["median_return_pct"]),
            "mr_is_worst_drawdown_pct": float(ranking.iloc[0]["worst_drawdown_pct"]),
            "correlation_daily_equity_returns": coex["correlation"],
            "trend_profit": metrics_tr["net_profit"],
            "trend_return_pct": metrics_tr["total_return_pct"],
            "trend_sharpe": metrics_tr["sharpe_ratio"],
            "trend_max_dd_pct": metrics_tr["max_drawdown_pct"],
            "trend_trades": metrics_tr["closed_trades"],
            "mr_profit": metrics_mr["net_profit"],
            "mr_return_pct": metrics_mr["total_return_pct"],
            "mr_sharpe": metrics_mr["sharpe_ratio"],
            "mr_max_dd_pct": metrics_mr["max_drawdown_pct"],
            "mr_trades": metrics_mr["closed_trades"],
            "parallel_profit": coex["par_net_profit"],
            "parallel_return_pct": coex["par_return_pct"],
            "parallel_sharpe": coex["par_sharpe"],
            "parallel_max_dd_pct": coex["par_max_dd_pct"],
            "exclusive_profit": coex["excl_net_profit"],
            "exclusive_return_pct": coex["excl_return_pct"],
            "exclusive_sharpe": coex["excl_sharpe"],
            "exclusive_max_dd_pct": coex["excl_max_dd_pct"],
            "exclusive_trades": coex["excl_total_trades"],
        }
        summary_rows.append(row)
        report_data.append(row)
        print(f"   [+] OOS completado: Trend ${row['trend_profit']:.2f}, MR ${row['mr_profit']:.2f}, Parallel ${row['parallel_profit']:.2f}, Exclusive ${row['exclusive_profit']:.2f}")

    summary = pd.DataFrame(summary_rows)
    summary.to_csv(os.path.join(dir_salida_mr, "REAL_RESULTS_SUMMARY.csv"), index=False)

    report_path = os.path.join(ROOT, "SUB_RAMA_MEAN_REVERSION", "REPORTE_SISTEMA_DUAL.md")
    write_markdown_report(report_path, report_data)
    print(f"\n[+] Pipeline corregido finalizado: {report_path}")


def _fmt_money(value: float) -> str:
    return f"${value:,.2f}"


def write_markdown_report(path: str, data: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write("# Reporte Corregido: HMM Trend + Mean Reversion (OOS)\n\n")
        f.write("> Este reporte fue regenerado desde ledgers OOS. Correcciones aplicadas: filtros ex-ante de volatilidad/aceleracion/momentum, optimizacion robusta por folds con DSR, desempacado correcto del backtest tendencial, equity MR con mark-to-market, señales ejecutables desplazadas, TP parcial MR, coexistencia paralela 50/50 y coexistencia exclusiva por ledger con expectancy reciente.\n\n")

        f.write("## Parametros MR Calibrados IS\n\n")
        f.write(" Activo  OOS  Z Long  Z Short  SL ATR Mult  Score Robusto  DSR Mediano IS  Retorno Mediano IS  Peor DD IS \n")
        f.write(" :---  :---  ---:  ---:  ---:  ---:  ---:  ---:  ---: \n")
        for d in data:
            f.write(f" {d['asset']}  {d['oos_start']} a {d['oos_end']}  {d['z_entry_long']}  {d['z_entry_short']}  {d['mr_sl_atr_mult']}  {d['mr_robust_score']:.4f}  {d['mr_is_median_dsr_probability']:.4f}  {d['mr_is_median_return_pct']:.2f}%  {d['mr_is_worst_drawdown_pct']:.2f}% \n")

        f.write("\n## Resultados Reales OOS\n\n")
        for d in data:
            f.write(f"### {d['asset']}\n\n")
            f.write(f"Correlacion diaria de equity Trend/MR: `{d['correlation_daily_equity_returns']:.4f}`\n\n")
            f.write(" Sistema  Retorno  Profit  Sharpe  Max DD  Trades \n")
            f.write(" :---  ---:  ---:  ---:  ---:  ---: \n")
            f.write(f" HMM Trend Only  {d['trend_return_pct']:.2f}%  {_fmt_money(d['trend_profit'])}  {d['trend_sharpe']:.2f}  {d['trend_max_dd_pct']:.2f}%  {d['trend_trades']} \n")
            f.write(f" Mean Reversion Only  {d['mr_return_pct']:.2f}%  {_fmt_money(d['mr_profit'])}  {d['mr_sharpe']:.2f}  {d['mr_max_dd_pct']:.2f}%  {d['mr_trades']} \n")
            f.write(f" Parallel 50/50 Sleeves  {d['parallel_return_pct']:.2f}%  {_fmt_money(d['parallel_profit'])}  {d['parallel_sharpe']:.2f}  {d['parallel_max_dd_pct']:.2f}%  N/A \n")
            f.write(f" Exclusive Ledger Dynamic Expectancy  {d['exclusive_return_pct']:.2f}%  {_fmt_money(d['exclusive_profit'])}  {d['exclusive_sharpe']:.2f}  {d['exclusive_max_dd_pct']:.2f}%  {d['exclusive_trades']} \n\n")

        f.write("## Veredicto\n\n")
        f.write("Estos numeros sustituyen al reporte anterior. La seleccion MR ya no optimiza por profit sino por robustez DSR en folds temporales. La coexistencia paralela no usa optimizacion L1 ni correlacion fija; es una suma auditada de sleeves 50/50. La coexistencia exclusiva filtra ledgers sin solape usando expectancy reciente. Para produccion real todavia conviene portar exactamente este ledger a MT5/tick-level antes de operar capital.\n")


if __name__ == "__main__":
    main()
