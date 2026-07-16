# pyright: reportMissingImports=false
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from engine.efficacy import lean_oracle


def _fake_runner(tmp_path: Path) -> tuple[Path, Path]:
    capture = tmp_path / "request.json"
    runner = tmp_path / "fake-sandbox-runner"
    runner.write_text(
        f"""#!{sys.executable}
import json
import pathlib
import sys

if sys.argv[1:] == ["--identity"]:
    json.dump({{
        "protocol": {lean_oracle.SANDBOX_IDENTITY_PROTOCOL!r},
        "lean_toolchain": "leanprover/lean4:v4.27.0",
        "lean_version": "Lean (version 4.27.0, fake-platform, commit fake, Release)",
        "lean_binary_sha256": "f" * 64,
    }}, sys.stdout)
    raise SystemExit(0)
request = json.load(sys.stdin)
pathlib.Path({str(capture)!r}).write_text(json.dumps(request), encoding="utf-8")
json.dump({{
    "protocol": {lean_oracle.SANDBOX_PROTOCOL!r},
    "compiles": True,
    "proven": True,
    "sorry_tainted": False,
    "diagnostic": "sandbox-pass",
}}, sys.stdout)
""",
        encoding="utf-8",
    )
    runner.chmod(0o755)
    return runner.resolve(), capture


def test_missing_and_relative_sandbox_runner_fail_closed(tmp_path: Path) -> None:
    assert (
        lean_oracle.sandbox_available(
            environ={},
            system="Linux",
        )
        is False
    )
    with pytest.raises(lean_oracle.SandboxUnavailable, match="required"):
        lean_oracle.ExternalSandboxLeanEvaluator.from_environment(
            environ={},
            system="Linux",
        )
    relative = tmp_path.name
    with pytest.raises(lean_oracle.SandboxUnavailable, match="absolute"):
        lean_oracle.ExternalSandboxLeanEvaluator.from_environment(
            environ={lean_oracle.SANDBOX_RUNNER_ENV: relative},
            system="Linux",
        )


def test_external_runner_protocol_is_argv_only_and_hash_bound(tmp_path: Path) -> None:
    runner, capture = _fake_runner(tmp_path)
    evaluator = lean_oracle.ExternalSandboxLeanEvaluator(runner=runner, timeout=2)

    verdict = evaluator(
        "sandbox_ok",
        "(n : Nat) : n + 0 = n",
        "by rfl",
    )

    assert verdict.proven is True
    assert len(evaluator.runner_sha256) == 64
    assert evaluator.lean_toolchain == "leanprover/lean4:v4.27.0"
    assert evaluator.lean_version == ("Lean (version 4.27.0, fake-platform, commit fake, Release)")
    assert evaluator.lean_binary_sha256 == "f" * 64
    request = json.loads(capture.read_text(encoding="utf-8"))
    assert request == {
        "protocol": lean_oracle.SANDBOX_PROTOCOL,
        "name": "sandbox_ok",
        "signature": "(n : Nat) : n + 0 = n",
        "proof": "by rfl",
        "preamble": "",
        "timeout_seconds": 2.0,
        "lean_toolchain": evaluator.lean_toolchain,
        "lean_version": evaluator.lean_version,
        "lean_binary_sha256": evaluator.lean_binary_sha256,
    }


def test_obvious_eval_payload_is_rejected_before_runner_invocation(
    tmp_path: Path,
) -> None:
    runner, capture = _fake_runner(tmp_path)
    evaluator = lean_oracle.ExternalSandboxLeanEvaluator(runner=runner, timeout=2)

    with pytest.raises(lean_oracle.UnsafeLeanPayload, match="command-level"):
        evaluator(
            "sandbox_escape",
            ": True",
            'by trivial\n#eval IO.println "escaped"',
        )

    assert capture.exists() is False


@pytest.mark.skipif(
    platform.system() != "Darwin"
    or not Path("/usr/bin/sandbox-exec").is_file()
    or shutil.which("elan") is None,
    reason="reference runner requires macOS sandbox-exec and elan",
)
def test_reference_macos_runner_uses_pinned_toolchain_and_blocks_escape_probes(
    tmp_path: Path,
) -> None:
    ssh_config = Path.home() / ".ssh" / "config"
    repo_file = Path(lean_oracle.__file__).resolve()
    temp_secret = tmp_path / "outside-runner-sandbox-secret.txt"
    temp_secret.write_text("must not be readable by generated Lean", encoding="utf-8")
    marker = Path.home() / "pi_lean_sandbox_escape_test"
    marker.unlink(missing_ok=True)
    evaluator = lean_oracle.ExternalSandboxLeanEvaluator.from_environment(
        environ={},
        system="Darwin",
    )

    repo_root = Path(lean_oracle.__file__).resolve().parents[2]
    assert (
        evaluator.lean_toolchain
        == (repo_root / "lean" / "lean-toolchain").read_text(encoding="utf-8").strip()
    )
    assert evaluator.lean_version.startswith("Lean (version 4.27.0,")
    assert len(evaluator.lean_binary_sha256) == 64
    assert all(char in "0123456789abcdef" for char in evaluator.lean_binary_sha256)
    mismatched_request = {
        "protocol": lean_oracle.SANDBOX_PROTOCOL,
        "name": "identity_mismatch",
        "signature": ": True",
        "proof": "by trivial",
        "preamble": "",
        "timeout_seconds": 2.0,
        "lean_toolchain": evaluator.lean_toolchain,
        "lean_version": evaluator.lean_version,
        "lean_binary_sha256": "0" * 64,
    }
    mismatch = subprocess.run(
        [str(evaluator.runner)],
        input=json.dumps(mismatched_request),
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert mismatch.returncode == 2
    assert mismatch.stdout == ""
    assert "requested Lean identity mismatch" in mismatch.stderr

    normal = evaluator(
        "sandbox_normal",
        "(n : Nat) : n + 0 = n",
        "by rfl",
        preamble="import Lean",
    )
    stable_error_1 = evaluator(
        "sandbox_stable_diagnostic",
        ": True",
        "by exact 1",
        preamble="import Lean",
    )
    stable_error_2 = evaluator(
        "sandbox_stable_diagnostic",
        ": True",
        "by exact 1",
        preamble="import Lean",
    )

    def read_probe(name: str, path: Path) -> lean_oracle.LeanVerdict:
        return evaluator(
            name,
            ": True",
            (f'by\n  run_tac\n    let _ ← IO.FS.readFile "{path}"\n    pure ()\n  trivial'),
            preamble="import Lean",
        )

    probes = {
        "etc": read_probe("sandbox_etc_read", Path("/etc/hosts")),
        "repo": read_probe("sandbox_repo_read", repo_file),
        "temp": read_probe("sandbox_temp_read", temp_secret),
        "data_etc": read_probe(
            "sandbox_data_etc_read",
            Path("/System/Volumes/Data/private/etc/hosts"),
        ),
        "data_repo": read_probe(
            "sandbox_data_repo_read",
            Path(f"/System/Volumes/Data{repo_file}"),
        ),
    }
    missing_data_etc_probe = read_probe(
        "sandbox_data_etc_firmlink_read",
        Path("/System/Volumes/Data/etc/hosts"),
    )
    if ssh_config.is_file():
        probes["home"] = read_probe("sandbox_home_read", ssh_config)
        probes["data_home"] = read_probe(
            "sandbox_data_home_read",
            Path(f"/System/Volumes/Data{ssh_config}"),
        )
    write_attempt = evaluator(
        "sandbox_home_write",
        ": True",
        (f'by\n  run_tac\n    IO.FS.writeFile "{marker}" "escaped"\n  trivial'),
        preamble="import Lean",
    )
    spawn_attempt = evaluator(
        "sandbox_process_spawn",
        ": True",
        (
            "by\n"
            "  run_tac\n"
            '    let _ ← IO.Process.output { cmd := "/bin/echo", args := #["escaped"] }\n'
            "    pure ()\n"
            "  trivial"
        ),
        preamble="import Lean",
    )
    network_attempt = evaluator(
        "sandbox_network",
        ": True",
        (
            "by\n"
            "  run_tac\n"
            "    let socket ← Std.Internal.IO.Async.TCP.Socket.Client.mk\n"
            "    let addr : Std.Net.SocketAddress := .v4 {\n"
            "      addr := Std.Net.IPv4Addr.ofParts 127 0 0 1, port := 9 }\n"
            "    (socket.connect addr).block\n"
            "  trivial"
        ),
        preamble="import Lean\nimport Std.Internal.Async.TCP",
    )

    assert normal.proven is True
    assert stable_error_1.proven is False
    assert stable_error_1.error_tail == stable_error_2.error_tail
    assert "pi-lean-sandbox-" not in stable_error_1.error_tail
    assert missing_data_etc_probe.proven is False
    assert all(verdict.proven is False for verdict in probes.values())
    assert all(
        "operation not permitted" in verdict.error_tail.lower() for verdict in probes.values()
    )
    assert write_attempt.proven is False
    assert spawn_attempt.proven is False
    assert network_attempt.proven is False
    assert "operation not permitted" in write_attempt.error_tail.lower()
    assert "operation not permitted" in network_attempt.error_tail.lower()
    assert marker.exists() is False
    marker.unlink(missing_ok=True)


@pytest.mark.skipif(
    platform.system() != "Darwin"
    or not Path("/usr/bin/sandbox-exec").is_file()
    or shutil.which("elan") is None,
    reason="reference runner requires macOS sandbox-exec and elan",
)
def test_reference_macos_runner_bounds_lean_output_flood() -> None:
    evaluator = lean_oracle.ExternalSandboxLeanEvaluator.from_environment(
        environ={},
        system="Darwin",
    )

    verdict = evaluator(
        "sandbox_output_flood",
        ": True",
        (
            "by\n"
            "  run_tac\n"
            "    for _ in List.range 3000 do\n"
            '      IO.println "0123456789abcdef0123456789abcdef"\n'
            "  trivial"
        ),
        preamble="import Lean",
    )

    assert verdict.compiles is False
    assert verdict.proven is False
    assert "output limit exceeded" in verdict.error_tail
    assert len(verdict.error_tail) <= 700


def test_sandbox_runner_environment_does_not_require_secret_variables(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner, _capture = _fake_runner(tmp_path)
    monkeypatch.setenv("SHOULD_NOT_REACH_RUNNER", "secret")
    evaluator = lean_oracle.ExternalSandboxLeanEvaluator(runner=runner, timeout=2)
    assert evaluator("no_secret_env", ": True", "by trivial").proven is True
    assert os.environ["SHOULD_NOT_REACH_RUNNER"] == "secret"
