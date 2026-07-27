import os
import sys
from pathlib import Path

import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from Capa_6.optimizer import evaluate_candidate, iter_candidates, load_parameter_space, score_metrics, split_train_validation


def main():
    oos_path = Path(os.environ.get("SOVEREIGN_RECENT_SOURCE", ROOT / "Capa_5" / "XAUUSD_M15_OOS_202405.parquet"))
    params_path = Path(os.environ.get("SOVEREIGN_PARAMS_PATH", ROOT / "HMM_Params_15M.csv"))
    space_path = Path(os.environ.get("SOVEREIGN_PARAM_SPACE", ROOT / "Capa_6" / "parameter_space.json"))
    out_dir = Path(os.environ.get("SOVEREIGN_RECENT_OUT", ROOT / "Capa_6" / "resultados_reentrenamiento_reciente"))
    recent_start = pd.Timestamp(os.environ.get("RECENT_START", "2025-01-01"))
    max_candidates_env = os.environ.get("MAX_CANDIDATES", "FULL")
    max_candidates = None if max_candidates_env.strip().lower() in {"", "none", "all", "full"} else int(max_candidates_env)
    dsr_trials = int(os.environ.get("DSR_TRIALS", "81"))

    out_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_parquet(oos_path)
    recent_df = df.loc[df.index >= recent_start].copy()
    if len(recent_df) < 1000:
        raise ValueError("Ventana reciente demasiado pequena")

    _, validation_df = split_train_validation(recent_df, validation_fraction=0.35, purge_bars=120)
    space = load_parameter_space(space_path)
    candidates = iter_candidates(space)
    if max_candidates is not None:
        candidates = candidates[:max(1, int(max_candidates))]

    print("=========================================================================")
    print("CAPA 6: REENTRENAMIENTO ROLLING RECIENTE")
    print("=========================================================================")
    print(f"Fuente reciente: {oos_path}")
    print(f"Inicio reciente: {recent_start}")
    print(f"Barras recientes: {len(recent_df)}")
    print(f"Barras validacion interna: {len(validation_df)}")
    print(f"Candidatos: {len(candidates)}")
    print(f"DSR_TRIALS: {dsr_trials}")

    cache = {}
    rows = []
    for idx, candidate in enumerate(candidates, start=1):
        metrics, trades, cashflows, equity = evaluate_candidate(candidate, validation_df, params_path, dsr_trials, cache)
        row = {**candidate, **metrics}
        row["score"] = score_metrics(metrics, space)
        rows.append(row)
        print(f"[{idx}/{len(candidates)}] score={row['score']:.4f} pf={row['profit_factor']:.3f} dd={row['max_drawdown_pct']:.2f}% {candidate}")

    ranking = pd.DataFrame(rows).sort_values("score", ascending=False).reset_index(drop=True)
    ranking.to_csv(out_dir / "ranking_reciente.csv", index=False)
    best = ranking.iloc[0]
    best_payload = {
        "threshold": float(best["threshold"]),
        "min_strength": float(best["min_strength"]),
        "vol_multiplier": float(best["vol_multiplier"]),
        "reward_risk": float(best["reward_risk"]),
        "kalman_gate": bool(best["kalman_gate"]),
        "score": float(best["score"]),
        "recent_start": str(recent_start),
        "note": "Candidato adaptativo reciente; validar en forward/paper antes de pasar a real.",
    }
    import json
    with open(out_dir / "recent_best_params.json", "w", encoding="utf-8") as handle:
        json.dump(best_payload, handle, indent=2)

    print("\nTop recientes:")
    cols = [
        "score", "threshold", "min_strength", "vol_multiplier", "reward_risk",
        "closed_trades", "total_return_pct", "profit_factor", "max_drawdown_pct",
        "deflated_sharpe_probability",
    ]
    print(ranking[cols].head(10).to_string(index=False))
    print(f"Resultados: {out_dir}")
    print("=========================================================================")


if __name__ == "__main__":
    main()
