# Codex: Git review

Read this before [Git review](../git-review.md). Run the installed gate with
`python3 "$HOME/.codex/hooks/ddl_gate.py" prepare-git-review --runtime codex`,
passing JSON on stdin. Use the project or development path when appropriate.
The input has `language` and an `operations` list; each operation names its
repository `cwd` and exact `command`.

The helper returns `reviewId`, `report`, `question`, and `nativeRequest`.
Show the ID and report, then pass `nativeRequest` unchanged to the permitted
`request_user_input_async` interface. End the turn after the receipt and wait
for the actual reply. The hook matches the request ID, full request, and
submitted human answer; an unreadable or unprovable result denies Git, even
under `never`, `bypassPermissions`, or `dontAsk`. Review detail in the gate's
state directory contains no approval flag. An ordinary `UserPromptSubmit`
revokes older preparations immediately; a possible matching native submission
is retained pending full request/result proof.

The native rule prompts for supported `git push` forms when the session's
permission policy permits prompting. A separate hook guard rejects recognized
static forms that miss the prefix; it does not grant or rewrite commands.
Absolute host Git paths retain native executable resolution.
Explicit `bypassPermissions` / `dontAsk` hook modes skip that form guard, not
the STOP or Git review. A no-prompt session cannot show the native prompt;
the content review still applies. See the shared Git procedure for limits.
