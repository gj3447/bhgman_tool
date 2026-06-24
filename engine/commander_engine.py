"""Common commander engine contract.

The 7-commander runtime has several entry points (CLI, MCP, legion). This module
defines the small contract those entry points should share before any transport
or presentation formatting is added.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol


CommanderContext = dict
CommanderOutput = dict
EngineFn = Callable[[CommanderContext], CommanderOutput]


class CommanderEngine(Protocol):
    """Transport-neutral commander core.

    ``deterministic_core`` is the floor: it must work without an LLM. ``run`` is
    the shared execution surface used by CLI/MCP/legion adapters.
    """

    name: str
    verb: str
    requires: tuple[str, ...]
    provides: tuple[str, ...]

    def deterministic_core(self, context: CommanderContext) -> CommanderOutput: ...

    def vllm_enrich(self, context: CommanderContext) -> CommanderOutput | None: ...

    def run(self, context: CommanderContext) -> CommanderOutput: ...


class DeterministicCommanderEngine:
    """Base class for commanders whose current measured scope is deterministic-only."""

    name: str
    verb: str
    requires: tuple[str, ...]
    provides: tuple[str, ...]

    def deterministic_core(self, context: CommanderContext) -> CommanderOutput:
        raise NotImplementedError

    def vllm_enrich(self, context: CommanderContext) -> CommanderOutput | None:
        return None

    def run(self, context: CommanderContext) -> CommanderOutput:
        output = self.deterministic_core(context)
        enrich = self.vllm_enrich(context)
        if enrich:
            output.update(enrich)
        return output


__all__ = [
    "CommanderContext",
    "CommanderEngine",
    "CommanderOutput",
    "DeterministicCommanderEngine",
    "EngineFn",
]
