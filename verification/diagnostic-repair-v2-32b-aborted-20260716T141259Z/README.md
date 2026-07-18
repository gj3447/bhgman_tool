# Aborted diagnostic-repair v2 live attempt

This directory is incident evidence, not efficacy evidence.

- The attempt started from clean commit
  `8b6a17da9649f5d6c9057ec5277381a0b7ebadae` at
  `2026-07-16T14:12:59Z`.
- It stopped with exit code `1` before the first `run_summary`.
- The partial JSONL contains 145 records and five completed task summaries.
- The terminating condition was an uncaught `UnsafeLeanPayload` raised for a
  generated command-level Lean proof payload.
- The sandbox rejection itself was correct. The v2 harness incorrectly treated
  that expected candidate rejection as a terminal process failure.
- This run must never be resumed, combined with v3 JSONL, or used for P1-P5.

V3 re-freezes the same experiment after making generated unsafe payloads a
canonical failed observation across direct arms, PI arms, and analyzer replay.
Sandbox availability, protocol failure, trusted frozen metadata, and decoy setup
failures remain terminal.

`abort-manifest.json` binds every retained artifact and its SHA-256.
