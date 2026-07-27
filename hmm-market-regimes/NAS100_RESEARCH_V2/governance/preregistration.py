"""Validation and canonical hashing of the frozen research preregistration."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .integrity import PolicyError, canonical_sha256, parse_utc


REQUIRED_TOP_LEVEL = {
    "schema_version",
    "immutable",
    "program_id",
    "created_utc",
    "research_scope",
    "data_policy",
    "candidate_budgets",
    "reproducibility",
    "governance",
}


@dataclass(frozen=True)
class Preregistration:
    path: Path
    document: Mapping[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: str  Path) -> "Preregistration":
        source = Path(path)
        try:
            document = json.loads(source.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise PolicyError(f"Preregistration does not exist: {source}") from exc
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise PolicyError(f"Preregistration is not valid UTF-8 JSON: {source}") from exc
        cls._validate(document)
        return cls(path=source, document=document, sha256=canonical_sha256(document))

    @staticmethod
    def _validate(document: Any) -> None:
        if not isinstance(document, dict):
            raise PolicyError("Preregistration must be a JSON object")
        if set(document) != REQUIRED_TOP_LEVEL:
            missing = sorted(REQUIRED_TOP_LEVEL - set(document))
            extra = sorted(set(document) - REQUIRED_TOP_LEVEL)
            raise PolicyError(f"Preregistration schema mismatch; missing={missing}, extra={extra}")
        if document["schema_version"] != 1:
            raise PolicyError("Only preregistration schema_version=1 is supported")
        if document["immutable"] is not True:
            raise PolicyError("Preregistration must set immutable=true")
        if not isinstance(document["program_id"], str) or not document["program_id"].strip():
            raise PolicyError("program_id must be non-empty")
        parse_utc(document["created_utc"], field="created_utc")

        scope = document["research_scope"]
        if not isinstance(scope, dict):
            raise PolicyError("research_scope must be an object")
        for field in ("symbol", "broker", "timeframe", "model_families"):
            if field not in scope:
                raise PolicyError(f"research_scope.{field} is required")
        if scope["symbol"] != "NAS100.fs":
            raise PolicyError("research_scope.symbol must be NAS100.fs")
        if "Axi" not in scope["broker"]:
            raise PolicyError("research_scope.broker must identify Axi")
        if scope["timeframe"] != "M15":
            raise PolicyError("research_scope.timeframe must be M15")
        families = scope["model_families"]
        if not isinstance(families, list) or sorted(families) != ["MEAN_REVERSION_V2", "TREND_V2"]:
            raise PolicyError("model_families must contain TREND_V2 and MEAN_REVERSION_V2 exactly")

        policy = document["data_policy"]
        if not isinstance(policy, dict):
            raise PolicyError("data_policy must be an object")
        required_policy = {
            "development_start_utc",
            "development_end_exclusive_utc",
            "holdout_start_utc",
            "holdout_boundary_rule",
            "consumed_sources",
            "holdout_access",
        }
        if set(policy) != required_policy:
            raise PolicyError("data_policy fields differ from the frozen schema")
        development_start = parse_utc(policy["development_start_utc"], field="development_start_utc")
        development_end = parse_utc(
            policy["development_end_exclusive_utc"], field="development_end_exclusive_utc"
        )
        holdout_start = parse_utc(policy["holdout_start_utc"], field="holdout_start_utc")
        if not development_start < development_end:
            raise PolicyError("development_start_utc must precede development_end_exclusive_utc")
        if holdout_start != development_end:
            raise PolicyError("holdout_start_utc must equal development_end_exclusive_utc")
        if policy["holdout_boundary_rule"] != "[start,end); timestamps >= holdout_start are holdout":
            raise PolicyError("holdout_boundary_rule changed from the frozen value")
        if not isinstance(policy["consumed_sources"], list) or not policy["consumed_sources"]:
            raise PolicyError("consumed_sources must be a non-empty list")
        for index, source in enumerate(policy["consumed_sources"]):
            if not isinstance(source, dict) or set(source) != {
                "dataset_id",
                "path",
                "classification",
                "reason",
            }:
                raise PolicyError(f"consumed_sources[{index}] has an invalid schema")
            if source["classification"] != "DEVELOPMENT_CONSUMED":
                raise PolicyError(f"consumed_sources[{index}] must be DEVELOPMENT_CONSUMED")
        access = policy["holdout_access"]
        if not isinstance(access, dict) or set(access) != {
            "development_purposes",
            "holdout_purposes",
            "authorization_required",
            "max_final_evaluations_per_experiment_dataset",
            "mixed_window_policy",
        }:
            raise PolicyError("data_policy.holdout_access has an invalid schema")
        if access["authorization_required"] is not True:
            raise PolicyError("holdout access must require authorization")
        if access["max_final_evaluations_per_experiment_dataset"] != 1:
            raise PolicyError("Exactly one final holdout evaluation is allowed")
        if access["mixed_window_policy"] != "DENY":
            raise PolicyError("Mixed development/holdout windows must be denied")

        budgets = document["candidate_budgets"]
        if not isinstance(budgets, dict) or set(budgets) != {"TREND_V2", "MEAN_REVERSION_V2"}:
            raise PolicyError("candidate_budgets must define both model families exactly")
        for family, expected in {"TREND_V2": 12, "MEAN_REVERSION_V2": 9}.items():
            value = budgets[family]
            if not isinstance(value, dict) or set(value) != {"max_candidates", "counting_rule"}:
                raise PolicyError(f"candidate_budgets.{family} has an invalid schema")
            if value["max_candidates"] != expected:
                raise PolicyError(f"candidate_budgets.{family}.max_candidates must be {expected}")
            if value["counting_rule"] != "Every distinct specification inspected against outcomes counts":
                raise PolicyError(f"candidate_budgets.{family}.counting_rule changed")

        reproducibility = document["reproducibility"]
        if not isinstance(reproducibility, dict) or set(reproducibility) != {
            "random_seeds",
            "deterministic_sorting",
            "hash_algorithm",
            "required_run_bindings",
        }:
            raise PolicyError("reproducibility has an invalid schema")
        seeds = reproducibility["random_seeds"]
        if not isinstance(seeds, list) or not seeds or any(type(seed) is not int for seed in seeds):
            raise PolicyError("random_seeds must be a non-empty list of integers")
        if len(set(seeds)) != len(seeds):
            raise PolicyError("random_seeds must be unique")
        if reproducibility["deterministic_sorting"] is not True:
            raise PolicyError("deterministic_sorting must be true")
        if reproducibility["hash_algorithm"] != "SHA-256":
            raise PolicyError("hash_algorithm must be SHA-256")
        required_bindings = reproducibility["required_run_bindings"]
        expected_bindings = [
            "preregistration_sha256",
            "candidate_config_sha256",
            "canonical_data_manifest_sha256",
            "code_identity",
            "environment_sha256",
        ]
        if required_bindings != expected_bindings:
            raise PolicyError("required_run_bindings differ from the frozen schema")

        governance = document["governance"]
        if not isinstance(governance, dict) or set(governance) != {
            "live_trading",
            "registry_mode",
            "integrity_failure_policy",
            "parameter_change_policy",
        }:
            raise PolicyError("governance has an invalid schema")
        expected = {
            "live_trading": "LIVE_LOCKED",
            "registry_mode": "APPEND_ONLY_HASH_CHAIN",
            "integrity_failure_policy": "FAIL_CLOSED",
            "parameter_change_policy": "NEW_CANDIDATE_AND_NEW_REGISTRY_EVENT",
        }
        if governance != expected:
            raise PolicyError("governance values differ from the frozen policy")

    @property
    def program_id(self) -> str:
        return str(self.document["program_id"])

    @property
    def development_start_utc(self):
        return parse_utc(self.document["data_policy"]["development_start_utc"])

    @property
    def development_end_exclusive_utc(self):
        return parse_utc(self.document["data_policy"]["development_end_exclusive_utc"])

    @property
    def holdout_start_utc(self):
        return parse_utc(self.document["data_policy"]["holdout_start_utc"])

    def candidate_budget(self, family: str) -> int:
        try:
            return int(self.document["candidate_budgets"][family]["max_candidates"])
        except KeyError as exc:
            raise PolicyError(f"Unknown model family: {family}") from exc


def _main() -> None:
    parser = argparse.ArgumentParser(description="Validate and hash a research preregistration")
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    prereg = Preregistration.load(args.path)
    print(json.dumps({"ok": True, "program_id": prereg.program_id, "sha256": prereg.sha256}, indent=2))


if __name__ == "__main__":
    _main()
