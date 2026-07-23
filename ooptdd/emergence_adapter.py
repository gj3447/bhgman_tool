"""ooptdd-loop in_process target — engineboy 창발(emergence) 엔진을 REAL 실행에 바인딩.

positive-TDD / log-based: the *store* is the judge, not the return value. adapter 는
engine.emergence 의 진짜 엔진을 돌려서 얻은 상태에서 *재도출* 한 count 로만 이벤트를
ship 한다. self-report 로는 게이트를 통과할 수 없다.

Honest-count contract:
    - emergence_cluster_recovered (==1): experiment.run_experiment 의 REAL engine.edges 에서
      재도출한 클러스터 내/간 엣지 비율이 임계 초과일 때만 1. noise=True (전역 랜덤, 잠재구조
      없음) => 비율 ~1 => 0 => RED. 창발이 실제로 일어났을 때만 emit.
    - emergence_private_isolated (==1): REAL EmergenceEngine 에 private 문서 + 근접-임베딩
      public query 를 넣고, public 이 private key 에 착지 못 했고 private embed 가 shared
      버킷에 없음을 *재검* 했을 때만 1. leak=True (private 을 public 으로) => public 이 착지
      => 0 => RED.
    - emergence_weight_converged (==1): REAL Hawkes 정상 스트림의 |w − w*| < tol 일 때만 1.
      short=True (짧은 런) => 미수렴 => 0 => RED.

Longinus binding (AST-checked): 각 must_emit 리터럴은 바인딩된 ADAPTER 심볼 몸통에 verbatim.
    rename => UNBOUND/RED. 리터럴은 engine/emergence/ 안이 아니라 여기 산다.

Run:   ooptdd-loop run ooptdd/emergence_requirements.yaml --json

# KG: finding-ooptdd-bhgman-emergence-adapter-20260713
# KG: engineboy-emergence-engine-fsm-design-2026-07-13
"""
from __future__ import annotations

from engine.emergence import (
    AccessEvent,
    EmergenceConfig,
    EmergenceEngine,
    InMemoryVectorResolver,
    VisibilityState,
)
from engine.emergence import hawkes
from engine.emergence.experiment import run_experiment

_KG_ANCHOR = "finding-ooptdd-bhgman-emergence-adapter-20260713"


def _ev(cid: str, event: str, **attrs) -> dict:
    return {
        "cid": cid,
        "correlation_id": cid,
        "cycle_id": cid,
        "service": "bhgman.emergence",
        "event": event,
        **attrs,
    }


def emit_cluster_phase(backend, cid: str, *, noise: bool = False) -> int:
    """REAL 엔진을 돌려 Hebbian 클러스터 복원이 실제로 일어났을 때만 'emergence_cluster_recovered'
    ship. count = structure_emerged(engine.edges 재도출). noise => 0. 리터럴 여기 산다."""
    res = run_experiment(seed=7, noise=noise)
    if res.structure_emerged:
        backend.ship([
            _ev(cid, "emergence_cluster_recovered",
                intra=round(res.intra_edge_mean, 3), inter=round(res.inter_edge_mean, 3))
        ])
        return 1
    return 0


def emit_isolation_phase(backend, cid: str, *, leak: bool = False) -> int:
    """REAL 엔진에 private 문서 + 근접 public query 를 넣고, 격리가 실제로 성립했을 때만
    'emergence_private_isolated' ship. leak => private 을 public 으로 => 착지 => 0. 리터럴 여기."""
    r = InMemoryVectorResolver(tau_sim=0.85)
    eng = EmergenceEngine(resolver=r)
    priv_acl = "public" if leak else "private"
    eng.ingest(AccessEvent("iso-priv", "alice-doc", "alice", 0.0,
                           acl=priv_acl, embed=(1.0, 0.0, 0.0)))
    tr = eng.ingest(AccessEvent("iso-pub", "pub-q", "bob", 1.0,
                                acl="public", embed=(0.99, 0.02, 0.0)))
    # 재검: public query 가 private 에 착지 못 했고, private embed 가 shared 버킷에 없음.
    isolated = (tr.namespace == "shared"
                and tr.key == "pub-q"
                and "alice-doc" not in r.bucket_keys("shared"))
    if isolated:
        backend.ship([_ev(cid, "emergence_private_isolated", public_landed_on=tr.key)])
        return 1
    return 0


def emit_convergence_phase(backend, cid: str, *, short: bool = False) -> int:
    """REAL Hawkes 정상 스트림이 해석해 평형으로 수렴했을 때만 'emergence_weight_converged' ship.
    short => 짧은 런 => 미수렴 => 0. 리터럴 여기 산다."""
    lam, kappa, step = 0.1, 1.0, 1.0
    cfg = EmergenceConfig(lam=lam, kappa=kappa, l1_capacity=10_000)
    eng = EmergenceEngine(cfg=cfg)
    n = 5 if short else 300
    last_w = 0.0
    for i in range(n):
        last_w = eng.ingest(AccessEvent(f"cv-{i}", "X", "ai", i * step)).w
    w_star = hawkes.equilibrium_weight(kappa, rate=1.0 / step, lam=lam)
    if abs(last_w - w_star) < 1e-6:
        backend.ship([_ev(cid, "emergence_weight_converged", w=round(last_w, 6))])
        return 1
    return 0


def run_emergence_pipeline(backend, cid: str, *, noise: bool = False,
                           leak: bool = False, short: bool = False) -> dict:
    """Loop entry. REAL 창발 엔진의 세 창발 성질(구조/격리/수렴)을 돌려 lifecycle 을 ship.
    'emergence_run_started' 와 'emergence_run_complete' 리터럴은 THIS 심볼에 verbatim."""
    backend.ship([_ev(cid, "emergence_run_started", phase="cluster")])
    n_cluster = emit_cluster_phase(backend, cid, noise=noise)
    n_isolated = emit_isolation_phase(backend, cid, leak=leak)
    n_converged = emit_convergence_phase(backend, cid, short=short)
    backend.ship([
        _ev(cid, "emergence_run_complete",
            cluster=n_cluster, isolated=n_isolated, converged=n_converged)
    ])
    return {"cluster": n_cluster, "isolated": n_isolated, "converged": n_converged}


__all__ = [
    "emit_cluster_phase",
    "emit_isolation_phase",
    "emit_convergence_phase",
    "run_emergence_pipeline",
]
