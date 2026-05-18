# 사회기술적 시스템

## 한 줄

Harness 3-tier 가 단순 architecture 가 아닌 *책임 분할* — Cherns 1976 STS. 사람과 시스템이 함께 진화.

---

## 도구 측 영향

Harness 3-tier (L_MC / L_RT / L_IDE) 는 *technical layer* 만의 분할이 아니다. 각 tier 는 *다른 사람들* 이 다른 역할 + 다른 책임 가진다.

| Tier | Technical 측 | Social 측 (사람 / 책임) |
|---|---|---|
| L_MC managed cloud | server-side orchestration | platform engineer / SRE / 보안 책임자 |
| L_RT application runtime | program-level multi-agent | application developer / framework integrator |
| L_IDE coding harness | developer interactive | individual developer / pair programming / code review |

→ 단순 *layer* 가 아닌 *책임 boundary*. Conway's Law (1968) — *조직 구조가 시스템 구조에 반영*.

bhgman 측은 그 역방향도 의식: *시스템 구조가 조직 구조를 형성* 한다. 따라서 3-tier 분할은 *사회기술적 책임 boundary*.

---

## ruflo 측 대조

ruflo 측 *100+ agents flat enumeration* 은 사회기술적 측면에서 *책임 boundary 없음*:
- 누가 "agent_47" 의 quality 를 책임지나?
- 누가 "plugin X" 의 security 를 책임지나?
- 누가 314 MCP tools 의 backward compatibility 를 책임지나?

→ flat enumeration 의 사회기술적 위험. STS 측 *autonomous responsible group* 부재.

---

## 정전 grounding

- **Trist-Bamforth 1951** — coal mining 사회기술적 연구 (STS 시작)
- **Cherns 1976 "Principles of Sociotechnical Design"** — 9 principles
  1. Compatibility
  2. Minimal critical specification
  3. Sociotechnical criterion
  4. Multifunctionality
  5. **Boundary location** ← Harness 3-tier 직접 응용
  6. Information flow
  7. Support congruence
  8. Design and human values
  9. Incompletion
- **Conway 1968** — "Organizations design systems that mirror their communication structure"
- **Brooks 1995 Mythical Man-Month** — silver bullet 부재 + 조직-시스템 동형
- **Holacracy** (Robertson 2015) — 책임 boundary 의 형식화

특히 **Cherns Principle 5** ("Boundary Location") 는 Harness 3-tier 분할의 직접적 grounding.

---

## 도구 측 실 적용

1. **Harness 3-tier 책임 표 명시** ([../02-concepts/harness.md](../02-concepts/harness.md))
2. **재배맨 SOP — parent process 측 책임 명시** (subagent stateless, parent 가 모든 책임)
3. **executor != reviewer 강제** (Naesengmoon) — Cherns Principle 3 (sociotechnical criterion)
4. **KG :Lesson + symmetric pair** — 조직 측 학습 (success bias 회피)

---

## 한 줄 정리

> 도구는 *technical* 만이 아니다. 책임 boundary + 조직 구조 + 사람의 학습 이 함께 들어간다. Harness 3-tier 는 STS Principle 5 의 직접 응용.

---

## 자세히는

- [../02-concepts/harness.md](../02-concepts/harness.md) §3-tier
- [../05-papers/cherns-1976-sts.md](../05-papers/cherns-1976-sts.md) (예정)
- [../06-philosophy/hermeneutic-circle.md](hermeneutic-circle.md) — 조직 학습 측면
