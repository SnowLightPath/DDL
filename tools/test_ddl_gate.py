#!/usr/bin/env python3
"""Tests for tools/ddl_gate.py.

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
import ddl_gate  # noqa: E402

GATE = str(TOOLS / "ddl_gate.py")
REPO = TOOLS.parent
FIXTURES = TOOLS / "fixtures"
ADAPTERS = {"claude": REPO / "hosts" / "claude" / "settings.json",
            "codex": REPO / "hosts" / "codex" / "hooks.json"}
EVENT_NAMES = {"pre-tool-use": "PreToolUse", "session-start": "SessionStart", "stop": "Stop",
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
                  ("git branch new", "git branch new")]
        for cmd, segment in denied:
            with self.subTest(cmd=cmd):
                self.assert_denied(self.run_gate("pre-tool-use", "claude", bash(cmd, transcript=transcript)), segment)

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
    in a subdirectory. Only the canonical gate is copied; generated hook mirrors are not trusted.
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
            shutil.copyfile(GATE, hooks / "ddl_gate.py")
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

    def pushed(self, runtime, proc):
        """A matched push passes: Codex leaves the native policy alone, Claude asks for the native confirmation."""
        if runtime == "codex":
            return self.assert_allowed(proc)
        out = json.loads(proc.stdout)["hookSpecificOutput"]
        self.assertEqual((out["hookEventName"], out["permissionDecision"]), ("PreToolUse", "ask"))
        self.assertEqual(out["permissionDecisionReason"], ddl_gate.PUSH_ASK_REASON)

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
            self.assert_allowed(self.check(runtime, permission_mode="bypassPermissions"))

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
                    self.assert_allowed(self.check(runtime))

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
                self.assert_allowed(self.check(runtime))
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
            self.assert_allowed(self.check(runtime))

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
                self.assert_allowed(self.check(runtime))
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
            self.assert_allowed(self.check(runtime))
            self.blocked(self.check(runtime, "git push origin main"))  # the planned commit does not exist yet
            self.git("commit", "--cleanup=verbatim", "-F", str(self.message))
            self.blocked(self.check(runtime))  # an approval cannot create a second, different commit
            self.pushed(runtime, self.check(runtime, "git push origin main"))
            self.git("push", "origin", "main")
            self.pushed(runtime, self.check(runtime, "git push origin main"))  # an idempotent retry sends no new content

    def test_claude_reviewed_push_asks_for_the_native_confirmation(self):
        review = self.prepare("claude", [self.command, "git push origin main"])
        self.record("claude", review)
        self.assert_allowed(self.check("claude"))  # a reviewed commit keeps the host's own policy
        self.git("commit", "--cleanup=verbatim", "-F", str(self.message))
        for mode in ("default", "acceptEdits", "bypassPermissions", "dontAsk"):
            with self.subTest(mode=mode):  # the hook asks in every mode; what the host does with it is its own
                self.pushed("claude", self.check("claude", "git push origin main", permission_mode=mode))
        self.assertEqual(untimed(events(self.repo, kind="ask"))[0], {
            "v": 1, "host": "claude", "session": "sess", "kind": "ask", "rule": "git-review", "tool": "Bash",
            "toolUseId": "toolu_01"})
        self.assertEqual(events(self.repo, kind="granted"), [])  # a Git review is no grant
        self.assertIn("DDL Git review", self.blocked(self.check("claude", "git push origin main:refs/heads/other")))

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
            self.assert_allowed(self.check(runtime))
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
        self.assert_allowed(self.check("claude"))

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
                                 (2, given, project_key(PROJECT)))
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
        self.assertEqual(ddl_gate.REPORT_VERSION, 2)

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
        """A PreToolUse call in this project; by default the runtime's first write tool."""
        name, default = WRITES[runtime][0]
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
                ddl_gate.approved_report_grant("claude", {"session_id": "sess", "transcript_path": answered})
            fresh = {"session_id": "fresh", "transcript_path": answered}
            self.assertEqual(ddl_gate.approved_report_grant("claude", fresh)["id"], prepared["reportId"][2:])
            with mock.patch("time.time", return_value=time.time() + 40 * 86400):  # past the grant's expiry
                with self.assertRaisesRegex(ValueError, "not in the future"):
                    ddl_gate.approved_report_grant("claude", fresh)

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

    def test_a_recorded_grant_allows_nothing_and_denies_nothing(self):
        for runtime in ("claude", "codex"):
            with self.subTest(runtime=runtime):
                prepared = self.prepared(runtime, grant=grant(paths=["**"], commands=list(ddl_gate.GRANT_COMMANDS)))
                self.assert_allowed(self.approve(runtime, prepared, session=runtime))
                self.assertIsNotNone(self.record(prepared))
                (shell, key), opened, closed = SHELL[runtime], fixture(runtime + "_open.jsonl"), fixture(runtime + "_closed_in_turn.jsonl")
                calls = WRITES[runtime] + READS[runtime] + [(shell, {key: command}) for command in (
                    "touch skills/x", "python3 tools/build.py", "git commit --cleanup=verbatim -m x", "git push origin main")]
                for transcript in (opened, closed):
                    for tool, tool_input in calls:
                        with self.subTest(transcript=os.path.basename(transcript), tool=tool, tool_input=tool_input):
                            granted = self.tool(runtime, transcript, runtime, tool, tool_input).stdout
                            # The same call in a project without any grant: the decision is the same, byte for byte.
                            bare = self.call(runtime, transcript, tool, tool_input, "bare-" + runtime).stdout
                            self.assertEqual(granted, bare)
                            self.assertNotIn("allow", granted)
                            if granted:
                                self.assertEqual(json.loads(granted)["hookSpecificOutput"]["permissionDecision"], "deny")
                            mutating = (tool, tool_input) not in READS[runtime]
                            if mutating and (transcript == closed or "git " in str(tool_input)):
                                self.assertTrue(granted)  # a pending STOP and the Git review hold inside the granted scope

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
        self.assertEqual(set(entry), {"id", "options", "grant", "toolUseId"})
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
            decision = ddl_gate.tool_decision("codex", data, note)
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
        for status in ddl_gate.ITEM_STATUSES:
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
