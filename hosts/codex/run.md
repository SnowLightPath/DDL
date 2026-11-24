# Codex: run

## Read when

Read before a plan names a grant, a snapshot is made or a resource is used, with the Run operation; it names the grant store, the hooks' decision under a grant, the event file, the unmeasured answer times, the subcommands and how resources are reached.

## Mapping

| Concern | Implementation |
|---|---|
| Grant record | Written by the gate at the first PreToolUse call that follows the human's reply (step 1), else at Stop; the user-level store is `$DDL_GATE_GRANT_DIR`, else `$XDG_STATE_HOME/ddl-gate`, else `$HOME/.local/state/ddl-gate`. |
| Decision | PreToolUse denies a call step 1 denies and returns nothing for one it allows, which the PermissionRequest hook then allows; none for a call run by a shell other than bash, sh, zsh or dash, and only a read's from a `workdir` outside the root. |
| Event record | The hook's events append to `.ddl/events.jsonl`. |
| Answer time | From the ledger: the hook's clock at the question's PreToolUse call and at the reply's UserPromptSubmit; from a rollout, the `timestamp` of those two lines (unmeasured; none gives `not measured`). |
| Subcommands | `python3 "$HOME/.codex/hooks/ddl_gate.py" report --run <N-id>` (or `--session <id>`, or `--runtime codex --transcript <file>`); `run-start` (JSON on stdin), `run-item <N-id> <item> <status>`, `snapshot [--run <N-id>] [--item <id>] [--git-dir <dir> --work-tree <dir>]` (or `snapshot list`), `run-join <N-id> --peer <name> --runtime claude|codex [--lead]`, `mail send --run <N-id> --to <lead|all|peer> [--kind note|amend|handoff] (--text <one line> | --file <file>) [--as <peer>]` (or `mail read --run <N-id> --peer <peer> [--all]`), `resources`, `measure <machine>`, `remote <machine> [--snapshot <ref|commit>] [--run <N-id>] [--item <id>] [--artifacts <glob>…] [--timeout <minutes>] [--keep] [--confirmed <R-id>] -- <command>…`, `service <name> --prompt-file <file> [--schema <file>] [--approve] [--confirmed <R-id>]` and `runner <N-id> [--max <n>] [--stagger <seconds>] [--timeout <minutes>] [--model <model>] [--host codex|claude]` likewise, or the project copy, from inside the project; unavailable while a decision is pending. |
| Mail | PreToolUse, UserPromptSubmit, SessionStart and a shell call's PostToolUse return a member's unread mail as additional context (unseen: Observed); `codex exec resume <session> "<message>"` wakes a peer between turns. |
| Resources | A `codex:` service carrying `confirm`, and any write to a service, only through `service`; a read may use the plugin itself; `remote` for an ssh machine. |

## Observed

| Fact | Version | Date |
|---|---|---|
| Resuming a session (Mail row) ran one turn of it (5 s); additional context is documented for the Mail row's events, seen only from SessionStart | codex-cli 0.167.2 | 2026-11-23 |
| Under `codex exec -s workspace-write` a shell command could not write under `.git/` but could under a hidden work-tree directory; the user-level hooks ran for PreToolUse and Stop | codex-cli 0.167.2 | 2026-11-23 |

## Coverage

- The gate does not see a plugin call made directly: the Resources row binds as an instruction only.
- No grant is recorded where `transcript_path` is null (its proof reads the rollout) or before the hooks are trusted and enabled.
- Unverified: whether a hook process can write the user-level store (else no grant is recorded); whether a hook runs for a subagent's tool call with an identifier; a live grant record and allow.
