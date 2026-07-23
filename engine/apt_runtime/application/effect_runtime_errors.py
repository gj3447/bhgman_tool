"""Shared fail-closed errors for the Slice 2 effect runtime."""

from __future__ import annotations

from engine.apt_runtime.domain.effect_runtime import BudgetLimit


class EffectSchedulerError(RuntimeError):
    """Base class for fail-closed scheduler failures."""


class EffectRuntimeStateError(EffectSchedulerError):
    """The operational queue and canonical event state do not safely align."""


class BudgetExhaustedError(EffectSchedulerError):
    """External execution is blocked by one or more snapshotted budget limits."""

    def __init__(self, limits: tuple[BudgetLimit, ...]) -> None:
        self.limits = limits
        names = ", ".join(limit.value for limit in limits)
        super().__init__(f"effect runtime budget exhausted: {names}")


class ProviderIdentityError(EffectSchedulerError):
    """A provider returned an observation for another fenced execution identity."""


class ProviderInvocationError(EffectSchedulerError):
    """A provider raised after invocation, so its external outcome is unknown."""


__all__ = [
    "BudgetExhaustedError",
    "EffectRuntimeStateError",
    "EffectSchedulerError",
    "ProviderIdentityError",
    "ProviderInvocationError",
]
