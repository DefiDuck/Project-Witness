"""Registry of perturbation types so the CLI can look them up by name."""
from __future__ import annotations

from typing import Any, Callable, Type

from witness.perturbations.base import Perturbation

# name -> factory(**params) -> Perturbation
PERTURBATION_REGISTRY: dict[str, Callable[..., Perturbation]] = {}


def register_perturbation(
    name: str | None = None,
) -> Callable[[Type[Perturbation]], Type[Perturbation]]:
    """Class decorator. Registers a Perturbation subclass under `name` (defaulting to
    the class's `.name` attribute or its lowercased class name).
    """

    def deco(cls: Type[Perturbation]) -> Type[Perturbation]:
        key = name or cls.name or cls.__name__.lower()
        cls.name = key
        PERTURBATION_REGISTRY[key] = cls
        return cls

    return deco


def get_perturbation(name: str, **params: Any) -> Perturbation:
    """Construct a perturbation by registered name."""
    if name not in PERTURBATION_REGISTRY:
        raise KeyError(
            f"unknown perturbation '{name}'. registered: {sorted(PERTURBATION_REGISTRY)}"
        )
    return PERTURBATION_REGISTRY[name](**params)


def list_perturbations() -> list[str]:
    return sorted(PERTURBATION_REGISTRY.keys())


__all__ = [
    "PERTURBATION_REGISTRY",
    "register_perturbation",
    "get_perturbation",
    "list_perturbations",
]
