# Codex: start

## Read when

Read this once per Codex session before the first command step, after the entry [DDL protocol](../../SKILL.md); it supplies the Codex names and paths that the host-neutral [Notebook](../notebook.md), [Close](../close.md) and [Command authoring](../command-authoring.md) procedures leave open. Before an operation, read [approval](codex-approval.md), [parallel work](codex-parallel.md) or [Git review](codex-git.md).

## Mapping

| Concern | Procedure |
|---|---|
| Invocation | `$command` (skill). A skill lists its name and description and loads its body on `$name`; its `agents/openai.yaml` with `allow_implicit_invocation: false` keeps Codex from starting a command skill on its own. The Codex skills are generated from the Claude Code ones by `tools/sync_mirrors.py`; the protocol skill is the same text. |
| Protocol lookup (Phase 0, step 1) | The project's copy `.agents/skills/ddl-protocol/SKILL.md` (or the file the project's instruction file names as the protocol), then the user-level copy `$HOME/.codex/skills/ddl-protocol/SKILL.md`. |
| Runtime guidance (Phase 0, step 2) | `AGENTS.md`. |
| Session start | The `AGENTS.md` chain (global, then project root down to the working directory) is read once per run before any work. Memories are injected when `memories.use_memories` is on; treat them as a recall layer, not a source of rules: a decision found only there is a proposal until design.md records it. |
| Compaction | The conversation is summarized; the adapter's SessionStart hook runs again on compact (and on resume, fork and clear), injects design.md and re-states a pending report. Re-read procedures and files no longer in context and rebuild a pending report verbatim. |
| Notebook loading (Phase 0, step 3) | The SessionStart hook in `.codex/hooks.json` (`session-start --runtime codex`, `additionalContextLimit: 0`) injects design.md as additional context on startup, resume, compact, fork and clear, when the hook is enabled and trusted. When it is not, Phase 0 reads design.md. |
| Project copy and overlay | `.agents/skills/<name>/SKILL.md` runs even when `$HOME/.codex/skills/<name>/SKILL.md` exists (Codex lists both under the same name, and the command's Phase 0 follows the project's copy). `commands/<name>.md` at the project root adds project facts unless it declares itself a full override. Deploy the user-level copy to `$HOME/.codex/skills/`. |
| Adapter paths | `.codex/` (`config.toml`, `agents/`, `hooks.json`, `hooks/`, `rules/`) plus the project `AGENTS.md`; the user-level install is the same files under `$HOME/.codex/` (DDL's `bin/install.sh`), except `config.toml`, which is set by hand. Project-local configuration needs project trust; user-level hooks are independent of that trust. Review new or changed hooks in `/hooks` when the host requests it. Hooks, agent files and rules may name tools; command files never do. Absent or untrusted, the adapter enforces nothing and every rule holds as an instruction; a renamed or removed tool changes these four host files and the adapter only. |
| `+++DDL_PHASE` | Required: emit `+++DDL_PHASE: <PhaseName>` as the first line of a mutating phase (Codex is execution-forward; the marker keeps the checkpoint visible). |
| `+++DDL_REPORT` | Required: emit a line-initial `+++DDL_REPORT` before every STOP report; the Stop hook records it (see [approval](codex-approval.md)). |

## Observed

| Fact | Version | Date |
|---|---|---|
| In `codex exec` design.md was injected at session start by the SessionStart hook and `transcript_path` was set | codex-cli 0.163.0 | 2026-10-18 |
| A probe with a trial skill in both `~/.codex/skills` and `$HOME/.agents/skills`, listed through `codex exec`, read both locations | codex-cli 0.163.0 | 2026-10-18 |
| Ordinary validation, design creation and the stop on a missing required reference ran as specified in a `codex exec` run | Codex CLI 0.166.0 | 2026-11-02 |

## Coverage

- Enforced: design.md injected by the SessionStart hook on startup, resume, compact, fork and clear, and `allow_implicit_invocation: false` on command skills, when Codex runs the project's `.codex/` under project trust or the user-level `$HOME/.codex/` hooks.
- Limits: an untrusted project, a disabled hook or a host that does not run hooks leaves Phase 0 to read design.md; the 2026-11-02 CLI run proves command exit codes and the stop on a missing reference, not the GUI, an actual compaction or hook trust in another host.
- Instructions: the `AGENTS.md` chain, the Phase 0 read order, `+++DDL_PHASE`, `+++DDL_REPORT`, and memories as a recall layer rather than a decision.
