---
name: reflect
description: Update documents based on implementation results
metadata:
  short-description: Code to Design
---

# reflect

Detect divergence between implementation and design.md, then reconcile.

## Usage

- `$reflect` — Check entire project alignment
- `$reflect <path>` — Check specific file/directory

## Phases

### Phase 0: INIT

1. `AGENTS.md` (Directive Reference, Codex Runtime Contract, +++SWARM Execution, design.md Sections) is in context from session start; read it only when it is not, and read any applicable command overlay (`commands/<name>.md`)
2. Read `design.md` when it is not already in context — extract scopes, principles, Experience, Binding Decisions, Direction, and Acceptance Gates (design.md Sections in `AGENTS.md`)
3. If no `design.md` exists → refuse ("Nothing to reflect against")
4. If a path is given, work only on the scopes it covers (+++SWARM Execution in `AGENTS.md`)

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
3. Compare finished work against Direction and Acceptance Gates through their passed marks (design.md Sections in `AGENTS.md`): which stages have every gate marked passed, which deviated, and whether every Acceptance Gate is marked passed
4. Compare Scopes and Validation against the repository: scope paths that no longer exist and Validation commands that cannot run
5. Classify divergences:
   - **Code drifted** — implementation violates a principle or a Binding Decision, or does not deliver an Experience item
   - **Philosophy outdated** — code shows better approach
   - **New pattern** — code introduced something `design.md` doesn't cover
   - **Direction spent** — stages whose gates are all marked passed; replace them with the outcome, delete the `Approved plan` lines that served them, and delete the section when every stage is done (quote the removed stages in the REPORT when design.md is not under version control)
   - **Acceptance Gates spent** — every gate is marked passed, so the work was accepted; move gates that should keep running into Validation, then delete the section (quote it in the REPORT when design.md is not under version control)
6. If the project keeps its own headings for these sections (for example `Stack` or `Execution plan`), propose one mapping onto the sections listed in design.md Sections of `AGENTS.md`; never force a rename

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

### Phase 3: REPORT

+++STOP: always

Do NOT modify `design.md` without approval. Only the user resolves a Binding Drift (D6): fix the code, or change the Binding Decision.

+++Report:
| # | Type | Target | Finding | Recommendation |
|---|------|--------|---------|----------------|

`Target` names the principle, Binding Decision, Direction stage, or section the finding is about.

Wait for user to approve, reject, or modify each recommendation.

### Phase 4: APPLY

**Pre-condition.** Enter this phase only after explicit user approval at the Phase 3 STOP gate (per the Codex Runtime Contract in `AGENTS.md`). If the most recent user message is not an approval token, return to Phase 3 and re-emit the report.

+++SWARM: 2+ approved changes across scopes

```
  team: reflect-apply
  spawn: writer-{scope}
  type: general-purpose
  max: 5
  batch: auto
  each: |
    Apply to {scope} the approved changes listed in this prompt, and nothing else.
    Report completion to the lead when done.
  collect: lead summarizes what changed
```

After applying:
1. Summarize what changed
2. Suggest next command if applicable

## Constraints

+++NEVER: Modify design.md without +++STOP approval
+++NEVER: Hardcode scopes — they come from design.md
+++NEVER: Skip meta-reflection — can reflect on design.md itself
+++NEVER: Rewrite a Binding Decision to match drifted code without the user's approval
+++NEVER: Add a Binding Decision row for a technology found only in code — report it as an existing premise until the user gives the reason
