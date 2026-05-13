# bhgman_tool — Claude Code Plugin

> Install via Claude Code plugin marketplace. One-line setup.

---

## Quickstart

```bash
# Add the marketplace
/plugin marketplace add gj3447/bhgman_tool

# Install core (foundation, required by others)
/plugin install bhgman-core@bhgman_tool

# Install individual sub-plugins
/plugin install bhgman-longinus@bhgman_tool
/plugin install bhgman-taliban@bhgman_tool
/plugin install bhgman-prometheus@bhgman_tool
/plugin install bhgman-jaebaeman@bhgman_tool

# Or install full cycles
/plugin install bhgman-apt-cycle@bhgman_tool  # forward methodology (auto-installs deps)
/plugin install bhgman-tpa-cycle@bhgman_tool  # reverse methodology
```

After installation, in chat:
```
/harness <agent>     — diagnose agent placement in 3-tier family
/longinus            — KG ↔ code reference audit
/prom <N> <topic>    — N parallel subagent research cycle
/tlb <target>        — adversarial validation
/jaebaeman           — SOP subagent orchestration
/apt                 — full forward cycle
/tpa <path>          — full reverse cycle
```

---

## Plugin dependency graph

```
bhgman-core (Harness foundation)
   ├── bhgman-longinus      (KG ↔ code binding)
   ├── bhgman-taliban       (adversarial validation)
   ├── bhgman-jaebaeman     (SOP — subagent orchestration)
   └── bhgman-prometheus    (knowledge-action spiral)
        └── (depends on jaebaeman)

bhgman-apt-cycle    ← depends on core + longinus + taliban + jaebaeman
bhgman-tpa-cycle    ← depends on core + longinus + taliban + jaebaeman
```

→ `bhgman-core` 만 설치하면 `/harness` 만 사용. 나머지는 별도 설치. APT/TPA cycle 은 deps 자동 해소.

---

## 7 plugins overview

| Plugin | Commands | External canonical grounding |
|---|---|---|
| **bhgman-core** | `/harness` | Lawvere 1969 / Yanofsky 2003 / Cherns 1976 / Smith 1984 |
| **bhgman-longinus** | `/longinus` | Foster-Pierce-Walker 2007 / Frege 1892 / Sanfeliu-Fu 1983 / graphify 2026 |
| **bhgman-prometheus** | `/prometheus`, `/prom` | Hegel Phenomenology / OODA (Boyd) / Lean Startup (Ries) |
| **bhgman-taliban** | `/taliban`, `/tlb`, `/88-taliban` | GAN (Goodfellow 2014) / Popper / Goodhart 1975 |
| **bhgman-jaebaeman** | `/jaebaeman` | Holacracy (Robertson 2015) / Wooldridge BDI (contrast) |
| **bhgman-apt-cycle** | `/apt`, `/apt-sa`, `/apt-sp`, `/apt-st`, `/apt-scw`, `/apt-meta-review`, `/apt-cleanup` | TDD (Beck) / OODA / Lakatos / Robert Martin Package Principles |
| **bhgman-tpa-cycle** | `/tpa`, `/tpa-tcw`, `/tpa-st`, `/tpa-sp`, `/tpa-ta` | Chikofsky-Cross 1990 / GoF DesignPatterns / Longinus 5 drift |

---

## Manual install (without plugin marketplace)

```bash
git clone https://github.com/gj3447/bhgman_tool.git
cp -R bhgman_tool/skills/* ~/.claude/skills/
# Restart Claude Code
```

This gives access to all 21 skill commands without going through the plugin marketplace.

---

## License

MIT.

---

## See also

- [Project README](../README.md)
- [docs/01-quickstart.md](../docs/01-quickstart.md)
- [docs/02-concepts/](../docs/02-concepts/)
- [docs/03-tutorials/](../docs/03-tutorials/)
