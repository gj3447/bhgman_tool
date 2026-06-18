---
name: server-status
kg_ref: ATOM_Skill_server_status
version: "1.0.0"
channel: stable
description: >
  비행기맨 서버 전체 상태를 점검합니다. Docker 컨테이너, DB 접속, 스토리지, 외부 접근, 네트워크 상태를 한눈에 확인할 때 사용합니다.
---

# 비행기맨 서버 상태 점검

다음 항목을 순서대로 점검하고 결과를 테이블로 보여줍니다:

## 1. Docker 컨테이너
```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

## 2. DB 접속 테스트
- Neo4j: `docker exec neo4j cypher-shell -u neo4j -p neo4jpassword "RETURN 'OK'"`
- PostgreSQL: `docker exec postgresql psql -U postgres -d maindb -t -c "SELECT 'OK'"`
- Redis: `docker exec redis redis-cli -a redispassword PING`
- MongoDB: `docker exec mongodb mongosh -u mongo -p mongopassword --quiet --eval "db.runCommand({ping:1}).ok"`
- MinIO: `curl -s -o /dev/null -w "%{http_code}" http://localhost:9001`

## 3. 외부 접근 (bhgman.iptime.org)
- /neo4j/, /minio/, /s3/, /n8n/, /traefik/ 각 경로 HTTP 상태 확인

## 4. 스토리지
```bash
df -h /Volumes/DB_STORAGE
```

## 5. 네트워크
- 내부 IP: `ifconfig en0 | grep "inet "`
- 공인 IP: `curl -s ifconfig.me`

결과를 깔끔한 테이블로 정리하여 보여줍니다.

# KG: ATOM_Skill_server_status
