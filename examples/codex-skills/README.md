# DDL Skills for Codex

Example implementation of [Design-Doc Loop (DDL)](../../docs/en/design_philosophy.md) as OpenAI Codex skills.

## Installation

```bash
# Copy skills to your project
cp -r examples/codex-skills/draft .codex/skills/
cp -r examples/codex-skills/realize .codex/skills/
cp -r examples/codex-skills/reflect .codex/skills/

# Copy AGENTS.md to project root
cp examples/codex-skills/AGENTS.md .
```

## Skills

| Skill | Intent |
|-------|--------|
| `$draft` | Capture ideal experience before implementation |
| `$realize` | Manifest philosophy as working code |
| `$reflect` | Update documents based on implementation |

## The Loop

```
      Draft
        ↓
Design Document ⇄ Code
   (Realize ↓  ↑ Reflect)
```

## Philosophy

These skills are **optional tools**, not required process.

From design_philosophy.md:
> DDL is not a strict process—it's a collection of Intents.
> Tools can become shackles. If they obstruct the Intent, discard them.
