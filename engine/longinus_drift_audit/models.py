"""Pydantic v2 schemas — ReferenceSite (Frege Sinn/Bedeutung), DriftRecord, AuditReport.

롱기누스 SKILL.md v3.2 1:1.
"""

from __future__ import annotations

import datetime as dt
import re
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class DriftType(str, Enum):
    # KG: ATOM_Skill_longinus
    MISSING = "Missing"  # PutGet violation: 코드 존재 ∧ KG ref 부재
    ORPHAN = "Orphan"  # GetPut violation: KG ref 존재 ∧ 코드 부재
    SIG_MISMATCH = "SigMismatch"  # PutGet violation: ref ↔ 시그니처 불일치
    PATTERN_DIV = "PatternDiv"  # PutPut violation: 동일 대상 ↔ 상충 ref
    LABEL_ROT = "LabelRot"  # PutPut violation: 라벨/이름 변경 미반영
    DISPATCH_DRIFT = "DispatchDrift"  # cardinality: dispatch intent_N ≠ actual_N (jaebaeman V5)


class ReferenceLayer(str, Enum):
    # KG: ATOM_Skill_longinus
    L1_ADDRESS = "L1_AddressIndirection"
    L2_LIFETIME = "L2_Lifetime"
    L3_TYPE = "L3_TypePermission"
    L4_SEMIOTIC = "L4_SemioticBinding"  # Frege Sinn↔Bedeutung
    L5_DISTRIBUTED = "L5_DistributedIdentity"
    L6_COMPRESSION = "L6_InformationCompression"
    L7_AESTHETIC = "L7_AestheticIntentional"


class Confidence(str, Enum):
    # KG: ATOM_Skill_longinus
    """3-tier confidence enum absorbed from graphify ARCHITECTURE.md (2026-05-13).

    KG: longinus-confidence-schema-3tier-2026-05-13 (:ConfidenceSchema:Canonical).
    Lean: MIND/lean_formalization/Longinus_ConfidenceSchema_GraphifyAbsorbed.lean (7 theorem PASS).
    """

    EXTRACTED = "EXTRACTED"  # explicitly stated in source (import / direct call / type)
    INFERRED = "INFERRED"  # reasonable deduction (call-graph 2-pass / co-occurrence)
    AMBIGUOUS = "AMBIGUOUS"  # uncertain, flagged for human review → :PRELIMINARY
    UNKNOWN = "UNKNOWN"  # P0 2026-07-21 hydration sentinel: confidence was never
    #   persisted to the KG (legacy node / pre-fix write). NOT one of the three
    #   scan-time tiers — deliberately excluded from the T1/T3/T6 Lean triple.
    #   Its sole guarantee: a KG round-trip of a site with no stored confidence
    #   yields UNKNOWN, never a silent promotion to EXTRACTED (design §8/§10 P0,
    #   HSWM/DESIGN_HARNESS_DOC_HSWM_LENS_DUALITY_2026-07-21.md).


def requires_human_verdict(c: Confidence) -> bool:
    # KG: ATOM_Skill_longinus
    """T1 Lean mirror: AMBIGUOUS is the unique human-gate tier."""
    return c == Confidence.AMBIGUOUS


def trust_level(c: Confidence) -> int:
    # KG: ATOM_Skill_longinus
    """T3 Lean mirror: EXTRACTED (2) > INFERRED (1) > AMBIGUOUS (0).

    UNKNOWN (P0 hydration sentinel, 2026-07-21) sits at the trust floor (0) — it is
    NOT part of the T3 strict-order triple; it only guarantees trust_level < EXTRACTED
    so a non-persisted confidence is never treated as trusted. Mapped explicitly so
    trust_level(UNKNOWN) never KeyErrors on a KG-hydrated site (design §10 regression
    guard: a hydration throw would be swallowed by the read-path bare-except).
    """
    return {
        Confidence.EXTRACTED: 2,
        Confidence.INFERRED: 1,
        Confidence.AMBIGUOUS: 0,
        Confidence.UNKNOWN: 0,
    }[c]


def any_ambiguous(sites: "list[ReferenceSite]") -> bool:
    # KG: ATOM_Skill_longinus
    """T6 Lean mirror: AMBIGUOUS contagion in aggregates.
    If any site is AMBIGUOUS, the aggregate requires :PRELIMINARY label."""
    return any(s.confidence == Confidence.AMBIGUOUS for s in sites)


# ─── Branded source identifiers ──────────────────────────────────────────

_SOURCE_ID_PATTERN = re.compile(
    r"^[A-Z][a-zA-Z0-9]*\.[a-zA-Z_][a-zA-Z0-9_]*$|^[a-z][a-z0-9-]+-[a-z0-9-]+$"
)
"""Two flavours:
   - PascalCase.symbol (e.g. `Prometheus.cycle_runner` or KG `lesson-foo-bar-2026`).
   The KG dash-pattern is also accepted (lesson-/finding-/seed- prefixes).
"""
_SOURCE_PATH_PATTERN = re.compile(r"^[a-zA-Z0-9/_.\-]+:[0-9]+(-[0-9]+)?$")
"""file:line or file:line-end (ASCII)."""
_DIRECTORY_OR_PATH_PATTERN = re.compile(r"^[^\s:]+$")
"""Directory- or filename-shape sourcePath (no colon, no whitespace).

Permits unicode (e.g. Korean `재배맨/`). Used for:
- L7_FullStack_DirCluster sites that bind a whole directory (sha256 → DIRECTORY_SKIP).
- L1-Document / L2-AxisFinding sites whose fs_path is a `.md` file without line range.
Added 2026-05-19 (lesson-bhgman-tool-sha256-baseline-already-covered-2026-05-19).
"""


class GuaranteeLevel(str, Enum):
    # KG: ATOM_Skill_longinus
    """v3.4 (2026-05-24 user RATIFY) — hermeticity spectrum tagging.

    Binary hermetic flag is insufficient — toolchain leaks, --remote_local_fallback,
    /proc, locale, timestamps need explicit spectrum tagging. PROM 16 Blaze C6
    consensus (3 cell independent flag).

    KG: rfc-longinus-v3.4-guarantee-level-2026-05-21 (CANONICAL).
    """

    PURE = "pure"  # Nix-derivation: declared inputs only, no ambient env, no network, content-addressed
    SANDBOXED = "sandboxed"  # Bazel default: explicit sandbox boundary, some leak allowed (/proc, locale, timestamps)
    TRUST_HOST = "trust_host"  # ambient host trust — no hermeticity claim


class Sha256Status(str, Enum):
    # KG: ATOM_Skill_longinus
    """SYMPOSIUM Wave 6 absorbed (2026-05-14) — sha256 baseline lifecycle.

    KG: longinus-sha256-daemon-canonical-2026-05-06 + Wave 6 LONGINUS_BINDING.md.
    """

    BASELINE = "BASELINE"  # initial sha256 recorded, no drift yet
    VERIFIED = "VERIFIED"  # last verify matched baseline
    DRIFT = "DRIFT"  # current sha256 != baseline
    FILE_MISSING = "FILE_MISSING"  # sourcePath no longer resolves on disk
    DIRECTORY_SKIP = "DIRECTORY_SKIP"  # sourcePath is a directory, not file
    NOT_LOCAL = "NOT_LOCAL"  # site's repo_id is not checked out on THIS machine (repo_registry
    #                          miss). Distinct from FILE_MISSING — "not here" ≠ "gone", so a
    #                          single-repo audit over the shared KG must NOT flag it as drift.
    UNKNOWN = "UNKNOWN"  # never initialized


class ReferenceSite(BaseModel):
    # KG: ATOM_Skill_longinus
    """Frege Sinn (sourceId) + Bedeutung (sourcePath) bundle.

    SKILL.md 의 *7-layer 관통 통일 entity*. ``# KG: xxx`` 한 줄이 이 객체 1개에 대응.

    Wave 6 additions (2026-05-14):
      - sha256 / sha256_baseline / sha256_status — KG-anchored disk-state baseline
      - kg_anchor — explicit upstream KG node name (Provenance L6 cross-link)
      - layer — explicit 7-layer Reference Model classification
      - last_validated — drift verification timestamp
    """

    sourceId: str = Field(..., description="L4 Sinn — semantic id (KG node name)")
    sourcePath: str = Field(..., description="L1+L4 Bedeutung — file:line")
    pierced_at: str = Field(default_factory=lambda: dt.datetime.now(dt.timezone.utc).isoformat())
    drift_detected_at: Optional[str] = None  # L2 lifetime
    drift_score: float = Field(default=0.0, ge=0.0, le=1.0)  # GED-normalized
    confidence: Confidence = Field(
        default=Confidence.EXTRACTED,
        description="3-tier confidence (graphify absorbed 2026-05-13). AMBIGUOUS triggers :PRELIMINARY + human verdict gate.",
    )

    # ── Wave 6 (2026-05-14) — sha256 baseline + 7-tuple expansion ────────
    sha256: Optional[str] = Field(
        default=None,
        description="Current sha256 hex digest of `sourcePath` file (L7 drift detection).",
    )
    sha256_baseline: Optional[str] = Field(
        default=None,
        description="Frozen baseline sha256 captured at --init. Mismatch with current = drift.",
    )
    sha256_status: Sha256Status = Field(
        default=Sha256Status.UNKNOWN,
        description="sha256 baseline lifecycle state. BASELINE→VERIFIED→DRIFT transitions.",
    )
    kg_anchor: Optional[str] = Field(
        default=None,
        description="Upstream KG node name (e.g. 'lesson-foo-2026-05-14') this site materializes.",
    )
    layer: Optional[ReferenceLayer] = Field(
        default=None,
        description="Explicit 7-layer Reference Model assignment (L1-L7).",
    )
    last_validated: Optional[str] = Field(
        default=None,
        description="ISO-8601 timestamp of last sha256 verification round (Wave 6).",
    )

    # ── v3.4 (2026-05-24) — 8-tuple expansion: guarantee_level ──────────
    guarantee_level: Optional[GuaranteeLevel] = Field(
        default=None,
        description="Hermeticity spectrum tag. pure/sandboxed/trust_host. None = unspecified (backward compat).",
    )

    # ── 2026-05-31 — signature baseline (SigMismatch counterpart of sha256_baseline) ──
    signature_baseline: Optional[str] = Field(
        default=None,
        description="Frozen canonical signature of the bound symbol, captured at record time "
        "(ast scanner). On re-audit, a differing live signature → SigMismatch (PutGet). "
        "None = never recorded (detector falls back to the label heuristic).",
    )

    # ── 2026-06-01 — repo scope tag (shared dgx KG: bhgman/SYMPOSIUM/SERVER co-resident) ──
    repo_tag: Optional[str] = Field(
        default=None,
        description="Repository this site belongs to (e.g. 'bhgman'). The dgx Neo4j is shared "
        "across repos; audit/materialize scope to one repo_tag so a single code-root audit "
        "does not false-flag another repo's ReferenceSites as Orphan/sha256-drift. "
        "None = unscoped (backward compat: matches all). Human alias; repo_id is the strong key.",
    )

    # ── 2026-06-18 — git-anchored, clone-portable binding (repo_identity + repo_registry) ──
    # The site addresses code by (repo_id + repo_relpath + blob_oid) — never an absolute path.
    # repo_id is the machine-independent join key; the machine-local registry maps it to a
    # local checkout, so the same anchor resolves on any clone. All Optional => backward compat.
    repo_id: Optional[str] = Field(
        default=None,
        description="Portable repo identity (machine-independent): '.longinus/repo.toml' id, "
        "else normalized origin remote ('github.com/owner/repo'), else 'rootcommit:<sha>'. "
        "Paired with the machine-local repo registry to resolve an absolute path.",
    )
    repo_relpath: Optional[str] = Field(
        default=None,
        description="POSIX path relative to the git toplevel (no machine prefix). With repo_id "
        "this fully addresses the file portably; sourcePath retains the :line range / legacy form.",
    )
    commit: Optional[str] = Field(
        default=None,
        description="Git commit the baseline was validated at (git rev-parse HEAD).",
    )
    blob_oid: Optional[str] = Field(
        default=None,
        description="git hash-object of the working-tree file — content-addressed, "
        "machine-independent. The drift signal of record.",
    )
    blob_oid_baseline: Optional[str] = Field(
        default=None,
        description="Frozen blob_oid baseline; mismatch with blob_oid = drift. Preferred over "
        "the sha256 baseline when present (git-native, reproducible across clones).",
    )

    @field_validator("sourceId")
    @classmethod
    def _check_id(cls, v: str) -> str:
        if not _SOURCE_ID_PATTERN.match(v):
            # 너무 엄격하지 않게 — KG-style names accepted via dash-form.
            # KG canonical names legitimately start with a digit (`7cmd-…`, `88-…`,
            # `333q-…`) or a unicode letter (`재배맨-v2`, `나생문-canonical`); `\w`
            # (re.UNICODE-by-default for str) covers all three. Leading-letter-only
            # was the bug that crashed `longinus bind` on `7cmd-…` (2026-06-02).
            if not re.match(r"^\w[\w\-./]*$", v):
                raise ValueError(f"invalid sourceId: {v}")
        return v

    @field_validator("sourcePath")
    @classmethod
    def _check_path(cls, v: str) -> str:
        if _SOURCE_PATH_PATTERN.match(v) or _DIRECTORY_OR_PATH_PATTERN.match(v):
            return v
        raise ValueError(
            f"sourcePath must match 'file:line(-end)' or non-empty path "
            f"without whitespace/colons — got {v!r}"
        )

    @property
    def is_directory_path(self) -> bool:
        return ":" not in self.sourcePath

    @property
    def file(self) -> str:
        return self.sourcePath.split(":", 1)[0]

    @property
    def line_start(self) -> int:
        if self.is_directory_path:
            raise ValueError(
                f"line_start undefined for directory-shape sourcePath {self.sourcePath!r}"
            )
        rng = self.sourcePath.split(":", 1)[1]
        return int(rng.split("-")[0])

    @property
    def line_end(self) -> Optional[int]:
        if self.is_directory_path:
            raise ValueError(
                f"line_end undefined for directory-shape sourcePath {self.sourcePath!r}"
            )
        rng = self.sourcePath.split(":", 1)[1]
        return int(rng.split("-")[1]) if "-" in rng else None


# ─── Drift record ────────────────────────────────────────────────────────


class DriftRecord(BaseModel):
    # KG: ATOM_Skill_longinus
    drift_type: DriftType
    sourceId: str
    sourcePath: Optional[str] = None
    expected: Optional[str] = None
    actual: Optional[str] = None
    layer_violated: ReferenceLayer
    lens_law_violated: str  # "GetPut" | "PutGet" | "PutPut"
    detected_at: str = Field(default_factory=lambda: dt.datetime.now(dt.timezone.utc).isoformat())


# ─── Code symbol (scanner output) ────────────────────────────────────────


class CodeSymbol(BaseModel):
    # KG: ATOM_Skill_longinus
    sourcePath: str  # file:line
    name: str  # symbol/function/class name
    kind: str = "unknown"  # function | class | module | const
    signature: Optional[str] = None
    kg_refs: list[str] = Field(default_factory=list)  # `# KG: xxx` lines found


# ─── KG ref record (KG side) ─────────────────────────────────────────────


class KgRefRecord(BaseModel):
    # KG: ATOM_Skill_longinus
    """Mirror of `(:ReferenceSite)` KG node."""

    sourceId: str
    sourcePath: str
    label: Optional[str] = None
    kg_node_kind: str = "ReferenceSite"
    expected_signature: Optional[str] = None
    """Baseline signature recorded in the KG. When set, detect_sig_mismatch does a
    structural ast comparison against the live signature (real PutGet drift);
    when None it falls back to the label-substring heuristic."""


# ─── KnowledgeHub (Forward Orphan target) ────────────────────────────────


class KnowledgeHubRecord(BaseModel):
    # KG: ATOM_Skill_longinus
    """SYMPOSIUM Wave 6 (2026-05-14) — :KnowledgeHub KG node mirror.

    Forward Orphan = KG hub node lacking ``package_path`` (KG → FS direction blind-spot).
    Complementary to Reverse Orphan (Code → KG direction).

    KG: hub-* nodes (e.g. ``hub-apt-methodology``, ``hub-longinus-reference``).
    """

    name: str = Field(..., description="KG hub name, e.g. 'hub-longinus-reference'")
    package_path: Optional[str] = Field(
        default=None,
        description="Filesystem path materializing this hub (e.g. 'THEORY/LONGINUS/').",
    )
    source_file: Optional[str] = Field(
        default=None,
        description="Canonical source file (e.g. 'THEORY/LONGINUS/README.md').",
    )
    ruflo_grade: Optional[str] = Field(
        default=None,
        description="Industry-grade rating (Wave 6 forward orphan resolution metric).",
    )


class ForwardOrphanRecord(BaseModel):
    # KG: ATOM_Skill_longinus
    """A KG :KnowledgeHub node missing ``package_path`` or ``source_file``.

    Wave 6 (2026-05-14): 7 hubs resolved (apt/tpa/jaebaeman/taliban/prometheus/longinus/harness).
    """

    hub_name: str
    missing_field: str  # 'package_path' | 'source_file' | 'ruflo_grade'
    detected_at: str = Field(default_factory=lambda: dt.datetime.now(dt.timezone.utc).isoformat())
    layer_violated: ReferenceLayer = ReferenceLayer.L3_TYPE
    lens_law_violated: str = "GetPut"  # KG asserts hub exists, but FS cannot be resolved


# ─── Drift Event (sha256 baseline mismatch) ──────────────────────────────


class SourceCodeDriftEvent(BaseModel):
    # KG: ATOM_Skill_longinus
    """SYMPOSIUM Wave 6 (2026-05-14) — :SourceCodeDriftEvent KG node mirror.

    Emitted by sha256 baseline daemon on mismatch. PROV evidence trail.
    """

    name: str
    ref_site: str
    path: str
    baseline_sha256: Optional[str] = None
    current_sha256: Optional[str] = None
    kind: str = "SHA256_MISMATCH"  # SHA256_MISMATCH | FILE_MISSING
    detected_by: str = "longinus_drift_audit.sha256_baseline"
    created_at: str = Field(default_factory=lambda: dt.datetime.now(dt.timezone.utc).isoformat())
    resolved: bool = False


# ─── BX Lens result ──────────────────────────────────────────────────────


class LensVerification(BaseModel):
    # KG: ATOM_Skill_longinus
    get_put: bool = True
    put_get: bool = True
    put_put: bool = True
    violations: list[str] = Field(default_factory=list)


# ─── GED report ──────────────────────────────────────────────────────────


class GedReport(BaseModel):
    # KG: ATOM_Skill_longinus
    kg_node_count: int
    code_node_count: int
    insertions: int
    deletions: int
    relabels: int
    ged_total: int
    normalized_score: float = Field(..., ge=0.0, le=1.0)


# ─── Audit final ─────────────────────────────────────────────────────────


class LayerCoverage(BaseModel):
    # KG: ATOM_Skill_longinus
    L1_address: float = 1.0
    L2_lifetime: float = 1.0
    L3_type: float = 1.0
    L4_semiotic: float = 1.0
    L5_distributed: float = 1.0
    L6_compression: float = 1.0
    L7_aesthetic_pierce_rate: float = 1.0


class AuditReport(BaseModel):
    # KG: ATOM_Skill_longinus
    audit_id: str
    drifts_by_type: dict[str, int] = Field(default_factory=dict)
    drift_records: list[DriftRecord] = Field(default_factory=list)
    reverse_orphans: list[str] = Field(default_factory=list)  # code symbols with no KG ref
    forward_orphans: list[ForwardOrphanRecord] = Field(
        default_factory=list
    )  # Wave 6 — KG hubs lacking package_path
    sha256_drift_events: list[SourceCodeDriftEvent] = Field(
        default_factory=list
    )  # Wave 6 — baseline mismatches
    sha256_baseline_count: int = 0  # Wave 6 — total :ReferenceSite with sha256_baseline set
    sha256_not_local_count: int = 0  # sites skipped because their repo isn't on this machine
    #                                  (repo_registry miss) — never counted as drift/missing.
    layer_coverage: LayerCoverage = Field(default_factory=LayerCoverage)
    lens_verification: LensVerification = Field(default_factory=LensVerification)
    ged_report: Optional[GedReport] = None
    completed_at: str = Field(default_factory=lambda: dt.datetime.now(dt.timezone.utc).isoformat())

    @property
    def total_drifts(self) -> int:
        return sum(self.drifts_by_type.values()) + len(self.sha256_drift_events)

    @property
    def is_clean(self) -> bool:
        return (
            self.total_drifts == 0
            and len(self.reverse_orphans) == 0
            and len(self.forward_orphans) == 0
        )
