"""Governed command-line execution of the preregistered NAS100 V2 program."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import math
import platform
from pathlib import Path
from typing import Any

import pandas as pd

from NAS100_RESEARCH_V2.governance.integrity import canonical_sha256, sha256_file, utc_now
from NAS100_RESEARCH_V2.governance.registry import ExperimentRegistry
from NAS100_RESEARCH_V2.integration import MeanReversionFoldEvaluator, TrendFoldEvaluator
from NAS100_RESEARCH_V2.mean_reversion_v2 import MeanReversionV2Config
from NAS100_RESEARCH_V2.validation import AxiCostModel, CandidateSpec, run_nested_research

from .mr_falsification_runner import run_mr_falsification


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "NAS100_RESEARCH_V2"
PREREG = PACKAGE / "governance" / "config" / "research_preregistration.v1.json"
REGISTRY_PATH = PACKAGE / "governance" / "state" / "experiment_registry.jsonl"
CANDIDATE_DIR = Path(__file__).with_name("candidates")
BROKER_PROFILE = ROOT / "NAS100_INSTITUTIONAL" / "config" / "broker_profile_nas100_fs.json"
ACTOR = "codex_nas100_v2"


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return value


def _load_manifest(path: Path) -> tuple[dict, pd.DataFrame]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    body = dict(manifest)
    supplied = body.pop("manifest_sha256", None)
    if supplied != canonical_sha256(body):
        raise ValueError("canonical development manifest hash mismatch")
    if manifest.get("classification") != "DEVELOPMENT_CONSUMED" or not manifest.get("quality_passed"):
        raise ValueError("research input is not approved development-consumed data")
    if not str(manifest.get("dataset_id", "")).startswith("NAS100_"):
        raise ValueError("research input is outside the preregistered NAS100 universe")
    item = manifest["artifact_files"]["canonical_bars"]
    bars_path = path.parent / item["path"]
    if sha256_file(bars_path) != item["sha256"]:
        raise ValueError("canonical development bars hash mismatch")
    bars = pd.read_parquet(bars_path)
    if bars.index.tz is None or str(bars.index.tz).upper() != "UTC":
        raise ValueError("canonical bars are not explicit UTC")
    return manifest, bars


def _candidate_documents(family: str) -> list[tuple[Path, dict]]:
    documents = []
    for path in sorted(CANDIDATE_DIR.glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        if document["model_family"] == family:
            documents.append((path, document))
    documents.sort(key=lambda item: item[1]["candidate_index"])
    return documents


def _spec(document: dict) -> CandidateSpec:
    return CandidateSpec(
        candidate_id=document["candidate_id"],
        parameters=document["parameters"],
        complexity=int(document["complexity"]),
        neighbor_ids=tuple(document["neighbor_ids"]),
        is_baseline=bool(document["is_baseline"]),
    )


def _code_identity() -> str:
    inventory = [
        {"path": path.relative_to(ROOT).as_posix(), "sha256": sha256_file(path)}
        for path in sorted(PACKAGE.rglob("*.py"))
        if "__pycache__" not in path.parts
    ]
    return "sha256:" + canonical_sha256(inventory)


def _environment_hash() -> str:
    packages = {}
    for name in ("numpy", "pandas", "scipy", "pyarrow", "statsmodels"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = "NOT_INSTALLED"
    return canonical_sha256(
        {"python": platform.python_version(), "platform": platform.platform(), "packages": packages}
    )


def register_family(family: str, data_manifest: dict) -> list[tuple[Path, dict]]:
    registry = ExperimentRegistry(REGISTRY_PATH, PREREG)
    states = registry.states()
    documents = _candidate_documents(family)
    for path, document in documents:
        experiment_id = document["candidate_id"]
        digest = sha256_file(path)
        if experiment_id in states:
            state = states[experiment_id]
            if state.candidate_config_sha256 != digest:
                raise ValueError(f"registered candidate file changed: {experiment_id}")
            continue
        registry.register(
            actor=ACTOR,
            experiment_id=experiment_id,
            model_family=family,
            candidate_index=int(document["candidate_index"]),
            candidate_config_sha256=digest,
            canonical_data_manifest_sha256=data_manifest["manifest_sha256"],
            hypothesis=document["hypothesis"],
            primary_metric=document["primary_metric"],
        )
        states = registry.states()
    return documents


def _start(experiment_ids: list[str]) -> None:
    registry = ExperimentRegistry(REGISTRY_PATH, PREREG)
    code, environment = _code_identity(), _environment_hash()
    for experiment_id in experiment_ids:
        state = registry.states()[experiment_id]
        if state.state == "REGISTERED":
            registry.start(
                actor=ACTOR,
                experiment_id=experiment_id,
                code_identity=code,
                environment_sha256=environment,
                random_seed=20260710,
            )


def _artifact_manifest(directory: Path) -> str:
    files = [
        {"path": path.relative_to(directory).as_posix(), "sha256": sha256_file(path)}
        for path in sorted(directory.rglob("*"))
        if path.is_file() and path.name != "artifact_manifest.json"
    ]
    document = {"schema_version": 1, "created_utc": utc_now(), "files": files}
    document["manifest_sha256"] = canonical_sha256(document)
    (directory / "artifact_manifest.json").write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return document["manifest_sha256"]


def _record_nested(documents: list[tuple[Path, dict]], result: dict, artifact_hash: str) -> None:
    registry = ExperimentRegistry(REGISTRY_PATH, PREREG)
    selected = set(result["selected_candidates"])
    overall = bool(result["research_gate"]["approved"])
    for _, document in documents:
        experiment_id = document["candidate_id"]
        if registry.states()[experiment_id].state != "RUNNING":
            continue
        metrics = result["candidate_metrics"].get(experiment_id, {})
        pf = metrics.get("profit_factor")
        numeric_pf = float(pf) if isinstance(pf, (int, float)) and math.isfinite(float(pf)) else 0.0
        registry.record_result(
            actor=ACTOR,
            experiment_id=experiment_id,
            artifact_manifest_sha256=artifact_hash,
            decision="PASS" if overall and experiment_id in selected else "FAIL",
            primary_metric_name="outer_oos_profit_factor",
            primary_metric_value=numeric_pf,
            metrics=_safe({**metrics, "selected_in_outer_fold": experiment_id in selected, "family_gate": overall}),
        )


def run_trend(data_manifest_path: Path, output: Path) -> dict:
    manifest, bars = _load_manifest(data_manifest_path)
    documents = register_family("TREND_V2", manifest)
    _start([document["candidate_id"] for _, document in documents])
    result = run_nested_research(
        bars,
        [_spec(document) for _, document in documents],
        TrendFoldEvaluator(prefix_diagnostic=True),
        output,
        historical_trials=129,
        cost_model=AxiCostModel.from_profile(BROKER_PROFILE),
        purge_bars=500,
    )
    artifact_hash = _artifact_manifest(output)
    _record_nested(documents, result, artifact_hash)
    return result


def run_mr(data_manifest_path: Path, output: Path) -> dict:
    manifest, bars = _load_manifest(data_manifest_path)
    documents = register_family("MEAN_REVERSION_V2", manifest)
    default_id = "MR_01_BOTH_Z25"
    _start([default_id])
    falsification_dir = output / "falsification"
    falsification = run_mr_falsification(bars, falsification_dir, MeanReversionV2Config(), purge_bars=500)
    approved_sides = set(falsification["approved_sides_for_nested"])
    registry = ExperimentRegistry(REGISTRY_PATH, PREREG)
    if not approved_sides:
        artifact_hash = _artifact_manifest(output)
        registry.record_result(
            actor=ACTOR,
            experiment_id=default_id,
            artifact_manifest_sha256=artifact_hash,
            decision="FAIL",
            primary_metric_name="edge_existence_gate",
            primary_metric_value=0.0,
            metrics=_safe(falsification),
        )
        return {"status": "MR_RETIRED_LIVE_LOCKED", "live_locked": True, "falsification": falsification}

    eligible = []
    for item in documents:
        sides = set(item[1]["parameters"]["signal"]["allowed_sides"])
        if sides.issubset(approved_sides):
            eligible.append(item)
    if default_id not in {item[1]["candidate_id"] for item in eligible}:
        # The default both-sides hypothesis failed even if one side survives.
        partial_hash = _artifact_manifest(falsification_dir)
        registry.record_result(
            actor=ACTOR,
            experiment_id=default_id,
            artifact_manifest_sha256=partial_hash,
            decision="FAIL",
            primary_metric_name="edge_existence_gate",
            primary_metric_value=0.0,
            metrics=_safe(falsification),
        )
    _start([item[1]["candidate_id"] for item in eligible])
    nested_dir = output / "nested"
    result = run_nested_research(
        bars,
        [_spec(document) for _, document in eligible],
        MeanReversionFoldEvaluator(prefix_diagnostic=True),
        nested_dir,
        historical_trials=129,
        cost_model=AxiCostModel.from_profile(BROKER_PROFILE),
        purge_bars=500,
    )
    artifact_hash = _artifact_manifest(output)
    _record_nested(eligible, result, artifact_hash)
    return {"status": result["status"], "live_locked": True, "falsification": falsification, "nested": result}


def _main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("register", "run-trend", "run-mr", "verify"))
    parser.add_argument("--data-manifest", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.command == "verify":
        result = ExperimentRegistry(REGISTRY_PATH, PREREG).verify()
    else:
        if args.data_manifest is None:
            parser.error("--data-manifest is required")
        manifest, _ = _load_manifest(args.data_manifest)
        if args.command == "register":
            register_family("TREND_V2", manifest)
            register_family("MEAN_REVERSION_V2", manifest)
            result = ExperimentRegistry(REGISTRY_PATH, PREREG).verify()
        elif args.command == "run-trend":
            if args.output is None:
                parser.error("--output is required")
            result = run_trend(args.data_manifest, args.output)
        else:
            if args.output is None:
                parser.error("--output is required")
            result = run_mr(args.data_manifest, args.output)
    print(json.dumps(_safe(result), indent=2, sort_keys=True))


if __name__ == "__main__":
    _main()
