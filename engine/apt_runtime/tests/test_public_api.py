"""Public import smoke tests for the Slice 2 effect-runtime boundary."""

from __future__ import annotations

from dataclasses import fields

import engine.apt_runtime as runtime
import engine.apt_runtime.adapters as adapters
import engine.apt_runtime.application as application
import engine.apt_runtime.domain as domain
import engine.apt_runtime.ports as ports
from engine.apt_runtime import (
    EffectCancellationAuthorization,
    EffectCancellationVerifier,
    EffectExecutionGrant,
    EffectGrantVerifier,
    EffectReconciliationCoordinator,
    EffectRecovery,
    EffectResultStore,
    EffectScheduler,
    ReconciliationAction,
    RecoveryAction,
    StoredEffectResult,
)
from engine.apt_runtime.adapters import SqliteEffectQueue, SqliteEffectResultStore


def test_slice2_symbols_are_bound_through_their_public_packages() -> None:
    """Public package imports resolve to the canonical implementation objects."""

    assert EffectExecutionGrant is domain.EffectExecutionGrant
    assert EffectCancellationAuthorization is ports.EffectCancellationAuthorization
    assert "cycle_id" in {field.name for field in fields(EffectExecutionGrant)}
    assert "cycle_id" in {field.name for field in fields(EffectCancellationAuthorization)}
    assert EffectCancellationVerifier is ports.EffectCancellationVerifier
    assert EffectGrantVerifier is ports.EffectGrantVerifier
    assert EffectResultStore is ports.EffectResultStore
    assert StoredEffectResult is ports.StoredEffectResult

    assert EffectScheduler is application.EffectScheduler
    assert EffectReconciliationCoordinator is application.EffectReconciliationCoordinator
    assert ReconciliationAction is application.ReconciliationAction
    assert EffectRecovery is application.EffectRecovery
    assert RecoveryAction is application.RecoveryAction

    assert SqliteEffectQueue is adapters.SqliteEffectQueue
    assert SqliteEffectResultStore is adapters.SqliteEffectResultStore


def test_slice2_root_all_matches_the_supported_convenience_surface() -> None:
    """The convenience root exposes contracts and orchestration, not adapters."""

    expected = {
        "EffectCancellationAuthorization",
        "EffectCancellationVerifier",
        "EffectExecutionGrant",
        "EffectGrantVerifier",
        "EffectReconciliationCoordinator",
        "EffectRecovery",
        "EffectResultStore",
        "EffectScheduler",
        "ReconciliationAction",
        "RecoveryAction",
        "StoredEffectResult",
    }

    assert expected <= set(runtime.__all__)
    assert all(getattr(runtime, name) is globals()[name] for name in expected)
    assert not hasattr(runtime, "SqliteEffectQueue")
    assert not hasattr(runtime, "SqliteEffectResultStore")
    assert not hasattr(runtime, "PostgresEffectQueue")
