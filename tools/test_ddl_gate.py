#!/usr/bin/env python3
"""Tests for the gate: tools/ddl_gate.py (the entry) and tools/ddl_gate_core.py (its code).

Unit tests import the module (shell allowlist, tool classification, the Claude human-prompt test,
the record readers). End-to-end tests run the hook as a subprocess with `python3 -I`, a private
state directory, and the hand-written transcript fixtures under tools/fixtures/. Every project the
gate is expected to act in is a disposable directory carrying an instruction file with the
`→ DDL-PROTOCOL` line, never this repository's own files. The grant store is a disposable directory
too, and the suite leaves this repository's tree as its working directory before any gate runs: the
gate's subcommands take their project, and so their `.ddl/` ledger, from the working directory.

Usage:
  python3 tools/test_ddl_gate.py
  python3 -I tools/test_ddl_gate.py
"""
import atexit
import datetime
import hashlib
import io
import json
import os
import pathlib
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

TOOLS = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import ddl_gate_core as ddl_gate  # noqa: E402  (the gate's code; GATE below is its entry, the launcher)
import ddl_run  # noqa: E402  (the Run subcommands; this suite drives them through ddl_gate.py's command line)

GATE = str(TOOLS / "ddl_gate.py")
GATE_FILES = ("ddl_gate.py", "ddl_gate_core.py", "ddl_run.py")  # the entry and the modules it loads from beside it
REPO = TOOLS.parent
FIXTURES = TOOLS / "fixtures"
ADAPTERS = {"claude": REPO / "hosts" / "claude" / "settings.json",
            "codex": REPO / "hosts" / "codex" / "hooks.json"}
EVENT_NAMES = {"pre-tool-use": "PreToolUse", "permission-request": "PermissionRequest", "session-start": "SessionStart", "stop": "Stop",
               "user-prompt-submit": "UserPromptSubmit"}
REPORT_TEXT = "+++DDL_REPORT\n\n## Realize report\n\nAwaiting approval."
SEGMENT_SUFFIX = " Shell segment is not read-only: `{}`."
MARKER_LINE = "→ DDL-PROTOCOL"


def fixture(name):
    return str(FIXTURES / name)


def render(value, replacements):
    """Fill a fixture template: a whole-value placeholder takes any JSON value, a string one also fills substrings."""
    if isinstance(value, str):
        if value in replacements:
            return replacements[value]
        for key, text in replacements.items():
            if isinstance(text, str):
                value = value.replace(key, text)
        return value
    if isinstance(value, list):
        return [render(v, replacements) for v in value]
    if isinstance(value, dict):
        return {k: render(v, replacements) for k, v in value.items()}
    return value


def template_rows(name, replacements):
    return [render(json.loads(line), replacements) for line in pathlib.Path(fixture(name)).read_text().splitlines()]


def write_rows(path, rows):
    pathlib.Path(path).write_text("".join(json.dumps(row) + "\n" for row in rows))


def codex_reply(call_id, question, answer):
    """The observed Codex envelope that delivers a submitted native answer as a user message."""
    rows = [{"questionItemId": json.dumps(["request_user_input_async", call_id, 0]), "question": question, "answer": answer}]
    return "<send_user_message_question_reply>\n" + json.dumps(rows) + "\n</send_user_message_question_reply>"


def codex_desktop_output(value):
    """Sanitized Desktop text(result) shape: two input_text blocks around an exec result."""
    result = {"chunk_id": "fixture", "wall_time_seconds": 0.01, "exit_code": 0,
              "original_token_count": 100, "output": json.dumps(value) + "\n"}
    return [{"type": "input_text", "text": "Script completed\nWall time 0.1 seconds\nOutput:\n"},
            {"type": "input_text", "text": json.dumps(result)}]


def codex_desktop_preparation(rows, prepared):
    """Replace only a fixture's preparation result; no assistant text or reasoning is needed."""
    rows = [row for row in rows if row.get("payload", {}).get("type") != "reasoning"]
    for row in rows:
        item = row.get("payload", {})
        if item.get("type") == "function_call_output" and item.get("call_id") == "prepare-call":
            item.update(type="custom_tool_call_output", output=codex_desktop_output(prepared))
    return rows


QUESTION_TOOL = {"claude": "AskUserQuestion", "codex": "request_user_input_async"}
QUESTION_KEY = {"claude": "question", "codex": "title"}


def mark_project(root, name=".claude/CLAUDE.md", line=MARKER_LINE):
    """Write an instruction file whose marker line (line 3) makes `root` a DDL project."""
    path = pathlib.Path(root) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# Project\n\n" + line + "\n", encoding="utf-8")
    return path


# The default project of a payload: a DDL project whose `.git` bounds the instruction-file search.
PROJECT = pathlib.Path(tempfile.mkdtemp(prefix="ddl-gate-project-"))
atexit.register(shutil.rmtree, str(PROJECT), True)
(PROJECT / ".git").mkdir()
mark_project(PROJECT)
# No test may write a grant into the real home or a ledger into this repository, whatever environment or
# working directory it builds for a gate process: both defaults point at disposable directories.
GRANTS = tempfile.mkdtemp(prefix="ddl-gate-grants-")
atexit.register(shutil.rmtree, GRANTS, True)
os.environ["DDL_GATE_GRANT_DIR"] = GRANTS
# Nor may a test read the user's resource table: the default place is a disposable directory that holds none, and
# a test that needs a table writes it into a directory of its own (ResourceTest.table).
CONFIG = tempfile.mkdtemp(prefix="ddl-gate-config-")
atexit.register(shutil.rmtree, CONFIG, True)
os.environ["XDG_CONFIG_HOME"] = CONFIG
os.chdir(str(PROJECT))


def grant(**changes):
    """A valid grant whose expiry lies a month ahead; `changes` replace whole fields."""
    expires = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))) + datetime.timedelta(days=30)
    data = {"paths": ["skills/**", "protocol/**"], "commands": ["build", "test", "check"], "machines": [],
            "handover": [], "budget": {"minutes": 360, "fixAttempts": 3},
            "expires": expires.replace(microsecond=0).isoformat()}
    data.update(changes)
    return data


def project_key(root):
    """The grant store's name for the project rooted at `root`."""
    return hashlib.sha256(os.path.realpath(str(root)).encode("utf-8")).hexdigest()[:16]


ISO_UTC = r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$"  # every time the gate writes


def events(root, **match):
    """The ledger lines of the project at `root` whose fields equal `match`."""
    path = pathlib.Path(root) / ".ddl" / "events.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.is_file() else []
    return [row for row in rows if all(row.get(key) == value for key, value in match.items())]


def untimed(rows):
    """Ledger lines without their `ts`, for comparing everything else exactly."""
    return [{key: value for key, value in row.items() if key != "ts"} for row in rows]


def payload(runtime, event="pre-tool-use", transcript=None, session="sess", cwd=None, **extra):
    """A hook payload built from the runtime's template; other events drop the PreToolUse-only fields."""
    data = json.loads((FIXTURES / "payload_pre_tool_use_{}.json".format(runtime)).read_text())
    data["session_id"] = session
    data["transcript_path"] = transcript
    data["cwd"] = cwd or str(PROJECT)
    data["hook_event_name"] = EVENT_NAMES[event]
    if event != "pre-tool-use":
        for key in ("tool_name", "tool_input", "tool_use_id"):
            data.pop(key, None)
    data.update(extra)
    return data


def bash(command, runtime="claude", transcript=None, **extra):
    return payload(runtime, transcript=transcript, tool_name="Bash", tool_input={"command": command}, **extra)


# --- unit tests -----------------------------------------------------------------------------------

ALLOWED_COMMANDS = [
    "git status",
    "git status && grep -n foo design.md | head",
    "ls 2>/dev/null",
    "ls > /dev/null",
    "grep -rn foo . 2>&1 | head -50",
    "cat file.txt",
    "/usr/bin/env grep x f",
    "env",
    "git -C /repo --no-pager log --oneline -5",
    "git branch -a",
    "git branch --show-current",
    "git ls-files tools",
    "git rev-parse HEAD; git show HEAD --stat; git blame -L 1,5 f; git check-ignore x; git grep foo",
    "find . -name '*.py' -newer x",
    "sed -n '1,10p' file",
    "sed -n '20p' file",
    "sed -n '$p' file",
    "sed -n '1,10p' first.txt second.txt",
    "sort -k1 f | uniq -c",
    "uniq -c f",
    "codex --version",
    "claude --version 2>/dev/null",
    "cd /tmp && pwd",
    'echo "a > b"',
    "grep '>' f",
    "[ -f x ] && echo yes",
    "test -f x; echo done",
    "jq '.a' f.json",
    "diff a b",
    "cmp a b || echo differ",
    "rg --pretty foo",
    "rg -n 'foo|bar' src",
    "rg -n -- 'a > b|two words|literal $value' src | head -n 20",
    "grep -n 'a; b && c' file | cut -d: -f1 | sort | uniq -c",
    "true",
    "date",
    "which git",
    "wc -l < f",
    "head -c 100 f\ntail -n 5 f",
    "printf '%s\\n' a b",
    "stat f; file f; type ls",
    "cut -d, -f1 f | tr a-z A-Z | sort | uniq",
    "grep -n /dev/tcp/ notes.txt",
]

DENIED_COMMANDS = [  # (command, offending segment); None means the whole command
    ("echo hi > x.txt", None),
    ("echo hi >> x.txt", None),
    ("echo hi 2>x.txt", None),
    ("cat f >| g", "cat f >"),
    ("sed -i 's/a/b/' f", None),
    ("sed -ni 's/a/b/p' f", None),
    ("sed --in-place=.bak s/a/b/ f", None),
    ("sed 's/a/b/w out.txt' f", None),
    ("sed -f script.sed f", None),
    ("sed -E 's/a/b/' file", None),
    ("sed -n '1,10p;w out.txt' file", None),
    ("sed -n '1p; e touch out.txt' file", None),
    ("sed '1e touch out.txt' file", None),
    ("sed -- 'e touch out.txt' file", None),
    ("sed -n -e '1p' -e 'e touch out.txt' file", None),
    ("sed -n --file=script.sed file", None),
    ("sed -n '1p' --file script.sed file", None),
    ("sed -n 1p -e 'e touch out.txt' file", None),
    ("find . -delete", None),
    ("find . -name x -exec rm {} \\;", None),
    ("find . -fprint out", None),
    ("git commit -m x", None),
    ("git branch new", None),
    ("git branch -d old", None),
    ("git branch --set-upstream-to=origin/main", None),
    ("git log --output=f", None),
    ("git -C /r push", None),
    ("git", None),
    ('python3 -c "print(1)"', None),
    ("python3 --version", None),
    ("cat a | tee b", "tee b"),
    ("ls; rm -rf x", "rm -rf x"),
    ("ls & rm x", "rm x"),
    ("ls || mkdir x", "mkdir x"),
    ("echo $(rm x)", None),
    ("echo `rm x`", None),
    ("diff <(ls a) <(ls b)", None),
    ('echo "unbalanced', None),
    ("awk '{print > \"f\"}' x", None),
    ("awk -F'|' '{print $1}' f", None),
    ("awk -f program.awk f", None),
    ("awk 'BEGIN{system(\"rm x\")}'", None),
    ("awk '{print | \"tee f\"}' x", None),
    ("sort -o out in", None),
    ("sort --output=out in", None),
    ("sort --compress-program='touch out.txt' in", None),
    ("uniq in out", None),
    ("codex exec 'do it'", None),
    ("claude -p hi", None),
    ("date -s 12:00", None),
    ("rg --pre cat foo", None),
    ("rg --pre='touch out.txt' foo", None),
    ("rg --future-execution-helper foo", None),
    ("ls --future-execution-helper", None),
    ("file -C -m local.magic", None),
    ("git -c 'core.fsmonitor=touch out.txt' status", None),
    ("git diff --ext-diff", None),
    ("git -c 'core.pager=touch out.txt' log", None),
    ("xargs rm", None),
    ("bash -c 'ls'", None),
    ("env -i rm x", None),
    ("FOO=1 env BAR=2 grep x y", None),
    ("FOO=bar", None),
    ("env BAR=2 grep x y", None),
    ("timeout 5 ls", None),
    ("/usr/bin/env python3 x.py", None),
    ("touch x", None),
    ("mv a b", None),
    ("cp a b", None),
    ("chmod +x f", None),
    ("rm x", None),
    ("mkdir -p x", None),
    ("nonexistent-tool arg", None),
    ("cat <<EOF\nhello\nEOF", None),
    ('grep "$PATTERN" file', None),
    ("grep foo *.py", None),
    ("cat ~user/file.txt", None),
    ("cat < /dev/tcp/127.0.0.1/9", None),
    ("ls -la 0</dev/udp/127.0.0.1/53", None),
    ("head -c1 <'/dev/tcp/example.invalid/80'", None),
]


class ShellAllowlistTest(unittest.TestCase):
    def test_read_only_commands(self):
        for cmd in ALLOWED_COMMANDS:
            with self.subTest(cmd=cmd):
                self.assertEqual(ddl_gate.shell_is_read_only(cmd), (True, ""))

    def test_mutating_commands(self):
        for cmd, segment in DENIED_COMMANDS:
            with self.subTest(cmd=cmd):
                self.assertEqual(ddl_gate.shell_is_read_only(cmd), (False, segment or cmd))

    def test_non_string_command(self):
        self.assertFalse(ddl_gate.shell_is_read_only(None)[0])
        self.assertFalse(ddl_gate.shell_is_read_only(42)[0])


class ToolClassificationTest(unittest.TestCase):
    def test_claude_tool_names(self):
        for name in sorted(ddl_gate.READ_ONLY_TOOLS):
            with self.subTest(tool=name):
                self.assertEqual(ddl_gate.is_mutating("claude", name, {}), (False, ""))
        for name in ("Edit", "Write", "NotebookEdit", "Agent", "SendMessage", "TaskCreate", "TaskUpdate",
                     "Task", "resume_agent", "followup_task", "send_input", "mcp__x__y", "FooTool", None):
            with self.subTest(tool=name):
                self.assertEqual(ddl_gate.is_mutating("claude", name, {}), (True, ""))

    def test_claude_bash(self):
        self.assertEqual(ddl_gate.is_mutating("claude", "Bash", {"command": "git status"}), (False, ""))
        self.assertEqual(ddl_gate.is_mutating("claude", "Bash", {"command": "rm x"}), (True, "rm x"))
        self.assertEqual(ddl_gate.is_mutating("claude", "Bash", {}), (True, ""))
        self.assertEqual(ddl_gate.is_mutating("claude", "Bash", None), (True, ""))
        self.assertEqual(ddl_gate.is_mutating("claude", "Bash", '{"command": "ls"}'), (False, ""))

    def test_codex_tools(self):
        for name in ("apply_patch", "spawn_agent", "Agent", "mcp__srv__tool", "update_plan", "send_input",
                     "resume_agent", "followup_task", "send_message", "interrupt_agent", "close_agent"):
            with self.subTest(tool=name):
                self.assertEqual(ddl_gate.is_mutating("codex", name, {}), (True, ""))
        self.assertEqual(ddl_gate.is_mutating("codex", "exec_command", {"cmd": "rg foo"}), (False, ""))
        self.assertEqual(ddl_gate.is_mutating("codex", "shell", {"command": ["ls", "-la"]}), (False, ""))
        self.assertEqual(ddl_gate.is_mutating("codex", "shell", {"command": ["rm", "x"]}), (True, "rm x"))
        # Codex's shell wraps the script as ["bash", "-lc", script]; the script is what gets judged.
        self.assertEqual(ddl_gate.is_mutating("codex", "shell", {"command": ["bash", "-lc", "git status"]}),
                         (False, ""))
        self.assertEqual(ddl_gate.is_mutating("codex", "shell", {"command": ["/bin/zsh", "-c", "rm x"]}),
                         (True, "rm x"))
        self.assertEqual(ddl_gate.is_mutating("codex", "shell", {"command": ["bash", "-lc"]}), (True, "bash -lc"))
        # `shell` is not a shell tool for Claude, so it is an unknown (mutating) tool there.
        self.assertEqual(ddl_gate.is_mutating("claude", "shell", {"command": "ls"}), (True, ""))

    def test_codex_native_reads(self):
        for name in ("view_image", "list_agents", "request_user_input", "request_user_input_async"):
            with self.subTest(tool=name):
                self.assertEqual(ddl_gate.is_mutating("codex", name, {}), (False, ""))

    def test_claude_native_reads_and_human_interaction(self):
        for name in ("TaskGet", "TaskList", "AskUserQuestion"):
            with self.subTest(tool=name):
                self.assertEqual(ddl_gate.is_mutating("claude", name, {}), (False, ""))

    def test_read_names_are_runtime_specific(self):
        self.assertEqual(ddl_gate.is_mutating("codex", "Read", {}), (True, ""))
        self.assertEqual(ddl_gate.is_mutating("claude", "view_image", {}), (True, ""))

    def test_polling_inputs_cannot_send_or_terminate(self):
        cases = [
            ("write_stdin", {"session_id": 1}, False),
            ("write_stdin", {"session_id": 1, "chars": ""}, False),
            ("write_stdin", {"session_id": 1, "chars": "\n"}, True),
            ("write_stdin", {"session_id": 1, "chars": "rm x\n"}, True),
            ("write_stdin", {"session_id": 1, "chars": None}, True),
            ("write_stdin", {"session_id": 1, "chars": []}, True),
            ("write_stdin", {"session_id": 1, "chars": "", "future_instruction": "continue"}, True),
            ("wait", {"cell_id": "running"}, False),
            ("wait", {"ids": ["agent-1"], "timeout_ms": 1}, False),
            ("wait", {"cell_id": "running", "terminate": False, "yield_time_ms": 1}, False),
            ("wait", {"cell_id": "running", "terminate": True}, True),
            ("wait", {"cell_id": "running", "terminate": "false"}, True),
            ("wait", {"cell_id": "running", "future_instruction": "continue"}, True),
            ("wait_agent", {"timeout_ms": 1}, False),
            ("wait_agent", {"timeout_ms": 1, "message": "continue"}, True),
        ]
        for name, tool_input, mutating in cases:
            with self.subTest(tool=name, tool_input=tool_input):
                self.assertEqual(ddl_gate.is_mutating("codex", name, tool_input), (mutating, ""))

    def test_malformed_polling_inputs_are_not_confirmed_reads(self):
        for name in ("write_stdin", "wait", "wait_agent"):
            for tool_input in (None, [], "not json", "[]"):
                with self.subTest(tool=name, tool_input=tool_input):
                    self.assertEqual(ddl_gate.is_mutating("codex", name, tool_input), (True, ""))


def user(content, **fields):
    entry = {"type": "user", "message": {"role": "user", "content": content}}
    entry.update(fields)
    return entry


HUMAN_ORIGIN = {"origin": {"kind": "human"}, "turnOrigin": "human", "promptSource": "typed"}
DIALOG = {"permissionDecision": {"decision": "accept", "source": "user_temporary"}}
APPROVED = [{"type": "tool_result", "tool_use_id": "t", "content": "User has approved your plan. Start coding."}]
REJECTED = [{"type": "tool_result", "tool_use_id": "t", "content": "The user rejected the plan. Feedback: no."}]

HUMAN_CASES = [  # (description, entry, is human)
    ("typed string", user("go", **HUMAN_ORIGIN), True),
    ("typed text block with image", user([{"type": "text", "text": "see"}, {"type": "image", "source": {}}],
                                         **HUMAN_ORIGIN), True),
    ("queued prompt", user("next", origin={"kind": "human"}, promptSource="queued"), True),
    ("task notification origin", user("<task-notification>x</task-notification>",
                                      origin={"kind": "task-notification"}), False),
    ("peer origin", user("hello", origin={"kind": "peer"}), False),
    ("compact summary", user("This session is being continued", isCompactSummary=True,
                             turnOrigin="task_notification"), False),
    ("compact summary with human origin", user("summary", isCompactSummary=True, **HUMAN_ORIGIN), False),
    ("meta skill body", user([{"type": "text", "text": "<command-name>/x</command-name>"}], isMeta=True), False),
    ("all tool_result blocks", user([{"type": "tool_result", "tool_use_id": "t", "content": "ok"}]), False),
    ("toolUseResult key", user([{"type": "text", "text": "ok"}], toolUseResult={"type": "text"}), False),
    ("turnOrigin human only", user("go", turnOrigin="human"), True),
    ("turnOrigin task_notification only", user("go", turnOrigin="task_notification"), False),
    ("legacy peer message", user("Another Claude session sent a message: hi"), False),
    ("legacy task notification", user("<task-notification>\n<task-id>1</task-id>"), False),
    ("legacy system reminder", user("  \n<system-reminder>x</system-reminder>"), False),
    ("legacy local command", user("<local-command-stdout>x</local-command-stdout>"), False),
    ("legacy command name", user("<command-name>/realize</command-name>"), False),
    ("legacy interrupted", user("[Request interrupted by user]"), False),
    ("legacy plain text", user("go"), True),
    ("legacy text blocks", user([{"type": "text", "text": "go"}]), True),
    ("legacy image only", user([{"type": "image", "source": {}}]), False),
    ("assistant entry", {"type": "assistant", "message": {"role": "assistant", "content": "go"}}, False),
    ("answered question", user([{"type": "tool_result", "tool_use_id": "t",
                                 "content": "Your questions have been answered:\n\"Q\"=\"Yes\""}],
                               toolUseResult={"questions": [], "answers": {"Q": "Yes"}, "annotations": {}},
                               **DIALOG), True),
    ("answered question without permissionDecision",
     user([{"type": "tool_result", "tool_use_id": "t", "content": "Your questions have been answered"}],
          toolUseResult={"questions": [], "answers": {"Q": "Yes"}, "annotations": {}}), False),
    ("answered question from a non-user source",
     user([{"type": "tool_result", "tool_use_id": "t", "content": "Your questions have been answered"}],
          toolUseResult={"answers": {}}, permissionDecision={"decision": "accept", "source": "config"}), False),
    ("approved plan", user(APPROVED, toolUseResult={"plan": "p", "isAgent": False, "filePath": "f",
                                                    "hasTaskTool": True}, **DIALOG), True),
    ("approved plan, text-block content",
     user([{"type": "tool_result", "tool_use_id": "t",
            "content": [{"type": "text", "text": "User has approved your plan."}]}],
          toolUseResult={"plan": "p"}, **DIALOG), True),
    ("plan result without approval text", user(REJECTED, toolUseResult={"plan": "p", "isAgent": False,
                                                                        "filePath": "f", "hasTaskTool": True},
                                               **DIALOG), False),
]


class HumanPromptTest(unittest.TestCase):
    def test_cases(self):
        for description, entry, expected in HUMAN_CASES:
            with self.subTest(case=description):
                self.assertIs(ddl_gate.is_human_prompt_claude(entry), expected)

    def test_empty_question_answers_are_not_human_input(self):
        for answers in ({}, [], "", "  ", None, {"Q": ""}, {"Q": " \n\t"}, {"Q": None},
                        {"Q": []}, {"Q": {}}, {"Q": False}):
            with self.subTest(answers=answers):
                entry = user([], toolUseResult={"answers": answers}, **DIALOG)
                self.assertIs(ddl_gate.is_human_prompt_claude(entry), False)

    def test_question_answers_are_human_input_without_classifying_approval(self):
        for answer in ("Yes", "No", "Cancel", "Wait", "Explain first"):
            with self.subTest(answer=answer):
                entry = user([], toolUseResult={"answers": {"Q": "", "Other question": answer}}, **DIALOG)
                self.assertIs(ddl_gate.is_human_prompt_claude(entry), True)

    def test_auto_submitted_question_answers_are_not_human_input(self):
        # Observed native timeout and explicit submission under the same 60s setting differ here.
        for answers in ({}, {"Q": "Sample A"}):
            with self.subTest(answers=answers):
                timed_out = user([], toolUseResult={"answers": answers, "afkTimeoutMs": 60000}, **DIALOG)
                self.assertIs(ddl_gate.is_human_prompt_claude(timed_out), False)
        for fields in ({}, {"afkTimeoutMs": None}):
            with self.subTest(explicit_submission=fields):
                submitted = user([], toolUseResult={"answers": {"Q": "Control A"}, **fields}, **DIALOG)
                self.assertIs(ddl_gate.is_human_prompt_claude(submitted), True)


class ReportTest(unittest.TestCase):
    def test_heading_forms(self):
        self.assertTrue(ddl_gate.has_report("+++DDL_REPORT\n\n## Report"))
        self.assertTrue(ddl_gate.has_report("done\n\n  +++DDL_REPORT: realize"))
        self.assertFalse(ddl_gate.has_report("| +++DDL_REPORT | marker |"))
        self.assertFalse(ddl_gate.has_report("emit a +++DDL_REPORT heading"))
        self.assertFalse(ddl_gate.has_report("+++DDL_REPORTS"))
        self.assertFalse(ddl_gate.has_report(None))


RECORD_STATES = {
    "claude_open.jsonl": False,
    "claude_closed_in_turn.jsonl": True,
    "claude_closed_after_task_notification.jsonl": True,
    "claude_reopened.jsonl": False,
    "claude_compact_not_human.jsonl": True,
    "claude_meta_toolresult_not_human.jsonl": True,
    "claude_legacy_no_origin.jsonl": True,
    "claude_legacy_reopened.jsonl": False,
    "claude_malformed.jsonl": True,
    "claude_dialog_answer.jsonl": False,
    "claude_question_empty.jsonl": True,
    "claude_question_cancelled.jsonl": True,
    "claude_question_timed_out.jsonl": True,
    "claude_plan_approved.jsonl": False,
    "claude_plan_rejected.jsonl": True,
    "claude_thinking_only_report.jsonl": False,  # a thinking block is never read
    "codex_open.jsonl": False,
    "codex_reasoning_only_report.jsonl": False,  # nor a reasoning item
    "codex_closed_in_turn.jsonl": True,
    "codex_previous_turn_report.jsonl": False,
    "codex_question_receipt.jsonl": True,
    "codex_question_answer.jsonl": False,
    "codex_question_answer_then_report.jsonl": True,
}


class RecordStateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ddl-gate-record-")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def reader(self, name):
        return ddl_gate.record_state_codex if name.startswith("codex") else ddl_gate.record_state_claude

    def test_fixtures(self):
        for name, expected in RECORD_STATES.items():
            with self.subTest(fixture=name):
                self.assertIs(self.reader(name)(fixture(name)), expected)

    def test_edge_files(self):
        empty = os.path.join(self.tmp, "empty.jsonl")
        garbage = os.path.join(self.tmp, "garbage.jsonl")
        pathlib.Path(empty).write_text("")
        pathlib.Path(garbage).write_text("{not json\n[1, 2\n")
        for reader in (ddl_gate.record_state_claude, ddl_gate.record_state_codex):
            with self.subTest(reader=reader.__name__):
                self.assertIs(reader(empty), False)
                self.assertIs(reader(garbage), None)
                self.assertIs(reader(os.path.join(self.tmp, "missing.jsonl")), None)
                self.assertIs(reader(self.tmp), None)

    def test_reverse_reading_across_blocks(self):
        # A report buried under more than one 64 KiB block of tool results is still found.
        big = os.path.join(self.tmp, "big.jsonl")
        with open(big, "w") as fh:
            for line in pathlib.Path(fixture("claude_closed_in_turn.jsonl")).read_text().splitlines():
                fh.write(line + "\n")
            for i in range(40):
                fh.write(json.dumps(user([{"type": "tool_result", "tool_use_id": "t%d" % i,
                                           "content": "x" * 5000}], toolUseResult={"type": "text"})) + "\n")
        self.assertIs(ddl_gate.record_state_claude(big), True)
        lines = list(ddl_gate.iter_lines_reversed(big, block=1000))
        self.assertEqual([l for l in lines if l], pathlib.Path(big).read_text().splitlines()[::-1])


# --- end-to-end tests ------------------------------------------------------------------------------

class GateTest(unittest.TestCase):
    """Runs the gate as a subprocess against a private state directory."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ddl-gate-e2e-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.state = os.path.join(self.tmp, "state")
        self.grants = os.path.join(self.tmp, "grants")

    def gate_env(self):
        return dict(getattr(self, "git_env", os.environ), DDL_GATE_STATE_DIR=self.state, DDL_GATE_GRANT_DIR=self.grants)

    def run_gate(self, event, runtime, data, argv=None, cwd=None):
        stdin = data if isinstance(data, str) else json.dumps(data)
        if argv is None:
            argv = [event, "--runtime", runtime]
        proc = subprocess.run([sys.executable, "-I", GATE] + argv, input=stdin, capture_output=True, text=True,
                              env=self.gate_env(), cwd=str(cwd or PROJECT))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stderr, "")
        return proc

    def subcommand(self, argv, data=None, cwd=None):
        """A subcommand that may fail: the finished process, whatever its exit status."""
        stdin = data if isinstance(data, str) or data is None else json.dumps(data)
        return subprocess.run([sys.executable, "-I", GATE] + argv, input=stdin, capture_output=True, encoding="utf-8",
                              env=self.gate_env(), cwd=str(cwd or PROJECT))

    def assert_allowed(self, proc):
        self.assertEqual(proc.stdout, "")

    def assert_denied(self, proc, segment=None):
        out = json.loads(proc.stdout)["hookSpecificOutput"]
        self.assertEqual(out["hookEventName"], "PreToolUse")
        self.assertEqual(out["permissionDecision"], "deny")
        expected = ddl_gate.DENY_REASON + (SEGMENT_SUFFIX.format(segment) if segment else "")
        self.assertEqual(out["permissionDecisionReason"], expected)

    def assert_reason(self, proc, reason):
        out = json.loads(proc.stdout)["hookSpecificOutput"]
        self.assertEqual((out["hookEventName"], out["permissionDecision"]), ("PreToolUse", "deny"))
        self.assertEqual(out["permissionDecisionReason"], reason)

    def assert_warning(self, proc):
        out = json.loads(proc.stdout)
        self.assertEqual(list(out), ["systemMessage"])
        return out["systemMessage"]

    def prepare_report(self, runtime, cwd=None, **fields):
        data = {"language": "ja", "decision": "README と docs の 3 件の修正を作業ツリーに入れるか",
                "recommendation": "すべて承認。R1 は版数を 0.7.0 に、R2・R3 はリンクの修正",
                "consequence": "3 ファイルが変わる（未コミット）",
                "detail": "## Realize report\n\n- R1 版数\n- R2 リンク\n- R3 リンク\n"}
        data.update(fields)
        return json.loads(self.run_gate(None, None, data, argv=["prepare-report", "--runtime", runtime], cwd=cwd).stdout)

    def context(self, proc):
        out = json.loads(proc.stdout)["hookSpecificOutput"]
        self.assertEqual(out["hookEventName"], "SessionStart")
        return out["additionalContext"]

    def marker(self, session):
        return pathlib.Path(self.state) / (session + ".pending")

    def project(self, design=True, git=False, sub=None, marker=True):
        """A temp project dir; `.git` bounds the design.md search so the test dir's parents never count."""
        root = pathlib.Path(self.tmp) / "proj"
        root.mkdir()
        if git:
            (root / ".git").mkdir()
        if marker:
            mark_project(root)
        if design:
            (root / "design.md").write_text("# design.md\n\n## Scopes\n\n- tools\n")
        cwd = root / sub if sub else root
        cwd.mkdir(parents=True, exist_ok=True)
        return root, str(cwd)


class ClaudePreToolUseTest(GateTest):
    def test_open_allows_edit(self):
        self.assert_allowed(self.run_gate("pre-tool-use", "claude", payload("claude", transcript=fixture("claude_open.jsonl"))))

    def test_closed_denies_mutating_tools(self):
        transcript = fixture("claude_closed_in_turn.jsonl")
        for tool in ("Edit", "Write", "Agent", "SendMessage", "mcp__x__y", "FooTool"):
            with self.subTest(tool=tool):
                self.assert_denied(self.run_gate("pre-tool-use", "claude",
                                                 payload("claude", transcript=transcript, tool_name=tool)))
        self.assert_allowed(self.run_gate("pre-tool-use", "claude",
                                          payload("claude", transcript=transcript, tool_name="Read")))

    def test_closed_bash(self):
        transcript = fixture("claude_closed_in_turn.jsonl")
        for cmd in ("git status && grep -n foo design.md | head", "ls 2>/dev/null"):
            with self.subTest(cmd=cmd):
                self.assert_allowed(self.run_gate("pre-tool-use", "claude", bash(cmd, transcript=transcript)))
        denied = [("echo hi > x.txt", "echo hi > x.txt"), ("sed -i 's/a/b/' f", "sed -i 's/a/b/' f"),
                  ("find . -delete", "find . -delete"), ("git commit -m x", "git commit -m x"),
                  ('python3 -c "print(1)"', 'python3 -c "print(1)"'), ("cat a | tee b", "tee b"),
                  ("git branch new", "git branch new"), ("cat < /dev/tcp/127.0.0.1/9", "cat < /dev/tcp/127.0.0.1/9")]
        for cmd, segment in denied:
            with self.subTest(cmd=cmd):
                self.assert_denied(self.run_gate("pre-tool-use", "claude", bash(cmd, transcript=transcript)), segment)
        codex = fixture("codex_closed_in_turn.jsonl")
        self.assert_denied(self.run_gate("pre-tool-use", "codex", bash("ls 0</dev/udp/127.0.0.1/53", "codex", codex)),
                           "ls 0</dev/udp/127.0.0.1/53")

    def test_fixture_outcomes(self):
        outcomes = {"claude_closed_after_task_notification.jsonl": False, "claude_reopened.jsonl": True,
                    "claude_compact_not_human.jsonl": False, "claude_meta_toolresult_not_human.jsonl": False,
                    "claude_legacy_no_origin.jsonl": False, "claude_legacy_reopened.jsonl": True,
                    "claude_malformed.jsonl": False, "claude_dialog_answer.jsonl": True,
                    "claude_question_empty.jsonl": False, "claude_question_cancelled.jsonl": False,
                    "claude_question_timed_out.jsonl": False,
                    "claude_plan_approved.jsonl": True, "claude_plan_rejected.jsonl": False,
                    "claude_thinking_only_report.jsonl": True}
        for name, allowed in outcomes.items():
            with self.subTest(fixture=name):
                proc = self.run_gate("pre-tool-use", "claude", payload("claude", transcript=fixture(name)))
                if allowed:
                    self.assert_allowed(proc)
                else:
                    self.assert_denied(proc)

    def test_record_wins_over_marker(self):
        # Claude: a stale marker does not close an OPEN record.
        transcript = fixture("claude_open.jsonl")
        self.run_gate("stop", "claude", payload("claude", "stop", transcript, last_assistant_message=REPORT_TEXT))
        self.assertTrue(self.marker("sess").exists())
        self.assert_allowed(self.run_gate("pre-tool-use", "claude", payload("claude", transcript=transcript)))

    def test_runtime_flag_with_equals(self):
        proc = self.run_gate("pre-tool-use", "claude", payload("claude", transcript=fixture("claude_closed_in_turn.jsonl")),
                             argv=["pre-tool-use", "--runtime=claude"])
        self.assert_denied(proc)


class CodexPreToolUseTest(GateTest):
    def test_open_allows_apply_patch(self):
        self.assert_allowed(self.run_gate("pre-tool-use", "codex", payload("codex", transcript=fixture("codex_open.jsonl"))))

    def test_closed_in_turn(self):
        transcript = fixture("codex_closed_in_turn.jsonl")
        for tool in ("apply_patch", "spawn_agent"):
            with self.subTest(tool=tool):
                self.assert_denied(self.run_gate("pre-tool-use", "codex", payload("codex", transcript=transcript, tool_name=tool)))
        self.assert_denied(self.run_gate("pre-tool-use", "codex", bash("echo hi > out.txt", "codex", transcript)),
                           "echo hi > out.txt")
        self.assert_allowed(self.run_gate("pre-tool-use", "codex", bash("rg foo", "codex", transcript)))

    def test_previous_turn_report_is_open(self):
        self.assert_allowed(self.run_gate("pre-tool-use", "codex",
                                          payload("codex", transcript=fixture("codex_previous_turn_report.jsonl"))))

    def test_requesting_human_input_does_not_itself_reopen(self):
        # A text-only STOP has no prepared question, so a bare question is denied and the STOP stays pending.
        transcript = fixture("codex_closed_in_turn.jsonl")
        for tool in ("request_user_input", "request_user_input_async"):
            with self.subTest(tool=tool):
                self.assert_reason(self.run_gate("pre-tool-use", "codex", payload("codex", transcript=transcript,
                                                                                 tool_name=tool)), ddl_gate.PREPARE_FIRST)
                self.assert_denied(self.run_gate("pre-tool-use", "codex", payload("codex", transcript=transcript)))
        self.assert_allowed(self.run_gate("pre-tool-use", "codex", payload("codex", transcript=fixture("codex_open.jsonl"),
                                                                            tool_name="request_user_input_async")))

    def test_native_question_receipt_answer_and_newer_report(self):
        # These hand-written fixtures use observed native envelopes, not the reader's implementation.
        for name, human_spoke in (("codex_question_receipt.jsonl", False),
                                  ("codex_question_answer.jsonl", True),
                                  ("codex_question_answer_then_report.jsonl", False)):
            with self.subTest(fixture=name):
                proc = self.run_gate("pre-tool-use", "codex", payload("codex", transcript=fixture(name)))
                (self.assert_allowed if human_spoke else self.assert_denied)(proc)


class PushConfirmationTest(GateTest):
    """The gate never executes these commands or supplies a native approval."""

    def test_canonical_push_needs_review_even_without_pending_stop(self):
        for transcript in (fixture("codex_open.jsonl"), None):
            for command in ("git push origin main", "/usr/bin/git push origin main"):
                with self.subTest(transcript=transcript, command=command):
                    data = payload("codex", transcript=transcript, tool_name="exec_command",
                                   tool_input={"cmd": command})
                    proc = self.run_gate("pre-tool-use", "codex", data)
                    out = json.loads(proc.stdout)["hookSpecificOutput"]
                    self.assertEqual(out["permissionDecision"], "deny")
                    self.assertIn("DDL Git review", out["permissionDecisionReason"])

    def test_noncanonical_direct_push_is_denied_even_without_pending_stop(self):
        commands = [
            "git -C /repo push origin main",
            "git -c advice.pushUpdateRejected=false push origin main",
            "git --git-dir=/repo/.git push origin main",
            "git --git-dir /repo/.git push origin main",
            "git --work-tree=/repo push origin main",
            "git --no-pager push origin main",
            "env git push origin main",
        ]
        for transcript in (fixture("codex_open.jsonl"), None):
            for command in commands:
                with self.subTest(transcript=transcript, command=command):
                    data = payload("codex", transcript=transcript, tool_name="exec_command",
                                   tool_input={"cmd": command})
                    proc = self.run_gate("pre-tool-use", "codex", data)
                    out = json.loads(proc.stdout)["hookSpecificOutput"]
                    self.assertEqual(out["permissionDecision"], "deny")
                    self.assertIn("push", out["permissionDecisionReason"].lower())
                    self.assertTrue(out["permissionDecisionReason"].strip())

    def test_argv_push_form_does_not_escape_confirmation_guard(self):
        data = payload("codex", transcript=fixture("codex_open.jsonl"), tool_name="shell",
                       tool_input={"command": ["git", "-C", "/repo", "push", "origin", "main"]})
        proc = self.run_gate("pre-tool-use", "codex", data)
        out = json.loads(proc.stdout)["hookSpecificOutput"]
        self.assertEqual(out["permissionDecision"], "deny")
        self.assertIn("push", out["permissionDecisionReason"].lower())

    def test_shell_shape_must_preserve_native_policy_inspection(self):
        commands = ["git -C /one -C /two push", "./git push", "bin/git push",
                    "FOO=1 echo ready; git push", "echo ready > /dev/null; git push",
                    "git push & echo ready", "bash -lc 'git push'", "git push 2>&1",
                    "git $SUBCOMMAND", 'git "$SUBCOMMAND"']
        for command in commands:
            with self.subTest(command=command):
                data = payload("codex", transcript=fixture("codex_open.jsonl"), tool_name="Bash",
                               tool_input={"command": command})
                out = json.loads(self.run_gate("pre-tool-use", "codex", data).stdout)
                self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_plain_compound_push_and_quoted_data_keep_native_policy(self):
        for command in ("git status && git push origin main", "echo 'a>b&c'; git push",
                        "git log --grep push | head", "git --version"):
            with self.subTest(command=command):
                data = payload("codex", transcript=fixture("codex_open.jsonl"), tool_name="Bash",
                               tool_input={"command": command})
                proc = self.run_gate("pre-tool-use", "codex", data)
                if ddl_gate.visible_git_write(command):
                    self.assertEqual(json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")
                else:
                    self.assert_allowed(proc)

    def test_mode_exception_does_not_skip_stop(self):
        command = "git -C /repo push origin main"
        for mode in ("bypassPermissions", "dontAsk"):
            with self.subTest(mode=mode):
                data = payload("codex", transcript=fixture("codex_open.jsonl"), permission_mode=mode,
                               tool_name="exec_command", tool_input={"cmd": command})
                self.assertIn("DDL Git review", self.run_gate("pre-tool-use", "codex", data).stdout)
                data["transcript_path"] = fixture("codex_closed_in_turn.jsonl")
                self.assert_denied(self.run_gate("pre-tool-use", "codex", data), command)

    def test_unknown_or_missing_native_mode_keeps_form_guard(self):
        command = "git -C /repo push origin main"
        for mode in (None, "default", "unknown", "never"):
            with self.subTest(mode=mode):
                data = payload("codex", transcript=fixture("codex_open.jsonl"), permission_mode=mode,
                               tool_name="exec_command", tool_input={"cmd": command})
                proc = self.run_gate("pre-tool-use", "codex", data)
                out = json.loads(proc.stdout)["hookSpecificOutput"]
                self.assertEqual(out["permissionDecision"], "deny")
                self.assertIn("push", out["permissionDecisionReason"].lower())

    def test_push_text_as_data_does_not_trigger_form_guard(self):
        for command in ("git log --grep push", "git show push", "git -C /repo log --grep push",
                        "git config remote.fixture.url push", "echo 'git push'"):
            with self.subTest(command=command):
                data = payload("codex", transcript=fixture("codex_open.jsonl"), tool_name="exec_command",
                               tool_input={"cmd": command})
                self.assert_allowed(self.run_gate("pre-tool-use", "codex", data))


class AdapterDispatchTest(GateTest):
    """Use the shipped matcher and command, without executing any tool payload.

    A private Git project makes the Codex adapter's root lookup real, including when the hook runs
    in a subdirectory. Only the canonical gate's files are copied (the entry, the code it loads, the Run
    subcommands, as a project copy holds them); generated hook mirrors are not trusted.
    """

    def setUp(self):
        super().setUp()
        self.root = pathlib.Path(self.tmp) / "adapter project"
        self.root.mkdir()
        self.home = pathlib.Path(self.tmp) / "home"
        self.home.mkdir()
        self.env = dict(os.environ, DDL_GATE_STATE_DIR=self.state, DDL_GATE_GRANT_DIR=self.grants, HOME=str(self.home),
                        CLAUDE_PROJECT_DIR=str(self.root), GIT_CONFIG_NOSYSTEM="1",
                        GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull)
        proc = subprocess.run(["git", "init", "-q", str(self.root)], capture_output=True, text=True, env=self.env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.subdir = self.root / "src" / "pkg"
        self.subdir.mkdir(parents=True)
        (self.root / "design.md").write_text("# Isolated adapter fixture\n", encoding="utf-8")
        mark_project(self.root)
        mark_project(self.root, "AGENTS.md")
        for directory in (".claude", ".codex"):
            hooks = self.root / directory / "hooks"
            hooks.mkdir(parents=True)
            for name in GATE_FILES:
                shutil.copyfile(TOOLS / name, hooks / name)
        self.adapters = {runtime: json.loads(path.read_text(encoding="utf-8"))
                         for runtime, path in ADAPTERS.items()}

    def run_adapter(self, runtime, event, data):
        """Apply native matcher semantics, then execute exactly the selected command hooks."""
        hook_event = EVENT_NAMES[event]
        match_value = data.get("tool_name", "") if event == "pre-tool-use" else data.get("source", "")
        selected = []
        for entry in self.adapters[runtime]["hooks"].get(hook_event, []):
            matcher = entry.get("matcher")
            if matcher not in (None, "*") and re.search(matcher, match_value) is None:
                continue
            selected.extend(entry.get("hooks", []))
        self.assertTrue(selected, "{} adapter omitted {} for {!r}".format(runtime, hook_event, match_value))
        results = []
        for hook in selected:
            self.assertEqual(hook["type"], "command")
            cwd = self.subdir if runtime == "codex" else self.root
            proc = subprocess.run(["sh", "-c", hook["command"]], input=json.dumps(data), cwd=str(cwd),
                                  capture_output=True, text=True, env=self.env, timeout=15)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(proc.stderr, "")
            results.append(proc)
        return results

    def adapter_payload(self, runtime, event="pre-tool-use", transcript=None, session="adapter", **extra):
        cwd = self.subdir if runtime == "codex" else self.root
        return payload(runtime, event, transcript, session, str(cwd), **extra)

    def assert_adapter_allowed(self, results):
        for proc in results:
            self.assert_allowed(proc)

    def assert_adapter_denied(self, results, segment=None):
        for proc in results:
            self.assert_denied(proc, segment)

    def test_actual_pretool_dispatch_covers_mutators_and_future_tools(self):
        cases = {
            "claude": [
                ("Edit", {}), ("Write", {}), ("NotebookEdit", {}), ("Agent", {}), ("Task", {}),
                ("SendMessage", {}), ("TaskCreate", {}), ("TaskUpdate", {}),
                ("Bash", {"command": "touch blocked.txt"}),
                ("mcp__fixture__write", {}), ("FutureWriteTool", {}),
            ],
            "codex": [
                ("apply_patch", {}), ("exec", {"cmd": "touch blocked.txt"}), ("spawn_agent", {}),
                ("exec_command", {"cmd": "touch blocked.txt"}), ("local_shell", {"command": "touch blocked.txt"}),
                ("send_input", {}), ("resume_agent", {}), ("followup_task", {}), ("send_message", {}),
                ("interrupt_agent", {}), ("close_agent", {}),
                ("write_stdin", {"session_id": 1, "chars": "touch blocked.txt\n"}),
                ("wait", {"cell_id": "running", "terminate": True}),
                ("mcp__fixture__write", {}), ("future_write_tool", {}),
            ],
        }
        for runtime, calls in cases.items():
            transcript = fixture(runtime + "_closed_in_turn.jsonl")
            for name, tool_input in calls:
                with self.subTest(runtime=runtime, tool=name):
                    data = self.adapter_payload(runtime, transcript=transcript, tool_name=name, tool_input=tool_input)
                    segment = (tool_input.get("cmd", tool_input.get("command"))
                               if name in ("Bash", "exec_command", "local_shell") else None)
                    self.assert_adapter_denied(self.run_adapter(runtime, "pre-tool-use", data), segment)
        self.assertFalse((self.root / "blocked.txt").exists())

    def test_actual_dispatch_keeps_confirmed_reads_available(self):
        cases = {
            "claude": [("Read", {"file_path": "design.md"}), ("Grep", {"pattern": "DDL"}),
                       ("TaskGet", {"taskId": "fixture"}), ("TaskList", {}),
                       ("Bash", {"command": "sed -n '1,10p' design.md | head -n 5"})],
            "codex": [("view_image", {"path": "fixture.png"}), ("list_agents", {}),
                      ("exec_command", {"cmd": "rg -n 'a > b|literal $value' src | head -n 5"}),
                      ("write_stdin", {"session_id": 1, "chars": ""}),
                      ("wait", {"cell_id": "running", "terminate": False}),
                      ("wait_agent", {"timeout_ms": 1})],
        }
        for runtime, calls in cases.items():
            transcript = fixture(runtime + "_closed_in_turn.jsonl")
            for name, tool_input in calls:
                with self.subTest(runtime=runtime, tool=name):
                    data = self.adapter_payload(runtime, transcript=transcript, tool_name=name, tool_input=tool_input)
                    self.assert_adapter_allowed(self.run_adapter(runtime, "pre-tool-use", data))

    def test_actual_dispatch_admits_only_the_prepared_question_while_pending(self):
        for runtime in ("claude", "codex"):
            with self.subTest(runtime=runtime):
                transcript = fixture(runtime + "_closed_in_turn.jsonl")
                bare = self.adapter_payload(runtime, transcript=transcript, tool_name=QUESTION_TOOL[runtime], tool_input={})
                for proc in self.run_adapter(runtime, "pre-tool-use", bare):
                    self.assert_reason(proc, ddl_gate.PREPARE_FIRST)
                prepared = self.prepare_report(runtime)
                asked = dict(bare, tool_input=prepared["nativeRequest"])
                self.assert_adapter_allowed(self.run_adapter(runtime, "pre-tool-use", asked))

    def test_actual_dispatch_blocks_script_and_execution_helper_regressions(self):
        commands = ("sed 'e touch blocked.txt' design.md", "sed -n '1p;w blocked.txt' design.md",
                    "sed -n --file=script.sed design.md", "awk -f program.awk design.md",
                    "rg --pre='touch blocked.txt' DDL design.md", "env env touch blocked.txt",
                    "env /usr/bin/env rm blocked.txt", "env env BAD=1 touch blocked.txt",
                    "git diff -C --output=blocked.txt", "git log --color --output=blocked.txt",
                    "git show --find-renames --output=blocked.txt",
                    "git log --format --output=blocked.txt", "printf -v PATH /tmp",
                    "printf '%n' PATH", "test -v 'path[$(printf proof >&2)]'",
                    "[ -v 'path[$(printf proof >&2)]' ]",
                    "test 'path[$(printf proof >&2)]' -eq 0",
                    "printf '%d' 'path[$(printf proof >&2)]'")
        for runtime in ("claude", "codex"):
            transcript = fixture(runtime + "_closed_in_turn.jsonl")
            for command in commands:
                with self.subTest(runtime=runtime, command=command):
                    tool = "Bash" if runtime == "claude" else "exec_command"
                    tool_input = {"command" if runtime == "claude" else "cmd": command}
                    data = self.adapter_payload(runtime, transcript=transcript, tool_name=tool, tool_input=tool_input)
                    self.assert_adapter_denied(self.run_adapter(runtime, "pre-tool-use", data), command)
        self.assertFalse((self.root / "blocked.txt").exists())

    def test_actual_codex_dispatch_applies_push_guard_while_open(self):
        data = self.adapter_payload("codex", transcript=fixture("codex_open.jsonl"), tool_name="exec_command",
                                    tool_input={"cmd": "git -C /repo push origin main"})
        for proc in self.run_adapter("codex", "pre-tool-use", data):
            out = json.loads(proc.stdout)["hookSpecificOutput"]
            self.assertEqual(out["permissionDecision"], "deny")
            self.assertIn("push", out["permissionDecisionReason"].lower())

    def append_record(self, path, entry):
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")

    def test_native_question_lifecycle_keeps_receipt_and_empty_answer_pending(self):
        # Execute configured hooks; this does not assert that a native UI dispatches these events.
        for runtime in ("claude", "codex"):
            with self.subTest(runtime=runtime):
                session = runtime + "-question"
                transcript = self.root / (runtime + "-question.jsonl")
                shutil.copyfile(fixture(runtime + "_closed_in_turn.jsonl"), transcript)
                pre = self.adapter_payload(runtime, transcript=str(transcript), session=session)
                stop = self.adapter_payload(runtime, "stop", str(transcript), session,
                                            last_assistant_message=REPORT_TEXT)
                self.assert_adapter_allowed(self.run_adapter(runtime, "stop", stop))
                prepared = self.prepare_report(runtime)
                asked = dict(pre, tool_name=QUESTION_TOOL[runtime], tool_input=prepared["nativeRequest"])
                self.assert_adapter_allowed(self.run_adapter(runtime, "pre-tool-use", asked))
                self.assertTrue(self.marker(session).exists())
                self.assert_adapter_denied(self.run_adapter(runtime, "pre-tool-use", pre))

                pending = "claude_question_empty.jsonl" if runtime == "claude" else "codex_question_receipt.jsonl"
                shutil.copyfile(fixture(pending), transcript)
                self.assert_adapter_denied(self.run_adapter(runtime, "pre-tool-use", pre))
                answered = "claude_dialog_answer.jsonl" if runtime == "claude" else "codex_question_answer.jsonl"
                shutil.copyfile(fixture(answered), transcript)
                self.assertTrue(self.marker(session).exists())
                if runtime == "codex":
                    # Its durable marker remains authoritative until UserPromptSubmit clears it.
                    self.assert_adapter_denied(self.run_adapter(runtime, "pre-tool-use", pre))
                prompt = self.adapter_payload(runtime, "user-prompt-submit", str(transcript), session,
                                              prompt="native question answer")
                self.assert_adapter_allowed(self.run_adapter(runtime, "user-prompt-submit", prompt))
                self.assertFalse(self.marker(session).exists())
                self.assert_adapter_allowed(self.run_adapter(runtime, "pre-tool-use", pre))

                report = ({"type": "assistant", "message": {"role": "assistant", "content": REPORT_TEXT}}
                          if runtime == "claude" else
                          {"type": "event_msg", "payload": {"type": "agent_message", "message": REPORT_TEXT}})
                self.append_record(transcript, report)
                self.assert_adapter_denied(self.run_adapter(runtime, "pre-tool-use", pre))

    def test_actual_lifecycle_closes_resumes_and_reopens_after_human_reply(self):
        for runtime in ("claude", "codex"):
            with self.subTest(runtime=runtime):
                session = runtime + "-lifecycle"
                transcript = self.root / (runtime + "-lifecycle.jsonl")
                shutil.copyfile(fixture(runtime + "_open.jsonl"), transcript)
                pre = self.adapter_payload(runtime, transcript=str(transcript), session=session)
                self.assert_adapter_allowed(self.run_adapter(runtime, "pre-tool-use", pre))
                report = ({"type": "assistant", "message": {"role": "assistant", "content": REPORT_TEXT}}
                          if runtime == "claude" else
                          {"type": "event_msg", "payload": {"type": "agent_message", "message": REPORT_TEXT}})
                self.append_record(transcript, report)
                stop = self.adapter_payload(runtime, "stop", str(transcript), session,
                                            last_assistant_message=REPORT_TEXT)
                self.assert_adapter_allowed(self.run_adapter(runtime, "stop", stop))
                self.assertTrue(self.marker(session).exists())
                self.assert_adapter_denied(self.run_adapter(runtime, "pre-tool-use", pre))

                start = self.adapter_payload(runtime, "session-start", str(transcript), session, source="resume")
                for proc in self.run_adapter(runtime, "session-start", start):
                    self.assertIn(ddl_gate.NOTICE, self.context(proc))
                    if runtime == "codex":
                        self.assertIn("# Isolated adapter fixture", self.context(proc))

                notification = (user("continue", origin={"kind": "peer"}) if runtime == "claude" else
                                {"type": "response_item", "payload": {"type": "message", "role": "user",
                                                                      "content": "injected context"}})
                self.append_record(transcript, notification)
                self.assert_adapter_denied(self.run_adapter(runtime, "pre-tool-use", pre))
                reply = (user("OK", **HUMAN_ORIGIN) if runtime == "claude" else
                         {"type": "event_msg", "payload": {"type": "item_completed",
                                                            "item": {"type": "UserMessage", "content": "OK"}}})
                self.append_record(transcript, reply)
                prompt = self.adapter_payload(runtime, "user-prompt-submit", str(transcript), session, prompt="OK")
                self.assert_adapter_allowed(self.run_adapter(runtime, "user-prompt-submit", prompt))
                self.assertFalse(self.marker(session).exists())
                self.assert_adapter_allowed(self.run_adapter(runtime, "pre-tool-use", pre))
                for proc in self.run_adapter(runtime, "session-start", start):
                    if proc.stdout:
                        self.assertNotIn(ddl_gate.NOTICE, self.context(proc))


class MarkerTest(GateTest):
    def test_stop_then_prompt_sequence(self):
        transcript = fixture("codex_open.jsonl")
        pre = payload("codex", transcript=transcript, session="seq")
        self.assert_allowed(self.run_gate("pre-tool-use", "codex", pre))
        self.run_gate("stop", "codex", payload("codex", "stop", transcript, "seq", last_assistant_message=REPORT_TEXT))
        self.assertTrue(self.marker("seq").exists())
        self.assert_denied(self.run_gate("pre-tool-use", "codex", pre))
        self.run_gate("user-prompt-submit", "codex", payload("codex", "user-prompt-submit", transcript, "seq", prompt="OK"))
        self.assertFalse(self.marker("seq").exists())
        self.assert_allowed(self.run_gate("pre-tool-use", "codex", pre))

    def test_stop_without_report_writes_nothing(self):
        self.run_gate("stop", "codex", payload("codex", "stop", fixture("codex_open.jsonl"), "quiet",
                                               last_assistant_message="Reading the tool."))
        self.assertFalse(self.marker("quiet").exists())

    def test_stop_falls_back_to_record(self):
        self.run_gate("stop", "codex", payload("codex", "stop", fixture("codex_closed_in_turn.jsonl"), "fb",
                                               last_assistant_message=None))
        self.assertTrue(self.marker("fb").exists())

    def test_session_id_is_sanitized(self):
        self.run_gate("stop", "claude", payload("claude", "stop", None, "../a b/c", last_assistant_message=REPORT_TEXT))
        self.assertTrue(self.marker(".._a_b_c").exists())

    def check_unreadable(self, runtime, transcript):
        pre = payload(runtime, transcript=transcript, session="nul")
        proc = self.run_gate("pre-tool-use", runtime, pre)
        self.assertEqual(self.assert_warning(proc), ddl_gate.UNREADABLE)
        self.assert_allowed(self.run_gate("pre-tool-use", runtime, pre))  # warned once per session
        self.run_gate("stop", runtime, payload(runtime, "stop", transcript, "nul", last_assistant_message=REPORT_TEXT))
        self.assert_denied(self.run_gate("pre-tool-use", runtime, pre))
        self.run_gate("user-prompt-submit", runtime, payload(runtime, "user-prompt-submit", transcript, "nul"))
        self.assert_allowed(self.run_gate("pre-tool-use", runtime, pre))

    def test_null_transcript(self):
        self.check_unreadable("codex", None)

    def test_missing_transcript_file(self):
        self.check_unreadable("claude", os.path.join(self.tmp, "no-such-transcript.jsonl"))


class SessionStartTest(GateTest):
    def test_codex_startup_injects_design(self):
        root, cwd = self.project()
        proc = self.run_gate("session-start", "codex", payload("codex", "session-start", None, cwd=cwd, source="startup"))
        self.assertEqual(self.context(proc), ddl_gate.DESIGN_HEADER + "\n\n" + (root / "design.md").read_text())

    def test_codex_compact_notice_precedes_design(self):
        root, cwd = self.project()
        for source in ("compact", "resume"):
            with self.subTest(source=source):
                proc = self.run_gate("session-start", "codex", payload("codex", "session-start", fixture("codex_closed_in_turn.jsonl"),
                                                                       cwd=cwd, source=source))
                self.assertEqual(self.context(proc), ddl_gate.NOTICE + "\n\n" + ddl_gate.DESIGN_HEADER + "\n\n"
                                 + (root / "design.md").read_text())
        proc = self.run_gate("session-start", "codex", payload("codex", "session-start", fixture("codex_closed_in_turn.jsonl"),
                                                               cwd=cwd, source="startup"))
        self.assertTrue(self.context(proc).startswith(ddl_gate.DESIGN_HEADER))

    def test_codex_compact_uses_marker_when_record_is_null(self):
        root, cwd = self.project(design=False, git=True)
        self.run_gate("stop", "codex", payload("codex", "stop", None, last_assistant_message=REPORT_TEXT))
        proc = self.run_gate("session-start", "codex", payload("codex", "session-start", None, cwd=cwd, source="compact"))
        self.assertEqual(self.context(proc), ddl_gate.NOTICE)

    def test_claude_never_injects_design(self):
        root, cwd = self.project()
        self.assert_allowed(self.run_gate("session-start", "claude", payload("claude", "session-start", None, cwd=cwd, source="startup")))
        proc = self.run_gate("session-start", "claude", payload("claude", "session-start", fixture("claude_compact_not_human.jsonl"),
                                                                cwd=cwd, source="compact"))
        self.assertEqual(self.context(proc), ddl_gate.NOTICE)
        self.assert_allowed(self.run_gate("session-start", "claude", payload("claude", "session-start", fixture("claude_compact_not_human.jsonl"),
                                                                             cwd=cwd, source="startup")))

    def test_no_design_and_open_prints_nothing(self):
        root, cwd = self.project(design=False, git=True)
        self.assert_allowed(self.run_gate("session-start", "codex", payload("codex", "session-start", fixture("codex_open.jsonl"),
                                                                            cwd=cwd, source="compact")))

    def test_design_found_from_subdirectory(self):
        root, cwd = self.project(git=True, sub="src/pkg")
        proc = self.run_gate("session-start", "codex", payload("codex", "session-start", None, cwd=cwd, source="startup"))
        self.assertTrue(self.context(proc).startswith(ddl_gate.DESIGN_HEADER))

    def test_search_stops_at_git_root(self):
        root, cwd = self.project(design=True, sub="inner")
        (root / "inner" / ".git").mkdir()  # a nested repository root hides the outer design.md
        mark_project(root / "inner", "CLAUDE.md")  # the inner project is DDL by its own instruction file
        self.assert_allowed(self.run_gate("session-start", "codex", payload("codex", "session-start", None, cwd=cwd, source="startup")))

    def test_codex_injects_nothing_without_the_marker_or_without_design(self):
        root, cwd = self.project(git=True, marker=False)
        for source in ("startup", "resume"):
            self.assert_allowed(self.run_gate("session-start", "codex", payload("codex", "session-start", fixture("codex_closed_in_turn.jsonl"),
                                                                                cwd=cwd, source=source)))
        shutil.rmtree(root)
        root, cwd = self.project(design=False, git=True)
        self.assert_allowed(self.run_gate("session-start", "codex", payload("codex", "session-start", None, cwd=cwd, source="startup")))


class GitReviewTest(GateTest):
    """Real disposable Git repositories; native-shaped fixtures authorize no real user repository."""

    def setUp(self):
        super().setUp()
        self.git_env = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
        self.repo = pathlib.Path(self.tmp) / "review repo"
        self.repo.mkdir()
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "user.name", "DDL fixture")
        self.git("config", "commit.gpgSign", "false")
        self.file = self.repo / "sample.txt"
        self.file.write_text("base\n")
        self.git("add", "sample.txt")
        self.git("commit", "-q", "--cleanup=verbatim", "-m", "base")
        self.stage("reviewed\n")
        self.message = pathlib.Path(self.tmp) / "message.txt"
        self.message.write_text("Record reviewed contents\n\nPreserve the exact message.\n")
        self.command = "git commit --cleanup=verbatim -F " + shlex.quote(str(self.message))
        self.remote = pathlib.Path(self.tmp) / "remote.git"
        subprocess.run(["git", "init", "--bare", "-q", str(self.remote)], check=True, capture_output=True, env=self.git_env)
        self.git("remote", "add", "origin", str(self.remote))
        self.transcript = pathlib.Path(self.tmp) / "native.jsonl"
        mark_project(self.repo)

    def git(self, *args):
        proc = subprocess.run(["git", "-C", str(self.repo), *args], capture_output=True, text=True, env=self.git_env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout.strip()

    def stage(self, text):
        self.file.write_text(text)
        self.git("add", "sample.txt")

    def prepare(self, runtime, commands=None):
        operations = [{"cwd": str(self.repo), "command": command} for command in (commands or [self.command])]
        self.review_input = {"language": "ja", "operations": operations}
        proc = self.run_gate("prepare-git-review", runtime, self.review_input)
        return json.loads(proc.stdout)

    def record(self, runtime, review, choice=0, mutate=None, variant="", desktop=False):
        """Write the native transcript for `review` from `git_review_<runtime><variant>.jsonl`."""
        q = review["question"]
        answer = q["options"][choice]
        request = review["nativeRequest"]
        prepare_input = json.dumps(getattr(self, "review_input", {}))
        codex_call = ("python3 \"$HOME/.codex/hooks/ddl_gate.py\" prepare-git-review --runtime codex <<'JSON'\n"
                      + prepare_input + "\nJSON")
        replacements = {"@ID@": review["reviewId"][2:], "@REPORT@": review["report"],
                        "@REQUEST@": request, "@REQUEST_JSON@": json.dumps(request),
                        "@ANSWERS@": {q["title"]: answer},
                        "@REPLY@": codex_reply("git-review-call", q["title"], answer),
                        "@PREPARED_JSON@": json.dumps(review), "@INPUT@": prepare_input,
                        "@PREPARE_ARGS_JSON@": json.dumps({"cmd": codex_call})}
        rows = template_rows("git_review_" + runtime + variant + ".jsonl", replacements)
        if desktop:
            rows = codex_desktop_preparation(rows, review)
        if mutate:
            mutate(rows)
        write_rows(self.transcript, rows)
        return rows

    def ask(self, runtime, request, transcript=None, **extra):
        """PreToolUse for the native question tool carrying `request`."""
        data = payload(runtime, cwd=str(self.repo), transcript=transcript or fixture(runtime + "_open.jsonl"),
                       tool_name=QUESTION_TOOL[runtime], tool_input=request, **extra)
        return self.run_gate("pre-tool-use", runtime, data)

    def check(self, runtime, command=None, transcript=True, **extra):
        data = payload(runtime, cwd=str(self.repo), transcript=str(self.transcript) if transcript else None,
                       tool_name="Bash", tool_input={"command": command or self.command}, **extra)
        return self.run_gate("pre-tool-use", runtime, data)

    def blocked(self, proc):
        out = json.loads(proc.stdout)["hookSpecificOutput"]
        self.assertEqual(out["permissionDecision"], "deny")
        return out["permissionDecisionReason"]

    def passed(self, runtime, proc, review=None):
        """A matched commit or push passes: Claude's PreToolUse allows it (the review was the one confirmation);
        Codex's PreToolUse says nothing, since Codex takes no allow there (its PermissionRequest answers)."""
        if runtime == "codex":
            return self.assert_allowed(proc)
        out = json.loads(proc.stdout)["hookSpecificOutput"]
        self.assertEqual((out["hookEventName"], out["permissionDecision"]), ("PreToolUse", "allow"))
        if review:
            self.assertEqual(out["permissionDecisionReason"], "DDL: matches Git review " + review["reviewId"])
        else:
            self.assertRegex(out["permissionDecisionReason"], r"^DDL: matches Git review G-[0-9a-f]{16}$")

    pushed = passed

    def permitted(self, runtime, command=None, **extra):
        """Codex's PermissionRequest for the same call: its output, parsed (None when it printed nothing)."""
        data = payload(runtime, "pre-tool-use", str(self.transcript), cwd=str(self.repo), tool_name="Bash",
                       tool_input={"command": command or self.command}, hook_event_name="PermissionRequest", **extra)
        data.pop("tool_use_id", None)  # PermissionRequest carries none
        out = self.run_gate("permission-request", runtime, data).stdout
        return json.loads(out) if out else None

    def test_missing_review_is_denied_in_both_runtimes_and_all_permission_modes(self):
        for runtime in ("claude", "codex"):
            for mode in ("default", "bypassPermissions", "dontAsk", "never"):
                for command in (self.command, "git push origin main"):
                    with self.subTest(runtime=runtime, mode=mode, command=command):
                        self.assertIn("DDL Git review", self.blocked(self.check(runtime, command, False, permission_mode=mode)))

    def test_doctor_probe_shape_still_denies_with_the_git_review_reason(self):
        # bin/ddl_setup.py doctor probes the installed hook this way and checks the `DDL Git review:` substring.
        project = pathlib.Path(self.tmp) / "doctor project"
        project.mkdir()
        (project / "CLAUDE.md").write_text("→ DDL-PROTOCOL\n", encoding="utf-8")
        records = {"claude": [{"type": "user", "message": {"role": "user", "content": "Continue."},
                               "origin": {"kind": "human"}, "turnOrigin": "human", "promptSource": "typed"}],
                   "codex": [{"type": "event_msg", "payload": {"type": "task_started", "turn_id": "doctor"}},
                             {"type": "response_item", "payload": {"type": "message", "role": "user",
                                                                   "content": [{"type": "input_text", "text": "Continue."}]}}]}
        for runtime, rows in records.items():
            write_rows(self.transcript, rows)
            for command, record, mode in (("git commit --cleanup=verbatim -m doctor", str(self.transcript), "default"),
                                          ("git push origin main", str(self.transcript), "default"),
                                          ("git push origin main", None, "default"),
                                          ("git push origin main", str(self.transcript), "bypassPermissions")):
                with self.subTest(runtime=runtime, command=command, record=record, mode=mode):
                    data = payload(runtime, cwd=str(project), transcript=record, session="doctor-" + runtime,
                                   permission_mode=mode, tool_name="Bash", tool_input={"command": command})
                    self.assertIn("DDL Git review:", self.blocked(self.run_gate("pre-tool-use", runtime, data)))

    def test_matching_native_choice_passes_without_granting_host_permission(self):
        for runtime in ("claude", "codex"):
            review = self.prepare(runtime)
            self.record(runtime, review)
            self.passed(runtime, self.check(runtime, permission_mode="bypassPermissions"))

    def test_hold_revision_and_normal_text_cannot_authorize_git(self):
        for runtime in ("claude", "codex"):
            review = self.prepare(runtime)
            for choice in (1, 2):
                self.record(runtime, review, choice)
                self.blocked(self.check(runtime))
            self.record(runtime, review)
            if runtime == "claude":
                row = user("OK", origin={"kind": "human"})
            else:
                row = {"type": "event_msg", "payload": {"type": "item_completed", "item": {
                    "type": "UserMessage", "content": [{"type": "text", "text": "OK"}]}}}
            with self.transcript.open("a") as f:
                f.write(json.dumps(row) + "\n")
            self.blocked(self.check(runtime))

    def test_missing_answer_or_request_denies_but_report_text_is_not_required(self):
        for runtime in ("claude", "codex"):
            review = self.prepare(runtime)
            def omit_detail(rows):
                entry = rows[0] if runtime == "claude" else rows[1]["payload"]
                message = entry["message"] if runtime == "claude" else entry
                message["content"][0]["text"] = "+++DDL_REPORT\nGit review " + review["reviewId"]
            with self.subTest(runtime=runtime, missing="answer"):
                self.record(runtime, review, mutate=lambda rows: rows.pop())
                reason = self.blocked(self.check(runtime))
                if runtime == "claude":  # the asked, unanswered question keeps its STOP pending and names it
                    self.assertTrue(reason.startswith(ddl_gate.WAITING_REASON.format(review["reviewId"], review["report"])))
                else:  # the next turn started without a reply
                    self.assertIn("DDL Git review:", reason)
            with self.subTest(runtime=runtime, missing="request"):
                self.record(runtime, review, mutate=lambda rows: rows.pop(1 if runtime == "claude" else 2))
                self.assertIn("DDL Git review:", self.blocked(self.check(runtime)))
            # The question carries the review; the chat report, whole or summarized, is not evidence either way.
            for change in (lambda rows: rows.pop(0 if runtime == "claude" else 1), omit_detail):
                with self.subTest(runtime=runtime, missing="report text"):
                    self.record(runtime, review, mutate=change)
                    self.passed(runtime, self.check(runtime))

    def test_report_recorded_only_as_thinking_still_proves_commit_and_push(self):
        for runtime in ("claude", "codex"):
            with self.subTest(runtime=runtime):
                self.stage("thinking " + runtime + "\n")
                review = self.prepare(runtime, [self.command, "git push origin main"])
                rows = self.record(runtime, review, variant="_thinking" if runtime == "claude" else "_reasoning")
                self.assertIn("+++DDL_REPORT", json.dumps(rows))  # present only where the gate never reads
                if runtime == "claude":
                    self.assertFalse(any(ddl_gate.claude_text(row) for row in rows if row["type"] == "assistant"))
                else:
                    self.assertFalse(any(row["payload"].get("type") in ("message", "agent_message") for row in rows))
                self.assert_allowed(self.ask(runtime, review["nativeRequest"], str(self.transcript)))
                self.passed(runtime, self.check(runtime))
                self.git("commit", "--cleanup=verbatim", "-F", str(self.message))
                self.pushed(runtime, self.check(runtime, "git push origin main"))

    def test_codex_desktop_preparation_and_receipt_do_not_authorize_git(self):
        review = self.prepare("codex", [self.command, "git push origin main"])
        rows = self.record("codex", review, variant="_reasoning", desktop=True)
        self.assertFalse(any(row["payload"].get("type") in ("message", "agent_message", "reasoning") for row in rows))
        pending = {"id": review["reviewId"], "report": review["report"]}
        waiting = ddl_gate.WAITING_REASON.format(review["reviewId"], review["report"])
        unrelated = {"questions": [{"title": "Which file first?", "options": ["A", "B"]}]}
        altered = json.loads(json.dumps(review["nativeRequest"]))
        altered["questions"][0]["title"] += " (changed)"
        for stage, record in (("prepared", rows[:3]), ("receipt", rows[:5])):
            with self.subTest(stage=stage):
                write_rows(self.transcript, record)
                with mock.patch.dict(os.environ, {"DDL_GATE_STATE_DIR": self.state}):
                    self.assertEqual(ddl_gate.scan_codex(self.transcript), (True, pending))
                for command in (self.command, "git push origin main", "touch x"):
                    self.assertTrue(self.blocked(self.check("codex", command)).startswith(waiting))
                self.assert_reason(self.ask("codex", unrelated, str(self.transcript)),
                                   ddl_gate.ASK_UNCHANGED.format(review["reviewId"]))
                self.assert_reason(self.ask("codex", altered, str(self.transcript)),
                                   ddl_gate.GIT_QUESTION_MISMATCH.format(review["reviewId"]))
                self.assert_allowed(self.ask("codex", review["nativeRequest"], str(self.transcript)))
        write_rows(self.transcript, rows)
        with mock.patch.dict(os.environ, {"DDL_GATE_STATE_DIR": self.state}):
            self.assertEqual(ddl_gate.scan_codex(self.transcript), (False, None))
        self.assert_allowed(self.check("codex"))
        self.git("commit", "--cleanup=verbatim", "-F", str(self.message))
        self.assert_allowed(self.check("codex", "git push origin main"))

    def test_codex_desktop_git_preparation_keeps_record_checks(self):
        review = self.prepare("codex")
        unknown = render(review, {review["reviewId"]: "G-0123456789abcdef"})
        self.record("codex", unknown, variant="_reasoning", desktop=True)
        self.assert_reason(self.ask("codex", unknown["nativeRequest"], str(self.transcript)),
                           ddl_gate.NOT_PREPARED.format(unknown["reviewId"]))
        changed = self.prepare("codex")
        (pathlib.Path(changed["report"]).parent / "review.json").write_text("{}\n")
        self.record("codex", changed, variant="_reasoning", desktop=True)
        self.assert_reason(self.ask("codex", changed["nativeRequest"], str(self.transcript)),
                           ddl_gate.NOT_PREPARED.format(changed["reviewId"]))
        foreign = self.prepare("claude")
        foreign["nativeRequest"] = {"questions": [foreign["question"]]}
        self.record("codex", foreign, variant="_reasoning", desktop=True)
        self.assert_reason(self.ask("codex", foreign["nativeRequest"], str(self.transcript)),
                           ddl_gate.NOT_PREPARED.format(foreign["reviewId"]))
        self.record("codex", review, variant="_reasoning", desktop=True)
        self.run_gate("session-start", "codex", payload("codex", "session-start", str(self.transcript),
                                                       cwd=str(self.repo), source="resume"))
        self.assert_reason(self.ask("codex", review["nativeRequest"], str(self.transcript)),
                           ddl_gate.PREDATES.format(review["reviewId"]))

    def test_altered_question_is_denied_and_cannot_authorize_git(self):
        for runtime in ("claude", "codex"):
            with self.subTest(runtime=runtime):
                review = self.prepare(runtime)
                key, execute = QUESTION_KEY[runtime], review["question"]["options"][0]
                altered = json.loads(json.dumps(review["nativeRequest"]))
                lines = altered["questions"][0][key].split("\n")
                lines[0] += "（修正）"
                altered["questions"][0][key] = "\n".join(lines)
                self.assert_reason(self.ask(runtime, altered),
                                   ddl_gate.GIT_QUESTION_MISMATCH.format(review["reviewId"]))
                self.assert_allowed(self.ask(runtime, review["nativeRequest"]))

                def alter(rows):
                    for row in rows:
                        for block in (row.get("message") or {}).get("content", []):
                            if isinstance(block, dict) and block.get("type") == "tool_use":
                                block["input"] = altered
                        if (row.get("payload") or {}).get("type") == "function_call":
                            row["payload"]["arguments"] = json.dumps(altered)
                    if runtime == "claude":
                        rows[-1]["toolUseResult"]["answers"] = {altered["questions"][0][key]: execute}
                    else:
                        rows[-1]["payload"]["item"]["content"][0]["text"] = codex_reply(
                            "git-review-call", altered["questions"][0][key], execute)
                self.record(runtime, review, mutate=alter)
                self.assertIn("does not match", self.blocked(self.check(runtime)))

    def test_git_question_after_resume_or_for_another_runtime_is_denied(self):
        for runtime, other in (("claude", "codex"), ("codex", "claude")):
            with self.subTest(runtime=runtime):
                review = self.prepare(runtime)
                foreign = self.prepare(other)
                foreign_request = json.loads(json.dumps(review["nativeRequest"]))
                key = QUESTION_KEY[runtime]
                foreign_request["questions"][0][key] = foreign["question"]["title"]
                self.assert_reason(self.ask(runtime, foreign_request), ddl_gate.NOT_PREPARED.format(foreign["reviewId"]))
                self.assert_allowed(self.ask(runtime, review["nativeRequest"]))
                self.run_gate("session-start", runtime, payload(runtime, "session-start", fixture(runtime + "_open.jsonl"),
                                                                cwd=str(self.repo), source="compact"))
                self.assert_reason(self.ask(runtime, review["nativeRequest"]), ddl_gate.PREDATES.format(review["reviewId"]))

    def test_git_question_names_what_will_run(self):
        review = self.prepare("claude")
        self.assertEqual(review["question"]["title"].split("\n"), [
            "決めること: コミット「Record reviewed contents」（1 ファイル）を main に記録するか",
            "推奨: この内容で実行する。内容・メッセージ・送信先は全文と差分のとおり",
            "影響: main に新しいコミットができる（送信はしない）",
            "確認 ID: " + review["reviewId"], "全文: " + review["report"]])
        self.assertTrue(os.path.isabs(review["report"]))
        self.assertEqual(ddl_gate.question_id(review["question"]["title"]), ("G", review["reviewId"][2:]))
        self.assertIn(review["question"]["title"], pathlib.Path(review["report"]).read_text(encoding="utf-8"))
        self.assertEqual(review["nativeRequest"]["questions"][0]["header"], "Git")
        both = self.prepare("codex", [self.command, "git push origin main"])
        lines = both["question"]["title"].split("\n")
        self.assertEqual(lines[0], "決めること: コミット「Record reviewed contents」（1 ファイル）を main に記録し、origin/main に送るか")
        self.assertEqual(lines[2], "影響: origin/main が新しいコミットに進む。取り消すには revert が要る")
        self.assertEqual(both["nativeRequest"], {"questions": [both["question"]]})
        push = self.prepare("codex", ["git push origin main"])
        self.assertEqual(push["question"]["title"].split("\n")[0],
                         "決めること: {} を origin/main に送るか".format(self.git("rev-parse", "HEAD")[:ddl_gate.SHORT_SHA_LENGTH]))

    def test_wrong_native_request_id_or_question_is_denied(self):
        for runtime in ("claude", "codex"):
            review = self.prepare(runtime)
            rows = self.record(runtime, review)
            if runtime == "claude":
                rows[-1]["message"]["content"][0]["tool_use_id"] = "another-call"
            else:
                rows[2]["payload"]["call_id"] = "another-call"
            self.transcript.write_text("".join(json.dumps(row) + "\n" for row in rows))
            self.blocked(self.check(runtime))

    def test_claude_auto_timeout_and_nonhuman_permission_are_denied(self):
        review = self.prepare("claude")
        for auto in (True, False):
            rows = self.record("claude", review)
            if auto:
                rows[-1]["toolUseResult"]["afkTimeoutMs"] = 60000
            else:
                rows[-1]["permissionDecision"]["source"] = "config"
            self.transcript.write_text("".join(json.dumps(row) + "\n" for row in rows))
            self.blocked(self.check("claude"))

    def test_codex_timeout_metadata_and_changed_question_are_unprovable(self):
        review = self.prepare("codex")
        rows = self.record("codex", review)
        text = rows[-1]["payload"]["item"]["content"][0]
        reply = json.loads(text["text"].split("\n")[1]);reply[0]["timedOut"] = True
        text["text"] = "<send_user_message_question_reply>\n" + json.dumps(reply) + "\n</send_user_message_question_reply>"
        self.transcript.write_text("".join(json.dumps(row) + "\n" for row in rows))
        self.blocked(self.check("codex"))
        rows = self.record("codex", review)
        request = json.loads(rows[2]["payload"]["arguments"])
        request["questions"][0]["options"][1] = "Different consequence"
        rows[2]["payload"]["arguments"] = json.dumps(request)
        self.transcript.write_text("".join(json.dumps(row) + "\n" for row in rows))
        self.blocked(self.check("codex"))

    def test_staged_contents_message_and_branch_changes_are_denied(self):
        for runtime in ("claude", "codex"):
            review = self.prepare(runtime)
            self.record(runtime, review)
            self.stage("changed after review\n")
            self.blocked(self.check(runtime))
            self.stage("reviewed\n")
            original = self.message.read_text()
            self.message.write_text("Unreviewed message\n")
            self.blocked(self.check(runtime))
            self.message.write_text(original)
            self.git("checkout", "-q", "-b", "other-" + runtime)
            self.blocked(self.check(runtime))
            self.git("checkout", "-q", "main")
            self.passed(runtime, self.check(runtime))

    def test_review_file_diff_and_report_tampering_are_denied(self):
        for runtime in ("claude", "codex"):
            for name in ("review.json", "1.patch", "report.md"):
                review = self.prepare(runtime)
                self.record(runtime, review)
                path = pathlib.Path(review["report"]).parent / name
                if name == "review.json":
                    data = json.loads(path.read_text());data["operations"][0]["message"] = "forged\n"
                    path.write_text(json.dumps(data))
                else:
                    path.write_text("changed review")
                self.blocked(self.check(runtime))

    def test_resume_compact_and_clear_invalidate_previous_review(self):
        for runtime in ("claude", "codex"):
            for source in ("resume", "compact", "fork", "clear"):
                review = self.prepare(runtime)
                self.record(runtime, review)
                self.passed(runtime, self.check(runtime))
                self.run_gate("session-start", runtime, payload(runtime, "session-start", str(self.transcript),
                              cwd=str(self.repo), source=source))
                self.blocked(self.check(runtime))

    def test_push_destination_url_and_source_changes_are_denied(self):
        for runtime in ("claude", "codex"):
            review = self.prepare(runtime, ["git push origin main"])
            self.record(runtime, review)
            self.pushed(runtime, self.check(runtime, "git push origin main"))
            self.blocked(self.check(runtime, "git push origin main:refs/heads/other"))
            self.git("remote", "set-url", "origin", str(self.remote) + "-other")
            self.blocked(self.check(runtime, "git push origin main"))
            self.git("remote", "set-url", "origin", str(self.remote))

    def test_one_native_answer_covers_commit_and_its_exact_push(self):
        for runtime in ("claude", "codex"):
            self.stage("reviewed " + runtime + "\n")
            review = self.prepare(runtime, [self.command, "git push origin main"])
            self.record(runtime, review)
            self.passed(runtime, self.check(runtime))
            self.blocked(self.check(runtime, "git push origin main"))  # the planned commit does not exist yet
            self.git("commit", "--cleanup=verbatim", "-F", str(self.message))
            self.blocked(self.check(runtime))  # an approval cannot create a second, different commit
            self.pushed(runtime, self.check(runtime, "git push origin main"))
            self.git("push", "origin", "main")
            self.pushed(runtime, self.check(runtime, "git push origin main"))  # an idempotent retry sends no new content

    def test_claude_reviewed_commit_and_push_are_allowed_without_a_second_question(self):
        review = self.prepare("claude", [self.command, "git push origin main"])
        self.record("claude", review)
        self.passed("claude", self.check("claude"), review)  # the review was the one confirmation
        self.git("commit", "--cleanup=verbatim", "-F", str(self.message))
        for mode in ("default", "acceptEdits", "bypassPermissions", "dontAsk"):
            with self.subTest(mode=mode):  # the same allow in every mode; the user's deny and ask rules still win
                self.passed("claude", self.check("claude", "git push origin main", permission_mode=mode), review)
        self.assertEqual(events(self.repo, kind="ask"), [])  # the push is no longer asked again
        self.assertEqual([(row["allow"], row["id"]) for row in events(self.repo, kind="allowed")],
                         [("commit", review["reviewId"])] + [("push", review["reviewId"])] * 4)
        self.assertEqual(untimed(events(self.repo, kind="allowed"))[0], {
            "v": 1, "host": "claude", "session": "sess", "kind": "allowed", "allow": "commit", "id": review["reviewId"],
            "tool": "Bash", "toolUseId": "toolu_01"})
        self.assertEqual(events(self.repo, kind="granted"), [])  # a Git review is no grant
        self.assertIn("DDL Git review", self.blocked(self.check("claude", "git push origin main:refs/heads/other")))

    def notebook(self):
        """A second Git directory `.notebook.git` over the same work tree (no remote), its design.md staged; the
        commit command that records it."""
        pair = ("--git-dir=.notebook.git", "--work-tree=.")
        self.git("--git-dir=.notebook.git", "init", "-q", "-b", "main")
        for key, value in (("user.email", "fixture@example.invalid"), ("user.name", "DDL fixture"), ("commit.gpgSign", "false")):
            self.git(*pair, "config", key, value)
        with (self.repo / ".git" / "info" / "exclude").open("a") as fh:
            fh.write(".notebook.git\ndesign.md\n.claude/\n")
        (self.repo / "design.md").write_text("first\n")
        self.git(*pair, "add", "design.md")
        self.git(*pair, "commit", "-q", "--cleanup=verbatim", "-m", "notebook base")
        (self.repo / "design.md").write_text("reviewed notebook\n")
        self.git(*pair, "add", "design.md")
        return "git --git-dir=.notebook.git --work-tree=. commit --cleanup=verbatim -F " + shlex.quote(str(self.message))

    def test_a_second_git_directory_is_its_own_repository_in_one_review(self):
        notebook = self.notebook()
        for runtime in ("claude", "codex"):
            with self.subTest(runtime=runtime):
                review = self.prepare(runtime, [self.command, notebook])
                ops = json.loads((pathlib.Path(review["report"]).parent / "review.json").read_text())["operations"]
                git_dir = os.path.realpath(str(self.repo / ".notebook.git"))
                self.assertEqual([(op["repo"], op.get("gitDir"), op.get("workTree")) for op in ops],
                                 [(os.path.realpath(str(self.repo)), None, None),
                                  (git_dir, git_dir, os.path.realpath(str(self.repo)))])
                self.assertEqual([[path for _, path in op["files"]] for op in ops], [["sample.txt"], ["design.md"]])
                self.assertEqual(review["question"]["title"].splitlines()[0],
                                 "決めること: 2 件のコミット（review repo、review repo (.notebook.git)）を記録するか")
                self.assertIn("main（review repo (.notebook.git)）", review["question"]["title"].splitlines()[2])
                self.assertIn("## 2. 記録 — {} ({})".format(os.path.realpath(str(self.repo)), git_dir),
                              pathlib.Path(review["report"]).read_text())
                self.record(runtime, review)
                self.passed(runtime, self.check(runtime, notebook), review)
                self.passed(runtime, self.check(runtime), review)
                self.passed(runtime, self.check(runtime, "git -C " + shlex.quote(str(self.repo)) + notebook[3:]), review)
                if runtime == "codex":
                    self.assertEqual(self.permitted(runtime, notebook), ALLOW_PERMISSION)
                # What the review did not show is denied: other staged contents in that repository.
                for text in ("changed after the review\n", "reviewed notebook\n"):
                    (self.repo / "design.md").write_text(text)
                    self.git("--git-dir=.notebook.git", "--work-tree=.", "add", "design.md")
                    if text.startswith("changed"):
                        self.assertIn("differ from the approved set", self.blocked(self.check(runtime, notebook)))
                        if runtime == "codex":
                            self.assertIsNone(self.permitted(runtime, notebook))
        write_rows(self.transcript, [])  # and no review at all
        for runtime in ("claude", "codex"):
            self.assertIn("DDL Git review", self.blocked(self.check(runtime, notebook)))

    def test_a_second_git_directory_takes_only_its_supported_form(self):
        self.notebook()
        message = shlex.quote(str(self.message))
        for command, problem in (
                ("git -C .notebook.git commit --cleanup=verbatim -F " + message, "run Git from the work tree"),
                ("git --git-dir=.notebook.git commit --cleanup=verbatim -F " + message, "second Git directory"),
                ("git --git-dir=.notebook.git --work-tree=. push origin main", "pushing from it is not supported"),
                ("git --git-dir=.notebook.git --work-tree=. -C . commit --cleanup=verbatim -F " + message,
                 "put -C before --git-dir"),
                ("git --git-dir=missing.git --work-tree=. commit --cleanup=verbatim -F " + message, "missing.git")):
            with self.subTest(command=command):
                proc = self.subcommand(["prepare-git-review", "--runtime", "codex"],
                                       {"operations": [{"cwd": str(self.repo), "command": command}]})
                self.assertEqual(proc.returncode, 2)
                self.assertIn(problem, proc.stderr)
                self.assertIn("DDL Git review", self.blocked(self.check("claude", command)))

    def test_codex_reviewed_commit_and_push_are_allowed_by_its_permission_request(self):
        review = self.prepare("codex", [self.command, "git push origin main"])
        self.record("codex", review)
        allow = {"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": {"behavior": "allow"}}}
        self.passed("codex", self.check("codex"))  # Codex's PreToolUse never prints an allow
        self.assertEqual(self.permitted("codex"), allow)
        self.git("commit", "--cleanup=verbatim", "-F", str(self.message))
        self.passed("codex", self.check("codex", "git push origin main"))
        self.assertEqual(self.permitted("codex", "git push origin main"), allow)
        # Nothing else: an unmatched push, another destination, a call without a review.
        for command in ("git push origin main:refs/heads/other", "git commit --cleanup=verbatim -m other", "touch x"):
            with self.subTest(command=command):
                self.assertIsNone(self.permitted("codex", command))
        rows = events(self.repo, kind="allowed")
        self.assertEqual([(row["allow"], row["id"], row.get("toolUseId")) for row in rows],
                         [("commit", review["reviewId"], None), ("push", review["reviewId"], None)])
        # Codex's PreToolUse logged no allow of its own: the PermissionRequest is the allow.
        self.assertEqual({row["host"] for row in rows}, {"codex"})

    def test_push_rejects_commit_created_with_different_message_or_tree(self):
        review = self.prepare("codex", [self.command, "git push origin main"])
        self.record("codex", review)
        self.git("commit", "--cleanup=verbatim", "-m", "different")
        self.blocked(self.check("codex", "git push origin main"))

    def test_push_rejects_unreviewed_tree_even_with_the_approved_message(self):
        review = self.prepare("codex", [self.command, "git push origin main"])
        self.record("codex", review)
        self.stage("unreviewed tree\n")
        self.git("commit", "--cleanup=verbatim", "-F", str(self.message))
        self.blocked(self.check("codex", "git push origin main"))

    def test_crlf_message_bytes_are_preserved_for_the_dependent_push(self):
        self.message.write_bytes(b"Reviewed message\r\n\r\nKeep CRLF.\r\n")
        review = self.prepare("codex", [self.command, "git push origin main"])
        self.record("codex", review)
        self.assert_allowed(self.check("codex"))
        self.git("commit", "--cleanup=verbatim", "-F", str(self.message))
        self.assert_allowed(self.check("codex", "git push origin main"))
        self.stage("another reviewed snapshot\n")
        args = ["commit", "--cleanup=verbatim", "-m", "first paragraph\n", "-m", "second paragraph"]
        command = shlex.join(["git", *args])
        review = self.prepare("codex", [command, "git push origin main"])
        self.record("codex", review)
        self.assert_allowed(self.check("codex", command))
        self.git(*args)
        self.assert_allowed(self.check("codex", "git push origin main"))

    def test_compatible_repositories_share_one_native_answer(self):
        other = pathlib.Path(self.tmp) / "another repo";other.mkdir();mark_project(other, "AGENTS.md")
        for args in (["init", "-q", "-b", "main"], ["add", "other.txt"]):
            (other / "other.txt").write_text("second repository\n")
            proc = subprocess.run(["git", "-C", str(other), *args], capture_output=True, env=self.git_env)
            self.assertEqual(proc.returncode, 0, proc.stderr)
        data = {"operations": [{"cwd": str(self.repo), "command": self.command},
                               {"cwd": str(other), "command": self.command}]}
        review = json.loads(self.run_gate("prepare-git-review", "codex", data).stdout)
        self.record("codex", review)
        self.assert_allowed(self.check("codex"))
        call = payload("codex", cwd=str(other), transcript=str(self.transcript), tool_name="Bash",
                       tool_input={"command": self.command})
        self.assert_allowed(self.run_gate("pre-tool-use", "codex", call))

    def test_internal_git_timeout_denies_instead_of_using_general_fail_open(self):
        data = payload("codex", cwd=str(self.repo), tool_name="Bash", tool_input={"command": self.command})
        with mock.patch.object(ddl_gate, "approved_git_review", side_effect=TimeoutError("probe timeout")):
            result = ddl_gate.git_review_guard("codex", data)
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn("probe timeout", result["hookSpecificOutput"]["permissionDecisionReason"])

    def test_intent_to_add_is_not_misrepresented_as_committed_content(self):
        (self.repo / "intent.txt").write_text("not fully staged\n")
        self.git("add", "-N", "intent.txt")
        proc = subprocess.run([sys.executable, "-I", GATE, "prepare-git-review", "--runtime", "codex"],
                              input=json.dumps({"operations": [{"cwd": str(self.repo), "command": self.command}]}),
                              capture_output=True, text=True, env=self.gate_env(), cwd=str(PROJECT))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("intent-to-add", proc.stderr)

    def test_literal_examples_and_program_source_are_data_not_git_operations(self):
        for command in ("echo 'git commit -m example'", "printf '%s' '$(git commit -m example)'",
                        "python3 - <<'PY'\nprint('git commit -m example')\nPY",
                        "cat <<'EXAMPLE'\ngit commit -m example\nEXAMPLE"):
            with self.subTest(command=command):
                self.assertFalse(ddl_gate.visible_git_write(command))
        self.assertTrue(ddl_gate.visible_git_write("cat <<'EXAMPLE'\ngit commit -m example\nEXAMPLE\ngit push origin main"))

    def test_new_prompt_revokes_old_git_approval_before_transcript_flush(self):
        for runtime in ("claude", "codex"):
            review = self.prepare(runtime)
            self.record(runtime, review)
            self.passed(runtime, self.check(runtime))
            self.run_gate("user-prompt-submit", runtime, payload(runtime, "user-prompt-submit", str(self.transcript),
                          cwd=str(self.repo), prompt="Please revise; do not execute."))
            self.blocked(self.check(runtime))  # the file still contains the earlier approved answer

    def test_codex_native_submission_does_not_revoke_its_own_preparation(self):
        review = self.prepare("codex")
        rows = self.record("codex", review)
        prompt = rows[-1]["payload"]["item"]["content"][0]["text"]
        self.transcript.write_text("".join(json.dumps(row) + "\n" for row in rows[:-1]))
        self.run_gate("user-prompt-submit", "codex", payload("codex", "user-prompt-submit", str(self.transcript),
                      cwd=str(self.repo), prompt=prompt))
        self.blocked(self.check("codex"))  # the receipt has not been recorded yet
        self.transcript.write_text("".join(json.dumps(row) + "\n" for row in rows))
        self.assert_allowed(self.check("codex"))

    def test_push_cannot_implicitly_send_tags_or_submodules(self):
        self.git("config", "push.followTags", "true")
        self.git("config", "push.recurseSubmodules", "on-demand")
        command = "git push --no-follow-tags --recurse-submodules=no origin main"
        review = self.prepare("codex", [command])
        self.record("codex", review)
        self.assert_allowed(self.check("codex", command))
        self.blocked(self.check("codex", "git push --recurse-submodules=no origin main"))
        self.blocked(self.check("codex", "git push --no-follow-tags origin main"))

    def test_subdirectory_and_relative_diff_config_still_review_the_entire_index(self):
        nested = self.repo / "src";nested.mkdir()
        (nested / "inside.txt").write_text("inside\n");self.git("add", "src/inside.txt")
        self.git("config", "diff.relative", "true")
        review = json.loads(self.run_gate("prepare-git-review", "codex", {"operations": [
            {"cwd": str(nested), "command": self.command}]}).stdout)
        record = json.loads((pathlib.Path(review["report"]).parent / "review.json").read_text())
        self.assertEqual({p for _, p in record["operations"][0]["files"]}, {"sample.txt", "src/inside.txt"})
        self.record("codex", review)
        data = payload("codex", cwd=str(nested), transcript=str(self.transcript), tool_name="Bash",
                       tool_input={"command": self.command})
        self.assert_allowed(self.run_gate("pre-tool-use", "codex", data))
        self.stage("changed outside the subdirectory\n")
        self.blocked(self.run_gate("pre-tool-use", "codex", data))

    def test_unstaged_files_are_not_silently_added_to_the_approved_commit(self):
        review = self.prepare("codex")
        self.record("codex", review)
        (self.repo / "unrelated.txt").write_text("not staged\n")
        self.assert_allowed(self.check("codex"))
        self.git("add", "unrelated.txt")
        self.blocked(self.check("codex"))

    def test_workdir_and_literal_git_C_resolve_the_repository(self):
        review = self.prepare("codex")
        self.record("codex", review)
        mark_project(self.tmp, "CLAUDE.md")  # the session's cwd decides the project, the tool's workdir the repository
        data = payload("codex", cwd=self.tmp, transcript=str(self.transcript), tool_name="exec_command",
                       tool_input={"cmd": self.command, "workdir": str(self.repo)})
        self.assert_allowed(self.run_gate("pre-tool-use", "codex", data))
        command = "git -C " + shlex.quote(str(self.repo)) + self.command[3:]
        self.assert_allowed(self.check("codex", command))

    def test_wrappers_compound_writes_and_unreviewed_options_are_denied(self):
        review = self.prepare("codex")
        self.record("codex", review)
        for command in ("env " + self.command, "env -i " + self.command, "env -u EXAMPLE " + self.command,
                        "command -p " + self.command, "sudo " + self.command,
                        "bash -lc " + shlex.quote(self.command),
                        "git add sample.txt && " + self.command, self.command + " --amend",
                        "git commit-tree HEAD^{tree}", "git send-pack origin main", "git $OPERATION",
                        'printf "%s" "$(git commit -m bypass)"'):
            with self.subTest(command=command):
                self.blocked(self.check("codex", command))

    def test_merge_state_and_non_verbatim_message_do_not_reuse_an_ordinary_review(self):
        review = self.prepare("codex")
        self.record("codex", review)
        self.blocked(self.check("codex", self.command.replace("--cleanup=verbatim ", "")))
        (self.repo / ".git" / "MERGE_HEAD").write_text(self.git("rev-parse", "HEAD") + "\n")
        self.blocked(self.check("codex"))

    def test_claude_report_and_question_in_one_assistant_message(self):
        review = self.prepare("claude")
        rows = self.record("claude", review)
        rows[1]["message"]["content"].insert(0, rows.pop(0)["message"]["content"][0])
        self.transcript.write_text("".join(json.dumps(row) + "\n" for row in rows))
        self.passed("claude", self.check("claude"))

    def test_initial_commit_and_push_share_one_review(self):
        self.git("checkout", "--orphan", "first")
        self.git("add", "sample.txt")
        review = self.prepare("codex", [self.command, "git push origin first"])
        self.record("codex", review)
        self.assert_allowed(self.check("codex"))
        self.git("commit", "--cleanup=verbatim", "-F", str(self.message))
        self.assert_allowed(self.check("codex", "git push origin first"))

    def test_remote_credentials_are_not_written_in_review_detail(self):
        self.git("remote", "set-url", "origin", "https://fixture:PRIVATE_CREDENTIAL@example.invalid/repo.git")
        review = self.prepare("codex", ["git push origin main"])
        directory = pathlib.Path(review["report"]).parent
        for path in directory.iterdir():
            self.assertNotIn("PRIVATE_CREDENTIAL", path.read_text())
        self.assertEqual(directory.stat().st_mode & 0o777, 0o700)

    def test_cli_preparation_errors_are_nonzero_and_never_approval(self):
        for data in ({"operations": []}, {"operations": [{"cwd": str(self.repo), "command": "git commit -m x"}]}):
            proc = subprocess.run([sys.executable, "-I", GATE, "prepare-git-review", "--runtime", "codex"],
                                  input=json.dumps(data), capture_output=True, text=True, env=self.gate_env(),
                                  cwd=str(PROJECT))
            self.assertEqual(proc.returncode, 2)
            self.assertIn("DDL Git review", proc.stderr)


PREPARE_CALL = {runtime: "python3 \"$HOME/.{0}/hooks/ddl_gate.py\" prepare-report --runtime {0} <<'JSON'\n"
                         "{{\"language\": \"ja\", \"detail\": \"$(not expanded)\"}}\nJSON".format(runtime)
                for runtime in ("claude", "codex")}
FLOW_STAGES = {"claude": {"prepared": 3, "asked": 4, "answered": 5}, "codex": {"prepared": 5, "asked": 8, "answered": 10}}
WRITES = {"claude": [("Edit", {"file_path": "design.md", "old_string": "a", "new_string": "b"}),
                     ("Write", {"file_path": "x.txt", "content": "x"}), ("Agent", {"prompt": "continue"})],
          "codex": [("apply_patch", {"patch": "*** Begin Patch\n*** End Patch"}), ("spawn_agent", {"message": "continue"})]}
READS = {"claude": [("Read", {"file_path": "design.md"}), ("Bash", {"command": "git status"})],
         "codex": [("exec_command", {"cmd": "rg -n DDL design.md"})]}
# A write no grant answers for: outside every project root (Claude), a patch without a target (Codex).
HOST_WRITES = {"claude": ("Edit", {"file_path": "/ddl-gate-fixture/outside.md", "old_string": "a", "new_string": "b"}),
               "codex": WRITES["codex"][0]}
SHELL = {"claude": ("Bash", "command"), "codex": ("exec_command", "cmd")}


def option_label(prepared, index=0):
    option = prepared["nativeRequest"]["questions"][0]["options"][index]
    return option["label"] if isinstance(option, dict) else option


class ReportFlowTest(GateTest):
    """Builds the report_flow transcript of a prepared report; the classes below share it."""

    def flow(self, runtime, prepared, stage, answer=0, desktop=False, mutate=None):
        """The report_flow transcript cut after `stage`: prepared, asked, or answered (option `answer`)."""
        question, label = prepared["question"], option_label(prepared, answer)
        replacements = {"@PREPARE_COMMAND@": PREPARE_CALL[runtime],
                        "@PREPARE_ARGS_JSON@": json.dumps({"cmd": PREPARE_CALL[runtime]}),
                        "@PREPARED_JSON@": json.dumps(prepared), "@REQUEST@": prepared["nativeRequest"],
                        "@REQUEST_JSON@": json.dumps(prepared["nativeRequest"]), "@ANSWERS@": {question: label},
                        "@REPLY@": codex_reply("report-question", question, label)}
        rows = template_rows("report_flow_" + runtime + ".jsonl", replacements)[:FLOW_STAGES[runtime][stage]]
        if desktop:
            rows = codex_desktop_preparation(rows, prepared)
        if mutate:
            mutate(rows)
        path = os.path.join(self.tmp, "{}-{}.jsonl".format(runtime, stage))
        write_rows(path, rows)
        return path

    def call(self, runtime, transcript, tool, tool_input, session="sess", **extra):
        return self.run_gate("pre-tool-use", runtime, payload(runtime, transcript=transcript, session=session,
                                                              tool_name=tool, tool_input=tool_input, **extra))

    def scan(self, runtime, transcript):
        with mock.patch.dict(os.environ, {"DDL_GATE_STATE_DIR": self.state}):
            return (ddl_gate.scan_codex if runtime == "codex" else ddl_gate.scan_claude)(transcript)


class ReportStopTest(ReportFlowTest):
    """A decision report proved from its prepared question, with the report text recorded only as thinking."""

    def test_prepared_report_holds_writes_until_its_question_is_answered(self):
        for runtime in ("claude", "codex"):
            with self.subTest(runtime=runtime):
                prepared = self.prepare_report(runtime)
                pending = {"id": prepared["reportId"], "report": prepared["report"]}
                waiting = ddl_gate.WAITING_REASON.format(prepared["reportId"], prepared["report"])
                for stage in ("prepared", "asked"):
                    transcript = self.flow(runtime, prepared, stage)
                    self.assertEqual(self.scan(runtime, transcript), (True, pending))
                    for tool, tool_input in WRITES[runtime]:
                        self.assert_reason(self.call(runtime, transcript, tool, tool_input), waiting)
                    shell, key = SHELL[runtime]
                    self.assert_reason(self.call(runtime, transcript, shell, {key: "touch x"}),
                                       waiting + SEGMENT_SUFFIX.format("touch x"))
                    for tool, tool_input in READS[runtime]:
                        self.assert_allowed(self.call(runtime, transcript, tool, tool_input))
                transcript = self.flow(runtime, prepared, "answered")
                self.assertEqual(self.scan(runtime, transcript), (False, None))
                for tool, tool_input in WRITES[runtime]:
                    self.assert_allowed(self.call(runtime, transcript, tool, tool_input))

    def test_codex_desktop_report_holds_writes_until_answered(self):
        prepared = self.prepare_report("codex")
        pending = {"id": prepared["reportId"], "report": prepared["report"]}
        waiting = ddl_gate.WAITING_REASON.format(prepared["reportId"], prepared["report"])
        unrelated = {"questions": [{"title": "Which file first?", "options": ["A", "B"]}]}
        altered = json.loads(json.dumps(prepared["nativeRequest"]))
        altered["questions"][0]["title"] += " (changed)"
        for stage in ("prepared", "asked", "answered"):
            with self.subTest(stage=stage):
                transcript = self.flow("codex", prepared, stage, desktop=True)
                rows = [json.loads(line) for line in pathlib.Path(transcript).read_text().splitlines()]
                self.assertFalse(any(row["payload"].get("type") in ("message", "agent_message", "reasoning") for row in rows))
                self.assertEqual(self.scan("codex", transcript), (False, None) if stage == "answered" else (True, pending))
                for tool, tool_input in WRITES["codex"]:
                    proc = self.call("codex", transcript, tool, tool_input)
                    if stage == "answered":
                        self.assert_allowed(proc)
                    else:
                        self.assert_reason(proc, waiting)
                if stage != "answered":
                    self.assert_reason(self.call("codex", transcript, "exec_command", {"cmd": "touch x"}),
                                       waiting + SEGMENT_SUFFIX.format("touch x"))
                    self.assert_reason(self.call("codex", transcript, QUESTION_TOOL["codex"], unrelated),
                                       ddl_gate.ASK_UNCHANGED.format(prepared["reportId"]))
                    self.assert_reason(self.call("codex", transcript, QUESTION_TOOL["codex"], altered),
                                       ddl_gate.ASK_UNCHANGED.format(prepared["reportId"]))
                    self.assert_allowed(self.call("codex", transcript, QUESTION_TOOL["codex"], prepared["nativeRequest"]))

    def test_codex_desktop_report_keeps_record_checks(self):
        prepared = self.prepare_report("codex")
        unknown = render(prepared, {prepared["reportId"]: "R-0123456789abcdef"})
        changed = self.prepare_report("codex")
        with open(changed["report"], "a", encoding="utf-8") as fh:
            fh.write("Changed after preparation.\n")
        foreign = self.prepare_report("claude")
        foreign["nativeRequest"] = {"questions": [{"title": foreign["question"], "options": ["A", "B"]}]}
        for invalid in (unknown, changed, foreign):
            with self.subTest(report=invalid["reportId"]):
                transcript = self.flow("codex", invalid, "prepared", desktop=True)
                self.assert_reason(self.call("codex", transcript, QUESTION_TOOL["codex"], invalid["nativeRequest"]),
                                   ddl_gate.NOT_PREPARED.format(invalid["reportId"]))
        transcript = self.flow("codex", prepared, "prepared", desktop=True)
        self.run_gate("session-start", "codex", payload("codex", "session-start", transcript, source="resume"))
        self.assert_reason(self.call("codex", transcript, QUESTION_TOOL["codex"], prepared["nativeRequest"]),
                           ddl_gate.PREDATES.format(prepared["reportId"]))

    def test_question_without_the_pending_id_is_denied(self):
        ordinary = {"claude": {"questions": [{"question": "Which file first?", "header": "Order", "multiSelect": False,
                                              "options": [{"label": "A", "description": "a"},
                                                          {"label": "B", "description": "b"}]}]},
                    "codex": {"questions": [{"title": "Which file first?", "options": ["A", "B"]}]}}
        for runtime in ("claude", "codex"):
            with self.subTest(runtime=runtime):
                prepared = self.prepare_report(runtime)
                transcript, tool = self.flow(runtime, prepared, "prepared"), QUESTION_TOOL[runtime]
                unchanged = ddl_gate.ASK_UNCHANGED.format(prepared["reportId"])
                self.assert_reason(self.call(runtime, transcript, tool, ordinary[runtime]), unchanged)
                altered = json.loads(json.dumps(prepared["nativeRequest"]))
                lines = altered["questions"][0][QUESTION_KEY[runtime]].split("\n")
                lines[1] += "（変更）"
                altered["questions"][0][QUESTION_KEY[runtime]] = "\n".join(lines)
                self.assert_reason(self.call(runtime, transcript, tool, altered), unchanged)
                self.assert_allowed(self.call(runtime, transcript, tool, prepared["nativeRequest"]))
                # A STOP marked only in text has no prepared question to name.
                self.assert_reason(self.call(runtime, fixture(runtime + "_closed_in_turn.jsonl"), tool, ordinary[runtime]),
                                   ddl_gate.PREPARE_FIRST)
                # Ordinary questions keep working while nothing is pending.
                self.assert_allowed(self.call(runtime, fixture(runtime + "_open.jsonl"), tool, ordinary[runtime]))

    def test_the_gates_own_preparation_call_runs_while_pending(self):
        for runtime in ("claude", "codex"):
            with self.subTest(runtime=runtime):
                prepared = self.prepare_report(runtime)
                transcript = self.flow(runtime, prepared, "prepared")
                shell, key = SHELL[runtime]
                own = ("python3 -I " + shlex.quote(GATE) + " prepare-git-review --runtime " + runtime +
                       " <<\"EOF\"\n{\"language\": \"ja\", \"operations\": []}\nEOF\n")
                for command in (PREPARE_CALL[runtime], own):
                    self.assert_allowed(self.call(runtime, transcript, shell, {key: command}))
                for command in (PREPARE_CALL[runtime] + "\ntouch x",
                                PREPARE_CALL[runtime].replace("'JSON'\n{", "'JSON'\n{}\nJSON\ntouch x\n{"),
                                PREPARE_CALL[runtime].replace("<<'JSON'", "<<'JSON' | tee x"),
                                PREPARE_CALL[runtime].replace("<<'JSON'", "<<JSON"),
                                PREPARE_CALL[runtime].replace("prepare-report", "pre-tool-use")):
                    with self.subTest(command=command):
                        out = json.loads(self.call(runtime, transcript, shell, {key: command}).stdout)
                        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")
                        self.assertTrue(out["hookSpecificOutput"]["permissionDecisionReason"].startswith(
                            ddl_gate.WAITING_REASON.format(prepared["reportId"], prepared["report"])))

    def test_stale_unknown_or_changed_ids_are_denied(self):
        for runtime in ("claude", "codex"):
            with self.subTest(runtime=runtime):
                prepared = self.prepare_report(runtime)
                tool, key, opened = QUESTION_TOOL[runtime], QUESTION_KEY[runtime], fixture(runtime + "_open.jsonl")
                self.assert_allowed(self.call(runtime, opened, tool, prepared["nativeRequest"]))
                forged = json.loads(json.dumps(prepared["nativeRequest"]))
                forged["questions"][0][key] = forged["questions"][0][key].replace(prepared["reportId"], "R-0123456789abcdef")
                self.assert_reason(self.call(runtime, opened, tool, forged), ddl_gate.NOT_PREPARED.format("R-0123456789abcdef"))
                changed = self.prepare_report(runtime)
                with open(changed["report"], "a", encoding="utf-8") as fh:
                    fh.write("- R4 added after preparation\n")
                self.assert_reason(self.call(runtime, opened, tool, changed["nativeRequest"]),
                                   ddl_gate.NOT_PREPARED.format(changed["reportId"]))
                self.run_gate("session-start", runtime, payload(runtime, "session-start", opened, source="resume"))
                self.assert_reason(self.call(runtime, opened, tool, prepared["nativeRequest"]),
                                   ddl_gate.PREDATES.format(prepared["reportId"]))
                self.assert_allowed(self.call(runtime, opened, tool, self.prepare_report(runtime)["nativeRequest"]))

    def test_stop_marks_and_compaction_names_the_pending_report(self):
        for runtime in ("claude", "codex"):
            with self.subTest(runtime=runtime):
                prepared = self.prepare_report(runtime)
                transcript, session = self.flow(runtime, prepared, "prepared"), runtime + "-notice"
                self.run_gate("stop", runtime, payload(runtime, "stop", transcript, session, last_assistant_message=""))
                self.assertTrue(self.marker(session).exists())
                proc = self.run_gate("session-start", runtime, payload(runtime, "session-start", transcript, session,
                                                                       source="compact"))
                self.assertEqual(self.context(proc), ddl_gate.PENDING_NOTICE.format(prepared["reportId"], prepared["report"]))
                # Compaction retires the ID: the report is prepared again under a new one.
                self.assert_reason(self.call(runtime, transcript, QUESTION_TOOL[runtime], prepared["nativeRequest"], session),
                                   ddl_gate.PREDATES.format(prepared["reportId"]))
                renewed = self.prepare_report(runtime)
                self.assert_allowed(self.call(runtime, transcript, QUESTION_TOOL[runtime], renewed["nativeRequest"], session))


class PrepareReportTest(GateTest):
    BASE = {"language": "ja", "decision": "R1–R3 を作業ツリーに入れるか", "recommendation": "すべて承認",
            "consequence": "3 ファイルが変わる", "detail": "## Report\n"}

    def cli(self, runtime, data, cwd=None):
        return self.subcommand(["prepare-report", "--runtime", runtime], data, cwd)

    def test_output_shape_and_files(self):
        detail = "## Realize report\n\n| ID | 内容 |\n|---|---|\n| R1 | 版数 |\n"
        out = self.prepare_report("claude", detail=detail)
        self.assertEqual(set(out), {"reportId", "report", "question", "nativeRequest"})
        self.assertRegex(out["reportId"], r"^R-[0-9a-f]{16}$")
        directory = pathlib.Path(self.state) / "reports" / out["reportId"][2:]
        self.assertEqual(out["report"], str(directory / "report.md"))
        self.assertTrue(os.path.isabs(out["report"]))
        self.assertEqual(out["question"].split("\n"), [
            "決めること: README と docs の 3 件の修正を作業ツリーに入れるか",
            "推奨: すべて承認。R1 は版数を 0.7.0 に、R2・R3 はリンクの修正",
            "影響: 3 ファイルが変わる（未コミット）",
            "確認 ID: " + out["reportId"], "全文: " + out["report"]])
        self.assertEqual(ddl_gate.question_id(out["question"]), ("R", out["reportId"][2:]))
        self.assertEqual(out["nativeRequest"], {"questions": [{"question": out["question"], "header": "DDL",
                                                               "multiSelect": False,
                                                               "options": ddl_gate.DEFAULT_OPTIONS["ja"]}]})
        text = (directory / "report.md").read_bytes()
        self.assertEqual(text.decode("utf-8"), out["question"] + "\n\n" + detail)
        record = json.loads((directory / "report.json").read_text(encoding="utf-8"))
        self.assertLessEqual({"version", "runtime", "language", "nonce", "createdAt", "id", "question",
                              "nativeRequest", "reportHash"}, set(record))
        self.assertEqual((record["id"], record["runtime"], record["language"], record["question"], record["nativeRequest"]),
                         (out["reportId"][2:], "claude", "ja", out["question"], out["nativeRequest"]))
        self.assertEqual(record["reportHash"], hashlib.sha256(text).hexdigest())
        self.assertEqual(directory.stat().st_mode & 0o777, 0o700)
        self.assertNotEqual(self.prepare_report("claude", detail=detail)["reportId"], out["reportId"])  # a nonce each time

    def test_english_labels_codex_shape_and_custom_options(self):
        out = self.prepare_report("codex", language="en", decision="Apply R1–R3 to the working tree?",
                                  recommendation="Approve all", consequence="Three files change (uncommitted)")
        self.assertEqual([line.split(": ", 1)[0] for line in out["question"].split("\n")],
                         ["Decision", "Recommendation", "Consequence", "ID", "Full report"])
        self.assertEqual(out["nativeRequest"], {"questions": [{"title": out["question"], "options": [
            "Approve all (Recommended)", "Subset or changes", "Hold"]}]})
        options = [{"label": "R1 only", "description": "Apply R1"}, {"label": "R1 and R2", "description": "Apply both"}]
        out = self.prepare_report("claude", language="en", options=options, multiSelect=True)
        self.assertEqual(out["nativeRequest"]["questions"][0],
                         {"question": out["question"], "header": "DDL", "multiSelect": True, "options": options})
        regional = self.prepare_report("claude", language="ja-JP")
        self.assertTrue(regional["question"].startswith("決めること: "))
        at_limit = self.prepare_report("codex", recommendation="あ" * ddl_gate.QUESTION_LINE_LIMIT)
        self.assertIn("推奨: " + "あ" * ddl_gate.QUESTION_LINE_LIMIT + "\n", at_limit["question"])

    def test_input_errors_exit_2_and_prepare_nothing(self):
        base, option = self.BASE, {"label": "A", "description": "a"}
        options = [{"label": str(i), "description": "d"} for i in range(ddl_gate.MAX_OPTIONS + 1)]
        cases = [("claude", dict(base, decision="一行目\n二行目")), ("claude", dict(base, consequence="a\rb")),
                 ("claude", dict(base, recommendation="あ" * (ddl_gate.QUESTION_LINE_LIMIT + 1))),
                 ("claude", dict(base, options=[option])), ("claude", dict(base, options=options)),
                 ("claude", dict(base, options=[option, option])), ("claude", dict(base, options=[option, {"label": "B"}])),
                 ("codex", dict(base, multiSelect=True)), ("claude", dict(base, multiSelect="yes")),
                 ("claude", {k: v for k, v in base.items() if k != "detail"}), ("claude", dict(base, detail=" \n")),
                 ("claude", dict(base, recommendation="  ")), ("claude", dict(base, language="日本語")),
                 ("claude", dict(base, surprise=1)), ("claude", [base]), ("claude", "not json"), ("gemini", base)]
        for runtime, data in cases:
            with self.subTest(runtime=runtime, data=data):
                proc = self.cli(runtime, data)
                self.assertEqual((proc.returncode, proc.stdout), (2, ""))
                self.assertTrue(proc.stderr.startswith("DDL STOP: "), proc.stderr)
        self.assertFalse((pathlib.Path(self.state) / "reports").exists())
        self.assertEqual(self.cli("codex", base).returncode, 0)


GRANT_LINE = {"ja": "許諾: 編集 2 範囲、命令 build・test・check、マシンなし、360 分、直し 3 回、期限 {}",
              "en": "Grant: edit 2 scopes; commands build, test, check; no machines; 360 minutes; 3 fix attempts; expires {}"}
GRANT_BLOCK = {"ja": "```\n範囲: skills/**、protocol/**。命令 build・test・check。マシン なし。引き継ぎ なし\n"
                     "予算: 360 分。失敗した検査ごとの直し 3 回\n期限: {}\n```",
               "en": "```\nScope: skills/**, protocol/**; commands build, test, check; machines none; handed over none\n"
                     "Budget: 360 minutes; 3 fix attempts per failing check\nExpiry: {}\n```"}


class GrantReportTest(GateTest):
    """prepare-report with a grant: validated, hashed with the project key, and rendered by the gate."""

    def cli(self, runtime, data, cwd=None):
        return self.subcommand(["prepare-report", "--runtime", runtime], data, cwd)

    def stored(self, prepared):
        return json.loads((pathlib.Path(prepared["report"]).parent / "report.json").read_text(encoding="utf-8"))

    def test_grant_is_stored_hashed_and_rendered(self):
        given, detail = grant(), "## Plan\n\n- P1 the gate\n"
        for runtime, language in (("claude", "ja"), ("codex", "en")):
            with self.subTest(runtime=runtime):
                out = self.prepare_report(runtime, language=language, detail=detail, grant=given)
                plain = self.prepare_report(runtime, language=language, detail=detail)
                self.assertEqual(set(out), {"reportId", "report", "question", "nativeRequest"})  # the output keeps its keys
                lines, five = out["question"].split("\n"), plain["question"].split("\n")
                self.assertEqual(len(five), 5)  # no grant, no sixth line
                self.assertEqual([line.split(": ", 1)[0] for line in lines[:5]], [line.split(": ", 1)[0] for line in five])
                self.assertEqual(lines[:3], five[:3])
                self.assertEqual([line.split(": ", 1)[1] for line in lines[3:5]], [out["reportId"], out["report"]])
                self.assertEqual(lines[5:], [GRANT_LINE[language].format(given["expires"][:10])])
                self.assertEqual(ddl_gate.question_id(out["question"]), ("R", out["reportId"][2:]))
                key = "question" if runtime == "claude" else "title"
                self.assertEqual(out["nativeRequest"]["questions"][0][key], out["question"])
                record = self.stored(out)
                self.assertEqual((record["version"], record["grant"], record["projectKey"]),
                                 (3, given, project_key(PROJECT)))
                core = {name: record[name] for name in ddl_gate.REPORT_CORE_KEYS}
                self.assertLessEqual({"grant", "projectKey"}, set(core))
                self.assertEqual(ddl_gate.review_hash(core)[:ddl_gate.ID_HEX_LENGTH], out["reportId"][2:])
                text = pathlib.Path(out["report"]).read_text(encoding="utf-8")
                self.assertEqual(text, out["question"] + "\n\n" + GRANT_BLOCK[language].format(given["expires"])
                                 + "\n\n" + detail)
                self.assertEqual(record["reportHash"], hashlib.sha256(text.encode("utf-8")).hexdigest())
                again = self.prepare_report(runtime, language=language, detail=detail, grant=given)
                self.assertNotEqual(again["reportId"], out["reportId"])  # a new ID per preparation
                # Without a grant: `grant` is present and null, and the file keeps its bytes.
                self.assertEqual((self.stored(plain)["grant"], self.stored(plain)["projectKey"]), (None, project_key(PROJECT)))
                self.assertEqual(pathlib.Path(plain["report"]).read_text(encoding="utf-8"),
                                 plain["question"] + "\n\n" + detail)
        self.assertEqual(ddl_gate.REPORT_VERSION, 3)

    def test_line_and_block_spell_out_each_field(self):
        given = grant(paths=["tools/ddl_gate.py"], commands=[], machines=["gpu-box", "mac-mini"], handover=["dataset v2"],
                      budget={"minutes": 1, "fixAttempts": 0}, expires="2099-01-02T03:04:05Z")
        ja = self.prepare_report("claude", grant=given)
        self.assertEqual(ja["question"].split("\n")[5],
                         "許諾: 編集 1 範囲、命令なし、マシン 2 台、引き継ぎ 1 件、1 分、直し 0 回、期限 2099-01-02")
        self.assertIn("\n\n```\n範囲: tools/ddl_gate.py。命令 なし。マシン gpu-box、mac-mini。引き継ぎ dataset v2\n"
                      "予算: 1 分。失敗した検査ごとの直し 0 回\n期限: 2099-01-02T03:04:05Z\n```\n\n",
                      pathlib.Path(ja["report"]).read_text(encoding="utf-8"))
        en = self.prepare_report("codex", language="en", grant=given)
        self.assertEqual(en["question"].split("\n")[5],
                         "Grant: edit 1 scope; no commands; 2 machines; 1 handed over; 1 minute; 0 fix attempts; "
                         "expires 2099-01-02")
        self.assertIn("\n\n```\nScope: tools/ddl_gate.py; commands none; machines gpu-box, mac-mini; handed over dataset v2\n"
                      "Budget: 1 minute; 0 fix attempts per failing check\nExpiry: 2099-01-02T03:04:05Z\n```\n\n",
                      pathlib.Path(en["report"]).read_text(encoding="utf-8"))
        # The detail may lack its last newline; the head is the same and the file still loads.
        bare = self.prepare_report("claude", grant=given, detail="one line")
        self.assertTrue(pathlib.Path(bare["report"]).read_text(encoding="utf-8").endswith("```\n\none line\n"))
        asked = payload("claude", transcript=fixture("claude_open.jsonl"), tool_name="AskUserQuestion",
                        tool_input=bare["nativeRequest"])
        self.assert_allowed(self.run_gate("pre-tool-use", "claude", asked))

    def test_malformed_grants_exit_2_and_prepare_nothing(self):
        base, good = PrepareReportTest.BASE, grant()
        bad = [[], "everything", 1, True, {key: value for key, value in good.items() if key != "handover"},
               dict(good, extra=1),
               dict(good, paths=[]), dict(good, paths=["p{}".format(i) for i in range(33)]), dict(good, paths="skills/**"),
               dict(good, paths=["/etc/**"]), dict(good, paths=["~/notes/**"]), dict(good, paths=["skills/../../x"]),
               dict(good, paths=[".."]), dict(good, paths=["a\\..\\b"]), dict(good, paths=["C:/x"]),
               dict(good, paths=["a\nb"]), dict(good, paths=["a\tb"]), dict(good, paths=[1]), dict(good, paths=[""]),
               dict(good, paths=[" skills/**"]), dict(good, paths=["a", "a"]),
               dict(good, commands=["deploy"]), dict(good, commands=["build", "build"]), dict(good, commands="build"),
               dict(good, commands=[True]),
               dict(good, machines=["m" * 81]), dict(good, machines=[str(i) for i in range(9)]), dict(good, machines=[""]),
               dict(good, machines=["a", "a"]), dict(good, machines=None),
               dict(good, handover=["h" * 81]), dict(good, handover=["one\ntwo"]), dict(good, handover={}),
               dict(good, budget={"minutes": 360}), dict(good, budget={"minutes": 360, "fixAttempts": 3, "hours": 6}),
               dict(good, budget={"minutes": 0, "fixAttempts": 3}), dict(good, budget={"minutes": 10081, "fixAttempts": 3}),
               dict(good, budget={"minutes": True, "fixAttempts": 3}), dict(good, budget={"minutes": 360, "fixAttempts": False}),
               dict(good, budget={"minutes": 1.5, "fixAttempts": 3}), dict(good, budget={"minutes": "360", "fixAttempts": 3}),
               dict(good, budget={"minutes": 360, "fixAttempts": -1}), dict(good, budget={"minutes": 360, "fixAttempts": 11}),
               dict(good, budget=[360, 3]),
               dict(good, expires="2099-12-23"), dict(good, expires="2099-12-23T00:00:00"),
               dict(good, expires="2020-01-01T00:00:00+09:00"), dict(good, expires="2020-01-01T00:00:00Z"),
               dict(good, expires="tomorrow"), dict(good, expires=4102412400), dict(good, expires=None),
               dict(good, expires="2099-13-01T00:00:00Z"), dict(good, expires="2099-01-01T00:00:00+25:00"),
               dict(good, expires="2099-01-01 00:00:00+09:00")]
        for value in bad:
            with self.subTest(grant=value):
                proc = self.cli("claude", dict(base, grant=value))
                self.assertEqual((proc.returncode, proc.stdout), (2, ""))
                self.assertTrue(proc.stderr.startswith("DDL STOP: "), proc.stderr)
        for runtime, data, cwd in (("claude", dict(base, grant=good, multiSelect=True), None),  # one answer approves
                                   ("claude", dict(base, grant=good), self.tmp)):  # a grant belongs to a DDL project
            with self.subTest(data=data, cwd=cwd):
                proc = self.cli(runtime, data, cwd)
                self.assertEqual((proc.returncode, proc.stdout), (2, ""))
                self.assertTrue(proc.stderr.startswith("DDL STOP: "), proc.stderr)
        self.assertFalse((pathlib.Path(self.state) / "reports").exists())
        self.assertFalse(os.path.exists(self.grants))  # preparing never touches the grant store
        # Accepted spellings of the expiry: `Z` (which Python 3.9's fromisoformat rejects), minutes only, a fraction.
        for expires in ("2099-01-01T00:00:00Z", "2099-01-01T00:00+09:00", "2099-01-01T00:00:00.5-08:00"):
            with self.subTest(expires=expires):
                self.assertEqual(self.cli("codex", dict(base, grant=dict(good, expires=expires))).returncode, 0)
        self.assertEqual(self.cli("claude", dict(base, grant=None)).returncode, 0)  # null is no grant
        outside = self.cli("claude", base, self.tmp)  # without a grant a report needs no project
        self.assertEqual(outside.returncode, 0, outside.stderr)
        self.assertIsNone(self.stored(json.loads(outside.stdout))["projectKey"])

    def test_changed_report_files_are_rejected(self):
        for runtime in ("claude", "codex"):
            with self.subTest(runtime=runtime):
                opened, tool, key = fixture(runtime + "_open.jsonl"), QUESTION_TOOL[runtime], QUESTION_KEY[runtime]

                def ask(prepared):
                    return self.run_gate("pre-tool-use", runtime, payload(runtime, transcript=opened, tool_name=tool,
                                                                          tool_input=prepared["nativeRequest"]))

                def files(prepared):
                    directory = pathlib.Path(prepared["report"]).parent
                    return directory / "report.json", directory / "report.md"

                def agree(prepared, text):  # rewrite report.md and make the stored hash agree with it
                    record_path, report = files(prepared)
                    record = json.loads(record_path.read_text(encoding="utf-8"))
                    report.write_text(text, encoding="utf-8")
                    record["reportHash"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
                    record_path.write_text(json.dumps(record), encoding="utf-8")

                intact = self.prepare_report(runtime, grant=grant())
                self.assert_allowed(ask(intact))
                wider = self.prepare_report(runtime, grant=grant())  # the stored grant widened
                record = self.stored(wider)
                record["grant"]["paths"].append("**")
                files(wider)[0].write_text(json.dumps(record), encoding="utf-8")
                self.assert_reason(ask(wider), ddl_gate.NOT_PREPARED.format(wider["reportId"]))
                moved = self.prepare_report(runtime, grant=grant())  # the project it belongs to changed
                record = self.stored(moved)
                record["projectKey"] = "0" * 16
                files(moved)[0].write_text(json.dumps(record), encoding="utf-8")
                self.assert_reason(ask(moved), ddl_gate.NOT_PREPARED.format(moved["reportId"]))
                narrowed = self.prepare_report(runtime, grant=grant())  # the block the human reads narrowed
                text = files(narrowed)[1].read_text(encoding="utf-8")
                shown = text.replace("範囲: skills/**、protocol/**", "範囲: skills/**")
                self.assertNotEqual(shown, text)
                agree(narrowed, shown)
                self.assert_reason(ask(narrowed), ddl_gate.NOT_PREPARED.format(narrowed["reportId"]))
                edited = self.prepare_report(runtime, grant=grant())  # the detail changed, hash made to agree
                agree(edited, files(edited)[1].read_text(encoding="utf-8") + "- R4 added after preparation\n")
                self.assert_reason(ask(edited), ddl_gate.NOT_PREPARED.format(edited["reportId"]))
                touched = self.prepare_report(runtime, grant=grant())  # report.md alone changed
                files(touched)[1].write_text("changed", encoding="utf-8")
                self.assert_reason(ask(touched), ddl_gate.NOT_PREPARED.format(touched["reportId"]))
                older = self.prepare_report(runtime)  # a report of the schema before the grant
                record = self.stored(older)
                del record["grant"], record["projectKey"]
                files(older)[0].write_text(json.dumps(dict(record, version=1)), encoding="utf-8")
                self.assert_reason(ask(older), ddl_gate.NOT_PREPARED.format(older["reportId"]))
                altered = json.loads(json.dumps(intact["nativeRequest"]))  # the asked grant line differs
                altered["questions"][0][key] = altered["questions"][0][key].replace("編集 2 範囲", "編集 1 範囲")
                self.assertNotEqual(altered, intact["nativeRequest"])
                self.assert_reason(ask(dict(intact, nativeRequest=altered)), ddl_gate.ASK_UNCHANGED.format(intact["reportId"]))
                self.assert_allowed(ask(intact))


class GrantFlowTest(ReportFlowTest):
    """A project of its own, and the steps from a prepared report with a grant to its record."""

    def setUp(self):
        super().setUp()
        self.root, self.cwd = self.project(design=False, git=True)
        self.store = pathlib.Path(self.grants) / project_key(self.root) / "grants"

    def prepared(self, runtime, **fields):
        fields.setdefault("grant", grant())
        return self.prepare_report(runtime, cwd=self.cwd, **fields)

    def tool(self, runtime, transcript, session="sess", tool=None, tool_input=None, **extra):
        """A PreToolUse call in this project; by default the runtime's first write tool, aimed where no grant
        answers (outside the project, or no target), so a recorded grant leaves its decision as it was."""
        name, default = HOST_WRITES[runtime]
        return self.call(runtime, transcript, tool or name, default if tool is None else tool_input, session,
                         cwd=self.cwd, **extra)

    def ask(self, runtime, prepared, session="sess", request=None):
        """The prepared question passes the guard, which arms the session for its answer."""
        return self.tool(runtime, self.flow(runtime, prepared, "prepared"), session, QUESTION_TOOL[runtime],
                         request or prepared["nativeRequest"], tool_use_id="report-question")

    def prompt(self, runtime, transcript, text, session="sess"):
        return self.run_gate("user-prompt-submit", runtime,
                             payload(runtime, "user-prompt-submit", transcript, session, self.cwd, prompt=text))

    def reply(self, prepared, answer=0, session="sess"):
        """Codex delivers a submitted answer as a prompt: the reply envelope."""
        text = codex_reply("report-question", prepared["question"], option_label(prepared, answer))
        return self.prompt("codex", self.flow("codex", prepared, "asked"), text, session)

    def approve(self, runtime, prepared, answer=0, session="sess", mutate=None):
        """Ask, let the human submit option `answer`, and make the next tool call; returns that call."""
        self.assert_allowed(self.ask(runtime, prepared, session))
        if runtime == "codex":
            self.assert_allowed(self.reply(prepared, answer, session))
        return self.tool(runtime, self.flow(runtime, prepared, "answered", answer, mutate=mutate), session)

    def stop(self, runtime, transcript, session="sess"):
        return self.run_gate("stop", runtime, payload(runtime, "stop", transcript, session, self.cwd,
                                                      last_assistant_message=""))

    def start(self, runtime, transcript, source, session="sess"):
        return self.run_gate("session-start", runtime, payload(runtime, "session-start", transcript, session, self.cwd,
                                                               source=source))

    def record_path(self, prepared):
        return self.store / (prepared["reportId"] + ".json")

    def record(self, prepared):
        path = self.record_path(prepared)
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None

    def armed(self, session="sess"):
        return os.path.exists(os.path.join(self.state, session + ".asked"))

    def armed_ids(self, session="sess"):
        """The IDs of the questions the session keeps armed, in the marker's order: oldest first."""
        path = pathlib.Path(self.state) / (session + ".asked")
        return [entry["id"] for entry in json.loads(path.read_text(encoding="utf-8"))] if path.is_file() else []

    def assert_no_grant(self):
        self.assertFalse(os.path.exists(self.grants))  # not even the store appears

    def lines(self, session="sess"):
        return [(row["kind"], row.get("id"), row.get("choice"), row.get("timeout"))
                for row in events(self.root, session=session)]

    def rows(self, runtime, prepared, stage, answer=0, call="report-question"):
        """The rows of one flow, its calls named after `call` so that two flows fit into one record."""
        text = pathlib.Path(self.flow(runtime, prepared, stage, answer)).read_text(encoding="utf-8")
        text = text.replace("prepare-call", "prepare-" + call).replace("report-question", call)
        return [json.loads(line) for line in text.splitlines()]

    def record_of(self, name, rows):
        """A conversation record of its own name: `flow` rewrites one file per runtime and stage."""
        path = os.path.join(self.tmp, name + ".jsonl")
        write_rows(path, rows)
        return path

    def ask_behind(self, first, second, session):
        """Claude asks `first`, the human approves it, and `second` is asked while the record lags: it still
        ends at the first question."""
        self.assert_allowed(self.ask("claude", first, session))
        self.assert_allowed(self.tool("claude", self.flow("claude", first, "asked"), session, QUESTION_TOOL["claude"],
                                      second["nativeRequest"], tool_use_id="second-question"))


class GrantRecordTest(GrantFlowTest):
    """The grant record: written once, and only from the human's submitted first option of the unchanged question."""

    def test_first_option_records_the_grant_on_both_hosts(self):
        for runtime in ("claude", "codex"):
            with self.subTest(runtime=runtime):
                given, session = grant(), runtime + "-grant"
                prepared = self.prepared(runtime, grant=given)
                ident = prepared["reportId"]
                self.assert_allowed(self.ask(runtime, prepared, session))
                self.assertTrue(self.armed(session))
                self.assertIsNone(self.record(prepared))  # asking records nothing
                if runtime == "codex":
                    self.assert_allowed(self.reply(prepared, 0, session))
                    self.assertIsNone(self.record(prepared))  # nor does the reply: the proof reads the record
                # The call passes by the gate's silence, as it would without a grant; no decision is printed.
                self.assert_allowed(self.tool(runtime, self.flow(runtime, prepared, "answered"), session))
                record = self.record(prepared)
                self.assertEqual(set(record), {"id", "projectKey", "root", "grant", "approvedAt", "session", "host"})
                self.assertEqual({key: record[key] for key in ("id", "projectKey", "root", "grant", "session", "host")},
                                 {"id": ident, "projectKey": project_key(self.root), "root": os.path.realpath(self.root),
                                  "grant": given, "session": session, "host": runtime})
                self.assertRegex(record["approvedAt"], ISO_UTC)
                for directory in (self.store, self.store.parent, self.store.parent.parent):
                    self.assertEqual(directory.stat().st_mode & 0o777, 0o700)
                self.assertEqual(self.record_path(prepared).stat().st_mode & 0o777, 0o600)
                self.assertEqual([path.name for path in self.store.parent.iterdir()], ["grants"])  # no uses/ yet
                self.assertEqual([(row["kind"], row.get("id"), row.get("toolUseId"), row.get("choice"), row.get("timeout"))
                                  for row in events(self.root, session=session)],
                                 [("asked", ident, "report-question", None, None),
                                  ("answered", ident, "report-question", 0, False),
                                  ("granted", ident, "report-question", None, None)])
                self.assertEqual(events(self.root, session=session, kind="answered")[0]["label"], option_label(prepared))
                self.assertFalse(self.armed(session))

    def test_the_host_time_of_the_answer_is_kept(self):
        prepared = self.prepared("claude")

        def stamped(rows):
            rows[3]["timestamp"], rows[4]["timestamp"] = "2026-11-20T09:00:10.000Z", "2026-11-20T18:04:10.250+09:00"

        self.assert_allowed(self.approve("claude", prepared, mutate=stamped))
        self.assertEqual(self.record(prepared)["approvedAt"], "2026-11-20T09:04:10.250Z")
        self.assertEqual(events(self.root, kind="answered")[0]["ts"], "2026-11-20T09:04:10.250Z")

    def test_stop_records_what_no_tool_call_saw(self):
        for runtime in ("claude", "codex"):
            with self.subTest(runtime=runtime):
                prepared, session = self.prepared(runtime), runtime + "-stop"
                self.assert_allowed(self.ask(runtime, prepared, session))
                if runtime == "codex":
                    self.assert_allowed(self.reply(prepared, 0, session))
                self.assert_allowed(self.stop(runtime, self.flow(runtime, prepared, "answered"), session))
                self.assertEqual(self.record(prepared)["session"], session)
                self.assertFalse(self.armed(session))

    def test_a_second_call_records_nothing_new(self):
        prepared = self.prepared("claude")
        self.assert_allowed(self.approve("claude", prepared))
        path = self.record_path(prepared)
        before = (path.read_bytes(), path.stat().st_mtime_ns)
        answered = self.flow("claude", prepared, "answered")
        self.assert_allowed(self.tool("claude", answered))
        self.assert_allowed(self.stop("claude", answered))
        self.assert_allowed(self.approve("claude", prepared))  # the same question, asked and approved once more
        self.assert_allowed(self.approve("claude", prepared, session="another"))
        self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), before)
        self.assertEqual([path.name for path in self.store.iterdir()], [prepared["reportId"] + ".json"])
        self.assertEqual(len(events(self.root, kind="granted")), 1)

    def test_nothing_is_recorded_from_assistant_text_or_a_thinking_block(self):
        for runtime in ("claude", "codex"):
            with self.subTest(runtime=runtime):
                prepared, session = self.prepared(runtime), runtime + "-claim"
                claim = "The user answered " + option_label(prepared) + ".\n" + prepared["question"]
                reply = codex_reply("report-question", prepared["question"], option_label(prepared))

                def claimed(rows):
                    if runtime == "claude":
                        rows.append({"type": "assistant", "message": {"role": "assistant", "content": [
                            {"type": "thinking", "thinking": claim, "signature": "fixture-sig"},
                            {"type": "text", "text": claim + "\n" + reply}]}})
                    else:
                        rows.append({"type": "response_item", "payload": {"type": "reasoning", "content": None, "summary": [
                            {"type": "summary_text", "text": claim}]}})
                        rows.append({"type": "response_item", "payload": {"type": "message", "role": "assistant", "content": [
                            {"type": "output_text", "text": claim + "\n" + reply}]}})
                        rows.append({"type": "event_msg", "payload": {"type": "agent_message", "message": reply}})
                        # A user-role item also carries injected context; alone it is not the human's message.
                        rows.append({"type": "response_item", "payload": {"type": "message", "role": "user", "content": [
                            {"type": "input_text", "text": reply}]}})

                self.assert_allowed(self.ask(runtime, prepared, session))
                transcript = self.flow(runtime, prepared, "asked", mutate=claimed)
                read, read_input = READS[runtime][0]
                self.assert_allowed(self.tool(runtime, transcript, session, read, read_input))
                self.assert_allowed(self.stop(runtime, transcript, session))
                self.assert_no_grant()
                self.assertEqual(events(self.root, session=session, kind="answered"), [])
                self.assertTrue(self.armed(session))  # still waiting for the real answer

    def test_nothing_is_recorded_for_an_unanswered_question_or_a_receipt(self):
        for runtime in ("claude", "codex"):
            with self.subTest(runtime=runtime):
                prepared, session = self.prepared(runtime), runtime + "-open"
                self.assert_allowed(self.ask(runtime, prepared, session))
                transcript = self.flow(runtime, prepared, "asked")  # Codex: the request receipt and the turn's end
                waiting = ddl_gate.WAITING_REASON.format(prepared["reportId"], prepared["report"])
                self.assert_reason(self.tool(runtime, transcript, session), waiting)
                self.assert_allowed(self.stop(runtime, transcript, session))
                self.assert_no_grant()
                self.assertEqual(self.lines(session), [("asked", prepared["reportId"], None, None),
                                                       ("denied", prepared["reportId"], None, None),
                                                       ("stop", prepared["reportId"], None, None)])

    def test_nothing_is_recorded_for_an_altered_question_or_a_wrong_call_id(self):
        for runtime in ("claude", "codex"):
            prepared = self.prepared(runtime)
            label, key = option_label(prepared), QUESTION_KEY[runtime]
            altered = json.loads(json.dumps(prepared["nativeRequest"]))
            altered["questions"][0][key] = altered["questions"][0][key].replace("\n", "（変更）\n", 1)
            changed = altered["questions"][0][key]

            def alter(rows):
                if runtime == "claude":
                    rows[3]["message"]["content"][0]["input"] = altered
                    rows[4]["toolUseResult"]["answers"] = {changed: label}
                else:
                    rows[5]["payload"]["arguments"] = json.dumps(altered)
                    rows[9]["payload"]["item"]["content"][0]["text"] = codex_reply("report-question", changed, label)

            def other_call(rows):
                if runtime == "claude":
                    rows[4]["message"]["content"][0]["tool_use_id"] = "another-call"
                else:
                    rows[5]["payload"]["call_id"] = "another-call"

            for name, change in (("altered", alter), ("call id", other_call)):
                with self.subTest(runtime=runtime, change=name):
                    session = "{}-{}".format(runtime, name.replace(" ", "-"))
                    self.assert_allowed(self.approve(runtime, prepared, session=session, mutate=change))
                    self.assert_allowed(self.stop(runtime, self.flow(runtime, prepared, "answered", mutate=change), session))
                    self.assert_no_grant()
                    self.assertEqual(events(self.root, session=session, kind="granted"), [])
            self.assert_reason(self.ask(runtime, prepared, request=altered), ddl_gate.ASK_UNCHANGED.format(prepared["reportId"]))

    def test_nothing_is_recorded_for_another_option(self):
        for runtime in ("claude", "codex"):
            for answer in (1, 2):
                with self.subTest(runtime=runtime, answer=answer):
                    prepared, session = self.prepared(runtime), "{}-option-{}".format(runtime, answer)
                    self.assert_allowed(self.approve(runtime, prepared, answer, session))
                    self.assert_allowed(self.stop(runtime, self.flow(runtime, prepared, "answered", answer), session))
                    self.assert_no_grant()
                    self.assertEqual(self.lines(session), [("asked", prepared["reportId"], None, None),
                                                           ("answered", prepared["reportId"], answer, False)])
                    self.assertFalse(self.armed(session))

    def test_nothing_is_recorded_for_an_idle_timeout_or_a_non_human_source(self):
        prepared = self.prepared("claude")
        waiting = ddl_gate.WAITING_REASON.format(prepared["reportId"], prepared["report"])

        def timed_out(rows):
            rows[4]["toolUseResult"]["afkTimeoutMs"] = 60000  # the host submitted the selection after the idle wait

        def configured(rows):
            rows[4]["permissionDecision"]["source"] = "config"

        for session, change, logged in (("timeout", timed_out, [("answered", prepared["reportId"], 0, True)]),
                                        ("config", configured, [])):
            with self.subTest(change=session):
                self.assert_reason(self.approve("claude", prepared, session=session, mutate=change), waiting)
                self.assert_allowed(self.stop("claude", self.flow("claude", prepared, "answered", mutate=change), session))
                self.assert_no_grant()
                self.assertEqual([line for line in self.lines(session) if line[0] == "answered"], logged)
                self.assertFalse(self.armed(session))  # the question is closed; nothing is retried

    def test_nothing_is_recorded_for_a_report_older_than_the_epoch(self):
        for runtime in ("claude", "codex"):
            for source in ("resume", "compact", "fork", "clear"):
                with self.subTest(runtime=runtime, source=source):
                    prepared, session = self.prepared(runtime), "{}-{}".format(runtime, source)
                    self.assert_allowed(self.ask(runtime, prepared, session))
                    self.start(runtime, self.flow(runtime, prepared, "asked"), source, session)
                    self.assertFalse(self.armed(session))
                    if runtime == "codex":
                        self.reply(prepared, 0, session)
                    answered = self.flow(runtime, prepared, "answered")
                    self.assert_allowed(self.tool(runtime, answered, session))
                    self.assert_allowed(self.stop(runtime, answered, session))
                    self.assert_no_grant()
        # The proof itself refuses such a report, whether or not the session is still armed.
        prepared = self.prepared("claude")
        self.assert_allowed(self.ask("claude", prepared))
        (pathlib.Path(self.state) / "sess.git-epoch").write_text(str(time.time() + 60))
        answered = self.flow("claude", prepared, "answered")
        self.assert_allowed(self.tool("claude", answered))
        self.assert_no_grant()
        with mock.patch.dict(os.environ, {"DDL_GATE_STATE_DIR": self.state, "DDL_GATE_GRANT_DIR": self.grants}):
            with self.assertRaisesRegex(ValueError, "predates"):
                ddl_gate.approved_report("claude", {"session_id": "sess", "transcript_path": answered})
            fresh = {"session_id": "fresh", "transcript_path": answered}
            self.assertEqual(ddl_gate.approved_report("claude", fresh)["id"], prepared["reportId"][2:])
            with mock.patch("time.time", return_value=time.time() + 40 * 86400):  # past the grant's expiry
                with self.assertRaisesRegex(ValueError, "not in the future"):
                    ddl_gate.approved_report("claude", fresh)

    def test_nothing_is_recorded_for_a_typed_message(self):
        for runtime in ("claude", "codex"):
            with self.subTest(runtime=runtime):
                prepared, session = self.prepared(runtime), runtime + "-typed"
                typed = (user("OK, approved.", **HUMAN_ORIGIN) if runtime == "claude" else
                         {"type": "event_msg", "payload": {"type": "item_completed", "item": {
                             "type": "UserMessage", "content": [{"type": "text", "text": "OK, approved."}]}}})
                transcript = self.flow(runtime, prepared, "asked", mutate=lambda rows: rows.append(typed))
                self.assert_allowed(self.ask(runtime, prepared, session))
                self.assert_allowed(self.prompt(runtime, transcript, "OK, approved.", session))
                self.assertFalse(self.armed(session))
                self.assert_allowed(self.tool(runtime, transcript, session))
                # Even an answer recorded before the typed message proves nothing once that message is the latest.
                late = self.flow(runtime, prepared, "answered", mutate=lambda rows: rows.append(typed))
                self.assert_allowed(self.ask(runtime, self.prepared(runtime), session))  # armed again, for another report
                self.assert_allowed(self.tool(runtime, late, session))
                self.assert_allowed(self.stop(runtime, late, session))
                self.assert_no_grant()
                self.assertEqual([line[0] for line in self.lines(session)], ["asked", "prompt", "asked"])

    def test_nothing_is_recorded_without_a_grant_or_for_another_project(self):
        for runtime in ("claude", "codex"):
            with self.subTest(runtime=runtime):
                plain, session = self.prepare_report(runtime, cwd=self.cwd), runtime + "-plain"
                self.assert_allowed(self.approve(runtime, plain, session=session))
                foreign = self.prepare_report(runtime, grant=grant())  # prepared in the default project
                self.assert_allowed(self.approve(runtime, foreign, session=session))
                self.assert_allowed(self.stop(runtime, self.flow(runtime, foreign, "answered"), session))
                self.assert_no_grant()
                # The approving answer of a grant that is not recorded leaves a line that says why.
                self.assertEqual([line[0] for line in self.lines(session)], ["asked", "answered", "asked", "answered", "warn"])
                self.assertEqual(untimed(events(self.root, session=session, kind="warn")), [
                    {"v": 1, "host": runtime, "session": session, "kind": "warn", "id": foreign["reportId"],
                     "rule": "grant-proof", "toolUseId": "report-question"}])

    def test_a_codex_reply_to_a_report_does_not_revoke_it(self):
        def epoch(session):
            return pathlib.Path(self.state) / (session + ".git-epoch")

        prepared = self.prepared("codex")
        self.assert_allowed(self.ask("codex", prepared, "kept"))
        self.assert_allowed(self.reply(prepared, 0, "kept"))
        self.assertFalse(epoch("kept").exists())  # the approving reply spares the epoch, like a Git review's
        self.assert_allowed(self.tool("codex", self.flow("codex", prepared, "answered"), "kept"))
        self.assertIsNotNone(self.record(prepared))
        self.assert_allowed(self.ask("codex", prepared, "kept"))  # and its question is still the prepared one
        plain = self.prepare_report("codex", cwd=self.cwd)  # the same holds for a report without a grant
        self.assert_allowed(self.ask("codex", plain, "kept"))
        self.assert_allowed(self.reply(plain, 0, "kept"))
        self.assertFalse(epoch("kept").exists())
        # Another option, a reply to a changed question, and typed text still move the epoch and retire the report.
        for name, text in (("revised", lambda p: codex_reply("report-question", p["question"], option_label(p, 1))),
                           ("held", lambda p: codex_reply("report-question", p["question"], option_label(p, 2))),
                           ("changed", lambda p: codex_reply("report-question", p["question"] + " ", option_label(p))),
                           ("typed", lambda p: option_label(p))):
            with self.subTest(prompt=name):
                other = self.prepared("codex")
                self.assert_allowed(self.ask("codex", other, name))
                self.assert_allowed(self.prompt("codex", self.flow("codex", other, "asked"), text(other), name))
                self.assertTrue(epoch(name).exists())
                self.assert_reason(self.ask("codex", other, name), ddl_gate.PREDATES.format(other["reportId"]))
                self.assertIsNone(self.record(other))

    def test_a_recorded_grant_survives_a_prompt_a_resume_and_a_new_session(self):
        for runtime in ("claude", "codex"):
            with self.subTest(runtime=runtime):
                given = grant()
                prepared = self.prepared(runtime, grant=given)
                self.assert_allowed(self.approve(runtime, prepared, session=runtime))
                before = self.record_path(prepared).read_bytes()
                answered, opened = self.flow(runtime, prepared, "answered"), fixture(runtime + "_open.jsonl")
                self.prompt(runtime, answered, "Now something else.", runtime)
                for source in ("resume", "compact", "fork", "clear"):
                    self.start(runtime, answered, source, runtime)
                self.start(runtime, opened, "startup", "next-" + runtime)
                self.assert_allowed(self.tool(runtime, opened, "next-" + runtime))
                self.assert_allowed(self.stop(runtime, opened, "next-" + runtime))
                self.assertEqual(self.record_path(prepared).read_bytes(), before)
                line = "Grant: {} (expires {}, valid)\n".format(prepared["reportId"], given["expires"][:10])
                self.assertIn(line, self.subcommand(["status", "--cwd", self.cwd]).stdout)
                report = self.subcommand(["report", "--session", runtime], cwd=self.cwd).stdout.splitlines()
                self.assertEqual(report[3], "許諾: {}（期限 {}、有効）".format(prepared["reportId"], given["expires"][:10]))

    def test_status_lists_grants_and_marks_an_expired_one(self):
        first = "DDL project: yes ({}:3)\n".format(self.root / ".claude" / "CLAUDE.md")
        self.assertEqual(self.subcommand(["status", "--cwd", self.cwd]).stdout, first)  # no grant: today's bytes
        self.assert_no_grant()  # and status creates nothing
        given = grant()
        prepared = self.prepared("claude", grant=given)
        self.assert_allowed(self.approve("claude", prepared))
        old = {"id": "R-" + "e" * 16, "projectKey": project_key(self.root), "root": os.path.realpath(self.root),
               "grant": grant(expires="2020-01-01T00:00:00+09:00"), "approvedAt": "2019-12-01T00:00:00.000Z",
               "session": "old", "host": "codex"}
        (self.store / (old["id"] + ".json")).write_text(json.dumps(old), encoding="utf-8")
        (self.store / "notes.txt").write_text("not a record", encoding="utf-8")
        (self.store / ("R-" + "f" * 16 + ".json")).write_text("{torn", encoding="utf-8")
        proc = self.subcommand(["status", "--cwd", self.cwd])
        self.assertEqual((proc.returncode, proc.stderr), (0, ""))
        self.assertEqual(proc.stdout, first + "Grant: {} (expires 2020-01-01, expired)\n".format(old["id"])
                         + "Grant: {} (expires {}, valid)\n".format(prepared["reportId"], given["expires"][:10]))
        # Another project has its own key and sees none of them.
        self.assertEqual(self.subcommand(["status", "--cwd", str(PROJECT)]).stdout,
                         "DDL project: yes ({}:3)\n".format(PROJECT / ".claude" / "CLAUDE.md"))

    def test_a_recorded_grant_answers_for_its_calls_and_never_under_a_pending_stop(self):
        for runtime in ("claude", "codex"):
            with self.subTest(runtime=runtime):
                prepared = self.prepared(runtime, grant=grant(paths=["skills/**"], commands=["build"]))
                self.assert_allowed(self.approve(runtime, prepared, session=runtime))
                self.assertIsNotNone(self.record(prepared))
                (shell, key), opened, closed = SHELL[runtime], fixture(runtime + "_open.jsonl"), fixture(runtime + "_closed_in_turn.jsonl")
                inside = ("Edit", {"file_path": "skills/a.md", "old_string": "a", "new_string": "b"}) if runtime == "claude" \
                    else ("apply_patch", {"patch": "*** Begin Patch\n*** Update File: skills/a.md\n@@\n-a\n+b\n*** End Patch"})
                calls = {"edit": inside, "read": READS[runtime][-1], "build": (shell, {key: "python3 tools/build.py"})}
                for kind, (tool, tool_input) in calls.items():
                    with self.subTest(kind=kind):
                        out = self.tool(runtime, opened, runtime, tool, tool_input).stdout
                        if runtime == "codex":  # Codex takes no allow from PreToolUse: its PermissionRequest answers
                            self.assertEqual(out, "")
                            permitted = self.run_gate("permission-request", runtime, payload(
                                runtime, transcript=opened, session=runtime, cwd=self.cwd, tool_name=tool,
                                tool_input=tool_input, hook_event_name="PermissionRequest")).stdout
                            self.assertEqual(json.loads(permitted)["hookSpecificOutput"]["decision"], {"behavior": "allow"})
                        else:
                            self.assertEqual(json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"],
                                             "DDL: inside grant {} ({})".format(prepared["reportId"], kind))
                        # A pending STOP decides as it always did: the same call, byte for byte as in a bare project.
                        held = self.tool(runtime, closed, runtime, tool, tool_input).stdout
                        bare = self.call(runtime, closed, tool, tool_input, "bare-" + runtime).stdout
                        self.assertEqual(held, bare)
                        self.assertNotIn("allow", held)
                        self.assertEqual(self.run_gate("permission-request", runtime, payload(
                            runtime, transcript=closed, session=runtime, cwd=self.cwd, tool_name=tool,
                            tool_input=tool_input)).stdout, "")
                # A commit or push still needs its Git review, grant or not.
                for command in ("git commit --cleanup=verbatim -m x", "git push origin main"):
                    out = json.loads(self.tool(runtime, opened, runtime, shell, {key: command}).stdout)
                    self.assertIn("DDL Git review", out["hookSpecificOutput"]["permissionDecisionReason"])

    def test_a_reply_to_a_report_without_options_still_moves_the_epoch(self):
        """A report record written by hand can agree with its own ID and offer no option to compare a reply with."""
        prepared = self.prepare_report("codex", cwd=self.cwd)
        directory = pathlib.Path(prepared["report"]).parent
        record = json.loads((directory / "report.json").read_text(encoding="utf-8"))
        detail = (directory / "report.md").read_text(encoding="utf-8")[len(prepared["question"]) + 2:]
        record["options"] = []
        record["id"] = ddl_gate.review_hash({key: record[key] for key in ddl_gate.REPORT_CORE_KEYS})[:ddl_gate.ID_HEX_LENGTH]
        forged = directory.parent / record["id"]
        forged.mkdir()
        question, request = ddl_gate.report_question(record, forged / "report.md")
        text = question + "\n\n" + detail
        (forged / "report.md").write_text(text, encoding="utf-8")
        record.update(question=question, nativeRequest=request, reportHash=hashlib.sha256(text.encode("utf-8")).hexdigest())
        (forged / "report.json").write_text(json.dumps(record), encoding="utf-8")
        with mock.patch.dict(os.environ, {"DDL_GATE_STATE_DIR": self.state}):
            self.assertEqual(ddl_gate.load_report(record["id"], "codex")["options"], [])  # it loads: every hash agrees
        waiting = self.prepared("codex")
        self.assert_allowed(self.ask("codex", waiting, "forged"))
        reply = codex_reply("report-question", question, "Approve all (Recommended)")
        # No internal error is printed, and the prompt counts as typed text: the epoch moves and the asked question retires.
        self.assert_allowed(self.prompt("codex", fixture("codex_open.jsonl"), reply, "forged"))
        self.assertTrue((pathlib.Path(self.state) / "forged.git-epoch").exists())
        self.assertFalse(self.armed("forged"))
        self.assertEqual([line[0] for line in self.lines("forged")], ["asked", "prompt"])
        self.assert_reason(self.ask("codex", waiting, "forged"), ddl_gate.PREDATES.format(waiting["reportId"]))

    def test_a_store_that_cannot_take_the_record_leaves_a_warning(self):
        pathlib.Path(self.grants).write_text("a file where the grant store belongs")
        for runtime in ("claude", "codex"):
            for seen_by in ("tool", "stop"):
                with self.subTest(runtime=runtime, seen_by=seen_by):
                    prepared, session = self.prepared(runtime), "{}-{}-blocked".format(runtime, seen_by)
                    ident = prepared["reportId"]
                    self.assert_allowed(self.ask(runtime, prepared, session))
                    if runtime == "codex":
                        self.assert_allowed(self.reply(prepared, 0, session))
                    answered = self.flow(runtime, prepared, "answered")
                    # No decision changes: the call after the answer passes in silence, a pending STOP still denies.
                    if seen_by == "tool":
                        self.assert_allowed(self.tool(runtime, answered, session))
                    else:
                        self.assert_allowed(self.stop(runtime, answered, session))
                    self.assertFalse(self.armed(session))
                    self.assert_denied(self.tool(runtime, fixture(runtime + "_closed_in_turn.jsonl"), session))
                    self.assert_allowed(self.tool(runtime, answered, session))  # and nothing is tried again
                    self.assert_allowed(self.stop(runtime, answered, session))
                    self.assertEqual(self.lines(session), [("asked", ident, None, None), ("answered", ident, 0, False),
                                                           ("warn", ident, None, None), ("denied", None, None, None)])
                    self.assertEqual(untimed(events(self.root, session=session, kind="warn")), [
                        {"v": 1, "host": runtime, "session": session, "kind": "warn", "id": ident, "rule": "grant-store",
                         "toolUseId": "report-question"}])
                    report = self.subcommand(["report", "--session", session], cwd=self.cwd).stdout.splitlines()
                    self.assertEqual(report[3], "許諾: なし")
        self.assertTrue(pathlib.Path(self.grants).is_file())  # no record anywhere
        self.assertEqual(events(self.root, kind="granted"), [])

    def test_a_lagging_record_does_not_cost_the_first_question_its_grant(self):
        """Claude Code writes its record asynchronously: the first answer can be missing from it when the next
        prepared question is asked. That question joins the first one instead of taking its place."""
        first, second, session = self.prepared("claude"), self.prepare_report("claude", cwd=self.cwd), "lag"
        self.ask_behind(first, second, session)
        self.assertIsNone(self.record(first))
        # The record catches up with the first answer before it holds the second question.
        read, read_input = READS["claude"][0]
        self.assert_allowed(self.tool("claude", self.flow("claude", first, "answered"), session, read, read_input))
        self.assertEqual((self.record(first) or {}).get("session"), session)  # lost when the second question took the marker
        self.assertEqual(self.armed_ids(session), [second["reportId"]])
        # The second question closes with its own answer, read by its own call.
        both = self.record_of("both", self.rows("claude", first, "answered")
                              + self.rows("claude", second, "answered", 1, "second-question")[1:])
        self.assert_allowed(self.tool("claude", both, session, read, read_input))
        self.assertFalse(self.armed(session))
        self.assertEqual([(row["kind"], row["id"], row.get("toolUseId"), row.get("choice")) for row in events(self.root, session=session)],
                         [("asked", first["reportId"], "report-question", None),
                          ("asked", second["reportId"], "second-question", None),
                          ("answered", first["reportId"], "report-question", 0),
                          ("granted", first["reportId"], "report-question", None),
                          ("answered", second["reportId"], "second-question", 1)])

    def test_two_waiting_codex_questions_each_keep_their_answer(self):
        """Codex asks without waiting, so two prepared questions can be open at once; the reply to the first
        one must find it still armed."""
        first, second, session = self.prepared("codex"), self.prepare_report("codex", cwd=self.cwd), "two"
        one, two = self.rows("codex", first, "answered"), self.rows("codex", second, "asked", call="second-question")
        self.assert_allowed(self.ask("codex", first, session))
        self.assert_allowed(self.tool("codex", self.record_of("second-prepared", one[:7] + two[3:5]), session,
                                      QUESTION_TOOL["codex"], second["nativeRequest"], tool_use_id="second-question"))
        self.assert_allowed(self.reply(first, 0, session))
        # Both calls, both receipts, the end of that turn, and the reply to the first question.
        replied = self.record_of("first-replied", one[:7] + two[3:7] + one[7:])
        self.assert_allowed(self.tool("codex", replied, session))
        self.assertEqual((self.record(first) or {}).get("session"), session)  # lost when the second question took the marker
        self.assertEqual(self.armed_ids(session), [second["reportId"]])  # still waiting for its own reply
        self.assertEqual(self.lines(session), [("asked", first["reportId"], None, None), ("asked", second["reportId"], None, None),
                                               ("answered", first["reportId"], 0, False),
                                               ("granted", first["reportId"], None, None)])
        # Any other reply moves the epoch, and with it every question that still waits.
        self.assert_allowed(self.prompt("codex", replied, codex_reply("second-question", second["question"],
                                                                      option_label(second, 1)), session))
        self.assertFalse(self.armed(session))

    def test_an_answer_behind_a_later_one_is_logged_and_its_grant_is_not_proved(self):
        """The proof reads the latest submitted answer. When the record first shows the first answer behind the
        second one, the first question gets its `answered` line and a warning; the second grant keeps its own time."""
        first, second, session = self.prepared("claude"), self.prepared("claude"), "behind"
        self.ask_behind(first, second, session)
        one, two = self.rows("claude", first, "answered"), self.rows("claude", second, "answered", call="second-question")
        one[4]["timestamp"], two[4]["timestamp"] = "2026-11-20T09:04:10.000Z", "2026-11-20T09:30:00.000Z"
        self.assert_allowed(self.tool("claude", self.record_of("both", one + two[1:]), session))
        self.assertFalse(self.armed(session))
        self.assertIsNone(self.record(first))
        self.assertEqual(self.record(second)["approvedAt"], "2026-11-20T09:30:00.000Z")
        self.assertEqual([(row["kind"], row["id"], row.get("rule")) for row in events(self.root, session=session)],
                         [("asked", first["reportId"], None), ("asked", second["reportId"], None),
                          ("answered", first["reportId"], None), ("warn", first["reportId"], "grant-proof"),
                          ("answered", second["reportId"], None), ("granted", second["reportId"], None)])
        self.assertEqual(events(self.root, session=session, kind="answered")[0]["ts"], "2026-11-20T09:04:10.000Z")

    def test_a_prompt_a_compaction_and_a_resume_retire_every_armed_question(self):
        retire = {"prompt": lambda record, session: self.prompt("claude", record, "Something else first.", session),
                  "compact": lambda record, session: self.start("claude", record, "compact", session),
                  "resume": lambda record, session: self.start("claude", record, "resume", session)}
        for name, event in retire.items():
            with self.subTest(event=name):
                first, second = self.prepared("claude"), self.prepared("claude")
                self.ask_behind(first, second, name)
                self.assertEqual(self.armed_ids(name), [first["reportId"], second["reportId"]])  # both wait, oldest first
                event(self.flow("claude", first, "asked"), name)
                self.assertFalse(self.armed(name))
                both = self.record_of("both-" + name, self.rows("claude", first, "answered")
                                      + self.rows("claude", second, "answered", call="second-question")[1:])
                self.assert_allowed(self.tool("claude", both, name))
                self.assert_allowed(self.stop("claude", both, name))
                self.assertEqual(events(self.root, session=name, kind="answered"), [])
        self.assert_no_grant()

    def test_the_marker_of_an_older_gate_is_still_read(self):
        prepared = self.prepared("claude")
        self.assert_allowed(self.ask("claude", prepared))
        marker = pathlib.Path(self.state) / "sess.asked"
        (entry,) = json.loads(marker.read_text(encoding="utf-8"))
        self.assertEqual(set(entry), {"id", "options", "grant", "confirm", "toolUseId"})
        del entry["confirm"]  # an older gate's entry: no confirmations
        marker.write_text(json.dumps(entry), encoding="utf-8")  # one bare object: the marker before it held a list
        self.assert_allowed(self.tool("claude", self.flow("claude", prepared, "answered")))
        self.assertIsNotNone(self.record(prepared))
        self.assertFalse(self.armed())
        # A marker that holds no question is dropped at the first look, and the next call costs one stat again.
        marker.write_text("{torn", encoding="utf-8")
        self.assert_allowed(self.tool("claude", fixture("claude_open.jsonl")))
        self.assertFalse(self.armed())

    def test_the_marker_keeps_the_newest_questions_past_its_limit(self):
        os.makedirs(self.state)
        entries = [{"id": "R-{:016x}".format(number), "options": ["A", "B"], "grant": False, "toolUseId": None}
                   for number in range(ddl_gate.ARMED_LIMIT + 2)]
        with mock.patch.dict(os.environ, {"DDL_GATE_STATE_DIR": self.state}):
            ddl_gate.arm("many", entries)
            self.assertEqual(ddl_gate.armed_questions("many"), entries[2:])  # oldest first, the two oldest let go
            ddl_gate.arm("many", [])
            self.assertEqual((ddl_gate.armed_questions("many"), os.listdir(self.state)), ([], []))  # nothing left behind

    def test_a_call_with_nothing_armed_costs_one_stat(self):
        data = payload("claude", transcript=fixture("claude_open.jsonl"), session="quiet", cwd=self.cwd)
        marker = os.path.join(os.path.abspath(self.state), "quiet.asked")
        with mock.patch.dict(os.environ, {"DDL_GATE_STATE_DIR": self.state}), \
                mock.patch.object(os.path, "exists", wraps=os.path.exists) as exists, \
                mock.patch("builtins.open", side_effect=AssertionError("a call with nothing armed opens no file")), \
                mock.patch.object(ddl_gate, "ledger_root", side_effect=AssertionError("nor does it look for the ledger")):
            ddl_gate.tool_note("claude", data, {"ddl": True, "cwd": self.cwd}, None, {"state": False})
        self.assertEqual(exists.call_args_list, [mock.call(marker)])

    def test_a_leftover_file_at_the_records_name_is_no_grant_and_gives_way_to_the_record(self):
        other = {"id": "R-" + "0" * 16, "projectKey": project_key(self.root), "root": "/synthetic", "grant": grant()}
        leftovers = {"empty": lambda ident: "",  # what an interrupted write of the gate before this one left
                     "torn": lambda ident: '{"id": "' + ident,
                     "another record": lambda ident: json.dumps(other),
                     "no grant": lambda ident: json.dumps({"id": ident, "grant": None})}
        self.store.mkdir(parents=True)
        for number, (name, leftover) in enumerate(leftovers.items()):
            with self.subTest(leftover=name):
                runtime, session = ("claude", "codex")[number % 2], "left-{}".format(number)
                prepared = self.prepared(runtime)
                path, ident = self.record_path(prepared), prepared["reportId"]
                path.write_text(leftover(ident), encoding="utf-8")
                # Every reader agrees that this is no grant.
                self.assertNotIn(ident, self.subcommand(["status", "--cwd", self.cwd]).stdout)
                with mock.patch.dict(os.environ, {"DDL_GATE_GRANT_DIR": self.grants}):
                    self.assertNotIn(ident, [record["id"] for record in ddl_gate.grant_records()])
                    self.assertIsNone(ddl_gate.read_grant(str(path), ident))
                # The approval then writes the record over it, whole and private.
                self.assert_allowed(self.approve(runtime, prepared, session=session))
                self.assertEqual((self.record(prepared)["id"], self.record(prepared)["session"]), (ident, session))
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                self.assertEqual(len(events(self.root, session=session, kind="granted")), 1)
                self.assertIn("Grant: {} ".format(ident), self.subcommand(["status", "--cwd", self.cwd]).stdout)
        self.assertEqual(len(list(self.store.iterdir())), len(leftovers))  # the records, and no temporary file

    def test_a_record_is_written_whole_or_not_at_all(self):
        body = {"id": "R-" + "5" * 16, "projectKey": "0" * 16, "root": "/synthetic", "grant": grant(),
                "approvedAt": "2026-11-20T09:04:10.000Z", "session": "S", "host": "claude"}
        directory = pathlib.Path(self.grants) / body["projectKey"] / "grants"
        with mock.patch.dict(os.environ, {"DDL_GATE_GRANT_DIR": self.grants}):
            for name in ("write", "link"):  # the disk fills up; the file system knows no hard link
                with self.subTest(fails=name):
                    with mock.patch.object(os, name, side_effect=OSError("synthetic failure")):
                        with self.assertRaises(OSError):
                            ddl_gate.store_grant(body)
                    self.assertEqual(os.listdir(directory), [])  # neither half a record nor the temporary file
            self.assertIs(ddl_gate.store_grant(body), True)
            self.assertIs(ddl_gate.store_grant(dict(body, approvedAt="2026-11-21T00:00:00.000Z")), False)  # written once
            self.assertEqual(os.listdir(directory), [body["id"] + ".json"])
            self.assertEqual(ddl_gate.read_grant(str(directory / (body["id"] + ".json")), body["id"]), body)
            self.assertIsNone(ddl_gate.read_grant(str(directory / (body["id"] + ".json")), "R-" + "6" * 16))

    def test_the_run_of_an_approved_plan_counts_the_plans_own_question(self):
        """The plan is asked, answered and granted before `run-start`; its Run counts that question too."""
        given = grant()
        plan = self.prepared("claude", grant=given)
        self.assert_allowed(self.approve("claude", plan))
        started = self.subcommand(["run-start"], {"report": plan["reportId"], "items": []}, cwd=self.cwd)
        self.assertEqual((started.returncode, started.stderr), (0, ""))
        run = json.loads(pathlib.Path(json.loads(started.stdout)["path"]).read_text(encoding="utf-8"))
        self.assertEqual(run["grant"], plan["reportId"])
        later = self.prepare_report("claude", cwd=self.cwd)
        self.assert_allowed(self.approve("claude", later, 1))
        self.assertEqual(self.lines()[:3], [("asked", plan["reportId"], None, None), ("answered", plan["reportId"], 0, False),
                                            ("granted", plan["reportId"], None, None)])
        report = self.subcommand(["report", "--run", run["id"]], cwd=self.cwd)
        self.assertEqual(report.stdout.splitlines(), [
            "問い: 2 件（承認 1、見直し 1、時間切れ 0）", "待ち: 人間 0 分（答えまで中央値 0 分、最長 0 分）", "拒否: 0 件",
            "許諾: {}（期限 {}、有効）".format(plan["reportId"], given["expires"][:10])])


CONFIRM = [{"resource": "batch-1", "action": "run the nightly job on the cluster"}]
PROMPT_TEXT = "List the jobs of the project.\nMake no change of any kind.\n```\nnot a fence of the report\n```\n"
CONFIRM_LINE = {"ja": "確認: batch-1: run the nightly job on the cluster",
                "en": "Confirm: batch-1: run the nightly job on the cluster"}


class ConfirmationTest(GrantFlowTest):
    """A report's confirmations for resources that ask each run: checked against the table when prepared, shown in the
    question and the report, recorded once on the human's submitted first option of the unchanged question (the
    grant's proof), never otherwise, and each item taken once by the run lane."""

    def setUp(self):
        super().setUp()
        self.config = os.path.join(self.tmp, "config")
        write_table(self.config)
        patcher = mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": self.config})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.confirmations = self.store.parent / "confirmations"
        self.prompt_file = self.root / "prompts" / "job.md"  # a service's prompt, inside the root
        self.prompt_file.parent.mkdir()
        self.prompt_file.write_text(PROMPT_TEXT, encoding="utf-8")

    def confirmed(self, runtime, **fields):
        fields.setdefault("grant", None)
        fields.setdefault("confirm", CONFIRM)
        return self.prepared(runtime, **fields)

    def confirmation(self, prepared):
        path = self.confirmations / (prepared["reportId"] + ".json")
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None

    def assert_no_confirmation(self):
        self.assertFalse(self.confirmations.exists())
        self.assertFalse((pathlib.Path(self.grants) / project_key(PROJECT) / "confirmations").exists())
        self.assertEqual(events(self.root, kind="confirmed"), [])

    def test_confirmations_join_the_question_and_the_report(self):
        given = grant()
        for runtime, language in (("claude", "ja"), ("codex", "en")):
            with self.subTest(runtime=runtime):
                out = self.confirmed(runtime, language=language)
                lines = out["question"].split("\n")
                self.assertEqual((len(lines), lines[5]), (6, CONFIRM_LINE[language]))
                self.assertEqual(ddl_gate.question_id(out["question"]), ("R", out["reportId"][2:]))
                text = pathlib.Path(out["report"]).read_text(encoding="utf-8")
                label = ddl_gate.CONFIRM_LABELS[language]
                self.assertTrue(text.startswith(out["question"] + "\n\n```\n{}: batch-1: {}\n```\n\n".format(
                    label, CONFIRM[0]["action"])), text)
                record = json.loads((pathlib.Path(out["report"]).parent / "report.json").read_text(encoding="utf-8"))
                self.assertEqual((record["version"], record["confirm"], record["grant"]), (3, CONFIRM, None))
                both = self.confirmed(runtime, language=language, grant=given)
                self.assertEqual(both["question"].split("\n")[5:],
                                 [GRANT_LINE[language].format(given["expires"][:10]), CONFIRM_LINE[language]])
                # Four long actions: the line is cut, the report keeps each in full.
                many = [dict({"resource": name, "action": "step {} ".format(name) + "x" * 180},
                             **({"prompt": "prompts/job.md"} if name.startswith("svc") else {}))
                        for name in ("batch-1", "svc-paid", "build-1", "svc")]
                long = self.confirmed(runtime, language=language, confirm=many)
                line = long["question"].split("\n")[5]
                self.assertTrue(len(line.split(": ", 1)[1]) <= ddl_gate.QUESTION_LINE_LIMIT and line.endswith("…"))
                report = pathlib.Path(long["report"]).read_text(encoding="utf-8")
                self.assertTrue(all("{}: {}: {}".format(label, item["resource"], item["action"]) in report for item in many))
                # The confirmations are hashed into the ID: a changed one is no prepared report.
                path = pathlib.Path(out["report"]).parent / "report.json"
                record["confirm"] = [{"resource": "batch-1", "action": "something else"}]
                path.write_text(json.dumps(record), encoding="utf-8")
                self.assert_reason(self.ask(runtime, out), ddl_gate.NOT_PREPARED.format(out["reportId"]))

    def test_confirmations_are_checked_before_anything_is_written(self):
        def refused(reason, cwd=None, hosts=("claude", "codex"), **fields):
            for given in hosts:
                with self.subTest(reason=reason, runtime=given, fields=fields):
                    before = sorted(pathlib.Path(self.state).rglob("report.*"))
                    data = dict(PrepareReportTest.BASE, **dict({"confirm": CONFIRM}, **fields))
                    proc = self.subcommand(["prepare-report", "--runtime", given], data, cwd or self.cwd)
                    self.assertEqual((proc.returncode, proc.stdout, proc.stderr), (2, "", "DDL STOP: " + reason + "\n"))
                    self.assertEqual(sorted(pathlib.Path(self.state).rglob("report.*")), before)

        shape = "confirm must be a list of 1 to 4 {resource, action} objects."
        entry = ("each confirm entry is {resource, action}, and {resource, action, prompt, schema?, approve?} for a "
                 "service.")
        name = "confirm: a resource is a name of the resource table (lowercase letters, digits, hyphens)."
        action = ("confirm: each action is one printable line of at most 200 characters, without surrounding spaces: "
                  "what will run.")
        five = [{"resource": "batch-1", "action": "run {}".format(i)} for i in range(5)]
        for value, reason in (([], shape), (five, shape), ("batch-1", shape), ({"resource": "batch-1"}, shape),
                              ([{"resource": "batch-1"}], entry), ([dict(CONFIRM[0], extra=1)], entry), (["batch-1"], entry),
                              ([{"resource": "Batch_1", "action": "x"}], name), ([{"resource": 1, "action": "x"}], name),
                              ([{"resource": "batch-1", "action": ""}], action), ([{"resource": "batch-1", "action": "a\nb"}], action),
                              ([{"resource": "batch-1", "action": "x" * 201}], action),
                              ([{"resource": "batch-1", "action": " run"}], action),
                              ([{"resource": "batch-1", "action": "a\tb"}], action),
                              ([{"resource": "batch-1", "action": 5}], action),
                              (CONFIRM + CONFIRM, "confirm entries must differ."),
                              ([{"resource": "nope", "action": "x"}], "confirm: `nope` is not declared in the resource table."),
                              ([{"resource": "desk", "action": "x"}],
                               "confirm: `desk` is not a compute resource in the resource table.")):
            refused(reason, confirm=value)
        refused("a report with confirmations takes one answer: its first option confirms, so multiSelect is false.",
                hosts=("claude",), multiSelect=True)  # Codex refuses multiSelect itself
        refused("a confirmation belongs to a DDL project; prepare the report from inside the project.", cwd=self.tmp)
        write_table(self.config, BOX + 'note = "at 192.0.2.10"\n')
        refused("confirm: the resource table is invalid (resource box: field note looks like an IP address (the value is "
                "not printed)); correct it before confirming.")
        write_table(self.config).unlink()
        refused("confirm names resources of the resource table, and there is none.")

    def test_a_service_confirmation_is_bound_to_its_prompt(self):
        service = [{"resource": "svc-paid", "action": "list the jobs", "prompt": "prompts/job.md"}]
        digest = hashlib.sha256(self.prompt_file.read_bytes()).hexdigest()
        for runtime, language in (("claude", "en"), ("codex", "ja")):
            with self.subTest(runtime=runtime):
                prepared, session = self.confirmed(runtime, language=language, confirm=service), runtime + "-prompt"
                self.assertEqual(prepared["question"].split("\n")[5],
                                 CONFIRM_LINE[language].split(":")[0] + ": svc-paid: list the jobs")
                text = pathlib.Path(prepared["report"]).read_text(encoding="utf-8")
                head = ("svc-paid の依頼（sha256 {}）:" if language == "ja" else "Prompt for svc-paid (sha256 {}):").format(digest)
                self.assertIn("\n\n" + head + "\n````\n" + PROMPT_TEXT + "````\n\n", text)  # whole, in a longer fence
                stored = json.loads((pathlib.Path(prepared["report"]).parent / "report.json").read_text(encoding="utf-8"))
                self.assertEqual(stored["confirm"], [dict(service[0], text=PROMPT_TEXT, digest=digest, approve=False)])
                self.prompt_file.write_text("Delete every job.\n", encoding="utf-8")  # changed after preparation
                self.assertEqual(pathlib.Path(prepared["report"]).read_text(encoding="utf-8"), text)
                self.assert_allowed(self.approve(runtime, prepared, session=session))
                self.assertEqual(self.confirmation(prepared)["items"],
                                 [{"resource": "svc-paid", "action": "list the jobs", "digest": digest, "approve": False,
                                   "used": None}])
                with mock.patch.dict(os.environ, {"DDL_GATE_GRANT_DIR": self.grants}):
                    path, index, item = ddl_gate.confirmation_item(str(self.root), prepared["reportId"], "svc-paid",
                                                                   with_item=True)
                    self.assertEqual((index, item["digest"], item["action"]), (0, digest, "list the jobs"))
                    self.assertEqual(ddl_gate.confirmation_item(str(self.root), prepared["reportId"], "svc-paid"),
                                     (path, 0))  # the two-value call stays
                self.prompt_file.write_text(PROMPT_TEXT, encoding="utf-8")
        # A prompt in a temporary directory, outside the root, is read as well; exactly 32 KiB is the most.
        outside = pathlib.Path(self.tmp) / "prompt.txt"
        outside.write_bytes(b"x" * (32 * 1024))
        self.assertTrue(self.confirmed("claude", confirm=[dict(service[0], prompt=str(outside))])["reportId"])

    def test_a_service_confirmation_pins_its_schema_and_whether_it_may_write(self):
        schema = self.root / "prompts" / "answer.json"
        schema.write_text('{"type": "object"}\n', encoding="utf-8")
        digests = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in (self.prompt_file, schema)}
        items = [{"resource": "svc-paid", "action": "close the stale jobs", "prompt": "prompts/job.md",
                  "schema": "prompts/answer.json", "approve": True},
                 {"resource": "svc-paid", "action": "list the jobs", "prompt": "prompts/job.md"}]
        for runtime, language in (("claude", "en"), ("codex", "ja")):
            with self.subTest(runtime=runtime):
                prepared, session = self.confirmed(runtime, language=language, confirm=items), runtime + "-schema"
                write = "（書き込みあり）" if language == "ja" else " (may write)"
                sep = "、" if language == "ja" else "; "
                self.assertEqual(prepared["question"].split("\n")[5], "{}: svc-paid: close the stale jobs{}{}svc-paid: "
                                 "list the jobs".format(ddl_gate.CONFIRM_LABELS[language], write, sep))
                text = pathlib.Path(prepared["report"]).read_text(encoding="utf-8")
                label = ddl_gate.CONFIRM_LABELS[language]
                self.assertIn("{}: svc-paid: close the stale jobs{}\n{}: svc-paid: list the jobs\n".format(label, write, label),
                              text)
                head = ("svc-paid の答えの形（sha256 {}）:" if language == "ja" else "Schema for svc-paid (sha256 {}):")
                self.assertIn(head.format(digests[schema]) + '\n```\n{"type": "object"}\n```', text)
                self.assert_allowed(self.approve(runtime, prepared, session=session))
                self.assertEqual(self.confirmation(prepared)["items"],
                                 [{"resource": "svc-paid", "action": "close the stale jobs", "digest": digests[self.prompt_file],
                                   "schemaDigest": digests[schema], "approve": True, "used": None},
                                  {"resource": "svc-paid", "action": "list the jobs", "digest": digests[self.prompt_file],
                                   "approve": False, "used": None}])
                # Every unused item of the resource, so the run lane can compare each with what it will run.
                with mock.patch.dict(os.environ, {"DDL_GATE_GRANT_DIR": self.grants}):
                    found = ddl_gate.confirmation_items(str(self.root), prepared["reportId"], "svc-paid")
                    self.assertEqual([(index, item["action"], item["approve"]) for _, index, item in found],
                                     [(0, "close the stale jobs", True), (1, "list the jobs", False)])
                    ddl_gate.mark_confirmation_used(found[1][0], 1)
                    self.assertEqual([index for _, index, _ in ddl_gate.confirmation_items(
                        str(self.root), prepared["reportId"], "svc-paid")], [0])
                    self.assertEqual(ddl_gate.confirmation_item(str(self.root), prepared["reportId"], "svc-paid")[1], 0)
                    ddl_gate.mark_confirmation_used(found[0][0], 0)
                    with self.assertRaisesRegex(ValueError, "used already"):
                        ddl_gate.confirmation_items(str(self.root), prepared["reportId"], "svc-paid")
                    with self.assertRaisesRegex(ValueError, "does not name"):
                        ddl_gate.confirmation_items(str(self.root), prepared["reportId"], "svc")
                    with self.assertRaisesRegex(ValueError, "R- and 16"):
                        ddl_gate.confirmation_items(str(self.root), "G-" + prepared["reportId"][2:], "svc-paid")

    def test_a_service_confirmation_without_a_good_prompt_is_refused(self):
        def refused(reason, confirm):
            for runtime in ("claude", "codex"):
                with self.subTest(reason=reason, runtime=runtime, confirm=confirm):
                    before = sorted(pathlib.Path(self.state).rglob("report.*"))
                    proc = self.subcommand(["prepare-report", "--runtime", runtime],
                                           dict(PrepareReportTest.BASE, confirm=confirm), self.cwd)
                    self.assertEqual((proc.returncode, proc.stdout, proc.stderr), (2, "", "DDL STOP: " + reason + "\n"))
                    self.assertEqual(sorted(pathlib.Path(self.state).rglob("report.*")), before)

        def item(resource="svc", **changes):
            return [dict({"resource": resource, "action": "list the jobs", "prompt": "prompts/job.md"}, **changes)]

        place = ("confirm: a prompt file lies inside the project, outside its protected places, or in a temporary "
                 "directory.")
        refused("confirm: `svc` is a service: its entry names the prompt it sends (prompt: a file).",
                [{"resource": "svc", "action": "list the jobs"}])
        refused("confirm: `batch-1` is reached by ssh: its action is the exact command, and it takes no prompt.",
                item("batch-1"))
        (self.root / ".claude" / "settings.json").write_text("{}")
        (self.root / "big.md").write_bytes(b"x" * (32 * 1024 + 1))
        (self.root / "latin.md").write_bytes(b"caf\xe9\n")
        os.symlink("/etc/hosts", str(self.root / "hosts.md"))
        for prompt, reason in ((".claude/settings.json", place), (".git/config", place), ("/etc/hosts", place),
                               ("hosts.md", place), (".ddl/events.jsonl", place), ("../outside.md", None),
                               ("big.md", "confirm: the prompt file holds more than 32 KiB."),
                               ("prompts", "confirm: the prompt file is not a regular file."),
                               ("missing.md", "confirm: the prompt file cannot be read."),
                               ("latin.md", "confirm: a prompt file is UTF-8 text."),
                               ("", "confirm: a prompt is the path of a file."),
                               ("a\nb", "confirm: a prompt is the path of a file.")):
            if reason is None:  # beside the root, in the temporary directory: read, so only a missing file fails
                reason = "confirm: the prompt file cannot be read."
            refused(reason, item(prompt=prompt))
        entry = ("each confirm entry is {resource, action}, and {resource, action, prompt, schema?, approve?} for a "
                 "service.")
        for changes in ({"digest": "0" * 64}, {"schemaDigest": "0" * 64}, {"text": "x"}):  # the gate computes these
            refused(entry, item(**changes))
        refused(entry, [{"resource": "svc", "action": "x", "schema": "prompts/job.md"}])  # no prompt
        refused(entry, [{"resource": "batch-1", "action": "make", "approve": True}])
        refused("confirm: `batch-1` is reached by ssh: its action is the exact command, and it takes no prompt.",
                item("batch-1", approve=False))
        for value in ("yes", 1, None):
            refused("confirm: approve is true or false.", item(approve=value))
        schema_place = place.replace("a prompt file", "a schema file")
        for schema, reason in ((".claude/settings.json", schema_place), ("/etc/hosts", schema_place),
                               ("big.md", "confirm: the schema file holds more than 32 KiB."),
                               ("prompts", "confirm: the schema file is not a regular file."),
                               ("missing.json", "confirm: the schema file cannot be read."),
                               ("latin.md", "confirm: a schema file is UTF-8 text."), ("", "confirm: a schema is the path of a file.")):
            refused(reason, item(schema=schema))

    def test_the_first_option_records_the_confirmations_on_both_hosts(self):
        for runtime in ("claude", "codex"):
            with self.subTest(runtime=runtime):
                prepared, session = self.confirmed(runtime), runtime + "-confirm"
                ident = prepared["reportId"]
                self.assert_allowed(self.ask(runtime, prepared, session))
                self.assertIsNone(self.confirmation(prepared))  # asking records nothing
                if runtime == "codex":
                    self.assert_allowed(self.reply(prepared, 0, session))
                    self.assertIsNone(self.confirmation(prepared))  # nor does the reply: the proof reads the record
                self.assert_allowed(self.tool(runtime, self.flow(runtime, prepared, "answered"), session))
                record = self.confirmation(prepared)
                self.assertEqual(set(record), {"id", "projectKey", "root", "items", "approvedAt", "session", "host"})
                self.assertEqual({key: record[key] for key in ("id", "projectKey", "root", "items", "session", "host")},
                                 {"id": ident, "projectKey": project_key(self.root), "root": os.path.realpath(self.root),
                                  "items": [dict(CONFIRM[0], used=None)], "session": session, "host": runtime})
                self.assertRegex(record["approvedAt"], ISO_UTC)
                path = self.confirmations / (ident + ".json")
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                self.assertEqual(self.confirmations.stat().st_mode & 0o777, 0o700)
                self.assertEqual([entry.name for entry in self.store.parent.iterdir()], ["confirmations"])  # no grant
                self.assertEqual([(row["kind"], row.get("id")) for row in events(self.root, session=session)],
                                 [("asked", ident), ("answered", ident), ("confirmed", ident)])
                self.assertFalse(self.armed(session))
                before = path.read_bytes()
                self.assert_allowed(self.stop(runtime, self.flow(runtime, prepared, "answered"), session))
                self.assertEqual(path.read_bytes(), before)  # written once

    def test_a_report_with_a_grant_and_confirmations_records_both_and_stop_records_too(self):
        for runtime in ("claude", "codex"):
            with self.subTest(runtime=runtime):
                prepared, session = self.confirmed(runtime, grant=grant()), runtime + "-both"
                self.assert_allowed(self.approve(runtime, prepared, session=session))
                self.assertTrue(self.record(prepared) and self.confirmation(prepared))
                self.assertEqual([row["kind"] for row in events(self.root, session=session)][-2:], ["granted", "confirmed"])
                late, session = self.confirmed(runtime), runtime + "-stop"
                self.assert_allowed(self.ask(runtime, late, session))
                if runtime == "codex":
                    self.assert_allowed(self.reply(late, 0, session))
                self.assert_allowed(self.stop(runtime, self.flow(runtime, late, "answered"), session))
                self.assertEqual(self.confirmation(late)["session"], session)

    def test_nothing_is_recorded_unless_the_first_option_is_submitted(self):
        for runtime in ("claude", "codex"):
            with self.subTest(runtime=runtime, case="unanswered"):
                prepared, session = self.confirmed(runtime), runtime + "-unanswered"
                self.assert_allowed(self.ask(runtime, prepared, session))
                asked = self.flow(runtime, prepared, "asked")
                self.tool(runtime, asked, session)
                self.assert_allowed(self.stop(runtime, asked, session))
                self.assert_no_confirmation()
            for answer in (1, 2):  # another option, or declining
                with self.subTest(runtime=runtime, answer=answer):
                    prepared, session = self.confirmed(runtime), "{}-option-{}".format(runtime, answer)
                    self.assert_allowed(self.approve(runtime, prepared, answer, session))
                    self.assert_allowed(self.stop(runtime, self.flow(runtime, prepared, "answered", answer), session))
                    self.assert_no_confirmation()
            with self.subTest(runtime=runtime, case="typed"):
                prepared, session = self.confirmed(runtime), runtime + "-typed"
                typed = (user("OK, confirmed.", **HUMAN_ORIGIN) if runtime == "claude" else
                         {"type": "event_msg", "payload": {"type": "item_completed", "item": {
                             "type": "UserMessage", "content": [{"type": "text", "text": "OK, confirmed."}]}}})
                transcript = self.flow(runtime, prepared, "asked", mutate=lambda rows: rows.append(typed))
                self.assert_allowed(self.ask(runtime, prepared, session))
                self.assert_allowed(self.prompt(runtime, transcript, "OK, confirmed.", session))
                self.assert_allowed(self.tool(runtime, transcript, session))
                late = self.flow(runtime, prepared, "answered", mutate=lambda rows: rows.append(typed))
                self.assert_allowed(self.tool(runtime, late, session))
                self.assert_allowed(self.stop(runtime, late, session))
                self.assert_no_confirmation()
            with self.subTest(runtime=runtime, case="another project"):
                foreign, session = self.prepare_report(runtime, confirm=CONFIRM), runtime + "-foreign"
                self.assert_allowed(self.approve(runtime, foreign, session=session))
                self.assert_allowed(self.stop(runtime, self.flow(runtime, foreign, "answered"), session))
                self.assert_no_confirmation()

        def timed_out(rows):
            rows[4]["toolUseResult"]["afkTimeoutMs"] = 60000  # the host submitted the selection after the idle wait

        prepared = self.confirmed("claude")
        self.approve("claude", prepared, session="timeout", mutate=timed_out)
        self.assert_allowed(self.stop("claude", self.flow("claude", prepared, "answered", mutate=timed_out), "timeout"))
        self.assert_no_confirmation()

    def test_an_item_is_taken_once(self):
        root, key, store = os.path.realpath(self.root), project_key(self.root), ddl_gate.store_confirmation

        def body(ident, *resources):
            return {"id": ident, "projectKey": key, "root": root, "approvedAt": "2026-11-24T00:00:00.000Z",
                    "items": [{"resource": name, "action": "run {}".format(i), "used": None}
                              for i, name in enumerate(resources)], "session": "s", "host": "claude"}

        ident = "R-" + "d" * 16
        with mock.patch.dict(os.environ, {"DDL_GATE_GRANT_DIR": self.grants}):
            self.assertIs(store(body(ident, "batch-1", "svc-paid", "batch-1")), True)
            path = str(self.confirmations / (ident + ".json"))
            self.assertEqual(ddl_gate.confirmation_item(str(self.root), ident, "batch-1"), (path, 0))
            self.assertRegex(ddl_gate.mark_confirmation_used(path, 0), ISO_UTC)
            self.assertEqual(oct(os.stat(path).st_mode & 0o777), oct(0o600))
            self.assertEqual(ddl_gate.confirmation_item(str(self.root), ident, "batch-1"), (path, 2))
            self.assertEqual(ddl_gate.confirmation_item(str(self.root), ident, "svc-paid"), (path, 1))
            ddl_gate.mark_confirmation_used(path, 2)
            with self.assertRaisesRegex(ValueError, "used already"):
                ddl_gate.confirmation_item(str(self.root), ident, "batch-1")
            with self.assertRaisesRegex(ValueError, "used already"):
                ddl_gate.mark_confirmation_used(path, 0)
            self.assertIs(store(body(ident, "batch-1", "svc-paid", "batch-1")), False)  # a later recording resets nothing
            items = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))["items"]
            self.assertEqual([item["used"] is None for item in items], [False, True, False])
            self.assertEqual(sorted(name for name in os.listdir(str(self.confirmations))), [ident + ".json", ident + ".json.lock"])
            for args, message in (((str(self.root), ident, "svc"), "does not name"),
                                  ((str(self.root), "G-" + "d" * 16, "batch-1"), "R- and 16"),
                                  ((str(self.root), "R-xyz", "batch-1"), "R- and 16"), ((str(self.root), None, "batch-1"), "R- and 16"),
                                  ((str(self.root), "R-" + "e" * 16, "batch-1"), "no confirmation"),
                                  ((str(self.tmp), ident, "batch-1"), "no confirmation"), ((None, ident, "batch-1"), "DDL project")):
                with self.subTest(args=args), self.assertRaisesRegex(ValueError, message):
                    ddl_gate.confirmation_item(*args)
            for index in (3, -1, True, "0", None):
                with self.subTest(index=index), self.assertRaisesRegex(ValueError, "no such"):
                    ddl_gate.mark_confirmation_used(path, index)
            with self.assertRaisesRegex(ValueError, "no such"):
                ddl_gate.mark_confirmation_used(str(self.confirmations / ("R-" + "e" * 16 + ".json")), 0)
            # Eight runs reach for one item at once: one takes it.
            other = "R-" + "f" * 16
            store(body(other, "svc-paid"))
            taken, path = [], str(self.confirmations / (other + ".json"))

            def take():
                try:
                    taken.append(ddl_gate.mark_confirmation_used(path, 0))
                except ValueError:
                    taken.append(None)

            import threading
            threads = [threading.Thread(target=take) for _ in range(8)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(len([stamp for stamp in taken if stamp]), 1, taken)
            self.assertEqual(json.loads(pathlib.Path(path).read_text(encoding="utf-8"))["items"][0]["used"],
                             next(stamp for stamp in taken if stamp))

    def test_the_hook_leaves_a_confirmed_call_to_the_host(self):
        for runtime in ("claude", "codex"):
            for command in ("remote batch-1 --confirmed R-{0} -- make", "remote build-1 --confirmed R-{0} -- make",
                            "service svc-paid --prompt-file tools/p.md --confirmed R-{0}",
                            "service svc --prompt-file tools/p.md --approve"):
                with self.subTest(runtime=runtime, command=command):
                    tool, key = SHELL[runtime]
                    proc = self.call(runtime, fixture(runtime + "_open.jsonl"), tool,
                                     {key: GATE_CALL + " " + command.format("d" * 16)}, cwd=self.cwd)
                    self.assertEqual(proc.stdout, "")


class GrantStoreTest(GrantFlowTest):
    """Where the grant store lives: DDL_GATE_GRANT_DIR, else XDG_STATE_HOME/ddl-gate, else HOME/.local/state/ddl-gate."""

    def setUp(self):
        super().setUp()
        self.home, self.variables = os.path.join(self.tmp, "home"), {}
        os.mkdir(self.home)

    def gate_env(self):
        """The store's variables are the test's own, and HOME is never the real one: the last fallback writes below it."""
        env = {name: value for name, value in super().gate_env().items()
               if name not in ("DDL_GATE_GRANT_DIR", "XDG_STATE_HOME")}
        env.update(self.variables, HOME=self.home)
        return env

    def test_each_fallback_holds_the_record_and_is_where_readers_look(self):
        named, xdg = os.path.join(self.tmp, "named"), os.path.join(self.tmp, "xdg")
        below_home = os.path.join(self.home, ".local")
        # A relative value is taken from the working directory of the gate process: a disposable project here.
        relative = os.path.join(os.getcwd(), "rel")
        self.assertEqual(os.path.realpath(relative), os.path.realpath(str(PROJECT / "rel")))
        self.addCleanup(shutil.rmtree, relative, True)
        cases = [("the variable", {"DDL_GATE_GRANT_DIR": named}, named, named),
                 ("the variable before the others", {"DDL_GATE_GRANT_DIR": named, "XDG_STATE_HOME": xdg}, named, named),
                 ("XDG_STATE_HOME", {"XDG_STATE_HOME": xdg}, os.path.join(xdg, "ddl-gate"), xdg),
                 ("an empty variable is unset", {"DDL_GATE_GRANT_DIR": "", "XDG_STATE_HOME": xdg},
                  os.path.join(xdg, "ddl-gate"), xdg),
                 ("neither variable", {}, os.path.join(below_home, "state", "ddl-gate"), below_home),
                 ("both empty", {"DDL_GATE_GRANT_DIR": "", "XDG_STATE_HOME": ""},
                  os.path.join(below_home, "state", "ddl-gate"), below_home),
                 ("a relative value", {"DDL_GATE_GRANT_DIR": os.path.join("rel", "store")},
                  os.path.join(relative, "store"), relative)]
        for number, (name, variables, store, top) in enumerate(cases):
            with self.subTest(case=name):
                self.variables = variables
                with mock.patch.dict(os.environ, self.gate_env(), clear=True):
                    self.assertEqual(ddl_gate.grant_store(), store)  # the path alone: asking for it creates nothing
                self.assertEqual([path for path in (named, xdg, below_home, relative) if os.path.exists(path)], [])
                prepared, session = self.prepared("claude"), "store-{}".format(number)
                self.assert_allowed(self.approve("claude", prepared, session=session))
                path = pathlib.Path(store) / project_key(self.root) / "grants" / (prepared["reportId"] + ".json")
                self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["session"], session)
                self.assertEqual([path for path in (named, xdg, below_home, relative) if os.path.exists(path)], [top])
                self.assertIn("Grant: {} ".format(prepared["reportId"]), self.subcommand(["status", "--cwd", self.cwd]).stdout)
                shutil.rmtree(top)
        self.assertFalse(os.path.exists(self.grants))  # the suite's default store was never used


PATCH = "*** Begin Patch\n{}*** End Patch"
ALLOW_PERMISSION = {"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": {"behavior": "allow"}}}


class GrantAnswers(GrantFlowTest):
    """A project with a few files, grant records written straight into the store, and the gate's answer to one call
    on both hosts. It holds no test: GrantAnswerTest and ResourceAnswerTest do."""

    def setUp(self):
        super().setUp()
        for directory in ("tools/deep", "skills", "bin", ".notebook.git/objects", ".ddl/runs/N-0123456789ab"):
            (self.root / directory).mkdir(parents=True, exist_ok=True)
        (self.root / ".notebook.git" / "HEAD").write_text("ref: refs/heads/main\n")
        (self.root / "tools" / "test_x.py").write_text("")
        self.outside = pathlib.Path(self.tmp) / "outside"
        self.outside.mkdir()

    def granted(self, ident="R-" + "a" * 16, days=30, approved="2026-11-20T00:00:00.000Z", **changes):
        """A grant record as the gate stores it (the form read_grant accepts); its ID."""
        expires = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=days)).replace(microsecond=0)
        fields = dict({"paths": ["tools/**", "skills/*.md"], "commands": ["test", "check"]}, **changes)
        record = {"id": ident, "projectKey": project_key(self.root), "root": os.path.realpath(self.root),
                  "grant": grant(expires=expires.isoformat(), **fields), "approvedAt": approved, "session": "plan",
                  "host": "claude"}
        self.store.mkdir(parents=True, exist_ok=True)
        (self.store / (ident + ".json")).write_text(json.dumps(record), encoding="utf-8")
        return ident

    @staticmethod
    def edit(runtime, *paths, kind="Update File"):
        if runtime == "claude":
            return "Edit", {"file_path": paths[0], "old_string": "a", "new_string": "b"}
        return "apply_patch", {"patch": PATCH.format("".join("*** {}: {}\n@@\n-a\n+b\n".format(kind, p) for p in paths))}

    @staticmethod
    def shell(runtime, command):
        tool, key = SHELL[runtime]
        return tool, {key: command}

    def decide(self, runtime, call, transcript=None, event="pre-tool-use", process=False):
        """The gate's output for one call: its `main` in this process (the same argv, stdin, stdout, environment
        and working directory as the hook's), or with `process` the launcher as a subprocess, as the hosts run it."""
        tool, tool_input = call
        data = payload(runtime, transcript=fixture(runtime + "_open.jsonl") if transcript is None else transcript or None,
                       session=runtime, cwd=self.cwd, tool_name=tool, tool_input=tool_input)
        if event == "permission-request":
            data.update(hook_event_name="PermissionRequest")
            data.pop("tool_use_id", None)
        if process:
            out = self.run_gate(event, runtime, data).stdout
        else:
            with mock.patch.dict(os.environ, {"DDL_GATE_STATE_DIR": self.state, "DDL_GATE_GRANT_DIR": self.grants}), \
                    mock.patch("sys.stdin", io.StringIO(json.dumps(data))), \
                    mock.patch("sys.stdout", new_callable=io.StringIO) as stdout, \
                    mock.patch("sys.stderr", new_callable=io.StringIO) as stderr:
                self.assertEqual(ddl_gate.main([event, "--runtime", runtime]), 0)
            self.assertEqual(stderr.getvalue(), "")
            out = stdout.getvalue()
        return json.loads(out) if out else None

    def outcome(self, runtime, call, transcript=None):
        """("allow" | "deny", reason) or None; Codex's allow is its PermissionRequest's, which has no reason."""
        pre = self.decide(runtime, call, transcript)
        verdict = pre and pre.get("hookSpecificOutput", {}).get("permissionDecision")
        if runtime == "codex":
            self.assertNotEqual(verdict, "allow")  # Codex refuses an allow from PreToolUse
            asked = self.decide(runtime, call, transcript, "permission-request")
            if pre is not None or asked is not None:
                self.assertTrue(pre is None or asked is None, (pre, asked))
            if asked is not None:
                self.assertEqual(asked, ALLOW_PERMISSION)  # no updatedInput, updatedPermissions or interrupt
                return "allow", None
        if pre is None:
            return None
        if "systemMessage" in pre:
            return "warn", pre["systemMessage"]
        return verdict, pre["hookSpecificOutput"]["permissionDecisionReason"]

    def expect(self, make, expected, transcript=None):
        for runtime in ("claude", "codex"):
            call = make(runtime)
            with self.subTest(runtime=runtime, call=call):
                want = ("allow", None) if expected and expected[0] == "allow" and runtime == "codex" else expected
                self.assertEqual(self.outcome(runtime, call, transcript and transcript(runtime)), want)

    def allow(self, ident, kind):
        return "allow", ddl_gate.GRANT_ALLOW.format(ident, kind)


class GrantAnswerTest(GrantAnswers):
    """What an active grant answers (the protocol's Run Operation step 1 and Formats): an allow inside it, a deny
    outside it, the host's own decision for everything else; never under a pending STOP, and nothing without it.

    Claude reads the allow from PreToolUse; Codex takes none there, so its PermissionRequest gives the same answer.
    Each check runs on both hosts, and a Codex call that PreToolUse denies gets nothing from PermissionRequest."""

    def test_the_launcher_gives_the_same_answers_as_the_code_it_loads(self):
        """The rest of this class calls the gate in process; the hook runs ddl_gate.py. Both answer alike."""
        ident = self.granted(machines=["build-1"])
        calls = [lambda rt: self.edit(rt, "tools/x.py"), lambda rt: self.edit(rt, "design.md"),
                 lambda rt: self.shell(rt, "python3 tools/test_x.py"), lambda rt: self.shell(rt, "python3 tools/build.py"),
                 lambda rt: self.shell(rt, "ssh build-1 git push"), lambda rt: self.shell(rt, "touch x"),
                 lambda rt: self.shell(rt, 'python3 "$HOME/.claude/hooks/ddl_gate.py" status')]
        for runtime in ("claude", "codex"):
            for make in calls:
                for event in ("pre-tool-use", "permission-request"):
                    with self.subTest(runtime=runtime, call=make(runtime), event=event):
                        self.assertEqual(self.decide(runtime, make(runtime), event=event, process=True),
                                         self.decide(runtime, make(runtime), event=event))
        self.assertEqual(self.outcome("claude", self.edit("claude", "tools/x.py")), self.allow(ident, "edit"))

    def test_an_edit_inside_the_grant_is_allowed_and_one_outside_its_paths_denied(self):
        ident = self.granted()
        for path in ("tools/x.py", "tools/deep/x.py", "skills/a.md", str(self.root / "tools" / "x.py"), "bin/../tools/x.py"):
            self.expect(lambda rt, p=path: self.edit(rt, p), self.allow(ident, "edit"))
        for path in ("docs/a.md", "skills/deep/a.md", "bin/x.sh", "toolsx/a.py"):
            self.expect(lambda rt, p=path: self.edit(rt, p), ("deny", ddl_gate.OUTSIDE_PATHS.format(path, ident)))
        for tool, key in (("Write", "file_path"), ("MultiEdit", "file_path"), ("NotebookEdit", "notebook_path")):
            self.assertEqual(self.outcome("claude", (tool, {key: "tools/n.ipynb"})), self.allow(ident, "edit"))
            self.assertEqual(self.outcome("claude", (tool, {key: "x.ipynb"})),
                             ("deny", ddl_gate.OUTSIDE_PATHS.format("x.ipynb", ident)))

    def test_protected_files_and_paths_outside_the_root_are_the_hosts(self):
        """Git directories, the ledger directory, the adapters' directories, the instruction files and the notebook
        are never a grant's, not even under `**` or by name; nor is anything outside the root."""
        ident = self.granted(paths=["**"])
        os.symlink(str(self.outside), str(self.root / "tools" / "out"))
        os.symlink(str(self.outside / "f.py"), str(self.root / "tools" / "link.py"))
        for path in (".git/config", ".notebook.git/config", ".ddl/notes.md", str(self.outside / "x.py"),
                     "../outside/x.py", "tools/out/x.py", "tools/link.py", ".claude/settings.json", ".claude/CLAUDE.md",
                     ".codex/config.toml", ".agents/skills/x/SKILL.md", "CLAUDE.md", "docs/AGENTS.md", "design.md",
                     "design-history.md", "tools/deep/design.md", ".mcp.json", "CLAUDE.local.md", "docs/AGENTS.override.md",
                     ".envrc", ".vscode/tasks.json", ".githooks/pre-commit", ".gitattributes", "sub/.gitmodules",
                     ".pre-commit-config.yaml", ".github/workflows/ci.yml", ".cursor/rules/x.mdc", ".claude.json",
                     "sub/.claude.json"):
            self.expect(lambda rt, p=path: self.edit(rt, p), None)
        self.granted(paths=[".claude/**", "design.md", "CLAUDE.md"])  # named explicitly: still the host's
        for path in (".claude/settings.json", "design.md", "CLAUDE.md"):
            self.expect(lambda rt, p=path: self.edit(rt, p), None)
        self.granted(paths=["**"])
        if ddl_gate.folds_case(os.path.realpath(str(self.root))):  # the macOS default: the spelling does not matter
            for path in (".CLAUDE/settings.json", ".Codex/config.toml", "Design.md", ".GIT/config", "claude.md",
                         ".VSCode/x.json", ".GitAttributes", "Claude.Local.md", ".MCP.json", "de\u017fign.md",
                         ".GitHub/Workflows/ci.yml", ".Cursor/x", ".Claude.json"):
                self.expect(lambda rt, p=path: self.edit(rt, p), None)
        self.expect(lambda rt: self.edit(rt, "docs/a.md"), self.allow(ident, "edit"))  # `**` reaches the rest
        self.expect(lambda rt: self.edit(rt, ".github/CODEOWNERS"), self.allow(ident, "edit"))  # only its workflows

    def test_codex_patch_targets_all_count_and_a_deletion_is_the_hosts(self):
        ident = self.granted()
        self.assertEqual(self.outcome("codex", self.edit("codex", "tools/a.py", "skills/b.md", kind="Add File")),
                         ("allow", None))
        self.assertEqual(self.outcome("codex", self.edit("codex", "tools/a.py", "docs/a.md")),
                         ("deny", ddl_gate.OUTSIDE_PATHS.format("docs/a.md", ident)))
        self.assertIsNone(self.outcome("codex", self.edit("codex", "tools/a.py", "design.md")))  # protected
        indented = ("apply_patch", {"patch": PATCH.format("*** Update File: tools/a.py\n@@\n-a\n+b\n"
                                                          "  *** Add File: ../outside/evil.txt\n+x\n")})
        self.assertIsNone(self.outcome("codex", indented))  # an indented header counts like any other
        self.assertIsNone(self.outcome("codex", self.edit("codex", "tools/a.py", str(self.outside / "b.py"))))
        self.assertIsNone(self.outcome("codex", self.edit("codex", "tools/a.py", kind="Delete File")))
        moved = ("apply_patch", {"patch": PATCH.format("*** Update File: tools/a.py\n*** Move to: ../outside/a.py\n")})
        self.assertIsNone(self.outcome("codex", moved))
        self.assertIsNone(self.outcome("codex", ("apply_patch", {"patch": PATCH.format("")})))  # no target named

    def test_commands_inside_the_grant_are_allowed_by_class(self):
        ident = self.granted(commands=["test", "check", "build"])
        cases = {
            "read": ["git status", "sed -n '1,5p' tools/x.py | head -n 3", "cd /tmp && ls"],
            "test": ["cd tools && python3 test_x.py 2>&1 | tail -5", "python3 -I -B tools/test_x.py -k Grant",
                     "/usr/bin/python3 tools/deep/x_test.py", "python3.9 -m unittest discover -s tools -p 'test_*.py'",
                     "python3 -m unittest -v tools.test_x", "python3 -m pytest tools", "pytest -q -x tools/test_x.py",
                     "pytest -k 'grant and not slow' --maxfail=2 -m fast tools", "npm test", "cargo test",
                     "cargo test --release -p core -- grant", "go test ./...",
                     "go test -v -race -run TestGrant -count 1 -timeout 10m ./...", "make test", "make -j 4 test",
                     "python3 tools/test_x.py --out /tmp/result.json < /dev/null"],
            "check": ["python3 tools/check_x.py source", "bash -n bin/install.sh bin/doctor.sh", "git diff --check",
                      "make lint", "make check"],
            "build": ["python3 tools/build.py", "make", "make all", "make -j8 build", "npm run build", "cargo build",
                      "cargo build --workspace --all-features", "go build ./...", "go build -v ./cmd/x"],
            "test, check": ["python3 tools/test_x.py > /dev/null && python3 tools/check_x.py"],
        }
        for kind, commands in cases.items():
            for command in commands:
                self.expect(lambda rt, c=command: self.shell(rt, c), self.allow(ident, kind))

    def test_a_validation_command_is_a_check_exactly_as_the_notebook_writes_it(self):
        ident = self.granted(commands=["check"])
        command = 'ddl_tmp=$(mktemp -d) &&\n(\n  trap \'rm -rf "$ddl_tmp"\' EXIT\n  python3 tools/run_x.py "$ddl_tmp"\n)'
        (self.root / "design.md").write_text(
            "# design.md\n\n## Validation\n\n```bash\n# V1 tools: a check\n" + command + "\n# expected: OK\n\n"
            "# V2 tools: a push is never a grant's\ngit push --dry-run origin main\n```\n", encoding="utf-8")
        self.expect(lambda rt: self.shell(rt, command), self.allow(ident, "check"))
        spaced = command.replace("trap", "trap  ").replace("\n  ", "\n\t") + "\n\n"
        self.expect(lambda rt: self.shell(rt, spaced), self.allow(ident, "check"))  # whitespace within lines
        self.expect(lambda rt: self.shell(rt, " ".join(command.split())), None)  # a newline is no space
        self.expect(lambda rt: self.shell(rt, command.replace("run_x", "run_y")), None)
        out = self.decide("claude", self.shell("claude", "git push --dry-run origin main"))
        self.assertIn("DDL Git review", out["hookSpecificOutput"]["permissionDecisionReason"])
        # Without the `check` class the notebook is not read, and the same text is the host's.
        self.granted(commands=["test"])
        self.expect(lambda rt: self.shell(rt, command), None)

    def test_the_notebook_the_guidance_names_holds_the_validation_commands(self):
        ident = self.granted(commands=["check"])
        mark_project(self.root)  # .claude/CLAUDE.md; point its Notebook import at another file
        path = self.root / ".claude" / "CLAUDE.md"
        path.write_text(path.read_text() + "\n## Notebook\n\n@../notes/plan.md\n", encoding="utf-8")
        (self.root / "notes").mkdir()
        (self.root / "notes" / "plan.md").write_text("## Validation\n\n```\n# V9 x\necho $HOME | wc -c\n```\n")
        (self.root / "design.md").write_text("## Validation\n\n```\n# V1 x\necho $PATH | wc -c\n```\n")
        self.expect(lambda rt: self.shell(rt, "echo $HOME | wc -c"), self.allow(ident, "check"))
        self.expect(lambda rt: self.shell(rt, "echo $PATH | wc -c"), None)
        self.granted(paths=["**"], commands=["check"])
        self.expect(lambda rt: self.edit(rt, "notes/plan.md"), None)  # the named notebook is protected too

    def test_the_gates_own_subcommands_need_no_class_and_snapshot_needs_its_own(self):
        ident = self.granted(commands=["test"])
        for command in ('python3 "$HOME/.claude/hooks/ddl_gate.py" status',
                        'python3 "$HOME/.codex/hooks/ddl_gate.py" run-item N-0123456789ab w1 done',
                        'python3 "${HOME}/.codex/hooks/ddl_gate.py" status',
                        "python3 {} run-start < /etc/hosts".format(shlex.quote(GATE)),
                        "python3 -I {} report --run N-0123456789ab".format(shlex.quote(GATE)),
                        'python3 "$HOME/.claude/hooks/ddl_gate.py" run-start <<\'JSON\'\n{"report": "R-x"}\nJSON',
                        PREPARE_CALL["claude"]):
            self.expect(lambda rt, c=command: self.shell(rt, c), self.allow(ident, "gate"))
        snapshot = 'python3 "$HOME/.claude/hooks/ddl_gate.py" snapshot --item w1'
        self.expect(lambda rt: self.shell(rt, snapshot), ("deny", ddl_gate.OUTSIDE_CLASS.format("snapshot", ident)))
        for command in ('python3 "$HOME/.claude/hooks/ddl_gate.py" bogus',
                        'python3 "$HOME/.claude/hooks/ddl_gate.py" status > status.txt',
                        "python3 tools/test_x.py <<'EOF'\ninput\nEOF"):
            self.expect(lambda rt, c=command: self.shell(rt, c), None)
        # Only the real gate: a project file of that name, a made-up path, an unquoted `$HOME` are not it.
        (self.root / "tools" / "ddl_gate.py").write_text("print('not the gate')\n")
        (self.root / ".claude" / "hooks").mkdir(parents=True, exist_ok=True)
        for command in ("python3 tools/ddl_gate.py status", "python3 ./tools/ddl_gate.py run-item N-0123456789ab w1 done",
                        "python3 /ddl-gate-entry/ddl_gate.py status", "python3 $HOME/.claude/hooks/ddl_gate.py status",
                        'python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/ddl_gate.py" status'):
            self.expect(lambda rt, c=command: self.shell(rt, c), None)
        other = self.granted("R-" + "b" * 16, commands=["snapshot"], approved="2026-11-21T00:00:00.000Z")
        self.expect(lambda rt: self.shell(rt, snapshot), self.allow(other, "snapshot"))
        inside = snapshot + " --git-dir .notebook.git --work-tree=."
        self.expect(lambda rt: self.shell(rt, inside), self.allow(other, "snapshot"))
        for pair in (" --git-dir=/tmp/other/.git --work-tree=/tmp/other", " --git-dir .git --work-tree " + shlex.quote(str(self.outside)),
                     " --git-dir ../outside/.git --work-tree ."):
            self.expect(lambda rt, c=snapshot + pair: self.shell(rt, c), None)  # both inside the root, or the host's

    def test_a_class_outside_the_grant_is_denied(self):
        ident = self.granted(commands=["test"])
        for command, kind in (("python3 tools/build.py", "build"), ("make", "build"), ("go build ./...", "build"),
                              ("python3 tools/check_x.py", "check"), ("git diff --check", "check"),
                              ("python3 tools/test_x.py && python3 tools/build.py", "build"),
                              ("ssh build-1 ls", None)):
            expected = ("deny", ddl_gate.OUTSIDE_CLASS.format(kind, ident)) if kind else \
                ("deny", ddl_gate.OUTSIDE_MACHINE.format("build-1", ident))
            self.expect(lambda rt, c=command: self.shell(rt, c), expected)

    def test_everything_else_is_the_hosts(self):
        self.granted(commands=["test", "check", "build"])
        for command in ("python3 tools/test_$X.py", "python3 /tmp/test_x.py", "python3 tools/test_x.py /etc/passwd",
                        "cd / && python3 tools/test_x.py", "cd tools | python3 ../../x/test_x.py",
                        "make install", "make deploy", "make deploy-prod", "make install-local", "make Install",
                        "make -j", "make VAR=1", "make -f other.mk", "make -C tools test",
                        "python3 tools/test_x.py > out.txt", "FOO=1 python3 tools/test_x.py",
                        "env python3 tools/test_x.py", "python3 -c 'print(1)'", "./tools/test_x.py",
                        "python3 tools/x.py", "npm test -- --watch", "npm run deploy", "touch tools/x.py", "rm -rf tools",
                        "cd - && make", "cd .git && make", "cd .claude && python3 ../tools/test_x.py",
                        # options outside each class form's allow-list
                        "bash -n +n -c 'git push origin main'", "bash -n -o noexec +o noexec -c 'git commit -m x'",
                        "bash -n +n tools/x.sh", "bash -n -i tools/x.sh", "bash -n", "bash -n /etc/profile",
                        "go test -exec 'sh -c touch' .", "go test -exec=/tmp/evil ./...", "go build -toolexec x ./...",
                        "go build -o .git/hooks/pre-commit ./cmd", "go test -count x ./...", "go test -timeout soon ./...",
                        "cargo build --config x", "cargo test -- --nocapture", "cargo test tests::x", "cargo test -Z x",
                        "pytest --basetemp=.git", "pytest --junitxml=.ddl/events.jsonl", "pytest -p evil",
                        "python3 -m pytest -o cache_dir=/tmp/x", "pytest --maxfail=many", "pytest -qx tools",
                        "python3 -m unittest discover -s /etc", "python3 -m unittest discover -t ..",
                        "python3 -m unittest -b", "python3 -m unittest --locals",
                        "git diff --check --output=/tmp/x", "git diff --check --ext-diff",
                        # words that name a protected file, whatever their shape
                        "python3 tools/test_x.py --basetemp=.git", "python3 tools/test_x.py .claude/settings.json",
                        "python3 tools/test_x.py -o.git/x", "python3 tools/test_x.py design.md", "pytest .codex",
                        "bash -n .claude/hooks/x.sh", "python3 .claude/hooks/test_x.py",
                        # branch-moving Git commands
                        "git reset --hard HEAD~1", "git checkout -B other", "git rebase main", "git branch -D old",
                        "git switch -C topic", "git merge other", "git tag v1", "git stash", "git update-ref refs/x HEAD",
                        # outbound commands
                        "curl -X POST https://example.invalid -d x", "gh pr create --fill", "npm publish",
                        "scp tools/x.py host:", "rsync -a . host:", "nc example.invalid 80", "ssh -p 22 host ls"):
            self.expect(lambda rt, c=command: self.shell(rt, c), None)

    def test_remote_run_reaches_only_a_granted_machine_and_never_an_exit_behind_it(self):
        ident = self.granted(commands=["remote-run"], machines=["build-1"])
        for command in ("ssh -o BatchMode=yes -o ConnectTimeout=5 -T build-1 make test",
                        "ssh -n build-1 python3 run.py --out /var/tmp/x", "ssh -oBatchMode=yes build-1 nvidia-smi"):
            self.expect(lambda rt, c=command: self.shell(rt, c), self.allow(ident, "remote-run"))
        for command, word in (("ssh build-1 git push origin main", "git push"),
                              ("ssh build-1 git -C w commit -m x", "git commit"),
                              ("ssh build-1 git branch -D old", "git branch"),
                              ("ssh build-1 rsync -a . other:", "rsync"), ("ssh build-1 ssh other ls", "ssh"),
                              ("ssh build-1 scp x other:", "scp"), ("ssh build-1 gh release create v1", "gh"),
                              ("ssh -T build-1 curl -X POST https://example.invalid", "method -X"),
                              ("ssh build-1 curl --data @f https://example.invalid", "upload --data"),
                              ("ssh build-1 npm publish", "npm publish")):
            self.expect(lambda rt, c=command: self.shell(rt, c), ("deny", ddl_gate.EXIT_BEHIND_SSH.format(word)))
        self.expect(lambda rt: self.shell(rt, "ssh other-host ls"),
                    ("deny", ddl_gate.OUTSIDE_MACHINE.format("other-host", ident)))
        for command in ("ssh -p 22 build-1 ls", "ssh build-1", "ssh -i key build-1 ls",
                        # an option after the machine: OpenSSH still reads it
                        "ssh build-1 -oProxyCommand=x true", "ssh build-1 -o ProxyCommand=nc true",
                        "ssh build-1 -oLocalCommand=x -oPermitLocalCommand=yes true", "ssh build-1 -F /tmp/cfg true",
                        "ssh build-1 -J jump true", "ssh build-1 -L 8080:intranet:80 sleep 9",
                        "ssh build-1 -R 2222:localhost:22 sleep 9", "ssh build-1 -D 1080 sleep 9",
                        # a remote command that is not literal words, which could hide an exit
                        "ssh build-1 'cd work && make test'", "ssh build-1 'g\"\"it push'", "ssh build-1 'gi\\t push'",
                        "ssh build-1 'x=gi; ${x}t push'", "ssh build-1 \"echo x | sh\"", "ssh build-1 make > /dev/null",
                        "ssh build-1 ma\\ke"):
            self.expect(lambda rt, c=command: self.shell(rt, c), None)

    def test_a_command_or_an_edit_starts_inside_the_root_and_runs_in_a_standard_shell(self):
        ident = self.granted(paths=["tools/**"], commands=["build", "test"])
        read, build = self.allow(ident, "read"), self.allow(ident, "build")
        outside = str(self.outside)
        for workdir in (outside, "/", ".claude", ".git", "../outside"):
            with self.subTest(workdir=workdir):
                for command in ("make", "pytest", 'python3 "$HOME/.claude/hooks/ddl_gate.py" status'):
                    call = ("exec_command", {"cmd": command, "workdir": workdir})
                    self.assertIsNone(self.outcome("codex", call))
                self.assertEqual(self.outcome("codex", ("exec_command", {"cmd": "git status", "workdir": workdir})),
                                 ("allow", None))  # a read may run anywhere
                patch = self.edit("codex", str(self.root / "tools" / "a.py"))
                self.assertIsNone(self.outcome("codex", (patch[0], dict(patch[1], workdir=workdir))))
        for workdir in ("tools", str(self.root / "tools")):
            self.assertEqual(self.outcome("codex", ("exec_command", {"cmd": "make", "workdir": workdir})), ("allow", None))
        # Claude's working directory is the call's `cwd`: a protected directory inside the root is not a start.
        for cwd, expected in ((self.root / ".claude", None), (self.root / "tools", build)):
            data = payload("claude", transcript=fixture("claude_open.jsonl"), session="cwd", cwd=str(cwd),
                           tool_name="Bash", tool_input={"command": "make"})
            out = self.run_gate("pre-tool-use", "claude", data).stdout
            self.assertEqual(json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"] if out else None,
                             expected and expected[1])
            data["tool_input"] = {"command": "git status"}
            out = self.run_gate("pre-tool-use", "claude", data).stdout
            self.assertEqual(json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"], read[1])
        # A command that runs through anything but bash, sh, zsh or dash is the host's, a read included.
        for tool_input in ({"cmd": "make", "shell": "/tmp/evil"}, {"cmd": "git status", "shell": "python3"},
                           {"command": ["/tmp/bash", "-lc", "make"]}, {"command": ["./zsh", "-c", "git status"]}):
            tool = "shell" if "command" in tool_input else "exec_command"
            self.assertIsNone(self.outcome("codex", (tool, tool_input)), tool_input)
        for tool_input in ({"cmd": "make", "shell": "/bin/zsh"}, {"cmd": "make", "shell": "bash", "login": True},
                           {"command": ["bash", "-lc", "make"]}, {"command": ["/usr/bin/env", "make"]},
                           {"command": ["make"]}):
            tool = "shell" if "command" in tool_input else "exec_command"
            expected = None if tool_input.get("command", [""])[0] == "/usr/bin/env" else ("allow", None)
            self.assertEqual(self.outcome("codex", (tool, tool_input)), expected, tool_input)

    def test_no_input_reaches_a_remote_shell_and_no_hidden_exit_passes(self):
        ident = self.granted(commands=["remote-run", "test"], machines=["build-1"])
        self.expect(lambda rt: self.shell(rt, "ssh build-1 make test | tail -5"), self.allow(ident, "remote-run"))
        self.expect(lambda rt: self.shell(rt, "python3 tools/test_x.py && ssh build-1 make test"),
                    self.allow(ident, "test, remote-run"))
        self.expect(lambda rt: self.shell(rt, "echo x &&\nssh build-1 make test"), self.allow(ident, "remote-run"))
        for command in ("echo git push | ssh build-1 sh", "cat tools/test_x.py | ssh build-1 bash",
                        "ssh build-1 sh < tools/test_x.py", "ssh build-1 sh 0<tools/test_x.py", "true & ssh build-1 sh",
                        # the shell continues a pipe across a newline
                        "echo git push |\nssh build-1 sh", "echo git push | \n ssh build-1 sh", "echo git push |\n\nssh build-1 sh"):
            self.expect(lambda rt, c=command: self.shell(rt, c), None)  # the remote shell would run that input
        for command, word in (("ssh build-1 git-push origin main", "git push"),
                              ("ssh build-1 /usr/lib/git-core/git-push origin main", "git push"),
                              ("ssh build-1 git-branch -D old", "git branch"), ("ssh build-1 hub push", "hub"),
                              ("ssh build-1 hub release create v1", "hub"), ("ssh build-1 aws s3 cp x s3://b/x", "aws s3 cp"),
                              ("ssh build-1 aws s3 sync . s3://b", "aws s3 sync"), ("ssh build-1 ftp example.invalid", "ftp"),
                              ("ssh build-1 git-http-push x", "git http-push"), ("ssh build-1 aws s3api put-object", "aws s3api"),
                              ("ssh build-1 gsutil cp a gs://b", "gsutil cp"), ("ssh build-1 lftp x", "lftp"),
                              ("ssh build-1 tftp x", "tftp"), ("ssh build-1 telnet x 25", "telnet"),
                              ("ssh build-1 python3 -m http.server", "http.server"),
                              ("ssh build-1 git-receive-pack x", "git receive-pack"),
                              ("ssh build-1 /usr/libexec/git-core/git-upload-pack x", "git upload-pack"),
                              ("ssh build-1 git-upload-archive x", "git upload-archive")):
            self.expect(lambda rt, c=command: self.shell(rt, c), ("deny", ddl_gate.EXIT_BEHIND_SSH.format(word)))

    def test_a_socket_redirect_or_a_sandbox_escape_gets_no_allow(self):
        ident = self.granted(commands=["build", "test"])
        for command in ("cat < /dev/tcp/127.0.0.1/9", "head -c1 < /dev/tcp/example.invalid/80",
                        "ls -la 0</dev/udp/127.0.0.1/53", "cat <'/dev/tcp/example.invalid/80'",
                        "python3 tools/test_x.py < /dev/tcp/example.invalid/80", "make 0</dev/udp/127.0.0.1/53"):
            self.expect(lambda rt, c=command: self.shell(rt, c), None)
        self.expect(lambda rt: self.shell(rt, "grep -n /dev/tcp/ notes.txt"), self.allow(ident, "read"))
        escapes = {"claude": [{"dangerouslyDisableSandbox": True}],
                   "codex": [{"sandbox_permissions": "require_escalated", "justification": "x"},
                             {"with_escalated_permissions": True}]}
        for runtime, fields in escapes.items():
            tool, key = SHELL[runtime]
            for extra in fields:
                for command in ("make", "git status", "python3 tools/test_x.py"):
                    with self.subTest(runtime=runtime, extra=extra, command=command):
                        self.assertIsNone(self.outcome(runtime, (tool, dict({key: command}, **extra))))
        self.assertEqual(self.outcome("codex", ("exec_command", {"cmd": "make", "sandbox_permissions": "use_default"})),
                         ("allow", None))
        for extra in ({"additional_permissions": {"network": True}}, {"additional_permissions": ["network"]}):
            for command in ("make", "git status"):
                self.assertIsNone(self.outcome("codex", ("exec_command", dict({"cmd": command}, **extra))), extra)
        self.assertEqual(self.outcome("codex", ("exec_command", {"cmd": "make", "additional_permissions": {}})),
                         ("allow", None))
        self.assertEqual(self.outcome("claude", ("Bash", {"command": "make", "dangerouslyDisableSandbox": False})),
                         self.allow(ident, "build"))

    def test_symlinks_tests_packages_and_jobs_stay_inside_their_bounds(self):
        ident = self.granted(commands=["build", "test", "check"])
        os.symlink(str(self.outside), str(self.root / "tools" / "outlink"))
        (self.outside / "evil.py").write_text("")
        (self.root / "tools" / "deep" / "test_d.py").write_text("")
        for command in ("cd tools && pytest outlink", "pytest tools/outlink", "pytest /tmp/x/test_a.py",
                        "python3 -m pytest tools/outlink/test_a.py::test", "python3 -m unittest tools.outlink.evil",
                        "python3 -m unittest antigravity", "python3 -m unittest idlelib.idle",
                        "python3 -m unittest discover tools/outlink", "python3 -m unittest discover -s tools/outlink",
                        "python3 -m unittest discover -s tools -t /", "python3 tools/outlink/test_a.py",
                        "bash -n tools/outlink/x.sh", "go test -run . all", "go test github.com/evil/pkg",
                        "go build tools/outlink", "go test -run -exec=x .", "make -j 999999999", "make -j257", "make -j 0",
                        "pytest -k -p tools"):
            self.expect(lambda rt, c=command: self.shell(rt, c), None)
        # A script's own argument may name the temporary directory, never a place outside it and the root.
        os.symlink(os.sep, str(self.root / "tools" / "homelink"))  # `/`: outside the root and every temporary directory
        for command in ("cd tools && python3 test_x.py homelink", "python3 tools/test_x.py tools/homelink",
                        "cd tools && python3 test_x.py --out=homelink"):
            self.expect(lambda rt, c=command: self.shell(rt, c), None)
        self.expect(lambda rt: self.shell(rt, "cd tools && python3 test_x.py deep"), self.allow(ident, "test"))
        for command, kind in (("python3 -m unittest tools.test_x", "test"), ("python3 -m unittest tools.deep.test_d.Case.test", "test"),
                              ("pytest tools/test_x.py::test_a", "test"), ("go build .", "build"), ("go test ./tools/...", "test"),
                              ("make -j 256 test", "test"), ("make -j8", "build")):
            self.expect(lambda rt, c=command: self.shell(rt, c), self.allow(ident, kind))

    def test_active_grants_form_a_union(self):
        first = self.granted(paths=["tools/**"], commands=["test"])
        second = self.granted("R-" + "b" * 16, paths=["skills/**"], commands=["build"], approved="2026-11-22T00:00:00.000Z")
        both = "{}, {}".format(first, second)
        self.expect(lambda rt: self.edit(rt, "skills/a.md"), self.allow(second, "edit"))
        self.assertEqual(self.outcome("codex", self.edit("codex", "tools/a.py", "skills/b.md")), ("allow", None))
        self.expect(lambda rt: self.shell(rt, "python3 tools/test_x.py && python3 tools/build.py"),
                    ("allow", ddl_gate.GRANT_ALLOW.format(both, "test, build")))
        self.expect(lambda rt: self.edit(rt, "docs/a.md"), ("deny", ddl_gate.OUTSIDE_PATHS.format("docs/a.md", both)))
        self.expect(lambda rt: self.shell(rt, "python3 tools/check_x.py"),
                    ("deny", ddl_gate.OUTSIDE_CLASS.format("check", both)))

    def corpus(self, runtime):
        """Calls a grant could answer for, inside and outside it."""
        return [self.edit(runtime, path) for path in ("tools/x.py", "design.md", ".ddl/notes.md")] + [
            self.shell(runtime, command) for command in (
                "git status", "python3 tools/test_x.py", "python3 tools/build.py", "ssh build-1 ls", "ssh x git push",
                'python3 "$HOME/.claude/hooks/ddl_gate.py" status', "git diff --check")]

    def test_no_grant_and_an_expired_grant_allow_nothing_and_deny_nothing_new(self):
        for runtime in ("claude", "codex"):
            bare = [self.outcome(runtime, call) for call in self.corpus(runtime)]
            with self.subTest(runtime=runtime, grant="none"):
                self.assertEqual(bare, [None] * len(bare))
        self.granted(days=-1, paths=["**"], commands=list(ddl_gate.GRANT_COMMANDS), machines=["build-1", "x"])
        self.granted("R-" + "c" * 16, paths=["skills/**"], commands=["test"], budget={"minutes": 0, "fixAttempts": 0})
        for runtime in ("claude", "codex"):
            with self.subTest(runtime=runtime, grant="expired or malformed"):
                self.assertEqual([self.outcome(runtime, call) for call in self.corpus(runtime)], [None] * 10)

    def test_a_pending_stop_keeps_its_decisions_with_a_grant_active(self):
        self.granted(paths=["**"], commands=list(ddl_gate.GRANT_COMMANDS), machines=["build-1"])
        for runtime in ("claude", "codex"):
            closed = fixture(runtime + "_closed_in_turn.jsonl")
            for call in self.corpus(runtime):
                with self.subTest(runtime=runtime, call=call):
                    held = self.outcome(runtime, call, closed)
                    data = payload(runtime, transcript=closed, session="bare", tool_name=call[0], tool_input=call[1])
                    bare = self.run_gate("pre-tool-use", runtime, data).stdout  # PROJECT has no grant
                    self.assertEqual(held, None if not bare else ("deny", json.loads(bare)["hookSpecificOutput"]
                                                                   ["permissionDecisionReason"]))
                    self.assertNotEqual(held and held[0], "allow")

    def test_an_unreadable_record_allows_nothing(self):
        self.granted(paths=["**"])
        for runtime in ("claude", "codex"):
            with self.subTest(runtime=runtime):
                self.assertEqual(self.outcome(runtime, self.edit(runtime, "tools/x.py"), False),
                                 ("warn", ddl_gate.UNREADABLE))
                self.assertIsNone(self.outcome(runtime, self.edit(runtime, "tools/x.py"), False))  # warned once

    def test_only_the_gate_writes_the_ledger_grant_or_not(self):
        for granted in (False, True):
            if granted:
                self.granted(paths=["**"], commands=list(ddl_gate.GRANT_COMMANDS))
            for path in (".ddl/events.jsonl", ".ddl/runs/N-0123456789ab/run.json", str(self.root / ".ddl/events.jsonl")):
                shown = os.path.join(".ddl", *pathlib.PurePosixPath(path.split(".ddl/", 1)[1]).parts)
                self.expect(lambda rt, p=path: self.edit(rt, p), ("deny", ddl_gate.LEDGER_REASON.format(shown)))
            for command in ("echo x >> .ddl/events.jsonl", "rm .ddl/events.jsonl", "cp /tmp/x .ddl/runs/N-0123456789ab/run.json",
                            "sed -i '' 1d .ddl/events.jsonl", "cd .ddl && truncate -s 0 events.jsonl",
                            "python3 tools/test_x.py >| .ddl/events.jsonl", "python3 tools/test_x.py <> .ddl/events.jsonl"):
                with self.subTest(command=command, granted=granted):
                    if command.startswith("cd "):  # the shell's own `cd` is followed no further: the host's
                        self.assertNotEqual(self.outcome("claude", self.shell("claude", command)), ("allow", None))
                        continue
                    self.expect(lambda rt, c=command: self.shell(rt, c), ("deny", ddl_gate.LEDGER_REASON.format(
                        os.path.join(".ddl", "runs", "N-0123456789ab", "run.json") if "run.json" in command
                        else os.path.join(".ddl", "events.jsonl"))))
            if ddl_gate.folds_case(os.path.realpath(str(self.root))):  # the macOS default: any spelling is the ledger
                for path in (".DDL/events.jsonl", ".Ddl/runs/N-0123456789ab/run.json"):
                    self.expect(lambda rt, p=path: self.edit(rt, p), ("deny", ddl_gate.LEDGER_REASON.format(path)))
                self.expect(lambda rt: self.shell(rt, "echo x > .DDL/EVENTS.jsonl"),
                            ("deny", ddl_gate.LEDGER_REASON.format(".DDL/EVENTS.jsonl")))
            read = None if not granted else self.allow("R-" + "a" * 16, "read")
            self.expect(lambda rt: self.shell(rt, "tail -n 3 .ddl/events.jsonl"), read)
            self.expect(lambda rt: self.shell(rt, "cp .ddl/events.jsonl /tmp/copy.jsonl"), None)
        # Under a pending STOP the STOP answers, as it always did.
        closed = lambda rt: fixture(rt + "_closed_in_turn.jsonl")
        self.expect(lambda rt: self.edit(rt, ".ddl/events.jsonl"), ("deny", ddl_gate.DENY_REASON), closed)

    def test_each_answer_writes_its_ledger_line(self):
        ident = self.granted()
        self.outcome("claude", self.edit("claude", "tools/x.py"))
        self.outcome("claude", self.shell("claude", "python3 tools/test_x.py && python3 tools/check_x.py"))
        self.outcome("claude", self.edit("claude", "docs/a.md"))
        self.outcome("codex", self.edit("codex", "tools/x.py"))
        rows = [{k: v for k, v in row.items() if k not in ("ts", "v", "session")}
                for row in events(self.root) if row["kind"] in ("allowed", "denied")]
        self.assertEqual(rows, [
            {"host": "claude", "kind": "allowed", "allow": "edit", "id": ident, "tool": "Edit", "toolUseId": "toolu_01"},
            {"host": "claude", "kind": "allowed", "allow": "test,check", "id": ident, "tool": "Bash",
             "toolUseId": "toolu_01"},
            {"host": "claude", "kind": "denied", "id": ident, "rule": "grant-paths", "tool": "Edit", "toolUseId": "toolu_01"},
            # Codex: its PreToolUse prints nothing and logs no allow; the PermissionRequest that allows does.
            {"host": "codex", "kind": "allowed", "allow": "edit", "id": ident, "tool": "apply_patch"}])

    def test_an_allowed_call_keeps_the_bookkeeping_of_a_call_that_passes(self):
        """The answer to a plan's question is read, and its grant recorded, also on a call a grant allows."""
        self.granted(paths=["tools/**"])
        for runtime in ("claude", "codex"):
            with self.subTest(runtime=runtime):
                session, prepared = runtime + "-next", self.prepared(runtime)
                self.assert_allowed(self.ask(runtime, prepared, session))
                if runtime == "codex":
                    self.assert_allowed(self.reply(prepared, 0, session))
                tool, tool_input = self.edit(runtime, "tools/x.py")
                out = self.tool(runtime, self.flow(runtime, prepared, "answered"), session, tool, tool_input).stdout
                if runtime == "claude":
                    self.assertEqual(json.loads(out)["hookSpecificOutput"]["permissionDecision"], "allow")
                else:
                    self.assertEqual(out, "")
                self.assertIsNotNone(self.record(prepared))
                self.assertEqual([row["kind"] for row in events(self.root, session=session)][-2:],
                                 ["granted", "allowed"] if runtime == "claude" else ["answered", "granted"])
                self.assertFalse(self.armed(session))

    def test_an_internal_error_allows_nothing(self):
        self.granted(paths=["**"])
        data = payload("claude", transcript=fixture("claude_open.jsonl"), cwd=self.cwd, tool_name="Edit",
                       tool_input={"file_path": "tools/x.py"})
        for event in ("pre-tool-use", "permission-request"):
            for name in ("edit_grant", "active_grants", "ledger_guard"):
                with self.subTest(event=event, failing=name), \
                        mock.patch.dict(os.environ, {"DDL_GATE_STATE_DIR": self.state, "DDL_GATE_GRANT_DIR": self.grants}), \
                        mock.patch.object(ddl_gate, name, side_effect=RuntimeError("probe")), \
                        mock.patch("sys.stdin", io.StringIO(json.dumps(data))), \
                        mock.patch("sys.stdout", new_callable=io.StringIO) as out:
                    self.assertEqual(ddl_gate.main([event, "--runtime", "claude"]), 0)
                    text = out.getvalue()
                    self.assertNotIn("allow\"", text.replace("allowed (fail-open)", ""))
                    if event == "pre-tool-use":
                        self.assertEqual(list(json.loads(text)), ["systemMessage"])
                    else:
                        self.assertEqual(text, "")


class GrantMatchTest(unittest.TestCase):
    """The pieces of the grant's answers, in process."""

    def test_path_globs(self):
        cases = [("tools/**", "tools/a.py", True), ("tools/**", "tools/a/b/c.py", True), ("tools/**", "toolsx/a", False),
                 ("**", "a/b", True), ("**/x.md", "x.md", True), ("**/x.md", "a/b/x.md", True), ("a/**/b", "a/b", True),
                 ("a/**/b", "a/x/y/b", True), ("skills/*.md", "skills/a.md", True), ("skills/*.md", "skills/d/a.md", False),
                 ("t?st/*", "test/x", True), ("t?st/*", "toast/x", False), ("a.b", "aXb", False), ("[ab]", "a", False),
                 ("design.md", "design.md", True)]
        for glob, path, expected in cases:
            with self.subTest(glob=glob, path=path):
                self.assertEqual(ddl_gate.glob_matches(glob, path.split("/")), expected)

    def test_exit_words(self):
        for text, word in (("git push origin main", "git push"), ("cd w && /usr/bin/git commit -m x", "git commit"),
                           ("git checkout -B x", "git checkout"), ("git switch -C y", "git switch"),
                           ("git branch -f main HEAD~1", "git branch"), ("echo $(scp a b:)", "scp"),
                           ("curl -T f https://x", "upload -T"), ("curl -sSfd x https://x", "upload -sSfd"),
                           ("curl --request=PUT https://x", "method --request=PUT"), ("wget --post-data=a https://x", "upload --post-data=a"),
                           ("twine upload dist/x", "twine upload"), ("nc -l 80", "nc"), ("glab mr create", "glab"),
                           ("git-push origin main", "git push"), ("/usr/lib/git-core/git-commit -m x", "git commit"),
                           ("git-branch -D old", "git branch"), ("hub release create v1", "hub"),
                           ("aws s3 cp x s3://b/x", "aws s3 cp"), ("aws s3 sync . s3://b", "aws s3 sync"),
                           ("aws s3 mv a s3://b/a", "aws s3 mv"), ("ftp example.invalid", "ftp"),
                           ("git-http-push x", "git http-push"), ("aws s3api put-object", "aws s3api"),
                           ("gsutil rsync a gs://b", "rsync"), ("gsutil mv a gs://b", "gsutil mv"), ("lftp x", "lftp"),
                           ("tftp x", "tftp"), ("telnet x 25", "telnet"), ("python3 -m http.server 8000", "http.server"),
                           ("git-receive-pack x", "git receive-pack"), ("/usr/lib/git-core/git-upload-pack x", "git upload-pack"),
                           ("git-upload-archive x", "git upload-archive")):
            with self.subTest(text=text):
                self.assertEqual(ddl_gate.exit_word(text), word)
        for text in ("git status", "git log --oneline", "make test", "curl -s https://x", "curl -X GET https://x",
                     "git branch --show-current", "python3 run.py --commit-message x", "echo push", "aws s3 ls s3://b",
                     "git-log --oneline", "aws ec2 describe-instances", "gsutil ls gs://b"):
            with self.subTest(text=text):
                self.assertIsNone(ddl_gate.exit_word(text))

    def test_validation_commands_are_read_from_the_validation_section_only(self):
        root = pathlib.Path(tempfile.mkdtemp(prefix="ddl-validation-"))
        self.addCleanup(shutil.rmtree, str(root), True)
        (root / "design.md").write_text(
            "## Scopes\n\n```\n# V0 not here\nrm -rf /\n```\n\n## Validation\n\nText.\n\n```bash\n# V1 a\npython3 a.py\n"
            "# expected: OK\n\n# V2 b\nx &&\n  y\n# note\nnot a command\n```\n\n## Next\n\n```\n# V3 c\nz\n```\n")
        project = {"source": str(root / "AGENTS.md")}
        self.assertEqual(ddl_gate.validation_commands(project, str(root)), {"python3 a.py", "x &&\ny"})

    def test_class_forms(self):
        gate = {"/gate/ddl_gate.py"}
        cases = {"python3 tools/build.py --x": (("build",), ["--x"], ["tools/build.py"], True, []),
                 "python3 -u -IB x_test.py": (("test",), [], ["x_test.py"], True, []),
                 "python3 /gate/ddl_gate.py snapshot --item a --git-dir .git": (("snapshot",), [], [".git"], False, []),
                 "python3 /gate/ddl_gate.py status": ("gate", [], [], False, []),
                 "make test all -j 2": (("test", "build"), [], [], True, []), "make lint": (("check",), [], [], True, []),
                 "bash -n a.sh": (("check",), [], ["a.sh"], True, []),
                 "go test -run X -count=3 ./...": (("test",), ["X", "3"], ["./..."], True, []),
                 "cargo test -p core -- name": (("test",), ["core", "name"], [], True, []),
                 "python3 -m unittest discover -s tools -t .": (("test",), [], ["tools", "."], True, []),
                 "python3 -m unittest -k fast tools.test_x tools/test_y.py": (("test",), ["fast"], ["tools/test_y.py"], True,
                                                                              ["tools.test_x"]),
                 "pytest -k slow a/test_b.py::test_c": (("test",), ["slow"], ["a/test_b.py"], True, []),
                 "python3 tools/ddl_gate.py status": None, "python3 -m pip install x": None,
                 "python3 -X dev tools/test_a.py": None, "git diff --check --output=x": None,
                 "python4 tools/test_a.py": None, "make test install": None, "npm run deploy": None,
                 "bash -n +n x.sh": None, "bash -n -c x": None, "go test -exec x .": None, "cargo build x": None,
                 "pytest -p plugin": None, "make -j": None, "python3 -m unittest -b": None, "go test all": None,
                 "go build example.com/x": None, "make -j 300": None, "pytest -k -x": None}
        for command, expected in cases.items():
            with self.subTest(command=command):
                self.assertEqual(ddl_gate.segment_class(shlex.split(command), gate.__contains__), expected)

    def test_a_word_that_starts_with_equals_is_not_literal(self):
        for command in ("ls =python3", "=ls", "cat =x", "service svc --prompt-file =python3", "echo a==b", "x &&=ls",
                        "a;=b", "a|=b", "echo x\n=ls", "make X==ls", "echo\t=x"):
            with self.subTest(command=command):
                self.assertFalse(ddl_gate.literal_shell(command))
                self.assertFalse(ddl_gate.shell_is_read_only(command)[0])
        for command in ("make X=1", "python3 run.py --out=x", "git log --format=%H", "echo '=x'", 'echo "=x"', "echo \\=x",
                        "a=b c=d make"):
            with self.subTest(command=command):
                self.assertTrue(ddl_gate.literal_shell(command))

    def test_a_remote_command_is_literal_words_after_the_machine(self):
        for command, expected in (("ssh -T -n box make test", ("box", ["make", "test"])), ("ssh box", None),
                                  ("ssh box -oProxyCommand=x true", None), ("ssh -p 22 box ls", None),
                                  ("ssh -o ConnectTimeout=5 box ls", ("box", ["ls"]))):
            with self.subTest(command=command):
                self.assertEqual(ddl_gate.ssh_form(shlex.split(command)), expected)


RESOURCES = FIXTURES / "resources_valid.toml"  # generic names: desk, build-1, gpu-1, batch-1, svc, svc-paid
GATE_CALL = "python3 " + shlex.quote(GATE)
# A compute resource that ssh reaches and that takes code: the start of a valid table for one problem more.
BOX = '[box]\nroles = ["compute"]\nreach = "ssh:box"\ndata = ["code"]\n'


def write_table(config, text=None):
    """The resource table at its place under the XDG_CONFIG_HOME `config`: the fixture's text, or `text`."""
    path = pathlib.Path(config) / "ddl" / "resources.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(RESOURCES.read_text(encoding="utf-8") if text is None else text, encoding="utf-8")
    return path


class ResourceTableTest(unittest.TestCase):
    """read_resource_table, the one reader of the user's resource table: its place, the format the personal
    environment's reader enforces alike, and its problems, which name a line, or a resource and a field, never a
    value."""

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="ddl-resources-"))
        self.addCleanup(shutil.rmtree, str(self.tmp), True)
        self.env = {"XDG_CONFIG_HOME": str(self.tmp / "config"), "HOME": str(self.tmp / "home")}

    def read(self, text):
        write_table(self.env["XDG_CONFIG_HOME"], text)
        return ddl_gate.read_resource_table(self.env)

    def test_the_place_is_xdg_config_home_else_the_homes_config(self):
        home, default = str(self.tmp / "home"), str(self.tmp / "home" / ".config" / "ddl" / "resources.toml")
        for given, expected in ((str(self.tmp / "x"), str(self.tmp / "x" / "ddl" / "resources.toml")),
                                ("", default), ("relative/config", default), ("./config", default), (None, default)):
            with self.subTest(xdg=given):
                env = {"HOME": home} if given is None else {"HOME": home, "XDG_CONFIG_HOME": given}
                self.assertEqual(ddl_gate.resource_table_path(env), expected)
        self.assertEqual(ddl_gate.resource_table_path(), os.path.join(CONFIG, "ddl", "resources.toml"))
        write_table(os.path.join(home, ".config"))
        table, error = ddl_gate.read_resource_table({"HOME": home, "XDG_CONFIG_HOME": "relative"})
        self.assertEqual((error, list(table)[:2]), (None, ["desk", "build-1"]))
        self.assertEqual(ddl_gate.read_resource_table({"HOME": home, "XDG_CONFIG_HOME": str(self.tmp / "none")}), ({}, None))

    def test_a_missing_file_is_no_table_and_an_unreadable_one_a_problem(self):
        self.assertEqual(ddl_gate.read_resource_table(self.env), ({}, None))
        (self.tmp / "config").write_text("")  # a file where a directory on the way would be
        self.assertEqual(ddl_gate.read_resource_table(self.env), ({}, None))
        (self.tmp / "config").unlink()
        path = write_table(self.env["XDG_CONFIG_HOME"])
        path.unlink()
        os.symlink(str(self.tmp / "gone.toml"), str(path))  # a link whose file is gone is not "no table"
        unreadable = ({}, "the resource table cannot be read")
        self.assertEqual(ddl_gate.read_resource_table(self.env), unreadable)
        path.unlink()
        path.mkdir()
        self.assertEqual(ddl_gate.read_resource_table(self.env), ({}, "the resource table is not a regular file"))
        path.rmdir()
        path.write_bytes(b'[box]\nnote = "\xff"\n')
        self.assertEqual(ddl_gate.read_resource_table(self.env), unreadable)
        if hasattr(os, "geteuid") and os.geteuid() != 0:
            write_table(self.env["XDG_CONFIG_HOME"])
            path.chmod(0)
            self.assertEqual(ddl_gate.read_resource_table(self.env), unreadable)
        # A linked file is read through its link, as the personal environment's install places it.
        path.chmod(0o600)
        path.unlink()
        os.symlink(str(RESOURCES), str(path))
        self.assertIsNone(ddl_gate.read_resource_table(self.env)[1])

    def test_only_a_regular_file_of_at_most_64_kib_is_read(self):
        path = write_table(self.env["XDG_CONFIG_HOME"], "")
        not_regular = ({}, "the resource table is not a regular file")
        path.unlink()
        os.mkfifo(str(path))  # opening a FIFO would wait for a writer: it is never opened
        code = ("import sys; sys.dont_write_bytecode = True; sys.path.insert(0, {!r}); import ddl_gate_core as g; "
                "print(repr(g.read_resource_table({!r})))").format(str(TOOLS), self.env)
        proc = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.stdout.strip(), repr(not_regular), proc.stderr)
        path.unlink()
        if os.path.exists("/dev/zero"):  # a device, linked: never read
            os.symlink("/dev/zero", str(path))
            self.assertEqual(ddl_gate.read_resource_table(self.env), not_regular)
            path.unlink()
        limit = 64 * 1024
        padding = limit - len(BOX.encode("utf-8")) - 2
        self.assertEqual(self.read(BOX + "#" + "x" * padding + "\n")[1], None)  # exactly 64 KiB
        self.assertEqual(len(path.read_bytes()), limit)
        self.assertEqual(self.read(BOX + "#" + "x" * (padding + 1) + "\n"), ({}, "the resource table is larger than 64 KiB"))
        self.assertEqual(self.read(BOX + "# " + "日本語" * 30000 + "\n"), ({}, "the resource table is larger than 64 KiB"))

    def test_lines_end_at_newline_and_no_other_break_is_taken(self):
        self.assertIsNone(self.read(BOX.replace("\n", "\r\n"))[1])
        for char in ("\r", "\x0b", "\x0c", "\x1c", "\x1d", "\x1e", "\x85", "\u2028", "\u2029"):
            for text, line in ((BOX + "# a comment" + char + 'confirm = "each run"\n', 5),
                               (BOX + 'note = "a' + char + 'b"\n', 5), (BOX.replace("\n", char), 1),
                               ('[box]' + char + '\n', 1)):
                if text == "[box]\r\n":
                    continue  # \r\n ends a line
                with self.subTest(char=repr(char), text=text):
                    self.assertEqual(self.read(text), ({}, "line {}: a line break other than \\n".format(line)))

    def test_the_fixture_reads_as_written(self):
        table, error = self.read(None)
        self.assertIsNone(error)
        self.assertEqual(list(table), ["desk", "build-1", "gpu-1", "batch-1", "svc", "svc-paid", "shared-1", "shared-2",
                                       "archive-1"])
        self.assertEqual(table["desk"], {"roles": ["host"], "hostname": "desk", "reach": "ssh:desk"})
        self.assertEqual(table["build-1"], {"roles": ["compute"], "reach": "ssh:build-1", "slots": 4,
                                            "labels": ["linux", "cpu"], "data": ["code"],
                                            "note": "builds and tests, 8/16 cores"})
        self.assertEqual(table["gpu-1"]["needs"], ["cuda"])
        self.assertEqual((table["batch-1"]["confirm"], table["svc"]["reach"]), ("each run", "codex:example"))

    def test_the_format_is_the_strict_subset(self):
        cases = [("\ufeff" + BOX, {}), (BOX.replace("\n", "\r\n"), {}), (BOX + "\n# a comment\n   \n", {}),
                 (BOX.replace("[box]", "[ box ]  # the header's comment"), {}),
                 (BOX + 'labels = [ "a" , "b", ]  # a trailing comma\n', {"labels": ["a", "b"]}),
                 (BOX + "labels = []\n", {"labels": []}), (BOX + "slots = 12 # twelve\n", {"slots": 12}),
                 (BOX + 'note = "say \\"hi\\" \\\\ # not a comment"\n', {"note": 'say "hi" \\ # not a comment'}),
                 (BOX + 'note=""\n', {"note": ""}), (BOX + 'note = "日本語の注記"\n', {"note": "日本語の注記"}),
                 (BOX.replace('["compute"]', '["host", "compute"]').replace("data", 'hostname = "box"\ndata'),
                  {"roles": ["host", "compute"], "hostname": "box"}),
                 (BOX.replace('"ssh:box"', '"codex:plug.in-1"'), {"reach": "codex:plug.in-1"}),
                 (BOX.replace('"ssh:box"', '"ssh:Box.lan_2"'), {"reach": "ssh:Box.lan_2"})]
        for text, fields in cases:
            with self.subTest(text=text):
                table, error = self.read(text)
                self.assertIsNone(error)
                expected = dict({"roles": ["compute"], "reach": "ssh:box", "data": ["code"]}, **fields)
                self.assertEqual(table, {"box": expected})

    def test_each_problem_names_a_line_or_a_resource_and_a_field(self):
        value = 'a value that is not a double-quoted string, a non-negative integer or a one-line list of strings'
        cases = [('roles = ["host"]\n', "line 1: key = value before the first [name] header"),
                 ("[Box]\n", "line 1: a resource name that is not lowercase letters, digits and hyphens"),
                 ("[a_b]\n", "line 1: a resource name that is not lowercase letters, digits and hyphens"),
                 ("[[box]]\n", "line 1: a table header that is not [name]"), ("[box] x\n", "line 1: a table header that is not [name]"),
                 ("[]\n", "line 1: a resource name that is not lowercase letters, digits and hyphens"),
                 ("[" + "a" * 40 + "]\n", "line 1: a resource name that looks like a token"),
                 (BOX + "[box]\n", "line 5: a resource declared twice (first on line 1)"),
                 (BOX + "slots = 01\n", "line 5: an integer with a leading zero"),
                 (BOX + "slots = -1\n", "line 5: " + value), (BOX + "slots = 1.5\n", "line 5: " + value),
                 (BOX + "note = true\n", "line 5: " + value), (BOX + "note = 'x'\n", "line 5: " + value),
                 (BOX + 'note = """x"""\n', "line 5: a multi-line string"),
                 (BOX + 'note = "x\\n"\n', "line 5: an escape other than \\\" or \\\\ in a string"),
                 (BOX + 'note = "x\tz"\n', "line 5: a control character in a string"),
                 (BOX + 'note = "x\n', "line 5: a string that does not close on its line"),
                 (BOX + 'labels = ["a" "b"]\n', "line 5: a list item followed by something other than a comma"),
                 (BOX + 'labels = ["a"\n', "line 5: a list that does not close on its line"),
                 (BOX + "labels = [1]\n", "line 5: a list item that is not a double-quoted string"),
                 (BOX + 'note = "a" b\n', "line 5: text after the value"), (BOX + "note =\n", "line 5: a key without a value"),
                 (BOX + "note = # c\n", "line 5: a key without a value"),
                 (BOX + "note\n", "line 5: a line that is neither a [name] header nor key = value"),
                 (BOX + 'no te = "x"\n', "line 5: a key that is not a bare word"),
                 (BOX + 'note = "x"\nnote = "y"\n', "line 6: a key given twice in one resource"),
                 (BOX + "port = 22\n", "resource box: unknown key port"),
                 (BOX + "p" * 30 + " = 1\n", "resource box: unknown key on line 5"),
                 ('[box]\nreach = "ssh:box"\ndata = ["code"]\n', "resource box: field roles is required"),
                 (BOX.replace('["compute"]', '["gpu"]'), "resource box: field roles must list host, compute or both"),
                 (BOX.replace('["compute"]', '[]'), "resource box: field roles must list host, compute or both"),
                 (BOX.replace('["compute"]', '["compute", "compute"]'), "resource box: field roles must list host, compute or both"),
                 (BOX.replace('"ssh:box"', '"rsync:box"'), "resource box: field reach must be ssh:<alias> or codex:<plugin>"),
                 (BOX.replace('"ssh:box"', '"codex:Plug"'), "resource box: field reach must be ssh:<alias> or codex:<plugin>"),
                 (BOX.replace('"ssh:box"', '["ssh:box"]'), "resource box: field reach must be ssh:<alias> or codex:<plugin>"),
                 ('[box]\nroles = ["compute"]\ndata = ["code"]\n', "resource box: field reach is required for compute"),
                 ('[box]\nroles = ["compute"]\nreach = "ssh:box"\n', "resource box: field data is required for compute"),
                 (BOX + "slots = 0\n", "resource box: field slots must be an integer of at least 1"),
                 (BOX + 'slots = "4"\n', "resource box: field slots must be an integer of at least 1"),
                 (BOX.replace('["code"]', '["code", "secrets"]'),
                  "resource box: field data must list code, personal, business or several of them"),
                 (BOX.replace('["code"]', '[]'), "resource box: field data must list code, personal, business or several of them"),
                 (BOX.replace('["code"]', '["code", "code"]'),
                  "resource box: field data must list code, personal, business or several of them"),
                 (BOX + 'confirm = "always"\n', 'resource box: field confirm must be "each run"'),
                 (BOX + 'labels = ["a b"]\n', "resource box: field labels must be a list of words (letters, digits, . _ + -)"),
                 (BOX + 'needs = "cuda"\n', "resource box: field needs must be a list of words (letters, digits, . _ + -)"),
                 (BOX + "note = 4\n", "resource box: field note must be a string"),
                 (BOX + 'hostname = "box"\n', "resource box: field hostname is for a host"),
                 ('[desk]\nroles = ["host"]\n', "resource desk: field hostname is required for a host"),
                 ('[desk]\nroles = ["host"]\nhostname = "desk.local"\n',
                  "resource desk: field hostname must be a short host name (letters, digits, hyphens)"),
                 ('[desk]\nroles = ["host"]\nhostname = "desk"\nreach = "codex:x"\n',
                  "resource desk: field reach of a host must be ssh:<alias>"),
                 ('[desk]\nroles = ["host"]\nhostname = "desk"\nslots = 2\n', "resource desk: field slots is for compute"),
                 ('[desk]\nroles = ["host"]\nhostname = "desk"\ndata = ["code"]\n', "resource desk: field data is for compute"),
                 ('[desk]\nroles = ["host"]\nhostname = "desk"\nconfirm = "each run"\n',
                  "resource desk: field confirm is for compute"),
                 ('[a]\nroles = ["host"]\nhostname = "Desk"\n[b]\nroles = ["host"]\nhostname = "desk"\n',
                  "resource b: field hostname is also declared by a"),
                 ("", "the resource table declares no resource"), ("# only a comment\n\n", "the resource table declares no resource"),
                 ("[box]\nnote = 01\nport = 1\n", "line 2: an integer with a leading zero"),
                 ('[box]\nroles = ["gpu"]\nport = 1\n', "resource box: unknown key port (and 1 more)")]
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(self.read(text), ({}, expected))

    def test_a_secret_shaped_value_is_refused_and_never_printed(self):
        for field, secret, kind in (("note", "at 192.0.2.10", "an IP address"), ("note", "fe80::1", "an IP address"),
                                    ("note", "2001:db8::7", "an IP address"), ("reach", "ssh:user@build", "user@host"),
                                    ("note", "see https://example.invalid", "a URL"), ("reach", "ssh:box:2222", "a port"),
                                    ("note", "keys in ~/.ssh/", "a path"), ("note", "/srv/data", "a path"),
                                    ("note", "x:/srv", "a path"), ("note", "sk-abc", "a key"), ("note", "ghp_x", "a key"),
                                    ("note", "-----BEGIN OPENSSH", "a key"), ("labels", "Q" * 40, "a token"),
                                    ("hostname", "a" * 33, "a token")):
            with self.subTest(field=field, kind=kind):
                text = BOX + ("{} = [{}]\n" if field == "labels" else '{} = "{}"\n').format(
                    field, json.dumps(secret) if field == "labels" else secret)
                if field == "reach":
                    text = BOX.replace('"ssh:box"', json.dumps(secret))
                table, error = self.read(text)
                self.assertEqual(table, {})
                self.assertTrue(error.startswith("resource box: field {} looks like {} (the value is not printed)".format(
                    field, kind)), error)
                self.assertNotIn(secret, error)
        for plain in ("8/16 cores", "and/or", "a:b", "1.2.3", "ssh:box"):
            with self.subTest(plain=plain):
                self.assertIsNone(self.read(BOX + 'note = "{}"\n'.format(plain))[1])

    def test_the_one_reader_keeps_its_signature(self):
        import inspect
        parameters = list(inspect.signature(ddl_gate.read_resource_table).parameters.values())
        self.assertEqual([(p.name, p.default) for p in parameters], [("env", None)])
        with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": self.env["XDG_CONFIG_HOME"]}):
            write_table(self.env["XDG_CONFIG_HOME"])
            self.assertIn("svc", ddl_gate.read_resource_table()[0])  # the process's environment by default

    def test_a_preparation_reads_the_table_only_for_machines_or_handed_over_data(self):
        with mock.patch.object(ddl_gate, "read_resource_table", side_effect=AssertionError("read")):
            self.assertIsNone(ddl_gate.grant_resources(grant()))
        with mock.patch.object(ddl_gate, "read_resource_table", return_value=({}, None)) as reader:
            self.assertIsNone(ddl_gate.grant_resources(grant(machines=["anything"], handover=["anything else"])))
            self.assertIsNone(ddl_gate.grant_resources(grant(handover=["x"])))
            self.assertEqual(reader.call_count, 2)


class ResourcePreparationTest(GateTest):
    """prepare-report with a grant that names machines or handed-over data, on both hosts: checked against the
    table when there is one and refused before anything is written; free names without a table."""

    def setUp(self):
        super().setUp()
        self.config = os.path.join(self.tmp, "config")
        patcher = mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": self.config})
        patcher.start()
        self.addCleanup(patcher.stop)

    def prepare(self, runtime, **changes):
        return self.subcommand(["prepare-report", "--runtime", runtime],
                               dict(PrepareReportTest.BASE, language="en", grant=grant(**changes)))

    def prepared(self, **changes):
        for runtime in ("claude", "codex"):
            with self.subTest(runtime=runtime, grant=changes):
                proc = self.prepare(runtime, **changes)
                self.assertEqual((proc.returncode, proc.stderr), (0, ""))
                self.assertTrue(json.loads(proc.stdout)["reportId"].startswith("R-"))

    def refused(self, reason, **changes):
        for runtime in ("claude", "codex"):
            with self.subTest(runtime=runtime, grant=changes):
                before = sorted(pathlib.Path(self.state).rglob("report.*"))
                proc = self.prepare(runtime, **changes)
                self.assertEqual((proc.returncode, proc.stdout, proc.stderr), (2, "", "DDL STOP: " + reason + "\n"))
                self.assertEqual(sorted(pathlib.Path(self.state).rglob("report.*")), before)  # nothing was written

    def test_without_a_table_the_names_stay_free(self):
        self.prepared(commands=["remote-run"], machines=["anything-1", "Build.Box"], handover=["snapshots", "logs"])

    def test_a_grant_names_declared_compute_resources_and_the_data_they_take(self):
        write_table(self.config)
        self.prepared(commands=["remote-run"], machines=["build-1"], handover=["code"])
        self.prepared(machines=["gpu-1", "build-1", "svc"], handover=["code"])
        self.prepared(machines=["gpu-1"], handover=["code", "personal"])
        self.prepared(machines=["batch-1", "svc-paid"])  # a resource with confirm may be named; each run still asks
        self.prepared()
        self.refused("grant.machines: `nope` is not declared in the resource table.", machines=["build-1", "nope"])
        self.refused("grant.machines: `gpu-alias` is not declared in the resource table.", machines=["gpu-alias"])
        self.refused("grant.machines: `desk` is not a compute resource in the resource table.", machines=["desk"])
        self.refused("grant.handover: `build-1` does not take `personal`.", machines=["gpu-1", "build-1"],
                     handover=["code", "personal"])
        self.refused("grant.handover: `svc` does not take `personal`.", machines=["svc"], handover=["personal"])
        for handover in (["snapshots"], ["code", "keys"], ["Code"]):
            self.refused("grant.handover names data kinds: code, personal, business.", machines=["build-1"],
                         handover=handover)
            self.refused("grant.handover names data kinds: code, personal, business.", handover=handover)

    def test_an_invalid_table_refuses_a_grant_that_names_machines(self):
        write_table(self.config, BOX + 'note = "at 192.0.2.10"\n')
        reason = ("grant.machines: the resource table is invalid (resource box: field note looks like an IP address "
                  "(the value is not printed)); correct it before a grant names machines.")
        self.refused(reason, machines=["box"])
        self.refused(reason, machines=["box"], handover=["code"])
        self.prepared()
        self.prepared(handover=["code"])  # no machine is named: nothing is handed to anyone
        write_table(self.config, "")
        self.refused("grant.machines: the resource table is invalid (the resource table declares no resource); "
                     "correct it before a grant names machines.", machines=["build-1"])


class ResourceAnswerTest(GrantAnswers):
    """The hook's answers for the resources a grant names, on both hosts: ssh resolves a granted machine through the
    table, a resource with `confirm` is left to the host, a service is never reached by ssh, and the gate's remote,
    measure and service are class remote-run for the resource they name. Every N3 rule still holds."""

    def setUp(self):
        super().setUp()
        self.config = os.path.join(self.tmp, "config")
        patcher = mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": self.config})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.prompt = pathlib.Path(self.tmp) / "prompt.md"  # a temporary file, outside the root
        self.prompt.write_text("item\n")

    def gate(self, rest):
        return GATE_CALL + " " + rest

    def each(self, commands, expected):
        for command in commands:
            self.expect(lambda rt, c=command: self.shell(rt, c), expected)

    def test_without_a_table_a_granted_machine_is_its_own_alias(self):
        ident = self.granted(commands=["remote-run"], machines=["build-1", "gpu-1"], handover=["code"])
        self.each(["ssh build-1 make test", "ssh gpu-1 make test", self.gate("measure gpu-1"),
                   self.gate("remote build-1 -- make test")], self.allow(ident, "remote-run"))
        self.expect(lambda rt: self.shell(rt, "ssh gpu-alias make"),
                    ("deny", ddl_gate.OUTSIDE_MACHINE.format("gpu-alias", ident)))
        self.each([self.gate("service gpu-1 --prompt-file tools/p.md"), self.gate("measure other")], None)

    def test_ssh_reaches_a_granted_resource_by_its_alias(self):
        write_table(self.config)
        ident = self.granted(commands=["remote-run"], machines=["build-1", "gpu-1", "batch-1", "svc", "svc-paid", "desk"])
        self.each(["ssh build-1 make test", "ssh -o BatchMode=yes -o ConnectTimeout=5 gpu-alias make test",
                   "ssh -T gpu-alias nvidia-smi", "ssh gpu-alias make test | tail -5"], self.allow(ident, "remote-run"))
        for command, reason in (("ssh gpu-1 make test", ddl_gate.NAME_FOR_ALIAS.format("gpu-1")),
                                ("ssh svc ls", ddl_gate.SERVICE_BY_SSH.format("svc")),
                                ("ssh desk ls", ddl_gate.NOT_COMPUTE.format("desk")),
                                ("ssh other-host ls", ddl_gate.OUTSIDE_MACHINE.format("other-host", ident)),
                                ("ssh gpu-alias git push origin main", ddl_gate.EXIT_BEHIND_SSH.format("git push")),
                                ("ssh batch-login git push origin main", ddl_gate.EXIT_BEHIND_SSH.format("git push")),
                                ("ssh batch-1 scp x y:", ddl_gate.EXIT_BEHIND_SSH.format("scp"))):
            self.expect(lambda rt, c=command: self.shell(rt, c), ("deny", reason))
        # A resource that asks each run is the host's, by its alias or its name; so is every N3 refusal.
        self.each(["ssh batch-login make test", "ssh batch-1 make test", "ssh svc-paid ls",
                   "ssh -p 22 gpu-alias ls", "ssh gpu-alias", "ssh gpu-alias -oProxyCommand=x true",
                   "ssh gpu-alias 'make test'", "ssh gpu-alias make > /dev/null", "echo git push | ssh gpu-alias sh",
                   "ssh gpu-alias sh < tools/test_x.py"], None)
        for workdir in (str(self.outside), ".claude"):
            self.assertIsNone(self.outcome("codex", ("exec_command", {"cmd": "ssh gpu-alias make", "workdir": workdir})))

    def test_only_a_granted_resource_is_reached(self):
        write_table(self.config)
        ident = self.granted(commands=["remote-run"], machines=["gpu-1", "retired"])  # `retired` left the table
        self.expect(lambda rt: self.shell(rt, "ssh gpu-alias make"), self.allow(ident, "remote-run"))
        for machine in ("build-1", "retired"):
            self.expect(lambda rt, m=machine: self.shell(rt, "ssh {} make".format(m)),
                        ("deny", ddl_gate.OUTSIDE_MACHINE.format(machine, ident)))
        self.each([self.gate("measure build-1"), self.gate("measure retired")], None)
        other = self.granted("R-" + "b" * 16, commands=["test"], machines=["build-1"], approved="2026-11-21T00:00:00.000Z")
        self.expect(lambda rt: self.shell(rt, "ssh build-1 make"), self.allow(ident, "remote-run"))  # a union
        self.expect(lambda rt: self.shell(rt, "python3 tools/test_x.py && ssh build-1 make"),
                    ("allow", ddl_gate.GRANT_ALLOW.format("{}, {}".format(other, ident), "test, remote-run")))

    def test_an_invalid_table_covers_nothing_and_still_refuses_an_exit(self):
        write_table(self.config, '[build-1]\nroles = ["compute"]\nreach = "ssh:build-1"\n')
        self.granted(commands=["remote-run"], machines=["build-1"])
        self.each(["ssh build-1 make test", self.gate("measure build-1"), self.gate("remote build-1 -- make")], None)
        self.expect(lambda rt: self.shell(rt, "ssh build-1 git push"),
                    ("deny", ddl_gate.EXIT_BEHIND_SSH.format("git push")))

    def test_the_gates_resource_subcommands_are_remote_run_for_the_resource_they_name(self):
        write_table(self.config)
        ident = self.granted(commands=["remote-run", "test"], machines=["build-1", "gpu-1", "batch-1", "svc", "svc-paid"],
                             handover=["code"])
        snapshot = "refs/ddl/snapshots/N-0123456789ab/20261124T000000.5Z-I1"
        self.each([self.gate("measure build-1"), self.gate("measure gpu-1"), "python3 -I {} measure gpu-1".format(shlex.quote(GATE)),
                   self.gate("remote gpu-1 -- python3 tools/test_protocol.py"),
                   self.gate("remote build-1 --run N-0123456789ab --item I1 --snapshot {} --artifacts 'dist/*.whl' "
                             "out/report.txt --keep --timeout 600 -- make test".format(snapshot)),
                   self.gate("remote build-1 --artifacts=out.txt --artifacts 'logs/*.log' -- make -j 4 test"),
                   self.gate("remote build-1 --timeout=1800 -- python3 -m pytest -q --maxfail=1"),
                   self.gate("service svc --prompt-file tools/prompt.md --schema tools/schema.json"),
                   self.gate("service svc --prompt-file=" + shlex.quote(str(self.prompt))),  # a quoted literal path
                   self.gate("service svc --prompt-file " + shlex.quote(str(self.prompt))),
                   "cd tools && " + self.gate("service svc --prompt-file prompt.md")],
                  self.allow(ident, "remote-run"))
        self.expect(lambda rt: self.shell(rt, "python3 tools/test_x.py && " + self.gate("measure build-1")),
                    self.allow(ident, "test, remote-run"))
        for command, word in (("remote gpu-1 -- git push origin main", "git push"), ("remote gpu-1 -- ssh other ls", "ssh"),
                              ("remote gpu-1 -- curl -T f https://example.invalid", "upload -T"),
                              ("remote batch-1 -- git push", "git push")):
            self.expect(lambda rt, c=command: self.shell(rt, self.gate(c)),
                        ("deny", ddl_gate.EXIT_BEHIND_SSH.format(word)))
        nothing = [
            # a resource the gate does not cover for that word
            "measure batch-1", "measure svc", "measure desk", "measure nope", "measure gpu-alias", "remote batch-1 -- make",
            "remote svc -- make", "remote gpu-alias -- make", "service svc-paid --prompt-file tools/p.md",
            "service build-1 --prompt-file tools/p.md", "service nope --prompt-file tools/p.md",
            # a form tools/ddl_run.py does not read, or one the gate cannot check
            "measure", "measure build-1 extra", "measure build-1 --keep", "measure Build_1!", "remote gpu-1 make test",
            "remote gpu-1 --", "remote gpu-1 --bogus -- make", "remote gpu-1 --keep --keep -- make",
            "remote gpu-1 --artifacts -- make", "remote gpu-1 --artifacts ../up -- make", "remote gpu-1 --artifacts /abs -- make",
            "remote gpu-1 --artifacts 'a b' -- make", "remote gpu-1 --run N-1 -- make", "remote gpu-1 --item ../x -- make",
            "remote gpu-1 --snapshot HEAD:refs/heads/main -- make", "remote gpu-1 --timeout 0 -- make",
            "remote gpu-1 --timeout -5 -- make", "remote gpu-1 -- 'make test'", "remote gpu-1 -- make\\ test",
            "remote gpu-1 -- 'make; git push'", "service svc", "service svc --schema tools/s.json",
            "service svc --prompt-file tools/p.md --prompt-file tools/q.md", "service svc --prompt-file tools/p.md extra",
            # a file handed over that lies outside the root and every temporary directory, or is protected
            "service svc --prompt-file /etc/hosts", "service svc --prompt-file tools/p.md --schema /etc/hosts",
            "service svc --prompt-file .claude/settings.json", "service svc --prompt-file .ddl/events.jsonl",
            "service svc --prompt-file .git/config"]
        self.each([self.gate(rest) for rest in nothing], None)
        # No input reaches them.
        self.each(["echo x | " + self.gate("remote gpu-1 -- sh"), self.gate("remote gpu-1 -- sh < tools/test_x.py"),
                   "cat tools/test_x.py | " + self.gate("service svc --prompt-file tools/p.md")], None)
        for workdir in (str(self.outside), ".claude"):
            self.assertIsNone(self.outcome("codex", ("exec_command", {"cmd": self.gate("measure build-1"), "workdir": workdir})))
        self.expect(lambda rt: self.shell(rt, self.gate("resources")), self.allow(ident, "gate"))

    def test_without_the_grant_the_subcommands_get_nothing(self):
        write_table(self.config)
        calls = [self.gate("measure build-1"), self.gate("remote build-1 -- make"),
                 self.gate("service svc --prompt-file tools/p.md")]
        self.each(calls, None)  # no grant at all
        ident = self.granted(commands=["test"], machines=["build-1", "svc"], handover=["code"])
        self.each(calls, None)  # the class is not granted: nothing, where ssh is denied
        self.expect(lambda rt: self.shell(rt, "ssh build-1 make"),
                    ("deny", ddl_gate.OUTSIDE_CLASS.format("remote-run", ident)))
        self.granted("R-" + "b" * 16, commands=["remote-run"], machines=["gpu-1"], approved="2026-11-21T00:00:00.000Z")
        self.each([self.gate("measure build-1"), self.gate("service svc --prompt-file tools/p.md")],
                  ("allow", ddl_gate.GRANT_ALLOW.format("R-" + "b" * 16, "remote-run")))  # a union of grants
        self.each([self.gate("measure batch-1"), self.gate("measure other")], None)

    def test_a_resource_is_covered_only_where_code_is_handed_over(self):
        write_table(self.config)
        calls = [self.gate("measure build-1"), self.gate("remote build-1 -- make"),
                 self.gate("service svc --prompt-file tools/p.md")]
        self.granted(commands=["remote-run"], machines=["build-1", "svc", "archive-1"])  # hands over nothing
        self.each(calls, None)
        other = self.granted("R-" + "b" * 16, commands=["remote-run"], machines=["gpu-1"], handover=["code"],
                             approved="2026-11-21T00:00:00.000Z")
        self.each(calls, None)  # the grant that names them hands over no code; another grant's handover does not count
        self.each([self.gate("measure gpu-1")], self.allow("R-" + "a" * 16, "remote-run"))
        third = self.granted("R-" + "c" * 16, commands=["test"], machines=["build-1", "svc", "archive-1"],
                             handover=["code", "business"], approved="2026-11-22T00:00:00.000Z")
        self.each(calls, self.allow("R-" + "a" * 16, "remote-run"))
        self.each([self.gate("measure archive-1"), self.gate("remote archive-1 -- make")], None)  # it takes no code
        self.assertTrue(other and third)
        # Without a table the grant's handover alone decides.
        write_table(self.config).unlink()
        self.each([self.gate("measure archive-1")], self.allow("R-" + "a" * 16, "remote-run"))
        for path in self.store.iterdir():
            path.unlink()
        self.granted(commands=["remote-run"], machines=["build-1"], handover=["personal"])
        self.each([self.gate("measure build-1"), self.gate("remote build-1 -- make")], None)

    def test_two_resources_on_one_alias_are_the_hosts_when_one_asks_each_run(self):
        write_table(self.config)
        self.granted(commands=["remote-run"], machines=["shared-1", "shared-2"], handover=["code"])
        self.each(["ssh shared-login make", "ssh shared-1 make", "ssh shared-2 make", self.gate("measure shared-1"),
                   self.gate("remote shared-1 -- make"), self.gate("remote shared-2 -- make")], None)
        self.expect(lambda rt: self.shell(rt, "ssh shared-login git push"),
                    ("deny", ddl_gate.EXIT_BEHIND_SSH.format("git push")))

    def test_an_equals_word_is_never_resolved(self):
        write_table(self.config)
        self.granted(commands=["remote-run", "test"], machines=["build-1", "gpu-1", "svc"], handover=["code"])
        self.each([self.gate("service svc --prompt-file =python3"), self.gate("service svc --prompt-file =ls"),
                   self.gate("service svc --prompt-file tools/p.md --schema =python3"),
                   self.gate("remote gpu-1 -- =git push origin main"), self.gate("remote gpu-1 --artifacts =x -- make"),
                   "ssh build-1 =git push", "python3 tools/test_x.py =x", "cat =python3", "=python3 tools/test_x.py",
                   self.gate("measure =ls"), "ssh =ls make"], None)

    def test_the_table_is_read_only_when_a_call_reaches_a_resource(self):
        write_table(self.config)
        self.granted(commands=["remote-run", "test", "build"], machines=["build-1"], handover=["code"])
        reads, real = [], ddl_gate.read_resource_table

        def counted(env=None):
            reads.append(env)
            return real(env)

        with mock.patch.object(ddl_gate, "read_resource_table", side_effect=counted):
            for make in (lambda rt: self.edit(rt, "tools/x.py"), lambda rt: self.shell(rt, "python3 tools/test_x.py"),
                         lambda rt: self.shell(rt, "git status"), lambda rt: self.shell(rt, "make"),
                         lambda rt: self.shell(rt, self.gate("status")), lambda rt: self.shell(rt, "touch x")):
                for runtime in ("claude", "codex"):
                    self.outcome(runtime, make(runtime))
            self.assertEqual(reads, [])
            command = "ssh build-1 make && ssh build-1 make test && " + self.gate("measure build-1")
            self.assertEqual(self.outcome("claude", self.shell("claude", command))[0], "allow")
            self.assertEqual(reads, [None])  # once for the call, from the process's environment

    def test_the_launcher_gives_the_same_answers_as_the_code_it_loads(self):
        write_table(self.config)
        self.granted(commands=["remote-run"], machines=["build-1", "gpu-1", "batch-1", "svc"], handover=["code"])
        for command in ("ssh gpu-alias make", "ssh gpu-1 make", "ssh batch-login make", "ssh svc ls",
                        self.gate("measure build-1"), self.gate("remote batch-1 -- make"),
                        self.gate("service svc --prompt-file tools/p.md")):
            for runtime in ("claude", "codex"):
                for event in ("pre-tool-use", "permission-request"):
                    with self.subTest(runtime=runtime, command=command, event=event):
                        call = self.shell(runtime, command)
                        self.assertEqual(self.decide(runtime, call, event=event, process=True),
                                         self.decide(runtime, call, event=event))

    def test_the_resource_words_are_the_gates_subcommands(self):
        self.assertLessEqual(set(ddl_gate.RESOURCE_WORDS) | {"resources"}, set(ddl_gate.RUN_WORDS))
        self.assertIn("resources", ddl_gate.GATE_WORDS)
        self.assertFalse(set(ddl_gate.RESOURCE_WORDS) & set(ddl_gate.GATE_WORDS))  # those need their class


class LedgerTest(ReportFlowTest):
    """Where the ledger lives, what the hook writes into it, and that it never touches a decision."""

    def pre(self, runtime, transcript, session, cwd, **extra):
        return self.run_gate("pre-tool-use", runtime, payload(runtime, transcript=transcript, session=session, cwd=cwd,
                                                              **extra))

    def test_linked_work_trees_resolve_to_one_ledger_root_and_one_project_key(self):
        env = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
        main, linked = pathlib.Path(self.tmp) / "main tree", pathlib.Path(self.tmp) / "linked tree"
        main.mkdir()

        def git(*args):
            proc = subprocess.run(["git", "-C", str(main), *args], capture_output=True, text=True, env=env)
            self.assertEqual(proc.returncode, 0, proc.stderr)

        git("init", "-q", "-b", "main")
        git("config", "user.email", "fixture@example.invalid")
        git("config", "user.name", "DDL fixture")
        git("config", "commit.gpgSign", "false")
        (main / "sample.txt").write_text("base\n")
        git("add", "sample.txt")
        git("commit", "-q", "-m", "base")
        git("worktree", "add", "-q", "-b", "side", str(linked))
        self.assertTrue((linked / ".git").is_file())  # a linked work tree: `.git` names its own Git directory
        for tree in (main, linked):
            mark_project(tree)
            (tree / "src" / "pkg").mkdir(parents=True)
        real = os.path.realpath(main)
        for cwd in (main, main / "src" / "pkg", linked, linked / "src" / "pkg"):
            with self.subTest(cwd=cwd):
                root = ddl_gate.ledger_root(ddl_gate.project_decision(str(cwd)))
                self.assertEqual((root, ddl_gate.project_key(root)), (real, project_key(main)))
        # One ledger: a denial in the linked tree is written under the main one, which ignores itself.
        self.assert_denied(self.pre("claude", fixture("claude_closed_in_turn.jsonl"), "linked", str(linked / "src" / "pkg")))
        self.assert_denied(self.pre("claude", fixture("claude_closed_in_turn.jsonl"), "main", str(main)))
        self.assertEqual([row["session"] for row in events(main, kind="denied")], ["linked", "main"])
        self.assertEqual((main / ".ddl" / ".gitignore").read_text(), "*\n")
        self.assertFalse((linked / ".ddl").exists())
        status = subprocess.run(["git", "-C", str(main), "status", "--porcelain", "--untracked-files=all"],
                                capture_output=True, text=True, env=env)
        self.assertNotIn(".ddl", status.stdout)
        # One project key: a report prepared in either tree carries it, and one grant store directory serves both.
        for cwd in (main, linked / "src"):
            prepared = self.prepare_report("claude", cwd=cwd, grant=grant())
            record = json.loads((pathlib.Path(prepared["report"]).parent / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(record["projectKey"], project_key(main))

    def test_root_falls_back_to_the_directory_that_carries_the_marker(self):
        def root_of(cwd):
            return ddl_gate.ledger_root(ddl_gate.project_decision(str(cwd)))

        base = pathlib.Path(self.tmp)
        for name in ("CLAUDE.md", ".claude/CLAUDE.md", "AGENTS.md"):  # no repository at all
            with self.subTest(name=name):
                project = base / ("bare-" + name.replace("/", "_"))
                (project / "deep").mkdir(parents=True)
                mark_project(project, name)
                self.assertEqual(root_of(project / "deep"), os.path.realpath(project))
        module = base / "super" / "module"  # a submodule: its Git directory is not named `.git`
        (base / "super" / ".git" / "modules" / "module").mkdir(parents=True)
        (module / "src").mkdir(parents=True)
        (module / ".git").write_text("gitdir: ../.git/modules/module\n")
        mark_project(module, "AGENTS.md")
        self.assertEqual(root_of(module / "src"), os.path.realpath(module))
        nested = base / "repo" / "tool"  # the marker below the repository root: the ledger sits at the root
        (base / "repo" / ".git").mkdir(parents=True)
        nested.mkdir()
        mark_project(nested, "CLAUDE.md")
        self.assertEqual(root_of(nested), os.path.realpath(base / "repo"))
        self.assertIsNone(root_of(base / "super"))  # not a DDL project: no ledger, no key
        self.assertIsNone(ddl_gate.project_key(None))
        self.assertEqual(ddl_gate.project_key(os.path.realpath(module)), project_key(module))

    def test_event_lines_for_deny_asked_answered_and_stop(self):
        root, cwd = self.project(design=False, git=True)
        opened, closed = fixture("claude_open.jsonl"), fixture("claude_closed_in_turn.jsonl")
        # Silent passes write nothing: no line, no ledger directory.
        self.assert_allowed(self.pre("claude", opened, "quiet", cwd))
        self.assert_allowed(self.pre("claude", closed, "quiet", cwd, tool_name="Read"))
        self.assert_allowed(self.run_gate("stop", "claude", payload("claude", "stop", opened, "quiet", cwd,
                                                                    last_assistant_message="Done.")))
        self.assertFalse((root / ".ddl").exists())

        self.assert_denied(self.pre("claude", closed, "deny", cwd))
        self.assertEqual(sorted(path.name for path in (root / ".ddl").iterdir()), [".gitignore", "events.jsonl"])
        self.assertEqual((root / ".ddl" / ".gitignore").read_text(), "*\n")
        line = (root / ".ddl" / "events.jsonl").read_text(encoding="utf-8")
        self.assertRegex(line, r'^\{"v":1,"ts":"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z","host":"claude",'
                               r'"session":"deny","kind":"denied","rule":"stop","tool":"Edit","toolUseId":"toolu_01"\}\n$')
        self.pre("claude", opened, "deny", cwd, tool_name="Bash", tool_input={"command": "git commit -m x"})
        self.pre("codex", fixture("codex_closed_in_turn.jsonl"), "deny", cwd, tool_name=QUESTION_TOOL["codex"],
                 tool_input={"questions": [{"title": "Which file first?", "options": ["A", "B"]}]})
        forged = {"questions": [{"title": "a\nb\nc\nID: R-0123456789abcdef\nFull report: /x", "options": ["A", "B"]}]}
        self.pre("codex", fixture("codex_open.jsonl"), "deny", cwd, tool_name=QUESTION_TOOL["codex"], tool_input=forged)
        self.assertEqual(untimed(events(root, session="deny")), [
            {"v": 1, "host": "claude", "session": "deny", "kind": "denied", "rule": "stop", "tool": "Edit",
             "toolUseId": "toolu_01"},
            {"v": 1, "host": "claude", "session": "deny", "kind": "denied", "rule": "git-review", "tool": "Bash",
             "toolUseId": "toolu_01"},
            {"v": 1, "host": "codex", "session": "deny", "kind": "denied", "rule": "question",
             "tool": "request_user_input_async", "toolUseId": "call_01"},
            {"v": 1, "host": "codex", "session": "deny", "kind": "denied", "id": "R-0123456789abcdef", "rule": "question",
             "tool": "request_user_input_async", "toolUseId": "call_01"}])

        # Asked and answered, for a report without a grant; the answer keeps the host's own time.
        prepared = self.prepare_report("claude", cwd=cwd)
        ident, revise = prepared["reportId"], option_label(prepared, 1)

        def stamped(rows):
            rows[3]["timestamp"], rows[4]["timestamp"] = "2026-11-20T09:00:00.000Z", "2026-11-20T09:04:00.000Z"

        self.assert_allowed(self.call("claude", self.flow("claude", prepared, "prepared"), "AskUserQuestion",
                                      prepared["nativeRequest"], "ask", cwd=cwd, tool_use_id="toolu_question"))
        self.assert_allowed(self.pre("claude", self.flow("claude", prepared, "answered", 1, mutate=stamped), "ask", cwd))
        asked, answered = events(root, session="ask")
        self.assertRegex(asked.pop("ts"), ISO_UTC)
        self.assertEqual(asked, {"v": 1, "host": "claude", "session": "ask", "kind": "asked", "id": ident,
                                 "tool": "AskUserQuestion", "toolUseId": "toolu_question"})
        self.assertEqual(answered, {"v": 1, "ts": "2026-11-20T09:04:00.000Z", "host": "claude", "session": "ask",
                                    "kind": "answered", "id": ident, "toolUseId": "report-question", "choice": 1,
                                    "label": revise, "timeout": False})

        # Stop, with the pending ID when the record names one; a prompt; a session start; the one warning.
        waiting = self.prepare_report("codex", cwd=cwd)
        for session, transcript, last in (("stop-text", opened, REPORT_TEXT),
                                          ("stop-id", self.flow("codex", waiting, "asked"), "")):
            runtime = "codex" if session == "stop-id" else "claude"
            self.run_gate("stop", runtime, payload(runtime, "stop", transcript, session, cwd, last_assistant_message=last))
        self.assertEqual(untimed(events(root, kind="stop")), [
            {"v": 1, "host": "claude", "session": "stop-text", "kind": "stop"},
            {"v": 1, "host": "codex", "session": "stop-id", "kind": "stop", "id": waiting["reportId"]}])
        self.run_gate("user-prompt-submit", "claude", payload("claude", "user-prompt-submit", opened, "life", cwd, prompt="go"))
        self.run_gate("session-start", "claude", payload("claude", "session-start", opened, "life", cwd, source="startup"))
        for _ in range(2):  # the warning is given once per session, and logged once
            self.pre("claude", os.path.join(self.tmp, "no-such-record.jsonl"), "life", cwd)
        self.assertEqual(untimed(events(root, session="life")), [
            {"v": 1, "host": "claude", "session": "life", "kind": "prompt"},
            {"v": 1, "host": "claude", "session": "life", "kind": "session-start", "rule": "startup"},
            {"v": 1, "host": "claude", "session": "life", "kind": "warn", "rule": "unreadable-record", "tool": "Edit",
             "toolUseId": "toolu_01"}])
        # A preparation is logged too, by the subcommand, in the project of its working directory.
        self.assertEqual(untimed(events(root, kind="prepared")), [
            {"v": 1, "host": "claude", "session": None, "kind": "prepared", "id": ident},
            {"v": 1, "host": "codex", "session": None, "kind": "prepared", "id": waiting["reportId"]}])
        self.assertEqual({row["kind"] for row in events(root)} - set(
            "prepared asked answered granted denied ask stop prompt session-start warn".split()), set())

    def test_push_form_denial_names_its_rule(self):
        note = {}
        data = payload("codex", transcript=fixture("codex_open.jsonl"), tool_name="exec_command",
                       tool_input={"cmd": "git -C /repo push origin main"})
        with mock.patch.dict(os.environ, {"DDL_GATE_STATE_DIR": self.state}), \
                mock.patch.object(ddl_gate, "git_review_guard", return_value=None):
            decision = ddl_gate.tool_decision("codex", data, ddl_gate.project_decision(str(PROJECT)), note)
        self.assertEqual(decision, ddl_gate.deny(ddl_gate.PUSH_FORM_REASON))
        self.assertEqual((note["rule"], note["state"]), ("push-form", False))

    def test_a_failed_write_changes_no_decision(self):
        root, cwd = self.project(design=False, git=True)
        (root / ".ddl").write_text("a file where the ledger directory belongs")
        opened, closed = fixture("claude_open.jsonl"), fixture("claude_closed_in_turn.jsonl")
        self.assert_denied(self.pre("claude", closed, "blocked", cwd))
        self.assert_allowed(self.pre("claude", opened, "blocked", cwd))
        self.assert_allowed(self.run_gate("stop", "claude", payload("claude", "stop", closed, "blocked", cwd,
                                                                    last_assistant_message=REPORT_TEXT)))
        self.assertTrue(self.marker("blocked").exists())
        self.assert_allowed(self.run_gate("user-prompt-submit", "claude", payload("claude", "user-prompt-submit", opened,
                                                                                  "blocked", cwd, prompt="go")))
        self.assert_allowed(self.run_gate("session-start", "claude", payload("claude", "session-start", opened, "blocked",
                                                                             cwd, source="startup")))
        prepared = self.prepare_report("claude", cwd=cwd, grant=grant())  # prepared although its line is lost
        self.assert_allowed(self.call("claude", self.flow("claude", prepared, "prepared"), "AskUserQuestion",
                                      prepared["nativeRequest"], "blocked", cwd=cwd))
        self.assert_allowed(self.pre("claude", self.flow("claude", prepared, "answered"), "blocked", cwd))
        self.assertTrue((root / ".ddl").is_file())
        # The grant does not depend on the ledger; and a store that cannot be created changes nothing either.
        store = pathlib.Path(self.grants) / project_key(root) / "grants"
        self.assertEqual([path.name for path in store.iterdir()], [prepared["reportId"] + ".json"])
        shutil.rmtree(self.grants)
        pathlib.Path(self.grants).write_text("a file where the grant store belongs")
        again = self.prepare_report("claude", cwd=cwd, grant=grant())
        self.assert_allowed(self.call("claude", self.flow("claude", again, "prepared"), "AskUserQuestion",
                                      again["nativeRequest"], "blocked", cwd=cwd))
        self.assert_allowed(self.pre("claude", self.flow("claude", again, "answered"), "blocked", cwd))
        self.assert_denied(self.pre("claude", closed, "blocked", cwd))
        self.assertTrue(pathlib.Path(self.grants).is_file())

    def test_the_ignore_file_is_written_whenever_it_is_missing_and_never_rewritten(self):
        root, cwd = self.project(design=False, git=True)
        closed, ledger = fixture("claude_closed_in_turn.jsonl"), root / ".ddl"
        ignore = ledger / ".gitignore"
        ledger.mkdir()  # a directory that was there before the gate first wrote into it
        self.assert_denied(self.pre("claude", closed, "one", cwd))
        self.assertEqual(ignore.read_text(), "*\n")
        self.assertEqual(sorted(path.name for path in ledger.iterdir()), [".gitignore", "events.jsonl"])
        ignore.unlink()  # an earlier write that failed, or a file somebody removed
        self.assert_denied(self.pre("claude", closed, "two", cwd))
        self.assertEqual(ignore.read_text(), "*\n")
        ignore.write_text("*\n!runs/\n")  # the project's own file stays as it is
        before = ignore.stat().st_mtime_ns
        self.assert_denied(self.pre("claude", closed, "three", cwd))
        self.assertEqual((ignore.read_text(), ignore.stat().st_mtime_ns), ("*\n!runs/\n", before))
        self.assertEqual([row["session"] for row in events(root, kind="denied")], ["one", "two", "three"])
        # The subcommands write through the same directory.
        prepared = self.prepare_report("claude", cwd=cwd)
        ignore.unlink()
        started = self.subcommand(["run-start"], {"report": prepared["reportId"], "items": []}, cwd=cwd)
        self.assertEqual((started.returncode, started.stderr), (0, ""))
        self.assertEqual(ignore.read_text(), "*\n")
        self.assertEqual(sorted(path.name for path in ledger.iterdir()), [".gitignore", "events.jsonl", "runs"])
        # While the file cannot be written, no line enters a ledger that would not ignore itself; nothing is raised.
        ignore.unlink()
        lines = len(events(root))
        with mock.patch.object(ddl_gate, "write_whole", side_effect=OSError("synthetic failure")):
            ddl_gate.ledger_event(os.path.realpath(root), "claude", "four", "denied")
        self.assertEqual((len(events(root)), ignore.exists()), (lines, False))
        ddl_gate.ledger_event(os.path.realpath(root), "claude", "four", "denied")
        self.assertEqual((len(events(root)), ignore.read_text()), (lines + 1, "*\n"))

    def test_a_ledger_directory_that_is_a_symbolic_link_is_not_followed(self):
        """Following the link would write the ignore file and the events outside the project."""
        root, cwd = self.project(design=False, git=True)
        outside = pathlib.Path(tempfile.mkdtemp(prefix="ddl-gate-elsewhere-"))
        self.addCleanup(shutil.rmtree, outside, True)
        (root / ".ddl").symlink_to(outside, target_is_directory=True)
        closed = fixture("claude_closed_in_turn.jsonl")
        self.assert_denied(self.pre("claude", closed, "one", cwd))  # the decision stands; nothing is written
        self.assertEqual(list(outside.iterdir()), [])
        prepared = self.prepare_report("claude", cwd=cwd)
        started = self.subcommand(["run-start"], {"report": prepared["reportId"], "items": []}, cwd=cwd)
        self.assertEqual(started.returncode, 2)
        self.assertIn("symbolic link", started.stderr)
        self.assertEqual(list(outside.iterdir()), [])


COUNT_SAMPLE = {"ja": ["問い: 3 件（承認 2、見直し 1、時間切れ 0）", "待ち: 人間 12 分（答えまで中央値 4 分、最長 7 分）", "拒否: 2 件"],
                "en": ["Questions: 3 (approved 2, revised 1, timed out 0)",
                       "Waiting: human 12 min (median to answer 4 min, longest 7 min)", "Denials: 2"]}


class CountReportTest(ReportFlowTest):
    """`report`: the four count lines, from a conversation record, a session's ledger events, or a Run."""

    def lines(self, *argv, cwd=None):
        proc = self.subcommand(["report", *argv], cwd=cwd)
        self.assertEqual((proc.returncode, proc.stderr), (0, ""))
        return proc.stdout.splitlines()

    def write_grant(self, ident, key="0" * 16, session="S", **changes):
        """A grant record written by hand; returns its expiry date."""
        given = grant(**changes)
        directory = pathlib.Path(self.grants) / key / "grants"
        directory.mkdir(parents=True, exist_ok=True)
        record = {"id": ident, "projectKey": key, "root": "/synthetic", "grant": given,
                  "approvedAt": "2026-11-20T09:04:10.000Z", "session": session, "host": "claude"}
        (directory / (ident + ".json")).write_text(json.dumps(record), encoding="utf-8")
        return given["expires"][:10]

    def event(self, clock, kind, session="S", **fields):
        return dict({"v": 1, "ts": "2026-11-20T" + clock + ".000Z", "host": "claude", "session": session, "kind": kind},
                    **fields)

    def ledger(self, root, rows, torn=True):
        (root / ".ddl").mkdir(exist_ok=True)
        text = "".join(json.dumps(row) + "\n" for row in rows) + ('{"v":1,"ts":"2026-11-20T10:' if torn else "")
        (root / ".ddl" / "events.jsonl").write_text(text, encoding="utf-8")

    def sample(self):
        """One session's events: four questions (two approved, one revised, one timed out), duplicates from a
        second install, and denials of this and of another session."""
        return [
            self.event("10:00:00", "asked", id="R-" + "a" * 16, tool="AskUserQuestion", toolUseId="c1"),
            self.event("10:00:00", "asked", id="R-" + "a" * 16, tool="AskUserQuestion", toolUseId="c1"),  # the other install
            self.event("10:04:00", "answered", id="R-" + "a" * 16, toolUseId="c1", choice=0, label="Approve", timeout=False),
            self.event("10:06:00", "denied", tool="Edit", toolUseId="d1", rule="stop"),
            self.event("10:06:00", "denied", tool="Edit", toolUseId="d1", rule="stop"),
            self.event("10:07:00", "denied", tool="Bash", toolUseId="d2", rule="git-review"),
            self.event("10:08:00", "denied", session="OTHER", tool="Edit", toolUseId="d1", rule="stop"),
            self.event("10:10:00", "asked", id="G-" + "b" * 16, tool="AskUserQuestion", toolUseId="c2"),
            self.event("10:11:00", "answered", id="G-" + "b" * 16, toolUseId="c2", choice=1, label="Revise", timeout=False),
            self.event("10:20:00", "asked", id="R-" + "c" * 16, tool="AskUserQuestion", toolUseId="c3"),
            self.event("10:21:00", "answered", id="R-" + "c" * 16, toolUseId="c3", timeout=True),
            self.event("10:30:00", "asked", id="R-" + "d" * 16, tool="AskUserQuestion", toolUseId="c4"),
            # The answer's call ID differs from the asked one: joined by the question's ID alone.
            self.event("10:37:00", "answered", id="R-" + "d" * 16, toolUseId="c4-other", choice=0, label="Approve",
                       timeout=False),
            self.event("10:38:00", "stop", id="R-" + "d" * 16), self.event("10:39:00", "prompt"),
            {"v": 2, "ts": "2026-11-20T10:40:00.000Z", "session": "S", "kind": "denied", "toolUseId": "future"},
        ]

    def test_claude_and_codex_transcripts_with_a_timeout_counted_apart(self):
        claude = ["--transcript", fixture("report_count_claude.jsonl"), "--runtime", "claude"]
        self.assertEqual(self.lines(*claude), ["問い: 5 件（承認 2、見直し 1、時間切れ 1）",
                                               "待ち: 人間 12 分（答えまで中央値 4 分、最長 7 分）", "拒否: 未計測", "許諾: なし"])
        self.assertEqual(self.lines(*claude, "--language", "ja"), self.lines(*claude))
        self.assertEqual(self.lines("--language=en", "--runtime=claude", "--transcript=" + fixture("report_count_claude.jsonl")),
                         ["Questions: 5 (approved 2, revised 1, timed out 1)",
                          "Waiting: human 12 min (median to answer 4 min, longest 7 min)", "Denials: not measured",
                          "Grant: none"])
        codex = ["--transcript", fixture("report_count_codex.jsonl"), "--runtime", "codex"]
        self.assertEqual(self.lines(*codex), ["問い: 3 件（承認 1、見直し 1、時間切れ 0）",
                                              "待ち: 人間 7 分（答えまで中央値 4 分、最長 5 分）", "拒否: 未計測", "許諾: なし"])
        self.assertEqual(self.lines(*codex, "--language", "en"), [
            "Questions: 3 (approved 1, revised 1, timed out 0)", "Waiting: human 7 min (median to answer 4 min, longest 5 min)",
            "Denials: not measured", "Grant: none"])
        self.assertFalse(os.path.exists(self.grants))  # reading creates no store
        # The grant line: the latest record among the reports the record asked about, whatever its project.
        day = self.write_grant("R-1111111111111111")
        self.assertEqual(self.lines(*claude)[3], "許諾: R-1111111111111111（期限 {}、有効）".format(day))
        self.assertEqual(self.lines(*claude, "--language", "en")[3], "Grant: R-1111111111111111 (expires {}, valid)".format(day))
        self.write_grant("R-9999999999999999")  # a grant of a report this record never asked about
        self.write_grant("R-bbbbbbbbbbbbbbbb", key="1" * 16, expires="2020-01-01T00:00:00Z")
        self.assertEqual(self.lines(*claude)[3], "許諾: R-1111111111111111（期限 {}、有効）".format(day))
        self.assertEqual(self.lines(*codex)[3], "許諾: R-bbbbbbbbbbbbbbbb（期限 2020-01-01、期限切れ）")
        self.assertEqual(self.lines(*codex, "--language", "en")[3], "Grant: R-bbbbbbbbbbbbbbbb (expires 2020-01-01, expired)")

    def test_a_value_that_cannot_be_derived_is_not_measured(self):
        for runtime in ("claude", "codex"):
            with self.subTest(runtime=runtime):
                prepared = self.prepare_report(runtime)
                # These records carry no timestamps: the answer is counted, its time is not estimated.
                answered = self.lines("--transcript", self.flow(runtime, prepared, "answered"), "--runtime", runtime)
                self.assertEqual(answered, ["問い: 1 件（承認 1、見直し 0、時間切れ 0）", "待ち: 未計測", "拒否: 未計測", "許諾: なし"])
                # An unanswered question waited for nobody's answer yet.
                asked = self.lines("--transcript", self.flow(runtime, prepared, "asked"), "--runtime", runtime, "--language", "en")
                self.assertEqual(asked, ["Questions: 1 (approved 0, revised 0, timed out 0)",
                                         "Waiting: human 0 min (median to answer not measured, longest not measured)",
                                         "Denials: not measured", "Grant: none"])
                missing = os.path.join(self.tmp, "no-such-record.jsonl")
                self.assertEqual(self.lines("--transcript", missing, "--runtime", runtime),
                                 ["問い: 未計測", "待ち: 未計測", "拒否: 未計測", "許諾: 未計測"])
                self.assertEqual(self.lines("--transcript", missing, "--runtime", runtime, "--language", "en"),
                                 ["Questions: not measured", "Waiting: not measured", "Denials: not measured",
                                  "Grant: not measured"])
        root, cwd = self.project(design=False, git=True)
        # A session of a project without a ledger (an older gate, or nothing logged yet), and outside any project.
        self.assertEqual(self.lines("--session", "S", cwd=cwd), ["問い: 未計測", "待ち: 未計測", "拒否: 未計測", "許諾: なし"])
        self.assertEqual(self.lines("--session", "S", cwd=self.tmp), ["問い: 未計測", "待ち: 未計測", "拒否: 未計測", "許諾: 未計測"])
        self.assertFalse((root / ".ddl").exists())  # reading creates no ledger

    def test_session_counts_come_from_the_ledger(self):
        root, cwd = self.project(design=False, git=True)
        self.ledger(root, self.sample())
        self.assertEqual(self.lines("--session", "S", cwd=cwd), [
            "問い: 4 件（承認 2、見直し 1、時間切れ 1）", COUNT_SAMPLE["ja"][1], "拒否: 2 件", "許諾: なし"])
        self.assertEqual(self.lines("--session=S", "--language=en", "--runtime", "claude", cwd=os.path.join(cwd, ".claude")), [
            "Questions: 4 (approved 2, revised 1, timed out 1)", COUNT_SAMPLE["en"][1], "Denials: 2", "Grant: none"])
        self.assertEqual(self.lines("--session", "OTHER", cwd=cwd), [
            "問い: 0 件（承認 0、見直し 0、時間切れ 0）", "待ち: 人間 0 分（答えまで中央値 未計測、最長 未計測）", "拒否: 1 件", "許諾: なし"])
        # The grant line: the session's own record in this project's store, the latest when it has several.
        day = self.write_grant("R-" + "a" * 16, key=project_key(root))
        self.write_grant("R-" + "9" * 16, key=project_key(root), session="OTHER")
        self.write_grant("R-" + "8" * 16, session="S")  # another project's
        self.assertEqual(self.lines("--session", "S", cwd=cwd)[3], "許諾: R-{}（期限 {}、有効）".format("a" * 16, day))
        # The contract's own sample, line for line.
        rows = [row for row in self.sample() if row.get("id") != "R-" + "c" * 16]
        self.ledger(root, rows, torn=False)
        self.assertEqual(self.lines("--session", "S", cwd=cwd), COUNT_SAMPLE["ja"] + ["許諾: R-{}（期限 {}、有効）".format("a" * 16, day)])
        self.assertEqual(self.lines("--session", "S", "--language", "en", cwd=cwd),
                         COUNT_SAMPLE["en"] + ["Grant: R-{} (expires {}, valid)".format("a" * 16, day)])

    def test_run_counts_cover_its_start_until_the_next_run(self):
        root, cwd = self.project(design=False, git=True)
        self.ledger(root, self.sample())
        runs = {"N-000000000001": ("10:05:00", "R-" + "a" * 16), "N-000000000002": ("10:25:00", "R-" + "7" * 16)}
        for run_id, (clock, report) in runs.items():
            directory = root / ".ddl" / "runs" / run_id
            directory.mkdir(parents=True)
            (directory / "run.json").write_text(json.dumps({
                "id": run_id, "report": report, "grant": None, "startedAt": "2026-11-20T" + clock + ".000Z", "items": []}))
        day = self.write_grant("R-" + "a" * 16, key=project_key(root), session="planner")
        # The first Run: every session's lines from its start to the second Run's start, and the question of its
        # own plan, which was asked at 10:00 and answered at 10:04, before the Run started.
        self.assertEqual(self.lines("--run", "N-000000000001", cwd=cwd), [
            "問い: 3 件（承認 1、見直し 1、時間切れ 1）", "待ち: 人間 5 分（答えまで中央値 3 分、最長 4 分）", "拒否: 3 件",
            "許諾: R-{}（期限 {}、有効）".format("a" * 16, day)])
        self.assertEqual(self.lines("--run=N-000000000002", "--language", "en", cwd=cwd), [
            "Questions: 1 (approved 1, revised 0, timed out 0)", "Waiting: human 7 min (median to answer 7 min, longest 7 min)",
            "Denials: 0", "Grant: none"])
        os.unlink(root / ".ddl" / "events.jsonl")  # the Run is known, its events are not
        self.assertEqual(self.lines("--run", "N-000000000001", cwd=cwd), [
            "問い: 未計測", "待ち: 未計測", "拒否: 未計測", "許諾: R-{}（期限 {}、有効）".format("a" * 16, day)])

    def test_a_run_counts_the_question_of_its_own_plan(self):
        """A plan is asked, answered and granted before `run-start`: its lines carry the report's ID, not the
        Run's dates."""
        root, cwd = self.project(design=False, git=True)
        plan, review, other = "R-" + "a" * 16, "G-" + "b" * 16, "R-" + "c" * 16
        run, following = "N-000000000001", "N-000000000002"
        self.ledger(root, [
            self.event("09:40:00", "asked", id=other, tool="AskUserQuestion", toolUseId="c0"),  # the plan before this one
            self.event("09:41:00", "answered", id=other, toolUseId="c0", choice=1, label="Revise", timeout=False),
            self.event("09:50:00", "prepared", session=None, id=plan),
            self.event("09:51:00", "denied", tool="Edit", toolUseId="d0", rule="stop"),  # before the Run, about no report
            self.event("09:52:00", "asked", id=plan, tool="AskUserQuestion", toolUseId="c1"),
            self.event("09:52:00", "asked", id=plan, tool="AskUserQuestion", toolUseId="c1"),  # the other install's copy
            self.event("09:53:00", "denied", id=plan, tool="Edit", toolUseId="d1", rule="stop"),  # held while the plan waited
            self.event("09:58:00", "answered", id=plan, toolUseId="c1", choice=0, label="Approve", timeout=False),
            self.event("09:58:00", "granted", id=plan, toolUseId="c1"),
            self.event("10:00:00", "prepared", session=None, id=run, run=run),
            self.event("10:10:00", "asked", id=review, tool="AskUserQuestion", toolUseId="c2"),
            self.event("10:12:00", "answered", id=review, toolUseId="c2", choice=0, label="Commit", timeout=False),
            self.event("10:30:00", "prepared", session=None, id=following, run=following),
            self.event("10:40:00", "denied", tool="Edit", toolUseId="d2", rule="stop")])
        for run_id, clock, report in ((run, "10:00:00", plan), (following, "10:30:00", "R-" + "7" * 16)):
            directory = root / ".ddl" / "runs" / run_id
            directory.mkdir(parents=True)
            (directory / "run.json").write_text(json.dumps({
                "id": run_id, "report": report, "grant": None, "startedAt": "2026-11-20T" + clock + ".000Z", "items": []}))
        day = self.write_grant(plan, key=project_key(root))
        # Both questions, each once; the waiting covers both: 6 minutes for the plan and 2 for the review.
        self.assertEqual(self.lines("--run", run, cwd=cwd), [
            "問い: 2 件（承認 2、見直し 0、時間切れ 0）", "待ち: 人間 8 分（答えまで中央値 4 分、最長 6 分）", "拒否: 1 件",
            "許諾: {}（期限 {}、有効）".format(plan, day)])
        # The Run after it counts neither that plan's question nor anything dated before its own start.
        self.assertEqual(self.lines("--run", following, cwd=cwd), [
            "問い: 0 件（承認 0、見直し 0、時間切れ 0）", "待ち: 人間 0 分（答えまで中央値 未計測、最長 未計測）", "拒否: 1 件",
            "許諾: なし"])

    def test_a_run_reports_in_the_language_of_its_plan(self):
        root, cwd = self.project(design=False, git=True)
        english = ["Questions: 0 (approved 0, revised 0, timed out 0)",
                   "Waiting: human 0 min (median to answer not measured, longest not measured)", "Denials: 0", "Grant: none"]
        japanese = ["問い: 0 件（承認 0、見直し 0、時間切れ 0）", "待ち: 人間 0 分（答えまで中央値 未計測、最長 未計測）", "拒否: 0 件",
                    "許諾: なし"]

        def started(language):
            prepared = self.prepare_report("claude", cwd=cwd, language=language)
            proc = self.subcommand(["run-start"], {"report": prepared["reportId"], "items": []}, cwd=cwd)
            self.assertEqual((proc.returncode, proc.stderr), (0, ""))
            return json.loads(proc.stdout)

        for language, lines in (("en", english), ("en-US", english), ("fr", english), ("ja", japanese), ("ja-JP", japanese)):
            with self.subTest(language=language):
                out = started(language)
                self.assertEqual(json.loads(pathlib.Path(out["path"]).read_text(encoding="utf-8"))["language"], language)
                self.assertEqual(self.lines("--run", out["run"], cwd=cwd), lines)  # the plan's language without the flag
                self.assertEqual(self.lines("--run", out["run"], "--language", "ja", cwd=cwd), japanese)  # the flag wins
                self.assertEqual(self.lines("--language=en", "--run", out["run"], cwd=cwd), english)
        # A Run that names no language (one written before the key existed) reports in Japanese.
        out = started("en")
        path = pathlib.Path(out["path"])
        run = json.loads(path.read_text(encoding="utf-8"))
        for stored in ({}, {"language": None}, {"language": 7}):
            with self.subTest(stored=stored):
                path.write_text(json.dumps(dict({key: value for key, value in run.items() if key != "language"}, **stored)))
                self.assertEqual(self.lines("--run", out["run"], cwd=cwd), japanese)
                self.assertEqual(self.lines("--run", out["run"], "--language", "en", cwd=cwd), english)
        # The other two sources keep Japanese as their default.
        self.assertEqual(self.lines("--session", "S", cwd=cwd)[2], "拒否: 0 件")
        self.assertEqual(self.lines("--transcript", fixture("report_count_claude.jsonl"), "--runtime", "claude")[2], "拒否: 未計測")

    def test_usage_errors_exit_2(self):
        root, cwd = self.project(design=False, git=True)
        record = fixture("report_count_claude.jsonl")
        for argv in ([], ["--language", "ja"], ["--transcript", record], ["--transcript", record, "--runtime", "gemini"],
                     ["--transcript", record, "--runtime", "claude", "--session", "S"], ["--session", "S", "--run", "N-000000000001"],
                     ["--session"], ["--session", ""], ["--session", "S", "--language", "fr"], ["--session", "S", "--session", "T"],
                     ["--session", "S", "--verbose"], ["S"], ["--run", "N-1"], ["--run", "R-0123456789abcdef"],
                     ["--run", "N-00000000000G"], ["--run", "N-000000000009"]):
            with self.subTest(argv=argv):
                proc = self.subcommand(["report", *argv], cwd=cwd)
                self.assertEqual((proc.returncode, proc.stdout), (2, ""))
                self.assertTrue(proc.stderr.startswith("DDL report: "), proc.stderr)
        outside = self.subcommand(["report", "--run", "N-000000000001"], cwd=self.tmp)  # a Run lives in a project's ledger
        self.assertEqual((outside.returncode, outside.stdout), (2, ""))
        self.assertFalse((root / ".ddl").exists())


class RunTest(GateTest):
    """`run-start` and `run-item`: the Run's record in the ledger. No hook reads it."""

    ITEMS = [{"id": "I1", "kind": "write", "files": ["tools/ddl_gate.py", "tools/test_ddl_gate.py"]},
             {"id": "I2", "kind": "verify", "after": ["I1"]}, {"id": "I3", "kind": "explore"},
             {"id": "I4", "kind": "compute", "files": [], "after": ["I2", "I3"]}]

    def setUp(self):
        super().setUp()
        self.root, self.cwd = self.project(design=False, git=True)

    def start(self, data, *argv, cwd=None):
        return self.subcommand(["run-start", *argv], data, cwd or self.cwd)

    def item(self, *argv, cwd=None):
        return self.subcommand(["run-item", *argv], cwd=cwd or self.cwd)

    def started(self, runtime="claude", **fields):
        prepared = self.prepare_report(runtime, cwd=self.cwd, **fields)
        proc = self.start({"report": prepared["reportId"], "items": self.ITEMS})
        self.assertEqual((proc.returncode, proc.stderr), (0, ""))
        return prepared, json.loads(proc.stdout)

    def test_run_start_writes_the_run_and_appends_an_event(self):
        prepared, out = self.started()
        self.assertEqual(set(out), {"run", "path"})
        self.assertRegex(out["run"], r"^N-[0-9a-f]{12}$")
        path = pathlib.Path(os.path.realpath(self.root)) / ".ddl" / "runs" / out["run"] / "run.json"
        self.assertEqual(out["path"], str(path))
        run = json.loads(path.read_text(encoding="utf-8"))
        self.assertRegex(run.pop("startedAt"), ISO_UTC)
        self.assertEqual(run, {"id": out["run"], "report": prepared["reportId"], "grant": None, "language": "ja", "items": [
            {"id": "I1", "kind": "write", "files": ["tools/ddl_gate.py", "tools/test_ddl_gate.py"], "after": [], "status": "ready"},
            {"id": "I2", "kind": "verify", "files": [], "after": ["I1"], "status": "ready"},
            {"id": "I3", "kind": "explore", "files": [], "after": [], "status": "ready"},
            {"id": "I4", "kind": "compute", "files": [], "after": ["I2", "I3"], "status": "ready"}]})
        self.assertEqual(untimed(events(self.root, run=out["run"])), [
            {"v": 1, "host": "claude", "session": None, "kind": "prepared", "id": out["run"], "run": out["run"]}])
        self.assertEqual((self.root / ".ddl" / ".gitignore").read_text(), "*\n")
        # One Run per approved plan: a second start for the same report is refused and names the first.
        again = self.start({"report": prepared["reportId"], "items": []})
        self.assertEqual((again.returncode, again.stdout), (2, ""))
        self.assertIn(out["run"], again.stderr)
        self.assertEqual(os.listdir(self.root / ".ddl" / "runs"), [out["run"]])

    def test_run_names_the_grant_only_when_its_record_exists(self):
        granted = self.prepare_report("codex", cwd=self.cwd, grant=grant())
        store = pathlib.Path(self.grants) / project_key(self.root) / "grants"
        store.mkdir(parents=True)
        (store / (granted["reportId"] + ".json")).write_text(json.dumps({"id": granted["reportId"], "grant": grant()}))
        proc = self.start({"report": granted["reportId"], "items": []}, "--runtime", "codex")
        self.assertEqual((proc.returncode, proc.stderr), (0, ""))
        run = json.loads(pathlib.Path(json.loads(proc.stdout)["path"]).read_text(encoding="utf-8"))
        self.assertEqual((run["grant"], run["report"], run["items"]), (granted["reportId"], granted["reportId"], []))
        self.assertEqual(events(self.root, kind="prepared", run=run["id"])[0]["host"], "codex")
        unapproved = self.prepare_report("claude", cwd=self.cwd, grant=grant())  # prepared, never approved: no record
        proc = self.start({"report": unapproved["reportId"], "items": []})
        self.assertIsNone(json.loads(pathlib.Path(json.loads(proc.stdout)["path"]).read_text(encoding="utf-8"))["grant"])
        # A file at the record's name is the grant only when it parses as that grant's record.
        for name, leftover in (("empty", lambda ident: ""), ("torn", lambda ident: '{"id": "' + ident),
                               ("another record", lambda ident: json.dumps({"id": granted["reportId"], "grant": grant()})),
                               ("no grant", lambda ident: json.dumps({"id": ident, "grant": None})),
                               ("a list", lambda ident: json.dumps([ident]))):
            with self.subTest(leftover=name):
                prepared = self.prepare_report("claude", cwd=self.cwd, grant=grant())
                (store / (prepared["reportId"] + ".json")).write_text(leftover(prepared["reportId"]), encoding="utf-8")
                proc = self.start({"report": prepared["reportId"], "items": []})
                self.assertEqual((proc.returncode, proc.stderr), (0, ""))
                run = json.loads(pathlib.Path(json.loads(proc.stdout)["path"]).read_text(encoding="utf-8"))
                self.assertIsNone(run["grant"])
                report = self.subcommand(["report", "--run", run["id"]], cwd=self.cwd)
                self.assertEqual(report.stdout.splitlines()[3], "許諾: なし")

    def test_run_start_input_errors_exit_2_and_write_nothing(self):
        prepared = self.prepare_report("claude", cwd=self.cwd)
        elsewhere = self.prepare_report("claude")  # prepared in the default project
        report, item = prepared["reportId"], {"id": "I1", "kind": "write"}
        cases = ["not json", [], {}, {"report": report}, {"items": []}, {"report": report, "items": [], "extra": 1},
                 {"report": "R-0123", "items": []}, {"report": "G-0123456789abcdef", "items": []},
                 {"report": "R-0123456789abcdef", "items": []}, {"report": elsewhere["reportId"], "items": []},
                 {"report": report, "items": {}}, {"report": report, "items": ["I1"]},
                 {"report": report, "items": [{"id": "I1"}]}, {"report": report, "items": [dict(item, kind="deploy")]},
                 {"report": report, "items": [dict(item, id="")]}, {"report": report, "items": [dict(item, id="a b")]},
                 {"report": report, "items": [dict(item, status="done")]}, {"report": report, "items": [item, item]},
                 {"report": report, "items": [dict(item, files="x.py")]}, {"report": report, "items": [dict(item, files=["a\nb"])]},
                 {"report": report, "items": [dict(item, after=["I0"])]},  # a dependency outside this Run
                 {"report": report, "items": [dict(item, after=["I1"])]},
                 {"report": report, "items": [dict(item, after=["I2"]), {"id": "I2", "kind": "verify", "after": ["I1"]}]}]
        for data in cases:
            with self.subTest(data=data):
                proc = self.start(data)
                self.assertEqual((proc.returncode, proc.stdout), (2, ""))
                self.assertTrue(proc.stderr.startswith("DDL run: "), proc.stderr)
        for argv, cwd in ((["--runtime", "codex"], self.cwd), (["--runtime", "gemini"], self.cwd), (["--force"], self.cwd),
                          ([], self.tmp)):  # the report's own runtime; a known runtime; no other flag; a DDL project
            with self.subTest(argv=argv, cwd=cwd):
                proc = self.start({"report": report, "items": [item]}, *argv, cwd=cwd)
                self.assertEqual((proc.returncode, proc.stdout), (2, ""))
        self.assertFalse((self.root / ".ddl" / "runs").exists())
        self.assertEqual(self.start({"report": report, "items": [item]}, "--runtime=claude").returncode, 0)

    def test_run_item_sets_one_status(self):
        _, out = self.started()
        path = pathlib.Path(out["path"])
        for status in ddl_run.ITEM_STATUSES:
            with self.subTest(status=status):
                proc = self.item(out["run"], "I2", status)
                self.assertEqual((proc.returncode, proc.stderr), (0, ""))
                self.assertEqual(json.loads(proc.stdout), {"run": out["run"], "item": "I2", "status": status})
                run = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual([item["status"] for item in run["items"]], ["ready", status, "ready", "ready"])
        self.assertEqual(os.listdir(path.parent), ["run.json"])  # replaced in place, nothing left beside it
        before = path.read_bytes()
        for argv in ([], [out["run"]], [out["run"], "I2"], [out["run"], "I2", "done", "extra"], [out["run"], "I2", "passed"],
                     [out["run"], "I9", "done"], ["N-000000000000", "I2", "done"], ["N-1", "I2", "done"],
                     ["R-0123456789abcdef", "I2", "done"]):
            with self.subTest(argv=argv):
                proc = self.item(*argv)
                self.assertEqual((proc.returncode, proc.stdout), (2, ""))
                self.assertTrue(proc.stderr.startswith("DDL run: "), proc.stderr)
        self.assertEqual(self.item(out["run"], "I2", "done", cwd=self.tmp).returncode, 2)  # outside the project
        self.assertEqual(path.read_bytes(), before)

    def test_a_done_item_is_never_a_gate_pass(self):
        _, out = self.started(grant=grant())
        for item in self.ITEMS:
            self.assertEqual(self.item(out["run"], item["id"], "done").returncode, 0)
        for runtime in ("claude", "codex"):
            with self.subTest(runtime=runtime):
                closed = fixture(runtime + "_closed_in_turn.jsonl")
                self.assert_denied(self.run_gate("pre-tool-use", runtime, payload(runtime, transcript=closed, cwd=self.cwd,
                                                                                  tool_use_id="edit-" + runtime)))
                commit = bash("git commit --cleanup=verbatim -m x", runtime, fixture(runtime + "_open.jsonl"), cwd=self.cwd,
                              tool_use_id="commit-" + runtime)
                out_commit = json.loads(self.run_gate("pre-tool-use", runtime, commit).stdout)["hookSpecificOutput"]
                self.assertEqual(out_commit["permissionDecision"], "deny")
                self.assertIn("DDL Git review", out_commit["permissionDecisionReason"])
        # The counts of the Run read the same ledger.
        proc = self.subcommand(["report", "--run", out["run"], "--language", "en"], cwd=self.cwd)
        self.assertEqual(proc.stdout.splitlines(), ["Questions: 0 (approved 0, revised 0, timed out 0)",
                                                    "Waiting: human 0 min (median to answer not measured, longest not measured)",
                                                    "Denials: 4", "Grant: none"])


class QuestionFormatTest(unittest.TestCase):
    """The five-line question, its ID line, and the shapes the gate recognizes; no state directory is touched."""

    def test_question_id_reads_only_the_fourth_line(self):
        hexid = "0123456789abcdef"
        self.assertEqual(ddl_gate.question_id("a\nb\nc\nID: R-" + hexid + "\n全文: /x"), ("R", hexid))
        self.assertEqual(ddl_gate.question_id("a\r\nb\r\nc\r\n確認 ID: G-" + hexid + "\r\n全文: /x"), ("G", hexid))
        for text in ("ID: R-" + hexid, "a\nb\nID: R-" + hexid + "\nc\nd", "a\nb\nc\nID: R-" + hexid.upper(),
                     "a\nb\nc\nID: R-" + hexid[:-1], "a\nb\nc\nID: R-" + hexid + " (old)", "a\nb\nc\nID:R-" + hexid,
                     "a\nb\nc\nID: X-" + hexid, None, 42):
            with self.subTest(text=text):
                self.assertIsNone(ddl_gate.question_id(text))

    def op_commit(self, repo="/r/app", message="Fix the gate\n\nBody.\n", files=2):
        return {"kind": "commit", "repo": repo, "branch": "refs/heads/main", "message": message,
                "files": [["M", "f{}".format(i)] for i in range(files)]}

    def op_push(self, repo="/r/app", dependent=True):
        return {"kind": "push", "repo": repo, "remote": "origin", "destination": "refs/heads/main",
                "commit": None if dependent else "0123456789abcdef0123", "fromCommit": "h" if dependent else None}

    def values(self, language, *ops):
        return ddl_gate.git_question_values({"language": language, "operations": list(ops)})

    def test_git_lines_are_generated_from_the_operations(self):
        self.assertEqual(self.values("en", self.op_commit(), self.op_push()), [
            'Record commit "Fix the gate" (2 files) on main and push it to origin/main?',
            "Execute it; contents, message and destination are as in the report and diff",
            "origin/main advances to the new commit; undoing it needs a revert"])
        self.assertEqual(self.values("en", self.op_commit(files=1)),
                         ['Record commit "Fix the gate" (1 file) on main?',
                          "Execute it; contents, message and destination are as in the report and diff",
                          "main gets a new commit (nothing is pushed)"])
        self.assertEqual(self.values("en", self.op_push(dependent=False))[0], "Push 0123456 to origin/main?")
        self.assertEqual(self.values("ja", self.op_push(dependent=False))[0], "0123456 を origin/main に送るか")
        several = [self.op_commit("/r/app"), self.op_commit("/r/lib"), self.op_push("/r/app"), self.op_push("/r/lib")]
        self.assertEqual(self.values("ja", *several), [
            "2 件のコミット（app、lib）を記録し、2 件を送るか",
            "この内容で実行する。内容・メッセージ・送信先は全文と差分のとおり",
            "origin/main（app）、origin/main（lib） が新しいコミットに進む。取り消すには revert が要る"])
        self.assertEqual(self.values("en", *several[:2]), [
            "Record 2 commits (app, lib)?", "Execute it; contents, message and destination are as in the report and diff",
            "main (app), main (lib) get new commits (nothing is pushed)"])

    def test_long_subject_is_shortened_within_the_line_limit(self):
        for language, tail in (("ja", "…」（2 ファイル）を main に記録するか"), ("en", '…" (2 files) on main?')):
            with self.subTest(language=language):
                decision = self.values(language, self.op_commit(message="x" * 500 + "\n"))[0]
                self.assertLessEqual(len(decision), ddl_gate.QUESTION_LINE_LIMIT)
                self.assertTrue(decision.endswith(tail), decision)
        self.assertEqual(len(ddl_gate.fit_line("y" * 1000)), ddl_gate.QUESTION_LINE_LIMIT)
        self.assertEqual(ddl_gate.fit_line("a\nb"), "a b")

    def test_prepared_output_is_parsed_not_searched(self):
        hexid = "a" * ddl_gate.ID_HEX_LENGTH
        doc = json.dumps({"reportId": "R-" + hexid, "report": "/x/report.md", "question": "q", "nativeRequest": {}})
        found = ("R", hexid)
        for value in (doc, "Chunk ID: 1f\nWall time: 0.1 seconds\nProcess exited with code 0\nOutput:\n" + doc + "\n",
                      json.dumps({"output": doc + "\n", "metadata": {"exit_code": 0}}), [{"type": "text", "text": doc}]):
            with self.subTest(value=value):
                self.assertEqual(ddl_gate.prepared_output(value), found)
        self.assertEqual(ddl_gate.prepared_output(json.dumps({"reviewId": "G-" + hexid, "nativeRequest": {}})), ("G", hexid))
        deep = doc
        for _ in range(ddl_gate.ENVELOPE_DEPTH):
            deep = json.dumps({"output": deep})
        for value in ('The gate prints "nativeRequest" and "reportId": "R-' + hexid + '".',
                      json.dumps({"reportId": "G-" + hexid, "nativeRequest": {}}),
                      json.dumps({"reportId": "R-" + hexid}), deep, None):
            with self.subTest(value=value):
                self.assertIsNone(ddl_gate.prepared_output(value))

    def test_codex_desktop_output_is_bounded_and_reads_only_text_blocks(self):
        hexid = "a" * ddl_gate.ID_HEX_LENGTH
        for kind, key in (("R", "reportId"), ("G", "reviewId")):
            with self.subTest(kind=kind):
                prepared = {key: kind + "-" + hexid, "nativeRequest": {}}
                output = codex_desktop_output(prepared)
                found = (kind, hexid)
                self.assertEqual(ddl_gate.prepared_output(output), found)  # exactly depth four
                for ptype in ("function_call_output", "custom_tool_call_output"):
                    self.assertEqual(ddl_gate.codex_pending_signal("response_item", ptype, {"output": output}),
                                     (True, found))
                self.assertIsNone(ddl_gate.prepared_output({"output": output}))  # one envelope too deep
                doc = json.dumps(prepared)
                self.assertEqual(ddl_gate.prepared_output([doc]), found)
                self.assertEqual(ddl_gate.prepared_output([{"type": "text", "text": doc}]), found)
                rejected = [doc + " trailing prose", "Preparation result: " + doc, doc[:-1],
                            {"metadata": {"output": doc}}, {"text": doc},
                            [{"type": "thinking", "text": doc}], [{"type": "reasoning", "text": doc}],
                            [{"type": "summary_text", "text": doc}], [{"text": doc}],
                            [prepared], [{"type": "input_text", "text": prepared}]]
                for value in rejected:
                    with self.subTest(value=value):
                        self.assertIsNone(ddl_gate.prepared_output(value))
                for ptype in ("reasoning", "thinking", "custom_tool_call"):
                    self.assertEqual(ddl_gate.codex_pending_signal("response_item", ptype, {"output": output}),
                                     (False, None))

    def test_only_the_exact_preparation_call_is_recognized(self):
        own = os.path.realpath(ddl_gate.__file__)
        body = "\n{\"language\": \"ja\", \"detail\": \"$(rm x) `rm x`\"}\n"
        allowed = ["python3 \"$HOME/.claude/hooks/ddl_gate.py\" prepare-report --runtime claude <<'JSON'" + body + "JSON",
                   "python3 -I \"$CLAUDE_PROJECT_DIR\"/.claude/hooks/ddl_gate.py prepare-git-review --runtime claude <<\"EOF\""
                   + body + "EOF\n",
                   "python3 $HOME/.codex/hooks/ddl_gate.py prepare-report --runtime=codex << 'JSON'" + body + "JSON",
                   "python3 .codex/hooks/ddl_gate.py prepare-report --runtime codex <<'JSON'" + body + "JSON",
                   "python3 " + shlex.quote(own) + " prepare-report --runtime codex <<'X'" + body + "X",
                   "python3 '" + own + "' prepare-report --runtime claude <<'JSON'" + body + "JSON"]
        for command in allowed:
            with self.subTest(command=command):
                self.assertTrue(ddl_gate.is_gate_preparation(command))
        head = "python3 \"$HOME/.claude/hooks/ddl_gate.py\" prepare-report --runtime claude "
        denied = [head + "<<JSON" + body + "JSON", head + "<<'JSON'" + body + "JSON\nrm x",
                  head + "<<'JSON'\n{}\nJSON\nrm x\nJSON", head + "<<'JSON'\n{}\n  JSON  \nrm x\nJSON",
                  head + "<<'JSON' | tee out" + body + "JSON", head + "<<'JSON' > out" + body + "JSON",
                  head + "<<'JSON'; rm x" + body + "JSON", head + "<<'JSON' && rm x" + body + "JSON",
                  head + "<<'JSON'" + body + "JSON\r", head.rstrip(), head + "<<'JSON'" + body,
                  "python3 /tmp/other.py prepare-report --runtime claude <<'JSON'" + body + "JSON",
                  "python3 ~/.claude/hooks/ddl_gate.py prepare-report --runtime claude <<'JSON'" + body + "JSON",
                  "python3 \"$HOME/.claude/hooks/ddl_gate.py\" pre-tool-use --runtime claude <<'JSON'" + body + "JSON",
                  "python3 \"$HOME/.claude/hooks/ddl_gate.py\" prepare-report --runtime gemini <<'JSON'" + body + "JSON",
                  "python3 -c 'print(1)' prepare-report --runtime claude <<'JSON'" + body + "JSON",
                  "python3 \"$EVIL/.claude/hooks/ddl_gate.py\" prepare-report --runtime claude <<'JSON'" + body + "JSON",
                  "/usr/bin/python3 \"$HOME/.claude/hooks/ddl_gate.py\" prepare-report --runtime claude <<'JSON'" + body + "JSON",
                  None, ["python3"]]
        for command in denied:
            with self.subTest(command=command):
                self.assertFalse(ddl_gate.is_gate_preparation(command))


class ProjectScopeTest(GateTest):
    """The gate acts only where an instruction file carries the `→ DDL-PROTOCOL` line."""

    def plain(self, name="plain"):
        """A repository with design.md but no instruction file: not a DDL project."""
        root = pathlib.Path(self.tmp) / name
        (root / ".git").mkdir(parents=True)
        (root / "design.md").write_text("# design.md\n", encoding="utf-8")
        return root

    def state_files(self):
        return sorted(p.name for p in pathlib.Path(self.state).iterdir()) if os.path.isdir(self.state) else []

    def test_every_event_returns_at_once_outside_a_ddl_project(self):
        root, seen = str(self.plain()), []
        for runtime in ("claude", "codex"):
            with self.subTest(runtime=runtime):
                closed, session = fixture(runtime + "_closed_in_turn.jsonl"), runtime + "-plain"
                seen.append(session + ".project")
                self.assert_allowed(self.run_gate("stop", runtime, payload(runtime, "stop", closed, session, root,
                                                                           last_assistant_message=REPORT_TEXT)))
                self.assertFalse(self.marker(session).exists())
                for data in (payload(runtime, transcript=closed, session=session, cwd=root),
                             bash("git commit -m x", runtime, closed, session=session, cwd=root),
                             bash("git push origin main", runtime, None, session=session, cwd=root),
                             bash("git -C /repo push origin main", runtime, None, session=session, cwd=root),
                             payload(runtime, transcript=None, session=session, cwd=root)):
                    self.assert_allowed(self.run_gate("pre-tool-use", runtime, data))
                    self.assert_allowed(self.run_gate("permission-request", runtime, dict(
                        data, hook_event_name="PermissionRequest")))
                question = "a\nb\nc\nID: R-0123456789abcdef\nFull report: /x"
                request = {"questions": [{QUESTION_KEY[runtime]: question, "options": ["A", "B"]}]}
                self.assert_allowed(self.run_gate("pre-tool-use", runtime, payload(
                    runtime, transcript=closed, session=session, cwd=root, tool_name=QUESTION_TOOL[runtime], tool_input=request)))
                for source in ("startup", "compact", "resume"):
                    self.assert_allowed(self.run_gate("session-start", runtime, payload(runtime, "session-start", closed,
                                                                                        session, root, source=source)))
                for prompt in ("go", codex_reply("call_01", question, "A")):
                    self.assert_allowed(self.run_gate("user-prompt-submit", runtime, payload(
                        runtime, "user-prompt-submit", closed, session, root, prompt=prompt)))
                self.assertEqual(self.state_files(), sorted(seen))  # no .pending, .warned, .git-epoch or .asked
        # Nor an event, a ledger directory, or a grant directory.
        self.assertEqual(sorted(os.listdir(root)), [".git", "design.md"])
        self.assertFalse(os.path.exists(self.grants))

    def test_marker_line_alone_makes_a_ddl_project(self):
        root, cwd = self.project(design=False, git=True)
        for runtime in ("claude", "codex"):
            with self.subTest(runtime=runtime):
                closed, session = fixture(runtime + "_closed_in_turn.jsonl"), runtime + "-bare"
                proc = self.run_gate("pre-tool-use", runtime, bash("git commit -m x", runtime, fixture(runtime + "_open.jsonl"),
                                                                   session=session, cwd=cwd))
                self.assertIn("DDL Git review", json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecisionReason"])
                self.run_gate("stop", runtime, payload(runtime, "stop", None, session, cwd, last_assistant_message=REPORT_TEXT))
                self.assertTrue(self.marker(session).exists())
                self.assert_denied(self.run_gate("pre-tool-use", runtime, payload(runtime, transcript=closed, session=session, cwd=cwd)))
                self.run_gate("user-prompt-submit", runtime, payload(runtime, "user-prompt-submit", closed, session, cwd, prompt="go"))
                self.assertFalse(self.marker(session).exists())

    def test_project_decision_recognizes_each_instruction_file_and_arrow(self):
        for name, line in (("CLAUDE.md", "→ DDL-PROTOCOL"), (".claude/CLAUDE.md", "  -> DDL-PROTOCOL\t"), ("AGENTS.md", "→ DDL-PROTOCOL")):
            with self.subTest(name=name, line=line):
                root = pathlib.Path(self.tmp) / name.replace("/", "_")
                (root / ".git").mkdir(parents=True)
                source = mark_project(root, name, line)
                (root / "src").mkdir()
                decision = ddl_gate.project_decision(str(root / "src"))
                self.assertEqual(decision, {"cwd": str(root / "src"), "ddl": True, "source": str(source), "line": 3,
                                            "mtime": source.stat().st_mtime})
        for line in ("the → DDL-PROTOCOL line", "| → DDL-PROTOCOL |", "→ DDL-PROTOCOL-SKILL", "DDL-PROTOCOL"):
            with self.subTest(line=line):
                root = pathlib.Path(self.tmp) / "prose"
                shutil.rmtree(root, True)
                (root / ".git").mkdir(parents=True)
                mark_project(root, "CLAUDE.md", line)
                self.assertFalse(ddl_gate.project_decision(str(root))["ddl"])
        for cwd in (None, "", 42):
            self.assertFalse(ddl_gate.project_decision(cwd)["ddl"])

    def test_search_stops_below_home_and_at_the_repository_root(self):
        home = pathlib.Path(self.tmp) / "home"
        mark_project(home, "CLAUDE.md")
        (home / "work" / "repo" / ".git").mkdir(parents=True)
        (home / "work" / "repo" / "src").mkdir()
        mark_project(home / "work", "AGENTS.md")
        with mock.patch.dict(os.environ, {"HOME": str(home)}):
            self.assertFalse(ddl_gate.project_decision(str(home))["ddl"])  # $HOME itself never counts
            self.assertTrue(ddl_gate.project_decision(str(home / "work"))["ddl"])
            self.assertFalse(ddl_gate.project_decision(str(home / "work" / "repo" / "src"))["ddl"])  # `.git` bounds it
            (home / "work" / "repo" / "src" / "sub").mkdir()
            mark_project(home / "work" / "repo")
            self.assertTrue(ddl_gate.project_decision(str(home / "work" / "repo" / "src" / "sub"))["ddl"])

    def test_cache_is_reused_by_pre_tool_use_and_refreshed_by_a_prompt(self):
        root, cwd = self.project(design=False, git=True)
        source, closed = root / ".claude" / "CLAUDE.md", fixture("claude_closed_in_turn.jsonl")
        pre = payload("claude", transcript=closed, session="cache", cwd=cwd)
        self.assert_denied(self.run_gate("pre-tool-use", "claude", pre))
        cache = pathlib.Path(self.state) / "cache.project"
        self.assertEqual(json.loads(cache.read_text()), {"cwd": cwd, "ddl": True, "source": str(source), "line": 3,
                                                         "mtime": source.stat().st_mtime})
        stat = source.stat()
        source.write_text("# no marker any more\n")
        os.utime(source, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        self.assert_denied(self.run_gate("pre-tool-use", "claude", pre))  # same cwd and mtime: reused unread
        self.run_gate("user-prompt-submit", "claude", payload("claude", "user-prompt-submit", closed, "cache", cwd, prompt="go"))
        self.assertFalse(json.loads(cache.read_text())["ddl"])  # a prompt recomputes
        self.assert_allowed(self.run_gate("pre-tool-use", "claude", pre))
        mark_project(root)  # the file changed, but a non-DDL decision is reused until the next prompt or session start
        self.assert_allowed(self.run_gate("pre-tool-use", "claude", pre))
        self.run_gate("session-start", "claude", payload("claude", "session-start", closed, "cache", cwd, source="startup"))
        self.assert_denied(self.run_gate("pre-tool-use", "claude", pre))
        source.write_text("# removed again\n")
        os.utime(source, ns=(stat.st_atime_ns, stat.st_mtime_ns + 5_000_000_000))
        self.assert_allowed(self.run_gate("pre-tool-use", "claude", pre))  # a changed mtime recomputes
        other = payload("claude", transcript=closed, session="cache", cwd=str(self.plain()))
        self.assert_allowed(self.run_gate("pre-tool-use", "claude", other))  # another cwd recomputes too
        self.assertEqual(json.loads(cache.read_text())["cwd"], other["cwd"])

    def test_status_prints_the_decision(self):
        root, cwd = self.project(design=False, git=True, sub="src")
        plain = self.plain()
        yes = "DDL project: yes ({}:3)\n".format(root / ".claude" / "CLAUDE.md")
        yes_real = "DDL project: yes ({}:3)\n".format(root.resolve() / ".claude" / "CLAUDE.md")  # os.getcwd() is resolved
        no = 'DDL project: no (no "→ DDL-PROTOCOL" line up to {})\n'.format(plain)
        for argv, directory, expected in (([], cwd, yes_real), (["--cwd", cwd], self.tmp, yes), (["--cwd=" + str(plain)], cwd, no),
                                          (["--cwd", str(plain / "src" / "deep")], cwd, no)):
            with self.subTest(argv=argv):
                proc = subprocess.run([sys.executable, "-I", GATE, "status", *argv], cwd=directory, capture_output=True, text=True)
                self.assertEqual((proc.returncode, proc.stdout, proc.stderr), (0, expected, ""))
        proc = subprocess.run([sys.executable, "-I", GATE, "status", "--bogus"], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("usage", proc.stderr)

    def test_non_ddl_path_loads_no_heavy_module(self):
        root = str(self.plain())
        heavy = {"subprocess", "hashlib", "shlex", "shutil", "secrets", "pathlib", "urllib", "urllib.parse", "typing",
                 "datetime"}
        for runtime in ("claude", "codex"):
            for event in ("pre-tool-use", "stop", "user-prompt-submit", "session-start"):
                with self.subTest(runtime=runtime, event=event):
                    data = payload(runtime, event, fixture(runtime + "_closed_in_turn.jsonl"), "lean", root, source="startup",
                                   last_assistant_message=REPORT_TEXT, prompt="go")
                    proc = subprocess.run([sys.executable, "-I", "-X", "importtime", GATE, event, "--runtime", runtime],
                                          input=json.dumps(data), capture_output=True, text=True, env=self.gate_env())
                    self.assertEqual((proc.returncode, proc.stdout), (0, ""))
                    loaded = {line.rsplit("|", 1)[1].strip() for line in proc.stderr.splitlines() if line.startswith("import time:")}
                    self.assertTrue(loaded, proc.stderr)
                    # json itself imports re, so re is the one heavier module the non-DDL path cannot avoid.
                    self.assertEqual(loaded & heavy, set())


class FailOpenTest(GateTest):
    def assert_fail_open(self, proc):
        if proc.stdout:
            self.assertEqual(list(json.loads(proc.stdout)), ["systemMessage"])

    def test_bad_stdin(self):
        self.assert_fail_open(self.run_gate("pre-tool-use", "claude", "not json"))
        self.assert_fail_open(self.run_gate("pre-tool-use", "codex", "[1, 2, 3]"))
        self.assert_fail_open(self.run_gate("pre-tool-use", "claude", ""))

    def test_unknown_event_and_runtime(self):
        data = payload("claude", transcript=fixture("claude_closed_in_turn.jsonl"))
        for argv in (["frobnicate", "--runtime", "claude"], ["pre-tool-use", "--runtime", "gemini"], ["pre-tool-use"],
                     [], ["pre-tool-use", "--runtime", "claude", "--extra"]):
            with self.subTest(argv=argv):
                proc = self.run_gate(None, None, data, argv=argv)
                self.assertIn("systemMessage", json.loads(proc.stdout))
                self.assertNotIn("permissionDecision", proc.stdout)

    def test_unwritable_state_dir_still_allows(self):
        self.state = os.path.join(self.tmp, "blocked", "state")
        pathlib.Path(os.path.join(self.tmp, "blocked")).write_text("a file, not a directory")
        proc = self.run_gate("pre-tool-use", "claude", payload("claude", transcript=fixture("claude_open.jsonl")))
        self.assert_fail_open(proc)
        self.assertNotIn("permissionDecision", proc.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=1)
