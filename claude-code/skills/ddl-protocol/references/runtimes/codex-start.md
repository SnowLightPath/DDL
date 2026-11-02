# Codex: start

## Read when

Read once per Codex session after the entry [DDL protocol](../../SKILL.md) and before the first command step; it supplies the Codex paths and hook events the shared procedures leave open, while [approval](codex-approval.md), [parallel work](codex-parallel.md) and [Git review](codex-git.md) name the Codex tools of each operation.

## Mapping

| Concern | Procedure |
|---|---|
| Session start | The `AGENTS.md` chain (global, then the project root down to the working directory) is read once per run before any work; memories are injected when `memories.use_memories` is on. |
| Compaction | The conversation is summarized; the SessionStart hook runs again on compact (also on resume, fork and clear), injects design.md and re-states a pending report. |
| Notebook loading | The SessionStart hook in `.codex/hooks.json` (`session-start --runtime codex`, `additionalContextLimit: 0`) injects design.md as additional context on startup, resume, compact, fork and clear, when the hook is enabled and trusted. |
| Adapter paths | `.codex/config.toml`, `.codex/agents/`, `.codex/hooks.json`, `.codex/hooks/`, `.codex/rules/` and the project `AGENTS.md`; `bin/install.sh` puts the same files under `$HOME/.codex/`, except `config.toml`, which is set by hand. Project-local configuration needs project trust, user-level hooks do not; review new or changed hooks in `/hooks` when the host asks. |
| `+++DDL_PHASE` | Must: `+++DDL_PHASE: <PhaseName>` as the first line of every mutating phase. |
| `+++DDL_REPORT` | Must; the Stop hook records the marker, as `transcript_path` may be null ([approval](codex-approval.md)). |

## Observed

| Fact | Version | Date |
|---|---|---|
| In `codex exec` design.md was injected at session start by the SessionStart hook and `transcript_path` was set | codex-cli 0.163.0 | 2026-10-18 |

## Coverage

- Enforced: the SessionStart injection above and `allow_implicit_invocation: false` in `agents/openai.yaml` of command skills, when Codex runs the project `.codex/` under project trust or the user-level `$HOME/.codex/` hooks.
- Limits: an untrusted project, a disabled hook or a host that does not run hooks leaves Phase 0 to read design.md; the GUI, an actual compaction and hook trust in another host are unverified.
