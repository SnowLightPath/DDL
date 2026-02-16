# DDL Commands

Example implementation of [Design-Doc Loop (DDL)](../../docs/en/design_philosophy.md) as Claude Code custom slash commands.

## Installation

```bash
cp examples/claude-commands/CLAUDE.md .claude/
cp examples/claude-commands/*.md .claude/commands/
```

## Commands

### Core Loop

| Command | Intent |
|---------|--------|
| `/draft` | Capture ideal experience before implementation |
| `/realize` | Manifest philosophy as working code |
| `/reflect` | Update documents based on implementation |

### Support Commands

| Command | Intent |
|---------|--------|
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

Every command follows the same pattern:

1. **Phases** — ordered steps (INIT → READ → EXECUTE → VALIDATE)
2. **+++DETECT** — automated checks at phase boundaries (D1–D7 per command)
3. **+++SWARM** — parallel agent execution when 2+ scopes exist
4. **+++STOP** — mandatory human approval before mutating shared artifacts
5. **+++NEVER** — invariants that must never be violated

## Philosophy

These commands are **optional tools**, not required process.

From design_philosophy.md:
> DDL is not a strict process—it's a collection of Intents.
> Tools can become shackles. If they obstruct the Intent, discard them.
