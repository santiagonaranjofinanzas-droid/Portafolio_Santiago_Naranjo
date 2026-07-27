"""Cutoff enforcement and append-only data/holdout access decisions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .integrity import (
    GovernanceError,
    HashChainedJsonl,
    IntegrityError,
    PolicyError,
    canonical_json_bytes,
    canonical_sha256,
    parse_utc,
    utc_now,
)
from .preregistration import Preregistration


class AccessDenied(PolicyError):
    """The denial has already been recorded in the access ledger."""


class HoldoutAccessController:
    ledger_type = "NAS100_RESEARCH_V2_DATA_ACCESS_MANIFEST"

    def __init__(self, path: str  Path, preregistration_path: str  Path) -> None:
        self.preregistration = Preregistration.load(preregistration_path)
        self.ledger = HashChainedJsonl(path, self.ledger_type)

    def initialize(self, *, actor: str) -> dict[str, Any]:
        policy = self.preregistration.document["data_policy"]
        return self.ledger.initialize(
            actor=actor,
            metadata={
                "program_id": self.preregistration.program_id,
                "preregistration_sha256": self.preregistration.sha256,
                "development_end_exclusive_utc": policy["development_end_exclusive_utc"],
                "holdout_start_utc": policy["holdout_start_utc"],
                "mixed_window_policy": "DENY",
            },
        )

    def _assert_binding(self, events: Sequence[Mapping[str, Any]]) -> None:
        if not events:
            raise IntegrityError("Data access manifest has no GENESIS record")
        genesis = events[0]["payload"]
        expected = {
            "program_id": self.preregistration.program_id,
            "preregistration_sha256": self.preregistration.sha256,
            "development_end_exclusive_utc": self.preregistration.document["data_policy"][
                "development_end_exclusive_utc"
            ],
            "holdout_start_utc": self.preregistration.document["data_policy"]["holdout_start_utc"],
            "mixed_window_policy": "DENY",
        }
        if genesis != expected:
            raise IntegrityError("Access manifest GENESIS is not bound to the active data policy")
        for event in events[1:]:
            if event["event_type"] != "ACCESS_DECISION":
                raise IntegrityError(f"Unknown access event at sequence {event['sequence']}")
            required = {
                "request_id",
                "dataset_id",
                "experiment_id",
                "purpose",
                "requested_start_utc",
                "requested_end_exclusive_utc",
                "window_class",
                "decision",
                "reason",
                "authorization_id",
                "source_reference",
            }
            if set(event["payload"]) != required:
                raise IntegrityError(f"Access event schema error at sequence {event['sequence']}")
            if event["payload"]["decision"] not in {"ALLOW", "DENY"}:
                raise IntegrityError(f"Invalid access decision at sequence {event['sequence']}")

    def verify(self) -> dict[str, Any]:
        events = self.ledger.read_verified()
        self._assert_binding(events)
        summary = self.ledger.verify()
        decisions = [event["payload"] for event in events[1:]]
        summary.update(
            {
                "program_id": self.preregistration.program_id,
                "preregistration_sha256": self.preregistration.sha256,
                "allow_count": sum(item["decision"] == "ALLOW" for item in decisions),
                "deny_count": sum(item["decision"] == "DENY" for item in decisions),
                "holdout_allow_count": sum(
                    item["decision"] == "ALLOW" and item["window_class"] == "HOLDOUT"
                    for item in decisions
                ),
            }
        )
        return summary

    def request_access(
        self,
        *,
        actor: str,
        dataset_id: str,
        experiment_id: str,
        purpose: str,
        requested_start_utc: str,
        requested_end_exclusive_utc: str,
        source_reference: str,
        authorization_id: str  None = None,
        request_id: str  None = None,
    ) -> dict[str, Any]:
        if not all(
            isinstance(value, str) and value.strip()
            for value in (actor, dataset_id, experiment_id, purpose, source_reference)
        ):
            raise PolicyError("actor, dataset_id, experiment_id, purpose and source_reference are required")
        start = parse_utc(requested_start_utc, field="requested_start_utc")
        end = parse_utc(requested_end_exclusive_utc, field="requested_end_exclusive_utc")
        if start >= end:
            raise PolicyError("requested_start_utc must precede requested_end_exclusive_utc")
        cutoff = self.preregistration.development_end_exclusive_utc
        holdout_start = self.preregistration.holdout_start_utc
        if end <= cutoff:
            window_class = "DEVELOPMENT"
        elif start >= holdout_start:
            window_class = "HOLDOUT"
        else:
            window_class = "MIXED"

        access_policy = self.preregistration.document["data_policy"]["holdout_access"]
        development_purposes = set(access_policy["development_purposes"])
        holdout_purposes = set(access_policy["holdout_purposes"])
        decision = "DENY"
        reason: str
        if window_class == "MIXED":
            reason = "A request may not cross the frozen development/holdout boundary"
        elif window_class == "DEVELOPMENT":
            if purpose in development_purposes:
                decision = "ALLOW"
                reason = "Purpose is preregistered for development-consumed data"
            else:
                reason = "Purpose is not preregistered for development data"
        else:
            if purpose not in holdout_purposes:
                reason = "Purpose is forbidden on holdout data"
            elif not authorization_id or not authorization_id.strip():
                reason = "Holdout access requires a non-empty authorization_id"
            else:
                decision = "ALLOW"
                reason = "Holdout purpose and explicit authorization are present"

        payload = {
            "request_id": request_id or canonical_sha256(
                {
                    "actor": actor,
                    "dataset_id": dataset_id,
                    "experiment_id": experiment_id,
                    "purpose": purpose,
                    "start": requested_start_utc,
                    "end": requested_end_exclusive_utc,
                    "authorization_id": authorization_id,
                    "requested_utc": utc_now(),
                }
            )[:24],
            "dataset_id": dataset_id,
            "experiment_id": experiment_id,
            "purpose": purpose,
            "requested_start_utc": requested_start_utc,
            "requested_end_exclusive_utc": requested_end_exclusive_utc,
            "window_class": window_class,
            "decision": decision,
            "reason": reason,
            "authorization_id": authorization_id,
            "source_reference": source_reference,
        }

        def validate(events: Sequence[Mapping[str, Any]]) -> None:
            self._assert_binding(events)
            if any(event["payload"].get("request_id") == payload["request_id"] for event in events[1:]):
                raise PolicyError(f"Duplicate request_id: {payload['request_id']}")
            if decision == "ALLOW" and window_class == "HOLDOUT" and purpose == "FINAL_EVALUATION":
                prior = sum(
                    event["payload"]["decision"] == "ALLOW"
                    and event["payload"]["window_class"] == "HOLDOUT"
                    and event["payload"]["purpose"] == "FINAL_EVALUATION"
                    and event["payload"]["experiment_id"] == experiment_id
                    and event["payload"]["dataset_id"] == dataset_id
                    for event in events[1:]
                )
                maximum = access_policy["max_final_evaluations_per_experiment_dataset"]
                if prior >= maximum:
                    # The outer method cannot change the already constructed
                    # payload while holding the ledger lock, so reject without
                    # claiming this was an allowed access.  The caller can log
                    # a new denied request after receiving the policy error.
                    raise PolicyError(
                        f"Final holdout evaluation limit reached for {experiment_id}/{dataset_id}"
                    )

        try:
            event = self.ledger.append(
                event_type="ACCESS_DECISION",
                actor=actor,
                payload=payload,
                correlation_id=experiment_id,
                pre_append_validator=validate,
            )
        except PolicyError as exc:
            # A repeated final evaluation is discovered atomically under lock.
            # Record a separate denial unless the problem is registry integrity.
            if "Final holdout evaluation limit reached" not in str(exc):
                raise
            payload["decision"] = "DENY"
            payload["reason"] = str(exc)
            event = self.ledger.append(
                event_type="ACCESS_DECISION",
                actor=actor,
                payload=payload,
                correlation_id=experiment_id,
                pre_append_validator=self._assert_binding,
            )
        if event["payload"]["decision"] != "ALLOW":
            raise AccessDenied(event["payload"]["reason"])
        return event


def create_cutoff_manifest(
    *,
    path: str  Path,
    preregistration_path: str  Path,
    actor: str,
) -> dict[str, Any]:
    """Create an immutable one-time snapshot of the cutoff policy."""

    destination = Path(path)
    prereg = Preregistration.load(preregistration_path)
    policy = prereg.document["data_policy"]
    document = {
        "schema_version": 1,
        "program_id": prereg.program_id,
        "preregistration_sha256": prereg.sha256,
        "created_utc": utc_now(),
        "actor": actor,
        "development_start_utc": policy["development_start_utc"],
        "development_end_exclusive_utc": policy["development_end_exclusive_utc"],
        "holdout_start_utc": policy["holdout_start_utc"],
        "boundary_rule": policy["holdout_boundary_rule"],
        "consumed_sources": policy["consumed_sources"],
        "status": "LIVE_LOCKED",
    }
    document["manifest_sha256"] = canonical_sha256(document)
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with destination.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical_json_bytes(document).decode("utf-8") + "\n")
            handle.flush()
    except FileExistsError as exc:
        raise IntegrityError(f"Cutoff manifest already exists; refusing overwrite: {destination}") from exc
    return document


def verify_cutoff_manifest(path: str  Path, preregistration_path: str  Path) -> dict[str, Any]:
    source = Path(path)
    try:
        document = json.loads(source.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise IntegrityError(f"Cutoff manifest cannot be verified: {source}") from exc
    if not isinstance(document, dict) or "manifest_sha256" not in document:
        raise IntegrityError("Cutoff manifest schema is invalid")
    body = dict(document)
    supplied = body.pop("manifest_sha256")
    if canonical_sha256(body) != supplied:
        raise IntegrityError("Cutoff manifest hash mismatch")
    prereg = Preregistration.load(preregistration_path)
    if document.get("preregistration_sha256") != prereg.sha256:
        raise IntegrityError("Cutoff manifest is bound to another preregistration")
    if document.get("development_end_exclusive_utc") != prereg.document["data_policy"][
        "development_end_exclusive_utc"
    ]:
        raise IntegrityError("Cutoff manifest cutoff does not match preregistration")
    return {"ok": True, "manifest_sha256": supplied, "status": document.get("status")}


def _main() -> None:
    parser = argparse.ArgumentParser(description="NAS100 V2 holdout access controller")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--preregistration", required=True, type=Path)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--actor", required=True)
    sub.add_parser("verify")
    request = sub.add_parser("request")
    request.add_argument("--actor", required=True)
    request.add_argument("--dataset-id", required=True)
    request.add_argument("--experiment-id", required=True)
    request.add_argument("--purpose", required=True)
    request.add_argument("--start", required=True)
    request.add_argument("--end", required=True)
    request.add_argument("--source-reference", required=True)
    request.add_argument("--authorization-id")
    args = parser.parse_args()
    controller = HoldoutAccessController(args.manifest, args.preregistration)
    if args.command == "init":
        output = controller.initialize(actor=args.actor)
    elif args.command == "verify":
        output = controller.verify()
    else:
        output = controller.request_access(
            actor=args.actor,
            dataset_id=args.dataset_id,
            experiment_id=args.experiment_id,
            purpose=args.purpose,
            requested_start_utc=args.start,
            requested_end_exclusive_utc=args.end,
            source_reference=args.source_reference,
            authorization_id=args.authorization_id,
        )
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        _main()
    except GovernanceError as exc:
        raise SystemExit(f"FAIL_CLOSED: {exc}") from exc

