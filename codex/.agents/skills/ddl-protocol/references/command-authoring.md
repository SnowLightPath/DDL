# Authoring a DDL command

## Read when

Read before creating or changing a DDL command for either host; the command
supplies its phases, work, detection targets, report contract and constraints,
and this file supplies the grammar and the checks (the template is in
[Examples](examples.md)).

## Syntax

```
---
<frontmatter: see Formats>
---

# <command-name>

<one-line intent>

## Usage

- `/<command-name>` — <default behavior>
- `/<command-name> <arg>` — <behavior with an argument>

## Phases

### Phase 0: INIT

<the three shared Phase 0 lines, verbatim from the template in Examples>
3. Read `design.md` when it is not already in context — <what to extract>
4. If no `design.md` → <fallback behavior>

### Phase N: NAME                 N from 1, consecutive; at least one work phase before REPORT

<work>

+++SWARM: <condition>             0+; the fenced operand block follows (Parallel work: Syntax)

+++DETECT:                        1+ per command
  D<n>: <name> — <trigger>        indented; unique and ascending from D1 across the command

+++STOP: on D<n>                  0+; a detection that needs a human decision

### Phase N: REPORT

+++STOP: always                   required here

+++Report:
<Label>: <what the user reviews>  labels in Formats

### Phase N+1: NAME

**Pre-condition.** <sentence>     first line of any phase after a `+++STOP: always`

## Constraints

+++NEVER: <prohibition in the imperative>   1+
```

## Fields

| Role | Phase name | Required |
|---|---|---|
| INIT | `INIT`, always Phase 0 | yes |
| SURVEY/READ | `SURVEY`, `READ`, or a domain name such as `SCAN` | no |
| WORK/IMPLEMENT | `WORK`, `IMPLEMENT`, or a domain name such as `COMPARE` | at least one work phase |
| REPORT | `REPORT`; a `REVIEW` phase that carries `+++Report:` fills this role | yes, with `+++STOP: always` |
| EXECUTE | `EXECUTE` or a domain name such as `COMMIT`; opens with `**Pre-condition.**` | no |
| VERIFY | `VERIFY` | no |

## Procedure

1. Copy the template in [Examples](examples.md) into
   `.claude/skills/<name>/SKILL.md` (Claude Code) or
   `.agents/skills/<name>/SKILL.md` (Codex) and set `name` in the frontmatter
   to the directory name.
2. Keep the shared Phase 0 lines (Formats) verbatim and edit lines 3 and 4
   only; the checker compares every command against the template.
3. Define the phases, numbered from 0 and consecutive, with the roles and
   requirements in Fields.
4. Write the detection targets: one `+++DETECT:` block per phase that needs
   them, `D<n>` lines unique and ascending from D1 across the whole command,
   each trigger operationally verifiable.
5. Place `+++STOP: on D<n>` where a detection needs a human decision, and open
   the phase after a `+++STOP: always` with the `**Pre-condition.**` line in
   Formats.
6. Write a `+++SWARM:` condition and operand block for each phase that fans
   out, by the Syntax and Fields of [Parallel work](parallel-work.md); keep
   `each` self-contained and end it with the report to the lead.
7. Write `+++Report:` with the labels in Formats, naming the decision,
   evidence, and consequences this command requires.
8. Write `## Constraints` with at least one `+++NEVER:` line; put global
   prohibitions and `G<n>` detections in the guidance file, not in the command.
9. Place project facts in `design.md` or a `commands/<name>.md` overlay
   (Boundaries), never in the command file.
10. Run `python3 tools/check_ddl.py commands` (or the project's equivalent) and
    fix every reported line. For Codex, run the generator
    (`tools/sync_mirrors.py` in the DDL repository): it derives the `$name`
    skill and its `agents/openai.yaml` from the Claude Code file.

## Formats

Frontmatter for Claude Code:

```yaml
---
name: command-name
description: One-line intent
argument-hint: "[arg]"
disable-model-invocation: true
metadata:
  short-description: Short name
---
```

Frontmatter for Codex (generated; `argument-hint` and
`disable-model-invocation` are dropped):

```yaml
---
name: command-name
description: One-line intent
metadata:
  short-description: Short name
---
```

The Codex skill's `agents/openai.yaml` (generated):

```yaml
policy:
  allow_implicit_invocation: false
```

- Phase heading: `### Phase N: NAME`.
- Detection block: `+++DETECT:` on its own line, then indented lines of the
  form `D1: name — trigger`.
- STOP forms: `+++STOP: always` and `+++STOP: on D<n>`.
- Pre-condition line: `**Pre-condition.** Enter this phase only after explicit
  user approval of its scope at the Phase N STOP gate (per Approval). If the
  actual answer does not authorize this work, return to Phase N and re-present
  the current decision.`
- Report contract: `+++Report:` followed by `Decision:`, `Recommendation:`,
  `Consequence:`, `Review detail:`, and `Choices:` lines; an informational
  report writes `Outcome:` in place of `Decision:`.
- Constraint: `+++NEVER:` followed by one prohibition in the imperative.
- Runtime markers `+++DDL_PHASE: <PhaseName>` and `+++DDL_REPORT`: a command
  file writes them only inside a rule, never as literal output (entry:
  Instruction set).
- Shared Phase 0 lines: the project-copy sentence and numbered lines 1 and 2
  of the template in [Examples](examples.md), the only copy; this file never
  repeats them.

## Boundaries

| Situation | Behavior |
|---|---|
| A project copy of the command exists (`.claude/skills/<name>/SKILL.md`, `.agents/skills/<name>/SKILL.md`, or the file the project's instruction file names) | It runs even when a user-level copy exists: Claude Code lists the user-level skill first and Codex lists both, and Phase 0 follows the project copy either way. An older self-contained project copy follows its own rules. |
| A `commands/<name>.md` overlay exists at the project root | It adds project facts to the command unless it declares itself a full override; Phase 0 line 2 reads it when it applies. |
| No notebook: `design.md` is absent and the project names no other file | Phase 0 line 4 states the command's fallback: refuse with the reason, or run the reduced behavior the command names. Never invent notebook sections. |
| Missing reference: a required protocol reference is absent, unreadable, or of uncertain version | Stop as the entry's Start says. |
| A runtime tool name would explain a step | State the meaning; the host files under `runtimes/` map it (entry: Start). |
| A domain phase name (SCAN, COMPARE, COMMIT, REVIEW) | Map it to a role in Fields. |
| The phase makes a read-only report | Emit `+++DDL_REPORT`, write `Outcome:` in place of `Decision:`, and end the turn at the STOP with no approval request (Approval Boundaries: informational). |

## Runtime

- Read [Claude Code](runtimes/claude-start.md) for the Claude Code adapter
  paths a command's Phase 0 and the gate rely on; the skill layout is in
  Procedure 1 and the frontmatter in Formats.
- Read [Codex](runtimes/codex-start.md) for the Codex adapter paths; the Codex
  skill is generated from the Claude Code file (Procedure 10), so author the
  Claude Code form first.
