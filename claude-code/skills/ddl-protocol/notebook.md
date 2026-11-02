# The shared notebook

## Read when

Read before a command reads or writes a notebook section, records a decision, a plan or a gate mark, or retires stages and gates; the command supplies the section name and the mark it writes; the notebook is `design.md` unless the project's guidance names another file.

## Syntax

None.

## Operands

Commands address sections by heading name; a project uses only those it needs and may keep others. The notebook holds only what the human agreed to; Experience comes first, and Binding Decisions, Direction and Acceptance Gates serve it, never contradict it.

| Section | Holds | Written by | Read by |
|---|---|---|---|
| `## Intent` | Why the project exists | human | every session; no command extracts it |
| `## Scopes` | Scope table; drives SWARM ([Parallel work](parallel-work.md)) | human, `/reflect` | commands whose units are scopes |
| `## Principles` | Design principles (`## Core Principles` is accepted) | `/draft` (D5), `/reflect` | `/draft`, `/realize`, `/reflect` |
| `## Experience` | Consumer-side usage: inputs, outputs, error/empty/boundary states | `/draft`, `/reflect` (additions found in code) | `/draft`, `/realize`, `/reflect` |
| `## Binding Decisions` | Means fixed before implementation (framework, language, platform, runtime, software, output format) and their reasons (step 1) | the human: via `/draft`, a delegated choice approved in the `/realize` plan, a change approved in `/realize` or `/reflect` (D6) | `/draft`, `/realize` (honors), `/reflect` (checks), `/refactoring` (keeps) |
| `## Direction` | Outlook: stages, parallel lanes (`/realize`'s SWARM units), what the human sees, gates | `/draft`; `/realize` (`Approved plan` line, marks); `/reflect` (retires) | `/draft`, `/realize` (follows), `/reflect` |
| `## Acceptance Gates` | Conditions for done: mechanical and human gates | `/draft`; `/realize` (marks); `/reflect` (retires) | `/draft`, `/realize`, `/validate`, `/reflect` |
| `## Validation` | Per-scope mechanical checks | human, `/reflect` | `/validate`, `/realize`, `/commit`, `/refactoring` |

Close ([Close](close.md)) writes wherever `/reflect` writes, the same way.

## Operation

1. **Binding Decisions:** One row per decision (Formats).
   - `Why it binds` names an Experience item, an external constraint or a stated preference; a row without reason or source (Formats) is incomplete.
   - Record the granularity the human stated; exact versions belong to code.
   - Only the human creates or changes a row; the LLM may propose. A proposal, a technology named without reason or a delegated choice is an `Unbound:` line under the table (Formats) and binds nothing.
   - State a delegated choice in the `/realize` plan; on plan approval move the line into the table with its Source (Formats).
2. **Direction:** A table of stages (Formats).
   - Non-binding: `/realize` follows it by default and reports every deviation (merged, reordered or skipped stage).
   - On plan approval, `/realize` writes the `Approved plan` line (Formats); a later or compacted session rebuilds worker prompts from it, not from a summary; `/reflect` deletes it with its stages.
   - Gates run at the end of their stage: a mechanical gate is a validation command, a human gate a `+++STOP` batched with the other ready gates ([Approval](approval.md)). None is dropped: a merged or reordered stage keeps its gates at its end; a skipped stage's move to the end of the next stage or of the work.
   - Every Direction ends with a stage named `Close` ([Close](close.md)): reflect, docs, resonate, validate and the Git review of the whole change set, its gate. `/draft` writes it last (missing: Close Exceptions).
   - `/reflect`, or Close, replaces stages whose gates are all marked passed with their outcome and deletes the section when every stage is done; history stays in version control (else Exceptions).
   - Direction is the notebook's most temporary part; retiring it, like Acceptance Gates, shrinks what later sessions load.
3. **Acceptance Gates:** A list of conditions for done (Formats).
   - `/realize` runs the mechanical gates in VALIDATE; `/validate` runs them with the Validation block.
   - Human gates: at the end of the work, step 2's `+++STOP` and step 4's marks.
   - Accepted when every gate is marked passed; `/reflect`, or Close, then retires the section, first moving mechanical gates that keep running to Validation.
4. **Passed marks:** A gate passes when its command gives the expected result or the human approves it, at the gate or in advance ([Approval](approval.md)). The marks (Formats) record progress and acceptance: `/reflect` reads them and never infers a pass from conversation memory.
5. **Aligned check references:** When the approved `/realize` plan moves a validation target or reference, align Scopes and Validation before that stage's check, keeping its purpose, expected result and coverage, and show the old and new mapping in the change set; no gate, Binding Decision or Experience item changes, and a real failure still stops the work.

## Formats

- Binding Decisions header: `| Decision | Why it binds | Source |`; `| Decision | Scope | Why it binds | Source |` when scopes bind different technologies.
- Source cell: the human's dated quoted words, `approved /draft report (<date>)` for a row approved with a report, or `approved in /realize plan (<date>)` for a delegated choice.
- Unbound line, under the table: `Unbound: <topic> — options A / B (delegated to /realize | awaiting choice)`.
- Direction header: `| Stage | Work (parallel lanes) | Human sees | Gate |`.
- Approved plan line, under the table: `Approved plan (<date>): files to touch, approach, Unbound choices made`.
- Pass mark: `passed <date>`, in the stage's Gate cell for Direction and after the gate for Acceptance Gates.
- Advance approval, same place, written the moment the user names the gate: `approved in advance (<date>)`, then `passed <date>` when the stage or work ends.
- Acceptance Gates lines: a mechanical gate `- <command> → <expected result>` (result when exit code alone does not decide); a human gate `- human: <what is reviewed>`.
- Validation block, one entry per check:

  ```
  # V<n>: <scopes the check covers>
  <command>
  # expected: <value when exit code alone does not decide>
  ```

## Example

Under `## Direction`, as it reads after `/realize` passed stage S1 (2026-10-21):

```markdown
| Stage | Work (parallel lanes) | Human sees | Gate |
|-------|-----------------------|------------|------|
| S0 | Settle the search API as a CLI | sample CLI output | `npm test`, passed 2026-10-20 |
| S1 | Three screen states (normal, empty, failure), one lane each | three screenshots | human approval, approved in advance (2026-10-20), passed 2026-10-21 |
| Close | reflect, docs, resonate, validate, Git review of the whole change set | final diff and the summary of design.md changes | Git review |

Approved plan (2026-10-20): files `cli/search.ts`, `app/search/**`; approach: CLI first, then the three states as three lanes; Unbound choices made: Language → TypeScript
```

## Exceptions

| Situation | Behavior |
|---|---|
| An `existing heading` under another name | Keep it; `/reflect` proposes one mapping onto Operands and never forces a rename |
| A technology already in the `existing code` | An existing premise, shown in reports; a row only when the human gives a reason |
| A decision found only in `automatic memory` | A recall layer: at most a premise shown in reports, a proposal until the human records it in the notebook |
| A command `argument` names a technology other than a Binding Decision | The notebook wins: the argument is a Binding Decision change and halts the command |
| The deliverable is a document or slides (`output format`) | The output format is the Binding Decision |
| The human `delegated` a choice | `Unbound:` line (Formats), then Operation step 1 |
| A technology is named with `no reason` | Ask once; without an answer, `Unbound: … (awaiting choice)` |
| The notebook is `not version controlled` | `/reflect` quotes the removed stages and gates in its REPORT |
| The project's guidance names an `other notebook file` | Read and write it wherever this protocol or a command says `design.md`, by the same section rules |

## Implementation

Loading is the host's part ([Claude Code](hosts/claude-code/start.md), [Codex](hosts/codex/start.md)); without an adapter, Phase 0 reads the notebook. The section rules are instructions in every host; a worker reads only the sections its prompt names.
