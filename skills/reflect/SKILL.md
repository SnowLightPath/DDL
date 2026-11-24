---
name: reflect
description: Update documents based on implementation results
argument-hint: "[path]"
disable-model-invocation: true
metadata:
  short-description: Code to Design
---

# reflect

Detect divergence between implementation and design.md, then reconcile.

## Usage

- `/reflect` — Check entire project alignment
- `/reflect <path>` — Check specific file/directory

## Phases

### Phase 0: INIT

A command run from a user-level install follows the project's own copy when one exists (`.claude/skills/<name>/SKILL.md` in Claude Code, `.agents/skills/<name>/SKILL.md` in Codex, or the file the project's instruction file names as the command's source): the project's version is the one that runs.

1. Read the DDL protocol when it is not already in context: the project's copy when present (`.claude/skills/ddl-protocol/SKILL.md` in Claude Code, `.agents/skills/ddl-protocol/SKILL.md` in Codex, or the file the project's instruction file names as the protocol); otherwise the user-level copy (`$HOME/.claude/skills/ddl-protocol/SKILL.md` in Claude Code, `$HOME/.codex/skills/ddl-protocol/SKILL.md` in Codex). Follow its Start steps before continuing.
2. Read the project's guidance file when it is not already in context (the host loads `AGENTS.md` for Codex, and `CLAUDE.md` or `.claude/CLAUDE.md` for Claude Code, at session start), and any applicable command overlay.
3. Read `design.md` when it is not already in context — extract scopes, principles, Experience, Binding Decisions, Direction, and Acceptance Gates (Notebook)
4. If no `design.md` exists → refuse ("Nothing to reflect against")
5. If a path is given, work only on the scopes it covers

Read the Notebook operation for the section rules.

When a STOP needs a decision, read the Approval operation and its implementation for the current host before presenting the decision. When a SWARM fires, read the Parallel work operation and its implementation before fan-out.

### Phase 1: READ

+++SWARM: 2+ scopes in design.md

```
  team: reflect-read
  spawn: reader-{scope}
  type: Explore
  max: 5
  batch: auto
  each: |
    Scan {scope} for current implementation state,
    including the technology it actually uses (manifests, lockfiles, config, entry points).
    Report findings to the lead when done.
  collect: lead also inspects design.md for internal consistency, then integrates all results
```

### Phase 2: COMPARE

Lead integrates results and performs cross-scope analysis:

1. Compare each scope's implementation against `design.md` principles and Binding Decisions
2. Compare implemented behavior against Experience: states the code handles that Experience does not describe, and Experience items the code does not deliver
3. Compare finished work against Direction and Acceptance Gates through their passed marks (Notebook): which stages have every gate marked passed, which deviated, and whether every Acceptance Gate is marked passed
4. Compare Scopes and Validation against the repository: scope paths that no longer exist and Validation commands that cannot run
5. Classify divergences:
   - **Code drifted** — implementation violates a principle or a Binding Decision, or does not deliver an Experience item
   - **Philosophy outdated** — code shows better approach
   - **New pattern** — code introduced something `design.md` doesn't cover
   - **Direction spent** — stages whose gates are all marked passed; retire them to the history with the `Approved plan` lines that served them (Notebook)
   - **Acceptance Gates spent** — every gate is marked passed, so the work was accepted; move gates that should keep running into Validation, then retire the section to the history (Notebook)
   - **Past kept** — a dated event, a finished stage's outcome, or a measurement of a past run that design.md still holds outside the lines, marks and cells Notebook Formats define; move it to the history (Notebook)
6. If the project keeps its own headings for these sections (for example `Stack` or `Execution plan`), propose one mapping onto Notebook; never force a rename

+++DETECT:
  D1: Drift — Implementation contradicts a stated principle
  D2: New Pattern — Code exhibits a pattern not captured in design.md
  D3: Outdated Principle — Principle references removed/changed behavior
  D4: Stale Reference — design.md links, paths, or Scopes paths no longer exist, or a Validation command cannot run
  D5: Self-Contradiction — Two principles in design.md conflict with each other
  D6: Binding Drift — Code uses a technology that replaces, bypasses, or contradicts a Binding Decision, or the reason a Binding Decision gives no longer holds
  D7: Spent Direction — Direction lists a stage whose gates are all marked passed, or the section remains after every stage is done
  D8: Spent Acceptance Gates — every gate in Acceptance Gates is marked passed and the section remains
  D9: Experience Gap — code handles a state Experience does not describe, or does not deliver an Experience item
  D10: Past Kept — design.md holds a dated event, a finished stage's outcome, or a measurement of a past run outside the lines, marks and cells that Notebook Formats define
  D11: Design Change — a proposal would add, change or remove a principle or a Binding Decision, or remove or alter an Experience item

Only the user resolves a Binding Drift (D6): fix the code, or change the Binding Decision. D11 asks with options: apply the proposal, leave it unapplied, or revise it.

+++STOP: on D6
+++STOP: on D11

### Phase 3: APPLY

Read the Run operation and its implementation for the current host, then make a snapshot (the gate's `snapshot`) before the first change.

+++DETECT:
  D12: No Snapshot — the snapshot cannot be made (no gate, no Git repository, or a failure)

D12 asks with options: apply without a snapshot, or apply nothing.

+++STOP: on D12

Apply every proposal inside design.md and its history, and a D6 or D11 proposal only as its answer chose; a finding whose fix lies elsewhere (code) is reported, not applied.

+++SWARM: 2+ changes across scopes

```
  team: reflect-apply
  spawn: writer-{scope}
  type: general-purpose
  max: 5
  batch: auto
  each: |
    Apply to {scope} the changes listed in this prompt, and nothing else.
    Report completion to the lead when done.
  collect: lead summarizes what changed
```

### Phase 4: REPORT

+++STOP: always

Report what was applied; ask nothing (Approval Exceptions: informational).

+++Report:
Outcome: the applied changes, numbered with stable IDs, each naming the affected principle, Binding Decision, Direction stage, or section as its `Target` and its effect, and the snapshot ref that undoes them.
Consequence: the changes stand in the working tree, uncommitted; restoring the snapshot undoes them all.
Review detail: each change's type, target, finding and supporting file/line evidence; what each retirement moved to the history; each finding left unapplied, with its reason; when a change touched a document that has a language counterpart, that pair and the reason it still needs syncing (standalone, that work is `/resonate`; inside the Close stage the Close operation covers it).
Choices: none; the report asks nothing. With no findings, state that nothing changed.

## Constraints

+++NEVER: Apply a change outside design.md and its history, or a Binding Decision, principle or behavior change unasked
+++NEVER: Hardcode scopes — they come from design.md
+++NEVER: Skip meta-reflection — can reflect on design.md itself
+++NEVER: Rewrite a Binding Decision to match drifted code without the user's approval
+++NEVER: Add a Binding Decision row for a technology found only in code — report it as an existing premise until the user gives the reason
