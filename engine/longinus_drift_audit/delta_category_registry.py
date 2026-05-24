"""
delta_category_registry.py — Wave 9c DIP refactor (DeltaCategoryRegistry).

Resolves vr-longinus-v3.4-wave6-8-followup-naesengmoon-3lens-2026-05-20 D3-DIP
HIGH defect (4 module-level singleton DeltaCategory instances → direct
concrete dependency from high-level lens). Introduces a Protocol abstraction
+ default registry singleton so callers can inject test mocks via factory.

Cascade effect:
- D3-SRP: kg_binding_delta_lens.py 측 9+ concepts → moves DeltaCategory
  instances to registry, lens definitions become thinner.
- D3-LSP: registry.get(name) 측 *common interface* — 1:1 lens + 1:N lens
  측 substitutable via factory.
- D3-DIP: high-level lens 측 abstract registry 측 의존, *not* concrete
  module-level singleton.

References:
    Martin, R.C. 2017. Clean Architecture. Ch.11 DIP.
    Fowler, M. 2004. Inversion of Control Containers and the
        Dependency Injection pattern.

# KG: ATOM_Skill_longinus, ap-longinus-v34-bx-lens-substitute-2026-05-20,
      vr-longinus-v3.4-wave6-8-followup-naesengmoon-3lens-2026-05-20 (D3-DIP-FAIL),
      Constrain Layer (1) t_sourcecode_required_fields_not_null enforced this MERGE
"""

from __future__ import annotations

from typing import Protocol, TypeVar, runtime_checkable

from delta_lens import DeltaCategory

S = TypeVar("S")
DS = TypeVar("DS")


@runtime_checkable
class DeltaCategoryRegistryProto(Protocol):
    """Protocol for a DeltaCategory registry — DIP abstraction.

    High-level code (DeltaLens factories) depends on this Protocol, not on
    concrete module-level singletons. Test code can inject mocks by
    implementing this Protocol.
    """

    def register(self, name: str, cat: DeltaCategory) -> None: ...

    def get(self, name: str) -> DeltaCategory: ...

    def has(self, name: str) -> bool: ...

    def names(self) -> list[str]: ...


class DefaultDeltaCategoryRegistry:
    """Default in-memory registry. Singleton via module-level instance below."""

    def __init__(self) -> None:
        self._cats: dict[str, DeltaCategory] = {}

    def register(self, name: str, cat: DeltaCategory) -> None:
        if name in self._cats:
            raise ValueError(
                f"DeltaCategory '{name}' already registered. "
                f"Use a different name or unregister explicitly."
            )
        self._cats[name] = cat

    def get(self, name: str) -> DeltaCategory:
        if name not in self._cats:
            raise KeyError(
                f"DeltaCategory '{name}' not registered. " f"Known: {sorted(self._cats.keys())}"
            )
        return self._cats[name]

    def has(self, name: str) -> bool:
        return name in self._cats

    def names(self) -> list[str]:
        return sorted(self._cats.keys())

    def unregister(self, name: str) -> None:
        """Test-only escape hatch. Production code should not unregister."""
        self._cats.pop(name, None)


# Module-level default registry singleton — backward-compat for callers that
# expect a global registry. Test code can construct a fresh
# DefaultDeltaCategoryRegistry() and inject it via factory functions.
default_registry: DeltaCategoryRegistryProto = DefaultDeltaCategoryRegistry()
