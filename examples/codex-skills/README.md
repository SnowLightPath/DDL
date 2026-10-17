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
| `$draft` | Write the user-side experience first, with the decisions and outlook it depends on |
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
2. **Detection Targets** — automated checks at phase boundaries (D1, D2, … per skill)
3. **+++SWARM** — parallel agents per scope via `.codex/config.toml` roles, one by one without multi-agent
4. **STOP gates** — mandatory human approval before mutating shared artifacts; the agent ends its turn and waits
5. **Constraints** — invariants that must never be violated

> **Note**: With [multi-agent enabled](https://developers.openai.com/codex/multi-agent/), `+++SWARM` spawns parallel agents via `.codex/config.toml` roles. Without multi-agent, scopes are processed sequentially.

## DESIGN.md Sections

`$draft` writes these sections into `DESIGN.md` when the draft needs them. Each is optional, and Experience comes first:

1. **Experience** — consumer-side usage with inputs, outputs, and error / empty / boundary states
2. **Binding Decisions** — technology the Experience depends on (Decision, Why it binds, Source); only the human binds
3. **Direction** — non-binding outlook: stages, parallel lanes, what the human sees, and human gates
4. **Acceptance Gates** — mechanical gates and human gates that define done

Details are in the DESIGN.md Sections of `AGENTS.md`.

## Philosophy

These skills are **optional tools**, not required process.

From design_philosophy.md:
> DDL is not a rigid process—it's a collection of desired designs.
> DDL documents are not final artifacts—they're temporary notes until the design is reflected in code.
