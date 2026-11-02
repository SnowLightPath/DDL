# Claude Code: approval

## Read when

Read with [approval](../approval.md) before a STOP or a design.md human gate; it names the Claude Code choice tool, its timeout field, the mutating tools and the hook's permitted calls.

## Mapping

| Concern | Procedure |
|---|---|
| Choice tool | `AskUserQuestion`, one question over the whole compatible set with concrete action options and optional free text. |
| Subset | `multiSelect` when the exposed schema supports it, otherwise compatible subsets as options; never one question per item. |
| Receipt | An empty, dismissed or auto-resolved result is no submission, even with an option returned. |
| Timeout | Idle auto-resolution returns a result with the host-only field `afkTimeoutMs`, with or without answers; a real submission omits it, and the gate places no boundary on it. |
| Mutating tools | Edit, Write, NotebookEdit, writing Bash, TaskCreate, TaskUpdate, `Agent`, `SendMessage`, and MCP or connector tools that create, update, send, publish or delete. |
| Human input boundary | An answered `AskUserQuestion` or an approved plan, never a worker notification or `SendMessage` from a teammate or another session; a synchronous answer resumes the approved scope without retyping. |
| Hook | `.claude/hooks/ddl_gate.py` in `.claude/settings.json` (`--runtime claude`); permitted while pending: Read, Grep, Glob, LS, NotebookRead, WebFetch, WebSearch, ToolSearch, ListAgents, ReadNotifications, TaskGet, TaskList, `AskUserQuestion`, and Bash for literal reads (`cat`, `head`, `tail`, `rg`, `grep`, `sed -n '1,10p' file`, `git status`). |

## Observed

| Fact | Version | Date |
|---|---|---|
| Against this repository's live transcript the gate denied a covered call after a report and allowed it after the plan approval, 0.04 s per call | Claude Code 2.1.302 | 2026-10-18 |
| Idle auto-resolution after the 60-second timeout returned selected answers plus `afkTimeoutMs`, an explicit submission omitted it, and the timer did not run under Remote Control | Claude Code 2.1.316 | 2026-11-01 |

## Coverage

- The hook classifies only the calls Claude Code dispatches through PreToolUse.
- Human input is recognized from the named `AskUserQuestion` result fields and the approved-plan record, nothing else in the transcript.
