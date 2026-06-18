---
name: deploy
kg_ref: ATOM_Skill_deploy
version: "1.0.0"
channel: stable
description: >
  비행기맨 서버의 Docker 서비스를 재배포합니다. docker-compose.yml 변경 후 적용하거나 특정 서비스를 재시작할 때 사용합니다.
disable-model-invocation: true
---

# 비행기맨 서버 배포

docker-compose 기반 서비스 배포를 수행합니다.

## 배포 전 확인
1. `/Users/lagyeongjun/CD/SERVER/docker-compose.yml` 변경사항 확인
2. 현재 실행 중인 컨테이너 상태 확인

## 배포 실행
```bash
cd /Users/lagyeongjun/CD/SERVER && docker compose up -d
```

## 특정 서비스만 재시작할 경우
인자로 서비스 이름이 주어지면 해당 서비스만 재시작:
```bash
docker compose restart <서비스명>
```

## 배포 후 검증
- 모든 컨테이너가 정상 가동 중인지 확인
- 재시작 루프에 빠진 컨테이너가 있는지 확인
- 외부 접근(bhgman.iptime.org) 경로별 HTTP 상태 확인

## 롤백
문제 발생 시:
```bash
docker compose down && docker compose up -d
```

# KG: ATOM_Skill_deploy
