---
name: docker-logs
kg_ref: ATOM_Skill_docker_logs
version: "1.0.0"
channel: stable
description: >
  Docker 컨테이너의 로그를 확인합니다. 서비스 장애 원인 파악이나 디버깅 시 사용합니다.
---

# Docker 로그 조회

## 사용법
인자로 컨테이너 이름을 받으면 해당 컨테이너 로그를 출력합니다.
인자가 없으면 모든 컨테이너 중 에러가 있는 것을 찾습니다.

## 특정 컨테이너 로그
```bash
docker logs <컨테이너명> --tail 50 2>&1
```

## 에러 로그만 필터링
```bash
docker logs <컨테이너명> 2>&1 | grep -i "error\|fatal\|exception\|fail" | tail -20
```

## 비정상 컨테이너 찾기
```bash
docker ps -a --filter "status=restarting" --format "{{.Names}}: {{.Status}}"
docker ps -a --filter "status=exited" --format "{{.Names}}: {{.Status}}"
```

## 사용 가능한 컨테이너
traefik, neo4j, postgresql, redis, mongodb, minio, n8n, kafka

# KG: ATOM_Skill_docker_logs
