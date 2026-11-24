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

1. Read the DDL protocol when it is not already in context: the project's copy when present (`.claude/skills/ddl-protocol/SKILL.md` in Claude Code, `.agents/skills/ddl-protocol/SKILL.md` in Codex, or the file the project's instruction file names as the protocol); otherwise the user-level copy (`$HOME/.claude/skills/ddl-protocol/SKILL.md` in Claude Code, `$HOME/.codex/skills/ddl-protocol/SKILL.md` in Codex). Follow its Start steps before continuing.
2. Read the project's guidance file when it is not already in context (the host loads `AGENTS.md` for Codex, and `CLAUDE.md` or `.claude/CLAUDE.md` for Claude Code, at session start), and any applicable command overlay.
3. Read `design.md` when it is not already in context — extract the document pairs (scopes with language counterparts) and the glossary the project names
4. If no `design.md` exists → work on the given path alone: pair the documents by their language directories, without a glossary or protected terms
5. Discover all `en/` and `ja/` counterparts in target path

When a STOP needs a decision, read the Approval operation and its implementation for the current host before presenting the decision. When a SWARM fires, read the Parallel work operation and its implementation before fan-out.

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
  D6: Design Change — the versions state a Binding Decision, a principle or a promised behavior differently, so aligning them changes what one of them promises

D6 asks with options: align to one version, leave the pair, or revise the proposal.

+++STOP: on D6

### Phase 3: APPLY

Read the Run operation and its implementation for the current host, then make a snapshot (the gate's `snapshot`) before the first change.

+++DETECT:
  D7: No Snapshot — the snapshot cannot be made (no gate, no Git repository, or a failure)

D7 asks with options: apply without a snapshot, or apply nothing.

+++STOP: on D7

Apply every proposal to BOTH language versions of the pairs Phase 0 found, and a D6 proposal only as its answer chose.

+++SWARM: 2+ document pairs with changes

```
  team: resonate-apply
  spawn: writer-{scope}
  type: general-purpose
  max: 5
  batch: auto
  each: |
    Apply to both language versions of {scope} the changes listed in this prompt, and nothing else.
    Report completion to the lead when done.
  collect: lead verifies changes applied to both language versions
```

### Phase 4: REPORT

+++STOP: always

Report what was applied; ask nothing (Approval Exceptions: informational).

+++Report:
Outcome: the applied proposals, numbered with stable IDs, each with its section and the nuance it restores, and the snapshot ref that undoes them.
Consequence: both language versions hold the changes in the working tree, uncommitted; restoring the snapshot undoes them all.
Review detail: each proposal ID, section, detection type, the EN/JA text before and after; what changed in each language; each finding left unapplied, with its reason; any sections that still need human review.
Choices: none; the report asks nothing. With no dissonance, state that nothing changed.

## Constraints

+++NEVER: Treat either language as strictly source — proposals refine BOTH versions
+++NEVER: Apply a change outside the document pairs Phase 0 found, or a Binding Decision, principle or behavior change unasked
+++NEVER: Override domain authority — English for technical precision, Japanese for cultural nuance
