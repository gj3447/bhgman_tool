# SYMPOSIUM Skills

> 5 무기 (apt / harness / longinus / taliban / jaebaeman / prometheus) + APT/TPA cycle + 인프라 28-skill bundle.
> v30.0.0 / Merkle-gated MANIFEST / Cosign keyless attestation / Lakatos PROGRESSIVE_CONFIRMED.

## 외부 머신에서 1줄 설치

```bash
curl -sSL https://install.metahumotonic.com/install | bash
```

또는 GitHub raw 직접:

```bash
curl -sSL https://raw.githubusercontent.com/airobotics-inc/symposium-skills/main/install.sh | bash
```

manual 모드 (스크립트 미리 보고 설치):

```bash
git clone https://github.com/airobotics-inc/symposium-skills.git ~/.symposium
bash ~/.symposium/install.sh
```

설치 후:
- `~/.claude/skills/` 에 28 skill symlink
- `~/.claude/hooks/` 에 autoloop + apt-gate-check (옵션)
- `~/.claude/settings.json` deep-merge (deny 룰 + Stop hook)
- (옵션 `--with-kg`) `symposium-neo4j` docker + KG snapshot 자동 로드

Claude Code 재시작 → `/skills` 또는 직접 `/apt`, `/prom 16 "..."`, `/tlb <target>` 호출.

## 설치 옵션

```bash
# KG 까지 같이 (Neo4j docker 자동 기동)
curl -sSL https://install.metahumotonic.com/install | bash -s -- --with-kg

# non-interactive
curl -sSL https://install.metahumotonic.com/install | SYMPOSIUM_YES=1 bash

# dry-run (할 일만 출력)
curl -sSL https://install.metahumotonic.com/install | bash -s -- --dry-run

# 커스텀 prefix
curl -sSL https://install.metahumotonic.com/install | bash -s -- --prefix /opt/symposium

# 옵션 일부 끄기
curl -sSL https://install.metahumotonic.com/install | bash -s -- --no-hooks --no-settings
```

env var 동등 (curl-pipe 친화):

| env | 의미 | default |
|---|---|---|
| `SYMPOSIUM_GIT_URL` | repo URL | `https://github.com/airobotics-inc/symposium-skills.git` |
| `SYMPOSIUM_BRANCH` | 브랜치 | `main` |
| `SYMPOSIUM_PREFIX` | 설치 경로 | `$HOME/.symposium` |
| `SYMPOSIUM_KG` | 1=Neo4j 자동 | `0` |
| `SYMPOSIUM_KG_PASSWORD` | neo4j password | `symposium` |
| `SYMPOSIUM_NO_HOOKS` | 1=hook skip | `0` |
| `SYMPOSIUM_NO_SETTINGS` | 1=settings.json skip | `0` |
| `SYMPOSIUM_YES` | 1=non-interactive | `0` |
| `SYMPOSIUM_DRY_RUN` | 1=show only | `0` |

## metahumotonic.com vanity URL 라우팅

GitHub repo가 source of truth, `metahumotonic.com/install` 가 깔끔한 vanity URL.

### 옵션 A) Cloudflare Worker (가장 깔끔, 0초 캐시)

```js
// worker.js — Cloudflare Worker
export default {
  async fetch(req) {
    const url = new URL(req.url);
    if (url.pathname === "/install" || url.pathname === "/install.sh") {
      return fetch("https://raw.githubusercontent.com/airobotics-inc/symposium-skills/main/install.sh", {
        cf: { cacheTtl: 60 }
      });
    }
    return new Response("metahumotonic.com — see /install", { status: 404 });
  }
};
```

배포:
```bash
npx wrangler init metahumotonic && cp worker.js src/index.js
# wrangler.toml: name="metahumotonic", routes=["metahumotonic.com/*"]
npx wrangler deploy
```

### 옵션 B) Cloudflare Pages + `_redirects`

```
# public/_redirects
/install         https://raw.githubusercontent.com/airobotics-inc/symposium-skills/main/install.sh    200
/install.sh      https://raw.githubusercontent.com/airobotics-inc/symposium-skills/main/install.sh    200
/uninstall       https://raw.githubusercontent.com/airobotics-inc/symposium-skills/main/uninstall.sh  200
```

Cloudflare Pages 대시보드에 빈 repo 연결 + `metahumotonic.com` custom domain.

### 옵션 C) GitHub Pages + 커스텀 도메인

`USER.github.io/symposium-skills` 에 install.sh 정적 호스팅 + DNS CNAME → GitHub Pages.
캐시 ~10분, redirect-free 직접 서빙.

→ 셋 다 1줄 명령으로 끝남. **권장: Worker** (instant cache invalidation, 무료, 100k req/day).

## KG 동봉 (선택)

```bash
# 로컬 push 전
bash kg/dump.sh                   # → kg/snapshot.cypher
git add kg/snapshot.cypher && git commit -m "kg snapshot" && git push

# 외부 머신
curl -sSL https://install.metahumotonic.com/install | bash -s -- --with-kg
```

상세: [kg/README.md](kg/README.md).

## 업데이트

설치 후 update는 동일 명령 재실행 (idempotent):
```bash
curl -sSL https://install.metahumotonic.com/install | bash
# 또는 manual:
cd ~/.symposium && git pull && bash install.sh
```

## Uninstall

```bash
bash ~/.symposium/uninstall.sh
# 그 후 (선택)
rm -rf ~/.symposium
docker rm -f symposium-neo4j
```

## 검증 (설치 후)

```bash
ls ~/.claude/skills/                  # 28 symlink
jq '.hooks.Stop' ~/.claude/settings.json
echo '{"stop_hook_active":false,"session_id":"smoke"}' | ~/.claude/hooks/auto_continue.sh
# Claude Code 재시작 후
# /apt
# /prom 16 "Hello SYMPOSIUM"
```

## 보안 주의

- `curl ... | bash` 패턴은 **install.sh를 신뢰**한다는 가정. paranoid 모드: `git clone` 후 `cat install.sh` 읽고 실행.
- public repo면 `kg/snapshot.cypher` 가 KG 전체 노출 — 민감 정보 있으면 private repo 또는 별도 storage 사용.
- 설치는 `~/.claude/settings.json` 을 수정 (deep-merge). 기존 설정 보존되지만 backup 자동 생성됨.

## 구조

```
symposium-skills/
├── install.sh          # 외부 bootstrap (curl-pipe friendly)
├── uninstall.sh        # cleanup
├── README.md           # 이 파일
├── MANIFEST.json       # Merkle root + skillCount
├── SBOM.json           # supply chain
├── .claude-plugin/
│   └── marketplace.json
├── kg/                 # KG snapshot dump/restore
│   ├── dump.sh
│   ├── restore.sh
│   ├── snapshot.cypher (gitignored locally, committed for distribution)
│   └── README.md
├── bin/                # tooling (resolve_slot, longinus_sha256_daemon, ...)
├── apt/, apt-sa/, apt-sp/, ...      # APT cycle (6 skill)
├── tpa/, tpa-tcw/, tpa-st/, ...     # TPA cycle (5 skill)
├── prometheus/, taliban/, longinus/, harness/, jaebaeman/  # 5 무기
├── prom/, tlb/, 88-taliban/         # alias
└── ... (인프라 + meta)
```
