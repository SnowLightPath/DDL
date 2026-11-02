# Claude Code: Git review

Read this before [Git review](../git-review.md). Run the installed gate with
`python3 "$HOME/.claude/hooks/ddl_gate.py" prepare-git-review --runtime claude`,
passing JSON on stdin. Use the project or development path when appropriate.
The input has `language` and an `operations` list; each operation names its
repository `cwd` and exact `command`.

The helper returns `reviewId`, `report`, `question`, and `nativeRequest`.
Show the ID and report, then pass `nativeRequest` unchanged to
`AskUserQuestion`. The hook matches the actual request/result ID, full request,
and human submission. An unavailable choice, timeout, or unprovable result
does not authorize Git. The review detail lives under the gate's state
directory; it contains no approval flag. An ordinary `UserPromptSubmit`
revokes older preparations immediately, even before the transcript flushes.

Claude's `permissions.ask` rule separately requests native permission for
`git push`; attribution is configured empty. Native permission does not replace
the content review. See the shared Git procedure for coverage and failure
limits.
