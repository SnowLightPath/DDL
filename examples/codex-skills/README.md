# DDL Skills for Codex

Example implementation of [Design-Doc Loop (DDL)](../../docs/en/design_philosophy.md) as OpenAI Codex skills.

## Installation

```bash
# Copy skills to your project
cp -r examples/codex-skills/draft .codex/skills/
cp -r examples/codex-skills/realize .codex/skills/
cp -r examples/codex-skills/reflect .codex/skills/
cp -r examples/codex-skills/commit .codex/skills/
cp -r examples/codex-skills/docs .codex/skills/
cp -r examples/codex-skills/refactoring .codex/skills/

# Copy AGENTS.md to project root
cp examples/codex-skills/AGENTS.md .
```

## Skills

### Core Loop

| Skill | Intent |
|-------|--------|
| `$draft` | Capture ideal experience before implementation |
| `$realize` | Manifest philosophy as working code |
| `$reflect` | Update documents based on implementation |

### Support Skills

| Skill | Intent |
|-------|--------|
| `$commit` | Record verified changes to repository |
| `$docs` | Audit and fix documentation quality |
| `$refactoring` | Audit and fix code quality |

## The Loop

```
      Draft
        ↓
Design Document ⇄ Code
   (Realize ↓  ↑ Reflect)
```

## Skill Structure

Every skill follows the same pattern:

1. **Phases** — ordered steps (INIT → READ → EXECUTE → VALIDATE)
2. **Detection Targets** — automated checks at phase boundaries (D1–D7 per skill)
3. **STOP gates** — mandatory human approval before mutating shared artifacts
4. **Constraints** — invariants that must never be violated

> **Note**: Codex processes all scopes **sequentially** (no parallel agent spawning). For parallel execution via Agent Teams (+++SWARM), see the [Claude Code commands](../claude-commands/).

## Philosophy

These skills are **optional tools**, not required process.

From design_philosophy.md:
> DDL is not a strict process—it's a collection of Intents.
> Tools can become shackles. If they obstruct the Intent, discard them.
