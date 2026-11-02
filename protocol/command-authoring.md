# Authoring a DDL command

## Read when

Read before creating or changing a DDL command for either host; the command
supplies its phases, work, detection targets, report contract and constraints,
and this operation supplies the grammar, the checks and the template
(Example).

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

<the three shared Phase 0 lines, verbatim from the template in Example>
3. Read `design.md` when it is not already in context — <what to extract>
4. If no `design.md` exists → <fallback behavior>
5. <further INIT steps, optional>

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

## Operands

| Role | Phase name | Required |
|---|---|---|
| INIT | `INIT`, always Phase 0 | yes |
| SURVEY/READ | `SURVEY`, `READ`, or a domain name such as `SCAN` | no |
| WORK/IMPLEMENT | `WORK`, `IMPLEMENT`, or a domain name such as `COMPARE` | at least one work phase |
| REPORT | `REPORT`; a `REVIEW` phase that carries `+++Report:` fills this role | yes, with `+++STOP: always` |
| EXECUTE | `EXECUTE` or a domain name such as `COMMIT`; opens with `**Pre-condition.**` | no |
| VERIFY | `VERIFY` | no |

## Operation

1. Copy the template in Example below into the host's project skill path
   (`.claude/skills/<name>/SKILL.md` in Claude, `.agents/skills/<name>/SKILL.md`
   in Codex), or into `skills/<name>/SKILL.md` of the DDL repository for a
   command shipped with DDL; the template is the Claude form, and a project in
   Codex writes that host's form (Formats). Set `name` in the frontmatter to
   the directory name.
2. Keep the shared Phase 0 lines (Formats) verbatim and edit lines 3 and 4
   only; the checker compares every command against the template.
3. Define the phases, numbered from 0 and consecutive, with the roles and
   requirements in Operands.
4. Write the detection targets: one `+++DETECT:` block per phase that needs
   them, `D<n>` lines unique and ascending from D1 across the whole command,
   each trigger operationally verifiable.
5. Place `+++STOP: on D<n>` where a detection needs a human decision, and open
   the phase after a `+++STOP: always` with the `**Pre-condition.**` line in
   Formats.
6. Write a `+++SWARM:` condition and operand block for each phase that fans
   out, by the Syntax and Operands of [Parallel work](parallel-work.md); keep
   `each` self-contained and end it with the report to the lead.
7. Write `+++Report:` with the labels in Formats, naming the decision,
   evidence, and consequences this command requires.
8. Write `## Constraints` with at least one `+++NEVER:` line; put global
   prohibitions and `G<n>` detections in the guidance file, not in the command.
9. Place project facts in `design.md` or a `commands/<name>.md` overlay
   (Exceptions), never in the command file.
10. Run the project's structure check (`python3 tools/check_ddl.py source` in
    the DDL repository) and fix every reported line. In the DDL repository,
    `tools/build.py` then renders the one source skill into both hosts'
    layouts (`dist/claude/.claude/skills/`, `dist/codex/.agents/skills/`),
    applying the Codex differences: no `argument-hint` or
    `disable-model-invocation`, `/name` rewritten to `$name`, and
    `agents/openai.yaml` added.

## Formats

Frontmatter for Claude:

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
  the current decision.` A phase that several STOPs can precede names them in
  place of `the Phase N STOP gate`.
- Report contract: `+++Report:` followed by `Decision:`, `Recommendation:`,
  `Consequence:`, `Review detail:`, and `Choices:` lines; an informational
  report writes `Outcome:` in place of `Decision:`.
- Constraint: `+++NEVER:` followed by one prohibition in the imperative.
- Output markers `+++DDL_PHASE: <PhaseName>` and `+++DDL_REPORT`: a command
  file writes them only inside a rule, never as literal output (entry:
  Instruction set).
- Shared Phase 0 lines: the project-copy sentence and numbered lines 1 and 2
  of the template in Example, the only copy; no other section repeats them.

## Example

The complete command as the source skill; its Phase 0 sentence and lines 1
and 2 are the shared lines:

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

1. Read the DDL protocol when it is not already in context: the project's copy when present (`.claude/skills/ddl-protocol/SKILL.md` in Claude Code, `.agents/skills/ddl-protocol/SKILL.md` in Codex, or the file the project's instruction file names as the protocol); otherwise the user-level copy (`$HOME/.claude/skills/ddl-protocol/SKILL.md` in Claude Code, `$HOME/.codex/skills/ddl-protocol/SKILL.md` in Codex). Follow its Start steps before continuing.
2. Read the project's guidance file when it is not already in context (the host loads `AGENTS.md` for Codex, and `CLAUDE.md` or `.claude/CLAUDE.md` for Claude Code, at session start), and any applicable command overlay.
3. Read `design.md` when it is not already in context — extract relevant items
4. If no `design.md` exists → fallback behavior

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

## Exceptions

| Situation | Behavior |
|---|---|
| A project copy of the command exists (`.claude/skills/<name>/SKILL.md`, `.agents/skills/<name>/SKILL.md`, or the file the project's instruction file names) | It runs (the Phase 0 sentence), whatever order the host lists the two copies in (host lookup: `hosts/{host}/start.md` Coverage). An older self-contained project copy follows its own rules. |
| A `commands/<name>.md` overlay exists at the project root | It adds project facts to the command unless it declares itself a full override; Phase 0 line 2 reads it when it applies. |
| No notebook: `design.md` is absent and the project names no other file | Phase 0 line 4 states the command's fallback: refuse with the reason, or run the reduced behavior the command names. Never invent notebook sections. |
| Missing file: a required protocol file is absent, unreadable, or of uncertain version | Stop as the entry's Start says. |
| A host tool name would explain a step | State the meaning; the implementations under `hosts/` map it (entry: Start). |
| A domain phase name (SCAN, COMPARE, COMMIT, REVIEW) | Map it to a role in Operands. |
| The phase makes a read-only report | Emit `+++DDL_REPORT`, write `Outcome:` in place of `Decision:`, and end the turn at the STOP with no approval request (Approval Exceptions: informational). |

## Implementation

- Read the implementation next: [{Host}](hosts/{host}/start.md), for the
  adapter paths a command's Phase 0 and the gate rely on; the project skill
  path is in Operation step 1 and the frontmatter in Formats.
- In the DDL repository, `tools/build.py` renders both hosts' layouts from the
  one source skill (Operation step 10); a project's own command is written
  directly in its host's form.
