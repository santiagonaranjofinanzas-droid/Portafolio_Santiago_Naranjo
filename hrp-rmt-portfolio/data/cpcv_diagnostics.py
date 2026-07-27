"""CPCV diagnostic and verification run on real ETF historical data.

Generates the validation mapping and logs details for the Phase F6 report.
"""

from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd

#Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from backtest.simulator import load_returns_panel, get_month_end_dates
from validation.cpcv import CombinatorialPurgedCV


def main():
    print("Loading data for CPCV diagnostics...")
    UNIVERSE_CSV = PROJECT_ROOT / "config" / "universe_v1_etf_longonly.csv"
    PRICE_DIR = PROJECT_ROOT / "data" / "raw" / "tiingo" / "prices"
    
    df_univ = pd.read_csv(UNIVERSE_CSV)
    tickers = df_univ["ticker"].tolist()
    
    # Load EOD panels to get date index
    returns_panel, _, _, _ = load_returns_panel(
        data_dir=str(PRICE_DIR),
        tickers=tickers,
    )
    all_daily_dates = returns_panel.index.sort_values()
    
    # Extract monthly rebalance dates (last business session of each month)
    # Filter by lookback start (similar to backtest start)
    rebalance_dates_raw = get_month_end_dates(all_daily_dates)
    
    # Exclude early rebalance dates that don't have enough history
    lookback = 252
    min_date = all_daily_dates[0] + pd.Timedelta(days=int(lookback * 1.5))
    rebalance_dates = pd.DatetimeIndex([d for d in rebalance_dates_raw if d >= min_date])
    
    print(f"Total Daily Dates: {len(all_daily_dates)}")
    print(f"Total Rebalance Dates (PIT): {len(rebalance_dates)}")
    
    # Initialize CPCV
    n_splits = 6
    n_test_splits = 2
    cv = CombinatorialPurgedCV(
        n_splits=n_splits,
        n_test_splits=n_test_splits,
        lookback=lookback,
        min_embargo=22,
    )
    
    folds = cv.split(rebalance_dates, all_daily_dates)
    paths = cv.generate_paths(folds)
    
    # Write CPCV fold partition map details
    print(f"\nCPCV Grid: N={n_splits}, k={n_test_splits} -> {len(folds)} Folds")
    print(f"Paths generated: {len(paths)} paths")
    
    # Calculate stats for the report
    fold_records = []
    for f in folds:
        train_count = len(f["train_dates"])
        test_count = len(f["test_dates"])
        
        # Purged and embargoed dates are rebalance dates excluded from training
        excluded_count = len(rebalance_dates) - train_count - test_count
        
        record = {
            "Fold": f["fold_idx"],
            "Test Blocks": f["test_blocks"],
            "Train Rebalances": train_count,
            "Test Rebalances": test_count,
            "Excluded (Purged+Embargoed)": excluded_count,
        }
        fold_records.append(record)
        
    df_folds = pd.DataFrame(fold_records)
    print("\nFold Stats Summary:")
    print(df_folds.to_string(index=False))
    
    print("\nDisjoint out-of-sample paths:")
    for i, p in enumerate(paths):
        print(f"Path {i}: Folds {p}")
        
    # We will write the report file directly after
    # Let's save a summary CSV for verification
    df_folds.to_csv("data/cpcv_summary.csv", index=False)


if __name__ == "__main__":
    main()
