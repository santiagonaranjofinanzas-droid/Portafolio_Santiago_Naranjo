"""Fail-closed research governance for NAS100 Research V2.

Exports are loaded on first use to keep every command-line module independent.
"""

from typing import Any

__all__ = [
    "AccessDenied",
    "ExperimentRegistry",
    "GovernanceError",
    "HashChainedJsonl",
    "HoldoutAccessController",
    "IntegrityError",
    "PolicyError",
    "Preregistration",
]


def __getattr__(name: str) -> Any:
    if name in {"AccessDenied", "HoldoutAccessController"}:
        from . import access_manifest

        return getattr(access_manifest, name)
    if name in {"GovernanceError", "HashChainedJsonl", "IntegrityError", "PolicyError"}:
        from . import integrity

        return getattr(integrity, name)
    if name == "Preregistration":
        from .preregistration import Preregistration

        return Preregistration
    if name == "ExperimentRegistry":
        from .registry import ExperimentRegistry

        return ExperimentRegistry
    raise AttributeError(name)
