# Claude: run

## Read when

Read with the Run operation before a plan names a grant, a snapshot is made or a resource is used; it names the gate's grant and event records, its decision under a grant, the transcript fields behind the counts, the subcommands and how resources are reached.

## Mapping

| Concern | Implementation |
|---|---|
| Grant record | The gate writes it in the user-level store (`$DDL_GATE_GRANT_DIR`, else `$XDG_STATE_HOME/ddl-gate`, else `$HOME/.local/state/ddl-gate`) at the first PreToolUse call or Stop whose transcript holds the human's answer (step 1). |
| Decision | PreToolUse answers a call step 1 allows with `permissionDecision: allow`, reason `DDL: inside grant <R-id> (<kind>)`, and one it denies with `deny`. |
| Event record | The hook's four events append to `.ddl/events.jsonl`. |
| Answer time | From a transcript: the `timestamp` of the entry that holds the question's tool call and of the entry that holds its answer (`toolUseResult.answers`). From the ledger (a Run or a session): the hook's clock at the question's PreToolUse call, and that `timestamp` of the answer. An idle auto-resolution carries `afkTimeoutMs` and counts as a timeout. |
| Subcommands | `python3 "$HOME/.claude/hooks/ddl_gate.py" report --run <N-id>` (or `--session <id>`, or `--runtime claude --transcript <file>`), `run-start` (JSON on stdin), `run-item <N-id> <item> <status>`, `snapshot [--run <N-id>] [--item <id>] [--git-dir <dir> --work-tree <dir>]` (or `snapshot list`), `resources`, `measure <machine>`, `remote <machine> [--snapshot <ref|commit>] [--run <N-id>] [--item <id>] [--artifacts <glob>…] [--timeout <minutes>] [--keep] [--confirmed <R-id>] -- <command>…` and `service <name> --prompt-file <file> [--schema <file>] [--approve] [--confirmed <R-id>]` likewise, or the project copy, from inside the project; unavailable while a decision is pending. |
| Resources | A `codex:` service only through `service`. |

## Observed

| Fact | Version | Date |
|---|---|---|
| In one session's transcript six questions carrying a report or review ID had a `timestamp` on the entry of the question's tool call and on the entry of its answer, 10 to 291 seconds apart; no submitted answer carried `afkTimeoutMs` | Claude Code 2.1.330 | 2026-11-23 |
| `claude -p`, a grant of `tools/**` and `test`: the hook's `allow` ran a test and an in-grant Edit unprompted, its `deny` stopped another; unhooked, all three were refused; with no saved record, no allow | Claude Code 2.1.330 | 2026-11-24 |

## Coverage

- A grant's record is covered by simulated dispatch only, the allow only under `claude -p` (Observed).
- Claude writes the transcript asynchronously, so the grant and the `answered` line may be recorded some calls after the answer.
