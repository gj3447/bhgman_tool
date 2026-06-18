# TCW World Reference

> TPA v1.1 TCW Phase 상세. SKILL.md가 "무엇을 하라"면 이 문서는 "구체적으로 어떻게"를 제공한다.
> Mirror sibling: `apt-scw/references/scw_world.md` (forward direction).

---

## 1. Phase Identity

**TCW = TargetCodeWorld** — 외부/레거시 코드 베이스에서 *실제로 존재하는* 모든 pub 심볼을 빠짐없이 채집한다.

| 질문 | 답 |
|------|----|
| 언제 시작? | 외부 repo 분석 의뢰 받았을 때 (`/tpa <path>` 자동 진입) |
| 무엇을 산출? | `:TPA_TCW_Result` (manifest + symbol list + LOC distribution) + Naesengmoon TCW VR |
| 무엇을 *하지* 않는가? | 의도 추론, 패턴 매칭, contract 추출 — 그 셋은 ST/SP/TA에서 |
| 입력 | 디렉토리 path, optional config (parallel.max_agents) |
| pre-gate | 없음 — TCW가 시작 phase. Hook은 통과시킴 (`echo '{}' && exit 0`) |
| post-gate | Naesengmoon 9-lens VR + 매니페스트 무결성 (TR5 union check) |

---

## 2. 진입 의식 (필수 KG 쿼리)

```cypher
// 1. SubagentTaskSpec 씨앗 조회
MATCH (ts:SubagentTaskSpec {name:'taskspec-tpa-TCW', skill:'tpa'})
RETURN ts.checkItems, ts.cypherQueries, ts.expectedOutcome, ts.parallelism_min

// 2. WorkBuffer current
MATCH (wb:WorkBuffer {status:'CURRENT'}) RETURN wb

// 3. 기존 TPA_Execution이 있는지 확인 (resume vs new)
MATCH (e:TPA_Execution) WHERE e.target = $target
RETURN e.name, e.status, e.started_at ORDER BY e.started_at DESC LIMIT 1
```

Resume 케이스는 `e.status = 'IN_PROGRESS_TCW'`로 진입. 새 사이클이면 새 `:TPA_Execution` 생성.

---

## 3. Manifest 구축 (TR5 + TR14)

```bash
# 1. 파일 목록 (TR4: AST 파서 적용 가능 언어만)
find $TARGET -type f \( -name '*.rs' -o -name '*.ts' -o -name '*.tsx' \
    -o -name '*.py' -o -name '*.go' -o -name '*.js' -o -name '*.jsx' \) \
    -not -path '*/target/*' -not -path '*/node_modules/*' -not -path '*/.git/*' \
    | sort > /tmp/tcw_manifest.txt

# 2. LOC per file
xargs -a /tmp/tcw_manifest.txt wc -l > /tmp/tcw_loc.txt

# 3. Total LOC + 에이전트 수 결정
TOTAL=$(awk '{s+=$1} END {print s}' /tmp/tcw_loc.txt)
# haiku 5K LOC/agent · sonnet 10K · opus 20K
```

**TR14 정전**: `TOTAL > 10K` → 재배맨 4 agent (file-level partition, *not* directory). `> 100K` → 8 agent + hierarchical merge.

**TR5 정전**: post-dispatch `assert union(agent_files) == manifest_files`. 불일치 시 보충 agent 출격.

---

## 4. AST 추출 — 언어별 파서 매핑 (TR4)

| Lang | 권장 파서 | fallback |
|------|----------|---------|
| Rust | `rust-analyzer --json` | `tree-sitter-rust` |
| TypeScript / JavaScript | `tree-sitter-typescript` | `@babel/parser` |
| Python | `pyright --outputjson` | `tree-sitter-python` |
| Go | `go/parser` | `tree-sitter-go` |

**금지**: grep 단독. TR4 hard rule. 파서 출력 갯수가 `wc -l` 기준 라인 수 분포와 합리적으로 일치해야 한다 (V29 ground truth).

---

## 5. Pub 심볼 추출 — 출력 schema

각 심볼에 대해:
```cypher
MERGE (sym:CodeSymbol:AbstractNode {name: $qualified_name})
SET sym.kind = $kind,                   // fn | struct | trait | impl | mod | class | interface
    sym.visibility = $vis,              // pub | pub(crate) | private | protected
    sym.file = $file,
    sym.line = $line,
    sym.signature = $signature,
    sym.parsed_with = $parser,
    sym.found_in_execution = $exec_name,
    sym.discovered_at = datetime()
```

ResearchProvider 자동 호출 조건 (TR6):
- `kind` 가 unknown
- `signature` 에 알 수 없는 syntax (예: 새 macro, 새 attribute)

---

## 6. TPA_TCW_Result 결정화

```cypher
MERGE (tcw:TPA_TCW_Result:AbstractNode {name: 'TCW_' + $target_id + '_' + $date})
SET tcw.sourcePath = $target,
    tcw.symbol_count = $sym_n,
    tcw.parser_symbol_count = $parser_n,
    tcw.parsed_with = $parser,
    tcw.skipped_files = 0,                          // TR5
    tcw.manifest_size = $manifest_n,
    tcw.union_size = $union_n,                       // assertion: == manifest_size
    tcw.unknown_count = $unknown_n,
    tcw.giant_method_candidates = $giants_n,         // LOC>100, deferred to SP
    tcw.parallel_agents_used = $n_agents,
    tcw.created_at = datetime()
MERGE (exec:TPA_Execution {name: $exec_name})-[:PHASE_OUTPUT {order:1}]->(tcw)
```

---

## 7. FulfillmentGate TCW (7 checks)

1. [ ] manifest_size == union_size (TR5 무결성)
2. [ ] symbol_count == parser_symbol_count (TR4 ground truth)
3. [ ] skipped_files == 0
4. [ ] parsed_with != 'grep'
5. [ ] giant_method_candidates는 SP phase로 표시 (deferred_to='SP' 라벨)
6. [ ] CodeSymbol 노드 sourcePath 모두 채워짐
7. [ ] taskspec.checkItems 전부 pass

---

## 8. Naesengmoon 9-lens (종료 의식)

```cypher
MATCH (s:MethodologySlot {name:'AdversarialValidator'})
RETURN s.invocation
-- {invocation} TPA_TCW_<target>
```

Critic 이 받는 컨텍스트:
- manifest 통계 (size, distribution, language mix)
- AST 파서 ground truth (parser_symbol_count vs `wc -l` 기준)
- skipped_files, unknown_count, giant_method_candidates
- 발견된 NewSyntax / unknown 패턴 목록

Critic 이 ≥3 finding 못 만들면 escalated prompt (references/adversarial.md §2) 재호출.

---

## 9. ValidationResult 기록

```cypher
MERGE (vr:ValidationResult {name:'VR_TPA_TCW_'+$target+'_'+$date, phase:'TCW'})
SET vr.verdict = $verdict,
    vr.evidence = [...],
    vr.validator = 'Naesengmoon-9lens',
    vr.target_phase = 'TCW',
    vr.validated_at = datetime(),
    vr.provenance = 'subagent-taliban-tcw'
MATCH (exec:TPA_Execution {name: $exec})
MERGE (exec)-[:HAS_VALIDATION]->(vr)
SET exec.status = CASE $verdict
    WHEN 'APPROVED' THEN 'IN_PROGRESS_TCW'
    ELSE 'BLOCKED_AT_TCW'
  END
```

`provenance = 'inline'` 금지 — 부모-인라인 APPROVED 차단 (TR11). 반드시 subagent 1개 이상 독립 출격.

---

## 10. Common Failure Modes

| 증상 | 원인 | 처방 |
|------|------|------|
| `union != manifest` | directory boundary chunking (v1 bug) | file-level partition으로 재분배 (TR14 v2) |
| `parser_symbol_count = 0` | 파서 binary 미설치 / 버전 mismatch | references/error_handling.md §3 |
| `unknown_count > 50` | 새 언어 / 새 macro 다수 | ResearchProvider 사전 호출 (`/prom 16`) |
| `skipped_files > 0` | feature-gated 코드 미스캔 | `#[cfg]` 등 동등 스캔 명시 (TR5) |
| Naesengmoon verdict = REJECT 반복 | manifest 결함 또는 파서 버그 | iter < 3에서 sigma_oracle escalate |

---

## 11. References

- `../tpa/references/phases.md` §1 (요약)
- `../tpa/references/error_handling.md` §2-3 (manifest/parser failure)
- `../tpa/references/adversarial.md` §2 (escalated prompt)
- `../apt-scw/references/scw_world.md` (mirror direction — forward TDD)

# KG: ATOM_Skill_tpa_tcw, fw-tpa-references-apt-parity-2026-05-06
