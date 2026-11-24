# Claude: run

## Read when

Read with the Run operation before a plan names a grant, a snapshot is made or a resource is used; it names the gate's grant and event records, its decision under a grant, the transcript fields behind the counts, the subcommands and how resources are reached.

## Mapping

| Concern | Implementation |
|---|---|
| Grant record | The gate writes it in the user-level store (`$DDL_GATE_GRANT_DIR`, else `$XDG_STATE_HOME/ddl-gate`, else `$HOME/.local/state/ddl-gate`) at the first PreToolUse call or Stop whose transcript holds the human's answer (step 1). |
| Decision | PreToolUse answers a call step 1 allows with `permissionDecision: allow`, reason `DDL: inside grant <R-id> (<kind>)`, and one it denies with `deny`. |
| Event record | The hook's five events append to `.ddl/events.jsonl`. |
| Answer time | From a transcript: the `timestamp` of the question's tool-call entry and of its answer's (`toolUseResult.answers`); from the ledger (a Run or a session), the hook's clock at the question's PreToolUse call and that answer `timestamp`. One carrying `afkTimeoutMs` counts as a timeout (approval). |
| Subcommands | `python3 "$HOME/.claude/hooks/ddl_gate.py" report --run <N-id>` (or `--session <id>`, or `--runtime claude --transcript <file>`), `run-start` (JSON on stdin), `run-item <N-id> <item> <status>`, `snapshot [--run <N-id>] [--item <id>] [--git-dir <dir> --work-tree <dir>]` (or `snapshot list`), `run-join <N-id> --peer <name> --runtime claude|codex [--lead]`, `mail send --run <N-id> --to <lead|all|peer> [--kind note|amend|handoff] (--text <one line> | --file <file>) [--as <peer>]` (or `mail read --run <N-id> --peer <peer> [--all]`), `resources`, `measure <machine>`, `remote <machine> [--snapshot <ref|commit>] [--run <N-id>] [--item <id>] [--artifacts <glob>…] [--timeout <minutes>] [--keep] [--confirmed <R-id>] -- <command>…`, `service <name> --prompt-file <file> [--schema <file>] [--approve] [--confirmed <R-id>]` and `runner <N-id> [--max <n>] [--stagger <seconds>] [--timeout <minutes>] [--model <model>] [--host codex|claude]` likewise, or the project copy, from inside the project; unavailable while a decision is pending. |
| Resources | A `codex:` service only through `service`. |
| Mail | A member's main conversation (no `agent_id`) gets its unread mail as `additionalContext` at PreToolUse, PostToolUse, UserPromptSubmit and SessionStart; `run-join`'s PostToolUse binds its `session_id`; a worker gets mail only by its prompt. |

## Observed

| Fact | Version | Date |
|---|---|---|
| In one session's transcript six questions carrying a report or review ID had a `timestamp` on the entry of the question's tool call and on the entry of its answer, 10 to 291 seconds apart; no submitted answer carried `afkTimeoutMs` | Claude Code 2.1.330 | 2026-11-23 |
| A hook's `additionalContext` from the Mail row's four events reached the model (`claude -p`, 4/4 twice); a subagent got only its own PreToolUse and PostToolUse text, and its calls carried the lead's `session_id` and an `agent_id` | Claude Code 2.1.330 | 2026-11-23 |
| `claude -p`, a grant of `tools/**` and `test`: the hook's `allow` ran a test and an in-grant Edit unprompted, its `deny` stopped another; unhooked, all three were refused; with no saved record, no allow | Claude Code 2.1.330 | 2026-11-24 |

## Coverage

- A grant's record is covered by simulated dispatch only, the allow only under `claude -p` (Observed).
- Claude writes the transcript asynchronously, so the grant and the `answered` line may be recorded some calls after the answer.
