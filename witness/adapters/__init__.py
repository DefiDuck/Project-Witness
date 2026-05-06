"""SDK adapters: monkey-patch known LLM clients to record into the active trace.

Adapters are *opt-in* per SDK. Importing `witness.adapters.anthropic` patches the
Anthropic SDK; importing `witness.adapters.openai` patches OpenAI. Without these
imports, Witness still works — users can call `record_decision` themselves.

`install_all()` patches whichever SDKs are importable and is what the example
script and `witness perturb` rerun path call.
"""
from __future__ import annotations

import logging
from typing import Callable

log = logging.getLogger(__name__)

_INSTALLED: dict[str, bool] = {}


def install_all() -> dict[str, bool]:
    """Install every adapter for which the underlying SDK is importable.

    Returns a dict of {adapter_name: installed_bool}. Safe to call multiple times.
    """
    results: dict[str, bool] = {}
    for adapter, installer in _ADAPTERS.items():
        if _INSTALLED.get(adapter):
            results[adapter] = True
            continue
        try:
            installer()
            _INSTALLED[adapter] = True
            results[adapter] = True
        except ImportError:
            results[adapter] = False
        except Exception as e:  # pragma: no cover — defensive
            log.warning("Failed to install witness adapter '%s': %s", adapter, e)
            results[adapter] = False
    return results


def _install_anthropic() -> None:
    from witness.adapters import anthropic as _a  # noqa: F401  (registers patches on import)

    _a.install()


def _install_openai() -> None:
    from witness.adapters import openai as _o  # noqa: F401

    _o.install()


_ADAPTERS: dict[str, Callable[[], None]] = {
    "anthropic": _install_anthropic,
    "openai": _install_openai,
}


__all__ = ["install_all"]
