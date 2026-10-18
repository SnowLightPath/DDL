---
name: resonate
description: Synchronize English and Japanese versions of the documentation
argument-hint: "[path]"
disable-model-invocation: true
metadata:
  short-description: Sync en/ja docs
---

# resonate

Synchronize English and Japanese versions.

## Usage

- `/resonate` — Synchronize all multilingual document pairs
- `/resonate <path>` — Synchronize specific file or directory

## Phases

### Phase 0: INIT

A command run from a user-level install follows the project's own copy when one exists (`.claude/skills/<name>/SKILL.md` in Claude Code, `.agents/skills/<name>/SKILL.md` in Codex, or the file the project's instruction file names as the command's source): the project's version is the one that runs.

1. Read the DDL protocol when it is not already in context: the project's copy when present (`.claude/skills/ddl-protocol/SKILL.md` in Claude Code, `.agents/skills/ddl-protocol/SKILL.md` in Codex, or the file the project's instruction file names as the protocol); otherwise the user-level copy (`$HOME/.claude/skills/ddl-protocol/SKILL.md` in Claude Code, `$HOME/.codex/skills/ddl-protocol/SKILL.md` in Codex).
2. Read project-local runtime guidance when it is not already in context (the runtime loads `AGENTS.md` for Codex, and `CLAUDE.md` or `.claude/CLAUDE.md` for Claude Code, at session start), and any applicable command overlay.
3. `design.md` is in context from session start; this command extracts nothing from it, because its units are document pairs
4. Discover all `en/` and `ja/` counterparts in target path

### Phase 1: READ

+++SWARM: 2+ document pairs

```
  team: resonate-read
  spawn: reader-{scope}
  type: Explore
  max: 5
  batch: auto
  each: |
    Parse both language versions of {scope}, extract section structure and content.
    Report findings to the lead when done.
  collect: lead collects parsed structures into a unified context
```

### Phase 2: COMPARE

Section-by-section comparison across language pairs:

1. Align sections by heading structure
2. Identify dissonance per section

+++DETECT:
  D1: Missing Nuance — One version carries meaning the other lacks
  D2: Different Emphasis — The same section differs between languages in paragraph count, list items, or emphasis markers
  D3: Structural Mismatch — Heading hierarchy or section order differs
  D4: Untranslated Section — Section exists in one language but not the other
  D5: Stale Pair — One language version changed after the pair was last synchronized

### Phase 3: REPORT

+++STOP: always

Do NOT apply changes without approval.

+++Report:
| # | Section | Type | EN | JA | Proposal |
|---|---------|------|----|----|----------|

Wait for user to approve, reject, or modify each proposal.

### Phase 4: APPLY

**Pre-condition.** Enter this phase only after explicit user approval at the Phase 3 STOP gate (per §1.5 of the protocol). If the most recent user message is not an approval token, return to Phase 3 and re-emit the report.

Apply approved changes to BOTH language versions.

+++SWARM: 2+ document pairs with approved changes

```
  team: resonate-apply
  spawn: writer-{scope}
  type: general-purpose
  max: 5
  batch: auto
  each: |
    Apply to both language versions of {scope} the approved changes listed in this prompt, and nothing else.
    Report completion to the lead when done.
  collect: lead verifies changes applied to both language versions
```

After applying:
1. Summarize what changed in each language
2. List any sections that still need human review

## Constraints

+++NEVER: Treat either language as strictly source — proposals refine BOTH versions
+++NEVER: Auto-apply changes — +++STOP is mandatory
+++NEVER: Override domain authority — English for technical precision, Japanese for cultural nuance

## Example

```
Human: /resonate docs/

Assistant: Comparing en/ and ja/...

+++DDL_REPORT

| # | Section | Type | EN | JA | Proposal |
|---|---------|------|----|----|----------|
| 1 | Intent | D1 Missing Nuance | "share design principles across sessions, agents, and harnesses" | "設計方針を共有し続ける" | JA: add 「セッション、エージェント、ハーネスをまたいで」; EN: keep |

Approve, reject, or modify proposal 1.
```
