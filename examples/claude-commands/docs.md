# docs

Audit and fix documentation quality.

## Usage

- `/docs` — Audit all documentation
- `/docs <path>` — Audit specific document or directory

## Phases

### Phase 0: INIT

1. Read the DDL protocol for the current runtime when it is not already in context: repo-local `commands/DDL-PROTOCOL-SKILL.md` when present; otherwise, in Claude Code, `.claude/commands/DDL-PROTOCOL-SKILL.md`, then `$HOME/.claude/commands/DDL-PROTOCOL-SKILL.md`; in Codex, `$HOME/.codex/commands/DDL-PROTOCOL-SKILL.md`, then the protocol sections of `AGENTS.md`.
2. Read project-local runtime guidance when it is not already in context (the runtime loads `AGENTS.md` for Codex, and `CLAUDE.md` or `.claude/CLAUDE.md` for Claude Code, at session start), and any applicable command overlay.
3. Read `design.md` when it is not already in context — extract scopes, and documentation paths when design.md lists them
4. If no `design.md` exists → treat the repository as one scope
5. Discover all documentation files (`.md`, `.txt`, etc.)
6. If a path is given, audit only that path and the scopes it covers (§2.3 of the protocol)

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

### Phase 3: REPORT

+++STOP: always

Do NOT fix without approval.

+++Report:
| # | File:Line | Type | Finding | Suggested Fix |
|---|-----------|------|---------|---------------|

Wait for user to approve, reject, or modify each fix.

### Phase 4: FIX

**Pre-condition.** Enter this phase only after explicit user approval at the Phase 3 STOP gate (per §1.5 of the protocol). If the most recent user message is not an approval token, return to Phase 3 and re-emit the report.

+++SWARM: 2+ approved fixes across different files

```
  team: docs-fix
  spawn: writer-{scope}
  type: general-purpose
  max: 5
  batch: auto
  each: |
    Apply to the {scope} documentation the approved fixes listed in this prompt, and nothing else.
    Report completion to the lead when done.
  collect: lead verifies all fixes applied correctly
```

### Phase 5: VERIFY

Re-scan fixed files to confirm:

1. No new Detection Targets introduced
2. All approved fixes applied correctly
3. Summarize final state

## Constraints

+++NEVER: Modify documentation without +++STOP approval
+++NEVER: Hardcode scopes or paths — they come from design.md
+++NEVER: Execute code examples — check conceptually only
