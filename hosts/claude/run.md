# Claude: run

## Read when

Read with the Run operation before a plan names a grant; it names the gate's grant and event records, the transcript fields behind the counts and the subcommands.

## Mapping

| Concern | Implementation |
|---|---|
| Grant record | The gate writes it at the first PreToolUse call after the human's answer to the prepared plan question (Stop as fallback), in the user-level store: `$DDL_GATE_GRANT_DIR`, else `$XDG_STATE_HOME/ddl-gate`, else `$HOME/.local/state/ddl-gate`. |
| Event record | `.ddl/events.jsonl` in the project's main work tree; the hook's four events append to it. |
| Answer time | From a transcript: the `timestamp` of the entry that holds the question's tool call and of the entry that holds its answer (`toolUseResult.answers`). From the ledger (a Run or a session): the hook's clock at the question's PreToolUse call, and that `timestamp` of the answer. An idle auto-resolution carries `afkTimeoutMs` and counts as a timeout. |
| Subcommands | `python3 "$HOME/.claude/hooks/ddl_gate.py" report --run <N-id>` (or `--session <id>`, or `--runtime claude --transcript <file>`), `run-start` (JSON on stdin) and `run-item <N-id> <item> <status>` likewise, or the project copy, from inside the project; unavailable while a decision is pending. |

## Observed

| Fact | Version | Date |
|---|---|---|
| In one session's transcript six questions carrying a report or review ID had a `timestamp` on the entry of the question's tool call and on the entry of its answer, 10 to 291 seconds apart; no submitted answer carried `afkTimeoutMs` | Claude Code 2.1.330 | 2026-11-23 |

## Coverage

- Recording a grant is covered by simulated dispatch only; no live recording was observed.
- Only the gate's own denials are counted; a native permission rejection is not.
- Claude writes the transcript asynchronously: the grant and the `answered` line are written at the first PreToolUse call or Stop at which the transcript holds the answer.
