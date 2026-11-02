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

1. Read the DDL protocol when it is not already in context: the project's copy when present (`.claude/skills/ddl-protocol/SKILL.md` in Claude Code, `.agents/skills/ddl-protocol/SKILL.md` in Codex, or the file the project's instruction file names as the protocol); otherwise the user-level copy (`$HOME/.claude/skills/ddl-protocol/SKILL.md` in Claude Code, `$HOME/.codex/skills/ddl-protocol/SKILL.md` in Codex). Complete its Start procedure before continuing.
2. Read project-local runtime guidance when it is not already in context (the runtime loads `AGENTS.md` for Codex, and `CLAUDE.md` or `.claude/CLAUDE.md` for Claude Code, at session start), and any applicable command overlay.
3. `design.md` is in context from session start; this command extracts nothing from it, because its units are document pairs
4. Discover all `en/` and `ja/` counterparts in target path

When a STOP needs a decision, read the selected protocol’s Approval feature and its current-host choice procedure before presenting the decision. When a SWARM fires, read its Parallel work feature before fan-out.

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
Consequence: approve-all covers the displayed ready set in both versions; subset approval covers only the selected proposal IDs.
Review detail: each stable proposal ID, section, detection type, relevant EN/JA text and proposed edits.
Choices: request one batch approval through Approval; open item selection only when requested, with no per-proposal or per-language reapproval after approve-all. With no dissonance, state that no change needs approval and stop.

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

## Example

```
Human: $resonate docs/

Assistant: Comparing en/ and ja/...

+++DDL_REPORT

Decision: apply the two displayed language-pair fixes together?
Recommendation: restore the intended context and matching instructions.
1. R1: add 「セッション、エージェント、ハーネスをまたいで」 to JA so the three contexts already named in EN are explicit.
2. R2: update the stale validation command in both versions to the command declared by design.md.
Consequence: approve-all applies R1 and R2; no further approval is requested per proposal or language.
Review detail: R1, D1 Missing Nuance, includes the current EN/JA paragraphs and exact edit; R2, D5 Stale Pair, includes both current commands, the declared command, and the exact replacements. Show this detail before asking.

The native choice interface presents: Apply both fixes / Select fixes or revise / Leave pending.
The assistant waits for one actual submission before applying anything. Selecting both applies R1 and R2 without a second approval. Item selection opens only if requested.
```
