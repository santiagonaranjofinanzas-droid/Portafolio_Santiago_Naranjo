"""Module for managing the Point-In-Time (PIT) eligible universe of assets."""

from __future__ import annotations
import csv
from datetime import datetime
from pathlib import Path
import pandas as pd
from data.stale_price_detector import detect_stale_prices


class PITUniverseManager:
    """Manages the point-in-time eligibility of assets in the portfolio."""

    def __init__(
        self,
        universe_csv: Path  str,
        price_dir: Path  str,
        min_history_days: int = 756,  # 3 years of daily business days (3 * 252)
        min_adv_usd: float = 5_000_000.0,  # 5 million USD ADV
    ):
        self.universe_csv = Path(universe_csv)
        self.price_dir = Path(price_dir)
        self.min_history_days = min_history_days
        self.min_adv_usd = min_adv_usd
        
        self.universe_assets = self._load_universe_metadata()
        self.price_data: dict[str, pd.DataFrame] = {}
        self._load_and_preprocess_prices()

    def _load_universe_metadata(self) -> list[dict[str, str]]:
        """Load the universe metadata from CSV."""
        if not self.universe_csv.exists():
            raise FileNotFoundError(f"Universe CSV not found at {self.universe_csv}")
        with self.universe_csv.open("r", encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    def _load_and_preprocess_prices(self) -> None:
        """Load and preprocess the EOD price CSVs for all assets in the universe."""
        for asset in self.universe_assets:
            ticker = asset["ticker"].upper()
            file_path = self.price_dir / f"{ticker}.csv"
            if not file_path.exists():
                # We skip missing files but log/alert if necessary.
                # In smoke test/coverage we ensure all 45 exist.
                continue

            # Load EOD prices
            df = pd.read_csv(file_path)
            if df.empty:
                continue

            # Convert date to standard pd.Timestamp and normalize
            df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None).dt.normalize()
            df = df.sort_values("date").reset_index(drop=True)

            # Detect stale price rows
            df["is_stale"] = detect_stale_prices(df)

            # Compute USD Volume
            df["usd_volume"] = df["adjVolume"] * df["adjClose"]

            # Compute 20-day rolling ADV (Average Daily Volume in USD)
            # ADV is calculated only on the past 20 trading days (inclusive of current)
            df["adv_20"] = df["usd_volume"].rolling(window=20, min_periods=20).mean()

            # Cumulative history count
            df["history_count"] = range(1, len(df) + 1)

            # Set date as index for fast PIT lookups
            df.set_index("date", inplace=True)
            self.price_data[ticker] = df

    def get_universe_state(self, date_t: str  datetime  pd.Timestamp) -> dict[str, object]:
        """Get the detailed state of the universe at a specific date.
        
        Returns a dict containing:
        - 'date': The evaluation date (normalized)
        - 'eligible_tickers': List of tickers that are eligible for HRP allocation
        - 'metrics': Density and exclusions metrics (N_elegible, N_con_historial_suficiente, etc.)
        - 'asset_details': Details for each asset (status, adv, history_count, is_stale)
        """
        ts_t = pd.to_datetime(date_t).tz_localize(None).normalize()

        eligible_tickers = []
        n_active = 0
        n_con_historial_suficiente = 0
        n_excluido_por_lookback = 0
        n_excluido_por_stale_liquidez = 0

        asset_details = {}

        for asset in self.universe_assets:
            ticker = asset["ticker"].upper()
            df = self.price_data.get(ticker)

            if df is None or df.empty:
                asset_details[ticker] = {"status": "missing", "reason": "No price file found"}
                continue

            # Get the point-in-time row. If date_t is not in index, find the last available row <= date_t
            # to avoid look-ahead bias and represent data available at that moment.
            past_rows = df.loc[df.index <= ts_t]
            if past_rows.empty:
                # The asset has not started trading yet relative to date_t
                asset_details[ticker] = {"status": "not_started", "reason": f"Inception after {ts_t.date()}"}
                continue

            # This is the point-in-time record available at date_t
            pit_record = past_rows.iloc[-1]
            record_date = past_rows.index[-1]

            # If the record is too old, the asset might be retired/delisted.
            # We assume it is retired if the last update is older than e.g. 10 business days
            # compared to ts_t (or if ts_t is after a known delisting date).
            days_since_last_quote = (ts_t - record_date).days
            if days_since_last_quote > 15:
                asset_details[ticker] = {
                    "status": "retired",
                    "reason": f"No data since {record_date.date()} (days={days_since_last_quote})",
                }
                continue

            n_active += 1

            # Check history requirement
            history_count = int(pit_record["history_count"])
            has_sufficient_history = history_count >= self.min_history_days

            if not has_sufficient_history:
                n_excluido_por_lookback += 1
                asset_details[ticker] = {
                    "status": "excluded_lookback",
                    "history_count": history_count,
                    "reason": f"History count {history_count} < {self.min_history_days}",
                }
                continue

            n_con_historial_suficiente += 1

            # Check liquidity requirement
            adv_20 = float(pit_record["adv_20"]) if not pd.isna(pit_record["adv_20"]) else 0.0
            is_stale = bool(pit_record["is_stale"])
            meets_liquidity = adv_20 >= self.min_adv_usd and not is_stale

            if not meets_liquidity:
                n_excluido_por_stale_liquidez += 1
                reason = "Stale price at date" if is_stale else f"ADV20 {adv_20:,.2f} < {self.min_adv_usd:,.2f}"
                asset_details[ticker] = {
                    "status": "excluded_liquidity",
                    "adv_20": adv_20,
                    "is_stale": is_stale,
                    "reason": reason,
                }
                continue

            # Eligible!
            eligible_tickers.append(ticker)
            asset_details[ticker] = {
                "status": "eligible",
                "adv_20": adv_20,
                "history_count": history_count,
                "is_stale": is_stale,
            }

        n_elegible = len(eligible_tickers)

        metrics = {
            "N_active": n_active,
            "N_con_historial_suficiente": n_con_historial_suficiente,
            "N_excluido_por_lookback": n_excluido_por_lookback,
            "N_excluido_por_stale_liquidez": n_excluido_por_stale_liquidez,
            "N_elegible": n_elegible,
        }

        return {
            "date": ts_t,
            "eligible_tickers": eligible_tickers,
            "metrics": metrics,
            "asset_details": asset_details,
        }
