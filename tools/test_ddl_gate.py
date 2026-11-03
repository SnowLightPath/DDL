#!/usr/bin/env python3
"""Tests for tools/ddl_gate.py.

Unit tests import the module (shell allowlist, tool classification, the Claude human-prompt test,
the record readers). End-to-end tests run the hook as a subprocess with `python3 -I`, a private
state directory, and the hand-written transcript fixtures under tools/fixtures/. Every project the
gate is expected to act in is a disposable directory carrying an instruction file with the
`→ DDL-PROTOCOL` line, never this repository's own files.

Usage:
  python3 tools/test_ddl_gate.py
  python3 -I tools/test_ddl_gate.py
"""
import atexit
import json
import os
import pathlib
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
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
    "codex_open.jsonl": False,
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

    def run_gate(self, event, runtime, data, argv=None):
        stdin = data if isinstance(data, str) else json.dumps(data)
        env = dict(getattr(self, "git_env", os.environ), DDL_GATE_STATE_DIR=self.state)
        if argv is None:
            argv = [event, "--runtime", runtime]
        proc = subprocess.run([sys.executable, "-I", GATE] + argv, input=stdin, capture_output=True, text=True, env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stderr, "")
        return proc

    def assert_allowed(self, proc):
        self.assertEqual(proc.stdout, "")

    def assert_denied(self, proc, segment=None):
        out = json.loads(proc.stdout)["hookSpecificOutput"]
        self.assertEqual(out["hookEventName"], "PreToolUse")
        self.assertEqual(out["permissionDecision"], "deny")
        expected = ddl_gate.DENY_REASON + (SEGMENT_SUFFIX.format(segment) if segment else "")
        self.assertEqual(out["permissionDecisionReason"], expected)

    def assert_warning(self, proc):
        out = json.loads(proc.stdout)
        self.assertEqual(list(out), ["systemMessage"])
        return out["systemMessage"]

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
                    "claude_plan_approved.jsonl": True, "claude_plan_rejected.jsonl": False}
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
        transcript = fixture("codex_closed_in_turn.jsonl")
        for tool in ("request_user_input", "request_user_input_async"):
            with self.subTest(tool=tool):
                self.assert_allowed(self.run_gate("pre-tool-use", "codex",
                                                 payload("codex", transcript=transcript, tool_name=tool)))
                self.assert_denied(self.run_gate("pre-tool-use", "codex", payload("codex", transcript=transcript)))

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
        self.env = dict(os.environ, DDL_GATE_STATE_DIR=self.state, HOME=str(self.home),
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
                       ("TaskGet", {"taskId": "fixture"}), ("TaskList", {}), ("AskUserQuestion", {}),
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
                question = "AskUserQuestion" if runtime == "claude" else "request_user_input_async"
                self.assert_adapter_allowed(self.run_adapter(runtime, "pre-tool-use", dict(pre, tool_name=question)))
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
        proc = self.run_gate("prepare-git-review", runtime, {"language": "ja", "operations": operations})
        return json.loads(proc.stdout)

    def record(self, runtime, review, choice=0, mutate=None):
        q = review["question"]
        answer = q["options"][choice]
        request = review["nativeRequest"]
        reply = [{"questionItemId": json.dumps(["request_user_input_async", "git-review-call", 0]),
                  "question": q["title"], "answer": answer}]
        replacements = {"@ID@": review["reviewId"][2:], "@REPORT@": review["report"],
                        "@REQUEST@": request, "@REQUEST_JSON@": json.dumps(request),
                        "@ANSWERS@": {q["title"]: answer},
                        "@REPLY@": "<send_user_message_question_reply>\n" + json.dumps(reply) +
                                   "\n</send_user_message_question_reply>"}
        def render(value):
            if isinstance(value, str):
                if value in replacements:
                    return replacements[value]
                for key in ("@ID@", "@REPORT@"):
                    value = value.replace(key, replacements[key])
                return value
            if isinstance(value, list):
                return [render(v) for v in value]
            if isinstance(value, dict):
                return {k: render(v) for k, v in value.items()}
            return value
        rows = [render(json.loads(line)) for line in pathlib.Path(fixture("git_review_" + runtime + ".jsonl")).read_text().splitlines()]
        if mutate:
            mutate(rows)
        self.transcript.write_text("".join(json.dumps(row) + "\n" for row in rows))
        return rows

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

    def test_receipt_missing_request_and_wrong_report_cannot_authorize_git(self):
        for runtime in ("claude", "codex"):
            review = self.prepare(runtime)
            def omit_detail(rows):
                entry = rows[0] if runtime == "claude" else rows[1]["payload"]
                message = entry["message"] if runtime == "claude" else entry
                message["content"][0]["text"] = "+++DDL_REPORT\nGit review " + review["reviewId"]
            for change in (lambda rows: rows.pop(), lambda rows: rows.pop(1 if runtime == "claude" else 2),
                           lambda rows: rows.pop(0 if runtime == "claude" else 1), omit_detail):
                self.record(runtime, review, mutate=change)
                self.blocked(self.check(runtime))

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
                              capture_output=True, text=True, env=dict(self.git_env, DDL_GATE_STATE_DIR=self.state))
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
        env = dict(os.environ, DDL_GATE_STATE_DIR=self.state)
        for data in ({"operations": []}, {"operations": [{"cwd": str(self.repo), "command": "git commit -m x"}]}):
            proc = subprocess.run([sys.executable, "-I", GATE, "prepare-git-review", "--runtime", "codex"],
                                  input=json.dumps(data), capture_output=True, text=True, env=env)
            self.assertEqual(proc.returncode, 2)
            self.assertIn("DDL Git review", proc.stderr)


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
                for source in ("startup", "compact", "resume"):
                    self.assert_allowed(self.run_gate("session-start", runtime, payload(runtime, "session-start", closed,
                                                                                        session, root, source=source)))
                self.assert_allowed(self.run_gate("user-prompt-submit", runtime, payload(runtime, "user-prompt-submit",
                                                                                         closed, session, root, prompt="go")))
                self.assertEqual(self.state_files(), sorted(seen))  # no .pending, .warned or .git-epoch

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
        heavy = {"subprocess", "hashlib", "shlex", "shutil", "secrets", "pathlib", "urllib", "urllib.parse", "typing"}
        for runtime in ("claude", "codex"):
            for event in ("pre-tool-use", "stop", "user-prompt-submit", "session-start"):
                with self.subTest(runtime=runtime, event=event):
                    data = payload(runtime, event, fixture(runtime + "_closed_in_turn.jsonl"), "lean", root, source="startup",
                                   last_assistant_message=REPORT_TEXT, prompt="go")
                    proc = subprocess.run([sys.executable, "-I", "-X", "importtime", GATE, event, "--runtime", runtime],
                                          input=json.dumps(data), capture_output=True, text=True,
                                          env=dict(os.environ, DDL_GATE_STATE_DIR=self.state))
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
