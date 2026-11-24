---
name: docs
description: Audit and fix documentation quality
argument-hint: "[path]"
disable-model-invocation: true
metadata:
  short-description: Documentation audit
---

# docs

Audit and fix documentation quality.

## Usage

- `/docs` — Audit all documentation
- `/docs <path>` — Audit specific document or directory

## Phases

### Phase 0: INIT

A command run from a user-level install follows the project's own copy when one exists (`.claude/skills/<name>/SKILL.md` in Claude Code, `.agents/skills/<name>/SKILL.md` in Codex, or the file the project's instruction file names as the command's source): the project's version is the one that runs.

1. Read the DDL protocol when it is not already in context: the project's copy when present (`.claude/skills/ddl-protocol/SKILL.md` in Claude Code, `.agents/skills/ddl-protocol/SKILL.md` in Codex, or the file the project's instruction file names as the protocol); otherwise the user-level copy (`$HOME/.claude/skills/ddl-protocol/SKILL.md` in Claude Code, `$HOME/.codex/skills/ddl-protocol/SKILL.md` in Codex). Follow its Start steps before continuing.
2. Read the project's guidance file when it is not already in context (the host loads `AGENTS.md` for Codex, and `CLAUDE.md` or `.claude/CLAUDE.md` for Claude Code, at session start), and any applicable command overlay.
3. Read `design.md` when it is not already in context — extract scopes, and documentation paths when design.md lists them
4. If no `design.md` exists → treat the repository as one scope
5. Discover all documentation files (`.md`, `.txt`, etc.), leaving out the notebook's history file
6. If a path is given, audit only that path and the scopes it covers

When a STOP needs a decision, read the Approval operation and its implementation for the current host before presenting the decision. When a SWARM fires, read the Parallel work operation and its implementation before fan-out.

### Phase 1: DISCOVER

+++SWARM: 2+ scopes in design.md

```
  team: docs-discover
  spawn: scanner-{scope}
  type: Explore
  max: 5
  batch: auto
  each: |
    Inventory documentation files and scan source for public APIs, exports, types in {scope}.
    Report findings to the lead when done.
  collect: lead collects discovery results into a unified context
```

### Phase 2: AUDIT

Lead integrates results and checks:

1. Cross-reference documentation against source code
2. Verify code examples compile/run conceptually
3. Check internal links and references

+++DETECT:
  D1: Stale Version — Doc references outdated version, API, or behavior
  D2: Broken Reference — Internal link or file path no longer exists
  D3: Missing Section — Public API or feature has no documentation
  D4: Stale Example — Code example doesn't match current implementation
  D5: Structure Mismatch — A doc lies outside the documentation paths, or lacks the headings, that design.md lists for it
  D6: Wrong Names — Doc uses names that don't exist in codebase
  D7: Design Change — a fix would change a Binding Decision, a principle or a promised behavior instead of matching the document to the code

D7 asks with options: apply the fix, leave it unapplied, or revise it.

+++STOP: on D7

### Phase 3: FIX

Read the Run operation and its implementation for the current host, then make a snapshot (the gate's `snapshot`) before the first fix.

+++DETECT:
  D8: No Snapshot — the snapshot cannot be made (no gate, no Git repository, or a failure)

D8 asks with options: apply without a snapshot, or apply nothing.

+++STOP: on D8

Apply every fix inside the documentation files Phase 0 found, and a D7 fix only as its answer chose.

+++SWARM: 2+ fixes across different files

```
  team: docs-fix
  spawn: writer-{scope}
  type: general-purpose
  max: 5
  batch: auto
  each: |
    Apply to the {scope} documentation the fixes listed in this prompt, and nothing else.
    Report completion to the lead when done.
  collect: lead verifies all fixes applied correctly
```

### Phase 4: VERIFY

Re-scan fixed files to confirm:

1. No new Detection Targets introduced
2. All fixes applied correctly
3. Summarize final state

### Phase 5: REPORT

+++STOP: always

Report what was applied; ask nothing (Approval Exceptions: informational).

+++Report:
Outcome: the applied fixes, numbered with stable IDs, each with its file and correction, and the snapshot ref that undoes them.
Consequence: the fixes stand in the working tree, uncommitted; restoring the snapshot undoes them all.
Review detail: each fix ID, file/line, detection type, finding, and correction; each finding left unapplied, with its reason; the final state VERIFY found.
Choices: none; the report asks nothing. With no findings, state that nothing changed.

## Constraints

+++NEVER: Apply a fix outside the documentation files Phase 0 found, or a Binding Decision, principle or behavior change unasked
+++NEVER: Hardcode scopes or paths — they come from design.md
+++NEVER: Execute code examples — check conceptually only
