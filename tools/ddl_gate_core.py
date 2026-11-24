#!/usr/bin/env python3
"""DDL gate: the mechanical half of the protocol's +++STOP rule, as a lifecycle hook.

This module holds the gate's code. Its entry is `ddl_gate.py` beside it, the file the adapters' settings,
the protocol and the commands name: a short launcher that loads this module from a private bytecode cache
under the state directory, so a hook call does not compile it. `python3 ddl_gate_core.py <word> …` runs it
too, uncached.

Approval is carried by the native question. A decision report is prepared with `prepare-report`
and a Git review with `prepare-git-review`; each returns one native question of five
`<label>: <value>` lines (decision, recommendation, consequence, ID `R-…`/`G-…`, absolute report
path). The STOP is pending from that preparation output, from a question that carries an ID, or
from a line-initial `+++DDL_REPORT` in assistant text, until submitted human input; meanwhile the
gate denies covered mutating calls and any question other than the prepared one. The gate proves
a pending STOP and a Git review from the question and its answer, never from assistant text, and
reads no thinking block or reasoning item. The assistant follows the protocol's Approval
operation: a synchronous question waits for the actual answer and can resume approved work in the
same turn; an asynchronous request receipt ends the turn while awaiting the actual answer.
Whether a human reply approves the current report and scope remains the assistant's judgment.
Ordinary Git commits and pushes have an additional, independent guard: a prepared content review
and an actual matching native choice are required even after STOP opens and even when native
command approvals are disabled.

Usage (the same command serves Claude Code and Codex CLI; the hook payload JSON is on stdin):
  python3 tools/ddl_gate.py pre-tool-use       --runtime claude|codex
  python3 tools/ddl_gate.py permission-request --runtime codex          (Codex's PermissionRequest)
  python3 tools/ddl_gate.py stop               --runtime claude|codex
  python3 tools/ddl_gate.py user-prompt-submit --runtime claude|codex
  python3 tools/ddl_gate.py session-start      --runtime claude|codex
  python3 tools/ddl_gate.py prepare-report     --runtime claude|codex
  python3 tools/ddl_gate.py prepare-git-review --runtime claude|codex
  python3 tools/ddl_gate.py status [--cwd DIR]
  python3 tools/ddl_gate.py run-start                              (JSON on stdin)
  python3 tools/ddl_gate.py run-item <N-id> <item id> <status>
  python3 tools/ddl_gate.py report (--transcript FILE --runtime claude|codex | --session ID | --run N-ID)
                                   [--language ja|en]
  python3 tools/ddl_gate.py snapshot [--run N-ID] [--item ID] [--git-dir DIR --work-tree DIR]
  python3 tools/ddl_gate.py snapshot list [--run N-ID] [--git-dir DIR --work-tree DIR]
  python3 tools/ddl_gate.py resources | measure <machine> | remote <machine> [options] -- <command>
  python3 tools/ddl_gate.py service <name> --prompt-file FILE [--schema FILE]
run-start, run-item, report, snapshot, resources, measure, remote and service (RUN_WORDS) live in tools/ddl_run.py
beside this file, which `main` imports for those words only (`ddl_run.py <word> …` runs them too, alike); no hook
event imports it. The resource table they read is this module's (read_resource_table, below).

prepare-report reads JSON {language, decision, recommendation, consequence, detail, options?,
multiSelect?, grant?, confirm?, holds?, queue?, provisional?} on stdin, writes report.md and report.json under `<state dir>/reports/<id>/`,
and prints {reportId, report, question, nativeRequest}. prepare-git-review reads JSON
{language: en|ja, operations: [{cwd, command}, ...]}, snapshots the staged changes and push
targets, writes review detail in the private state directory, and prints the same shape with
reviewId. Neither creates approval; invalid input prints `DDL STOP: …` / `DDL Git review: …` on
stderr and exits 2.

Grant, ledger and counts (no decision reads a ledger line; an active grant answers, see Decisions): a report
may carry a `grant` {paths, commands, machines, handover, budget {minutes, fixAttempts}, expires}.
When the user's resource table exists ($XDG_CONFIG_HOME/ddl/resources.toml, else ~/.config/ddl/resources.toml),
each machine is a declared compute resource, `handover` names data kinds (code, personal, business) and each
machine takes every kind handed over; an invalid table refuses a grant that names machines; without a table the
names are free. It is hashed into the report ID with the project key, adds one generated line to the question and
a block to report.md, and is written once to the user-level store ($DDL_GATE_GRANT_DIR, else
$XDG_STATE_HOME/ddl-gate, else $HOME/.local/state/ddl-gate) as `<project key>/grants/R-<id>.json`
when the record proves that the human submitted the first option of the unchanged question; after
that only its expiry ends it. The record appears whole or not at all, and a file that does not parse
as that grant's record is no grant. A report may also carry `confirm`, 1 to 4 {resource, action} for
compute resources of the table (a resource with `confirm = "each run"` runs only so), bound to what runs: an
ssh resource's action is the exact command, and a service's entry adds `prompt`, a file of at most 32 KiB in
the project (not protected) or a temporary directory, whose text report.md shows whole and whose SHA-256 is kept,
an optional `schema` file bound alike, and `approve` (whether it may write; false unless given, "(may write)").
It adds a `Confirm` (`確認`) line after the grant's and a block to report.md, and on the same proof is recorded
once as `<project key>/confirmations/R-<id>.json` {id, projectKey, root, items [{resource, action, digest?,
schemaDigest?, approve?, used: null}], approvedAt, session, host}; tools/ddl_run.py finds the unused items
with confirmation_items (the first with confirmation_item) and marks one used with mark_confirmation_used
before anything is sent. `holds` {run, items} names 1 to 16 items of a Run in the ledger that the question stops
(report.md shows them; the five lines stay); `queue: true` prepares it for a later batch, so its preparation makes
no STOP pending (the `prepared` line carries `queued`, `holds` and `provisional`); `provisional` {snapshot}, with
both, goes ahead as if its first option were chosen: the snapshot ref must exist under refs/ddl/snapshots/, no
other unanswered provisional question of the Run may hold an item it holds or one depending on them, and its
answer is `provisional-confirmed` on the first option, else `provisional-overturned`. Every queued report is kept
as `<project key>/queued/<original R-id>.json` until a proven answer to any asking of it: its held files stay held
meanwhile (edits and what commands name), a provisional one keeps every exit waiting, and Stop names those not
asked yet (a systemMessage; it never blocks). `replaces: <R-id>` (with `queue: true`) asks an open one again (the
same Run and items, snapshot, decision line and option labels) and takes over its marker; `status` lists them. In a DDL project the gate appends one JSON line per event to
`.ddl/events.jsonl` at the root of the main work tree (a silent pass writes nothing; an approved
grant that was not recorded leaves a `warn` line whose rule is `grant-proof` or `grant-store`; a recorded
confirmation writes `confirmed`, one not recorded a `warn` of `confirm-proof` or `confirm-store`).
`run-start` writes `.ddl/runs/<N-id>/run.json` from {report, items}; `run-item` sets one item's
status; `report` prints four lines: questions, waiting, denials, grant; and `snapshot` commits the work
tree under `refs/ddl/snapshots/` without moving a branch, the index or a file (tools/ddl_run.py says more).
These subcommands take the project from the working directory and exit 2 on a usage error.

Scope: the hook acts only in a DDL project, one whose instruction file (CLAUDE.md, .claude/CLAUDE.md
or AGENTS.md in the event's `cwd` or a parent, up to the directory holding `.git` and below $HOME)
contains the line `→ DDL-PROTOCOL` (`->` is accepted). Elsewhere every event returns at once, before
any transcript, marker or Git read. The decision is cached as `<state dir>/<session_id>.project`:
pre-tool-use and stop reuse it while `cwd` and the instruction file's mtime are unchanged;
user-prompt-submit and session-start recompute it. `status` prints the decision for a directory.
Only json, os and sys are imported up front; the other modules load on first use in a DDL project,
and tools/ddl_run.py only for its subcommands (RUN_WORDS). The bytecode cache is `<state dir>/pycache`
(0700): the gate creates it when it acts in a DDL project, never elsewhere, and the launcher uses it
only while it is a directory of this user that nobody else may enter, in a state directory nobody
else may write; otherwise the interpreter's own bytecode settings apply and nothing is written beside
the source.

Decisions (JSON on stdout; the exit status is always 0):
  pre-tool-use        CLOSED and the tool may mutate -> permissionDecision "deny";
                      a question carrying an ID must equal the prepared request (else "deny"), and
                      while CLOSED a question without the pending ID is denied; a Claude call of 2 to 4
                      questions passes when each is a queued report's unchanged question, and each is
                      armed, answered and proved on its own; while a question holds items (every
                      pending question names `holds`), a call an active grant allows as an edit, test
                      or check, no exit and no question, naming no owner file of a held item or of one
                      depending on it (resolved: links, NFC, case), is allowed as if no STOP were
                      pending, and a command naming no path stays held; while a provisional question
                      is unanswered, every command that may leave the machine (however quoted, the
                      gate by its real path, any Git alias) and every MCP tool without a read verb is
                      denied; an edit of a file an unanswered queued question holds is denied;
                      ordinary commit/push also needs a matching native content review while OPEN,
                      and the matched one is allowed ("allow": the review was its one confirmation); a
                      plain commit (`-m` or `-F`, optional `--cleanup=verbatim`, nothing else) inside an
                      active grant that names `commit` needs none: in this project's repository or its
                      second Git directory (work tree: the root), on a branch, its staged paths inside the
                      grant's paths (a protected file only named literally); it writes a `commit` line;
                      a push review lists every commit the push sends, and a pinned superproject commit
                      (`pin` {submodule, from}) matches when its gitlink is the commit that push sent
                      (the steps between them, submodule update, fetch, checkout, add, are allowed);
                      prepare-git-review refuses a push while the newest Run has open items and no
                      `close` item whose dependencies are done;
                      codex also denies unsupported push forms in confirmation-enabled modes;
                      a write of `.ddl/events.jsonl` or `.ddl/runs/*/run.json` -> "deny";
                      OPEN with an active grant (recorded, before its expiry): a read; from a working
                      directory inside the root, an edit inside its paths or granted command classes
                      in their allow-listed forms with literal arguments -> "allow"
                      ("DDL: inside grant <id> (<kind>)"); the gate's remote, measure and service are
                      class remote-run for the resource they name (allowed when covered: a grant that
                      names it hands over code, and no resource on its reach asks each run; else nothing);
                      with a resource table, ssh reaches a granted compute resource only by the alias
                      of its `reach = ssh:<alias>`, a resource with `confirm` is never covered (nothing)
                      and a `codex:` one never by ssh; a path, class or machine outside every
                      active grant, or an exit behind ssh -> "deny"; a protected file (Git's files,
                      CI workflows, .ddl/, an agent's, editor's or direnv's settings, an instruction
                      file, the notebook), a call asking to leave the sandbox and anything else print nothing.
                      Codex takes no allow from PreToolUse: there an allow prints nothing
  permission-request  the same decision; its allow only, as PermissionRequest's {"behavior": "allow"},
                      else nothing (Codex asks it before its own confirmation; no tool_use_id)
  stop                writes the marker file when the turn ended with a report; prints nothing
                      (it also records an approved grant the tool path has not seen yet)
  user-prompt-submit  first records the answers the record already holds, then removes the marker (a human
                      spoke); on Claude a prompt that starts like a worker's completion notice or another
                      envelope (NOT_HUMAN_PREFIXES) is no human: it keeps the marker, the epoch and the
                      asked questions and is logged as `prompt` with rule `notification`; prints nothing
  session-start       compact/resume while CLOSED -> additionalContext with a notice (naming the
                      pending ID and report when known);
                      codex also gets design.md injected (claude imports it through CLAUDE.md)

State: the conversation record (`transcript_path`) is read from the end. A readable record is
authoritative for Claude; Codex keeps a pending marker authoritative even over an OPEN record
until the marker is cleared. An answered AskUserQuestion and an approved plan count as human input
(toolUseResult / permissionDecision from the user). A prepared ID older than the session's
`.git-epoch` (resume, compaction, fork, clear, or a new prompt) covers nothing. Claude Code writes
the transcript asynchronously, so a continuation in the same turn can escape the gate; the rule then holds as
an instruction. A marker file `<state dir>/<session_id>.pending` carries the signal across
turns and for runtimes whose record is unreadable, and `<state dir>/<session_id>.warned` makes
the unreadable-record warning appear once per session; `<state dir>/<session_id>.asked` lists the
prepared questions that await their answers, so a call with nothing asked costs one stat. The state
dir is $DDL_GATE_STATE_DIR, else $TMPDIR/ddl-gate, else /tmp/ddl-gate. Wire all four events, or
the marker is never cleared.

The general STOP gate fails open on internal errors. Recognized Git commit/push review failures
instead deny the operation; an unreadable or changed review never creates permission. The shell
allowlist guards against accidental continuation; it is not a sandbox. Both adapters use catch-all
matchers, but only calls reaching the runtime's tool hooks are checked. Only exact known read tools,
a bounded, literal shell subset, and the gate's own preparation call pass while CLOSED; unknown
tools, general scripts and code wrappers do not. Ambient executable/config
behavior is outside this static check. Push form checks do not inspect arbitrary scripts or aliases
and never rewrite a command. An allow comes only from a matched Git review or an active grant while
the record is OPEN, never from an internal error, an unreadable record or a pending STOP.
Runtime-level hook failures/timeouts can still fail open; the content check uses a shorter time
budget to leave headroom beneath the adapter timeout. Review directories are private; their JSON
is preparation data, not an approval flag. Native request/result proof is checked on every call.
"""
from __future__ import annotations

import json
import os
import sys


class _Lazy:
    """A standard-library module bound on first attribute access.

    The non-DDL path returns before touching any of them, so it pays for json, os and sys only; the
    first use in a DDL project imports the module and rebinds the global name to it."""
    __slots__ = ("_name", "_alias")

    def __init__(self, name, alias=None):
        self._name, self._alias = name, alias or name

    def __getattr__(self, attr):
        module = __import__(self._name)
        for part in self._name.split(".")[1:]:
            module = getattr(module, part)
        globals()[self._alias] = module
        return getattr(module, attr)


class _Pattern:
    """A regular expression compiled on first use, which then rebinds the global name to the pattern."""
    __slots__ = ("_alias", "_source")

    def __init__(self, alias, source):
        self._alias, self._source = alias, source

    def __getattr__(self, attr):
        pattern = re.compile(self._source)
        globals()[self._alias] = pattern
        return getattr(pattern, attr)


datetime, hashlib, ipaddress, pathlib, re, secrets, shlex, shutil, subprocess, time = (
    _Lazy(name) for name in ("datetime", "hashlib", "ipaddress", "pathlib", "re", "secrets", "shlex", "shutil",
                             "subprocess", "time"))
urlparse = _Lazy("urllib.parse", "urlparse")

EVENTS = ("pre-tool-use", "permission-request", "session-start", "stop", "user-prompt-submit", "post-tool-use")
RUNTIMES = ("claude", "codex")
REPORT = _Pattern("REPORT", r"(?m)^\s*\+\+\+DDL_REPORT\b")

DENY_REASON = ("DDL gate: a +++DDL_REPORT was emitted after the last human message, so this STOP is pending "
               "(the protocol's Approval operation). End the turn and wait for the user's approval; read-only "
               "tools may run only to clarify the report.")
NOTICE = ("DDL gate: a +++DDL_REPORT is awaiting the user's approval. Re-emit the report (the protocol's Approval "
          "operation) and wait; do not continue the phase.")
DESIGN_HEADER = "# design.md (injected by the DDL adapter; it stays in context, do not re-read)"
UNREADABLE = ("DDL gate: could not read the conversation record and no marker exists; the +++STOP rule is "
              "enforced by instruction only for this call.")
INTERNAL = "DDL gate: internal error ({}: {}); the call was allowed (fail-open)."

READ_ONLY_TOOLS = {"Read", "Grep", "Glob", "WebFetch", "WebSearch", "ToolSearch", "ListAgents", "ReadNotifications",
                   "LS", "NotebookRead"}
SAFE_TOOLS = {"claude": READ_ONLY_TOOLS | {"TaskGet", "TaskList", "AskUserQuestion"},
              "codex": {"view_image", "list_agents", "request_user_input", "request_user_input_async"}}
SHELL_TOOLS = {"claude": {"Bash"}, "codex": {"Bash", "shell", "exec_command", "local_shell", "shell_command"}}
READ_ONLY_PROGRAMS = {"cat", "head", "tail", "sed", "grep", "rg", "egrep", "fgrep", "wc", "ls", "find", "stat",
                      "file", "which", "type", "echo", "printf", "pwd", "env", "diff", "cmp", "sort", "uniq", "cut",
                      "tr", "jq", "test", "[", "true", "date", "cd", "git", "codex", "claude"}
GIT_READ_ONLY = {"status", "diff", "log", "show", "ls-files", "rev-parse", "branch", "check-ignore", "blame", "grep"}
SAFE_GIT_CONFIG = {"core.pager=cat", "core.fsmonitor=false", "color.ui=never"}
PUSH_FORM_REASON = ("DDL gate: this Git push form cannot be read as one plain `git push` by the Git review or by "
                    "Codex's approval policy. "
                    "Run a separate literal `git push ...` with the tool's working directory set to the intended "
                    "repository, only if that preserves the original options and configuration. Do not silently "
                    "discard required options; explain the limitation instead. No command was rewritten.")
NOT_HUMAN_PREFIXES = ("Another Claude session sent a message", "<task-notification>", "<system-reminder>",
                      "<local-command", "<command-name>", "[Request interrupted")
ASSIGNMENT = _Pattern("ASSIGNMENT", r"[A-Za-z_][A-Za-z0-9_]*=")
REDIRECT = _Pattern("REDIRECT", r">>?")
# A whole token that is a harmless redirect (`2>&1`, `2>/dev/null`, `<in`) or a bare operator (`>`, `2>>`, `<`).
REDIR_TOKEN = _Pattern("REDIR_TOKEN", r"(\d*|&)>>?(&\d+|/dev/null)?$|\d*<\S*$")

GIT_REVIEW_REASON = ("DDL Git review: this commit or push needs a submitted native choice for its exact "
                     "contents, message, and destination. Prepare a Git review with ddl_gate.py "
                     "prepare-git-review, ask its prepared question unchanged, and wait for the actual answer. ")
REVIEW_ALLOW_REASON = "DDL: matches Git review {}"
GIT_PROTECTED = {"commit", "push", "commit-tree", "send-pack"}
# Leave headroom beneath the adapters' ten-second hook timeout. A timed-out runtime hook may fail open.
GIT_REVIEW_BUDGET_SECONDS = 4
SENT_LIMIT = 300  # commits one push review lists, at most
MESSAGE_BYTES = 64 * 1024  # the largest commit message file read
LS_REMOTE_SECONDS = 20  # the remote's branch is read at a push review's preparation, within this
LS_REMOTE_PIN_SECONDS = 6  # and the submodule's remote branch when a pinned commit runs, within this
RUN_STATUSES = ("ready", "running", "done", "failed", "dropped")  # an item's status in run.json (ddl_run's)
DEFAULT_PORTS = {"ssh": 22, "git+ssh": 22, "ssh+git": 22, "https": 443, "http": 80, "git": 9418, "ftp": 21, "ftps": 990}
COMMIT_HOOKS = ("pre-commit", "prepare-commit-msg", "commit-msg", "post-commit", "reference-transaction",
                "post-index-change", "pre-auto-gc", "post-rewrite")  # hooks a commit may run
PIN_STEP_ALLOW = "DDL: a step of the pin in Git review {}"
_git_review_deadline = None

# --- the prepared question --------------------------------------------------------------------
# A decision report (R-) and a Git review (G-) are each asked as one native question of five
# `<label>: <value>` lines: what to decide, the recommendation, the consequence, the ID, and the
# absolute path of report.md. The host records that question and its answer verbatim, so the gate
# proves a pending STOP and a Git approval from them rather than from assistant text.
# One short sentence per line keeps the question readable on a phone; detail belongs in the report file.
QUESTION_LINE_LIMIT = 300
QUESTION_LABELS = {"ja": ("決めること", "推奨", "影響", "確認 ID", "全文"),
                   "en": ("Decision", "Recommendation", "Consequence", "ID", "Full report")}
QUESTION_ID_LINE = 3  # zero-based: the ID is the fourth of the five lines
# A prepared ID is this many hex digits (64 bits) of a SHA-256 over the record, which carries a nonce.
ID_HEX_LENGTH = 16
NONCE_BYTES = 16  # 128 random bits, so two preparations of the same content never share an ID
QUESTION_ID = _Pattern("QUESTION_ID", r"[^\n:]+: ([RG])-([0-9a-f]{%d})" % ID_HEX_LENGTH)
PREPARED_ID = _Pattern("PREPARED_ID", r"([RG])-([0-9a-f]{%d})" % ID_HEX_LENGTH)
ELLIPSIS = "…"
SHORT_SHA_LENGTH = 7  # Git's default abbreviation; it only names a pushed commit in the question
# A BCP 47-style language tag: a two-to-eight-letter primary subtag, then optional subtags.
LANGUAGE_CODE = _Pattern("LANGUAGE_CODE", r"[A-Za-z]{2,8}(?:[-_][A-Za-z0-9]{1,8})*")
MIN_OPTIONS, MAX_OPTIONS = 2, 4  # the bounds of one native Claude question's options
REPORT_VERSION = 3  # the report.json schema; a change of fields bumps it (2: grant and projectKey; 3: confirm)
REPORT_INPUT_KEYS = {"language", "decision", "recommendation", "consequence", "detail", "options", "multiSelect",
                     "grant", "confirm", "holds", "queue", "provisional", "replaces"}
REPORT_LINE_KEYS = ("decision", "recommendation", "consequence")
# The fields the report ID hashes; report.json adds id, question, nativeRequest and reportHash.
# `grant` and `confirm` are None for a report without them; `projectKey` is None outside a DDL project.
REPORT_CORE_KEYS = ("version", "runtime", "language", "nonce", "createdAt", *REPORT_LINE_KEYS,
                    "options", "multiSelect", "detailHash", "grant", "confirm", "projectKey")
DEFAULT_OPTIONS = {
    "ja": [{"label": "すべて承認（推奨）", "description": "表示した推奨をすべて適用する"},
           {"label": "一部・修正", "description": "項目を選ぶか修正を求める。報告を作り直して聞き直す"},
           {"label": "保留", "description": "何も適用しない"}],
    "en": [{"label": "Approve all (Recommended)", "description": "Apply every displayed recommendation"},
           {"label": "Subset or changes",
            "description": "Select items or request changes; the report is rebuilt and asked again"},
           {"label": "Hold", "description": "Apply nothing"}]}
QUESTION_TOOLS = {"claude": {"AskUserQuestion"}, "codex": {"request_user_input", "request_user_input_async"}}
WAITING_REASON = "DDL STOP: {} is waiting for the user's answer (report: {})"
ASK_UNCHANGED = "DDL STOP: ask the prepared question for {} unchanged"
PREPARE_FIRST = "DDL STOP: prepare the report and ask its question"
NOT_PREPARED = "DDL STOP: {} was not prepared here; prepare the report again"
PREDATES = "DDL STOP: {} predates the latest user message, resume or compaction; prepare the report again"
# Held, queued and provisional questions (each only where a report names it; without these keys nothing changes).
# A report's optional keys are hashed into its ID only when given, so a report without them keeps its bytes.
REPORT_OPTIONAL_KEYS = ("holds", "queue", "provisional", "replaces")
HOLD_ITEMS = (1, 16)  # items one question may hold
RUN_ID_SOURCE, ITEM_ID_SOURCE = r"N-[0-9a-f]{12}", r"[A-Za-z0-9][A-Za-z0-9._-]{0,31}"  # as tools/ddl_run.py reads them
SNAPSHOT_REFS = "refs/ddl/snapshots/"
BATCH_QUESTIONS = (2, 4)  # the prepared questions one native call may carry (Claude)
HELD_KINDS = {"edit", "test", "check"}  # what may go on beside a held question, inside an active grant
HELD_ALLOW = "DDL: inside grant {} ({}); outside the items {} holds"
HOLD_LABELS = {"ja": ("止める項目", "見込み"), "en": ("Holds", "Provisional")}
BATCH_UNCHANGED = "DDL STOP: a batch carries 2 to 4 queued prepared questions, each unchanged ({})"
SETTLED_REPLACEMENT = ("DDL STOP: {} asks {} again, which is answered already; prepare the question anew, without "
                       "replaces, if it is still open")
PROVISIONAL_EXIT = ("DDL provisional: {} is not answered yet; a provisional decision never leaves this machine, so no "
                    "commit, push or other exit runs until it is answered")
QUEUED_HOLD = ("DDL queued: {} holds {} and is not answered yet; ask it (in a batch with the other queued questions) and "
               "wait for its answer")
QUEUED_NOTICE = "DDL: queued questions not asked yet: {}. Ask them together in one question call."
OWNER_MATCHES = 4096  # existing files one owner glob is resolved to, at most
NETWORK_CLIENTS = {"curl", "wget", "http", "https", "xh", "aria2c", "lynx", "w3m", "links", "elinks"}
WRAPPERS = {"env", "command", "exec", "nohup", "nice", "time", "timeout", "stdbuf", "sudo", "doas", "xargs", "chronic"}
WRAPPER_VALUES = {"env": ("-u", "-C", "-S"), "nice": ("-n",), "sudo": ("-u", "-g", "-C"), "xargs": ("-n", "-P", "-I", "-L",
                                                                                               "-s", "-d", "-E"),
                  "stdbuf": ("-i", "-o", "-e"), "timeout": ("-s", "-k")}
PUBLISHERS = {("npm", ("publish",)), ("yarn", ("publish",)), ("pnpm", ("publish",)), ("twine", ("upload",)),
              ("cargo", ("publish",)), ("gem", ("push",)), ("docker", ("push",)), ("podman", ("push",))}
# The host's own tools that carry something off the machine: publishing a page and its data and comments, sending a
# file to the user, a message to another session, a remote trigger, the web. A notification to the human (Claude's
# PushNotification) is no exit: the lead tells the human once that no unheld work is left.
OUTWARD_TOOLS = {"Artifact", "ArtifactData", "ArtifactComments", "SendUserFile", "SendFile", "SendMessage",
                 "SendUserMessage", "RemoteTrigger", "WebFetch", "WebSearch"}
# Git subcommands that ship with Git and stay on this machine (or are read by exit_word as exits); any other is
# possibly an alias, which may run anything.
LOCAL_GIT = {"status", "diff", "log", "show", "ls-files", "rev-parse", "branch", "check-ignore", "blame", "grep", "add",
             "restore", "rm", "mv", "init", "stash", "checkout", "switch", "fetch", "clone", "config", "notes",
             "describe", "shortlog", "show-ref", "cat-file", "ls-tree", "for-each-ref", "worktree", "clean", "apply",
             "reflog", "fsck", "count-objects", "var", "help", "version", "range-diff", "whatchanged", "diff-tree",
             "diff-index", "diff-files", "merge-base", "name-rev", "rev-list", "ls-remote", "hash-object", "bisect",
             "check-attr", "check-ref-format", "verify-commit", "verify-tag", "symbolic-ref", "read-tree", "write-tree",
             "update-index", "gc", "prune", "repack", "maintenance"} | {"push", "commit", "merge", "rebase", "reset",
             "cherry-pick", "revert", "am", "pull", "tag", "update-ref", "send-email", "commit-tree", "send-pack",
             "http-push", "receive-pack", "upload-pack", "upload-archive"}
GIT_QUESTION_MISMATCH = "DDL Git review: the question does not match prepared review {}; ask it unchanged"
PENDING_NOTICE = ("DDL gate: report {} is awaiting the user's answer (report: {}). Prepare it again under a new ID "
                  "and ask its question; do not continue the phase.")
# Codex Desktop can wrap the gate's JSON in four steps: content list, text, parsed exec result,
# and its output JSON. Deeper nesting is not the gate's own output.
ENVELOPE_DEPTH = 4
# The gate's own preparation call: python3 [-I] <gate> <subcommand> --runtime <rt> <<'DELIM' (quoted).
PREPARE_HEAD = _Pattern("PREPARE_HEAD", r"python3(?:[ \t]+-I)?[ \t]+(.+?)[ \t]+(?:prepare-report|prepare-git-review)"
                                        r"[ \t]+--runtime(?:[ \t]+|=)(?:claude|codex)[ \t]*<<[ \t]*(['\"])"
                                        r"([A-Za-z_][A-Za-z0-9_]*)\2[ \t]*")


# --- the grant, the ledger and the counts ------------------------------------------------------
# A plan's approval can name a grant: where the Run may edit, the command classes, machines and
# handed-over data it may use, its budget and its expiry. Recorded, it answers for the calls it
# classifies (the grant's answers, below) until it expires; no decision reads a ledger line or a Run.
GRANT_KEYS = ("paths", "commands", "machines", "handover", "budget", "expires")
GRANT_COMMANDS = ("build", "test", "check", "snapshot", "remote-run", "commit")
GRANT_LISTS = {"paths": (1, 32), "commands": (0, 8), "machines": (0, 8), "handover": (0, 8)}  # entries per list
GRANT_BUDGET = {"minutes": (1, 10080), "fixAttempts": (0, 10)}
GRANT_NAME_LIMIT = 80  # characters of one machine or handed-over entry
# The question's extra line, then the three lines of the block in report.md.
GRANT_LABELS = {"ja": ("許諾", "範囲", "予算", "期限"), "en": ("Grant", "Scope", "Budget", "Expiry")}
# A report's confirmations: 1 to 4 {resource, action} for resources that ask each run, each used once.
CONFIRM_ITEMS, CONFIRM_ACTION_LIMIT = (1, 4), 200
CONFIRM_LABELS = {"ja": "確認", "en": "Confirm"}
# A service's confirmation names the prompt it sends: a file of at most PROMPT_BYTES, whose text the report shows
# and whose SHA-256 the record keeps, so that what runs is what the human read. An ssh resource's action is the
# exact command (the run lane compares it).
PROMPT_BYTES = 32 * 1024
# Beyond {resource, action}, a service's entry: its prompt, an optional schema file (its answer's shape, bound the
# same way) and `approve` (whether it may write; false unless given). The report keeps each file's text and SHA-256.
SERVICE_KEYS = {"prompt", "schema", "approve"}
STORED_SERVICE_KEYS = SERVICE_KEYS | {"text", "digest", "schemaText", "schemaDigest"}
MAY_WRITE = {"ja": "（書き込みあり）", "en": " (may write)"}
HEX64 = _Pattern("HEX64", r"[0-9a-f]{64}")
# The grant's answers to one call (in the PreToolUse decision, which Codex's PermissionRequest shares).
GRANT_ALLOW = "DDL: inside grant {} ({})"
OUTSIDE_PATHS = ("DDL grant: {} is outside the paths of grant {}; widening a grant is an exit gate, so ask the "
                 "human for a revised plan")
OUTSIDE_CLASS = "DDL grant: the command class {} is outside grant {}; ask the human for a revised plan"
OUTSIDE_MACHINE = "DDL grant: the machine {} is outside grant {}; ask the human for a revised plan"
EXIT_BEHIND_SSH = ("DDL grant: `{}` behind ssh is an exit or another transfer, which no grant covers; an exit runs "
                   "here, through its own review")
# ssh to a granted resource of the table by anything but its alias, or to a resource that ssh does not reach.
SERVICE_BY_SSH = ("DDL grant: `{}` is a service in the resource table (codex:); it is reached only through the gate's "
                  "`service`, never by ssh")
NAME_FOR_ALIAS = ("DDL grant: `{}` is a resource's name; ssh reaches it by the alias its `reach` names in the resource "
                  "table, or through the gate's `remote`")
NOT_COMPUTE = "DDL grant: `{}` is not a compute resource in the resource table; ask the human for a revised plan"
LEDGER_REASON = "DDL gate: only the gate writes the ledger ({}); use the gate's subcommands"
# Claude's editing tools and the key that names the file each writes; Codex edits with apply_patch.
EDIT_KEYS = {"Edit": "file_path", "Write": "file_path", "MultiEdit": "file_path", "NotebookEdit": "notebook_path"}
# A patch's file headers; an indented one counts too (Codex's own parser may accept it).
PATCH_TARGET = _Pattern("PATCH_TARGET", r"(?m)^[ \t]*\*\*\* (Add File|Update File|Delete File|Move to): (.*?)[ \t]*$")
PYTHON = _Pattern("PYTHON", r"python3(?:\.\d+)?|/usr/bin/python3")
PYTHON_FLAGS = _Pattern("PYTHON_FLAGS", r"-[IBu]+")
SSH_OPTION = _Pattern("SSH_OPTION", r"BatchMode=yes|ConnectTimeout=\d+")
# A remote command is literal words only: nothing a shell on either side would read as quoting or syntax.
SSH_SYNTAX = _Pattern("SSH_SYNTAX", r"['\"\\$`<>]")
GATE_WORDS = ("status", "report", "run-start", "run-item", "prepare-report", "prepare-git-review",
              "resources")  # need no class
# The gate's subcommands that reach the resource they name (class remote-run), the words of the command `remote`
# runs there (literal: nothing a remote shell reads as syntax), and the values of their options.
RESOURCE_WORDS = ("remote", "measure", "service")
REMOTE_WORD = _Pattern("REMOTE_WORD", r"[A-Za-z0-9_./:=@%+,-]+")
REMOTE_VALUES = {"--snapshot": r"[A-Za-z0-9_][A-Za-z0-9_./-]*", "--run": r"N-[0-9a-f]{12}",
                 "--item": r"[A-Za-z0-9][A-Za-z0-9._-]{0,31}", "--timeout": r"[1-9][0-9]{0,5}"}
ARTIFACT_GLOB = _Pattern("ARTIFACT_GLOB", r"[A-Za-z0-9_.*?+-][A-Za-z0-9_.*?/+-]*")
# The options each class form takes (anything else leaves the call to the host): a flag, or an option with a
# value (the next word or `=value`) that must match its pattern ("" for any literal word, "dir" for a directory
# inside the root).
NUMBER, DURATION = r"\d+", r"(?:\d+(?:\.\d+)?(?:ns|us|ms|s|m|h))+"
GO_OPTIONS = ({"-v", "-race", "-short", "-cover"}, {"-run": "", "-count": NUMBER, "-timeout": DURATION})
CARGO_OPTIONS = ({"--release", "--workspace", "--all-features", "--lib", "--bins", "--tests"},
                 {"-p": r"[A-Za-z0-9_][A-Za-z0-9_.-]*"})
PYTEST_OPTIONS = ({"-q", "-v", "-x", "-s"}, {"-k": "", "-m": "", "--maxfail": NUMBER})
UNITTEST_OPTIONS = ({"-v", "-q", "-f"}, {"-k": ""})
DISCOVER_OPTIONS = ({"-v", "-q", "-f"}, {"-k": "", "-s": "dir", "-p": "", "-t": "dir"})
MAKE_TARGETS = {"all": "build", "build": "build", "test": "test", "check": "check", "lint": "check"}
MAKE_JOBS = 256  # the most parallel jobs `make -j` may ask for
# What a grant never covers, even `**`: the adapters' directories, the ledger, the instruction files and the
# notebook (the gate reads its Validation commands), besides Git directories (in_git_directory).
PROTECTED_DIRS = (".claude", ".codex", ".agents", ".ddl", ".vscode", ".cursor", ".githooks")
PROTECTED_FILES = ("CLAUDE.md", "CLAUDE.local.md", "AGENTS.md", "AGENTS.override.md", ".claude.json", ".mcp.json", ".envrc",
                   ".gitattributes", ".gitmodules", ".pre-commit-config.yaml", "design.md", "design-history.md")
PROTECTED_PAIRS = ((".github", "workflows"),)  # a directory protected only inside its parent
SHELLS = ("bash", "sh", "zsh", "dash")
SHELL_HOMES = ("/bin", "/usr/bin", "/usr/local/bin", "/opt/homebrew/bin")
# Exit words: never allowed by a grant, and forbidden behind ssh. `gh` and `glab` count whatever the verb.
GIT_EXITS = {"push", "commit", "merge", "rebase", "reset", "cherry-pick", "revert", "am", "pull", "tag",
             "update-ref", "send-email", "commit-tree", "send-pack", "http-push", "receive-pack", "upload-pack",
             "upload-archive"}
GIT_EXIT_FLAGS = {"branch": {"-D", "-f", "--force"}, "checkout": {"-B"}, "switch": {"-C"}}
TRANSFERS = {"ssh", "scp", "rsync", "sftp", "ftp", "lftp", "tftp", "telnet", "rclone", "nc", "ncat", "socat", "gh",
             "glab", "hub"}
AWS_TRANSFERS = {"cp", "sync", "mv"}  # `aws s3 <verb>`; `aws s3api` whatever the verb
GSUTIL_TRANSFERS = {"cp", "rsync", "mv"}
UPLOAD_FLAGS = {"-T", "--upload-file", "-d", "--data", "--data-ascii", "--data-binary", "--data-raw",
                "--data-urlencode", "-F", "--form", "--form-string", "--json", "--post-data", "--post-file",
                "--body-data", "--body-file"}
METHOD_FLAGS = {"-X", "--request", "--method"}
# Writers a shell command may aim at a ledger file: every operand, or the last one (the destination).
LEDGER_WRITERS = {"rm": 0, "unlink": 0, "truncate": 0, "touch": 0, "tee": 0, "chmod": 0, "chown": 0, "shred": 0,
                  "mv": 0, "cp": -1, "install": -1, "ln": -1}
PROJECT_KEY_LENGTH = 16  # hex digits of the SHA-256 of the resolved ledger root
LEDGER = ".ddl"  # at the root of the main work tree; it ignores itself
EVENT_VERSION = 1
EVENT_TEXT_LIMIT = 200  # characters kept of a label, tool name or rule in one ledger line
ARMED_LIMIT = 8  # prepared questions one session keeps waiting for their answers; past it the oldest is let go
# The subcommands tools/ddl_run.py holds (see run_module); tools/test_ddl_run.py pins them to its WORDS.
RUN_WORDS = ("report", "run-start", "run-item", "snapshot", "resources", "measure", "remote", "service", "runner",
             "restore", "mail", "run-join")
CACHE = "pycache"  # the launcher's bytecode cache under the state directory (ddl_gate.py reads the same name)
ENTRY = None  # the launcher's path as it was run; ddl_gate.py sets it (gate_path_tokens)
# A timestamp the gate reads: date, `T`, time to the minute or finer, then `Z` or `±HH:MM` (group 8, optional
# here so that the caller can tell a missing offset from a malformed value).
ISO_TIME = _Pattern("ISO_TIME", r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,9}))?)?"
                                r"(Z|[+-]\d{2}:\d{2})?")
# The four count lines of `report` (tools/ddl_run.py) and the grant line of `status`: labels, then the body
# of each line.
COUNT_TEXT = {
    "ja": {"labels": ("問い", "待ち", "拒否", "許諾"), "asked": "{} 件（承認 {}、見直し {}、時間切れ {}）",
           "waiting": "人間 {}（答えまで中央値 {}、最長 {}）", "minutes": "{} 分", "denied": "{} 件",
           "grant": "{}（期限 {}、{}）", "valid": "有効", "expired": "期限切れ", "none": "なし", "unmeasured": "未計測"},
    "en": {"labels": ("Questions", "Waiting", "Denials", "Grant"), "asked": "{} (approved {}, revised {}, timed out {})",
           "waiting": "human {} (median to answer {}, longest {})", "minutes": "{} min", "denied": "{}",
           "grant": "{} (expires {}, {})", "valid": "valid", "expired": "expired", "none": "none",
           "unmeasured": "not measured"}}


def review_json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def review_hash(value):
    return hashlib.sha256(review_json(value).encode()).hexdigest()


def review_directory():
    return session_file("git-reviews", "").with_suffix("")


def git_read(cwd, *args, input_data=None, optional=False, ctx=None):
    """Bounded Git plumbing reads; do not invoke a pager, fsmonitor, replacement, or external diff.

    `ctx` {gitDir, workTree} names a second Git directory and its work tree: every read for it uses that pair."""
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0")
    timeout = min(5, _git_review_deadline - time.monotonic()) if _git_review_deadline else 5
    if timeout <= 0:
        raise TimeoutError("the Git review could not be verified within its hook time budget.")
    pair = ["--git-dir=" + ctx["gitDir"], "--work-tree=" + ctx["workTree"]] if ctx else []
    proc = subprocess.run(["git", "--no-pager", "--no-replace-objects", "-c", "core.fsmonitor=false", *pair,
                           "-C", str(cwd), *args], input=input_data, capture_output=True, env=env, timeout=timeout)
    if proc.returncode and not optional:
        raise ValueError("could not inspect Git state ({}).".format(args[0]))
    return proc.stdout if not proc.returncode else None


def git_text(cwd, *args, optional=False, ctx=None):
    data = git_read(cwd, *args, optional=optional, ctx=ctx)
    return None if data is None else data.decode("utf-8", "surrogateescape").strip()


def git_review_command(command, cwd):
    """Parse the narrow executable forms supported by a review, never rewrite the attempted call.

    (directory, `commit` or `push`, arguments, ctx): ctx is {gitDir, workTree} for a commit in a second Git
    directory (`git [-C <path>] --git-dir=<dir> --work-tree=<dir> commit …`, both resolved from the directory
    the preceding `-C` gives), else None."""
    parts = split_segments(command)
    if not parts or len(parts[0]) != 1 or not native_linear_shell(command, parts):
        raise ValueError("use a standalone literal Git command; wrappers and compound writes are not reviewable.")
    args = shlex.split(command)
    executable = args.pop(0) if args else ""
    if os.path.basename(executable) != "git":
        raise ValueError("use a standalone Git command.")
    if executable != "git" and (not os.path.isabs(executable) or pathlib.Path(executable).resolve() !=
                                pathlib.Path(shutil.which("git") or "git").resolve()):
        raise ValueError("use Git from the configured PATH, not a relative or alternate executable.")
    here, pair = pathlib.Path(cwd).resolve(strict=True), {}
    while args and args[0].startswith("-"):
        flag = args.pop(0)
        name, equal, value = flag.partition("=")
        if name in ("--git-dir", "--work-tree") and not equal and args:
            value, equal = args.pop(0), "="
        if name in ("--git-dir", "--work-tree") and equal and value and name not in pair:
            pair[name] = str((here / value).resolve(strict=True))
        elif pair and (flag == "-C" or flag.startswith("-C")):
            raise ValueError("put -C before --git-dir and --work-tree; Git reads those from the directory -C gives.")
        elif flag == "-C" and args:
            here = (here / args.pop(0)).resolve(strict=True)
        elif flag.startswith("-C") and len(flag) > 2:
            here = (here / flag[2:]).resolve(strict=True)
        elif flag not in ("--no-pager", "--no-optional-locks", "--no-replace-objects"):
            raise ValueError("this Git global option is not supported by a content review: {}.".format(flag))
    if not args or args[0] not in ("commit", "push"):
        raise ValueError("only ordinary commit and push operations are reviewable; low-level equivalents are denied.")
    if pair and (len(pair) != 2 or args[0] != "commit"):
        raise ValueError("a second Git directory is reviewed as `git --git-dir=<dir> --work-tree=<dir> commit …`;"
                         " pushing from it is not supported.")
    for key in os.environ:
        if key in {"GIT_INDEX_FILE", "GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_OBJECT_DIRECTORY",
                   "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_NAMESPACE", "GIT_CONFIG", "GIT_CONFIG_PARAMETERS"} \
                or key.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_")):
            raise ValueError("an ambient Git context override prevents a reliable review: {}.".format(key))
    ctx = {"gitDir": pair["--git-dir"], "workTree": pair["--work-tree"]} if pair else None
    if not ctx and git_text(here, "rev-parse", "--is-inside-git-dir", optional=True) == "true":
        # `git -C <a git directory> commit` would show one repository's branch with another's index.
        raise ValueError("run Git from the work tree; a second Git directory takes --git-dir and --work-tree.")
    return here, args[0], args[1:], ctx


def visible_git_write(command, depth=0):
    """Recognize literal protected Git calls, including static shell/env wrappers, not arbitrary programs."""
    if not isinstance(command, str) or depth > 4:
        return False
    # Quoted here-documents are data, often source code containing examples of Git commands.
    # Do not mistake their lines for shell execution or scan arbitrary program bodies.
    command = re.sub(r"(<<-?\s*(['\"])([A-Za-z_][A-Za-z0-9_]*)\2[^\n]*\n).*?^\t*\3\s*$",
                     r"\1", command, flags=re.M | re.S)
    quote, i = None, 0
    while i < len(command):
        ch = command[i]
        if ch == "\\" and quote != "'":
            i += 2
            continue
        if ch == "'" and quote != '"':
            quote = None if quote == "'" else "'"
        elif ch == '"' and quote != "'":
            quote = None if quote == '"' else '"'
        elif quote != "'" and (command[i:i + 2] == "$(" or ch == "`"):
            start = i + (2 if ch == "$" else 1)
            end = command.find(")" if ch == "$" else "`", start)
            if end != -1 and visible_git_write(command[start:end], depth + 1):
                return True
        i += 1
    parts = split_segments(command)
    if not parts:
        return re.match(r"\s*(?:git|[^\s]+/git)\s+(?:commit|push|commit-tree|send-pack)\b", command) is not None
    for part in parts[0]:
        try:
            args = shlex.split(part)
        except ValueError:
            continue
        while args:
            if ASSIGNMENT.match(args[0]):
                args.pop(0)
            elif os.path.basename(args[0]) in ("env", "command", "builtin", "exec", "sudo"):
                args.pop(0)
                while args and (args[0].startswith("-") or ASSIGNMENT.match(args[0])):
                    flag = args.pop(0)
                    if flag in ("-u", "--unset", "-C", "--chdir", "--user", "--group", "-g") and args:
                        args.pop(0)
                    elif flag in ("-S", "--split-string") and args:
                        if visible_git_write(args.pop(0), depth + 1):
                            return True
            else:
                break
        if not args:
            continue
        if os.path.basename(args[0]) in ("bash", "sh", "zsh", "dash") and len(args) == 3 \
                and re.fullmatch(r"-[a-z]*c[a-z]*", args[1]):
            if visible_git_write(args[2], depth + 1):
                return True
        if os.path.basename(args[0]) == "git":
            index, _ = git_command(args[1:])
            if index is not None and args[index + 1] in GIT_PROTECTED:
                return True
            if index is not None and any(c in args[index + 1] for c in "$`*?{"):
                return True
            if index is None and any(a in GIT_PROTECTED for a in args[1:]):
                return True
    return False


def git_tree_fingerprint(cwd, commit=None, ctx=None, pin=None):
    """The hash of a commit's tree or of the index. `pin` (path, marker, accept): that gitlink reads as the marker
    when `accept` is None (a preparation, before the pushed commit exists) or when accept(its commit) is true."""
    cwd = git_repo(cwd, ctx)
    args = ("ls-tree", "--full-tree", "-r", "-z", commit) if commit else ("ls-files", "--full-name", "--stage", "-z")
    rows = []
    for row in git_read(cwd, *args, ctx=ctx).split(b"\0"):
        if not row:
            continue
        metadata, path = row.split(b"\t", 1)
        mode, second, third = metadata.split()
        oid = third if commit else second
        if not commit and third != b"0":
            raise ValueError("resolve the unmerged index before reviewing a commit.")
        name, oid = path.decode("utf-8", "surrogateescape"), oid.decode()
        if pin and name == pin[0] and mode == b"160000" and (pin[2] is None or pin[2](oid)):
            oid = pin[1]
        rows.append([mode.decode(), oid, name])
    return review_hash(sorted(rows))


def git_message(args, cwd):
    message, verbatim, file_message, i = [], False, False, 0
    while i < len(args):
        arg = args[i]
        if arg == "--cleanup=verbatim":
            verbatim = True
        elif arg in ("-m", "--message", "-F", "--file"):
            i += 1
            if i == len(args):
                raise ValueError("a commit message value is missing.")
            if arg in ("-F", "--file"):
                if message or args[i] == "-":
                    raise ValueError("use one literal message file, without stdin or mixed message forms.")
                try:  # a regular file of at most MESSAGE_BYTES, looked at before any open
                    message = [small_file(str(pathlib.Path(cwd) / args[i]), MESSAGE_BYTES).decode("utf-8")]
                except ValueError:
                    raise ValueError("a commit message file is a regular file of at most 64 KiB.") from None
                file_message = True
            else:
                if file_message:
                    raise ValueError("do not mix -m and -F message forms.")
                message.append(args[i])
        else:
            raise ValueError("unsupported commit option {}; use --cleanup=verbatim with -m or -F.".format(arg))
        i += 1
    if not verbatim or not message:
        raise ValueError("use git commit --cleanup=verbatim with -m or -F to preserve the reviewed message.")
    # Git completes each -m paragraph with LF, then inserts one LF between paragraphs.
    text = "\n".join(part if part.endswith("\n") else part + "\n" for part in message)
    if not text.strip() or "\0" in text:
        raise ValueError("the reviewed commit message must be nonempty UTF-8 text without NUL.")
    return text


def git_repo(cwd, ctx=None):
    return str(pathlib.Path(git_text(cwd, "rev-parse", "--show-toplevel", ctx=ctx)).resolve())


def repo_name(op):
    """How the question names an operation's repository: its directory, and for a second Git directory also that
    directory, `<work tree> (<git dir>)`, so a review holding a commit in each says which is which."""
    if op.get("gitDir") and op["gitDir"] != os.path.join(op["workTree"], ".git"):
        return "{} ({})".format(os.path.basename(op["workTree"]), os.path.basename(op["gitDir"]))
    return os.path.basename(op["repo"])


def commit_snapshot(cwd, args, ctx=None, pin=None, accept=None):
    """The reviewed commit. In a second Git directory (`ctx`) every read uses that pair, and the repository is
    the Git directory's real path: one review may hold a commit there and one in the work tree's own `.git`.

    `pin` {submodule, from}: a superproject commit whose submodule gitlink is the commit push operation `from`
    sends; its staged changes are shown without that gitlink, which reads as "pinned:<from>" (at a preparation,
    and at the commit when `accept`, the review's own account of what that push sends, accepts it)."""
    top = git_repo(cwd, ctx)
    git_dir = pathlib.Path(git_text(cwd, "rev-parse", "--absolute-git-dir", ctx=ctx))
    if any((git_dir / name).exists() for name in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge", "rebase-apply")):
        raise ValueError("finish the merge, rebase, cherry-pick, or revert before an ordinary commit review.")
    encoding = git_text(cwd, "config", "--get", "i18n.commitEncoding", optional=True, ctx=ctx)
    if encoding and encoding.lower().replace("-", "") != "utf8":
        raise ValueError("the ordinary review supports UTF-8 commit messages.")
    branch = git_text(cwd, "symbolic-ref", "--quiet", "HEAD", optional=True, ctx=ctx)
    if not branch:
        raise ValueError("review commits on a named branch; detached HEAD is not supported.")
    raw_args = ("diff", "--cached", "--no-relative", "--raw", "--no-ext-diff", "--no-textconv", "--no-renames")
    if git_read(top, *raw_args, "--ita-visible-in-index", ctx=ctx) != \
            git_read(top, *raw_args, "--ita-invisible-in-index", ctx=ctx):
        raise ValueError("fully stage or remove intent-to-add entries before reviewing the index.")
    scope = ("--", ".", ":(exclude){}".format(pin["submodule"])) if pin else ()
    if pin and git_read(top, "ls-files", "--stage", "--", pin["submodule"], ctx=ctx)[:6] != b"160000":
        raise ValueError("pin.submodule names a submodule (a gitlink) of the superproject.")
    patch = git_read(top, "diff", "--cached", "--no-relative", "--binary", "--no-ext-diff", "--no-textconv",
                     "--no-renames", *scope, ctx=ctx)
    if not patch and not pin:
        raise ValueError("stage the proposed files before preparing the review; the index is empty.")
    names = git_read(top, "diff", "--cached", "--no-relative", "--name-status", "-z", "--no-renames", *scope,
                     ctx=ctx).split(b"\0")
    files = [[names[i].decode(), names[i + 1].decode("utf-8", "surrogateescape")]
             for i in range(0, len(names) - 1, 2)] + ([["pin", pin["submodule"]]] if pin else [])
    marker = (pin["submodule"], "pinned:{}".format(pin["from"]), accept) if pin else None
    op = {"kind": "commit", "repo": top, "branch": branch,
          "head": git_text(cwd, "rev-parse", "--verify", "HEAD", optional=True, ctx=ctx),
          "tree": git_tree_fingerprint(cwd, ctx=ctx, pin=marker), "message": git_message(args, cwd),
          "files": files, "patchHash": hashlib.sha256(patch).hexdigest()}
    if pin:
        op["pin"] = {"submodule": pin["submodule"], "from": pin["from"]}
    if ctx:
        op.update(repo=str(git_dir.resolve()), gitDir=str(git_dir.resolve()), workTree=top)
    return op, patch


def display_remote(url):
    """A remote URL as reports and messages show it: never its user part (credentials, or an ssh login)."""
    if "://" in url:
        parsed = urlparse.urlsplit(url)
        if parsed.netloc and "@" in parsed.netloc:
            return urlparse.urlunsplit(parsed._replace(netloc=parsed.netloc.rsplit("@", 1)[1]))
        return url
    head = url.split(":", 1)[0]
    if ":" in url and "@" in head and "/" not in head:  # user@host:path
        return url[head.rindex("@") + 1:]
    return url


def push_snapshot(cwd, args, commits=(), record=None):
    flags = []
    while args and args[0] in ("--no-follow-tags", "--recurse-submodules=no"):
        flags.append(args[0]);args = args[1:]
    if "--no-follow-tags" not in flags and git_text(cwd, "config", "--bool", "--get", "push.followTags", optional=True) == "true":
        raise ValueError("use --no-follow-tags so the review cannot send additional tags.")
    recurse = git_text(cwd, "config", "--get", "push.recurseSubmodules", optional=True)
    recurse = recurse or git_text(cwd, "config", "--get", "submodule.recurse", optional=True)
    if recurse and recurse.lower() not in ("no", "false", "0", "off", "check") and "--recurse-submodules=no" not in flags:
        raise ValueError("use --recurse-submodules=no so the review cannot send to additional submodule remotes.")
    if len(args) != 2 or any(a.startswith("-") for a in args):
        raise ValueError("use one configured remote and one branch/refspec; unreviewed push options are unsupported.")
    remote, spec = args
    repo = git_repo(cwd)
    if remote not in (git_text(cwd, "remote") or "").splitlines():
        raise ValueError("review a configured remote name, not a URL or an implicit destination.")
    if git_text(cwd, "config", "--bool", "--get", "remote." + remote + ".mirror", optional=True) == "true":
        raise ValueError("mirror pushes are not supported by an ordinary branch review.")
    urls = git_text(cwd, "remote", "get-url", "--push", "--all", remote).splitlines()
    if len(urls) != 1:
        raise ValueError("review one push URL per remote.")
    source, sep, destination = spec.partition(":")
    if not sep:
        if source == "HEAD":
            raise ValueError("name the destination explicitly for a HEAD push.")
        destination = source if source.startswith("refs/heads/") else "refs/heads/" + source
    if not destination.startswith("refs/heads/") or not git_read(cwd, "check-ref-format", destination, optional=True) == b"":
        raise ValueError("the destination must be one explicit branch ref.")
    if not source or source.startswith("+") or any(c in source + destination for c in "*?[]"):
        raise ValueError("wildcards, deletion, and forced refspecs are not ordinary branch reviews.")
    dependent = next((c for c in commits if c["repo"] == repo and source in
                      ("HEAD", c["branch"], c["branch"].removeprefix("refs/heads/"))), None)
    oid = None if dependent else git_text(cwd, "rev-parse", "--verify", source + "^{commit}")
    tip = git_text(cwd, "rev-parse", "--verify", "--quiet", source + "^{commit}", optional=True) if dependent else oid
    if record is None:  # a preparation: what the remote has now, read from the remote itself
        head, known = remote_refs(cwd, remote, destination)
        base = None
    else:  # the push: what the review recorded of it
        reviewed = next((op for op in record["operations"] if op["kind"] == "push" and op["repo"] == repo
                         and op["remote"] == remote and op["destination"] == destination), None)
        if reviewed is None or reviewed.get("remoteHead") is None and reviewed.get("remoteBase") is None:
            raise ValueError("this push is not one of the approved set.")
        head, base, known = reviewed["remoteHead"], reviewed["remoteBase"], None
    if record is None and head and tip and git_read(cwd, "merge-base", "--is-ancestor", head, tip, optional=True) is None:
        raise ValueError("the remote's {} is not an ancestor of what is pushed (fetch and integrate it first).".format(
            destination[len("refs/heads/"):]))
    sends, parents = sent_commits(cwd, tip, head, known if base is None else base) if tip else ([], set())
    if record is None and not head:  # a new branch: the commits just outside what it sends bound it at the push
        base = sorted(parents - {entry["commit"] for entry in sends}) if sends else ([tip] if tip else [])
    placeholder = {"commit": None, "subject": None}  # the commit this review creates
    if dependent and record is None:
        sends.append(placeholder)  # a preparation: it comes last
    elif dependent and sends and matches_created_commit(dependent, cwd, sends[-1]["commit"],
                                                        pin_accept(record, dependent.get("pin"))):
        sends[-1] = placeholder
    return {"kind": "push", "repo": repo, "cwd": str(cwd), "remote": remote,
            "urlHash": review_hash(urls), "displayUrl": display_remote(urls[0]),
            "source": source, "destination": destination, "commit": oid,
            "fromCommit": review_hash(dependent) if dependent else None, "sends": sends, "remoteHead": head,
            "remoteBase": None if head else base}, b""


def push_target(cwd, remote):
    """The one URL a push to `remote` goes to, as `git push` resolves it (pushurl, pushInsteadOf). ValueError when
    reading that URL could reach another repository than the push: remote.<name>.uploadpack or .receivepack set, no
    single push URL, or a URL that reading rewrites (url.<base>.insteadOf)."""
    for key in ("uploadpack", "receivepack"):
        if git_read(cwd, "config", "--get-all", "remote.{}.{}".format(remote, key), optional=True) is not None:
            raise ValueError("remote.{}.{} is set; a review reads a remote only where its push goes.".format(remote, key))
    urls = (git_text(cwd, "remote", "get-url", "--push", "--all", remote, optional=True) or "").splitlines()
    if len(urls) != 1 or not urls[0]:
        raise ValueError("the push URL of the remote {} cannot be resolved to one URL.".format(remote))
    if git_text(cwd, "ls-remote", "--get-url", urls[0], optional=True) != urls[0]:
        raise ValueError("the push URL of the remote {} is rewritten when it is read (url.*.insteadOf); a review "
                         "reads a remote only where its push goes.".format(remote))
    return urls[0]


def ls_remote(cwd, remote, flags, patterns, seconds):
    """[(oid, ref)] `git ls-remote <flags> <push URL> <patterns>` reports, read where a push to `remote` goes
    (push_target; no prompt, no stdin, within `seconds`); ValueError with the reason when it cannot be read."""
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0")
    target = push_target(cwd, remote)
    try:
        proc = subprocess.run(["git", "--no-pager", "-C", str(cwd), "ls-remote", *flags, target, *patterns],
                              capture_output=True,
                              stdin=subprocess.DEVNULL, env=env, timeout=seconds)
    except subprocess.TimeoutExpired:
        raise ValueError("the remote {} did not answer within {} seconds; its branches cannot be read.".format(
            remote, seconds)) from None
    if proc.returncode:
        raise ValueError("the remote {} cannot be read now, so what it holds is not known.".format(remote))
    found = []
    for line in proc.stdout.decode("utf-8", "replace").splitlines():
        oid, _, ref = line.partition("\t")
        if re.fullmatch(r"[0-9a-f]{40,64}", oid):
            found.append((oid, ref))
    return found


def remote_refs(cwd, remote, destination, seconds=LS_REMOTE_SECONDS):
    """(head, known) from the remote itself: the commit its branch `destination` names (None when it has no such
    branch), and the commits its branches and tags name that this repository has (never a local tracking ref)."""
    found = ls_remote(cwd, remote, ["--heads", "--tags"], [], seconds)
    head = next((oid for oid, ref in found if ref == destination), None)
    oids = sorted({oid for oid, _ in found})
    types = git_read(cwd, "cat-file", "--batch-check=%(objectname) %(objecttype)",
                     input_data="".join(oid + "\n" for oid in oids).encode()).decode("utf-8", "replace").split("\n") \
        if oids else []
    known = {line.split(" ")[0] for line in types if line.endswith(" commit")}
    if head and head not in known:
        raise ValueError("the remote's {} is a commit this repository does not have; fetch it first.".format(
            destination[len("refs/heads/"):]))
    return head, sorted(known)


def sent_commits(cwd, tip, head, known=()):
    """([{commit, subject}], parents) a push of `tip` sends, oldest first: the commits after `head`, the remote
    branch's commit, or when the branch is new there, those that none of `known` (the commits the remote's branches
    and tags name) reaches; and every parent of those commits."""
    revs = [tip] + ["^" + oid for oid in ([head] if head else known)]
    lines = git_read(cwd, "rev-list", "--reverse", "--parents", "--format=%s", "--stdin",
                     input_data="".join(rev + "\n" for rev in revs).encode()).decode("utf-8", "replace").split("\n")
    sends, parents, i = [], set(), 0
    while i < len(lines):
        if re.fullmatch(r"commit [0-9a-f]{40,64}( [0-9a-f]{40,64})*", lines[i]):
            oids = lines[i].split(" ")[1:]
            sends.append({"commit": oids[0], "subject": lines[i + 1] if i + 1 < len(lines) else ""})
            parents.update(oids[1:])
            i += 2
        else:
            i += 1
    if len(sends) > SENT_LIMIT:
        raise ValueError("this push sends {} commits; a review lists at most {}.".format(len(sends), SENT_LIMIT))
    return sends, parents


def commit_patch(cwd, oid):
    """(message, patch bytes) of one commit against its first parent (the empty tree for a root commit)."""
    message = git_read(cwd, "log", "-1", "--format=%B", oid).decode("utf-8", "replace")
    parent = git_text(cwd, "rev-parse", "--verify", "--quiet", oid + "^1", optional=True)
    base = parent or git_text(cwd, "hash-object", "-t", "tree", os.devnull)
    patch = git_read(cwd, "diff", "--binary", "--no-ext-diff", "--no-textconv", "--no-renames", base, oid)
    return message, patch


def snapshot_operation(request, commits=(), record=None, pin=None, live=False):
    """(operation, patch) of one review request: at a preparation (`record` None), or at the commit or push the review
    `record` approved. `pin` reads a commit as the pinned one (commit_snapshot), its gitlink judged by the record."""
    if not isinstance(request, dict) or not isinstance(request.get("command"), str):
        raise ValueError("each review operation needs a literal command and working directory.")
    cwd, kind, args, ctx = git_review_command(request["command"], request.get("cwd") or os.getcwd())
    if pin and kind != "commit":
        raise ValueError("pin goes with a commit of the superproject.")
    if kind == "commit":  # at a preparation a pinned gitlink is unknown yet; at a commit the record judges it
        return commit_snapshot(cwd, args, ctx, pin, None if record is None else pin_accept(record, pin, live))
    return push_snapshot(cwd, args, commits, record)


def pin_accept(record, pin, live=False):
    """For a pin of the approved review `record`, the test a gitlink's commit must pass, from the hash-protected record
    alone: the commit a commit operation of the review creates (its prepared parent, message and tree) when the push
    `pin.from` sends that one, else exactly the source commit the review recorded. `live` (the pinned commit runs):
    that commit must also be what the push's remote branch names now, or an ancestor of it, read with `git ls-remote`
    (ValueError with the reason otherwise, and when the remote cannot be read). None without a pin."""
    if not pin:
        return None
    push = record["operations"][pin["from"] - 1] if 1 <= pin["from"] <= len(record["operations"]) else {}
    if push.get("kind") != "push":
        return lambda oid: False
    accept = recorded_pin(record, push)
    if not live:
        return accept

    def pushed(oid):
        global _git_review_deadline
        if not accept(oid):
            return False
        started = time.monotonic()
        found = ls_remote(push["cwd"], push["remote"], [], [push["destination"]], LS_REMOTE_PIN_SECONDS)
        if _git_review_deadline:  # the network read does not count against the hook's own Git budget
            _git_review_deadline += time.monotonic() - started
        head = next((found_oid for found_oid, ref in found if ref == push["destination"]), None)
        branch = push["destination"][len("refs/heads/"):]
        if head == oid:
            return True
        if head and git_read(push["cwd"], "merge-base", "--is-ancestor", oid, head, optional=True) is not None:
            return True
        raise ValueError("the pinned commit is not on {}'s {} (run its reviewed push first, or fetch).".format(
            push["remote"], branch))
    return pushed


def recorded_pin(record, push):
    """The record's own test for the commit a pin's push sends (pin_accept)."""
    if push.get("fromCommit"):
        created = next((op for op in record["operations"] if op["kind"] == "commit"
                        and review_hash(op) == push["fromCommit"]), None)
        if created is None or created.get("pin"):
            return lambda oid: False

        def made(oid):
            try:
                return matches_created_commit(created, created["repo"], oid)
            except (OSError, ValueError, TypeError):
                return False
        return made
    return lambda oid: bool(push.get("commit")) and oid == push["commit"]


def is_japanese(language):
    """Japanese labels for `ja` and its regional forms (`ja-JP`); every other language gets English labels."""
    return isinstance(language, str) and language.replace("_", "-").split("-")[0].lower() == "ja"


def fit_line(text):
    """One question value: line breaks flattened, at most QUESTION_LINE_LIMIT characters (cut with an ellipsis)."""
    text = " ".join(str(text).splitlines())
    return text if len(text) <= QUESTION_LINE_LIMIT else text[:QUESTION_LINE_LIMIT - len(ELLIPSIS)] + ELLIPSIS


def fit_subject(make, subject):
    """`make(subject)`, shortening the commit subject first so the whole line stays within the limit."""
    line = make(subject)
    excess = len(line) - QUESTION_LINE_LIMIT
    if excess > 0:
        line = make(subject[:max(len(subject) - excess - len(ELLIPSIS), 0)] + ELLIPSIS)
    return fit_line(line)


def question_text(language, values):
    """The five `<label>: <value>` lines; labels follow the language, values stay as given."""
    labels = QUESTION_LABELS["ja" if is_japanese(language) else "en"]
    return "\n".join(label + ": " + value for label, value in zip(labels, values))


def question_id(text):
    """(kind, hex) parsed from the ID line (`<label>: R-<hex>` or `G-<hex>`) of a question, or None.

    This one helper serves the PreToolUse check, the pending-STOP scan and the Git proof."""
    if not isinstance(text, str):
        return None
    lines = text.replace("\r\n", "\n").split("\n")
    match = QUESTION_ID.fullmatch(lines[QUESTION_ID_LINE]) if len(lines) > QUESTION_ID_LINE else None
    return (match[1], match[2]) if match else None


def first_question(request):
    """The first question object of a native request, given as an object or as JSON text; None when it has none."""
    if isinstance(request, str):
        try:
            request = json.loads(request)
        except ValueError:
            return None
    questions = request.get("questions") if isinstance(request, dict) else None
    if not isinstance(questions, list) or not questions or not isinstance(questions[0], dict):
        return None
    return questions[0]


def asked_question(runtime, request):
    """The first question's text in a native request (Claude `question`, Codex `title`), or None."""
    question = first_question(request)
    text = question.get("question" if runtime == "claude" else "title") if question else None
    return text if isinstance(text, str) else None


def option_labels(request):
    """The option labels of a native request's first question, in order (Claude lists objects, Codex strings)."""
    question = first_question(request)
    options = question.get("options") if question else None
    return [o.get("label") if isinstance(o, dict) else o for o in options] if isinstance(options, list) else []


def iso_seconds(text):
    """Seconds since the epoch for a timestamp that carries `Z` or a UTC offset, else None.

    Read by hand so that every Python agrees: `datetime.fromisoformat` learned `Z` and short fractions in 3.11."""
    match = ISO_TIME.fullmatch(text) if isinstance(text, str) else None
    if not match or not match[8]:
        return None
    offset = 0
    if match[8] != "Z":
        hours, minutes = int(match[8][1:3]), int(match[8][4:6])
        if hours > 23 or minutes > 59:
            return None
        offset = (hours * 3600 + minutes * 60) * (-1 if match[8][0] == "-" else 1)
    year, month, day, hour, minute, second = (int(match[i] or 0) for i in range(1, 7))
    leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    if not (1 <= year <= 9999 and 1 <= month <= 12 and hour <= 23 and minute <= 59 and second <= 59
            and 1 <= day <= (31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)[month - 1]):
        return None  # no such date or time of day (datetime's own bounds)
    # Days since 1970-01-01 in the proleptic Gregorian calendar, computed rather than imported: the datetime
    # module costs a hook call more than the arithmetic does.
    y = year - (month <= 2)
    days = 365 * y + y // 4 - y // 100 + y // 400 + (153 * ((month + 9) % 12) + 2) // 5 + day - 719469
    seconds = days * 86400 + hour * 3600 + minute * 60 + second
    return seconds + (float("0." + match[7]) if match[7] else 0.0) - offset


def utc_stamp(seconds=None):
    """`seconds` since the epoch (default: now) as ISO 8601 UTC with milliseconds: the form of every time the gate writes."""
    seconds = time.time() if seconds is None else seconds
    whole = int(seconds // 1)
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(whole)) + ".{:03d}Z".format(int((seconds - whole) * 1000))


def unique(items):
    return list(dict.fromkeys(items))


def counted(n, noun):
    return "{} {}{}".format(n, noun, "" if n == 1 else "s")


def git_question_values(record):
    """Decision, recommendation and consequence lines generated from the reviewed operations."""
    ja, ops = record["language"] == "ja", record["operations"]
    commits = [op for op in ops if op["kind"] == "commit"]
    pushes = [op for op in ops if op["kind"] == "push"]
    sep = "、" if ja else ", "
    several_repos = len({op["repo"] for op in ops}) > 1

    def where(op, text):  # name the repository only when the review spans more than one
        name = repo_name(op)
        return text + ("（{}）".format(name) if ja else " ({})".format(name)) if several_repos else text

    def branch(op):
        return op["branch"].removeprefix("refs/heads/")

    targets = unique(where(op, op["remote"] + "/" + op["destination"].removeprefix("refs/heads/")) for op in pushes)
    target_text = sep.join(targets)

    def sent(op):  # the commits a push sends (one for an operation that does not list them)
        return len(op.get("sends") or [None])

    if len(commits) == 1 and len(pushes) <= 1 and all(op["fromCommit"] for op in pushes):
        op, n = commits[0], len(commits[0]["files"])
        subject = (op["message"].splitlines() or [""])[0].strip()
        earlier = sent(pushes[0]) - 1 if pushes else 0
        if ja:
            tail = ("に記録し、先の {} 件と合わせて {} に送るか".format(earlier, target_text) if earlier else
                    "に記録し、{} に送るか".format(target_text)) if pushes else "に記録するか"
            decision = fit_subject(lambda s: "コミット「{}」（{} ファイル）を {} {}".format(s, n, branch(op), tail), subject)
        else:
            tail = (" and push it with {} to {}?".format(counted(earlier, "earlier commit"), target_text) if earlier else
                    " and push it to {}?".format(target_text)) if pushes else "?"
            decision = fit_subject(lambda s: 'Record commit "{}" ({}) on {}{}'.format(s, counted(n, "file"), branch(op), tail),
                                   subject)
    elif not commits and len(pushes) == 1:
        sha, n = (pushes[0]["commit"] or "")[:SHORT_SHA_LENGTH], sent(pushes[0])
        if n > 1:
            decision = ("{} 件のコミット（{} まで）を {} に送るか".format(n, sha, target_text) if ja else
                        "Push {} (up to {}) to {}?".format(counted(n, "commit"), sha, target_text))
        else:
            decision = "{} を {} に送るか".format(sha, target_text) if ja else "Push {} to {}?".format(sha, target_text)
    else:
        k, m = len(commits), sum(sent(op) for op in pushes)
        repos = sep.join(unique(repo_name(op) for op in commits))
        if commits and pushes:
            decision = ("{} 件のコミット（{}）を記録し、{} 件を送るか".format(k, repos, m) if ja else
                        "Record {} ({}) and push {}?".format(counted(k, "commit"), repos, m))
        elif commits:
            decision = ("{} 件のコミット（{}）を記録するか".format(k, repos) if ja else
                        "Record {} ({})?".format(counted(k, "commit"), repos))
        else:
            decision = ("{} 件を {} に送るか".format(m, target_text) if ja else
                        "Push {} to {}?".format(counted(m, "commit"), target_text))
    recommendation = ("この内容で実行する。内容・メッセージ・送信先は全文と差分のとおり" if ja else
                      "Execute it; contents, message and destination are as in the report and diff")
    if pushes:
        consequence = ("{} が新しいコミットに進む。取り消すには revert が要る".format(target_text) if ja else
                       ("{} advance to the new commits; undoing them needs a revert" if len(targets) > 1 else
                        "{} advances to the new commit; undoing it needs a revert").format(target_text))
    else:
        branches = unique(where(op, branch(op)) for op in commits)
        consequence = ("{} に新しいコミットができる（送信はしない）".format(sep.join(branches)) if ja else
                       ("{} get new commits (nothing is pushed)" if len(commits) > 1 else
                        "{} gets a new commit (nothing is pushed)").format(sep.join(branches)))
    return [fit_line(decision), fit_line(recommendation), fit_line(consequence)]


def review_question(record):
    """The five-line Git question (title) and its option labels, generated from the review record."""
    report = review_directory() / record["id"] / "report.md"
    title = question_text(record["language"], git_question_values(record) + ["G-" + record["id"], str(report)])
    counts = [sum(op["kind"] == kind for op in record["operations"]) for kind in ("commit", "push")]
    if record["language"] == "ja":
        action = "この内容で記録・送信する" if all(counts) else ("この内容を記録する" if counts[0] else "この内容を送信する")
        return {"title": title, "options": [action + "（推奨）", "内容を見直す", "保留する"]}
    action = "Commit and push" if all(counts) else ("Create reviewed commits" if counts[0] else "Push reviewed commits")
    return {"title": title, "options": [action + " (Recommended)", "Revise this review", "Hold"]}


def native_git_request(record):
    q = review_question(record)
    if record["runtime"] == "codex":
        return {"questions": [q]}
    descriptions = (["表示した変更・メッセージ・送信先だけを実行します。",
                     "実行せずに、確認案を見直します。", "記録・送信せずに止めます。"] if record["language"] == "ja" else
                    ["Execute only the displayed contents, message, and destinations.",
                     "Revise the review without executing it.", "Stop without committing or pushing."])
    kinds = {op["kind"] for op in record["operations"]}
    if record["language"] == "ja" and kinds == {"commit"}:
        descriptions[0], descriptions[2] = "表示した変更とメッセージでGitに記録します。", "記録せずに止めます。"
    elif record["language"] == "ja" and kinds == {"push"}:
        descriptions[0], descriptions[2] = "表示したコミットを、指定した送信先へ送信します。", "送信せずに止めます。"
    return {"questions": [{"question": q["title"], "header": "Git", "multiSelect": False,
                           "options": [{"label": label, "description": description}
                                       for label, description in zip(q["options"], descriptions)]}]}


def review_report(record, directory):
    question = review_question(record)
    ja = record["language"] == "ja"
    labels = ({"heading": "Gitの確認案", "commit": "記録", "push": "送信", "branch": "ブランチ", "base": "基準",
               "initial": "最初のコミット", "message": "コミットメッセージ", "files": "変更するファイル", "diff": "差分を確認する",
               "remote": "送信先", "destination": "送信先ブランチ", "source": "送信するコミット",
               "dependent": "この確認案の変更内容とメッセージで作成するコミット",
               "sends": "送るコミット（{} 件）:", "pin": "サブモジュール {}: 操作 {} が送るコミット"} if ja else
              {"heading": "Git review", "commit": "Commit", "push": "Push", "branch": "Branch", "base": "Base",
               "initial": "initial commit", "message": "Message", "files": "Files", "diff": "Full diff",
               "remote": "Remote", "destination": "Destination", "source": "Commit",
               "dependent": "the commit created from this same reviewed set",
               "sends": "Commits sent ({}):", "pin": "Submodule {}: the commit operation {} pushes"})
    lines = ["# " + labels["heading"] + " G-" + record["id"], "", question["title"], ""]
    for i, op in enumerate(record["operations"], 1):
        where = "{} ({})".format(op["workTree"], op["gitDir"]) if op.get("gitDir") else op["repo"]
        lines += ["## {}. {} — {}".format(i, labels[op["kind"]], where), ""]
        if op["kind"] == "commit":
            lines += [labels["branch"] + ": " + op["branch"], labels["base"] + ": " + (op["head"] or labels["initial"]),
                      "", labels["message"] + ":", "", *["> " + line for line in op["message"].splitlines()], "", labels["files"] + ":", ""]
            lines += ["- {} {}".format(status, json.dumps(path, ensure_ascii=False)) for status, path in op["files"]]
            if op.get("pin"):
                lines += ["", labels["pin"].format(json.dumps(op["pin"]["submodule"], ensure_ascii=False), op["pin"]["from"])]
            lines += ["", "[" + labels["diff"] + "](<" + str(directory / (str(i) + ".patch")) + ">)", ""]
        else:
            lines += [labels["remote"] + ": {} ({})".format(op["remote"], op["displayUrl"]),
                      labels["destination"] + ": " + op["destination"],
                      labels["source"] + ": " + (op["commit"] or labels["dependent"]), ""]
            sends = op.get("sends") or []
            if sends:
                lines += [labels["sends"].format(len(sends)), ""]
            for k, entry in enumerate(sends, 1):
                if not entry["commit"]:
                    lines += ["{}. {}".format(k, labels["dependent"]), ""]
                    continue
                detail = (record.get("sent") or {}).get("{}.{}".format(i, k), {})
                outside = (" （コミットの時点で許諾の外）" if ja else " (outside the grant at commit time)") if detail.get("outside") else ""
                lines += ["{}. {} {}{}".format(k, entry["commit"], entry["subject"], outside), "",
                          *["> " + line for line in detail.get("message", "").splitlines()], "",
                          "[" + labels["diff"] + "](<" + str(directory / "{}.{}.patch".format(i, k)) + ">)", ""]
    lines += (["承認するのは、この確認案に示した一式です。内容・メッセージ・送信先が変わった場合は、改めて確認します。",
               "保留・見直し・取消・時間切れでは実行しません。", ""] if ja else
              ["Approval covers this set only. Changed contents, message, source, or destination require a new review.",
               "A hold, revision, timeout, unrelated answer, or request receipt does not authorize Git execution.", ""])
    return "\n".join(lines)


def prepare_git_review(runtime, data):
    """Prepare immutable review detail, never an approval. Input is JSON on stdin."""
    if not isinstance(data, dict) or data.get("language", "en") not in ("en", "ja"):
        raise ValueError("choose language en or ja.")
    requests = data.get("operations")
    if not isinstance(requests, list) or not requests or len(requests) > 20:
        raise ValueError("prepare between one and twenty ready operations in one review.")

    operations, patches, commits = [], [], []
    for request in requests:
        pin = request.get("pin") if isinstance(request, dict) else None
        if pin is not None:
            if not isinstance(pin, dict) or set(pin) != {"submodule", "from"} or not one_line(pin["submodule"]) \
                    or type(pin["from"]) is not int:
                raise ValueError("pin is {submodule, from}: the submodule's path in the superproject and the number of "
                                 "an earlier push operation of this review (1 for the first operation).")
            if not 1 <= pin["from"] <= len(operations) or operations[pin["from"] - 1]["kind"] != "push":
                raise ValueError("pin.from names an earlier push operation of this review by its number.")
        op, patch = snapshot_operation(request, commits, None, pin)
        if pin:
            push = operations[pin["from"] - 1]
            url = submodule_url(op["repo"], pin["submodule"])
            if comparable_url(url, op["repo"]) != comparable_url(push_target(push["cwd"], push["remote"]), push["repo"]):
                raise ValueError("pin.from names a push to {}, not to the submodule's own URL in .gitmodules.".format(
                    push["displayUrl"]))
        if op in operations or op["kind"] == "commit" and any(c["repo"] == op["repo"] for c in commits):
            raise ValueError("review one commit per repository, and no duplicate operations.")
        if op["kind"] == "commit":
            commits.append(op)
        operations.append(op)
        patches.append(patch)
    if any(op["kind"] == "push" for op in operations):
        roots = {cwd_ledger()[0]} | {ledger_root(project_decision(op.get("workTree") or op["repo"])) for op in operations}
        open_run = next((run for run in (unclosed_run(root) for root in sorted(filter(None, roots))) if run), None)
        if open_run:
            raise ValueError("Run {} has open items and no `close` item whose dependencies are done; a push in the "
                             "middle of a Run needs a `close` item in the plan.".format(open_run))
    record = {"version": 1, "runtime": runtime, "language": data.get("language", "en"),
              "nonce": secrets.token_hex(NONCE_BYTES), "createdAt": time.time(), "operations": operations}
    sent = {}  # every commit a push sends: its message and diff, in the report
    for i, op in enumerate(operations, 1):
        marks = os.path.join(grant_store(), str(project_key(ledger_root(project_decision(op["repo"])))), "outside") \
            if op["kind"] == "push" else None
        for k, entry in enumerate(op.get("sends") or [], 1):
            if entry["commit"]:
                message, patch = commit_patch(op["cwd"], entry["commit"])
                detail = {"message": message, "patchHash": hashlib.sha256(patch).hexdigest()}
                if marks and os.path.exists(os.path.join(marks, entry["commit"])):
                    detail["outside"] = True  # a commit allowed inside a grant held paths outside it, after the look
                sent["{}.{}".format(i, k)] = (detail, patch)
    if sent:
        record["sent"] = {key: detail for key, (detail, _) in sent.items()}
    record["id"] = review_hash(record)[:ID_HEX_LENGTH]
    directory = review_directory() / record["id"]
    directory.mkdir(parents=True, mode=0o700, exist_ok=False)
    for i, patch in enumerate(patches, 1):
        if patch:
            (directory / (str(i) + ".patch")).write_bytes(patch)
    for key, (_, patch) in sent.items():
        (directory / (key + ".patch")).write_bytes(patch)
    (directory / "report.md").write_text(review_report(record, directory), encoding="utf-8")
    (directory / "review.json").write_text(review_json(record) + "\n", encoding="utf-8")
    return {"reviewId": "G-" + record["id"], "report": str(directory / "report.md"),
            "question": review_question(record), "nativeRequest": native_git_request(record)}


def submodule_url(top, path):
    """The URL the staged `.gitmodules` of the superproject at `top` gives the submodule at `path`; ValueError
    without one."""
    found = git_read(top, "config", "--blob", ":.gitmodules", "--get-regexp", r"^submodule\..*\.path$",
                     optional=True) or b""  # as the index holds it: what the commit records, not the work tree
    entries = [line.partition(" ") for line in found.decode("utf-8", "replace").splitlines()]
    if sum(1 for _, _, value in entries if value == path) > 1:
        raise ValueError("two .gitmodules entries name the path {}; give it one.".format(path))
    for key, _, value in entries:
        if value == path:
            url = git_text(top, "config", "--blob", ":.gitmodules", "--get", key[:-len(".path")] + ".url", optional=True)
            if url:
                return url
    raise ValueError("pin.submodule names a submodule that .gitmodules gives a URL.")


def comparable_url(url, base):
    """A Git URL as two spellings of one repository compare, a tuple, within one transport only: https/http (the
    user part ignored: credentials, not the repository), ssh (ssh:// and user@host:path, the user compared, a relative
    user@host:path no absolute ssh:// path) and git://. The host without case and with IPv6 brackets read, the port
    with its scheme's default filled in, the path without a trailing `/` or `.git`; a local path or file:// resolved
    from `base`. ValueError for a URL with a query, a fragment, a backslash or a space, or an unknown scheme: one that
    tools may read as another host. No error message carries the URL."""
    url = url.strip()
    scheme = re.match(r"([A-Za-z][A-Za-z0-9+.-]*)://", url)
    scp = None if scheme or url.startswith(("./", "../", "/")) else \
        re.match(r"(?:([^@/:\[\]]*)@)?(\[[^\]/]*\]|[^/:\[\]]+):(.*)\Z", url)
    if scheme and scheme[1].lower() != "file" or scp:
        if "\\" in url or "?" in url or "#" in url or any(ord(c) < 33 for c in url):
            raise ValueError("a URL with a query, a fragment, a backslash or a space is not compared.")
    if scp:  # user@host:path is ssh; its path is relative to the login unless it starts with /
        host = scp[2][1:-1] if scp[2].startswith("[") else scp[2]
        transport, user, port, path = "ssh", scp[1], DEFAULT_PORTS["ssh"], scp[3]
    elif scheme and scheme[1].lower() != "file":
        name = scheme[1].lower()
        transport = {"https": "http", "http": "http", "ssh": "ssh", "git+ssh": "ssh", "ssh+git": "ssh",
                     "git": "git"}.get(name)
        if transport is None:
            raise ValueError("a {} URL is not compared.".format(name))
        parsed = urlparse.urlsplit(url)
        try:
            port = parsed.port or DEFAULT_PORTS[name]
        except ValueError:
            raise ValueError("a URL with an unreadable port is not compared.") from None
        host, path = parsed.hostname, parsed.path or "/"
        user = parsed.username if transport == "ssh" else None
    else:  # a local path, or file://
        if url.startswith(("./", "../")):
            raise ValueError("a relative submodule URL is not compared; give .gitmodules the remote's own URL.")
        local = os.path.realpath(os.path.join(base, url[len("file://"):] if scheme else url)).rstrip("/")
        return "file", local[:-4] if local.endswith(".git") else local
    if not host:
        raise ValueError("a URL without a host is not compared.")
    path = path.rstrip("/")
    path = (path[:-4] if path.endswith(".git") else path).rstrip("/")
    return transport, user, host.lower(), port, path


def unclosed_run(root):
    """The ID of a Run of the project (the newest such) that has an open item (ready or running) and no `close` item
    of its own that is ready, running or done and whose dependencies are all settled (done or dropped): its `after`,
    or every other item when that is empty. None when every Run is closed so, and without a ledger or a Run.
    ValueError naming the Run's directory when its run.json is unreadable or malformed (fail closed)."""
    if not root:
        return None
    runs = os.path.join(root, LEDGER, "runs")
    try:
        names = os.listdir(runs)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise ValueError("{} cannot be read ({}); a push waits until its Runs can be read.".format(
            runs, exc.strerror or type(exc).__name__)) from None
    unclosed = []
    for name in names:
        directory = os.path.join(runs, name)
        if name.startswith(".") or not os.path.isdir(directory):
            continue
        if not os.path.lexists(os.path.join(directory, "run.json")):
            continue  # no Run (yet): run-start writes run.json whole
        try:
            with open(os.path.join(directory, "run.json"), encoding="utf-8") as fh:
                run = json.load(fh)
            items = run["items"] if isinstance(run, dict) else None
            if not isinstance(items, list) or not all(
                    isinstance(item, dict) and isinstance(item.get("id"), str) and item.get("status") in RUN_STATUSES
                    and isinstance(item.get("after", []), list)
                    and all(isinstance(after, str) for after in item.get("after", [])) for item in items) \
                    or len({item["id"] for item in items}) != len(items):
                raise ValueError("not a Run's items")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise ValueError("the Run in {} cannot be read ({}); a push waits until its run.json is whole.".format(
                directory, getattr(exc, "strerror", None) or str(exc).split(":")[0] or type(exc).__name__)) from None
        if not any(item["status"] in ("ready", "running") for item in items):
            continue
        settled = {item["id"] for item in items if item["status"] in ("done", "dropped")}
        closed = False
        for item in items:
            if item.get("kind") == "close" and item["status"] in ("ready", "running", "done"):
                after = set(item.get("after") or []) or {other["id"] for other in items if other is not item}
                closed = closed or after <= settled
        if not closed:
            unclosed.append((iso_seconds(run.get("startedAt")) or 0, str(run.get("id") or name)))
    return max(unclosed)[1] if unclosed else None


def load_git_review(review_id, runtime):
    """The prepared review record and its directory; ValueError when it was changed or is foreign."""
    directory = review_directory() / review_id
    record = json.loads((directory / "review.json").read_text(encoding="utf-8"))
    core = {k: v for k, v in record.items() if k != "id"}
    if record.get("id") != review_id or review_hash(core)[:ID_HEX_LENGTH] != review_id or record.get("runtime") != runtime:
        raise ValueError("the prepared review was changed or belongs to another runtime.")
    return record, directory


# --- decision reports -------------------------------------------------------------------------

def report_directory():
    return pathlib.Path(state_directory()) / "reports"


def grant_entries(grant, key, check):
    """One list of a grant: its size, then each entry as one printable line that passes `check`, all different."""
    values, (low, high) = grant[key], GRANT_LISTS[key]
    if not isinstance(values, list) or not low <= len(values) <= high:
        raise ValueError("grant.{} must be a list of {} to {} entries.".format(key, low, high))
    for value in values:
        if not one_line(value) or value != value.strip() or not value.isprintable():
            raise ValueError("grant.{}: each entry is one printable line without surrounding spaces.".format(key))
        check(value)
    if len(set(values)) != len(values):
        raise ValueError("grant.{} entries must differ.".format(key))


def validated_grant(grant, now):
    """The grant unchanged once every field passed; ValueError names the first problem.

    Nothing is repaired or defaulted: the object is hashed into the report ID exactly as it was given."""
    if not isinstance(grant, dict) or set(grant) != set(GRANT_KEYS):
        raise ValueError("grant must be an object with exactly these keys: {}.".format(", ".join(GRANT_KEYS)))

    def path(value):
        if value.startswith(("/", "~", "\\")) or re.match(r"[A-Za-z]:[/\\]", value) or ".." in re.split(r"[/\\]", value):
            raise ValueError("grant.paths: {!r} must be a relative glob: no leading / or ~, no .. segment.".format(value))

    def command(value):
        if value not in GRANT_COMMANDS:
            raise ValueError("grant.commands: {!r} is not one of {}.".format(value, ", ".join(GRANT_COMMANDS)))

    def name(value):
        if len(value) > GRANT_NAME_LIMIT:
            raise ValueError("grant.machines and grant.handover entries take at most {} characters.".format(
                GRANT_NAME_LIMIT))

    for key, check in (("paths", path), ("commands", command), ("machines", name), ("handover", name)):
        grant_entries(grant, key, check)
    budget = grant["budget"]
    if not isinstance(budget, dict) or set(budget) != set(GRANT_BUDGET):
        raise ValueError("grant.budget must be exactly {}.".format(" and ".join(GRANT_BUDGET)))
    for key, (low, high) in GRANT_BUDGET.items():
        if type(budget[key]) is not int or not low <= budget[key] <= high:  # `type is`: True and False are not counts
            raise ValueError("grant.budget.{} must be an integer from {} to {}.".format(key, low, high))
    expires = iso_seconds(grant["expires"])
    if expires is None:
        raise ValueError("grant.expires must be a timestamp with its UTC offset, such as 2026-12-23T00:00:00+09:00.")
    if expires <= now:
        raise ValueError("grant.expires is not in the future.")
    return grant


def validated_confirm(confirm, stored=False):
    """The confirmations unchanged once their shape passed: 1 to 4 different {resource, action}, with `prompt` (a
    file's path) for a service; the resource a table name, the action one printable line of at most
    CONFIRM_ACTION_LIMIT characters (an ssh resource's exact command, a service's summary). ValueError names the
    first problem. The preparation checks each resource against the table and reads each prompt
    (confirm_resources); `stored` checks the form the report keeps, where a prompt also has its text and digest."""
    low, high = CONFIRM_ITEMS
    if not isinstance(confirm, list) or not low <= len(confirm) <= high:
        raise ValueError("confirm must be a list of {} to {} {{resource, action}} objects.".format(low, high))
    for item in confirm:
        extra = set(item) - {"resource", "action"} if isinstance(item, dict) else None
        if extra is None or not {"resource", "action"} <= set(item) or extra and "prompt" not in extra \
                or not extra <= (STORED_SERVICE_KEYS if stored else SERVICE_KEYS) \
                or stored and extra and not {"text", "digest", "approve"} <= extra \
                or stored and ("schema" in extra) != ("schemaText" in extra) or ("schemaText" in extra) != ("schemaDigest" in extra):
            raise ValueError("each confirm entry is {resource, action}, and {resource, action, prompt, schema?, approve?} "
                             "for a service.")
        for key in ("prompt", "schema"):
            if key in item and not one_line(item[key]):
                raise ValueError("confirm: a {} is the path of a file.".format(key))
        if "approve" in item and type(item["approve"]) is not bool:
            raise ValueError("confirm: approve is true or false.")
        for text, digest in (("text", "digest"), ("schemaText", "schemaDigest")):
            if stored and text in item and not (isinstance(item[text], str) and HEX64.fullmatch(str(item[digest])) and
                                                hashlib.sha256(item[text].encode("utf-8")).hexdigest() == item[digest]):
                raise ValueError("confirm: a file's text does not match its digest.")
        if not table_word("name", item["resource"]):
            raise ValueError("confirm: a resource is a name of the resource table (lowercase letters, digits, hyphens).")
        action = item["action"]
        if not one_line(action) or action != action.strip() or not action.isprintable() \
                or len(action) > CONFIRM_ACTION_LIMIT:
            raise ValueError("confirm: each action is one printable line of at most {} characters, without surrounding "
                             "spaces: what will run.".format(CONFIRM_ACTION_LIMIT))
    if len({(item["resource"], item["action"]) for item in confirm}) != len(confirm):
        raise ValueError("confirm entries must differ.")
    return confirm


def confirm_line(language, confirm):
    """The value of the question's confirmation line: `resource: action` pairs, cut to one question line."""
    write = MAY_WRITE["ja" if is_japanese(language) else "en"]
    return fit_line(("、" if is_japanese(language) else "; ").join(
        "{}: {}{}".format(item["resource"], item["action"], write if item.get("approve") else "") for item in confirm))


def confirm_block(language, confirm):
    """The confirmations in full, as report.md shows them after the grant's block: one line each in a code fence,
    then each service's prompt, whole, under its SHA-256, in a fence longer than any run of backticks it holds."""
    ja = is_japanese(language)
    label, write = CONFIRM_LABELS["ja" if ja else "en"], MAY_WRITE["ja" if ja else "en"]
    parts = ["```\n" + "\n".join("{}: {}: {}{}".format(label, item["resource"], item["action"],
                                                    write if item.get("approve") else "") for item in confirm) + "\n```"]
    heads = {"text": ("{} の依頼（sha256 {}）:", "Prompt for {} (sha256 {}):", "digest"),
             "schemaText": ("{} の答えの形（sha256 {}）:", "Schema for {} (sha256 {}):", "schemaDigest")}
    for item in confirm:
        for key, (head_ja, head_en, digest) in heads.items():
            if key in item:
                fence = "`" * max([3] + [len(run) + 1 for run in re.findall(r"`+", item[key])])
                head = (head_ja if ja else head_en).format(item["resource"], item[digest])
                body = item[key] if item[key].endswith("\n") else item[key] + "\n"
                parts.append(head + "\n" + fence + "\n" + body + fence)
    return "\n\n".join(parts)


def grant_line(language, grant):
    """The value of the question's generated grant line: sizes, command classes, budget and the expiry date.

    Paths, machines and handed-over data are counted here and spelled out in the report's grant block."""
    budget, day = grant["budget"], grant["expires"][:10]
    paths, commands, machines, handover = (grant[key] for key in GRANT_KEYS[:4])
    if is_japanese(language):
        parts = ["編集 {} 範囲".format(len(paths)), "命令 " + "・".join(commands) if commands else "命令なし",
                 "マシン {} 台".format(len(machines)) if machines else "マシンなし"]
        parts += ["引き継ぎ {} 件".format(len(handover))] if handover else []
        parts += ["{} 分".format(budget["minutes"]), "直し {} 回".format(budget["fixAttempts"]), "期限 " + day]
        return fit_line("、".join(parts))
    parts = ["edit " + counted(len(paths), "scope"), "commands " + ", ".join(commands) if commands else "no commands",
             counted(len(machines), "machine") if machines else "no machines"]
    parts += ["{} handed over".format(len(handover))] if handover else []
    parts += [counted(budget["minutes"], "minute"), counted(budget["fixAttempts"], "fix attempt"), "expires " + day]
    return fit_line("; ".join(parts))


def grant_block(language, grant):
    """The grant in full, as report.md shows it between the question and the detail: Scope, Budget, Expiry.

    A code fence keeps the three lines apart and the globs literal (`**` would otherwise read as emphasis)."""
    ja = is_japanese(language)
    _, scope, budget, expiry = GRANT_LABELS["ja" if ja else "en"]
    comma, none = ("、", "なし") if ja else (", ", "none")
    paths, commands, machines, handover = ((sep.join(grant[key]) if grant[key] else none)
                                           for key, sep in zip(GRANT_KEYS[:4], (comma, "・" if ja else ", ", comma, comma)))
    minutes, fixes = grant["budget"]["minutes"], grant["budget"]["fixAttempts"]
    if ja:
        lines = ["{}: {}。命令 {}。マシン {}。引き継ぎ {}".format(scope, paths, commands, machines, handover),
                 "{}: {} 分。失敗した検査ごとの直し {} 回".format(budget, minutes, fixes)]
    else:
        lines = ["{}: {}; commands {}; machines {}; handed over {}".format(scope, paths, commands, machines, handover),
                 "{}: {}; {} per failing check".format(budget, counted(minutes, "minute"), counted(fixes, "fix attempt"))]
    return "```\n" + "\n".join(lines + ["{}: {}".format(expiry, grant["expires"])]) + "\n```"


def report_question(record, path):
    """The question and the host's native request for a prepared decision report: five lines, then one generated
    from the grant when the report carries one, and one from its confirmations when it carries them. The first
    five keep their positions."""
    values = [record[key] for key in REPORT_LINE_KEYS] + ["R-" + record["id"], str(path)]
    question = question_text(record["language"], values)
    if record["grant"]:
        label = GRANT_LABELS["ja" if is_japanese(record["language"]) else "en"][0]
        question += "\n" + label + ": " + grant_line(record["language"], record["grant"])
    if record["confirm"]:
        label = CONFIRM_LABELS["ja" if is_japanese(record["language"]) else "en"]
        question += "\n" + label + ": " + confirm_line(record["language"], record["confirm"])
    if record["runtime"] == "codex":
        return question, {"questions": [{"title": question, "options": [o["label"] for o in record["options"]]}]}
    return question, {"questions": [{"question": question, "header": "DDL", "multiSelect": record["multiSelect"],
                                     "options": [{"label": o["label"], "description": o["description"]}
                                                 for o in record["options"]]}]}


def one_line(value):
    return isinstance(value, str) and bool(value.strip()) and value.splitlines() == [value]


def report_options(language, options):
    if options is None:
        return DEFAULT_OPTIONS["ja" if is_japanese(language) else "en"]
    if not isinstance(options, list) or not MIN_OPTIONS <= len(options) <= MAX_OPTIONS:
        raise ValueError("options must be a list of {} to {} choices.".format(MIN_OPTIONS, MAX_OPTIONS))
    for option in options:
        if not isinstance(option, dict) or set(option) != {"label", "description"} or not one_line(option["label"]) \
                or not isinstance(option["description"], str) or not option["description"].strip():
            raise ValueError("each option is {label, description}: a one-line label and a non-empty description.")
    if len({option["label"] for option in options}) != len(options):
        raise ValueError("option labels must differ, because the answer names one label.")
    return options


# --- the resource table -----------------------------------------------------------------------
# The machines and services a grant may name are the user's: the personal environment declares them in one
# file per user, `$XDG_CONFIG_HOME/ddl/resources.toml` (an empty or relative XDG_CONFIG_HOME counts as unset),
# else `~/.config/ddl/resources.toml`. DDL fixes the place and the format, a strict subset of TOML that the
# personal environment's own reader enforces alike: `[name]` tables; double-quoted strings (escapes \" and \\
# only), non-negative integers and one-line lists of strings; `#` comments outside strings; blank lines. The
# table holds names and rules only, never how a machine is reached: a value shaped like an address, a path, a
# key or a token is refused. A problem names a line, or a resource and a field, never a value. The gate reads
# the file only when a preparation names machines or handed-over data, or a granted call reaches a resource.

RESOURCE_KEYS = ("roles", "hostname", "reach", "slots", "labels", "data", "needs", "confirm", "note")
RESOURCE_ROLES = ("host", "compute")
DATA_KINDS = ("code", "personal", "business")
CONFIRM_VALUES = ("each run",)
# A word of the table: (its first character, the characters after it, its longest length). It is checked character
# by character, and a secret shape's pattern is compiled only when its trigger is in the text, so that reading a
# table compiles nearly nothing, and ipaddress loads only for a run of characters that could be an IPv6 address.
ALNUM = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
LOWER_ALNUM = "abcdefghijklmnopqrstuvwxyz0123456789"
TABLE_WORDS = {"name": (LOWER_ALNUM, LOWER_ALNUM + "-", None), "key": (ALNUM + "_-", ALNUM + "_-", None),
               "hostname": (ALNUM, ALNUM + "-", 63), "alias": (ALNUM, ALNUM + "._-", None),
               "plugin": (LOWER_ALNUM, LOWER_ALNUM + "._-", None), "label": (ALNUM, ALNUM + "._+-", None)}
DIGITS = frozenset("0123456789")
HEX_RUN = frozenset("0123456789ABCDEFabcdef:.%")  # the characters of an IPv6 candidate
IPV4 = _Pattern("IPV4", r"(?<![0-9])[0-9]{1,3}(?:\.[0-9]{1,3}){3}(?![0-9])")
KEY_PREFIXES = ("sk-", "AIza", "ghp_", "github_pat_", "xox", "-----BEGIN")
# The shapes after an address, in order: (kind, the trigger no match lacks, the pattern).
SECRET_SHAPES = (("user@host", lambda text: "@" in text, r"[^\s@]@[^\s@]"),
                 ("a URL", lambda text: "://" in text, r"://"),
                 ("a port", lambda text: any(text[i + 1:i + 2] in DIGITS for i, char in enumerate(text) if char == ":"),
                  r"[A-Za-z0-9.\]-]:[0-9]{1,5}(?![0-9A-Za-z])"),
                 # a path wherever it starts: at the start or after a character no path holds ("x:/srv", "`/srv`")
                 ("a path", lambda text: "/" in text, r"(?:^|[^A-Za-z0-9._~/-])(?:/[A-Za-z0-9._~]|~[A-Za-z0-9._-]*/)"),
                 ("a key", lambda text: any(prefix in text for prefix in KEY_PREFIXES),
                  r"(?<![A-Za-z0-9])(?:sk-|AIza|ghp_|github_pat_|xox)|-----BEGIN"),
                 ("a token", lambda text: len(text) >= 32, r"[A-Za-z0-9_-]{32,}"))
LIST_VALUE = "a value that is not a double-quoted string, a non-negative integer or a one-line list of strings"
TABLE_BYTES = 64 * 1024  # the largest table read
# Lines end at \n alone (a \r before it is dropped); any other character that some reader takes for a line break
# is refused, so that no reader of the same file can see a line, a `confirm` for one, that another hides.
OTHER_BREAKS = frozenset("\r\x0b\x0c\x1c\x1d\x1e\x85\u2028\u2029")
_SHAPES = {}  # pattern source -> compiled pattern, filled on first use


def table_word(kind, text):
    """True when `text` is a word of the kind TABLE_WORDS names (a resource name, a key, a host name, an ssh alias,
    a Codex plugin, a label)."""
    first, rest, longest = TABLE_WORDS[kind]
    return isinstance(text, str) and bool(text) and text[0] in first and all(char in rest for char in text[1:]) \
        and (longest is None or len(text) <= longest)


def resource_table_path(env=None):
    """Where the user's resource table lives, whether or not it exists."""
    env = os.environ if env is None else env
    base = env.get("XDG_CONFIG_HOME") or ""
    if not os.path.isabs(base):
        base = os.path.join(env.get("HOME") or os.path.expanduser("~"), ".config")
    return os.path.join(base, "ddl", "resources.toml")


def read_resource_table(env=None):
    """(table, error) of the user's resource table (`env` defaults to this process's environment).

    The table is {name: {key: value}} in the file's order, each resource with the keys it declares as written
    (strings, lists of strings, `slots` an integer), and error is None. A missing file gives ({}, None): there is
    no table. A file that cannot be read, is not a regular file of at most 64 KiB, breaks the format or declares
    no resource gives ({}, reason)."""
    path, unreadable = resource_table_path(env), "the resource table cannot be read"
    try:
        os.lstat(path)
    except (FileNotFoundError, NotADirectoryError):
        return {}, None
    except OSError:
        return {}, unreadable
    try:
        text = small_file(path, TABLE_BYTES).decode("utf-8")
    except (OSError, UnicodeDecodeError):  # a dangling link, no permission, not UTF-8
        return {}, unreadable
    except ValueError as exc:
        return {}, "the resource table " + ("is larger than 64 KiB" if "larger" in str(exc) else "is not a regular file")
    return parse_resource_table(text)


def small_file(path, limit):
    """The bytes of the regular file at `path` (links followed), at most `limit` of them. It is looked at before any
    open, so that a FIFO, a device or a directory is never opened, and again once open. ValueError("not a regular
    file" or "larger than the limit"); OSError when it cannot be read."""
    import stat
    if not stat.S_ISREG(os.stat(path).st_mode):
        raise ValueError("not a regular file")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_CLOEXEC", 0))
    try:
        info, chunks, size = os.fstat(fd), [], 0
        if not stat.S_ISREG(info.st_mode):  # replaced between the two looks
            raise ValueError("not a regular file")
        while info.st_size <= limit and size <= limit:
            chunk = os.read(fd, limit + 1 - size)
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
        if info.st_size > limit or size > limit:
            raise ValueError("larger than the limit")
        return b"".join(chunks)
    finally:
        os.close(fd)


def secret_shape(text):
    """The kind of secret-like shape in `text` (an IP address, user@host, a URL, a port, a path, a key, a token), or
    None. Messages name the kind, never the text."""
    if "." in text and IPV4.search(text) or text.count(":") >= 2 and ipv6_in(text):
        return "an IP address"
    for kind, trigger, source in SECRET_SHAPES:
        if trigger(text):
            if source not in _SHAPES:
                _SHAPES[source] = re.compile(source)
            if _SHAPES[source].search(text):
                return kind
    return None


def ipv6_in(text):
    """True when a run of hexadecimal digits, colons, dots and `%` that no letter or digit touches is, without its
    scope and its outer dots, an IPv6 address as ipaddress reads one."""
    i, n = 0, len(text)
    while i < n:
        if text[i] not in HEX_RUN:
            i += 1
            continue
        j = i
        while j < n and text[j] in HEX_RUN:
            j += 1
        token, touched, i = text[i:j], (i and text[i - 1].isalnum()) or (j < n and text[j].isalnum()), j
        token = token.split("%", 1)[0].strip(".")
        if not touched and token.count(":") >= 2 and could_be_ipv6(token):
            try:
                ipaddress.IPv6Address(token)
                return True
            except ValueError:
                pass
    return False


def could_be_ipv6(token):
    """A condition every IPv6 address meets (ipaddress's own count of groups and their length), so that the module is
    loaded only for a token it may accept: at most 9 groups, exactly 8 without `::`, an IPv4 tail counting as two,
    and each group at most 4 characters without a dot."""
    parts = token.split(":")
    if "." in parts[-1]:
        parts = parts[:-1] + ["0", "0"]
    return len(parts) <= 9 and ("::" in token or len(parts) == 8) and all(len(part) <= 4 and "." not in part
                                                                        for part in parts)


def header_name(line):
    """The name in a `[name]` header (a stripped line), or None when the line is not one: `[`, blanks, the name (no
    `]` and no white space), blanks, `]`, blanks and an optional `#` comment."""
    i = _blank(line, 1)
    j = i
    while j < len(line) and line[j] != "]" and not line[j].isspace():
        j += 1
    k = _blank(line, j)
    if k >= len(line) or line[k] != "]":
        return None
    k = _blank(line, k + 1)
    return line[i:j] if k >= len(line) or line[k] == "#" else None


def _blank(text, index):
    while index < len(text) and text[index] in " \t":
        index += 1
    return index


def _table_string(text, index):
    """(string, index after it) of the double-quoted string at `index`; ValueError names what is wrong."""
    if text.startswith('"""', index):
        raise ValueError("a multi-line string")
    out, index = [], index + 1
    while index < len(text):
        char = text[index]
        if char == "\\":
            if text[index + 1:index + 2] in ('"', "\\"):
                out.append(text[index + 1])
                index += 2
                continue
            raise ValueError("an escape other than \\\" or \\\\ in a string")
        if char == '"':
            return "".join(out), index + 1
        if ord(char) < 0x20 or char == "\x7f":
            raise ValueError("a control character in a string")
        out.append(char)
        index += 1
    raise ValueError("a string that does not close on its line")


def _table_value(text):
    """The value after `key =`: a string, a non-negative integer or a one-line list of strings."""
    index = _blank(text, 0)
    if index >= len(text) or text[index] == "#":
        raise ValueError("a key without a value")
    char = text[index]
    if char == '"':
        value, index = _table_string(text, index)
    elif "0" <= char <= "9":
        end = index
        while end < len(text) and text[end] in DIGITS:
            end += 1
        digits = text[index:end]
        if len(digits) > 1 and digits[0] == "0":
            raise ValueError("an integer with a leading zero")
        value, index = int(digits), index + len(digits)
        if index < len(text) and text[index] not in " \t#":
            raise ValueError(LIST_VALUE)
    elif char == "[":
        value, index = [], _blank(text, index + 1)
        if text[index:index + 1] == "]":
            index += 1
        else:
            while True:
                index = _blank(text, index)
                if index >= len(text):
                    raise ValueError("a list that does not close on its line")
                if text[index] != '"':
                    raise ValueError("a list item that is not a double-quoted string")
                item, index = _table_string(text, index)
                value.append(item)
                index = _blank(text, index)
                if text[index:index + 1] == ",":
                    index = _blank(text, index + 1)
                    if text[index:index + 1] == "]":
                        index += 1
                        break
                    continue
                if text[index:index + 1] == "]":
                    index += 1
                    break
                if index >= len(text):
                    raise ValueError("a list that does not close on its line")
                raise ValueError("a list item followed by something other than a comma")
    else:
        raise ValueError(LIST_VALUE)
    index = _blank(text, index)
    if index < len(text) and text[index] != "#":
        raise ValueError("text after the value")
    return value


def parse_resource_table(text):
    """(table, error) of a resource table's text: what read_resource_table returns for a file holding it."""
    resources, headers, errors, current = {}, {}, [], None  # name -> {key: (value, line)}; name -> its line
    if text.startswith("\ufeff"):
        text = text[1:]
    for number, raw in enumerate(text.split("\n"), 1):
        raw = raw[:-1] if raw.endswith("\r") else raw
        if any(char in OTHER_BREAKS for char in raw):
            errors.append("line {}: a line break other than \\n".format(number))
            continue
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            name = header_name(line)
            current = {}  # the keys under a header in error belong to no resource
            if name is None or line.startswith("[["):
                errors.append("line {}: a table header that is not [name]".format(number))
            elif not table_word("name", name):
                errors.append("line {}: a resource name that is not lowercase letters, digits and hyphens".format(number))
            elif secret_shape(name):
                errors.append("line {}: a resource name that looks like a token".format(number))
            elif name in resources:
                errors.append("line {}: a resource declared twice (first on line {})".format(number, headers[name]))
            else:
                current, headers[name] = resources.setdefault(name, {}), number
            continue
        key, sep, rest = line.partition("=")
        key = key.strip()
        if not sep:
            errors.append("line {}: a line that is neither a [name] header nor key = value".format(number))
        elif not table_word("key", key):
            errors.append("line {}: a key that is not a bare word".format(number))
        elif current is None:
            errors.append("line {}: key = value before the first [name] header".format(number))
        else:
            try:
                value = _table_value(rest)
            except ValueError as exc:
                errors.append("line {}: {}".format(number, exc))
                continue
            if key in current:
                errors.append("line {}: a key given twice in one resource".format(number))
            else:
                current[key] = (value, number)
    if not errors:
        hostnames = {}
        for name, fields in resources.items():
            errors += ["resource {}: {}".format(name, problem) for problem in resource_problems(fields, name, hostnames)]
    if errors:
        more = len(errors) - 1
        return {}, errors[0] + (" (and {} more)".format(more) if more else "")
    if not resources:
        return {}, "the resource table declares no resource"
    return {name: {key: entry[0] for key, entry in fields.items()} for name, fields in resources.items()}, None


def resource_problems(fields, name, hostnames):
    """What one resource's fields break, as `field <key> …` phrases; `hostnames` collects the hosts' names."""
    problems, shaped = [], set()

    def label(key, line):  # a key is named when it is short and plain, else by its line
        return key if len(key) <= 24 and not secret_shape(key) else "on line {}".format(line)

    def get(key):
        return fields[key][0] if key in fields else None

    for key, (value, line) in fields.items():
        for text in [value] if isinstance(value, str) else value if isinstance(value, list) else []:
            kind = secret_shape(text)
            if kind:
                problems.append("field {} looks like {} (the value is not printed)".format(label(key, line), kind))
                shaped.add(key)
                break
    problems += ["unknown key " + label(key, line) for key, (_, line) in fields.items() if key not in RESOURCE_KEYS]
    roles = get("roles")
    valid = isinstance(roles, list) and bool(roles) and all(role in RESOURCE_ROLES for role in roles) \
        and len(set(roles)) == len(roles)
    if roles is None:
        problems.append("field roles is required")
    elif not valid:
        problems.append("field roles must list host, compute or both")
    known = roles if isinstance(roles, list) and roles and all(role in RESOURCE_ROLES for role in roles) else []
    host, compute = "host" in known, "compute" in known
    hostname = get("hostname")
    if "hostname" in fields and "hostname" not in shaped:
        if not table_word("hostname", hostname):
            problems.append("field hostname must be a short host name (letters, digits, hyphens)")
        elif known and not host:
            problems.append("field hostname is for a host")
        elif hostname.lower() in hostnames:
            problems.append("field hostname is also declared by " + hostnames[hostname.lower()])
        else:
            hostnames[hostname.lower()] = name
    elif host and "hostname" not in fields:
        problems.append("field hostname is required for a host")
    reach = get("reach")
    if "reach" in fields and "reach" not in shaped:
        scheme, _, target = reach.partition(":") if isinstance(reach, str) else ("", "", "")
        if scheme == "ssh" and table_word("alias", target):
            pass
        elif scheme == "codex" and table_word("plugin", target):
            if host:
                problems.append("field reach of a host must be ssh:<alias>")
        else:
            problems.append("field reach must be ssh:<alias> or codex:<plugin>")
    elif compute and "reach" not in fields:
        problems.append("field reach is required for compute")
    if "slots" in fields:
        slots = get("slots")
        if not isinstance(slots, int) or slots < 1:
            problems.append("field slots must be an integer of at least 1")
        elif known and not compute:
            problems.append("field slots is for compute")
    for key in ("labels", "needs"):
        if key in fields and key not in shaped:
            value = get(key)
            if not isinstance(value, list) or any(not table_word("label", v) for v in value):
                problems.append("field {} must be a list of words (letters, digits, . _ + -)".format(key))
    if "data" in fields:
        data = get("data")
        if not isinstance(data, list) or not data or any(d not in DATA_KINDS for d in data) or len(set(data)) != len(data):
            problems.append("field data must list code, personal, business or several of them")
        elif known and not compute:
            problems.append("field data is for compute")
    elif compute:
        problems.append("field data is required for compute")
    if "confirm" in fields:
        if get("confirm") not in CONFIRM_VALUES:
            problems.append('field confirm must be "each run"')
        elif known and not compute:
            problems.append("field confirm is for compute")
    if "note" in fields and not isinstance(get("note"), str):
        problems.append("field note must be a string")
    return problems


def grant_resources(grant):
    """Refuse (ValueError) a grant whose machines or handed-over data the resource table does not allow.

    With a table, each machine is a declared compute resource, `handover` names data kinds, and each machine's
    `data` holds every kind handed over. An invalid table refuses a grant that names machines. Without a table
    the names are free, as before (a machine is then its own ssh alias). Nothing is read for a grant that names
    neither machines nor handed-over data."""
    machines, handover = grant["machines"], grant["handover"]
    if not machines and not handover:
        return
    table, problem = read_resource_table()
    if problem:
        if machines:
            raise ValueError("grant.machines: the resource table is invalid ({}); correct it before a grant names "
                             "machines.".format(problem))
        return
    if not table:
        return
    for name in machines:
        if name not in table:
            raise ValueError("grant.machines: `{}` is not declared in the resource table.".format(name))
        if "compute" not in table[name]["roles"]:
            raise ValueError("grant.machines: `{}` is not a compute resource in the resource table.".format(name))
    if any(kind not in DATA_KINDS for kind in handover):
        raise ValueError("grant.handover names data kinds: {}.".format(", ".join(DATA_KINDS)))
    for name in machines:
        for kind in handover:
            if kind not in table[name]["data"]:
                raise ValueError("grant.handover: `{}` does not take `{}`.".format(name, kind))


def confirm_resources(confirm):
    """The confirmations as the report keeps them: each service's prompt read, with its text and SHA-256 added.

    ValueError when a resource is not a compute resource of the table (without a table, or with one that is
    invalid, there is nothing to confirm), a service names no prompt, an ssh resource names one, or a prompt file
    is not one confirm_prompt reads."""
    table, problem = read_resource_table()
    if problem:
        raise ValueError("confirm: the resource table is invalid ({}); correct it before confirming.".format(problem))
    if not table:
        raise ValueError("confirm names resources of the resource table, and there is none.")
    stored = []
    for item in confirm:
        entry = table.get(item["resource"])
        if entry is None:
            raise ValueError("confirm: `{}` is not declared in the resource table.".format(item["resource"]))
        if "compute" not in entry["roles"]:
            raise ValueError("confirm: `{}` is not a compute resource in the resource table.".format(item["resource"]))
        service = str(entry.get("reach")).startswith("codex:")
        if service and "prompt" not in item:
            raise ValueError("confirm: `{}` is a service: its entry names the prompt it sends (prompt: a file).".format(
                item["resource"]))
        if not service and set(item) & SERVICE_KEYS:
            raise ValueError("confirm: `{}` is reached by ssh: its action is the exact command, and it takes no "
                             "prompt.".format(item["resource"]))
        if service:
            item = dict(item, approve=item.get("approve", False))
            for key, text, digest in (("prompt", "text", "digest"), ("schema", "schemaText", "schemaDigest")):
                if key in item:
                    data = confirm_prompt(item[key], key)
                    try:
                        item[text] = data.decode("utf-8")
                    except UnicodeDecodeError:
                        raise ValueError("confirm: a {} file is UTF-8 text.".format(key)) from None
                    item[digest] = hashlib.sha256(data).hexdigest()
        stored.append(dict(item))
    return stored


def confirm_prompt(given, what="prompt"):
    """The bytes of a confirmation's prompt or schema file (`what`): `given` resolved from the working directory
    (links followed) to a regular file of at most PROMPT_BYTES inside the project's root, outside its protected
    places, or in a temporary directory. ValueError names what is wrong."""
    cwd = os.getcwd()
    decision = project_decision(cwd)
    place = Place(decision, project_root(decision))
    path = os.path.realpath(os.path.join(cwd, given))
    compared = place.locate(path)[1]
    if place.protected(compared) if compared is not None else not inside(path, place.temporary):
        raise ValueError("confirm: a {} file lies inside the project, outside its protected places, or in a "
                         "temporary directory.".format(what))
    try:
        return small_file(path, PROMPT_BYTES)
    except OSError:
        raise ValueError("confirm: the {} file cannot be read.".format(what)) from None
    except ValueError as exc:
        raise ValueError("confirm: the {} file {}.".format(
            what, "holds more than 32 KiB" if "larger" in str(exc) else "is not a regular file")) from None


def run_record(root, run_id):
    """The items of a Run in the project's ledger, `.ddl/runs/<N-id>/run.json` (read as tools/ddl_run.py's load_run
    reads it): {item id: {"files": [owner globs], "after": [item ids]}}; ValueError when there is no such Run."""
    try:
        with open(os.path.join(root, LEDGER, "runs", run_id, "run.json"), encoding="utf-8") as fh:
            run = json.load(fh)
    except (OSError, ValueError, TypeError):
        run = None
    if not isinstance(run, dict) or run.get("id") != run_id or not isinstance(run.get("items"), list):
        raise ValueError("Run {} is not in this project's ledger.".format(run_id))
    items = {}
    for item in run["items"]:
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            files, after = item.get("files", []), item.get("after", [])
            items[item["id"]] = {"files": [glob for glob in files if isinstance(glob, str)] if isinstance(files, list) else [],
                                 "after": [name for name in after if isinstance(name, str)] if isinstance(after, list) else []}
    return items


def held_closure(items, held):
    """The held items and every item that depends on one of them, through `after`, transitively."""
    closure, grown = set(held), True
    while grown:
        grown = False
        for name, item in items.items():
            if name not in closure and closure & set(item["after"]):
                closure.add(name)
                grown = True
    return closure


def validated_holds(holds, root):
    """`holds` unchanged once it names 1 to 16 different items of a Run in the project's ledger; ValueError says why
    not."""
    if not isinstance(holds, dict) or set(holds) != {"run", "items"}:
        raise ValueError("holds is {run, items}: a Run ID and the IDs of the items the question holds.")
    if not isinstance(holds["run"], str) or not re.fullmatch(RUN_ID_SOURCE, holds["run"]):
        raise ValueError("holds.run is a Run ID: N- and 12 hexadecimal characters.")
    low, high = HOLD_ITEMS
    items = holds["items"]
    if not isinstance(items, list) or not low <= len(items) <= high or len(set(map(str, items))) != len(items) \
            or not all(isinstance(name, str) and re.fullmatch(ITEM_ID_SOURCE, name) for name in items):
        raise ValueError("holds.items is a list of {} to {} different item IDs.".format(low, high))
    known = run_record(root, holds["run"])
    unknown = [name for name in items if name not in known]
    if unknown:
        raise ValueError("holds.items: {} is not an item of Run {}.".format(unknown[0], holds["run"]))
    return holds


def open_markers(key):
    """{original R-id: record} of the project's queued questions not answered yet: the files
    `<store>/<project key>/queued/<original R-id>.json` {id (the original), current (the latest asking), ids (every
    asking, oldest first), holds, provisional, snapshot, decision, options (labels), createdAt}. A question asked
    again (`replaces`) takes over its original's marker; a marker goes only on a proven answer to one of its ids."""
    found = {}
    if not key:
        return found
    directory = os.path.join(grant_store(), str(key), "queued")
    try:
        names = sorted(os.listdir(directory))
    except OSError:
        return found
    for name in names:
        try:
            with open(os.path.join(directory, name), encoding="utf-8") as fh:
                record = json.load(fh)
        except (OSError, ValueError):
            continue
        if isinstance(record, dict) and name == str(record.get("id")) + ".json" and isinstance(record.get("ids"), list) \
                and record.get("current") in record["ids"]:
            found[record["id"]] = record
    return found


def provisional_markers(key):
    """{current R-id: record} of the project's open provisional questions."""
    return {record["current"]: record for record in open_markers(key).values() if record.get("provisional")}


def write_marker(key, body):
    """Write the marker of an open queued question, privately (0600), whole or not at all."""
    store = grant_store()
    for part in (None, key, "queued"):
        store = os.path.join(store, part) if part else store
        private_directory(store)
    path = os.path.join(store, body["id"] + ".json")
    scratch = "{}.{}.tmp".format(path, os.getpid())
    fd = os.open(scratch, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, (review_json(body) + "\n").encode("ascii"))
    finally:
        os.close(fd)
    os.replace(scratch, path)


def validated_replaces(replaces, key, holds, provisional, decision, labels):
    """The original of the open queued question `replaces` asks again, when it is the same question: this project's,
    with the same Run and items (or none), the same provisional snapshot (or none), the same decision line and the
    same option labels. ValueError otherwise."""
    markers = open_markers(key)
    original = next((name for name, record in markers.items() if isinstance(replaces, str) and replaces in record["ids"]),
                    None)
    if original is None:
        raise ValueError("replaces names an open queued question of this project, by its report ID.")
    old, mine = markers[original], holds or {}
    theirs = old.get("holds") or {}
    same_holds = theirs.get("run") == mine.get("run") and \
        sorted(map(str, theirs.get("items") or [])) == sorted(map(str, mine.get("items") or []))
    if not same_holds or bool(old.get("provisional")) != bool(provisional) \
            or old.get("snapshot") != (provisional or {}).get("snapshot") or old.get("decision") != decision \
            or old.get("options") != labels:
        raise ValueError("replaces asks the same question again: the same Run and items, snapshot, decision line and "
                         "option labels as {}.".format(replaces))
    return original


def validated_provisional(provisional, holds, queue, root, key, skip=None):
    """`provisional` unchanged when it names an existing snapshot ref, goes with `queue: true` and `holds`, and no
    other unanswered provisional question of the same Run (`skip`, the original asked again, aside) holds an item
    this one holds or one depending on them."""
    if not isinstance(provisional, dict) or set(provisional) != {"snapshot"}:
        raise ValueError("provisional is {snapshot}: the snapshot ref to go back to when the answer differs.")
    if holds is None or queue is not True:
        raise ValueError("provisional goes with queue: true and holds: the items that depend on the choice.")
    ref = provisional["snapshot"]
    if not one_line(ref) or not ref.startswith(SNAPSHOT_REFS) or ".." in ref or not ref[len(SNAPSHOT_REFS):] \
            or git_read(root, "rev-parse", "--verify", "--quiet", ref + "^{commit}", optional=True) is None:
        raise ValueError("provisional.snapshot is an existing ref under {}.".format(SNAPSHOT_REFS))
    items = run_record(root, holds["run"])
    mine = held_closure(items, holds["items"])
    for original, other in open_markers(key).items():
        if original == skip or not other.get("provisional") or not other.get("holds"):
            continue
        if other["holds"].get("run") == holds["run"] and \
                mine & held_closure(items, [str(name) for name in other["holds"].get("items", [])]):
            raise ValueError("provisional: {} is not answered yet and holds items of Run {} this one depends on or "
                             "holds; no provisional decision rests on another.".format(other["current"], holds["run"]))
    return provisional


def hold_block(language, record):
    """The items a report holds (and its snapshot, for a provisional one), as report.md shows them: a code fence."""
    holds_label, provisional_label = HOLD_LABELS["ja" if is_japanese(language) else "en"]
    lines = ["{}: {}: {}".format(holds_label, record["holds"]["run"], ", ".join(record["holds"]["items"]))]
    if record.get("provisional"):
        lines.append("{}: {}".format(provisional_label, record["provisional"]["snapshot"]))
    return "```\n" + "\n".join(lines) + "\n```"


def report_core(record):
    """The fields a report's ID hashes: REPORT_CORE_KEYS, and each of REPORT_OPTIONAL_KEYS the report carries."""
    return {key: record[key] for key in REPORT_CORE_KEYS + tuple(key for key in REPORT_OPTIONAL_KEYS if key in record)}


def prepare_report(runtime, data):
    """Prepare a decision report and its native question; never an approval. Input is JSON on stdin."""
    if not isinstance(data, dict):
        raise ValueError("send one JSON object with language, decision, recommendation, consequence and detail.")
    unknown = sorted(set(data) - REPORT_INPUT_KEYS)
    if unknown:
        raise ValueError("unknown input keys: {}.".format(", ".join(unknown)))
    language = data.get("language")
    if not isinstance(language, str) or not LANGUAGE_CODE.fullmatch(language):
        raise ValueError("language must be a language code such as ja or en.")
    for key in REPORT_LINE_KEYS:
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError("{} must be a non-empty string.".format(key))
        if value.splitlines() != [value]:
            raise ValueError("{} must be one line; put the detail in the report.".format(key))
        if len(value) > QUESTION_LINE_LIMIT:
            raise ValueError("{} has {} characters; keep it within {} and put the detail in the report.".format(
                key, len(value), QUESTION_LINE_LIMIT))
    detail = data.get("detail")
    if not isinstance(detail, str) or not detail.strip():
        raise ValueError("detail must be the complete report as a non-empty string.")
    multi = data.get("multiSelect")
    multi = False if multi is None else multi
    if not isinstance(multi, bool):
        raise ValueError("multiSelect must be true or false.")
    if multi and runtime == "codex":
        raise ValueError("multiSelect is available on Claude only; a Codex question takes one answer.")
    created = time.time()
    try:
        _, project = cwd_ledger()
    except OSError:  # no working directory to read: no project
        project = None
    grant = data.get("grant")
    if grant is not None:
        validated_grant(grant, created)
        if multi:
            raise ValueError("a report with a grant takes one answer: its first option approves, so multiSelect is false.")
        if project is None:
            raise ValueError("a grant belongs to a DDL project; prepare the report from inside the project.")
        grant_resources(grant)
    confirm = data.get("confirm")
    if confirm is not None:
        validated_confirm(confirm)
        if multi:
            raise ValueError("a report with confirmations takes one answer: its first option confirms, so multiSelect "
                             "is false.")
        if project is None:
            raise ValueError("a confirmation belongs to a DDL project; prepare the report from inside the project.")
        confirm = confirm_resources(confirm)
    optional = {key: data[key] for key in REPORT_OPTIONAL_KEYS if data.get(key) is not None}
    if optional:
        root = cwd_ledger()[0]
        if project is None or root is None:
            raise ValueError("holds, queue and provisional belong to a DDL project; prepare the report from inside it.")
        if "holds" in optional:
            validated_holds(optional["holds"], root)
        if "queue" in optional and optional["queue"] is not True:
            raise ValueError("queue is true when given: the question waits to be asked in a batch.")
        original = None
        if "replaces" in optional:
            if optional.get("queue") is not True:
                raise ValueError("replaces goes with queue: true: it asks an open queued question again.")
            original = validated_replaces(optional["replaces"], project, optional.get("holds"), optional.get("provisional"),
                                          data["decision"], [o["label"] for o in report_options(language, data.get("options"))])
        if "provisional" in optional:
            if multi:
                raise ValueError("a provisional report takes one answer: its first option is the one gone ahead with.")
            validated_provisional(optional["provisional"], optional.get("holds"), optional.get("queue"), root, project,
                                  original)
    record = {"version": REPORT_VERSION, "runtime": runtime, "language": language,
              "nonce": secrets.token_hex(NONCE_BYTES), "createdAt": created,
              **{key: data[key] for key in REPORT_LINE_KEYS},
              "options": report_options(language, data.get("options")), "multiSelect": multi,
              "detailHash": hashlib.sha256(detail.encode("utf-8")).hexdigest(), "grant": grant, "confirm": confirm,
              "projectKey": project, **optional}
    record["id"] = review_hash(record)[:ID_HEX_LENGTH]
    directory = report_directory() / record["id"]
    question, request = report_question(record, directory / "report.md")
    # Without a grant the file keeps its bytes: the question, a blank line, the detail.
    text = (report_head(record, question) + detail + ("" if detail.endswith("\n") else "\n")).encode("utf-8")
    directory.mkdir(parents=True, mode=0o700, exist_ok=False)
    (directory / "report.md").write_bytes(text)
    record.update(question=question, nativeRequest=request, reportHash=hashlib.sha256(text).hexdigest())
    (directory / "report.json").write_text(review_json(record) + "\n", encoding="utf-8")
    if "queue" in optional:  # open until its answer: Stop names it while it is not asked, its holds stay held, and
        ident = "R-" + record["id"]  # a provisional one keeps every exit waiting
        old = open_markers(project).get(original) if "replaces" in optional else None
        if old:  # asked again: the original's marker, taken over
            body = dict(old, current=ident, ids=old["ids"] + [ident], updatedAt=utc_stamp(created))
        else:
            body = {"id": ident, "current": ident, "ids": [ident], "holds": optional.get("holds"),
                    "provisional": "provisional" in optional,
                    "snapshot": optional["provisional"]["snapshot"] if "provisional" in optional else None,
                    "decision": record["decision"], "options": [option["label"] for option in record["options"]],
                    "createdAt": utc_stamp(created)}
        write_marker(project, body)
    return {"reportId": "R-" + record["id"], "report": str(directory / "report.md"), "question": question,
            "nativeRequest": request}


def report_head(record, question):
    """What the gate writes at the top of report.md: the question, the grant's block and the confirmations' block
    when the report carries them; the detail follows."""
    block = grant_block(record["language"], record["grant"]) + "\n\n" if record["grant"] else ""
    block += confirm_block(record["language"], record["confirm"]) + "\n\n" if record["confirm"] else ""
    block += hold_block(record["language"], record) + "\n\n" if record.get("holds") else ""
    return question + "\n\n" + block


def load_report(report_id, runtime=None):
    """The prepared report record; ValueError when it, its question, or report.md was changed or is foreign.

    `runtime` None accepts either host's report (the Run subcommands read it outside a hook). Reading creates
    nothing: not even the state directory."""
    directory = pathlib.Path(state_base()) / "reports" / report_id
    record = json.loads((directory / "report.json").read_text(encoding="utf-8"))
    core = report_core(record)
    if record.get("id") != report_id or review_hash(core)[:ID_HEX_LENGTH] != report_id \
            or record.get("runtime") != (runtime or record.get("runtime")):
        raise ValueError("the prepared report was changed or belongs to another runtime.")
    if (record.get("question"), record.get("nativeRequest")) != report_question(record, directory / "report.md"):
        raise ValueError("the prepared question was changed.")
    text = (directory / "report.md").read_bytes()
    if hashlib.sha256(text).hexdigest() != record.get("reportHash"):
        raise ValueError("the report was changed after preparation.")
    # reportHash sits outside the hashed core, so also tie the file to the ID itself: the gate's own head
    # (question, grant block), then exactly the hashed detail. What the human reads is what was prepared.
    head = report_head(record, record["question"]).encode("utf-8")
    detail = text[len(head):]
    given = (detail, detail[:-1]) if detail.endswith(b"\n") else (detail,)  # preparation may have added the last newline
    if not text.startswith(head) or record["detailHash"] not in [hashlib.sha256(d).hexdigest() for d in given]:
        raise ValueError("the report was changed after preparation.")
    return record


def prepared_location(kind, prepared_id):
    """The report.md a prepared ID names (`R` decision report or `G` Git review)."""
    return (report_directory() if kind == "R" else review_directory()) / prepared_id / "report.md"


def predates_epoch(session_id, created_at):
    """True when the preparation is not newer than the session's last resume, compaction, fork, clear or prompt."""
    epoch = session_file(session_id, ".git-epoch")
    return epoch.exists() and created_at <= float(epoch.read_text())


def codex_git_reply(text):
    """Decode only the observed native reply envelope, without interpreting free-form approval words."""
    if not isinstance(text, str):
        return None
    try:
        match = re.fullmatch(r"\s*<send_user_message_question_reply>\s*(.*?)\s*</send_user_message_question_reply>\s*", text, re.S)
        rows = json.loads(match[1]) if match else None
        if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict) \
                or set(rows[0]) != {"questionItemId", "question", "answer"}:
            return None
        ref = json.loads(rows[0]["questionItemId"])
        if not isinstance(ref, list) or len(ref) != 3 or ref[0] != "request_user_input_async" \
                or not isinstance(ref[1], str) or not ref[1] or type(ref[2]) is not int or ref[2] != 0:
            return None
        return ref[1], rows[0]["question"], rows[0]["answer"]
    except (ValueError, TypeError, KeyError, IndexError):
        return None


def native_git_choice(runtime, path):
    """Return (question request, answer) only for the latest real submitted native choice.

    Match native request/result IDs, not an approval word, an assistant-authored receipt, or any
    assistant text: the question itself carries the review (its ID line). The walk stops at the
    matching request; a later human message, compaction, or unreadable record invalidates the proof.
    """
    stats = {"lines": 0, "parsed": 0}
    answer, request_id, title = None, None, None
    try:
        for entry in iter_entries_reversed(path, stats):
            if _git_review_deadline and time.monotonic() >= _git_review_deadline:
                return None
            if entry.get("isSidechain"):
                continue
            if entry.get("isCompactSummary") or entry.get("type") == "compacted":
                return None
            if runtime == "claude":
                if entry.get("type") == "assistant":
                    if answer is None:
                        continue
                    for block in (entry.get("message") or {}).get("content", []):
                        if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("id") == request_id:
                            if block.get("name") != "AskUserQuestion":
                                return None
                            return block.get("input", {}), answer
                elif is_human_prompt_claude(entry):
                    if answer is not None or not is_dialog_answer_claude(entry):
                        return None
                    result = entry.get("toolUseResult", {}).get("answers", {})
                    blocks = (entry.get("message") or {}).get("content", [])
                    refs = [b.get("tool_use_id") for b in blocks if isinstance(b, dict) and b.get("type") == "tool_result"]
                    if len(result) != 1 or len(refs) != 1 or not refs[0]:
                        return None
                    answer, request_id = next(iter(result.values())), refs[0]
            else:
                payload = entry.get("payload", {})
                kind, typ = entry.get("type"), payload.get("type")
                if kind == "event_msg" and typ == "task_started" and answer is None:
                    return None
                if kind == "event_msg" and typ == "item_completed" and payload.get("item", {}).get("type") == "UserMessage":
                    if answer is not None:
                        return None
                    reply = codex_git_reply(codex_text(payload["item"]))
                    if not reply:
                        return None
                    request_id, title, answer = reply
                if kind == "response_item" and typ == "function_call" and answer is not None \
                        and payload.get("call_id") == request_id:
                    if payload.get("name") != "request_user_input_async":
                        return None
                    request = json.loads(payload.get("arguments", "{}"))
                    # The reply envelope repeats the title. Normalize line endings before comparing: how the
                    # native host carries a multi-line title in that envelope has not been observed.
                    asked = request.get("questions", [{}])[0].get("title")
                    if not isinstance(asked, str) or not isinstance(title, str) or \
                            asked.replace("\r\n", "\n") != title.replace("\r\n", "\n"):
                        return None
                    return request, answer
    except (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError):
        return None
    return None


def approved_git_review(runtime, payload):
    proof = native_git_choice(runtime, payload.get("transcript_path"))
    if not proof:
        raise ValueError("no submitted native answer to a prepared Git review question is recorded.")
    request, answer = proof
    questions = request.get("questions", []) if isinstance(request, dict) else []
    if len(questions) != 1:
        raise ValueError("the Git review needs one whole-set native question.")
    ident = question_id(asked_question(runtime, request))
    if not ident or ident[0] != "G":
        raise ValueError("the choice is not for a prepared Git review.")
    record, directory = load_git_review(ident[1], runtime)
    expected = review_question(record)
    if request != native_git_request(record):
        raise ValueError("the question does not match the prepared review.")
    if answer != expected["options"][0]:
        raise ValueError("the selected action does not approve the current Git review.")
    if predates_epoch(payload.get("session_id"), record["createdAt"]):
        raise ValueError("prepare and review again after resume or compaction.")
    if (directory / "report.md").read_text(encoding="utf-8") != review_report(record, directory):
        raise ValueError("the review detail was changed after preparation.")
    for i, op in enumerate(record["operations"], 1):
        if _git_review_deadline and time.monotonic() >= _git_review_deadline:
            raise TimeoutError("the prepared review exceeded the hook time budget.")
        if op["kind"] == "commit":
            path = directory / (str(i) + ".patch")  # a pin that changes only its gitlink has no patch file
            data = b"" if op.get("pin") and not path.exists() else path.read_bytes()
            if hashlib.sha256(data).hexdigest() != op["patchHash"]:
                raise ValueError("the reviewed diff was changed after preparation.")
    for key, detail in (record.get("sent") or {}).items():
        if hashlib.sha256((directory / (key + ".patch")).read_bytes()).hexdigest() != detail["patchHash"]:
            raise ValueError("the diff of a commit the push sends was changed after preparation.")
    return record


def approved_report(runtime, payload, ident=None):
    """The prepared report whose grant or confirmations the human approved, proved like a Git review: from the
    question and its answer. ValueError says what is missing.

    The latest human input must be the submitted choice (never an idle timeout, a receipt or typed text) of
    the first option of the unchanged prepared question, for a report that carries a grant or confirmations, is
    not older than the session's epoch, and whose grant has not expired. The proof records a grant and the
    confirmations; it permits nothing. With `ident`, a question asked in a batch of queued questions (Claude) is
    proved from its own answer in that batch's submission."""
    proof = native_git_choice(runtime, payload.get("transcript_path"))
    if not proof and ident and runtime == "claude":
        proof = native_batch_choice(payload.get("transcript_path"), ident)
    if not proof:
        raise ValueError("no submitted native answer to a prepared report question is recorded.")
    request, answer = proof[:2]
    questions = request.get("questions", []) if isinstance(request, dict) else []
    if len(questions) != 1:
        raise ValueError("a grant needs one whole-plan native question.")
    ident = question_id(asked_question(runtime, request))
    if not ident or ident[0] != "R":
        raise ValueError("the choice is not for a prepared report.")
    record = load_report(ident[1], runtime)
    if request != record["nativeRequest"] or len(proof) > 2 and record.get("queue") is not True:
        raise ValueError("the question does not match the prepared report.")
    if not (record["grant"] or record["confirm"]) or record["multiSelect"]:
        raise ValueError("the report carries no grant and no confirmation.")
    if answer != record["options"][0]["label"]:
        raise ValueError("the selected option does not approve the plan.")
    if predates_epoch(payload.get("session_id"), record["createdAt"]):
        raise ValueError("the report predates the latest user message, resume or compaction.")
    if record["grant"]:
        validated_grant(record["grant"], time.time())  # a record written by hand passes no weaker check; expiry included
    if record["confirm"]:
        validated_confirm(record["confirm"], stored=True)
    return record


def native_batch_choice(path, ident):
    """({"questions": [the question]}, its answer, "batch") for the question `ident` (kind, hex) of the latest real
    submitted Claude batch of questions, or None: the walk and its rules are native_git_choice's, for a result
    that answers 2 to 4 questions."""
    stats, answers, request_id = {"lines": 0, "parsed": 0}, None, None
    low, high = BATCH_QUESTIONS
    try:
        for entry in iter_entries_reversed(path, stats):
            if entry.get("isSidechain"):
                continue
            if entry.get("isCompactSummary") or entry.get("type") == "compacted":
                return None
            if entry.get("type") == "assistant":
                if answers is None:
                    continue
                for block in entry_blocks(entry):
                    if block.get("type") == "tool_use" and block.get("id") == request_id:
                        if block.get("name") != "AskUserQuestion":
                            return None
                        questions = block.get("input", {}).get("questions")
                        for question in questions if isinstance(questions, list) else []:
                            text = question.get("question") if isinstance(question, dict) else None
                            if isinstance(text, str) and question_id(text) == tuple(ident) and text in answers:
                                return {"questions": [question]}, answers[text], "batch"
                        return None
            elif is_human_prompt_claude(entry):
                if answers is not None or not is_dialog_answer_claude(entry):
                    return None
                result = entry.get("toolUseResult", {}).get("answers", {})
                refs = [b.get("tool_use_id") for b in entry_blocks(entry) if b.get("type") == "tool_result"]
                if not isinstance(result, dict) or not low <= len(result) <= high or len(refs) != 1 or not refs[0]:
                    return None
                answers, request_id = result, refs[0]
    except (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError):
        return None
    return None


def matches_created_commit(op, cwd, oid, accept=None):
    """True when commit `oid` is the one the reviewed commit `op` creates: its parent, message and tree (a pinned
    gitlink one that `accept`, the review's account of what its push sends, accepts)."""
    data = git_read(cwd, "cat-file", "commit", oid)
    header, message = data.split(b"\n\n", 1)
    parents = [line.split(b" ", 1)[1].decode() for line in header.splitlines() if line.startswith(b"parent ")]
    pin = op.get("pin")
    marker = (pin["submodule"], "pinned:{}".format(pin["from"]), accept or (lambda found: False)) if pin else None
    return parents == ([op["head"]] if op["head"] else []) and message.decode("utf-8") == op["message"] \
        and git_tree_fingerprint(cwd, oid, pin=marker) == op["tree"]


def same_push(current, op):
    """True when the push `current` is the reviewed push `op`, sending the end of the commits it lists (all of them,
    or fewer when the destination has some already)."""
    if op.get("kind") != "push" or {k: v for k, v in current.items() if k != "sends"} != {k: v for k, v in op.items()
                                                                                       if k != "sends"}:
        return False
    sends, listed = current.get("sends") or [], op.get("sends") or []
    return len(sends) <= len(listed) and listed[len(listed) - len(sends):] == sends


def pin_step(runtime, payload, project, note):
    """The allow for a step between a reviewed push and the pinned commit that follows it, in an approved Git review:
    `git -C <superproject> submodule update --remote <path>`, `git -C <superproject>/<path> fetch [<remote>]`,
    `git -C <superproject>/<path> checkout <commit>` (the commit the push sends, as the review records it) and
    `git -C <superproject> add <path>`. None otherwise, and on any error."""
    try:
        if payload.get("tool_name") not in SHELL_TOOLS.get(runtime, set()) or escalated(payload) \
                or not ordinary_shell(payload):
            return None
        command = shell_command(payload.get("tool_input"))
        if not isinstance(command, str) or not command.startswith("git -C ") or not literal_shell(command):
            return None
        parts = split_segments(command)
        if not parts or len([raw for raw in parts[0] if raw.strip()]) != 1:
            return None
        tokens = shlex.split(command)
        if len(tokens) < 4 or tokens[:2] != ["git", "-C"]:
            return None
        target, rest = os.path.realpath(os.path.join(call_cwd(payload), tokens[2])), tokens[3:]
        record = approved_git_review(runtime, payload)
        for op in record["operations"]:
            pin = op.get("pin")
            if not pin:
                continue
            submodule = os.path.realpath(os.path.join(op["repo"], pin["submodule"]))

            def pushed(name):  # the commit the checkout names is the one the push sends, by the record
                found = git_text(submodule, "rev-parse", "--verify", "--quiet", name + "^{commit}", optional=True)
                return bool(found) and re.fullmatch(r"[0-9a-f]{7,64}", name) is not None and pin_accept(record, pin)(found)

            step = target == op["repo"] and rest in (["submodule", "update", "--remote", pin["submodule"]],
                                                     ["add", pin["submodule"]]) or \
                target == submodule and (rest == ["fetch"] or len(rest) == 2 and rest[0] == "fetch"
                                         and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", rest[1])
                                         or len(rest) == 2 and rest[0] == "checkout" and pushed(rest[1]))
            if step:
                note["allowed"] = {"kind": "pin-step", "id": "G-" + record["id"]}
                return permission("allow", PIN_STEP_ALLOW.format("G-" + record["id"]))
    except Exception:
        return None
    return None


def git_review_guard(runtime, payload, note=None):
    """None for a call that is no recognized commit or push; else a deny, or the allow for exactly the reviewed
    operation the human approved (`note` then gets `allowed`: the operation's kind and the review ID)."""
    global _git_review_deadline
    if payload.get("tool_name") not in SHELL_TOOLS.get(runtime, set()):
        return None
    command = shell_command(payload.get("tool_input"))
    if not visible_git_write(command):
        return None
    _git_review_deadline = time.monotonic() + GIT_REVIEW_BUDGET_SECONDS
    try:
        inputs = payload.get("tool_input", {})
        if isinstance(inputs, str):
            inputs = json.loads(inputs)
        cwd = inputs.get("workdir") or inputs.get("cwd") or payload.get("cwd")
        record = approved_git_review(runtime, payload)
        commits = [op for op in record["operations"] if op["kind"] == "commit"]
        request = {"command": command, "cwd": cwd}
        current, _ = snapshot_operation(request, commits, record)
        if current not in record["operations"] and current["kind"] == "commit":
            # A pinned commit: its gitlink must be what its push sends, as the review itself records it.
            for op in record["operations"]:
                if op.get("pin") and op["repo"] == current["repo"]:
                    pinned, _ = snapshot_operation(request, commits, record, op["pin"], live=True)
                    if pinned == op:
                        current = pinned
                        break
        if current["kind"] == "push":  # it may send fewer of the listed commits (some arrived already), never others
            current = next((op for op in record["operations"] if same_push(current, op)), current)
        if current not in record["operations"]:
            raise ValueError("the Git contents, message, branch, or destination differ from the approved set.")
        if current["kind"] == "push" and current["fromCommit"]:
            source = git_text(current["cwd"], "rev-parse", "--verify", current["source"] + "^{commit}")
            commit = next(op for op in commits if review_hash(op) == current["fromCommit"])
            if not matches_created_commit(commit, current["cwd"], source,  # a pinned one: its push reached the remote
                                          pin_accept(record, commit.get("pin"), live=True)):
                raise ValueError("the push source is not the commit created from the approved snapshot and message.")
        if time.monotonic() >= _git_review_deadline:
            raise TimeoutError("the Git state could not be verified within the hook time budget.")
    except Exception as exc:
        # An unreadable receipt must not become the generic STOP gate's fail-open path.
        return deny(GIT_REVIEW_REASON + str(exc))
    finally:
        _git_review_deadline = None
    # The content-bound review was the one confirmation: the host asks nothing more (its deny rules still win).
    if note is not None:
        note["allowed"] = {"kind": current["kind"], "id": "G-" + record["id"]}
    return permission("allow", REVIEW_ALLOW_REASON.format("G-" + record["id"]))


# --- conversation records -------------------------------------------------------------------

def iter_lines_reversed(path, block=65536):
    """Yield the lines of a file from the last to the first, decoded leniently."""
    with open(path, "rb") as fh:
        fh.seek(0, os.SEEK_END)
        pos = fh.tell()
        tail = b""
        while pos > 0:
            step = min(block, pos)
            pos -= step
            fh.seek(pos)
            parts = (fh.read(step) + tail).split(b"\n")
            tail = parts[0]  # may continue in the previous block
            for part in reversed(parts[1:]):
                yield part.decode("utf-8", "replace")
        yield tail.decode("utf-8", "replace")


def iter_entries_reversed(path, stats):
    """Yield the JSON objects of a JSONL file right to left; `stats` counts non-blank and parsed lines."""
    for line in iter_lines_reversed(path):
        if not line.strip():
            continue
        stats["lines"] += 1
        try:
            entry = json.loads(line)
        except ValueError:
            continue  # a truncated or foreign line; the entries around it still count
        if isinstance(entry, dict):
            stats["parsed"] += 1
            yield entry


def has_report(text) -> bool:
    return isinstance(text, str) and REPORT.search(text) is not None


def claude_text(entry) -> str:
    """The text of a Claude transcript entry: a string, or the `text` blocks of a block list."""
    content = (entry.get("message") or {}).get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
    return ""


def tool_result_text(entry) -> str:
    """The text inside the `tool_result` blocks of a Claude user entry (string or text-block content)."""
    content = (entry.get("message") or {}).get("content")
    out = []
    for block in content if isinstance(content, list) else []:
        if isinstance(block, dict) and block.get("type") == "tool_result":
            inner = block.get("content")
            if isinstance(inner, str):
                out.append(inner)
            elif isinstance(inner, list):
                out.extend(x.get("text", "") for x in inner if isinstance(x, dict))
    return "\n".join(out)


def is_dialog_answer_claude(entry) -> bool:
    """An answered AskUserQuestion or an approved ExitPlanMode plan: a human decision recorded as a tool
    result. Both carry `permissionDecision.source` starting with `user`; a rejected plan or
    auto-resolved question is not a submitted human answer."""
    result, decision = entry.get("toolUseResult"), entry.get("permissionDecision")
    if not isinstance(result, dict) or not isinstance(decision, dict):
        return False
    if not str(decision.get("source") or "").startswith("user"):
        return False
    # Native host-only timeout provenance is present even when selected options were auto-submitted.
    # A user-sourced permission decision alone therefore cannot establish a human submission.
    if result.get("afkTimeoutMs") is not None:
        return False
    if "answers" in result:
        answers = result["answers"]
        return isinstance(answers, dict) and any(isinstance(answer, str) and answer.strip()
                                                 for answer in answers.values())
    return "plan" in result and "approved your plan" in tool_result_text(entry)


def is_human_prompt_claude(entry) -> bool:
    """True when a `user` entry is something the human typed, queued, accepted, or decided in a dialog."""
    if entry.get("type") != "user":
        return False
    # Structural marks come before the origin fields: a compaction summary has been observed carrying a
    # turn-origin field, and tool results and attachments are never prompts whatever else they carry,
    # except the dialog answers above, which are the human speaking through a tool.
    if entry.get("isCompactSummary") or entry.get("isMeta"):
        return False
    if is_dialog_answer_claude(entry):
        return True
    if "toolUseResult" in entry:
        return False
    content = (entry.get("message") or {}).get("content")
    if isinstance(content, list) and content and all(isinstance(b, dict) and b.get("type") == "tool_result"
                                                     for b in content):
        return False
    origin = entry.get("origin")
    if isinstance(origin, dict) and "kind" in origin:
        return origin.get("kind") == "human"
    if "turnOrigin" in entry:
        return entry.get("turnOrigin") == "human"
    # Legacy entries carry no origin: judge the text itself (an image-only entry counts as not human).
    text = claude_text(entry).lstrip()
    return bool(text) and not text.startswith(NOT_HUMAN_PREFIXES)


def prepared_output(value, depth=0):
    """(kind, hex) when a tool output is the JSON that prepare-report or prepare-git-review printed, else None.

    Parsed, not searched, so reading a file that merely mentions an ID does not close the record. The JSON
    may sit in a known envelope: a JSON object's `output` field, a list of text items, or an `Output:` section."""
    if depth > ENVELOPE_DEPTH:
        return None
    if isinstance(value, str):
        text = value.strip()
        if "nativeRequest" not in text:  # cheap filter before parsing every tool output
            return None
        candidates = [text] + ([text.rsplit("Output:\n", 1)[1].strip()] if "Output:\n" in text else [])
        for candidate in candidates:
            try:
                found = prepared_output(json.loads(candidate), depth + 1)
            except ValueError:
                continue
            if found:
                return found
        return None
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict) and item.get("type") in ("text", "input_text"):
                item = item.get("text")
            if not isinstance(item, str):
                continue
            found = prepared_output(item, depth + 1)
            if found:
                return found
        return None
    if isinstance(value, dict):
        if "nativeRequest" in value:
            for kind, key in (("R", "reportId"), ("G", "reviewId")):
                match = PREPARED_ID.fullmatch(value[key]) if isinstance(value.get(key), str) else None
                if match and match[1] == kind:
                    return kind, match[2]
            return None
        if "output" in value:
            return prepared_output(value["output"], depth + 1)
    return None


def known_preparation(ident):
    """{"id", "report"} for a prepared ID whose report.md exists in this state directory, else None."""
    if not ident:
        return None
    path = prepared_location(*ident)
    return {"id": ident[0] + "-" + ident[1], "report": str(path)} if path.is_file() else None


def claude_pending_signal(entry):
    """(closes the record, prepared ID or None) for one Claude entry after the last human input.

    Assistant `text` blocks and question tool_use inputs are read; `thinking` blocks never are, since a
    signed thinking block may hold only a summary of what the assistant wrote."""
    content = (entry.get("message") or {}).get("content")
    blocks = [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []
    if entry.get("type") == "assistant":
        for block in blocks:
            if block.get("type") == "tool_use" and block.get("name") in QUESTION_TOOLS["claude"]:
                ident = question_id(asked_question("claude", block.get("input")))
                if ident:
                    return True, ident
        return has_report(claude_text(entry)), None
    if entry.get("type") == "user":
        result = entry.get("toolUseResult")
        ident = prepared_output(result.get("stdout")) if isinstance(result, dict) else None
        for block in blocks:
            if not ident and block.get("type") == "tool_result":
                ident = prepared_output(block.get("content"))
        if ident and queued_preparation(ident):
            return False, None  # prepared for a later batch: asking it makes the STOP pending
        return ident is not None, ident
    return False, None


def queued_preparation(ident):
    """True when a prepared ID names a decision report prepared with `queue: true` (its ID binds that key)."""
    if ident[0] != "R":
        return False
    try:
        return load_report(ident[1]).get("queue") is True
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return False


def scan_claude(path):
    """(state, pending): state is CLOSED (True), OPEN (False), or None when the record is unreadable;
    pending is {"id", "report"} when a known preparation is waiting, else None.

    Walking back to the last human input, the record is CLOSED by a line-initial +++DDL_REPORT in
    assistant text, by a question whose ID line names a preparation, or by the preparation output.
    The walk continues past a text-only signal to learn the pending ID."""
    stats = {"lines": 0, "parsed": 0}
    closed = False
    try:
        for entry in iter_entries_reversed(path, stats):
            if entry.get("isSidechain"):
                continue
            if is_human_prompt_claude(entry):
                break
            closes, ident = claude_pending_signal(entry)
            closed = closed or closes
            pending = known_preparation(ident)
            if pending:
                return True, pending
    except OSError:
        return (True, None) if closed else (None, None)
    if not closed and stats["lines"] and not stats["parsed"]:
        return None, None
    return closed, None


def record_state_claude(path) -> bool | None:
    """CLOSED (True), OPEN (False), or None when the record is unreadable."""
    return scan_claude(path)[0]


def codex_text(payload) -> str:
    content = payload.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(c.get("text", "") for c in content if isinstance(c, dict) and isinstance(c.get("text"), str))
    return ""


def codex_pending_signal(kind, ptype, payload):
    """(closes the record, prepared ID or None) for one Codex rollout item; reasoning items are never read."""
    if kind == "response_item" and ptype == "message" and payload.get("role") == "assistant":
        return has_report(codex_text(payload)), None
    if kind == "event_msg" and ptype == "agent_message":
        return has_report(payload.get("message")), None
    if kind == "response_item" and ptype == "function_call" and payload.get("name") in QUESTION_TOOLS["codex"]:
        ident = question_id(asked_question("codex", payload.get("arguments")))
        return ident is not None, ident
    if kind == "response_item" and ptype in ("function_call_output", "custom_tool_call_output"):
        ident = prepared_output(payload.get("output"))
        if ident and queued_preparation(ident):
            return False, None  # prepared for a later question: asking it makes the STOP pending
        return ident is not None, ident
    return False, None


def scan_codex(path):
    """Same contract as scan_claude, for a Codex rollout file.

    Only `item_completed`/UserMessage and `task_started` mark the human's turn: user-role messages also
    carry injected context (AGENTS.md, environment), so they cannot be the signal."""
    stats = {"lines": 0, "parsed": 0}
    closed = False
    try:
        for entry in iter_entries_reversed(path, stats):
            payload = entry.get("payload")
            if not isinstance(payload, dict):
                continue
            kind, ptype = entry.get("type"), payload.get("type")
            if kind == "event_msg" and ptype == "task_started":
                break
            if kind == "event_msg" and ptype == "item_completed":
                item = payload.get("item")
                if isinstance(item, dict) and item.get("type") == "UserMessage":
                    break
                continue
            closes, ident = codex_pending_signal(kind, ptype, payload)
            closed = closed or closes
            pending = known_preparation(ident)
            if pending:
                return True, pending
    except OSError:
        return (True, None) if closed else (None, None)
    if not closed and stats["lines"] and not stats["parsed"]:
        return None, None
    return closed, None


def record_state_codex(path, turn_id=None) -> bool | None:
    """Same contract as record_state_claude, for a Codex rollout file. `turn_id` is accepted for callers
    that have it; the boundary rule does not need it."""
    return scan_codex(path)[0]


# --- marker files -----------------------------------------------------------------------------

def state_base() -> str:
    """The state directory's absolute path; nothing is created."""
    base = os.environ.get("DDL_GATE_STATE_DIR") or os.path.join(os.environ.get("TMPDIR") or "/tmp", "ddl-gate")
    return os.path.abspath(base)  # the question's last line names report.md by its absolute path


def state_directory() -> str:
    base = state_base()
    os.makedirs(base, exist_ok=True)
    return base


def state_name(session_id) -> str:
    """The session id reduced to [A-Za-z0-9._-], the stem of its state file names."""
    name = "".join(c if c.isascii() and (c.isalnum() or c in "._-") else "_" for c in str(session_id or ""))
    return name or "unknown"


def session_file(session_id, suffix) -> pathlib.Path:
    return pathlib.Path(state_directory()) / (state_name(session_id) + suffix)


def marker_path(session_id) -> pathlib.Path:
    return session_file(session_id, ".pending")


# --- project detection ------------------------------------------------------------------------

MARKER = "→ DDL-PROTOCOL"
MARKERS = (MARKER, "-> DDL-PROTOCOL")
INSTRUCTION_FILES = ("CLAUDE.md", ".claude/CLAUDE.md", "AGENTS.md")


def instruction_directories(cwd):
    """`cwd` and its parents up to the directory holding `.git`; $HOME itself and anything above are excluded."""
    home = os.path.normpath(os.path.expanduser("~"))
    here = os.path.normpath(os.path.abspath(cwd))
    while here != home:
        yield here
        if os.path.exists(os.path.join(here, ".git")):
            return
        parent = os.path.dirname(here)
        if parent == here:
            return
        here = parent


def marker_line(path):
    """The number of the first line that is the DDL marker (surrounding whitespace allowed), or None."""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for number, line in enumerate(fh, 1):
                if line.strip() in MARKERS:
                    return number
    except OSError:
        pass
    return None


def project_decision(cwd) -> dict:
    """Whether `cwd` lies in a DDL project: cwd, ddl, source (the instruction file), line and mtime."""
    decision = {"cwd": cwd, "ddl": False, "source": None, "line": None, "mtime": None}
    if not isinstance(cwd, str) or not cwd:
        return decision
    for directory in instruction_directories(cwd):
        for name in INSTRUCTION_FILES:
            path = os.path.join(directory, name)
            line = marker_line(path)
            if line is not None:
                decision.update(ddl=True, source=path, line=line, mtime=os.stat(path).st_mtime)
                return decision
    return decision


def session_project(payload, refresh=False) -> dict:
    """The project decision for the event's `cwd`, cached per session as `<session_id>.project`.

    pre-tool-use and stop reuse the cache while `cwd` matches and the instruction file's mtime is
    unchanged (one stat); user-prompt-submit and session-start pass `refresh`. The cache is a
    convenience: an unusable state directory leaves the decision to a fresh search."""
    cwd = payload.get("cwd") or os.getcwd()
    try:
        path = os.path.join(state_directory(), state_name(payload.get("session_id")) + ".project")
    except OSError:
        return project_decision(cwd)
    if not refresh:
        try:
            with open(path, encoding="utf-8") as fh:
                cached = json.load(fh)
            if cached["cwd"] == cwd and (cached["ddl"] is False or
                                         os.stat(cached["source"]).st_mtime == cached["mtime"]):
                return cached
        except (OSError, ValueError, TypeError, KeyError):
            pass
    decision = project_decision(cwd)
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(decision, fh)
    except OSError:
        pass
    if decision["ddl"]:
        bytecode_cache()
    return decision


def bytecode_cache():
    """Create the launcher's bytecode cache `<state dir>/pycache` for this user alone (0700), in a DDL project
    only, so an unrelated project's hook writes no more than its decision. A failure changes no decision:
    the gate then runs uncached."""
    try:
        os.mkdir(os.path.join(state_directory(), CACHE), 0o700)
    except OSError:
        pass  # there already, or the state directory cannot take it


def project_status(argv) -> int:
    """`status [--cwd DIR]`: one line saying whether DIR (default: the current directory) is a DDL project."""
    cwd, rest = os.getcwd(), list(argv)
    while rest:
        arg = rest.pop(0)
        if arg == "--cwd" and rest:
            cwd = rest.pop(0)
        elif arg.startswith("--cwd="):
            cwd = arg.split("=", 1)[1]
        else:
            print("usage: ddl_gate.py status [--cwd DIR]", file=sys.stderr)
            return 2
    decision = project_decision(cwd)
    if decision["ddl"]:
        print("DDL project: yes ({}:{})".format(decision["source"], decision["line"]))
        try:  # one more line per recorded grant; a project without one prints exactly the line above
            key = project_key(ledger_root(decision))
            for record in grant_records(key):
                print("Grant: " + grant_summary(record, "en"))
            markers = sorted(open_markers(key).values(), key=lambda record: str(record.get("createdAt")))
            for label, wanted in (("Provisional", True), ("Queued", None)):  # open questions, oldest first
                for record in markers:
                    if wanted and not record.get("provisional"):
                        continue
                    started = iso_seconds(record.get("createdAt"))
                    age = "{} min".format(int((time.time() - started) // 60)) if started else "?"
                    extra = ", snapshot {}".format(record["snapshot"]) if record.get("snapshot") else ""
                    again = ", asked again from {}".format(record["id"]) if record["id"] != record["current"] else ""
                    print("{}: {} (Run {}{}, open {}{})".format(label, record["current"],
                                                               (record.get("holds") or {}).get("run") or "-", extra, age, again))
        except Exception:
            pass
    else:
        searched = list(instruction_directories(cwd))
        print('DDL project: no (no "{}" line up to {})'.format(MARKER, searched[-1] if searched else cwd))
    return 0


# --- the ledger and the grant store -----------------------------------------------------------

def git_common_directory(top):
    """The Git common directory of the work tree at `top`, read from `.git` and `commondir`; None without one.

    No Git process runs on the hook path. A linked work tree's `.git` is a file that names its own Git
    directory, and that directory's `commondir` leads to the repository every work tree shares."""
    dotgit = os.path.join(top, ".git")
    if os.path.isdir(dotgit):
        gitdir = dotgit
    else:
        try:
            with open(dotgit, encoding="utf-8", errors="replace") as fh:
                head = fh.readline().strip()
        except OSError:
            return None
        if not head.startswith("gitdir:"):
            return None
        gitdir = os.path.normpath(os.path.join(top, head[len("gitdir:"):].strip()))
    try:
        with open(os.path.join(gitdir, "commondir"), encoding="utf-8", errors="replace") as fh:
            return os.path.normpath(os.path.join(gitdir, fh.readline().strip()))
    except OSError:
        return gitdir  # the main work tree's own `.git` has no `commondir`


def ledger_root(decision):
    """The resolved root of the project's main work tree, where `.ddl/` lives; None outside a DDL project.

    It is the parent of the Git common directory when that directory is named `.git`, so every linked work
    tree shares one ledger and one project key. Otherwise (no repository, a bare one, a submodule) it is
    the directory that carries the marker's instruction file."""
    if not decision.get("ddl"):
        return None
    top = None
    for top in instruction_directories(decision["cwd"]):
        pass  # the search ends at the directory that holds `.git`, when there is one
    common = git_common_directory(top) if top else None
    if common and os.path.basename(common) == ".git":
        root = os.path.dirname(common)
    else:
        source = decision["source"]
        name = max((n for n in INSTRUCTION_FILES if source.endswith(os.sep + n)), key=len)
        root = source[:-len(name) - 1]
    return os.path.realpath(root)


def project_key(root):
    """A project's name in the grant store: the first hex digits of the SHA-256 of its resolved ledger root."""
    if not root:
        return None
    try:  # the interpreter's own SHA-256: hashlib would load OpenSSL first, which costs a hook call milliseconds
        from _sha2 import sha256  # Python 3.12 and later
    except ImportError:
        try:
            from _sha256 import sha256  # Python 3.11 and earlier
        except ImportError:
            sha256 = hashlib.sha256
    return sha256(root.encode("utf-8", "surrogateescape")).hexdigest()[:PROJECT_KEY_LENGTH]


def cwd_ledger():
    """(ledger root, project key) of the working directory, where a subcommand runs; (None, None) outside a
    DDL project."""
    root = ledger_root(project_decision(os.getcwd()))
    return root, project_key(root)


def write_whole(path, text):
    """Make `text` the whole of `path`: a reader sees the file as it was or as it is now, never half of it."""
    scratch = "{}.{}.tmp".format(path, os.getpid())
    try:
        with open(scratch, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(scratch, path)
    except OSError:
        try:
            os.unlink(scratch)
        except OSError:
            pass
        raise


def ledger_directory(root):
    """`<root>/.ddl` with a `.gitignore` of `*`: the ledger ignores itself.

    The ignore file is written whenever it is missing (the first use, a `.ddl/` that was there before, an
    earlier write that failed) and never rewritten once it exists, which costs one stat per ledger write.
    While it cannot be written this raises, so no line enters a ledger that Git would show. A `.ddl` that
    is a symbolic link raises too: following it would write outside the project."""
    directory = os.path.join(root, LEDGER)
    if os.path.islink(directory):
        raise OSError("the ledger directory is a symbolic link")
    ignore = os.path.join(directory, ".gitignore")
    if not os.path.exists(ignore):
        try:
            os.mkdir(directory)
        except FileExistsError:
            pass  # it was there already, or another gate process created it a moment ago
        write_whole(ignore, "*\n")
    return directory


def ledger_event(root, runtime, session, kind, ts=None, nulls=(), **fields):
    """Append one event line to `<root>/.ddl/events.jsonl`; fields that are None are left out, except those
    `nulls` names, which are written as null (an answer's `choice` when the human typed free text).

    It never raises and prints nothing: a failed write loses the line and changes no decision. One
    `os.write` per line on an O_APPEND descriptor, no lock, so concurrent hooks interleave whole lines.
    Two installs can each write the same hook event; a reader counts one kind, id and toolUseId once."""
    try:
        if not root:
            return
        line = {"v": EVENT_VERSION, "ts": ts or utc_stamp(), "host": runtime, "session": session, "kind": kind}
        for key, value in fields.items():
            if value is not None or key in nulls:
                line[key] = value[:EVENT_TEXT_LIMIT] if isinstance(value, str) else value
        data = (json.dumps(line, separators=(",", ":")) + "\n").encode("ascii")
        fd = os.open(os.path.join(ledger_directory(root), "events.jsonl"),
                     os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            os.write(fd, data)
        finally:
            os.close(fd)
    except Exception:
        pass


def cli_event(runtime, kind, **fields):
    """A subcommand's ledger line, in the working directory's project; like every ledger write it never raises."""
    try:
        ledger_event(cwd_ledger()[0], runtime, None, kind, **fields)
    except Exception:
        pass


def grant_store():
    """The durable user-level store of grant records: the path only. Recording a grant creates it."""
    base = os.environ.get("DDL_GATE_GRANT_DIR")
    if not base:
        state = os.environ.get("XDG_STATE_HOME") or os.path.join(os.path.expanduser("~"), ".local", "state")
        base = os.path.join(state, "ddl-gate")
    return os.path.abspath(base)


def private_directory(path):
    """Create `path` for its owner alone (0o700) when it is missing; missing parents get the default mode."""
    if not os.path.isdir(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            os.mkdir(path, 0o700)
        except FileExistsError:
            pass


def grant_file(key, ident):
    """Where the store keeps the record of one grant: `<store>/<project key>/grants/<R-id>.json`."""
    return os.path.join(grant_store(), key, "grants", ident + ".json")


def read_grant(path, ident):
    """The grant record in `path`, or None unless the file parses as a grant record that carries `ident`.

    Every reader goes through here: an empty or torn file, another record's copy and anything else that
    sits at a record's name is no grant."""
    try:
        with open(path, encoding="utf-8") as fh:
            record = json.load(fh)
    except (OSError, ValueError):
        return None
    if isinstance(record, dict) and record.get("id") == ident and isinstance(record.get("grant"), dict):
        return record
    return None


def grant_records(key=None):
    """The readable grant records of one project, or of every project when `key` is None; oldest approval
    first. Nothing is created, and a file that is not a grant record is skipped."""
    store, records, suffix = grant_store(), [], ".json"
    try:
        keys = sorted(os.listdir(store)) if key is None else [key]
    except OSError:
        return records
    for name in keys:
        directory = os.path.join(store, name, "grants")
        try:
            files = sorted(os.listdir(directory))
        except OSError:
            continue
        for file in files:
            record = read_grant(os.path.join(directory, file), file[:-len(suffix)]) if file.endswith(suffix) else None
            if record:
                records.append(record)
    return sorted(records, key=lambda record: (str(record.get("approvedAt")), record["id"]))


def grant_summary(record, language):
    """One grant record as a count line shows it: its ID, its expiry date, and whether it is still valid.

    Only the expiry ends a recorded grant: no session, prompt, resume or epoch is consulted here."""
    text, expires = COUNT_TEXT[language], record["grant"].get("expires")
    seconds = iso_seconds(expires)
    state = "valid" if seconds is not None and seconds > time.time() else "expired"
    return text["grant"].format(record["id"], expires[:10] if isinstance(expires, str) else "?", text[state])


def proved_grant(runtime, payload, root, ident, approved_at=None):
    """The record of the grant the human just approved under `ident`, ready for the store.

    The proof raises when it does not hold. It reads the latest submitted answer, so it also raises when
    that answer belongs to another question than `ident`, or to a report of another project."""
    record, key = proved_report(runtime, payload, root, ident)
    if not record["grant"]:
        raise ValueError("the report carries no grant.")
    return {"id": ident, "projectKey": key, "root": root, "grant": record["grant"],
            "approvedAt": approved_at or utc_stamp(), "session": payload.get("session_id"), "host": runtime}


def proved_confirmation(runtime, payload, root, ident, approved_at=None):
    """The record of the confirmations the human just approved under `ident`, ready for the store: each item
    unused. The proof is the grant's (proved_report); it raises when it does not hold."""
    record, key = proved_report(runtime, payload, root, ident)
    if not record["confirm"]:
        raise ValueError("the report carries no confirmation.")
    return {"id": ident, "projectKey": key, "root": root,
            "items": [dict({"resource": item["resource"], "action": item["action"], "used": None},
                           **{key: item[key] for key in ("digest", "schemaDigest", "approve") if key in item})
                      for item in record["confirm"]],
            "approvedAt": approved_at or utc_stamp(), "session": payload.get("session_id"), "host": runtime}


def proved_report(runtime, payload, root, ident):
    """(report record, project key) of the report the latest submitted answer approved, when that is `ident` and it
    was prepared in the project rooted at `root`; ValueError otherwise."""
    record = approved_report(runtime, payload, tuple(ident.split("-")) if isinstance(ident, str) else None)
    key = project_key(root)
    if "R-" + record["id"] != ident:
        raise ValueError("the latest submitted answer is for another question.")
    if not key or record["projectKey"] != key:
        raise ValueError("the report was prepared in another project.")
    return record, key


def store_grant(body):
    """Write one grant record, once: `<store>/<project key>/grants/R-<id>.json`. False when the record is
    there already (it is never rewritten); OSError when the store cannot take it.

    The record appears whole or not at all: a private temporary file beside it is linked to its name, and
    the link fails when the name is taken. A file at that name that is no grant record (an empty one that
    an interrupted write left) is replaced. Later stages keep their use log under `uses/`, beside
    `grants/`; nothing is created there now."""
    return store_once(body, "grants", read_grant)


def store_once(body, kind, reader):
    """Write `body` once as `<store>/<project key>/<kind>/<id>.json` (store_grant says how); False when a record
    that `reader` accepts is there already."""
    path = os.path.join(grant_store(), body["projectKey"], kind, body["id"] + ".json")
    if reader(path, body["id"]):
        return False
    directory = grant_store()
    for part in (None, body["projectKey"], kind):
        directory = os.path.join(directory, part) if part else directory
        private_directory(directory)
    scratch = "{}.{}.{}.tmp".format(path, os.getpid(), os.urandom(4).hex())
    fd = os.open(scratch, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        try:
            os.write(fd, (review_json(body) + "\n").encode("ascii"))
        finally:
            os.close(fd)
        try:
            os.link(scratch, path)
        except FileExistsError:
            if reader(path, body["id"]):
                return False  # another gate process recorded the same approval a moment ago
            os.replace(scratch, path)
        return True
    finally:
        try:
            os.unlink(scratch)
        except OSError:
            pass  # the replacement above took it


def confirmation_file(key, ident):
    """Where the store keeps the record of one report's confirmations: `<store>/<project key>/confirmations/<R-id>.json`."""
    return os.path.join(grant_store(), key, "confirmations", ident + ".json")


def read_confirmation(path, ident):
    """The confirmation record in `path`, or None unless it parses as one that carries `ident`: items of a resource,
    an action, and `used` (null, or when it was used)."""
    try:
        with open(path, encoding="utf-8") as fh:
            record = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(record, dict) or record.get("id") != ident:
        return None
    items = record.get("items")
    if not isinstance(items, list) or not items or not all(
            isinstance(item, dict) and isinstance(item.get("resource"), str) and isinstance(item.get("action"), str)
            and (item.get("used") is None or isinstance(item.get("used"), str))
            and all(key not in item or HEX64.fullmatch(str(item[key])) for key in ("digest", "schemaDigest"))
            and ("approve" not in item or type(item["approve"]) is bool) for item in items):
        return None
    return record


def store_confirmation(body):
    """Write one report's confirmation record, once, like a grant's (store_grant): False when it is there already.
    A record whose items were used is never rewritten by a later recording."""
    return store_once(body, "confirmations", read_confirmation)


def confirmation_items(project_root, report_id, resource):
    """[(path, index, item)] for every unused item naming `resource` in the confirmation record the human approved
    under `report_id` in the project rooted at `project_root` (its ledger root, as a grant record keeps it), in the
    record's order. An item holds its resource, action (an ssh resource's exact command), `used`, and for a
    service `digest` (its prompt's SHA-256 hex), `schemaDigest` when a schema was confirmed and `approve`.
    ValueError says why there is none. A Git review's G- ID is never a confirmation, and a grant never stands in for
    one."""
    if not isinstance(report_id, str) or not report_id.startswith("R-") or not PREPARED_ID.fullmatch(report_id):
        raise ValueError("a confirmation is named by its decision report's ID: R- and 16 hexadecimal characters.")
    key = project_key(os.path.realpath(project_root)) if project_root else None
    if not key:
        raise ValueError("a confirmation belongs to a DDL project.")
    path = confirmation_file(key, report_id)
    record = read_confirmation(path, report_id)
    if record is None or record.get("projectKey") != key:
        raise ValueError("{} is no confirmation the human approved in this project.".format(report_id))
    named = [(index, item) for index, item in enumerate(record["items"]) if item["resource"] == resource]
    if not named:
        raise ValueError("the confirmation {} does not name {}.".format(report_id, resource))
    unused = [(path, index, dict(item)) for index, item in named if item["used"] is None]
    if not unused:
        raise ValueError("the confirmation {} for {} was used already.".format(report_id, resource))
    return unused


def confirmation_item(project_root, report_id, resource, with_item=False):
    """(path, index) of the first unused item naming `resource` (confirmation_items says which), and with
    `with_item` (path, index, item)."""
    path, index, item = confirmation_items(project_root, report_id, resource)[0]
    return (path, index, item) if with_item else (path, index)


def mark_confirmation_used(path, index):
    """Mark item `index` of the confirmation record at `path` used, now, before anything is sent; return the time.

    ValueError when that item was used already or the record is gone or changed. Under an exclusive lock beside the
    record (so two runs never both take one item), the record is rewritten whole: a private temporary file beside it
    replaces it by rename."""
    import fcntl
    ident = os.path.basename(path)[:-len(".json")] if path.endswith(".json") else None
    lock = os.open(path + ".lock", os.O_WRONLY | os.O_CREAT, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX)
        record = read_confirmation(path, ident) if ident else None
        if record is None or type(index) is not int or not 0 <= index < len(record["items"]):
            raise ValueError("there is no such confirmation item.")
        if record["items"][index]["used"] is not None:
            raise ValueError("this confirmation was used already.")
        record["items"][index]["used"] = stamp = utc_stamp()
        scratch = "{}.{}.{}.tmp".format(path, os.getpid(), os.urandom(4).hex())
        fd = os.open(scratch, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            try:
                os.write(fd, (review_json(record) + "\n").encode("ascii"))
                os.fsync(fd)
            finally:
                os.close(fd)
            os.replace(scratch, path)
        except BaseException:
            try:
                os.unlink(scratch)
            except OSError:
                pass
            raise
        return stamp
    finally:
        os.close(lock)  # which releases the lock


# --- shell allowlist --------------------------------------------------------------------------

def split_segments(cmd, ends=None):
    """Split a command on `&&`, `||`, `;`, `|`, `&` and newlines outside quotes.

    Returns (raw, masked) segment lists, or None when a quote is unbalanced. In the masked copy every
    quoted or escaped character is `x`, so later checks can look for operators without tracking quotes;
    indices line up with the raw segment. `ends`, when given, receives the separator that ended each
    segment (None for the last)."""
    raw, masked, cur_raw, cur_masked = [], [], [], []
    quote = None
    i, n = 0, len(cmd)

    def flush(separator=None):
        raw.append("".join(cur_raw))
        masked.append("".join(cur_masked))
        del cur_raw[:], cur_masked[:]
        if ends is not None:
            ends.append(separator)

    while i < n:
        ch = cmd[i]
        if quote:
            if ch == quote:
                quote = None
            elif ch == "\\" and quote == '"' and i + 1 < n:
                cur_raw.append(ch), cur_masked.append("x")
                i, ch = i + 1, cmd[i + 1]
            cur_raw.append(ch), cur_masked.append("x")
            i += 1
        elif ch in "'\"":
            quote = ch
            cur_raw.append(ch), cur_masked.append("x")
            i += 1
        elif ch == "\\" and i + 1 < n:
            cur_raw.extend(cmd[i:i + 2]), cur_masked.extend("xx")
            i += 2
        elif cmd[i:i + 2] in ("&&", "||"):
            flush(cmd[i:i + 2])
            i += 2
        elif ch in ";|\n" or (ch == "&" and not (cur_raw and cur_raw[-1] in "<>") and cmd[i + 1:i + 2] != ">"):
            flush(ch)  # a lone `&` backgrounds a segment; `>&`, `<&` and `&>` are redirects, not separators
            i += 1
        else:
            cur_raw.append(ch), cur_masked.append(ch)
            i += 1
    if quote:
        return None
    flush()
    return raw, masked


def redirects_are_harmless(raw, masked) -> bool:
    """Only `/dev/null` and `&N` (as in `2>&1`) may follow a `>` or `>>` outside quotes."""
    for m in REDIRECT.finditer(masked):
        j = m.end()
        while j < len(masked) and masked[j] in " \t":
            j += 1
        k = j
        while k < len(masked) and not masked[k].isspace():
            k += 1
        target = raw[j:k].strip("'\"")
        if target != "/dev/null" and not re.fullmatch(r"&\d+", target):
            return False
    return True


def strip_redirect_tokens(args):
    """Drop harmless redirect tokens so the per-program rules see only real arguments."""
    out, skip = [], False
    for a in args:
        if skip:
            skip = False
        elif REDIR_TOKEN.match(a):
            skip = a.endswith((">", "<"))  # a bare operator: the next token is its target
        else:
            out.append(a)
    return out


def literal_shell(text) -> bool:
    """Recognize the small shell subset we inspect, never evaluate expansions.

    Single-quoted patterns may contain shell metacharacters. Double quotes still expand `$`,
    so they do not turn a dynamic command into a statically checkable one. An unquoted word that starts
    with `=` is refused, as is `==`: zsh's equals expansion turns `=name` into the path of a command.
    """
    quote, i = None, 0
    while i < len(text):
        ch = text[i]
        if ch == "\\" and quote != "'":
            i += 2
            continue
        if quote:
            if ch == quote:
                quote = None
            elif quote == '"' and ch in "$`":
                return False
        elif ch in "'\"":
            quote = ch
        elif ch in "$`*?(){}~" or text[i:i + 2] in ("<<", "<(", ">("):
            return False
        elif ch == "=" and (i == 0 or text[i - 1] in " \t\n;&|<>="):
            return False  # zsh expands `=name` (and, with MAGIC_EQUAL_SUBST, `x==name`) to a command's path
        elif ch == "[" and (not (i == 0 or text[i - 1].isspace()) or
                            text[i + 1:i + 2] not in (" ", "\t")):
            return False
        i += 1
    return quote is None


def option_operands(args, flags=(), values=(), shorts="", short_values="", numbers=False):
    """Return operands for an explicit option vocabulary; None means unsupported syntax.

    This is intentionally not a utility's full grammar. Unknown options cannot acquire new
    execution/write behavior unnoticed when a utility is upgraded.
    """
    operands, i = [], 0
    flags, values = set(flags), set(values)
    while i < len(args):
        arg = args[i]
        if arg == "--":
            return operands + args[i + 1:]
        if arg.startswith("--"):
            key, equal, value = arg.partition("=")
            if key in flags and not equal:
                pass
            elif key in values:
                if not equal:
                    i += 1
                    if i >= len(args) or args[i].startswith("-"):
                        return None
                elif not value:
                    return None
            else:
                return None
        elif arg.startswith("-") and arg != "-":
            if numbers and re.fullmatch(r"-\d+", arg):
                i += 1
                continue
            for pos, flag in enumerate(arg[1:], 1):
                if flag in short_values:
                    if pos == len(arg) - 1:
                        i += 1
                        if i >= len(args) or args[i].startswith("-"):
                            return None
                    break
                if flag not in shorts:
                    return None
        else:
            operands.append(arg)
        i += 1
    return operands


def git_command(args):
    """(subcommand index, harmless globals). None index means opaque/missing subcommand."""
    i, harmless = 0, True
    while i < len(args):
        arg = args[i]
        if arg in ("--version", "--help", "--exec-path", "--html-path", "--man-path", "--info-path"):
            return i, harmless
        if arg in ("--no-pager", "-P", "--no-optional-locks", "--literal-pathspecs", "--no-replace-objects"):
            i += 1
        elif arg in ("-C", "-c", "--git-dir", "--work-tree", "--namespace"):
            if i + 1 >= len(args):
                return None, False
            if arg == "-c" and args[i + 1] not in SAFE_GIT_CONFIG:
                harmless = False
            i += 2
        elif arg.startswith(("-C", "-c")) and len(arg) > 2:
            if arg.startswith("-c") and arg[2:] not in SAFE_GIT_CONFIG:
                harmless = False
            i += 1
        elif arg.startswith(("--git-dir=", "--work-tree=", "--namespace=", "--config-env=", "--exec-path=")):
            harmless = harmless and not arg.startswith(("--config-env=", "--exec-path="))
            i += 1
        elif arg.startswith("-"):
            return None, False
        else:
            return i, harmless
    return None, harmless


def git_is_read_only(args) -> bool:
    index, harmless = git_command(args)
    if index is None or not harmless or args[index] not in GIT_READ_ONLY:
        return False
    sub, rest = args[index], args[index + 1:]
    if sub == "branch":
        operands = option_operands(rest, flags={"--all", "--remotes", "--show-current", "--list", "--verbose",
                                               "--no-color"}, values={"--format", "--sort", "--contains", "--merged",
                                                                     "--no-merged"}, shorts="arv")
        return operands is not None and (not operands or "--list" in rest)
    flags = {"--short", "--branch", "--porcelain", "--oneline", "--stat", "--numstat", "--name-only",
             "--name-status", "--summary", "--patch", "--raw", "--no-patch", "--no-color", "--no-renames",
             "--cached", "--staged", "--exit-code", "--quiet", "--no-ext-diff", "--no-textconv", "--relative",
             "--all", "--reverse", "--topo-order", "--date-order", "--first-parent", "--merges", "--no-merges",
             "--graph", "--decorate", "--follow", "--abbrev-commit", "--show-toplevel", "--show-prefix",
             "--show-cdup", "--is-inside-work-tree", "--verify", "--symbolic-full-name", "--abbrev-ref",
             "--others", "--exclude-standard", "--deleted", "--modified", "--full-name", "--error-unmatch",
             "--line-porcelain", "--ignore-space-change", "--ignore-all-space", "--ignore-case", "--fixed-strings",
             "--extended-regexp", "--files-with-matches", "--line-number", "--invert-match"}
    values = {"--format", "--pretty", "--date", "--since", "--until", "--after", "--before", "--author",
              "--committer", "--grep", "--max-count", "--skip", "--max-depth", "--unified", "--diff-filter",
              "--color", "--porcelain", "--decorate", "--abbrev", "--find-renames", "--find-copies", "--exclude"}
    return option_operands(rest, flags, values, shorts="psbuwaAzfinlvEFrq", short_values="nLSGCe", numbers=True) is not None


# Only mixed-capability utilities need option profiles. Pure readers still receive literal
# arguments, so a quoted pattern stays a pattern rather than becoming shell source.
PROFILES = {
    "ls": ("all almost-all long human-readable directory recursive inode size classify color", "color sort time", "aAlhdtRrSsiF1", ""),
    "rg": ("files hidden no-ignore no-ignore-vcs count count-matches files-with-matches files-without-match line-number no-line-number ignore-case smart-case case-sensitive fixed-strings word-regexp line-regexp invert-match only-matching quiet pretty no-heading heading with-filename no-filename multiline multiline-dotall dotall text null null-data follow stats sort-files", "glob iglob type type-not type-add max-count max-depth context before-context after-context encoding color colors sort sortr threads regexp file", "nNilicHhFwevqosUuatzPL", "gTtmABCjef"),
    "grep": ("recursive dereference-recursive line-number ignore-case invert-match count files-with-matches files-without-match fixed-strings extended-regexp only-matching quiet no-messages with-filename no-filename word-regexp line-regexp text null", "regexp file max-count after-context before-context context include exclude exclude-dir binary-files", "rRnNiclvLEFoqsHhwxaz", "efmABC"),
    "sort": ("numeric-sort general-numeric-sort human-numeric-sort reverse unique stable check ignore-case dictionary-order ignore-leading-blanks zero-terminated version-sort", "key field-separator buffer-size parallel batch-size", "nghruscbdfzV", "ktS"),
    "uniq": ("count repeated unique ignore-case zero-terminated", "skip-fields skip-chars check-chars", "cduiz", "fsw"),
    "file": ("brief mime mime-type mime-encoding dereference no-dereference separator keep-going", "magic-file separator", "bihkLNz", "mF"),
    "jq": ("raw-output compact-output null-input slurp exit-status monochrome-output color-output sort-keys raw-input join-output tab stream ascii-output", "arg argjson slurpfile rawfile indent", "rcnseMCSRja", ""),
}


def program_is_read_only(prog, args) -> bool:
    """Accept bounded display forms instead of looking for known-dangerous fragments."""
    if prog == "sed":
        return (len(args) >= 2 and args[0] == "-n" and
                re.fullmatch(r"(?:\d+|\$)(?:,(?:\d+|\$))?p", args[1]) is not None and
                all(not arg.startswith("-") or arg == "-" for arg in args[2:]))
    if prog == "find":
        values = {"-name", "-iname", "-path", "-ipath", "-type", "-size", "-mtime", "-mmin", "-newer",
                  "-maxdepth", "-mindepth", "-regex"}
        flags = {"-print", "-print0", "-empty", "-type", "-o", "-a", "-not", "!"}
        i = 0
        while i < len(args):
            if args[i] in values:
                i += 1
                if i >= len(args):
                    return False
            elif args[i].startswith("-") and args[i] not in flags:
                return False
            i += 1
        return True
    if prog == "date":
        return not args or len(args) == 1 and (args[0].startswith("+") or args[0] in ("-u", "--utc", "--iso-8601"))
    if prog in ("codex", "claude"):
        return args == ["--version"]
    if prog == "printf":
        form = args[1:] if args[:1] == ["--"] else args
        # zsh's numeric conversions can evaluate array subscripts, even in quoted operands.
        return bool(form) and not form[0].startswith("-") and re.fullmatch(
            r"(?:[^%]|%%|%s)*", form[0]) is not None
    if prog in ("test", "["):
        if prog == "[":
            if not args or args[-1] != "]":
                return False
            args = args[:-1]
        # File/string predicates do not invoke shell arithmetic (unlike zsh test -v/-eq).
        return (len(args) <= 1 or
                len(args) == 2 and args[0] in ("-f", "-d", "-e", "-r", "-w", "-x", "-s", "-L", "-h", "-n", "-z") or
                len(args) == 3 and args[1] in ("=", "!=", "=="))
    if prog == "git":
        return git_is_read_only(args)
    profile = PROFILES.get("grep" if prog in ("egrep", "fgrep") else prog)
    if profile:
        flags, values, shorts, short_values = profile
        operands = option_operands(args, {"--" + x for x in flags.split()}, {"--" + x for x in values.split()},
                                   shorts, short_values)
        return operands is not None and (prog != "uniq" or len(operands) <= 1)
    return prog in READ_ONLY_PROGRAMS


def shell_is_read_only(cmd) -> tuple[bool, str]:
    """(True, "") when every segment of the command only reads; else (False, the offending segment)."""
    if not isinstance(cmd, str):
        return False, repr(cmd)
    if not literal_shell(cmd):
        return False, cmd.strip()
    parts = split_segments(cmd)
    if parts is None:
        return False, cmd.strip()
    for raw, masked in zip(*parts):
        if raw.strip() and not segment_is_read_only(raw, masked):
            return False, raw.strip()
    return True, ""


def network_redirect(raw, masked) -> bool:
    """True when a redirect of the segment opens /dev/tcp/… or /dev/udp/…, which the shell turns into a socket
    (as an argument the name is an ordinary missing file)."""
    for m in re.finditer(r"[<>]", masked):
        word = raw[m.end():].lstrip(" \t&<>").split()
        if word and re.match(r"""['"]?/dev/(?:tcp|udp)/""", word[0]):
            return True
    return False


def segment_is_read_only(raw, masked) -> bool:
    """One segment of a literal command (split_segments) that only reads."""
    if not redirects_are_harmless(raw, masked) or network_redirect(raw, masked):
        return False
    try:
        tokens = shlex.split(raw)
    except ValueError:
        return False
    while tokens and os.path.basename(tokens[0]) == "env":
        tokens.pop(0)
    if tokens and (ASSIGNMENT.match(tokens[0]) or tokens[0].startswith("-")):
        return False  # environment overrides can install execution helpers
    if not tokens:
        return True
    prog = os.path.basename(tokens[0])
    return prog in READ_ONLY_PROGRAMS and program_is_read_only(prog, strip_redirect_tokens(tokens[1:]))


def shell_command(tool_input) -> str | None:
    """The command text of a shell tool call, or None when the input carries none.

    Codex's `shell` tool sends argv; its usual shape is ["bash", "-lc", "<script>"], which is unwrapped
    to the script so the allowlist judges what actually runs."""
    if isinstance(tool_input, str):
        try:
            tool_input = json.loads(tool_input)
        except ValueError:
            return None
    if not isinstance(tool_input, dict):
        return None
    cmd = tool_input.get("command", tool_input.get("cmd"))
    if isinstance(cmd, list) and all(isinstance(a, str) for a in cmd):
        if len(cmd) == 3 and os.path.basename(cmd[0]) in ("bash", "sh", "zsh", "dash") \
                and re.fullmatch(r"-[a-z]*c[a-z]*", cmd[1]):
            return cmd[2]
        return shlex.join(cmd)
    return cmd if isinstance(cmd, str) else None


def is_mutating(runtime, tool_name, tool_input) -> tuple[bool, str]:
    """(True, offending shell segment or "") when the call may change state; unknown tools count as mutating."""
    if tool_name in SAFE_TOOLS.get(runtime, set()):
        return False, ""
    if runtime == "codex" and isinstance(tool_input, dict):
        fields = {"write_stdin": {"session_id", "chars", "max_output_tokens", "yield_time_ms"},
                  "wait": {"ids", "timeout_ms", "cell_id", "max_tokens", "yield_time_ms", "terminate"},
                  "wait_agent": {"timeout_ms"}}
        if tool_name in fields and set(tool_input) <= fields[tool_name]:
            if tool_name == "write_stdin":
                return (tool_input.get("chars", "") != ""), ""
            return (tool_input.get("terminate", False) is not False), ""
    if tool_name in SHELL_TOOLS.get(runtime, set()):
        cmd = shell_command(tool_input)
        if cmd is None:
            return True, ""
        ok, segment = shell_is_read_only(cmd)
        return (not ok), segment
    return True, ""


def gate_path_tokens():
    """The spellings of this gate's path that its own preparation call may use: the launcher's, as it was run
    (beside this file when this module was not loaded through it), and this module's own."""
    tokens, entry = set(), ENTRY or os.path.join(os.path.dirname(os.path.abspath(__file__)), "ddl_gate.py")
    paths = {".codex/hooks/ddl_gate.py"} | {form(path) for path in (entry, __file__)
                                             for form in (os.path.realpath, os.path.abspath)}
    for path in paths:
        tokens |= {path, '"' + path + '"', "'" + path + "'"}
    for var, homes in (("HOME", (".claude", ".codex")), ("CLAUDE_PROJECT_DIR", (".claude",))):
        for home in homes:
            rest = "/" + home + "/hooks/ddl_gate.py"
            for ref in ("$" + var, "${" + var + "}"):
                tokens |= {ref + rest, '"' + ref + rest + '"', '"' + ref + '"' + rest}
    return tokens


def is_gate_preparation(command) -> bool:
    """Exactly `python3 [-I] <gate> prepare-report|prepare-git-review --runtime <rt> <<'DELIM'` with the
    JSON in a quoted here-document and nothing else: no pipe, redirect, list, or further command.

    Rebuilding a report after compaction or a clarification is part of presenting it, so this call stays
    available while the STOP is pending. The quoted delimiter keeps the body free of expansions."""
    if not isinstance(command, str):
        return False
    head, newline, body = command.partition("\n")
    match = PREPARE_HEAD.fullmatch(head) if newline else None
    if not match or match[1] not in gate_path_tokens():
        return False
    lines = body.split("\n")
    if lines[-1] == "":
        lines.pop()  # the newline that ends the terminator line
    # Any earlier line that the shell could read as the terminator would run the lines after it.
    return bool(lines) and lines[-1] == match[3] and all(line.strip() != match[3] for line in lines[:-1])


def gate_preparation(runtime, payload) -> bool:
    return payload.get("tool_name") in SHELL_TOOLS.get(runtime, set()) and \
        is_gate_preparation(shell_command(payload.get("tool_input")))


def native_linear_shell(command, parts) -> bool:
    """The conservative subset a host's approval policy can inspect as individual argv lists."""
    if not literal_shell(command):
        return False
    quote, i = None, 0
    while i < len(command):
        ch = command[i]
        if ch == "\\" and quote != "'":
            i += 2
            continue
        if quote:
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
        elif ch in "<>":
            return False
        elif ch == "&":
            if command[i:i + 2] != "&&":
                return False
            i += 1
        i += 1
    for raw in parts[0]:
        try:
            tokens = shlex.split(raw)
        except ValueError:
            return False
        if tokens and ASSIGNMENT.match(tokens[0]):
            return False
    return True


def push_form_problem(command, nested=False, depth=0) -> bool:
    """Reject static Git push forms that neither the Git review nor Codex's approval policy reads as one plain
    `git push` argv list (wrappers, assignments, global options, compound or dynamic shell).

    This is a command-form guard, not a shell interpreter. Opaque programs, aliases and scripts
    are outside its coverage. An absolute host Git path keeps native executable resolution.
    """
    if not isinstance(command, str) or depth > 2:
        return False
    parts = split_segments(command)
    if parts is None:
        return False
    # The native shell splitter does not split expansions, redirections or background jobs.
    native_linear = native_linear_shell(command, parts)
    for raw in parts[0]:
        try:
            tokens = shlex.split(raw)
        except ValueError:
            continue
        if not tokens:
            continue
        wrapped = nested
        while tokens and ASSIGNMENT.match(tokens[0]):
            wrapped = True
            tokens.pop(0)
        if not tokens:
            continue
        while tokens and os.path.basename(tokens[0]) in ("env", "command", "builtin", "exec"):
            wrapped = True
            tokens.pop(0)
            while tokens and (ASSIGNMENT.match(tokens[0]) or tokens[0] in ("--", "-i", "-p")):
                tokens.pop(0)
        if not tokens:
            continue
        prog = os.path.basename(tokens[0])
        if prog in ("bash", "sh", "zsh", "dash") and len(tokens) == 3 and re.fullmatch(r"-[a-z]*c[a-z]*", tokens[1]):
            if push_form_problem(tokens[2], nested=True, depth=depth + 1):
                return True
            continue
        if prog != "git":
            continue
        index, _ = git_command(tokens[1:])
        if index is None:
            # A dynamic or unknown Git subcommand cannot be read as a plain push.
            return True
        sub = tokens[index + 1]
        if any(ch in sub for ch in "$`*?[{"):
            return True
        host_git = tokens[0] == "git" or os.path.isabs(tokens[0])
        if sub == "push" and (wrapped or not host_git or index != 0 or not native_linear):
            return True
    return False


def push_guard(runtime, payload):
    # These explicit harness modes waive immediate confirmation, never the STOP contract.
    if runtime != "codex" or payload.get("permission_mode") in ("bypassPermissions", "dontAsk"):
        return None
    if payload.get("tool_name") not in SHELL_TOOLS["codex"]:
        return None
    if push_form_problem(shell_command(payload.get("tool_input"))):
        return deny(PUSH_FORM_REASON)
    return None


def permission(decision, reason):
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": decision,
                                   "permissionDecisionReason": reason}}


def deny(reason):
    return permission("deny", reason)


def verdict(decision):
    """The permissionDecision of a PreToolUse decision, or None."""
    out = decision.get("hookSpecificOutput") if isinstance(decision, dict) else None
    return out.get("permissionDecision") if isinstance(out, dict) else None


# --- the grant's answers ----------------------------------------------------------------------
# With a grant active (recorded, not expired) and no STOP pending, the gate answers for the calls it can
# classify: an edit inside the grant's paths, a read, a granted command class with literal arguments. It
# denies a path, class or machine outside every active grant and an exit behind ssh, and leaves every other
# call to the host. Without an active grant it answers as before, except that only the gate writes the ledger.

def project_root(decision):
    """The resolved top of the work tree the call runs in: the directory holding `.git` (a linked work tree's
    own), else the directory of the instruction file that carries the marker. Grant paths are relative to it."""
    top = None
    for top in instruction_directories(decision["cwd"]):
        pass
    if top and os.path.exists(os.path.join(top, ".git")):
        return os.path.realpath(top)
    source = decision["source"]
    name = max((n for n in INSTRUCTION_FILES if source.endswith(os.sep + n)), key=len)
    return os.path.realpath(source[:-len(name) - 1])


def active_grants(project):
    """The project's grant records whose expiry lies ahead, oldest approval first; none when the store is
    missing. A record is active only when its grant still passes the preparation's checks, expiry included."""
    if not os.path.isdir(grant_store()):
        return []
    key, now, records = project_key(ledger_root(project)), time.time(), []
    for record in grant_records(key):
        try:
            if record.get("projectKey") == key and validated_grant(record["grant"], now):
                records.append(record)
        except (ValueError, TypeError, KeyError, AttributeError):
            pass  # a record no preparation would have written answers for nothing
    return records


def relative_parts(path, root):
    """The segments of `path` below `root` (both resolved), or None when it lies outside."""
    rel = os.path.relpath(path, root)
    if rel == os.curdir:
        return []
    parts = rel.split(os.sep)
    return None if parts[0] == os.pardir or os.path.isabs(rel) else parts


def inside(path, roots):
    return any(relative_parts(path, root) is not None for root in roots)


def folds_case(root):
    """True when the file system at `root` ignores the case of names (the macOS default), read from the root
    itself; when that cannot be told, True, so that a protected name is never missed for its spelling."""
    head, name = os.path.split(root)
    variant = os.path.join(head, name.swapcase()) if name.swapcase() != name else None
    try:
        return os.path.samefile(root, variant) if variant else True
    except OSError:
        return False


class Place:
    """Where one call looks: the project root, whether its file system ignores case, the temporary
    directories, and the notebook the guidance names (as root-relative, case-compared parts)."""

    def __init__(self, project, root):
        self.project, self.root, self.folds = project, root, folds_case(root)
        self.dirs = {self.fold(name) for name in PROTECTED_DIRS}
        self.files = {self.fold(name) for name in PROTECTED_FILES}
        self.pairs = {tuple(self.fold(name) for name in pair) for pair in PROTECTED_PAIRS}
        self._notebook = self._temporary = False  # read on first use: most calls need neither

    @property
    def notebook(self):
        if self._notebook is False:
            parts = self.locate(os.path.realpath(notebook_path(self.project, self.root)))
            self._notebook = parts[1] if parts[0] is not None else None
        return self._notebook

    @property
    def temporary(self):
        if self._temporary is False:
            self._temporary = unique(os.path.realpath(path) for path in (os.environ.get("TMPDIR"), "/tmp") if path)
        return self._temporary

    def fold(self, name):
        return name.casefold() if self.folds else name

    def locate(self, path):
        """(parts, compared parts) of a resolved path below the root, or (None, None) outside it. Where the file
        system ignores case, the compared parts are case-folded and decide what lies inside and what is
        protected; the parts keep their spelling for a grant's globs."""
        if not self.folds:
            parts = relative_parts(path, self.root)
            return parts, parts
        folded = relative_parts(path.casefold(), self.root.casefold())
        if folded is None:
            return None, None
        return (path.split(os.sep)[-len(folded):] if folded else []), folded

    def protected(self, compared):
        """True for a path no grant covers: in an adapter directory, the ledger directory or a Git directory, an
        instruction file, or the notebook."""
        if any(name in self.dirs for name in compared) or (compared and compared[-1] in self.files) or \
                any(tuple(compared[i:i + 2]) in self.pairs for i in range(len(compared) - 1)):
            return True
        return in_git_directory(self.root, compared, self.fold) or compared == self.notebook

    def usable(self, path):
        """True for a resolved directory or file inside the root and not protected."""
        compared = self.locate(path)[1]
        return compared is not None and not self.protected(compared)


def in_git_directory(root, parts, fold=lambda name: name):
    """True when `parts` (below `root`) lie in a Git directory: `.git`, `<name>.git`, or one holding HEAD and
    objects. A grant's glob never reaches there, not even `**`."""
    for i, name in enumerate(parts):
        if name == fold(".git") or (i < len(parts) - 1 and name.endswith(fold(".git"))):
            return True
        if i < len(parts) - 1:
            prefix = os.path.join(root, *parts[:i + 1])
            if os.path.isfile(os.path.join(prefix, "HEAD")) and os.path.isdir(os.path.join(prefix, "objects")):
                return True
    return False


def segment_glob(glob, name):
    """One path segment against one glob segment: `*` and `?` stay within the segment, the rest is literal."""
    pattern = "".join("[^/]*" if c == "*" else "[^/]" if c == "?" else re.escape(c) for c in glob)
    return re.fullmatch(pattern, name) is not None


def glob_matches(glob, parts):
    """A grant path glob against a root-relative path: `**` matches any number of whole segments."""
    pattern = glob.split("/")

    def match(i, j):
        if i == len(pattern):
            return j == len(parts)
        if pattern[i] == "**":
            return any(match(i + 1, k) for k in range(j, len(parts) + 1))
        return j < len(parts) and segment_glob(pattern[i], parts[j]) and match(i + 1, j + 1)
    return match(0, 0)


def tool_inputs(payload):
    inputs = payload.get("tool_input")
    if isinstance(inputs, str):
        try:
            inputs = json.loads(inputs)
        except ValueError:
            inputs = None
    return inputs if isinstance(inputs, dict) else {}


def call_cwd(payload):
    """The working directory a tool call runs in: the shell's `workdir` or `cwd` when it names one."""
    inputs = tool_inputs(payload)
    named = inputs.get("workdir") or inputs.get("cwd")
    cwd = payload.get("cwd") or os.getcwd()
    return os.path.join(cwd, named) if isinstance(named, str) and named else cwd


def standard_shell(path):
    """True for bash, sh, zsh or dash by name or from a system directory: what runs a command line."""
    return isinstance(path, str) and os.path.basename(path) in SHELLS and \
        (path in SHELLS or os.path.dirname(path) in SHELL_HOMES)


def ordinary_shell(payload):
    """False when the call runs its command through anything but a standard shell: Codex's `shell` field, or an
    argv `[<shell>, -c, <script>]` whose shell is not one."""
    inputs = tool_inputs(payload)
    if "shell" in inputs and not standard_shell(inputs["shell"]):
        return False
    argv = inputs.get("command", inputs.get("cmd"))
    return not (isinstance(argv, list) and len(argv) == 3 and argv and isinstance(argv[0], str)
                and os.path.basename(argv[0]) in SHELLS and not standard_shell(argv[0]))


def edit_targets(runtime, payload):
    """(paths, deletes) an editing call writes, the paths as given; None when the call is no edit. An edit
    whose target cannot be read gives no paths, and is left to the host."""
    tool, data = payload.get("tool_name"), payload.get("tool_input")
    if runtime == "claude" and tool in EDIT_KEYS:
        path = data.get(EDIT_KEYS[tool]) if isinstance(data, dict) else None
        return ([path] if isinstance(path, str) and path else []), False
    if runtime == "codex" and tool == "apply_patch":
        text = data if isinstance(data, str) else next(
            (data[key] for key in ("patch", "input", "command") if isinstance(data, dict) and isinstance(data.get(key), str)),
            "")
        found = PATCH_TARGET.findall(text)
        return [path for _, path in found if path], any(kind == "Delete File" for kind, _ in found)
    return None


def ledger_file(path, ledger, folds=False):
    """True when the resolved `path` is the ledger's event log or a Run's record below the ledger root."""
    fold = str.casefold if folds else str
    if not ledger or fold(os.sep + LEDGER + os.sep) not in fold(path + os.sep):
        return False
    parts = relative_parts(fold(path), fold(ledger))
    return bool(parts) and parts[0] == LEDGER and (parts[1:] == ["events.jsonl"] or (
        len(parts) == 4 and parts[1] == "runs" and parts[3] == "run.json"))


def shell_write_targets(command):
    """The paths a shell command visibly writes: redirect targets (`>`, `>>`, `>|`, `<>`), and the operands of
    the writers it calls (LEDGER_WRITERS, `sed -i`, `dd of=`). A bounded reading of literal text, not a shell."""
    parts = split_segments(command.replace(">|", "> ")) if isinstance(command, str) else None
    targets = []
    for raw, masked in zip(*parts) if parts else ():
        for m in re.finditer(r">>?", masked):
            word = raw[m.end():].lstrip().split()
            if word:
                targets.append(word[0].strip("'\""))
        try:
            tokens = strip_redirect_tokens(shlex.split(raw))
        except ValueError:
            continue
        while tokens and (ASSIGNMENT.match(tokens[0]) or os.path.basename(tokens[0]) in ("env", "sudo", "command")):
            tokens.pop(0)
        if not tokens:
            continue
        prog, operands = os.path.basename(tokens[0]), [t for t in tokens[1:] if not t.startswith("-")]
        if prog in LEDGER_WRITERS and operands:
            targets += operands[LEDGER_WRITERS[prog]:] if LEDGER_WRITERS[prog] else operands
        elif prog in ("sed", "perl") and any(t.startswith("-i") for t in tokens[1:]):
            targets += operands
        elif prog == "dd":
            targets += [t[3:] for t in tokens[1:] if t.startswith("of=")]
    return targets


def ledger_guard(runtime, payload, project):
    """A deny for an edit or a recognized shell write of `.ddl/events.jsonl` or `.ddl/runs/*/run.json` (in any
    case where the file system ignores it): in a DDL project only the gate writes the ledger, grant or not."""
    edit, cwd = edit_targets(runtime, payload), call_cwd(payload)
    if edit is not None:
        paths = edit[0]
    elif payload.get("tool_name") in SHELL_TOOLS.get(runtime, set()):
        command = shell_command(payload.get("tool_input"))
        paths = shell_write_targets(command) if isinstance(command, str) and LEDGER in command.casefold() else []
    else:
        return None
    resolved = [os.path.realpath(os.path.join(cwd, path)) for path in paths]
    hits = [path for path in resolved if os.sep + LEDGER + os.sep in (path + os.sep).casefold()]
    ledger = ledger_root(project) if hits else None
    folds = folds_case(ledger) if ledger else False
    hit = next((path for path in hits if ledger_file(path, ledger, folds)), None)
    return deny(LEDGER_REASON.format(os.path.relpath(hit, ledger))) if hit else None


def exit_word(text):
    """The first exit the text names (git's recording and branch-moving verbs, forge clients, publishing,
    transfers, an upload or a non-GET method), read word by word whatever the quoting; None when it names none."""
    words = re.findall(r"[^\s;&|()<>`'\"]+", text)
    names = []
    for word in words:  # `git-push` and `/usr/lib/git-core/git-push` read as `git push`
        name = word.rsplit("/", 1)[-1]
        names += ["git", name[4:]] if name.startswith("git-") else [name]
    for name in names:
        if name in TRANSFERS:
            return name
    if "aws" in names and ("s3api" in names or "s3" in names and set(names) & AWS_TRANSFERS):
        return "aws s3api" if "s3api" in names else "aws s3 " + sorted(set(names) & AWS_TRANSFERS)[0]
    if "gsutil" in names and set(names) & GSUTIL_TRANSFERS:
        return "gsutil " + sorted(set(names) & GSUTIL_TRANSFERS)[0]
    if "http.server" in names:  # `python3 -m http.server` serves the files to the network
        return "http.server"
    if "git" in names:
        for name in names:
            if name in GIT_EXITS or set(names) & GIT_EXIT_FLAGS.get(name, set()):
                return "git " + name
    for program, verb in (("npm", "publish"), ("twine", "upload")):
        if program in names and verb in names:
            return program + " " + verb
    if "curl" in names or "wget" in names:
        for i, word in enumerate(words):
            flag, equal, value = word.partition("=")
            if flag in UPLOAD_FLAGS or (not word.startswith("--") and word.startswith("-")
                                        and set(word[1:]) & set("TdF") and not word.startswith("-X")):
                return "upload " + word
            method = value if equal else (words[i + 1] if i + 1 < len(words) else "")
            if flag in METHOD_FLAGS and method.upper() != "GET" or word.startswith("-X") and len(word) > 2 \
                    and word[2:].upper() != "GET":
                return "method " + word
    return None


def notebook_path(project, root):
    """The notebook the guidance names: the instruction file's `@<file>` import under its Notebook heading
    (resolved from that file), else the root's design.md."""
    source, section = project.get("source"), False
    try:
        with open(source, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if line.startswith("## "):
                    section = line.strip() == "## Notebook"
                elif section and re.fullmatch(r"@(\S+)\s*", line):
                    return os.path.join(os.path.dirname(source), line.strip()[1:])
    except (OSError, TypeError):
        pass
    return os.path.join(root, "design.md")


def command_lines(text):
    """A command compared with the notebook's: the whitespace inside each line collapsed, blank lines dropped,
    the line breaks kept (a newline ends a command, a space does not)."""
    return "\n".join(" ".join(line.split()) for line in text.splitlines() if line.strip())


def validation_commands(project, root):
    """The commands of the notebook's `## Validation` code blocks (command_lines): each is the lines between a
    `# V…` comment and the next comment or the block's end."""
    commands, section, block, current = set(), False, False, None

    def flush():
        text = command_lines("\n".join(current or []))
        if text:
            commands.add(text)
    try:
        with open(notebook_path(project, root), encoding="utf-8", errors="replace") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return commands
    for line in lines:
        if not block and line.startswith("## "):
            section = line.strip() == "## Validation"
        elif section and line.lstrip().startswith("```"):
            if block:
                flush()
            block, current = not block, None
        elif section and block:
            if line.lstrip().startswith("#"):
                flush()
                current = [] if re.match(r"#\s*V\S", line.lstrip()) else None
            elif current is not None:
                current.append(line)
    return commands


def gate_spellings():
    """{quoted spelling: the path it names} for the quoted `$HOME` and `$CLAUDE_PROJECT_DIR` spellings of an
    installed gate, which a command may use literally; the variables are read from this process."""
    spelled = {}
    for var, homes in (("HOME", (".claude", ".codex")), ("CLAUDE_PROJECT_DIR", (".claude",))):
        value = os.path.expanduser("~") if var == "HOME" else os.environ.get(var)
        for home in homes:
            rest = "/" + home + "/hooks/ddl_gate.py"
            for ref in ("$" + var, "${" + var + "}"):
                for spelling in ('"' + ref + rest + '"', '"' + ref + '"' + rest):
                    spelled[spelling] = (value + rest) if value else None
    return spelled


def gate_files():
    """The resolved files a command may run as this gate: the launcher as it was run (beside this module when it
    was not), this module, and the launchers installed under $HOME. A project file of that name is not one."""
    home, entry = os.path.expanduser("~"), ENTRY or os.path.join(os.path.dirname(os.path.abspath(__file__)), "ddl_gate.py")
    return {os.path.realpath(path) for path in (entry, __file__, os.path.join(home, ".claude", "hooks", "ddl_gate.py"),
                                                os.path.join(home, ".codex", "hooks", "ddl_gate.py"))}


def heredoc_head(command):
    """The first line of `<head> <<'DELIM'` (quoted, so the body is data) when the body ends at DELIM and no
    earlier line could end it; else None."""
    head, newline, body = command.partition("\n")
    match = re.fullmatch(r"(.*?)[ \t]*<<[ \t]*(['\"])([A-Za-z_][A-Za-z0-9_]*)\2[ \t]*", head) if newline else None
    if not match:
        return None
    lines = body.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    if not lines or lines[-1] != match[3] or any(line.strip() == match[3] for line in lines[:-1]):
        return None
    return match[1]


def piped(raw, ends, k):
    """True when segment `k` reads a pipe (or follows `&`): the separators before it, looked up past empty
    segments, since the shell continues `|` across a newline."""
    j = k - 1
    while j >= 0:
        if ends[j] in ("|", "&"):
            return True
        if raw[j].strip():
            return False
        j -= 1
    return False


def option_words(args, options, operands=True):
    """(operands, values, directories) of `args` when every option is one `options` (flags, {value option:
    pattern}) names; a value is the next word or `=value`, never one that starts with `-`; the directories are
    the values that must be directories inside the root. None when anything else appears (an operand too,
    without `operands`)."""
    flags, values = options
    found, given, directories, i = [], [], [], 0
    while i < len(args):
        arg = args[i]
        name, equal, value = arg.partition("=")
        if arg in flags:
            i += 1
            continue
        if name in values and (equal or i + 1 < len(args)):
            if not equal:
                i += 1
                value = args[i]
            pattern = values[name]
            if value.startswith("-") or pattern not in ("", "dir") and not re.fullmatch(pattern, value):
                return None
            (directories if pattern == "dir" else given).append(value)
        elif arg.startswith(("-", "+")) or not operands:
            return None
        else:
            found.append(arg)
        i += 1
    return found, given, directories


def segment_class(tokens, is_gate):
    """The class form of one segment (the protocol's Run Formats), with only the options its allow-list names:
    (classes, words, paths inside the root, guarded, modules). `words` (a script's arguments, option values)
    may name paths inside the root or a temporary directory; the paths (a script, test files and directories,
    packages) stay inside the root; `modules` are unittest names, which must be modules inside the root;
    `guarded` says no word may name a protected file. ("gate", …) for a gate subcommand that needs no class;
    None for anything else, which is the host's."""
    prog, args = tokens[0], tokens[1:]
    if PYTHON.fullmatch(prog):
        i = 0
        while i < len(args) and PYTHON_FLAGS.fullmatch(args[i]):
            i += 1
        rest = args[i + 1:]
        if args[i:i + 1] == ["-m"] and rest and rest[0] == "pytest":
            return pytest_form(rest[1:])
        if args[i:i + 1] == ["-m"] and rest and rest[0] == "unittest":
            if rest[1:2] == ["discover"]:
                found = option_words(rest[2:], DISCOVER_OPTIONS)
                return found and (("test",), found[1], found[0] + found[2], True, [])
            found = option_words(rest[1:], UNITTEST_OPTIONS)
            if found is None:
                return None
            files = [name for name in found[0] if "/" in name or name.endswith(".py")]
            return ("test",), found[1], files, True, [name for name in found[0] if name not in files]
        if i >= len(args) or args[i].startswith("-"):
            return None
        script = args[i]
        if is_gate(script):
            word = rest[0] if rest else None
            if word == "snapshot":
                found = option_words(rest[1:], (set(), {"--run": "", "--item": "", "--git-dir": "dir",
                                                         "--work-tree": "dir"}), operands=False)
                return found and (("snapshot",), [], found[2], False, [])
            return ("gate", [], [], False, []) if word in GATE_WORDS else None
        name = script.rsplit("/", 1)[-1]
        kind = ("build" if name == "build.py" else "check" if name.startswith("check_") and name.endswith(".py")
                else "test" if name.endswith(".py") and (name.startswith("test_") or name.endswith("_test.py"))
                else None)
        return ((kind,), rest, [script], True, []) if kind else None
    if prog == "pytest":
        return pytest_form(args)
    if prog == "make":
        targets, i = [], 0
        while i < len(args):
            jobs = args[i + 1] if args[i] == "-j" and i + 1 < len(args) else args[i][2:] if args[i].startswith("-j") else None
            if jobs is not None:
                if not (re.fullmatch(NUMBER, jobs) and 1 <= int(jobs) <= MAKE_JOBS):
                    return None
                i += 2 if args[i] == "-j" else 1
                continue
            if args[i] not in MAKE_TARGETS:
                return None
            targets.append(MAKE_TARGETS[args[i]])
            i += 1
        return tuple(unique(targets or ["build"])), [], [], True, []
    if tokens == ["npm", "run", "build"]:
        return ("build",), [], [], True, []
    if tokens == ["npm", "test"]:
        return ("test",), [], [], True, []
    if prog == "cargo" and args[:1] in (["build"], ["test"]):
        rest = args[1:]
        cut = rest.index("--") if "--" in rest else len(rest)
        filters = rest[cut + 1:]  # test-name filters after `--`
        found = option_words(rest[:cut], CARGO_OPTIONS, operands=False)
        if found is None or any(word.startswith(("-", "+")) for word in filters):
            return None
        return (args[0],), found[1] + filters, [], True, []
    if prog == "go" and args[:1] in (["build"], ["test"]):
        found = option_words(args[1:], GO_OPTIONS)
        # Packages only as relative paths: `all` or an import path could reach code outside the project.
        if found is None or any(not (package == "." or package.startswith("./")) for package in found[0]):
            return None
        return (args[0],), found[1], found[0], True, []
    if prog == "bash" and args[:1] == ["-n"] and len(args) > 1:
        if any(a.startswith(("-", "+")) for a in args[1:]):
            return None
        return ("check",), [], args[1:], True, []
    if prog == "git" and args[:2] == ["diff", "--check"]:
        found = option_words(args[2:], ({"--"}, {}))
        return found and (("check",), found[0], [], True, [])
    return None


def pytest_form(args):
    """`pytest` or `python3 -m pytest` with its allow-listed options; its test files and directories (before
    any `::`) stay inside the root."""
    found = option_words(args, PYTEST_OPTIONS)
    return found and (("test",), found[1], [operand.split("::")[0] for operand in found[0]], True, [])


def module_inside(name, cwds, place):
    """True when the dotted unittest name starts with a module or package inside the root (a file `<a/b>.py` or a
    directory `<a/b>`, resolved, not protected) from every working directory; a name the root lacks would be
    imported from elsewhere on the path."""
    parts = name.split(".")
    if not all(parts):
        return False
    for where in cwds:
        for k in range(len(parts), 0, -1):
            base = os.path.join(where, *parts[:k])
            path = base + ".py" if os.path.isfile(base + ".py") else base if os.path.isdir(base) else None
            if path:
                if not place.usable(os.path.realpath(path)):
                    return False
                break
        else:
            return False
    return True


def ssh_form(tokens):
    """(machine, remote command words) of `ssh [-T] [-n] [-o BatchMode=yes] [-o ConnectTimeout=<n>] <machine>
    <command>`, or None for any other ssh call: an interactive login has no command, and a word after the
    machine that starts with `-` is an option OpenSSH would still read."""
    i = 1
    while i < len(tokens) and tokens[i].startswith("-"):
        if tokens[i] in ("-T", "-n", "-Tn", "-nT"):
            i += 1
        elif tokens[i] == "-o" and i + 1 < len(tokens) and SSH_OPTION.fullmatch(tokens[i + 1]):
            i += 2
        elif tokens[i].startswith("-o") and SSH_OPTION.fullmatch(tokens[i][2:]):
            i += 1
        else:
            return None
    if i + 1 >= len(tokens) or tokens[i + 1].startswith("-"):
        return None
    return tokens[i], tokens[i + 1:]


def ssh_resource(machine, grants, found):
    """How the active grants meet `ssh <machine>`, given the resource table as read_resource_table `found` it:
    "covered", "host" (the host's own decision), or the reason of a deny.

    Without a table a granted machine is its own ssh alias. With one, the ssh alias must be the `reach =
    ssh:<alias>` of a granted compute resource; a resource's name is accepted only where it equals that alias.
    A resource with `confirm` is never covered: the host's confirmation shows the command. A `codex:` service is
    never reached by ssh. A table that cannot be read covers nothing and refuses nothing."""
    table, problem = found
    granted = {name for record in grants for name in record["grant"]["machines"]}
    outside = OUTSIDE_MACHINE.format(machine, ", ".join(record["id"] for record in grants))
    if problem:
        return "host"
    if not table:
        return "covered" if machine in granted else outside
    held = [name for name, entry in table.items() if entry.get("reach") == "ssh:" + machine]
    entry = table.get(machine)
    shared = [other for other in table.values() if entry is not None and other.get("reach") == entry.get("reach")]
    if any("confirm" in table[name] for name in held) or any("confirm" in other for other in shared):
        return "host"  # a resource that asks each run, by its alias or its name, or one that shares its reach
    if any(name in granted and "compute" in table[name]["roles"] for name in held):
        return "covered"
    if entry is not None and str(entry.get("reach")).startswith("codex:"):
        return SERVICE_BY_SSH.format(machine)
    if entry is not None and machine in granted:
        return NAME_FOR_ALIAS.format(machine) if entry.get("reach") != "ssh:" + machine else NOT_COMPUTE.format(machine)
    return outside


def subcommand_options(args, values, flags=(), lists=()):
    """{option: value} of a gate subcommand's options when each word is a flag of `flags`, an option of `values`
    ({option: pattern}) given once with its value (the next word or `=value`), or an option of `lists` followed by
    one or more values (it may repeat); a value never starts with `-`. None for anything else."""
    found, i = {}, 0
    while i < len(args):
        name, equal, value = args[i].partition("=")
        if args[i] in flags and args[i] not in found:
            found[args[i]] = True
        elif name in values and name not in found and (equal or i + 1 < len(args)):
            if not equal:
                i += 1
                value = args[i]
            if value.startswith("-") or not re.fullmatch(values[name], value):
                return None
            found[name] = value
        elif name in lists:
            given = found.setdefault(name, [])
            before = len(given)
            if equal:
                given.append(value)
            while not equal and i + 1 < len(args) and not args[i + 1].startswith("-"):
                i += 1
                given.append(args[i])
            if len(given) == before or any(item.startswith("-") or not item for item in given[before:]):
                return None
        else:
            return None
        i += 1
    return found


def resource_use(tokens, is_gate):
    """(word, resource, remote command words, local files) of the gate's `remote`, `measure` or `service` in the
    forms tools/ddl_run.py reads, False for one of those words in any other form, None for anything else:
      remote <machine> [--snapshot REF] [--run N-ID] [--item ID] [--artifacts GLOB…] [--keep] [--timeout N] -- <command>
      measure <machine>
      service <name> --prompt-file FILE [--schema FILE]
    An artifact glob is relative to the remote work tree; the command is literal words (REMOTE_WORD). Any other
    option (`--confirmed` after the host's confirmation of a resource that asks each run, `--approve`) is False:
    the host's."""
    if not PYTHON.fullmatch(tokens[0]):
        return None
    i = 1
    while i < len(tokens) and PYTHON_FLAGS.fullmatch(tokens[i]):
        i += 1
    if i + 1 >= len(tokens) or tokens[i + 1] not in RESOURCE_WORDS or tokens[i].startswith("-") or not is_gate(tokens[i]):
        return None
    word, args = tokens[i + 1], tokens[i + 2:]
    if not args or not table_word("alias", args[0]):
        return False
    name, args = args[0], args[1:]
    if word == "measure":
        return (word, name, [], []) if not args else False
    if word == "service":
        found = subcommand_options(args, {"--prompt-file": r"[^\n]+", "--schema": r"[^\n]+"})
        if found is None or "--prompt-file" not in found:
            return False
        return word, name, [], [found[key] for key in ("--prompt-file", "--schema") if key in found]
    cut = args.index("--") if "--" in args else len(args)
    found, command = subcommand_options(args[:cut], REMOTE_VALUES, {"--keep"}, {"--artifacts"}), args[cut + 1:]
    if found is None or not command or not all(REMOTE_WORD.fullmatch(w) for w in command) or not all(
            ARTIFACT_GLOB.fullmatch(glob) and ".." not in glob.split("/") for glob in found.get("--artifacts", [])):
        return False
    return word, name, command, []


def resource_covered(word, name, grants, found):
    """True when an active grant names the resource of `remote`, `measure` or `service` and hands over `code`, and
    the table, as read_resource_table `found` it, lets a grant cover it: a compute resource that takes `code`,
    reached by ssh for the first two and by codex for `service`, with neither it nor a resource sharing its reach
    asking each run. Without a table a granted machine is its own ssh alias and no service exists; a table that
    cannot be read covers nothing."""
    table, problem = found
    if problem or not any(name in record["grant"]["machines"] and "code" in record["grant"]["handover"]
                          for record in grants):
        return False
    if not table:
        return word != "service"
    entry = table.get(name)
    if entry is None or "compute" not in entry["roles"] or "code" not in entry.get("data", []):
        return False
    reach = str(entry.get("reach"))
    if any("confirm" in other for other in table.values() if other.get("reach") == reach):
        return False  # the resource itself, or one that the same alias or plugin reaches, asks each run
    return reach.startswith("codex:" if word == "service" else "ssh:")


def named(word):
    """What a word may name as a path: itself, or for an option its value (`--opt=value`, `-ovalue`)."""
    if not word.startswith("-"):
        return [word]
    if "=" in word:
        return [word.partition("=")[2]]
    return [word[2:]] if not word.startswith("--") and len(word) > 2 else []


def path_word(token):
    """The path a class form's word names, or None: a word with `/`, `.` or `..`, or an option's value."""
    if token.startswith("-"):
        value = token.partition("=")[2] if "=" in token else token[2:] if not token.startswith("--") else ""
        return value if "/" in value else None
    return token if "/" in token or token in (os.curdir, os.pardir) else None


def granting(grants, kind):
    """The ID of the oldest active grant that names the command class `kind`, or None."""
    return next((record["id"] for record in grants if kind in record["grant"]["commands"]), None)


def allowed(note, ids, kinds):
    """The allow for a call inside the active grants `ids`, noted for the ledger (`allowed`, its kind)."""
    ids, kind = unique(ids), ",".join(unique(kinds))
    note["allowed"] = {"kind": kind, "id": ids[0], "grants": ids if len(ids) > 1 else None}
    return permission("allow", GRANT_ALLOW.format(", ".join(ids), kind.replace(",", ", ")))


def refused(note, rule, grants, reason):
    note.update(rule=rule, id=grants[0]["id"])
    return deny(reason)


def edit_grant(paths, deletes, cwd, place, grants, note):
    """An edit inside every target's grant path is allowed; one inside the root but outside every path is
    denied. One outside the root or in a protected place, a deletion, and any edit from a working directory
    outside the root are the host's."""
    names = ", ".join(record["id"] for record in grants)
    ids, miss, host = [], None, not paths or deletes or not place.usable(os.path.realpath(cwd))
    for path in paths:
        parts, compared = place.locate(os.path.realpath(os.path.join(cwd, path)))
        if parts is None or not parts or place.protected(compared):
            host = True
            continue
        note.setdefault("touched", []).append(os.path.realpath(os.path.join(cwd, path)))  # for a held question
        hit = next((record["id"] for record in grants
                    if any(glob_matches(glob, parts) for glob in record["grant"]["paths"])), None)
        if hit is None:
            miss = miss or "/".join(parts)
        ids.append(hit)
    if miss:
        return refused(note, "grant-paths", grants, OUTSIDE_PATHS.format(miss, names))
    return None if host else allowed(note, ids, ["edit"])


def shell_grant(command, cwd, place, grants, note, held=False):
    """The grant's answer to a shell command (the protocol's Run Operation step 1 and Formats), or None.

    `note` also gets `touched`, the compared parts of every path inside the root its class forms name, and
    `untouched` when a form names what no path shows (a unittest module). `held` (a question holds items) skips
    the validation commands' exact-text answer, so that what the command names is known."""
    if not isinstance(command, str) or not command.strip():
        return None
    names, root = ", ".join(record["id"] for record in grants), place.root
    if shell_is_read_only(command)[0]:
        return allowed(note, [grants[0]["id"]], ["read"])
    if not place.usable(os.path.realpath(cwd)):
        return None  # a command class, a gate subcommand: only from a working directory inside the root
    check = granting(grants, "check")
    if check and not held and command_lines(command) in validation_commands(place.project, root) \
            and not exit_word(command):
        return allowed(note, [check], ["check"])  # the human approved that exact text, `$` and subshells included
    spelled, files = gate_spellings(), []
    head = heredoc_head(command)
    text, stand_ins = head if head is not None else command, {}
    for i, (spelling, path) in enumerate(sorted(spelled.items(), key=lambda item: -len(item[0]))):
        if spelling in text:
            stand_ins["/ddl-gate-spelled/{}".format(i)] = path
            text = text.replace(spelling, "/ddl-gate-spelled/{}".format(i))
    ends = []
    parts = split_segments(text, ends) if literal_shell(text) else None
    if not parts:
        return None
    cwds, kinds, ids, host, segments, table = [cwd], [], [], False, 0, []

    def resources():
        """The resource table, read once per call and only when a segment reaches a resource."""
        if not table:
            table.append(read_resource_table())
        return table[0]

    def resolved(word):
        """The real paths `word` names from every working directory a segment may run in."""
        if word in stand_ins:
            return [os.path.realpath(stand_ins[word])] if stand_ins[word] else [None]
        return [os.path.realpath(os.path.join(where, word)) for where in cwds]

    def is_gate(word):
        if not files:
            files.append(gate_files())
        return all(path in files[0] for path in resolved(word))

    for k, (raw_segment, masked) in enumerate(zip(*parts)):
        if not raw_segment.strip():
            continue
        segments += 1
        try:
            tokens = strip_redirect_tokens(shlex.split(raw_segment))
        except ValueError:
            return None
        if not redirects_are_harmless(raw_segment, masked) or network_redirect(raw_segment, masked) or not tokens:
            host = True
            continue
        if tokens[0] == "cd":
            # Later segments may run in any directory seen so far (`cd` in a pipe changes nothing after it), so
            # each path is checked from all of them.
            moved = resolved(tokens[1]) if len(tokens) == 2 and not tokens[1].startswith("-") else []
            if not moved or not all(path and place.usable(path) for path in moved):
                host = True
            cwds = unique(cwds + [path for path in moved if path])
            continue
        if tokens[0] == "ssh":
            form = ssh_form(tokens)
            if form is None or SSH_SYNTAX.search(raw_segment) or piped(parts[0], ends, k):
                # An option after the machine, a remote command that is not literal words, or input that the
                # remote shell would run: ssh must start its pipeline and read no redirect.
                host = True
                continue
            machine, remote = form
            reach = ssh_resource(machine, grants, resources())
            if reach not in ("covered", "host"):
                return refused(note, "grant-machine", grants, reach)
            word = exit_word(" ".join(remote))
            if word:
                return refused(note, "ssh-exit", grants, EXIT_BEHIND_SSH.format(word))
            if reach == "host":
                host = True
                continue
            classes = ("remote-run",)
        elif segment_is_read_only(raw_segment, masked):
            continue
        else:
            use = resource_use(tokens, is_gate)
            if use is not None:
                # The gate's remote, measure and service: class remote-run for the resource they name, allowed when
                # an active grant covers it and the class; anything else, in any form, is the host's. No input
                # reaches them, the command `remote` runs is literal words without an exit, and a file `service`
                # hands over lies inside the root (not protected) or a temporary directory.
                word = use and exit_word(" ".join(use[2]))
                if word:
                    return refused(note, "ssh-exit", grants, EXIT_BEHIND_SSH.format(word))
                hit = granting(grants, "remote-run")
                if not use or not hit or "<" in masked or piped(parts[0], ends, k) \
                        or not resource_covered(use[0], use[1], grants, resources()):
                    host = True
                    continue
                for path in (path for name in use[3] for path in resolved(name)):
                    compared = place.locate(path)[1] if path else None
                    if path is None or (place.protected(compared) if compared is not None
                                        else not inside(path, place.temporary)):
                        host = True
                kinds.append("remote-run")
                ids.append(hit)
                continue
            form = segment_class(tokens, is_gate)
            if not form:
                host = True
                continue
            classes, words, strict, guarded, modules = form
            if not all(module_inside(name, cwds, place) for name in modules):
                host = True
            if modules:
                note["untouched"] = True
            if classes == "gate":
                kinds.append("gate")
                ids.append(grants[0]["id"])
                continue
            # A word that names a path stays inside the root (or a temporary directory); a script, a checked
            # file or a directory stays inside the root; no word names a protected file, whatever its shape.
            checks = [(path_word(w), True) for w in words if path_word(w)] + [(w, False) for w in strict] + \
                [(name, True) for w in words for name in named(w)
                 if name and any(os.path.lexists(os.path.join(where, name)) for where in cwds)]
            for word, temporary in checks:
                for path in resolved(word):
                    if path is None or not (place.locate(path)[0] is not None or
                                            temporary and inside(path, place.temporary)):
                        host = True
            if held:
                # Beside a hold, every word the form names may be a path (an output file, a directory), from every
                # working directory a segment may run in; `...` names its directory and all below it.
                operands = [name for w in words for name in named(w) if name] + list(strict)
                note.setdefault("touched", []).extend(
                    path for word in operands for path in resolved(word[:-3] or "." if word.endswith("...") else word)
                    if path)
                note["named"] = note.get("named", 0) + len(operands)
                note["cwds"] = list(cwds)
            if guarded:
                for word in [name for w in words for name in named(w)] + strict:
                    if word and any(path is None or place.locate(path)[1] is not None and
                                    place.protected(place.locate(path)[1]) for path in resolved(word)):
                        host = True
        for kind in classes:
            hit = granting(grants, kind)
            if hit is None:
                return refused(note, "grant-class", grants, OUTSIDE_CLASS.format(kind, names))
            kinds.append(kind)
            ids.append(hit)
    if host or not kinds or (head is not None and (segments != 1 or kinds != ["gate"] and kinds != ["snapshot"])):
        return None
    return allowed(note, ids, kinds)


def grant_decision(runtime, payload, project, note, held=False):
    """The active grants' answer to a call while no STOP is pending (or beside a held question, `held`): an allow,
    a deny, or None (the host's)."""
    edit = edit_targets(runtime, payload)
    shell = payload.get("tool_name") in SHELL_TOOLS.get(runtime, set())
    if edit is None and not shell or shell and not ordinary_shell(payload):
        return None
    grants = active_grants(project)
    if not grants:
        return None
    cwd, place = call_cwd(payload), Place(project, project_root(project))
    if edit is not None:
        return edit_grant(edit[0], edit[1], cwd, place, grants, note)
    return shell_grant(shell_command(payload.get("tool_input")), cwd, place, grants, note, held)


# --- events -----------------------------------------------------------------------------------

def record_scan(runtime, payload):
    """(state, pending) from the conversation record; (None, None) when it is missing or unreadable."""
    path = payload.get("transcript_path")
    if not isinstance(path, str) or not path:
        return None, None
    return scan_codex(path) if runtime == "codex" else scan_claude(path)


def record_state(runtime, payload) -> bool | None:
    return record_scan(runtime, payload)[0]


def pending_scan(runtime, payload):
    """Combine record and marker into (state, pending). Codex: its record format is unstable, so a marker
    is trusted even over an OPEN record. Claude: the record is authoritative whenever it is readable."""
    state, pending = record_scan(runtime, payload)
    marker = marker_path(payload.get("session_id")).exists()
    if runtime == "codex":
        state = True if (state is True or marker) else state
    else:
        state = True if (state is None and marker) else state
    return state, (pending if state is True else None)


def question_texts(runtime, request):
    """The text of every question in a native request (Claude `question`, Codex `title`), in order."""
    if isinstance(request, str):
        try:
            request = json.loads(request)
        except ValueError:
            return []
    questions = request.get("questions") if isinstance(request, dict) else None
    key = "question" if runtime == "claude" else "title"
    return [q.get(key) if isinstance(q, dict) and isinstance(q.get(key), str) else None
            for q in questions] if isinstance(questions, list) else []


def pending_signals(runtime, path):
    """The prepared IDs that keep the STOP pending in the record, since the last human input, as a set of
    (kind, hex); None when anything else keeps it pending too (an ID this state directory did not prepare, a
    question without one, a +++DDL_REPORT that no asked prepared question follows) or the record cannot be read.
    Every question of a batch counts. A +++DDL_REPORT before an asked prepared question (the Approval operation
    writes the report, then asks) belongs to that question."""
    stats, found, asked = {"lines": 0, "parsed": 0}, set(), False  # walking back: `asked` is later in the turn
    try:
        for entry in iter_entries_reversed(path, stats):
            if runtime == "claude":
                if entry.get("isSidechain"):
                    continue
                if is_human_prompt_claude(entry):
                    break
                idents, question = [], False
                if entry.get("type") == "assistant":
                    for block in entry_blocks(entry):
                        if block.get("type") == "tool_use" and block.get("name") in QUESTION_TOOLS["claude"]:
                            idents += [question_id(text) for text in question_texts("claude", block.get("input"))]
                    question = bool(idents)
                    closes = question or has_report(claude_text(entry))
                else:
                    closes, ident = claude_pending_signal(entry)
                    idents = [ident] if ident else []
            else:
                payload = entry.get("payload")
                if not isinstance(payload, dict):
                    continue
                kind, ptype = entry.get("type"), payload.get("type")
                if kind == "event_msg" and ptype == "task_started":
                    break
                if kind == "event_msg" and ptype == "item_completed":
                    item = payload.get("item")
                    if isinstance(item, dict) and item.get("type") == "UserMessage":
                        break
                    continue
                if kind == "response_item" and ptype == "function_call" and payload.get("name") in QUESTION_TOOLS["codex"]:
                    idents = [question_id(text) for text in question_texts("codex", payload.get("arguments"))]
                    question = closes = bool(idents)
                else:
                    closes, ident = codex_pending_signal(kind, ptype, payload)
                    idents, question = [ident] if ident else [], False
            if not closes:
                continue
            if not idents:
                if not asked:
                    return None  # a report that no asked prepared question follows: a total stop
                continue
            if not all(ident and known_preparation(ident) for ident in idents):
                return None
            found.update(idents)
            asked = asked or question
    except OSError:
        return None
    return found or None


def held_scope(runtime, payload, project):
    """{"ids", "globs"} while every question that keeps the STOP pending names the items it holds: the pending IDs,
    and the owner globs (`files` of the Run's run.json) of those items and of every item that depends on one; None
    for a total stop (a question without `holds`, a Git review, a +++DDL_REPORT, a STOP only the marker shows)."""
    path = payload.get("transcript_path")
    if not isinstance(path, str) or not path:
        return None
    signals = pending_signals(runtime, path)  # None also when only the marker shows the STOP
    if not signals or any(kind != "R" for kind, _ in signals):
        return None
    root, held = ledger_root(project), {}
    try:
        for _, hexid in sorted(signals):
            holds = load_report(hexid, runtime).get("holds")
            if not holds:
                return None
            held.setdefault(holds["run"], set()).update(holds["items"])
        globs = set()
        for run_id, names in held.items():
            items = run_record(root, run_id)
            for name in held_closure(items, names):
                globs.update(items.get(name, {}).get("files", []))
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return None
    return {"ids": ["R-" + hexid for _, hexid in sorted(signals)], "globs": sorted(globs)}


def comparable(path, place):
    """A path as owner paths are compared: NFC, and without case where the file system ignores case."""
    import unicodedata
    return place.fold(unicodedata.normalize("NFC", path))


def owner_specs(root, globs, place):
    """(paths, patterns) of owner globs, resolved for comparing: each literal path, lexical and through its links;
    each glob's literal directory prefix, both ways, with the rest of the glob; and each existing match, resolved.
    A leading `./` and a trailing `/` are dropped; all in comparable form. Third, the (device, inode) of every
    existing owner file (the files of an owner directory included), so that a hard link to one is held too."""
    import glob as globbing
    import unicodedata
    paths, patterns = set(), set()
    for raw in globs:
        text = unicodedata.normalize("NFC", str(raw))
        while text.startswith("./"):
            text = text[2:]
        text = text.rstrip("/")
        segments = [segment for segment in text.split("/") if segment not in ("", ".")]
        cut = next((i for i, segment in enumerate(segments) if any(char in segment for char in "*?[")), len(segments))
        lexical = os.path.normpath(os.path.join(root, *segments[:cut]))
        bases = {lexical, os.path.realpath(lexical)}
        if cut == len(segments):
            paths.update(bases)
            continue
        rest = "/".join(segments[cut:])
        patterns.update((base, rest) for base in bases)
        for match in globbing.glob(os.path.join(globbing.escape(root), *segments), recursive=True)[:OWNER_MATCHES]:
            paths.add(os.path.realpath(match))
    inodes, counted = set(), 0
    for path in sorted(paths):
        for top, _, files in os.walk(path) if os.path.isdir(path) else [(os.path.dirname(path), [], [os.path.basename(path)])]:
            for name in files:
                counted += 1
                if counted > OWNER_MATCHES:
                    break
                try:
                    info = os.stat(os.path.join(top, name))
                except OSError:
                    continue
                inodes.add((info.st_dev, info.st_ino))
    return ({comparable(path, place) for path in paths},
            {(comparable(base, place), comparable(rest, place)) for base, rest in patterns}, inodes)


def held_target(path, specs, place, contains=True):
    """True when the resolved `path` is a held owner path, lies under one, matches a held glob below its prefix, or
    (`contains`: an operand that is a directory) holds one of them."""
    target, (paths, patterns, inodes) = comparable(path, place), specs
    try:
        info = os.stat(path)
        if (info.st_dev, info.st_ino) in inodes:
            return True  # a hard link to an owner file
    except OSError:
        pass
    for owner in paths:
        if target == owner or target.startswith(owner + os.sep) or contains and owner.startswith(target + os.sep):
            return True
    for base, rest in patterns:
        if target == base or contains and base.startswith(target + os.sep):
            return True
        if target.startswith(base + os.sep):
            parts = target[len(base) + 1:].split(os.sep)
            if any(glob_matches(rest, parts[:k]) for k in range(1, len(parts) + 1)) or contains and os.path.isdir(path):
                return True
    return False


def held_owner_globs(root, key, scope_globs):
    """The owner globs a call beside a hold must stay clear of: the held items' (and their dependents'), and those of
    every queued question that holds items and is not answered yet (a provisional one goes ahead instead)."""
    globs = set(scope_globs)
    for record in open_markers(key).values():
        if record.get("holds") and not record.get("provisional"):
            items = run_record(root, record["holds"]["run"])
            for name in held_closure(items, record["holds"]["items"]):
                globs.update(items.get(name, {}).get("files", []))
    return sorted(globs)


def held_answer(runtime, payload, project, note):
    """The allow for a call that may go on beside the held questions pending, or None (today's STOP denial).

    Only a call an active grant allows as an edit, a test or a check, that asks for nothing outside the sandbox, is
    no exit and no question, names at least one path, and whose every path operand, target and working directory
    stays clear of the held owners (resolved through links, NFC, without case where the file system ignores it).
    Any failure here is None: under a pending STOP an error never allows."""
    try:
        return held_allow(runtime, payload, project, note)
    except Exception:
        return None


def held_allow(runtime, payload, project, note):
    if escalated(payload) or payload.get("tool_name") in QUESTION_TOOLS.get(runtime, set()):
        return None
    scope = held_scope(runtime, payload, project)
    if scope is None:
        return None
    shell = payload.get("tool_name") in SHELL_TOOLS.get(runtime, set())
    if shell:
        command = shell_command(payload.get("tool_input"))
        if not isinstance(command, str) or visible_git_write(command) or exit_word(command):
            return None
    if ledger_guard(runtime, payload, project) is not None:
        return None
    scratch = {}
    answer = grant_decision(runtime, payload, project, scratch, held=True)
    allowed = scratch.get("allowed") or {}
    if verdict(answer) != "allow" or not set(str(allowed.get("kind")).split(",")) <= HELD_KINDS \
            or scratch.get("untouched") or shell and not scratch.get("named") or not scratch.get("touched"):
        return None
    root = ledger_root(project)
    place = Place(project, project_root(project))
    specs = owner_specs(place.root, held_owner_globs(root, project_key(root), scope["globs"]), place)
    if any(held_target(path, specs, place) for path in scratch["touched"]) \
            or any(held_target(cwd, specs, place, contains=False) for cwd in scratch.get("cwds", [])):
        return None
    note["allowed"], note["held"] = allowed, scope["ids"]
    return permission("allow", HELD_ALLOW.format(allowed["id"] if not allowed.get("grants") else
                                                 ", ".join(allowed["grants"]), allowed["kind"].replace(",", ", "),
                                                 ", ".join(scope["ids"])))


def pending_state(runtime, payload) -> bool | None:
    return pending_scan(runtime, payload)[0]


def question_guard(runtime, payload, state, pending, note):
    """Check a native question before the safe-tool shortcut.

    A question that carries an ID must equal the request prepared under that ID, in this state
    directory and after the session's last epoch. A question without an ID is an ordinary question,
    except while a STOP is pending: then only the prepared question may be asked. `note` receives what
    the ledger records: the ID a denial names, or the prepared question that passed (`asked`)."""
    if payload.get("tool_name") not in QUESTION_TOOLS.get(runtime, set()):
        return None
    request = payload.get("tool_input")
    if isinstance(request, str):
        try:
            request = json.loads(request)
        except ValueError:
            pass
    ident = question_id(asked_question(runtime, request))
    if ident is None:
        if state is not True:
            return None
        note.update(rule="question", id=pending["id"] if pending else None)
        return deny(ASK_UNCHANGED.format(pending["id"]) if pending else PREPARE_FIRST)
    kind, prepared_id = ident
    label = kind + "-" + prepared_id
    note.update(rule="question", id=label)
    if runtime == "claude" and kind == "R" and len(question_texts(runtime, request)) > 1 \
            and queued_preparation(ident):
        return batch_guard(runtime, payload, request, note)  # several queued questions in one call
    try:
        if kind == "R":
            record = load_report(prepared_id, runtime)
            expected = record["nativeRequest"]
        else:
            record, _ = load_git_review(prepared_id, runtime)
            expected = native_git_request(record)
        stale = predates_epoch(payload.get("session_id"), record["createdAt"])
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return deny(NOT_PREPARED.format(label))
    if stale:
        return deny(PREDATES.format(label))
    if request != expected:
        return deny((GIT_QUESTION_MISMATCH if kind == "G" else ASK_UNCHANGED).format(label))
    if kind == "R" and settled_replacement(label, record):
        return deny(SETTLED_REPLACEMENT.format(label, record["replaces"]))
    del note["rule"]
    note["asked"] = asked_entry(label, expected, record if kind == "R" else None)
    return None  # the prepared question; the host's own policy still applies


def settled_replacement(label, record):
    """True for a report that asks a queued question again (`replaces`) whose marker is gone: the question was
    answered meanwhile, so this asking would decide it a second time."""
    if not record.get("replaces"):
        return False
    try:
        markers = open_markers(record.get("projectKey"))
    except Exception:
        return True
    return not any(label in marker["ids"] for marker in markers.values())


def asked_entry(label, request, record):
    """What the session keeps of an asked question until its answer: its ID, its option labels, whether its first
    option records a grant or confirmations, and (only for one) that it is provisional."""
    entry = {"id": label, "options": option_labels(request), "grant": bool(record and record["grant"]),
             "confirm": bool(record and record["confirm"])}
    if record and record.get("provisional"):
        entry["provisional"] = True
    if record and record.get("queue"):
        entry["queued"] = True
    return entry


def batch_guard(runtime, payload, request, note):
    """Several prepared questions in one native call (Claude): 2 to 4, each the unchanged question of a report
    prepared with `queue: true`, all different, none older than the session's epoch. `note` gets them all as
    `asked`; anything else is denied, naming the first question that is not such a one."""
    low, high = BATCH_QUESTIONS
    questions = request.get("questions") if isinstance(request, dict) else None
    entries = []
    if not isinstance(request, dict) or set(request) != {"questions"} or not isinstance(questions, list) \
            or not low <= len(questions) <= high:
        return deny(BATCH_UNCHANGED.format(note["id"]))
    for question in questions:
        text = question.get("question") if isinstance(question, dict) else None
        ident = question_id(text) if isinstance(text, str) else None
        label = "-".join(ident) if ident else "?"
        if not ident or ident[0] != "R" or label in [entry["id"] for entry in entries]:
            return deny(BATCH_UNCHANGED.format(label))
        try:
            record = load_report(ident[1], runtime)
            stale = predates_epoch(payload.get("session_id"), record["createdAt"])
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            return deny(NOT_PREPARED.format(label))
        if stale:
            return deny(PREDATES.format(label))
        if record.get("queue") is not True or [question] != record["nativeRequest"]["questions"]:
            return deny(BATCH_UNCHANGED.format(label))
        if settled_replacement(label, record):
            return deny(SETTLED_REPLACEMENT.format(label, record["replaces"]))
        entries.append(asked_entry(label, {"questions": [question]}, record))
    del note["rule"]
    note["asked"] = entries
    return None


def asked_marker(session_id):
    """`<state dir>/<session>.asked`: the prepared questions this session asked and has not seen closed."""
    return os.path.join(state_base(), state_name(session_id) + ".asked")


def disarm(session_id):
    """Retire every armed question of the session."""
    try:
        os.unlink(asked_marker(session_id))
    except OSError:
        pass


def armed_questions(session_id):
    """The questions the marker holds, oldest first; none when it is missing or unreadable.

    Each is {id, options, grant, toolUseId} and, once Codex delivered its approving reply, `answered`. An
    older gate wrote the one question it kept as a bare object."""
    try:
        with open(asked_marker(session_id), encoding="utf-8") as fh:
            armed = json.load(fh)
    except (OSError, ValueError):
        return []
    armed = [armed] if isinstance(armed, dict) else armed if isinstance(armed, list) else []
    return [entry for entry in armed
            if isinstance(entry, dict) and isinstance(entry.get("id"), str) and PREPARED_ID.fullmatch(entry["id"])]


def arm(session_id, armed):
    """Make `armed` the session's armed questions. With none left the marker goes, and the next call costs
    one stat again."""
    if armed:
        write_whole(asked_marker(session_id), json.dumps(armed[-ARMED_LIMIT:]))
    else:
        disarm(session_id)


def claude_question_close(entry):
    """(label, timed out) for the Claude tool result that closes a question, or None when it carries neither a
    submitted answer nor an idle auto-resolution (a rejection, an empty answer, a non-user source)."""
    result = entry.get("toolUseResult")
    answers = result.get("answers") if isinstance(result, dict) else None
    if not isinstance(answers, dict):
        return None
    labels = [answer for answer in answers.values() if isinstance(answer, str) and answer.strip()]
    if result.get("afkTimeoutMs") is not None:  # the host resolved it after the idle wait
        return (labels[0] if len(labels) == 1 else None), True
    if len(answers) != 1 or len(labels) != 1 or not is_dialog_answer_claude(entry):
        return None
    return labels[0], False


def entry_blocks(entry):
    """The dict blocks of a Claude entry's message content."""
    message = entry.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    return [block for block in content if isinstance(block, dict)] if isinstance(content, list) else []


def armed_close_claude(path, ident):
    """How the latest question carrying `ident` was closed: {toolUseId, label, timeout, ts}; False when it
    closed without an answer; None while it is open or lies before the last typed prompt or compaction."""
    results = {}
    for entry in iter_entries_reversed(path, {"lines": 0, "parsed": 0}):
        if entry.get("isSidechain"):
            continue
        if entry.get("isCompactSummary"):
            return None
        blocks = entry_blocks(entry)
        if entry.get("type") == "user":
            refs = [block.get("tool_use_id") for block in blocks if block.get("type") == "tool_result"]
            for ref in refs:
                results.setdefault(ref, entry)
            if not refs and is_human_prompt_claude(entry):
                return None
        elif entry.get("type") == "assistant":
            for block in blocks:
                if block.get("type") != "tool_use" or block.get("name") not in QUESTION_TOOLS["claude"]:
                    continue
                texts = question_texts("claude", block.get("input"))
                batch = len(texts) > 1 and ident in [question_id(text) for text in texts if text]
                if batch or question_id(asked_question("claude", block.get("input"))) == ident:
                    result = results.get(block.get("id"))
                    if result is None:
                        return None
                    if batch:  # one of several questions: its own answer in the shared result
                        text = next(text for text in texts if text and question_id(text) == ident)
                        close = claude_batch_close(result, text)
                    else:
                        close = claude_question_close(result)
                    return {"toolUseId": block.get("id"), "label": close[0], "timeout": close[1],
                            "ts": result.get("timestamp")} if close else False
    return None


def claude_batch_close(entry, text):
    """(label, timed out) for one question `text` of a batch, from the tool result that closes the batch; None when
    the result carries no submitted answer to it (claude_question_close says the same of a single question)."""
    result = entry.get("toolUseResult")
    answers = result.get("answers") if isinstance(result, dict) else None
    if not isinstance(answers, dict):
        return None
    label = answers.get(text)
    label = label if isinstance(label, str) and label.strip() else None
    if result.get("afkTimeoutMs") is not None:
        return label, True
    if label is None or not is_dialog_answer_claude(entry):
        return None
    return label, False


def armed_close_codex(path, ident):
    """Same contract as armed_close_claude for a Codex rollout: the reply envelope to the question's call."""
    reply = stamp = None
    for entry in iter_entries_reversed(path, {"lines": 0, "parsed": 0}):
        payload = entry.get("payload")
        if entry.get("type") == "compacted":
            return None
        if not isinstance(payload, dict):
            continue
        kind, ptype, item = entry.get("type"), payload.get("type"), payload.get("item")
        if kind == "event_msg" and ptype == "item_completed" and isinstance(item, dict) and item.get("type") == "UserMessage":
            if reply is not None:
                return None
            reply, stamp = codex_git_reply(codex_text(item)), entry.get("timestamp")
            if not reply or question_id(reply[1]) != ident:
                return None  # typed text, or the reply to another question
        elif kind == "response_item" and ptype == "function_call" and payload.get("name") in QUESTION_TOOLS["codex"]:
            asked = asked_question("codex", payload.get("arguments"))
            if question_id(asked) != ident:
                continue
            if reply is None or reply[0] != payload.get("call_id"):
                return None
            if not isinstance(reply[1], str) or asked.replace("\r\n", "\n") != reply[1].replace("\r\n", "\n"):
                return False
            return {"toolUseId": reply[0], "label": reply[2], "timeout": False, "ts": stamp}
    return None


def note_answer(runtime, payload, root, armed, close):
    """The lines of one closed question: `answered`, unless Codex's reply was logged as it arrived, and for
    the approving answer of a grant either `granted` or a `warn` that names why no record follows; for one of
    confirmations, `confirmed` or such a `warn`.

    The warning's rule is `grant-proof` (`confirm-proof`) when the record does not prove the approval and
    `grant-store` (`confirm-store`) when the store could not take the record. Nothing is retried: the question
    is closed either way."""
    session, ident = payload.get("session_id"), armed["id"]
    labels, label, seconds = armed.get("options") or [], close["label"], iso_seconds(close["ts"])
    stamp = None if seconds is None else utc_stamp(seconds)  # the host's own time of the answer, when it wrote one
    choice = labels.index(label) if label in labels else None
    if not armed.get("answered"):
        ledger_event(root, runtime, session, "answered", ts=stamp, nulls=("choice",), id=ident,
                     toolUseId=close["toolUseId"], choice=choice, label=label if choice is not None else None,
                     timeout=close["timeout"])
    if (armed.get("provisional") or armed.get("queued")) and not close["timeout"] and not armed.get("answered"):
        settle_provisional(root, runtime, session, ident, choice, close["toolUseId"], stamp)  # once: Codex's reply did
    if choice != 0 or close["timeout"]:
        return
    for flag, prove, store, where, reader, done in (
            ("grant", proved_grant, store_grant, grant_file, read_grant, "granted"),
            ("confirm", proved_confirmation, store_confirmation, confirmation_file, read_confirmation, "confirmed")):
        if not armed.get(flag):
            continue
        rule = flag + "-proof"
        try:
            body = prove(runtime, payload, root, ident, stamp)
            rule = flag + "-store"
            written = store(body)
        except Exception:
            key = project_key(root)
            if not key or not reader(where(key, ident), ident):  # an earlier approval's record is no loss
                ledger_event(root, runtime, session, "warn", id=ident, rule=rule, toolUseId=close["toolUseId"])
            continue
        if written:
            ledger_event(root, runtime, session, done, id=ident, toolUseId=close["toolUseId"])


def settle_provisional(root, runtime, session, ident, choice, tool_use_id, ts=None):
    """The proven answer of a queued question, to any asking of it: its marker goes (one per original, whichever
    asking was answered). For a provisional one, its first option confirms what went ahead (`provisional-confirmed`)
    and any other answer overturns it (`provisional-overturned`, and the lead restores), one line per asking."""
    key = project_key(root)
    for original, record in open_markers(key).items():
        if ident not in record["ids"]:
            continue
        try:
            os.unlink(os.path.join(grant_store(), key, "queued", original + ".json"))
        except OSError:
            pass
        if record.get("provisional"):
            for name in record["ids"]:  # every asking of it is answered by this one
                ledger_event(root, runtime, session, "provisional-confirmed" if choice == 0 else "provisional-overturned",
                             ts=ts, id=name, toolUseId=tool_use_id, by=ident if name != ident else None)


def observe_answers(runtime, payload, root):
    """Close each armed question whose answer the record now holds: its `answered` line, and its grant
    record when the proof holds. It decides nothing, and it closes a question at most once.

    With nothing armed this is one stat. A question whose answer the record does not hold yet stays armed,
    also behind a question asked after it, until a typed prompt, a compaction or a resume retires them all."""
    session = payload.get("session_id")
    if not os.path.exists(asked_marker(session)):
        return
    find = armed_close_codex if runtime == "codex" else armed_close_claude
    armed = armed_questions(session)
    closes = [find(payload.get("transcript_path"), tuple(entry["id"].split("-"))) for entry in armed]
    if armed and all(close is None for close in closes):
        return
    # First, so that a failure below is never retried on every later call.
    arm(session, [entry for entry, close in zip(armed, closes) if close is None])
    for entry, close in zip(armed, closes):
        if close:
            try:
                note_answer(runtime, payload, root, entry, close)
            except Exception:
                pass  # one question's bookkeeping never costs the next one its lines


def tool_note(runtime, payload, project, decision, note):
    """The ledger's share of one tool call: its line, the asked question, and a grant to record.

    It runs after the decision is made and cannot change it. An ordinary call (nothing asked, nothing
    decided) writes nothing and costs at most the one stat for the asked question."""
    session = payload.get("session_id")
    decided = verdict(decision)
    passes = decided in (None, "allow")  # an allowed call keeps the bookkeeping of a call the gate let pass
    asked = note.get("asked") if passes else None
    # Look for the answers while the record is OPEN, and when a new question joins the asked ones. A call
    # that is denied or asked does not wait for that reading: the next call that passes looks.
    observe = passes and (note.get("state") is False or bool(asked)) \
        and os.path.exists(asked_marker(session))
    if not (observe or asked or decision):
        return
    root = ledger_root(project)
    call = {key: value if isinstance(value, str) else None
            for key, value in (("tool", payload.get("tool_name")), ("toolUseId", payload.get("tool_use_id")))}
    if observe:
        try:
            observe_answers(runtime, payload, root)
        except Exception:
            pass
    if decided in ("deny", "ask"):
        ledger_event(root, runtime, session, "denied" if decided == "deny" else "ask", id=note.get("id"),
                     rule=note.get("rule"), **call)
    elif decided == "allow":
        allowed_event(root, runtime, session, note, call)
        if note.get("commit"):
            ledger_event(root, runtime, session, "commit", **note["commit"], **call)
            remember_commit(payload, note)
    elif asked:
        entries = asked if isinstance(asked, list) else [asked]  # a batch asks several at once
        for entry in entries:
            ledger_event(root, runtime, session, "asked", id=entry["id"], **call)
        # Behind the questions that have not closed: a record that lags must not cost an earlier question its
        # answer. Asked again, a question takes its new call's place.
        ids = [entry["id"] for entry in entries]
        waiting = [entry for entry in armed_questions(session) if entry["id"] not in ids]
        arm(session, waiting + [dict(entry, toolUseId=call["toolUseId"]) for entry in entries])
    if isinstance(decision, dict) and "systemMessage" in decision:
        ledger_event(root, runtime, session, "warn", rule=note.get("rule"), **call)


def allowed_event(root, runtime, session, note, call):
    """The ledger line of an allow: what it allowed (`allow`: `edit`, `read`, the command classes, `gate`, or the
    reviewed `commit` or `push`; the line's own `kind` is `allowed`) and the grant or Git review behind it."""
    given = note.get("allowed") or {}
    ledger_event(root, runtime, session, "allowed", allow=given.get("kind"), id=given.get("id"),
                 grants=given.get("grants"), **call)


def escalated(payload):
    """True when the call asks to run outside the host's sandbox or with more permissions: Claude's
    `dangerouslyDisableSandbox`, Codex's `sandbox_permissions` (other than `use_default`),
    `with_escalated_permissions` or a non-empty `additional_permissions`."""
    inputs = tool_inputs(payload)
    return inputs.get("dangerouslyDisableSandbox") not in (None, False) or \
        inputs.get("sandbox_permissions") not in (None, "use_default") or \
        inputs.get("with_escalated_permissions") not in (None, False) or \
        inputs.get("additional_permissions") not in (None, False, "", {}, [])


def tool_decision(runtime, payload, project, note):
    """The decision on one tool call, in PreToolUse's shape; Codex's PermissionRequest reads the same answer.
    `note` collects what the ledger records about it (state, rule, id, asked, allowed).

    A pending STOP decides as it always did and nothing is allowed under it. No exception path allows, and a
    call that asks to leave the sandbox is never allowed: the host decides it."""
    decision = decide_call(runtime, payload, project, note)
    if verdict(decision) == "allow" and escalated(payload):
        note.pop("allowed", None)
        return None
    return decision


def plain_commit(args, cwd):
    """The message of a plain `git commit`: one or more `-m <message>`, or one `-F <file>` (not stdin), and at most
    one `--cleanup=verbatim`; None for any other form (`--amend`, `-a`, a pathspec, `--no-verify`, …)."""
    paragraphs, files, verbatim, i = [], [], False, 0
    while i < len(args):
        arg = args[i]
        if arg == "--cleanup=verbatim" and not verbatim:
            verbatim, i = True, i + 1
            continue
        if arg in ("-m", "-F") and i + 1 < len(args):
            (paragraphs if arg == "-m" else files).append(args[i + 1])
            i += 2
            continue
        return None
    if bool(paragraphs) == bool(files) or len(files) > 1 or files and files[0] in ("-", ""):
        return None
    if files:  # a regular file of at most MESSAGE_BYTES, looked at before any open: a FIFO never blocks the hook
        try:
            return small_file(os.path.join(cwd, files[0]), MESSAGE_BYTES).decode("utf-8")
        except (OSError, ValueError):
            return None
    return "\n".join(part if part.endswith("\n") else part + "\n" for part in paragraphs)


def commit_hooks(here, top, ctx=None):
    """True when a commit at `here` may run a hook, or that cannot be known: an executable file other than a
    `.sample` in the effective hooks directory (core.hooksPath from any scope, relative to the work tree's top, or the
    repository's own), each hook a commit runs looked up by name as Git does (X_OK on its path), any `hook.<name>.command`
    or `hook.<name>.event` entry in the config (any scope), and any error other than "does not exist" on the way."""
    if git_read(here, "config", "--get-regexp", r"^hook\..*\.(command|event)$", optional=True, ctx=ctx):
        return True
    places = {os.path.join(here, git_text(here, "rev-parse", "--git-path", "hooks", ctx=ctx))}
    configured = git_text(here, "config", "--get", "core.hooksPath", optional=True, ctx=ctx)
    if configured:
        configured = os.path.expanduser(configured)
        places |= {os.path.join(top, configured), os.path.join(here, configured)}
    for place in places:
        try:
            names = set(os.listdir(place))
        except FileNotFoundError:
            names = set()
        except OSError:
            return True  # unreadable: it may hold a hook
        for name in names | set(COMMIT_HOOKS):
            if name.endswith(".sample"):
                continue
            path = os.path.join(place, name)
            try:
                mode = os.stat(path).st_mode
            except FileNotFoundError:
                continue
            except OSError:
                return True
            if not (mode & 0o170000) == 0o040000 and os.access(path, os.X_OK):  # not a directory (S_ISDIR)
                return True
    return False


def grant_commit(runtime, payload, project, note):
    """The allow for a plain commit inside an active grant that names `commit`, or None: then the Git review decides
    as it always did. Any failure is None."""
    try:
        return commit_allow(runtime, payload, project, note)
    except Exception:
        return None


def commit_allow(runtime, payload, project, note):
    """A plain commit (plain_commit) in this project's repository (its main or a linked work tree) or in its second
    Git directory whose work tree is the project root, on a branch, with a staged index whose every path a grant's
    path glob matches; a protected file only where a grant names it literally, in the second Git directory or this
    tree. `note` gets the allow and the `commit` line's fields."""
    if payload.get("tool_name") not in SHELL_TOOLS.get(runtime, set()) or escalated(payload) or not ordinary_shell(payload):
        return None
    grants = active_grants(project)
    hit = granting(grants, "commit")
    if not hit:
        return None
    command, cwd = shell_command(payload.get("tool_input")), call_cwd(payload)
    here, kind, args, ctx = git_review_command(command, cwd)
    if kind != "commit":
        return None
    message = plain_commit(args, str(here))
    if message is None or not message.strip() or "\0" in message:
        return None
    root, main = os.path.realpath(project_root(project)), ledger_root(project)
    if ctx:  # the project's second Git directory: inside the root, not bare, its work tree the root, ignored by the main one
        top, git_dir = os.path.realpath(ctx["workTree"]), os.path.realpath(ctx["gitDir"])
        if top != root or os.path.dirname(git_dir) != root or git_dir == os.path.join(root, ".git"):
            return None
        bare = git_text(root, "--git-dir=" + git_dir, "config", "--bool", "core.bare", optional=True)
        tree = git_text(root, "--git-dir=" + git_dir, "config", "core.worktree", optional=True)
        if bare == "true" or not tree or os.path.realpath(os.path.join(git_dir, tree)) != root \
                or git_read(root, "check-ignore", "-q", os.path.relpath(git_dir, root), optional=True) is None:
            return None
        second = True
    else:
        top = os.path.realpath(git_repo(str(here)))
        common = git_common_directory(top)
        if not common or os.path.basename(common) != ".git" or os.path.realpath(os.path.dirname(common)) != main:
            return None
        git_dir, second = common, False
    git_meta = pathlib.Path(git_text(str(here), "rev-parse", "--absolute-git-dir", ctx=ctx))
    if any((git_meta / name).exists() for name in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge",
                                                   "rebase-apply")):
        return None
    branch = git_text(str(here), "symbolic-ref", "--quiet", "HEAD", optional=True, ctx=ctx)
    if not branch:
        return None
    if commit_hooks(str(here), top, ctx):
        return None  # a hook could stage, change or add to what the commit holds after this look
    staged = [name.decode("utf-8", "surrogateescape") for name in git_read(
        top, "diff", "--cached", "--no-relative", "--name-only", "-z", "--no-renames", ctx=ctx).split(b"\0") if name]
    if not staged:
        return None
    place = Place(project, top)
    globs = [glob for record in grants for glob in record["grant"]["paths"]]
    for name in staged:
        parts = name.split("/")
        compared = place.locate(os.path.normpath(os.path.join(top, name)))[1]
        if compared is None:
            return None
        if place.protected(compared):  # the notebook, its history, an instruction or settings file: named literally
            if not (second or top == root) or name not in globs:
                return None
        elif not any(glob_matches(glob, parts) for glob in globs):
            return None
    note["allowed"] = {"kind": "commit", "id": hit, "grants": None}
    note["committed"] = {"top": top, "gitDir": git_dir if second else None, "second": second, "own": top == root,
                         "globs": globs, "id": hit,
                         "head": git_text(str(here), "rev-parse", "--verify", "--quiet", "HEAD", optional=True, ctx=ctx)}
    note["commit"] = {"repo": os.path.relpath(git_dir, main) if git_dir.startswith(main) else os.path.basename(git_dir),
                      "branch": branch.removeprefix("refs/heads/"), "files": len(staged),
                      "subject": (message.splitlines() or [""])[0], "id": hit}
    return permission("allow", GRANT_ALLOW.format(hit, "commit"))


def leaves_machine(command, cwd=None):
    """True for a shell command that may carry something off this machine: in command position (the first word of a
    segment, past assignments and known wrappers such as env, xargs or nohup) a transfer program or network client,
    Git with a subcommand that is an exit or not shipped with Git (it may be an alias) or a `-c` setting beyond the
    safe ones, the gate (by its real path, from every directory a `cd` before it reaches) with `remote`, `service` or
    `measure`, inline code, a shell's `-c`, or a publisher; and any command that cannot be read literally (a glob in
    an argument is read). Words are read as the shell reads them; a quoted here-document's body is data, and a
    command that only reads leaves nothing. A word anywhere else is an argument, never a program."""
    head = heredoc_head(command)
    text = head if head is not None else command
    for spelling, path in gate_spellings().items():
        if spelling in text:
            text = text.replace(spelling, shlex.quote(path) if path else "unknown")
    if shell_is_read_only(command)[0]:
        return False
    if visible_git_write(command) or not literal_shell(re.sub(r"[*?]", "x", text)):
        return True
    parts = split_segments(text)
    if parts is None:
        return True
    cwds = [cwd or os.getcwd()]
    for raw in parts[0]:
        if not raw.strip():
            continue
        try:
            tokens = strip_redirect_tokens(shlex.split(raw))
        except ValueError:
            return True
        if tokens[:1] == ["cd"]:
            cwds = unique(cwds + [os.path.realpath(os.path.join(where, tokens[1])) for where in cwds if len(tokens) == 2])
            continue
        if tokens and segment_leaves(tokens, cwds):
            return True
    return False


def command_position(tokens):
    """The index of the program a segment runs, past variable assignments and the wrappers that run the rest
    (env, command, exec, nohup, nice, time, timeout, stdbuf, sudo, doas, xargs) with their options; None when
    a wrapper's options cannot be read."""
    i = 0
    while i < len(tokens):
        word = tokens[i]
        if ASSIGNMENT.match(word) and "=" in word:
            i += 1
            continue
        name = word.rsplit("/", 1)[-1]
        if name not in WRAPPERS:
            return i
        i += 1
        while i < len(tokens) and (tokens[i].startswith("-") or ASSIGNMENT.match(tokens[i]) and "=" in tokens[i]
                                   or name == "timeout" and re.fullmatch(r"[0-9.]+[smhd]?", tokens[i])):
            if tokens[i] in WRAPPER_VALUES.get(name, ()):
                i += 1  # an option that takes the next word
            i += 1
    return None


def segment_leaves(tokens, cwds):
    """leaves_machine for one segment's words, read from the program in command position."""
    at = command_position(tokens)
    if at is None:
        return True
    program, args = tokens[at], tokens[at + 1:]
    name = program.rsplit("/", 1)[-1]
    if any(char in program for char in "*?["):
        return True  # a glob in command position: any program at all
    if name in TRANSFERS or name in NETWORK_CLIENTS or name == "osascript" or name.startswith("git-") and (
            name[4:] in GIT_EXITS or name[4:] not in LOCAL_GIT):
        return True
    if name == "open" and any("://" in arg for arg in args):
        return True
    if name == "find" and set(args) & {"-exec", "-execdir", "-ok", "-okdir"}:
        return True
    flags = []
    for arg in args:
        if not arg.startswith("-") or arg == "--":
            break
        flags.append(arg)
    short = [flag for flag in flags if not flag.startswith("--")]
    if name in SHELLS and any("c" in flag[1:] for flag in short):
        return True  # a script in a string: anything at all
    if PYTHON.fullmatch(name) or name.startswith("python"):
        if any("c" in flag[1:] for flag in short) or args[len(flags):len(flags) + 2] == ["-m", "http.server"]:
            return True  # code given inline, or a server
        rest = args[len(flags):]
        if rest[:1] == ["-m"]:
            return False
        return bool(rest) and len(rest) > 1 and rest[1] in RESOURCE_WORDS and any(is_gate_file(rest[0], where) for where in cwds)
    if name in ("node", "deno", "ruby", "perl", "php") and set(flags) & {"-e", "-E", "--eval", "-r", "-p"}:
        return True
    if name == "git":
        return git_leaves(args) or git_subcommand(args) in GIT_EXITS or bool(
            set(args) & GIT_EXIT_FLAGS.get(git_subcommand(args) or "", set()))
    if name == "aws" and ("s3api" in args or "s3" in args and set(args) & AWS_TRANSFERS) or \
            name == "gsutil" and set(args) & GSUTIL_TRANSFERS:
        return True
    if (name, tuple(args[:1])) in PUBLISHERS:
        return True
    return bool(args) and args[0] in RESOURCE_WORDS and any(is_gate_file(program, where) for where in cwds)


def git_subcommand(args):
    """The subcommand of a Git invocation's arguments (past its global options), or None."""
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("-c", "--config-env", "-C", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--super-prefix"):
            i += 2
        elif arg.startswith("-"):
            i += 1
        else:
            return arg
    return None


def git_leaves(args):
    """True for a Git invocation (its arguments) that may leave the machine beyond what exit_word reads: a `-c`
    setting other than the safe ones (an alias, a pager, an ssh command), or a subcommand Git does not ship locally
    (it may be an alias)."""
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("-c", "--config-env") or arg.startswith(("-c", "--config-env=")):
            setting = args[i + 1] if arg in ("-c", "--config-env") and i + 1 < len(args) else arg.partition("=")[2] \
                if arg.startswith("--config-env=") else arg[2:]
            if setting not in SAFE_GIT_CONFIG:
                return True
            i += 2 if arg in ("-c", "--config-env") else 1
            continue
        if arg in ("-C", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--super-prefix"):
            i += 2
            continue
        if arg.startswith("-"):
            i += 1
            continue
        return arg not in LOCAL_GIT
    return False


def is_gate_file(word, cwd):
    """True when `word`, resolved from `cwd`, is this gate (any launcher of it) or tools/ddl_run.py beside it."""
    path = os.path.realpath(os.path.join(cwd, word))
    gates = gate_files()
    runs = {os.path.realpath(os.path.join(os.path.dirname(gate), "ddl_run.py")) for gate in gates}
    return path in gates or path in runs


def provisional_guard(runtime, payload, project, note):
    """A deny for a call that may leave this machine while a provisional question of the project is unanswered:
    what was decided provisionally never leaves it. A shell command that leaves_machine reads as an exit, every tool
    of an MCP server or connector (no name tells what it sends), and the host's outward tools; a notification to the
    human is none. None otherwise; with no open provisional question nothing else is read. An error while it is open
    denies."""
    tool = payload.get("tool_name")
    shell = tool in SHELL_TOOLS.get(runtime, set())
    mcp = isinstance(tool, str) and tool.startswith(("mcp__", "mcp."))
    if not shell and not mcp and tool not in OUTWARD_TOOLS:
        return None
    try:
        pending = sorted(provisional_markers(project_key(ledger_root(project))))
    except Exception:
        pending = ["(unreadable)"]
    if not pending:
        return None
    try:
        if shell:
            command = shell_command(payload.get("tool_input"))
            validation = isinstance(command, str) and command_lines(command) in validation_commands(
                project, project_root(project)) and not exit_word(command)  # the human approved that exact text
            leaves = not isinstance(command, str) or not validation and leaves_machine(command, call_cwd(payload))
        else:
            leaves = True  # a connector's tool, whatever its name, or the host's own way out
    except Exception:
        leaves = True
    if not leaves:
        return None
    note.update(rule="provisional", id=pending[0])
    return deny(PROVISIONAL_EXIT.format(", ".join(pending)))


def shell_touches(command, cwd):
    """[(word, resolved path)] of what a literal shell command names: every word and option value of every segment
    and every redirect target, resolved from every directory a `cd` before it reaches; None when it cannot be read
    literally (then nothing is known it names)."""
    head = heredoc_head(command)
    text = head if head is not None else command
    if not literal_shell(text):
        return None
    parts = split_segments(text)
    if parts is None:
        return None
    cwds, found = [cwd], []
    for raw in parts[0]:
        try:
            tokens = shlex.split(raw)
        except ValueError:
            return None
        if tokens[:1] == ["cd"] and len(tokens) == 2:
            cwds = unique(cwds + [os.path.realpath(os.path.join(where, tokens[1])) for where in cwds])
            continue
        words, i = [], 0
        while i < len(tokens):
            match = re.fullmatch(r"(?:\d*|&)>>?(.*)|\d*<(.*)", tokens[i])
            if match:  # a redirect: its target is the rest of the word, or the next word
                target = match[1] if match[1] is not None else match[2]
                if not target and i + 1 < len(tokens):
                    i += 1
                    target = tokens[i]
                if target and not target.startswith("&"):
                    words.append(target)
            else:
                words += [name for name in named(tokens[i]) if name]
            i += 1
        found += [(word, os.path.realpath(os.path.join(where, word))) for word in words for where in cwds]
    return found


def queued_guard(runtime, payload, project, note):
    """A deny for an edit of a file that a queued question, not answered yet, holds (its items' owner files and those
    of the items depending on them; a provisional question goes ahead instead). None otherwise, and on any error."""
    try:
        edit = edit_targets(runtime, payload)
        shell = payload.get("tool_name") in SHELL_TOOLS.get(runtime, set())
        if not (edit and edit[0]) and not shell:
            return None
        root = ledger_root(project)
        markers = {record["current"]: record for record in open_markers(project_key(root)).values()
                   if record.get("holds") and not record.get("provisional")}
        if not markers:
            return None
        place, cwd = Place(project, project_root(project)), call_cwd(payload)
        if edit and edit[0]:
            targets = [(target, os.path.realpath(os.path.join(cwd, target))) for target in edit[0]]
        else:  # what a command names: its words and option values, its redirect targets; reads touch nothing
            command = shell_command(payload.get("tool_input"))
            if not isinstance(command, str) or shell_is_read_only(command)[0]:
                return None
            targets = shell_touches(command, cwd) or []
        for ident, record in sorted(markers.items()):
            items = run_record(root, record["holds"]["run"])
            globs = [glob for name in held_closure(items, record["holds"]["items"])
                     for glob in items.get(name, {}).get("files", [])]
            specs = owner_specs(place.root, globs, place)
            for given, target in targets:
                if held_target(target, specs, place):
                    note.update(rule="queued", id=ident)
                    return deny(QUEUED_HOLD.format(ident, given))
    except Exception:
        return None
    return None


def decide_call(runtime, payload, project, note):
    """tool_decision's answer before the sandbox check."""
    provisional = provisional_guard(runtime, payload, project, note)
    if provisional is not None:
        return provisional
    git_review = git_review_guard(runtime, payload, note)
    try:
        state, pending = pending_scan(runtime, payload)
    except Exception:
        if git_review is not None and verdict(git_review) != "allow":
            note["rule"] = "git-review"
            return git_review
        raise
    note["state"] = state
    asked = question_guard(runtime, payload, state, pending, note)
    if asked is not None:
        return asked
    if state is True:
        mutating, segment = is_mutating(runtime, payload.get("tool_name"), payload.get("tool_input"))
        if mutating and not gate_preparation(runtime, payload):
            held = held_answer(runtime, payload, project, note)
            if held is not None:
                return held
            note.update(rule="stop", id=pending["id"] if pending else None)
            reason = WAITING_REASON.format(pending["id"], pending["report"]) if pending else DENY_REASON
            return deny(reason + (" Shell segment is not read-only: `{}`.".format(segment) if segment else ""))
    if git_review is not None:
        if verdict(git_review) != "allow":
            granted = grant_commit(runtime, payload, project, note) if state is False else None
            if granted is not None:
                return granted
            note["rule"] = "git-review"
        return git_review
    outward = push_guard(runtime, payload)
    if outward is not None:
        note["rule"] = "push-form"
        return outward
    if state is True:
        return None  # what passes a pending STOP passes as it always did: no grant answers under it
    ledger = ledger_guard(runtime, payload, project)
    if ledger is not None:
        note["rule"] = "ledger"
        return ledger
    queued = queued_guard(runtime, payload, project, note)
    if queued is not None:
        return queued
    if state is False:
        step = pin_step(runtime, payload, project, note)
        if step is not None:
            return step
    if state is None:
        warned = session_file(payload.get("session_id"), ".warned")
        if warned.exists():
            return None  # warn once per session; the rule still holds by instruction
        warned.write_text(str(time.time()))
        note["rule"] = "unreadable-record"
        return {"systemMessage": UNREADABLE}
    # An OPEN record: the active grants answer for what they classify; everything else is the host's.
    return grant_decision(runtime, payload, project, note)


def commit_key(payload):
    """What names one commit call across its PreToolUse (or PermissionRequest) and its PostToolUse."""
    return review_hash([shell_command(payload.get("tool_input")), call_cwd(payload)])[:ID_HEX_LENGTH]


def remember_commit(payload, note):
    """Keep what an allowed commit inside a grant was checked against, for the look after it ran (handle_post_tool_use)."""
    path = session_file(payload.get("session_id"), ".commits")
    try:
        kept = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (OSError, ValueError):
        kept = {}
    kept = kept if isinstance(kept, dict) else {}
    kept[commit_key(payload)] = note["committed"]
    write_whole(str(path), json.dumps(dict(list(kept.items())[-ARMED_LIMIT:])))


def handle_post_tool_use(runtime, payload):
    """After a commit the gate allowed inside a grant: compare the paths of every commit made since the look (from the
    HEAD then to the HEAD now) with the grant, since a hook or anything else may have changed them. Each commit that
    leaves it writes a `warn` line (rule `commit-outside-grant`) and a mark the next push review shows on it; more
    than one commit writes a `warn` line (rule `commits-after-grant`). It never decides anything."""
    try:
        # A look creates nothing and, outside a DDL project, imports nothing more.
        path = os.path.join(state_base(), state_name(payload.get("session_id")) + ".commits")
        if payload.get("tool_name") not in SHELL_TOOLS.get(runtime, set()) or not os.path.exists(path):
            return None
        project = session_project(payload)
        if not project["ddl"]:
            return None
        with open(path, encoding="utf-8") as fh:
            kept = json.load(fh)
        checked = kept.pop(commit_key(payload), None) if isinstance(kept, dict) else None
        if checked is None:
            return None
        write_whole(str(path), json.dumps(kept))
        ctx = {"gitDir": checked["gitDir"], "workTree": checked["top"]} if checked.get("gitDir") else None
        top = checked["top"]
        head = git_text(top, "rev-parse", "--verify", "HEAD", ctx=ctx)
        if head == checked.get("head"):
            return None  # no commit was made
        made = git_text(top, "rev-list", "--reverse", "HEAD", *(["--not", checked["head"]] if checked.get("head") else []),
                        ctx=ctx).split()  # every commit since the look (an amend, a hook's commit) is compared
        root = ledger_root(project)
        session = payload.get("session_id")
        if len(made) > 1:
            ledger_event(root, runtime, session, "warn", rule="commits-after-grant", id=checked["id"], commit=head,
                         count=len(made))
        place = Place(project, top)
        for commit in made[-SENT_LIMIT:]:
            names = [name.decode("utf-8", "surrogateescape") for name in git_read(
                top, "diff-tree", "--no-commit-id", "--name-only", "-r", "-m", "--root", "-z", commit,
                ctx=ctx).split(b"\0") if name]
            outside = set()
            for name in names:
                compared = place.locate(os.path.normpath(os.path.join(top, name)))[1]
                literal = name in checked["globs"] and (checked.get("second") or checked.get("own"))
                if compared is None or (place.protected(compared) and not literal) or not place.protected(compared) \
                        and not any(glob_matches(glob, name.split("/")) for glob in checked["globs"]):
                    outside.add(name)
            if outside:
                ledger_event(root, runtime, session, "warn", rule="commit-outside-grant", id=checked["id"],
                             commit=commit, files=len(outside))
                store = os.path.join(grant_store(), project_key(root), "outside")
                private_directory(store)
                write_whole(os.path.join(store, commit), json.dumps({"id": checked["id"], "files": len(outside)}))
    except Exception:
        pass
    return None


def handle_pre_tool_use(runtime, payload):
    project = session_project(payload)
    if not project["ddl"]:
        return None
    note = {}
    decision = tool_decision(runtime, payload, project, note)
    if runtime == "codex" and verdict(decision) == "allow":
        # Codex takes no allow from PreToolUse; its PermissionRequest hook gives the same answer instead.
        decision = None
        note.pop("allowed", None)
    try:  # the ledger and the grant record come after the decision and never change it
        tool_note(runtime, payload, project, decision, note)
    except Exception:
        pass
    return decision


def handle_permission_request(runtime, payload):
    """Codex asks this before it confirms a call with the human: allow what the decision allows (inside an
    active grant, or the reviewed commit or push), else say nothing. Every deny was PreToolUse's already.

    It never rewrites the call, its permissions or the turn, and an internal error allows nothing."""
    try:
        project = session_project(payload)
        if not project["ddl"]:
            return None
        note = {}
        if verdict(tool_decision(runtime, payload, project, note)) != "allow":
            return None
    except Exception:
        return None
    try:
        call = {"tool": payload.get("tool_name") if isinstance(payload.get("tool_name"), str) else None,
                "toolUseId": payload.get("tool_use_id") if isinstance(payload.get("tool_use_id"), str) else None}
        allowed_event(ledger_root(project), runtime, payload.get("session_id"), note, call)
        if note.get("commit"):
            ledger_event(ledger_root(project), runtime, payload.get("session_id"), "commit", **note["commit"], **call)
            remember_commit(payload, note)
    except Exception:
        pass
    return {"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": {"behavior": "allow"}}}


def handle_stop(runtime, payload):
    project = session_project(payload)
    if not project["ddl"]:
        return None
    # The last message is the cheap signal; the record catches a report emitted earlier in the same turn,
    # including one that is recorded only as a prepared question or the preparation output.
    pending = None
    closed = has_report(payload.get("last_assistant_message"))
    if not closed:
        state, pending = record_scan(runtime, payload)
        closed = state is True
    if closed:
        marker_path(payload.get("session_id")).write_text(str(time.time()))
    try:  # the fallback for an answer no tool call has seen: the turn can end right after it
        root = ledger_root(project) if closed or os.path.exists(asked_marker(payload.get("session_id"))) else None
        if closed:
            ledger_event(root, runtime, payload.get("session_id"), "stop", id=pending["id"] if pending else None)
        observe_answers(runtime, payload, root)
    except Exception:
        pass
    try:  # a queued question not asked yet is named once per turn's end; it never blocks
        asked = {entry["id"] for entry in armed_questions(payload.get("session_id"))}
        unasked = sorted(record["current"] for record in open_markers(project_key(ledger_root(project))).values()
                         if not set(record["ids"]) & asked)
        if unasked:
            return {"systemMessage": QUEUED_NOTICE.format(", ".join(unasked))}
    except Exception:
        pass
    return None


def prompt_note(runtime, payload, project, answered):
    """The ledger's share of one submitted prompt. `answered` is (ID, reply, option labels) when the prompt
    is Codex's reply envelope to the unchanged prepared question, else None: typed text."""
    session, root = payload.get("session_id"), ledger_root(project)
    if answered is None:
        disarm(session)  # a typed prompt retires the asked questions: their reports now predate the epoch
        ledger_event(root, runtime, session, "prompt")
        return
    label, reply, labels = answered
    choice = labels.index(reply[2]) if reply[2] in labels else None
    ledger_event(root, runtime, session, "answered", nulls=("choice",), id=label, toolUseId=reply[0], choice=choice,
                 label=reply[2] if choice is not None else None, timeout=False)  # free text never enters the ledger
    if any(entry["id"] == label and (entry.get("provisional") or entry.get("queued")) for entry in armed_questions(session)):
        settle_provisional(root, runtime, session, label, choice, reply[0])
    if choice != 0:
        disarm(session)  # any other reply moved the epoch, as typed text does
        return
    # The approving reply spared the epoch, so the other questions keep waiting. Its own question stays only
    # for a grant, which still needs its proof from the record at the next tool call; its line is done.
    armed = armed_questions(session)
    kept = [dict(entry, answered=True) if entry["id"] == label else entry
            for entry in armed if entry["id"] != label or entry.get("grant") or entry.get("confirm")]
    if kept != armed:
        arm(session, kept)


def handle_user_prompt_submit(runtime, payload):
    project = session_project(payload, refresh=True)
    if not project["ddl"]:
        return None
    session = payload.get("session_id")
    try:  # first: an answer the record already holds is recorded before anything below retires its question
        observe_answers(runtime, payload, ledger_root(project))
    except Exception:
        pass
    prompt = payload.get("prompt")
    if runtime == "claude" and isinstance(prompt, str) and prompt.lstrip().startswith(NOT_HUMAN_PREFIXES):
        # A background worker's completion notice, or another envelope the host submits as a prompt: no human
        # spoke, so the marker, the epoch and the asked questions stay as they are.
        ledger_event(ledger_root(project), runtime, session, "prompt", rule="notification")
        return None
    marker_path(session).unlink(missing_ok=True)
    # Revoke older preparations immediately, even if the new prompt has not reached the
    # asynchronous transcript yet. A possible matching native submission is not itself a grant:
    # PreToolUse must still prove its request/result association from the conversation record.
    # The reply that approves a prepared report is spared like the one that approves a Git review:
    # bumping the epoch for it would retire the very report it answers before its grant is proved.
    matching_submission, answered = False, None
    if runtime == "codex":
        try:
            reply = codex_git_reply(payload.get("prompt"))
            ident = question_id(reply[1]) if reply else None
            if ident and ident[0] == "G":
                record, _ = load_git_review(ident[1], runtime)
                q = review_question(record)
                title, labels = q["title"], q["options"]
            elif ident:
                record = load_report(ident[1], runtime)
                title, labels = record["question"], [option["label"] for option in record["options"]]
            if ident and reply[1].replace("\r\n", "\n") == title:
                matching_submission = reply[2] == labels[0]
                answered = ("-".join(ident), reply, labels)
        except (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError):
            pass  # no usable record of that question (IndexError: one without options): the epoch moves
    if not matching_submission:
        session_file(payload.get("session_id"), ".git-epoch").write_text(str(time.time()))
    try:
        prompt_note(runtime, payload, project, answered)
    except Exception:
        pass
    return None


def find_design_md(cwd) -> pathlib.Path | None:
    """design.md in cwd or a parent, stopping at the repository root (`.git`) or at $HOME."""
    if not cwd:
        return None
    try:
        home = pathlib.Path.home()
    except Exception:
        home = None
    here = pathlib.Path(cwd)
    for cand in [here] + list(here.parents):
        if cand == home:
            break
        if (cand / "design.md").is_file():
            return cand / "design.md"
        if (cand / ".git").exists():
            break
    return None


def handle_session_start(runtime, payload):
    project = session_project(payload, refresh=True)
    if not project["ddl"]:
        return None
    parts, source = [], payload.get("source")
    if source in ("compact", "resume", "fork", "clear"):
        session_file(payload.get("session_id"), ".git-epoch").write_text(str(time.time()))
        disarm(payload.get("session_id"))  # the asked report now predates the epoch; a recorded grant stays
    try:
        ledger_event(ledger_root(project), runtime, payload.get("session_id"), "session-start",
                     rule=source if isinstance(source, str) else None)
    except Exception:
        pass
    if payload.get("source") in ("compact", "resume"):
        state, pending = pending_scan(runtime, payload)
        if state is True:
            parts.append(PENDING_NOTICE.format(pending["id"], pending["report"]) if pending else NOTICE)
    if runtime == "codex":
        design = find_design_md(payload.get("cwd"))
        if design is not None:
            parts.append(DESIGN_HEADER + "\n\n" + design.read_text(encoding="utf-8", errors="replace"))
    if not parts:
        return None
    return {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "\n\n".join(parts)}}


HANDLERS = {"pre-tool-use": handle_pre_tool_use, "permission-request": handle_permission_request,
            "post-tool-use": handle_post_tool_use,
            "session-start": handle_session_start, "stop": handle_stop, "user-prompt-submit": handle_user_prompt_submit}


def parse_args(argv):
    """(event, runtime, problem); `problem` is the warning text when the arguments are unusable."""
    event, runtime, rest = None, None, list(argv)
    while rest:
        a = rest.pop(0)
        if a == "--runtime":
            runtime = rest.pop(0) if rest else None
        elif a.startswith("--runtime="):
            runtime = a.split("=", 1)[1]
        elif event is None and not a.startswith("-"):
            event = a
        else:
            return event, runtime, "DDL gate: unexpected argument {!r}; the call was allowed.".format(a)
    if event not in EVENTS:
        return event, runtime, "DDL gate: unknown event {!r} (expected one of {}); the call was allowed.".format(
            event, ", ".join(EVENTS))
    if runtime not in RUNTIMES:
        return event, runtime, "DDL gate: unknown runtime {!r} (expected {}); the call was allowed.".format(
            runtime, " or ".join(RUNTIMES))
    return event, runtime, None


def emit(obj):
    if obj is not None:
        sys.stdout.write(json.dumps(obj) + "\n")
        sys.stdout.flush()


def run_module():
    """tools/ddl_run.py, which holds the Run subcommands, imported from beside this file (symbolic links
    resolved) only for their words: no hook event compiles it.

    It finds this module as `ddl_gate_core` whether this file runs as the script or was imported, so the gate
    is loaded once, and the import writes bytecode only under a prefix (the launcher's private cache, or the
    interpreter's own), never a `__pycache__` beside an installed copy (dist/ or a project)."""
    here = os.path.dirname(os.path.realpath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    this = sys.modules.get(__name__)
    if this is not None:
        sys.modules.setdefault("ddl_gate_core", this)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = previous or sys.pycache_prefix is None
    try:
        import ddl_run
    finally:
        sys.dont_write_bytecode = previous
    return ddl_run


def main(argv) -> int:
    if argv and argv[0] == "status":
        return project_status(argv[1:])
    if argv and argv[0] in RUN_WORDS:
        try:
            run = run_module()
        except Exception as exc:  # a layout that lacks the module (an older project copy): a usage error
            print("DDL {}: ddl_run.py could not be loaded beside the gate ({}: {}); install DDL again.".format(
                argv[0] if argv[0] in ("report", "snapshot") else "run", type(exc).__name__, exc), file=sys.stderr)
            return 2
        return run.main(argv)
    if argv and argv[0] == "prepare-git-review":
        try:
            _, runtime, problem = parse_args(["session-start", *argv[1:]])
            if problem:
                raise ValueError(problem)
            result = prepare_git_review(runtime, json.loads(sys.stdin.read()))
            emit(result)
            cli_event(runtime, "prepared", id=result["reviewId"])
            return 0
        except Exception as exc:
            print("DDL Git review: " + str(exc), file=sys.stderr)
            return 2
    if argv and argv[0] == "prepare-report":
        try:
            _, runtime, problem = parse_args(["session-start", *argv[1:]])
            if problem:
                raise ValueError(problem)
            try:
                data = json.loads(sys.stdin.read())
            except ValueError as exc:
                raise ValueError("the input is not JSON ({}).".format(exc)) from None
            result = prepare_report(runtime, data)
            emit(result)
            # A queued, held or provisional report says so in its line; any other keeps the line it had.
            extra = {} if not isinstance(data, dict) else {
                key: value for key, value in (("queued", data.get("queue")), ("holds", data.get("holds")),
                                              ("provisional", True if data.get("provisional") else None))
                if value is not None}
            cli_event(runtime, "prepared", id=result["reportId"], **extra)
            return 0
        except Exception as exc:
            print("DDL STOP: " + str(exc), file=sys.stderr)
            return 2
    try:
        event, runtime, problem = parse_args(argv)
        if problem:
            emit({"systemMessage": problem})
            return 0
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
        emit(HANDLERS[event](runtime, payload if isinstance(payload, dict) else {}))
    except Exception as exc:  # fail-open: a broken gate must never deny by accident
        try:
            emit({"systemMessage": INTERNAL.format(type(exc).__name__, exc)})
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
