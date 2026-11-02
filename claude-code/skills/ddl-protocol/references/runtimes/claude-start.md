# Claude Code: start

## Read when

Read this once per Claude Code session before the first command step, after the entry [DDL protocol](../../SKILL.md); it supplies the Claude Code names and paths that the host-neutral [Notebook](../notebook.md), [Close](../close.md) and [Command authoring](../command-authoring.md) procedures leave open. Before an operation, read [approval](claude-approval.md), [parallel work](claude-parallel.md) or [Git review](claude-git.md).

## Mapping

| Concern | Procedure |
|---|---|
| Invocation | `/command`. A command skill loads its body on `/name`; its frontmatter `disable-model-invocation: true` keeps the model from starting it on its own and `argument-hint` shows the user an argument hint. The protocol skill lists its name and description and loads its body when read or used. |
| Protocol lookup (Phase 0, step 1) | The project's copy `.claude/skills/ddl-protocol/SKILL.md` (or the file the project's instruction file names as the protocol), then the user-level copy `$HOME/.claude/skills/ddl-protocol/SKILL.md`. |
| Runtime guidance (Phase 0, step 2) | `CLAUDE.md` or `.claude/CLAUDE.md`. |
| Session start | Already in context: the user `CLAUDE.md`, the project `CLAUDE.md` or `.claude/CLAUDE.md` (which imports design.md when the adapter is installed) and the automatic memory file; nested `CLAUDE.md` and path-scoped rules load on demand. Do not read these again. Treat automatic memory as a recall layer: a decision found only there is a proposal until design.md records it. |
| Compaction | The project `CLAUDE.md` and the automatic memory are re-injected from disk, and the adapter's SessionStart hook (on startup, resume, compact, fork and clear) re-states a pending report. The conversation is summarized and early instructions may be lost: re-read procedures and files no longer in context and rebuild a pending report verbatim. |
| Notebook loading (Phase 0, step 3) | The `@../design.md` import line in `.claude/CLAUDE.md` (`@design.md` from a root `CLAUDE.md`; a project whose notebook is another file points the line at that file), loaded with the guidance at session start. Subagents receive it unless their definition sets `omitClaudeMd`. An import whose file does not exist is skipped silently; when the import is unavailable, Phase 0 reads design.md. |
| Project copy and overlay | A project's own copy `.claude/skills/<name>/SKILL.md` runs even when a user-level copy `$HOME/.claude/skills/<name>/SKILL.md` exists: Claude Code lists the user-level skill first, and the command's Phase 0 follows the project's copy. `commands/<name>.md` at the project root adds project facts to the command unless it declares itself a full override. |
| Adapter paths | `.claude/settings.json` (hooks, `env`, `permissions`, `attribution`), `.claude/agents/` (`explorer.md`, `worker.md`), `.claude/hooks/` (`ddl_gate.py`) and the import line in `.claude/CLAUDE.md`; the user-level install is the same files under `$HOME/.claude/` (DDL's `bin/install.sh`). Hooks, agent definitions and permission rules may name tools; command files never do. Absent or untrusted, the adapter enforces nothing and every rule holds as an instruction; a renamed or removed tool changes these four host files and the adapter only. |
| `+++DDL_PHASE` | Recommended: emit `+++DDL_PHASE: <PhaseName>` as the first line of a mutating phase, above all in long sessions. |
| `+++DDL_REPORT` | Required: emit a line-initial `+++DDL_REPORT` before every STOP report; the Stop hook records it (see [approval](claude-approval.md)). |

## Observed

| Fact | Version | Date |
|---|---|---|
| A fresh session quoted design.md without reading a file: the `@../design.md` import loaded it with `.claude/CLAUDE.md` | Claude Code 2.1.302 | 2026-10-18 |
| An `@` import whose file does not exist was skipped silently | Claude Code 2.1.302 | 2026-10-18 |
| Fable 5.1 at xhigh effort read the entry and this file in order, ran validation, emitted `+++DDL_REPORT`, and with the native choice unavailable explained it and left the work unapproved | Claude Code 2.1.316 | 2026-11-02 |
| Haiku 5.5 at low effort omitted parts of the read order and the markers in the same setup | Claude Code 2.1.316 | 2026-11-02 |
| A protocol file named `claude.md` under `references/runtimes/` was injected as a nested `CLAUDE.md` instruction file when a file in that directory was read: the filesystem is case-insensitive and Claude Code loads nested `CLAUDE.md` files on demand. The start files are therefore named `claude-start.md` and `codex-start.md` | Claude Code 2.1.316 | 2026-11-02 |

## Coverage

- Enforced: design.md in context at start and after compaction through the import line (when `.claude/CLAUDE.md` carries it and the file exists), the SessionStart re-statement of a pending report, and `disable-model-invocation` on command skills, when Claude Code loads the trusted project or user-level settings.
- Limits: a missing import file is silent; early conversation instructions lost at compaction return only by re-reading; the 2026-11-02 CLI checks prove the read order and the markers for one model and effort each, not an actual compaction.
- Naming: never name a protocol file `claude.md` or `CLAUDE.md`; on a case-insensitive filesystem Claude Code injects it as a nested instruction file whenever a neighbouring file is read, which adds unintended context and is not an adapter mechanism.
- Instructions: the Phase 0 read order, `+++DDL_PHASE`, and memory as a recall layer rather than a decision.
