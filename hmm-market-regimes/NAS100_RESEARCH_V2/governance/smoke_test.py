"""Read-only smoke verification for the initialized governance/data package."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from NAS100_RESEARCH_V2.data_tools.axi_qa import verify_canonical_manifest
from NAS100_RESEARCH_V2.governance.bootstrap import DEFAULT_PREREGISTRATION, DEFAULT_STATE, verify
from NAS100_RESEARCH_V2.governance.integrity import IntegrityError
from NAS100_RESEARCH_V2.governance.preregistration import Preregistration


ROOT = Path(__file__).resolve().parents[1]
DATA_MANIFEST = ROOT / "data_tools" / "artifacts" / "canonical_data_manifest.json"
BARS = ROOT / "data_tools" / "artifacts" / "NAS100_fs_M15_DEVELOPMENT_CANONICAL.parquet"


def main() -> None:
    prereg = Preregistration.load(DEFAULT_PREREGISTRATION)
    governance = verify(DEFAULT_STATE)
    data = verify_canonical_manifest(DATA_MANIFEST)
    if not data["quality_passed"]:
        raise IntegrityError("Canonical dataset did not pass QA")
    manifest = json.loads(DATA_MANIFEST.read_text(encoding="utf-8"))
    bars = pd.read_parquet(BARS)
    timestamps = pd.to_datetime(bars.index, utc=True)
    if len(bars) != manifest["canonical_bar_rows"]:
        raise IntegrityError("Canonical bar row count differs from its manifest")
    if timestamps.max().to_pydatetime() >= prereg.development_end_exclusive_utc:
        raise IntegrityError("Canonical development bars reach into holdout")
    if governance["access_manifest"]["holdout_allow_count"] != 0:
        raise IntegrityError("Holdout has already been accessed")
    result = {
        "ok": True,
        "program_id": prereg.program_id,
        "preregistration_sha256": prereg.sha256,
        "canonical_data_manifest_sha256": data["manifest_sha256"],
        "canonical_bar_rows": len(bars),
        "registry_records": governance["experiment_registry"]["records"],
        "access_records": governance["access_manifest"]["records"],
        "holdout_allow_count": 0,
        "status": "LIVE_LOCKED",
    }
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
