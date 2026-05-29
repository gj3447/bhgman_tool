# code_to_kg — tree-sitter source → KG (POC 2)

PROM 16 (`prom16-code-to-kg-2026-05-28`) 권고의 **tree-sitter primary** 파이프라인 구현.
소스코드를 파싱해 함수/클래스/import/call 심볼을 KG에 적재한다.

## 왜 tree-sitter (POC 2)인가
PROM 16 비교(Cognee / tree-sitter / Joern) 결론:
- **기존 KG 스키마와 자유롭게 엮임** — Cognee처럼 자기 스키마를 강요하지 않음. `:CodeSymbol`
  노드가 기존 `:SourceCodeNode`(롱기누스)에 `DERIVED_FROM`으로 붙는다.
- **가벼운 의존성** — `pip install tree-sitter tree-sitter-python` 끝. Joern은 JVM+대용량 메모리.
- Python 중심 + 향후 C++/TS 확장도 tree-sitter 한 파이프라인으로 커버.

> 셋 다 동시 적용 금지 — 각자 자기 스키마로 노드를 만들어 KG가 오염되고 어느 노드가
> 진실인지 헷갈린다. 본진은 tree-sitter 하나. (Cognee 벡터검색은 향후 `:CogneeChunk`로 격리
> 보강, Joern은 C++ 콜그래프 필요 시에만.)

## 설계 불변식
- **unidirectional** code→KG + **sha256 baseline** (각 심볼 span 해시 = 롱기누스 L1 drift 기준).
- **격리**: 모든 노드에 우산 라벨 `:CodeSymbol` → POC 그래프 전체가 하나의 제거 가능 집합.
- **멱등**: 심볼 ID = `sourcePath::qualname` (안정). 재적재 = MERGE, 중복 0.
- **graceful import**: tree-sitter 부재 시 문서화된 스텁으로 degrade.

## 스키마
```
(:CodeSymbol:CodeModule   {symbol_id, name, qualname, kind, sourcePath, start_line, end_line, sha256, language})
(:CodeSymbol:CodeClass    {...})
(:CodeSymbol:CodeFunction {...})         # kind = function | method
(:CodeSymbol:CodeExternal {name})        # 미해소 import/call 스텁 (Cypher 모드)

(module)-[:DERIVED_FROM]->(:SourceCodeNode {sourcePath})   # 기존 스키마에 엮기
(parent)-[:DEFINES]->(child)                                # 모듈→함수/클래스, 클래스→메서드
(func)  -[:CALLS]->(func|external)                          # file-local 해소, 외부는 스텁
(module)-[:IMPORTS]->(external)
```

CALLS는 **file-local best-effort 해소** (PROM 16 A4 함정: tree-sitter는 semantic binding을
strip — 완전 name resolution은 LSP/Stack Graphs 보강 패스로 deferred).

## 사용
```bash
# Neo4j용 idempotent MERGE Cypher 출력 (실행 안 함, 안전 기본)
python -m engine.code_to_kg.cli ingest <file_or_dir>

# 로컬 JSON KG(~/.bhgman/kg.json)에 적재 — neo4j 0 (occam/eureka/hades --local 관용)
python -m engine.code_to_kg.cli ingest <file_or_dir> --local
```

## 모듈
- `ts_extractor.py` — tree-sitter 파싱 → `CodeGraph` (순수/오프라인/결정론).
- `kg_writer.py` — `write_local` (JSON store) + `to_cypher` (Neo4j).
- `cli.py` — `ingest` 엔트리.
- `tests/` — 16 pytest (추출 8 + writer 8).

## SYMPOSIUM 위상
비행기맨 #4 산하 **롱기누스(연결)** 의 1:N sibling. graphify / code-review-graph /
Stack Graphs / SCIP 와 형제. 본 POC = "tree-sitter→KG 적재" sub-type (롱기누스는
*drift-bidirectional* sub-type). family-expansion-pattern.

# KG: lesson-prom16-code-to-kg-tools-2026-05-28, cycle prom16-code-to-kg-2026-05-28,
      ATOM_Skill_longinus, family-expansion-pattern-canonical-2026-04-30
