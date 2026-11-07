# Content-bound Git review

## Read when

Read before preparing or performing any ordinary commit or push in any DDL command, also outside `/commit` and at Close step 5; the command supplies the change set to stage, the exact message and whether a push was requested (`remote`).

## Syntax

```
python3 <gate> prepare-git-review --runtime <host>
  stdin:  {"language": <code>, "operations": [{"cwd": <repository>, "command": <git form>}, ...]}
  stdout: {"reviewId": "G-<id>", "report": <path>, "question": <text>, "nativeRequest": <host request>}
```

`<gate>`: the installed gate script (path: the implementation); `<host>`: `claude` or `codex`.

## Operands

| Git action | Supported forms | Unsupported forms |
|---|---|---|
| `commit` | `git commit` on a named branch with `--cleanup=verbatim` and `-m <message>` or `-F <UTF-8 file>` | Forced, mirror, deletion, wildcard, multi-target, in-progress merge/rebase/cherry-pick/revert, intent-to-add, stdin message, alternate executable, dynamic and compound write forms |
| `push` | `git push <remote> <branch or refspec>` with one configured remote and one branch or refspec; `--no-follow-tags` when follow-tags is enabled; `--recurse-submodules=no` when configuration could push submodules | The same list, and a push whose source commit, resolved remote or destination differs from the reviewed one |

Run Git in the shell tool's working directory for the intended repository; read commands need no review.

## Operation

1. **Prepare.** Stage the actual set, write the exact message and include only explicitly requested ready pushes; a batch holds one ready commit per repository and its compatible pushes, each commit before its push; discard no unrelated change. Run the helper (Syntax); staging is reversible preparation, not approval.
2. **Review.** Emit `+++DDL_REPORT` and the report, then pass the returned native request to the host's choice tool unchanged (exact title and action labels); its five lines carry the review ID and the report file, so the chat report is not evidence. Append no approval word, change no scope. Outcomes: approve the whole compatible set, revise or hold (Exceptions).
3. **Wait.** Wait for the human submission to that exact request (Approval step 3). Not Git approval: an implementation approval given before the final diff existed, a prior plan, an ordinary STOP release, an assistant's claim of approval or a blanket instruction to commit without review, a timeout, a receipt, a cancellation, an unrelated, later or unreadable answer, a permission mode that suppresses native prompts.
4. **Keep the reviewed index intact.** One answer covers a ready commit and its push only when the push resolves to the commit with precisely the reviewed parent, tree and verbatim message. Never restage newer contents under the old answer. Resume or compaction invalidates the preparation: prepare again.
5. **Record.** Run exactly the reviewed Git actions (the `operations` list) in the reviewed order and report the commit hash as progress; emit no new STOP report between an approved commit and its approved push.

## Formats

- Input JSON keys: `language` (the user's language for the report), `operations` (in execution order), each with `cwd` (the repository) and `command` (the literal Git form).
- Output JSON keys: `reviewId`, `report` (the report file), `question` (its five lines: Approval Formats, built from the reviewed operations), `nativeRequest` (the host's request, passed unchanged).
- The review ID `G-<id>`: 16 hexadecimal characters.
- The review directory `<state dir>/git-reviews/<id>/`: `report.md`, `review.json`, one `<n>.patch` per commit.

## Example

The helper's input for one commit and its push; one answer records the commit and sends the push:

```json
{
  "language": "en",
  "operations": [
    {"cwd": "/path/to/repository", "command": "git commit --cleanup=verbatim -F /path/to/message.txt"},
    {"cwd": "/path/to/repository", "command": "git push origin main"}
  ]
}
```

## Exceptions

| Situation | Behavior |
|---|---|
| Hold | Nothing is recorded; the index stays as reviewed; the edits stay in the working tree |
| Revision or subset requested | Prepare the revised set and review it under a new ID; the old answer covers nothing |
| Timeout, automatic submission or receipt | Not approval (step 3): wait or end the turn as Approval says |
| Changed candidate (contents, base, message, branch, push target) after the answer | A new review (step 4); the hook denies the mismatch |
| Resume in a new session, or compaction | Step 4; a summary or an old answer is not approval |
| Unsupported form | Stop with the reason; drop no required option, change no meaning silently; retry a canonical form only when the original options and configuration keep their meaning |
| Alias and the other cases outside the hook's reach (Implementation) | Report the limit; the rule binds as an instruction |
| No adapter, or an untrusted one | No mechanical guarantee; when matching cannot be established, report the limitation and stop; never bypass the gate or fabricate a receipt |
| Hook failure or timeout at the host level | May fail open (Implementation); promise no more |
| Unprovable answer | Denied (step 3); free text may discuss, never manufacture the Git receipt |

## Implementation

The host's implementation: [{Host}](hosts/{host}/git-review.md), folded into this section in the installed skill. Hook coverage (one script, both hosts):

- Matches request and answer by identifier, compares the complete request (labels, descriptions, selection mode), checks that the question carries this review, and compares the real staged contents, base, message and branch; for a push also source commit, resolved remote and destination branch.
- Denies a recognized unreviewed commit or push, also under no-prompt permission modes where the implementation says so; Git reads keep working, the native permission policy still applies after the content check, and the hook never grants, rewrites or stages a command.
- Covers recognized calls reaching the hook, not aliases, arbitrary programs, state-changing Git hooks, a concurrent index change or input to an existing process. The review files carry no approval flag: the answer is proved from the current conversation record, and missing or altered detail denies the recognized call.
- An unprovable review fails closed in a running handler, which verifies within a shorter internal time budget to leave timeout headroom; a host-level failure fails open, like a general STOP failure.
- An ordinary UserPromptSubmit revokes older preparations at once, even before the transcript flushes; resume and compaction advance the epoch `<session>.git-epoch`. Diagnostics and tests use simulated dispatch, which proves neither the live choice interface nor the hook's trust.
