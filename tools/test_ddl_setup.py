#!/usr/bin/env python3
"""Installer/configuration integration tests, using disposable homes and projects only.

Run separately from doctor: python3 -I tools/test_ddl_setup.py. Doctor runs the gate suite,
never this suite, so its install/doctor/uninstall rehearsal cannot recurse. Hook dispatch
uses the saved runtime matchers and commands; payload tool commands are never executed.
The installer links and copies the generated dist/ of this checkout, so the suite builds it
from the source (tools/build.py) before the first test.
"""
import contextlib
import importlib.util
import io
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import stat
import tempfile
import time
import unittest
import warnings
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bin"))
import ddl_setup  # noqa: E402

SETUP = ROOT / "bin/ddl_setup.py"
BUILD = ROOT / "tools/build.py"


def setUpModule():
    """RUNTIMES point into dist/: generate it from the source before installing from this checkout."""
    if not BUILD.is_file():
        raise unittest.SkipTest("tools/build.py missing: dist/ cannot be built for the installer")
    spec = importlib.util.spec_from_file_location("ddl_build", BUILD)
    build = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build)
    if not hasattr(build, "write"):
        raise unittest.SkipTest("tools/build.py lacks write() yet: dist/ cannot be built for the installer")
    build.write(ROOT)
FIXTURES = ROOT / "tools/fixtures"
AUDIT = "== exit audit"


def summary(exits, wrappers, counted="not counted", unaudited=0):
    """The exit audit's summary line, the one before doctor's last line."""
    unread = f", {unaudited} not audited" if unaudited else ""
    return f"info      exit audit: {exits} exit, {wrappers} wrapper{unread} in user settings ({counted})"


def gate_module():
    """tools/ddl_gate.py as a module (read only): the grant store doctor checks must be the gate's."""
    spec = importlib.util.spec_from_file_location("ddl_gate_for_setup_test", ROOT / "tools/ddl_gate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ROOT_USER = hasattr(os, "geteuid") and os.geteuid() == 0  # file modes do not stop root: those tests are skipped


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
        # The durable grant store is isolated like the state directory: no test reaches the real one.
        self.grants = self.base / "grants"
        self.env = dict(os.environ, HOME=str(self.home), CODEX_HOME=str(self.home / ".codex"),
                        DDL_GATE_STATE_DIR=str(self.state), DDL_GATE_GRANT_DIR=str(self.grants), TMPDIR=str(self.base),
                        XDG_CONFIG_HOME=str(self.home / ".config"), XDG_CACHE_HOME=str(self.home / ".cache"),
                        XDG_STATE_HOME=str(self.home / ".local/state"))
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
                              env=self.env, cwd=self.base, capture_output=True, text=True, timeout=300)
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

    def allow(self, *rules):
        """Set permissions.allow of the Claude Code user settings, keeping every other entry."""
        path = self.settings_path("claude")
        settings = json.loads(path.read_text()) if path.exists() else {}
        settings.setdefault("permissions", {})["allow"] = list(rules)
        self.write_settings("claude", settings)

    def codex_file(self, name, text):
        path = self.home / ".codex" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def in_home(self, call, *args, **kwargs):
        """Run one installer function in this process against the disposable home: (result, output)."""
        out = io.StringIO()
        with mock.patch.dict(os.environ, self.env, clear=True), contextlib.redirect_stdout(out):
            result = call(*args, **kwargs)
        return result, out.getvalue()

    def audit(self, *runtimes, strict=False):
        """doctor's exit audit alone: (printed lines, the report with its counts)."""
        report = ddl_setup.Report()
        _, out = self.in_home(ddl_setup.doctor_exit_audit, list(runtimes) or list(RUNTIMES), report, strict)
        return out.splitlines(), report

    def doctor(self, *options):
        """The whole doctor in this process: (exit code, printed lines).

        Only the run of the gate's own suite is replaced (it takes more than a minute, and one
        command-line test runs it for real); every other check runs as installed.
        """
        cwd = os.getcwd()
        os.chdir(self.base)
        try:
            with mock.patch.object(ddl_setup, "gate_suite", return_value=(True, "OK")):
                code, out = self.in_home(ddl_setup.main, ["doctor", *options])
        finally:
            os.chdir(cwd)
        return code, out.splitlines()

    def run_main(self, command, *options):
        """install or uninstall in this process: (exit code, printed text)."""
        return self.in_home(ddl_setup.main, [command, *options])

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
        # While the STOP is pending only the prepared question may be asked; a bare question is denied.
        clarification = "AskUserQuestion" if runtime == "claude" else "request_user_input_async"
        outputs = self.dispatch(config, "PreToolUse", dict(data, tool_name=clarification), nested, project)
        self.assert_denied(outputs)
        self.assertEqual(outputs[0]["hookSpecificOutput"]["permissionDecisionReason"],
                         "DDL STOP: prepare the report and ask its question")
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
        self.assertFalse(self.grants.exists(), "install must leave the grant store to the gate hook")
        out = self.cli("doctor", "--claude", "--codex")
        self.assertRegex(out, r"\d+ OK, 0 not OK")
        self.assertEqual(out.splitlines()[-2], summary(0, 0))
        self.assertRegex(out.splitlines()[-1], r"^\d+ OK, 0 not OK$")
        self.assertIn(f"info      grant store {self.grants} absent", out)
        self.assertIn("codex native execpolicy check: git push -> prompt", out)
        self.assertIn("codex native execpolicy check: git -C /tmp push -> no matching rule", out)
        self.assertEqual(out.count("deny (independent Git review)"), 10)
        checks = [json.loads(line) for line in self.policy_log.read_text().splitlines()]
        self.assertEqual([args[4:] for args in checks], [["git", "push"], ["git", "-C", "/tmp", "push"]])
        self.cli("uninstall", "--claude", "--codex")
        for runtime, rt in RUNTIMES.items():
            with self.subTest(runtime=runtime):
                self.assertFalse(self.settings_path(runtime).exists())
                self.assertFalse((self.home / rt["gate"]).is_symlink())
        self.assertFalse(self.state.exists(), "doctor must keep probe state in its disposable directory")
        self.assertFalse(self.grants.exists(), "doctor must keep probe grants in its disposable directory")

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
        (project / "CLAUDE.md").write_text("→ DDL-PROTOCOL\n")  # the gate acts only in a DDL project
        for runtime in RUNTIMES:
            with self.subTest(runtime=runtime):
                self.lifecycle(runtime, self.read_settings(runtime), project, nested)

    def test_project_copies_run_from_nested_git_directory_and_keep_instructions(self):
        project = self.base / "project with spaces"
        nested = project / "src/pkg"
        nested.mkdir(parents=True)
        (project / "CLAUDE.md").write_text("→ DDL-PROTOCOL\n")  # the gate acts only in a DDL project
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
        code, lines = self.doctor("--codex")
        out = "\n".join(lines)
        self.assertEqual(code, 1, out)
        self.assertIn("git push -> allow (expected prompt)", out)
        self.assertEqual(out.count("deny (independent Git review)"), 6)
        self.assertRegex(lines[-1], r"^\d+ OK, 1 not OK$")

    def test_doctor_rejects_missing_independent_guard_and_explicit_allow(self):
        # A synthetic installed hook verifies diagnostic failure behavior without editing sources.
        base = self.base / "standin"
        gate = base / "hooks/ddl_gate.py"
        gate.parent.mkdir(parents=True)
        settings = {"hooks": {"PreToolUse": [{"matcher": ".*", "hooks": [{
            "type": "command", "command": 'python3 "$HOME/.codex/hooks/ddl_gate.py"'}]}]}}
        for body, ok, bad in [("", 0, 6),
                              ('print(\'{"hookSpecificOutput":{"permissionDecision":"allow"}}\')\n', 0, 6)]:
            with self.subTest(body=body):
                gate.write_text(body)
                report = ddl_setup.Report()
                with contextlib.redirect_stdout(io.StringIO()):
                    ddl_setup.doctor_git_hooks("codex", base, settings, report)
                self.assertEqual((report.ok, report.bad), (ok, bad))

    def test_dry_run_creates_no_runtime_files(self):
        self.cli("install", "--claude", "--codex", "--dry-run")
        self.assertEqual(list(self.home.iterdir()), [])
        self.assertFalse(self.grants.exists())

    # ---- doctor's exit audit ----

    def test_clean_allow_list_reports_no_finding(self):
        self.install()
        self.allow("Bash(ls:*)", "Bash(git status)", "Bash(git commit:*)", "Bash(gh pr view:*)",
                   "Bash(python3 tools/build.py:*)", "Read", "WebFetch(domain:example.com)")
        code, lines = self.doctor("--claude", "--codex")
        self.assertEqual(code, 0, lines)
        self.assertEqual(lines[lines.index(AUDIT):-1], [AUDIT, summary(0, 0)])
        self.assertRegex(lines[-1], r"^\d+ OK, 0 not OK$")
        # The gate part carries the grant store line; the store is absent until the hook needs it.
        gate = lines[lines.index("== gate"):lines.index(AUDIT)]
        self.assertEqual([line for line in gate if "grant store" in line],
                         [f"info      grant store {self.grants} absent (the gate creates it when it first records a grant)"])

    def test_findings_name_the_file_the_place_of_the_rule_and_what_passes(self):
        self.write_settings("claude", {"permissions": {"allow": [
            "Bash(git push:*)", "Read", "Bash(env:*)", "Bash(ls:*)", "Bash(git cherry-pick:*)", "Bash",
            "Bash(FOO=1 *)", "Bash(/usr/bin/*)"]}})
        name = "~/.claude/settings.json: permissions.allow"
        lines, report = self.audit("claude")
        self.assertEqual(lines, [
            AUDIT,
            f"exit      {name}[0] Bash(git push …) passes git push unasked",
            f"wrapper   {name}[2] Bash(env …) wraps any command",
            f"exit      {name}[4] Bash(git cherry-pick …) passes git cherry-pick unasked",
            f"wrapper   {name}[5] Bash wraps any command",
            f"wrapper   {name}[6] Bash(FOO=…) wraps any command",
            f"wrapper   {name}[7] Bash(…/bin/* …) passes every program of a directory unasked",
            summary(2, 4)])
        self.assertEqual((report.ok, report.bad), (0, 0))
        lines, report = self.audit("claude", strict=True)
        self.assertEqual(lines[-1], summary(2, 4, "counted"))
        self.assertEqual((report.ok, report.bad), (0, 6))
        # Only the selected host is read.
        self.assertEqual(self.audit("codex")[0], [AUDIT, summary(0, 0)])

    def test_rules_under_ask_or_deny_are_never_findings(self):
        risky = ["Bash", "Bash(*)", "Bash(git push:*)", "Bash(env:*)", "Bash(curl:*)", "Bash(gh pr create:*)", "Bash(python3:*)"]
        self.write_settings("claude", {"permissions": {"allow": ["Bash(ls:*)"], "ask": risky, "deny": risky}})
        self.assertEqual(self.audit("claude")[0], [AUDIT, summary(0, 0)])
        self.write_settings("claude", {"permissions": {"allow": risky}})
        lines, _ = self.audit("claude")
        self.assertEqual(len(lines), len(risky) + 2, lines)
        self.assertEqual(lines[-1], summary(3, 4))

    def test_findings_leave_the_counts_and_the_exit_code_unchanged_unless_strict(self):
        self.install()
        self.allow("Bash(ls:*)")
        code, clean = self.doctor("--claude", "--codex")
        self.assertEqual(code, 0, clean)
        self.assertRegex(clean[-1], r"^\d+ OK, 0 not OK$")
        self.allow("Bash(ls:*)", "Bash(git push:*)", "Bash(sudo:*)")
        self.codex_file("rules/default.rules", 'prefix_rule(pattern=["gh", "pr", "create"], decision="allow")\n')
        code, found = self.doctor("--claude", "--codex")
        self.assertEqual(code, 0, found)
        self.assertEqual(found[-1], clean[-1])
        self.assertEqual(found[found.index(AUDIT):-1], [
            AUDIT,
            "exit      ~/.claude/settings.json: permissions.allow[1] Bash(git push …) passes git push unasked",
            "wrapper   ~/.claude/settings.json: permissions.allow[2] Bash(sudo …) wraps any command",
            "exit      ~/.codex/rules/default.rules:1: prefix_rule(gh pr create …) passes gh pr create unasked",
            summary(2, 1)])
        # What the other checks print does not depend on the findings.
        self.assertEqual(found[:found.index(AUDIT)], clean[:clean.index(AUDIT)])
        code, strict = self.doctor("--claude", "--codex", "--strict")
        self.assertEqual(code, 1, strict)
        self.assertEqual(strict[-1], clean[-1].replace(", 0 not OK", ", 3 not OK"))
        self.assertEqual(strict[:-2], found[:-2])
        self.assertEqual(strict[-2], summary(2, 1, "counted"))
        self.assertEqual([line for line in strict if line.startswith("not OK")], [])

    def test_strict_exits_1_and_applies_to_doctor_only(self):
        # The gate's suite is stubbed here; test_empty_home_install_doctor_uninstall is the one
        # command-line doctor run that executes it. main's return value is the process's exit status.
        self.install()
        self.allow("Bash(git push:*)", "Bash(sudo:*)")
        code, lines = self.doctor("--claude", "--strict")
        self.assertEqual(code, 1, lines)
        self.assertIn("exit      ~/.claude/settings.json: permissions.allow[0] Bash(git push …) passes git push unasked", lines)
        self.assertIn("wrapper   ~/.claude/settings.json: permissions.allow[1] Bash(sudo …) wraps any command", lines)
        self.assertEqual(lines[-2], summary(1, 1, "counted"))
        self.assertRegex(lines[-1], r"^\d+ OK, 2 not OK$")
        self.assertEqual([line for line in lines if line.startswith("not OK")], [])
        for command in ("install", "uninstall"):
            with self.subTest(command=command):
                self.cli(command, "--claude", "--strict", expected=2)

    def test_strict_counts_what_the_audit_could_not_read(self):
        self.write_settings("claude", {"permissions": {"defaultMode": "bypassPermissions", "allow": [
            'Bash(echo "unclosed:*)', "Bash(ls:*)", "Bash($RUNNER test:*)", "Bash(" + "sudo " * 10 + "ls)"]}})
        self.codex_file("rules/broken.rules", 'prefix_rule(pattern = ["git", "push"\n')
        self.codex_file("rules/names.rules", 'PUSH = ["git", "push"]\nprefix_rule(pattern=PUSH)\n')
        self.codex_file("rules/quote.rules", 'prefix_rule(pattern=["bash", "-lc", "git log \\"unclosed"])\n')
        self.codex_file("rules/wide.rules", "prefix_rule(pattern=[" + ", ".join(['["a", "b"]'] * 9) + "])\n")
        self.codex_file("config.toml", 'approval_policy = "never"\nsandbox_mode = "danger-full-access"\n')
        unread = [
            "~/.claude/settings.json: permissions.allow[0] Bash rule whose quoting does not close; not audited",
            "~/.claude/settings.json: permissions.allow[2] Bash rule whose program is a variable; not audited",
            "~/.claude/settings.json: permissions.allow[3] Bash rule that nests commands deeper than the audit follows; not audited",
            "~/.codex/rules/broken.rules: cannot be read as prefix_rule calls; not audited",
            "~/.codex/rules/names.rules:2: prefix_rule whose decision or pattern is not a plain literal; not audited",
            "~/.codex/rules/quote.rules:1: prefix_rule whose quoting does not close; not audited",
            "~/.codex/rules/wide.rules:1: prefix_rule with more than 256 alternatives; not audited"]
        # The user chose a mode that asks before nothing: that stays information and is never counted.
        chosen = ['info      ~/.claude/settings.json: permissions.defaultMode "bypassPermissions": '
                  "Claude Code asks before no command (information only)",
                  'info      ~/.codex/config.toml: approval_policy "never" with sandbox_mode "danger-full-access": '
                  "Codex asks before no command and sandboxes none (information only)"]
        for strict, word, counted in ((False, "info      ", "not counted"), (True, "not OK    ", "counted")):
            with self.subTest(strict=strict):
                lines, report = self.audit(strict=strict)
                self.assertEqual(lines, [AUDIT, *[word + line for line in unread[:3]], chosen[0],
                                         *[word + line for line in unread[3:]], chosen[1],
                                         summary(0, 0, counted, unaudited=7)])
                self.assertEqual((report.ok, report.bad), (0, 7 if strict else 0))
        # Settings the audit cannot read as an object are not audited either, and strict says so.
        for text, words in (("{not json", "not valid JSON"), ("[]", "not a JSON object")):
            with self.subTest(text=text):
                self.settings_path("claude").write_text(text)
                line = f"~/.claude/settings.json: {words}; permissions.allow not audited"
                self.assertEqual(self.audit("claude")[0], [AUDIT, "info      " + line, summary(0, 0, unaudited=1)])
                lines, report = self.audit("claude", strict=True)
                self.assertEqual(lines, [AUDIT, "not OK    " + line, summary(0, 0, "counted", unaudited=1)])
                self.assertEqual((report.ok, report.bad), (0, 1))

    def test_a_settings_file_doctor_cannot_read_counts_twice_under_strict(self):
        self.install()
        self.settings_path("claude").write_text("{not json")
        code, lines = self.doctor("--claude", "--strict")
        self.assertEqual(code, 1, lines)
        bad = [line for line in lines if line.startswith("not OK")]
        self.assertEqual(len(bad), 2, lines)  # once for the check of the merged entries, once for the audit
        self.assertTrue(bad[0].startswith("not OK    ~/.claude/settings.json is not valid JSON ("), bad)
        self.assertEqual(bad[1], "not OK    ~/.claude/settings.json: not valid JSON; permissions.allow not audited")
        self.assertEqual(lines[-2], summary(0, 0, "counted", unaudited=1))
        self.assertRegex(lines[-1], r"^\d+ OK, 2 not OK$")
        # The module's own account names the summary's forms and this double count.
        account = " ".join(ddl_setup.__doc__.split())
        for phrase in ("`exit audit: N exit, M wrapper in user settings (not counted)`", "`, K not audited`", "`(counted)`",
                       "counts twice"):
            self.assertIn(phrase, account)

    def test_strict_exits_1_for_a_rule_it_could_not_read(self):
        self.install()
        self.allow("Bash(ls:*)", 'Bash(echo "unclosed:*)')
        code, lines = self.doctor("--claude")
        self.assertEqual(code, 0, lines)
        self.assertEqual(lines[-2], summary(0, 0, unaudited=1))
        code, lines = self.doctor("--claude", "--strict")
        self.assertEqual(code, 1, lines)
        self.assertEqual([line for line in lines if line.startswith("not OK")], [
            "not OK    ~/.claude/settings.json: permissions.allow[1] Bash rule whose quoting does not close; not audited"])
        self.assertRegex(lines[-1], r"^\d+ OK, 1 not OK$")

    def test_absent_settings_give_no_audit_line(self):
        self.assertEqual(self.audit()[0], [AUDIT, summary(0, 0)])
        for rt in RUNTIMES.values():
            (self.home / rt["home"]).mkdir()
        lines, report = self.audit()
        self.assertEqual(lines, [AUDIT, summary(0, 0)])
        self.assertEqual((report.ok, report.bad), (0, 0))

    def test_malformed_settings_keep_one_not_ok_and_the_other_host_is_still_audited(self):
        self.install()
        self.codex_file("rules/default.rules", 'prefix_rule(pattern=["git", "push"], decision="allow")\n')
        codex_finding = "exit      ~/.codex/rules/default.rules:1: prefix_rule(git push …) passes git push unasked"
        self.allow("Bash(curl:*)")
        claude_finding = "exit      ~/.claude/settings.json: permissions.allow[0] Bash(curl …) passes curl unasked"
        valid = self.settings_path("claude").read_text()
        self.settings_path("claude").write_text("{not json")
        code, lines = self.doctor("--claude", "--codex")
        self.assertEqual(code, 1, lines)
        bad = [line for line in lines if line.startswith("not OK")]
        self.assertEqual(len(bad), 1, lines)
        self.assertIn("~/.claude/settings.json is not valid JSON", bad[0])
        self.assertIn("== Codex (~/.codex)", lines)
        self.assertEqual(lines[lines.index(AUDIT):-1], [
            AUDIT, "info      ~/.claude/settings.json: not valid JSON; permissions.allow not audited",
            codex_finding, summary(1, 0, unaudited=1)])
        self.assertRegex(lines[-1], r"^\d+ OK, 1 not OK$")
        # The other way round: a malformed hooks.json of Codex skips neither host's audit.
        self.settings_path("claude").write_text(valid)
        self.settings_path("codex").write_text("[")
        code, lines = self.doctor("--claude", "--codex")
        self.assertEqual(code, 1, lines)
        bad = [line for line in lines if line.startswith("not OK")]
        self.assertEqual(len(bad), 1, lines)
        self.assertIn("~/.codex/hooks.json is not valid JSON", bad[0])
        self.assertEqual(lines[lines.index(AUDIT):-1], [AUDIT, claude_finding, codex_finding, summary(2, 0)])

    def test_wrong_typed_permissions_are_ignored_without_a_traceback(self):
        entries = [1, None, True, {"rule": "Bash"}, ["Bash(git push:*)"], "Bash(ls:*)"]
        for permissions in ("all", ["Bash"], 7, None, {"allow": "Bash"}, {"allow": {"Bash": True}},
                            {"allow": None}, {"allow": entries}):
            with self.subTest(permissions=permissions):
                self.write_settings("claude", {"permissions": permissions})
                self.assertEqual(self.audit("claude")[0], [AUDIT, summary(0, 0)])
        # A string beside the non-string entries is still read, and named by its own place in the list.
        self.write_settings("claude", {"permissions": {"allow": entries + ["Bash(git push:*)"]}})
        self.assertEqual(self.audit("claude")[0][1:], [
            "exit      ~/.claude/settings.json: permissions.allow[6] Bash(git push …) passes git push unasked", summary(1, 0)])
        # The whole doctor survives the wrong type as well.
        self.install()
        settings = self.read_settings("claude")
        settings["permissions"] = "all"
        self.write_settings("claude", settings)
        code, lines = self.doctor("--claude")
        self.assertEqual(code, 0, lines)
        self.assertEqual(lines[-2], summary(0, 0))

    # ---- settings doctor, install and uninstall cannot work with ----

    def test_doctor_names_settings_that_are_not_an_object_and_goes_on(self):
        self.install()
        self.codex_file("rules/default.rules", 'prefix_rule(pattern=["git", "push"])\n')
        for text, kind in (("[]", "a list"), ("null", "null"), ('"text"', "a string"), ("7", "a number"),
                           ("1.5", "a number"), ("true", "a boolean")):
            with self.subTest(text=text):
                self.settings_path("claude").write_text(text + "\n")
                code, lines = self.doctor("--claude", "--codex")
                self.assertEqual(code, 1, lines)
                self.assertEqual([line for line in lines if line.startswith("not OK")],
                                 [f"not OK    ~/.claude/settings.json is not a JSON object (its top level is {kind})"])
                # The run goes on: the other host, the gate part and the audit are all there.
                self.assertIn("== Codex (~/.codex)", lines)
                self.assertIn("== gate", lines)
                self.assertEqual(sum("deny (independent Git review)" in line for line in lines), 6)
                self.assertEqual(lines[lines.index(AUDIT):-1], [
                    AUDIT, "info      ~/.claude/settings.json: not a JSON object; permissions.allow not audited",
                    "exit      ~/.codex/rules/default.rules:1: prefix_rule(git push …) passes git push unasked",
                    summary(1, 0, unaudited=1)])
                self.assertRegex(lines[-1], r"^\d+ OK, 1 not OK$")

    def test_install_and_uninstall_refuse_settings_that_are_not_an_object(self):
        for runtime in RUNTIMES:
            name = f"~/{RUNTIMES[runtime]['home']}/{RUNTIMES[runtime]['settings']}"
            for text, problem in (("{not json", r"not valid JSON \(.+\)"), ("[]", r"not a JSON object \(its top level is a list\)"),
                                  ("null", r"not a JSON object \(its top level is null\)"),
                                  ('"text"', r"not a JSON object \(its top level is a string\)"),
                                  ("7", r"not a JSON object \(its top level is a number\)")):
                with self.subTest(runtime=runtime, text=text):
                    path = self.settings_path(runtime)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(text)
                    for command, tail in (("install", "fragment not merged"), ("uninstall", "fragment not removed")):
                        code, out = self.run_main(command, "--" + runtime)
                        self.assertEqual(code, 1, out)
                        self.assertRegex(out, rf"(?m)^not OK    {re.escape(name)} is {problem}; {tail}$")
                        self.assertEqual(path.read_text(), text, "a file that is no object is never rewritten")
                        self.assertFalse(path.with_name(path.name + ".ddl-backup").exists())
        # A refused file of one runtime does not keep the other from being installed, and the exit status still says so.
        self.settings_path("codex").unlink()
        code, out = self.run_main("install", "--claude", "--codex")
        self.assertEqual(code, 1, out)
        self.assertIn("OK        merge ~/.codex/hooks.json (updated)\n", out)
        self.assertEqual(self.settings_path("claude").read_text(), "7")
        # A line that is `not OK` for another reason leaves install's exit status as it was.
        self.settings_path("claude").unlink()
        blocked = self.home / ".claude/agents/worker.md"
        blocked.unlink()
        blocked.write_text("the user's own file\n")
        code, out = self.run_main("install", "--claude")
        self.assertEqual(code, 0, out)
        self.assertIn("not OK    ~/.claude/agents/worker.md exists and is not a symlink; move it away and run install again\n", out)
        self.assertEqual(blocked.read_text(), "the user's own file\n")
        blocked.unlink()
        self.settings_path("claude").write_text("7")
        # From the command line: the refusal is the exit status, with nothing on the error stream.
        for command in ("install", "uninstall"):
            with self.subTest(command=command):
                proc = subprocess.run([sys.executable, "-I", str(SETUP), command, "--claude"], env=self.env, cwd=self.base,
                                      capture_output=True, text=True, timeout=300)
                self.assertEqual((proc.returncode, proc.stderr), (1, ""), proc.stdout)
                self.assertIn("is not a JSON object", proc.stdout)

    def test_settings_that_cannot_be_written_back_are_refused_and_left_whole(self):
        # Python reads these; written back they would be no JSON, or no text at all.
        shapes = {"half a character": '"note": "\\ud83d"', "a number out of range": '"limit": 1e400', "not a number": '"limit": NaN'}
        reasons = {"half a character": "it holds text that is no valid Unicode"}
        for runtime in RUNTIMES:
            name = f"~/{RUNTIMES[runtime]['home']}/{RUNTIMES[runtime]['settings']}"
            path = self.settings_path(runtime)
            for label, entry in shapes.items():
                with self.subTest(runtime=runtime, shape=label):
                    if path.exists():
                        path.unlink()
                    self.assertEqual(self.run_main("install", "--" + runtime)[0], 0)
                    installed = path.read_text()
                    path.write_text(installed.replace("{", "{\n  " + entry + ",", 1))  # DDL's entries are in the file
                    self.assertIn("hooks", json.loads(path.read_text()))
                    before = path.read_bytes()
                    reason = reasons.get(label, "it holds a number outside JSON's range")
                    line = f"not OK    {name} is not JSON that can be written back ({reason})"
                    for command, tail in (("install", "; fragment not merged"), ("uninstall", "; fragment not removed"),
                                          ("install", "; fragment not merged")):
                        code, out = self.run_main(command, "--" + runtime)
                        self.assertEqual(code, 1, out)
                        self.assertIn(line + tail + "\n", out)
                        self.assertEqual(path.read_bytes(), before, "the file is left exactly as it was")
                        self.assertEqual(sorted(found.name for found in path.parent.iterdir() if found.is_file()), [path.name])
                    code, lines = self.doctor("--" + runtime)
                    self.assertEqual(code, 1, lines)
                    self.assertEqual([found for found in lines if found.startswith("not OK")], [line])
                    self.assertEqual(path.read_bytes(), before)

    def test_a_settings_file_gets_its_new_content_in_one_step(self):
        path = self.settings_path("claude")
        path.parent.mkdir(parents=True)
        path.write_text('{"keep": true}\n')
        path.chmod(0o600)
        report = ddl_setup.Report()

        def whole():
            return path.read_text() == '{"keep": true}\n' and [found.name for found in path.parent.iterdir()] == ["settings.json"]

        # A write that fails on the way leaves the old content, and nothing beside it.
        with mock.patch.object(ddl_setup.os, "replace", side_effect=OSError("no space left")), self.assertRaises(OSError):
            ddl_setup.write_json(path, {"new": 1}, report, backup=False)
        self.assertTrue(whole())
        with mock.patch.object(ddl_setup.shutil, "copymode", side_effect=KeyboardInterrupt), self.assertRaises(KeyboardInterrupt):
            ddl_setup.write_json(path, {"new": 1}, report, backup=False)
        self.assertTrue(whole())
        # Content that cannot be written is refused before anything is touched.
        with self.assertRaises(UnicodeEncodeError):
            ddl_setup.write_json(path, {"new": "\ud83d"}, report, backup=False)
        with self.assertRaises(ValueError):
            ddl_setup.write_json(path, {"new": float("inf")}, report, backup=False)
        self.assertTrue(whole())
        # A write that succeeds keeps the file's mode.
        self.assertTrue(ddl_setup.write_json(path, {"new": 1}, report, backup=False))
        self.assertEqual((json.loads(path.read_text()), stat.S_IMODE(path.stat().st_mode)), ({"new": 1}, 0o600))
        self.assertEqual([found.name for found in path.parent.iterdir()], ["settings.json"])
        self.assertFalse(ddl_setup.write_json(path, {"new": 1}, report, backup=False), "the same content is not written again")
        # A settings file kept elsewhere stays a link: its target gets the new content.
        elsewhere = self.base / "dotfiles/settings.json"
        elsewhere.parent.mkdir()
        elsewhere.write_text('{"otherSetting": 1}\n')
        path.unlink()
        path.symlink_to(elsewhere)
        code, out = self.run_main("install", "--claude", "--codex")
        self.assertEqual(code, 0, out)
        self.assertTrue(path.is_symlink())
        merged = json.loads(elsewhere.read_text())
        self.assertEqual((merged["otherSetting"], "PreToolUse" in merged["hooks"]), (1, True))
        self.assertEqual(path.with_name("settings.json.ddl-backup").read_text(), '{"otherSetting": 1}\n')
        self.assertEqual([found.name for found in elsewhere.parent.iterdir()], ["settings.json"])
        # A settings file DDL creates gets the mode any new file gets.
        mask = os.umask(0)
        os.umask(mask)
        self.assertEqual(stat.S_IMODE(self.settings_path("codex").stat().st_mode), 0o666 & ~mask)
        code, out = self.run_main("uninstall", "--claude", "--codex")
        self.assertEqual(code, 0, out)
        self.assertEqual((path.is_symlink(), json.loads(elsewhere.read_text())), (True, {"otherSetting": 1}))

    def test_entries_of_another_type_are_named_and_left_as_they_are(self):
        cases = [("claude", {"hooks": []}, "hooks is a list, not an object"),
                 ("claude", {"hooks": 3}, "hooks is a number, not an object"),
                 ("claude", {"hooks": None}, "hooks is null, not an object"),
                 ("claude", {"hooks": {"PreToolUse": {}}}, "hooks.PreToolUse is an object, not a list"),
                 ("claude", {"env": "x"}, "env is a string, not an object"),
                 ("claude", {"attribution": True}, "attribution is a boolean, not an object"),
                 ("codex", {"hooks": ["x"]}, "hooks is a list, not an object")]
        for runtime, odd, words in cases:
            with self.subTest(runtime=runtime, odd=odd):
                data = dict(odd, otherSetting={"keep": True})
                self.write_settings(runtime, data)
                path = self.settings_path(runtime)
                text = path.read_text()
                name = f"~/{RUNTIMES[runtime]['home']}/{RUNTIMES[runtime]['settings']}"
                problem = f"not OK    {name} is not shaped as DDL needs it ({words})"
                code, out = self.run_main("install", "--" + runtime)
                self.assertEqual(code, 1, out)
                self.assertIn(problem + "; fragment not merged\n", out)
                self.assertEqual(path.read_text(), text)
                code, lines = self.doctor("--" + runtime)
                self.assertEqual(code, 1, lines)
                self.assertEqual([line for line in lines if line.startswith("not OK") and name in line], [problem])
                self.assertEqual(lines[-2], summary(0, 0))
                # Nothing of DDL's can be in such an entry, so uninstall has nothing to refuse.
                code, out = self.run_main("uninstall", "--" + runtime)
                self.assertEqual(code, 0, out)
                self.assertEqual(path.read_text(), text)

    def test_uninstall_removes_its_entries_beside_an_entry_of_another_type(self):
        self.install()
        settings = self.read_settings("claude")
        settings["env"] = ["not", "an", "object"]
        settings["hooks"]["Notification"] = "not a list"
        settings["hooks"]["Stop"].insert(0, "not a group")
        self.write_settings("claude", settings)
        code, out = self.run_main("uninstall", "--claude")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.read_settings("claude"), {"env": ["not", "an", "object"],
                                                        "hooks": {"Notification": "not a list", "Stop": ["not a group"]}})

    def test_the_readers_of_settings_take_any_shape(self):
        frag = ddl_setup.fragment_for(ddl_setup.RUNTIMES["claude"])
        entries = len(frag["hooks"]) + len(frag["env"]) + len(frag["attribution"])
        odd_groups = ["x", 3, None, [], {"hooks": "y"}, {"hooks": [1, None, {"command": 5}, {}]}, {"matcher": 1}]
        for settings in ({"hooks": []}, {"hooks": "x"}, {"hooks": {"PreToolUse": {}}}, {"hooks": {"PreToolUse": odd_groups}},
                         {"env": []}, {"env": None}, {"attribution": 1}, {"permissions": []}, {"permissions": {"ask": {}}}):
            with self.subTest(settings=settings):
                present, missing, differing = ddl_setup.merged_state(settings, frag)
                self.assertEqual((present, differing, len(missing)), ([], [], entries))
                self.assertEqual(ddl_setup.unmerge(settings, frag), settings)
                with self.assertRaisesRegex(ValueError, "no configured DDL PreToolUse hook"):
                    ddl_setup.configured_hook_outputs(settings, "PreToolUse", {"tool_name": "Bash"}, {}, self.base)
        for group in odd_groups:
            self.assertFalse(ddl_setup.is_ddl_group(group))

    def test_settings_that_cannot_be_read_are_named_without_a_traceback(self):
        path = self.settings_path("claude")
        path.parent.mkdir(parents=True)

        def not_utf8():
            path.write_bytes(b'{"env": {"X": "\xff\xfe"}}\n')

        def a_directory():
            path.mkdir()

        def unreadable():
            path.write_text("{}\n")
            path.chmod(0)

        def a_number_too_long():
            path.write_text('{"limit": ' + "9" * 5000 + "}\n")

        def nested_too_deep():
            path.write_text("[" * 200000 + "\n")

        unread = "not valid JSON (a number too long or a nesting too deep to read)"
        cases = [(not_utf8, "not UTF-8 text", "not UTF-8 text"), (a_directory, "not readable (Is a directory)", "not readable"),
                 (nested_too_deep, unread, "not valid JSON")]
        if sys.version_info >= (3, 11):  # earlier versions read an integer of any length
            cases.append((a_number_too_long, unread, "not valid JSON"))
        if not ROOT_USER:
            cases.append((unreadable, "not readable (Permission denied)", "not readable"))
        for prepare, problem, short in cases:
            with self.subTest(case=prepare.__name__):
                prepare()
                line = f"not OK    ~/.claude/settings.json is {problem}"
                code, out = self.run_main("install", "--claude")
                self.assertEqual(code, 1, out)
                self.assertIn(line + "; fragment not merged\n", out)
                code, lines = self.doctor("--claude")
                self.assertEqual(code, 1, lines)
                self.assertEqual([found for found in lines if found.startswith("not OK")], [line])
                self.assertEqual(lines[lines.index(AUDIT):-1], [
                    AUDIT, f"info      ~/.claude/settings.json: {short}; permissions.allow not audited", summary(0, 0, unaudited=1)])
                code, out = self.run_main("uninstall", "--claude")
                self.assertEqual(code, 1, out)
                self.assertIn(line + "; fragment not removed\n", out)
                self.assertTrue(os.path.lexists(path), "what cannot be read is left in place")
                path.rmdir() if path.is_dir() else path.unlink()

    @unittest.skipIf(ROOT_USER, "file modes do not stop root")
    def test_a_runtime_home_nobody_may_search_gives_lines_not_a_traceback(self):
        self.install()
        claude = self.home / ".claude"
        claude.chmod(0)
        self.addCleanup(claude.chmod, 0o700)
        code, lines = self.doctor("--claude")
        self.assertEqual(code, 1, lines)
        self.assertIn("not OK    ~/.claude/settings.json is not readable (Permission denied)", lines)
        self.assertIn("not OK    ~/.claude/hooks/ddl_gate.py missing", lines)
        self.assertRegex(lines[-1], r"^\d+ OK, \d+ not OK$")
        for command in ("install", "uninstall"):
            with self.subTest(command=command):
                code, out = self.run_main(command, "--claude")
                self.assertEqual(code, 1, out)
                self.assertRegex(out, r"(?m)^not OK    .*Permission denied")

    def test_a_link_that_points_at_itself_is_a_line_not_a_traceback(self):
        self.install()
        link = self.home / ".claude/skills/draft"
        link.unlink()
        link.symlink_to(link)
        code, lines = self.doctor("--claude")
        self.assertEqual(code, 1, lines)
        self.assertEqual(len([line for line in lines if line.startswith("not OK    ~/.claude/skills/draft -> ")]), 1, lines)
        code, out = self.run_main("install", "--claude")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.doctor("--claude")[0], 0)

    # ---- what a printed line may carry ----

    def test_no_printed_line_carries_the_text_of_a_rule(self):
        # Invented credentials, put together here so that no scanner of the repository takes one for real.
        token = "ghp_" + "0aB1cD2eF3gH4iJ5kL6m" + "N7oP8qR9sT0uV1wX"
        secret = {name: f"{name}-{token[4 + index:][:12]}" for index, name in enumerate(
            "basic url flag docker array append unicode assign query unclosed variable path nested body word program "
            "remote env script user literal quote broken config setting other".split())}
        secret["header"] = token
        rules = [
            f'Bash(curl -H "Authorization: Bearer {secret["header"]}" https://api.example.com/user:*)',
            f"Bash(curl -u alice:{secret['basic']} https://example.com/:*)",
            f"Bash(git push https://deploy:{secret['url']}@git.example.com/o/r.git:*)",
            f"Bash(mytool --token {secret['flag']}:*)",
            f"Bash(docker login -p {secret['docker']} registry.example.com && docker push example/image)",
            f"Bash(ARR[0]={secret['array']} git push)",
            f"Bash(KEY+={secret['append']} *)",
            f"Bash(ÜBER={secret['unicode']} *)",
            f"Bash(TOKEN={secret['assign']} gh pr create:*)",
            f"Bash(gh api /repos/o/r/issues?access_token={secret['query']}:*)",
            f'Bash(echo "{secret["unclosed"]}:*)',
            f"Bash(${secret['variable'].replace('-', '_')} test:*)",
            f"Bash(/opt/{secret['path']}/bin/*)",
            f"Bash(bash -c 'curl -H \"X-Api-Key: {secret['nested']}\" https://example.com')",
            f"Bash(gh secret set DEPLOY_KEY --body {secret['body']}:*)",
            f"Bash(gh {secret['word']} {secret['word']}:*)",
            f"Bash({secret['program']}*)",
            f"Bash(ssh deploy@host.example.com 'cat {secret['remote']}')",
        ]
        self.install()
        settings = self.read_settings("claude")
        settings["env"]["SERVICE_TOKEN"] = secret["setting"]
        settings["permissions"] = {"allow": rules, "ask": [f"Bash(curl -u bob:{secret['other']} *)"]}
        self.write_settings("claude", settings)
        self.codex_file("rules/default.rules",
                        f'prefix_rule(pattern=["curl", "-H", "Authorization: Bearer {secret["header"]}"])\n'
                        f'prefix_rule(pattern=["env", "API_KEY={secret["env"]}", "git", "push"])\n'
                        f'prefix_rule(pattern=["bash", "-lc", "SECRET=\'{secret["script"]}\' '
                        f'curl https://user:{secret["user"]}@example.com"])\n'
                        f'prefix_rule(pattern=["git", TOKEN_{secret["literal"].replace("-", "_")}])\n'
                        f'prefix_rule(pattern=["bash", "-lc", "echo \\"{secret["quote"]}"])\n')
        self.codex_file("rules/broken.rules", f'prefix_rule(pattern=["curl", "{secret["broken"]}"\n')
        self.codex_file("config.toml", f'api_key = "{secret["config"]}"\napproval_policy = "never"\nsandbox_mode = "danger-full-access"\n')
        claude, codex = "~/.claude/settings.json: permissions.allow", "~/.codex/rules/"
        expected = [
            AUDIT,
            f"exit      {claude}[0] Bash(curl …) passes curl unasked",
            f"exit      {claude}[1] Bash(curl …) passes curl unasked",
            f"exit      {claude}[2] Bash(git push …) passes git push unasked",
            f"exit      {claude}[4] Bash(docker push …) passes docker push unasked",
            f"exit      {claude}[5] Bash(git push …) passes git push unasked",
            f"wrapper   {claude}[6] Bash(KEY=…) wraps any command",
            f"wrapper   {claude}[7] Bash(…=…) wraps any command",
            f"exit      {claude}[8] Bash(gh pr create …) passes gh pr create unasked",
            f"exit      {claude}[9] Bash(gh api …) passes gh api unasked",
            f"info      {claude}[10] Bash rule whose quoting does not close; not audited",
            f"info      {claude}[11] Bash rule whose program is a variable; not audited",
            f"wrapper   {claude}[12] Bash(…/bin/* …) passes every program of a directory unasked",
            f"exit      {claude}[13] Bash(curl …) passes curl unasked",
            f"exit      {claude}[14] Bash(gh secret set …) passes gh secret set unasked",
            f"exit      {claude}[15] Bash(gh … …) passes gh … … unasked",
            f"exit      {claude}[17] Bash(ssh …) passes ssh unasked",
            f"info      {codex}broken.rules: cannot be read as prefix_rule calls; not audited",
            f"exit      {codex}default.rules:1: prefix_rule(curl …) passes curl unasked",
            f"exit      {codex}default.rules:2: prefix_rule(git push …) passes git push unasked",
            f"exit      {codex}default.rules:3: prefix_rule(curl …) passes curl unasked",
            f"info      {codex}default.rules:4: prefix_rule whose decision or pattern is not a plain literal; not audited",
            f"info      {codex}default.rules:5: prefix_rule whose quoting does not close; not audited",
            'info      ~/.codex/config.toml: approval_policy "never" with sandbox_mode "danger-full-access": '
            "Codex asks before no command and sandboxes none (information only)",
            summary(14, 3, unaudited=5)]
        code, lines = self.doctor("--claude", "--codex")
        self.assertEqual(code, 0, lines)
        self.assertEqual(lines[lines.index(AUDIT):-1], expected)
        outputs = ["\n".join(lines), "\n".join(self.doctor("--claude", "--codex", "--strict")[1])]
        # A settings file that cannot be parsed is named by its problem, never by what it holds.
        self.settings_path("claude").write_text('{"env": {"SERVICE_TOKEN": "%s"}, "permissions": {"allow": ["%s"]' % (
            secret["setting"], rules[1]))
        self.settings_path("codex").write_text('{"hooks": "%s"}' % secret["setting"])
        outputs.append("\n".join(self.doctor("--claude", "--codex")[1]))
        for command in ("install", "uninstall"):
            outputs.append(self.run_main(command, "--claude", "--codex")[1])
        for output in outputs:
            for name, value in secret.items():
                with self.subTest(secret=name):
                    self.assertNotIn(value, output)
                    self.assertNotIn(value.replace("-", "_"), output)

    def test_a_rule_of_any_length_or_content_is_one_short_line(self):
        self.allow("Bash(git push origin main\n\x1b[31m&& echo done)", "Bash(curl " + "x" * 3000 + ")",
                   "Bash(" + "sudo -u root " * 3 + "\tgit\tpush\r)", "Bash(curl " + "x" * 5000 + ")",
                   "Bash(python3." + "7" * 3000 + " -c:*)", "Bash(env " + "A" * 3000 + "=1 *)", "Bash(python3.12 -c:*)")
        name = "~/.claude/settings.json: permissions.allow"
        lines, _ = self.audit("claude")
        self.assertEqual(lines[1:-1], [
            f"exit      {name}[0] Bash(git push …) passes git push unasked",
            f"exit      {name}[1] Bash(curl …) passes curl unasked",
            f"exit      {name}[2] Bash(git push …) passes git push unasked",
            f"info      {name}[3] Bash rule that is longer than the audit reads; not audited",
            f"wrapper   {name}[5] Bash(…=…) wraps any command",      # a name too long to show is left out with its value
            f"wrapper   {name}[6] Bash(python …) wraps any command"])  # and a version is not shown at all
        self.assertLess(max(len(line) for line in lines), 120)

    def test_no_printed_line_is_longer_than_the_limit(self):
        report, out = ddl_setup.Report(), io.StringIO()
        with contextlib.redirect_stdout(out):
            report.info("x" * 100000)
            report.fail("short")
        long, short = out.getvalue().splitlines()
        self.assertEqual((len(long), long[-1], short), (10 + ddl_setup.LINE_LIMIT, "…", "not OK    short"))

    def test_output_survives_a_terminal_that_cannot_show_every_character(self):
        self.install()
        self.allow("Bash(git push:*)", "Bash(TOKEN=x *)")
        # The whole doctor through main, in a process whose output is Latin-1. The build, the gate's suite and the
        # hook probes are left out: they are not about the output, and the build should not run under another locale.
        code = ("import sys; sys.dont_write_bytecode = True; sys.path.insert(0, sys.argv[1]); import ddl_setup; "
                "ddl_setup.ensure_dist = lambda report: None; ddl_setup.gate_suite = lambda: (True, 'OK'); "
                "ddl_setup.doctor_git_hooks = lambda *args: None; sys.exit(ddl_setup.main(['doctor', '--claude']))")
        for label, extra in (("the locale", {"LC_ALL": "en_US.ISO8859-1", "LANG": "en_US.ISO8859-1"}),
                             ("the stream", {"PYTHONIOENCODING": "latin-1"})):
            with self.subTest(set_by=label):
                env = {key: value for key, value in self.env.items() if key not in ("PYTHONUTF8", "PYTHONIOENCODING", "LC_CTYPE")}
                proc = subprocess.run([sys.executable, "-c", code, str(ROOT / "bin")], env=dict(env, **extra), cwd=self.base,
                                      capture_output=True, timeout=300)
                self.assertEqual((proc.returncode, proc.stderr), (0, b""), proc.stdout)
                out = proc.stdout.decode("utf-8", errors="replace")
                self.assertRegex(out, r"(?m)^exit      ~/\.claude/settings\.json: permissions\.allow\[0\] Bash\(git push (…|\?)\) passes")
                self.assertRegex(out, r"(?m)^wrapper   ~/\.claude/settings\.json: permissions\.allow\[1\] Bash\(TOKEN=(…|\?)\) wraps")
                self.assertRegex(out, r"(?m)^\d+ OK, 0 not OK$")
        # The stream that cannot encode `…` shows `?` in its place.
        self.assertIn(b"Bash(git push ?) passes git push unasked", proc.stdout)

    # ---- Codex rules and config ----

    def test_codex_allow_rules_are_audited(self):
        name = "~/.codex/rules/default.rules"
        push = f"exit      {name}:1: prefix_rule(git push …) passes git push unasked"
        cases = [
            ('prefix_rule(pattern=["git", "push"], decision="allow")', [push]),
            ('prefix_rule(pattern=["git", "push"])', [push]),
            ('prefix_rule(pattern=["bash", "-lc"], decision="allow")', [f"wrapper   {name}:1: prefix_rule(bash …) wraps any command"]),
            ('prefix_rule(pattern=["zsh"], decision="allow")', [f"wrapper   {name}:1: prefix_rule(zsh …) wraps any command"]),
            ('prefix_rule(pattern=["bash", "-lc", "git status && ls -la | head"], decision="allow")', []),
            ('prefix_rule(pattern=["bash", "-lc", "cd repo && git push origin main"], decision="allow")', [push]),
            ('prefix_rule(pattern=["bash", "-lc", "git status\\nsudo -n git push"], decision="allow")', [push]),
            ('prefix_rule(pattern=["bash", "-o", "pipefail", "-c", "git push"], decision="allow")', [push]),
            ('prefix_rule(pattern=["git", "push"], decision="prompt")', []),
            ('prefix_rule(pattern=["git", "push"], decision="forbidden")', []),
            ('prefix_rule(pattern=["git", ["status", "push"]], decision="allow")', [push]),
            ('prefix_rule(pattern=[["bash", "zsh"], "-lc"], decision="allow")',
             [f"wrapper   {name}:1: prefix_rule(bash …) wraps any command",
              f"wrapper   {name}:1: prefix_rule(zsh …) wraps any command"]),
            ('prefix_rule(pattern=["git", ["status", "log", "diff"]], decision="allow")', []),
            ('prefix_rule(pattern=["python3", "tools/build.py"], decision="allow")', []),
            ('prefix_rule(pattern=["python3", "-m", "pytest"], decision="allow")', []),
            ('prefix_rule(pattern=["timeout", "60", "npm", "test"], decision="allow")', []),
            ('prefix_rule(pattern=["bash", "tools/check.sh"], decision="allow")', []),
            ('# a comment\n\nprefix_rule(\n    pattern = ["gh", "pr", ["view", "create"]],\n    decision = "allow",\n'
             '    justification = "x",\n)\nprefix_rule(pattern = ["ls"])\n',
             [f"exit      {name}:3: prefix_rule(gh pr create …) passes gh pr create unasked"]),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                self.codex_file("rules/default.rules", text + "\n")
                lines, report = self.audit("codex")
                self.assertEqual(lines[1:-1], expected)
                self.assertEqual((report.ok, report.bad), (0, 0))

    def test_codex_rules_absent_or_unparsable(self):
        (self.home / ".codex").mkdir()
        self.assertEqual(self.audit("codex")[0], [AUDIT, summary(0, 0)])
        (self.home / ".codex/rules").mkdir()
        self.assertEqual(self.audit("codex")[0], [AUDIT, summary(0, 0)])
        self.codex_file("rules/broken.rules", 'prefix_rule(pattern = ["git", "push"\n')
        (self.home / ".codex/rules/binary.rules").write_bytes(b"\xff\xfe\x00prefix_rule(")
        self.codex_file("rules/default.rules", 'prefix_rule(pattern=["git", "push"])\n')
        self.codex_file("rules/names.rules", 'PUSH = ["git", "push"]\nprefix_rule(pattern=PUSH)\nprefix_rule(pattern=[1])\n'
                                             'prefix_rule(decision="allow")\nprefix_rule(pattern=PUSH, decision="prompt")\n')
        self.codex_file("rules/notes.txt", 'prefix_rule(pattern=["curl"])\n')
        (self.home / ".codex/rules/folder.rules").mkdir()
        lines, report = self.audit("codex")
        self.assertEqual(lines, [
            AUDIT,
            "info      ~/.codex/rules/binary.rules: cannot be read as prefix_rule calls; not audited",
            "info      ~/.codex/rules/broken.rules: cannot be read as prefix_rule calls; not audited",
            "exit      ~/.codex/rules/default.rules:1: prefix_rule(git push …) passes git push unasked",
            "info      ~/.codex/rules/names.rules:2: prefix_rule whose decision or pattern is not a plain literal; not audited",
            "info      ~/.codex/rules/names.rules:3: prefix_rule whose decision or pattern is not a plain literal; not audited",
            "info      ~/.codex/rules/names.rules:4: prefix_rule whose decision or pattern is not a plain literal; not audited",
            summary(1, 0, unaudited=5)])
        self.assertEqual((report.ok, report.bad), (0, 0))

    @unittest.skipIf(ROOT_USER, "file modes do not stop root")
    def test_codex_rules_that_may_not_be_read_are_not_audited(self):
        hidden = self.codex_file("rules/hidden.rules", 'prefix_rule(pattern=["git", "push"])\n')
        hidden.chmod(0)
        self.assertEqual(self.audit("codex")[0], [
            AUDIT, "info      ~/.codex/rules/hidden.rules: cannot be read as prefix_rule calls; not audited", summary(0, 0, unaudited=1)])
        rules = self.home / ".codex/rules"
        rules.chmod(0)
        self.addCleanup(rules.chmod, 0o700)
        lines, report = self.audit("codex", strict=True)
        self.assertEqual(lines, [AUDIT, "not OK    ~/.codex/rules: cannot be listed; its rules are not audited",
                                 summary(0, 0, "counted", unaudited=1)])
        self.assertEqual((report.ok, report.bad), (0, 1))

    def test_codex_config_that_never_asks_and_sandboxes_nothing_is_information(self):
        line = ('info      ~/.codex/config.toml: approval_policy "never" with sandbox_mode "danger-full-access": '
                "Codex asks before no command and sandboxes none (information only)")
        self.codex_file("config.toml", 'model = "x"\napproval_policy = "never"  # no prompt\nsandbox_mode = \'danger-full-access\'\n\n'
                                       '[agents]\nmax_concurrent_threads_per_session = 5\n')
        for strict in (False, True):
            with self.subTest(strict=strict):
                lines, report = self.audit("codex", strict=strict)
                self.assertEqual(lines, [AUDIT, line, summary(0, 0, "counted" if strict else "not counted")])
                self.assertEqual((report.ok, report.bad), (0, 0))
        quiet = {
            "commented": '# approval_policy = "never"\n# sandbox_mode = "danger-full-access"\n',
            "half commented": 'approval_policy = "never"\n# sandbox_mode = "danger-full-access"\n',
            "profile": '[profiles.fast]\napproval_policy = "never"\nsandbox_mode = "danger-full-access"\n',
            "after a table": 'approval_policy = "never"\n[sandbox]\nsandbox_mode = "danger-full-access"\n',
            "sandboxed": 'approval_policy = "never"\nsandbox_mode = "workspace-write"\n',
            "asks": 'approval_policy = "on-request"\nsandbox_mode = "danger-full-access"\n',
            "inside a string": 'notes = """\napproval_policy = "never"\nsandbox_mode = "danger-full-access"\n"""\n',
            "empty": "",
        }
        for label, text in quiet.items():
            with self.subTest(label=label):
                self.codex_file("config.toml", text)
                self.assertEqual(self.audit("codex")[0], [AUDIT, summary(0, 0)])

    def test_claude_default_mode_that_asks_before_nothing_is_information(self):
        line = ('info      ~/.claude/settings.json: permissions.defaultMode "bypassPermissions": '
                "Claude Code asks before no command (information only)")
        self.write_settings("claude", {"permissions": {"defaultMode": "bypassPermissions"}})
        for strict in (False, True):
            with self.subTest(strict=strict):
                lines, report = self.audit("claude", strict=strict)
                self.assertEqual(lines, [AUDIT, line, summary(0, 0, "counted" if strict else "not counted")])
                self.assertEqual((report.ok, report.bad), (0, 0))
        for permissions in ({"defaultMode": "acceptEdits"}, {"defaultMode": ["bypassPermissions"]}, {"ask": ["bypassPermissions"]}):
            with self.subTest(permissions=permissions):
                self.write_settings("claude", {"permissions": permissions, "defaultMode": "bypassPermissions"})
                self.assertEqual(self.audit("claude")[0], [AUDIT, summary(0, 0)])

    def test_agents_thread_limit_is_read_from_the_agents_table(self):
        self.install()
        unset = "info      ~/.codex/config.toml does not set [agents] max_concurrent_threads_per_session (optional; SWARM uses max: 5)"
        code, lines = self.doctor("--codex")
        self.assertEqual((code, lines.count(unset)), (0, 1), lines)
        self.codex_file("config.toml", "# [agents]\n# max_concurrent_threads_per_session = 5\n")
        code, lines = self.doctor("--codex")
        self.assertEqual((code, lines.count(unset)), (0, 1), lines)
        for text in ('model = "x"\n\n[agents]\nmax_concurrent_threads_per_session = 5\n',
                     'model = "x"\nagents = { max_concurrent_threads_per_session = 5 }\n',
                     "agents = { job_max_runtime_seconds = 60, max_concurrent_threads_per_session = 5 }  # one line\n",
                     "agents.max_concurrent_threads_per_session = 5\n"):
            with self.subTest(text=text):
                self.codex_file("config.toml", text)
                code, lines = self.doctor("--codex")
                self.assertEqual((code, lines.count(unset)), (0, 0), lines)

    def test_a_status_of_several_lines_keeps_one_line_per_check(self):
        self.install()
        real = subprocess.run

        def run(command, *args, **options):
            if isinstance(command, list) and "status" in command:  # a stand-in for a status that adds lines
                return subprocess.CompletedProcess(command, 0, stdout="DDL project: yes\nsecond line\n", stderr="")
            return real(command, *args, **options)

        with mock.patch.object(ddl_setup.subprocess, "run", run):
            code, lines = self.doctor("--claude")
        self.assertEqual(code, 0, lines)
        self.assertEqual(lines[lines.index("== gate") + 1:][:2], ["info      DDL project: yes", "info      second line"])

    # ---- the durable grant store ----

    def grant_store_line(self):
        report = ddl_setup.Report()
        _, out = self.in_home(ddl_setup.doctor_grant_store, report)
        return out.rstrip("\n"), (report.ok, report.bad)

    def test_doctor_checks_who_can_enter_the_grant_store(self):
        name = f"grant store {self.grants}"
        self.assertEqual(self.grant_store_line(),
                         (f"info      {name} absent (the gate creates it when it first records a grant)", (0, 0)))
        self.grants.mkdir()
        self.grants.chmod(0o700)
        self.assertEqual(self.grant_store_line(), (f"OK        {name} (only its owner can enter)", (1, 0)))
        for mode in (0o750, 0o705, 0o770, 0o755, 0o701):
            with self.subTest(mode=oct(mode)):
                self.grants.chmod(mode)
                self.assertEqual(self.grant_store_line(),
                                 (f"not OK    {name} is open to group or others (mode {mode:04o}; expected 0700)", (0, 1)))
        self.grants.rmdir()
        private = self.base / "elsewhere"
        private.mkdir()
        private.chmod(0o700)
        self.grants.symlink_to(private)
        self.assertEqual(self.grant_store_line(),
                         (f"not OK    {name} is a symlink (expected a directory only its owner can enter)", (0, 1)))
        self.grants.unlink()
        self.grants.symlink_to(self.base / "missing")
        self.assertEqual(self.grant_store_line()[1], (0, 1))
        self.grants.unlink()
        self.grants.write_text("")
        self.assertEqual(self.grant_store_line(), (f"not OK    {name} is not a directory", (0, 1)))

    def test_grant_store_path_follows_the_contract_order(self):
        for env, expected in [
                ({"DDL_GATE_GRANT_DIR": "/grants", "XDG_STATE_HOME": "/state"}, "/grants"),
                ({"XDG_STATE_HOME": "/state"}, "/state/ddl-gate"),
                ({}, "/home/.local/state/ddl-gate"),
                ({"DDL_GATE_GRANT_DIR": "", "XDG_STATE_HOME": ""}, "/home/.local/state/ddl-gate")]:
            with self.subTest(env=env), mock.patch.dict(os.environ, dict(env, HOME="/home"), clear=True):
                self.assertEqual(ddl_setup.grant_store(), pathlib.Path(expected))

    def test_grant_store_is_the_directory_the_gate_writes(self):
        gate = gate_module()
        cases = {
            "the variable set": {"DDL_GATE_GRANT_DIR": "/var/grants", "XDG_STATE_HOME": "/state"},
            "set but empty": {"DDL_GATE_GRANT_DIR": "", "XDG_STATE_HOME": "/state"},
            "set to a relative path": {"DDL_GATE_GRANT_DIR": "grants/here"},
            "set with ..": {"DDL_GATE_GRANT_DIR": "/var/tmp/../grants/./x", "XDG_STATE_HOME": "/state"},
            "relative with ..": {"DDL_GATE_GRANT_DIR": "../grants"},
            "XDG_STATE_HOME set": {"XDG_STATE_HOME": "/state"},
            "XDG_STATE_HOME relative": {"XDG_STATE_HOME": "state/../other"},
            "XDG_STATE_HOME empty": {"XDG_STATE_HOME": ""},
            "neither set": {},
        }
        cwd = os.getcwd()
        os.chdir(self.base)
        try:
            here = os.getcwd()
            for label, env in cases.items():
                with self.subTest(label=label), mock.patch.dict(os.environ, dict(env, HOME="/home"), clear=True):
                    store = ddl_setup.grant_store()
                    self.assertEqual(str(store), gate.grant_store())
                    self.assertTrue(store.is_absolute())
                    self.assertNotIn("..", store.parts)
            with mock.patch.dict(os.environ, {"DDL_GATE_GRANT_DIR": "grants/here", "HOME": "/home"}, clear=True):
                self.assertEqual(str(ddl_setup.grant_store()), os.path.join(here, "grants/here"))
            with mock.patch.dict(os.environ, {"DDL_GATE_GRANT_DIR": "/var/tmp/../grants/./x", "HOME": "/home"}, clear=True):
                self.assertEqual(str(ddl_setup.grant_store()), "/var/grants/x")
            # doctor checks that directory: a relative value names the store below the current directory.
            (self.base / "relative grants").mkdir(mode=0o700)
            self.env["DDL_GATE_GRANT_DIR"] = "sub/../relative grants"
            self.assertEqual(self.grant_store_line(), (
                f"OK        grant store {os.path.join(here, 'relative grants')} (only its owner can enter)", (1, 0)))
        finally:
            os.chdir(cwd)

    @unittest.skipIf(ROOT_USER, "file modes do not stop root")
    def test_a_grant_store_nobody_may_reach_is_a_line_not_a_traceback(self):
        locked = self.base / "locked"
        (locked / "grants").mkdir(parents=True)
        self.env["DDL_GATE_GRANT_DIR"] = str(locked / "grants")
        locked.chmod(0)
        self.addCleanup(locked.chmod, 0o700)
        self.assertEqual(self.grant_store_line(), (
            f"not OK    grant store {locked / 'grants'} cannot be examined (Permission denied)", (0, 1)))
        # uninstall cannot see it either: it says nothing and removes nothing.
        report = ddl_setup.Report()
        self.assertEqual(self.in_home(ddl_setup.uninstall_grant_store, report)[1], "")
        locked.chmod(0o700)
        self.assertTrue((locked / "grants").is_dir())
        # A directory in the way of the store's parent is the same kind of line.
        (self.base / "plain").write_text("")
        self.env["DDL_GATE_GRANT_DIR"] = str(self.base / "plain/grants")
        self.assertEqual(self.grant_store_line(), (
            f"not OK    grant store {self.base / 'plain/grants'} cannot be examined (Not a directory)", (0, 1)))

    def test_uninstall_leaves_a_grant_store_that_holds_anything_and_removes_an_empty_one(self):
        self.install()
        out = self.cli("uninstall", "--claude", "--codex")
        self.assertNotIn("grant store", out)
        self.assertFalse(self.grants.exists())
        self.install()
        record = self.grants / "0123456789abcdef/grants/R-0000000000000000.json"
        record.parent.mkdir(parents=True)
        record.write_text("{}\n")
        out = self.cli("uninstall", "--claude", "--codex")
        self.assertIn(f"info      grant store {self.grants} left in place", out)
        self.assertEqual(record.read_text(), "{}\n")
        self.install()
        shutil.rmtree(self.grants)
        self.grants.mkdir()
        out = self.cli("uninstall", "--claude", "--codex", "--dry-run")
        self.assertIn(f"OK        remove {self.grants} (empty grant store)", out)
        self.assertTrue(self.grants.is_dir())
        out = self.cli("uninstall", "--claude", "--codex")
        self.assertIn(f"OK        remove {self.grants} (empty grant store)", out)
        self.assertFalse(self.grants.exists())
        # A store that is a symlink is not DDL's to remove.
        self.install()
        target = self.base / "elsewhere"
        target.mkdir()
        self.grants.symlink_to(target)
        out = self.cli("uninstall", "--claude", "--codex")
        self.assertIn(f"info      grant store {self.grants} is not a plain directory; left in place", out)
        self.assertTrue(self.grants.is_symlink() and target.is_dir())

    def test_doctor_hook_probes_use_a_disposable_grant_store(self):
        # A stand-in for the installed gate records the environment each probe gives it.
        base = self.base / "standin"
        gate = base / "hooks/ddl_gate.py"
        gate.parent.mkdir(parents=True)
        gate.write_text("import json, os\n"
                        "names = ('HOME', 'DDL_GATE_STATE_DIR', 'DDL_GATE_GRANT_DIR')\n"
                        "with open(os.environ['DDL_TEST_PROBE_LOG'], 'a') as log:\n"
                        "    log.write(json.dumps([os.environ.get(name) for name in names]) + '\\n')\n")
        settings = {"hooks": {"PreToolUse": [{"matcher": ".*", "hooks": [{
            "type": "command", "command": 'python3 "$HOME/.codex/hooks/ddl_gate.py"'}]}]}}
        log = self.base / "probe-env.jsonl"
        self.env["DDL_TEST_PROBE_LOG"] = str(log)
        self.in_home(ddl_setup.doctor_git_hooks, "codex", base, settings, ddl_setup.Report())
        seen = [json.loads(line) for line in log.read_text().splitlines()]
        self.assertEqual(len(seen), 6)
        for probe_home, state, grants in seen:
            self.assertEqual((state, grants), (os.path.join(probe_home, "state"), os.path.join(probe_home, "grants")))
            self.assertNotEqual(probe_home, str(self.home))
            self.assertFalse(os.path.exists(probe_home), "the probe's home is disposable")
        self.assertFalse(self.grants.exists())

    def test_gate_suite_runs_with_a_disposable_grant_store(self):
        seen = {}

        def run(command, **options):
            grants = options["env"]["DDL_GATE_GRANT_DIR"]
            seen.update(command=command, grants=grants, existed=os.path.isdir(grants))
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="..\n\nOK\n")

        with mock.patch.object(ddl_setup.subprocess, "run", run):
            result, _ = self.in_home(ddl_setup.gate_suite)
        self.assertEqual(result, (True, "OK"))
        self.assertTrue(seen["command"][-1].endswith("test_ddl_gate.py"))
        self.assertTrue(seen["existed"])
        self.assertNotEqual(seen["grants"], str(self.grants))
        self.assertFalse(os.path.exists(seen["grants"]))


PUSH = "git push"
EXIT_RULES = [
    *[(f"Bash({program}:*)", program) for program in "rsync scp sftp ssh rclone nc ncat socat ftp curl wget".split()],
    ("Bash(git push:*)", PUSH), ("Bash(git push)", PUSH), ("Bash(git push *)", PUSH),
    ("Bash(git push*)", PUSH), ("Bash(git push origin main)", PUSH),
    ("Bash(git:*)", "git (any subcommand)"), ("Bash(git *)", "git (any subcommand)"),
    *[(f"Bash(git {verb}:*)", f"git {verb}")
      for verb in "merge cherry-pick revert reset rebase pull checkout switch send-email".split()],
    ("Bash(git lfs push:*)", "git lfs push"), ("Bash(git lfs:*)", "git lfs push"), ("Bash(git lfs pu*)", "git lfs push"),
    ("Bash(git subtree push --prefix=docs origin main)", "git subtree push"),
    ("Bash(git subtree -P docs push origin main)", "git subtree push"),
    ("Bash(/usr/bin/git push:*)", PUSH), ("Bash(GIT_TRACE=1 git push:*)", PUSH),
    ("Bash(git -C /tmp push:*)", PUSH), ("Bash(git --no-pager -c push.default=current push:*)", PUSH),
    *[(f"Bash({program} publish:*)", f"{program} publish") for program in "npm pnpm yarn bun cargo uv poetry".split()],
    ("Bash(gem push:*)", "gem push"), ("Bash(twine upload:*)", "twine upload"),
    ("Bash(docker push:*)", "docker push"), ("Bash(podman push:*)", "podman push"),
    ("Bash(docker image push:*)", "docker push"), ("Bash(yarn npm publish)", "yarn publish"),
    ("Bash(cargo +nightly publish)", "cargo publish"), ("Bash(pnpm --filter web publish)", "pnpm publish"),
    # A rule that names only the program leaves its verb open, the publish verb included.
    ("Bash(npm:*)", "npm publish"), ("Bash(pnpm *)", "pnpm publish"), ("Bash(cargo:*)", "cargo publish"),
    ("Bash(docker:*)", "docker push"), ("Bash(gem:*)", "gem push"), ("Bash(npm pub*)", "npm publish"),
    ("Bash(gh:*)", "gh (any subcommand)"), ("Bash(gh api:*)", "gh api"),
    ("Bash(gh api repos/o/r/pulls --method POST:*)", "gh api"),  # the endpoint is never shown
    ("Bash(gh pr:*)", "gh pr"), ("Bash(gh pr create:*)", "gh pr create"), ("Bash(gh pr merge:*)", "gh pr merge"),
    ("Bash(gh release create:*)", "gh release create"), ("Bash(gh workflow run:*)", "gh workflow run"),
    ("Bash(glab:*)", "glab (any subcommand)"), ("Bash(glab mr create:*)", "glab mr create"), ("Bash(glab api:*)", "glab api"),
    # A spelled-out exit is one wherever it stands: behind a wrapper and its options, in a script, in a substitution.
    ("Bash(timeout 60 git push:*)", PUSH), ("Bash(sudo -u root git push)", PUSH), ("Bash(sudo -nu root git push)", PUSH),
    ("Bash(sudo --user=root git push)", PUSH), ("Bash(env -u X git push)", PUSH), ("Bash(env -i PATH=/bin git push)", PUSH),
    ("Bash(timeout -s KILL 5 git push)", PUSH), ("Bash(timeout --signal=KILL -k 1 5 git push)", PUSH),
    ("Bash(xargs -I {} git push {})", PUSH), ("Bash(xargs -n1 git push)", PUSH), ("Bash(doas -u root git push)", PUSH),
    ("Bash(nice -n 10 git push)", PUSH), ("Bash(stdbuf -oL git push)", PUSH), ("Bash(setsid git push)", PUSH),
    ("Bash(gtimeout 5 git push)", PUSH), ("Bash(nohup git push &)", PUSH), ("Bash(exec -a x git push)", PUSH),
    ("Bash(command -p git push)", PUSH), ("Bash(time -p git push)", PUSH),
    ("Bash(sudo env nice nohup time timeout 5 exec command git push)", PUSH),
    ("Bash(busybox wget https://example.com)", "wget"), ("Bash(busybox sh -c 'git push')", PUSH),
    ("Bash(su -c 'git push' root)", PUSH), ("Bash(su - root -c 'git push')", PUSH),
    ("Bash(bash -c 'git push')", PUSH), ("Bash(bash -o pipefail -c 'git push')", PUSH), ("Bash(bash -cl 'git push')", PUSH),
    ("Bash(bash -euo pipefail -c 'git push')", PUSH), ("Bash(zsh -l -c 'git push')", PUSH), ("Bash(sh -c 'cd x && git push':*)", PUSH),
    ("Bash(fish --command='git push')", PUSH), ("Bash(bash -c \"bash -c 'bash -c \\\"git push\\\"'\")", PUSH),
    ('Bash(echo "$(git push)")', PUSH), ('Bash(echo "`git push`")', PUSH), ("Bash(echo `git push`)", PUSH),
    ("Bash(echo $(git push))", PUSH), ("Bash(echo $(curl -s https://example.com):*)", "curl"),
    ("Bash(echo $(git:*)", "git (any subcommand)"),
    ('Bash(echo "a $(echo "b $(git push)") c")', PUSH), ('Bash(VALUE="$(curl example.com)" ls)', "curl"),
    ("Bash(! git push:*)", PUSH), ("Bash({ git push:*)", PUSH), ("Bash(if true; then git push:*)", PUSH),
    ("Bash(for remote in a b; do git push:*)", PUSH), ("Bash(while ! git push; do sleep 1; done)", PUSH),
    ("Bash(f() { git push; }; f)", PUSH),
    # A here-document a shell reads is its script; any other body is input, not commands.
    ("Bash(bash <<EOF\ngit push\nEOF)", PUSH), ("Bash(bash -s <<'EOF'\ncd repo\ngit push\nEOF)", PUSH),
    ("Bash(sudo sh <<-EOF\n\tgit push\n\tEOF)", PUSH), ("Bash(cat <<EOF | sh\necho hi\nEOF\ngit push)", PUSH),
    # A runner runs what follows it, like a wrapper.
    ("Bash(uv run git push)", PUSH), ("Bash(poetry run twine upload:*)", "twine upload"), ("Bash(npx git push)", PUSH),
    ("Bash(npm exec -- git push)", PUSH), ("Bash(npm x -- curl example.com)", "curl"), ("Bash(pnpm --filter web exec git push)", PUSH),
    ("Bash(pnpm dlx --package x git push)", PUSH), ("Bash(yarn exec git push)", PUSH), ("Bash(yarn dlx -p x git push)", PUSH),
    ("Bash(pdm run git push)", PUSH), ("Bash(hatch run git push)", PUSH), ("Bash(bundle exec git push)", PUSH),
    ("Bash(pipx run --spec x git push)", PUSH), ("Bash(uv run --with requests git push)", PUSH),
    ("Bash(uv tool run git push)", PUSH), ("Bash(uvx --from x git push)", PUSH), ("Bash(bunx git push)", PUSH),
    ("Bash(uv run sudo -u root git push)", PUSH), ("Bash(uv:*)", "uv publish"), ("Bash(yarn *)", "yarn publish"),
    # `-h` is not help everywhere.
    ("Bash(rsync -h:*)", "rsync"), ("Bash(ssh -h:*)", "ssh"),
    ("Bash(watch -n 5 git push)", PUSH), ("Bash(parallel -j 4 git push ::: a b)", PUSH), ("Bash(eval 'git push; ls')", PUSH),
    ("Bash(env -S 'git push origin')", PUSH), ("Bash(ARR[0]=x git push)", PUSH), ("Bash(KEY+=x git push)", PUSH),
]
WRAPPER_RULES = [
    "Bash", "Bash()", "Bash(*)", "Bash(:*)", "Bash(FOO=1:*)", "Bash(FOO=1 BAR='2 3' *)", "Bash(* --version)",
    *[f"Bash({program}:*)" for program in ("env xargs bash sh zsh fish dash ksh sudo nohup timeout time nice command exec "
                                           "eval watch parallel doas su setsid stdbuf gtimeout busybox").split()],
    *[f"Bash({program}:*)" for program in "python python3 python3.12 node ruby perl deno bun php lua osascript pwsh".split()],
    # An interpreter or a shell whose code the rule leaves open.
    "Bash(python3 -c:*)", "Bash(node -e:*)", "Bash(ruby -e:*)", "Bash(perl -pe:*)", "Bash(python3 -m:*)",
    "Bash(python3 -u -c:*)", "Bash(php -r:*)", "Bash(lua -e:*)", "Bash(osascript -e:*)", "Bash(pwsh -NoProfile -Command:*)",
    "Bash(deno run:*)", "Bash(deno eval:*)", "Bash(bun run:*)", "Bash(python3 - :*)", "Bash(python3 -m py*)",
    "Bash(PATH=/x bash:*)", "Bash(bash -lc:*)", "Bash(bash -c:*)", "Bash(bash -s:*)", "Bash(bash -c 'git status'*)",
    "Bash(xargs sh -c)", "Bash(su root:*)", "Bash(sudo -h:*)", "Bash(bash -h:*)",
    # A runner with no command spelled after it.
    "Bash(npx:*)", "Bash(uvx:*)", "Bash(bunx:*)", "Bash(npx -y:*)", "Bash(npx --package x:*)", "Bash(uv run:*)",
    "Bash(uv tool run:*)", "Bash(uv tool:*)", "Bash(uv run --with x:*)", "Bash(uv r*)", "Bash(npm exec:*)", "Bash(npm x:*)",
    "Bash(npm ex*)", "Bash(pnpm exec:*)", "Bash(pnpm dlx:*)", "Bash(yarn dlx:*)", "Bash(yarn exec:*)", "Bash(poetry run:*)",
    "Bash(pdm run:*)", "Bash(hatch run:*)", "Bash(bundle exec:*)", "Bash(pipx run:*)", "Bash(bun x:*)",
    "Bash(pipx:*)", "Bash(pdm:*)", "Bash(hatch:*)", "Bash(bundle:*)", "Bash(uv run python -c:*)", "Bash(npx bash -c:*)",
    # An option that takes a value does not name the script or the code.
    "Bash(python3 -X dev -c:*)", "Bash(python3 -W ignore:*)", "Bash(node -r ./x.js -e:*)", "Bash(node --require ./x.js:*)",
    "Bash(ruby -I lib -e:*)", "Bash(php -d display_errors=1 -r:*)", "Bash(lua -l mod -e:*)", "Bash(osascript -l JavaScript -e:*)",
    "Bash(pwsh -ExecutionPolicy Bypass -Command:*)", "Bash(bash -o pipefail -c:*)", "Bash(bash --rcfile x:*)",
    # A wrapper is one only where the rule ends before a command is spelled.
    "Bash(sudo -u root:*)", "Bash(sudo -u*)", "Bash(env -u X:*)", "Bash(env FOO=1:*)", "Bash(timeout -s KILL 5:*)",
    "Bash(timeout 60:*)", "Bash(timeout 6*)", "Bash(xargs -I {}:*)", "Bash(nice -n 10:*)", "Bash(git status && *)", "Bash(ls;*)",
    # A wildcard that may stand for a wrapper, a code flag or a whole command.
    "Bash(s*)", "Bash(g*)", "Bash(sudo g*)", "Bash(bash * x.sh)", "Bash(bash -* x)", "Bash(timeout * git status)",
    "Bash(sudo * --help)", "Bash(python3 * x)", "Bash(python3 -* x.py)", "Bash(bash -c 'ls *.py')",
    # Every program of a system directory.
    "Bash(/usr/bin/*)", "Bash(/bin/*)", "Bash(/opt/homebrew/bin/*)", "Bash(~/.local/bin/*)", "Bash($HOME/bin/*)",
    "Bash(/usr/sbin/* --help)",
]
NARROW_RULES = [
    "Bash(gh pr view:*)", "Bash(git commit:*)", "Bash(python3 tools/build.py:*)", "Bash(git log:*)",
    "Bash(git branch:*)", "Bash(git stash:*)", "Bash(git config:*)", "Bash(git remote:*)", "Bash(git status)",
    "Bash(git diff:*)", "Bash(git -C /tmp log:*)", "Bash(find:*)", "Bash(awk:*)", "Bash(make:*)",
    "Bash(rm:*)", "Bash(open:*)", "Bash(gh pr list:*)", "Bash(gh status)", "Bash(gh search prs:*)",
    "Bash(gh run watch:*)", "Bash(gh pr checks:*)", "Bash(gh pr diff:*)", "Bash(gh pr view*)", "Bash(npm run build:*)",
    "Bash(npm test)", "Bash(docker ps:*)", "Bash(twine check:*)", "Bash(node scripts/build.js:*)",
    "Bash(python3 tools/build.py -c settings.toml:*)", "Bash(ruby script/run.rb:*)", "Bash(./scripts/*)",
    "Read", "Edit(src/**)", "WebFetch(domain:example.com)", "mcp__server__push", "BashOutput",
    # A wrapper, an interpreter or a shell followed by one spelled-out command, module or script.
    "Bash(python3 -m pytest:*)", "Bash(bash tools/x.sh:*)", "Bash(timeout 60 npm test:*)", "Bash(xargs grep:*)",
    "Bash(ls | xargs rm)", "Bash(ls | xargs)", "Bash(sudo ls)", "Bash(/usr/bin/env FOO=1 make:*)", "Bash(nice -n 10 make:*)",
    "Bash(nohup npm run dev:*)", "Bash(time make:*)", "Bash(sudo -n true && ls:*)", "Bash(command -v:*)",
    "Bash(python3 -X dev tools/x.py:*)", "Bash(python3 -c 'print(1)':*)", "Bash(bash -c 'git status':*)",
    "Bash(bash -c 'git status' arg:*)", "Bash(bash -lc 'git status && ls -la | head')", "Bash(php artisan test:*)",
    "Bash(lua tools/x.lua:*)", "Bash(osascript tools/x.scpt:*)", "Bash(pwsh -File tools/x.ps1:*)", "Bash(bun run build:*)",
    "Bash(deno task build:*)", "Bash(deno run tools/x.ts:*)", "Bash(su -c 'ls' root)",
    # An exact rule passes what it spells and nothing more.
    "Bash(git)", "Bash(gh)", "Bash(git --version)", "Bash(gh --version)", "Bash(python3 --version)", "Bash(env)",
    "Bash(bash -n bin/install.sh)", "Bash(sudo -v)", "Bash(python3)", "Bash(bash)", "Bash(bash -s)", "Bash(FOO=1)",
    "Bash(curl --version)", "Bash(ssh -V)", "Bash(curl)", "Bash(npm)", "Bash(git lfs)", "Bash(su root)", "Bash(xargs)",
    "Bash(timeout 5)", "Bash(python3 -c 'print(1)')", "Bash(node -e 'console.log(1)')", "Bash(eval)", "Bash(glab)",
    # The verbs and programs next to the listed ones.
    "Bash(git lfs pull:*)", "Bash(git subtree split:*)", "Bash(glab mr view:*)", "Bash(glab ci status:*)",
    "Bash(docker compose up:*)", "Bash(yarn npm info:*)", "Bash(cargo build:*)", "Bash(uv run pytest:*)",
    "Bash(gem list:*)", "Bash(poetry install:*)", "Bash(podman ps:*)", "Bash(pnpm install:*)",
    # A wildcard over the project's own scripts, or over nothing the audit knows.
    "Bash(python3 tools/*)", "Bash(bash tools/*.sh)", "Bash(bin/*)", "Bash(./bin/*)", "Bash(node_modules/.bin/*)",
    "Bash(sudo q*)", "Bash(git st*)",
    # The rule goes on behind a substitution or a subshell: no new command starts there.
    "Bash(echo $(date):*)", "Bash(echo `date` *)", "Bash((cd docs && make) *)", "Bash(ls $(pwd)*)",
    # A runner followed by one spelled-out command; the forms next to the runner forms.
    "Bash(npx prettier:*)", "Bash(npx --yes prettier --check .)", "Bash(uvx ruff check:*)", "Bash(bunx tsc:*)", "Bash(uv run)",
    "Bash(uv run pytest -q:*)", "Bash(uv run --with requests script.py:*)", "Bash(uv tool run ruff:*)", "Bash(uv tool install ruff)",
    "Bash(uv pip install:*)", "Bash(npm exec prettier:*)", "Bash(npm run exec:*)", "Bash(pnpm dlx prettier:*)",
    "Bash(pnpm run build:*)", "Bash(yarn dlx prettier:*)", "Bash(yarn run build:*)", "Bash(poetry run pytest:*)",
    "Bash(pdm run test:*)", "Bash(hatch run test:*)", "Bash(bundle exec rake:*)", "Bash(bundle install:*)",
    "Bash(pipx run black:*)", "Bash(pipx install black)", "Bash(cargo run:*)", "Bash(cargo run --release -- args:*)",
    "Bash(bun x cowsay:*)", "Bash(pipx)", "Bash(pdm)",
    # Asked for its version or its help, a program runs nothing else, whatever may follow.
    "Bash(python3 --version:*)", "Bash(node --version:*)", "Bash(git --version:*)", "Bash(npm --version:*)",
    "Bash(curl --version:*)", "Bash(python3 -V:*)", "Bash(python3 -h:*)", "Bash(curl -h:*)", "Bash(curl -V)", "Bash(git -h:*)",
    "Bash(bash --version:*)", "Bash(sudo --version:*)", "Bash(sudo -V:*)", "Bash(env --help:*)", "Bash(gh --help:*)",
    "Bash(uv --version:*)", "Bash(npx --version)", "Bash(ssh -V:*)", "Bash(docker --help:*)", "Bash(timeout --version:*)",
    "Bash(/usr/bin/python3.12 --version:*)", "Bash(git --version*)",
    # The body of a here-document is input, not commands: a line of prose in it is no command.
    "Bash(cat <<EOF\ngit push\nEOF)", "Bash(cat <<'EOF' > notes.txt\ncurl is optional\nEOF)",
    "Bash(cat <<-EOF\n\tcurl x\n\tEOF)", 'Bash(cat <<"EOF"\nit doesn\'t matter (really) :)\nEOF)',
    'Bash(git commit -m "$(cat <<\'EOF\'\ncurl is optional\nit doesn\'t matter :)\n1) rsync, 2) "ssh\nEOF\n)")',
    "Bash(git commit -F - <<EOF\nwget and curl\nEOF)", "Bash(python3 - <<'EOF'\nimport os\nEOF)",
    "Bash(cat <<A <<B\ncurl\nA\nwget\nB)", "Bash(tee out <<EOF\ncurl\nEOF:*)",
    "Bash(cat <<< 'curl x')", "Bash(echo $((1 << 2)))", "Bash(bash build.sh <<EOF\ncurl x\nEOF)",
    # Quoted or commented text is not a command.
    "Bash(echo 'git push; curl x')", 'Bash(echo "\\$(git push)")', "Bash(ls # git push)", "Bash($HOME/bin/tool:*)",
]
UNAUDITED_RULES = [
    ('Bash(echo "unclosed:*)', "whose quoting does not close"),
    ("Bash(echo 'a' \"b; git push)", "whose quoting does not close"),  # the open quote must not hide the push
    ("Bash(git commit -m 'it:*)", "whose quoting does not close"),
    ('Bash(echo "$(git push")', "whose quoting does not close"),
    ("Bash($RUNNER test:*)", "whose program is a variable"),
    ('Bash("$@")', "whose program is a variable"),
    ("Bash($(which python3) x.py)", "whose program is a variable"),
    ("Bash(" + "sudo " * 10 + "ls)", "that nests commands deeper than the audit follows"),
    ("Bash(cat <<EOF\ngit push)", "whose here-document does not end"),
    ("Bash(cat <<EOF)", "whose here-document does not end"),
    ('Bash(git commit -m "$(cat <<EOF\ntext\n)")', "whose quoting does not close"),  # inside quotes the reason is the quote's
    ("Bash(curl " + "x" * 4000 + ")", "that is longer than the audit reads"),
    ("Bash(" + ";".join(f"*q* {number}" for number in range(9)) + ")", "that spells more wildcard programs than the audit follows"),
]


class ExitAuditReadersTest(unittest.TestCase):
    """The audit's readers and its classification, without a home directory."""

    def test_each_exit_rule(self):
        for rule, what in EXIT_RULES:
            with self.subTest(rule=rule):
                self.assertEqual(ddl_setup.claude_rule_findings(rule), [("exit", what)])

    def test_each_wrapper_rule(self):
        for rule in WRAPPER_RULES:
            with self.subTest(rule=rule):
                self.assertEqual([status for status, _ in ddl_setup.claude_rule_findings(rule)], ["wrapper"])

    def test_narrow_rules_are_not_findings(self):
        for rule in NARROW_RULES:
            with self.subTest(rule=rule):
                self.assertEqual(ddl_setup.claude_rule_findings(rule), [])

    def test_rules_that_cannot_be_read_say_why(self):
        for rule, why in UNAUDITED_RULES:
            with self.subTest(rule=rule):
                self.assertEqual(ddl_setup.claude_rule_findings(rule), [("unaudited", why)])

    def test_no_rule_takes_long_whatever_it_spells(self):
        def nested(levels, padding):
            """`bash -c "echo $(…)"` inside itself, with a padded command in the middle."""
            text = "git status " + "x " * padding
            for _ in range(levels):
                text = 'bash -c "echo $(' + text + ')"'
            return text

        long = [("unaudited", "that is longer than the audit reads")]
        many = ("unaudited", "that spells more wildcard programs than the audit follows")
        shapes = [
            ("Bash(" + "*e* " * 6 + "x)", [("wrapper", "bundle exec")]),       # a wildcard program in every word:
            ("Bash(" + "*e* " * 8 + "x)", [("wrapper", "bundle exec")]),       # the names it may stand for multiply
            ("Bash(" + "*e* " * 400 + "x)", [("wrapper", "bundle exec")]),
            ("Bash(" + nested(8, 50000) + ")", long),                          # a substitution in a script, eight deep, 100,000 characters
            ("Bash(" + nested(8, 1800) + ")", []),                             # the same within the length the audit reads
            ("Bash(" + nested(8, 0).replace("git status", "git push") + ")", [("exit", "git push")]),
            ("Bash(" + "*" * 100000 + "x)", long),                             # a hundred thousand wildcards
            ("Bash(" + "*" * 3990 + "x)", []),
            ("Bash(" + "*a" * 1990 + ")", []),
            ("Bash(" + ";".join(f"*q* *q* {number}" for number in range(300)) + ")", [many]),
            ("Bash(*a* -c '" + ";".join(f"*a* c{number}" for number in range(400)) + "')", [("wrapper", "bash")]),
            ("Bash(" + ";".join(f"sudo env nice time c{number}" for number in range(160)) + ")", []),
        ]
        patterns = [([""] * 100000, long), ([["a", "b"]] * 8 + ["x"] * 1900, long), ([["bash", "sh"]] * 8, [])]
        start = time.perf_counter()
        found = [ddl_setup.claude_rule_findings(rule) for rule, _ in shapes]
        expanded = [ddl_setup.codex_pattern_findings(pattern) for pattern, _ in patterns]
        spent = time.perf_counter() - start
        for (rule, expected), got in zip(shapes, found):
            with self.subTest(rule=rule[:40], length=len(rule)):
                self.assertEqual(got, expected)
        self.assertEqual(expanded, [expected for _, expected in patterns])
        # Each takes a few milliseconds; the bound is generous so that a busy machine does not fail the test.
        self.assertLess(spent, 2, f"{len(shapes) + len(patterns)} rules took {spent:.2f} s")

    def test_the_lists_name_the_programs_of_a_general_default(self):
        audited = set(ddl_setup.AUDITED)
        for names in ("npm pnpm yarn bun cargo gem twine uv poetry docker podman", "rsync scp sftp ssh rclone nc ncat socat ftp curl wget",
                      "gh glab git", "env xargs sudo nohup timeout time nice command exec eval watch parallel doas su setsid stdbuf "
                      "gtimeout busybox", "bash sh zsh fish dash ksh", "python python3 node ruby perl deno bun php lua osascript pwsh",
                      "npx uvx bunx pipx uv npm pnpm yarn poetry pdm hatch bundle"):
            self.assertLessEqual(set(names.split()), audited)
        self.assertEqual(ddl_setup.PUBLISHES["gem"], "push")
        self.assertEqual(ddl_setup.PUBLISHES["twine"], "upload")
        self.assertLessEqual({"send-email", "push", "pull"}, ddl_setup.GIT_EXITS)
        self.assertEqual(ddl_setup.GIT_PAIRS, {"lfs": "push", "subtree": "push"})
        self.assertEqual({f"{program} {form}" for program, forms in ddl_setup.RUNNER_FORMS.items() for form in forms}, {
            "pipx run", "uv run", "uv tool run", "npm exec", "npm x", "pnpm exec", "pnpm dlx", "yarn dlx", "yarn exec",
            "poetry run", "pdm run", "hatch run", "bundle exec", "bun x"})
        self.assertNotIn("cargo", ddl_setup.RUNNER_FORMS)  # `cargo run` runs the project's own binary

    def test_rule_parts(self):
        for rule, parts in [("Bash", ("", "")), ("Bash(*)", ("", "*")), ("Bash(git push:*)", ("git push", ":*")),
                            ("Bash(git push *)", ("git push", " *")), ("Bash(git pu*)", ("git pu", "*")),
                            ("Bash(git push)", ("git push", "")), ("Bash(a\nb)", ("a\nb", "")),
                            ("Read", None), ("BashOutput", None), ("Bash(x", None)]:
            with self.subTest(rule=rule):
                self.assertEqual(ddl_setup.claude_rule_parts(rule), parts)

    def test_open_words_and_several_commands_in_one_rule(self):
        for rule, expected in [
                ("Bash(git pu*)", [("exit", "git pull/push")]),         # the rule stops inside the verb
                ("Bash(git pus*)", [("exit", "git push")]),
                ("Bash(git l*)", [("exit", "git lfs push")]),
                ("Bash(git * main)", [("exit", "git (any subcommand)")]),
                ("Bash(gh pr v*)", [("exit", "gh pr …")]),               # not yet the read verb `view`; the word is not shown
                ("Bash(gh frobnicate now:*)", [("exit", "gh … …")]),     # only the audit's own words are shown
                ("Bash(g*)", [("wrapper", "gtimeout")]),                 # the first wrapper the open word may become
                ("Bash(*e* *e* x)", [("wrapper", "bundle exec")]),
                ("Bash(s* git status)", [("exit", "scp")]),              # no wrapper among them: the first exit it may become
                ("Bash(gi*)", [("exit", "git (any subcommand)")]),
                ("Bash(npm:*)", [("exit", "npm publish")]),              # the open verb includes publish
                ("Bash(bun:*)", [("wrapper", "bun")]),                   # an interpreter first: it covers its publish verb
                ("Bash(bun publish:*)", [("exit", "bun publish")]),
                ("Bash(uv:*)", [("exit", "uv publish")]),                # one line: the publish verb, which its runner does not narrow
                ("Bash(uv run:*)", [("wrapper", "uv run")]),
                ("Bash(uv tool:*)", [("wrapper", "uv tool run")]),
                ("Bash(npx:*)", [("wrapper", "npx")]),
                ("Bash(pdm:*)", [("wrapper", "pdm")]),
                ("Bash(npm * git push)", [("exit", "npm publish")]),     # the wildcard verb may be publish
                ("Bash(python3.12 -c:*)", [("wrapper", "python")]),      # the version is not shown
                ("Bash(python3." + "9" * 3000 + ":*)", []),             # no such name: nothing of it can reach a line
                ("Bash(cd /srv/app && git push)", [("exit", "git push")]),
                ("Bash(git pull && git push:*)", [("exit", "git pull"), ("exit", "git push")]),
                ("Bash(bash -c 'git pull'*)", [("wrapper", "bash"), ("exit", "git pull")]),
                ("Bash(git status && ls:*)", []),
                ("Bash(git status\ngit push)", [("exit", "git push")]),
                ("Bash(FOO=1 *)", [("wrapper", "FOO=…")]),               # an assignment only: its name, never its value
                ("Bash(ARR[0]=x KEY+=y *)", [("wrapper", "ARR=…")]),
                ("Bash(ÜBER=1 *)", [("wrapper", "…=…")]),
                ("Bash(" + "A" * 50 + "=1 *)", [("wrapper", "…=…")]),
                ("Bash", [("wrapper", "")]),
                ("Bash(* --version)", [("wrapper", "*")]),
                ("Bash(/usr/bin/*)", [("wrapper", "…/bin/*")]),
                ("Bash(/usr/local/sbin/*)", [("wrapper", "…/sbin/*")]),
                ("Bash(" + "*" * 200 + "x push)", []),                   # many wildcards cost nothing
                ("Bash(" + "*a" * 200 + ")", [])]:
            with self.subTest(rule=rule):
                self.assertEqual(ddl_setup.claude_rule_findings(rule), expected)

    def test_shell_text_is_split_into_commands(self):
        here = ddl_setup.HERE
        for text, expected in [
                ("git status && ls -la | head", ([["git", "status"], ["ls", "-la"]], ["head"], [])),
                ("echo 'a; b' \"c | d\" e\\ f", ([], ["echo", "a; b", "c | d", "e f"], [])),
                ("a;", ([["a"]], [], [])),                                # the text ends at a separator: a command may start
                ("", ([], [], [])),
                # A substitution in double quotes is read once, as its own text; `$` stands for it in the word.
                ("echo \"x $(git push) `ls`\" y", ([], ["echo", "x $ $", "y"], ["git push", "ls"])),
                ("echo \"\\$(ls) \\\"q\\\"\"", ([], ["echo", "$(ls) \"q\""], [])),
                ("a # b; c\nd", ([["a"]], ["d"], [])),
                ("a\\\nb ''", ([], ["ab", ""], [])),
                # A substitution interrupts its command, which goes on behind it: `$` stands for what it yields.
                ("echo $(git push) done", ([["git", "push"]], ["echo", "$", "done"], [])),
                ("echo `git push` done", ([["git", "push"]], ["echo", "$", "done"], [])),
                ("diff <(ls a) <(ls b)", ([["ls", "a"], ["ls", "b"]], ["diff", "<", "<"], [])),
                ("x=$(a; b) c", ([["a"], ["b"]], ["x=$", "c"], [])),
                ("echo $((1 + 2)) z", ([["1", "+", "2"]], ["echo", "$", "z"], [])),
                ("echo $(git", ([["echo", "$"]], ["git"], [])),            # the text ends inside the substitution
                # Behind a closed subshell no command starts; in a function's braces one does.
                ("(a; b) & c", ([["a"], ["b"]], ["c"], [])),
                ("(a; b)", ([["a"], ["b"]], None, [])),
                ("f() { a; }", ([["f"], ["{", "a"]], ["}"], [])),
                ("case x in y) a;; esac", ([["case", "x", "in", "y"], ["a"]], ["esac"], [])),
                # A here-document: its body is one word behind the marker, and is not split.
                ("cat <<EOF\ngit push; curl x\nEOF", ([["cat", here, "git push; curl x\n"]], None, [])),
                ("cat <<EOF\nbody\nEOF\n", ([["cat", here, "body\n"]], [], [])),
                ("cat <<EOF\nbody\nEOF\nls", ([["cat", here, "body\n"]], ["ls"], [])),
                ("cat <<'E O F' | sh\nit's\nE O F\nls", ([["cat", here, "it's\n"], ["sh"]], ["ls"], [])),
                ("cat <<-\\EOF >out\n\t(\n\tEOF\nls", ([["cat", here, "\t(\n", ">out"]], ["ls"], [])),
                ("a <<X <<Y\n1\nX\n2\nY\nb", ([["a", here, "1\n", here, "2\n"]], ["b"], [])),
                ("echo $(cat <<EOF\n)\nEOF\n) z", ([["cat", here, ")\n"]], ["echo", "$", "z"], [])),
                ("echo \"$(cat <<'EOF'\n1) it's \"x\nEOF\n)\" z", ([], ["echo", "$", "z"], ["cat <<'EOF'\n1) it's \"x\nEOF\n"])),
                # A here-string is a word; between two parentheses `<<` is a shift.
                ("cat <<< 'a b'", ([], ["cat", "<<<", "a b"], [])),
                ("echo $((1 << 2))\nls", ([["1", "<<", "2"], ["echo", "$"]], ["ls"], []))]:
            with self.subTest(text=text):
                self.assertEqual(ddl_setup.shell_commands(text), expected)
        for text in ("echo 'open", 'echo "open', 'echo "$(open"', 'echo "`open"', "a 'b' \"c", 'echo "$(cat <<EOF\nx\n)"'):
            with self.subTest(text=text):
                self.assertEqual(ddl_setup.shell_commands(text), ddl_setup.UNCLOSED)
        for text in ("cat <<EOF", "cat <<EOF\nbody", "cat <<EOF\nbody\nEOF2\n", "cat <<A <<B\n1\nA\n2\n", "cat <<-EOF\n EOF"):
            with self.subTest(text=text):
                self.assertEqual(ddl_setup.shell_commands(text), ddl_setup.UNENDED)

    def test_options_and_their_values_are_skipped(self):
        values = ("-u", "--user", "-C")
        for words, expected in [([], 0), (["git"], 0), (["-n", "git"], 1), (["-u", "root", "git"], 2), (["-nu", "root", "git"], 2),
                                (["-uroot", "git"], 1), (["--user", "root", "git"], 2), (["--user=root", "git"], 1),
                                (["-u"], 2), (["--", "-u"], 1), (["-", "x"], 0), (["-n", "-E", "-C", "3", "ls"], 4)]:
            with self.subTest(words=words):
                self.assertEqual(ddl_setup.after_options(words, values), expected)

    def test_codex_rule_reader(self):
        text = ('# comment\n'
                'prefix_rule(pattern=["git", "push"], decision="allow")\n'
                'prefix_rule(\n    pattern = ["gh", ["pr", "issue"], "create"],\n    justification = "x",\n)\n'
                'prefix_rule(pattern=["git", "push"], decision="prompt")\n'
                'prefix_rule(pattern=["rm"], decision="forbidden")\n'
                'prefix_rule(pattern=("ls",), decision="allow")\n'
                'prefix_rule(pattern=NAME, decision="allow")\n'
                'prefix_rule(pattern=["a"], decision=NAME)\n'
                'prefix_rule(pattern=[], decision="allow")\n'
                'prefix_rule(pattern=["a", []])\n'
                'prefix_rule(pattern="git push")\n'
                'prefix_rule(pattern=NAME, decision="prompt")\n'
                'other_rule(pattern=["curl"])\n'
                'host.prefix_rule(pattern=["curl"])\n')
        self.assertEqual(ddl_setup.codex_allow_rules(text), [
            (2, ["git", "push"]), (3, ["gh", ["pr", "issue"], "create"]), (9, ["ls"]),
            (10, None), (11, None), (12, None), (13, None), (14, None)])
        self.assertEqual(ddl_setup.codex_allow_rules(""), [])
        for broken in ('prefix_rule(pattern=["git"', "prefix_rule(pattern=[\x00])", "def (:\n"):
            with self.subTest(broken=broken), self.assertRaises((SyntaxError, ValueError)):
                ddl_setup.codex_allow_rules(broken)

    def test_codex_reader_executes_nothing(self):
        with tempfile.TemporaryDirectory(prefix="ddl setup test ") as tmp:
            marker = pathlib.Path(tmp) / "ran"
            text = (f"open({str(marker)!r}, 'w').close()\n"
                    f"prefix_rule(pattern=[open({str(marker)!r}, 'w').name], decision='allow')\n")
            self.assertEqual(ddl_setup.codex_allow_rules(text), [(2, None)])
            self.assertFalse(marker.exists())

    def test_a_rules_file_is_parsed_without_a_warning(self):
        # `"\d"` is an escape Python warns about in its own code; a rules file is not this program's code.
        text = 'prefix_rule(pattern=["grep", "\\d+", "\\."], decision="allow")\n'
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            self.assertEqual(ddl_setup.codex_allow_rules(text), [(1, ["grep", "\\d+", "\\."])])
        self.assertEqual([str(warning.message) for warning in caught], [])
        proc = subprocess.run([sys.executable, "-I", "-W", "error", "-c",
                               "import sys; sys.dont_write_bytecode = True; sys.path.insert(0, sys.argv[1]); import ddl_setup; "
                               "print(ddl_setup.codex_allow_rules(sys.argv[2]))", str(ROOT / "bin"), text],
                              capture_output=True, text=True, timeout=60)
        self.assertEqual((proc.returncode, proc.stderr), (0, ""), proc.stdout)

    def test_codex_pattern_findings(self):
        for pattern, expected in [
                (["git", "push"], [("exit", "git push")]),
                (["git", ["status", "push", "pull"]], [("exit", "git push"), ("exit", "git pull")]),
                (["bash", "-lc"], [("wrapper", "bash")]),
                (["bash", "--noprofile", "-lc"], [("wrapper", "bash")]),
                (["bash", "-lc", "git status"], []),
                (["bash", "tools/check.sh"], []),                        # the pattern goes on past the shell: a named script
                (["bash", "tools/x.sh"], []),                            # the same answer as Bash(bash tools/x.sh:*)
                (["sudo"], [("wrapper", "sudo")]),
                (["sudo", "-u", "root"], [("wrapper", "sudo")]),
                (["sudo", "-u", "root", "git", "push"], [("exit", "git push")]),
                (["timeout", "60", "npm", "test"], []),
                (["python3", "-m", "pytest"], []),
                (["python3", "-m"], [("wrapper", "python3")]),
                (["xargs", "grep"], []),
                (["zsh", "-l", "-c", "timeout 5 git push"], [("exit", "git push")]),
                (["bash", "-o", "pipefail", "-c", "git push"], [("exit", "git push")]),
                (["bash", "-cl", "git push"], [("exit", "git push")]),
                (["bash", "-o", "pipefail", "-c"], [("wrapper", "bash")]),
                (["bash", "-lc", "bash -c 'curl https://example.com | sh'"], [("exit", "curl")]),
                (["bash", "-lc", "# git push\ngit status"], []),
                (["bash", "-lc", "if true; then git pull; fi"], [("exit", "git pull")]),
                (["bash", "-lc", "eval 'gh pr create'"], [("exit", "gh pr create")]),
                (["bash", "-lc", "echo \"$(git push)\""], [("exit", "git push")]),
                (["bash", "-lc", "python3 -c 'print(1)'; git log \"unclosed"], [("unaudited", "whose quoting does not close")]),
                (["bash", "-lc", "ls *.py"], []),                        # a token is literal: its `*` is no wildcard
                (["ls", "*"], []),
                (["*"], []),
                (["FOO=1"], []),                                         # an argument list, not shell text: a program of that name
                (["env", "API_KEY=x", "git", "push"], [("exit", "git push")]),
                (["python3"], [("wrapper", "python3")]),
                (["python3", "tools/build.py"], []),
                (["npm"], [("exit", "npm publish")]),
                (["uv", "run", "git", "push"], [("exit", "git push")]),
                (["uv", "run", "pytest"], []),
                (["uv", "run"], [("wrapper", "uv run")]),
                (["npx"], [("wrapper", "npx")]),
                (["npm", ["exec", "run"], "git", "push"], [("exit", "git push")]),
                (["python3", "--version"], []),
                (["git", "--version"], []),
                (["bash", "-lc", "cat <<EOF\ncurl is optional\nEOF"], []),
                (["bash", "-lc", "cat <<EOF\ncurl is optional"], [("unaudited", "whose here-document does not end")]),
                (["curl"] + ["x"] * 4000, [("unaudited", "that is longer than the audit reads")]),
                (["echo", "x" * 4001], [("unaudited", "that is longer than the audit reads")]),
                ([["a", "b"]] * 8 + ["x"] * 70, [("unaudited", "that is longer than the audit reads")]),
                (["glab", "mr", ["view", "merge"]], [("exit", "glab mr merge")]),
                (["gh", "pr", ["view", "list"]], [])]:
            with self.subTest(pattern=pattern):
                self.assertEqual(ddl_setup.codex_pattern_findings(pattern), expected)
        self.assertIsNone(ddl_setup.codex_pattern_findings([["a", "b"]] * 9))

    def test_toml_scanner(self):
        text = ('# approval_policy = "commented"\n'
                'approval_policy = "never"   # trailing comment\n'
                "sandbox_mode = 'danger-full-access'\n"
                'title = "a # not a comment \\"quoted\\""\n'
                "limit = 1_000\nnegative = -3\nenabled = true\ndisabled = false\n"
                "ratio = 1.5\nwhen = 2026-01-01\nlist = [1, 2]\ninline = { a = 1 }\n"
                'notes = """\napproval_policy = "inside a string"\n[not.a.table]\n"""\n'
                "single = '''\nsandbox_mode = 'inside'\n'''\n"
                'oneline = """x"""\n'
                'writable = [\n  "approval_policy = 1",\n  "b",  # [x]\n]\n'
                'after = "the array"\n'
                "a.b = 1\n"
                '"quoted key" = 2\n'
                "approval_policy = \"second\"\n"
                "[agents]\nmax_concurrent_threads_per_session = 5\n"
                '  [ profiles . "x.y" ]  # header comment\napproval_policy = "on-request"\n'
                "[[servers]]\nname = 'one'\n"
                "broken line without equals\n= 3\n")
        self.assertEqual(ddl_setup.toml_scalars(text), {
            "approval_policy": "never", "sandbox_mode": "danger-full-access", "title": 'a # not a comment "quoted"',
            "limit": 1000, "negative": -3, "enabled": True, "disabled": False, "inline.a": 1, "after": "the array", "a.b": 1,
            "quoted key": 2, "agents.max_concurrent_threads_per_session": 5,
            "profiles.x.y.approval_policy": "on-request", "servers[].name": "one"})
        self.assertEqual(ddl_setup.toml_scalars(""), {})
        self.assertEqual(ddl_setup.toml_scalars("agents.max_concurrent_threads_per_session = 5\n"),
                         {"agents.max_concurrent_threads_per_session": 5})
        self.assertEqual(ddl_setup.toml_scalars("# [agents]\n# max_concurrent_threads_per_session = 5\n"), {})
        # A value Python cannot convert is skipped, never a traceback.
        self.assertEqual(ddl_setup.toml_scalars("huge = " + "9" * 5000 + "\nafter = 1\n").get("after"), 1)

    def test_toml_inline_tables(self):
        key = "agents.max_concurrent_threads_per_session"
        for text, expected in [
                ("agents = { max_concurrent_threads_per_session = 5 }\n", {key: 5}),
                ("agents = {max_concurrent_threads_per_session=5}  # the limit\n", {key: 5}),
                ('agents = { name = "a, b } c", max_concurrent_threads_per_session = 5, on = true }\n',
                 {"agents.name": "a, b } c", key: 5, "agents.on": True}),
                ("agents = { roles = [1, 2], nested = { deep = 1 }, max_concurrent_threads_per_session = 5 }\n", {key: 5}),
                ("[profiles.fast]\nagents = { max_concurrent_threads_per_session = 5 }\n", {"profiles.fast." + key: 5}),
                ("agents = {\n  max_concurrent_threads_per_session = 5\n}\nafter = 1\n", {"after": 1}),  # over several lines: skipped
                ("# agents = { max_concurrent_threads_per_session = 5 }\n", {}),
                ("agents = { }\nempty = {}\n", {})]:
            with self.subTest(text=text):
                self.assertEqual(ddl_setup.toml_scalars(text), expected)

    def test_a_line_shows_only_the_audits_own_words(self):
        for what in ("git push", "git (any subcommand)", "git pull/push", "git lfs push", "gh pr …", "glab mr create",
                     "FOO=…", "…=…", "…/bin/*", "…/sbin/*", "*", "", "python", "npm publish", "uv tool run", "npm exec",
                     *sorted(ddl_setup.REASONS)):
            with self.subTest(what=what):
                self.assertEqual(ddl_setup.own_words(what), what)
        for what in ("ghp_token", "git ghp_token", "gh api /repos?token=x", "FOO=bar", "…/opt/*", "curl -u user:pass", "x" * 41 + "=…",
                     "python3.12", "python3." + "1" * 50):
            with self.subTest(what=what):
                self.assertEqual(ddl_setup.own_words(what), "…")
        lines = ddl_setup.finding_lines("Bash", [("exit", "git push"), ("exit", "git push"), ("exit", "git (any subcommand)"),
                                                 ("wrapper", "env"), ("wrapper", ""), ("wrapper", "TOKEN=…"),
                                                 ("wrapper", "…/bin/*"), ("exit", "curl -u user:pass"),
                                                 ("unaudited", "whose quoting does not close")])
        self.assertEqual(lines, [
            ("exit", "Bash(git push …) passes git push unasked"),
            ("exit", "Bash(git …) passes git (any subcommand) unasked"),
            ("wrapper", "Bash(env …) wraps any command"),
            ("wrapper", "Bash wraps any command"),
            ("wrapper", "Bash(TOKEN=…) wraps any command"),
            ("wrapper", "Bash(…/bin/* …) passes every program of a directory unasked"),
            ("exit", "Bash(…) passes … unasked"),
            ("unaudited", "Bash rule whose quoting does not close; not audited")])
        self.assertEqual(ddl_setup.finding_lines("prefix_rule", [("exit", "git push"), ("unaudited", "whose program is a variable")]),
                         [("exit", "prefix_rule(git push …) passes git push unasked"),
                          ("unaudited", "prefix_rule whose program is a variable; not audited")])

    def test_no_word_of_a_rule_reaches_a_line(self):
        # Every word of each rule is replaced in turn by a marker; no line built from the findings may carry it.
        marker = "MARK" + "9z8y7x"
        rules = [rule for rule, _ in EXIT_RULES] + WRAPPER_RULES + NARROW_RULES + [rule for rule, _ in UNAUDITED_RULES]
        for rule in rules:
            parts = ddl_setup.claude_rule_parts(rule)
            if not parts or not parts[0]:
                continue
            words = parts[0].split(" ")
            variants = [" ".join(words[:at] + [marker] + words[at + 1:]) for at in range(len(words))]
            variants += [" ".join(words[:at] + [word + marker] + words[at + 1:]) for at, word in enumerate(words)]
            for body in variants:
                found = ddl_setup.claude_rule_findings(f"Bash({body}{parts[1]})")
                text = "\n".join(line for _, line in ddl_setup.finding_lines("Bash", found))
                self.assertNotIn(marker, text, body)


if __name__ == "__main__":
    unittest.main(verbosity=1)
