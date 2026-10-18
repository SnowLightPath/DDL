#!/usr/bin/env python3
"""DDL gate: the mechanical half of the protocol's +++STOP rule, as a lifecycle hook.

After the assistant emits a report under the heading `+++DDL_REPORT`, the turn must end and
nothing may mutate until a human speaks again. This hook decides exactly one thing: "has a
human spoken since the last +++DDL_REPORT?" (CLOSED when not, OPEN when yes). Whether the
human's reply is an approval is the assistant's business, never the gate's.

Usage (the same command serves Claude Code and Codex CLI; the hook payload JSON is on stdin):
  python3 tools/ddl_gate.py pre-tool-use       --runtime claude|codex
  python3 tools/ddl_gate.py stop               --runtime claude|codex
  python3 tools/ddl_gate.py user-prompt-submit --runtime claude|codex
  python3 tools/ddl_gate.py session-start      --runtime claude|codex

Decisions (JSON on stdout; the exit status is always 0):
  pre-tool-use        CLOSED and the tool mutates -> permissionDecision "deny"; otherwise nothing
  stop                writes the marker file when the turn ended with a report; prints nothing
  user-prompt-submit  removes the marker (a human spoke); prints nothing
  session-start       compact/resume while CLOSED -> additionalContext with a notice;
                      codex also gets design.md injected (claude imports it through CLAUDE.md)

State: the conversation record (`transcript_path`) is read from the end and decides whenever
it is readable. A marker file `<state dir>/<session_id>.pending` carries the signal across
turns and for runtimes whose record is unreadable, and `<state dir>/<session_id>.warned` makes
the unreadable-record warning appear once per session; the state dir is $DDL_GATE_STATE_DIR,
else $TMPDIR/ddl-gate, else /tmp/ddl-gate. Wire all four events, or the marker is never cleared.

Fail-open: any internal error prints a `systemMessage` warning and allows the call. The shell
allowlist guards against accidental continuation; it is not a sandbox.
"""
import json
import os
import pathlib
import re
import shlex
import sys
import time
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
SHELL_TOOLS = {"claude": {"Bash"}, "codex": {"Bash", "shell", "exec_command", "local_shell", "shell_command", "exec"}}
READ_ONLY_PROGRAMS = {"cat", "head", "tail", "sed", "awk", "grep", "rg", "egrep", "fgrep", "wc", "ls", "find", "stat",
                      "file", "which", "type", "echo", "printf", "pwd", "env", "diff", "cmp", "sort", "uniq", "cut",
                      "tr", "jq", "test", "[", "true", "date", "cd", "git", "codex", "claude"}
FIND_WRITE = {"-delete", "-exec", "-execdir", "-ok", "-okdir", "-fprint", "-fprint0", "-fprintf", "-fls"}
GIT_READ_ONLY = {"status", "diff", "log", "show", "ls-files", "rev-parse", "branch", "check-ignore", "blame", "grep"}
GIT_BRANCH_WRITE = {"-d", "-D", "-m", "-M", "-c", "-C", "-u", "-f", "--delete", "--move", "--copy",
                    "--set-upstream-to", "--unset-upstream", "--edit-description", "--force"}
NOT_HUMAN_PREFIXES = ("Another Claude session sent a message", "<task-notification>", "<system-reminder>",
                      "<local-command", "<command-name>", "[Request interrupted")
ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
REDIRECT = re.compile(r">>?")
# A whole token that is a harmless redirect (`2>&1`, `2>/dev/null`, `<in`) or a bare operator (`>`, `2>>`, `<`).
REDIR_TOKEN = re.compile(r"(\d*|&)>>?(&\d+|/dev/null)?$|\d*<\S*$")


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
    result. Both carry `permissionDecision.source` starting with `user`; a rejected plan is not human."""
    result, decision = entry.get("toolUseResult"), entry.get("permissionDecision")
    if not isinstance(result, dict) or not isinstance(decision, dict):
        return False
    if not str(decision.get("source") or "").startswith("user"):
        return False
    if "answers" in result:
        return True
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


def git_is_read_only(args) -> bool:
    i = 0
    while i < len(args):
        if args[i] in ("-C", "-c"):
            i += 2
        elif args[i].startswith("--git-dir=") or args[i] in ("--no-pager", "-P"):
            i += 1
        else:
            break
    if i >= len(args) or args[i] not in GIT_READ_ONLY:
        return False
    rest = args[i + 1:]
    if any(a.startswith("--output") for a in rest):
        return False
    if args[i] == "branch":
        return not any(not a.startswith("-") or a.split("=", 1)[0] in GIT_BRANCH_WRITE for a in rest)
    return True


def program_is_read_only(prog, args) -> bool:
    """Rules for the allowlisted programs whose options or scripts can still write."""
    if prog == "sed":
        for a in args:  # -i edits in place, -f hides the script, and a `w` command writes from inside it
            if a.startswith(("--in-place", "--file")) or (a.startswith("-") and not a.startswith("--")
                                                           and re.match(r"-[a-zA-Z]*[if]", a)):
                return False
            if not a.startswith("-") and re.search(r"(?:^|[\s;{}\d$/])[wW]\s", a):
                return False
        return True
    if prog == "find":
        return not any(a in FIND_WRITE for a in args)
    if prog == "awk":  # `>` and `|` inside the program write or spawn; -F/-v values may hold a literal `|`
        return not any(">" in a or "system(" in a or ("|" in a and not a.startswith(("-F", "-v"))) for a in args)
    if prog == "sort":
        return not any(a.startswith("--output") or re.match(r"-[a-zA-Z]*o", a) for a in args)
    if prog == "uniq":
        return len([a for a in args if not a.startswith("-")]) < 2
    if prog in ("codex", "claude"):
        return args == ["--version"]
    if prog == "date":
        return not any(a == "-s" or a.startswith("--set") for a in args)
    if prog == "rg":
        return not any(re.match(r"--pre(-glob)?(=|$)", a) for a in args)
    if prog == "git":
        return git_is_read_only(args)
    return True


def shell_is_read_only(cmd) -> Tuple[bool, str]:
    """(True, "") when every segment of the command only reads; else (False, the offending segment)."""
    if not isinstance(cmd, str):
        return False, repr(cmd)
    if any(tok in cmd for tok in ("$(", "`", "<(", ">(")):
        return False, cmd.strip()  # substitutions run arbitrary programs; not worth parsing
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
        while tokens and (ASSIGNMENT.match(tokens[0]) or os.path.basename(tokens[0]) == "env"):
            tokens.pop(0)  # leading NAME=value and `env` do not change what runs
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
    if tool_name in READ_ONLY_TOOLS:
        return False, ""
    if tool_name in SHELL_TOOLS.get(runtime, set()):
        cmd = shell_command(tool_input)
        if cmd is None:
            return True, ""
        ok, segment = shell_is_read_only(cmd)
        return (not ok), segment
    return True, ""


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
    state = pending_state(runtime, payload)
    if state is None:
        warned = session_file(payload.get("session_id"), ".warned")
        if warned.exists():
            return None  # warn once per session; the rule still holds by instruction
        warned.write_text(str(time.time()))
        return {"systemMessage": UNREADABLE}
    if state is False:
        return None
    mutating, segment = is_mutating(runtime, payload.get("tool_name"), payload.get("tool_input"))
    if not mutating:
        return None
    reason = DENY_REASON + (" Shell segment is not read-only: `{}`.".format(segment) if segment else "")
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                   "permissionDecisionReason": reason}}


def handle_stop(runtime, payload):
    # The last message is the cheap signal; the record catches a report emitted earlier in the same turn.
    closed = has_report(payload.get("last_assistant_message")) or record_state(runtime, payload) is True
    if closed:
        marker_path(payload.get("session_id")).write_text(str(time.time()))
    return None


def handle_user_prompt_submit(runtime, payload):
    marker_path(payload.get("session_id")).unlink(missing_ok=True)
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
