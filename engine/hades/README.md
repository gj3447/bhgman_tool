# hades (하네스=하데스) — 실현 군단장

ACCEPTED 추상 spec → 구체 소스코드 materialization. 유레카(구체→추상)의 **dual** (추상→구체).

- `hades.py` / `hades_runner.py` — 본체 + 러너
- `hades_apply.py` — libcst 기반 코드 재작성 적용
- `extract_superclass.py` — 공통 상위클래스 추출 (true-Leiden)
- `hades_models.py` — 데이터 모델

neo4j-free. CLI: `bhgman-tool hades`.
