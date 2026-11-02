---
name: ddl-protocol
description: "Use when executing or authoring a Design-Doc Loop command that uses phases, DETECT, STOP, SWARM, or design.md-driven workflow control."
---

# DDL protocol

Design-Doc Loop: a human-LLM workflow protocol. A command describes its work
in phases; this protocol holds the shared rules.

## Start

1. Links resolve relative to the selected protocol file (Phase 0 selects it).
   A missing, unreadable or version-uncertain reference stops the affected
   operation: say what is unconfirmed, never fill it from another installation.
2. Read the host's start file, [Claude Code](references/runtimes/claude-start.md)
   or [Codex](references/runtimes/codex-start.md); another host uses its
   documented capabilities. Never invent a tool.
3. Read `design.md` (or the file the project names as its notebook) and project
   guidance only when not already in context.
4. Only host files and the adapter name tools; commands and references state
   meaning.

## Instruction set

Commands are programs and this protocol is their instruction set: the
processor (the LLM) runs each `+++` directive by the procedure defined here,
and the host harness implements the processor through the host files.

| Directive | Syntax | Count | Placement | Rule |
|---|---|---|---|---|
| `# header` | `# command-name` and a one-line intent | 1 | command file | The first heading names the command, the next line states its purpose. |
| `## Usage` | `## Usage` and a dash list of invocations | 1+ | command file | One item per form, `/command` or `/command <arg>`, each with its behavior. |
| `### Phase` | `### Phase N: NAME` | 3+ | command file | N from 0, ascending by one; at least INIT, a work phase and REPORT. Phase 0 reads only what is not in context, in the order of its shared lines (Examples); roles: Command authoring Fields. |
| `+++DETECT` | `+++DETECT:` then indented `D1: name — trigger` lines | 1+ | phase body; `G<n>` in the guidance file binds every command | D from 1, unique and ascending per command; each trigger operationally verifiable; check a phase's targets in parallel. |
| `+++STOP` | `+++STOP: always` / `+++STOP: on D<n>` | 1+ | phase body | `always` is required at REPORT; `on D<n>` halts when that detection fires. A STOP is an executable halt: run Approval, never auto-proceed; the phase after `always` opens with the `**Pre-condition.**` line (Command authoring Formats). |
| `+++SWARM` | `+++SWARM: <condition>` then a fenced operand block (Parallel work Syntax) | 0+ | phase body | Fan `each` out to workers, one per unit or batch. The condition counts scopes in `design.md` or the units the command names; Scale decides inline, skip and batches. |
| `+++NEVER` | `+++NEVER: <prohibition in the imperative>` | 1+ | command `## Constraints`; global in the guidance file | Binds this command, or every command from the guidance file; refuse the prohibited action in every phase. |
| `+++Report` | `+++Report:` then labeled lines (labels: Approval Formats) | 0–1 | REPORT phase body | Content contract at a STOP: the command says what the user reviews; Approval says how to present and ask. |
| `+++DDL_PHASE` | `+++DDL_PHASE: <PhaseName>` | 0+ | runtime output | Output marker on the first line of a mutating phase, paired with its heading; the host start file says whether it is required. |
| `+++DDL_REPORT` | `+++DDL_REPORT` alone on a line, then the report | 0+ | runtime output | Output heading before the decision report at every STOP, in every host. |

- Markdown headings mark document structure and are never instructions.
- A `+++` line in a phase body is an instruction; the fenced block after
  `+++SWARM:` holds its operands.
- `+++DDL_PHASE` and `+++DDL_REPORT` are output markers: a command file writes
  them only inside a rule, never as output lines.

## Pending STOP

- While a decision STOP is pending, call no tool that mutates the work and
  start or continue no worker.
- The native question is the sole exception; opening it grants no work
  permission. Before it, or after an actual request for clarification,
  read-only tools may clarify the report, never begin the next phase.

## Reading map

| Before | Read |
|---|---|
| Notebook sections, decisions, plans, gates, marks | [Notebook](references/notebook.md) |
| A `+++SWARM` selecting two or more units | [Parallel work](references/parallel-work.md) |
| A decision report or a human gate at a STOP | [Approval](references/approval.md) |
| Close | [Close](references/close.md) |
| An ordinary commit or push, in any command | [Git review](references/git-review.md) |
| Creating or changing a command | [Command authoring](references/command-authoring.md) |
| A form in Formats is not enough (report, notebook row, SWARM block, command) | [Examples](references/examples.md) |

Read a procedure before the action, with the host file its Runtime names.

## Interruption

- After compaction or restart, reconstruct the phase and durable state from
  the notebook, passed marks, git and the current files; reload procedures no
  longer in context, and rebuild a pending report not present verbatim before
  presenting it again.
- An adapter that does not enforce a rule, or cannot be used, leaves the rule
  an instruction; claim no broader coverage. A renamed or removed tool changes
  host files and adapter only.
