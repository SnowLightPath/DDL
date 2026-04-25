# DDL Skills for Codex

Example implementation of [Design-Doc Loop (DDL)](../../docs/en/design_philosophy.md) as OpenAI Codex skills.

## Installation

```bash
# Copy everything to your project root
cp -r examples/codex-skills/.agents .
cp -r examples/codex-skills/.codex .
cp examples/codex-skills/AGENTS.md .

# Create your design document
touch DESIGN.md
```

The template mirrors Codex's directory convention — no rearranging needed.

## Usage

```bash
# Start Codex
codex

# Enable multi-agent (optional, for parallel +++SWARM)
/experimental
# → enable multi_agent

# Invoke a skill (type $ to see available skills)
$draft
$realize
$reflect
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
| `$validate` | Run mechanical validation per scope (lint/test/build) |
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

> **Note**: With [multi-agent enabled](https://developers.openai.com/codex/multi-agent/), `+++SWARM` spawns parallel agents via `.codex/config.toml` roles. Without multi-agent, scopes are processed sequentially.

## Philosophy

These skills are **optional tools**, not required process.

From design_philosophy.md:
> DDL is not a strict process—it's a collection of Intents.
> Tools can become shackles. If they obstruct the Intent, discard them.
