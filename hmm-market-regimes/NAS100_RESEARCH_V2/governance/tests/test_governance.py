from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from NAS100_RESEARCH_V2.governance.access_manifest import (
    AccessDenied,
    HoldoutAccessController,
    create_cutoff_manifest,
    verify_cutoff_manifest,
)
from NAS100_RESEARCH_V2.governance.integrity import HashChainedJsonl, IntegrityError, PolicyError
from NAS100_RESEARCH_V2.governance.preregistration import Preregistration
from NAS100_RESEARCH_V2.governance.registry import ExperimentRegistry


HERE = Path(__file__).resolve().parents[1]
PREREGISTRATION = HERE / "config" / "research_preregistration.v1.json"
HEX_A = "a" * 64
HEX_B = "b" * 64
HEX_C = "c" * 64


class IntegrityLedgerTests(unittest.TestCase):
    def test_tamper_and_partial_write_are_detected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "ledger.jsonl"
            ledger = HashChainedJsonl(path, "TEST")
            ledger.initialize(actor="tester", metadata={"purpose": "test"})
            ledger.append(event_type="NOTE", actor="tester", payload={"value": 1})
            self.assertEqual(ledger.verify()["records"], 2)

            events = path.read_text(encoding="utf-8").splitlines()
            changed = json.loads(events[1])
            changed["payload"]["value"] = 2
            events[1] = json.dumps(changed, sort_keys=True, separators=(",", ":"))
            path.write_text("\n".join(events) + "\n", encoding="utf-8")
            with self.assertRaises(IntegrityError):
                ledger.verify()

            path.unlink()
            ledger.initialize(actor="tester", metadata={"purpose": "test"})
            path.write_bytes(path.read_bytes().rstrip(b"\n"))
            with self.assertRaises(IntegrityError):
                ledger.verify()

    def test_sealed_ledger_rejects_append(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "ledger.jsonl"
            ledger = HashChainedJsonl(path, "TEST")
            ledger.initialize(actor="tester", metadata={})
            ledger.seal(actor="tester")
            self.assertTrue(ledger.verify()["sealed"])
            with self.assertRaises(IntegrityError):
                ledger.append(event_type="NOTE", actor="tester", payload={})


class PreregistrationTests(unittest.TestCase):
    def test_production_preregistration_is_valid_and_canonical(self) -> None:
        prereg = Preregistration.load(PREREGISTRATION)
        self.assertEqual(prereg.candidate_budget("TREND_V2"), 12)
        self.assertEqual(prereg.candidate_budget("MEAN_REVERSION_V2"), 9)
        self.assertEqual(len(prereg.sha256), 64)
        self.assertEqual(prereg.holdout_start_utc, prereg.development_end_exclusive_utc)


class ExperimentRegistryTests(unittest.TestCase):
    def test_happy_path_and_invalid_transition(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "experiments.jsonl"
            registry = ExperimentRegistry(path, PREREGISTRATION)
            registry.initialize(actor="tester")
            registry.register(
                actor="tester",
                experiment_id="TRENDV2.C01",
                model_family="TREND_V2",
                candidate_index=1,
                candidate_config_sha256=HEX_A,
                canonical_data_manifest_sha256=HEX_B,
                hypothesis="A preregistered causal hypothesis",
                primary_metric="outer_oos_daily_sharpe",
            )
            registry.start(
                actor="tester",
                experiment_id="TRENDV2.C01",
                code_identity="git:test",
                environment_sha256=HEX_C,
                random_seed=20260710,
            )
            registry.record_result(
                actor="tester",
                experiment_id="TRENDV2.C01",
                artifact_manifest_sha256=HEX_A,
                decision="FAIL",
                primary_metric_name="outer_oos_daily_sharpe",
                primary_metric_value=0.2,
                metrics={"profit_factor": 0.9},
            )
            summary = registry.verify()
            self.assertEqual(summary["state_counts"]["COMPLETED"], 1)
            self.assertEqual(summary["budget_usage"]["TREND_V2"]["used"], 1)
            with self.assertRaises(PolicyError):
                registry.record_result(
                    actor="tester",
                    experiment_id="TRENDV2.C01",
                    artifact_manifest_sha256=HEX_A,
                    decision="PASS",
                    primary_metric_name="outer_oos_daily_sharpe",
                    primary_metric_value=2.0,
                    metrics={},
                )

    def test_duplicate_candidate_index_is_denied(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            registry = ExperimentRegistry(Path(temporary) / "experiments.jsonl", PREREGISTRATION)
            registry.initialize(actor="tester")
            common = dict(
                actor="tester",
                model_family="MEAN_REVERSION_V2",
                candidate_index=1,
                candidate_config_sha256=HEX_A,
                canonical_data_manifest_sha256=HEX_B,
                hypothesis="Residual stationarity predicts reversal",
                primary_metric="net_conditional_reversal",
            )
            registry.register(experiment_id="MRV2.C01", **common)
            with self.assertRaises(PolicyError):
                registry.register(experiment_id="MRV2.C02", **common)


class HoldoutAccessTests(unittest.TestCase):
    def test_cutoff_and_one_shot_holdout_are_enforced_and_logged(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            ledger_path = Path(temporary) / "access.jsonl"
            controller = HoldoutAccessController(ledger_path, PREREGISTRATION)
            controller.initialize(actor="tester")
            controller.request_access(
                actor="tester",
                dataset_id="DEV",
                experiment_id="TRENDV2.C01",
                purpose="TRAINING",
                requested_start_utc="2026-07-01T00:00:00Z",
                requested_end_exclusive_utc="2026-07-02T00:00:00Z",
                source_reference="fixture",
                request_id="REQ_DEV_ALLOW",
            )
            with self.assertRaises(AccessDenied):
                controller.request_access(
                    actor="tester",
                    dataset_id="MIXED",
                    experiment_id="TRENDV2.C01",
                    purpose="TRAINING",
                    requested_start_utc="2026-07-10T00:00:00Z",
                    requested_end_exclusive_utc="2026-07-12T00:00:00Z",
                    source_reference="fixture",
                    request_id="REQ_MIXED_DENY",
                )
            with self.assertRaises(AccessDenied):
                controller.request_access(
                    actor="tester",
                    dataset_id="FUTURE",
                    experiment_id="TRENDV2.C01",
                    purpose="TRAINING",
                    requested_start_utc="2026-07-11T00:00:00Z",
                    requested_end_exclusive_utc="2026-08-01T00:00:00Z",
                    source_reference="fixture",
                    request_id="REQ_HOLDOUT_TRAIN_DENY",
                )
            controller.request_access(
                actor="tester",
                dataset_id="FUTURE",
                experiment_id="TRENDV2.C01",
                purpose="FINAL_EVALUATION",
                requested_start_utc="2026-07-11T00:00:00Z",
                requested_end_exclusive_utc="2026-08-01T00:00:00Z",
                source_reference="fixture",
                authorization_id="AUTH-001",
                request_id="REQ_FINAL_ALLOW",
            )
            with self.assertRaises(AccessDenied):
                controller.request_access(
                    actor="tester",
                    dataset_id="FUTURE",
                    experiment_id="TRENDV2.C01",
                    purpose="FINAL_EVALUATION",
                    requested_start_utc="2026-08-01T00:00:00Z",
                    requested_end_exclusive_utc="2026-09-01T00:00:00Z",
                    source_reference="fixture",
                    authorization_id="AUTH-002",
                    request_id="REQ_FINAL_REPEAT_DENY",
                )
            summary = controller.verify()
            self.assertEqual(summary["allow_count"], 2)
            self.assertEqual(summary["deny_count"], 3)
            self.assertEqual(summary["holdout_allow_count"], 1)

    def test_cutoff_manifest_is_immutable_and_verifiable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "cutoff.json"
            create_cutoff_manifest(
                path=path, preregistration_path=PREREGISTRATION, actor="tester"
            )
            self.assertTrue(verify_cutoff_manifest(path, PREREGISTRATION)["ok"])
            with self.assertRaises(IntegrityError):
                create_cutoff_manifest(
                    path=path, preregistration_path=PREREGISTRATION, actor="tester"
                )


if __name__ == "__main__":
    unittest.main()
