import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from Capa_6.optimizer import run_optimization


def main():
    is_path = Path(os.environ.get("SOVEREIGN_IS_PATH", ROOT / "Capa_5" / "XAUUSD_M15_IS_PURGED.parquet"))
    oos_path = Path(os.environ.get("SOVEREIGN_OOS_PATH", ROOT / "Capa_5" / "XAUUSD_M15_OOS_202405.parquet"))
    params_path = Path(os.environ.get("SOVEREIGN_PARAMS_PATH", ROOT / "HMM_Params_15M.csv"))
    space_path = Path(os.environ.get("SOVEREIGN_PARAM_SPACE", ROOT / "Capa_6" / "parameter_space.json"))
    out_dir = Path(os.environ.get("SOVEREIGN_OPT_OUT", ROOT / "Capa_6" / "resultados_optimizacion"))
    dsr_trials = int(os.environ.get("DSR_TRIALS", "1"))

    max_candidates_env = os.environ.get("MAX_CANDIDATES", "8")
    max_candidates = None if max_candidates_env.strip().lower() in {"", "none", "all", "full"} else int(max_candidates_env)

    print("=========================================================================")
    print("CAPA 6: OPTIMIZACION Y REENTRENAMIENTO ANTI ALPHA DECAY")
    print("=========================================================================")
    print(f"IS: {is_path}")
    print(f"OOS holdout: {oos_path}")
    print(f"Parametros HMM: {params_path}")
    print(f"Espacio de busqueda: {space_path}")
    print(f"MAX_CANDIDATES: {max_candidates if max_candidates is not None else 'FULL'}")
    print(f"DSR_TRIALS: {dsr_trials}")

    ranking = run_optimization(
        is_path=is_path,
        oos_path=oos_path,
        params_path=params_path,
        space_path=space_path,
        out_dir=out_dir,
        max_candidates=max_candidates,
        dsr_trials=dsr_trials,
    )
    if ranking.empty:
        print("No se generaron candidatos.")
        return

    print("\nTop candidatos:")
    cols = [
        "score", "threshold", "min_strength", "vol_multiplier", "reward_risk",
        "closed_trades", "total_return_pct", "profit_factor", "max_drawdown_pct",
        "deflated_sharpe_probability",
    ]
    print(ranking[cols].head(10).to_string(index=False))
    print(f"\nResultados: {out_dir}")
    print("=========================================================================")


if __name__ == "__main__":
    main()
