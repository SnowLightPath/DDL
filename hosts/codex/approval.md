# Codex: approval

## Read when

Read before a STOP or a design.md human gate, with the Approval operation; it names the Codex choice tool, its receipt and selector limits, the mutating tools and the hook's permitted calls.

## Mapping

| Concern | Implementation |
|---|---|
| Choice tool | GUI first. `request_user_input_async` where the host exposes it for approval, one whole-set question, the prepared `nativeRequest` (`questions`, the five lines in `title`, `options`); `request_user_input` is Plan-only in some hosts and barred from permission requests in Default. |
| Subset | No multi-select field in the async schema; a grouped form only where a permitted interface has one; no invented `multiSelect`. |
| Receipt | `accepted: true` from the async call is a receipt, not an answer. |
| Timeout | A host that clears the pending question at turn completion is not approval-capable for the decision (`interface unavailable`). |
| Mutating tools | `apply_patch`, writing shell commands, starting, messaging or resuming an agent (MCP: the entry's Pending STOP). |
| Human input boundary | The reply arrives as a `UserMessage`, the boundary the `UserPromptSubmit` hook recognizes. |
| Prepare | `python3 "$HOME/.codex/hooks/ddl_gate.py" prepare-report --runtime codex <<'EOF'`, the input JSON (Formats), `EOF`; or the project copy (start: Adapter paths). |
| Hook | `.codex/hooks/ddl_gate.py` in `.codex/hooks.json` (`--runtime codex`); permitted while pending: `view_image`, `list_agents`, `request_user_input`, `request_user_input_async`, input-free polling (`wait`, `wait_agent`, `write_stdin` with empty `chars`, no `terminate`), and `shell`, `exec_command`, `local_shell`, `shell_command` or `Bash` for the preparation and the literal reads (Approval Implementation). |

## Observed

| Fact | Version | Date |
|---|---|---|
| In `codex exec` a same-turn `apply_patch` and `echo hi > file` were denied with the reason shown to the model, `git status --short` passed | codex-cli 0.163.0 | 2026-10-18 |
| In Default mode the async question, receipt and selector were real, but the selector was cleared at turn completion before any reply | Codex CLI 0.166.0 | 2026-11-01 |
| The GUI host of the same chat delivered click replies after turn completion as `send_user_message_question_reply` (question ID, question, answer) and a `UserMessage` rollout boundary | Codex GUI host (app version not recorded) | 2026-11-01 |

## Coverage

- Only `apply_patch` and shell denials are observed: the question match needs `request_user_input_async` to reach the hook (unverified); the record still proves opening and release; a multi-line reply `title` (unverified) is compared newline-normalized.
- The GUI click reply (Observed) is one host on one day and does not generalize.
- Scope: outside a DDL project, one whose instruction file between the working directory and the repository root or `$HOME` carries the `→ DDL-PROTOCOL` line, each event of the hook returns at once.
