# OMD (입체운행물방울) orbit partition for `bhgman_tool`

This directory applies the **OMD** parallel-dev coordinator (입체운행물방울 군단장,
under SINGULON / 특이점 core) to `bhgman_tool`. It declares a **pairwise-disjoint
write-set partition** — a set of "orbits" (궤도) — so that many development
droplets (물방울) can run in parallel with a **structurally guaranteed
merge-conflict count of zero**.

The guarantee is OMD's **SINGULON invariant**: a droplet only ever gets a lease
(HELD + a monotonic *fence* token) on a write-set that is *입체* (disjoint) from
every other active lease. Two droplets can therefore never hold overlapping
write-sets at once, so their branches can never produce a merge conflict.

> No git tree is mutated by this setup. `start`/`connect` (worktree + merge) are
> documented but **not executed** here — see `run_orbit.py`.

## Files

| File | Purpose |
|------|---------|
| `orbits.bhgman.sh` | Idempotent declaration of the 13 orbits into `omd.bhgman.db`; ends with `omd status`. |
| `run_orbit.py` | Documented droplet-lifecycle driver (`next -> claim -> start -> commit -> finish -> connect`); git phases are guarded off. |
| `omd.bhgman.db` | OMD's SQLite state (gitignored, plus `-wal`/`-shm` sidecars). |

## The partition (13 orbits)

Each orbit is a `omd declare <task> --writes <glob...>`. Globs are subtree
directory globs (`<dir>/**`) over **real** `bhgman_tool` directories. **No glob
nests inside another** — verified below.

**5 orbits over `engine/` subsystems** (grouped by cohesion):

| orbit | write-set |
|-------|-----------|
| `orbit_longinus` | `engine/longinus_drift/**`, `engine/longinus_drift_audit/**` |
| `orbit_fabric`   | `engine/harness/**`, `engine/legion/**`, `engine/agents/**` |
| `orbit_kg`       | `engine/code_to_kg/**`, `engine/kg_local/**`, `engine/memory/**`, `engine/resolver/**` |
| `orbit_reason`   | `engine/occam/**`, `engine/prometheus/**`, `engine/eureka/**` |
| `orbit_iface`    | `engine/cli/**`, `engine/mcp_server/**`, `engine/gate/**` |

**8 top-level orbits** (one real dir subtree each):
`theory/**`, `lean/**`, `verification/**`, `worked/**`, `skills/**`,
`symposium-skills/**`, `docs/**`, `scripts/**`.

### Rationale

- **Cohesion → fewer orbits, less coordination.** Tightly-coupled `engine/`
  subsystems are grouped so a single droplet can refactor a whole concern
  (e.g. the KG plumbing `code_to_kg`+`kg_local`+`memory`+`resolver`) without
  fighting itself for leases.
- **`longinus_drift` vs `longinus_drift_audit`.** These are *sibling* dirs whose
  names share a prefix. The subtree globs `engine/longinus_drift/**` and
  `engine/longinus_drift_audit/**` are still disjoint because OMD compares path
  **segments**: the segment `longinus_drift` and the segment
  `longinus_drift_audit` are distinct literals, so they never intersect. (They
  live in the *same* orbit anyway, so this is just a soundness note.)
- **Soundness over parallelism.** OMD's `disjoint` engine never reports a
  false-negative (it errs toward "overlap" for `[...]` char-classes). Plain
  `**` subtree globs give an exact, conflict-free partition.

## Disjointness verification

Prove that all 13 write-sets are pairwise disjoint, straight from the DB, using
OMD's own `omd_server.disjoint.sets_overlap`:

```bash
/data/kjra/PROJECT/PI/bhgman_tool/.venv/bin/python - <<'PY'
import json, itertools
from omd_server import Coordinator
from omd_server.disjoint import sets_overlap

omd = Coordinator("/data/kjra/PROJECT/PI/bhgman_tool/omd/omd.bhgman.db")
sets = {t["task_id"]: json.loads(omd.store.get_task(t["task_id"])["writes"])
        for t in omd.store.snapshot()["tasks"]}
assert len(sets) == 13
bad = [(a, b) for (a, s1), (b, s2) in itertools.combinations(sets.items(), 2)
       if sets_overlap(s1, s2)]
assert not bad, f"NOT DISJOINT: {bad}"
print(f"13 orbits, {13*12//2} distinct pairs, overlaps: {bad or 'NONE'}  -> 입체 OK")
PY
```

Expected: `13 orbits, 78 distinct pairs, overlaps: NONE  -> 입체 OK`.

## Demonstrating the SINGULON lease (no git)

```bash
DB=/data/kjra/PROJECT/PI/bhgman_tool/omd/omd.bhgman.db
OMD=/data/kjra/PROJECT/PI/bhgman_tool/.venv/bin/omd

$OMD --db "$DB" next droplet-A                      # offer a task
# A leases the longinus orbit  -> HELD + fence
$OMD --db "$DB" claim droplet-A \
  engine/longinus_drift/** engine/longinus_drift_audit/** \
  --mode write --task orbit_longinus
# B asks for a FILE inside A's leased subtree -> PENDING (denied: SINGULON)
$OMD --db "$DB" claim droplet-B \
  engine/longinus_drift_audit/sha256_baseline.py --mode write
# B asks for a DISJOINT orbit -> HELD (granted concurrently with A)
$OMD --db "$DB" claim droplet-B docs/** --mode write --task orbit_docs
```

The middle claim returning `PENDING` (with `conflicts` pointing at A's orbit) is
the SINGULON invariant **correctly rejecting a non-disjoint write-set**; the
last claim returning `HELD` shows a disjoint write-set is granted in parallel.

## Shared / serial zone

A few paths have **no orbit** and must be edited **serially** (one droplet at a
time, on the integration branch — never in two parallel droplets):

- **Repo-root files**: `pyproject.toml`, `conftest.py`, `README*.md`,
  `.gitignore`, `uv.lock`, etc. (project-wide; everyone touches them).
- **`engine/` root engine modules**: `engine/commander_engine.py`,
  `engine/longinus_engine.py`, `engine/occam_engine.py` — these are NOT under
  any subsystem dir, so they fall outside every orbit glob on purpose.
- Any `engine/` subdir **not** listed above (e.g. `efficacy/`, `hades/`,
  `embedding/`, `jaebaeman/`, `naesengmoon/`, `provexport/`, `tpa/`) is
  likewise unpartitioned in this MVP and is shared/serial until an orbit is
  declared for it.

Because these are excluded from every write-set, OMD will never hand out a lease
that touches them — by construction they stay a single-writer (serial) zone, and
the 13 orbits above remain a clean disjoint partition of the parallelizable
surface.
