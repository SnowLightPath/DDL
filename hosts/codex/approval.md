# Codex: approval

## Read when

Read before a STOP or design.md human gate, with Approval; names the choice tool, receipt and selector limits, mutating tools and permitted hook calls.

## Mapping

| Concern | Implementation |
|---|---|
| Choice tool | GUI first: `request_user_input_async` where exposed for approval, one whole-set question with the prepared `nativeRequest` (`questions`, five-line `title`, `options`); `request_user_input` is Plan-only in some hosts and barred from permission requests in Default. |
| Subset | Async has no multi-select field; a grouped form requires a permitted interface that supports it; no invented `multiSelect`. |
| Receipt | Async `accepted: true` is a receipt, not an answer. |
| Timeout | A host clearing its pending question at turn completion is unable to collect approval for that decision (`interface unavailable`). |
| Mutating tools | `apply_patch`, writing shell commands, starting, messaging or resuming an agent (MCP: entry's Pending STOP). |
| Human input boundary | The `UserMessage` reply is the boundary recognized by `UserPromptSubmit`. |
| Prepare | `python3 "$HOME/.codex/hooks/ddl_gate.py" prepare-report --runtime codex <<'EOF'`, input JSON (Formats), `EOF`; or project copy (start: Adapter paths). |
| Hook | `.codex/hooks/ddl_gate.py` in `.codex/hooks.json` (`--runtime codex`); while pending permits `view_image`, `list_agents`, both choice tools above, input-free polling (`wait`, `wait_agent`, `write_stdin` with empty `chars`, no `terminate`), and `shell`, `exec_command`, `local_shell`, `shell_command` or `Bash` for preparation and literal reads (Approval Implementation). |

## Observed

| Fact | Version | Date |
|---|---|---|
| `codex exec`: same-turn `apply_patch` and `echo hi > file` denied with a visible reason; `git status --short` passed | codex-cli 0.163.0 | 2026-10-18 |
| Default's async question and receipt were real; its selector cleared at turn completion before any answer | Codex CLI 0.166.0 | 2026-11-01 |
| GUI click replies arrived after turn completion as `send_user_message_question_reply` (question ID, question, answer) and a `UserMessage` boundary | Codex GUI (version unrecorded) | 2026-11-01 |
| Async reached `PreToolUse`: an ID-less question was denied; the exact prepared question passed. The user saw all five lines; the reply's `question` equaled the prepared `title`, including LF | Codex Desktop 0.167.0-alpha.3.2 | 2026-11-07 |
| `apply_patch` and `echo hi > file` denied under the pending report, then passed after the native answer | Codex Desktop 0.167.0-alpha.3.2 | 2026-11-07 |

## Coverage

- Live results cover only the listed hosts and dates; synchronous choice and independent host-cwd behavior remain untested.
- Outside DDL projects (a working-directory-to-repository-root instruction file, below `$HOME`, carries `→ DDL-PROTOCOL`), each hook event returns at once.
