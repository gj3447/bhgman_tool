---
name: backup
kg_ref: ATOM_Skill_backup
version: "1.0.0"
channel: stable
description: >
  비행기맨 서버의 DB 데이터를 백업합니다. Neo4j, PostgreSQL, MongoDB, Redis 데이터를 MinIO 또는 로컬에 백업할 때 사용합니다.
disable-model-invocation: true
---

# DB 백업

## 백업 대상 및 방법

### Neo4j
```bash
docker exec neo4j cypher-shell -u neo4j -p neo4jpassword "CALL apoc.export.json.all('file:///backup.json', {useTypes:true})"
docker cp neo4j:/var/lib/neo4j/import/backup.json /Volumes/DB_STORAGE/backups/neo4j-$(date +%Y%m%d).json
```

### PostgreSQL
```bash
docker exec postgresql pg_dumpall -U postgres > /Volumes/DB_STORAGE/backups/postgresql-$(date +%Y%m%d).sql
```

### MongoDB
```bash
docker exec mongodb mongodump -u mongo -p mongopassword --out /tmp/mongodump
docker cp mongodb:/tmp/mongodump /Volumes/DB_STORAGE/backups/mongodb-$(date +%Y%m%d)
```

### Redis
```bash
docker exec redis redis-cli -a redispassword BGSAVE
docker cp redis:/data/dump.rdb /Volumes/DB_STORAGE/backups/redis-$(date +%Y%m%d).rdb
```

## 백업 저장 위치
- 로컬: `/Volumes/DB_STORAGE/backups/`
- MinIO: `backups` 버킷

## 백업 후
- 백업 파일 크기 확인
- MinIO에 업로드 (선택)

# KG: ATOM_Skill_backup
