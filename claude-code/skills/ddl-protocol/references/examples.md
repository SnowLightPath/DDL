# Examples

Read only when a string in a reference's Formats is not enough to write a report, a notebook row, a SWARM block or a command; nothing here is executed, and the command template is the single source of the shared Phase 0 lines.

## Command template

The complete command in its Claude Code form; its Phase 0 sentence and lines 1 and 2 are the shared lines every command keeps verbatim:

````markdown
---
name: command-name
description: One-line intent
argument-hint: "[arg]"
disable-model-invocation: true
metadata:
  short-description: Short name
---

# command-name

One-line intent.

## Usage

- `/command-name` — default behavior
- `/command-name <arg>` — behavior with an argument

## Phases

### Phase 0: INIT

A command run from a user-level install follows the project's own copy when one exists (`.claude/skills/<name>/SKILL.md` in Claude Code, `.agents/skills/<name>/SKILL.md` in Codex, or the file the project's instruction file names as the command's source): the project's version is the one that runs.

1. Read the DDL protocol when it is not already in context: the project's copy when present (`.claude/skills/ddl-protocol/SKILL.md` in Claude Code, `.agents/skills/ddl-protocol/SKILL.md` in Codex, or the file the project's instruction file names as the protocol); otherwise the user-level copy (`$HOME/.claude/skills/ddl-protocol/SKILL.md` in Claude Code, `$HOME/.codex/skills/ddl-protocol/SKILL.md` in Codex). Complete its Start procedure before continuing.
2. Read project-local runtime guidance when it is not already in context (the runtime loads `AGENTS.md` for Codex, and `CLAUDE.md` or `.claude/CLAUDE.md` for Claude Code, at session start), and any applicable command overlay.
3. Read `design.md` when it is not already in context — extract relevant items
4. If no `design.md` → fallback behavior

### Phase 1: SURVEY

+++SWARM: 2+ scopes in design.md

```
  team: command-survey
  spawn: reader-{scope}
  type: Explore
  max: 5
  batch: auto
  each: |
    Scan {scope} for the items this command needs.
    Report findings to the lead when done.
  collect: lead merges all scope findings
```

### Phase 2: WORK

Core activity here.

+++DETECT:
  D1: name — trigger condition
  D2: name — trigger condition
  D3: name — trigger condition
  D4: name — trigger condition
  D5: name — trigger condition

### Phase 3: REPORT

+++STOP: always

Emit `+++DDL_REPORT`, then the report below; follow Approval to present it and ask.

+++Report:
Decision: {approve the complete current review set, select or revise it, or hold}
Recommendation: {preferred action, its reason, and any material downside or unknown}
Consequence: {what each selection authorizes or changes}
Review detail: {the complete evidence this command requires, accessible before approval}
Choices: {one batch approval interaction through Approval; item selection only when requested}

### Phase 4: EXECUTE

**Pre-condition.** Enter this phase only after explicit user approval of its scope at the Phase 3 STOP gate (per Approval). If the actual answer does not authorize this work, return to Phase 3 and re-present the current decision.

+++SWARM: 2+ approved changes across scopes

```
  team: command-execute
  spawn: writer-{scope}
  type: general-purpose
  max: 5
  batch: auto
  each: |
    Apply to {scope} the approved changes listed in this prompt, and nothing else.
    Report completion to the lead when done.
  collect: lead verifies all changes applied
```

### Phase 5: VERIFY

Re-scan the changed scopes and summarize. Name a next command only when work this command cannot do itself remains, with the reason.

## Constraints

+++NEVER: prohibition
+++NEVER: prohibition
+++NEVER: prohibition
````

## Approval report

A decision report at a STOP; the native question that follows carries its three actions:

```
+++DDL_REPORT
Decision: apply the three documentation fixes the Close scan found, or hold.
Recommendation: approve all. R1–R3 are independent and each restores a name or
version the change set already uses; nothing else under docs/ changes.
  R1 README.md — the install section names version 0.7.0 instead of 0.6.0
  R2 docs/en/extended.md — link to the renamed references/close.md
  R3 docs/ja/extended.md — the same link in the Japanese counterpart
Consequence: approve all applies R1–R3 to the working tree; they join the change
set the Git review will show. Nothing is committed here. Gate S2 (human: the
three screen states) is ready and named here; approve all passes it.
Review detail: the three diffs follow this report; `git diff docs/` shows them
in full; the S2 screenshots are under review/s2/.
Choices: approve all (R1–R3, pass S2) / select a subset or request changes /
hold (nothing applied, S2 stays open)
```

## Close report

The final report of `/realize` after the commit:

```
+++DDL_REPORT
Outcome: recorded 4f2c9e1 on feature/search-states: the three screen states,
the S0–S1 outcomes in design.md, the README section "States" and its Japanese
counterpart. Nothing remains.
Recommendation: none after a Close.
Consequence: no further action; the branch holds the reviewed set, unpushed.
Review detail: src/states/* implemented; every Binding Decision honored, none
changed; S0 and S1 retired with their outcome and their Approved plan lines
deleted; `npm test` passed; S1 passed 2026-10-21 by human approval; the Close
changes are in the same commit; no detection fired.
```

## Git review request

The helper's input for a commit and a push reviewed together; one submitted answer records the commit and sends the push:

```json
{
  "language": "en",
  "operations": [
    {"cwd": "/path/to/repository", "command": "git commit --cleanup=verbatim -F /path/to/message.txt"},
    {"cwd": "/path/to/repository", "command": "git push origin main"}
  ]
}
```

## Notebook tables

The notebook sections of one project at two moments.

Under `## Binding Decisions`, as `/draft` saved them (2026-10-17):

```markdown
| Decision | Why it binds | Source |
|----------|--------------|--------|
| Next.js App Router | Answers stream in while they are written, and per-route loading and error states are the core of the Experience | "I want to build it with Next.js", "Yes, App Router" (2026-10-17) |

Unbound: Language — options TypeScript / JavaScript (delegated to /realize)
```

Under `## Direction`, as it reads after `/realize` passed stage S1 (2026-10-21):

```markdown
| Stage | Work (parallel lanes) | Human sees | Gate |
|-------|-----------------------|------------|------|
| S0 | Settle the search API as a CLI | sample CLI output | `npm test`, passed 2026-10-20 |
| S1 | Three screen states (normal, empty, failure), one lane each | three screenshots | human approval, approved in advance (2026-10-20), passed 2026-10-21 |
| Close | reflect, docs, resonate, validate, Git review of the whole change set | final diff and the summary of design.md changes | Git review |

Approved plan (2026-10-20): files `cli/search.ts`, `app/search/**`; approach: CLI first, then the three states as three lanes; Unbound choices made: Language → TypeScript
```

Under `## Acceptance Gates`, at the same moment:

```markdown
- `npm test` → all suites pass
- `npm run build` → exit 0 and no type errors, passed 2026-10-21
- human: the three screen states match the Experience, approved in advance (2026-10-20), passed 2026-10-21
```
