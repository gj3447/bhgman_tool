"""APT vNext deterministic runtime with SQLite/PostgreSQL durability (Slices 0-1B).

Mutation is intentionally exported through :class:`DurableKernel`; concrete
event-store adapters remain trusted low-level ports under ``adapters``.
"""

from .application import (
    CommandDecision,
    DecisionKernel,
    DecisionOutcome,
    DurableKernel,
    DurableKernelError,
    EffectRequest,
)
from .domain import (
    AptCycleState,
    CanonicalCommandEnvelope,
    CommandSchemaError,
    EventEnvelope,
    EventType,
    state_hash,
)

__all__ = [
    "AptCycleState",
    "CanonicalCommandEnvelope",
    "CommandDecision",
    "CommandSchemaError",
    "DecisionKernel",
    "DecisionOutcome",
    "DurableKernel",
    "DurableKernelError",
    "EffectRequest",
    "EventEnvelope",
    "EventType",
    "state_hash",
]
