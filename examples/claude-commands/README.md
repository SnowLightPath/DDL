# DDL Commands

Example implementation of [Design-Doc Loop (DDL)](../../docs/en/design_philosophy.md) as Claude Code custom slash commands.

## Installation

```bash
cp examples/claude-commands/CLAUDE.md .claude/
cp examples/claude-commands/draft.md .claude/commands/
cp examples/claude-commands/realize.md .claude/commands/
cp examples/claude-commands/reflect.md .claude/commands/
```

## Commands

| Command | Intent |
|---------|--------|
| `/draft` | Capture ideal experience before implementation |
| `/realize` | Manifest philosophy as working code |
| `/reflect` | Update documents based on implementation |

## The Loop

```
      Draft
        ↓
Design Document ⇄ Code
   (Realize ↓  ↑ Reflect)
```

## Philosophy

These commands are **optional tools**, not required process.

From design_philosophy.md:
> DDL is not a strict process—it's a collection of Intents.
> Tools can become shackles. If they obstruct the Intent, discard them.
