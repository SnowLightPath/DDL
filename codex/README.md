# DDL for Codex

The Codex side of [Design-Doc Loop (DDL)](../docs/en/design_philosophy.md): the skills, the protocol skill `ddl-protocol`, and the adapter. This directory has the layout of a project's root: `AGENTS.md` (the template for a project's `AGENTS.md`), `.agents/skills/<name>/` for the eight skills and `ddl-protocol` (each with `SKILL.md` and `agents/openai.yaml`), and the adapter in `.codex/` (`config.toml`, `agents/`, `hooks.json`, `hooks/`, `rules/`).

## Installation

**In the environment** (recommended). One clone serves every project:

```bash
git clone https://github.com/SnowLightPath/DDL.git
bash DDL/bin/install.sh --codex
```

The script symlinks `~/.codex/skills/<name>` for the nine skills, `~/.codex/agents/explorer.toml` and `worker.toml`, `~/.codex/hooks/ddl_gate.py`, and `~/.codex/rules/ddl.rules`, and merges the gate hooks into `~/.codex/hooks.json`; existing entries are kept. If Codex asks, run `/hooks` once to trust the DDL hooks. Without `--codex`, it installs for each runtime whose home directory exists (`~/.claude`, `~/.codex`). `bash DDL/bin/doctor.sh` checks the install; `bash DDL/bin/uninstall.sh` removes the links and the merged fragment. To update, `git pull` in the clone (the links follow) and run `bash DDL/bin/install.sh` again; it is idempotent.

A project then needs only `design.md` and a short `AGENTS.md`:

```bash
cp DDL/codex/AGENTS.md your-project/AGENTS.md
```

**In the project.** Copy the skills, the adapter, and `AGENTS.md` into the project root (`bash DDL/bin/install.sh --project your-project` does the same copy):

```bash
cp -R DDL/codex/{.agents,.codex,AGENTS.md} your-project/
```

Codex loads the project's `.codex/` (config, custom agents, hooks, and rules) only when you trust the project. Then run `/hooks` in Codex once to review and trust the DDL hooks in `.codex/hooks.json`; they run only after that.

Either way, the rules are the same without the adapter, as instructions; the adapter enforces the mechanical part. A skill run from the environment install follows the project's own copy (`.agents/skills/<name>/SKILL.md`) when the project has one, and a project's `commands/<name>.md` adds project facts to a skill (target paths, protected terms, validation commands) without copying the whole skill. Skills look up the protocol, when it is not already in context, in the project's copy `.agents/skills/ddl-protocol/SKILL.md`, then the user-level copy `$HOME/.codex/skills/ddl-protocol/SKILL.md`.

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
| `$resonate` | `$resonate`, `$resonate <path>` | Synchronize multilingual document versions |
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
4. **STOP gates** — mandatory human approval before mutating shared artifacts; Codex ends its turn and waits, starting or messaging no agent until approval; an advance approval is written after its gate at once as `approved in advance (<date>)`; a conversation summary (compaction) approves nothing: when the report a STOP asked about is no longer in context verbatim, the skill rebuilds it from design.md, git, and the files it described and asks again, and what the user approves is written to design.md at once (protocol §1.5)
5. **Markers** — `+++DDL_PHASE` before a mutating phase (required in Codex) and `+++DDL_REPORT` at every STOP (protocol §2.5)
6. **Session start** — Codex loads `AGENTS.md` (the short project file) at session start, the SessionStart hook injects design.md then and again after a compaction (when the hooks are trusted; otherwise the skill reads it), and the protocol skill `ddl-protocol` loads when a skill runs (Phase 0); a subagent reads only the files and design.md sections its prompt names. Codex memories are a recall layer: a decision found only there is a proposal until design.md records it
7. **Adapter** — `.codex/hooks.json` with `hooks/ddl_gate.py` (the gate: after a `+++DDL_REPORT` and until your next prompt, `apply_patch`, writing shell commands, `spawn_agent`, and MCP tool calls are denied; and design.md is injected at session start and after a compaction, so it is in context without a read), `.codex/agents/` (`explorer`, `worker`), `agents/openai.yaml` in each skill (keeps Codex from starting it on its own), and `.codex/rules/ddl.rules` (a prompt before `git push`; a session whose approval policy never prompts shows nothing, and the approval in the `$commit` report still applies). The rules are the same without the adapter, as instructions (protocol §1.5). The gate is a `python3` script (standard library only); if `python3` is missing, the hook fails open and the rules hold as instructions.
8. **Constraints** — invariants that must never be violated

> **Note**: [Subagents](https://developers.openai.com/codex/subagents) are on by default in current Codex releases, and `+++SWARM` uses the `explorer` and `worker` agents in `.codex/agents/`. Subagents inherit the session's sandbox and approval settings, so `explorer` stays read-only through its instructions and the lead's prompt, not through a separate sandbox; set the sandbox and approval policy on the Codex session. A subagent may fork the lead's conversation (`fork_turns`), but DDL prompts are self-contained anyway (scope paths, the Experience items the scope serves, principles, Binding Decisions, the Direction stage, the scope's validation commands, the approved rows verbatim, and in `$realize` the approved plan), and that prompt is the subagent's whole context, so no agent depends on it. A subagent may also spawn agents of its own, so the agent files and the prompts tell every agent to start none: only the lead fans out. When subagents are turned off (`agents.enabled = false`) or not provided, the lead runs the assignments itself (the fallback in protocol §2.5). The gate hook `.codex/hooks/ddl_gate.py`, wired in `.codex/hooks.json`, refuses writes, agent starts, and MCP tool calls after a `+++DDL_REPORT` until your next prompt, so a STOP holds even when the model would continue.

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

Details are in protocol §3 (`.agents/skills/ddl-protocol/SKILL.md`).

## Philosophy

These skills are **optional tools**, not required process.

From design_philosophy.md:
> DDL is not a rigid process—it's a collection of desired designs.
> DDL documents are not final artifacts—they're temporary notes until the design is reflected in code.
