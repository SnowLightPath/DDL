---
name: resonate
description: Synchronize English and Japanese versions of the documentation
metadata:
  short-description: Sync en/ja docs
---

# resonate

Synchronize English and Japanese versions.

## Usage

- `$resonate` — Synchronize all multilingual document pairs
- `$resonate <path>` — Synchronize specific file or directory

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

### Phase 3: REPORT

+++STOP: always

Do NOT apply changes without approval.

+++Report:
Decision: apply all current compatible language-pair proposals, select or revise the set, or leave it pending.
Recommendation: a concise overall reason, then numbered proposals with stable IDs, the nuance each restores, and its effect on both languages.
Consequence: approve all covers the displayed ready set in both versions; subset approval covers only the selected proposal IDs.
Review detail: each stable proposal ID, section, detection type, relevant EN/JA text and proposed edits.
Choices: request one batch approval through Approval; open item selection only when requested, with no per-proposal or per-language reapproval after approve all. With no dissonance, state that no change needs approval and stop.

### Phase 4: APPLY

**Pre-condition.** Enter this phase only after explicit user approval of its scope at the Phase 3 STOP gate (per Approval). If the actual answer does not authorize this work, return to Phase 3 and re-present the current decision.

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
