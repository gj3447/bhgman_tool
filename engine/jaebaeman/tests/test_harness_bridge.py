"""harness → 재배맨 seed bridge — '하네스 자체가 재배맨 씨앗'을 코드로 닫는 RED 아티팩트.

재배맨 v2 = subagent-runtime-protocol: 씨앗 = :SubagentTaskSpec = 하네스(subagent) 컨텍스트.
하지만 harness *진단*(engine/harness, 3계층/4축)과 재배맨 *씨앗*은 아직 안 묶여 있었다. 이
브릿지가 그 갭을 닫는다: harness diagnosis → PRESENT로 확인되지 않은 각 축마다 plantable Goal(씨앗).
4축 완비 harness → 0 씨앗(보완 불필요), 축 무신호 → 4. RED until harness_seed_goals exists.

# KG: 재배맨-v2-subagent-runtime-protocol
"""
from __future__ import annotations

from engine.harness.harness import diagnose
from engine.jaebaeman.harness_bridge import (
    germinate_under_harness,
    harness_germination_system,
    harness_seed_goals,
)


def _missing(goals) -> list[str]:
    return sorted(g.name.rsplit("ensure-", 1)[-1] for g in goals)


def test_missing_axes_become_compensation_seeds():
    # claude code: IDE_HOST, present {CONSTRAIN, VERIFY} → missing {INFORM, CORRECT}.
    goals = harness_seed_goals(diagnose("claude code"))
    assert len(goals) == 2
    assert _missing(goals) == ["correct", "inform"]
    assert all(g.task_type == "harness-compensation" for g in goals)
    assert all(g.target_domain == "IDE_HOST" for g in goals)  # the diagnosed tier


def test_full_four_axis_harness_yields_no_seed():
    # an explicit all-axes-present harness has no gap → no compensation seed.
    d = diagnose("x", signals={"inform": True, "constrain": True, "verify": True, "correct": True})
    assert harness_seed_goals(d) == []


def test_axis_less_harness_yields_four():
    goals = harness_seed_goals(diagnose("totally-unknown-xyz-framework"))
    assert len(goals) == 4
    assert _missing(goals) == ["constrain", "correct", "inform", "verify"]


def test_seeds_can_anchor_to_the_harness_diagnosis_node():
    # the harness diagnosis node (KG :HarnessDiagnosis) becomes the soil the seeds anchor to.
    d = diagnose("claude code")
    anchored = harness_seed_goals(d, anchor=d.subject)
    assert anchored and all(g.anchor == "claude code" for g in anchored)
    # default stays self-anchored (backward compat).
    assert all(g.anchor is None for g in harness_seed_goals(d))


def test_bridge_goals_are_plantable_via_jaebaeman():
    # the bridge output is real 재배맨 Goals → run_jaebaeman plants them as seeds (the handoff):
    # harness diagnosis → seeds → (germinate → subagent contexts, see test_germinate_handoff).
    from engine.jaebaeman.jaebaeman_models import Goal
    from engine.jaebaeman.jaebaeman_runner import run_jaebaeman
    from engine.jaebaeman.planner import static_decompose

    goals = harness_seed_goals(diagnose("claude code"))
    root = Goal(name="harness::claude code", objective="compensate harness gaps")
    res = run_jaebaeman(
        root,
        decompose=static_decompose({root.name: goals}),
        skill="harness",
        apply=False,
        validate=False,
    )
    seed_names = [s.name for s in res.seeds]
    assert any("ensure-inform" in n for n in seed_names)
    assert any("ensure-correct" in n for n in seed_names)


# ── reverse direction: the harness shapes HOW a seed germinates (germination environment) ──


def test_harness_germination_system_names_tier_and_axes():
    sysd = harness_germination_system(diagnose("claude code"))
    assert "tier=IDE_HOST" in sysd
    assert "CONSTRAIN" in sysd and "VERIFY" in sysd  # provides — use them
    assert "INFORM" in sysd and "CORRECT" in sysd  # UNKNOWN — supply yourself
    assert "does NOT advertise" in sysd


def test_full_harness_has_no_compensation_directive():
    d = diagnose("x", signals={"inform": True, "constrain": True, "verify": True, "correct": True})
    assert "does NOT advertise" not in harness_germination_system(d)  # nothing to compensate


def test_germinate_under_harness_bakes_environment_into_subagent():
    from engine.jaebaeman.jaebaeman_models import SeedRecord

    seed = SeedRecord(
        name="s1", skill="harness", source_id="s1", display_name="do X", task_type="research",
        target_domain="kg", expected_outcome="Y", germination_method="manual", depth=0, parent=None,
    )
    spec = germinate_under_harness(seed, diagnose("claude code"))
    assert "tier=IDE_HOST" in spec.system  # harness shapes HOW it germinates (environment)
    assert spec.user == "do X\n기대 산출: Y"  # seed shapes WHAT
    assert spec.web_search is False


# ── closed loop: harness → seed → KG plant → read-back → germinate(harness-aware) → status ──


class _FakeKg:
    """Faithful in-memory :SubagentTaskSpec store — plant / read-ready / status round-trip."""

    def __init__(self):
        self.nodes: dict = {}
        self.parent: dict = {}
        self.diagnoses: dict = {}
        self.has_seed: list = []

    def __call__(self, cypher, params=None):
        p = params or {}
        if "MERGE (h:HarnessDiagnosis {name: $subject})" in cypher:  # plant diagnosis (the soil)
            self.diagnoses[p["subject"]] = dict(p)
            return [{"diagnosed": p["subject"]}]
        if "MERGE (s:SubagentTaskSpec {name: $name})" in cypher:  # plant
            self.nodes[p["name"]] = {**p, "status": "READY"}
            return [{"seeded": p["name"]}]
        if "MERGE (p)-[:DECOMPOSES_TO]->(c)" in cypher:  # plan edge
            self.parent[p["child"]] = p["parent"]
            return [{"child": p["child"]}]
        if "MERGE (a)-[r:HAS_SEED]->(s)" in cypher:  # anchor edge → record (soil ↔ seed)
            self.has_seed.append((p["anchor"], p["seed"]))
            return [{"linked": p.get("seed")}]
        if "WHERE s.status = 'READY'" in cypher:  # read-back
            cyc = p.get("cycle_id")
            rows = []
            for n, pr in self.nodes.items():
                if pr.get("status") != "READY" or (cyc and pr.get("cycle_id") != cyc):
                    continue
                rows.append({
                    "name": n, "skill": pr.get("skill"), "sourceId": pr.get("sourceId"),
                    "displayName": pr.get("displayName"), "taskType": pr.get("taskType"),
                    "targetDomain": pr.get("targetDomain"), "expectedOutcome": pr.get("expectedOutcome"),
                    "germinationMethod": pr.get("germinationMethod"), "depth": pr.get("depth", 0),
                    "parent": self.parent.get(n),
                })
            return rows
        if "SET s.status = $status" in cypher:  # status writeback
            if p["name"] in self.nodes:
                self.nodes[p["name"]]["status"] = p["status"]
            return [{"updated": p["name"]}]
        return []


def test_closed_loop_harness_to_seed_to_germinate_to_status():
    from engine.jaebaeman.jaebaeman_models import Goal, SeedStatus
    from engine.jaebaeman.jaebaeman_runner import germinate_ready_seeds, run_jaebaeman
    from engine.jaebaeman.lifecycle import SeedOutcome
    from engine.jaebaeman.planner import static_decompose

    kg = _FakeKg()
    d = diagnose("claude code")
    goals = harness_seed_goals(d)  # 2 compensation goals (INFORM, CORRECT)
    root = Goal(name="harness::claude code", objective="compensate harness gaps")

    # plant (apply=True) — seeds land in the KG as READY :SubagentTaskSpec.
    res = run_jaebaeman(
        root, run_cypher=kg, write_cypher=kg,
        decompose=static_decompose({root.name: goals}),
        skill="harness", cycle_id="loop-1", apply=True, validate=False,
    )
    assert res.apply_result.applied_count == 3  # root + 2 leaves
    assert all(p["status"] == "READY" for p in kg.nodes.values())

    # germinate (apply=True) — read READY back, germinate UNDER the harness, write status back.
    germinated = []

    def dispatcher(seeds):
        out = []
        for s in seeds:
            germinated.append(germinate_under_harness(s, d))  # reverse bridge: harness-aware
            out.append(SeedOutcome(s.name, SeedStatus.COLLECTED, "germinated"))
        return out

    lc = germinate_ready_seeds(dispatcher, kg, cycle_id="loop-1", write_cypher=kg, apply=True)
    assert lc.collected == 3 and lc.failed == 0
    assert all(p["status"] == "COLLECTED" for p in kg.nodes.values())  # status round-tripped to KG
    assert all("tier=IDE_HOST" in g.system for g in germinated)  # every subagent harness-aware
    assert any("ensure-inform" in g.name for g in germinated)


def test_harness_diagnosis_is_the_soil_its_seeds_anchor_to():
    from engine.harness.harness import build_diagnosis_cypher
    from engine.jaebaeman.jaebaeman_models import Goal
    from engine.jaebaeman.jaebaeman_runner import run_jaebaeman
    from engine.jaebaeman.planner import static_decompose

    kg = _FakeKg()
    d = diagnose("claude code")

    # ① plant the harness diagnosis node itself (the soil) — harness classifier → KG.
    kg(*build_diagnosis_cypher(d))
    assert kg.diagnoses["claude code"]["tier"] == "IDE_HOST"
    assert set(kg.diagnoses["claude code"]["axes"]) == {"CONSTRAIN", "VERIFY"}

    # ② plant the compensation seeds ANCHORED to that diagnosis node (HAS_SEED edge = soil↔seed).
    goals = harness_seed_goals(d, anchor=d.subject)
    root = Goal(name="harness-root::claude code", objective="root")  # self-anchored root
    run_jaebaeman(
        root, run_cypher=kg, write_cypher=kg,
        decompose=static_decompose({root.name: goals}),
        skill="harness", cycle_id="soil-1", apply=True, validate=False,
    )
    anchored = [seed for anc, seed in kg.has_seed if anc == "claude code"]
    assert len(anchored) == 2  # the 2 compensation seeds grow in the harness-diagnosis soil
    assert all("ensure-" in s for s in anchored)
