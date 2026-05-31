# Falsifier — bhgman tooling on a real public OSS (pallets/click)

> The honest "**capability vs discipline**" test the self-critique (2026-05-28)
> and the external A/B (2026-05-30) asked for: point the tooling at *external*
> code (not the project's own KG) and see whether it produces a real,
> externally-valid deliverable.

## What was run

`run.py` scans every class in [pallets/click](https://github.com/pallets/click)
(16k★) with the hades Extract-Superclass engine — stdlib-`ast` **structural**
method comparison (formatting-insensitive: it compares parsed ASTs, not text) —
and reports class pairs sharing a byte-for-byte-identical non-dunder method, then
generates a real format-preserving patch (libcst) for one.

```
python worked/04-falsifier-click/run.py    # clones click --depth 1 on first run
```

## What it found (real, on click@HEAD)

Scanned **84 classes**; **2 genuine Extract-Superclass candidates**:

| duplicated method | classes | already share base | verdict |
|---|---|---|---|
| `get_completion_args` (24 LOC, reads `COMP_WORDS`/`COMP_CWORD`) | `BashComplete` ~ `ZshComplete` | **`ShellComplete`** | real duplication → should live in `ShellComplete` |
| `format_message` | `NoSuchOption` ~ `NoSuchCommand` | **`UsageError`** | real duplication → should live in `UsageError` |

Both are **true positives**: the methods are AST-identical and the two classes
*already* extend a common base, so lifting is a clean, behavior-preserving
refactor. The tool also generated a real patch (`generated_patch.txt`) and
correctly noted the existing common base in each case ("lift it there").

## Verdict — discipline, not capability

This is a **real external deliverable** — the tooling found valid, actionable
refactorings in a major OSS, not self-referential KG work. That partially closes
the self-critique's "external impact unmeasured" gap: the engine *does* produce
value on code it has never seen.

**But it is discipline, not intelligence**, consistent with the 2026-05-30 A/B:

- A click maintainer, or any dev with `grep get_completion_args` + a glance,
  finds these too. The tool adds nothing super-human.
- What it *does* add is **exhaustiveness** (all C(84,2)=3486 class pairs checked),
  **structural precision** (AST equality catches semantic dupes a text-`grep`
  would miss across formatting differences, and ignores trivially-identical
  dunders), and **determinism / reproducibility** (same input → same findings,
  re-runnable in CI).

That is the project's honest thesis restated on external evidence: **bhgman_tool
is a governance / audit layer — reproducibility, exhaustiveness, precision — not
a capability multiplier.** The falsifier did *not* surface a deep logic bug,
because these tools are drift/structure auditors, not general bug-finders; that
boundary is the honest scope, not a gap.

## Honest caveats

- "Should be lifted" is a *judgment* the tool flags, not decides — some
  duplication is intentional. The covenant keeps it dry-run (PLANNED) by design.
- 2 findings in one mid-size library is a small sample; this demonstrates the
  tool produces real external artifacts, it does not quantify how *often* it
  finds something worth acting on.
