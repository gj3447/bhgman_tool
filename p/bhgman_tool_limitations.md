# bhgman_tool 한계 정리

## 1. 추론 능력 자체를 올려주지는 않음

README도 솔직하게 "governance/audit layer, not intelligence"라고 말한다. 즉 모델이 틀릴 것을 덜 틀리게 만드는 마법이 아니라, 출처, 검증, 재현성, 드리프트 감시를 강제하는 장치에 가깝다. 좋은 규율이지, 지능 증폭기는 아니다.

## 2. 독립 실행 엔진이 아직 완전하지 않음

`/apt`, `/tpa` 같은 큰 방법론 흐름은 완전한 in-process 엔진이라기보다 Claude Code skill 라우팅 의존이 크다. `engine/cli/main.py`에도 cohort B 명령들이 실제 phase logic을 직접 실행하지 않는다고 적혀 있다.

## 3. 외부 의존성이 많음

제대로 쓰려면 Claude Code skill, KG, 선택적으로 Neo4j, Anthropic/OpenAI-compatible LLM, Lean, submodule 등이 엮인다. `--local` 경로는 있지만 전체 가치가 나오려면 환경 세팅 비용이 크다.

## 4. 용어와 세계관 진입장벽이 높음

Longinus, Occam, Hades, Naesengmoon, Jaebaeman 같은 내부 명명 체계가 강해서 만든 사람이나 팀에게는 압축적이지만, 외부 개발자에게는 첫 이해 비용이 크다. 범용 OSS로는 가장 큰 friction이다.

## 5. 품질 게이트 일부가 soft임

풀 테스트는 통과하지만 CI에서 ruff/mypy가 `|| true`로 되어 있어서 실패를 막는 hard gate는 아니다. `.github/workflows/ci.yml` 기준 lint/typecheck는 아직 정보성에 가까운 부분이 있다.

## 6. 성숙도가 기능별로 다름

`longinus`, `occam`, `hades`, `eureka` 쪽은 코드와 테스트가 꽤 있는데, LLM commander 계열은 fake/double 기반 테스트와 일부 live backend 검증이 섞인 상태다. README도 Anthropic-specific `web_search`/cache 쪽은 아직 unverified라고 밝힌다.

## 7. 패키징 기대와 실제 repo 기능 사이에 간극이 있음

PyPI wheel은 `engine/` 중심이고, `install-skills`, Lean 검증, skill 문서까지 포함한 풀 기능은 소스 체크아웃과 submodule이 필요하다. `pip install`만으로 README 전체 경험이 다 되는 구조는 아니다.

## 8. 레포가 넓어서 유지보수 리스크가 있음

CLI, KG backend, formal proof, skill docs, MCP server, efficacy 실험, plugin manifest가 한 저장소에 같이 있다. 내부 일관성은 강하지만, 변경 blast radius가 커지고 신규 기여자가 어디를 고쳐야 하는지 헷갈릴 수 있다.

## 요약

프로세스 감사와 재현성 도구로는 강하지만, 독립 제품성, 온보딩, hard gate, 실행 엔진 완성도는 아직 실험 단계다.
