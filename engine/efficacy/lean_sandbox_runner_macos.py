#!/usr/bin/env python3
"""Reference macOS Lean sandbox runner for the PI efficacy harness.

Protocol: one JSON request on stdin, one JSON response on stdout. This process
is trusted control-plane code; the generated Lean source is executed only under
``/usr/bin/sandbox-exec`` with an explicit file-content read allowlist plus
network, child-process, and outside-temporary-directory write restrictions.

The runner resolves the exact toolchain named by the repository's authoritative
``lean/lean-toolchain`` pin. It never asks elan for the mutable default
toolchain. ``--identity`` exposes the pin, full Lean version string, and
executable digest so the parent harness can freeze and bind every request to the
same compiler identity.
"""

from __future__ import annotations

import json
import os
import re
import resource
import selectors
import signal
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROTOCOL = "pi-lean-sandbox-runner/v2"
IDENTITY_PROTOCOL = "pi-lean-sandbox-identity/v1"
_ERROR_RE = re.compile(r"\berror:", re.IGNORECASE)
_VERSION_RE = re.compile(r"^Lean \(version ([^,]+),")
_TOOLCHAIN_RE = re.compile(r"^[A-Za-z0-9._/+:-]+$")
_MAX_REQUEST_BYTES = 256_000
_MAX_OUTPUT_CHARS = 16_000
_MAX_CHILD_OUTPUT_BYTES = 64_000
_REPO_ROOT = Path(__file__).resolve().parents[2]
_TOOLCHAIN_FILE = _REPO_ROOT / "lean" / "lean-toolchain"


@dataclass(frozen=True)
class LeanIdentity:
    toolchain: str
    version: str
    binary_sha256: str
    binary: Path
    prefix: Path


def _response(
    *,
    compiles: bool,
    proven: bool,
    sorry_tainted: bool,
    diagnostic: str,
) -> dict[str, Any]:
    return {
        "protocol": PROTOCOL,
        "compiles": compiles,
        "proven": proven,
        "sorry_tainted": sorry_tainted,
        "diagnostic": diagnostic[-_MAX_OUTPUT_CHARS:],
    }


def _read_request() -> dict[str, Any]:
    raw = sys.stdin.buffer.read(_MAX_REQUEST_BYTES + 1)
    if len(raw) > _MAX_REQUEST_BYTES:
        raise ValueError("sandbox request exceeds byte limit")
    request = json.loads(raw.decode("utf-8"))
    if not isinstance(request, dict):
        raise TypeError("sandbox request must be an object")
    expected = {
        "protocol",
        "name",
        "signature",
        "proof",
        "preamble",
        "timeout_seconds",
        "lean_toolchain",
        "lean_version",
        "lean_binary_sha256",
    }
    if set(request) != expected:
        raise ValueError("sandbox request has an invalid field set")
    if request["protocol"] != PROTOCOL:
        raise ValueError("unsupported sandbox protocol")
    for key in ("name", "signature", "proof", "preamble"):
        if not isinstance(request[key], str):
            raise TypeError(f"{key} must be a string")
    for key in ("lean_toolchain", "lean_version", "lean_binary_sha256"):
        if not isinstance(request[key], str) or not request[key]:
            raise TypeError(f"{key} must be a non-empty string")
    digest = request["lean_binary_sha256"]
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise ValueError("lean_binary_sha256 must be a lowercase SHA-256 digest")
    timeout = request["timeout_seconds"]
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not 0 < float(timeout) <= 300
    ):
        raise ValueError("timeout_seconds must be in (0, 300]")
    return request


def _sha256_file(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_toolchain_pin() -> str:
    try:
        raw = _TOOLCHAIN_FILE.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(
            f"authoritative Lean toolchain pin is unavailable: {_TOOLCHAIN_FILE}"
        ) from exc
    toolchain = raw.strip()
    if (
        not toolchain
        or len(toolchain) > 200
        or "\n" in toolchain
        or not _TOOLCHAIN_RE.fullmatch(toolchain)
    ):
        raise RuntimeError("authoritative Lean toolchain pin is malformed")
    return toolchain


def _elan_executable() -> Path:
    preferred = Path.home() / ".elan" / "bin" / "elan"
    raw = str(preferred) if preferred.is_file() else shutil.which("elan")
    if not raw:
        raise RuntimeError("elan is unavailable")
    elan = Path(raw).resolve(strict=True)
    if not elan.is_file() or not os.access(elan, os.X_OK):
        raise RuntimeError("elan is not executable")
    return elan


def _resolve_lean() -> LeanIdentity:
    toolchain = _read_toolchain_pin()
    elan = _elan_executable()
    try:
        prefix_text = subprocess.run(
            [str(elan), "run", toolchain, "lean", "--print-prefix"],
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(f"pinned Lean toolchain is unavailable: {toolchain}") from exc
    try:
        prefix = Path(prefix_text).resolve(strict=True)
        binary = (prefix / "bin" / "lean").resolve(strict=True)
    except OSError as exc:
        raise RuntimeError("pinned Lean prefix does not contain an executable") from exc
    if (
        not prefix.is_absolute()
        or not prefix.is_dir()
        or not binary.is_file()
        or not os.access(binary, os.X_OK)
        or prefix not in binary.parents
    ):
        raise RuntimeError("pinned Lean prefix does not contain a valid executable")
    try:
        direct_prefix = subprocess.run(
            [str(binary), "--print-prefix"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        ).stdout.strip()
        version = subprocess.run(
            [str(binary), "--version"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError("pinned Lean executable failed its identity probe") from exc
    try:
        if Path(direct_prefix).resolve(strict=True) != prefix:
            raise RuntimeError("pinned Lean executable reports a different prefix")
    except OSError as exc:
        raise RuntimeError("pinned Lean executable reports an invalid prefix") from exc
    version_match = _VERSION_RE.match(version)
    pinned_version = toolchain.rsplit(":v", 1)[-1] if ":v" in toolchain else ""
    if version_match is None or not pinned_version or version_match.group(1) != pinned_version:
        raise RuntimeError(
            f"pinned Lean version mismatch: toolchain={toolchain!r}, output={version!r}"
        )
    return LeanIdentity(
        toolchain=toolchain,
        version=version,
        binary_sha256=_sha256_file(binary),
        binary=binary,
        prefix=prefix,
    )


def _identity_response(identity: LeanIdentity) -> dict[str, str]:
    return {
        "protocol": IDENTITY_PROTOCOL,
        "lean_toolchain": identity.toolchain,
        "lean_version": identity.version,
        "lean_binary_sha256": identity.binary_sha256,
    }


def _assert_requested_identity(request: dict[str, Any], identity: LeanIdentity) -> None:
    expected = {
        "lean_toolchain": identity.toolchain,
        "lean_version": identity.version,
        "lean_binary_sha256": identity.binary_sha256,
    }
    mismatches = sorted(key for key, value in expected.items() if request[key] != value)
    if mismatches:
        raise RuntimeError(f"requested Lean identity mismatch: {', '.join(mismatches)}")


def _profile(
    *,
    identity: LeanIdentity,
    sandbox_dir: Path,
) -> str:
    quote = json.dumps
    allowed_subpaths = (sandbox_dir, identity.prefix)
    allowed_literals = (
        Path("/"),
        Path("/dev/null"),
        Path("/dev/random"),
        Path("/dev/urandom"),
    )
    outside_allowlist = " ".join(
        [
            *(f"(require-not (subpath {quote(str(path))}))" for path in allowed_subpaths),
            *(f"(require-not (literal {quote(str(path))}))" for path in allowed_literals),
        ]
    )
    lines = [
        "(version 1)",
        # Default is retained only for non-file platform services that Lean may
        # need. File-content access is separately denied outside and explicitly
        # allowed inside the minimum path allowlist below.
        "(allow default)",
        "(deny network*)",
        (f"(deny process-exec (require-not (literal {quote(str(identity.binary))})))"),
        "(deny process-fork)",
        (f"(deny file-write* (require-not (subpath {quote(str(sandbox_dir))})))"),
        f"(deny file-read-data (require-all {outside_allowlist}))",
    ]
    for allowed in allowed_subpaths:
        lines.append(f"(allow file-read-data (subpath {quote(str(allowed))}))")
    for allowed in allowed_literals:
        lines.append(f"(allow file-read-data (literal {quote(str(allowed))}))")
    lines.append("")
    return "\n".join(lines)


def _resource_limits(timeout_seconds: float) -> None:
    def lower_soft_limit(kind: int, requested: int) -> None:
        try:
            _soft, hard = resource.getrlimit(kind)
            target = requested if hard == resource.RLIM_INFINITY else min(requested, hard)
            resource.setrlimit(kind, (target, hard))
        except (OSError, ValueError):
            pass

    cpu = max(1, min(300, int(timeout_seconds) + 1))
    lower_soft_limit(resource.RLIMIT_CPU, cpu)
    lower_soft_limit(resource.RLIMIT_FSIZE, 16 * 1024 * 1024)
    lower_soft_limit(resource.RLIMIT_NOFILE, 128)
    if hasattr(resource, "RLIMIT_NPROC"):
        lower_soft_limit(resource.RLIMIT_NPROC, 64)
    if hasattr(resource, "RLIMIT_AS"):
        lower_soft_limit(resource.RLIMIT_AS, 4 * 1024**3)


def _kill_process_tree(process: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
        return
    except (ProcessLookupError, PermissionError):
        pass
    try:
        process.kill()
    except ProcessLookupError:
        pass


class _ByteCapture:
    """Keep the first and last bytes without growing with compiler output."""

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
    process: subprocess.Popen[bytes],
    *,
    timeout_seconds: float,
    output_limit: int,
) -> tuple[str, bool, bool]:
    """Drain Lean incrementally and kill it on timeout or output overflow."""
    capture = _ByteCapture(output_limit)
    selector = selectors.DefaultSelector()
    pipes = [pipe for pipe in (process.stdout, process.stderr) if pipe is not None]
    for pipe in pipes:
        os.set_blocking(pipe.fileno(), False)
        selector.register(pipe, selectors.EVENT_READ)
    deadline = time.monotonic() + timeout_seconds
    timed_out = False
    output_overflow = False
    try:
        while True:
            running = process.poll() is None
            remaining = deadline - time.monotonic()
            if running and remaining <= 0:
                timed_out = True
                _kill_process_tree(process)
                break
            wait = min(0.05, max(0.0, remaining)) if running else 0.0
            ready = selector.select(wait)
            if not ready and not running:
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
                    _kill_process_tree(process)
                    break
            if output_overflow:
                break
        if process.poll() is None:
            try:
                process.wait(timeout=0.2)
            except subprocess.TimeoutExpired:
                process.kill()
                try:
                    process.wait(timeout=0.2)
                except subprocess.TimeoutExpired:
                    pass
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


def _normalize_diagnostic(output: str, *sandbox_paths: Path | str) -> str:
    normalized = output.replace("\r\n", "\n")
    aliases = sorted(
        {os.fspath(path) for path in sandbox_paths if os.fspath(path)},
        key=len,
        reverse=True,
    )
    for alias in aliases:
        normalized = normalized.replace(alias, "<sandbox_dir>")
    return normalized


def _run(request: dict[str, Any]) -> dict[str, Any]:
    identity = _resolve_lean()
    _assert_requested_identity(request, identity)
    if _sha256_file(identity.binary) != identity.binary_sha256:
        raise RuntimeError("pinned Lean executable changed before sandbox execution")
    timeout = float(request["timeout_seconds"])
    head = f"{request['preamble']}\n" if request["preamble"] else ""
    source = (
        f"{head}theorem {request['name']} {request['signature']} := "
        f"{request['proof']}\n#print axioms {request['name']}\n"
    )
    with tempfile.TemporaryDirectory(prefix="pi-lean-sandbox-") as raw_dir:
        sandbox_dir = Path(raw_dir).resolve()
        source_path = sandbox_dir / "Main.lean"
        source_path.write_text(source, encoding="utf-8")
        env = {
            "PATH": os.environ.get("PATH", os.defpath),
            "HOME": str(sandbox_dir),
            "TMPDIR": str(sandbox_dir),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
        }
        process = subprocess.Popen(
            [
                "/usr/bin/sandbox-exec",
                "-p",
                _profile(
                    identity=identity,
                    sandbox_dir=sandbox_dir,
                ),
                str(identity.binary),
                str(source_path),
            ],
            cwd=sandbox_dir,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
            shell=False,
            preexec_fn=lambda: _resource_limits(timeout),
        )
        output, timed_out, output_overflow = _bounded_process_output(
            process,
            timeout_seconds=timeout,
            output_limit=_MAX_CHILD_OUTPUT_BYTES,
        )
        output = _normalize_diagnostic(output, raw_dir, sandbox_dir)
        if timed_out:
            output = (
                f"{output.rstrip()}\nLean sandbox timed out after {timeout:g}s"
            ).lstrip()
            if _sha256_file(identity.binary) != identity.binary_sha256:
                raise RuntimeError(
                    "pinned Lean executable changed during sandbox execution"
                )
            return _response(
                compiles=False,
                proven=False,
                sorry_tainted=False,
                diagnostic=output,
            )
        if output_overflow:
            output = (
                f"{output.rstrip()}\n"
                f"Lean sandbox output limit exceeded ({_MAX_CHILD_OUTPUT_BYTES} bytes)"
            ).lstrip()
            if _sha256_file(identity.binary) != identity.binary_sha256:
                raise RuntimeError(
                    "pinned Lean executable changed during sandbox execution"
                )
            return _response(
                compiles=False,
                proven=False,
                sorry_tainted=False,
                diagnostic=output,
            )
    if _sha256_file(identity.binary) != identity.binary_sha256:
        raise RuntimeError("pinned Lean executable changed during sandbox execution")
    has_error = process.returncode != 0 or bool(_ERROR_RE.search(output))
    compiles = not has_error
    sorry_tainted = "sorryAx" in output
    return _response(
        compiles=compiles,
        proven=compiles and not sorry_tainted,
        sorry_tainted=sorry_tainted,
        diagnostic=output,
    )


def main() -> int:
    try:
        if sys.argv[1:] == ["--identity"]:
            sys.stdout.write(
                json.dumps(_identity_response(_resolve_lean()), ensure_ascii=False, sort_keys=True)
            )
            sys.stdout.write("\n")
            return 0
        if sys.argv[1:]:
            raise ValueError("unsupported sandbox runner arguments")
        result = _run(_read_request())
    except Exception as exc:  # noqa: BLE001 -- protocol boundary must fail closed
        print(f"sandbox runner error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
