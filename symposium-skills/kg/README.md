# SYMPOSIUM KG (Neo4j) snapshot

External-machine bootstrap의 KG 측 동봉 메커니즘.

## 흐름

```
[로컬 머신]                    [git]                       [외부 머신]
                                                          
  Neo4j (live KG)                                          (clean Neo4j)
       │                                                       ▲
       │ kg/dump.sh                                             │
       ▼                                                       │
  kg/snapshot.cypher  ──── git push ───── git pull ──── kg/restore.sh
                                                          OR install.sh --with-kg
```

## 사용

### 1) 로컬에서 dump (push 전 1회)

```bash
# 기본 (localhost:7687, password=symposium)
bash kg/dump.sh

# 커스텀
NEO4J_URI=bolt://localhost:7687 \
NEO4J_USER=neo4j \
NEO4J_PASSWORD=mypass \
bash kg/dump.sh
```

생성물: `kg/snapshot.cypher` (idempotent CREATE/MERGE statements).

APOC 플러그인이 있으면 `apoc.export.cypher.all` 사용 (가장 완전). 없으면 fallback (label-by-label).

### 2) git push

```bash
git add kg/snapshot.cypher
git commit -m "kg: snapshot $(date +%Y-%m-%d)"
git push
```

### 3) 외부 머신에서 restore — 옵션 A: install.sh 통합

```bash
curl -sSL https://install.metahumotonic.com/install | bash -s -- --with-kg
# 또는
SYMPOSIUM_KG=1 curl -sSL https://install.metahumotonic.com/install | bash
```

install.sh가 자동으로:
1. `docker run neo4j:5` 컨테이너 기동 (`symposium-neo4j`)
2. bolt 포트 열릴 때까지 대기 (최대 60초)
3. `kg/snapshot.cypher` 자동 로드

### 4) 외부 머신에서 restore — 옵션 B: 수동

```bash
cd ~/.symposium
bash kg/restore.sh                      # localhost:7687 default
bash kg/restore.sh --container my-neo4j # docker exec
bash kg/restore.sh --reset              # CAUTION: 대상 DB 먼저 wipe
```

## CI dump 자동화 (옵션)

`.github/workflows/kg-snapshot.yml`로 매일 자동 dump + commit:

```yaml
name: KG snapshot
on:
  schedule: [{cron: "0 18 * * *"}]   # 03:00 KST 매일
  workflow_dispatch:
jobs:
  dump:
    runs-on: self-hosted             # 로컬 Neo4j 접근 가능한 runner
    steps:
      - uses: actions/checkout@v4
      - run: bash kg/dump.sh
        env: {NEO4J_PASSWORD: ${{ secrets.NEO4J_PASSWORD }}}
      - uses: stefanzweifel/git-auto-commit-action@v5
        with: {commit_message: "kg: nightly snapshot"}
```

## Drift 감지

`kg/snapshot.cypher` 가 git에 commit되어 있으면 외부 머신 KG가 *snapshot 시점의* 상태. 로컬 KG가 그 후 변경되면 drift 발생. 처리:

- **light**: install.sh 재실행 (git pull + 자동 restore — `--reset` 모드)
- **heavy**: longinus_sha256_daemon.py 같은 patrol로 drift 측정

## 주의

- snapshot.cypher 는 **public repo에 가면 KG 전체 노출**. 민감 정보 있으면 *private repo* 또는 *별도 storage* (S3/R2 + signed URL).
- APOC export는 모든 properties 그대로 직렬화. PII 필터링 필요시 dump.sh에 `apoc.export.cypher.query("MATCH (n) WHERE NOT n.secret RETURN n", ...)` 패턴 추가.
- Neo4j 5.x cypher-shell + Neo4j 4.x snapshot 호환성 주의 (역방향 NOT supported).
