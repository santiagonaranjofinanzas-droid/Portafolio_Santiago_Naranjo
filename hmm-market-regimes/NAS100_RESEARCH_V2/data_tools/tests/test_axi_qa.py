from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from NAS100_RESEARCH_V2.data_tools.axi_qa import audit_axi_dataset, verify_canonical_manifest
from NAS100_RESEARCH_V2.governance.integrity import IntegrityError


class AxiQaTests(unittest.TestCase):
    def _fixture(self, root: Path, *, crossed: bool = False) -> Path:
        ticks = root / "ticks" / "year=2026" / "month=1"
        ticks.mkdir(parents=True)
        timestamps = pd.date_range("2026-01-05T00:00:00Z", periods=30, freq="1min")
        bid = 100.0 + np.arange(len(timestamps)) * 0.25
        ask = bid + 1.0
        if crossed:
            ask[10] = bid[10] - 0.25
        frame = pd.DataFrame(
            {
                "timestamp": timestamps.tz_convert(None),
                "bid": bid,
                "ask": ask,
                "flags": np.full(len(timestamps), 134, dtype=np.uint32),
            }
        )
        frame.to_parquet(ticks / "ticks_NAS100_fs_20260105.parquet", index=False)
        indexed = frame.set_index(pd.DatetimeIndex(timestamps))
        reference = indexed["bid"].resample("5min").ohlc()
        reference.to_parquet(root / "reference.parquet")
        config = {
            "schema_version": 1,
            "dataset_id": "AXI_FIXTURE",
            "symbol": "NAS100.fs",
            "broker": "Axi-Test",
            "source_timezone": "UTC",
            "source_root": "ticks",
            "source_glob": "year=*/month=*/*.parquet",
            "reference_bar_path": "reference.parquet",
            "audit_start_utc": "2026-01-05T00:00:00Z",
            "audit_end_exclusive_utc": "2026-01-05T00:30:00Z",
            "development_cutoff_exclusive_utc": "2026-01-06T00:00:00Z",
            "bar_frequency": "5min",
            "tick_size": 0.25,
            "expected_file_count": 1,
            "session_calendar": {
                "timezone": "UTC",
                "weekdays": [0, 1, 2, 3, 4],
                "regular_start": "00:00",
                "regular_end": "00:30",
                "exceptions": {},
            },
            "quality_gates": {
                "minimum_complete_bar_coverage": 1.0,
                "maximum_active_tick_gap_seconds": 61.0,
                "maximum_active_gap_count": 0,
                "maximum_stale_quote_seconds": 61.0,
                "maximum_stale_run_count": 0,
                "maximum_spread_price": 2.0,
                "maximum_crossed_rows": 0,
                "maximum_locked_rows": 0,
                "maximum_duplicate_timestamps": 0,
                "maximum_out_of_order_rows": 0,
                "maximum_invalid_price_rows": 0,
                "maximum_off_grid_rows": 0,
            },
            "canonical_bar_filename": "canonical.parquet",
        }
        path = root / "config.json"
        path.write_text(json.dumps(config), encoding="utf-8")
        return path

    def test_happy_path_and_artifact_verification(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = self._fixture(root)
            output = root / "output"
            result = audit_axi_dataset(
                config_path=config,
                workspace_root=root,
                output_dir=output,
            )
            self.assertTrue(result["ok"])
            self.assertEqual(result["canonical_bar_rows"], 6)
            verification = verify_canonical_manifest(output / "canonical_data_manifest.json")
            self.assertTrue(verification["ok"])
            bars = pd.read_parquet(output / "canonical.parquet")
            self.assertEqual(len(bars), 6)
            self.assertIn("bid_open", bars.columns)
            self.assertIn("ask_close", bars.columns)

            report_path = output / "axi_tick_bar_qa_report.json"
            report_path.write_text(report_path.read_text(encoding="utf-8") + " ", encoding="utf-8")
            with self.assertRaises(IntegrityError):
                verify_canonical_manifest(output / "canonical_data_manifest.json")

    def test_crossed_market_fails_quality_gate_without_hiding_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = self._fixture(root, crossed=True)
            result = audit_axi_dataset(
                config_path=config,
                workspace_root=root,
                output_dir=root / "output",
            )
            self.assertFalse(result["ok"])
            self.assertFalse(result["gate_results"]["crossed_rows"])
            report = json.loads(
                (root / "output" / "axi_tick_bar_qa_report.json").read_text(encoding="utf-8")
            )
            self.assertEqual(report["tick_quality"]["crossed_rows"], 1)

    def test_existing_artifacts_are_never_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = self._fixture(root)
            output = root / "output"
            audit_axi_dataset(config_path=config, workspace_root=root, output_dir=output)
            with self.assertRaises(IntegrityError):
                audit_axi_dataset(config_path=config, workspace_root=root, output_dir=output)


if __name__ == "__main__":
    unittest.main()
