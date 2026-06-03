# External impact audit — bhgman_tool / SYMPOSIUM (2026-06-04)

> Closes the last OPEN axis of the efficacy line (`VERDICT.md` §3 "External impact — UNMEASURED").
> Question: does any of this register on an **external, ungameable** counter, or is it entirely
> self-referential? Method: 6 dimensions, each measured with ungameable signals + the project's
> **preflight 3-falsifier** (circularity / no-signal / inversion), then **adversarially verified in
> both directions** (refute the impact AND steelman a missed channel). 13-agent fan-out, ~180 tool
> calls (gh CLI, curl, WebSearch, OpenAlex/Crossref/Zenodo, GitHub code-search). Every verdict held.
> # KG: efficacy-measurement-line-2026-06-01, project_bhgman_self_critique_2026_05_28

## Verdict

**realized external impact = `trace`. potential = `weak`.** As of today essentially **nothing has
crossed an ungameable outside boundary.** The `trace` is generous — it rests entirely on *one*
owner-account AI reproduction whose *content* is non-circular; a stricter (account-circularity) reading
is `none`. It was **not** rounded to `weak`: that would require at least one genuinely-external human or
one ungameable index registering the work, and none does.

This is exactly where a solo, self-referential research system is structurally weakest, and the
measurement confirms it without flinching.

## Per-dimension (all 6 verified, both directions)

| dimension | realized | potential | the ungameable killer-fact |
|---|---|---|---|
| GitHub adoption | none | trace | stars=2 + fork=1 are **all owner accounts** (gj3447 + gira-airobotics); only non-owner actor is `dependabot[bot]` (= anti-adoption). The 6567 clones are **own CI**: Pearson r≈0.96 with the repo's Actions runs, ~6.4 clones/run, clone:view ≈ **253:1** (ephemeral-runner-checkout signature). 8 workflows all `actions/checkout@v6`. |
| Distribution | none | weak | **not on PyPI / npm / Docker Hub / GHCR** (all 404). The README advertises `pip install bhgman_tool` — which **404s every variant** (a broken/aspirational promise). Only release asset = `hero.mp4` demo video (36 dl). |
| Academic | none | weak | 2 papers stuck at `SUBMISSION_READY` in a **PRIVATE** repo; an agent cannot submit (arXiv auth = owner-only). **OpenAlex / Crossref / Zenodo / arXiv all return 0** for author "Gyeongjun Ra / 라경준" and for the unique coinage "metahumotonic". |
| 3rd-party reproduction | **trace** | weak | the "independent" reproduction is **`gira-airobotics` (the owner's own company account) running an AI agent (Claude Code Opus 4.8) that has the project's own skills installed**. Content *is* substantively non-circular (ran on Lean **4.27 vs pinned 4.29.1**, found owner-unknown bugs — README install cmds fail verbatim + count drift — and the critique was preserved whole). Account-circular though = "external in name only." High-water mark, trace at best. |
| Live service | none | trace | metahumotonic.com is genuinely **live (HTTP 200)** with SEO/sitemap/ontology.ttl — but the Mongo backing store's `web_feedback` collection holds **7 docs, ALL owner curl-probes from LAN 192.168.0.23**. 0 inbound links, 0 Wayback snapshots, 0 analytics; `/api/stats` reports internal **KG size, not usage**; 13 candidate metrics endpoints all 404. |
| Web footprint | none | trace | ~12 web searches + **GitHub code-search = 0** genuine cross-repo references. No HN/Reddit/X/blog/forum mention, no inbound link, no non-owner citation. Every hit is a common-word / pop-culture collision. The owner's 9 followers are pre-existing dormant ties, not project-awareness. |

## The one big number is Goodhart noise (worth stating plainly)

`clones = 6567 / 687 "uniques"` over 14 days *looks* like adoption. It is the project's **own 7-workflow
CI fleet**: every push fires 8 GitHub Actions workflows, each does `actions/checkout@v6` (= a git clone
on a fresh ephemeral runner, each counted as a "unique IP"); `ci.yml` is a 3-version Python matrix. The
per-day clone count tracks the per-day Actions-run count at **Pearson r ≈ 0.96** (~6.4 clones/run, 1241
all-time runs), against only **26 human page-views / 3 uniques**. A 253:1 clone-to-view ratio with zero
external referrers is the canonical CI-checkout signature, not 687 developers. Reading it as adoption
would be precisely the enumeration-as-quality Goodhart move the project criticizes elsewhere.

## What would move it (all OWNER calls — agent-blocked)

1. **arXiv upload** of paper #1 (`337_forced_free_explosive`, math.LO+cs.LO) from the SUBMISSION_READY
   package. Highest leverage: a public DOI/abstract + moderation is the first genuinely ungameable
   external surface. Ceiling is real but low (self-admittedly an expository note, not a new theorem).
   *Agent-blocked: arXiv auth/endorsement.*
2. **PyPI publish** (`twine upload`; the `[resolver]/[gate]/[agents]/[all]` extras are already
   scaffolded) so the README's advertised `pip install bhgman_tool` stops 404-ing — converting a broken
   self-distribution promise into a real install-counter channel. *Agent-blocked: PyPI credentials.*
3. **Make SYMPOSIUM/papers public + add repo topics/homepage + one human-facing post (Show HN / blog).**
   Repos currently have EMPTY topics, EMPTY homepage, `hasDiscussions=false`, 0 web footprint — the live
   assets are *discoverable-but-undiscovered*. One discovery surface lets them actually be found.
4. **Invite ONE genuinely external human** (not gira-airobotics, not an agent) to run the one-line
   verifier. A single non-owner reproduction would be the first event to clear all three falsifiers.
5. **Instrument before promoting** (privacy-light counter e.g. plausible/umami + a real non-CI clone
   path) so that IF external traffic arrives it is measurable and not buried under the 253:1 CI noise.
   *(The only one an agent could prep; activation/promotion remain owner calls.)*

## Tie-back

This completes the efficacy picture. Cognitive uplift = ~0 (within-competence) / noise-floor (faithful
headroom). Operational substrate = the robust, real value. **External impact = trace/weak** — the system
is fully *discoverable-but-undiscovered*: live MIT repo + live site + arXiv-ready papers all exist, with
zero discovery surface and zero external pull. The bottleneck is not quality of artifact; it is that the
two acts creating external exposure (arXiv upload, PyPI publish) are owner-only and have not happened.
Nothing here is auto-actionable — it is a set of owner decisions, surfaced honestly.
