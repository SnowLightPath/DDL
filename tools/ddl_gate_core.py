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
run-start, run-item, report and snapshot (RUN_WORDS) live in tools/ddl_run.py beside this file, which `main`
imports for those words only (`ddl_run.py <word> …` runs them too, alike); no hook event imports it.

prepare-report reads JSON {language, decision, recommendation, consequence, detail, options?,
multiSelect?, grant?} on stdin, writes report.md and report.json under `<state dir>/reports/<id>/`,
and prints {reportId, report, question, nativeRequest}. prepare-git-review reads JSON
{language: en|ja, operations: [{cwd, command}, ...]}, snapshots the staged changes and push
targets, writes review detail in the private state directory, and prints the same shape with
reviewId. Neither creates approval; invalid input prints `DDL STOP: …` / `DDL Git review: …` on
stderr and exits 2.

Grant, ledger and counts (no decision reads a ledger line; an active grant answers, see Decisions): a report
may carry a `grant` {paths, commands, machines, handover, budget {minutes, fixAttempts}, expires}.
It is hashed into the report ID with the project key, adds one generated line to the question and
a block to report.md, and is written once to the user-level store ($DDL_GATE_GRANT_DIR, else
$XDG_STATE_HOME/ddl-gate, else $HOME/.local/state/ddl-gate) as `<project key>/grants/R-<id>.json`
when the record proves that the human submitted the first option of the unchanged question; after
that only its expiry ends it. The record appears whole or not at all, and a file that does not parse
as that grant's record is no grant. In a DDL project the gate appends one JSON line per event to
`.ddl/events.jsonl` at the root of the main work tree (a silent pass writes nothing; an approved
grant that was not recorded leaves a `warn` line whose rule is `grant-proof` or `grant-store`).
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
                      while CLOSED a question without the pending ID is denied;
                      ordinary commit/push also needs a matching native content review while OPEN,
                      and the matched one is allowed ("allow": the review was its one confirmation);
                      codex also denies unsupported push forms in confirmation-enabled modes;
                      a write of `.ddl/events.jsonl` or `.ddl/runs/*/run.json` -> "deny";
                      OPEN with an active grant (recorded, before its expiry): a read; from a working
                      directory inside the root, an edit inside its paths or granted command classes
                      in their allow-listed forms with literal arguments -> "allow"
                      ("DDL: inside grant <id> (<kind>)"); a path, class or machine outside every
                      active grant, or an exit behind ssh -> "deny"; a protected file (Git's files,
                      CI workflows, .ddl/, an agent's, editor's or direnv's settings, an instruction
                      file, the notebook), a call asking to leave the sandbox and anything else print nothing.
                      Codex takes no allow from PreToolUse: there an allow prints nothing
  permission-request  the same decision; its allow only, as PermissionRequest's {"behavior": "allow"},
                      else nothing (Codex asks it before its own confirmation; no tool_use_id)
  stop                writes the marker file when the turn ended with a report; prints nothing
                      (it also records an approved grant the tool path has not seen yet)
  user-prompt-submit  removes the marker (a human spoke); prints nothing
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


datetime, hashlib, pathlib, re, secrets, shlex, shutil, subprocess, time = (
    _Lazy(name) for name in ("datetime", "hashlib", "pathlib", "re", "secrets", "shlex", "shutil", "subprocess",
                             "time"))
urlparse = _Lazy("urllib.parse", "urlparse")

EVENTS = ("pre-tool-use", "permission-request", "session-start", "stop", "user-prompt-submit")
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
REPORT_VERSION = 2  # the report.json schema; a change of fields bumps it (2: grant and projectKey)
REPORT_INPUT_KEYS = {"language", "decision", "recommendation", "consequence", "detail", "options", "multiSelect",
                     "grant"}
REPORT_LINE_KEYS = ("decision", "recommendation", "consequence")
# The fields the report ID hashes; report.json adds id, question, nativeRequest and reportHash.
# `grant` is None for a report without one; `projectKey` is None when it was prepared outside a DDL project.
REPORT_CORE_KEYS = ("version", "runtime", "language", "nonce", "createdAt", *REPORT_LINE_KEYS,
                    "options", "multiSelect", "detailHash", "grant", "projectKey")
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
GRANT_COMMANDS = ("build", "test", "check", "snapshot", "remote-run")
GRANT_LISTS = {"paths": (1, 32), "commands": (0, 8), "machines": (0, 8), "handover": (0, 8)}  # entries per list
GRANT_BUDGET = {"minutes": (1, 10080), "fixAttempts": (0, 10)}
GRANT_NAME_LIMIT = 80  # characters of one machine or handed-over entry
# The question's extra line, then the three lines of the block in report.md.
GRANT_LABELS = {"ja": ("許諾", "範囲", "予算", "期限"), "en": ("Grant", "Scope", "Budget", "Expiry")}
# The grant's answers to one call (in the PreToolUse decision, which Codex's PermissionRequest shares).
GRANT_ALLOW = "DDL: inside grant {} ({})"
OUTSIDE_PATHS = ("DDL grant: {} is outside the paths of grant {}; widening a grant is an exit gate, so ask the "
                 "human for a revised plan")
OUTSIDE_CLASS = "DDL grant: the command class {} is outside grant {}; ask the human for a revised plan"
OUTSIDE_MACHINE = "DDL grant: the machine {} is outside grant {}; ask the human for a revised plan"
EXIT_BEHIND_SSH = ("DDL grant: `{}` behind ssh is an exit or another transfer, which no grant covers; an exit runs "
                   "here, through its own review")
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
GATE_WORDS = ("status", "report", "run-start", "run-item", "prepare-report", "prepare-git-review")  # need no class
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
RUN_WORDS = ("report", "run-start", "run-item", "snapshot")  # the subcommands tools/ddl_run.py holds (see run_module)
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


def git_tree_fingerprint(cwd, commit=None, ctx=None):
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
        rows.append([mode.decode(), oid.decode(), path.decode("utf-8", "surrogateescape")])
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
                with (pathlib.Path(cwd) / args[i]).open(encoding="utf-8", newline="") as stream:
                    message = [stream.read()]
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


def commit_snapshot(cwd, args, ctx=None):
    """The reviewed commit. In a second Git directory (`ctx`) every read uses that pair, and the repository is
    the Git directory's real path: one review may hold a commit there and one in the work tree's own `.git`."""
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
    patch = git_read(top, "diff", "--cached", "--no-relative", "--binary", "--no-ext-diff", "--no-textconv",
                     "--no-renames", ctx=ctx)
    if not patch:
        raise ValueError("stage the proposed files before preparing the review; the index is empty.")
    names = git_read(top, "diff", "--cached", "--no-relative", "--name-status", "-z", "--no-renames", ctx=ctx).split(b"\0")
    files = [[names[i].decode(), names[i + 1].decode("utf-8", "surrogateescape")]
             for i in range(0, len(names) - 1, 2)]
    op = {"kind": "commit", "repo": top, "branch": branch,
          "head": git_text(cwd, "rev-parse", "--verify", "HEAD", optional=True, ctx=ctx),
          "tree": git_tree_fingerprint(cwd, ctx=ctx), "message": git_message(args, cwd),
          "files": files, "patchHash": hashlib.sha256(patch).hexdigest()}
    if ctx:
        op.update(repo=str(git_dir.resolve()), gitDir=str(git_dir.resolve()), workTree=top)
    return op, patch


def display_remote(url):
    parsed = urlparse.urlsplit(url)
    if parsed.scheme and parsed.netloc and "@" in parsed.netloc:
        return urlparse.urlunsplit(parsed._replace(netloc=parsed.netloc.rsplit("@", 1)[1]))
    return url


def push_snapshot(cwd, args, commits=()):
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
    return {"kind": "push", "repo": repo, "cwd": str(cwd), "remote": remote,
            "urlHash": review_hash(urls), "displayUrl": display_remote(urls[0]),
            "source": source, "destination": destination, "commit": oid,
            "fromCommit": review_hash(dependent) if dependent else None}, b""


def snapshot_operation(request, commits=()):
    if not isinstance(request, dict) or not isinstance(request.get("command"), str):
        raise ValueError("each review operation needs a literal command and working directory.")
    cwd, kind, args, ctx = git_review_command(request["command"], request.get("cwd") or os.getcwd())
    return commit_snapshot(cwd, args, ctx) if kind == "commit" else push_snapshot(cwd, args, commits)


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
    if len(commits) == 1 and len(pushes) <= 1 and all(op["fromCommit"] for op in pushes):
        op, n = commits[0], len(commits[0]["files"])
        subject = (op["message"].splitlines() or [""])[0].strip()
        if ja:
            tail = "に記録し、{} に送るか".format(target_text) if pushes else "に記録するか"
            decision = fit_subject(lambda s: "コミット「{}」（{} ファイル）を {} {}".format(s, n, branch(op), tail), subject)
        else:
            tail = " and push it to {}?".format(target_text) if pushes else "?"
            decision = fit_subject(lambda s: 'Record commit "{}" ({}) on {}{}'.format(s, counted(n, "file"), branch(op), tail),
                                   subject)
    elif not commits and len(pushes) == 1:
        sha = (pushes[0]["commit"] or "")[:SHORT_SHA_LENGTH]
        decision = "{} を {} に送るか".format(sha, target_text) if ja else "Push {} to {}?".format(sha, target_text)
    else:
        k, m = len(commits), len(pushes)
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
               "dependent": "この確認案の変更内容とメッセージで作成するコミット"} if ja else
              {"heading": "Git review", "commit": "Commit", "push": "Push", "branch": "Branch", "base": "Base",
               "initial": "initial commit", "message": "Message", "files": "Files", "diff": "Full diff",
               "remote": "Remote", "destination": "Destination", "source": "Commit",
               "dependent": "the commit created from this same reviewed set"})
    lines = ["# " + labels["heading"] + " G-" + record["id"], "", question["title"], ""]
    for i, op in enumerate(record["operations"], 1):
        where = "{} ({})".format(op["workTree"], op["gitDir"]) if op.get("gitDir") else op["repo"]
        lines += ["## {}. {} — {}".format(i, labels[op["kind"]], where), ""]
        if op["kind"] == "commit":
            lines += [labels["branch"] + ": " + op["branch"], labels["base"] + ": " + (op["head"] or labels["initial"]),
                      "", labels["message"] + ":", "", *["> " + line for line in op["message"].splitlines()], "", labels["files"] + ":", ""]
            lines += ["- {} {}".format(status, json.dumps(path, ensure_ascii=False)) for status, path in op["files"]]
            lines += ["", "[" + labels["diff"] + "](<" + str(directory / (str(i) + ".patch")) + ">)", ""]
        else:
            lines += [labels["remote"] + ": {} ({})".format(op["remote"], op["displayUrl"]),
                      labels["destination"] + ": " + op["destination"],
                      labels["source"] + ": " + (op["commit"] or labels["dependent"]), ""]
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
        op, patch = snapshot_operation(request, commits)
        if op in operations or op["kind"] == "commit" and any(c["repo"] == op["repo"] for c in commits):
            raise ValueError("review one commit per repository, and no duplicate operations.")
        if op["kind"] == "commit":
            commits.append(op)
        operations.append(op)
        patches.append(patch)
    record = {"version": 1, "runtime": runtime, "language": data.get("language", "en"),
              "nonce": secrets.token_hex(NONCE_BYTES), "createdAt": time.time(), "operations": operations}
    record["id"] = review_hash(record)[:ID_HEX_LENGTH]
    directory = review_directory() / record["id"]
    directory.mkdir(parents=True, mode=0o700, exist_ok=False)
    for i, patch in enumerate(patches, 1):
        if patch:
            (directory / (str(i) + ".patch")).write_bytes(patch)
    (directory / "report.md").write_text(review_report(record, directory), encoding="utf-8")
    (directory / "review.json").write_text(review_json(record) + "\n", encoding="utf-8")
    return {"reviewId": "G-" + record["id"], "report": str(directory / "report.md"),
            "question": review_question(record), "nativeRequest": native_git_request(record)}


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
    """The question and the host's native request for a prepared decision report: five lines, and a sixth,
    generated from the grant, when the report carries one. The first five keep their positions."""
    values = [record[key] for key in REPORT_LINE_KEYS] + ["R-" + record["id"], str(path)]
    question = question_text(record["language"], values)
    if record["grant"]:
        label = GRANT_LABELS["ja" if is_japanese(record["language"]) else "en"][0]
        question += "\n" + label + ": " + grant_line(record["language"], record["grant"])
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
    record = {"version": REPORT_VERSION, "runtime": runtime, "language": language,
              "nonce": secrets.token_hex(NONCE_BYTES), "createdAt": created,
              **{key: data[key] for key in REPORT_LINE_KEYS},
              "options": report_options(language, data.get("options")), "multiSelect": multi,
              "detailHash": hashlib.sha256(detail.encode("utf-8")).hexdigest(), "grant": grant, "projectKey": project}
    record["id"] = review_hash(record)[:ID_HEX_LENGTH]
    directory = report_directory() / record["id"]
    question, request = report_question(record, directory / "report.md")
    # Without a grant the file keeps its bytes: the question, a blank line, the detail.
    text = (report_head(record, question) + detail + ("" if detail.endswith("\n") else "\n")).encode("utf-8")
    directory.mkdir(parents=True, mode=0o700, exist_ok=False)
    (directory / "report.md").write_bytes(text)
    record.update(question=question, nativeRequest=request, reportHash=hashlib.sha256(text).hexdigest())
    (directory / "report.json").write_text(review_json(record) + "\n", encoding="utf-8")
    return {"reportId": "R-" + record["id"], "report": str(directory / "report.md"), "question": question,
            "nativeRequest": request}


def report_head(record, question):
    """What the gate writes at the top of report.md: the question and, for a grant, its block; the detail follows."""
    block = grant_block(record["language"], record["grant"]) + "\n\n" if record["grant"] else ""
    return question + "\n\n" + block


def load_report(report_id, runtime=None):
    """The prepared report record; ValueError when it, its question, or report.md was changed or is foreign.

    `runtime` None accepts either host's report (the Run subcommands read it outside a hook)."""
    directory = report_directory() / report_id
    record = json.loads((directory / "report.json").read_text(encoding="utf-8"))
    core = {key: record[key] for key in REPORT_CORE_KEYS}
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
        if op["kind"] == "commit" and hashlib.sha256((directory / (str(i) + ".patch")).read_bytes()).hexdigest() != op["patchHash"]:
            raise ValueError("the reviewed diff was changed after preparation.")
    return record


def approved_report_grant(runtime, payload):
    """The prepared report whose grant the human approved, proved like a Git review: from the question and
    its answer. ValueError says what is missing.

    The latest human input must be the submitted choice (never an idle timeout, a receipt or typed text) of
    the first option of the unchanged prepared question, for a report that carries a grant, is not older
    than the session's epoch, and has not expired. The proof records a grant; it permits nothing."""
    proof = native_git_choice(runtime, payload.get("transcript_path"))
    if not proof:
        raise ValueError("no submitted native answer to a prepared report question is recorded.")
    request, answer = proof
    questions = request.get("questions", []) if isinstance(request, dict) else []
    if len(questions) != 1:
        raise ValueError("a grant needs one whole-plan native question.")
    ident = question_id(asked_question(runtime, request))
    if not ident or ident[0] != "R":
        raise ValueError("the choice is not for a prepared report.")
    record = load_report(ident[1], runtime)
    if request != record["nativeRequest"]:
        raise ValueError("the question does not match the prepared report.")
    if not record["grant"] or record["multiSelect"]:
        raise ValueError("the report carries no grant.")
    if answer != record["options"][0]["label"]:
        raise ValueError("the selected option does not approve the plan.")
    if predates_epoch(payload.get("session_id"), record["createdAt"]):
        raise ValueError("the report predates the latest user message, resume or compaction.")
    validated_grant(record["grant"], time.time())  # a record written by hand passes no weaker check; expiry included
    return record


def matches_created_commit(op, cwd, oid):
    data = git_read(cwd, "cat-file", "commit", oid)
    header, message = data.split(b"\n\n", 1)
    parents = [line.split(b" ", 1)[1].decode() for line in header.splitlines() if line.startswith(b"parent ")]
    return parents == ([op["head"]] if op["head"] else []) and message.decode("utf-8") == op["message"] \
        and git_tree_fingerprint(cwd, oid) == op["tree"]


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
        current, _ = snapshot_operation({"command": command, "cwd": cwd}, commits)
        if current not in record["operations"]:
            raise ValueError("the Git contents, message, branch, or destination differ from the approved set.")
        if current["kind"] == "push" and current["fromCommit"]:
            source = git_text(current["cwd"], "rev-parse", "--verify", current["source"] + "^{commit}")
            commit = next(op for op in commits if review_hash(op) == current["fromCommit"])
            if not matches_created_commit(commit, current["cwd"], source):
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
        return ident is not None, ident
    return False, None


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
            for record in grant_records(project_key(ledger_root(decision))):
                print("Grant: " + grant_summary(record, "en"))
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


def ledger_event(root, runtime, session, kind, ts=None, **fields):
    """Append one event line to `<root>/.ddl/events.jsonl`; fields that are None are left out.

    It never raises and prints nothing: a failed write loses the line and changes no decision. One
    `os.write` per line on an O_APPEND descriptor, no lock, so concurrent hooks interleave whole lines.
    Two installs can each write the same hook event; a reader counts one kind, id and toolUseId once."""
    try:
        if not root:
            return
        line = {"v": EVENT_VERSION, "ts": ts or utc_stamp(), "host": runtime, "session": session, "kind": kind}
        for key, value in fields.items():
            if value is not None:
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
    record = approved_report_grant(runtime, payload)
    key = project_key(root)
    if "R-" + record["id"] != ident:
        raise ValueError("the latest submitted answer is for another question.")
    if not key or record["projectKey"] != key:
        raise ValueError("the report was prepared in another project.")
    return {"id": ident, "projectKey": key, "root": root, "grant": record["grant"],
            "approvedAt": approved_at or utc_stamp(), "session": payload.get("session_id"), "host": runtime}


def store_grant(body):
    """Write one grant record, once: `<store>/<project key>/grants/R-<id>.json`. False when the record is
    there already (it is never rewritten); OSError when the store cannot take it.

    The record appears whole or not at all: a private temporary file beside it is linked to its name, and
    the link fails when the name is taken. A file at that name that is no grant record (an empty one that
    an interrupted write left) is replaced. Later stages keep their use log under `uses/`, beside
    `grants/`; nothing is created there now."""
    path = grant_file(body["projectKey"], body["id"])
    if read_grant(path, body["id"]):
        return False
    directory = grant_store()
    for part in (None, body["projectKey"], "grants"):
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
            if read_grant(path, body["id"]):
                return False  # another gate process recorded the same approval a moment ago
            os.replace(scratch, path)
        return True
    finally:
        try:
            os.unlink(scratch)
        except OSError:
            pass  # the replacement above took it


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
    so they do not turn a dynamic command into a statically checkable one.
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
        hit = next((record["id"] for record in grants
                    if any(glob_matches(glob, parts) for glob in record["grant"]["paths"])), None)
        if hit is None:
            miss = miss or "/".join(parts)
        ids.append(hit)
    if miss:
        return refused(note, "grant-paths", grants, OUTSIDE_PATHS.format(miss, names))
    return None if host else allowed(note, ids, ["edit"])


def shell_grant(command, cwd, place, grants, note):
    """The grant's answer to a shell command (the protocol's Run Operation step 1 and Formats), or None."""
    if not isinstance(command, str) or not command.strip():
        return None
    names, root = ", ".join(record["id"] for record in grants), place.root
    if shell_is_read_only(command)[0]:
        return allowed(note, [grants[0]["id"]], ["read"])
    if not place.usable(os.path.realpath(cwd)):
        return None  # a command class, a gate subcommand: only from a working directory inside the root
    check = granting(grants, "check")
    if check and command_lines(command) in validation_commands(place.project, root) and not exit_word(command):
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
    cwds, kinds, ids, host, segments = [cwd], [], [], False, 0

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
            if not any(machine in record["grant"]["machines"] for record in grants):
                return refused(note, "grant-machine", grants, OUTSIDE_MACHINE.format(machine, names))
            word = exit_word(" ".join(remote))
            if word:
                return refused(note, "ssh-exit", grants, EXIT_BEHIND_SSH.format(word))
            classes = ("remote-run",)
        elif segment_is_read_only(raw_segment, masked):
            continue
        else:
            form = segment_class(tokens, is_gate)
            if not form:
                host = True
                continue
            classes, words, strict, guarded, modules = form
            if not all(module_inside(name, cwds, place) for name in modules):
                host = True
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


def grant_decision(runtime, payload, project, note):
    """The active grants' answer to a call while no STOP is pending: an allow, a deny, or None (the host's)."""
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
    return shell_grant(shell_command(payload.get("tool_input")), cwd, place, grants, note)


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
    del note["rule"]
    note["asked"] = {"id": label, "options": option_labels(expected), "grant": kind == "R" and bool(record["grant"])}
    return None  # the prepared question; the host's own policy still applies


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
                if block.get("type") == "tool_use" and block.get("name") in QUESTION_TOOLS["claude"] \
                        and question_id(asked_question("claude", block.get("input"))) == ident:
                    result = results.get(block.get("id"))
                    if result is None:
                        return None
                    close = claude_question_close(result)
                    return {"toolUseId": block.get("id"), "label": close[0], "timeout": close[1],
                            "ts": result.get("timestamp")} if close else False
    return None


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
    the approving answer of a grant either `granted` or a `warn` that names why no record follows.

    The warning's rule is `grant-proof` when the record does not prove the approval and `grant-store` when
    the store could not take the record. Nothing is retried: the question is closed either way."""
    session, ident = payload.get("session_id"), armed["id"]
    labels, label, seconds = armed.get("options") or [], close["label"], iso_seconds(close["ts"])
    stamp = None if seconds is None else utc_stamp(seconds)  # the host's own time of the answer, when it wrote one
    choice = labels.index(label) if label in labels else None
    if not armed.get("answered"):
        ledger_event(root, runtime, session, "answered", ts=stamp, id=ident, toolUseId=close["toolUseId"],
                     choice=choice, label=label, timeout=close["timeout"])
    if not armed.get("grant") or choice != 0 or close["timeout"]:
        return
    rule = "grant-proof"
    try:
        body = proved_grant(runtime, payload, root, ident, stamp)
        rule = "grant-store"
        written = store_grant(body)
    except Exception:
        key = project_key(root)
        if not key or not read_grant(grant_file(key, ident), ident):  # an earlier approval's record is no loss
            ledger_event(root, runtime, session, "warn", id=ident, rule=rule, toolUseId=close["toolUseId"])
        return
    if written:
        ledger_event(root, runtime, session, "granted", id=ident, toolUseId=close["toolUseId"])


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
    elif asked:
        ledger_event(root, runtime, session, "asked", id=asked["id"], **call)
        # Behind the questions that have not closed: a record that lags must not cost an earlier question its
        # answer. Asked again, a question takes its new call's place.
        waiting = [entry for entry in armed_questions(session) if entry["id"] != asked["id"]]
        arm(session, waiting + [dict(asked, toolUseId=call["toolUseId"])])
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


def decide_call(runtime, payload, project, note):
    """tool_decision's answer before the sandbox check."""
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
            note.update(rule="stop", id=pending["id"] if pending else None)
            reason = WAITING_REASON.format(pending["id"], pending["report"]) if pending else DENY_REASON
            return deny(reason + (" Shell segment is not read-only: `{}`.".format(segment) if segment else ""))
    if git_review is not None:
        if verdict(git_review) != "allow":
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
    if state is None:
        warned = session_file(payload.get("session_id"), ".warned")
        if warned.exists():
            return None  # warn once per session; the rule still holds by instruction
        warned.write_text(str(time.time()))
        note["rule"] = "unreadable-record"
        return {"systemMessage": UNREADABLE}
    # An OPEN record: the active grants answer for what they classify; everything else is the host's.
    return grant_decision(runtime, payload, project, note)


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
    ledger_event(root, runtime, session, "answered", id=label, toolUseId=reply[0], choice=choice, label=reply[2],
                 timeout=False)
    if choice != 0:
        disarm(session)  # any other reply moved the epoch, as typed text does
        return
    # The approving reply spared the epoch, so the other questions keep waiting. Its own question stays only
    # for a grant, which still needs its proof from the record at the next tool call; its line is done.
    armed = armed_questions(session)
    kept = [dict(entry, answered=True) if entry["id"] == label else entry
            for entry in armed if entry["id"] != label or entry.get("grant")]
    if kept != armed:
        arm(session, kept)


def handle_user_prompt_submit(runtime, payload):
    project = session_project(payload, refresh=True)
    if not project["ddl"]:
        return None
    marker_path(payload.get("session_id")).unlink(missing_ok=True)
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
            cli_event(runtime, "prepared", id=result["reportId"])
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
