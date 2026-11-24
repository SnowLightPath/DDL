#!/usr/bin/env python3
"""Install, check, or remove DDL at the user level (bin/install.sh, bin/doctor.sh, bin/uninstall.sh).

DDL is installed into the environment, not into each project: the skills, the agent definitions
and the gate hook are symlinked from this checkout's generated layout `dist/` into
`$HOME/.claude/` and `$HOME/.codex/`, and the adapter's settings fragment is merged into
`$HOME/.claude/settings.json` and `$HOME/.codex/hooks.json`. `install`, `doctor`, and `--project`
build `dist/` first (`tools/build.py`, from `skills/`, `protocol/`, `hosts/`, and the gate's three files
`tools/ddl_gate.py`, `tools/ddl_gate_core.py` and `tools/ddl_run.py`), so a fresh clone works. The gate
hook is those three files side by side in each runtime's `hooks/`: `ddl_gate.py` (the entry the settings
name), `ddl_gate_core.py` (the code it loads) and `ddl_run.py` (its Run subcommands); each is linked,
checked and removed on its own. A project then needs only `design.md` and a short instruction
file (`dist/claude/.claude/CLAUDE.md` as `.claude/CLAUDE.md`, `dist/codex/AGENTS.md` as `AGENTS.md`;
both come from `hosts/<host>/guidance.md`).

  install    build dist/, create or repoint the symlinks, and merge the fragment (idempotent; existing
             settings are kept, DDL's own entries are replaced so a path change takes effect); a
             retired link that points into a DDL build (the Codex push rule `rules/ddl.rules`, which
             DDL no longer installs) is removed and named
  doctor     build dist/, check every link and merged entry, report a retired link as not OK until
             install removes it, probe the configured hooks in a temporary home (an unreviewed commit
             or push is denied; on Claude an edit inside a grant written into that home's store is
             allowed), run the gate's tests, check the gate's grant store, say whether the current
             directory is a DDL project, and audit the user-level settings for exits (below); prints
             `N OK, M not OK` and exits 1 when M > 0
  uninstall  remove the links that point at DDL, retired ones included, and the merged entries (an
             entry is removed only when its value is the one DDL wrote); a settings file left empty
             is removed; no backup is written on uninstall; needs no dist/ (the fragment is generated
             in memory when its file is absent); the gate's grant store is left in place and named
             when it holds anything, and removed when it is empty

A settings file that is not what DDL can work with (unreadable, not UTF-8, not valid JSON, not a
JSON object at its top level, or holding what cannot be written back as JSON: a number out of
range, text that is no valid Unicode) is never rewritten and never a traceback: doctor prints one
`not OK` line that names the file and the problem and goes on with its other checks; install and
uninstall print that line, leave the file as it is, go on with the other runtime, and exit 1. The
same holds in install and doctor for a `hooks`, `env` or `attribution` entry of another JSON
type; uninstall leaves such an entry alone, since nothing of DDL's can be in it, and still removes
DDL's entries from the others. A file or directory install or uninstall may not read or change
ends the run with one `not OK` line and exit 1. A settings file gets its new content in one step:
the content is written to a new file beside it, which then takes its place, so a write that fails
leaves the old file whole; a settings file that is a link stays one.

Runtimes: `--claude` and `--codex` select one; by default each runtime whose home directory exists
(`$HOME/.claude`, `$HOME/.codex`) is handled. `install --project DIR` copies the per-project layout
instead (`dist/claude/.claude/` into `DIR/.claude/`, `dist/codex/` into `DIR/`; an existing
instruction file is kept, and a retired file that an earlier copy left, recognized by its first line,
is removed). `--dry-run` prints the actions on the home directory without performing
them (dist/ is still built: it is this checkout's own build product). `$HOME` is honoured, so a
temporary home can be used for a rehearsal.

What the merge does (Claude Code `settings.json`): `hooks.<event>` gets the fragment's groups
appended after any group that already carries a DDL command (one whose `command` contains
`ddl_gate.py`) has been removed; `env`, `permissions.ask`, and `attribution` get the fragment's
values when the key is absent (a different existing value is kept and reported by `doctor`).
Codex `hooks.json` gets the same `hooks` treatment. The hook commands are rewritten for the user
level: `$CLAUDE_PROJECT_DIR/.claude/hooks/ddl_gate.py` becomes `$HOME/.claude/hooks/ddl_gate.py`,
and the Codex `git rev-parse` form becomes `$HOME/.codex/hooks/ddl_gate.py`. The first time a file
is changed, a copy is kept next to it as `<name>.ddl-backup`.

The exit audit (doctor). An exit leaves the machine or cannot be undone: a push, pull request and
release commands, publishing a package or an image, a transfer to another machine, a branch-moving
git command. doctor reads each `Bash` rule in `permissions.allow` of `$HOME/.claude/settings.json`
and each allowing `prefix_rule` in `$HOME/.codex/rules/*.rules`, and names the rules that let an
exit through unasked (status `exit`) or that run whatever command follows (status `wrapper`: a
wrapper such as `env` or `sudo`, or a runner such as `npx` or `uv run`, with no command spelled
after it; a shell or an interpreter whose script or code the rule leaves open; a rule that names
no program; every program of a system directory). Behind a listed wrapper or runner, and behind
those of its options the audit knows, the command a rule spells is classified in the wrapper's
place: `timeout 60 npm test`, `uv run pytest` and `python3 -m pytest` are no findings,
`sudo -u root git push` is an exit. A Claude rule without a wildcard is exact and passes only what
it spells, and a rule that asks a program for its version or its help is no finding. A line names
its rule by position (`permissions.allow[4]`, or file and line) and by the program and verb it was
classified by, in the audit's own words; the only piece of a rule's text a line can show is a
variable's name, for a rule that is nothing but an assignment (`Bash(NAME=…)`), never its value.
A rule or file the audit cannot read gets a `not audited` line: a quote or a here-document that
does not close, a program named through a variable, a rule of more than 4,000 characters, one that
spells more wildcard programs or deeper nesting than the audit follows, a rules file or a pattern
that is not plain literals or has more than 256 alternatives, a settings file doctor cannot read.
doctor also says, as information, when `permissions.defaultMode` is `bypassPermissions` and when
`$HOME/.codex/config.toml` never asks and sandboxes nothing. The audit ends with `exit audit: N
exit, M wrapper in user settings (not counted)`, with `, K not audited` behind the wrapper count
when K is not zero. The findings are information: they change neither the counts nor the exit code.
`doctor --strict` counts each finding and each `not audited` line as `not OK` and ends that line
with `(counted)`; a Claude settings file doctor cannot read then counts twice, once for the check
of the merged entries and once for the audit.

What the audit does not cover. It reads the rules as text and runs nothing, so how a host really
matches a rule against a command (word boundaries, compound commands, quoting, the host's own
built-in checks) stays the host's own; where the text can be read two ways the audit takes the
wider one. It reads the two user-level places only: not a project's `.claude/settings.json` or
`.claude/settings.local.json`, not managed settings, not a rule granted during a session, not the
`allowed-tools` of a user-level skill. It reads `Bash` rules and `prefix_rule` calls only: a rule
of another tool (an MCP tool, `WebFetch`, an edit of a file that is run later) is not looked at.
An allow rule that an `ask` or `deny` rule shadows is still reported. Its lists of programs and of
their options are a general default, not a complete one: a program they do not name is no finding,
and an option they do not name is read as taking no value. Inside a rule these are not read: the
script or code an interpreter is given, also where the rule spells it; the body of a
here-document, unless a shell takes it as its script; a here-string; a function defined with the
word `function` (the body of `name() { … }` is read), and what a call of a function, an alias or
a variable stands for; a redirection before the command word; `env -S` other than as a word of
its own, `fish -C`, and a runner's option that takes a command as one string (`npx -c`); an
escaped or quoted parenthesis inside a command substitution; a wildcard over a relative `bin`
directory such as `.venv/bin/*` (only one over a system directory is a finding).

The grant store (`$DDL_GATE_GRANT_DIR`, else `$XDG_STATE_HOME/ddl-gate`, else
`$HOME/.local/state/ddl-gate`) is created by the gate hook when it first needs it, never by
install. doctor checks that only its owner can enter it; its hook probes and its run of the
gate's tests get a disposable store, so doctor never writes into the durable one: the grant the
Claude probe needs is written into the probe's own temporary home.

Standard library only; python3 is the same dependency the gate hook has.
"""
import argparse
import ast
import hashlib
import itertools
import json
import os
import pathlib
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import warnings

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKILLS = ["ddl-protocol", "draft", "realize", "reflect", "validate", "commit", "docs", "refactoring", "resonate"]
GATE_MARK = "ddl_gate.py"
# The gate's files under each runtime's hooks/: the entry the settings name, the code it loads from beside itself,
# and the Run subcommands that code imports. Each is linked, checked and removed on its own.
GATE_FILES = ("ddl_gate.py", "ddl_gate_core.py", "ddl_run.py")

# Every source path points into the generated layout dist/ (tools/build.py), never at skills/, protocol/, or hosts/.
RUNTIMES = {
    "claude": {
        "home": ".claude",
        "label": "Claude Code",
        "retired": {},  # home-relative link -> (its former source in dist/, the first line of its former copy)
        "links": {**{f"skills/{n}": f"dist/claude/.claude/skills/{n}" for n in SKILLS},
                  "agents/explorer.md": "dist/claude/.claude/agents/explorer.md",
                  "agents/worker.md": "dist/claude/.claude/agents/worker.md",
                  **{f"hooks/{n}": f"dist/claude/.claude/hooks/{n}" for n in GATE_FILES}},
        "settings": "settings.json",
        "fragment": "dist/claude/.claude/settings.json",
        "rewrite": ('"$CLAUDE_PROJECT_DIR"/.claude/hooks/ddl_gate.py', '"$HOME"/.claude/hooks/ddl_gate.py'),
        "project_src": "dist/claude/.claude",
        "project_dst": ".claude",
        "instruction": "CLAUDE.md",
    },
    "codex": {
        "home": ".codex",
        "label": "Codex",
        "links": {**{f"skills/{n}": f"dist/codex/.agents/skills/{n}" for n in SKILLS},
                  "agents/explorer.toml": "dist/codex/.codex/agents/explorer.toml",
                  "agents/worker.toml": "dist/codex/.codex/agents/worker.toml",
                  **{f"hooks/{n}": f"dist/codex/.codex/hooks/{n}" for n in GATE_FILES}},
        # The push confirmation rule DDL once linked here; the gate now answers a reviewed push itself.
        "retired": {"rules/ddl.rules": ("dist/codex/.codex/rules/ddl.rules", "# DDL adapter for Codex: command rules")},
        "settings": "hooks.json",
        "fragment": "dist/codex/.codex/hooks.json",
        "rewrite": ('"$(git rev-parse --show-toplevel 2>/dev/null || pwd)/.codex/hooks/ddl_gate.py"',
                    '"$HOME/.codex/hooks/ddl_gate.py"'),
        "project_src": "dist/codex",
        "project_dst": ".",
        "instruction": "AGENTS.md",
    },
}


def build_module():
    """tools/build.py from this checkout (python3 -I keeps the script directory off sys.path)."""
    tools = str(ROOT / "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    import build
    return build


def ensure_dist(report):
    """Generate dist/ from the sources, so the links and copies have something to point at on a fresh clone."""
    written = build_module().write(ROOT)
    report.info(f"build {ROOT / 'dist'} ({len(written)} files)")


LINE_LIMIT = 500  # characters of one printed line


class Report:
    def __init__(self, dry_run=False):
        self.ok = 0
        self.bad = 0
        self.dry_run = dry_run

    def line(self, status, text):
        if len(text) > LINE_LIMIT:  # no line grows with what a file or a rule holds
            text = text[:LINE_LIMIT - 1] + "…"
        print(f"{status:<10}{text}")

    def good(self, text):
        self.ok += 1
        self.line("OK", text)

    def fail(self, text):
        self.bad += 1
        self.line("not OK", text)

    def info(self, text):
        self.line("info", text)


def home():
    return pathlib.Path(os.path.expanduser("~"))


def pretty(path):
    try:
        return "~/" + str(pathlib.Path(path).relative_to(home()))
    except ValueError:
        return str(path)


def load_json(path):
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return {}
    return json.loads(text)


def json_kind(value):
    """The JSON type of a value, in words."""
    kinds = {dict: "an object", list: "a list", str: "a string", bool: "a boolean", type(None): "null"}
    return kinds.get(type(value), "a number")


def user_settings(path):
    """(settings, None) for a user's settings file that is absent, empty or a JSON object that can be
    written back, and (None, what is wrong with it) otherwise. The words follow `<file> is`; they
    never quote the file, so a settings file that holds a secret cannot leak it through its own error."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}, None
    except UnicodeDecodeError:
        return None, "not UTF-8 text"
    except OSError as error:  # no permission, a directory in the file's place, ...
        return None, f"not readable ({error.strerror or type(error).__name__})"
    if not text.strip():
        return {}, None
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        return None, f"not valid JSON ({error})"
    except (ValueError, RecursionError):  # not the parser's own complaint: its words are not known to be free of the file's
        return None, "not valid JSON (a number too long or a nesting too deep to read)"
    if not isinstance(data, dict):
        return None, f"not a JSON object (its top level is {json_kind(data)})"
    # Python reads more than JSON text can carry (`1e400` becomes infinity, `"\ud83d"` half a
    # character). Such a file could be merged into but not written back, so it is refused here.
    try:
        json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except UnicodeEncodeError:
        return None, "not JSON that can be written back (it holds text that is no valid Unicode)"
    except (ValueError, RecursionError):
        return None, "not JSON that can be written back (it holds a number outside JSON's range)"
    return data, None


def section(settings, key, kind=dict):
    """settings[key] when it has the JSON type DDL writes there, else an empty value of that type:
    an entry of another type holds nothing of DDL's and is never a reason for a traceback."""
    value = settings.get(key)
    return value if isinstance(value, kind) else kind()


def misplaced(settings, frag):
    """What keeps DDL's fragment from being merged into settings, in words that follow `<file> is`:
    the first entry the fragment touches whose JSON type is not the one DDL writes. None when all fit."""
    wanted = [(key, dict) for key in ("hooks", "env", "permissions", "attribution") if key in frag]
    wanted += [(f"hooks.{event}", list) for event in frag.get("hooks", {})]
    wanted += [("permissions.ask", list)] if "ask" in frag.get("permissions", {}) else []
    absent = object()  # an entry that is not there fits; one that is `null` does not
    for name, kind in wanted:
        value = settings
        for part in name.split("."):
            value = value.get(part, absent) if isinstance(value, dict) else absent
        if value is not absent and not isinstance(value, kind):
            return f"not shaped as DDL needs it ({name} is {json_kind(value)}, not {json_kind(kind())})"
    return None


def read_text(path):
    """The file's text; empty when the file is absent or cannot be read."""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def same_file(link, source):
    """True when both paths lead to the same place. os.path.realpath never raises, where
    Path.resolve() does for a link that points at itself."""
    return os.path.realpath(link) == os.path.realpath(source)


def is_empty_directory(path):
    """True for a directory, not a link to one, that holds nothing; False when it cannot be listed."""
    try:
        return not os.path.islink(path) and os.path.isdir(path) and not os.listdir(path)
    except OSError:
        return False


def grant_store():
    """The gate's durable grant store at the user level: $DDL_GATE_GRANT_DIR, else
    $XDG_STATE_HOME/ddl-gate, else ~/.local/state/ddl-gate (an empty variable counts as unset).
    The same expression as grant_store in tools/ddl_gate.py, absolute path included, so doctor
    checks the directory the gate writes for a relative value or one with `..` too."""
    base = os.environ.get("DDL_GATE_GRANT_DIR")
    if not base:
        state = os.environ.get("XDG_STATE_HOME") or os.path.join(os.path.expanduser("~"), ".local", "state")
        base = os.path.join(state, "ddl-gate")
    return pathlib.Path(os.path.abspath(base))


def fragment_for(rt):
    """The adapter's settings with the hook commands rewritten for the user level; read from dist/ when
    it is built, otherwise generated in memory (uninstall needs no dist/)."""
    path = ROOT / rt["fragment"]
    if path.is_file():
        data = load_json(path)
    else:
        rel = pathlib.Path(rt["fragment"]).relative_to("dist").as_posix()
        data = json.loads(build_module().generate(ROOT)[rel].decode("utf-8"))
    old, new = rt["rewrite"]
    for groups in data.get("hooks", {}).values():
        for group in groups:
            for hook in group.get("hooks", []):
                hook["command"] = hook["command"].replace(old, new)
    data.pop("$comment", None)
    data.pop("description", None)
    return data


def is_ddl_group(group):
    """True for a hook group that carries a DDL command; anything of another shape is not DDL's."""
    hooks = section(group, "hooks", list) if isinstance(group, dict) else []
    return any(isinstance(h, dict) and isinstance(h.get("command"), str) and GATE_MARK in h["command"] for h in hooks)


def merge(settings, frag):
    """Return (merged, notes). Existing keys are kept; DDL hook groups are replaced."""
    out = json.loads(json.dumps(settings))
    notes = []
    hooks = out.setdefault("hooks", {})
    for event, groups in frag.get("hooks", {}).items():
        kept = [g for g in hooks.get(event, []) if not is_ddl_group(g)]
        hooks[event] = kept + groups
    for key, value in frag.get("env", {}).items():
        env = out.setdefault("env", {})
        if key not in env:
            env[key] = value
        elif env[key] != value:
            notes.append(f"env.{key} is {env[key]!r}, DDL expects {value!r} (kept)")
    for rule in frag.get("permissions", {}).get("ask", []):
        ask = out.setdefault("permissions", {}).setdefault("ask", [])
        if rule not in ask:
            ask.append(rule)
    for key, value in frag.get("attribution", {}).items():
        attr = out.setdefault("attribution", {})
        if key not in attr:
            attr[key] = value
        elif attr[key] != value:
            notes.append(f"attribution.{key} is {attr[key]!r}, DDL expects {value!r} (kept)")
    return out, notes


def unmerge(settings, frag):
    """settings without DDL's entries. An entry whose JSON type is not the one DDL writes holds
    nothing of DDL's: it is left as it is, so only what DDL installed is removed."""
    out = json.loads(json.dumps(settings))
    hooks = section(out, "hooks")
    for event in [event for event in hooks if isinstance(hooks[event], list)]:
        hooks[event] = [g for g in hooks[event] if not is_ddl_group(g)]
        if not hooks[event]:
            del hooks[event]
    env = section(out, "env")
    for key, value in frag.get("env", {}).items():
        if key in env and env[key] == value:
            del env[key]
    permissions = section(out, "permissions")
    ask = section(permissions, "ask", list)
    for rule in frag.get("permissions", {}).get("ask", []):
        if rule in ask:
            ask.remove(rule)
    if permissions.get("ask") == []:
        del permissions["ask"]
        if not permissions:
            del out["permissions"]
    attribution = section(out, "attribution")
    for key, value in frag.get("attribution", {}).items():
        if key in attribution and attribution[key] == value:
            del attribution[key]
    for key in ("hooks", "env", "attribution"):
        if out.get(key) == {}:
            del out[key]
    return out


def merged_state(settings, frag):
    """(present, missing, differing) entries of the fragment inside settings, for doctor."""
    present, missing, differing = [], [], []
    for event, groups in frag.get("hooks", {}).items():
        have = [g for g in section(section(settings, "hooks"), event, list) if is_ddl_group(g)]
        for g in groups:
            words = g["hooks"][0]["command"].split()
            what = words[2] if len(words) > 2 else words[-1]
            (present if g in have else missing).append(f"hooks.{event} ({what})")
    for key, value in frag.get("env", {}).items():
        got = section(settings, "env").get(key)
        (present if got == value else differing if got is not None else missing).append(f"env.{key}")
    asked = section(section(settings, "permissions"), "ask", list)  # a wrong-typed value holds no rule
    for rule in frag.get("permissions", {}).get("ask", []):
        (present if rule in asked else missing).append(f"permissions.ask {rule}")
    for key, value in frag.get("attribution", {}).items():
        got = section(settings, "attribution").get(key)
        (present if got == value else differing if got is not None else missing).append(f"attribution.{key}")
    return present, missing, differing


def write_json(path, data, report, backup=True):
    text = json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    if report.dry_run:
        return True
    if backup and path.exists():
        copy = path.with_name(path.name + ".ddl-backup")
        if not copy.exists():
            shutil.copy2(path, copy)
    replace_file(path, text)
    return True


def replace_file(path, text):
    """Give a user's file new content in one step: the text goes to a new file beside it, which
    then takes its place, so a write that fails leaves the old content whole. A link is followed
    (a settings file kept elsewhere stays a link) and an existing file keeps its mode."""
    data = text.encode("utf-8")  # before anything is touched: text that cannot be written changes nothing
    target = pathlib.Path(os.path.realpath(path))
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, scratch = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=".ddl-new")
    try:
        with os.fdopen(handle, "wb") as out:
            out.write(data)
        if target.exists():
            shutil.copymode(target, scratch)
        else:  # mkstemp makes a private file; a new settings file gets the mode any new file would
            mask = os.umask(0)
            os.umask(mask)
            os.chmod(scratch, 0o666 & ~mask)
        os.replace(scratch, target)
    except BaseException:
        try:
            os.unlink(scratch)
        except OSError:
            pass
        raise


def points_at_ddl(link, rel_source):
    """True when the symlink's target ends with the DDL-relative source path (any DDL checkout)."""
    try:
        target = os.readlink(link)
    except OSError:
        return False
    return target.rstrip("/").endswith(rel_source)


def retired_links(base, rt):
    """The links under base that DDL once installed and installs no more, still pointing into a DDL build
    (a dangling one included). A file of that name that is not such a link is the user's."""
    return [base / rel for rel, (source, _) in rt["retired"].items()
            if os.path.islink(base / rel) and points_at_ddl(base / rel, source)]


def selected_runtimes(args):
    chosen = [k for k in RUNTIMES if getattr(args, k)]
    if chosen:
        return chosen
    found = [k for k, rt in RUNTIMES.items() if os.path.isdir(home() / rt["home"])]
    if not found:
        raise SystemExit("neither ~/.claude nor ~/.codex exists; pass --claude or --codex to create one")
    return found


def cmd_install(args, report):
    if args.project:
        return install_project(args, report)
    keys = selected_runtimes(args)
    refused = 0  # settings files left unmerged: they alone make install exit 1, as other `not OK` lines never did
    for key in keys:
        rt = RUNTIMES[key]
        base = home() / rt["home"]
        print(f"== {rt['label']} ({pretty(base)})")
        for rel, src in rt["links"].items():
            source = ROOT / src
            link = base / rel
            if not source.exists():
                report.fail(f"{src} missing in {ROOT} (run python3 tools/build.py?)")
                continue
            if os.path.islink(link):
                if same_file(link, source):
                    report.good(f"link {pretty(link)} (unchanged)")
                    continue
                old = os.readlink(link)
                if not report.dry_run:
                    link.unlink()
                    link.symlink_to(source)
                report.good(f"link {pretty(link)} -> {source} (was {old})")
            elif os.path.exists(link):
                report.fail(f"{pretty(link)} exists and is not a symlink; move it away and run install again")
            else:
                if not report.dry_run:
                    link.parent.mkdir(parents=True, exist_ok=True)
                    link.symlink_to(source)
                report.good(f"link {pretty(link)} -> {source}")
        for link in retired_links(base, rt):
            old = os.readlink(link)
            if not report.dry_run:
                link.unlink()
                if is_empty_directory(link.parent):
                    link.parent.rmdir()
            report.good(f"remove {pretty(link)} (was {old}; DDL no longer installs it)")
        settings_path = base / rt["settings"]
        fragment = fragment_for(rt)
        settings, problem = user_settings(settings_path)
        problem = problem or misplaced(settings, fragment)
        if problem:  # the file is the user's: what cannot be merged into safely is left exactly as it is
            report.fail(f"{pretty(settings_path)} is {problem}; fragment not merged")
            refused += 1
            continue
        merged, notes = merge(settings, fragment)
        changed = write_json(settings_path, merged, report)
        report.good(f"merge {pretty(settings_path)} ({'updated' if changed else 'unchanged'})")
        for n in notes:
            report.info(n)
    if "codex" in keys:
        report.info("Codex: if Codex asks about new hooks, run /hooks once to trust them; "
                    "set [agents] max_concurrent_threads_per_session = 5 in ~/.codex/config.toml to match SWARM max: 5")
    return 1 if refused else 0


def install_project(args, report):
    dest = pathlib.Path(args.project).resolve()
    if not dest.is_dir():
        raise SystemExit(f"{dest}: not a directory")
    for key in [k for k in RUNTIMES if getattr(args, k)] or list(RUNTIMES):
        rt = RUNTIMES[key]
        src = ROOT / rt["project_src"]
        target = (dest / rt["project_dst"]).resolve()
        print(f"== {rt['label']} -> {target}")
        for path in sorted(p for p in src.rglob("*") if p.is_file()):
            rel = path.relative_to(src)
            out = target / rel
            if rel.name == rt["instruction"] and rel.parent == pathlib.Path(".") and out.exists():
                report.info(f"keep {out} (exists)")
                continue
            if out.exists() and out.read_bytes() == path.read_bytes():
                report.good(f"copy {out} (unchanged)")
                continue
            if not report.dry_run:
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, out)
            report.good(f"copy {out}")
        # An older copy carried the host implementations as files under the protocol skill; the generated
        # skill folds them into the entry and the operations, so the stale directory would shadow nothing
        # but confuse a reader.
        for stale in sorted(target.glob("**/ddl-protocol/hosts")):
            if stale.is_dir():
                if not report.dry_run:
                    shutil.rmtree(stale)
                report.good(f"remove {stale} (stale implementations, now folded into the skill)")
        # A retired file an earlier copy left: removed only when its first line is the one DDL's copy began with.
        for source, first in rt["retired"].values():
            old = target / pathlib.PurePosixPath(source).relative_to(rt["project_src"])
            if old.is_file() and not old.is_symlink() and read_text(old).startswith(first):
                if not report.dry_run:
                    old.unlink()
                    if is_empty_directory(old.parent):
                        old.parent.rmdir()
                report.good(f"remove {old} (DDL no longer installs it)")
    report.info("project copy done: the hook commands use $CLAUDE_PROJECT_DIR / the repository root; "
                "trust the folder (Claude Code) or the project and its hooks (Codex)")
    return 0


def configured_hook_outputs(settings, event, payload, env, cwd):
    """Run only matching DDL hooks from the saved configuration; never run the payload's tool.

    An empty output is a normal continuation, not an explicit permission grant. Keeping dispatch
    here means doctor checks the installed matcher and command as well as the gate itself.
    """
    outputs, count = [], 0
    match_value = payload.get("tool_name", "") if event == "PreToolUse" else payload.get("source", "")
    for group in section(section(settings, "hooks"), event, list):
        if not is_ddl_group(group):
            continue
        matcher = group.get("matcher")
        if matcher not in (None, "", "*") and not re.search(matcher, match_value):
            continue
        for hook in group["hooks"]:
            command = hook.get("command", "") if isinstance(hook, dict) else ""
            if not isinstance(command, str) or GATE_MARK not in command:
                continue
            count += 1
            proc = subprocess.run(command, shell=True, input=json.dumps(payload), capture_output=True,
                                  text=True, cwd=cwd, env=env, timeout=10)
            if proc.returncode != 0 or proc.stderr:
                raise ValueError(f"configured {event} hook failed: {proc.stderr.strip() or proc.returncode}")
            if proc.stdout.strip():
                output = json.loads(proc.stdout)
                if not isinstance(output, dict):
                    raise ValueError(f"configured {event} hook returned a non-object")
                outputs.append(output)
    if not count:
        raise ValueError(f"no configured DDL {event} hook matched {match_value!r}")
    return outputs


PROBE_GRANT = "R-d0c7d0c7d0c7d0c7"  # the report ID of the grant the Claude probe writes into its temporary store
PROJECT_KEY_LENGTH = 16  # the gate's own (ddl_gate_core.PROJECT_KEY_LENGTH): hex digits of the root's SHA-256


def probe_grant(store, project, host):
    """Record one active grant for `project` in `store` as the gate keeps it, `<store>/<project key>/grants/<id>.json`
    (only its owner can enter): an edit of `src/**`, expiring in an hour. The store is the probe's own."""
    root = os.path.realpath(project)
    key = hashlib.sha256(root.encode("utf-8", "surrogateescape")).hexdigest()[:PROJECT_KEY_LENGTH]
    stamp = lambda seconds: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(seconds))  # noqa: E731
    now = time.time()
    record = {"id": PROBE_GRANT, "projectKey": key, "root": root,
              "grant": {"paths": ["src/**"], "commands": [], "machines": [], "handover": [],
                        "budget": {"minutes": 60, "fixAttempts": 0}, "expires": stamp(now + 3600)},
              "approvedAt": stamp(now), "session": "doctor", "host": host}
    directory = pathlib.Path(store)
    for part in ("", key, "grants"):
        directory = directory / part if part else directory
        directory.mkdir(mode=0o700, exist_ok=True)
    fd = os.open(directory / (PROBE_GRANT + ".json"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


def doctor_git_hooks(key, base, settings, report):
    """Probe through the installed hooks that an unapproved commit or push is denied and, on Claude, that an edit
    inside a grant recorded in the probe's own store is allowed; execute no payload command."""
    with tempfile.TemporaryDirectory(prefix="ddl-doctor-hooks-") as tmp:
        isolated = pathlib.Path(tmp)
        hooks = isolated / RUNTIMES[key]["home"] / "hooks"
        hooks.mkdir(parents=True)
        for name in GATE_FILES:  # as installed: the entry and the modules beside it
            (hooks / name).symlink_to(base / "hooks" / name)
        # The gate acts only in a DDL project: one below the temporary home with the marker line.
        project = isolated / "project"
        project.mkdir()
        (project / "CLAUDE.md").write_text("→ DDL-PROTOCOL\n", encoding="utf-8")
        # The probes never reach the durable grant store: state and grants both stay in the temporary home.
        env = dict(os.environ, HOME=str(isolated), CODEX_HOME=str(isolated / ".codex"),
                   CLAUDE_PROJECT_DIR=str(isolated), DDL_GATE_STATE_DIR=str(isolated / "state"),
                   DDL_GATE_GRANT_DIR=str(isolated / "grants"))
        transcript = isolated / "open.jsonl"
        if key == "claude":
            records = [{"type": "user", "message": {"role": "user", "content": "Continue."},
                        "origin": {"kind": "human"}, "turnOrigin": "human", "promptSource": "typed"}]
        else:
            records = [{"type": "event_msg", "payload": {"type": "task_started", "turn_id": "doctor"}},
                       {"type": "response_item", "payload": {"type": "message", "role": "user",
                         "content": [{"type": "input_text", "text": "Continue."}]}}]
        transcript.write_text("".join(json.dumps(record) + "\n" for record in records))
        probes = [("git commit --cleanup=verbatim -m doctor", str(transcript), "default"),
                  ("git push origin main", str(transcript), "default"),
                  ("git push origin main", None, "default"),
                  ("git push origin main", str(transcript), "bypassPermissions")]
        if key == "codex":
            probes += [("git -C /tmp push", str(transcript), "default"), ("git -C /tmp push", None, "default")]
        for index, (command, record, mode) in enumerate(probes):
            payload = {"session_id": f"doctor-{index}", "turn_id": "doctor", "transcript_path": record,
                       "cwd": str(project), "hook_event_name": "PreToolUse", "permission_mode": mode,
                       "tool_name": "Bash", "tool_input": {"command": command}}
            name = (f"{RUNTIMES[key]['label']} installed PreToolUse: {command} "
                    f"({'OPEN' if record else 'null'} transcript, {mode})")
            try:
                outputs = configured_hook_outputs(settings, "PreToolUse", payload, env, project)
                decisions = [specific.get("permissionDecision") if isinstance(specific, dict) else None
                             for specific in (out.get("hookSpecificOutput") for out in outputs)]
                valid = decisions == ["deny"] and all("DDL Git review:" in out.get("hookSpecificOutput", {}).get(
                    "permissionDecisionReason", "") for out in outputs)
                outcome = "deny (independent Git review)"
                (report.good if valid else report.fail)(f"{name} -> {outcome if valid else repr(outputs)}")
            except (OSError, ValueError, TypeError, re.error, subprocess.TimeoutExpired) as exc:
                report.fail(f"{name} -> {exc}")
        if key != "claude":  # Codex answers allow only through PermissionRequest; its PreToolUse never allows
            return
        # An edit inside a grant: the grant is recorded in the probe's store, after the deny probes ran without one.
        (project / "src").mkdir()
        target = project / "src/doctor.txt"
        target.write_text("a\n", encoding="utf-8")
        name = (f"{RUNTIMES[key]['label']} installed PreToolUse: Edit src/doctor.txt inside grant {PROBE_GRANT} "
                "(OPEN transcript, default)")
        payload = {"session_id": "doctor-grant", "turn_id": "doctor", "transcript_path": str(transcript),
                   "cwd": str(project), "hook_event_name": "PreToolUse", "permission_mode": "default",
                   "tool_name": "Edit", "tool_input": {"file_path": str(target), "old_string": "a", "new_string": "b"}}
        try:
            probe_grant(env["DDL_GATE_GRANT_DIR"], project, key)
            outputs = configured_hook_outputs(settings, "PreToolUse", payload, env, project)
            specific = [out.get("hookSpecificOutput") for out in outputs]
            valid = (len(specific) == 1 and isinstance(specific[0], dict)
                     and specific[0].get("permissionDecision") == "allow"
                     and str(specific[0].get("permissionDecisionReason", "")).startswith(f"DDL: inside grant {PROBE_GRANT}"))
            outcome = "allow (inside the grant)"
            (report.good if valid else report.fail)(f"{name} -> {outcome if valid else repr(outputs)}")
        except (OSError, ValueError, TypeError, re.error, subprocess.TimeoutExpired) as exc:
            report.fail(f"{name} -> {exc}")


def doctor_retired(rt, base, report):
    """A link DDL once installed and installs no more (the Codex push rule) is not OK until install removes it;
    its absence is the check that no DDL rule is installed. A file of that name that is not DDL's link is named."""
    found = retired_links(base, rt)
    for link in found:
        report.fail(f"{pretty(link)} -> {os.readlink(link)}: DDL no longer installs it (run install to remove it)")
    for rel in rt["retired"]:
        link = base / rel
        if link in found:
            continue
        if os.path.lexists(link):
            report.info(f"{pretty(link)} is not DDL's; left in place")
        else:
            report.good(f"{pretty(link)} absent (DDL installs no {rt['label']} rule)")


# The exit audit. It reads each allowing rule as text, classifies the commands the rule spells out,
# and runs nothing. A printed line names a rule by its position and by words from the lists below,
# never by the rule's own text: a rule may carry a token, a password or a credential URL.
#
# How the last command of a rule ends decides what it can still become.
CLOSED, OPEN, INSIDE = 0, 1, 2  # spelled out in full; more words may follow; the last word itself is unfinished

SHELLS = frozenset("bash sh zsh fish dash ksh".split())
SHELL_VALUE_OPTIONS = frozenset(["-o", "+o", "-O", "+O", "--rcfile", "--init-file"])
CODE_FLAG = re.compile(r"-[A-Za-z]*c[A-Za-z]*|--command")
# The options of a runner (`npx`, `uv run`, `npm exec`) whose value is the next word.
RUNNER_VALUE_OPTIONS = frozenset(
    "-p --package --from --with --with-editable --with-requirements --python --spec --index --index-url "
    "--extra-index-url --env-file --directory --project --config-file --cache-dir --pip-args -w --workspace "
    "--filter -C --dir --cwd --venv --extra --group --only-group --no-group".split())
# A wrapper runs the command spelled after its own options. Each one maps to the options whose value
# is the next word: without them `sudo -u root git push` would read `root` as the program.
WRAPPERS = {name: frozenset(options.split()) for name, options in {
    "env": "-u --unset -C --chdir -P -a --argv0",
    "sudo": "-u --user -g --group -h --host -p --prompt -C --close-from -D --chdir -R --chroot -r --role "
            "-t --type -T --command-timeout -U --other-user",
    "doas": "-u -C",
    "timeout": "-s --signal -k --kill-after",
    "gtimeout": "-s --signal -k --kill-after",
    "xargs": "-I -n -P -L -s -E -d -a -J -R -S --max-args --max-procs --max-lines --max-chars --delimiter --arg-file",
    "parallel": "-j --jobs -a --arg-file -N -n --max-args -L -S --sshlogin -I -d --delimiter -E --colsep -C "
                "--results --joblog --timeout --delay --retries --halt --tmpdir --tagstring --env --workdir --wd",
    "nice": "-n --adjustment",
    "stdbuf": "-i --input -o --output -e --error",
    "time": "-f --format -o --output",
    "exec": "-a",
    "watch": "-n --interval -q --equexit",
    "nohup": "", "setsid": "", "command": "", "busybox": "", "eval": "", "su": "",
}.items()}
# A package runner fetches or finds a program and runs it with the words that follow.
WRAPPERS.update({name: RUNNER_VALUE_OPTIONS for name in ("npx", "uvx", "bunx")})
WRAPPER_ARGUMENTS = {"timeout": 1, "gtimeout": 1}       # words of its own before the command: the duration
TEXT_WRAPPERS = frozenset(["eval", "watch", "parallel"])  # these hand their words to a shell as one text
APPENDING = frozenset(["xargs", "parallel"])             # these add arguments from their input
# The same for a package manager's runner form: the command follows the form's words and options.
RUNNER_FORMS = {"pipx": ("run",), "uv": ("run", "tool run"), "npm": ("exec", "x"), "pnpm": ("exec", "dlx"),
                "yarn": ("dlx", "exec"), "poetry": ("run",), "pdm": ("run",), "hatch": ("run",), "bundle": ("exec",),
                "bun": ("x",)}
# An interpreter runs the script, module or code a rule names; the options listed take a value that is none of those.
INTERPRETERS = {name: frozenset(options.split()) for name, options in {
    "python": "-X -W --check-hash-based-pycs",
    "python3": "-X -W --check-hash-based-pycs",
    "node": "-r --require --import --loader --experimental-loader -C --conditions --env-file",
    "deno": "-c --config --import-map --cert --location --seed -L --log-level",
    "bun": "-r --preload --cwd -c --config --env-file --define -d --loader -l",
    "ruby": "-I -r -C -E",
    "perl": "-I",
    "php": "-d --define -c --php-ini -z --zend-extension -t --docroot -S --server",
    "lua": "-l",
    "osascript": "-l -s",
    "pwsh": "-executionpolicy -ep -ex -workingdirectory -wd -configurationname -settingsfile -settings "
            "-windowstyle -inputformat -outputformat -custompipename",
}.items()}
SUBCOMMANDS = {"deno": ("run", "eval"), "bun": ("run",)}  # after these the script or code is still to come
# `python3.12` is read as `python`. The pattern is closed: no part of a rule gets into a line through it.
PYTHON = re.compile(r"python(?:[0-9](?:\.[0-9]{1,2})?)?")
INLINE = re.compile(r"-[A-Za-z]*[cemr]|--eval|--print|eval|-command|-encodedcommand|-commandwithargs")
TRANSFERS = frozenset("rsync scp sftp ssh rclone nc ncat socat ftp curl wget".split())
# Asked for its version or its help, a program runs nothing else. The long flags mean that everywhere
# (a program without them stops with an error); `-V` and `-h` only for the programs named here
# (`rsync -h` and `sudo -h host` mean something else).
INQUIRIES = frozenset(["--version", "--help"])
SHORT_VERSION = frozenset("python python3 curl wget ssh rsync rclone socat sudo perl".split())
SHORT_HELP = frozenset("python python3 node perl ruby php deno bun curl wget rclone socat git gh glab npm pnpm yarn "
                       "cargo uv poetry gem twine docker podman".split())
GIT_EXITS = frozenset("push merge cherry-pick revert reset rebase pull checkout switch send-email".split())
GIT_PAIRS = {"lfs": "push", "subtree": "push"}
GIT_VALUE_OPTIONS = frozenset(["-C", "-c", "--git-dir", "--work-tree", "--namespace"])
FORGES = frozenset(["gh", "glab"])
FORGE_READS = frozenset("view list status diff checks watch search help version".split())
FORGE_VALUE_OPTIONS = frozenset(["-R", "--repo"])
# The forge words a line may show; any other word of a forge command is printed as `…`.
FORGE_WORDS = frozenset(
    "api pr mr issue release repo workflow run ci gist secret variable auth browse codespace cache label project "
    "ruleset extension alias config snippet schedule deploy-key ssh-key gpg-key create merge close reopen edit "
    "update comment note review ready delete sync fork clone rename archive unarchive transfer upload download "
    "rerun retry cancel enable disable set remove add lock unlock pin unpin develop login logout refresh checkout "
    "approve revoke rebase push publish trigger".split())
PUBLISHES = {"npm": "publish", "pnpm": "publish", "yarn": "publish", "bun": "publish", "cargo": "publish",
             "uv": "publish", "poetry": "publish", "gem": "push", "twine": "upload", "docker": "push", "podman": "push"}
PUBLISH_GROUPS = {"yarn": ("npm",), "docker": ("image", "manifest", "compose"), "podman": ("image", "manifest")}
PUBLISH_VALUE_OPTIONS = frozenset("--prefix -w --workspace --filter -F -C --cwd --dir --directory -P --project "
                                  "--context -H --host --config --log-level --registry --userconfig".split())
RUNNER_GLOBALS = PUBLISH_VALUE_OPTIONS | RUNNER_VALUE_OPTIONS  # the options before a runner form whose value is the next word
AUDITED = sorted(set(WRAPPERS) | SHELLS | set(INTERPRETERS) | TRANSFERS | FORGES | set(PUBLISHES) | set(RUNNER_FORMS) | {"git"})
ASSIGNMENT = re.compile(r"[^\W\d]\w*(?:\[[^\]]*\])?\+?=")
VARIABLE = re.compile(r"(?:[A-Za-z_][A-Za-z0-9_]{0,39}|…)=…")
SHELL_BREAKS = ";&|()`\n"
SHELL_KEYWORDS = frozenset(["if", "then", "elif", "else", "while", "until", "do", "!", "{"])
HERE = "\0<<"  # stands in a command's words for a here-document; the word after it is the body
HERE_ENDS = " \t\r\n;&|()<>`"
UNCLOSED = "whose quoting does not close"
UNENDED = "whose here-document does not end"
NESTED = "that nests commands deeper than the audit follows"
UNNAMED = "whose program is a variable"
TOO_LONG = "that is longer than the audit reads"
TOO_MANY = "that spells more wildcard programs than the audit follows"
REASONS = frozenset([UNCLOSED, UNENDED, NESTED, UNNAMED, TOO_LONG, TOO_MANY])
EVERY_PROGRAM = "passes every program of a directory unasked"
SYSTEM_PARENTS = frozenset(["/usr", "/usr/local", "/opt", "/opt/homebrew", "~", "$HOME"])  # the program directories lie below
OWN_WORDS = (frozenset(AUDITED) | GIT_EXITS | FORGE_WORDS | set(GIT_PAIRS) | set(GIT_PAIRS.values()) | set(PUBLISHES.values())
             | {word for forms in RUNNER_FORMS.values() for form in forms for word in form.split()}
             | {"(any", "subcommand)", "*", "…", "bin", "sbin"})
# One rule must cost little whatever it spells: a wildcard program stands for every listed name, and
# scripts nest in scripts. These bound the work; a rule beyond them is reported as not audited.
RULE_LIMIT = 4000     # characters of one rule
NESTING_LIMIT = 8     # commands inside commands
WILDCARD_COST = 4     # levels of that nesting a wildcard program uses up
WILDCARD_LIMIT = 8    # wildcard programs in one rule
PATTERN_LIMIT = 256   # alternatives of one Codex pattern


class Reading:
    """What reading one rule has found and cost so far. The same words reached twice (through two
    names a wildcard may stand for) are classified once, and wildcard programs are counted."""

    def __init__(self):
        self.known = {}
        self.wildcards = 0


def pieces(word):
    """The texts between the wildcards of a rule's word. A run of wildcards counts as one: the pieces
    between them are then no more than the word's letters, however many wildcards it spells."""
    return (re.sub(r"\*+", "*", word) if "**" in word else word).split("*")


def fits(word, name, open_end=False, parts=None):
    """True when a rule's word can stand for name: `*` inside the word matches anything, and with an
    open end (the rule stops inside the word) the word may be only the beginning of name. parts are
    the word's pieces, for a caller that tries one word against many names."""
    first, *middle = parts or pieces(word)
    if not name.startswith(first):
        return False
    if not middle:
        return open_end or name == first
    position = len(first)
    for piece in middle[:-1]:  # leftmost match of each piece: linear, whatever the rule spells
        position = name.find(piece, position) + len(piece)
        if position < len(piece):
            return False
    if open_end:
        return name.find(middle[-1], position) >= 0
    return len(name) - len(middle[-1]) >= position and name.endswith(middle[-1])


def positionals(words, value_options=()):
    """(index, word) of each word that is not an option, one at a time; the word after an option that
    takes its value as the next word is skipped. A caller takes the first few and reads no further."""
    skip = False
    for index, word in enumerate(words):
        if skip:
            skip = False
        elif word.startswith("-"):
            skip = word in value_options
        else:
            yield index, word


def after_options(words, values=()):
    """How many leading words are options or the values of options. `values` names the options whose
    value is the next word; one may end a cluster of short flags (`-nu root`), while `--user=root`
    and `-uroot` carry their value themselves. `--` ends the options and a lone `-` is not one."""
    index = 0
    while index < len(words) and words[index].startswith("-") and words[index] != "-":
        word = words[index]
        index += 1
        if word == "--":
            break
        letters = "" if word.startswith("--") else word[1:]
        first = next((at for at, letter in enumerate(letters) if "-" + letter in values), None)
        if word in values or (first is not None and first == len(letters) - 1):
            index += 1
    return index


def spelled(words):
    """words without here-documents: a body is input to the command, not part of its command line."""
    kept, skip = [], 0
    for word in words:
        skip = 2 if word == HERE else skip
        if skip:
            skip -= 1
        else:
            kept.append(word)
    return kept


def here_document(text, at):
    """(terminator, tabs, index behind the operator) for the `<<` at `at`, or None when what follows
    names no terminator. tabs is True for `<<-`, whose terminator line may begin with tabs."""
    cut = at + 2
    tabs = text.startswith("-", cut)
    cut += tabs
    while text[cut:cut + 1] in (" ", "\t"):
        cut += 1
    quote = text[cut:cut + 1]
    if quote in ("'", '"'):
        close = text.find(quote, cut + 1)
        return (text[cut + 1:close], tabs, close + 1) if close > cut + 1 else None
    stop = cut
    while stop < len(text) and text[stop] not in HERE_ENDS:
        stop += 1
    terminator = text[cut:stop].replace("\\", "")
    return (terminator, tabs, stop) if terminator else None


def here_document_end(text, at, terminator, tabs):
    """(where the body that starts at `at` ends, where the terminator's line ends), or None when the
    text ends before a line that is the terminator."""
    while True:
        close = text.find("\n", at)
        stop = len(text) if close < 0 else close
        line = text[at:stop].rstrip("\r")
        if (line.lstrip("\t") if tabs else line) == terminator:
            return at, stop
        if close < 0:
            return None
        at = close + 1


def closing_parenthesis(text, at):
    """Index of the parenthesis that closes the one opened before `at`, or -1. The body of a
    here-document is passed over: it is prose, and its parentheses and quotes pair with nothing.
    Inside `$((`, `<<` is a shift and starts none."""
    depth, pending, arithmetic = 1, [], text.startswith("(", at)
    while at < len(text):
        ch = text[at]
        if ch == "<" and text.startswith("<<", at) and not arithmetic:
            opened = None if text.startswith("<<<", at) else here_document(text, at)
            if opened:
                pending.append(opened)
            at = opened[2] if opened else at + 2 + text.startswith("<<<", at)
            continue
        at += 1
        if ch == "\n" and pending:
            for terminator, tabs, _ in pending:
                ended = here_document_end(text, at, terminator, tabs)
                if ended is None:
                    return -1
                at = min(ended[1] + 1, len(text))
            pending = []
            continue
        depth += (ch == "(") - (ch == ")")
        if not depth:
            return at - 1
    return -1


def double_quoted(text, at, nested):
    """(the text inside the double quotes opened before `at`, the index after them), or None when
    they do not close. There a backslash frees only `$`, a backquote, a quote, itself and a newline.
    A command substitution still runs: its text is added to nested, to be classified once, and `$`
    stands for it in the quoted text."""
    inside = []
    while at < len(text):
        ch = text[at]
        if ch == '"':
            return "".join(inside), at + 1
        if ch == "\\" and text[at + 1:at + 2] in ('"', "\\", "$", "`", "\n"):
            inside.append(text[at + 1].strip("\n"))
            at += 2
            continue
        opened = 1 if ch == "`" else 2 if text.startswith("$(", at) else 0
        if not opened:
            inside.append(ch)
            at += 1
            continue
        close = text.find("`", at + 1) if ch == "`" else closing_parenthesis(text, at + 2)
        if close < 0:
            return None
        nested.append(text[at + opened:close])
        inside.append("$")
        at = close + 1
    return None


def shell_commands(text):
    """(closed, last, nested) for a shell text, or why it cannot be read (UNCLOSED, UNENDED).

    closed holds the words of each command the text completes: it is split at `;`, `&`, `|`,
    parentheses, backquotes and newlines outside quotes. last holds the words of the command the
    text ends in (none yet where a new one may start), or is None where none may start (right
    behind a closed subshell or a here-document). A command substitution interrupts its command,
    which goes on behind it with `$` standing for the substitution; nested holds the text of each
    substitution found inside double quotes. A here-document leaves HERE and then its body among
    its command's words, and the body is not split. A comment is dropped and a backslash keeps the
    character after it.
    """
    closed, words, nested = [], [], []
    held = []     # per open parenthesis or backquote: (what closes it, the command a substitution interrupts)
    pending = []  # the here-documents opened on this line: (terminator, tabs, the words they belong to, the body's place)
    word = None   # the pieces of the word being read, joined at its end: a long word costs its length, no more
    fresh = True  # a new command may start here
    at, size = 0, len(text)
    while at < size:
        ch = text[at]
        if ch == "<" and text.startswith("<<", at):
            # Between two parentheses `<<` is a shift; `<<<` starts a here-string, which is one more word.
            shift = len(held) > 1 and held[-1][0] == held[-2][0] == ")"
            opened = None if shift or text.startswith("<<<", at) else here_document(text, at)
            if opened:
                words += (["".join(word)] if word is not None else []) + [HERE, ""]
                pending.append((opened[0], opened[1], words, len(words) - 1))
                word, at = None, opened[2]
            else:
                run = 2 + text.startswith("<<<", at)
                word = (word or []) + [text[at:at + run]]
                at += run
            continue
        if ch in SHELL_BREAKS or ch in " \t\r":
            opens = ch == "`" and not (held and held[-1][0] == "`")
            if opens:
                word = (word or []) + ["$"]
            if word is not None:
                words.append("".join(word))
                word = None
            if opens or (ch == "(" and text[at - 1:at] in ("$", "<", ">")):
                held.append((")" if ch == "(" else "`", words))
                words, fresh = [], True
            elif ch == "(":  # a subshell, or the parentheses of a function: a new command starts in it
                closed.append(words)
                held.append((")", None))
                words, fresh = [], True
            elif held and ch == held[-1][0]:
                closed.append(words)
                interrupted = held.pop()[1]
                # Behind a subshell only an operator can follow: no command starts there until one does.
                words, fresh = ([], False) if interrupted is None else (interrupted, True)
            elif ch in SHELL_BREAKS:
                closed.append(words)
                words, fresh = [], True
            at += 1
            if ch == "\n" and pending:  # the bodies start on the next line, in the order they were opened
                for terminator, tabs, owner, place in pending:
                    ended = here_document_end(text, at, terminator, tabs)
                    if ended is None:
                        return UNENDED
                    owner[place] = text[at:ended[0]]
                    at = min(ended[1] + 1, size)
                    fresh = ended[1] < size  # a terminator at the very end leaves no line for a new command
                pending = []
            continue
        if ch == "#" and word is None:
            close = text.find("\n", at)
            at = size if close < 0 else close
            continue
        word = [] if word is None else word
        if ch == "\\":
            if text[at + 1:at + 2] != "\n":  # a backslash before a newline only joins the two lines
                word.append(text[at + 1:at + 2])
            at += 2
        elif ch == "'":
            close = text.find("'", at + 1)
            if close < 0:
                return UNCLOSED
            word.append(text[at + 1:close])
            at = close + 1
        elif ch == '"':
            quoted = double_quoted(text, at + 1, nested)
            if quoted is None:
                return UNCLOSED
            word.append(quoted[0])
            at = quoted[1]
        else:
            word.append(ch)
            at += 1
    if pending:
        return UNENDED  # the text ends on the line that opens the here-document
    if word is not None:
        words.append("".join(word))
    closed += [interrupted for _, interrupted in held if interrupted]  # the text ends inside a substitution
    return [command for command in closed if command], words if words or fresh else None, nested


def text_findings(text, end, depth, reading):
    """[(status, what)] for every command a shell text spells out; `end` is how its last command ends."""
    if depth > NESTING_LIMIT:
        return [("unaudited", NESTED)]
    key = (text, end, depth)
    if key not in reading.known:
        split = shell_commands(text)
        if isinstance(split, str):
            found = [("unaudited", split)]  # a later command could hide behind what does not close
        else:
            closed, last, nested = split
            found = []
            for inner in nested:
                found += text_findings(inner, CLOSED, depth + 1, reading)
            for words in closed:
                found += command_findings(words, CLOSED, depth, reading)
            if last is not None:
                found += command_findings(last, end, depth, reading)
        reading.known[key] = found
    return reading.known[key]


def command_findings(words, end, depth, reading):
    """[(status, what)] for one command and the way it ends (CLOSED, OPEN or INSIDE).

    status is "exit" (what: the program and verb the rule lets through), "wrapper" (what: the
    program that runs any command; `NAME=…`, `*` or nothing where the rule names no program) or
    "unaudited" (what: why the command cannot be read). what is made of this module's own words.
    A command spelled out in full can only pass what it spells; an open one also what may follow.
    """
    if depth > NESTING_LIMIT:
        return [("unaudited", NESTED)]
    key = (tuple(words), end, depth)
    if key not in reading.known:
        reading.known[key] = one_command(list(words), end, depth, reading)
    return reading.known[key]


def one_command(words, end, depth, reading):
    """command_findings for words not classified before."""
    words = list(itertools.dropwhile(SHELL_KEYWORDS.__contains__, words))
    assigned = list(itertools.takewhile(ASSIGNMENT.match, words))
    words = words[len(assigned):]
    if not words:  # the rule ends before it names a program
        if end == CLOSED:
            return []
        if not assigned:
            return [("wrapper", "")]
        # The variable's name stands for the rule; a name the line cannot show safely is left out with its value.
        name = re.match(r"[A-Za-z_][A-Za-z0-9_]{0,39}(?![A-Za-z0-9_])", assigned[0])
        return [("wrapper", (name.group() if name else "…") + "=…")]
    directory, _, program = words[0].rpartition("/")
    rest = words[1:]
    unfinished = end == INSIDE and not rest
    if "$" in program:
        return [("unaudited", UNNAMED)]
    if "*" not in program and not unfinished:
        return program_findings(program, rest, end, depth, reading)
    if not program.strip("*"):  # every program: of one directory, or any at all
        if not directory:
            return [("wrapper", "*")]
        folder = os.path.basename(directory)
        # A system directory holds wrappers and exits. Any other one, a relative one above all, holds
        # scripts of the project's or the user's own, and a rule over them is one over fixed scripts.
        if directory[0] in "/~$" and folder in ("bin", "sbin"):
            return [("wrapper", f"…/{folder}/*")]
        return [("wrapper", "…/*")] if directory in SYSTEM_PARENTS else []
    # A wildcard program stands for every listed name it fits. Each such program uses up several
    # levels of nesting and one of the few a rule may spell: the names would multiply otherwise.
    reading.wildcards += 1
    if reading.wildcards > WILDCARD_LIMIT:
        return [("unaudited", TOO_MANY)]
    found, parts = [], pieces(program)
    for name in AUDITED:
        if fits(program, name, unfinished, parts):
            found += program_findings(name, rest, min(end, OPEN) if not rest else end, depth + WILDCARD_COST, reading)
    for status in ("wrapper", "exit", "unaudited"):  # one line for the rule: the widest thing it may become
        chosen = [finding for finding in found if finding[0] == status][:1]
        if chosen:
            return chosen
    return []


def program_findings(program, rest, end, depth, reading):
    """Findings for one program name and the words after it (the cases are command_findings')."""
    if program not in INTERPRETERS and PYTHON.fullmatch(program):
        program = "python"
    asked, whole = rest[0] if rest else "", not (end == INSIDE and len(rest) == 1)
    if asked in INQUIRIES or (whole and ((asked == "-V" and program in SHORT_VERSION) or (asked == "-h" and program in SHORT_HELP))):
        return []  # its version or its help: the program runs nothing else, whatever follows
    if program in SHELLS or program == "su":
        return shell_findings(program, rest, end, depth, reading)
    if program in WRAPPERS:
        return wrapper_findings(program, rest, end, depth, reading)
    if program in INTERPRETERS:
        found = interpreter_findings(program, rest, end)
        if found or not (program in PUBLISHES or program in RUNNER_FORMS):
            return found
    if program in TRANSFERS:
        return [] if end == CLOSED and not rest else [("exit", program)]  # alone and spelled out in full, it moves nothing
    if program == "git":
        return git_findings(rest, end)
    if program in FORGES:
        return forge_findings(program, rest, end)
    # A package manager publishes and runs. A rule that names it alone keeps the one line for its
    # publish verb, which the runner form does not make any narrower.
    found = publish_findings(program, rest, end) if program in PUBLISHES else []
    if found or program not in RUNNER_FORMS:
        return found
    return runner_findings(program, rest, end, depth, reading)


def shell_findings(program, rest, end, depth, reading):
    """A shell (or su) runs the script after its command flag, a script file, or a here-document.
    A file named in the rule is fixed and a script is read as commands; the shell is a wrapper
    while the rule leaves either one open."""
    rest = [part for word in rest for part in (["--command", word[10:]] if word.startswith("--command=") else [word])]
    if program == "su":  # a user's name is no script: only the word after the command flag is one
        flags = [at for at, word in enumerate(rest) if CODE_FLAG.fullmatch(word)]
        rest = rest[flags[0]:] if flags else []
    code = stdin = False
    index = 0
    while index < len(rest) and rest[index][:1] in ("-", "+"):
        word = rest[index]
        cluster = "" if word.startswith("--") else word[1:]
        code = code or bool(CODE_FLAG.fullmatch(word))
        stdin = stdin or (word[0] == "-" and "s" in cluster)
        index += 2 if word in SHELL_VALUE_OPTIONS or cluster[-1:] in ("o", "O") else 1
    script = rest[index] if index < len(rest) else ""
    if any("*" in word for word in rest[:index]) or set(script) == {"*"}:
        return [("wrapper", program)]  # a wildcard where the options stand can become the command flag and a script
    here = next((at for at in range(index, len(rest) - 1) if rest[at] == HERE), None)
    if not code and here is not None and (stdin or here == index):  # the script is the here-document's body
        return text_findings(rest[here + 1], CLOSED, depth + 1, reading)
    if index >= len(rest) or (stdin and not code):  # no script is spelled: it comes from what follows or from the input
        return [] if end == CLOSED else [("wrapper", program)]
    if not code:
        return []
    found = text_findings(script, CLOSED, depth + 1, reading)
    # A wildcard inside the script, or a rule that stops inside it, lets any command be added to it.
    return ([("wrapper", program)] if "*" in script or (end == INSIDE and index == len(rest) - 1) else []) + found


def wrapped(program, shown, after, values, as_text, end, depth, reading):
    """Findings for the command spelled in `after`, the words behind a wrapper or a runner form:
    its own options (`values` take the next word) are passed over and the command is classified.
    The wrapper is a finding itself, shown as `shown`, only when the rule ends before a command."""
    start = after_options(after, values) + WRAPPER_ARGUMENTS.get(program, 0)
    as_text = as_text or (program == "env" and {"-S", "--split-string"} & set(after[:start]))
    command = after[start:]
    if any("*" in word for word in after[:start]):
        return [("wrapper", shown)]  # a wildcard among the wrapper's own words can take in a whole command
    if not command:
        return [] if end == CLOSED else [("wrapper", shown)]
    if program in APPENDING:
        end = max(end, OPEN)
    if as_text:
        return text_findings(" ".join(spelled(command)), end, depth + 1, reading)
    return command_findings(command, end, depth + 1, reading)


def wrapper_findings(program, rest, end, depth, reading):
    """A wrapper runs the command spelled after its own options and arguments, so that command is
    classified; the wrapper is a finding itself only when the rule ends before a command is spelled."""
    if program == "command" and rest[:1] in (["-v"], ["-V"]):
        return []  # a lookup: it names the command and does not run it
    return wrapped(program, program, rest, WRAPPERS[program], program in TEXT_WRAPPERS, end, depth, reading)


def runner_findings(program, rest, end, depth, reading):
    """A package manager's runner form (`uv run`, `npm exec`) runs the command spelled after it,
    which is classified as behind a wrapper. No finding when the words are no runner form."""
    args, last = list(itertools.islice(positionals(rest, RUNNER_GLOBALS), 2)), len(rest) - 1
    if not args:  # only the program is named: every form of it is still open
        return [] if end == CLOSED else [("wrapper", program)]
    for form in RUNNER_FORMS[program]:
        parts = form.split()
        for at, part in enumerate(parts):
            if at == len(args):  # the form's next word is still to come
                return [] if end == CLOSED else [("wrapper", f"{program} {form}")]
            index, word = args[at]
            if not fits(word, part, end == INSIDE and index == last):
                break
            if "*" in word or (end == INSIDE and index == last):
                return [("wrapper", f"{program} {form}")]  # a word that may still become the form's
        else:
            after = rest[args[len(parts) - 1][0] + 1:]
            return wrapped(program, f"{program} {form}", after, RUNNER_VALUE_OPTIONS, False, end, depth, reading)
    return []


def interpreter_findings(program, rest, end):
    """An interpreter is a wrapper while the rule leaves open what it runs. A script, a module or
    code spelled in the rule is fixed; the audit does not read it."""
    if program == "pwsh":  # its options are spelled in any case
        rest = [word.lower() if word.startswith("-") else word for word in rest]
    values = INTERPRETERS[program]
    index = after_options(rest, values)
    if rest[index:index + 1] and rest[index] in SUBCOMMANDS.get(program, ()):
        index += 1 + after_options(rest[index + 1:], values)
    if any("*" in word for word in rest[:index]):
        return [("wrapper", program)]  # a wildcard where the options stand can become a code flag and its code
    if index >= len(rest) or rest[index] == "-":  # nothing is named, or the code comes from the input
        return [] if end == CLOSED else [("wrapper", program)]
    named, before = rest[index], rest[index - 1] if index else ""
    loose = "*" in named or (end == INSIDE and index == len(rest) - 1)
    # Unfinished code or an unfinished module name is open; a path that ends in a wildcard still names scripts.
    return [("wrapper", program)] if loose and (not named.strip("*") or INLINE.fullmatch(before)) else []


def git_findings(rest, end):
    """The branch-moving and sending git verbs a rule lets through."""
    verbs, last = list(itertools.islice(positionals(rest, GIT_VALUE_OPTIONS), 1)), len(rest) - 1
    if not verbs:
        return [] if end == CLOSED else [("exit", "git (any subcommand)")]
    index, verb = verbs[0]
    inside = end == INSIDE and index == last
    names = [name for name in GIT_EXITS if fits(verb, name, inside)]
    if len(names) == len(GIT_EXITS):
        return [("exit", "git (any subcommand)")]
    for first, second in GIT_PAIRS.items():  # `git lfs push`: the second word decides, or is still open
        if not fits(verb, first, inside):
            continue
        after = next(positionals(rest[index + 1:], ("-P", "--prefix")), None)
        if after is None:
            passes = end != CLOSED
        else:
            passes = fits(after[1], second, end == INSIDE and index + 1 + after[0] == last)
        if passes:
            names.append(f"{first} {second}")
    return [("exit", "git " + "/".join(sorted(names)))] if names else []


def forge_findings(program, rest, end):
    """A forge command is an exit unless one of its first two words is a read verb; `api` always is one."""
    args, last = list(itertools.islice(positionals(rest, FORGE_VALUE_OPTIONS), 2)), len(rest) - 1
    if not args:
        return [] if end == CLOSED else [("exit", f"{program} (any subcommand)")]
    if args[0][1] == "api":
        return [("exit", f"{program} api")]  # the endpoint is not shown: it may carry a token
    # A read verb is a whole word; an unfinished last word counts only when it already spells one.
    reads = [any(word.startswith(read) for read in FORGE_READS) if end == INSIDE and index == last else word in FORGE_READS
             for index, word in args]
    if any(reads):
        return []
    return [("exit", " ".join([program] + [word if word in FORGE_WORDS else "…" for _, word in args]))]


def publish_findings(program, rest, end):
    """The publish verb of a package or image program, also where the rule leaves the verb open."""
    groups, verb = PUBLISH_GROUPS.get(program, ()), PUBLISHES[program]
    spelt = next(((index, word) for index, word in positionals(rest, PUBLISH_VALUE_OPTIONS)
                  if not word.startswith("+") and word not in groups), None)
    if spelt is None:
        return [] if end == CLOSED else [("exit", f"{program} {verb}")]
    return [("exit", f"{program} {verb}")] if fits(spelt[1], verb, end == INSIDE and spelt[0] == len(rest) - 1) else []


def claude_rule_parts(rule):
    """(body, suffix) of a Bash permission rule: the command text and the trailing wildcard it was
    written with (`:*`, ` *`, `*` or none); None for a rule of another tool."""
    match = re.fullmatch(r"Bash(\((.*)\))?", rule, re.S)
    if not match:
        return None
    body = match.group(2) or ""
    for suffix in (":*", " *", "*"):
        if body.endswith(suffix):
            return body[:-len(suffix)], suffix
    return body, ""


def claude_rule_findings(rule):
    """[(status, what)] for one permissions.allow rule; empty when the rule is no finding.

    A rule without a wildcard is exact: it passes what it spells and nothing more. `:*` and ` *`
    let more words follow, and a `*` directly after text leaves the last word unfinished.
    """
    parts = claude_rule_parts(rule)
    if parts is None:
        return []
    if len(rule) > RULE_LIMIT:
        return [("unaudited", TOO_LONG)]
    body, suffix = parts
    if not body.strip():
        return [("wrapper", "")]  # bare Bash, Bash(), Bash(*): any command
    end = INSIDE if suffix == "*" and not body[-1].isspace() else OPEN if suffix else CLOSED
    return list(dict.fromkeys(text_findings(body, end, 0, Reading())))


def codex_allow_rules(text):
    """(line, pattern) of each prefix_rule call that allows, read from the syntax tree; nothing is executed.

    A rule without `decision` allows. The pattern is None where the call does not spell its decision
    and pattern as literals of the expected shape. Raises SyntaxError or ValueError for a file that
    cannot be parsed.
    """
    with warnings.catch_warnings():  # a rules file is not this program's code: its escapes are not ours to warn about
        warnings.simplefilter("ignore")
        tree = ast.parse(text)
    rules = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "prefix_rule"):
            continue
        given = {keyword.arg: keyword.value for keyword in node.keywords}
        try:
            decision = ast.literal_eval(given["decision"]) if "decision" in given else "allow"
            pattern = ast.literal_eval(given["pattern"]) if decision == "allow" else None
        except (KeyError, ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
            rules.append((node.lineno, None))
            continue
        if decision != "allow":
            continue
        shaped = isinstance(pattern, (list, tuple)) and pattern and all(
            isinstance(token, str) or (isinstance(token, (list, tuple)) and token
                                       and all(isinstance(choice, str) for choice in token))
            for token in pattern)
        rules.append((node.lineno, [token if isinstance(token, str) else list(token) for token in pattern] if shaped else None))
    return sorted(rules, key=lambda rule: rule[0])


def codex_pattern_findings(pattern):
    """[(status, what)] for one allowed pattern, every alternative expanded; None when the pattern
    has more alternatives than the audit expands. A prefix rule lets more words follow."""
    if len(pattern) > RULE_LIMIT:
        return [("unaudited", TOO_LONG)]
    choices = [[token] if isinstance(token, str) else token for token in pattern]
    total = 1
    for choice in choices:
        total *= len(choice)
        if total > PATTERN_LIMIT:
            return None
    # The same bound as for a Claude rule, on what is spelled and on what its alternatives expand to.
    if sum(len(word) + 1 for choice in choices for word in choice) > RULE_LIMIT or total * len(choices) > 4 * RULE_LIMIT:
        return [("unaudited", TOO_LONG)]
    found, reading = [], Reading()
    for argv in itertools.product(*choices):
        if argv[0] in SHELL_KEYWORDS or ASSIGNMENT.match(argv[0]):
            continue  # the words of a pattern are an argument list, not shell text: this one names a program
        # A token is literal: its `*` is no wildcard, so it must not be read as one.
        found += command_findings([word.replace("*", "\0") for word in argv], OPEN, 0, reading)
    return list(dict.fromkeys(found))


def own_words(what):
    """what when each of its words is one of this module's own (a list entry, a variable's name before
    `=…`, a fixed reason), else `…`: whatever a rule spells, a printed line never carries its text."""
    if what in REASONS:
        return what
    words = [word for word in re.split(r"[ /]", what) if word]
    return what if all(word in OWN_WORDS or VARIABLE.fullmatch(word) for word in words) else "…"


def finding_lines(kind, found):
    """(status, text) once per distinct finding of one rule. kind is the rule's kind (`Bash`,
    `prefix_rule`); the words in parentheses stand for the rule, whose text is not printed."""
    lines = []
    for status, what in dict.fromkeys(found):
        what = own_words(what)
        if status == "unaudited":
            lines.append((status, f"{'Bash rule' if kind == 'Bash' else kind} {what}; not audited"))
            continue
        label = what.replace(" (any subcommand)", "")
        label += "" if label.endswith("…") else " …"  # the rest of the rule is never printed
        says = f"passes {what} unasked" if status == "exit" else EVERY_PROGRAM if what.endswith("/*") else "wraps any command"
        lines.append((status, f"{kind}({label}) {says}" if what else f"{kind} {says}"))
    return lines


TOML_KEY = r"""(?:[A-Za-z0-9_-]+|"[^"]*"|'[^']*')"""
TOML_PATH = TOML_KEY + r"(?:\s*\.\s*" + TOML_KEY + r")*"
TOML_HEADER = re.compile(r"(\[\[?)\s*(" + TOML_PATH + r")\s*\]\]?\s*(?:#.*)?")
TOML_PAIR = re.compile(r"(" + TOML_PATH + r")\s*=\s*(.*)")


def toml_path(text):
    """A dotted TOML key as one string, without quotes or the spaces around the dots."""
    return ".".join(part.strip("\"'") for part in re.findall(TOML_KEY, text))


def toml_brackets(line):
    """How many more brackets and braces a line opens than it closes, outside strings and comments."""
    depth, quote, escaped = 0, None, False
    for ch in line:
        if escaped:
            escaped = False
        elif quote:
            if ch == "\\" and quote == '"':
                escaped = True
            elif ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "#":
            break
        elif ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
    return depth


def toml_scalar(text):
    """A one-line TOML string, integer or boolean, with any comment after it; None for anything else."""
    match = re.fullmatch(r'("(?:[^"\\]|\\.)*")\s*(?:#.*)?', text)
    if match:
        try:
            return json.loads(match.group(1), strict=False)
        except ValueError:
            return None
    match = re.fullmatch(r"'([^']*)'\s*(?:#.*)?", text)
    if match:
        return match.group(1)
    match = re.fullmatch(r"(true|false|[+-]?[0-9][0-9_]*)\s*(?:#.*)?", text)
    if not match:
        return None
    word = match.group(1)
    try:
        return word == "true" if word in ("true", "false") else int(word.replace("_", ""))
    except ValueError:  # Python refuses to convert an integer of thousands of digits
        return None


def toml_inline(text):
    """(key, value) of the one-line scalars in an inline table `{ a = 1, b = "x" }`; an array or a
    table nested in it is skipped."""
    parts, start, depth, quote, escaped = [], 1, 0, None, False
    for at, ch in enumerate(text[1:], 1):
        if escaped:
            escaped = False
        elif quote:
            if ch == "\\" and quote == '"':
                escaped = True
            elif ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch in "[{":
            depth += 1
        elif ch in "]}" and depth:
            depth -= 1
        elif ch in ",}":
            parts.append(text[start:at])
            start = at + 1
            if ch == "}":
                break
    pairs = []
    for part in parts:
        pair = TOML_PAIR.fullmatch(part.strip())
        value = toml_scalar(pair.group(2)) if pair else None
        if value is not None:
            pairs.append((toml_path(pair.group(1)), value))
    return pairs


def toml_scalars(text):
    """{dotted key: value} of the one-line scalars in a TOML text, the table's name leading the key.

    A line scanner, not a TOML parser, so it reads the same on every Python version (tomllib exists
    only from 3.11): it follows `[table]` headers, skips comments, triple-quoted spans and arrays or
    inline tables that run over several lines, and takes a value only when it is a string, an
    integer or a boolean on the key's own line or in an inline table that closes on that line
    (`agents = { limit = 5 }` reads like `[agents]` and `limit = 5`). The first value of a key wins.
    """
    values, table, closing, depth = {}, "", None, 0
    for raw in text.splitlines():
        line = raw.strip()
        if closing:
            closing = None if closing in line else closing
            continue
        if depth > 0:
            depth += toml_brackets(line)
            continue
        header = TOML_HEADER.fullmatch(line)
        if header:
            table = toml_path(header.group(2)) + ("[]" if header.group(1) == "[[" else "")
            continue
        pair = TOML_PAIR.fullmatch(line)
        if not pair:
            continue
        key, rest = toml_path(pair.group(1)), pair.group(2)
        if rest[:3] in ('"""', "'''"):
            closing = None if rest[:3] in rest[3:] else rest[:3]
        elif rest[:1] in ("[", "{"):
            depth = toml_brackets(rest)
            if rest[0] == "{" and not depth:
                for name, value in toml_inline(rest):
                    values.setdefault(".".join(part for part in (table, key, name) if part), value)
        else:
            value = toml_scalar(rest)
            if value is not None:
                values.setdefault(f"{table}.{key}" if table else key, value)
    return values


def audit_claude(path, note, report):
    """Findings in permissions.allow of the Claude Code user settings (ask and deny are never read).
    A rule is named by its place in the list; and one line of information when the default mode
    asks before no command."""
    settings, problem = user_settings(path)
    if problem:
        note("unaudited", f"{pretty(path)}: {problem.split(' (')[0]}; permissions.allow not audited")
        return
    permissions = section(settings, "permissions")
    for index, rule in enumerate(section(permissions, "allow", list)):
        for status, text in finding_lines("Bash", claude_rule_findings(rule) if isinstance(rule, str) else []):
            note(status, f"{pretty(path)}: permissions.allow[{index}] {text}")
    if permissions.get("defaultMode") == "bypassPermissions":
        report.info(f'{pretty(path)}: permissions.defaultMode "bypassPermissions": '
                    "Claude Code asks before no command (information only)")


def audit_codex(base, note, report):
    """Findings in the allowing prefix_rule calls of every Codex rules file, each named by its file
    and line, and one line of information when config.toml never asks and sandboxes nothing."""
    rules_dir = base / "rules"
    try:
        names = sorted(name for name in os.listdir(rules_dir) if name.endswith(".rules"))
    except (FileNotFoundError, NotADirectoryError):
        names = []
    except OSError:
        names = []
        note("unaudited", f"{pretty(rules_dir)}: cannot be listed; its rules are not audited")
    for path in [rules_dir / name for name in names]:
        if os.path.isdir(path):
            continue
        try:
            rules = codex_allow_rules(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, SyntaxError, MemoryError, RecursionError):
            note("unaudited", f"{pretty(path)}: cannot be read as prefix_rule calls; not audited")
            continue
        for line, pattern in rules:
            where = f"{pretty(path)}:{line}:"
            if pattern is None:
                note("unaudited", f"{where} prefix_rule whose decision or pattern is not a plain literal; not audited")
                continue
            found = codex_pattern_findings(pattern)
            if found is None:
                note("unaudited", f"{where} prefix_rule with more than {PATTERN_LIMIT} alternatives; not audited")
                continue
            for status, text in finding_lines("prefix_rule", found):
                note(status, f"{where} {text}")
    config = base / "config.toml"
    values = toml_scalars(read_text(config))
    if values.get("approval_policy") == "never" and values.get("sandbox_mode") == "danger-full-access":
        report.info(f'{pretty(config)}: approval_policy "never" with sandbox_mode "danger-full-access": '
                    "Codex asks before no command and sandboxes none (information only)")


def doctor_exit_audit(keys, report, strict=False):
    """Name the user-level settings that let an exit through unasked or wrap any command.

    The findings carry their own status words and stay out of the OK and not OK counts, and what
    could not be read is information. With strict each finding counts as not OK, and so does each
    rule or file the audit could not read: strict must not pass what it has not seen. The two
    lines about a mode that asks before nothing stay information: the user chose that environment.
    Returns the counts per status.
    """
    counts = {"exit": 0, "wrapper": 0, "unaudited": 0}

    def note(status, text):
        counts[status] += 1
        if status == "unaudited":
            (report.fail if strict else report.info)(text)
            return
        report.bad += strict
        report.line(status, text)

    print("== exit audit")
    if "claude" in keys:
        audit_claude(home() / RUNTIMES["claude"]["home"] / RUNTIMES["claude"]["settings"], note, report)
    if "codex" in keys:
        audit_codex(home() / RUNTIMES["codex"]["home"], note, report)
    unread = f", {counts['unaudited']} not audited" if counts["unaudited"] else ""
    report.info(f"exit audit: {counts['exit']} exit, {counts['wrapper']} wrapper{unread} in user settings "
                f"({'counted' if strict else 'not counted'})")
    return counts


def doctor_grant_store(report):
    """The durable grant store must be a directory only its owner can enter; the gate creates it lazily."""
    store = grant_store()
    name = f"grant store {pretty(store)}"
    try:
        state = os.lstat(store)
    except FileNotFoundError:
        report.info(f"{name} absent (the gate creates it when it first records a grant)")
        return
    except OSError as error:  # for instance below a directory nobody may search: the gate cannot reach it either
        report.fail(f"{name} cannot be examined ({error.strerror or type(error).__name__})")
        return
    mode = stat.S_IMODE(state.st_mode)
    if stat.S_ISLNK(state.st_mode):
        report.fail(f"{name} is a symlink (expected a directory only its owner can enter)")
    elif not stat.S_ISDIR(state.st_mode):
        report.fail(f"{name} is not a directory")
    elif hasattr(os, "getuid") and state.st_uid != os.getuid():
        report.fail(f"{name} belongs to another user")
    elif mode & 0o077:
        report.fail(f"{name} is open to group or others (mode {mode:04o}; expected 0700)")
    else:
        report.good(f"{name} (only its owner can enter)")


# One shard of the gate's suite: load tools/test_ddl_gate.py from its installed path, run every N-th test of the
# sorted test IDs (round robin, so the shards are even), and print one tally line: the tests run and any that failed.
SHARD_TALLY = "DDL-GATE-SHARD"
GATE_SHARD = r"""
import importlib.util, os, sys, unittest
path, index, count = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
sys.path.insert(0, os.path.dirname(path))
spec = importlib.util.spec_from_file_location("test_ddl_gate", path)
module = importlib.util.module_from_spec(spec)
sys.modules["test_ddl_gate"] = module
spec.loader.exec_module(module)


def flat(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from flat(test)
        else:
            yield test


tests = sorted(flat(unittest.defaultTestLoader.loadTestsFromModule(module)), key=lambda test: test.id())
mine = unittest.TestSuite(test for number, test in enumerate(tests) if number % count == index)
with open(os.devnull, "w") as quiet:
    result = unittest.TextTestRunner(stream=quiet, verbosity=0).run(mine)
bad = [test.id() for test, _ in result.failures + result.errors] + [test.id() for test in result.unexpectedSuccesses]
print(" ".join([TALLY, "ran", str(result.testsRun)] + bad), flush=True)
sys.exit(0 if result.wasSuccessful() else 1)
""".replace("TALLY", repr(SHARD_TALLY))


def gate_suite():
    """Run the gate's own tests: (passed, the text doctor prints after the file name: `OK`, or `FAILED:` and the
    failing test IDs). The suite runs in min(CPU count, 8) processes, each loading the installed
    tools/test_ddl_gate.py and running every N-th of its sorted test IDs, each with a disposable grant store of its
    own, so no test of the gate can write into the durable one. A shard that crashes or prints no tally is not OK."""
    count = min(os.cpu_count() or 2, 8)
    path = str(ROOT / "tools/test_ddl_gate.py")
    failing, crashed = [], 0
    with tempfile.TemporaryDirectory(prefix="ddl-doctor-grants-") as tmp:
        shards = []
        for index in range(count):
            store = os.path.join(tmp, f"grants-{index}")
            os.mkdir(store)
            out = open(os.path.join(tmp, f"shard-{index}.out"), "w+", encoding="utf-8")  # a file: no pipe fills up
            shards.append((out, subprocess.Popen([sys.executable, "-I", "-c", GATE_SHARD, path, str(index), str(count)],
                                                 stdout=out, stderr=subprocess.STDOUT, text=True, cwd=ROOT,
                                                 env=dict(os.environ, DDL_GATE_GRANT_DIR=store))))
        for out, proc in shards:
            code = proc.wait()
            out.seek(0)
            tallies = [line.split() for line in out.read().splitlines() if line.startswith(SHARD_TALLY + " ran ")]
            out.close()
            if not tallies:
                crashed += 1
                continue
            failing += tallies[-1][3:]
            crashed += code != 0 and not tallies[-1][3:]
    if not failing and not crashed:
        return True, "OK"
    parts = failing + ([f"{crashed} shard(s) crashed"] if crashed else [])
    return False, "FAILED: " + ", ".join(parts)


def cmd_doctor(args, report):
    keys = selected_runtimes(args)
    for key in keys:
        rt = RUNTIMES[key]
        base = home() / rt["home"]
        print(f"== {rt['label']} ({pretty(base)})")
        for rel, src in rt["links"].items():
            link = base / rel
            source = ROOT / src
            if os.path.islink(link) and same_file(link, source) and source.exists():
                report.good(f"{pretty(link)} -> {src}")
            elif os.path.islink(link):
                report.fail(f"{pretty(link)} -> {os.readlink(link)} (expected {source})")
            elif os.path.exists(link):
                report.fail(f"{pretty(link)} is not a symlink")
            else:
                report.fail(f"{pretty(link)} missing")
        doctor_retired(rt, base, report)
        settings_path = base / rt["settings"]
        fragment = fragment_for(rt)
        settings, problem = user_settings(settings_path)
        problem = problem or misplaced(settings, fragment)
        if problem:  # one line names the file and what is wrong with it; the other checks go on
            report.fail(f"{pretty(settings_path)} is {problem}")
            continue
        present, missing, differing = merged_state(settings, fragment)
        for p in present:
            report.good(f"{pretty(settings_path)}: {p}")
        for m in missing:
            report.fail(f"{pretty(settings_path)}: {m} missing (run install)")
        for d in differing:
            report.info(f"{pretty(settings_path)}: {d} has another value (kept; DDL's is not applied)")
        doctor_git_hooks(key, base, settings, report)
        if key == "codex":
            config = base / "config.toml"
            if "agents.max_concurrent_threads_per_session" not in toml_scalars(read_text(config)):
                report.info(f"{pretty(config)} does not set [agents] max_concurrent_threads_per_session (optional; SWARM uses max: 5)")
    print("== gate")
    status = subprocess.run([sys.executable, "-I", str(ROOT / "tools/ddl_gate.py"), "status", "--cwd", os.getcwd()],
                            capture_output=True, text=True)
    # One line per check: a status that prints several lines (it adds grant lines when a grant exists) keeps the column.
    for line in status.stdout.strip().splitlines() or [f"DDL project: unknown ({status.stderr.strip() or status.returncode})"]:
        report.info(line)
    doctor_grant_store(report)
    passed, last = gate_suite()
    (report.good if passed else report.fail)(f"python3 tools/test_ddl_gate.py: {last}")
    doctor_exit_audit(keys, report, strict=args.strict)
    print(f"{report.ok} OK, {report.bad} not OK")
    return 1 if report.bad else 0


def cmd_uninstall(args, report):
    refused = 0  # settings files whose fragment could not be removed
    for key in selected_runtimes(args):
        rt = RUNTIMES[key]
        base = home() / rt["home"]
        print(f"== {rt['label']} ({pretty(base)})")
        for rel, src in rt["links"].items():
            link = base / rel
            if os.path.islink(link) and points_at_ddl(link, src):
                if not report.dry_run:
                    link.unlink()
                report.good(f"unlink {pretty(link)}")
            elif os.path.lexists(link):
                report.info(f"{pretty(link)} is not DDL's; left in place")
        for link in retired_links(base, rt):  # an install from before its retirement left it
            if not report.dry_run:
                link.unlink()
            report.good(f"unlink {pretty(link)}")
        for rel in ("skills", "agents", "hooks", "rules"):
            if is_empty_directory(base / rel) and not report.dry_run:
                (base / rel).rmdir()
        settings_path = base / rt["settings"]
        settings, problem = user_settings(settings_path)
        if problem:  # what cannot be read as an object is not rewritten: nothing in it is known to be DDL's
            report.fail(f"{pretty(settings_path)} is {problem}; fragment not removed")
            refused += 1
            continue
        if not settings:
            continue
        cleaned = unmerge(settings, fragment_for(rt))
        if cleaned == settings:
            report.good(f"{pretty(settings_path)} (no DDL entries)")
        elif not cleaned:
            if not report.dry_run:
                settings_path.unlink()
            report.good(f"remove {pretty(settings_path)} (only DDL entries were in it)")
        else:
            write_json(settings_path, cleaned, report, backup=False)
            report.good(f"unmerge {pretty(settings_path)}")
    uninstall_grant_store(report)
    return 1 if refused else 0


def uninstall_grant_store(report):
    """The grant store holds the record of what the human approved: it is left in place and named
    when it holds anything; only an empty directory is removed."""
    store = grant_store()
    if os.path.islink(store) or not os.path.isdir(store):
        if os.path.lexists(store):
            report.info(f"grant store {pretty(store)} is not a plain directory; left in place")
        return
    if not is_empty_directory(store):
        report.info(f"grant store {pretty(store)} left in place (the grants recorded there are not removed; delete it by hand)")
        return
    if not report.dry_run:
        store.rmdir()
    report.good(f"remove {pretty(store)} (empty grant store)")


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["install", "doctor", "uninstall"])
    parser.add_argument("--claude", action="store_true", help="only Claude Code (~/.claude)")
    parser.add_argument("--codex", action="store_true", help="only Codex (~/.codex)")
    parser.add_argument("--project", metavar="DIR", help="install: copy the per-project layout into DIR instead")
    parser.add_argument("--dry-run", action="store_true", help="print the actions without performing them")
    parser.add_argument("--strict", action="store_true",
                        help="doctor: count each finding of the exit audit, and each rule it could not read, as not OK")
    if hasattr(sys.stdout, "reconfigure"):  # a terminal that cannot show `…` gets `?` in its place, not a traceback
        sys.stdout.reconfigure(errors="replace")
    args = parser.parse_args(argv)
    if args.project and args.command != "install":
        parser.error("--project applies to install only")
    if args.strict and args.command != "doctor":
        parser.error("--strict applies to doctor only")
    report = Report(dry_run=args.dry_run)
    if args.dry_run:
        print("(dry run: nothing is written)")
    try:
        if args.command in ("install", "doctor"):
            ensure_dist(report)
        return {"install": cmd_install, "doctor": cmd_doctor, "uninstall": cmd_uninstall}[args.command](args, report)
    except OSError as error:  # a file or directory that may not be read or changed: name it, without a traceback
        where = f"{pretty(error.filename)}: " if isinstance(error.filename, str) else ""
        report.fail(f"{where}{error.strerror or type(error).__name__} ({args.command} stopped here)")
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
