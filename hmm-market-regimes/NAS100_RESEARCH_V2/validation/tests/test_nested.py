from __future__ import annotations

import numpy as np
import pandas as pd

from NAS100_RESEARCH_V2.validation import CandidateSpec, FoldRun, run_nested_research


class DummyEvaluator:
    def _run(self, bars, candidate, multiplier=1.0):
        step = 15 if candidate.candidate_id == "BASE" else 10
        rows = []
        for i in range(1, len(bars), step):
            pnl = (1.0 if candidate.candidate_id == "BASE" else 2.0) * multiplier
            if (i // step) % 5 == 0:
                pnl *= -0.5
            rows.append(
                {
                    "entry_time": bars.index[i - 1],
                    "exit_time": bars.index[i],
                    "net_pnl": pnl,
                    "return_pct": pnl / 100.0,
                    "pnl": pnl,
                }
            )
        return FoldRun(pd.DataFrame(rows), {})

    def training_run(self, bars, candidate, costs):
        return self._run(bars, candidate)

    def __call__(self, train, test, candidate, costs, fold):
        drag = 1.0 if costs.name == "base" else 0.8 if costs.name == "adverse" else 0.6
        return self._run(test, candidate, drag)


def test_nested_runner_uses_28_inner_splits_and_keeps_live_locked(tmp_path):
    index = pd.date_range("2019-01-01", "2026-07-01", freq="B", tz="UTC")
    close = 10_000.0 + np.arange(len(index), dtype=float)
    bars = pd.DataFrame(
        {"open": close, "high": close + 1, "low": close - 1, "close": close},
        index=index,
    )
    result = run_nested_research(
        bars,
        [
            CandidateSpec("BASE", {"strategy": "momentum_long_only"}, is_baseline=True),
            CandidateSpec("EDGE", {"strategy": "trend_v2"}, neighbor_ids=("BASE",)),
        ],
        DummyEvaluator(),
        tmp_path,
        historical_trials=129,
        purge_bars=5,
        bootstrap_samples=100,
    )
    assert result["inner_cpcv_splits_per_fold"] == 28
    assert result["live_locked"] is True
    assert (tmp_path / "nested_decision.json").exists()
