# CHU 와 비행기맨

> CHU (Computable Hyper Universe) 자체의 정전은 별도 repo `chu` 에서 다룬다. 이 문서는 *비행기맨이 CHU 위에서 어떻게 정의되는가* 만.

---

## CHU 짧은 정의 (full body 는 `chu` repo)

```
CHU : Type           모든 것이 hyperedge 인 type universe
CHUPiece := CHU → Prop   각 piece 는 CHU 상의 명제
```

CHU 의 본격 정전 (Chu construction 1979, Po-Hsiang Chu / Barr *⋆-Autonomous Categories* / Wolfram Hypergraph Universe 측 grounding) 은 `chu` repo (예정).

---

## 비행기맨의 CHU 의존

비행기맨 정의가 `∀x:CHU, j.covers x` 인 만큼, *CHU 가 무엇인지* 가 정의의 의미를 결정.

핵심:
- **CHU 가 *모든 것* 의 universe** (hypergraph 위에서) 라야 비행기맨의 ∀-cover 가 *진짜* universal 이 됨.
- 만약 CHU 가 *어떤 fragment* 라면 비행기맨도 *fragment-covering*. universal 아님.

→ bhgman 은 CHU 가 *full universe* 라는 axiom 을 받아들임. 검증은 `chu` repo 측.

---

## 한 줄

CHU = 비행기맨이 *cover 해야 할 universe*. 이 repo 측에서는 그 사실 인정만, 정전 본문은 `chu` 측.

자세히는 `chu` repo 또는 [../07-metahumotonic-trace.md](../07-metahumotonic-trace.md).
