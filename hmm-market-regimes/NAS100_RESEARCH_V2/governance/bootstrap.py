"""One-time creation and later verification of governance state."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .access_manifest import (
    HoldoutAccessController,
    create_cutoff_manifest,
    verify_cutoff_manifest,
)
from .integrity import GovernanceError
from .preregistration import Preregistration
from .registry import ExperimentRegistry


HERE = Path(__file__).resolve().parent
DEFAULT_PREREGISTRATION = HERE / "config" / "research_preregistration.v1.json"
DEFAULT_STATE = HERE / "state"


def bootstrap(*, actor: str, state_dir: Path = DEFAULT_STATE) -> dict:
    prereg = Preregistration.load(DEFAULT_PREREGISTRATION)
    state_dir.mkdir(parents=True, exist_ok=True)
    registry = ExperimentRegistry(
        state_dir / "experiment_registry.jsonl", DEFAULT_PREREGISTRATION
    )
    access = HoldoutAccessController(
        state_dir / "holdout_access_manifest.jsonl", DEFAULT_PREREGISTRATION
    )
    registry.initialize(actor=actor)
    access.initialize(actor=actor)
    cutoff = create_cutoff_manifest(
        path=state_dir / "data_cutoff_manifest.json",
        preregistration_path=DEFAULT_PREREGISTRATION,
        actor=actor,
    )
    return {
        "ok": True,
        "program_id": prereg.program_id,
        "preregistration_sha256": prereg.sha256,
        "experiment_registry": registry.verify(),
        "access_manifest": access.verify(),
        "cutoff_manifest_sha256": cutoff["manifest_sha256"],
    }


def verify(state_dir: Path = DEFAULT_STATE) -> dict:
    prereg = Preregistration.load(DEFAULT_PREREGISTRATION)
    registry = ExperimentRegistry(
        state_dir / "experiment_registry.jsonl", DEFAULT_PREREGISTRATION
    )
    access = HoldoutAccessController(
        state_dir / "holdout_access_manifest.jsonl", DEFAULT_PREREGISTRATION
    )
    return {
        "ok": True,
        "program_id": prereg.program_id,
        "preregistration_sha256": prereg.sha256,
        "experiment_registry": registry.verify(),
        "access_manifest": access.verify(),
        "cutoff_manifest": verify_cutoff_manifest(
            state_dir / "data_cutoff_manifest.json", DEFAULT_PREREGISTRATION
        ),
    }


def _main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap or verify NAS100 V2 governance")
    parser.add_argument("command", choices=("init", "verify"))
    parser.add_argument("--actor")
    parser.add_argument("--state-dir", type=Path, default=DEFAULT_STATE)
    args = parser.parse_args()
    if args.command == "init":
        if not args.actor:
            parser.error("--actor is required for init")
        result = bootstrap(actor=args.actor, state_dir=args.state_dir)
    else:
        result = verify(state_dir=args.state_dir)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        _main()
    except GovernanceError as exc:
        raise SystemExit(f"FAIL_CLOSED: {exc}") from exc

