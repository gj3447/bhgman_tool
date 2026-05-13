---
name: skill-creator
kg_ref: ATOM_Skill_skill_creator
version: "1.0.0"
channel: stable
description: >
  Anthropic's official Skill Creator — develop, test, and refine Claude skills through iterative workflow.
  Creates SKILL.md files with frontmatter, instructions, examples, and references structure.
  Invoke when: "skill 만들어줘", "새 skill 생성", "SKILL.md 작성", "skill 업데이트",
  "slash command 만들기", "create skill", "build skill".
  Source: https://github.com/anthropics/skills/tree/main/skills/skill-creator
---

# Skill Creator Guide

The Skill Creator is Anthropic's tool for developing, testing, and refining Claude skills through an iterative workflow.

## Core Process

The fundamental loop:

1. **Capturing Intent** — Understand what the skill should do, when it triggers, expected outputs, and whether test cases are needed
2. **Drafting** — Write the SKILL.md with clear instructions and examples
3. **Testing** — Run 2-3 realistic test prompts with and without the skill
4. **Evaluation** — Use the eval viewer to let users review outputs and provide feedback
5. **Iteration** — Improve the skill based on feedback and repeat

## Skill Structure

```
~/.claude/skills/{skill-name}/
├── SKILL.md              ← Required. Core instructions. <500 lines.
├── references/            ← Optional. Detailed docs.
│   └── {topic}.md
├── evals/                 ← Optional. Test cases.
│   └── evals.json
└── scripts/               ← Optional. Helper scripts.
```

### SKILL.md Frontmatter

```yaml
---
name: my-skill              # kebab-case, max 64 chars. Becomes /slash-command.
description: >               # CRITICAL: Claude uses this to decide when to invoke.
  What this skill does.       # Max ~200 chars effective.
  Invoke when: trigger keywords.
---
```

**Optional frontmatter fields:**

| Field | Default | Description |
|-------|---------|-------------|
| `disable-model-invocation` | false | true = manual `/skill` only |
| `user-invocable` | true | false = Claude auto-invoke only |
| `allowed-tools` | none | Auto-approve tools: `Read, Bash(git *)` |
| `context` | inline | `fork` = isolated subagent |
| `agent` | general-purpose | Agent type when `context: fork` |
| `model` | inherited | Specific model override |
| `effort` | inherited | low/medium/high/max |

## Key Principles

### Progressive Disclosure
Skills load metadata first (~100 words), then SKILL.md body (<500 lines), with bundled resources as needed. Keep SKILL.md lean; move details to `references/`.

### Generalization Over Overfitting
When iterating, avoid changes tailored only to test examples. Branch out with different metaphors and patterns.

### Explanation > Rigid Rules
Rather than all-caps directives like "ALWAYS", explain *why* something matters. Models apply reasoning beyond rote instructions.

### Lean Prompts
Remove instructions that aren't productive. Watch transcripts for wasted effort.

## Drafting the Skill

### Step 1: Capture Intent

Ask:
- What does this skill do?
- When should it trigger? (keywords)
- What tools does it need?
- What does good output look like?
- Are there edge cases?

### Step 2: Write SKILL.md

```markdown
---
name: example-skill
description: >
  Does X when Y. Invoke when: "keyword1", "keyword2", "keyword3".
---

# Skill Title

Brief description of what this skill does.

## Instructions

Step-by-step instructions Claude follows.

## Examples

Concrete examples of input → output.

## What NOT to do

Common mistakes to avoid.
```

### Step 3: Quality Checklist

- [ ] `name` matches directory name (kebab-case)
- [ ] `description` has 3+ trigger keywords
- [ ] `description` includes "Invoke when:" pattern
- [ ] Body ≤ 500 lines
- [ ] Step-by-step instructions present
- [ ] Next skill call noted (if chained)
- [ ] "What NOT to do" section present
- [ ] Code/Cypher examples are copy-paste ready

## Testing Workflow

1. Save test cases to `evals/evals.json` (no assertions initially)
2. Spawn with-skill and baseline runs in parallel
3. Draft quantitative assertions explaining what each checks
4. Use `eval-viewer/generate_review.py` to show results before iterating

## Description Optimization

After the skill is complete, optimize its description for triggering accuracy:

1. Create 20 eval queries — 10 that should trigger, 10 that should NOT
2. Run the automated loop with `scripts/run_loop`
3. Iterate description until trigger accuracy is high

## Skill Chaining

### Linear Chain (APT example)
```
/apt → /apt-sa → /apt-sp → /apt-st → /apt-scw
```

Each skill's last section should point to the next:
```markdown
## Next Step
SP decomposition complete. Run `/apt-st` to define Contracts.
```

### Conditional Routing
```
/apt → Phase Detection
  ├── PH3 → /apt-sp
  ├── PH4 → /apt-st
  └── PH5 → /apt-scw
```

## Arguments & Dynamic Context

### Arguments
```markdown
Target: $ARGUMENTS
```
Usage: `/my-skill some-argument`

### Dynamic Context (preprocessed)
```markdown
Current status: !`git status`
Recent log: !`git log --oneline -5`
```
`!` backtick executes before skill loads — result injected into prompt.

## Anti-Patterns

| Anti-pattern | Fix |
|-------------|-----|
| SKILL.md > 500 lines | Move to references/ |
| Vague description | Add "Invoke when:" + 3 keywords |
| Hardcoded paths | Use $ARGUMENTS or config |
| No next-step guidance | Add "Next Step" section |
| No testing | Create evals/evals.json |
| ALL-CAPS rules | Explain why instead |

# KG: ATOM_Skill_skill_creator
