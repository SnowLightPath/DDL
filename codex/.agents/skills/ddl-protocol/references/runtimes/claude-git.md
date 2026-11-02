# Claude Code: Git review

## Read when

Read this before the shared [Git review](../git-review.md) procedure, for every ordinary `git commit` or `git push` (the Close step and `/commit`). It names the helper path, the choice tool and the native push rule in Claude Code.

## Mapping

| Concern | Procedure |
|---|---|
| Prepare | Run `python3 "$HOME/.claude/hooks/ddl_gate.py" prepare-git-review --runtime claude` with the JSON (`language`, `operations[]` with `cwd` and `command`) on stdin; project copy `python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/ddl_gate.py`, development source `tools/ddl_gate.py` in this repository. The helper snapshots the staged set and returns `reviewId` (`G-<id>`), `report` (the path of `report.md`), `question` and `nativeRequest`. Show the ID and link the report before asking. Use the shell tool's working directory for the intended repository. |
| `nativeRequest` | Pass `nativeRequest` unchanged as the arguments of `AskUserQuestion`, keeping its exact title, labels, descriptions and selection mode, and wait for the actual submitted answer. The hook matches the prepared review with the actual request/result ID, the full request and a human-source submission; a timeout (`afkTimeoutMs`), an unavailable choice or an unprovable result does not authorize Git. A typed approval cannot replace the native answer. |
| Revocation | An ordinary `UserPromptSubmit` revokes older preparations at once, even before the transcript flushes; resume or compaction invalidates them through the session epoch (`<session>.git-epoch`). Prepare again after such a boundary and after any change to the staged set, message or branch. |
| Push confirmation | `permissions.ask` rule `Bash(git push *)` in `.claude/settings.json` asks for native permission in every permission mode. It is additional to the content review, never a replacement: a native grant without a matched review is denied. |
| Attribution | `attribution` in `.claude/settings.json` is empty (`commit` and `pr` empty, `sessionUrl: false`); never add AI attribution in the message by hand. |

## Observed

| Fact | Version | Date |
|---|---|---|
| The gate hook ran at 0.04 s per call on this repository's live transcript, within the `timeout: 10` budget | Claude Code 2.1.302 | 2026-10-18 |
| Idle auto-resolution of `AskUserQuestion` carried `afkTimeoutMs` even when selected answers were returned; the gate does not count such a result as the human submission a Git review needs | Claude Code 2.1.316 | 2026-11-01 |

## Coverage

- The hook denies recognized ordinary `git commit` and `git push` calls that reach PreToolUse without a prepared review matched to the actual native submission and the current Git snapshot (repository, base, staged contents, message, branch; for a push the source commit, resolved remote and destination), even while a STOP is open or native prompts are suppressed. Git read commands keep working.
- The check covers recognized calls dispatched through the hook, not arbitrary programs, aliases, state-changing Git hooks, concurrent index changes or input to an existing process; it never grants, rewrites or stages. Review files under `<state dir>/git-reviews/<id>/` (`report.md`, `review.json`, patches) carry no approval flag; the submission must be proved from the conversation record.
- An unprovable recognized review fails closed inside a running handler, while a runtime-level hook failure or timeout can still fail open; verification uses a shorter internal time budget than the hook's `timeout: 10`. Installation diagnostics and deterministic tests use simulated dispatch, which proves neither native hook trust nor the live choice UI.
