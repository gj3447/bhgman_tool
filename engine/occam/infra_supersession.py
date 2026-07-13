"""Occam infra-config supersession lens — ghost-reference detection.

The infra sibling of the KG-node / source-code supersession pass (`occam.py`): same
`SupersessionCandidate`-shaped, archive-only, escalate-when-uncertain covenant, but the identity
key is a *parsed infra reference* (not a file sha256) and the twin-oracle is a *supersession-fact
table + live inventory* (not a disk hash).

Catches the SYMPOSIUM cp-migration 2026-06 failure: after a control-plane move, live configs kept
referencing SUPERSEDED entities (dead IP 192.168.2.2:6443 in kubeadm-config/cluster-info/kube-proxy/
coturn/kubeconfig, dead node `k8s-cp`, dead relay 192.168.0.101:8443) → ghost references → cascading
failures each MISDIAGNOSED as a host freeze. One dead entity referenced by N configs = one root cause
faking N symptoms.

Design = PROM-16 `cycle-prom16-occam-infra-config-supersession-2026-07-13`
(THEORY/occam_infra_config_supersession/PROM_16_REPORT.md). Deterministic, no LLM. Load-bearing:
  - C2  fact-driven: supersession is ASSERTED by an explicit old→new fact, never guessed.
  - C1  parse→canonicalize→match: compare on canonical identity, never raw string.
  - C3  dual detectors: fact-map (outbound ref-integrity) + live-universe set-diff.
  - C4  reverse blast-radius: group by superseded entity → one finding per root cause.
  - C6  live-vs-historical gate FIRST: the same dead IP is a ghost in a live CM and a correct
        record in a backup/lesson/_archive — flag the former, PRESERVE the latter (Eilu-va-Eilu).
  - C7  archive-only: FLAG + propose a fix string; NEVER edit the live file, NEVER delete. KG write
        is status-flag + SUPERSEDED_BY edge only (reuses occam `_assert_archive_only`). Idempotent.
  - C5  static-first: an absent runtime symptom must never CLEAR a ghost.

# KG: impl-occam-infra-config-supersession-2026-07-13,
#     cycle-prom16-occam-infra-config-supersession-2026-07-13, occam-kam-canonical-2026-05-26
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from engine.occam.kg_adapter import _assert_archive_only  # reuse the covenant tripwire (single source)
from engine.occam.occam_models import Confidence  # HIGH | MEDIUM — reused verbatim


# ── kinds / verdicts ──────────────────────────────────────────────────────────

class RefKind(str, Enum):
    ENDPOINT = "endpoint"      # ip[:port]
    RELAY = "relay"            # host:port relay
    REGISTRY = "registry"      # container-registry host
    NODE_NAME = "node_name"    # k8s node name token
    NODE_LABEL = "node_label"  # key=value selector value
    IMAGE = "image"            # host/repo[:tag][@digest]


# Verdict strings mirror occam SupersessionCandidate.verdict.
SUPERSEDE, VERIFY, KEEP, PROTECTED_V, FLAG_ONLY = "SUPERSEDE", "VERIFY", "KEEP", "PROTECTED", "FLAG_ONLY"


class SourceClass(str, Enum):
    LIVE = "live"              # the copy the running control loop reads — a stale ref here is a ghost
    HISTORICAL = "historical"  # backup/snapshot/lesson/_archive — a stale ref here is a correct record
    AMBIGUOUS = "ambiguous"    # template/staging/dual-homed — escalate, never default-flag


# ── value objects ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class InfraRef:
    """A canonically-parsed infra reference — the equality key (the sha256-twin analogue)."""

    kind: RefKind
    raw: str
    canonical: str
    host: str | None = None  # ip / registry-host component (the migration-critical sub-part)


def make_ref(kind: RefKind, raw: str) -> InfraRef:
    """Parse + canonicalize (C1). MATCH happens on `.canonical`/`.host`, never on `raw`."""
    tok = raw.strip()
    if kind in (RefKind.ENDPOINT, RefKind.RELAY):
        low = tok.lower()
        host = low.split(":", 1)[0] if ":" in low else low
        return InfraRef(kind, raw, low, host)
    if kind == RefKind.REGISTRY:
        low = tok.lower()
        return InfraRef(kind, raw, low, low)
    if kind == RefKind.IMAGE:
        low = tok.lower()
        host = low.split("/", 1)[0] if "/" in low and ("." in low.split("/", 1)[0] or ":" in low.split("/", 1)[0]) else None
        return InfraRef(kind, raw, low, host)
    if kind == RefKind.NODE_LABEL:
        # "key = value" → "key=value"; the dead-node value is the salient token.
        norm = "=".join(p.strip() for p in tok.split("=", 1)) if "=" in tok else tok
        return InfraRef(kind, raw, norm)
    # NODE_NAME
    return InfraRef(kind, raw, tok)


@dataclass(frozen=True)
class InfraSupersessionFact:
    """One (superseded → current) fact + provenance — the migration old→new map (disk_truth analogue)."""

    superseded: InfraRef
    current: InfraRef | None      # None = removed with no replacement → FLAG_ONLY (machloket)
    axis: str
    provenance: str               # 'migration_decommission_event:cp-migration-2026-06' | 'kg:SUPERSEDED_BY' | 'user_verdict'
    recorded_at: str = ""
    fact_source_last_validated: str = ""  # C9 self-staleness check


@dataclass(frozen=True)
class SourceRef:
    file_path: str
    line: int = 0
    field_path: str = ""          # e.g. 'data.controlPlaneEndpoint'
    source_kind: str = ""         # configmap|kubeconfig|systemd|launchd|env|manifest|generic
    reload_atomic: bool = False   # metallb pool / kubeadm CM — whole-config-reject-on-restart


@dataclass(frozen=True)
class LiveInventory:
    """Per-axis frozensets of canonical LIVE entities — the second, weaker oracle (Detector B)."""

    endpoints: frozenset[str] = frozenset()   # live ip / ip:port
    node_names: frozenset[str] = frozenset()
    node_labels: frozenset[str] = frozenset()
    registries: frozenset[str] = frozenset()


@dataclass(frozen=True)
class InfraSupersessionCandidate:
    """Mirrors occam SupersessionCandidate (NodeRecord→InfraRef) + infra fields. Archive-only."""

    stale: InfraRef
    current: InfraRef | None
    source_ref: SourceRef
    axis: str
    reason: str
    confidence: Confidence
    evidence: str                 # fact_map | set_diff | rename_record
    fact_provenance: str
    action: str = "SUPERSEDED_BY"
    blast_radius: int = 1
    reload_atomic: bool = False
    proposed_fix: str | None = None  # replacement value a human/PR applies (None ⇒ current is None)
    score: float | None = None
    verdict: str | None = None


@dataclass(frozen=True)
class InfraGhostReport:
    """Mirrors OccamReport — NO delete field (covenant)."""

    candidates: tuple[InfraSupersessionCandidate, ...] = ()
    scanned_sources: int = 0
    live_sources: int = 0
    historical_sources_skipped: int = 0
    blast_radius_groups: tuple[tuple[str, tuple[InfraSupersessionCandidate, ...]], ...] = ()
    orphans: tuple[InfraRef, ...] = ()                 # set-diff, unmapped → longinus escalation (machloket)
    fact_table_staleness_warnings: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    @property
    def ghost_count(self) -> int:
        return len(self.candidates)


# ── C6: live-vs-historical classification (gate FIRST) ────────────────────────

_HISTORICAL_MARKERS = (
    "/_archive/", "/archive/", "/backups/", "/backup/", "/snapshots/", "/snapshot/", "/history/",
    "/receipts/", "/_pidna_receipts/", "/compaction_archive/", "/lesson", "/replay/", "/.git/",
    ".bak", ".stale", ".disabled", ".old", "-do-not-use",
)


def classify_source(source_ref: SourceRef, *, tombstoned: bool = False,
                    ambiguous: bool = False, authoritative: bool | None = None) -> SourceClass:
    """3-gate classification. tombstone / path-provenance / authoritative-copy. Ambiguous → escalate."""
    if tombstoned:
        return SourceClass.HISTORICAL          # gate 3: already carries a supersession marker
    if ambiguous or authoritative is False:
        return SourceClass.AMBIGUOUS if ambiguous else SourceClass.HISTORICAL
    low = source_ref.file_path.lower()
    if any(m in low for m in _HISTORICAL_MARKERS):
        return SourceClass.HISTORICAL          # gate 1: path/provenance
    # a `_`-prefixed path segment = ephemeral / Longinus-exempt (SYMPOSIUM convention)
    if any(seg.startswith("_") for seg in low.split("/") if seg):
        return SourceClass.HISTORICAL
    return SourceClass.LIVE


# ── detection ─────────────────────────────────────────────────────────────────

_IPISH = re.compile(r"^[0-9.]+$")


def _salient_tokens(ref: InfraRef) -> list[str]:
    """Tokens whose presence in a live source proves a reference to this entity."""
    toks: list[str] = []
    for t in (ref.canonical, ref.host, ref.raw.strip()):
        if t and t not in toks:
            toks.append(t)
    if ref.kind == RefKind.NODE_LABEL and "=" in ref.canonical:  # the value is what points at the dead node
        val = ref.canonical.split("=", 1)[1]
        if val and val not in toks:
            toks.append(val)
    return toks


def _token_re(tok: str) -> re.Pattern:
    """Boundary-safe matcher: '192.168.2.2' must NOT match inside '192.168.2.20'."""
    esc = re.escape(tok)
    if _IPISH.match(tok):
        return re.compile(rf"(?<![\d.]){esc}(?![\d.])")
    return re.compile(rf"(?<![\w.:-]){esc}(?![\w.:-])")


# regex for Detector B endpoint extraction (bare ip or ip:port literals).
_ENDPOINT_LITERAL = re.compile(r"(?<![\d.])(\d{1,3}(?:\.\d{1,3}){3})(?::(\d{1,5}))?(?![\d.])")

# C8: never-flag allowlist (system-owned, not migration ghosts).
DEFAULT_ALLOWLIST: frozenset[str] = frozenset({
    "127.0.0.1", "0.0.0.0", "10.96.0.1", "kube-root-ca.crt", "kubernetes",
})


def _scan_fact_in_source(text: str, source_ref: SourceRef, fact: InfraSupersessionFact,
                         *, allowlist: frozenset[str]) -> list[InfraSupersessionCandidate]:
    """Detector A — literal token scan for the superseded entity (the 'recursive grep old-IP' core)."""
    if fact.superseded.canonical in allowlist or (fact.superseded.host or "") in allowlist:
        return []
    tokens = _salient_tokens(fact.superseded)
    patterns = [(t, _token_re(t)) for t in tokens]
    lines = text.splitlines() or [text]
    out: list[InfraSupersessionCandidate] = []
    seen_lines: set[int] = set()
    for i, line in enumerate(lines, 1):
        if i in seen_lines:
            continue
        if any(p.search(line) for _, p in patterns):
            seen_lines.add(i)
            has_fix = fact.current is not None
            out.append(InfraSupersessionCandidate(
                stale=fact.superseded,
                current=fact.current,
                source_ref=SourceRef(source_ref.file_path, i, source_ref.field_path,
                                     source_ref.source_kind, source_ref.reload_atomic),
                axis=fact.axis,
                reason=(f"live config references superseded {fact.axis} "
                        f"{fact.superseded.canonical!r}"
                        + (f" → replace with {fact.current.canonical!r}" if has_fix
                           else " (removed, no replacement)")),
                confidence=Confidence.HIGH,   # exact fact-map hit in a LIVE source
                evidence="fact_map",
                fact_provenance=fact.provenance,
                blast_radius=1,
                reload_atomic=source_ref.reload_atomic,
                proposed_fix=fact.current.canonical if has_fix else None,
                verdict=SUPERSEDE if has_fix else FLAG_ONLY,
            ))
    return out


def _detect_setdiff(text: str, source_ref: SourceRef, facts: list[InfraSupersessionFact],
                    live: LiveInventory, *, allowlist: frozenset[str]) -> list[InfraRef]:
    """Detector B — endpoint literals absent from BOTH the fact map and the live inventory = orphans."""
    mapped = {t for f in facts for t in _salient_tokens(f.superseded)}
    orphans: list[InfraRef] = []
    seen: set[str] = set()
    for m in _ENDPOINT_LITERAL.finditer(text):
        ip, port = m.group(1), m.group(2)
        canonical = f"{ip}:{port}" if port else ip
        if canonical in seen:
            continue
        seen.add(canonical)
        if ip in allowlist or canonical in allowlist:
            continue
        if ip in mapped or canonical in mapped:
            continue                                   # already a known fact → Detector A owns it
        if ip in live.endpoints or canonical in live.endpoints:
            continue                                   # live → fine
        orphans.append(make_ref(RefKind.ENDPOINT, canonical))
    return orphans


def scan(sources: list[tuple[str, SourceRef]], facts: list[InfraSupersessionFact], *,
         live_inventory: LiveInventory | None = None,
         allowlist: frozenset[str] = DEFAULT_ALLOWLIST,
         source_flags: dict[str, dict] | None = None) -> InfraGhostReport:
    """Scan config sources for ghost references. `sources` = [(text, SourceRef)].

    `source_flags[file_path]` may carry {tombstoned, ambiguous, authoritative} for C6 gates.
    Never reads/edits files; never touches the network — pure over the supplied text + facts.
    """
    flags = source_flags or {}
    candidates: list[InfraSupersessionCandidate] = []
    orphans: list[InfraRef] = []
    live_n = hist_n = 0
    for text, sref in sources:
        cls = classify_source(sref, **{k: flags.get(sref.file_path, {}).get(k)
                                       for k in ("tombstoned", "ambiguous", "authoritative")
                                       if flags.get(sref.file_path, {}).get(k) is not None})
        if cls is SourceClass.HISTORICAL:
            hist_n += 1
            continue                                   # C6: preserve historical records, never flag
        live_n += 1
        for fact in facts:
            candidates.extend(_scan_fact_in_source(text, sref, fact, allowlist=allowlist))
        if live_inventory is not None:
            orphans.extend(_detect_setdiff(text, sref, facts, live_inventory, allowlist=allowlist))
        if cls is SourceClass.AMBIGUOUS:
            # flag every candidate from an ambiguous source down to VERIFY (escalate, don't auto-supersede)
            candidates = [
                (c if c.source_ref.file_path != sref.file_path
                 else InfraSupersessionCandidate(**{**c.__dict__, "confidence": Confidence.MEDIUM,
                                                    "verdict": VERIFY, "evidence": "fact_map_ambiguous_source"}))
                for c in candidates
            ]

    # C4: reverse blast-radius grouping — one dead entity across N sites = one root cause.
    groups: dict[str, list[InfraSupersessionCandidate]] = {}
    for c in candidates:
        groups.setdefault(c.stale.canonical, []).append(c)
    regraded: list[InfraSupersessionCandidate] = []
    grouped_out: list[tuple[str, tuple[InfraSupersessionCandidate, ...]]] = []
    for key, group in groups.items():
        n = len(group)
        fixed = tuple(InfraSupersessionCandidate(**{**c.__dict__, "blast_radius": n}) for c in group)
        regraded.extend(fixed)
        grouped_out.append((key, fixed))

    # dedup orphans by canonical
    uniq_orphans, seen = [], set()
    for o in orphans:
        if o.canonical not in seen:
            seen.add(o.canonical)
            uniq_orphans.append(o)

    warnings = _fact_table_staleness(facts)
    return InfraGhostReport(
        candidates=tuple(regraded),
        scanned_sources=len(sources),
        live_sources=live_n,
        historical_sources_skipped=hist_n,
        blast_radius_groups=tuple(grouped_out),
        orphans=tuple(uniq_orphans),
        fact_table_staleness_warnings=tuple(warnings),
        notes=(f"{len(regraded)} ghost refs across {len(grouped_out)} superseded entities; "
               f"{hist_n} historical sources preserved.",),
    )


def _fact_table_staleness(facts: list[InfraSupersessionFact], *, floor: str = "") -> list[str]:
    """C9 — the supersession map is itself an entity that can go stale; flag facts never re-validated."""
    return [f"fact for {f.superseded.canonical!r} has no fact_source_last_validated (C9 self-check)"
            for f in facts if not f.fact_source_last_validated]


# ── covenant: archive-only KG write + escalation routing ──────────────────────

def is_confident_supersede(c: InfraSupersessionCandidate) -> bool:
    """occam is_confident_supersede analogue: auto-archive ONLY a HIGH SUPERSEDE with a known current."""
    return (c.verdict == SUPERSEDE and c.confidence is Confidence.HIGH
            and c.current is not None and c.evidence in ("fact_map", "rename_record"))


def build_supersede_cypher(c: InfraSupersessionCandidate) -> tuple[str, dict]:
    """Archive-only: MERGE stale/current InfraRef nodes + SUPERSEDED_BY edge + status flag.

    NO delete/detach/remove — asserted by the reused occam covenant tripwire. The live config FILE is
    never touched; `proposed_fix` is emitted for a human/PR to apply (reversible: reset the status)."""
    cypher = (
        "MERGE (stale:InfraRef {canonical:$stale}) "
        "SET stale.kind=$kind, stale.axis=$axis, stale.status='SUPERSEDED', "
        "stale.source_path=$path, stale.field_path=$field "
        "WITH stale "
        "FOREACH (_ IN CASE WHEN $current IS NULL THEN [] ELSE [1] END | "
        "  MERGE (cur:InfraRef {canonical:$current}) SET cur.kind=$kind, cur.axis=$axis "
        "  MERGE (stale)-[r:SUPERSEDED_BY]->(cur) SET r.provenance=$prov, r.confidence=$conf)"
    )
    _assert_archive_only(cypher)  # tripwire: raises if the template ever grows a destructive token
    return cypher, {
        "stale": c.stale.canonical, "current": (c.current.canonical if c.current else None),
        "kind": c.stale.kind.value, "axis": c.axis, "path": c.source_ref.file_path,
        "field": c.source_ref.field_path, "prov": c.fact_provenance, "conf": c.confidence.value,
    }


def build_infra_escalation_plan(report: InfraGhostReport) -> dict[str, list[str]]:
    """Route uncertainty (occam build_escalation_plan analogue).

    HIGH SUPERSEDE + known current → no escalation (confirmed, safe). Uncertain (VERIFY / FLAG_ONLY /
    ambiguous-source) → naesengmoon. Endpoint-shaped-but-unmapped orphan → longinus drift audit.
    """
    naesengmoon = [f"{c.axis}:{c.stale.canonical} @ {c.source_ref.file_path}:{c.source_ref.line}"
                   for c in report.candidates if not is_confident_supersede(c)]
    longinus = [f"unmapped endpoint {o.canonical}" for o in report.orphans]
    return {"naesengmoon": naesengmoon, "longinus": longinus}


__all__ = [
    "RefKind", "SourceClass", "InfraRef", "make_ref", "InfraSupersessionFact", "SourceRef",
    "LiveInventory", "InfraSupersessionCandidate", "InfraGhostReport", "classify_source", "scan",
    "is_confident_supersede", "build_supersede_cypher", "build_infra_escalation_plan",
    "DEFAULT_ALLOWLIST", "SUPERSEDE", "VERIFY", "FLAG_ONLY", "PROTECTED_V",
]
