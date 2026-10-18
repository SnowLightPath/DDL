#!/usr/bin/env python3
"""Tests for tools/ddl_gate.py.

Unit tests import the module (shell allowlist, tool classification, the Claude human-prompt test,
the record readers). End-to-end tests run the hook as a subprocess with `python3 -I`, a private
state directory, and the hand-written transcript fixtures under tools/fixtures/.

Usage:
  python3 tools/test_ddl_gate.py
  python3 -I tools/test_ddl_gate.py
"""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

TOOLS = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import ddl_gate  # noqa: E402

GATE = str(TOOLS / "ddl_gate.py")
FIXTURES = TOOLS / "fixtures"
EVENT_NAMES = {"pre-tool-use": "PreToolUse", "session-start": "SessionStart", "stop": "Stop",
               "user-prompt-submit": "UserPromptSubmit"}
REPORT_TEXT = "+++DDL_REPORT\n\n## Realize report\n\nAwaiting approval."
SEGMENT_SUFFIX = " Shell segment is not read-only: `{}`."


def fixture(name):
    return str(FIXTURES / name)


def payload(runtime, event="pre-tool-use", transcript=None, session="sess", cwd=None, **extra):
    """A hook payload built from the runtime's template; other events drop the PreToolUse-only fields."""
    data = json.loads((FIXTURES / "payload_pre_tool_use_{}.json".format(runtime)).read_text())
    data["session_id"] = session
    data["transcript_path"] = transcript
    data["cwd"] = cwd or str(TOOLS)
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
    "FOO=1 env BAR=2 grep x y",
    "/usr/bin/env grep x f",
    "env",
    "FOO=bar",
    "git -C /repo --no-pager log --oneline -5",
    "git -c core.pager=cat diff --stat",
    "git branch -a",
    "git branch --show-current",
    "git ls-files tools",
    "git rev-parse HEAD; git show HEAD --stat; git blame -L 1,5 f; git check-ignore x; git grep foo",
    "find . -name '*.py' -newer x",
    "sed -n '1,10p' file",
    "sed -E 's/a/b/' file",
    "awk -F'|' '{print $1}' f",
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
    ("awk 'BEGIN{system(\"rm x\")}'", None),
    ("awk '{print | \"tee f\"}' x", None),
    ("sort -o out in", None),
    ("sort --output=out in", None),
    ("uniq in out", None),
    ("codex exec 'do it'", None),
    ("claude -p hi", None),
    ("date -s 12:00", None),
    ("rg --pre cat foo", None),
    ("xargs rm", None),
    ("bash -c 'ls'", None),
    ("env -i rm x", None),
    ("timeout 5 ls", None),
    ("/usr/bin/env python3 x.py", None),
    ("touch x", None),
    ("mv a b", None),
    ("cp a b", None),
    ("chmod +x f", None),
    ("rm x", None),
    ("mkdir -p x", None),
    ("nonexistent-tool arg", None),
    ("cat <<EOF\nhello\nEOF", "hello"),  # heredoc bodies are not parsed, so they fail closed
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
                     "mcp__x__y", "FooTool", None):
            with self.subTest(tool=name):
                self.assertEqual(ddl_gate.is_mutating("claude", name, {}), (True, ""))

    def test_claude_bash(self):
        self.assertEqual(ddl_gate.is_mutating("claude", "Bash", {"command": "git status"}), (False, ""))
        self.assertEqual(ddl_gate.is_mutating("claude", "Bash", {"command": "rm x"}), (True, "rm x"))
        self.assertEqual(ddl_gate.is_mutating("claude", "Bash", {}), (True, ""))
        self.assertEqual(ddl_gate.is_mutating("claude", "Bash", None), (True, ""))
        self.assertEqual(ddl_gate.is_mutating("claude", "Bash", '{"command": "ls"}'), (False, ""))

    def test_codex_tools(self):
        for name in ("apply_patch", "spawn_agent", "Agent", "mcp__srv__tool", "update_plan"):
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
    "claude_plan_approved.jsonl": False,
    "claude_plan_rejected.jsonl": True,
    "codex_open.jsonl": False,
    "codex_closed_in_turn.jsonl": True,
    "codex_previous_turn_report.jsonl": False,
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
        env = dict(os.environ, DDL_GATE_STATE_DIR=self.state)
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

    def project(self, design=True, git=False, sub=None):
        """A temp project dir; `.git` bounds the design.md search so the test dir's parents never count."""
        root = pathlib.Path(self.tmp) / "proj"
        root.mkdir()
        if git:
            (root / ".git").mkdir()
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
        self.assert_allowed(self.run_gate("session-start", "codex", payload("codex", "session-start", None, cwd=cwd, source="startup")))


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
