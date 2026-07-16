"""Typed, bounded diagnostics from deterministic external verifiers.

This module is the execution/observation port for diagnostic repair loops.  A
verifier result is more than a scalar fitness value: the next repair attempt
needs the concrete failure evidence (exit code, bounded stdout/stderr, timeout
state) while the acceptance decision must remain with the external tool.

Commands are argv-only and always run with ``shell=False``.  That is an
intentional hardening over coding-agent loops that execute an arbitrary shell
string.  Callers may derive argv/cwd from a candidate, but must explicitly
provide those functions; this module never interpolates candidate text into a
shell command.

The output is capped with a head/tail window.  This preserves the first parser
error and the final test summary without allowing an unbounded observation to
consume the next model context.
"""

from __future__ import annotations

import hashlib
import math
import os
import selectors
import signal
import subprocess
import tempfile
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

CommandFactory = Callable[[Any], Sequence[str]]
CwdResolver = Callable[[Any], str | Path | None]
CommandScoreFn = Callable[[int, str], float]
CandidateInput = Callable[[Any], str | None]

_ALL_STATUSES = frozenset({"passed", "failed", "timeout", "output_limit", "unavailable", "error"})
_VALID_STATUSES = frozenset({"passed", "failed"})
_TERMINAL_ERROR_STATUSES = frozenset({"unavailable", "error"})


def _bounded(text: str, limit: int) -> str:
    """Keep useful evidence from both ends of a potentially huge tool output."""
    if len(text) <= limit:
        return text
    marker = f"\n... <{len(text) - limit} chars truncated> ...\n"
    remaining = max(0, limit - len(marker))
    head = remaining // 2
    tail = remaining - head
    return f"{text[:head]}{marker}{text[-tail:] if tail else ''}"


def _summary(detail: str, limit: int = 800) -> str:
    compact = detail.strip()
    return _bounded(compact, limit) if compact else "(no verifier output)"


def _fingerprint(*, kind: str, status: str, exit_code: int | None, detail: str) -> str:
    material = "\0".join((kind, status, str(exit_code), detail.replace("\r\n", "\n")))
    return hashlib.sha256(material.encode("utf-8", "replace")).hexdigest()


def _finite_score(value: float) -> float:
    score = float(value)
    if not math.isfinite(score):
        raise ValueError("diagnostic score must be finite")
    return score


def _kill_process_tree(proc: subprocess.Popen[Any]) -> None:
    """Kill the verifier process group so timeout cannot leave child tools behind."""
    if os.name == "posix":
        try:
            os.killpg(proc.pid, signal.SIGKILL)
            return
        except (ProcessLookupError, PermissionError):
            pass
    try:
        proc.kill()
    except ProcessLookupError:
        pass


class _ByteCapture:
    """Bounded first/last-byte capture; memory never grows with verifier output."""

    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.total = 0
        self._head_limit = limit // 2
        self._tail_limit = limit - self._head_limit
        self._head = bytearray()
        self._tail = bytearray()

    def add(self, chunk: bytes) -> None:
        self.total += len(chunk)
        if len(self._head) < self._head_limit:
            take = min(len(chunk), self._head_limit - len(self._head))
            self._head.extend(chunk[:take])
        self._tail.extend(chunk)
        if len(self._tail) > self._tail_limit:
            del self._tail[: len(self._tail) - self._tail_limit]

    @property
    def overflowed(self) -> bool:
        return self.total > self.limit

    def text(self) -> str:
        if self.total <= self.limit:
            overlap = max(0, len(self._head) + len(self._tail) - self.total)
            raw = bytes(self._head) + bytes(self._tail[overlap:])
        else:
            omitted = self.total - self.limit
            marker = f"\n... <at least {omitted} output bytes truncated> ...\n".encode()
            raw = bytes(self._head) + marker + bytes(self._tail)
        return raw.decode("utf-8", "replace")


def _close_pipe(pipe: Any) -> None:
    if pipe is not None:
        try:
            pipe.close()
        except OSError:
            pass


def _bounded_process_output(
    proc: subprocess.Popen[bytes], *, timeout_s: float, output_limit: int
) -> tuple[str, bool, bool]:
    """Read output without unbounded buffering or waiting for escaped descendants."""
    capture = _ByteCapture(output_limit)
    selector = selectors.DefaultSelector()
    pipes = [pipe for pipe in (proc.stdout, proc.stderr) if pipe is not None]
    for pipe in pipes:
        os.set_blocking(pipe.fileno(), False)
        selector.register(pipe, selectors.EVENT_READ)
    deadline = time.monotonic() + timeout_s
    timed_out = False
    output_overflow = False
    try:
        while True:
            running = proc.poll() is None
            remaining = deadline - time.monotonic()
            if running and remaining <= 0:
                timed_out = True
                _kill_process_tree(proc)
                break
            wait = min(0.05, max(0.0, remaining)) if running else 0.0
            ready = selector.select(wait)
            if not ready and not running:
                # A detached descendant may still own a pipe. Do not wait for its EOF.
                break
            for key, _mask in ready:
                try:
                    chunk = os.read(key.fd, 65_536)
                except BlockingIOError:
                    continue
                if not chunk:
                    try:
                        selector.unregister(key.fileobj)
                    except KeyError:
                        pass
                    continue
                capture.add(chunk)
                if capture.overflowed:
                    output_overflow = True
                    _kill_process_tree(proc)
                    break
            if output_overflow:
                break
        if proc.poll() is None:
            try:
                proc.wait(timeout=0.2)
            except subprocess.TimeoutExpired:
                proc.kill()
                try:
                    proc.wait(timeout=0.2)
                except subprocess.TimeoutExpired:
                    pass
        # One non-blocking drain; never wait for inherited pipe EOF.
        for key, _mask in selector.select(0):
            try:
                chunk = os.read(key.fd, 65_536)
            except (BlockingIOError, OSError):
                continue
            if chunk:
                capture.add(chunk)
    finally:
        selector.close()
        for pipe in pipes:
            _close_pipe(pipe)
    return capture.text(), timed_out, output_overflow


@dataclass(frozen=True)
class DiagnosticFeedback:
    """One prompt-visible, bounded external-oracle observation.

    ``status`` is one of ``passed``, ``failed``, ``timeout``, ``unavailable``,
    or ``error``.  Only passed/failed are authoritative completed executions.
    A timeout is still repairable feedback, while unavailable/error identifies
    an infrastructure/configuration failure that the repair loop must not call
    success.
    """

    lens: str
    kind: str
    status: str
    passed: bool
    score: float
    diagnostic: str
    summary: str
    fingerprint: str
    command: tuple[str, ...] = ()
    exit_code: int | None = None
    timed_out: bool = False
    duration_ms: int = 0

    def __post_init__(self) -> None:
        if type(self.passed) is not bool:
            raise TypeError("passed must be a bool")
        if type(self.timed_out) is not bool:
            raise TypeError("timed_out must be a bool")
        if self.status not in _ALL_STATUSES:
            raise ValueError(f"unknown diagnostic status: {self.status!r}")
        if self.passed != (self.status == "passed"):
            raise ValueError("passed must be true exactly when status='passed'")
        _finite_score(self.score)
        if self.duration_ms < 0:
            raise ValueError("duration_ms must be >= 0")
        if self.timed_out != (self.status == "timeout"):
            raise ValueError("timed_out must be true exactly when status='timeout'")

    @property
    def valid(self) -> bool:
        return self.status in _VALID_STATUSES

    @property
    def terminal_error(self) -> bool:
        return self.status in _TERMINAL_ERROR_STATUSES

    @property
    def missing(self) -> str:
        """OpenHands-style name for the evidence still missing from completion."""
        return "" if self.passed else self.diagnostic

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class DiagnosticOracle(Protocol):
    """Port implemented by deterministic test/compiler/lint/proof oracles."""

    name: str
    kind: str

    def evaluate(self, candidate: Any) -> DiagnosticFeedback: ...


@dataclass(frozen=True)
class CallableDiagnosticOracle:
    """Small DI adapter for task-specific deterministic evaluators."""

    name: str
    kind: str
    evaluator: Callable[[Any], DiagnosticFeedback]

    def evaluate(self, candidate: Any) -> DiagnosticFeedback:
        feedback = self.evaluator(candidate)
        if not isinstance(feedback, DiagnosticFeedback):
            raise TypeError("diagnostic evaluator must return DiagnosticFeedback")
        return feedback


def feedback_from_value(
    *,
    lens: str,
    kind: str,
    passed: bool,
    score: float,
    diagnostic: str,
    status: str | None = None,
) -> DiagnosticFeedback:
    """Build typed feedback for a non-subprocess deterministic oracle."""
    if type(passed) is not bool:
        raise TypeError("passed must be a bool")
    resolved_status = status if status is not None else ("passed" if passed else "failed")
    detail = _bounded(str(diagnostic), 16_000)
    return DiagnosticFeedback(
        lens=lens,
        kind=kind,
        status=resolved_status,
        passed=passed,
        score=_finite_score(score),
        diagnostic=detail,
        summary="PASS" if passed else _summary(detail),
        fingerprint=_fingerprint(
            kind=kind,
            status=resolved_status,
            exit_code=None,
            detail=detail,
        ),
    )


@dataclass(frozen=True)
class CommandDiagnosticOracle:
    """Run an argv command and return bounded, typed diagnostic feedback.

    ``command`` and ``cwd`` may be static values or candidate-aware callables.
    The latter supports isolated candidate worktrees without coupling the loop
    to a particular code representation.  ``score_fn`` can extract a continuous
    metric such as pytest pass ratio; acceptance is still exit-code zero only.

    This class is a process controller, not a sandbox. Host execution is disabled
    by default; when explicitly enabled it is suitable only for trusted verifier
    binaries and trusted candidate material. Use a separately sandboxed
    ``DiagnosticOracle`` for generated or otherwise untrusted programs.
    """

    name: str
    kind: str
    command: tuple[str, ...] | CommandFactory
    cwd: str | Path | CwdResolver | None = None
    timeout_s: float = 120.0
    output_limit: int = 16_000
    score_fn: CommandScoreFn | None = None
    stdin: CandidateInput | None = None
    env: Mapping[str, str] | None = None
    inherit_env: bool = False
    allow_host_execution: bool = False

    def __post_init__(self) -> None:
        if isinstance(self.command, str):
            raise TypeError("command must be an argv sequence, never a shell string")
        if type(self.allow_host_execution) is not bool:
            raise TypeError("allow_host_execution must be a bool")
        if type(self.inherit_env) is not bool:
            raise TypeError("inherit_env must be a bool")
        if (
            isinstance(self.timeout_s, bool)
            or not isinstance(self.timeout_s, (int, float))
            or not math.isfinite(float(self.timeout_s))
            or self.timeout_s <= 0
        ):
            raise ValueError("timeout_s must be finite and > 0")
        if type(self.output_limit) is not int or self.output_limit < 256:
            raise ValueError("output_limit must be >= 256")

    def _argv(self, candidate: Any) -> tuple[str, ...]:
        raw = self.command(candidate) if callable(self.command) else self.command
        if isinstance(raw, str):
            raise TypeError("command factory must return argv, never a shell string")
        argv = tuple(raw)
        if not argv or not all(isinstance(part, str) and part for part in argv):
            raise ValueError("command argv must contain at least one non-empty string")
        return argv

    def _cwd(self, candidate: Any) -> str | None:
        raw = self.cwd(candidate) if callable(self.cwd) else self.cwd
        return None if raw is None else os.fspath(raw)

    def _feedback(
        self,
        *,
        status: str,
        argv: tuple[str, ...],
        detail: str,
        duration_ms: int,
        exit_code: int | None = None,
        timed_out: bool = False,
        score: float = 0.0,
    ) -> DiagnosticFeedback:
        bounded = _bounded(detail, self.output_limit)
        passed = status == "passed"
        return DiagnosticFeedback(
            lens=self.name,
            kind=self.kind,
            status=status,
            passed=passed,
            score=_finite_score(score),
            diagnostic=bounded,
            summary="PASS" if passed else _summary(bounded),
            fingerprint=_fingerprint(
                kind=self.kind,
                status=status,
                exit_code=exit_code,
                detail=bounded,
            ),
            command=argv,
            exit_code=exit_code,
            timed_out=timed_out,
            duration_ms=duration_ms,
        )

    def evaluate(self, candidate: Any) -> DiagnosticFeedback:
        started = time.monotonic()
        argv: tuple[str, ...] = ()
        proc: subprocess.Popen[bytes] | None = None
        stdin_file: Any = None
        try:
            if self.allow_host_execution is not True:
                raise ValueError(
                    "host execution disabled; set allow_host_execution=True only for trusted "
                    "verifiers, or inject a sandboxed DiagnosticOracle"
                )
            argv = self._argv(candidate)
            cwd = self._cwd(candidate)
            candidate_input = self.stdin(candidate) if self.stdin is not None else None
            if candidate_input is not None:
                if not isinstance(candidate_input, str):
                    raise TypeError("stdin candidate adapter must return str or None")
                stdin_file = tempfile.TemporaryFile(mode="w+b")
                stdin_file.write(candidate_input.encode("utf-8"))
                stdin_file.seek(0)
            base_env = (
                dict(os.environ)
                if self.inherit_env
                else {
                    "PATH": os.environ.get("PATH", os.defpath),
                    "LANG": "C.UTF-8",
                    "LC_ALL": "C.UTF-8",
                }
            )
            env = {**base_env, **dict(self.env or {})}
            proc = subprocess.Popen(  # noqa: S603 -- explicit host opt-in, argv-only
                argv,
                cwd=cwd,
                env=env,
                stdin=stdin_file,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=os.name == "posix",
                shell=False,
            )
            detail, timed_out, output_overflow = _bounded_process_output(
                proc,
                timeout_s=self.timeout_s,
                output_limit=self.output_limit,
            )
            if timed_out:
                detail = f"timeout after {self.timeout_s:g}s\n{detail}".rstrip()
                return self._feedback(
                    status="timeout",
                    argv=argv,
                    detail=detail,
                    duration_ms=int((time.monotonic() - started) * 1000),
                    timed_out=True,
                )
            if output_overflow:
                return self._feedback(
                    status="output_limit",
                    argv=argv,
                    detail=f"output limit exceeded ({self.output_limit} bytes)\n{detail}",
                    duration_ms=int((time.monotonic() - started) * 1000),
                )
            assert proc.returncode is not None
            status = "passed" if proc.returncode == 0 else "failed"
            score = (
                self.score_fn(proc.returncode, detail)
                if self.score_fn is not None
                else (1.0 if proc.returncode == 0 else 0.0)
            )
            return self._feedback(
                status=status,
                argv=argv,
                detail=detail,
                duration_ms=int((time.monotonic() - started) * 1000),
                exit_code=proc.returncode,
                score=score,
            )
        except OSError as exc:
            return self._feedback(
                status="unavailable",
                argv=argv,
                detail=f"{type(exc).__name__}: {exc}",
                duration_ms=int((time.monotonic() - started) * 1000),
            )
        except Exception as exc:  # noqa: BLE001 -- candidate adapters are an injected boundary
            return self._feedback(
                status="error",
                argv=argv,
                detail=f"{type(exc).__name__}: {exc}",
                duration_ms=int((time.monotonic() - started) * 1000),
            )
        finally:
            if proc is not None and proc.poll() is None:
                _kill_process_tree(proc)
                try:
                    proc.wait(timeout=0.2)
                except subprocess.TimeoutExpired:
                    pass
            if stdin_file is not None:
                stdin_file.close()


__all__ = [
    "CallableDiagnosticOracle",
    "CandidateInput",
    "CommandDiagnosticOracle",
    "CommandFactory",
    "CommandScoreFn",
    "CwdResolver",
    "DiagnosticFeedback",
    "DiagnosticOracle",
    "feedback_from_value",
]
