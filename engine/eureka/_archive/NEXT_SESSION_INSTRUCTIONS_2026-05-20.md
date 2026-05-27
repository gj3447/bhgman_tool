> **[SUPERSEDED — archived by 오캄(Occam) 2026-05-27]**
> This was a one-time session pickup-pointer. All 6 action items are now **DONE** and their
> canonical living record is in the KG, not this doc:
> - §1 APOC `t_abstractclass_required_fields` → `seed-hookinstall-t_abstractclass_required_fields-2026-05-20` = **INSTALLED**
> - §2 GDS plugin → Gap `GDS not installed` = **RESOLVED** / `wqi-l8-gds-plugin-install-2026-05-20` = **COMPLETED**
> - §3 neo4j-graphrag → Gap = **RESOLVED** / `wqi-l8-neo4j-graphrag-pip-install-2026-05-20` = **COMPLETED**
> - §4 crontab → `wqi-l8-crontab-install-2026-05-20` = **COMPLETED**
> - §5 AMIE3 JAR → `wqi-l8-amie3-jar-wrapper-2026-05-20` = **COMPLETED** (see `vendor/`)
> - §6 3-way bake-off → `wqi-l8-bake-off-3way-2026-05-20` = **UNBLOCKED — STILL LIVE WORK, not done.**
>   The §6 recipe below is still the actionable spec for this open task; it is tracked as a live
>   WorkQueueItem in the KG, not orphaned by this archive.
>
> Kept (not deleted) per Occam covenant. 5/6 items done; §6 bake-off remains open.
> For current state query the KG, not this file.

---

# NEXT_SESSION_INSTRUCTIONS — longinus_l8_induction

Generated 2026-05-20. Pickup pointer for follow-up session.
KG: `next-session-entry-2026-05-21-l8-induction` (write-time anchor).

---

## 1. APOC trigger install (admin Neo4j role 필요)

현재 Neo4j 연결 user 측 `CALL apoc.trigger.install` access denied. 다음 admin 세션 시 한 줄로 install.

### 1.1 Admin 자격으로 cypher-shell 접속

```bash
# .env 의 NEO4J_URI 사용, admin user 측 별도 (Neo4j Enterprise 측 neo4j default admin)
! source .env && cypher-shell -a "$NEO4J_URI" -u neo4j -p '<ADMIN_PW>' --format plain
```

### 1.2 install Cypher (한 번에 paste)

```cypher
CALL apoc.trigger.install('neo4j', 't_abstractclass_required_fields', '
UNWIND $createdNodes AS n
WITH n WHERE n:AbstractClass
  AND (n.name IS NULL OR n.summary IS NULL OR n.inductionMethod IS NULL
       OR n.cycleId IS NULL OR n.createdAt IS NULL OR n.status IS NULL)
CALL apoc.util.validate(true,
  "AbstractClass required fields NOT NULL: name + summary + inductionMethod + cycleId + createdAt + status",
  []
) RETURN count(*)
', {phase: 'before'}) YIELD name, installed RETURN name, installed;
```

### 1.3 확인

```cypher
CALL apoc.trigger.list() YIELD name, paused
WHERE name = 't_abstractclass_required_fields'
RETURN name, paused;
```

### 1.4 KG 측 install 완료 기록 (admin 후 본 user 측)

```cypher
MATCH (s {name: 'seed-hookinstall-t_abstractclass_required_fields-2026-05-20'})
SET s.status = 'INSTALLED',
    s.installed_at = datetime(),
    s.installed_by = 'admin_session_post_2026-05-20';
```

---

## 2. GDS plugin install on Neo4j VM

stage_2_community / Leiden-LLM induction 측 차단 의존성.

### 2.1 SSH 측 Neo4j VM (Mac 안 Multipass)

```bash
! multipass shell <neo4j-vm-name>
```

또는 KG `reference_kg_infra_topology.md` 측 dgx-worker 측 DB pod.

### 2.2 GDS plugin download (Neo4j 5.x 호환 버전)

```bash
# 호스트 측
cd /var/lib/neo4j/plugins/
wget https://github.com/neo4j/graph-data-science/releases/download/2.13.0/neo4j-graph-data-science-2.13.0.jar
```

### 2.3 neo4j.conf 측 procedure unrestricted 추가

```ini
dbms.security.procedures.unrestricted=gds.*,apoc.*
dbms.security.procedures.allowlist=gds.*,apoc.*
```

### 2.4 Neo4j restart

```bash
systemctl restart neo4j
# or
neo4j restart
```

### 2.5 확인

```cypher
SHOW PROCEDURES YIELD name WHERE name STARTS WITH 'gds.' RETURN count(*);
-- 측 ≥ 200 procedures 측 예상
```

### 2.6 KG 측 :Gap close

```cypher
MATCH (g:Gap {name: 'GDS not installed'})
SET g.status = 'RESOLVED',
    g.resolved_at = datetime(),
    g.resolution = 'gds plugin <version> installed on Neo4j VM';
```

---

## 3. neo4j-graphrag pip install (stage_6 RRF 의존성)

### 3.1 airo conda env 활성

```bash
! source ~/miniconda3/bin/activate airo
```

### 3.2 install

```bash
pip install 'neo4j-graphrag[all]'
```

`[all]` extra 측 VectorRetriever / HybridRetriever / HybridCypherRetriever / SimpleKGPipeline / Text2CypherRetriever / LLMGraphTransformer 모두 포함.

### 3.3 확인

```bash
python -c "import neo4j_graphrag; print(neo4j_graphrag.__version__)"
# 측 1.16.0+ 측 예상
```

### 3.4 KG 측 :Gap close

```cypher
MATCH (g:Gap {name: 'neo4j-graphrag not installed'})
SET g.status = 'RESOLVED',
    g.resolved_at = datetime();
```

---

## 4. nightly drift check 측 crontab install

stage_7 wire. 30일 baseline 수집 시작.

### 4.1 crontab 측 추가

```bash
! crontab -l > /tmp/cron.bak && \
  echo '17 3 * * * cd /Users/lagyeongjun/CD/bhgman_tool/engine/longinus_l8_induction && /usr/bin/env python3 nightly_drift_check.py >> ~/.bhgman/l8_drift.log 2>&1' >> /tmp/cron.bak && \
  crontab /tmp/cron.bak
```

### 4.2 로그 디렉토리 측 생성

```bash
! mkdir -p ~/.bhgman && touch ~/.bhgman/l8_drift.log
```

### 4.3 확인

```bash
! crontab -l | grep nightly_drift_check
```

GDS install 전 측 nightly_drift_check.py 측 `BLOCKED_GDS_NOT_INSTALLED` 상태로 매일 1줄 로그. GDS install 직후 즉시 실제 community signal 수집 시작.

---

## 5. AMIE 3 JAR download

Java JAR. https://github.com/dig-team/amie/releases (latest stable).

### 5.1 download

```bash
! mkdir -p /Users/lagyeongjun/CD/bhgman_tool/engine/longinus_l8_induction/vendor && \
  cd /Users/lagyeongjun/CD/bhgman_tool/engine/longinus_l8_induction/vendor && \
  wget https://github.com/dig-team/amie/releases/download/v3.5/amie3.5-jar-with-dependencies.jar -O amie3.jar
```

### 5.2 induction_operators/amie3.py 측 subprocess wrapper 작성

stub (`raise NotImplementedError`) 측 실제 구현으로 교체. KG triple export → AMIE3 input format → Java subprocess → Horn rule parsing → AbstractClass 후보 생성.

---

## 6. 3-way bake-off 실시

dependencies = [1, 2, 3, 5] 모두 RESOLVED 후 실시.

bhgman_tool/engine/longinus_l8_induction/bench/bake_off.py 작성:
- subset (≤ 500 nodes) SYMPOSIUM KG 측 추출
- FCA / AMIE3 / Leiden-LLM 측 각각 induce
- silhouette / modularity / FCA stability / 시간 측정
- ResearchFinding MERGE
- plan-prom16lag-l8-induction-2026-05-20 측 status FUTURE→IMPLEMENTED 격상

---

## 7. WorkQueueItem KG pointer

다음 세션 entry: `next-session-entry-2026-05-21-l8-induction` (이 세션 종료 시 결정화 예정).

deferred 4건 (#1, #2, #3, #5, #6) 측 WorkQueueItem 노드로 결정화. priority + estimatedEffort + BLOCKED_BY edge 측 명시.

---

## 8. 30일 GED baseline 측 자동 부산물

cron live 후 매일 03:17 KST 측 1 :DriftCheck 노드 누적. 30개 누적 시 phase 측 자동 cold-start → steady-state 측 전환 (ged_drift_detector.py 측 `day_since_cold_start > 30` 분기). passive — 별도 작업 없음.

# KG: next-session-entry-2026-05-21-l8-induction, longinus-l8-induction-prototype-init-2026-05-20
