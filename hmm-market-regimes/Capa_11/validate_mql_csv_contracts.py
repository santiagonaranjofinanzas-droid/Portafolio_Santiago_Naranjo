from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def check(path: Path, expected_columns: int) -> None:
    df = pd.read_csv(path)
    actual = len(df.columns)
    if actual != expected_columns:
        raise SystemExit(f"CSV contract mismatch: {path} has {actual} columns, expected {expected_columns}")
    print(f"OK {path} columns={actual}")


def main() -> None:
    check(ROOT / "MT5_Version_50001" / "Files" / "Sovereign_Config_50001.csv", 42)
    check(ROOT / "MT5_Version_50001" / "Files" / "Sovereign_Layer_Config_50001.csv", 23)
    check(ROOT / "MT5_Version_50001" / "Files" / "HMM_Params_15M_50001.csv", 18)


if __name__ == "__main__":
    main()
