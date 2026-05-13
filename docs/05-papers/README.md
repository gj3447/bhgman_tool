# Paper-track — 정전 인용 요약

> 각 정전의 *bhgman_tool 측 응용* 짧은 요약. 본문 deep dive 는 원본 paper 또는 별도 repo.

---

## 디렉토리

| Paper | bhgman 측 무엇에 |
|---|---|
| [lawvere-1969-FPT.md](lawvere-1969-FPT.md) | `∀-cover` 자기참조 형식 한계 + Lean 형식화 |
| [foster-pierce-walker-2007-bx-lens.md](foster-pierce-walker-2007-bx-lens.md) | Longinus 측 BX Lens Laws — GetPut / PutGet / PutPut |
| [goodhart-1975.md](goodhart-1975.md) | metric collapse 안전 장치 + Strathern 1997 통속화 |
| [hofstadter-1979-strange-loop.md](hofstadter-1979-strange-loop.md) | 자기참조의 미학적 인정 |
| [frege-1892-sense-reference.md](frege-1892-sense-reference.md) | Longinus 측 sourceId(Sinn) vs sourcePath(Bedeutung) |
| [evans-2003-ddd.md](evans-2003-ddd.md) | Bounded Context + Ubiquitous Language → APT Contract |
| [yanofsky-2003.md](yanofsky-2003.md) | Russell/Cantor/Gödel 통합 — self-reference 한계 |
| [cherns-1976-sts.md](cherns-1976-sts.md) | STS Principle 5 (Boundary Location) → Harness 3-tier |
| [smith-1984-reflection-mop.md](smith-1984-reflection-mop.md) | MOP reflection → APT meta-review phase |
| [lakatos-1976.md](lakatos-1976.md) | progressive vs degenerating research programme |
| [traag-2019-leiden.md](traag-2019-leiden.md) | community detection (KG cluster) |
| [chu-1979-construction.md](chu-1979-construction.md) | CHU type universe grounding |

---

## 우선순위 (bhgman_tool 측 직접 응용 강도)

| 우선순위 | Paper | 이유 |
|---|---|---|
| ★★★ | Lawvere 1969 / Foster-Pierce-Walker 2007 / Goodhart 1975 | 도구 측 직접 형식화 + 안전 장치 |
| ★★ | Evans 2003 / Cherns 1976 / Yanofsky 2003 | 책임 분할 + self-reference 한계 |
| ★ | Smith 1984 / Hofstadter 1979 / Lakatos 1976 / Frege 1892 / Traag 2019 / Chu 1979 | 미학 + meta-level 측 grounding |

---

## 응용 예시

도구 사용자가 *어떻게* 이 정전을 활용하나:

```python
# Longinus drift audit 실행
from longinus_drift_audit import LonginusAudit, ReferenceSite, Confidence

# Frege Sense/Reference 측 적용 (paper #5)
rs = ReferenceSite(
    sourceId="lesson-foo-2026-05-13",      # Sinn (KG 측 의미 id)
    sourcePath="engine/longinus.py:42",    # Bedeutung (위치 reference)
    confidence=Confidence.EXTRACTED,        # graphify 흡수 schema
)

# BX Lens Laws 측 검증 (paper #2)
audit = LonginusAudit(...)
result = audit.verify_lens_laws(rs)  # GetPut / PutGet / PutPut

# Goodhart 측 안전 (paper #3) — confidence AMBIGUOUS 자동 human verdict 강제
if rs.confidence == Confidence.AMBIGUOUS:
    raise HumanVerdictRequired(rs)
```

---

## 작성 상태

각 paper md 파일은 *짧은 요약 + bhgman 측 응용* 형태 (1-2 page). 본문 deep dive 는 원본 paper 또는 별도 academic repo.

현재 일부 paper 본문은 placeholder. 우선순위 ★★★ 측 3 paper 부터 작성.

---

## 자세히는

- [../04-references/citations.md](../04-references/citations.md) — 17 axes 전체 + 추가 정전
- [../06-philosophy/](../06-philosophy/) — 정전 의 *함의* 측 요약
