#!/usr/bin/env python3
"""Tests for the gate's three files: the entry tools/ddl_gate.py (a launcher), the code it loads,
tools/ddl_gate_core.py, and the Run subcommands, tools/ddl_run.py.

They pin the import boundary (no hook event imports ddl_run, and the Run words load it and the gate's
code once each), the direct `ddl_run.py` command line (the same output, errors and exit codes as
`ddl_gate.py` for report, run-start, run-item and snapshot), the installed forms (linked and copied
files find their siblings, write no `__pycache__` beside themselves, and a copy that lacks its modules
fails open), the bytecode cache under the state directory (created in a DDL project only, used only
while it is private, passed over when its code cannot be loaded), the shipping of all three files by
tools/build.py and tools/check_ddl.py, and `snapshot` in real repositories (what the tree holds, HEAD
or none, a linked work tree, the second Git directory, the refused existing ref, the identity, the
order of `snapshot list`, the ledger event, and the index, HEAD, branches and files left as they were).
Every project, repository, state directory, grant store and output tree is disposable; this
repository's tree is never the working directory of a gate process, and no snapshot is made outside
the test's temporary directory.

Usage:
  python3 tools/test_ddl_run.py
  python3 -I tools/test_ddl_run.py
"""
import contextlib
import importlib.util
import inspect
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
import unittest
from unittest import mock

TOOLS = pathlib.Path(__file__).resolve().parent
REPO = TOOLS.parent
sys.path.insert(0, str(TOOLS))
import build  # noqa: E402
import check_ddl  # noqa: E402
import ddl_gate_core  # noqa: E402
import ddl_run  # noqa: E402

GATE_FILES = ("ddl_gate.py", "ddl_gate_core.py", "ddl_run.py")
GATE, CORE, RUN = (str(TOOLS / name) for name in GATE_FILES)
FIXTURES = TOOLS / "fixtures"
MARKER_LINE = "→ DDL-PROTOCOL"
EVENTS = ("pre-tool-use", "stop", "user-prompt-submit", "session-start")
EVENT_NAMES = {"pre-tool-use": "PreToolUse", "session-start": "SessionStart", "stop": "Stop",
               "user-prompt-submit": "UserPromptSubmit"}
CLOSED = {runtime: str(FIXTURES / (runtime + "_closed_in_turn.jsonl")) for runtime in ("claude", "codex")}


def launcher():
    """tools/ddl_gate.py as a module: its functions, without running it."""
    spec = importlib.util.spec_from_file_location("ddl_gate_launcher_for_test", GATE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def imported(stderr):
    """The module names `python3 -X importtime` reports, in order."""
    return [line.rsplit("|", 1)[-1].strip() for line in stderr.splitlines() if line.startswith("import time:")][1:]


class SplitTest(unittest.TestCase):
    """A disposable DDL project (instruction file with the marker line, `.git` bounding the search), an
    unrelated repository, and a private state directory and grant store for every gate process."""

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="ddl-run-test-"))
        self.addCleanup(shutil.rmtree, str(self.tmp), True)
        self.state = self.tmp / "state"
        self.grants = self.tmp / "grants"
        self.project = self.tmp / "project"
        (self.project / ".git").mkdir(parents=True)
        (self.project / "CLAUDE.md").write_text("# Project\n\n" + MARKER_LINE + "\n", encoding="utf-8")
        self.unrelated = self.tmp / "unrelated"
        (self.unrelated / ".git").mkdir(parents=True)
        (self.unrelated / "design.md").write_text("# design.md\n", encoding="utf-8")
        patcher = mock.patch.dict(os.environ, {"DDL_GATE_GRANT_DIR": str(self.grants)})
        patcher.start()
        self.addCleanup(patcher.stop)

    def env(self, **extra):
        return dict(os.environ, DDL_GATE_STATE_DIR=str(self.state), DDL_GATE_GRANT_DIR=str(self.grants), **extra)

    def run_script(self, script, argv, data=None, cwd=None, flags=("-I",), env=None):
        stdin = data if isinstance(data, str) or data is None else json.dumps(data)
        return subprocess.run([sys.executable, *flags, str(script), *argv], input=stdin, capture_output=True,
                              encoding="utf-8", env=env or self.env(), cwd=str(cwd or self.project), timeout=60)

    def payload(self, runtime, event, cwd, session="S", transcript=None, **extra):
        data = json.loads((FIXTURES / "payload_pre_tool_use_{}.json".format(runtime)).read_text())
        data.update(session_id=session, transcript_path=transcript, cwd=str(cwd), hook_event_name=EVENT_NAMES[event])
        if event != "pre-tool-use":
            for key in ("tool_name", "tool_input", "tool_use_id"):
                data.pop(key, None)
        data.update(extra)
        return data

    def hook(self, script, runtime, event, cwd, **fields):
        proc = self.run_script(script, [event, "--runtime", runtime], self.payload(runtime, event, cwd, **fields), cwd)
        self.assertEqual((proc.returncode, proc.stderr), (0, ""))
        return proc.stdout

    def assert_denied(self, stdout):
        self.assertEqual(json.loads(stdout)["hookSpecificOutput"]["permissionDecision"], "deny")

    def prepare(self, script=GATE, runtime="claude"):
        data = {"language": "en", "decision": "Split the gate", "recommendation": "Approve",
                "consequence": "Three files", "detail": "## Plan\n\n- I1\n"}
        proc = self.run_script(script, ["prepare-report", "--runtime", runtime], data)
        self.assertEqual((proc.returncode, proc.stderr), (0, ""))
        return json.loads(proc.stdout)

    def bytecode(self, directory):
        return sorted(str(path.relative_to(directory)) for path in pathlib.Path(directory).rglob("*.pyc"))


class ImportBoundaryTest(SplitTest):
    def test_no_hook_event_imports_the_run_module(self):
        for runtime in ("claude", "codex"):
            for cwd in (self.project, self.unrelated):
                for event in EVENTS:
                    with self.subTest(runtime=runtime, cwd=cwd.name, event=event):
                        proc = self.run_script(GATE, [event, "--runtime", runtime],
                                               self.payload(runtime, event, cwd, transcript=CLOSED[runtime]), cwd,
                                               flags=("-I", "-X", "importtime"))
                        self.assertEqual(proc.returncode, 0, proc.stderr)
                        names = imported(proc.stderr)
                        self.assertNotIn("ddl_run", names)
                        self.assertEqual(names.count("ddl_gate_core"), 1)

    def test_in_process_dispatch_leaves_the_run_module_unloaded(self):
        script = ("import io, json, sys\n"
                  "sys.path.insert(0, sys.argv[1])\n"
                  "import ddl_gate_core\n"
                  "seen = []\n"
                  "for data in json.loads(sys.argv[2]):\n"
                  "    sys.stdin, out = io.StringIO(json.dumps(data['payload'])), io.StringIO()\n"
                  "    sys.stdout, real = out, sys.stdout\n"
                  "    try:\n"
                  "        code = ddl_gate_core.main(data['argv'])\n"
                  "    finally:\n"
                  "        sys.stdout = real\n"
                  "    seen.append([code, 'ddl_run' in sys.modules])\n"
                  "sys.stdin = io.StringIO('')\n"
                  "sys.stdout, real = io.StringIO(), sys.stdout\n"
                  "ddl_gate_core.main(['report', '--session', 'S'])\n"
                  "sys.stdout = real\n"
                  "print(json.dumps([seen, 'ddl_run' in sys.modules]))\n")
        calls = [{"argv": [event, "--runtime", runtime],
                  "payload": self.payload(runtime, event, cwd, transcript=CLOSED[runtime])}
                 for runtime in ("claude", "codex") for cwd in (self.project, self.unrelated) for event in EVENTS]
        proc = subprocess.run([sys.executable, "-I", "-c", script, str(TOOLS), json.dumps(calls)], capture_output=True,
                              encoding="utf-8", env=self.env(), cwd=str(self.project), timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        seen, after_report = json.loads(proc.stdout)
        self.assertEqual(seen, [[0, False]] * len(calls))
        self.assertTrue(after_report)  # the positive control: a Run word loads it

    def test_a_run_word_loads_the_run_module_and_the_gate_once_each(self):
        for script in (GATE, RUN):
            with self.subTest(script=pathlib.Path(script).name):
                proc = self.run_script(script, ["report", "--session", "S"], flags=("-I", "-X", "importtime"))
                self.assertEqual(proc.returncode, 0, proc.stderr)
                names = imported(proc.stderr)
                self.assertEqual((names.count("ddl_gate_core"), names.count("ddl_gate"), names.count("ddl_run")),
                                 (1, 0, 0 if script == RUN else 1))


class DirectInvocationTest(SplitTest):
    def same(self, argv, data=None, cwd=None):
        """Both entries on the same arguments: (returncode, stdout, stderr) of each, which must agree."""
        results = [self.run_script(script, argv, data, cwd) for script in (GATE, RUN)]
        outcomes = [(proc.returncode, proc.stdout, proc.stderr) for proc in results]
        self.assertEqual(outcomes[0], outcomes[1])
        return outcomes[0]

    def test_errors_and_counts_match_the_gates(self):
        transcript = str(FIXTURES / "report_count_claude.jsonl")
        cases = [(["report"], None, self.project, 2), (["report", "--run", "N-1"], None, self.project, 2),
                 (["report", "--transcript", transcript], None, self.project, 2),
                 (["report", "--bogus", "1"], None, self.project, 2),
                 (["report", "--run", "N-000000000000"], None, self.project, 2),
                 (["report", "--run", "N-000000000000"], None, self.unrelated, 2),
                 (["report", "--session", "S"], None, self.unrelated, 0),
                 (["report", "--session", "S", "--language", "en"], None, self.project, 0),
                 (["report", "--transcript", transcript, "--runtime", "claude"], None, self.project, 0),
                 (["report", "--language=en", "--runtime=codex", "--transcript=" + str(self.tmp / "missing")], None,
                  self.project, 0),
                 (["run-item"], None, self.project, 2), (["run-item", "N-000000000000", "I1", "done"], None, self.project, 2),
                 (["run-item", "N-000000000000", "I1", "done"], None, self.unrelated, 2),
                 (["run-item", "N-000000000000", "I1", "passed"], None, self.project, 2),
                 (["run-start"], "not json", self.project, 2), (["run-start"], {}, self.project, 2),
                 (["run-start", "--runtime", "gemini"], {"report": "R-0123456789abcdef", "items": []}, self.project, 2),
                 (["run-start", "--force"], {"report": "R-0123456789abcdef", "items": []}, self.project, 2),
                 (["run-start"], {"report": "R-0123456789abcdef", "items": []}, self.project, 2),
                 (["run-start"], {"report": "R-0123456789abcdef", "items": []}, self.unrelated, 2)]
        for argv, data, cwd, code in cases:
            with self.subTest(argv=argv, cwd=cwd.name):
                returncode, stdout, stderr = self.same(argv, data, cwd)
                self.assertEqual(returncode, code, stderr)
                if code == 2:
                    self.assertEqual(stdout, "")
                    self.assertRegex(stderr, r"^DDL (report|run): ")
                else:
                    self.assertEqual((len(stdout.splitlines()), stderr), (4, ""))

    def test_a_run_started_through_one_entry_is_driven_through_the_other(self):
        prepared = self.prepare()
        items = [{"id": "I1", "kind": "write", "files": ["tools/ddl_run.py"]}, {"id": "I2", "kind": "verify", "after": ["I1"]}]
        proc = self.run_script(RUN, ["run-start"], {"report": prepared["reportId"], "items": items})
        self.assertEqual((proc.returncode, proc.stderr), (0, ""))
        started = json.loads(proc.stdout)
        self.assertEqual(set(started), {"run", "path"})
        self.assertEqual(self.same(["report", "--run", started["run"]])[1].splitlines(),
                         ["Questions: 0 (approved 0, revised 0, timed out 0)",
                          "Waiting: human 0 min (median to answer not measured, longest not measured)",
                          "Denials: 0", "Grant: none"])
        for script, status in ((GATE, "running"), (RUN, "done")):
            proc = self.run_script(script, ["run-item", started["run"], "I1", status])
            self.assertEqual((proc.returncode, proc.stderr), (0, ""))
            self.assertEqual(json.loads(proc.stdout), {"run": started["run"], "item": "I1", "status": status})
        run = json.loads(pathlib.Path(started["path"]).read_text(encoding="utf-8"))
        self.assertEqual([item["status"] for item in run["items"]], ["done", "ready"])
        # One Run per plan, refused alike by either entry.
        returncode, stdout, stderr = self.same(["run-start"], {"report": prepared["reportId"], "items": []})
        self.assertEqual((returncode, stdout), (2, ""))
        self.assertIn(started["run"], stderr)

    def test_ddl_run_without_one_of_its_words_is_a_usage_error(self):
        for argv in ([], ["status"], ["prepare-report", "--runtime", "claude"], ["pre-tool-use", "--runtime", "claude"]):
            with self.subTest(argv=argv):
                proc = self.run_script(RUN, argv, "{}")
                self.assertEqual((proc.returncode, proc.stdout), (2, ""))
                self.assertTrue(proc.stderr.startswith("usage: ddl_run.py report|run-start|run-item|snapshot"),
                                proc.stderr)
        self.assertEqual(ddl_run.WORDS, ddl_gate_core.RUN_WORDS)


class LayoutTest(SplitTest):
    """The installed forms: links into a build (the user-level install) and copies (a project's)."""

    def layout(self, name, files=GATE_FILES, link=False):
        hooks = self.tmp / name / "hooks"
        hooks.mkdir(parents=True)
        for file in files:
            if link:
                (hooks / file).symlink_to(TOOLS / file)
            else:
                shutil.copyfile(TOOLS / file, hooks / file)
        return hooks

    def test_linked_files_find_the_modules_beside_what_they_point_at(self):
        argv = ["report", "--session", "S", "--language", "en"]
        for name, files in (("linked", GATE_FILES), ("entry-only", ("ddl_gate.py",)), ("run-only", ("ddl_run.py",))):
            hooks = self.layout(name, files, link=True)
            with self.subTest(layout=name):
                if "ddl_gate.py" in files:  # a denial of session S, which the counts below then show
                    self.assert_denied(self.hook(hooks / "ddl_gate.py", "claude", "pre-tool-use", self.project,
                                                 transcript=CLOSED["claude"], tool_use_id="deny-" + name))
                expected = self.run_script(RUN, argv)
                self.assertEqual((expected.returncode, expected.stderr), (0, ""))
                for file in files:
                    proc = self.run_script(hooks / file, argv)
                    self.assertEqual((proc.returncode, proc.stdout, proc.stderr), (0, expected.stdout, ""))
        self.assertEqual(self.run_script(RUN, argv).stdout.splitlines()[2], "Denials: 2")

    def test_copied_and_built_files_write_no_bytecode_beside_them(self):
        hooks = self.layout("copied")
        out = self.tmp / "dist"
        written = build.write(REPO, out)
        built = out / "claude/.claude/hooks"
        for directory in (hooks, built):
            with self.subTest(directory=str(directory)):
                for runtime in ("claude", "codex"):
                    for cwd in (self.unrelated, self.project):
                        for event in EVENTS:
                            self.hook(directory / "ddl_gate.py", runtime, event, cwd, transcript=CLOSED[runtime])
                prepared = self.prepare(directory / "ddl_gate.py")
                started = self.run_script(directory / "ddl_run.py", ["run-start"],
                                          {"report": prepared["reportId"], "items": [{"id": "I1", "kind": "write"}]})
                self.assertEqual((started.returncode, started.stderr), (0, ""))
                run_id = json.loads(started.stdout)["run"]
                for script in ("ddl_gate.py", "ddl_run.py"):
                    for argv in (["report", "--run", run_id], ["run-item", run_id, "I1", "done"]):
                        proc = self.run_script(directory / script, argv)
                        self.assertEqual((proc.returncode, proc.stderr), (0, ""))
                status = self.run_script(directory / "ddl_gate.py", ["status", "--cwd", str(self.project)])
                self.assertEqual((status.returncode, status.stderr), (0, ""))
                self.assertEqual(sorted(path.name for path in directory.iterdir()), sorted(GATE_FILES))
        # The build that ran holds exactly the files it was written with (build.py --check would list any extra).
        present = sorted(str(path.relative_to(out).as_posix()) for path in out.rglob("*") if not path.is_dir())
        self.assertEqual(present, sorted(str(key) for key in written))
        self.assertTrue(self.bytecode(self.state / "pycache"))  # the bytecode went to the private cache

    def test_without_the_cache_an_interpreter_prefix_stays_in_use(self):
        """macOS /usr/bin/python3 keeps its bytecode under a prefix of its own; the launcher's fallback keeps it (a
        disposable one here, never the real ~/Library/Caches), and still writes nothing beside the source."""
        hooks = self.layout("prefixed")
        prefix = self.tmp / "interpreter-prefix"
        env = self.env(PYTHONPYCACHEPREFIX=str(prefix))
        env.pop("PYTHONDONTWRITEBYTECODE", None)
        for script, argv in (("ddl_gate.py", ["pre-tool-use", "--runtime", "claude"]), ("ddl_run.py", ["report", "--session", "S"]),
                             ("ddl_gate.py", ["report", "--session", "S"])):
            with self.subTest(script=script, argv=argv):
                proc = self.run_script(hooks / script, argv, self.payload("claude", "pre-tool-use", self.unrelated),
                                       self.unrelated, flags=(), env=env)
                self.assertEqual((proc.returncode, proc.stderr), (0, ""))
        self.assertFalse((self.state / "pycache").exists())
        self.assertEqual(sorted(path.name for path in hooks.iterdir()), sorted(GATE_FILES))
        written = [pathlib.PurePath(name).name.split(".")[0] for name in self.bytecode(prefix)]
        self.assertIn("ddl_gate_core", written)
        self.assertIn("ddl_run", written)

    def test_a_copy_without_its_modules_fails_open(self):
        entry = self.layout("entry-only-copy", ("ddl_gate.py",)) / "ddl_gate.py"
        for runtime in ("claude", "codex"):
            for event in EVENTS:
                with self.subTest(runtime=runtime, event=event):
                    out = json.loads(self.hook(entry, runtime, event, self.project, transcript=CLOSED[runtime]))
                    self.assertEqual(list(out), ["systemMessage"])
                    self.assertIn("(fail-open)", out["systemMessage"])
        # Every subcommand word exits 2; anything else, a hook form that starts with a flag too, fails open.
        words = [[word] for word in launcher().SUBCOMMANDS] + [["prepare-report", "--runtime", "claude"],
                                                               ["report", "--session", "S"], ["snapshot", "list"]]
        self.assertEqual({argv[0] for argv in words}, {"status", "prepare-report", "prepare-git-review",
                                                       *ddl_gate_core.RUN_WORDS})
        for argv in words:
            with self.subTest(argv=argv):
                proc = self.run_script(entry, argv, "{}")
                self.assertEqual((proc.returncode, proc.stdout), (2, ""))
                self.assertTrue(proc.stderr.startswith("DDL gate: the gate's code could not be loaded"), proc.stderr)
        for argv in (["--runtime", "codex", "permission-request"], ["permission-request", "--runtime", "codex"]):
            with self.subTest(argv=argv):
                proc = self.run_script(entry, argv, "{}")
                self.assertEqual((proc.returncode, proc.stderr), (0, ""))
                self.assertIn("(fail-open)", json.loads(proc.stdout)["systemMessage"])
        no_run = self.layout("no-run-copy", ("ddl_gate.py", "ddl_gate_core.py")) / "ddl_gate.py"
        self.assert_denied(self.hook(no_run, "claude", "pre-tool-use", self.project, transcript=CLOSED["claude"]))
        for argv in [[word] for word in ddl_gate_core.RUN_WORDS] + [["report", "--session", "S"], ["snapshot", "list"],
                                                                    ["run-item", "N-000000000000", "I1", "done"]]:
            with self.subTest(argv=argv):
                proc = self.run_script(no_run, argv)
                self.assertEqual((proc.returncode, proc.stdout), (2, ""))
                prefix = "DDL {}: ".format(argv[0] if argv[0] in ("report", "snapshot") else "run")
                self.assertTrue(proc.stderr.startswith(prefix + "ddl_run.py could not be loaded beside the gate"),
                                proc.stderr)


class CacheTest(SplitTest):
    def cached(self):
        return [name for name in self.bytecode(self.state / "pycache") if "ddl_gate_core." in name]

    def test_the_cache_is_created_in_a_ddl_project_only(self):
        for event in EVENTS:
            self.hook(GATE, "claude", event, self.unrelated, transcript=CLOSED["claude"])
        self.assertFalse((self.state / "pycache").exists())  # an unrelated project writes its decision alone
        self.hook(GATE, "claude", "session-start", self.project)
        cache = self.state / "pycache"
        self.assertEqual((cache.is_dir(), cache.stat().st_mode & 0o777), (True, 0o700))
        self.assertEqual(self.cached(), [])  # this call itself was compiled from the source
        self.assert_denied(self.hook(GATE, "claude", "pre-tool-use", self.project, transcript=CLOSED["claude"]))
        self.assertEqual(len(self.cached()), 1)
        self.hook(GATE, "codex", "pre-tool-use", self.unrelated)  # once there, every call may use it
        self.assertEqual(len(self.cached()), 1)

    def test_a_cache_others_could_reach_is_not_used(self):
        other = self.tmp / "elsewhere"

        def spoil(case, cache):
            if case == "open to others":
                cache.chmod(0o755)
            elif case == "in a state directory others may write":
                self.state.chmod(0o777)
            else:
                cache.rmdir()
                if case == "a symbolic link":
                    other.mkdir(mode=0o700)
                    cache.symlink_to(other)
                else:
                    cache.write_text("")

        for case in ("open to others", "in a state directory others may write", "a symbolic link", "not a directory"):
            with self.subTest(case=case):
                self.hook(GATE, "claude", "session-start", self.project)
                cache = self.state / "pycache"
                spoil(case, cache)
                self.assert_denied(self.hook(GATE, "claude", "pre-tool-use", self.project, transcript=CLOSED["claude"]))
                self.assertEqual(self.bytecode(self.state), [])
                self.assertFalse(other.exists() and self.bytecode(other))
                self.state.chmod(0o755)
                shutil.rmtree(str(self.state))
                if other.is_dir():
                    shutil.rmtree(str(other))

    def test_cached_code_that_cannot_be_loaded_is_compiled_again(self):
        self.hook(GATE, "claude", "session-start", self.project)
        self.hook(GATE, "claude", "session-start", self.project)
        [name] = self.cached()
        path = self.state / "pycache" / name
        path.write_bytes(path.read_bytes()[:16] + b"\x00 not marshalled code")  # a valid header, a spoiled body
        for runtime in ("claude", "codex"):
            with self.subTest(runtime=runtime):
                self.assert_denied(self.hook(GATE, runtime, "pre-tool-use", self.project, transcript=CLOSED[runtime]))
        prepared = self.prepare()
        self.assertRegex(prepared["reportId"], r"^R-[0-9a-f]{16}$")

    def test_the_launcher_and_the_core_agree(self):
        entry = launcher()
        for env in ({"DDL_GATE_STATE_DIR": str(self.state)}, {"DDL_GATE_STATE_DIR": "relative/state"},
                    {"DDL_GATE_STATE_DIR": "", "TMPDIR": str(self.tmp)}, {"DDL_GATE_STATE_DIR": "", "TMPDIR": ""}):
            with self.subTest(env=env), mock.patch.dict(os.environ, env):
                self.assertEqual(entry.cache_path(), os.path.join(ddl_gate_core.state_base(), ddl_gate_core.CACHE))
        # The launcher names the core's subcommand words, which a missing core cannot name: the same set.
        self.assertEqual(set(entry.SUBCOMMANDS), {"status", "prepare-report", "prepare-git-review",
                                                  *ddl_gate_core.RUN_WORDS})
        self.assertIn("snapshot", entry.SUBCOMMANDS)
        self.assertEqual(len(set(entry.SUBCOMMANDS)), len(entry.SUBCOMMANDS))
        dispatched = set(re.findall(r'argv\[0\] == "([a-z-]+)"', inspect.getsource(ddl_gate_core.main)))
        self.assertLessEqual(dispatched, set(entry.SUBCOMMANDS))  # a word the core's main answers by name
        self.assertFalse(set(entry.SUBCOMMANDS) & set(ddl_gate_core.EVENTS))

    def plant(self, names):
        """A cached file with a valid header and a spoiled body for each module in `names`, where the interpreter
        would look for it under the private cache (the source's own path below the prefix)."""
        cache = self.state / "pycache"
        planted = []
        for name in names:
            spec = importlib.util.find_spec(name)
            if spec is None or not (spec.origin or "").endswith(".py"):
                continue  # a built-in or frozen module has no source file to cache
            with mock.patch.object(sys, "pycache_prefix", str(cache)):
                path = pathlib.Path(importlib.util.cache_from_source(spec.origin))
            source = os.stat(spec.origin)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(importlib.util.MAGIC_NUMBER + bytes(4) + (int(source.st_mtime) & 0xFFFFFFFF).to_bytes(4, "little")
                             + (source.st_size & 0xFFFFFFFF).to_bytes(4, "little") + b"\x00 not marshalled code")
            planted.append(name)
        return planted

    def lazy_modules(self):
        """The standard-library modules the core binds lazily, as a fresh interpreter names them, less those the
        core's own imports load already (json loads re)."""
        script = ("import __future__, json, sys\nsys.path.insert(0, sys.argv[1])\nimport ddl_gate_core as core\n"
                  "print(json.dumps(sorted(v._name for v in vars(core).values() if isinstance(v, core._Lazy)\n"
                  "                        and v._name not in sys.modules)))\n")
        proc = subprocess.run([sys.executable, "-I", "-B", "-c", script, str(TOOLS)], capture_output=True, encoding="utf-8",
                              env=self.env(), cwd=str(self.tmp), timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def cached_modules(self):
        """The names of the modules whose bytecode the private cache holds."""
        return {pathlib.PurePath(name).name.split(".")[0] for name in self.bytecode(self.state / "pycache")}

    def spoil_every_cached_file(self):
        """Keep each cached file's header and spoil its body; the names of the modules spoiled."""
        spoiled = []
        for name in self.bytecode(self.state / "pycache"):
            path = self.state / "pycache" / name
            path.write_bytes(path.read_bytes()[:16] + b"\x00 not marshalled code")
            spoiled.append(pathlib.PurePath(name).name.split(".")[0])
        return spoiled

    def test_spoiling_every_cached_file_changes_no_decision(self):
        """A cached file whose header is valid and whose body is not code is passed over and its source compiled:
        a pending STOP still denies an Edit on both hosts, and the subcommands answer as before. First only the
        standard-library modules the core loads after its own import (pathlib, shlex, …: the case that once
        failed open on every call), then every cached file, the core's and ddl_run's included."""
        self.hook(GATE, "claude", "session-start", self.project)  # creates the cache
        for runtime in ("claude", "codex"):
            for event in EVENTS:
                self.hook(GATE, runtime, event, self.project, transcript=CLOSED[runtime])
        expected = self.run_script(GATE, ["report", "--session", "S"])  # puts ddl_run in the cache too
        self.assertEqual((expected.returncode, expected.stderr), (0, ""))
        # The standard library is cached too: json's decoder, and packages such as pathlib as `__init__`.
        self.assertTrue({"ddl_gate_core", "ddl_run", "decoder", "__init__"} <= self.cached_modules(), self.cached_modules())
        lazy = self.lazy_modules()
        self.assertTrue({"pathlib", "shlex"} <= set(self.plant(lazy)))
        for runtime in ("claude", "codex"):
            with self.subTest(spoiled="loaded after the core", runtime=runtime):
                self.assert_denied(self.hook(GATE, runtime, "pre-tool-use", self.project, transcript=CLOSED[runtime]))
        spoiled = self.spoil_every_cached_file()
        self.assertTrue({"ddl_gate_core", "ddl_run", "decoder", "shlex", "__init__"} <= set(spoiled), spoiled)
        for runtime in ("claude", "codex"):
            with self.subTest(spoiled="every cached file", runtime=runtime):
                self.assert_denied(self.hook(GATE, runtime, "pre-tool-use", self.project, transcript=CLOSED[runtime]))
        proc = self.run_script(GATE, ["report", "--session", "S"])
        self.assertEqual((proc.returncode, proc.stdout, proc.stderr), (0, expected.stdout, ""))
        prepared = self.prepare()  # a subcommand that loads more of the standard library
        self.assertRegex(prepared["reportId"], r"^R-[0-9a-f]{16}$")

    def test_a_run_word_takes_ddl_run_from_the_cache_and_a_spoiled_copy_from_the_source(self):
        def cached_run():
            return [name for name in self.bytecode(self.state / "pycache") if "ddl_run." in name]

        self.hook(GATE, "claude", "session-start", self.project)
        for event in EVENTS:
            self.hook(GATE, "claude", event, self.project, transcript=CLOSED["claude"])
        self.assertEqual(cached_run(), [])  # no hook event loads it
        expected = self.run_script(RUN, ["report", "--session", "S"])
        self.assertEqual((expected.returncode, expected.stderr), (0, ""))
        for _ in range(2):
            proc = self.run_script(GATE, ["report", "--session", "S"])
            self.assertEqual((proc.returncode, proc.stdout, proc.stderr), (0, expected.stdout, ""))
        [name] = cached_run()
        self.assertTrue({"ddl_gate_core", "ddl_run"} <= self.cached_modules())
        path = self.state / "pycache" / name
        path.write_bytes(path.read_bytes()[:16] + b"\x00 not marshalled code")
        proc = self.run_script(GATE, ["report", "--session", "S"], flags=("-I", "-X", "importtime"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, expected.stdout)
        self.assertEqual(imported(proc.stderr).count("ddl_gate_core"), 1)

    def test_the_preparation_call_may_name_the_launcher_or_the_core(self):
        body = "\n{}\nJSON"
        self.addCleanup(setattr, ddl_gate_core, "ENTRY", ddl_gate_core.ENTRY)
        for entry in (None, "/opt/elsewhere/hooks/ddl_gate.py"):
            ddl_gate_core.ENTRY = entry
            for path in ((entry or GATE), CORE):
                with self.subTest(entry=entry, path=path):
                    command = "python3 " + shlex.quote(path) + " prepare-report --runtime claude <<'JSON'" + body
                    self.assertTrue(ddl_gate_core.is_gate_preparation(command))
            other = "python3 /opt/other/ddl_gate.py prepare-report --runtime claude <<'JSON'" + body
            self.assertFalse(ddl_gate_core.is_gate_preparation(other))


RUN_A, RUN_B = "N-0123456789ab", "N-ba9876543210"
FIXED_DATES = {"GIT_AUTHOR_DATE": "2026-11-24T00:00:00Z", "GIT_COMMITTER_DATE": "2026-11-24T00:00:00Z"}
NEUTRAL = "DDL snapshot <snapshot@ddl.invalid>"
AI_NAMES = ("claude", "codex", "anthropic", "openai", "gpt", "copilot", "gemini", "assistant")
STAMPED = re.compile(r"/\d{8}T\d{6}\.\d{3}Z-")


def snapshot_ref(run, item):
    """The pattern of a snapshot's ref name."""
    return r"^refs/ddl/snapshots/{}/\d{{8}}T\d{{6}}\.\d{{3}}Z-{}$".format(re.escape(run), re.escape(item))


def ident(value):
    """`Name <email>` of a commit's author or committer line (its time and zone dropped)."""
    return value.rsplit(" ", 2)[0]


class SnapshotTest(SplitTest):
    """`snapshot` in real repositories under the test's temporary directory. Git reads no system or user
    configuration (a private HOME and global file), takes no identity from the environment, discovers no
    repository above the temporary directory, and writes the temporary index under a private TMPDIR that is
    empty again afterwards. Fixture commits are made by a fixture identity in these repositories only."""

    def setUp(self):
        super().setUp()
        self.home = self.tmp / "home"
        self.home.mkdir()
        (self.home / ".gitconfig").write_text("")
        self.scratch = self.tmp / "scratch"
        self.scratch.mkdir()

    def env(self, **extra):
        env = {name: value for name, value in os.environ.items() if not name.startswith("GIT_") and name != "EMAIL"}
        env.update(HOME=str(self.home), XDG_CONFIG_HOME=str(self.home / ".config"), GIT_CONFIG_NOSYSTEM="1",
                   GIT_CONFIG_GLOBAL=str(self.home / ".gitconfig"), GIT_CEILING_DIRECTORIES=str(self.tmp.resolve()),
                   TMPDIR=str(self.scratch), DDL_GATE_STATE_DIR=str(self.state), DDL_GATE_GRANT_DIR=str(self.grants))
        env.update(extra)
        return env

    def git(self, *args, cwd, check=True, env=None):
        proc = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, env=env or self.env(), timeout=60)
        if check:
            self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        return proc.stdout.decode("utf-8", "surrogateescape").strip() if proc.returncode == 0 else None

    def commit(self, root, *where, message="fixture"):
        self.git(*where, "add", "-A", cwd=root)
        self.git(*where, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "-c", "commit.gpgSign=false",
                 "commit", "-q", "-m", message, cwd=root)

    def repository(self, name="repo", marker=True, identity=True, commit=True):
        """tmp/<name> on `main`: CLAUDE.md (with the DDL marker line when `marker`), a `.gitignore` of `*.log`,
        a.txt and gone.txt, committed once unless not `commit`; `identity` configures one in the repository."""
        root = self.tmp / name
        root.mkdir()
        self.git("init", "-q", "-b", "main", cwd=root)
        if identity:
            self.git("config", "user.name", "Test Person", cwd=root)
            self.git("config", "user.email", "test.person@example.invalid", cwd=root)
        (root / "CLAUDE.md").write_text("# Project\n\n" + (MARKER_LINE if marker else "No marker.") + "\n",
                                        encoding="utf-8")
        (root / ".gitignore").write_text("*.log\n")
        (root / "a.txt").write_text("1\n")
        (root / "gone.txt").write_text("gone\n")
        if commit:
            self.commit(root)
        return root

    def snap(self, cwd, *argv, script=RUN, env=None):
        self.assertTrue(pathlib.Path(cwd).resolve().is_relative_to(self.tmp.resolve()))
        return self.run_script(script, ["snapshot", *argv], None, cwd, env=env)

    def snapped(self, cwd, *argv, **kwargs):
        proc = self.snap(cwd, *argv, **kwargs)
        self.assertEqual((proc.returncode, proc.stderr), (0, ""))
        return json.loads(proc.stdout)

    def same(self, cwd, argv, env=None):
        """`ddl_gate.py` and `ddl_run.py` on the same arguments: (returncode, stdout, stderr), which must agree."""
        outcomes = [(proc.returncode, proc.stdout, proc.stderr)
                    for proc in (self.snap(cwd, *argv, script=script, env=env) for script in (GATE, RUN))]
        self.assertEqual(outcomes[0], outcomes[1])
        return outcomes[0]

    def in_process(self, cwd, argv):
        """ddl_run.main in this process, in `cwd` with the private Git environment: (code, stdout, stderr)."""
        out, err, previous = io.StringIO(), io.StringIO(), os.getcwd()
        os.chdir(str(cwd))
        try:
            with mock.patch.dict(os.environ, self.env(), clear=True), mock.patch("tempfile.tempdir", str(self.scratch)), \
                    contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = ddl_run.main(argv)
        finally:
            os.chdir(previous)
        return code, out.getvalue(), err.getvalue()

    def kept(self, top, *where):
        """What a snapshot leaves as it was: the index file's bytes and mtime, HEAD's name, value and reflog,
        every ref outside refs/ddl/, the status, and every work-tree file's bytes and mtime."""
        quiet = self.env(GIT_OPTIONAL_LOCKS="0")

        def git(*args, check=True):
            return self.git(*where, *args, cwd=top, check=check, env=quiet)

        def stat(path):
            return (path.read_bytes(), path.stat().st_mtime_ns) if path.exists() else None

        index = stat(pathlib.Path(git("rev-parse", "--path-format=absolute", "--git-path", "index")))  # read first
        files = {}
        for directory, names, filenames in os.walk(str(top)):
            names[:] = [name for name in names if name != ".ddl" and not name.endswith(".git")]
            for filename in filenames:
                if filename != ".git":
                    path = pathlib.Path(directory, filename)
                    files[str(path.relative_to(top))] = stat(path)
        return {"index": index, "files": files,
                "reflog": stat(pathlib.Path(git("rev-parse", "--path-format=absolute", "--git-path", "logs/HEAD"))),
                "head": (git("symbolic-ref", "-q", "HEAD", check=False), git("rev-parse", "-q", "--verify", "HEAD", check=False)),
                "refs": [line for line in git("for-each-ref", "--format=%(refname) %(objectname)").splitlines()
                         if not line.startswith("refs/ddl/")],
                "status": git("status", "--porcelain=v1", "--untracked-files=all")}

    def tree(self, commit, cwd, *where):
        return sorted(self.git(*where, "ls-tree", "-r", "--name-only", commit, cwd=cwd).splitlines())

    def commit_of(self, commit, cwd, *where):
        """A commit's header fields (each a list of values) and its message."""
        header, _, message = self.git(*where, "cat-file", "commit", commit, cwd=cwd).partition("\n\n")
        fields = {}
        for line in header.splitlines():
            key, _, value = line.partition(" ")
            fields.setdefault(key, []).append(value)
        return fields, message

    def events(self, root):
        path = root / ".ddl" / "events.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def test_a_snapshot_saves_the_work_tree_as_add_all_sees_it(self):
        root = self.repository()
        head = self.git("rev-parse", "HEAD", cwd=root)
        (root / "a.txt").write_text("staged\n")
        self.git("add", "a.txt", cwd=root)  # the real index stages a version that is neither HEAD's nor the file's
        (root / "a.txt").write_text("worked\n")
        (root / "gone.txt").unlink()
        (root / "new.txt").write_text("new\n")
        (root / "sub").mkdir()
        (root / "sub" / "b.txt").write_text("b\n")
        (root / "debug.log").write_text("ignored by .gitignore\n")
        (root / "secret.txt").write_text("ignored by info/exclude\n")
        (root / ".git" / "info").mkdir(exist_ok=True)
        with open(str(root / ".git" / "info" / "exclude"), "a") as fh:
            fh.write("secret.txt\n")
        before = self.kept(root)
        out = self.snapped(root / "sub", "--run", RUN_A, "--item", "I1")  # from a subdirectory: the whole tree
        self.assertEqual(self.kept(root), before)
        self.assertEqual(os.listdir(str(self.scratch)), [])  # the temporary index is gone
        self.assertEqual(sorted(out), ["files", "ref", "snapshot", "unchanged"])
        self.assertRegex(out["ref"], snapshot_ref(RUN_A, "I1"))
        self.assertEqual((out["files"], out["unchanged"]), (4, False))
        self.assertEqual(self.git("rev-parse", out["ref"], cwd=root), out["snapshot"])
        self.assertEqual(self.tree(out["snapshot"], root), [".gitignore", "CLAUDE.md", "a.txt", "new.txt", "sub/b.txt"])
        self.assertEqual(self.git("cat-file", "blob", out["snapshot"] + ":a.txt", cwd=root), "worked")
        self.assertEqual(self.git("cat-file", "blob", ":a.txt", cwd=root), "staged")  # still staged, unchanged
        fields, message = self.commit_of(out["snapshot"], root)
        self.assertEqual((fields["parent"], message), ([head], "DDL snapshot {} I1".format(RUN_A)))
        self.assertEqual([ident(fields[role][0]) for role in ("author", "committer")],
                         ["Test Person <test.person@example.invalid>"] * 2)
        self.assertNotIn("gpgsig", fields)

    def test_an_unchanged_tree_is_saved_and_said_to_be_unchanged(self):
        root = self.repository()
        (root / "debug.log").write_text("ignored, so nothing changed\n")
        before = self.kept(root)
        out = self.snapped(root)
        self.assertEqual(self.kept(root), before)
        self.assertRegex(out["ref"], snapshot_ref("adhoc", "snap"))
        self.assertEqual((out["files"], out["unchanged"]), (0, True))
        self.assertEqual(self.git("rev-parse", out["snapshot"] + "^{tree}", cwd=root),
                         self.git("rev-parse", "HEAD^{tree}", cwd=root))
        self.assertEqual(self.commit_of(out["snapshot"], root)[1], "DDL snapshot adhoc snap")

    def test_without_head_the_snapshot_has_no_parent_and_no_branch_is_born(self):
        root = self.repository(commit=False)
        (root / "debug.log").write_text("ignored\n")
        before = self.kept(root)
        self.assertIsNone(before["index"])  # no index file yet, and none is made
        out = self.snapped(root, "--item", "first")
        self.assertEqual(self.kept(root), before)
        self.assertEqual(self.git("for-each-ref", "refs/heads", cwd=root), "")
        fields, _ = self.commit_of(out["snapshot"], root)
        self.assertNotIn("parent", fields)
        self.assertEqual(self.tree(out["snapshot"], root), [".gitignore", "CLAUDE.md", "a.txt", "gone.txt"])
        self.assertEqual((out["files"], out["unchanged"]), (4, False))
        empty = self.tmp / "empty"
        empty.mkdir()
        self.git("init", "-q", "-b", "main", cwd=empty)
        out = self.snapped(empty)
        self.assertEqual((out["files"], out["unchanged"]), (0, True))
        self.assertEqual(self.git("rev-parse", out["snapshot"] + "^{tree}", cwd=empty),
                         self.git("hash-object", "-t", "tree", os.devnull, cwd=empty))

    def test_the_second_git_directory_is_saved_on_its_own(self):
        # This project's layout: the public repository's info/exclude leaves out the notebook's files, and the
        # notebook's own excludes everything but them, with the project root as its work tree.
        root = self.repository(name="public")
        (root / ".git" / "info").mkdir(exist_ok=True)
        (root / ".git" / "info" / "exclude").write_text("design.md\nhistory.md\n.notebook.git/\n")
        notebook = ["--git-dir=" + str(root / ".notebook.git"), "--work-tree=" + str(root)]
        self.git("init", "-q", "--bare", "-b", "main", str(root / ".notebook.git"), cwd=root)
        self.git(*notebook, "config", "core.bare", "false", cwd=root)
        self.git(*notebook, "config", "core.worktree", str(root), cwd=root)
        (root / ".notebook.git" / "info").mkdir(exist_ok=True)
        (root / ".notebook.git" / "info" / "exclude").write_text("*\n!design.md\n!history.md\n")
        (root / "design.md").write_text("one\n")
        self.commit(root, *notebook, message="notebook")
        notebook_head = self.git(*notebook, "rev-parse", "HEAD", cwd=root)
        (root / "design.md").write_text("one, revised\n")
        (root / "history.md").write_text("two\n")
        (root / "a.txt").write_text("a change of the public repository\n")
        before = (self.kept(root), self.kept(root, *notebook))
        out = self.snapped(root, "--git-dir", ".notebook.git", "--work-tree", ".", "--item", "notes")
        self.assertEqual((self.kept(root), self.kept(root, *notebook)), before)
        self.assertEqual(self.tree(out["snapshot"], root, *notebook), ["design.md", "history.md"])
        self.assertEqual((out["files"], out["unchanged"]), (2, False))
        self.assertEqual(self.commit_of(out["snapshot"], root, *notebook)[0]["parent"], [notebook_head])
        self.assertEqual(self.git(*notebook, "rev-parse", out["ref"], cwd=root), out["snapshot"])
        self.assertEqual(self.git("for-each-ref", "refs/ddl", cwd=root), "")  # nothing in the public repository
        self.assertEqual(self.snapped(root, "list", "--git-dir=.notebook.git", "--work-tree=."),
                         {"snapshots": [{"ref": out["ref"], "commit": out["snapshot"]}]})
        self.assertEqual(self.snapped(root, "list"), {"snapshots": []})
        self.assertEqual([(event["kind"], event["ref"]) for event in self.events(root)], [("snapshot", out["ref"])])

    def test_a_linked_work_tree_is_saved_on_its_own_head(self):
        root = self.repository()
        linked = self.tmp / "linked"
        self.git("worktree", "add", "-q", "-b", "side", str(linked), cwd=root)
        (linked / "a.txt").write_text("side\n")
        self.commit(linked, message="side")
        side = self.git("rev-parse", "HEAD", cwd=linked)
        (linked / "a.txt").write_text("side, changed\n")
        (linked / "new.txt").write_text("new\n")
        (root / "main-only.txt").write_text("in the main work tree\n")
        before = (self.kept(root), self.kept(linked))
        out = self.snapped(linked, "--item", "I2")
        self.assertEqual((self.kept(root), self.kept(linked)), before)
        self.assertEqual(self.commit_of(out["snapshot"], linked)[0]["parent"], [side])
        self.assertEqual(self.tree(out["snapshot"], linked), [".gitignore", "CLAUDE.md", "a.txt", "gone.txt", "new.txt"])
        self.assertEqual(self.git("cat-file", "blob", out["snapshot"] + ":a.txt", cwd=linked), "side, changed")
        self.assertEqual((out["files"], out["unchanged"]), (2, False))
        self.assertEqual(self.git("rev-parse", out["ref"], cwd=root), out["snapshot"])  # refs are shared
        self.assertEqual([event["ref"] for event in self.events(root)], [out["ref"]])  # the main work tree's ledger
        self.assertFalse((linked / ".ddl").exists())

    def test_a_conflicted_merge_is_saved_as_it_stands(self):
        root = self.repository()
        self.git("checkout", "-q", "-b", "other", cwd=root)
        (root / "a.txt").write_text("other\n")
        self.commit(root, message="other")
        self.git("checkout", "-q", "main", cwd=root)
        (root / "a.txt").write_text("main\n")
        self.commit(root, message="main")
        merge = self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "merge", "-q", "other",
                         cwd=root, check=False)
        self.assertIsNone(merge)  # a conflict: the real index holds three stages of a.txt
        before = self.kept(root)
        out = self.snapped(root, "--item", "conflict")
        self.assertEqual(self.kept(root), before)
        self.assertTrue((root / ".git" / "MERGE_HEAD").exists())
        self.assertIn("<<<<<<<", self.git("cat-file", "blob", out["snapshot"] + ":a.txt", cwd=root))

    def test_an_existing_ref_is_refused_and_nothing_changes(self):
        root = self.repository()
        main = self.git("rev-parse", "main", cwd=root)
        with mock.patch.object(ddl_run, "ref_stamp", return_value="20261124T001200.000Z"):
            code, stdout, stderr = self.in_process(root, ["snapshot", "--run", RUN_A, "--item", "I1"])
            self.assertEqual((code, stderr), (0, ""))
            made = json.loads(stdout)
            (root / "a.txt").write_text("changed\n")
            self.assertEqual(self.in_process(root, ["snapshot", "--run", RUN_A, "--item", "I1"]),
                             (2, "", "DDL snapshot: {} exists already; nothing was changed.\n".format(made["ref"])))
            # A name planted as a symbolic ref to a branch is refused too: the branch never moves.
            planted = "refs/ddl/snapshots/{}/20261124T001200.000Z-I3".format(RUN_A)
            self.git("symbolic-ref", planted, "refs/heads/main", cwd=root)
            self.assertEqual(self.in_process(root, ["snapshot", "--run", RUN_A, "--item", "I3"]),
                             (2, "", "DDL snapshot: {} exists already; nothing was changed.\n".format(planted)))
        self.assertEqual(self.git("rev-parse", made["ref"], cwd=root), made["snapshot"])
        self.assertEqual(self.git("rev-parse", "main", cwd=root), main)
        self.assertEqual([event["kind"] for event in self.events(root)], ["snapshot"])
        self.assertEqual(os.listdir(str(self.scratch)), [])

    def test_the_identity_is_the_users_or_a_neutral_one(self):
        people = {"GIT_AUTHOR_NAME": "Env Author", "GIT_AUTHOR_EMAIL": "env.author@example.invalid",
                  "GIT_COMMITTER_NAME": "Env Committer", "GIT_COMMITTER_EMAIL": "env.committer@example.invalid"}
        cases = [("none configured", {}, {}, {}, [NEUTRAL, NEUTRAL]),
                 ("a name alone", {"user.name": "Only Name"}, {}, {}, [NEUTRAL, NEUTRAL]),
                 ("the user's file", {}, {"user.name": "Global Person", "user.email": "global@example.invalid"}, {},
                  ["Global Person <global@example.invalid>"] * 2),
                 ("the repository's", {"user.name": "Local Person", "user.email": "local@example.invalid"}, {}, {},
                  ["Local Person <local@example.invalid>"] * 2),
                 ("the environment's", {}, {}, people,
                  ["Env Author <env.author@example.invalid>", "Env Committer <env.committer@example.invalid>"]),
                 ("an author alone", {}, {}, {key: people[key] for key in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL")},
                  ["Env Author <env.author@example.invalid>", NEUTRAL]),
                 ("a signing setup", {"user.name": "Local Person", "user.email": "local@example.invalid",
                                      "commit.gpgSign": "true", "gpg.program": "false"}, {}, {},
                  ["Local Person <local@example.invalid>"] * 2)]
        for number, (case, local, user, extra, expected) in enumerate(cases):
            with self.subTest(case=case):
                (self.home / ".gitconfig").write_text("")
                for key, value in user.items():
                    self.git("config", "--file", str(self.home / ".gitconfig"), key, value, cwd=self.tmp)
                root = self.repository(name="identity-{}".format(number), identity=False)
                for key, value in local.items():
                    self.git("config", key, value, cwd=root)
                out = self.snapped(root, env=self.env(**extra))
                fields, message = self.commit_of(out["snapshot"], root)
                self.assertEqual([ident(fields[role][0]) for role in ("author", "committer")], expected)
                self.assertNotIn("gpgsig", fields)
                said = " ".join([*fields["author"], *fields["committer"], message]).lower()
                self.assertFalse([name for name in AI_NAMES if name in said])
        (self.home / ".gitconfig").write_text("")

    def test_list_is_newest_first_and_narrows_to_one_run(self):
        root = self.repository()
        made = {}
        for run, item, stamp in ((RUN_A, "I1", "20261124T001500.000Z"), (None, None, "20261124T002000.500Z"),
                                 (RUN_B, "I9", "20261124T001000.000Z"), (RUN_A, "I2", "20261124T001500.250Z")):
            argv = ["snapshot", *(["--run", run] if run else []), *(["--item", item] if item else [])]
            with mock.patch.object(ddl_run, "ref_stamp", return_value=stamp):
                code, stdout, stderr = self.in_process(root, argv)
            self.assertEqual((code, stderr), (0, ""))
            out = json.loads(stdout)
            made[out["ref"]] = out["snapshot"]
        head = self.git("rev-parse", "HEAD", cwd=root)
        night = "refs/ddl/snapshots/{}/20261124T001700Z-label".format(RUN_A)  # seconds only, as `git stash create` refs
        handmade = "refs/ddl/snapshots/adhoc/handmade"  # no stamp: last
        for ref in (night, handmade):
            self.git("update-ref", ref, head, cwd=root)
            made[ref] = head
        order = ["refs/ddl/snapshots/adhoc/20261124T002000.500Z-snap", night,
                 "refs/ddl/snapshots/{}/20261124T001500.250Z-I2".format(RUN_A),
                 "refs/ddl/snapshots/{}/20261124T001500.000Z-I1".format(RUN_A),
                 "refs/ddl/snapshots/{}/20261124T001000.000Z-I9".format(RUN_B), handmade]
        self.assertEqual(sorted(order), sorted(made))
        self.assertEqual(self.snapped(root, "list"), {"snapshots": [{"ref": ref, "commit": made[ref]} for ref in order]})
        self.assertEqual([entry["ref"] for entry in self.snapped(root, "list", "--run", RUN_A)["snapshots"]],
                         [ref for ref in order if "/{}/".format(RUN_A) in ref])
        self.assertEqual(self.snapped(root, "list", "--run=N-000000000000"), {"snapshots": []})
        self.assertEqual(self.snapped(self.repository(name="none"), "list"), {"snapshots": []})

    def test_the_ledger_event_names_the_ref_the_commit_and_the_item(self):
        root = self.repository()
        out = self.snapped(root, "--run", RUN_A, "--item", "I1")
        adhoc = self.snapped(root)
        events = self.events(root)
        self.assertEqual([{key: event.get(key) for key in ("v", "host", "session", "kind", "ref", "commit", "item", "run")}
                          for event in events],
                         [{"v": 1, "host": None, "session": None, "kind": "snapshot", "ref": out["ref"],
                           "commit": out["snapshot"], "item": "I1", "run": RUN_A},
                          {"v": 1, "host": None, "session": None, "kind": "snapshot", "ref": adhoc["ref"],
                           "commit": adhoc["snapshot"], "item": None, "run": None}])
        self.assertFalse({"item", "run"} & set(events[1]))
        self.assertEqual(self.git("status", "--porcelain", cwd=root), "")  # the ledger ignores itself
        plain = self.repository(name="plain", marker=False)  # outside a DDL project: the snapshot alone
        made = self.snapped(plain)
        self.assertEqual(self.git("rev-parse", made["ref"], cwd=plain), made["snapshot"])
        self.assertFalse((plain / ".ddl").exists())

    def test_both_entries_give_the_same_output(self):
        root = self.repository()
        (root / "a.txt").write_text("changed\n")
        env = self.env(**FIXED_DATES)  # the same tree, parent, message, identity and dates: the same commit
        made = [self.snapped(root, "--item", "I1", script=script, env=env) for script in (GATE, RUN)]
        self.assertEqual([dict(out, ref=STAMPED.sub("/<stamp>-", out["ref"])) for out in made],
                         [{"snapshot": made[0]["snapshot"], "ref": "refs/ddl/snapshots/adhoc/<stamp>-I1", "files": 1,
                           "unchanged": False}] * 2)
        listed = self.same(root, ["list"])
        self.assertEqual((listed[0], listed[2]), (0, ""))
        self.assertEqual(sorted(entry["ref"] for entry in json.loads(listed[1])["snapshots"]), sorted(out["ref"] for out in made))
        nowhere = self.tmp / "nowhere"
        nowhere.mkdir()
        cases = [(root, ["--git-dir", ".git"]), (root, ["--work-tree", "."]), (root, ["--run", "N-1"]), (root, ["--run"]),
                 (root, ["--run="]), (root, ["--item", "a..b"]), (root, ["--item", "I1.lock"]), (root, ["--item", "I1."]),
                 (root, ["--item", "-x"]), (root, ["--item", "I1", "--item", "I2"]), (root, ["--bogus"]), (root, ["extra"]),
                 (root, ["list", "--item", "I1"]), (root, ["list", "list"]), (root, ["list", "--run", "N-1"]),
                 (root, ["--git-dir", "missing.git", "--work-tree", "."]), (nowhere, []), (nowhere, ["list"])]
        for cwd, argv in cases:
            with self.subTest(cwd=cwd.name, argv=argv):
                returncode, stdout, stderr = self.same(cwd, argv)
                self.assertEqual((returncode, stdout), (2, ""))
                self.assertRegex(stderr, r"^DDL snapshot: \S")
        self.assertEqual(sorted(self.git("for-each-ref", "--format=%(refname)", "refs/ddl", cwd=root).splitlines()),
                         sorted(out["ref"] for out in made))
        self.assertEqual(len(self.events(root)), 2)

    def test_the_snapshot_words_load_the_run_module_and_a_hook_event_does_not(self):
        root = self.repository()
        for script in (GATE, RUN):
            for argv in (["snapshot", "list"], ["snapshot", "--item", "I1"]):
                with self.subTest(script=pathlib.Path(script).name, argv=argv):
                    proc = self.run_script(script, argv, None, root, flags=("-I", "-X", "importtime"))
                    self.assertEqual(proc.returncode, 0, proc.stderr)
                    names = imported(proc.stderr)
                    self.assertEqual((names.count("ddl_gate_core"), names.count("ddl_gate"), names.count("ddl_run")),
                                     (1, 0, 0 if script == RUN else 1))
        made = self.git("for-each-ref", "--format=%(refname)", "refs/ddl", cwd=root)
        command = "python3 tools/ddl_gate.py snapshot --item I9"
        for runtime, tool in (("claude", ("Bash", {"command": command})), ("codex", ("exec_command", {"cmd": command}))):
            for transcript in (CLOSED[runtime], None):
                with self.subTest(runtime=runtime, closed=bool(transcript)):
                    payload = self.payload(runtime, "pre-tool-use", root, transcript=transcript, tool_name=tool[0],
                                           tool_input=tool[1])
                    proc = self.run_script(GATE, ["pre-tool-use", "--runtime", runtime], payload, root,
                                           flags=("-I", "-X", "importtime"))
                    self.assertEqual(proc.returncode, 0, proc.stderr)
                    self.assertNotIn("ddl_run", imported(proc.stderr))
        self.assertEqual(self.git("for-each-ref", "--format=%(refname)", "refs/ddl", cwd=root), made)  # nothing ran


class BuildTest(unittest.TestCase):
    """tools/build.py ships the three files beside each other for both hosts; tools/check_ddl.py checks them."""

    def source_copy(self, directory):
        repo = pathlib.Path(directory) / "repo"
        for name in ("skills", "protocol", "hosts"):
            shutil.copytree(str(REPO / name), str(repo / name), ignore=shutil.ignore_patterns("__pycache__", ".DS_Store"))
        (repo / "tools").mkdir()
        for name in GATE_FILES:
            shutil.copyfile(TOOLS / name, repo / "tools" / name)
        return repo

    def test_each_host_gets_every_gate_file(self):
        tree = build.generate(REPO)
        for host, spec in build.HOSTS.items():
            for name in GATE_FILES:
                with self.subTest(host=host, file=name):
                    key = "{}/hooks/{}".format(spec["adapter"], name)
                    self.assertEqual(tree[key], (TOOLS / name).read_bytes())
                    self.assertEqual(check_ddl.DIST_GATE_FILES["tools/" + name][host], key)
        self.assertEqual(build.GATE_SOURCES, tuple("tools/" + name for name in GATE_FILES))
        self.assertEqual(check_ddl.GATE_FILES, build.GATE_SOURCES)

    def test_a_collision_or_a_missing_file_stops_the_build(self):
        with tempfile.TemporaryDirectory(prefix="ddl-run-build-") as tmp:
            repo = self.source_copy(tmp)
            self.assertTrue({"{}/hooks/{}".format(spec["adapter"], name) for spec in build.HOSTS.values()
                             for name in GATE_FILES} <= set(build.generate(repo)))
            for host in build.HOSTS:
                for name in GATE_FILES:
                    with self.subTest(host=host, file=name):
                        planted = repo / "hosts" / host / "hooks" / name
                        planted.parent.mkdir(exist_ok=True)
                        planted.write_text("# an adapter file of the same name\n")
                        with self.assertRaises(SystemExit) as raised:
                            build.generate(repo)
                        self.assertEqual(str(raised.exception), "hosts/{}/hooks/{}: collides with the gate copy of "
                                                                "tools/{}".format(host, name, name))
                        planted.unlink()
            for name in GATE_FILES:
                with self.subTest(missing=name):
                    source = repo / "tools" / name
                    data = source.read_bytes()
                    source.unlink()
                    with self.assertRaises(SystemExit) as raised:
                        build.generate(repo)
                    self.assertEqual(str(raised.exception), "tools/{}: missing".format(name))
                    source.write_bytes(data)

    def test_the_dist_check_names_a_missing_or_different_copy(self):
        tree = {key: bytes(data) for key, data in build.generate(REPO).items()}
        del tree["codex/.codex/hooks/ddl_run.py"]
        tree["claude/.claude/hooks/ddl_gate_core.py"] += b"# altered\n"
        with mock.patch.object(check_ddl, "generated_tree", return_value=(tree, [])), \
                contextlib.redirect_stdout(io.StringIO()):
            errors = check_ddl.check_dist()
        self.assertIn("dist: missing codex/.codex/hooks/ddl_run.py", errors)
        self.assertIn("dist: claude/.claude/hooks/ddl_gate_core.py differs from tools/ddl_gate_core.py", errors)
        self.assertNotIn("dist: missing claude/.claude/hooks/ddl_run.py", errors)

    def test_a_pycache_in_a_build_is_reported(self):
        with tempfile.TemporaryDirectory(prefix="ddl-run-build-") as tmp:
            repo = self.source_copy(tmp)  # a still copy: the check compares the build with these very sources
            out = pathlib.Path(tmp) / "dist"
            build.write(repo, out)
            self.assertEqual(build.check(repo, out)[0], [])
            junk = out / "codex/.codex/hooks/__pycache__/ddl_gate_core.cpython-39.pyc"
            junk.parent.mkdir()
            junk.write_bytes(b"")
            self.assertEqual(build.check(repo, out)[0], ["extra: codex/.codex/hooks/__pycache__/ddl_gate_core.cpython-39.pyc"])


if __name__ == "__main__":
    unittest.main(verbosity=1)
