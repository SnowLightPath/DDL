#!/usr/bin/env python3
"""DDL gate: the mechanical half of the protocol's +++STOP rule, as a lifecycle hook.

After detecting a report under the heading `+++DDL_REPORT`, the gate denies covered mutating
calls until submitted human input. The assistant follows protocol section 1.5: a synchronous
question waits for the actual answer and can resume approved work in the same turn; an
asynchronous request receipt ends the turn while awaiting the actual answer. Informational
reports require no approval by themselves. Whether a human reply approves the current report
and scope normally remains the assistant's judgment. Ordinary Git commits and pushes have an
additional, independent guard: a prepared content review and an actual matching native choice
are required even after STOP opens and even when native command approvals are disabled.

Usage (the same command serves Claude Code and Codex CLI; the hook payload JSON is on stdin):
  python3 tools/ddl_gate.py pre-tool-use       --runtime claude|codex
  python3 tools/ddl_gate.py stop               --runtime claude|codex
  python3 tools/ddl_gate.py user-prompt-submit --runtime claude|codex
  python3 tools/ddl_gate.py session-start      --runtime claude|codex
  python3 tools/ddl_gate.py prepare-git-review --runtime claude|codex

The preparation command reads JSON {language: en|ja, operations: [{cwd, command}, ...]} on stdin.
It snapshots the staged changes and push targets, writes review detail in the private state
directory, and returns the report path and native question. It cannot create approval.

Decisions (JSON on stdout; the exit status is always 0):
  pre-tool-use        CLOSED and the tool may mutate -> permissionDecision "deny";
                      ordinary commit/push also needs a matching native content review while OPEN
                      codex also denies unsupported push forms in confirmation-enabled modes
  stop                writes the marker file when the turn ended with a report; prints nothing
  user-prompt-submit  removes the marker (a human spoke); prints nothing
  session-start       compact/resume while CLOSED -> additionalContext with a notice;
                      codex also gets design.md injected (claude imports it through CLAUDE.md)

State: the conversation record (`transcript_path`) is read from the end. A readable record is
authoritative for Claude; Codex keeps a pending marker authoritative even over an OPEN record
until the marker is cleared. An answered AskUserQuestion and an approved plan count as human input
(toolUseResult / permissionDecision from the user). Claude Code writes the transcript
asynchronously, so a continuation in the same turn can escape the gate; the rule then holds as
an instruction. A marker file `<state dir>/<session_id>.pending` carries the signal across
turns and for runtimes whose record is unreadable, and `<state dir>/<session_id>.warned` makes
the unreadable-record warning appear once per session; the state dir is $DDL_GATE_STATE_DIR,
else $TMPDIR/ddl-gate, else /tmp/ddl-gate. Wire all four events, or the marker is never cleared.

The general STOP gate fails open on internal errors. Recognized Git commit/push review failures
instead deny the operation; an unreadable or changed review never creates permission. The shell
allowlist guards against accidental continuation; it is not a sandbox. Both adapters use catch-all
matchers, but only calls reaching the runtime's tool hooks are checked. Only exact known read tools
and a bounded, literal shell subset pass while CLOSED; unknown tools, general scripts and code
wrappers do not. Ambient executable/config
behavior is outside this static check. Push form checks do not inspect arbitrary scripts or aliases,
never rewrite a command, and never emit an affirmative permission grant.
Runtime-level hook failures/timeouts can still fail open; the content check uses a shorter time
budget to leave headroom beneath the adapter timeout. Review directories are private; their JSON
is preparation data, not an approval flag. Native request/result proof is checked on every call.
"""
import hashlib
import json
import os
import pathlib
import re
import secrets
import shlex
import shutil
import subprocess
import sys
import time
import urllib.parse
from typing import Optional, Tuple

EVENTS = ("pre-tool-use", "session-start", "stop", "user-prompt-submit")
RUNTIMES = ("claude", "codex")
REPORT = re.compile(r"(?m)^\s*\+\+\+DDL_REPORT\b")

DENY_REASON = ("DDL gate: a +++DDL_REPORT was emitted after the last human message, so this STOP is pending "
               "(protocol §1.5). End the turn and wait for the user's approval; read-only tools may run only to "
               "clarify the report.")
NOTICE = ("DDL gate: a +++DDL_REPORT is awaiting the user's approval. Re-emit the report (protocol §1.5 Summary "
          "rule) and wait; do not continue the phase.")
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
ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
REDIRECT = re.compile(r">>?")
# A whole token that is a harmless redirect (`2>&1`, `2>/dev/null`, `<in`) or a bare operator (`>`, `2>>`, `<`).
REDIR_TOKEN = re.compile(r"(\d*|&)>>?(&\d+|/dev/null)?$|\d*<\S*$")

GIT_REVIEW_TAG = re.compile(r"\[G-([0-9a-f]{16})\]$")
GIT_REVIEW_REASON = ("DDL Git review: this commit or push needs a submitted native choice for its exact "
                     "contents, message, and destination. Prepare a Git review with ddl_gate.py "
                     "prepare-git-review, show its report and question, and wait for the actual answer. ")
GIT_PROTECTED = {"commit", "push", "commit-tree", "send-pack"}
# Leave headroom beneath the adapters' ten-second hook timeout. A timed-out runtime hook may fail open.
GIT_REVIEW_BUDGET_SECONDS = 4
_git_review_deadline = None


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
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme and parsed.netloc and "@" in parsed.netloc:
        return urllib.parse.urlunsplit(parsed._replace(netloc=parsed.netloc.rsplit("@", 1)[1]))
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


def review_question(record):
    counts = [sum(op["kind"] == kind for op in record["operations"]) for kind in ("commit", "push")]
    tag = "[G-{}]".format(record["id"])
    if record["language"] == "ja":
        scope = "・".join("{}{}件".format(label, n) for label, n in zip(("記録", "送信"), counts) if n)
        action = "この内容で記録・送信する" if all(counts) else ("この内容を記録する" if counts[0] else "この内容を送信する")
        return {"title": "このGit確認案（{}）を実行しますか？ {}".format(scope, tag),
                "options": [action + "（推奨）", "内容を見直す", "保留する"]}
    scope = ", ".join("{} {}".format(n, label) for label, n in zip(("commits", "pushes"), counts) if n)
    action = "Commit and push" if all(counts) else ("Create reviewed commits" if counts[0] else "Push reviewed commits")
    return {"title": "Execute this Git review ({})? {}".format(scope, tag),
            "options": [action + " (Recommended)", "Revise this review", "Hold"]}


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
              "nonce": secrets.token_hex(16), "createdAt": time.time(), "operations": operations}
    record["id"] = review_hash(record)[:16]
    directory = review_directory() / record["id"]
    directory.mkdir(parents=True, mode=0o700, exist_ok=False)
    for i, patch in enumerate(patches, 1):
        if patch:
            (directory / (str(i) + ".patch")).write_bytes(patch)
    (directory / "report.md").write_text(review_report(record, directory), encoding="utf-8")
    (directory / "review.json").write_text(review_json(record) + "\n", encoding="utf-8")
    return {"reviewId": "G-" + record["id"], "report": str(directory / "report.md"),
            "question": review_question(record), "nativeRequest": native_git_request(record)}


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
    """Return (question, answer, report text) only for the latest real submitted native choice.

    Match native request/result IDs, not an approval word or an assistant-authored receipt.
    A later report, human message, compaction, or unreadable record invalidates the proof.
    """
    stats = {"lines": 0, "parsed": 0}
    answer, request_id, title, request = None, None, None, None
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
                    text = claude_text(entry)
                    for block in (entry.get("message") or {}).get("content", []):
                        if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("id") == request_id:
                            if block.get("name") != "AskUserQuestion":
                                return None
                            request = block.get("input", {})
                    if has_report(text):
                        return (request, answer, text) if request else None
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
                text = codex_text(payload) if kind == "response_item" and payload.get("role") == "assistant" else (
                    payload.get("message") if kind == "event_msg" and typ == "agent_message" else None)
                if has_report(text):
                    return (request, answer, text) if request else None
                if kind == "event_msg" and typ == "task_started" and answer is None:
                    return None
                if kind == "event_msg" and typ == "item_completed" and payload.get("item", {}).get("type") == "UserMessage":
                    if answer is not None:
                        return None
                    reply = codex_git_reply(codex_text(payload["item"]))
                    if not reply:
                        return None
                    request_id, title, answer = reply
                if kind == "response_item" and typ == "function_call" and payload.get("call_id") == request_id:
                    if payload.get("name") != "request_user_input_async":
                        return None
                    request = json.loads(payload.get("arguments", "{}"))
                    if request.get("questions", [{}])[0].get("title") != title:
                        return None
    except (OSError, ValueError, TypeError, KeyError, IndexError):
        return None
    return None


def approved_git_review(runtime, payload):
    proof = native_git_choice(runtime, payload.get("transcript_path"))
    if not proof:
        raise ValueError("no matching native choice and current Git report are recorded.")
    request, answer, report = proof
    questions = request.get("questions", [])
    if len(questions) != 1:
        raise ValueError("the Git review needs one whole-set native question.")
    q = questions[0]
    title = q.get("question" if runtime == "claude" else "title", "")
    match = GIT_REVIEW_TAG.search(title)
    if not match:
        raise ValueError("the choice is not for a prepared Git review.")
    directory = review_directory() / match[1]
    record = json.loads((directory / "review.json").read_text(encoding="utf-8"))
    core = {k: v for k, v in record.items() if k != "id"}
    if record.get("id") != match[1] or review_hash(core)[:16] != match[1] or record.get("runtime") != runtime:
        raise ValueError("the prepared review was changed or belongs to another runtime.")
    expected = review_question(record)
    if request != native_git_request(record):
        raise ValueError("the question does not match the prepared review.")
    if answer != expected["options"][0] or "G-" + match[1] not in report:
        raise ValueError("the selected action does not approve the current Git review.")
    if str(directory / "report.md") not in report:
        raise ValueError("the decision report did not make the complete prepared review accessible.")
    epoch = session_file(payload.get("session_id"), ".git-epoch")
    if epoch.exists() and record["createdAt"] <= float(epoch.read_text()):
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


def record_state_claude(path) -> Optional[bool]:
    """CLOSED (True), OPEN (False), or None when the record is unreadable."""
    stats = {"lines": 0, "parsed": 0}
    try:
        for entry in iter_entries_reversed(path, stats):
            if entry.get("isSidechain"):
                continue
            if entry.get("type") == "assistant" and has_report(claude_text(entry)):
                return True
            if is_human_prompt_claude(entry):
                return False
    except OSError:
        return None
    if stats["lines"] and not stats["parsed"]:
        return None
    return False


def codex_text(payload) -> str:
    content = payload.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(c.get("text", "") for c in content if isinstance(c, dict) and isinstance(c.get("text"), str))
    return ""


def record_state_codex(path, turn_id=None) -> Optional[bool]:
    """Same contract as record_state_claude, for a Codex rollout file.

    Only `item_completed`/UserMessage and `task_started` mark the human's turn: user-role messages also
    carry injected context (AGENTS.md, environment), so they cannot be the signal. `turn_id` is accepted
    for callers that have it; the boundary rule does not need it."""
    stats = {"lines": 0, "parsed": 0}
    try:
        for entry in iter_entries_reversed(path, stats):
            payload = entry.get("payload")
            if not isinstance(payload, dict):
                continue
            kind, ptype = entry.get("type"), payload.get("type")
            if kind == "response_item" and ptype == "message" and payload.get("role") == "assistant":
                if has_report(codex_text(payload)):
                    return True
            elif kind == "event_msg" and ptype == "agent_message" and has_report(payload.get("message")):
                return True
            elif kind == "event_msg" and ptype == "item_completed":
                item = payload.get("item")
                if isinstance(item, dict) and item.get("type") == "UserMessage":
                    return False
            elif kind == "event_msg" and ptype == "task_started":
                return False
    except OSError:
        return None
    if stats["lines"] and not stats["parsed"]:
        return None
    return False


# --- marker files -----------------------------------------------------------------------------

def session_file(session_id, suffix) -> pathlib.Path:
    base = os.environ.get("DDL_GATE_STATE_DIR") or os.path.join(os.environ.get("TMPDIR") or "/tmp", "ddl-gate")
    pathlib.Path(base).mkdir(parents=True, exist_ok=True)
    name = re.sub(r"[^A-Za-z0-9._-]", "_", str(session_id or "")) or "unknown"
    return pathlib.Path(base) / (name + suffix)


def marker_path(session_id) -> pathlib.Path:
    return session_file(session_id, ".pending")


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


def shell_is_read_only(cmd) -> Tuple[bool, str]:
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


def shell_command(tool_input) -> Optional[str]:
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


def is_mutating(runtime, tool_name, tool_input) -> Tuple[bool, str]:
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


def deny(reason):
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                   "permissionDecisionReason": reason}}


# --- events -----------------------------------------------------------------------------------

def record_state(runtime, payload) -> Optional[bool]:
    path = payload.get("transcript_path")
    if not isinstance(path, str) or not path:
        return None
    if runtime == "codex":
        return record_state_codex(path, payload.get("turn_id"))
    return record_state_claude(path)


def pending_state(runtime, payload) -> Optional[bool]:
    """Combine record and marker. Codex: its record format is unstable, so a marker is trusted even over
    an OPEN record. Claude: the record is authoritative whenever it is readable."""
    state = record_state(runtime, payload)
    marker = marker_path(payload.get("session_id")).exists()
    if runtime == "codex":
        return True if (state is True or marker) else state
    return True if (state is None and marker) else state


def handle_pre_tool_use(runtime, payload):
    git_review = git_review_guard(runtime, payload)
    try:
        state = pending_state(runtime, payload)
    except Exception:
        if git_review is not None:
            return git_review
        raise
    if state is True:
        mutating, segment = is_mutating(runtime, payload.get("tool_name"), payload.get("tool_input"))
        if mutating:
            return deny(DENY_REASON + (" Shell segment is not read-only: `{}`.".format(segment) if segment else ""))
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
    # The last message is the cheap signal; the record catches a report emitted earlier in the same turn.
    closed = has_report(payload.get("last_assistant_message")) or record_state(runtime, payload) is True
    if closed:
        marker_path(payload.get("session_id")).write_text(str(time.time()))
    return None


def handle_user_prompt_submit(runtime, payload):
    marker_path(payload.get("session_id")).unlink(missing_ok=True)
    # Revoke older Git preparations immediately, even if the new prompt has not reached the
    # asynchronous transcript yet. A possible matching native submission is not itself a grant:
    # PreToolUse must still prove its request/result association from the conversation record.
    matching_submission = False
    if runtime == "codex":
        try:
            reply = codex_git_reply(payload.get("prompt"))
            match = GIT_REVIEW_TAG.search(reply[1]) if reply else None
            if match:
                record = json.loads((review_directory() / match[1] / "review.json").read_text())
                q = review_question(record)
                matching_submission = record.get("runtime") == runtime and reply[1] == q["title"] and reply[2] == q["options"][0]
        except (OSError, ValueError, TypeError, KeyError):
            pass
    if not matching_submission:
        session_file(payload.get("session_id"), ".git-epoch").write_text(str(time.time()))
    return None


def find_design_md(cwd) -> Optional[pathlib.Path]:
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
    parts = []
    if payload.get("source") in ("compact", "resume", "fork", "clear"):
        session_file(payload.get("session_id"), ".git-epoch").write_text(str(time.time()))
    if payload.get("source") in ("compact", "resume") and pending_state(runtime, payload) is True:
        parts.append(NOTICE)
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
