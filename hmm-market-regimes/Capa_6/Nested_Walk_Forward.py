import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from Capa_6.nested_engine import run_nested_walk_forward


def main():
    data_path = Path(os.environ.get("NWF_DATA_PATH", ROOT / "Capa_5" / "XAUUSD_M15_IS_PURGED.parquet"))
    space_path = Path(os.environ.get("NWF_SPACE_PATH", ROOT / "Capa_6" / "parameter_space.json"))
    out_dir = Path(os.environ.get("NWF_OUT", ROOT / "Capa_6" / "nested_walk_forward"))
    n_folds = int(os.environ.get("NWF_FOLDS", "4"))
    purge_bars = int(os.environ.get("NWF_PURGE_BARS", "120"))
    dsr_trials = int(os.environ.get("DSR_TRIALS", "81"))
    max_candidates_env = os.environ.get("MAX_CANDIDATES", "FULL")
    max_candidates = None if max_candidates_env.strip().lower() in {"", "none", "all", "full"} else int(max_candidates_env)

    print("=========================================================================")
    print("CAPA 6: NESTED WALK-FORWARD")
    print("=========================================================================")
    print(f"Data: {data_path}")
    print(f"Folds: {n_folds}")
    print(f"Max candidates: {max_candidates if max_candidates is not None else 'FULL'}")
    print(f"DSR trials: {dsr_trials}")

    _, stability = run_nested_walk_forward(
        data_path=data_path,
        space_path=space_path,
        out_dir=out_dir,
        n_folds=n_folds,
        purge_bars=purge_bars,
        dsr_trials=dsr_trials,
        max_candidates=max_candidates,
    )
    if stability.empty:
        print("No se genero ranking estable.")
        return
    cols = [
        "robust_score", "threshold", "min_strength", "vol_multiplier", "reward_risk",
        "folds", "mean_pf", "min_pf", "mean_return", "min_return", "worst_dd", "mean_dsr",
    ]
    print("\nTop estabilidad nested:")
    print(stability[cols].head(10).to_string(index=False))
    print(f"\nResultados: {out_dir}")
    print("=========================================================================")


if __name__ == "__main__":
    main()
