"""Canonical Axi NAS100 tick and bar quality tooling.

Exports are lazy so ``python -m ...data_tools.axi_qa`` has no runpy warning.
"""

from typing import Any

__all__ = ["audit_axi_dataset", "verify_canonical_manifest"]


def __getattr__(name: str) -> Any:
    if name in __all__:
        from . import axi_qa

        return getattr(axi_qa, name)
    raise AttributeError(name)
"""Canonical data tooling for the NAS100 V2 research program."""
