# Content-bound Git review

Read this before preparing or performing an ordinary commit or push, including
when the user did not invoke the commit command. Also read the selected host's
procedure: [Claude Code](runtimes/claude-git.md) or
[Codex](runtimes/codex-git.md).

## Prepare and review

1. Prepare the actual staged set and exact message. Include only explicitly
   requested ready pushes; a batch can contain one ready commit per repository
   and compatible pushes, with each commit before its push. Do not discard
   unrelated changes. Preparation creates review detail, not approval.
2. Use the host procedure to prepare the review. Before the decision, read
   [approval](approval.md) and the host's choice instructions. Emit
   `+++DDL_REPORT`, show the review ID, and link the complete report and diff
   before the exact native question returned by the helper. The user may
   approve the compatible set, revise it, or hold. Rebuild the review for a
   requested subset.
3. Wait for the actual human submission to that exact request. A prior plan,
   ordinary STOP release, assistant assertion, timeout, receipt, unrelated
   answer, or no-prompt permission mode is not a Git approval.
4. Keep the reviewed index intact. The hook checks the reviewed repository,
   base, staged contents, message and branch; push also checks the source
   commit, resolved remote, and destination. If contents, message, target, or
   review change, prepare and approve a new review. Resume or compaction also
   invalidates the old preparation. A push reviewed with its commit must resolve
   to a commit with the reviewed parent, tree, and verbatim message.

For example, the helper input is JSON:

```json
{"language":"en","operations":[{"cwd":"/path/to/repository","command":"git commit --cleanup=verbatim -F /path/to/message.txt"}]}
```

Ordinary commits use a named branch and `--cleanup=verbatim` with `-m` or a
UTF-8 `-F` file. Ordinary pushes name one configured remote and one branch or
refspec; preserve relevant options, including `--no-follow-tags` and
`--recurse-submodules=no` when needed. Forced, mirror, deletion, wildcard,
multi-target, in-progress merge/rebase/cherry-pick/revert, intent-to-add,
stdin-message, alternate-executable, dynamic, and compound write forms are not
supported. Stop with the reason; do not silently change their meaning. Retry a
canonical form only if it preserves the original Git options and configuration.

## Limits and interruption

The check covers recognized calls reaching the hook, not arbitrary programs,
aliases, Git hooks that change state, concurrent index changes, or input to an
existing process. The hook never grants a command or replaces native permission
policy. General STOP hook failures warn and fail open; a running Git handler
denies an unprovable review, but a runtime hook failure or timeout can still
fail open. Do not promise more.

Without a supported adapter there is no mechanical guarantee; the same review
rule remains an instruction. If the required matching cannot be established,
report the limitation and stop.

After a restart or compaction, reconstruct the pending decision from the
available notebook, git, and review detail. Never treat a summary, old review,
or old answer as a new approval. If the host cannot safely prepare and receive
the required fresh review without crossing a pending STOP, explain the
limitation and stop; do not bypass the gate or fabricate a receipt.
