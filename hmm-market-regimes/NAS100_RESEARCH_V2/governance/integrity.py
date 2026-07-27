"""Small, dependency-free integrity primitives used by governance ledgers.

The JSONL ledgers are append-only at the application layer.  Every record is
bound to its predecessor, so edits, insertions, reordering and partial writes
are detected before another record can be appended.  A ledger can also be
sealed with an immutable anchor; a sealed ledger rejects all later appends.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Sequence


ZERO_HASH = "0" * 64
HASH_RE = re.compile(r"^[0-9a-f]{64}$")


class GovernanceError(RuntimeError):
    """Base error for governance controls."""


class IntegrityError(GovernanceError):
    """Raised when persisted state cannot be trusted."""


class PolicyError(GovernanceError):
    """Raised when an action violates a frozen policy."""


def utc_now() -> str:
    """Return an RFC3339 timestamp with microsecond precision."""

    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def parse_utc(value: str, *, field: str = "timestamp") -> datetime:
    """Parse a timezone-aware timestamp and normalize it to UTC."""

    if not isinstance(value, str) or not value.strip():
        raise PolicyError(f"{field} must be a non-empty RFC3339 string")
    candidate = value.strip()
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise PolicyError(f"{field} is not valid RFC3339: {value!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise PolicyError(f"{field} must contain an explicit timezone: {value!r}")
    return parsed.astimezone(timezone.utc)


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize JSON deterministically and reject NaN/Infinity."""

    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise PolicyError(f"Value is not canonical JSON: {exc}") from exc
    return encoded.encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: str  Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def require_sha256(value: str, *, field: str) -> str:
    if not isinstance(value, str) or not HASH_RE.fullmatch(value):
        raise PolicyError(f"{field} must be a lowercase SHA-256 hex digest")
    return value


class HashChainedJsonl:
    """Append-only JSONL ledger with a hash chain and exclusive writer lock.

    The lock deliberately has no automatic stale-lock recovery.  A leftover
    lock indicates an interrupted write and therefore requires manual review;
    continuing automatically would not be fail-closed.
    """

    schema_version = 1

    def __init__(self, path: str  Path, ledger_type: str) -> None:
        self.path = Path(path)
        self.ledger_type = ledger_type
        self.lock_path = self.path.with_name(self.path.name + ".lock")
        self.seal_path = self.path.with_name(self.path.name + ".seal.json")

    def initialize(self, *, actor: str, metadata: Mapping[str, Any]) -> dict[str, Any]:
        if not actor.strip():
            raise PolicyError("actor cannot be empty")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = dict(metadata)
        event = self._build_event(
            sequence=0,
            previous_hash=ZERO_HASH,
            event_type="GENESIS",
            actor=actor,
            payload=payload,
            correlation_id=None,
        )
        encoded = canonical_json_bytes(event) + b"\n"
        try:
            descriptor = os.open(self.path, os.O_WRONLY  os.O_CREAT  os.O_EXCL, 0o600)
        except FileExistsError as exc:
            raise IntegrityError(f"Ledger already exists; refusing to replace it: {self.path}") from exc
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
        except BaseException:
            # Leave any partial file in place.  Future calls will fail integrity
            # checks instead of silently recreating history.
            raise
        self.verify()
        return event

    def _build_event(
        self,
        *,
        sequence: int,
        previous_hash: str,
        event_type: str,
        actor: str,
        payload: Mapping[str, Any],
        correlation_id: str  None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "schema_version": self.schema_version,
            "ledger_type": self.ledger_type,
            "sequence": sequence,
            "previous_hash": previous_hash,
            "recorded_utc": utc_now(),
            "event_type": event_type,
            "actor": actor,
            "correlation_id": correlation_id,
            "payload": dict(payload),
        }
        body["event_hash"] = canonical_sha256(body)
        return body

    @contextmanager
    def _exclusive_lock(self) -> Iterator[None]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(self.lock_path, os.O_WRONLY  os.O_CREAT  os.O_EXCL, 0o600)
        except FileExistsError as exc:
            raise IntegrityError(
                f"Ledger lock exists ({self.lock_path}); manual review is required"
            ) from exc
        try:
            os.write(descriptor, f"pid={os.getpid()} utc={utc_now()}\n".encode("utf-8"))
            os.fsync(descriptor)
            os.close(descriptor)
            yield
        finally:
            try:
                os.close(descriptor)
            except OSError:
                pass
            try:
                self.lock_path.unlink()
            except FileNotFoundError:
                pass

    def read_verified(self, *, require_exists: bool = True) -> list[dict[str, Any]]:
        if not self.path.exists():
            if require_exists:
                raise IntegrityError(f"Required ledger does not exist: {self.path}")
            return []
        raw = self.path.read_bytes()
        if not raw:
            raise IntegrityError(f"Ledger is empty: {self.path}")
        if not raw.endswith(b"\n"):
            raise IntegrityError(f"Ledger has a partial final record: {self.path}")
        lines = raw.splitlines()
        if any(not line.strip() for line in lines):
            raise IntegrityError(f"Ledger contains a blank record: {self.path}")

        events: list[dict[str, Any]] = []
        expected_previous = ZERO_HASH
        for index, line in enumerate(lines):
            try:
                event = json.loads(line)
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise IntegrityError(f"Ledger record {index} is not valid UTF-8 JSON") from exc
            if not isinstance(event, dict):
                raise IntegrityError(f"Ledger record {index} is not an object")
            required = {
                "schema_version",
                "ledger_type",
                "sequence",
                "previous_hash",
                "recorded_utc",
                "event_type",
                "actor",
                "correlation_id",
                "payload",
                "event_hash",
            }
            if set(event) != required:
                raise IntegrityError(
                    f"Ledger record {index} fields differ from the frozen schema"
                )
            if event["schema_version"] != self.schema_version:
                raise IntegrityError(f"Unsupported schema at record {index}")
            if event["ledger_type"] != self.ledger_type:
                raise IntegrityError(f"Wrong ledger type at record {index}")
            if event["sequence"] != index:
                raise IntegrityError(f"Non-contiguous sequence at record {index}")
            if event["previous_hash"] != expected_previous:
                raise IntegrityError(f"Broken hash chain at record {index}")
            if index == 0 and event["event_type"] != "GENESIS":
                raise IntegrityError("First ledger record must be GENESIS")
            if index > 0 and event["event_type"] == "GENESIS":
                raise IntegrityError(f"Unexpected GENESIS at record {index}")
            if not isinstance(event["payload"], dict):
                raise IntegrityError(f"payload is not an object at record {index}")
            if not isinstance(event["actor"], str) or not event["actor"].strip():
                raise IntegrityError(f"actor is invalid at record {index}")
            try:
                parse_utc(event["recorded_utc"], field=f"record {index} recorded_utc")
            except PolicyError as exc:
                raise IntegrityError(str(exc)) from exc
            supplied_hash = event["event_hash"]
            if not isinstance(supplied_hash, str) or not HASH_RE.fullmatch(supplied_hash):
                raise IntegrityError(f"Invalid event hash at record {index}")
            body = dict(event)
            del body["event_hash"]
            calculated = canonical_sha256(body)
            if calculated != supplied_hash:
                raise IntegrityError(f"Hash mismatch at record {index}")
            expected_previous = supplied_hash
            events.append(event)

        self._verify_seal(events)
        return events

    def verify(self) -> dict[str, Any]:
        events = self.read_verified()
        return {
            "ok": True,
            "ledger_type": self.ledger_type,
            "records": len(events),
            "head_sequence": events[-1]["sequence"],
            "head_hash": events[-1]["event_hash"],
            "sealed": self.seal_path.exists(),
        }

    def append(
        self,
        *,
        event_type: str,
        actor: str,
        payload: Mapping[str, Any],
        correlation_id: str  None = None,
        pre_append_validator: Callable[[Sequence[Mapping[str, Any]]], None]  None = None,
    ) -> dict[str, Any]:
        if event_type == "GENESIS" or not event_type.strip():
            raise PolicyError("append event_type must be non-empty and cannot be GENESIS")
        if not actor.strip():
            raise PolicyError("actor cannot be empty")
        # Validate serializability before acquiring the lock.
        canonical_json_bytes(dict(payload))
        with self._exclusive_lock():
            if self.seal_path.exists():
                raise IntegrityError(f"Ledger is sealed and immutable: {self.path}")
            events = self.read_verified()
            if pre_append_validator is not None:
                pre_append_validator(events)
            event = self._build_event(
                sequence=len(events),
                previous_hash=events[-1]["event_hash"],
                event_type=event_type,
                actor=actor,
                payload=payload,
                correlation_id=correlation_id,
            )
            with self.path.open("ab", buffering=0) as handle:
                handle.write(canonical_json_bytes(event) + b"\n")
                os.fsync(handle.fileno())
            self.read_verified()
            return event

    def seal(self, *, actor: str) -> dict[str, Any]:
        if not actor.strip():
            raise PolicyError("actor cannot be empty")
        with self._exclusive_lock():
            events = self.read_verified()
            if self.seal_path.exists():
                raise IntegrityError(f"Ledger seal already exists: {self.seal_path}")
            anchor = {
                "schema_version": 1,
                "ledger_type": self.ledger_type,
                "ledger_name": self.path.name,
                "record_count": len(events),
                "head_hash": events[-1]["event_hash"],
                "ledger_sha256": sha256_file(self.path),
                "sealed_utc": utc_now(),
                "actor": actor,
            }
            anchor["anchor_hash"] = canonical_sha256(anchor)
            encoded = canonical_json_bytes(anchor) + b"\n"
            descriptor = os.open(self.seal_path, os.O_WRONLY  os.O_CREAT  os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            self._verify_seal(events)
            return anchor

    def _verify_seal(self, events: Sequence[Mapping[str, Any]]) -> None:
        if not self.seal_path.exists():
            return
        try:
            anchor = json.loads(self.seal_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise IntegrityError(f"Ledger seal is invalid: {self.seal_path}") from exc
        if not isinstance(anchor, dict) or "anchor_hash" not in anchor:
            raise IntegrityError(f"Ledger seal schema is invalid: {self.seal_path}")
        body = dict(anchor)
        supplied = body.pop("anchor_hash")
        if canonical_sha256(body) != supplied:
            raise IntegrityError(f"Ledger seal hash mismatch: {self.seal_path}")
        checks = {
            "ledger_type": self.ledger_type,
            "ledger_name": self.path.name,
            "record_count": len(events),
            "head_hash": events[-1]["event_hash"],
            "ledger_sha256": sha256_file(self.path),
        }
        for key, expected in checks.items():
            if anchor.get(key) != expected:
                raise IntegrityError(f"Ledger seal mismatch for {key}: {self.seal_path}")

