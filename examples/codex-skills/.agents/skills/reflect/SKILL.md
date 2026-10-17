---
name: reflect
description: Update documents based on implementation results
metadata:
  short-description: Code to Design
---

# reflect

Detect divergence between implementation and DESIGN.md, then reconcile.

## Usage

- `$reflect` — Check entire project alignment
- `$reflect <path>` — Check specific file/directory

## Phases

### Phase 0: INIT

1. Read `AGENTS.md` — Directive Reference, Codex Runtime Contract, +++SWARM Execution, and DESIGN.md Sections
2. Read `DESIGN.md` — extract scopes, principles, Experience, Binding Decisions, Direction, and Acceptance Gates (DESIGN.md Sections in `AGENTS.md`)
3. If no `DESIGN.md` exists → refuse ("Nothing to reflect against")

### Phase 1: READ

+++SWARM: 2+ scopes in DESIGN.md

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
  collect: lead also inspects DESIGN.md for internal consistency, then integrates all results
```

### Phase 2: COMPARE

Lead integrates results and performs cross-scope analysis:

1. Compare each scope's implementation against `DESIGN.md` principles and Binding Decisions
2. Compare implemented behavior against Experience: states the code handles that Experience does not describe, and Experience items the code does not deliver
3. Compare finished work against Direction: which stages are done and passed their gate, which deviated
4. Classify divergences:
   - **Code drifted** — implementation violates a principle or a Binding Decision
   - **Philosophy outdated** — code shows better approach
   - **New pattern** — code introduced something `DESIGN.md` doesn't cover
   - **Direction spent** — stages whose work is done and whose gate has passed; replace them with the outcome, and delete the section when every stage is done (quote the removed stages in the REPORT when DESIGN.md is not under version control)
5. If the project keeps its own headings for these sections (for example `Stack` or `Execution plan`), propose one mapping onto the sections listed in DESIGN.md Sections of `AGENTS.md`; never force a rename

+++DETECT:
  D1: Drift — Implementation contradicts a stated principle
  D2: New Pattern — Code exhibits a pattern not captured in DESIGN.md
  D3: Outdated Principle — Principle references removed/changed behavior
  D4: Stale Reference — DESIGN.md links or paths no longer exist
  D5: Self-Contradiction — Two principles in DESIGN.md conflict with each other
  D6: Binding Drift — Code uses a technology that replaces, bypasses, or contradicts a Binding Decision
  D7: Spent Direction — Direction lists stages whose work is done and whose gate has passed, or the section remains after every stage is done

### Phase 3: REPORT

+++STOP: always

Do NOT modify `DESIGN.md` without approval. Only the user resolves a Binding Drift (D6): fix the code, or change the Binding Decision.

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
    Apply only approved changes to {scope}.
    Report completion to the lead when done.
  collect: lead summarizes what changed
```

After applying:
1. Summarize what changed
2. Suggest next command if applicable

## Constraints

+++NEVER: Modify DESIGN.md without +++STOP approval
+++NEVER: Hardcode scopes — they come from DESIGN.md
+++NEVER: Skip meta-reflection — can reflect on DESIGN.md itself
+++NEVER: Rewrite a Binding Decision to match drifted code without the user's approval
+++NEVER: Add a Binding Decision row for a technology found only in code — report it as an existing premise or an `Unbound:` line until the user gives the reason
