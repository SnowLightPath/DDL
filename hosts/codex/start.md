# Codex: start

## Read when

Read once per Codex session after the entry and before the first command step; it supplies the Codex paths and hook events the shared operations leave open, while the approval, parallel work and Git review implementations name the Codex tools of each operation.

## Mapping

| Concern | Implementation |
|---|---|
| Session start | The `AGENTS.md` chain (global, then the project root down to the working directory) is read once per run before any work; memories are injected when `memories.use_memories` is on. |
| Compaction | The conversation is summarized; the SessionStart hook (Notebook loading) runs again, injects design.md and re-states a pending report's ID and file. |
| Notebook loading | The SessionStart hook in `.codex/hooks.json` (`session-start --runtime codex`, `additionalContextLimit: 0`) injects design.md as additional context at every SessionStart event (wiring: Approval Implementation), when the hook is enabled and trusted. |
| Adapter paths | `.codex/config.toml`, `.codex/agents/`, `.codex/hooks.json`, `.codex/hooks/`, `.codex/rules/` and the project `AGENTS.md`; `bin/install.sh` puts the same files under `$HOME/.codex/`, except `config.toml`, which is set by hand. Project-local configuration needs project trust, user-level hooks do not; review new or changed hooks in `/hooks` when the host asks. |
| `+++DDL_PHASE` | Must. |
| `+++DDL_REPORT` | Must; the Stop hook records the marker, as `transcript_path` may be null (Approval Implementation). |

## Observed

| Fact | Version | Date |
|---|---|---|
| In `codex exec` design.md was injected at session start by the SessionStart hook and `transcript_path` was set | codex-cli 0.163.0 | 2026-10-18 |

## Coverage

- Lookup: Codex lists a project skill and a user-level skill of the same name both; Phase 0 reads the project copy by path.
- Enforced: the SessionStart injection above and `allow_implicit_invocation: false` in `agents/openai.yaml` of command skills, under the trust in Adapter paths.
- Limits: an untrusted project, a disabled hook or a host that does not run hooks leaves Phase 0 to read design.md; the GUI, an actual compaction and hook trust in another host are unverified.
