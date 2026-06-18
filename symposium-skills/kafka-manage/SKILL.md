---
name: kafka-manage
kg_ref: ATOM_Skill_kafka_manage
version: "1.0.0"
channel: stable
description: >
  Kafka 토픽 관리, 메시지 생산/소비, 클러스터 상태 확인에 사용합니다.
---

# Kafka 관리

## 토픽 목록
```bash
docker exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list
```

## 토픽 생성
```bash
docker exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --topic <토픽명> --partitions 1 --replication-factor 1
```

## 토픽 상세 정보
```bash
docker exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --describe --topic <토픽명>
```

## 메시지 생산
```bash
echo "<메시지>" | docker exec -i kafka /opt/kafka/bin/kafka-console-producer.sh --bootstrap-server localhost:9092 --topic <토픽명>
```

## 메시지 소비 (최근 10개)
```bash
docker exec kafka /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic <토픽명> --from-beginning --max-messages 10
```

## 토픽 삭제
```bash
docker exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --delete --topic <토픽명>
```

# KG: ATOM_Skill_kafka_manage
