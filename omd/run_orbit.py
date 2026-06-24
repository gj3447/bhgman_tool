#!/usr/bin/env python3
"""run_orbit.py — OMD droplet (물방울) lifecycle driver for bhgman_tool.

This is a *documented* reference for how a single 입체운행물방울 (parallel-dev
droplet) moves a declared orbit through OMD's finite-state machine. It binds the
Coordinator to the REAL bhgman_tool repo so that, in a full setup,
`start`/`connect` would carve a real git worktree and merge it back. In THIS MVP
setup we DO NOT execute start/connect — see the big warning below.

Lifecycle (verified against /data/kjra/PROJECT/PI/omd/omd_server/core.py):

    declare  -> task PENDING                      (orbits.bhgman.sh did this)
    next     -> Coordinator.next_task(agent)      pick a deps-satisfied, write-set
                                                  -disjoint task, mark it READY
    claim    -> Coordinator.claim(agent, globs)   acquire the write-set lease;
                                                  returns HELD + a fence token,
                                                  or PENDING/DENIED if it overlaps
                                                  an active HELD orbit (SINGULON)
    start    -> Coordinator.start(task, agent)    READY->IN_ORBIT; with a repo
                                                  bound this RUNS git: it creates
                                                  branch omd/<task> in a worktree
    commit   -> Coordinator.commit(task, msg)     commit the droplet's worktree
    finish   -> Coordinator.finish(task)          IN_ORBIT->DONE
    connect  -> Coordinator.connect(task)         CLOUD CONNECT: fence-gated merge
                                                  of the droplet branch back into
                                                  the integration branch, then
                                                  release the orbit lease

==========================================================================
!! start() and connect() are NOT executed by this MVP setup. !!
   With repo='/data/kjra/PROJECT/PI/bhgman_tool' bound, start() calls
   git.add_worktree() (real worktree on disk) and connect() calls git.merge()
   (real merge into the integration branch == current branch == main).
   The task brief forbids mutating the main git tree, so this script only
   demonstrates the *lease* portion (declare/next/claim) by default and leaves
   start->commit->finish->connect as documented-but-guarded code.
==========================================================================

Run (lease-only demo, no git mutation):
    /data/kjra/PROJECT/PI/bhgman_tool/.venv/bin/python \
        /data/kjra/PROJECT/PI/bhgman_tool/omd/run_orbit.py
"""

from __future__ import annotations

import os

from omd_server import Coordinator

REPO = "/data/kjra/PROJECT/PI/bhgman_tool"
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "omd.bhgman.db")

# Set this True ONLY in a throwaway clone where a real worktree+merge is wanted.
# Leaving it False keeps the main git tree pristine (task hard rule).
EXECUTE_GIT_PHASES = False


def lifecycle_demo(agent: str = "droplet-demo", task: str | None = None) -> None:
    """Drive one droplet through the lease phases (and, if enabled, git phases).

    `task` must be one of the orbit task_ids declared by orbits.bhgman.sh; its
    `--writes` globs are the write-set this droplet will lease. If `task` is
    None, OMD picks the first deps-clear, write-set-disjoint orbit via next_task
    so the demo is self-contained regardless of what leases already exist.
    """
    import json

    # repo is bound so the code path is the REAL one; git is only *invoked* by
    # start()/connect(), which we gate behind EXECUTE_GIT_PHASES below.
    omd = Coordinator(DB, repo=REPO)

    # --- LEASE PHASES (always safe: pure SQLite state, no filesystem mutation) ---
    ready = omd.next_task(agent)  # deps-clear + disjoint -> READY (or None)
    print("next  ->", ready and ready["task_id"], ready and ready["state"])
    if task is None:
        # Take whatever OMD just offered; if the board is fully leased, fall back
        # to the declared orbit_docs so the call path is still exercised.
        task = ready["task_id"] if ready else "orbit_docs"

    # Claim the orbit's write-set. We read the declared globs straight from the
    # task row so the lease matches the declaration exactly.
    trow = omd.store.get_task(task)
    writes = json.loads(trow["writes"]) if trow else []
    grant = omd.claim(agent, writes, mode="write", task_id=task)
    print(f"claim -> {task}:", grant.get("state"), "fence=", grant.get("fence"),
          "conflicts=", grant.get("conflicts"))

    if not EXECUTE_GIT_PHASES:
        print("start/commit/finish/connect: SKIPPED (EXECUTE_GIT_PHASES=False; "
              "would create a real worktree+merge into main).")
        # Release the lease so the demo leaves no held orbit behind.
        if grant.get("state") == "HELD":
            omd.release(grant["orbit_id"], agent, grant["fence"])
            print("release-> ok (lease returned, no git touched)")
        return

    # --- GIT PHASES (guarded; only run in a throwaway clone) -------------------
    started = omd.start(task, agent)  # READY->IN_ORBIT + real worktree/branch
    print("start ->", started["state"], "branch=", started["branch"])
    omd.commit(task, f"OMD droplet work for {task}")
    omd.finish(task)                  # IN_ORBIT->DONE
    merged = omd.connect(task)        # CLOUD CONNECT: fence-gated merge to main
    print("connect->", merged)


if __name__ == "__main__":
    lifecycle_demo()
