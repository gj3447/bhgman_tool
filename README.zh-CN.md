<div align="center">

# bhgman_tool

**为 Claude Code skill workflow 设计的 KG 锚定 agent orchestration toolkit。** Lean 4 验证的 confidence schema (定理 7 个,`sorry=0`) · KG↔code drift 审计 (Python + APOC trigger, 当前 warn-mode)。

<a href="https://github.com/gj3447/bhgman_tool/releases/download/v0.1.0-assets/hero.mp4"><img src="assets/hero.gif" width="600" alt="bhgman_tool hero (点击查看完整 mp4)"></a>

[English](README.md) | [한국어](README.ko-KR.md) | [中文](README.zh-CN.md) | [日本語](README.ja-JP.md)

[![Status: experimental](https://img.shields.io/badge/status-experimental-orange.svg?style=flat-square)](https://github.com/gj3447/bhgman_tool#status-experimental)
[![PyPI: not yet published](https://img.shields.io/badge/PyPI-not%20yet%20published-lightgrey.svg?style=flat-square)](docs/PYPI_PUBLISH_STATUS.md)
[![MIT License](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)
[![Lean 4](https://img.shields.io/badge/Lean-4.30.0-purple.svg?style=flat-square)](https://leanprover.github.io/)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg?style=flat-square)](https://www.python.org/)
[![Pytest engine](https://img.shields.io/badge/pytest%20engine-332%20PASS-green.svg?style=flat-square)](engine/longinus_drift_audit/tests/)
[![Pre-commit gate](https://img.shields.io/badge/pre--commit%20gate-1359%20tests-blue.svg?style=flat-square)](.pre-commit-config.yaml)

</div>

---

## 30 秒内可获得

```bash
# 尚未发布到 PyPI (publish 已延后) — 目前从源码安装:
git clone --recurse-submodules https://github.com/gj3447/bhgman_tool.git && cd bhgman_tool
uv run bhgman-tool install-skills    # 添加 /apt /prom /tpa /tlb /longinus /harness /jaebaeman 到 Claude Code
```

重启 Claude Code,在 chat 中:

```
/prom 16 "调研主题"
# parent 派发 16 个 haiku 并行 subagent,
# 各自返回 JSON,parent 批量写入 knowledge graph,
# 每个 claim 都带有 citation_url + 可复现的 cycle_id。
```

短暂的 subagent run 变为一等公民、可审计的 record。

---

## 为什么选择 bhgman_tool

- **可验证的 provenance** — 每次 subagent run 都产生 KG 锚定、sha256 基线的 `ResearchFinding` 节点,含 cycle_id、axis seed、citation URL、parent-lesson edge。重跑幂等。会话结束后 claim 仍在。
- **内建 drift 审计** — Longinus 7-layer 引用模型 + sha256 基线 + 正反向 orphan 扫描,在 drift 累积前发现 KG↔source-code 偏差。可作 CLI、pre-commit hook 或 CI job 运行。
- **即用的方法论 skill** — `bhgman-tool install-skills` 一行命令安装 APT/TPA cycle orchestrator + 5-tool 堆栈(Prometheus / Longinus / Naesengmoon / Jaebaeman / Harness)为 Claude Code slash command。无需自定义 MCP wiring。

---

## 安装

```bash
# ⚠ 尚未发布到 PyPI — 发布后才可用。在此之前请用上面的 git clone。
pip install bhgman_tool                       # 最小 (CLI + Pydantic 模型)
pip install "bhgman_tool[resolver]"           # + APT v27 resolver (Jinja2 + Neo4j)
pip install "bhgman_tool[gate]"               # + APT v27 gate endpoint (FastAPI + Redis)
pip install "bhgman_tool[all]"                # 全部
```

> **尚未发布到 PyPI**(无 token，已延后 — [docs/PYPI_PUBLISH_STATUS.md](docs/PYPI_PUBLISH_STATUS.md))。现在 `pip install bhgman_tool` 会失败；请从源码安装：`git clone --recurse-submodules https://github.com/gj3447/bhgman_tool.git`。发布后 PyPI wheel 仅包含 `engine/`。`install-skills` / `verify` / `version` subcommand 需要 source repo(`skills/` + `lean/`)同时存在 — 完整功能需 clone。详见 [docs/PYPI_PUBLISH.md](docs/PYPI_PUBLISH.md)。

### 已测效能 — 它*不会增加*什么 (外部 A/B, 2026-05-30)

由**外部 oracle**(植入的 ground truth / 实时 URL 检查 — *并非* bhgman 自己的 KG)评分、base-LLM arm 获得**同等工具预算**的可证伪 A/B:

- **确定性引擎不增加能力。** 在 sha256 drift 检测(含不可见的 zero-width / NBSP / homoglyph 编辑)与 KG 节点去重上,`longinus` / `occam` / `hades` 得 **F1 1.0 — 但用 `shasum`/推理的 base LLM 同样 1.0,在测试过的每个规模(直到 2000 文件)**。其价值是**确定性、穷尽性、幂等性与带签名的审计轨迹**,而非"比模型更聪明"。
- **Grounding 有效,但属 RAG 通用能力。** 喂入真实检索源把幻觉引用从 **42.9% 降到 0%** — 这是*检索*的价值,任何 LLM + 检索皆可获得;bhgman 只是封装,并非发明。
- **对抗式 verify-gate(`tlb`/naesengmoon)曾过度拒绝 — 已于 2026-05-30 修复。** 早期 prompt 会误标健全且充分 hedge 的工作(随模型规模上升 precision 降至 0)。一次校准修复(仅在*可命名*的违规时 FAIL,诚实的 hedge 通过)使其**与 base 模型打平,同时保持 100% 的过度声明捕获**。
- **组合涌现是治理,而非认知。** 7 军团长 contract + oracle-gate 流水线(`legion`)以可防篡改的 **HMAC** 审计轨迹确定性地捕获集成失败 — 这是 ad-hoc 编排默认不提供的 — 但它**不会**把推理提升到 base 模型之上。

**结论: bhgman_tool 是治理 / 审计层(可复现性、provenance、contract 强制、drift 检测),而非能力倍增器。请将其视为 *discipline*(纪律),而非 *intelligence*(智能)。**

---

## Quickstart (3 分钟)

```bash
git clone https://github.com/gj3447/bhgman_tool.git
cd bhgman_tool

# 1. engine — pytest 验证
cd engine/longinus_drift_audit
uv run --with pytest pytest tests/ -q          # 预期: 332 passed, 1 skipped, ~2s

# 2. Lean 4 — 形式验证 (可选)
cd ../../lean
lean Longinus_ConfidenceSchema_GraphifyAbsorbed.lean   # exit 0, sorry=0

# 3. Claude Code skill 安装
cd ../..
uv run bhgman-tool install-skills              # 默认: ~/.claude/skills

# 4. (仅贡献者) pre-commit ratchet
uvx pre-commit install --hook-type pre-commit --hook-type pre-push
```

重启 Claude Code,之后 `/apt` `/prom` `/tpa` `/tlb` `/longinus` `/harness` `/jaebaeman` 即可使用。完整指南: [docs/01-quickstart.md](docs/01-quickstart.md)。

```mermaid
flowchart LR
    A([git clone]) --> B[engine pytest<br/>332 PASS]
    B --> C{Lean 4?<br/>可选}
    C -- yes --> D[lean 验证<br/>sorry=0]
    C -- skip --> E[bhgman-tool install-skills]
    D --> E
    E --> F[重启 Claude Code]
    F --> G[/apt · /prom · /tpa · /tlb<br/>/longinus · /harness · /jaebaeman/]
    E -. 仅贡献者 .-> H[pre-commit install<br/>4-ratchet gate]

    classDef startNode fill:#dcfce7,stroke:#166534,stroke-width:2px,color:#1f2937
    classDef endNode fill:#fce7f3,stroke:#9d174d,stroke-width:2px,color:#1f2937
    classDef optNode fill:#fef9c3,stroke:#854d0e,stroke-width:1px,stroke-dasharray:5 5,color:#1f2937
    class A startNode
    class G endNode
    class H optNode
```

---

## 它是如何工作的

`/apt` 编排 5 阶段 cycle(SemanticAnchor → SemanticPyramid → SemanticTwin → SourceCodeWorld → MetaReview),在每个 gate 派发合适的工具。`/tpa` 是反向(代码 → 设计还原)。skill 派发图 + Harness 4-axis / 3-tier family 图详见 [docs/02-concepts/skills-graph.md](docs/02-concepts/skills-graph.md)、[docs/02-concepts/harness.md](docs/02-concepts/harness.md)。

---

## 复现 claim

README 中所有定量 claim 都附有一条命令验证器。在干净的 clone 上运行:

| Claim | Command | 检查什么 |
|---|---|---|
| `332 pytest PASS` (engine 子集) | `cd engine/longinus_drift_audit && uv run --with pytest pytest -q` | engine 子集 pass count + runtime |
| `1355 passed, 4 skipped` (整个 repo; 1359 collected) | `uvx pre-commit run --all-files` (或在 root 运行 `pytest -q`) | 整个 repo pass count (4 skip = 无密钥 clone: 实-API smoke 3 + otel no-op 1) |
| `Lean 4: proof-position sorry=0` | `cd lean && for f in *.lean; do lean "$f" \|\| exit 1; done && grep -rEn '(:=\|by) +sorry' *.lean \| wc -l` | 14 个 standalone(Mathlib-free)文件构建 + 未完成证明数(= 0；树中所有 `sorry` 标记都在注释里） |
| `105 theorems` (整个 `lean/` 树；standalone 14 文件 89) | `grep -rcE '^(theorem\|lemma) ' lean/ \| awk -F: '{s+=$2} END{print s}'` | 顶级 theorem/lemma 声明数量 |
| `KG cycle reproducibility` | `bhgman-tool replay-cycle <cycle_id>` | 重跑 cycle 并 diff KG output |

**Goodhart 声明:** 这些脚本验证的是*指标值的可复现性*,不是*指标所要度量之物的有效性*。theorem count / sorry count / pytest count 都易受 Goodhart 法则影响 — 它们确认"这个数字在 clean clone 上稳定可达",而非"这个数字意味着系统是正确的"。有效性在于证明本体、测试主体、cycle 输出,不在 count 里。

---

## Documentation

- [docs/01-quickstart.md](docs/01-quickstart.md) — 完整 setup
- [docs/02-concepts/](docs/02-concepts/) — Harness、APT、TPA、5 武器
- [docs/04-references/related-work.md](docs/04-references/related-work.md) — 与相邻 OSS(LangGraph、CrewAI、ruflo)对比
- [docs/06-philosophy/](docs/06-philosophy/) — 概念本质层,以及本工具是从 SYMPOSIUM 十二使徒框架中分离出来的背景(可选阅读)

---

## Status: experimental

早期 adopter 阶段。API surface、skill contract、badge 数字均可能不经 deprecation cycle 而变更。production 用途请 pin specific commit (或 `pip install bhgman_tool==<version>`)。生成本 README 的 cycle (PROM 16 + 三层 Naesengmoon round-2) 在 project KG 中标记 `EXPLORATORY_NOT_CONFIRMATORY` — 详见 SYMPOSIUM monorepo 中 `THEORY/bhgman_tool_readme_design/PROM_16_REPORT.md`。

## Contributing

Pre-commit 4-ratchet gate 在每次 commit 运行 ruff lint+format / complexipy ≤15 / deptry / 1359 个 pytest,每次 push 运行 lychee 链接检查。安装: `uvx pre-commit install --hook-type pre-commit --hook-type pre-push`。

---

## License

MIT. 作者: [gj3447@gmail.com](mailto:gj3447@gmail.com)。

---

<sub>在 SYMPOSIUM 十二使徒 / 5 武器框架内结晶。工具本身独立可用;概念本质层位于 [docs/06-philosophy/](docs/06-philosophy/)。KG provenance: `github-mirror-bhgman-2026-05-13` (`:PublicReferenceRepo:Canonical`, scope=tool-layer-only)。</sub>
