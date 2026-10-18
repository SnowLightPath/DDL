# DDL Skills for Codex

Example implementation of [Design-Doc Loop (DDL)](../../docs/en/design_philosophy.md) as OpenAI Codex skills.

## Installation

```bash
# From the DDL repository root, copy the template into your project root
cp -r examples/codex-skills/{.agents,.codex,AGENTS.md} /path/to/your-project/
```

The template mirrors Codex's directory convention — no rearranging needed. Codex loads the project's `.codex/` (config and custom agents) only when you trust the project.

Do not create an empty `design.md`: `$realize`, `$reflect`, and `$validate` refuse to run without one, and an empty file defeats that guard. Run `$draft` instead; it writes `design.md` from the experience you describe.

## Usage

Start Codex in your project:

```bash
codex
```

Then type a skill in the Codex prompt (type `$` to see available skills):

```text
$draft
$realize
$reflect
```

## Skills

### Core Loop

| Skill | Usage | Intent |
|-------|-------|--------|
| `$draft` | `$draft`, `$draft <feature>`, `$draft <feature> <technology or outlook>` | Write the user-side experience first, with the decisions and outlook it depends on |
| `$realize` | `$realize`, `$realize <feature>` | Write code based on design principles and Binding Decisions |
| `$reflect` | `$reflect`, `$reflect <path>` | Update documents based on implementation |

### Support Skills

| Skill | Usage | Intent |
|-------|-------|--------|
| `$validate` | `$validate`, `$validate <scope>` | Run mechanical validation per scope: the Validation block and the mechanical gates in Acceptance Gates |
| `$commit` | `$commit` (local only), `$commit remote` (commit and push) | Record verified changes to repository |
| `$docs` | `$docs`, `$docs <path>` | Audit and fix documentation quality |
| `$refactoring` | `$refactoring`, `$refactoring <path>` | Audit and fix code quality |

## The Loop

```
      Draft
        ↓
Design Document ⇄ Code
   (Realize ↓  ↑ Reflect)
```

## Skill Structure

Every skill follows the same pattern:

1. **Phases** — ordered steps (INIT → SURVEY/READ → WORK → REPORT (+++STOP) → EXECUTE → VERIFY)
2. **Detection Targets** — automated checks that run in parallel within their phase (D1, D2, … per skill), plus the global targets G1–G7 in `AGENTS.md`
3. **+++SWARM** — parallel subagents, one per scope or batch (`explorer` and `worker` in `.codex/agents/`), set by the `team:`, `spawn:`, `type:`, `max:`, `batch:`, `each:`, `collect:` fields; without subagents, the lead runs the assignments itself, with parallel shell reads for read-only work and one by one otherwise
4. **STOP gates** — mandatory human approval before mutating shared artifacts; Codex ends its turn and waits, starting or messaging no agent until approval; an advance approval is written after its gate at once as `approved in advance (<date>)`; a conversation summary (compaction) approves nothing: when the report a STOP asked about is no longer in context verbatim, the skill rebuilds it from design.md, git, and the files it described and asks again, and what the user approves is written to design.md at once (Codex Runtime Contract in `AGENTS.md`)
5. **Codex Runtime Contract** — `+++DDL_PHASE` before mutation and `+++DDL_REPORT` at every STOP (see `AGENTS.md`)
6. **Session start** — Codex loads `AGENTS.md`, with the protocol sections, at session start, and `AGENTS.md` has design.md read then; both stay in context, and a subagent reads only the files and design.md sections its prompt names. Codex memories are a recall layer: a decision found only there is a proposal until design.md records it
7. **Constraints** — invariants that must never be violated

> **Note**: [Subagents](https://developers.openai.com/codex/subagents) are on by default in current Codex releases, and `+++SWARM` uses the `explorer` and `worker` agents in `.codex/agents/`. Subagents inherit the session's sandbox and approval settings, so `explorer` stays read-only through its instructions and the lead's prompt, not through a separate sandbox; set the sandbox and approval policy on the Codex session. A subagent may fork the lead's conversation (`fork_turns`), but DDL prompts are self-contained anyway (scope paths, the Experience items the scope serves, principles, Binding Decisions, the Direction stage, the scope's validation commands, the approved rows verbatim, and in `$realize` the approved plan), and that prompt is the subagent's whole context, so no agent depends on it. A subagent may also spawn agents of its own, so the agent files and the prompts tell every agent to start none: only the lead fans out. When subagents are turned off (`agents.enabled = false`) or not provided, the lead runs the assignments itself (the fallback in `AGENTS.md`).

## design.md Sections

`design.md` is the shared notebook between human and LLM. Skills read and write these sections by heading name. Retiring a section (a spent Direction, accepted Acceptance Gates) also shrinks what every later session loads. Experience is always needed and comes first; Binding Decisions, Direction, and Acceptance Gates are optional, and `$draft` asks about them only when the user's words point to them:

1. **Intent** — why the project exists. Written by: human
2. **Scopes** — scope table; drives SWARM. Written by: human, `$reflect`
3. **Principles** — design principles, under `## Principles` or `## Core Principles`. Written by: `$draft` (D5), `$reflect`
4. **Experience** — consumer-side usage with inputs, outputs, and error / empty / boundary states. Written by: `$draft`, `$reflect`
5. **Binding Decisions** — technology fixed before implementation because the Experience depends on it, an external constraint requires it, or the human prefers it and says so (Decision, Why it binds, Source); only the human binds. Written by: the human through `$draft`; `$realize` records an approved delegated choice
6. **Direction** — non-binding outlook: stages, parallel lanes, what the human sees, and each stage's gates; `$realize` appends `passed <date>` to each gate that passes (after `approved in advance (<date>)` when the gate was waived) and writes the approved plan under the table as `Approved plan (<date>)`. Written by: `$draft`; `$realize` marks gates passed and writes the Approved plan lines; `$reflect` retires passed stages with their Approved plan lines
7. **Acceptance Gates** — mechanical gates and human gates that define done; the work is accepted when every gate is marked passed. Written by: `$draft`; `$realize` marks gates passed; `$reflect` retires the section (lasting checks move to Validation)
8. **Validation** — per-scope mechanical checks. Written by: human, `$reflect`

Details are in the design.md Sections of `AGENTS.md`.

## Philosophy

These skills are **optional tools**, not required process.

From design_philosophy.md:
> DDL is not a rigid process—it's a collection of desired designs.
> DDL documents are not final artifacts—they're temporary notes until the design is reflected in code.
