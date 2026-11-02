# The shared notebook

## Read when

Read this before a command reads or writes a notebook section, records a decision, an approved plan, or a gate mark, or retires stages and gates; the command supplies the section name and the mark it writes. The notebook is `design.md` unless the project's guidance names other files; the host adapter loads it at session start or Phase 0 reads it, and it carries what the human agreed to and nothing else, so agent progress and automatic memory stay out of it. Gate marks follow a STOP ([Approval](approval.md)), the lanes of a stage are the units of [Parallel work](parallel-work.md), and the Close stage ([Close](close.md)) writes the same sections as `/reflect`.

## Syntax

None.

## Fields

Commands read and write these sections by heading name. A project uses only the sections it needs and may keep other headings. Experience comes first: Binding Decisions, Direction, and Acceptance Gates serve the Experience and never contradict it.

| Section | Holds | Written by | Read by |
|---|---|---|---|
| `## Intent` | Why the project exists | human | every session, because the notebook loads at session start; no command extracts it |
| `## Scopes` | Scope table; drives SWARM ([Parallel work](parallel-work.md)) | human, `/reflect` | every command whose units are scopes; a command that fans out over other units (for example document pairs) reads none |
| `## Principles` | Design principles (`## Core Principles` is an accepted heading) | `/draft` (D5), `/reflect` | `/draft`, `/realize`, `/reflect` |
| `## Experience` | Consumer-side usage: inputs, outputs, and error / empty / boundary states | `/draft`, `/reflect` (additions found in code) | `/draft`, `/realize`, `/reflect` |
| `## Binding Decisions` | Means fixed before implementation (framework, language, platform, runtime, software, output format) because the Experience depends on them, an external constraint requires them, or the human prefers them and says so | the human, through `/draft`; `/realize` records a delegated choice after the human approves it in the plan; a change the human approves in `/realize` or `/reflect` (D6) | `/draft`, `/realize` (honors), `/reflect` (checks), `/refactoring` (keeps) |
| `## Direction` | Non-binding outlook on the path to implementation: stages, parallel lanes, what the human sees, gates | `/draft`; `/realize` writes the `Approved plan` lines and the gate marks (`approved in advance`, `passed`); `/reflect` replaces passed stages and deletes their `Approved plan` lines | `/draft`, `/realize` (follows), `/reflect` (retires) |
| `## Acceptance Gates` | What must hold when done: mechanical gates and human gates | `/draft`; `/realize` marks gates passed; `/reflect` retires it after acceptance | `/draft`, `/realize`, `/validate`, `/reflect` (retires) |
| `## Validation` | Per-scope mechanical checks | human, `/reflect` | `/validate`, `/realize`, `/commit`, `/refactoring` |

Where this table names `/reflect` as a writer, the Close stage of `/realize` and `/commit` ([Close](close.md)) writes the same sections in the same way.

## Procedure

1. **Binding Decisions:** Write one row per decision in the table of Formats.
   - `Why it binds` names an Experience item, an external constraint (organization standard, existing system, hosting), or a stated preference. A row without a reason or a source is incomplete.
   - `Source` quotes the human's words with the date. When the human approves a report that listed the row, that approval is the source, written as `approved /draft report (<date>)`.
   - Record the granularity the human stated. Exact versions belong to code (manifests and lockfiles).
   - Add a `Scope` column when scopes bind different technologies.
   - Only the human creates or changes a row. The LLM may propose a technology; list a proposal, a technology named without a reason, and a choice the human delegates under the table as an `Unbound:` line (Formats). An `Unbound:` line binds nothing.
   - State a delegated choice in the `/realize` plan; when the human approves the plan, `/realize` moves the line into the table with Source `approved in /realize plan (<date>)`.
2. **Direction:** Write a table of stages (Formats).
   - Direction is non-binding. `/realize` follows it by default and reports every deviation (a merged, reordered, or skipped stage).
   - The lanes of a stage are the units `/realize` fans out ([Parallel work](parallel-work.md)).
   - When the user approves the `/realize` plan, `/realize` writes its durable parts under the table as `Approved plan (<date>): files to touch, approach, Unbound choices made`, so a later or compacted session rebuilds worker prompts from it instead of from a summary. `/reflect` deletes these lines with the stages they served.
   - Gates in the `Gate` column run at the end of their stage: a mechanical gate is a validation command, and a human gate is executed as `+++STOP` ([Approval](approval.md)) unless the human approved it in advance. Review the compatible human gates ready at that boundary in one batch, including the last stage's gates and the final Acceptance Gates when all evidence is ready. Gates are never dropped: a merged stage keeps its gates at its end; a skipped stage's gates move to the end of the next stage (or to the end of the work when it is the last stage); a reordered stage keeps its gates.
   - Every Direction ends with a stage named `Close` ([Close](close.md)): reflect, docs, resonate, validate, and the Git review of the whole change set. `/draft` writes it as the last row; `/realize` adds it to the plan when it is missing. Its gate is the Git review.
   - `/reflect`, or the Close stage, replaces the stages whose gates are all marked passed with their outcome, and deletes the section when every stage is done. When the notebook is under version control, the history stays there; otherwise `/reflect` quotes the removed stages in its REPORT.
   - Direction is the most temporary part of the notebook. Retiring it, like retiring Acceptance Gates, shrinks what every later session loads.
3. **Acceptance Gates:** Write a list of conditions for done (Formats).
   - Mechanical gates are commands, each with the expected result when the command does not fail by exit code alone. `/realize` runs them in VALIDATE, and `/validate` runs them with the Validation block.
   - Human gates are approvals. At the end of the work, `/realize` names all compatible ready human gates in one `+++STOP` review set ([Approval](approval.md)), collects one batch submission, and marks each approved gate passed. It does not ask again for each gate.
   - The work is accepted when every gate is marked passed. `/reflect`, or the Close stage, then retires the section: move the mechanical gates that should keep running into the Validation block first.
4. **Passed marks:** A gate passes when its command gives the expected result, or when the human approves it at the gate or in advance ([Approval](approval.md)).
   - `/realize` appends `passed <date>` to each gate that passes: in the stage's Gate cell for Direction (for example `human approval, passed 2026-10-20`), and after the gate for Acceptance Gates.
   - Write a named advance approval in the same place the moment the user gives it, as `approved in advance (<date>)`; when the stage or the work ends, `passed <date>` follows it (Example).
   - These marks are the record of progress and acceptance: `/reflect` reads them and never infers a pass from conversation memory.
5. **Aligned check references:** When the approved `/realize` plan moves a validation target or reference, align Scopes and Validation before running that stage's check.
   - Preserve the check's purpose, the meaning of its expected result, and its coverage; show the old and new mapping in the change set.
   - This changes no Acceptance Gate, Binding Decision, Experience item, or human gate. An actual check failure still stops the work.

## Formats

- Binding Decisions table header: `| Decision | Why it binds | Source |`; with a `Scope` column, `| Decision | Scope | Why it binds | Source |`.
- Source cell: the human's quoted words with the date, `approved /draft report (<date>)`, or `approved in /realize plan (<date>)` for a delegated choice.
- Unbound line, under the table: `Unbound: <topic> — options A / B (delegated to /realize | awaiting choice)`.
- Direction table header: `| Stage | Work (parallel lanes) | Human sees | Gate |`.
- Approved plan line, under the Direction table: `Approved plan (<date>): files to touch, approach, Unbound choices made`.
- Pass mark, in the Gate cell or after the gate: `passed <date>`.
- Advance approval, in the same place, written at once: `approved in advance (<date>)`; `passed <date>` follows when the stage or the work ends.
- Acceptance Gates lines: a mechanical gate `- <command> → <expected result>` (the result stated when exit code alone does not decide); a human gate `- human: <what is reviewed>`.
- Validation block, one entry per check:

  ```
  # V<n>: <scopes the check covers>
  <command>
  # expected: <value when exit code alone does not decide>
  ```

## Example

Under `## Binding Decisions`, as `/draft` saved them (2026-10-17):

```markdown
| Decision | Why it binds | Source |
|----------|--------------|--------|
| Next.js App Router | Answers stream in while they are written, and per-route loading and error states are the core of the Experience | "I want to build it with Next.js", "Yes, App Router" (2026-10-17) |

Unbound: Language — options TypeScript / JavaScript (delegated to /realize)
```

Under `## Direction`, as it reads after `/realize` passed stage S1 (2026-10-21):

```markdown
| Stage | Work (parallel lanes) | Human sees | Gate |
|-------|-----------------------|------------|------|
| S0 | Settle the search API as a CLI | sample CLI output | `npm test`, passed 2026-10-20 |
| S1 | Three screen states (normal, empty, failure), one lane each | three screenshots | human approval, approved in advance (2026-10-20), passed 2026-10-21 |
| Close | reflect, docs, resonate, validate, Git review of the whole change set | final diff and the summary of design.md changes | Git review |

Approved plan (2026-10-20): files `cli/search.ts`, `app/search/**`; approach: CLI first, then the three states as three lanes; Unbound choices made: Language → TypeScript
```

Under `## Acceptance Gates`, at the same moment:

```markdown
- `npm test` → all suites pass
- `npm run build` → exit 0 and no type errors, passed 2026-10-21
- human: the three screen states match the Experience, approved in advance (2026-10-20), passed 2026-10-21
```

## Boundaries

| Situation | Behavior |
|---|---|
| The project keeps an `existing heading` of its own (for example `Stack` or `Execution plan`) | Keep it. `/reflect` proposes one mapping onto the sections in Fields and never forces a rename |
| A technology is already present in the `existing code` | An existing premise: commands show it in their reports, and the notebook does not record it because the code already does. It becomes a row only when the human gives a reason |
| A decision is found only in the host's `automatic memory` | At most such a premise: commands show it in their reports, and it binds nothing until the human records it in the notebook |
| After approval, a command `argument` names a technology different from a Binding Decision | The notebook wins over the argument: the argument is a change to a Binding Decision and halts the command; it is never permission to replace the row |
| The deliverable is a document or slides (`output format`) | For documents and slides, the output format is the Binding Decision |
| The human `delegated` a choice | List it as `Unbound: … (delegated to /realize)`; `/realize` states the choice in its plan and, on approval, moves it into the table with Source `approved in /realize plan (<date>)` |
| A technology is named with `no reason` | Ask once; without an answer, list it as `Unbound: … (awaiting choice)`. A row without a reason or a source is incomplete |
| A stage is merged, skipped, or reordered | Its gates are kept as Procedure step 2 states; a gate is never dropped |
| The human gives a general approval | It waives no gate; only a named advance approval is written as `approved in advance (<date>)` |
| The notebook is `not version controlled` | `/reflect` quotes the removed stages and gates in its REPORT; otherwise the history stays in git |
| The project's guidance names an `other notebook file` (for example a library whose README and guides are its living specification) | Commands read and write those files wherever this protocol or a command says `design.md`, by the same section rules |

## Runtime

How the notebook is loaded is a host matter: [Claude Code](runtimes/claude-start.md) imports it through the instruction file and re-injects it after compaction; [Codex](runtimes/codex-start.md) injects it through the session-start hook on startup, resume, and compaction. Without an adapter, Phase 0 reads it. Loading is the only part an adapter provides; the section rules above are instructions in every host, and a worker reads only the sections its prompt names ([Parallel work](parallel-work.md)).
