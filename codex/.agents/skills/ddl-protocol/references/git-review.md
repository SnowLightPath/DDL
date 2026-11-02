# Content-bound Git review

## Read when

Read this before preparing or performing an ordinary Git commit or push in any DDL command, including when the user did not invoke the commit command, and at step 5 of [Close](close.md). The command supplies the change set to stage, the exact message, and whether a push was requested (`remote`). The decision is presented and awaited as in [Approval](approval.md); the host procedure is in [Claude Code](runtimes/claude-git.md) or [Codex](runtimes/codex-git.md).

## Syntax

```
python3 <gate> prepare-git-review --runtime <host>
  stdin:  {"language": <code>, "operations": [{"cwd": <repository>, "command": <git form>}, ...]}
  stdout: {"reviewId": "G-<id>", "report": <path>, "question": <text>, "nativeRequest": <host request>}
```

`<gate>` is the installed gate script and `<host>` is `claude` or `codex`; the host file gives the path. List the operations in execution order, a commit before its dependent push.

## Fields

| Operation | Supported forms | Unsupported forms |
|---|---|---|
| `commit` | `git commit` on a named branch with `--cleanup=verbatim` and `-m <message>` or `-F <UTF-8 file>`; one ready commit per repository in a batch | Forced, mirror, deletion, wildcard, multi-target, in-progress merge/rebase/cherry-pick/revert, intent-to-add, stdin message, alternate executable, dynamic and compound write forms |
| `push` | `git push <remote> <branch or refspec>` with one configured remote and one branch or refspec; `--no-follow-tags` when follow-tags is enabled; `--recurse-submodules=no` when configuration could push submodules; only when explicitly requested, after its commit | The same list, and a push whose source commit, resolved remote or destination differs from the reviewed one |

An unsupported form stops with the reason; do not silently drop a required option or change the meaning. Retry a canonical form only when the original Git options and configuration keep the same meaning. Run Git in the shell tool's working directory for the intended repository; read commands need no review.

## Procedure

Ordinary commits and pushes need this independent review in every DDL command. An implementation approval given before the final diff existed is not this review; clearing the general STOP marker, an assistant's claim of approval and a permission mode that suppresses native prompts do not grant Git permission.

1. **Prepare.** Stage the actual set and write the exact message; include only explicitly requested ready pushes. A batch holds one ready commit per repository and compatible pushes, each commit before its push. Do not discard unrelated changes. Run the helper (Syntax): it snapshots the real staged set, so staging is reversible review preparation, and preparation writes review detail, not approval.
2. **Review.** Emit `+++DDL_REPORT`, show the review ID `G-<id>`, and link the complete report and diff before the question. Pass the returned native request to the host's choice tool unchanged, with its exact title and action labels; append no other approval word and change no scope. The user may approve the whole compatible set, revise it, or hold; for a requested subset, prepare that subset and review it again.
3. **Wait.** Wait for the actual human submission to that exact request, as Approval step 3 says. A prior plan, an ordinary STOP release, an assistant assertion, a timeout, a receipt, an unrelated answer or a no-prompt permission mode is not Git approval.
4. **Keep the reviewed index intact.** The hook matches the native request and the submitted answer by their identifiers, compares the complete request (labels, descriptions, selection mode), checks that the report names this review, and compares the real staged contents, base, message and branch; a push also checks its source commit, resolved remote and destination branch. One answer can cover a ready commit and its push: the push must resolve to the commit with precisely the reviewed parent, tree contents and verbatim message. A changed candidate needs a new review; do not restage newer contents and reuse the answer. Resume or compaction invalidates the preparation: rebuild the review.
5. **Record.** Run exactly the reviewed operations in the reviewed order and report the commit hash as progress. Do not emit a new STOP report between an approved commit and its approved push; finish the reviewed set before the final informational report.

## Formats

- Input JSON keys: `language` (the user's language for the report), `operations` (a list in execution order), each operation with `cwd` (the repository) and `command` (the literal Git form).
- Output JSON keys: `reviewId`, `report` (the path of the report file to link), `question` (the question text), `nativeRequest` (the host's request, passed unchanged).
- The review ID: `G-<id>` (16 hexadecimal characters). The report emitted before the question shows it and links the report file.
- The review directory `<state dir>/git-reviews/<id>/` holds `report.md`, `review.json` and one `<n>.patch` per commit. It carries no approval flag: the submitted native answer is proved from the current conversation record, never from these files, and missing or altered detail denies the recognized call.

## Example

```json
{
  "language": "en",
  "operations": [
    {"cwd": "/path/to/repository", "command": "git commit --cleanup=verbatim -F /path/to/message.txt"},
    {"cwd": "/path/to/repository", "command": "git push origin main"}
  ]
}
```

The helper answers with `reviewId` `G-3f9c0a7e51b2d4c8`, the `report` path, the `question` and the `nativeRequest`; the assistant emits `+++DDL_REPORT`, names `G-3f9c0a7e51b2d4c8` with the report link and the diff, then passes the request on and waits. One submitted approval records the commit and sends the push; without the push operation in the input, nothing is pushed.

## Boundaries

| Situation | Behavior |
|---|---|
| Hold | Nothing is recorded; the index stays as reviewed; the edits stay in the working tree |
| Revision or subset requested | Prepare the revised set and review it again under a new ID; the old answer covers nothing |
| Timeout or automatic submission | Denies the operation; not approval |
| Receipt (the request was accepted, no answer yet) | Not an answer; end the turn on an asynchronous interface, keep waiting on a synchronous one |
| Changed candidate (contents, base, message, branch or push target) after approval | New review; do not restage newer contents and reuse the answer; the hook denies the mismatch |
| Resume in a new session | Invalidates the preparation; rebuild the review |
| Compaction | Invalidates the preparation; rebuild the review; a summary or an old answer is not approval |
| Unsupported form | Stop with the reason; do not silently change the meaning; retry a canonical form only when the options and configuration keep the same meaning |
| Alias, arbitrary program, state-changing Git hook, concurrent index change, or input to an existing process | Outside the check, which covers recognized calls reaching the hook: report the limit rather than promising universal enforcement; the rule still binds as an instruction |
| No adapter, or an adapter that is not trusted | No mechanical guarantee; the same review rule remains an instruction. When the required matching cannot be established, report the limitation and stop; do not bypass the gate or fabricate a receipt |
| Hook failure or timeout at the runtime level | Can fail open; general STOP failures warn and fail open, while a running Git handler denies an unprovable review and verifies within a shorter internal time budget to leave timeout headroom. Do not promise more |
| Unprovable answer (a later report, an unrelated answer, a cancellation, an unreadable reply) | Denies the operation; free-form text remains available for discussion but cannot manufacture the mechanical Git receipt |
| Native permission policy | Still applies after the content check; the hook never grants or rewrites a command; Git read commands keep working |

## Runtime

Read the selected host's procedure next: [Claude Code](runtimes/claude-git.md) or [Codex](runtimes/codex-git.md); they name the gate path, how the native request is passed, what revokes a preparation, and how a push is confirmed. The adapter's hook enforces the match (identifiers, report, staged contents, message, branch, push target) and denies recognized unreviewed commit and push calls, including under no-prompt permission modes where the host file says so. The preparation, the report, the wait and the index discipline remain instructions, and without an adapter the whole rule is an instruction.
