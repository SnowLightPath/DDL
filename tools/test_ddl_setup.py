#!/usr/bin/env python3
"""Installer/configuration integration tests, using disposable homes and projects only.

Run separately from doctor: python3 -I tools/test_ddl_setup.py. Doctor runs the gate suite,
never this suite, so its install/doctor/uninstall rehearsal cannot recurse. Hook dispatch
uses the saved runtime matchers and commands; payload tool commands are never executed.
"""
import contextlib
import io
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bin"))
import ddl_setup  # noqa: E402

SETUP = ROOT / "bin/ddl_setup.py"
FIXTURES = ROOT / "tools/fixtures"
REPORT = "+++DDL_REPORT\n\n## Realize report\n\nAwaiting approval."
RUNTIMES = {
    "claude": {"home": ".claude", "settings": "settings.json", "project_settings": ".claude/settings.json",
               "instruction": ".claude/CLAUDE.md", "gate": ".claude/hooks/ddl_gate.py",
               "legacy_matcher": "^(Edit|Write|NotebookEdit|Bash|Agent|SendMessage|TaskCreate|TaskUpdate|mcp__.*)$"},
    "codex": {"home": ".codex", "settings": "hooks.json", "project_settings": ".codex/hooks.json",
              "instruction": "AGENTS.md", "gate": ".codex/hooks/ddl_gate.py",
              "legacy_matcher": "^(apply_patch|Bash|shell|exec_command|local_shell|shell_command|spawn_agent|mcp__.*)$"},
}


class SetupTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ddl setup test ")
        self.addCleanup(self.tmp.cleanup)
        self.base = pathlib.Path(self.tmp.name)
        self.home = self.base / "home"
        self.home.mkdir()
        self.state = self.base / "state"
        self.env = dict(os.environ, HOME=str(self.home), CODEX_HOME=str(self.home / ".codex"),
                        DDL_GATE_STATE_DIR=str(self.state), TMPDIR=str(self.base),
                        XDG_CONFIG_HOME=str(self.home / ".config"), XDG_CACHE_HOME=str(self.home / ".cache"))
        # Native policy checks are deterministic even on machines without the Codex executable.
        self.fake_bin = self.base / "bin"
        self.fake_bin.mkdir()
        codex = self.fake_bin / "codex"
        codex.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, pathlib, sys\n"
            "args = sys.argv[1:]\n"
            "if args[:2] != ['execpolicy', 'check']: sys.exit(2)\n"
            "with pathlib.Path(os.environ['DDL_TEST_POLICY_LOG']).open('a') as log:\n"
            "    log.write(json.dumps(args) + '\\n')\n"
            "result = ({'decision': os.environ.get('DDL_TEST_POLICY_DECISION', 'prompt')}\n"
            "          if args[-2:] == ['git', 'push'] else {'matchedRules': []})\n"
            "print(json.dumps(result))\n")
        codex.chmod(0o755)
        self.policy_log = self.base / "policy.jsonl"
        self.env.update(PATH=str(self.fake_bin) + os.pathsep + os.environ.get("PATH", ""),
                        DDL_TEST_POLICY_LOG=str(self.policy_log))

    def cli(self, command, *options, expected=0):
        proc = subprocess.run([sys.executable, "-I", str(SETUP), command, *options],
                              env=self.env, cwd=self.base, capture_output=True, text=True, timeout=90)
        self.assertEqual(proc.returncode, expected, proc.stdout + proc.stderr)
        return proc.stdout

    def settings_path(self, runtime):
        rt = RUNTIMES[runtime]
        return self.home / rt["home"] / rt["settings"]

    def read_settings(self, runtime):
        return json.loads(self.settings_path(runtime).read_text())

    def install(self):
        return self.cli("install", "--claude", "--codex")

    def write_settings(self, runtime, data):
        path = self.settings_path(runtime)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data) + "\n")

    def dispatch(self, config, event, payload, cwd, project=None):
        """Independent dispatch through the persisted matcher and command, including unknown tools."""
        env = dict(self.env, CLAUDE_PROJECT_DIR=str(project or cwd))
        payload = dict(payload, hook_event_name=event)
        matched, outputs = 0, []
        value = payload.get("tool_name", "") if event == "PreToolUse" else payload.get("source", "")
        for group in config["hooks"].get(event, []):
            matcher = group.get("matcher")
            if matcher not in (None, "", "*") and not re.search(matcher, value):
                continue
            for hook in group["hooks"]:
                if "ddl_gate.py" not in hook.get("command", ""):
                    continue
                matched += 1
                proc = subprocess.run(hook["command"], shell=True, input=json.dumps(payload), env=env,
                                      cwd=cwd, capture_output=True, text=True, timeout=10)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertEqual(proc.stderr, "")
                if proc.stdout.strip():
                    outputs.append(json.loads(proc.stdout))
        self.assertEqual(matched, 1, f"{event}: expected exactly one matching DDL hook for {value!r}")
        return outputs

    def payload(self, runtime, project, transcript, **fields):
        data = {"session_id": "setup-" + runtime, "turn_id": "turn-1", "transcript_path": str(transcript),
                "cwd": str(project), "permission_mode": "default", "tool_name": "FutureMutatingTool", "tool_input": {}}
        data.update(fields)
        return data

    def assert_denied(self, outputs):
        self.assertEqual(len(outputs), 1, outputs)
        self.assertEqual(outputs[0]["hookSpecificOutput"]["permissionDecision"], "deny")

    def lifecycle(self, runtime, config, project, nested):
        transcript = self.base / (runtime + "-transcript.jsonl")
        closed = FIXTURES / (runtime + "_closed_in_turn.jsonl")
        answered = FIXTURES / ("claude_dialog_answer.jsonl" if runtime == "claude" else "codex_question_answer.jsonl")
        shutil.copyfile(closed, transcript)
        data = self.payload(runtime, nested, transcript)
        self.assertEqual(self.dispatch(config, "Stop", dict(data, last_assistant_message=REPORT), nested, project), [])
        self.assert_denied(self.dispatch(config, "PreToolUse", data, nested, project))
        # Clarification tools can continue while the STOP is pending.
        clarification = "AskUserQuestion" if runtime == "claude" else "request_user_input_async"
        self.assertEqual(self.dispatch(config, "PreToolUse", dict(data, tool_name=clarification), nested, project), [])
        self.assert_denied(self.dispatch(config, "PreToolUse", data, nested, project))
        if runtime == "codex":
            shutil.copyfile(FIXTURES / "codex_question_receipt.jsonl", transcript)
            self.assert_denied(self.dispatch(config, "PreToolUse", data, nested, project))
        # A native human answer is distinct from the receipt. Its configured prompt event clears the marker.
        shutil.copyfile(answered, transcript)
        prompt = dict(data, prompt="native question answer")
        self.assertEqual(self.dispatch(config, "UserPromptSubmit", prompt, nested, project), [])
        self.assertFalse((self.state / (data["session_id"] + ".pending")).exists())
        self.assertEqual(self.dispatch(config, "PreToolUse", data, nested, project), [])

    def test_empty_home_install_doctor_uninstall(self):
        self.install()
        for runtime, rt in RUNTIMES.items():
            with self.subTest(runtime=runtime):
                self.assertTrue((self.home / rt["gate"]).is_symlink())
                self.assertTrue(self.settings_path(runtime).is_file())
        out = self.cli("doctor", "--claude", "--codex")
        self.assertRegex(out, r"\d+ OK, 0 not OK")
        self.assertIn("codex native execpolicy check: git push -> prompt", out)
        self.assertIn("codex native execpolicy check: git -C /tmp push -> no matching rule", out)
        self.assertEqual(out.count("deny (independent push guard)"), 2)
        checks = [json.loads(line) for line in self.policy_log.read_text().splitlines()]
        self.assertEqual([args[4:] for args in checks], [["git", "push"], ["git", "-C", "/tmp", "push"]])
        self.cli("uninstall", "--claude", "--codex")
        for runtime, rt in RUNTIMES.items():
            with self.subTest(runtime=runtime):
                self.assertFalse(self.settings_path(runtime).exists())
                self.assertFalse((self.home / rt["gate"]).is_symlink())
        self.assertFalse(self.state.exists(), "doctor must keep probe state in its disposable directory")

    def test_unrelated_settings_hooks_and_files_survive_reinstall_and_uninstall(self):
        original, installed = {}, {}
        for runtime, rt in RUNTIMES.items():
            original[runtime] = {
                "hooks": {"PreToolUse": [{"matcher": "Read", "hooks": [{"type": "command", "command": "echo unrelated"}]}],
                          "OtherEvent": [{"hooks": [{"type": "command", "command": "echo retained"}]}]},
                "env": {"UNRELATED": "kept"}, "permissions": {"ask": ["Bash(custom *)"]},
                "otherSetting": {"keep": True},
            }
            self.write_settings(runtime, original[runtime])
            custom = self.home / rt["home"] / "skills/custom/SKILL.md"
            custom.parent.mkdir(parents=True)
            custom.write_text("unrelated skill\n")
        self.install()
        for runtime in RUNTIMES:
            installed[runtime] = self.settings_path(runtime).read_bytes()
            config = self.read_settings(runtime)
            self.assertEqual(config["hooks"]["PreToolUse"][0], original[runtime]["hooks"]["PreToolUse"][0])
            self.assertEqual(config["hooks"]["OtherEvent"], original[runtime]["hooks"]["OtherEvent"])
            backup = self.settings_path(runtime).with_name(self.settings_path(runtime).name + ".ddl-backup")
            self.assertEqual(json.loads(backup.read_text()), original[runtime])
        self.install()
        for runtime in RUNTIMES:
            self.assertEqual(self.settings_path(runtime).read_bytes(), installed[runtime])
        self.cli("uninstall", "--claude", "--codex")
        for runtime, rt in RUNTIMES.items():
            self.assertEqual(self.read_settings(runtime), original[runtime])
            self.assertEqual((self.home / rt["home"] / "skills/custom/SKILL.md").read_text(), "unrelated skill\n")

    def test_legacy_narrow_matchers_are_replaced_once(self):
        for runtime, rt in RUNTIMES.items():
            self.write_settings(runtime, {"hooks": {"PreToolUse": [
                {"matcher": rt["legacy_matcher"], "hooks": [{"type": "command", "command": "python3 /old/ddl_gate.py pre-tool-use"}]}]}})
        self.install()
        for runtime in RUNTIMES:
            groups = self.read_settings(runtime)["hooks"]["PreToolUse"]
            self.assertEqual(len(groups), 1)
            self.assertNotEqual(groups[0].get("matcher"), RUNTIMES[runtime]["legacy_matcher"])
            self.assertNotIn("/old/", groups[0]["hooks"][0]["command"])
        self.install()
        for runtime in RUNTIMES:
            self.assertEqual(len(self.read_settings(runtime)["hooks"]["PreToolUse"]), 1)

    def test_installed_configs_enforce_stop_and_resume_for_both_runtimes(self):
        self.install()
        project = self.base / "project"
        nested = project / "src/pkg"
        nested.mkdir(parents=True)
        for runtime in RUNTIMES:
            with self.subTest(runtime=runtime):
                self.lifecycle(runtime, self.read_settings(runtime), project, nested)

    def test_project_copies_run_from_nested_git_directory_and_keep_instructions(self):
        project = self.base / "project with spaces"
        nested = project / "src/pkg"
        nested.mkdir(parents=True)
        subprocess.run(["git", "init", "--quiet", str(project)], env=self.env, check=True, capture_output=True)
        for rt in RUNTIMES.values():
            instruction = project / rt["instruction"]
            instruction.parent.mkdir(parents=True, exist_ok=True)
            instruction.write_text("Keep the project's existing instructions.\n")
        self.cli("install", "--project", str(project))
        first = {runtime: (project / rt["project_settings"]).read_bytes() for runtime, rt in RUNTIMES.items()}
        self.cli("install", "--project", str(project))
        for runtime, rt in RUNTIMES.items():
            with self.subTest(runtime=runtime):
                self.assertEqual((project / rt["instruction"]).read_text(), "Keep the project's existing instructions.\n")
                self.assertFalse((project / rt["gate"]).is_symlink())
                self.assertEqual((project / rt["project_settings"]).read_bytes(), first[runtime])
                config = json.loads(first[runtime])
                self.lifecycle(runtime, config, project, nested)
                transcript = self.base / (runtime + "-transcript.jsonl")
                data = self.payload(runtime, nested, transcript, source="resume")
                (project / "design.md").write_text("# Disposable project design\n")
                outputs = self.dispatch(config, "SessionStart", data, nested, project)
                if runtime == "codex":
                    self.assertIn("Disposable project design", outputs[0]["hookSpecificOutput"]["additionalContext"])
                else:
                    self.assertEqual(outputs, [])
        self.assertFalse((self.home / ".claude").exists())
        self.assertFalse((self.home / ".codex").exists())

    def test_doctor_fails_native_canonical_rule_without_confusing_hook_guard(self):
        self.install()
        self.env["DDL_TEST_POLICY_DECISION"] = "allow"
        out = self.cli("doctor", "--codex", expected=1)
        self.assertIn("git push -> allow (expected prompt)", out)
        self.assertEqual(out.count("deny (independent push guard)"), 2)
        self.assertIn("1 not OK", out)

    def test_doctor_rejects_missing_independent_guard_and_explicit_allow(self):
        # A synthetic installed hook verifies diagnostic failure behavior without editing sources.
        base = self.base / "standin"
        gate = base / "hooks/ddl_gate.py"
        gate.parent.mkdir(parents=True)
        settings = {"hooks": {"PreToolUse": [{"matcher": ".*", "hooks": [{
            "type": "command", "command": 'python3 "$HOME/.codex/hooks/ddl_gate.py"'}]}]}}
        for body, ok, bad in [("", 1, 2),
                              ('print(\'{"hookSpecificOutput":{"permissionDecision":"allow"}}\')\n', 0, 3)]:
            with self.subTest(body=body):
                gate.write_text(body)
                report = ddl_setup.Report()
                with contextlib.redirect_stdout(io.StringIO()):
                    ddl_setup.doctor_push_hooks("codex", base, settings, report)
                self.assertEqual((report.ok, report.bad), (ok, bad))

    def test_dry_run_creates_no_runtime_files(self):
        self.cli("install", "--claude", "--codex", "--dry-run")
        self.assertEqual(list(self.home.iterdir()), [])


if __name__ == "__main__":
    unittest.main(verbosity=1)
