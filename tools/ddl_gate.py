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

prepare-report reads JSON {language, decision, recommendation, consequence, detail, options?,
multiSelect?} on stdin, writes report.md and report.json under `<state dir>/reports/<id>/`, and
prints {reportId, report, question, nativeRequest}. prepare-git-review reads JSON
{language: en|ja, operations: [{cwd, command}, ...]}, snapshots the staged changes and push
targets, writes review detail in the private state directory, and prints the same shape with
reviewId. Neither creates approval; invalid input prints `DDL STOP: …` / `DDL Git review: …` on
stderr and exits 2.

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
the unreadable-record warning appear once per session; the state dir is $DDL_GATE_STATE_DIR,
else $TMPDIR/ddl-gate, else /tmp/ddl-gate. Wire all four events, or the marker is never cleared.

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


hashlib, pathlib, re, secrets, shlex, shutil, subprocess, time = (
    _Lazy(name) for name in ("hashlib", "pathlib", "re", "secrets", "shlex", "shutil", "subprocess", "time"))
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
REPORT_VERSION = 1  # the report.json schema; a change of fields bumps it
REPORT_INPUT_KEYS = {"language", "decision", "recommendation", "consequence", "detail", "options", "multiSelect"}
REPORT_LINE_KEYS = ("decision", "recommendation", "consequence")
# The fields the report ID hashes; report.json adds id, question, nativeRequest and reportHash.
REPORT_CORE_KEYS = ("version", "runtime", "language", "nonce", "createdAt", *REPORT_LINE_KEYS,
                    "options", "multiSelect", "detailHash")
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
# A tool output wraps the gate's JSON in at most a few envelopes (a JSON `output` field, a content list,
# an `Output:` section); deeper nesting is not the gate's own output.
ENVELOPE_DEPTH = 3
# The gate's own preparation call: python3 [-I] <gate> <subcommand> --runtime <rt> <<'DELIM' (quoted).
PREPARE_HEAD = _Pattern("PREPARE_HEAD", r"python3(?:[ \t]+-I)?[ \t]+(.+?)[ \t]+(?:prepare-report|prepare-git-review)"
                                        r"[ \t]+--runtime(?:[ \t]+|=)(?:claude|codex)[ \t]*<<[ \t]*(['\"])"
                                        r"([A-Za-z_][A-Za-z0-9_]*)\2[ \t]*")


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


def asked_question(runtime, request):
    """The first question's text in a native request (Claude `question`, Codex `title`), or None."""
    if isinstance(request, str):
        try:
            request = json.loads(request)
        except ValueError:
            return None
    questions = request.get("questions") if isinstance(request, dict) else None
    if not isinstance(questions, list) or not questions or not isinstance(questions[0], dict):
        return None
    text = questions[0].get("question" if runtime == "claude" else "title")
    return text if isinstance(text, str) else None


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


def report_question(record, path):
    """The five-line question and the host's native request for a prepared decision report."""
    values = [record[key] for key in REPORT_LINE_KEYS] + ["R-" + record["id"], str(path)]
    question = question_text(record["language"], values)
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
    record = {"version": REPORT_VERSION, "runtime": runtime, "language": language,
              "nonce": secrets.token_hex(NONCE_BYTES), "createdAt": time.time(),
              **{key: data[key] for key in REPORT_LINE_KEYS},
              "options": report_options(language, data.get("options")), "multiSelect": multi,
              "detailHash": hashlib.sha256(detail.encode("utf-8")).hexdigest()}
    record["id"] = review_hash(record)[:ID_HEX_LENGTH]
    directory = report_directory() / record["id"]
    question, request = report_question(record, directory / "report.md")
    text = (question + "\n\n" + detail + ("" if detail.endswith("\n") else "\n")).encode("utf-8")
    directory.mkdir(parents=True, mode=0o700, exist_ok=False)
    (directory / "report.md").write_bytes(text)
    record.update(question=question, nativeRequest=request, reportHash=hashlib.sha256(text).hexdigest())
    (directory / "report.json").write_text(review_json(record) + "\n", encoding="utf-8")
    return {"reportId": "R-" + record["id"], "report": str(directory / "report.md"), "question": question,
            "nativeRequest": request}


def load_report(report_id, runtime):
    """The prepared report record; ValueError when it, its question, or report.md was changed or is foreign."""
    directory = report_directory() / report_id
    record = json.loads((directory / "report.json").read_text(encoding="utf-8"))
    core = {key: record[key] for key in REPORT_CORE_KEYS}
    if record.get("id") != report_id or review_hash(core)[:ID_HEX_LENGTH] != report_id or record.get("runtime") != runtime:
        raise ValueError("the prepared report was changed or belongs to another runtime.")
    if (record.get("question"), record.get("nativeRequest")) != report_question(record, directory / "report.md"):
        raise ValueError("the prepared question was changed.")
    if hashlib.sha256((directory / "report.md").read_bytes()).hexdigest() != record.get("reportHash"):
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
            found = prepared_output(item.get("text") if isinstance(item, dict) else item, depth + 1)
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
    if kind == "response_item" and ptype == "function_call_output":
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

def state_directory() -> str:
    base = os.environ.get("DDL_GATE_STATE_DIR") or os.path.join(os.environ.get("TMPDIR") or "/tmp", "ddl-gate")
    base = os.path.abspath(base)  # the question's last line names report.md by its absolute path
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
    else:
        searched = list(instruction_directories(cwd))
        print('DDL project: no (no "{}" line up to {})'.format(MARKER, searched[-1] if searched else cwd))
    return 0


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


def question_guard(runtime, payload, state, pending):
    """Check a native question before the safe-tool shortcut.

    A question that carries an ID must equal the request prepared under that ID, in this state
    directory and after the session's last epoch. A question without an ID is an ordinary question,
    except while a STOP is pending: then only the prepared question may be asked."""
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
        return deny(ASK_UNCHANGED.format(pending["id"]) if pending else PREPARE_FIRST)
    kind, prepared_id = ident
    label = kind + "-" + prepared_id
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
    return None  # the prepared question; the host's own policy still applies


def handle_pre_tool_use(runtime, payload):
    if not session_project(payload)["ddl"]:
        return None
    git_review = git_review_guard(runtime, payload)
    try:
        state, pending = pending_scan(runtime, payload)
    except Exception:
        if git_review is not None:
            return git_review
        raise
    asked = question_guard(runtime, payload, state, pending)
    if asked is not None:
        return asked
    if state is True:
        mutating, segment = is_mutating(runtime, payload.get("tool_name"), payload.get("tool_input"))
        if mutating and not gate_preparation(runtime, payload):
            reason = WAITING_REASON.format(pending["id"], pending["report"]) if pending else DENY_REASON
            return deny(reason + (" Shell segment is not read-only: `{}`.".format(segment) if segment else ""))
    if git_review is not None:
        return git_review
    outward = push_guard(runtime, payload)
    if outward is not None:
        return outward
    if state is None:
        warned = session_file(payload.get("session_id"), ".warned")
        if warned.exists():
            return None  # warn once per session; the rule still holds by instruction
        warned.write_text(str(time.time()))
        return {"systemMessage": UNREADABLE}
    return None  # never emit an affirmative allow that could replace the harness's decision


def handle_stop(runtime, payload):
    if not session_project(payload)["ddl"]:
        return None
    # The last message is the cheap signal; the record catches a report emitted earlier in the same turn,
    # including one that is recorded only as a prepared question or the preparation output.
    closed = has_report(payload.get("last_assistant_message")) or record_state(runtime, payload) is True
    if closed:
        marker_path(payload.get("session_id")).write_text(str(time.time()))
    return None


def handle_user_prompt_submit(runtime, payload):
    if not session_project(payload, refresh=True)["ddl"]:
        return None
    marker_path(payload.get("session_id")).unlink(missing_ok=True)
    # Revoke older Git preparations immediately, even if the new prompt has not reached the
    # asynchronous transcript yet. A possible matching native submission is not itself a grant:
    # PreToolUse must still prove its request/result association from the conversation record.
    matching_submission = False
    if runtime == "codex":
        try:
            reply = codex_git_reply(payload.get("prompt"))
            ident = question_id(reply[1]) if reply else None
            if ident and ident[0] == "G":
                record, _ = load_git_review(ident[1], runtime)
                q = review_question(record)
                matching_submission = reply[1].replace("\r\n", "\n") == q["title"] and reply[2] == q["options"][0]
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            pass
    if not matching_submission:
        session_file(payload.get("session_id"), ".git-epoch").write_text(str(time.time()))
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
    if not session_project(payload, refresh=True)["ddl"]:
        return None
    parts = []
    if payload.get("source") in ("compact", "resume", "fork", "clear"):
        session_file(payload.get("session_id"), ".git-epoch").write_text(str(time.time()))
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
    if argv and argv[0] == "prepare-git-review":
        try:
            _, runtime, problem = parse_args(["session-start", *argv[1:]])
            if problem:
                raise ValueError(problem)
            emit(prepare_git_review(runtime, json.loads(sys.stdin.read())))
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
            emit(prepare_report(runtime, data))
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
