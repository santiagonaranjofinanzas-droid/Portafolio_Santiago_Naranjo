"""Append-only experiment registry with enforced candidate budgets and states."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .integrity import (
    GovernanceError,
    HashChainedJsonl,
    IntegrityError,
    PolicyError,
    require_sha256,
)
from .preregistration import Preregistration


EXPERIMENT_ID_RE = re.compile(r"^[A-Z0-9][A-Z0-9_.-]{2,63}$")
ALLOWED_FAMILIES = {"TREND_V2", "MEAN_REVERSION_V2"}
ALLOWED_EVENTS = {"REGISTER", "START", "RESULT", "ABORT"}
TERMINAL_STATES = {"COMPLETED", "ABORTED"}


@dataclass(frozen=True)
class ExperimentState:
    experiment_id: str
    model_family: str
    candidate_index: int
    candidate_config_sha256: str
    state: str
    registered_sequence: int
    terminal_sequence: int  None = None


class ExperimentRegistry:
    """Stateful interface over an integrity-checked JSONL ledger."""

    ledger_type = "NAS100_RESEARCH_V2_EXPERIMENT_REGISTRY"

    def __init__(self, path: str  Path, preregistration_path: str  Path) -> None:
        self.preregistration = Preregistration.load(preregistration_path)
        self.ledger = HashChainedJsonl(path, self.ledger_type)

    def initialize(self, *, actor: str) -> dict[str, Any]:
        return self.ledger.initialize(
            actor=actor,
            metadata={
                "program_id": self.preregistration.program_id,
                "preregistration_sha256": self.preregistration.sha256,
                "mode": "APPEND_ONLY_HASH_CHAIN",
                "integrity_failure_policy": "FAIL_CLOSED",
            },
        )

    def _verified_events(self) -> list[dict[str, Any]]:
        events = self.ledger.read_verified()
        genesis = events[0]["payload"]
        if genesis.get("program_id") != self.preregistration.program_id:
            raise IntegrityError("Registry program_id does not match the preregistration")
        if genesis.get("preregistration_sha256") != self.preregistration.sha256:
            raise IntegrityError("Registry is bound to a different preregistration hash")
        self._derive_states(events)  # Validates semantic history, not only hashes.
        return events

    @staticmethod
    def _validate_experiment_id(experiment_id: str) -> None:
        if not isinstance(experiment_id, str) or not EXPERIMENT_ID_RE.fullmatch(experiment_id):
            raise PolicyError(
                "experiment_id must be 3-64 uppercase alphanumeric characters plus ._-"
            )

    def _derive_states(
        self, events: Sequence[Mapping[str, Any]]
    ) -> dict[str, ExperimentState]:
        states: dict[str, ExperimentState] = {}
        used_candidate_indices: dict[str, set[int]] = {family: set() for family in ALLOWED_FAMILIES}
        for event in events[1:]:
            event_type = event["event_type"]
            if event_type not in ALLOWED_EVENTS:
                raise IntegrityError(f"Unknown registry event type at sequence {event['sequence']}")
            payload = event["payload"]
            experiment_id = payload.get("experiment_id")
            try:
                self._validate_experiment_id(experiment_id)
            except PolicyError as exc:
                raise IntegrityError(
                    f"Invalid experiment_id at sequence {event['sequence']}: {exc}"
                ) from exc
            current = states.get(experiment_id)
            if event_type == "REGISTER":
                required = {
                    "experiment_id",
                    "model_family",
                    "candidate_index",
                    "candidate_config_sha256",
                    "canonical_data_manifest_sha256",
                    "hypothesis",
                    "primary_metric",
                }
                if set(payload) != required:
                    raise IntegrityError(f"REGISTER schema error at sequence {event['sequence']}")
                if current is not None:
                    raise IntegrityError(f"Duplicate REGISTER for {experiment_id}")
                family = payload["model_family"]
                if family not in ALLOWED_FAMILIES:
                    raise IntegrityError(f"Invalid model family for {experiment_id}")
                index = payload["candidate_index"]
                if type(index) is not int or not 1 <= index <= self.preregistration.candidate_budget(family):
                    raise IntegrityError(f"Candidate index outside preregistered budget for {experiment_id}")
                if index in used_candidate_indices[family]:
                    raise IntegrityError(f"Duplicate candidate index {family}/{index}")
                used_candidate_indices[family].add(index)
                for field in ("candidate_config_sha256", "canonical_data_manifest_sha256"):
                    try:
                        require_sha256(payload[field], field=field)
                    except PolicyError as exc:
                        raise IntegrityError(str(exc)) from exc
                if not isinstance(payload["hypothesis"], str) or not payload["hypothesis"].strip():
                    raise IntegrityError(f"Empty hypothesis for {experiment_id}")
                if not isinstance(payload["primary_metric"], str) or not payload["primary_metric"].strip():
                    raise IntegrityError(f"Empty primary_metric for {experiment_id}")
                states[experiment_id] = ExperimentState(
                    experiment_id=experiment_id,
                    model_family=family,
                    candidate_index=index,
                    candidate_config_sha256=payload["candidate_config_sha256"],
                    state="REGISTERED",
                    registered_sequence=event["sequence"],
                )
            elif event_type == "START":
                required = {
                    "experiment_id",
                    "code_identity",
                    "environment_sha256",
                    "random_seed",
                }
                if set(payload) != required:
                    raise IntegrityError(f"START schema error at sequence {event['sequence']}")
                if current is None or current.state != "REGISTERED":
                    raise IntegrityError(f"Invalid START transition for {experiment_id}")
                try:
                    require_sha256(payload["environment_sha256"], field="environment_sha256")
                except PolicyError as exc:
                    raise IntegrityError(str(exc)) from exc
                if not isinstance(payload["code_identity"], str) or not payload["code_identity"].strip():
                    raise IntegrityError(f"Invalid code_identity for {experiment_id}")
                allowed_seeds = self.preregistration.document["reproducibility"]["random_seeds"]
                if payload["random_seed"] not in allowed_seeds:
                    raise IntegrityError(f"Unregistered random_seed for {experiment_id}")
                states[experiment_id] = ExperimentState(**{**current.__dict__, "state": "RUNNING"})
            elif event_type == "RESULT":
                required = {
                    "experiment_id",
                    "artifact_manifest_sha256",
                    "decision",
                    "primary_metric_name",
                    "primary_metric_value",
                    "metrics",
                }
                if set(payload) != required:
                    raise IntegrityError(f"RESULT schema error at sequence {event['sequence']}")
                if current is None or current.state != "RUNNING":
                    raise IntegrityError(f"Invalid RESULT transition for {experiment_id}")
                try:
                    require_sha256(payload["artifact_manifest_sha256"], field="artifact_manifest_sha256")
                except PolicyError as exc:
                    raise IntegrityError(str(exc)) from exc
                if payload["decision"] not in {"PASS", "FAIL", "ERROR"}:
                    raise IntegrityError(f"Invalid result decision for {experiment_id}")
                if not isinstance(payload["metrics"], dict):
                    raise IntegrityError(f"metrics must be an object for {experiment_id}")
                if not isinstance(payload["primary_metric_name"], str):
                    raise IntegrityError(f"primary_metric_name is invalid for {experiment_id}")
                value = payload["primary_metric_value"]
                if not isinstance(value, (int, float)) or isinstance(value, bool):
                    raise IntegrityError(f"primary_metric_value is invalid for {experiment_id}")
                states[experiment_id] = ExperimentState(
                    **{**current.__dict__, "state": "COMPLETED", "terminal_sequence": event["sequence"]}
                )
            else:  # ABORT
                if set(payload) != {"experiment_id", "reason"}:
                    raise IntegrityError(f"ABORT schema error at sequence {event['sequence']}")
                if current is None or current.state != "RUNNING":
                    raise IntegrityError(f"Invalid ABORT transition for {experiment_id}")
                if not isinstance(payload["reason"], str) or not payload["reason"].strip():
                    raise IntegrityError(f"ABORT reason is empty for {experiment_id}")
                states[experiment_id] = ExperimentState(
                    **{**current.__dict__, "state": "ABORTED", "terminal_sequence": event["sequence"]}
                )
        return states

    def verify(self) -> dict[str, Any]:
        events = self._verified_events()
        states = self._derive_states(events)
        summary = self.ledger.verify()
        summary["program_id"] = self.preregistration.program_id
        summary["preregistration_sha256"] = self.preregistration.sha256
        summary["experiments"] = len(states)
        summary["state_counts"] = {
            state: sum(item.state == state for item in states.values())
            for state in ("REGISTERED", "RUNNING", "COMPLETED", "ABORTED")
        }
        summary["budget_usage"] = {
            family: {
                "used": sum(item.model_family == family for item in states.values()),
                "maximum": self.preregistration.candidate_budget(family),
            }
            for family in sorted(ALLOWED_FAMILIES)
        }
        return summary

    def states(self) -> dict[str, ExperimentState]:
        return self._derive_states(self._verified_events())

    def register(
        self,
        *,
        actor: str,
        experiment_id: str,
        model_family: str,
        candidate_index: int,
        candidate_config_sha256: str,
        canonical_data_manifest_sha256: str,
        hypothesis: str,
        primary_metric: str,
    ) -> dict[str, Any]:
        self._validate_experiment_id(experiment_id)
        if model_family not in ALLOWED_FAMILIES:
            raise PolicyError(f"Unknown model family: {model_family}")
        if type(candidate_index) is not int:
            raise PolicyError("candidate_index must be an integer")
        require_sha256(candidate_config_sha256, field="candidate_config_sha256")
        require_sha256(canonical_data_manifest_sha256, field="canonical_data_manifest_sha256")
        if not hypothesis.strip() or not primary_metric.strip():
            raise PolicyError("hypothesis and primary_metric cannot be empty")
        payload = {
            "experiment_id": experiment_id,
            "model_family": model_family,
            "candidate_index": candidate_index,
            "candidate_config_sha256": candidate_config_sha256,
            "canonical_data_manifest_sha256": canonical_data_manifest_sha256,
            "hypothesis": hypothesis,
            "primary_metric": primary_metric,
        }

        def validate(events: Sequence[Mapping[str, Any]]) -> None:
            self._assert_genesis(events)
            states = self._derive_states(events)
            if experiment_id in states:
                raise PolicyError(f"experiment_id is already registered: {experiment_id}")
            maximum = self.preregistration.candidate_budget(model_family)
            if not 1 <= candidate_index <= maximum:
                raise PolicyError(f"candidate_index must be between 1 and {maximum}")
            if any(
                item.model_family == model_family and item.candidate_index == candidate_index
                for item in states.values()
            ):
                raise PolicyError(f"candidate index already used: {model_family}/{candidate_index}")
            if sum(item.model_family == model_family for item in states.values()) >= maximum:
                raise PolicyError(f"Candidate budget exhausted for {model_family}")

        return self.ledger.append(
            event_type="REGISTER",
            actor=actor,
            payload=payload,
            correlation_id=experiment_id,
            pre_append_validator=validate,
        )

    def _assert_genesis(self, events: Sequence[Mapping[str, Any]]) -> None:
        if not events:
            raise IntegrityError("Registry has no GENESIS record")
        genesis = events[0]["payload"]
        if genesis.get("program_id") != self.preregistration.program_id:
            raise IntegrityError("Registry program mismatch")
        if genesis.get("preregistration_sha256") != self.preregistration.sha256:
            raise IntegrityError("Registry preregistration hash mismatch")

    def _append_transition(
        self,
        *,
        event_type: str,
        actor: str,
        experiment_id: str,
        payload: Mapping[str, Any],
        expected_state: str,
    ) -> dict[str, Any]:
        self._validate_experiment_id(experiment_id)

        def validate(events: Sequence[Mapping[str, Any]]) -> None:
            self._assert_genesis(events)
            state = self._derive_states(events).get(experiment_id)
            if state is None:
                raise PolicyError(f"Unknown experiment: {experiment_id}")
            if state.state != expected_state:
                raise PolicyError(
                    f"{event_type} requires {expected_state}; {experiment_id} is {state.state}"
                )

        return self.ledger.append(
            event_type=event_type,
            actor=actor,
            payload=payload,
            correlation_id=experiment_id,
            pre_append_validator=validate,
        )

    def start(
        self,
        *,
        actor: str,
        experiment_id: str,
        code_identity: str,
        environment_sha256: str,
        random_seed: int,
    ) -> dict[str, Any]:
        require_sha256(environment_sha256, field="environment_sha256")
        if not code_identity.strip():
            raise PolicyError("code_identity cannot be empty")
        allowed = self.preregistration.document["reproducibility"]["random_seeds"]
        if random_seed not in allowed:
            raise PolicyError(f"random_seed must be one of {allowed}")
        return self._append_transition(
            event_type="START",
            actor=actor,
            experiment_id=experiment_id,
            expected_state="REGISTERED",
            payload={
                "experiment_id": experiment_id,
                "code_identity": code_identity,
                "environment_sha256": environment_sha256,
                "random_seed": random_seed,
            },
        )

    def record_result(
        self,
        *,
        actor: str,
        experiment_id: str,
        artifact_manifest_sha256: str,
        decision: str,
        primary_metric_name: str,
        primary_metric_value: float,
        metrics: Mapping[str, Any],
    ) -> dict[str, Any]:
        require_sha256(artifact_manifest_sha256, field="artifact_manifest_sha256")
        if decision not in {"PASS", "FAIL", "ERROR"}:
            raise PolicyError("decision must be PASS, FAIL or ERROR")
        if not primary_metric_name.strip():
            raise PolicyError("primary_metric_name cannot be empty")
        if not isinstance(primary_metric_value, (int, float)) or isinstance(primary_metric_value, bool):
            raise PolicyError("primary_metric_value must be numeric")
        return self._append_transition(
            event_type="RESULT",
            actor=actor,
            experiment_id=experiment_id,
            expected_state="RUNNING",
            payload={
                "experiment_id": experiment_id,
                "artifact_manifest_sha256": artifact_manifest_sha256,
                "decision": decision,
                "primary_metric_name": primary_metric_name,
                "primary_metric_value": primary_metric_value,
                "metrics": dict(metrics),
            },
        )

    def abort(self, *, actor: str, experiment_id: str, reason: str) -> dict[str, Any]:
        if not reason.strip():
            raise PolicyError("reason cannot be empty")
        return self._append_transition(
            event_type="ABORT",
            actor=actor,
            experiment_id=experiment_id,
            expected_state="RUNNING",
            payload={"experiment_id": experiment_id, "reason": reason},
        )


def _main() -> None:
    parser = argparse.ArgumentParser(description="NAS100 V2 append-only experiment registry")
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--preregistration", required=True, type=Path)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "verify", "seal"):
        command = sub.add_parser(name)
        if name != "verify":
            command.add_argument("--actor", required=True)
    register = sub.add_parser("register")
    register.add_argument("--actor", required=True)
    register.add_argument("--experiment-id", required=True)
    register.add_argument("--model-family", choices=sorted(ALLOWED_FAMILIES), required=True)
    register.add_argument("--candidate-index", type=int, required=True)
    register.add_argument("--candidate-config-sha256", required=True)
    register.add_argument("--data-manifest-sha256", required=True)
    register.add_argument("--hypothesis", required=True)
    register.add_argument("--primary-metric", required=True)
    args = parser.parse_args()
    registry = ExperimentRegistry(args.registry, args.preregistration)
    if args.command == "init":
        output = registry.initialize(actor=args.actor)
    elif args.command == "verify":
        output = registry.verify()
    elif args.command == "seal":
        output = registry.ledger.seal(actor=args.actor)
    else:
        output = registry.register(
            actor=args.actor,
            experiment_id=args.experiment_id,
            model_family=args.model_family,
            candidate_index=args.candidate_index,
            candidate_config_sha256=args.candidate_config_sha256,
            canonical_data_manifest_sha256=args.data_manifest_sha256,
            hypothesis=args.hypothesis,
            primary_metric=args.primary_metric,
        )
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        _main()
    except GovernanceError as exc:
        raise SystemExit(f"FAIL_CLOSED: {exc}") from exc

