# Claude: start

## Read when

Read once per Claude session, after the entry and before the first command step, for the Claude paths and hook events; the tool names are in the approval, parallel work and Git review implementations.

## Mapping

| Concern | Implementation |
|---|---|
| Session start | In context already, never to be read again: the user and project `CLAUDE.md` (or `.claude/CLAUDE.md`) and the automatic memory file; nested `CLAUDE.md` files and path-scoped rules load on demand. |
| Compaction | The project `CLAUDE.md` and the memory file are re-injected from disk; the SessionStart hook re-states a pending report's ID and file. |
| Notebook loading | The `@../design.md` import line in `.claude/CLAUDE.md` (`@design.md` from a root `CLAUDE.md`, or the project's other notebook file) loads it with the guidance at start and after compaction; subagents get it unless their definition sets `omitClaudeMd`. |
| Adapter paths | `.claude/settings.json` (hooks, `env`, `permissions`, `attribution`), `.claude/agents/explorer.md` and `worker.md`, `.claude/hooks/ddl_gate.py`, the import line in `.claude/CLAUDE.md`; `bin/install.sh` mirrors them under `$HOME/.claude/`. |
| `+++DDL_PHASE` | Should, above all in a long session. |
| `+++DDL_REPORT` | Must; the Stop hook records it (Approval Implementation). |

## Observed

| Fact | Version | Date |
|---|---|---|
| A fresh session quoted design.md without reading a file: the `@../design.md` import loaded it with `.claude/CLAUDE.md` | Claude Code 2.1.302 | 2026-10-18 |
| An `@` import whose file does not exist was skipped silently | Claude Code 2.1.302 | 2026-10-18 |
| A protocol file named `claude.md` beside the implementations was injected as a nested `CLAUDE.md` when a neighbouring file was read (case-insensitive filesystem) | Claude Code 2.1.316 | 2026-11-02 |
| Invoking `ddl-protocol` by name through the `Skill` tool in a `-p` session loaded the user-level copy although the project had its own; only reading the project path reached the project copy | Claude Code 2.1.316 | 2026-11-02 |

## Coverage

- Enforced: the import line, the SessionStart re-statement and `disable-model-invocation: true` in command skill frontmatter, under trusted project or user-level settings.
- Lookup: the `Skill` tool resolves a skill name to the user-level copy; Phase 0 reads the project copy by path (Observed).
- Naming: never name a protocol file `claude.md` or `CLAUDE.md`; it would load as a nested instruction file (Observed).
