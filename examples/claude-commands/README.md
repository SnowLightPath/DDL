# DDL Commands

Example implementation of [Design-Doc Loop (DDL)](../../docs/en/design_philosophy.md) as Claude Code custom slash commands.

## Installation

```bash
cp examples/claude-commands/CLAUDE.md .claude/
cp examples/claude-commands/{draft,realize,reflect,validate,commit,docs,refactoring,DDL-PROTOCOL-SKILL}.md .claude/commands/
```

## Commands

### Core Loop

| Command | Intent |
|---------|--------|
| `/draft` | Capture ideal experience, and the decisions and outlook it depends on, before implementation |
| `/realize` | Manifest philosophy as working code |
| `/reflect` | Update documents based on implementation |

### Support Commands

| Command | Intent |
|---------|--------|
| `/validate` | Run mechanical validation per scope (lint/test/build) |
| `/commit` | Record verified changes to repository |
| `/docs` | Audit and fix documentation quality |
| `/refactoring` | Audit and fix code quality |

## The Loop

```
      Draft
        ↓
Design Document ⇄ Code
   (Realize ↓  ↑ Reflect)
```

## Command Structure

Every command follows the DDL-PROTOCOL defined in `DDL-PROTOCOL-SKILL.md`:

1. **Phases** — ordered steps (INIT → READ → EXECUTE → VALIDATE)
2. **+++DETECT** — automated checks at phase boundaries (D1, D2, … per command)
3. **+++SWARM** — parallel workers per scope (`team:`, `spawn:`, `type:`, `each:`, `collect:`) when 2+ scopes exist, run with the runtime's own mechanism (protocol §2.5)
4. **+++STOP** — mandatory human approval before mutating shared artifacts; the agent ends its turn and waits (protocol §1.5)
5. **+++NEVER** — invariants that must never be violated

## design.md Sections

`/draft` writes these sections into `design.md` when the draft needs them, and Experience comes first:

1. **Experience** — consumer-side usage with inputs, outputs, and error / empty / boundary states
2. **Binding Decisions** — technology the Experience depends on (Decision, Why it binds, Source); only the human binds
3. **Direction** — non-binding outlook: stages, parallel lanes, what the human sees, and human gates
4. **Acceptance Gates** — mechanical gates and human gates that define done

See `DDL-PROTOCOL-SKILL.md` §3.

## Philosophy

These commands are **optional tools**, not required process.

From design_philosophy.md:
> DDL is not a rigid process—it's a collection of desired designs.
> DDL documents are not final artifacts—they're temporary notes until the design is reflected in code.
