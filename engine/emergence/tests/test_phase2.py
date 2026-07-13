"""phase2 falsifier — ② Validity + ③ Visibility FSM + 시맨틱 RESOLVE.

F4 ACL(private 격리) + Validity SWR + semantic dedup.
"""
# KG: engineboy-emergence-engine-fsm-design-2026-07-13, rf-engineboy-caching-D3-2026-07-13

from __future__ import annotations

from engine.emergence import (
    AccessEvent,
    ActivityState,
    EmergenceConfig,
    EmergenceEngine,
    InMemoryVectorResolver,
    ServingPolicy,
    ValidityState,
    VisibilityState,
)

S = ActivityState


# ---------- ② Validity FSM (SWR) ----------
def test_validity_fsm_and_swr_serving():
    eng = EmergenceEngine()
    eng.ingest(AccessEvent("v0", "X", "human", 0.0))
    assert eng.serving_policy("X") is ServingPolicy.SERVE_FRESH

    assert eng.mark_stale("X") is ValidityState.STALE
    assert eng.serving_policy("X") is ServingPolicy.SERVE_STALE_REVALIDATE  # SWR

    assert eng.start_revalidate("X") is ValidityState.REVALIDATING
    assert eng.serving_policy("X") is ServingPolicy.SERVE_LAST_GOOD

    assert eng.mark_revalidated("X") is ValidityState.FRESH
    assert eng.serving_policy("X") is ServingPolicy.SERVE_FRESH


def test_validity_orthogonal_to_activity():
    # HOT 이어도 STALE 가능 (직교)
    cfg = EmergenceConfig(theta_hot=2.0, theta_warm=1.0, n_est=2)
    eng = EmergenceEngine(cfg=cfg)
    for i in range(6):
        eng.ingest(AccessEvent(f"h-{i}", "H", "human", float(i)))
    assert eng.nodes["H"].state is S.HOT
    eng.mark_stale("H")
    assert eng.nodes["H"].state is S.HOT                      # activity 불변
    assert eng.serving_policy("H") is ServingPolicy.SERVE_STALE_REVALIDATE


# ---------- ③ Visibility FSM / F4 ACL ----------
def test_f4_public_query_never_resolves_to_private():
    r = InMemoryVectorResolver(tau_sim=0.85)
    eng = EmergenceEngine(resolver=r)
    # alice 의 private 문서 (embed E)
    eng.ingest(AccessEvent("pv0", "alice-doc", "alice", 0.0,
                           acl="private", embed=(1.0, 0.0, 0.0)))
    # bob 의 public query, embed E' ≈ E (cosine ~0.9998)
    tr = eng.ingest(AccessEvent("pq0", "pub-q", "bob", 1.0,
                                acl="public", embed=(0.99, 0.02, 0.0)))
    # 공유 query 는 private 에 착지 못 함 → 신규 노드
    assert tr.namespace == "shared"
    assert tr.key == "pub-q"
    assert "tenant:alice::alice-doc" in eng.nodes
    assert "alice-doc" not in r.bucket_keys("shared")        # private embed 공유 index 부재


def test_f4_private_never_reaches_shared_hot_tier():
    cfg = EmergenceConfig(theta_hot=2.0, theta_warm=1.0, n_est=2)
    eng = EmergenceEngine(cfg=cfg)
    for i in range(15):
        eng.ingest(AccessEvent(f"pv-{i}", "secret", "alice", float(i), acl="private"))
    # private 은 공유 L1(HOT) 승격 불가 (③ 가드)
    assert all(not e.key.startswith("tenant:") for e in eng.by_state(S.HOT))
    assert eng.nodes["tenant:alice::secret"].state is not S.HOT
    assert eng.hot_count() == 0


def test_visibility_publish_moves_hagye_to_sangye():
    eng = EmergenceEngine()
    eng.ingest(AccessEvent("p0", "draft", "alice", 0.0, acl="private"))
    assert "tenant:alice::draft" in eng.nodes
    # gate 거부 → 그대로 private
    assert eng.publish("tenant:alice::draft", "bob", lambda k, r: False) is False
    assert eng.nodes["tenant:alice::draft"].s_vis is VisibilityState.PRIVATE
    # gate 통과 → 상계로 이동
    assert eng.publish("tenant:alice::draft", "admin", lambda k, r: True) is True
    assert "draft" in eng.nodes
    assert eng.nodes["draft"].s_vis is VisibilityState.PUBLISHED


# ---------- (c) 시맨틱 RESOLVE (embedding 기반 dedup) ----------
def test_semantic_resolve_dedups_near_embeddings():
    r = InMemoryVectorResolver(tau_sim=0.86)
    eng = EmergenceEngine(resolver=r)
    eng.ingest(AccessEvent("s0", "topicA", "human", 0.0, embed=(1.0, 0.0, 0.0)))
    # 다른 key, 근접 embed → 같은 노드로 착지 (시맨틱 dedup)
    eng.ingest(AccessEvent("s1", "topicA-restated", "human", 1.0, embed=(0.98, 0.03, 0.0)))
    assert len(eng.nodes) == 1
    assert eng.nodes["topicA"].n == 2
    # 먼 embed → 신규 노드 창발
    eng.ingest(AccessEvent("s2", "topicB", "human", 2.0, embed=(0.0, 1.0, 0.0)))
    assert len(eng.nodes) == 2
