"""창발 엔진 orchestrator.

파이프라인: INGEST(dedup) → RESOLVE(namespace 격리) → WEIGHT(Hawkes+Hebbian)
          → SCORE(UCB) → GUARD(① Activity FSM) → COMMIT(store, optional sink).

직교 3 FSM: ① Activity(ingest 구동) / ② Validity(mark_stale·revalidate·serving_policy)
          / ③ Visibility(namespace 격리 + publish).
"""
# KG: engineboy-emergence-engine-fsm-design-2026-07-13

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from engine.emergence import fsm, hawkes, validity, visibility
from engine.emergence.protocols import (
    AccessEvent,
    Action,
    ActivityState,
    Element,
    EmergenceConfig,
    ServingPolicy,
    ValidityState,
    VisibilityState,
)
from engine.emergence.resolver import IdentityResolver, VectorResolver

S = ActivityState
Vis = VisibilityState


def tier_of(state: ActivityState) -> str:
    return {
        S.HOT: "L1", S.COOLING: "L1", S.WARM: "L2",
        S.NASCENT: "L2", S.COLD: "L3", S.DORMANT: "ARCHIVE",
    }[state]


@dataclass(frozen=True)
class Transition:
    key: str
    from_state: Optional[ActivityState]
    to_state: ActivityState
    action: Action
    w: float
    score: float
    namespace: str = "shared"
    deduped: bool = False


class EmergenceEngine:
    def __init__(
        self,
        cfg: Optional[EmergenceConfig] = None,
        resolver: Optional[VectorResolver] = None,
        sink: Optional[Callable[[Transition, Element], None]] = None,
    ) -> None:
        self.cfg = cfg or EmergenceConfig()
        self.resolver: VectorResolver = resolver or IdentityResolver()
        self.sink = sink
        self.nodes: dict[str, Element] = {}
        self.edges: dict[str, Element] = {}
        self._seen: set[str] = set()
        self._total_node_n: int = 0
        self._hot_count: int = 0

    # ---- helpers ----
    @staticmethod
    def _namespace(ev: AccessEvent) -> tuple[str, VisibilityState]:
        if ev.acl == "private":
            return f"tenant:{ev.actor}", Vis.PRIVATE
        return "shared", Vis.PUBLISHED

    @staticmethod
    def _store_key(namespace: str, key: str) -> str:
        # shared 는 plain key (phase1 호환). tenant 는 prefix 로 격리.
        return key if namespace == "shared" else f"{namespace}::{key}"

    @staticmethod
    def _edge_key(a: str, b: str) -> str:
        lo, hi = sorted((a, b))
        return f"edge::{lo}::{hi}"

    def _touch(self, elem: Element, t: float, actor: str, is_edge: bool) -> None:
        elem.w, elem.t_last = hawkes.apply_access(
            elem.w, elem.t_last, t, self.cfg.lam, self.cfg.kappa_for(actor)
        )
        elem.n += 1
        if not is_edge:
            self._total_node_n += 1

    def _get_or_create(
        self, store, skey, t, is_edge, vis=Vis.PUBLISHED, namespace="shared", acl="public"
    ) -> Element:
        e = store.get(skey)
        if e is None:
            e = Element(
                key=skey, created_ts=t, state_since=t, state=S.NASCENT,
                is_edge=is_edge, s_vis=vis, namespace=namespace, acl=acl,
            )
            store[skey] = e
        return e

    # ---- pipeline ----
    def ingest(self, ev: AccessEvent) -> Transition:
        # INGEST: 멱등 dedup
        if ev.event_id in self._seen:
            return Transition(ev.element_key, None, S.NASCENT, Action.NONE, 0.0, 0.0, deduped=True)
        self._seen.add(ev.event_id)

        # RESOLVE (namespace 격리 — ③ 불변식)
        ns, vis = self._namespace(ev)
        resolved = self.resolver.resolve(ev.element_key, ev.embed, ns)
        skey = self._store_key(ns, resolved)
        created = skey not in self.nodes
        node = self._get_or_create(self.nodes, skey, ev.ts, False, vis, ns, ev.acl)
        if created and ev.embed is not None:
            self.resolver.add(resolved, ev.embed, ns)

        # WEIGHT (node + Hebbian 엣지, 동일 namespace 내에서만)
        self._touch(node, ev.ts, ev.actor, is_edge=False)
        for ck in ev.co_keys:
            ck_res = self.resolver.resolve(ck, None, ns)
            if ck_res == resolved:
                continue
            other = self._store_key(ns, ck_res)
            ekey = self._edge_key(skey, other)
            edge = self._get_or_create(self.edges, ekey, ev.ts, True, vis, ns, ev.acl)
            if edge.src is None:  # set once, on first creation
                edge.src, edge.dst = skey, other
            self._touch(edge, ev.ts, ev.actor, is_edge=True)

        # SCORE (UCB)
        score = hawkes.ucb_score(node.w, node.n, self._total_node_n, self.cfg.ucb_c)

        # GUARD (① Activity FSM). HOT = 공유 L1 → ③ 가드: PRIVATE 은 승격 불가
        from_state = node.state
        shared_ok = visibility.can_enter_shared_tier(node.s_vis)
        l1_cap = self._hot_count < self.cfg.l1_capacity and shared_ok
        to_state, action = fsm.next_state(node, ev.ts, score, l1_cap, self.cfg)

        # COMMIT
        if to_state is not from_state:
            if from_state is S.HOT and to_state is not S.HOT:
                self._hot_count -= 1
            if to_state is S.HOT and from_state is not S.HOT:
                self._hot_count += 1
            node.state = to_state
            node.state_since = ev.ts

        tr = Transition(
            key=skey,
            from_state=(None if created else from_state),
            to_state=to_state,
            action=(Action.CREATE if created and action is Action.NONE else action),
            w=node.w, score=score, namespace=ns,
        )
        if self.sink is not None:
            self.sink(tr, node)
        return tr

    # ---- ② Validity FSM ----
    def mark_stale(self, skey: str) -> Optional[ValidityState]:
        e = self.nodes.get(skey)
        if e is None:
            return None
        e.s_val = validity.on_source_changed(e.s_val)
        return e.s_val

    def start_revalidate(self, skey: str) -> Optional[ValidityState]:
        e = self.nodes.get(skey)
        if e is None:
            return None
        e.s_val = validity.on_revalidate_start(e.s_val)
        return e.s_val

    def mark_revalidated(self, skey: str) -> Optional[ValidityState]:
        e = self.nodes.get(skey)
        if e is None:
            return None
        e.s_val = validity.on_revalidated(e.s_val)
        return e.s_val

    def serving_policy(self, skey: str) -> Optional[ServingPolicy]:
        e = self.nodes.get(skey)
        return None if e is None else validity.serving_policy(e.s_val)

    # ---- ③ Visibility FSM ----
    def publish(self, tenant_skey: str, requester: str, gate) -> bool:
        """하계(tenant) element 를 상계(shared)로 publish. gate 통과 필수.

        통과 시 element 를 shared namespace 로 이동 + 공유 resolver 에 embed 등록.
        """
        e = self.nodes.get(tenant_skey)
        if e is None or e.s_vis is Vis.PUBLISHED:
            return False
        base = tenant_skey.split("::", 1)[-1] if "::" in tenant_skey else tenant_skey
        new_vis = visibility.on_publish_request(e.s_vis, base, requester, gate)
        if new_vis is not Vis.PUBLISHED:
            return False
        # 이동: tenant → shared
        del self.nodes[tenant_skey]
        e.key = base
        e.namespace = "shared"
        e.s_vis = Vis.PUBLISHED
        e.acl = "public"
        self.nodes[base] = e
        return True

    # ---- query helpers ----
    def snapshot(self) -> dict[str, Element]:
        return dict(self.nodes)

    def by_state(self, state: ActivityState) -> list[Element]:
        return [e for e in self.nodes.values() if e.state is state]

    def hot_count(self) -> int:
        return self._hot_count

    def current_weight(self, skey: str, t: float) -> float:
        e = self.nodes.get(skey)
        return 0.0 if e is None else hawkes.decayed_weight(e.w, e.t_last, t, self.cfg.lam)
