#!/usr/bin/env python3
"""DDL gate: the mechanical half of the protocol's +++STOP rule, as a lifecycle hook.

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

prepare-report reads JSON {language, decision, recommendation, consequence, detail, options?,
multiSelect?, grant?} on stdin, writes report.md and report.json under `<state dir>/reports/<id>/`,
and prints {reportId, report, question, nativeRequest}. prepare-git-review reads JSON
{language: en|ja, operations: [{cwd, command}, ...]}, snapshots the staged changes and push
targets, writes review detail in the private state directory, and prints the same shape with
reviewId. Neither creates approval; invalid input prints `DDL STOP: …` / `DDL Git review: …` on
stderr and exits 2.

Grant, ledger and counts (recorded and reported; no hook decision reads any of them): a report
may carry a `grant` {paths, commands, machines, handover, budget {minutes, fixAttempts}, expires}.
It is hashed into the report ID with the project key, adds one generated line to the question and
a block to report.md, and is written once to the user-level store ($DDL_GATE_GRANT_DIR, else
$XDG_STATE_HOME/ddl-gate, else $HOME/.local/state/ddl-gate) as `<project key>/grants/R-<id>.json`
when the record proves that the human submitted the first option of the unchanged question; after
that only its expiry ends it. The record appears whole or not at all, and a file that does not parse
as that grant's record is no grant. In a DDL project the gate appends one JSON line per event to
`.ddl/events.jsonl` at the root of the main work tree (a silent pass writes nothing; an approved
grant that was not recorded leaves a `warn` line whose rule is `grant-proof` or `grant-store`),
`run-start` writes `.ddl/runs/<N-id>/run.json` from {report, items}, `run-item` sets one item's
status, and `report` prints four lines: questions, waiting, denials, grant. A Run's lines count its
plan's own question too, in the plan's language unless `--language` names one. A value that cannot
be derived is printed as `未計測` (`not measured`). The three subcommands take the project from the
working directory and exit 2 on a usage error.

Scope: the hook acts only in a DDL project, one whose instruction file (CLAUDE.md, .claude/CLAUDE.md
or AGENTS.md in the event's `cwd` or a parent, up to the directory holding `.git` and below $HOME)
contains the line `→ DDL-PROTOCOL` (`->` is accepted). Elsewhere every event returns at once, before
any transcript, marker or Git read. The decision is cached as `<state dir>/<session_id>.project`:
pre-tool-use and stop reuse it while `cwd` and the instruction file's mtime are unchanged;
user-prompt-submit and session-start recompute it. `status` prints the decision for a directory.
Only json, os and sys are imported up front; the other modules load on first use in a DDL project.

Decisions (JSON on stdout; the exit status is always 0):
  pre-tool-use        CLOSED and the tool may mutate -> permissionDecision "deny";
                      a question carrying an ID must equal the prepared request (else "deny"), and
                      while CLOSED a question without the pending ID is denied;
                      ordinary commit/push also needs a matching native content review while OPEN;
                      claude answers a reviewed ordinary push with "ask" (native confirmation)
                      codex also denies unsupported push forms in confirmation-enabled modes
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
behavior is outside this static check. Push form checks do not inspect arbitrary scripts or aliases,
never rewrite a command, and never emit an affirmative permission grant.
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

EVENTS = ("pre-tool-use", "session-start", "stop", "user-prompt-submit")
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
PUSH_FORM_REASON = ("DDL gate: this Git push form does not reliably reach Codex's native git push confirmation. "
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
PUSH_ASK_REASON = "DDL Git review: confirm the reviewed push natively."
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
# handed-over data it may use, its budget and its expiry. This stage records and reports it; no
# decision of the hook reads a grant, a ledger line or a Run.
GRANT_KEYS = ("paths", "commands", "machines", "handover", "budget", "expires")
GRANT_COMMANDS = ("build", "test", "check", "snapshot", "remote-run")
GRANT_LISTS = {"paths": (1, 32), "commands": (0, 8), "machines": (0, 8), "handover": (0, 8)}  # entries per list
GRANT_BUDGET = {"minutes": (1, 10080), "fixAttempts": (0, 10)}
GRANT_NAME_LIMIT = 80  # characters of one machine or handed-over entry
# The question's extra line, then the three lines of the block in report.md.
GRANT_LABELS = {"ja": ("許諾", "範囲", "予算", "期限"), "en": ("Grant", "Scope", "Budget", "Expiry")}
PROJECT_KEY_LENGTH = 16  # hex digits of the SHA-256 of the resolved ledger root
LEDGER = ".ddl"  # at the root of the main work tree; it ignores itself
EVENT_VERSION = 1
EVENT_TEXT_LIMIT = 200  # characters kept of a label, tool name or rule in one ledger line
ARMED_LIMIT = 8  # prepared questions one session keeps waiting for their answers; past it the oldest is let go
RUN_ID_BYTES = 6  # a Run ID is N- and these random bytes in hex
RUN_ID = _Pattern("RUN_ID", r"N-[0-9a-f]{%d}" % (2 * RUN_ID_BYTES))
ITEM_ID = _Pattern("ITEM_ID", r"[A-Za-z0-9][A-Za-z0-9._-]{0,31}")
ITEM_KEYS = {"id", "kind", "files", "after"}
ITEM_KINDS = ("write", "verify", "explore", "compute")
ITEM_STATUSES = ("ready", "running", "done", "failed", "dropped")
MAX_RUN_ITEMS = 200
# A timestamp the gate reads: date, `T`, time to the minute or finer, then `Z` or `±HH:MM` (group 8, optional
# here so that the caller can tell a missing offset from a malformed value).
ISO_TIME = _Pattern("ISO_TIME", r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,9}))?)?"
                                r"(Z|[+-]\d{2}:\d{2})?")
# The four count lines of `report`: labels, then the body of each line.
COUNT_TEXT = {
    "ja": {"labels": ("問い", "待ち", "拒否", "許諾"), "asked": "{} 件（承認 {}、見直し {}、時間切れ {}）",
           "waiting": "人間 {}（答えまで中央値 {}、最長 {}）", "minutes": "{} 分", "denied": "{} 件",
           "grant": "{}（期限 {}、{}）", "valid": "有効", "expired": "期限切れ", "none": "なし", "unmeasured": "未計測"},
    "en": {"labels": ("Questions", "Waiting", "Denials", "Grant"), "asked": "{} (approved {}, revised {}, timed out {})",
           "waiting": "human {} (median to answer {}, longest {})", "minutes": "{} min", "denied": "{}",
           "grant": "{} (expires {}, {})", "valid": "valid", "expired": "expired", "none": "none",
           "unmeasured": "not measured"}}
REPORT_FLAGS = ("--transcript", "--runtime", "--session", "--run", "--language")
REPORT_USAGE = ("usage: ddl_gate.py report (--transcript FILE --runtime claude|codex | --session ID | --run N-ID) "
                "[--language ja|en]")
RUN_USAGE = "usage: ddl_gate.py run-start (JSON on stdin) | run-item <N-id> <item id> <status>"


def review_json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def review_hash(value):
    return hashlib.sha256(review_json(value).encode()).hexdigest()


def review_directory():
    return session_file("git-reviews", "").with_suffix("")


def git_read(cwd, *args, input_data=None, optional=False):
    """Bounded Git plumbing reads; do not invoke a pager, fsmonitor, replacement, or external diff."""
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0")
    timeout = min(5, _git_review_deadline - time.monotonic()) if _git_review_deadline else 5
    if timeout <= 0:
        raise TimeoutError("the Git review could not be verified within its hook time budget.")
    proc = subprocess.run(["git", "--no-pager", "--no-replace-objects", "-c", "core.fsmonitor=false",
                           "-C", str(cwd), *args], input=input_data, capture_output=True, env=env, timeout=timeout)
    if proc.returncode and not optional:
        raise ValueError("could not inspect Git state ({}).".format(args[0]))
    return proc.stdout if not proc.returncode else None


def git_text(cwd, *args, optional=False):
    data = git_read(cwd, *args, optional=optional)
    return None if data is None else data.decode("utf-8", "surrogateescape").strip()


def git_review_command(command, cwd):
    """Parse the narrow executable forms supported by a review, never rewrite the attempted call."""
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
    here = pathlib.Path(cwd).resolve(strict=True)
    while args and args[0].startswith("-"):
        flag = args.pop(0)
        if flag == "-C" and args:
            here = (here / args.pop(0)).resolve(strict=True)
        elif flag.startswith("-C") and len(flag) > 2:
            here = (here / flag[2:]).resolve(strict=True)
        elif flag not in ("--no-pager", "--no-optional-locks", "--no-replace-objects"):
            raise ValueError("this Git global option is not supported by a content review: {}.".format(flag))
    if not args or args[0] not in ("commit", "push"):
        raise ValueError("only ordinary commit and push operations are reviewable; low-level equivalents are denied.")
    for key in os.environ:
        if key in {"GIT_INDEX_FILE", "GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_OBJECT_DIRECTORY",
                   "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_NAMESPACE", "GIT_CONFIG", "GIT_CONFIG_PARAMETERS"} \
                or key.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_")):
            raise ValueError("an ambient Git context override prevents a reliable review: {}.".format(key))
    return here, args[0], args[1:]


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


def git_tree_fingerprint(cwd, commit=None):
    cwd = git_repo(cwd)
    args = ("ls-tree", "--full-tree", "-r", "-z", commit) if commit else ("ls-files", "--full-name", "--stage", "-z")
    rows = []
    for row in git_read(cwd, *args).split(b"\0"):
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


def git_repo(cwd):
    return str(pathlib.Path(git_text(cwd, "rev-parse", "--show-toplevel")).resolve())


def commit_snapshot(cwd, args):
    repo = git_repo(cwd)
    git_dir = pathlib.Path(git_text(cwd, "rev-parse", "--absolute-git-dir"))
    if any((git_dir / name).exists() for name in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge", "rebase-apply")):
        raise ValueError("finish the merge, rebase, cherry-pick, or revert before an ordinary commit review.")
    encoding = git_text(cwd, "config", "--get", "i18n.commitEncoding", optional=True)
    if encoding and encoding.lower().replace("-", "") != "utf8":
        raise ValueError("the ordinary review supports UTF-8 commit messages.")
    branch = git_text(cwd, "symbolic-ref", "--quiet", "HEAD", optional=True)
    if not branch:
        raise ValueError("review commits on a named branch; detached HEAD is not supported.")
    raw_args = ("diff", "--cached", "--no-relative", "--raw", "--no-ext-diff", "--no-textconv", "--no-renames")
    if git_read(repo, *raw_args, "--ita-visible-in-index") != git_read(repo, *raw_args, "--ita-invisible-in-index"):
        raise ValueError("fully stage or remove intent-to-add entries before reviewing the index.")
    patch = git_read(repo, "diff", "--cached", "--no-relative", "--binary", "--no-ext-diff", "--no-textconv", "--no-renames")
    if not patch:
        raise ValueError("stage the proposed files before preparing the review; the index is empty.")
    names = git_read(repo, "diff", "--cached", "--no-relative", "--name-status", "-z", "--no-renames").split(b"\0")
    files = [[names[i].decode(), names[i + 1].decode("utf-8", "surrogateescape")]
             for i in range(0, len(names) - 1, 2)]
    return {"kind": "commit", "repo": repo, "branch": branch,
            "head": git_text(cwd, "rev-parse", "--verify", "HEAD", optional=True),
            "tree": git_tree_fingerprint(cwd), "message": git_message(args, cwd),
            "files": files, "patchHash": hashlib.sha256(patch).hexdigest()}, patch


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
    cwd, kind, args = git_review_command(request["command"], request.get("cwd") or os.getcwd())
    return commit_snapshot(cwd, args) if kind == "commit" else push_snapshot(cwd, args, commits)


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
    try:
        moment = datetime.datetime(*(int(match[i]) for i in range(1, 6)), int(match[6] or 0),
                                   tzinfo=datetime.timezone.utc)
    except ValueError:  # no such date or time of day
        return None
    return moment.timestamp() + (float("0." + match[7]) if match[7] else 0.0) - offset


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
        name = os.path.basename(op["repo"])
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
        repos = sep.join(unique(os.path.basename(op["repo"]) for op in commits))
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
        lines += ["## {}. {} — {}".format(i, labels[op["kind"]], op["repo"]), ""]
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


def git_review_guard(runtime, payload):
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
    if runtime == "claude" and current["kind"] == "push":
        return permission("ask", PUSH_ASK_REASON)  # the reviewed push is still confirmed natively
    return None  # retain the host's native permission policy; never grant permission


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
    return decision


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
    return hashlib.sha256(root.encode("utf-8", "surrogateescape")).hexdigest()[:PROJECT_KEY_LENGTH]


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


def ledger_lines(root):
    """The ledger's event objects, first to last; None when the project has no ledger file.

    A line that repeats the session, kind, id and toolUseId of an earlier one is the second install's copy
    of the same hook event and is dropped. Lines without a toolUseId cannot be told apart and all stay."""
    events, seen = [], set()
    try:
        fh = open(os.path.join(root, LEDGER, "events.jsonl"), encoding="utf-8", errors="replace")
    except OSError:
        return None
    with fh:
        for line in fh:
            try:
                event = json.loads(line)
            except ValueError:
                continue  # a torn or foreign line; the lines around it still count
            if not isinstance(event, dict) or event.get("v") != EVENT_VERSION:
                continue
            if event.get("toolUseId") is not None:
                key = json.dumps([event.get(name) for name in ("session", "kind", "id", "toolUseId")])
                if key in seen:
                    continue
                seen.add(key)
            events.append(event)
    return events


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

def split_segments(cmd):
    """Split a command on `&&`, `||`, `;`, `|`, `&` and newlines outside quotes.

    Returns (raw, masked) segment lists, or None when a quote is unbalanced. In the masked copy every
    quoted or escaped character is `x`, so later checks can look for operators without tracking quotes;
    indices line up with the raw segment."""
    raw, masked, cur_raw, cur_masked = [], [], [], []
    quote = None
    i, n = 0, len(cmd)

    def flush():
        raw.append("".join(cur_raw))
        masked.append("".join(cur_masked))
        del cur_raw[:], cur_masked[:]

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
            flush()
            i += 2
        elif ch in ";|\n" or (ch == "&" and not (cur_raw and cur_raw[-1] in "<>") and cmd[i + 1:i + 2] != ">"):
            flush()  # a lone `&` backgrounds a segment; `>&`, `<&` and `&>` are redirects, not separators
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
        if not raw.strip():
            continue
        if not redirects_are_harmless(raw, masked):
            return False, raw.strip()
        try:
            tokens = shlex.split(raw)
        except ValueError:
            return False, raw.strip()
        while tokens and os.path.basename(tokens[0]) == "env":
            tokens.pop(0)
        if tokens and (ASSIGNMENT.match(tokens[0]) or tokens[0].startswith("-")):
            return False, raw.strip()  # environment overrides can install execution helpers
        if not tokens:
            continue
        prog = os.path.basename(tokens[0])
        if prog not in READ_ONLY_PROGRAMS or not program_is_read_only(prog, strip_redirect_tokens(tokens[1:])):
            return False, raw.strip()
    return True, ""


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
    """The spellings of this gate's path that its own preparation call may use."""
    tokens = set()
    for path in {os.path.realpath(__file__), os.path.abspath(__file__), ".codex/hooks/ddl_gate.py"}:
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
    """The conservative subset the native policy can inspect as individual argv lists."""
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
    """Reject static Git pushes that cannot reliably reach the native exact-prefix rule.

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
            # A dynamic or unknown Git subcommand cannot be certified by the prefix rule.
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
    out = decision.get("hookSpecificOutput") if isinstance(decision, dict) else None
    verdict = out.get("permissionDecision") if isinstance(out, dict) else None
    asked = note.get("asked") if verdict is None else None
    # Look for the answers while the record is OPEN, and when a new question joins the asked ones. A call
    # that is denied or asked does not wait for that reading: the next call that passes looks.
    observe = verdict is None and (note.get("state") is False or bool(asked)) \
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
    if verdict in ("deny", "ask"):
        ledger_event(root, runtime, session, "denied" if verdict == "deny" else "ask", id=note.get("id"),
                     rule=note.get("rule"), **call)
    elif asked:
        ledger_event(root, runtime, session, "asked", id=asked["id"], **call)
        # Behind the questions that have not closed: a record that lags must not cost an earlier question its
        # answer. Asked again, a question takes its new call's place.
        waiting = [entry for entry in armed_questions(session) if entry["id"] != asked["id"]]
        arm(session, waiting + [dict(asked, toolUseId=call["toolUseId"])])
    if isinstance(decision, dict) and "systemMessage" in decision:
        ledger_event(root, runtime, session, "warn", rule=note.get("rule"), **call)


def tool_decision(runtime, payload, note):
    """The PreToolUse decision; `note` collects what the ledger records about it (state, rule, id, asked)."""
    git_review = git_review_guard(runtime, payload)
    try:
        state, pending = pending_scan(runtime, payload)
    except Exception:
        if git_review is not None:
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
        note["rule"] = "git-review"
        return git_review
    outward = push_guard(runtime, payload)
    if outward is not None:
        note["rule"] = "push-form"
        return outward
    if state is None:
        warned = session_file(payload.get("session_id"), ".warned")
        if warned.exists():
            return None  # warn once per session; the rule still holds by instruction
        warned.write_text(str(time.time()))
        note["rule"] = "unreadable-record"
        return {"systemMessage": UNREADABLE}
    return None  # never emit an affirmative allow that could replace the harness's decision


def handle_pre_tool_use(runtime, payload):
    project = session_project(payload)
    if not project["ddl"]:
        return None
    note = {}
    decision = tool_decision(runtime, payload, note)
    try:  # the ledger and the grant record come after the decision and never change it
        tool_note(runtime, payload, project, decision, note)
    except Exception:
        pass
    return decision


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


# --- counts and the Run -----------------------------------------------------------------------
# Subcommands, run outside a hook. They read what the hook recorded and the conversation record; nothing
# here is read back by a hook decision.

def question_outcome(labels, label, timeout):
    """`timeout`, `approved` (the first option was submitted) or `revised` (anything else was)."""
    return "timeout" if timeout else "approved" if labels and label == labels[0] else "revised"


def refused_by_hook(entry):
    """True when the host recorded that a hook refused the call: such a question was never shown."""
    decision = entry.get("permissionDecision")
    return isinstance(decision, dict) and decision.get("source") == "hook" and decision.get("decision") == "reject"


def claude_questions(path):
    """The questions that carry an ID in a Claude transcript, in order, each with the `timestamp` of the
    entry that holds its tool call and of the entry that holds its answer."""
    asked = {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if '"tool_' not in line:  # neither a tool call nor a tool result
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if not isinstance(entry, dict) or entry.get("isSidechain"):
                continue
            for block in entry_blocks(entry):
                if entry.get("type") == "assistant" and block.get("type") == "tool_use" \
                        and block.get("name") in QUESTION_TOOLS["claude"] and block.get("id") not in asked:
                    ident = question_id(asked_question("claude", block.get("input")))
                    if ident:
                        asked[block.get("id")] = {"id": "-".join(ident), "labels": option_labels(block.get("input")),
                                                  "asked": iso_seconds(entry.get("timestamp")), "outcome": None}
                elif entry.get("type") == "user" and block.get("type") == "tool_result":
                    question = asked.get(block.get("tool_use_id"))
                    if question is None or "closed" in question:
                        continue
                    question["closed"] = not refused_by_hook(entry)
                    close = claude_question_close(entry)
                    if close:
                        question.update(outcome=question_outcome(question["labels"], *close),
                                        answered=iso_seconds(entry.get("timestamp")))
    return [question for question in asked.values() if question.get("closed", True)]


def codex_questions(path):
    """Same for a Codex rollout: the line of the question's call and the line of its reply message, each
    with its top-level `timestamp` when the rollout writes one."""
    asked = {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            payload = entry.get("payload") if isinstance(entry, dict) else None
            if not isinstance(payload, dict):
                continue
            kind, ptype, item = entry.get("type"), payload.get("type"), payload.get("item")
            if kind == "response_item" and ptype == "function_call" and payload.get("name") in QUESTION_TOOLS["codex"] \
                    and payload.get("call_id") not in asked:
                text = asked_question("codex", payload.get("arguments"))
                ident = question_id(text)
                if ident:
                    asked[payload.get("call_id")] = {"id": "-".join(ident), "text": text, "outcome": None,
                                                     "labels": option_labels(payload.get("arguments")),
                                                     "asked": iso_seconds(entry.get("timestamp"))}
            elif kind == "event_msg" and ptype == "item_completed" and isinstance(item, dict) \
                    and item.get("type") == "UserMessage":
                reply = codex_git_reply(codex_text(item))
                question = asked.get(reply[0]) if reply else None
                if question and question["outcome"] is None and isinstance(reply[1], str) \
                        and reply[1].replace("\r\n", "\n") == question["text"].replace("\r\n", "\n"):
                    question.update(outcome=question_outcome(question["labels"], reply[2], False),
                                    answered=iso_seconds(entry.get("timestamp")))
    return list(asked.values())


def event_questions(events):
    """The questions in a selection of ledger events: each `asked` line, joined with the `answered` line of
    the same session, id and call (of the same id alone when the two hosts' call ids differ)."""
    questions, latest = [], {}
    for event in events:
        ident, kind = event.get("id"), event.get("kind")
        keys = [json.dumps([event.get("session"), ident, call]) for call in (event.get("toolUseId"), None)]
        if kind == "asked" and isinstance(ident, str):
            question = {"id": ident, "asked": iso_seconds(event.get("ts")), "outcome": None}
            questions.append(question)
            latest.update((key, question) for key in keys)
        elif kind == "answered":
            question = latest.get(keys[0]) or latest.get(keys[1])
            if question and question["outcome"] is None:
                question.update(answered=iso_seconds(event.get("ts")),
                                outcome="timeout" if event.get("timeout") else
                                "approved" if event.get("choice") == 0 else "revised")
    return questions


def count_lines(language, questions, denials, grant):
    """The four count lines. `questions` (each with outcome, asked, answered) and `denials` are None when the
    source cannot tell them; `grant` is a grant record, False for none, or None when it cannot be looked up.

    Waiting covers the submitted answers, from the question's call to its answer; a timeout is counted apart
    on the first line. Minutes are rounded to the nearest whole one. Nothing is estimated: a value that
    cannot be derived is printed as not measured."""
    text = COUNT_TEXT[language]
    unmeasured, asked, waiting = text["unmeasured"], text["unmeasured"], text["unmeasured"]

    def minutes(seconds):
        return text["minutes"].format(int((seconds + 30) // 60))

    if questions is not None:
        tally = [sum(q["outcome"] == key for q in questions) for key in ("approved", "revised", "timeout")]
        asked = text["asked"].format(len(questions), *tally)
        waits = [q["answered"] - q["asked"] if q.get("answered") is not None and q["asked"] is not None else None
                 for q in questions if q["outcome"] in ("approved", "revised")]
        if all(wait is not None and wait >= 0 for wait in waits):
            waits.sort()
            middle = len(waits) // 2
            # The median by hand: the middle value, or the mean of the two middle ones.
            median = waits[middle] if len(waits) % 2 else (waits[middle - 1] + waits[middle]) / 2 if waits else None
            waiting = text["waiting"].format(minutes(sum(waits)), minutes(median) if waits else unmeasured,
                                             minutes(waits[-1]) if waits else unmeasured)
    lines = [asked, waiting, unmeasured if denials is None else text["denied"].format(denials),
             unmeasured if grant is None else grant_summary(grant, language) if grant else text["none"]]
    return [label + ": " + line for label, line in zip(text["labels"], lines)]


def run_file(root, run_id):
    return os.path.join(root, LEDGER, "runs", run_id, "run.json")


def load_run(root, run_id):
    """The Run's record; ValueError when the ID is malformed or the project's ledger holds no such Run."""
    if not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id):
        raise ValueError("a Run ID is N- and 12 hexadecimal characters.")
    try:
        with open(run_file(root, run_id), encoding="utf-8") as fh:
            run = json.load(fh)
    except (OSError, ValueError, TypeError):
        run = None
    if not isinstance(run, dict) or run.get("id") != run_id or not isinstance(run.get("items"), list):
        raise ValueError("Run {} is not in this project's ledger.".format(run_id))
    return run


def ledger_runs(root):
    """Every readable Run of the ledger."""
    try:
        names = sorted(os.listdir(os.path.join(root, LEDGER, "runs")))
    except OSError:
        return []
    runs = []
    for name in names:
        try:
            runs.append(load_run(root, name))
        except ValueError:
            continue
    return runs


def report_command(argv):
    """`report`: the four count lines for a conversation record, a session's ledger events, or a Run.

    A Run's events are those the ledger dates from its start until the next Run of the project starts, and
    those that carry the ID of its plan's report whenever they were written: the plan is asked and answered
    before its Run starts. Without `--language` a Run's lines are in its plan's language (Japanese for a
    Japanese code and for a Run that names none, English for any other); the other two default to Japanese."""
    options, rest = {}, list(argv)
    while rest:
        name, equal, value = rest.pop(0).partition("=")
        if name not in REPORT_FLAGS or name in options or not (equal or rest):
            raise ValueError(REPORT_USAGE)
        options[name] = value if equal else rest.pop(0)
    modes = [name for name in ("--transcript", "--session", "--run") if name in options]
    given, runtime = options.get("--language"), options.get("--runtime")
    if len(modes) != 1 or given not in (None, *COUNT_TEXT) or runtime not in (None,) + RUNTIMES \
            or (modes[0] == "--transcript" and runtime is None) or not options[modes[0]]:
        raise ValueError(REPORT_USAGE)
    mode, value, language = modes[0], options[modes[0]], given or "ja"
    if mode == "--transcript":
        try:
            questions = (codex_questions if runtime == "codex" else claude_questions)(value)
        except OSError:
            return count_lines(language, None, None, None)  # an unreadable record: nothing can be derived
        asked = {question["id"] for question in questions}
        grants = [record for record in grant_records() if record["id"] in asked]
        # A record shows no gate decision the gate can tell from another hook's, so denials are not counted here.
        return count_lines(language, questions, None, grants[-1] if grants else False)
    if mode == "--run" and not RUN_ID.fullmatch(value):
        raise ValueError(REPORT_USAGE)
    root, key = cwd_ledger()
    if not root and mode == "--run":
        raise ValueError("Run {} needs its DDL project as the working directory.".format(value))
    if not root:
        return count_lines(language, None, None, None)
    events = ledger_lines(root)
    if mode == "--session":
        chosen = None if events is None else [event for event in events if event.get("session") == value]
        grants = [record for record in grant_records(key) if record.get("session") == value]
    else:
        run = load_run(root, value)
        if given is None and isinstance(run.get("language"), str) and not is_japanese(run["language"]):
            language = "en"
        plan, start = run.get("report"), iso_seconds(run.get("startedAt"))
        later = [moment for moment in (iso_seconds(other.get("startedAt")) for other in ledger_runs(root))
                 if moment is not None and start is not None and moment > start]
        end = min(later) if later else None

        def of_run(event):  # dated within the Run, or about its plan's report; each ledger line is seen once
            moment = iso_seconds(event.get("ts"))
            return (isinstance(plan, str) and event.get("id") == plan) or (
                moment is not None and moment >= start and (end is None or moment < end))

        chosen = None if events is None or start is None else [event for event in events if of_run(event)]
        grants = [record for record in grant_records(key) if record["id"] == plan]
    if chosen is None:
        return count_lines(language, None, None, grants[-1] if grants else False)
    return count_lines(language, event_questions(chosen), sum(event.get("kind") == "denied" for event in chosen),
                       grants[-1] if grants else False)


def run_items(items):
    """The items of a new Run, each with `status: "ready"`; ValueError names the first problem."""
    if not isinstance(items, list) or len(items) > MAX_RUN_ITEMS:
        raise ValueError("items must be a list of at most {} items.".format(MAX_RUN_ITEMS))
    out = []
    for item in items:
        if not isinstance(item, dict) or not {"id", "kind"} <= set(item) <= ITEM_KEYS:
            raise ValueError("each item is {id, kind, files?, after?}.")
        if not isinstance(item["id"], str) or not ITEM_ID.fullmatch(item["id"]):
            raise ValueError("an item id is 1 to 32 letters, digits, dots, hyphens or underscores, such as I1.")
        if item["kind"] not in ITEM_KINDS:
            raise ValueError("item {}: kind must be one of {}.".format(item["id"], ", ".join(ITEM_KINDS)))
        lists = {key: item.get(key, []) for key in ("files", "after")}
        for key, values in lists.items():
            if not isinstance(values, list) or not all(one_line(value) for value in values) \
                    or len(set(values)) != len(values):
                raise ValueError("item {}: {} must be a list of different one-line strings.".format(item["id"], key))
        out.append({"id": item["id"], "kind": item["kind"], **lists, "status": "ready"})
    ids = [item["id"] for item in out]
    if len(set(ids)) != len(ids):
        raise ValueError("item ids must differ.")
    for item in out:
        if item["id"] in item["after"] or not set(item["after"]) <= set(ids):
            raise ValueError("item {}: after names other items of this Run.".format(item["id"]))
    ended = set()
    while len(ended) < len(out):  # every item must be reachable in dependency order
        free = [item["id"] for item in out if item["id"] not in ended and set(item["after"]) <= ended]
        if not free:
            raise ValueError("the after relations form a cycle.")
        ended.update(free)
    return out


def run_start(data, runtime=None):
    """`run-start`: write `.ddl/runs/<N-id>/run.json` for one approved plan's report and print {run, path}.

    The Run names the grant only when the store holds that grant's record, and keeps the plan's language,
    in which `report --run` prints. It is a record for people and reports. No hook reads it: an item's
    `done` is never a gate pass."""
    if not isinstance(data, dict) or set(data) != {"report", "items"}:
        raise ValueError("send one JSON object with report and items.")
    match = PREPARED_ID.fullmatch(data["report"]) if isinstance(data["report"], str) else None
    if not match or match[1] != "R":
        raise ValueError("report must be a prepared report ID such as R-0123456789abcdef.")
    items = run_items(data["items"])
    root, key = cwd_ledger()
    if not root:
        raise ValueError("a Run belongs to a DDL project; start it from inside the project.")
    try:
        record = load_report(match[2], runtime)
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        raise ValueError("report {} is not prepared here ({}).".format(data["report"], exc)) from None
    if record["projectKey"] != key:
        raise ValueError("report {} was prepared in another project.".format(data["report"]))
    for run in ledger_runs(root):
        if run.get("report") == data["report"]:  # one Run per approved plan, also after a compaction or restart
            raise ValueError("report {} already started Run {} ({}).".format(
                data["report"], run["id"], run_file(root, run["id"])))
    granted = read_grant(grant_file(key, data["report"]), data["report"]) is not None
    os.makedirs(os.path.join(ledger_directory(root), "runs"), exist_ok=True)
    while True:
        run_id = "N-" + secrets.token_hex(RUN_ID_BYTES)
        try:
            os.mkdir(os.path.dirname(run_file(root, run_id)))
            break
        except FileExistsError:
            continue
    run = {"id": run_id, "report": data["report"], "grant": data["report"] if granted else None,
           "language": record["language"], "startedAt": utc_stamp(), "items": items}
    with open(run_file(root, run_id), "w", encoding="utf-8") as fh:
        fh.write(json.dumps(run, ensure_ascii=False, indent=2) + "\n")
    ledger_event(root, record["runtime"], None, "prepared", id=run_id, run=run_id)
    return {"run": run_id, "path": run_file(root, run_id)}


def run_item(argv):
    """`run-item <N-id> <item id> <status>`: set one item's status in the Run's record and print it."""
    if len(argv) != 3:
        raise ValueError(RUN_USAGE)
    run_id, item_id, status = argv
    if status not in ITEM_STATUSES:
        raise ValueError("status must be one of {}.".format(", ".join(ITEM_STATUSES)))
    root, _ = cwd_ledger()
    if not root:
        raise ValueError("a Run belongs to a DDL project; run this from inside the project.")
    run = load_run(root, run_id)
    item = next((item for item in run["items"] if isinstance(item, dict) and item.get("id") == item_id), None)
    if item is None:
        raise ValueError("Run {} has no item {}.".format(run_id, item_id))
    item["status"] = status
    path = run_file(root, run_id)
    scratch = "{}.{}.tmp".format(path, os.getpid())
    with open(scratch, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(run, ensure_ascii=False, indent=2) + "\n")
    os.replace(scratch, path)  # readers see the old record or the new one, never half of one
    return {"run": run_id, "item": item_id, "status": status}


HANDLERS = {"pre-tool-use": handle_pre_tool_use, "session-start": handle_session_start, "stop": handle_stop,
            "user-prompt-submit": handle_user_prompt_submit}


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


def main(argv) -> int:
    if argv and argv[0] == "status":
        return project_status(argv[1:])
    if argv and argv[0] == "report":
        try:
            lines = report_command(argv[1:])
            sys.stdout.buffer.write(("\n".join(lines) + "\n").encode("utf-8"))  # whatever the locale's encoding
            sys.stdout.flush()
            return 0
        except Exception as exc:
            print("DDL report: " + str(exc), file=sys.stderr)
            return 2
    if argv and argv[0] in ("run-start", "run-item"):
        try:
            if argv[0] == "run-item":
                emit(run_item(argv[1:]))
                return 0
            runtime = None
            if argv[1:]:  # optional, and then it must be the report's own runtime
                _, runtime, problem = parse_args(["session-start", *argv[1:]])
                if problem:
                    raise ValueError(RUN_USAGE)
            try:
                data = json.loads(sys.stdin.read())
            except ValueError as exc:
                raise ValueError("the input is not JSON ({}).".format(exc)) from None
            emit(run_start(data, runtime))
            return 0
        except Exception as exc:
            print("DDL run: " + str(exc), file=sys.stderr)
            return 2
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
