#!/usr/bin/env python3
"""Install, check, or remove DDL at the user level (bin/install.sh, bin/doctor.sh, bin/uninstall.sh).

DDL is installed into the environment, not into each project: the skills, the agent definitions,
the gate hook, and the rules file are symlinked from this checkout into `$HOME/.claude/` and
`$HOME/.codex/`, and the adapter's settings fragment is merged into `$HOME/.claude/settings.json`
and `$HOME/.codex/hooks.json`. A project then needs only `design.md` and a short instruction file
(`claude-code/CLAUDE.md` as `.claude/CLAUDE.md`, `codex/AGENTS.md` as `AGENTS.md`).

  install    create or repoint the symlinks and merge the fragment (idempotent; existing settings
             are kept, DDL's own entries are replaced so a path change takes effect)
  doctor     check every link and merged entry, run the gate's tests, and check the Codex rule;
             prints `N OK, M not OK` and exits 1 when M > 0
  uninstall  remove the links that point at DDL and the merged entries (an entry is removed only
             when its value is the one DDL wrote)

Runtimes: `--claude` and `--codex` select one; by default each runtime whose home directory exists
(`$HOME/.claude`, `$HOME/.codex`) is handled. `install --project DIR` copies the per-project layout
instead (`claude-code/` into `DIR/.claude/`, `codex/` into `DIR/`; an existing instruction file is
kept). `--dry-run` prints the actions without performing them. `$HOME` is honoured, so a temporary
home can be used for a rehearsal.

What the merge does (Claude Code `settings.json`): `hooks.<event>` gets the fragment's groups
appended after any group that already carries a DDL command (one whose `command` contains
`ddl_gate.py`) has been removed; `env`, `permissions.ask`, and `attribution` get the fragment's
values when the key is absent (a different existing value is kept and reported by `doctor`).
Codex `hooks.json` gets the same `hooks` treatment. The hook commands are rewritten for the user
level: `$CLAUDE_PROJECT_DIR/.claude/hooks/ddl_gate.py` becomes `$HOME/.claude/hooks/ddl_gate.py`,
and the Codex `git rev-parse` form becomes `$HOME/.codex/hooks/ddl_gate.py`. The first time a file
is changed, a copy is kept next to it as `<name>.ddl-backup`.

Standard library only; python3 is the same dependency the gate hook has.
"""
import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKILLS = ["ddl-protocol", "draft", "realize", "reflect", "validate", "commit", "docs", "refactoring", "resonate"]
GATE_MARK = "ddl_gate.py"

RUNTIMES = {
    "claude": {
        "home": ".claude",
        "label": "Claude Code",
        "links": {**{f"skills/{n}": f"claude-code/skills/{n}" for n in SKILLS},
                  "agents/explorer.md": "claude-code/agents/explorer.md",
                  "agents/worker.md": "claude-code/agents/worker.md",
                  "hooks/ddl_gate.py": "claude-code/hooks/ddl_gate.py"},
        "settings": "settings.json",
        "fragment": "claude-code/settings.json",
        "rewrite": ('"$CLAUDE_PROJECT_DIR"/.claude/hooks/ddl_gate.py', '"$HOME"/.claude/hooks/ddl_gate.py'),
        "project_src": "claude-code",
        "project_dst": ".claude",
        "instruction": "CLAUDE.md",
    },
    "codex": {
        "home": ".codex",
        "label": "Codex",
        "links": {**{f"skills/{n}": f"codex/.agents/skills/{n}" for n in SKILLS},
                  "agents/explorer.toml": "codex/.codex/agents/explorer.toml",
                  "agents/worker.toml": "codex/.codex/agents/worker.toml",
                  "hooks/ddl_gate.py": "codex/.codex/hooks/ddl_gate.py",
                  "rules/ddl.rules": "codex/.codex/rules/ddl.rules"},
        "settings": "hooks.json",
        "fragment": "codex/.codex/hooks.json",
        "rewrite": ('"$(git rev-parse --show-toplevel 2>/dev/null || pwd)/.codex/hooks/ddl_gate.py"',
                    '"$HOME/.codex/hooks/ddl_gate.py"'),
        "project_src": "codex",
        "project_dst": ".",
        "instruction": "AGENTS.md",
    },
}


class Report:
    def __init__(self, dry_run=False):
        self.ok = 0
        self.bad = 0
        self.dry_run = dry_run

    def line(self, status, text):
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
    text = path.read_text()
    if not text.strip():
        return {}
    return json.loads(text)


def fragment_for(rt):
    """The adapter's settings with the hook commands rewritten for the user level."""
    data = load_json(ROOT / rt["fragment"])
    old, new = rt["rewrite"]
    for groups in data.get("hooks", {}).values():
        for group in groups:
            for hook in group.get("hooks", []):
                hook["command"] = hook["command"].replace(old, new)
    data.pop("$comment", None)
    data.pop("description", None)
    return data


def is_ddl_group(group):
    return any(GATE_MARK in (h.get("command") or "") for h in group.get("hooks", []))


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
    out = json.loads(json.dumps(settings))
    hooks = out.get("hooks", {})
    for event in list(hooks):
        hooks[event] = [g for g in hooks[event] if not is_ddl_group(g)]
        if not hooks[event]:
            del hooks[event]
    if "hooks" in out and not out["hooks"]:
        del out["hooks"]
    for key, value in frag.get("env", {}).items():
        if out.get("env", {}).get(key) == value:
            del out["env"][key]
    if "env" in out and not out["env"]:
        del out["env"]
    for rule in frag.get("permissions", {}).get("ask", []):
        ask = out.get("permissions", {}).get("ask", [])
        if rule in ask:
            ask.remove(rule)
    if "permissions" in out and out["permissions"].get("ask") == []:
        del out["permissions"]["ask"]
        if not out["permissions"]:
            del out["permissions"]
    for key, value in frag.get("attribution", {}).items():
        if out.get("attribution", {}).get(key) == value:
            del out["attribution"][key]
    if "attribution" in out and not out["attribution"]:
        del out["attribution"]
    return out


def merged_state(settings, frag):
    """(present, missing, differing) entries of the fragment inside settings, for doctor."""
    present, missing, differing = [], [], []
    for event, groups in frag.get("hooks", {}).items():
        have = [g for g in settings.get("hooks", {}).get(event, []) if is_ddl_group(g)]
        for g in groups:
            words = g["hooks"][0]["command"].split()
            what = words[2] if len(words) > 2 else words[-1]
            (present if g in have else missing).append(f"hooks.{event} ({what})")
    for key, value in frag.get("env", {}).items():
        got = settings.get("env", {}).get(key)
        (present if got == value else differing if got is not None else missing).append(f"env.{key}")
    for rule in frag.get("permissions", {}).get("ask", []):
        (present if rule in settings.get("permissions", {}).get("ask", []) else missing).append(f"permissions.ask {rule}")
    for key, value in frag.get("attribution", {}).items():
        got = settings.get("attribution", {}).get(key)
        (present if got == value else differing if got is not None else missing).append(f"attribution.{key}")
    return present, missing, differing


def write_json(path, data, report):
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    if path.exists() and path.read_text() == text:
        return False
    if report.dry_run:
        return True
    if path.exists():
        backup = path.with_name(path.name + ".ddl-backup")
        if not backup.exists():
            shutil.copy2(path, backup)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return True


def points_at_ddl(link, rel_source):
    """True when the symlink's target ends with the DDL-relative source path (any DDL checkout)."""
    try:
        target = os.readlink(link)
    except OSError:
        return False
    return target.rstrip("/").endswith(rel_source)


def selected_runtimes(args):
    chosen = [k for k in RUNTIMES if getattr(args, k)]
    if chosen:
        return chosen
    found = [k for k, rt in RUNTIMES.items() if (home() / rt["home"]).is_dir()]
    if not found:
        raise SystemExit("neither ~/.claude nor ~/.codex exists; pass --claude or --codex to create one")
    return found


def cmd_install(args, report):
    if args.project:
        return install_project(args, report)
    keys = selected_runtimes(args)
    for key in keys:
        rt = RUNTIMES[key]
        base = home() / rt["home"]
        print(f"== {rt['label']} ({pretty(base)})")
        for rel, src in rt["links"].items():
            source = ROOT / src
            link = base / rel
            if not source.exists():
                report.fail(f"{src} missing in {ROOT} (run tools/sync_mirrors.py?)")
                continue
            if link.is_symlink():
                if link.resolve() == source.resolve():
                    report.good(f"link {pretty(link)} (unchanged)")
                    continue
                old = os.readlink(link)
                if not report.dry_run:
                    link.unlink()
                    link.symlink_to(source)
                report.good(f"link {pretty(link)} -> {source} (was {old})")
            elif link.exists():
                report.fail(f"{pretty(link)} exists and is not a symlink; move it away and run install again")
            else:
                if not report.dry_run:
                    link.parent.mkdir(parents=True, exist_ok=True)
                    link.symlink_to(source)
                report.good(f"link {pretty(link)} -> {source}")
        settings_path = base / rt["settings"]
        try:
            settings = load_json(settings_path)
        except json.JSONDecodeError as e:
            report.fail(f"{pretty(settings_path)} is not valid JSON ({e}); fragment not merged")
            continue
        merged, notes = merge(settings, fragment_for(rt))
        changed = write_json(settings_path, merged, report)
        report.good(f"merge {pretty(settings_path)} ({'updated' if changed else 'unchanged'})")
        for n in notes:
            report.info(n)
    if "codex" in keys:
        report.info("Codex: if Codex asks about new hooks, run /hooks once to trust them; "
                    "set [agents] max_concurrent_threads_per_session = 5 in ~/.codex/config.toml to match SWARM max: 5")
    return 0


def install_project(args, report):
    dest = pathlib.Path(args.project).resolve()
    if not dest.is_dir():
        raise SystemExit(f"{dest}: not a directory")
    for key in [k for k in RUNTIMES if getattr(args, k)] or list(RUNTIMES):
        rt = RUNTIMES[key]
        src = ROOT / rt["project_src"]
        target = (dest / rt["project_dst"]).resolve()
        print(f"== {rt['label']} -> {target}")
        for path in sorted(p for p in src.rglob("*") if p.is_file() and p.name != "README.md"):
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
    report.info("project copy done: the hook commands use $CLAUDE_PROJECT_DIR / the repository root; "
                "trust the folder (Claude Code) or the project and its hooks (Codex)")
    return 0


def cmd_doctor(args, report):
    for key in selected_runtimes(args):
        rt = RUNTIMES[key]
        base = home() / rt["home"]
        print(f"== {rt['label']} ({pretty(base)})")
        for rel, src in rt["links"].items():
            link = base / rel
            source = ROOT / src
            if link.is_symlink() and link.resolve() == source.resolve() and source.exists():
                report.good(f"{pretty(link)} -> {src}")
            elif link.is_symlink():
                report.fail(f"{pretty(link)} -> {os.readlink(link)} (expected {source})")
            elif link.exists():
                report.fail(f"{pretty(link)} is not a symlink")
            else:
                report.fail(f"{pretty(link)} missing")
        settings_path = base / rt["settings"]
        try:
            settings = load_json(settings_path)
        except json.JSONDecodeError as e:
            report.fail(f"{pretty(settings_path)} is not valid JSON ({e})")
            continue
        present, missing, differing = merged_state(settings, fragment_for(rt))
        for p in present:
            report.good(f"{pretty(settings_path)}: {p}")
        for m in missing:
            report.fail(f"{pretty(settings_path)}: {m} missing (run install)")
        for d in differing:
            report.info(f"{pretty(settings_path)}: {d} has another value (kept; DDL's is not applied)")
        if key == "codex":
            rules = base / "rules/ddl.rules"
            if shutil.which("codex") and rules.exists():
                try:
                    out = subprocess.run(["codex", "execpolicy", "check", "--rules", str(rules), "git", "push"],
                                         capture_output=True, text=True, timeout=30)
                    decision = json.loads(out.stdout or "{}").get("decision") if out.returncode == 0 else None
                except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
                    decision = None
                (report.good if decision == "prompt" else report.fail)(
                    f"codex execpolicy check: git push -> {decision or 'no decision'} (expected prompt)")
            else:
                report.info("codex not on PATH; the rule file was not checked")
            config = base / "config.toml"
            if not (config.exists() and "max_concurrent_threads_per_session" in config.read_text()):
                report.info(f"{pretty(config)} does not set [agents] max_concurrent_threads_per_session (optional; SWARM uses max: 5)")
    print("== gate")
    test = ROOT / "tools/test_ddl_gate.py"
    out = subprocess.run([sys.executable, "-I", str(test)], capture_output=True, text=True, cwd=ROOT)
    last = (out.stderr.strip().splitlines() or ["(no output)"])[-1]
    (report.good if out.returncode == 0 and last == "OK" else report.fail)(f"python3 tools/test_ddl_gate.py: {last}")
    print(f"{report.ok} OK, {report.bad} not OK")
    return 1 if report.bad else 0


def cmd_uninstall(args, report):
    for key in selected_runtimes(args):
        rt = RUNTIMES[key]
        base = home() / rt["home"]
        print(f"== {rt['label']} ({pretty(base)})")
        for rel, src in rt["links"].items():
            link = base / rel
            if link.is_symlink() and points_at_ddl(link, src):
                if not report.dry_run:
                    link.unlink()
                report.good(f"unlink {pretty(link)}")
            elif link.is_symlink() or link.exists():
                report.info(f"{pretty(link)} is not DDL's; left in place")
        for rel in ("skills", "agents", "hooks", "rules"):
            d = base / rel
            if d.is_dir() and not any(d.iterdir()) and not report.dry_run:
                d.rmdir()
        settings_path = base / rt["settings"]
        try:
            settings = load_json(settings_path)
        except json.JSONDecodeError as e:
            report.fail(f"{pretty(settings_path)} is not valid JSON ({e}); fragment not removed")
            continue
        if not settings:
            continue
        cleaned = unmerge(settings, fragment_for(rt))
        if cleaned == settings:
            report.good(f"{pretty(settings_path)} (no DDL entries)")
        elif not cleaned and key == "codex":
            if not report.dry_run:
                settings_path.unlink()
            report.good(f"remove {pretty(settings_path)} (only DDL entries were in it)")
        else:
            write_json(settings_path, cleaned, report)
            report.good(f"unmerge {pretty(settings_path)}")
    return 0


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["install", "doctor", "uninstall"])
    parser.add_argument("--claude", action="store_true", help="only Claude Code (~/.claude)")
    parser.add_argument("--codex", action="store_true", help="only Codex (~/.codex)")
    parser.add_argument("--project", metavar="DIR", help="install: copy the per-project layout into DIR instead")
    parser.add_argument("--dry-run", action="store_true", help="print the actions without performing them")
    args = parser.parse_args(argv)
    if args.project and args.command != "install":
        parser.error("--project applies to install only")
    report = Report(dry_run=args.dry_run)
    if args.dry_run:
        print("(dry run: nothing is written)")
    return {"install": cmd_install, "doctor": cmd_doctor, "uninstall": cmd_uninstall}[args.command](args, report)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
