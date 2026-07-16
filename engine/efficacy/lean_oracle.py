"""Ungameable Lean oracle for the 거기 (headroom) composition test.

The task fixes the THEOREM STATEMENT; the model supplies ONLY the proof term/tactic block. So
statement-fidelity and no-weakening are enforced BY CONSTRUCTION — the model cannot rename or weaken
`theorem T <sig> := <proof>` because we own `T` and `<sig>`. The hidden eval is therefore ungameable:

  proven  ⇔  assemble(sig + proof) compiles with no `error:`  AND  `#print axioms T` shows no `sorryAx`.

A `sorry` compiles (warning only) but taints axioms → caught. A wrong proof fails to compile → caught.
A weakened/renamed statement is impossible → the model never sees the `theorem ... :=` line.

`public` (the repair signal the loop MAY see) = compiles-clean + the lean error text (for oracle-guided
repair). Standalone Mathlib-free (matches the W4 corpus; `lean` resolves core only).

# KG: project-apt-ultracode-roadmap-2026-06-02 (거기/headroom faithful test), lean_axiom_probe (W4)
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import signal
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

_ERROR_RE = re.compile(r"\berror:", re.IGNORECASE)
_LEAN_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_']*$")
_TRAILING_COMMAND_RE = re.compile(
    r"(?mi)^\s*(?:"
    r"#(?:eval|check|print|reduce)\b|"
    r"(?:import|theorem|lemma|def|axiom|opaque|example|namespace|section|"
    r"end|set_option)\b"
    r")"
)
SANDBOX_PROTOCOL = "pi-lean-sandbox-runner/v2"
SANDBOX_IDENTITY_PROTOCOL = "pi-lean-sandbox-identity/v1"
ORACLE_ISOLATION = "external-sandbox-runner/v2"
SANDBOX_RUNNER_ENV = "PI_LEAN_SANDBOX_RUNNER"
_REFERENCE_MACOS_RUNNER = Path(__file__).with_name("lean_sandbox_runner_macos.py")
_MAX_RUNNER_OUTPUT = 64_000


class SandboxUnavailable(RuntimeError):
    """No executable external Lean isolation boundary is configured."""


class SandboxProtocolError(RuntimeError):
    """The external runner failed or violated the frozen JSON protocol."""


class UnsafeLeanPayload(ValueError):
    """The proof contains an obvious command-level escape from the proof slot."""


@dataclass(frozen=True)
class LeanCompilerIdentity:
    toolchain: str
    version: str
    binary_sha256: str

    def as_record(self) -> dict[str, str]:
        return {
            "lean_toolchain": self.toolchain,
            "lean_version": self.version,
            "lean_binary_sha256": self.binary_sha256,
        }


@dataclass(frozen=True)
class LeanVerdict:
    compiles: bool  # no `error:` (the public/repair signal)
    proven: bool  # compiles AND no sorryAx — the ungameable hidden eval
    sorry_tainted: bool
    error_tail: str  # last lean output (for oracle-guided repair feedback)

    @property
    def public_score(self) -> float:
        return 1.0 if self.compiles else 0.0

    @property
    def graded_score(self) -> float:
        """3-level partial-progress fitness: 0 = no compile, 0.5 = compiles but sorry-tainted
        (incomplete), 1.0 = proven (compiles + no sorryAx). Gives read-back/repair a gradient
        that the binary `proven` hides."""
        if self.proven:
            return 1.0
        if self.compiles:
            return 0.5
        return 0.0


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _configured_runner(
    *,
    environ: Mapping[str, str] | None = None,
    system: str | None = None,
) -> Path:
    env = os.environ if environ is None else environ
    raw = env.get(SANDBOX_RUNNER_ENV)
    if raw:
        configured = Path(raw)
        if not configured.is_absolute():
            raise SandboxUnavailable(f"{SANDBOX_RUNNER_ENV} must be an absolute path")
    elif (system or platform.system()) == "Darwin":
        configured = _REFERENCE_MACOS_RUNNER
    else:
        raise SandboxUnavailable(
            f"{SANDBOX_RUNNER_ENV} is required outside Darwin; host Lean fallback is disabled"
        )
    try:
        resolved = configured.resolve(strict=True)
    except OSError as exc:
        raise SandboxUnavailable(f"sandbox runner is unavailable: {configured}") from exc
    if not resolved.is_file() or not os.access(resolved, os.X_OK):
        raise SandboxUnavailable(f"sandbox runner is not executable: {resolved}")
    return resolved


def sandbox_available(
    runner: str | Path | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    system: str | None = None,
) -> bool:
    """Whether a valid executable sandbox boundary can be resolved."""
    try:
        if runner is None:
            _configured_runner(environ=environ, system=system)
        else:
            raw = os.fspath(runner)
            _configured_runner(
                environ={SANDBOX_RUNNER_ENV: raw},
                system=system,
            )
    except SandboxUnavailable:
        return False
    return True


def _reject_obvious_command_escape(proof: str) -> None:
    if "\x00" in proof:
        raise UnsafeLeanPayload("Lean proof contains a NUL byte")
    if _TRAILING_COMMAND_RE.search(proof):
        raise UnsafeLeanPayload(
            "Lean proof contains an obvious command-level payload; the proof slot accepts terms only"
        )


def _kill_process_group(process: subprocess.Popen[str]) -> None:
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGKILL)
            return
        except (ProcessLookupError, PermissionError):
            pass
    try:
        process.kill()
    except ProcessLookupError:
        pass


def _runner_identity(runner: Path, *, output_limit: int) -> LeanCompilerIdentity:
    before_hash = _sha256_file(runner)
    try:
        process = subprocess.run(  # noqa: S603 -- absolute, pre-hashed executable; no shell
            [str(runner), "--identity"],
            capture_output=True,
            text=True,
            shell=False,
            timeout=30,
            check=False,
            env={
                "PATH": os.environ.get("PATH", os.defpath),
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
            },
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise SandboxUnavailable("Lean sandbox runner identity probe failed") from exc
    if _sha256_file(runner) != before_hash:
        raise SandboxProtocolError("Lean sandbox runner changed during identity probe")
    if len(process.stdout) + len(process.stderr) > output_limit:
        raise SandboxProtocolError("Lean sandbox identity exceeded its output limit")
    if process.returncode != 0:
        detail = (process.stderr or process.stdout).strip()[-2000:]
        raise SandboxUnavailable(
            f"Lean sandbox runner identity probe exited {process.returncode}: {detail}"
        )
    try:
        response: Any = json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        raise SandboxProtocolError("Lean sandbox runner identity returned invalid JSON") from exc
    expected = {
        "protocol",
        "lean_toolchain",
        "lean_version",
        "lean_binary_sha256",
    }
    if not isinstance(response, dict) or set(response) != expected:
        raise SandboxProtocolError("Lean sandbox runner identity has an invalid field set")
    if response["protocol"] != SANDBOX_IDENTITY_PROTOCOL:
        raise SandboxProtocolError("Lean sandbox runner identity protocol mismatch")
    if not all(
        isinstance(response[key], str) and response[key]
        for key in ("lean_toolchain", "lean_version", "lean_binary_sha256")
    ):
        raise SandboxProtocolError("Lean sandbox runner identity fields must be non-empty strings")
    digest = response["lean_binary_sha256"]
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise SandboxProtocolError("Lean sandbox runner returned an invalid binary digest")
    return LeanCompilerIdentity(
        toolchain=response["lean_toolchain"],
        version=response["lean_version"],
        binary_sha256=digest,
    )


@dataclass(frozen=True)
class ExternalSandboxLeanEvaluator:
    """Authoritative v2 evaluator using an external isolation executable.

    The runner—not this defense-in-depth parser—is the security authority. The
    protocol sends fixed statement components as JSON and accepts only a strict
    verdict object. No host ``lean`` fallback exists.
    """

    runner: Path
    timeout: float = 60.0
    output_limit: int = _MAX_RUNNER_OUTPUT
    lean_toolchain: str = field(init=False)
    lean_version: str = field(init=False)
    lean_binary_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        resolved = _configured_runner(environ={SANDBOX_RUNNER_ENV: os.fspath(self.runner)})
        object.__setattr__(self, "runner", resolved)
        if (
            isinstance(self.timeout, bool)
            or not isinstance(self.timeout, (int, float))
            or not 0 < float(self.timeout) <= 300
        ):
            raise ValueError("sandbox timeout must be in (0, 300]")
        if type(self.output_limit) is not int or self.output_limit < 1024:
            raise ValueError("sandbox output_limit must be >= 1024")
        identity = _runner_identity(resolved, output_limit=self.output_limit)
        object.__setattr__(self, "lean_toolchain", identity.toolchain)
        object.__setattr__(self, "lean_version", identity.version)
        object.__setattr__(self, "lean_binary_sha256", identity.binary_sha256)

    @classmethod
    def from_environment(
        cls,
        *,
        environ: Mapping[str, str] | None = None,
        system: str | None = None,
    ) -> ExternalSandboxLeanEvaluator:
        env = os.environ if environ is None else environ
        timeout_raw = env.get("PI_LEAN_SANDBOX_TIMEOUT", "60")
        try:
            timeout = float(timeout_raw)
        except ValueError as exc:
            raise SandboxUnavailable("PI_LEAN_SANDBOX_TIMEOUT must be numeric") from exc
        return cls(
            runner=_configured_runner(environ=env, system=system),
            timeout=timeout,
        )

    @property
    def runner_sha256(self) -> str:
        return _sha256_file(self.runner)

    @property
    def compiler_identity(self) -> LeanCompilerIdentity:
        return LeanCompilerIdentity(
            toolchain=self.lean_toolchain,
            version=self.lean_version,
            binary_sha256=self.lean_binary_sha256,
        )

    def __call__(
        self,
        name: str,
        signature: str,
        proof: str,
        *,
        preamble: str = "",
    ) -> LeanVerdict:
        if not _LEAN_NAME_RE.fullmatch(name):
            raise UnsafeLeanPayload("Lean theorem name is not a simple identifier")
        if not all(isinstance(value, str) for value in (signature, proof, preamble)):
            raise TypeError("Lean statement components must be strings")
        _reject_obvious_command_escape(proof)
        request = {
            "protocol": SANDBOX_PROTOCOL,
            "name": name,
            "signature": signature,
            "proof": proof,
            "preamble": preamble,
            "timeout_seconds": float(self.timeout),
            **self.compiler_identity.as_record(),
        }
        encoded = json.dumps(
            request,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        before_hash = self.runner_sha256
        process = subprocess.Popen(  # noqa: S603 -- absolute, pre-hashed executable; no shell
            [str(self.runner)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=False,
            start_new_session=os.name == "posix",
            env={
                "PATH": os.environ.get("PATH", os.defpath),
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
            },
        )
        try:
            stdout, stderr = process.communicate(encoded, timeout=float(self.timeout) + 5.0)
        except subprocess.TimeoutExpired as exc:
            _kill_process_group(process)
            process.communicate()
            raise SandboxProtocolError(
                f"Lean sandbox runner timed out after {self.timeout:g}s"
            ) from exc
        if _sha256_file(self.runner) != before_hash:
            raise SandboxProtocolError("Lean sandbox runner changed during evaluation")
        if len(stdout) + len(stderr) > self.output_limit:
            raise SandboxProtocolError("Lean sandbox runner exceeded its output limit")
        if process.returncode != 0:
            detail = (stderr or stdout).strip()[-2000:]
            raise SandboxProtocolError(f"Lean sandbox runner exited {process.returncode}: {detail}")
        try:
            response: Any = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise SandboxProtocolError("Lean sandbox runner returned invalid JSON") from exc
        expected = {"protocol", "compiles", "proven", "sorry_tainted", "diagnostic"}
        if not isinstance(response, dict) or set(response) != expected:
            raise SandboxProtocolError("Lean sandbox response has an invalid field set")
        if response["protocol"] != SANDBOX_PROTOCOL:
            raise SandboxProtocolError("Lean sandbox response protocol mismatch")
        if not all(type(response[key]) is bool for key in ("compiles", "proven", "sorry_tainted")):
            raise SandboxProtocolError("Lean sandbox verdict fields must be booleans")
        if not isinstance(response["diagnostic"], str):
            raise SandboxProtocolError("Lean sandbox diagnostic must be a string")
        compiles = response["compiles"]
        proven = response["proven"]
        sorry_tainted = response["sorry_tainted"]
        if proven != (compiles and not sorry_tainted):
            raise SandboxProtocolError("Lean sandbox verdict invariants are inconsistent")
        return LeanVerdict(
            compiles=compiles,
            proven=proven,
            sorry_tainted=sorry_tainted,
            error_tail=response["diagnostic"][-700:],
        )


def lean_available() -> bool:
    """Legacy host-oracle availability; v2 harnesses must use sandbox_available."""
    return shutil.which("lean") is not None


def _run_lean(src: str, timeout: int) -> tuple[int, str]:
    with tempfile.NamedTemporaryFile("w", suffix=".lean", delete=False, encoding="utf-8") as f:
        f.write(src)
        path = f.name
    try:
        proc = subprocess.run(
            ["lean", path], capture_output=True, text=True, timeout=timeout, check=False
        )
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except Exception as exc:  # noqa: BLE001
        return 1, f"lean run failed: {exc}"
    finally:
        Path(path).unlink(missing_ok=True)


def evaluate(
    name: str, signature: str, proof: str, *, preamble: str = "", timeout: int = 60
) -> LeanVerdict:
    """Legacy host evaluator retained for historical callers.

    New efficacy harnesses must use :class:`ExternalSandboxLeanEvaluator`.
    """
    head = f"{preamble}\n" if preamble else ""
    src = f"{head}theorem {name} {signature} := {proof}\n#print axioms {name}\n"
    rc, out = _run_lean(src, timeout)
    has_error = rc != 0 or bool(_ERROR_RE.search(out))
    compiles = not has_error
    sorry_tainted = "sorryAx" in out
    return LeanVerdict(
        compiles=compiles,
        proven=compiles and not sorry_tainted,
        sorry_tainted=sorry_tainted,
        error_tail=out[-700:],
    )


__all__ = [
    "ExternalSandboxLeanEvaluator",
    "LeanCompilerIdentity",
    "LeanVerdict",
    "ORACLE_ISOLATION",
    "SANDBOX_IDENTITY_PROTOCOL",
    "SANDBOX_PROTOCOL",
    "SANDBOX_RUNNER_ENV",
    "SandboxProtocolError",
    "SandboxUnavailable",
    "UnsafeLeanPayload",
    "evaluate",
    "lean_available",
    "sandbox_available",
]
