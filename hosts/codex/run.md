# Codex: run

## Read when

Read before a plan names a grant, with the Run operation; it names the grant store, the event file, the unmeasured answer times and the subcommands.

## Mapping

| Concern | Implementation |
|---|---|
| Grant record | Written by the gate at the first PreToolUse call that follows the human's reply to the prepared plan question, else at Stop; the user-level store is `$DDL_GATE_GRANT_DIR`, else `$XDG_STATE_HOME/ddl-gate`, else `$HOME/.local/state/ddl-gate`. |
| Event record | The hook's four events append to `.ddl/events.jsonl` in the project's main work tree. |
| Answer time | From the ledger (a Run or a session): the hook's clock at the question's PreToolUse call and at the reply's UserPromptSubmit. From a rollout: the `timestamp` of the question call's line and of the reply message's line, both unmeasured; a line without one gives `not measured`. |
| Subcommands | `python3 "$HOME/.codex/hooks/ddl_gate.py" report --run <N-id>` (or `--session <id>`, or `--runtime codex --transcript <file>`); `run-start` (JSON on stdin) and `run-item <N-id> <item> <status>` likewise, or the project copy, from inside the project; unavailable while a decision is pending. |

## Observed

| Fact | Version | Date |
|---|---|---|
| Under `codex exec -s workspace-write` in a scratch repository a shell command could not create a file under `.git/` and could create one under a hidden directory of the work tree; the user-level hooks ran for PreToolUse and Stop | codex-cli 0.167.2 | 2026-11-23 |

## Coverage

- No grant is recorded where `transcript_path` is null (its proof reads the rollout) or before the hooks are trusted and enabled.
- Counted denials are the gate's own, never a native permission rejection.
- Unverified: whether a hook process can write the user-level store (if not, that grant is never recorded); whether a hook runs for a subagent's tool call with an identifier; a live grant record (simulated dispatch only).
