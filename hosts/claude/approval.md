# Claude: approval

## Read when

Read with the Approval operation before a STOP or a design.md human gate; it names the Claude choice tool, its timeout field, the mutating tools and the hook's permitted calls.

## Mapping

| Concern | Implementation |
|---|---|
| Choice tool | `AskUserQuestion` with the prepared `nativeRequest`: the prepared lines in `questions[0].question`, header `DDL`, the action options; a batch, 2–4 prepared `questions` in one call. |
| Subset | `multiSelect` (a preparation input) where the exposed schema has it. |
| Receipt | An empty or dismissed result is no submission. |
| Timeout | The host-only field `afkTimeoutMs` marks idle auto-resolution (Observed); the gate places no boundary on it. |
| Mutating tools | Edit, Write, NotebookEdit, writing Bash, TaskCreate, TaskUpdate, `Agent`, `SendMessage` (MCP: the entry's Pending STOP). |
| Human input boundary | An answered `AskUserQuestion`, an approved plan or a mid-turn message (`queued_command` attachment, `origin.kind` `human`); a `SendMessage` or a scheduled prompt (a `user` entry with `isMeta` true and `turnOrigin` `scheduled`) is not one. |
| Prepare | `python3 "$HOME/.claude/hooks/ddl_gate.py" prepare-report --runtime claude <<'EOF'`, the input JSON (Formats), `EOF`; or the project copy (start: Adapter paths). |
| Hook | `.claude/hooks/ddl_gate.py` in `.claude/settings.json` (`--runtime claude`); permitted while pending: Read, Grep, Glob, LS, NotebookRead, WebFetch, WebSearch, ToolSearch, ListAgents, ReadNotifications, TaskGet, TaskList, `AskUserQuestion`, and Bash for the preparation and the literal reads (Approval Implementation). |

## Observed

| Fact | Version | Date |
|---|---|---|
| Against this repository's live transcript the gate denied a covered call after a report and allowed it after the plan approval, 0.04 s per call | Claude Code 2.1.302 | 2026-10-18 |
| Idle auto-resolution after the 60-second timeout returned selected answers plus `afkTimeoutMs`, an explicit submission omitted it, and the timer did not run under Remote Control | Claude Code 2.1.316 | 2026-11-01 |
| Under Remote Control 38 messages of one session recorded the decision reports only as a signed thinking block with a one- or two-sentence summary; the native question and answer were verbatim | Claude Code 2.1.317 in the record, 2.1.319 binary | 2026-11-07 |
| 205 mid-turn messages, 2026-10-28 to 11-24, left no `user` entry; UserPromptSubmit fired 41 ms after one | Claude Code 2.1.311 to 2.1.331 | 2026-11-25 |
| Scheduled prompts (cron, `/loop` wakeup) arrived only while the session was idle, each as a new turn with `promptSource` `system`: one live, 85 recorded | Claude Code 2.1.331 live, 2.1.325 to 2.1.330 recorded | 2026-11-25 |

## Coverage

- Human input (Mapping) and the question are recognized from the record's named fields (Observed).
- Scope: a DDL project only, its instruction file (from the working directory up to the repository root or `$HOME`) holding `→ DDL-PROTOCOL`; elsewhere every event returns at once.