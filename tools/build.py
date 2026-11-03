#!/usr/bin/env python3
"""Build the deployable layouts under dist/ from the sources.

Sources (hand-maintained, tracked):
  skills/<name>/SKILL.md            the eight commands, in the Claude Code skill form (the union of the frontmatter
                                    fields, `/name` for a command)
  protocol/SKILL.md                 the protocol entry; `{host}` and `{Host}` are placeholders for the host name
  protocol/<operation>.md           the six operations beside the entry, with the same placeholders
  hosts/<host>/<implementation>.md  the four protocol implementations of a host: start, approval, parallel-work,
                                    git-review
  hosts/<host>/guidance.md          the host's instruction-file template
  hosts/<host>/**                   every other file is an adapter file of that host (settings, agents, hooks, rules);
                                    README.md documents the host and is not deployed
  tools/ddl_gate.py                 the gate

Generated (dist/, untracked; `python3 tools/build.py`):
  dist/claude/.claude/CLAUDE.md                                hosts/claude/guidance.md
  dist/claude/.claude/<adapter path>                           hosts/claude/<adapter path>, byte for byte
  dist/claude/.claude/hooks/ddl_gate.py                        tools/ddl_gate.py
  dist/claude/.claude/skills/<name>/SKILL.md                   skills/<name>/SKILL.md, byte for byte
  dist/claude/.claude/skills/ddl-protocol/SKILL.md             protocol/SKILL.md with hosts/claude/start.md folded in
                                                               as its `## Host` section, {host} = claude, {Host} = Claude
  dist/claude/.claude/skills/ddl-protocol/<operation>.md       protocol/<operation>.md, rendered the same way; approval,
                                                               parallel-work and git-review carry hosts/claude/<operation>.md
                                                               folded into their `## Implementation`
  dist/codex/AGENTS.md                                         hosts/codex/guidance.md
  dist/codex/.codex/<adapter path>                             hosts/codex/<adapter path>, byte for byte
  dist/codex/.codex/hooks/ddl_gate.py                          tools/ddl_gate.py
  dist/codex/.agents/skills/<name>/SKILL.md                    skills/<name>/SKILL.md in the Codex form
  dist/codex/.agents/skills/<name>/agents/openai.yaml          no implicit invocation
  dist/codex/.agents/skills/ddl-protocol/SKILL.md              protocol/SKILL.md folded and rendered for codex / Codex,
                                                               in the Codex form, plus agents/openai.yaml
  dist/codex/.agents/skills/ddl-protocol/<operation>.md        protocol/<operation>.md, folded and rendered the same way

One file per action: an installed protocol has no hosts/ directory. The fold (fold()) drops an implementation's
H1 and `## Read when`, demotes `## Mapping`, `## Observed` and `## Coverage` to H3 and appends them under the
operation's `## Implementation` (its last section) or, for the entry, under a new `## Host` section after
`## Interruption`. The links to hosts/{host}/<implementation>.md are then pointed at the folded sections
(relink()): `#host` or `SKILL.md#host` for start, `#implementation` in the operation that folds the
implementation and `<operation>.md#implementation` elsewhere. The order is fold, relink, render, and for Codex
to_codex.

Rules:
  - The Codex form of a command SKILL.md keeps name, description, and metadata.short-description from the
    source frontmatter and drops argument-hint and disable-model-invocation, which Codex does not know
    (agents/openai.yaml replaces the latter). Its body is the source body with slash commands turned into
    skills: `/draft` -> `$draft` for the eight command names, not inside paths or words (the SLASH regex);
    the Notebook Formats literals in PROTECTED keep their "/". Phase 0 stays as written.
  - The Codex form of the protocol entry keeps name and description (and metadata.short-description when
    the source has one); its body is only rendered, not even `/cmd` -> `$cmd`. The operations have no
    frontmatter and are only rendered.
  - Rendering replaces the literal `{host}` with the host name and `{Host}` with its capitalised form;
    no other brace is touched. A host's deployed protocol holds only that host's four implementations,
    folded in; the link rewriting replaces exact tokens and never formats the text.
  - agents/openai.yaml is the same fixed text for every command skill, with the skill's name; the protocol
    gets a comment saying it is read in Phase 0 and never invoked.
  - Symlinks are refused, in the sources and in the generated paths (not followed, not removed).

Errors (exit 1 with a message): a required source is missing (a command, the entry, an operation, an
implementation, guidance.md, or the gate); a skill has no frontmatter, a frontmatter name different from its
directory name, or no description; a command has no metadata.short-description; an adapter file collides
with a generated one (hosts/<host>/hooks/ddl_gate.py); an implementation has a section other than Read when,
Mapping, Observed and Coverage; a folded operation's last section is not `## Implementation`.

Usage:
  python3 tools/build.py [REPO] [--check] [--out DIR]

REPO defaults to the checkout this script lives in. The default writes dist/ (or DIR with --out), removes
files under dist/claude and dist/codex that are no longer generated, and prints "built claude, codex
(N files)". --check writes nothing: it compares the build with the files on disk, prints "dist up to date
(N files)" and exits 0, or lists every missing, differing, and extra file and exits 1.
"""
import os
import pathlib
import re
import sys

COMMANDS = ["draft", "realize", "reflect", "validate", "commit", "docs", "refactoring", "resonate"]
PROTOCOL = "ddl-protocol"
OPERATIONS = ["approval", "parallel-work", "notebook", "close", "git-review", "command-authoring"]
IMPLEMENTATIONS = ["start", "approval", "parallel-work", "git-review"]
FOLDED = ["Mapping", "Observed", "Coverage"]  # the implementation sections folded in, in this order; the rest is dropped
DROPPED = ["Read when"]
HOST_SECTION = "Host"  # the entry's folded section (start); the operations fold under their last section
IMPLEMENTATION_SECTION = "Implementation"
GUIDANCE = "guidance.md"
NOT_DEPLOYED = ["README.md"]
GATE_SOURCE = "tools/ddl_gate.py"
HOSTS = {
    "claude": {"Host": "Claude", "adapter": "claude/.claude", "guidance": "claude/.claude/CLAUDE.md",
               "skills": "claude/.claude/skills"},
    "codex": {"Host": "Codex", "adapter": "codex/.codex", "guidance": "codex/AGENTS.md",
              "skills": "codex/.agents/skills"},
}

OPENAI_POLICY = ("policy:\n"
                 "  allow_implicit_invocation: false\n")
OPENAI_YAML = ("# DDL: a skill runs when the user invokes ${name}; Codex does not start it on its own "
               "(the host's implementations are folded into the entry and the operations of the protocol skill).\n"
               + OPENAI_POLICY)
OPENAI_YAML_PROTOCOL = ("# DDL: the protocol skill; the command skills read it in Phase 0, nobody invokes $ddl-protocol, and Codex "
                        "does not start it on its own (the host's implementations are folded into the entry and the operations).\n"
                        + OPENAI_POLICY)

# Notebook Formats literals keep their "/" in both hosts: design.md records them as the protocol spells them.
PROTECTED = ("approved /draft report", "approved in /realize plan", "delegated to /realize")
SLASH = re.compile(r"(?<![A-Za-z0-9_./-])/(draft|realize|reflect|validate|commit|docs|refactoring|resonate)\b")


def require(repo, rel):
    """The bytes of a source file; a missing file or a symlink is an error."""
    path = repo / rel
    if path.is_symlink():
        raise SystemExit(f"{rel}: symlink (refused)")
    if not path.is_file():
        raise SystemExit(f"{rel}: missing")
    return path.read_bytes()


def split_frontmatter(name, text, short_description):
    """(fields, body). `fields` holds name, description, and short-description when present; the rest of the
    frontmatter is Claude-only and dropped on the Codex side. `short_description` says whether it is required."""
    m = re.match(r"---\n(.*?)\n---\n\n?", text, re.S)
    if not m:
        raise SystemExit(f"{name}: no frontmatter")
    fields = {}
    for line in m.group(1).split("\n"):
        key, sep, value = line.strip().partition(":")
        if sep and key in ("name", "description", "short-description"):
            fields[key] = value.strip()
    required = ("name", "description") + (("short-description",) if short_description else ())
    for key in required:
        if key not in fields:
            raise SystemExit(f"{name}: frontmatter lacks {key}")
    if fields["name"] != name:
        raise SystemExit(f"{name}: frontmatter name is {fields['name']!r}")
    return fields, text[m.end():]


def to_codex(name, text):
    """The Codex SKILL.md: Codex frontmatter, then the body with /cmd -> $cmd for a command and unchanged
    for the protocol."""
    fields, body = split_frontmatter(name, text, short_description=name != PROTOCOL)
    if name != PROTOCOL:
        protected = {f"\x00{i}\x00": lit for i, lit in enumerate(PROTECTED)}
        for key, lit in protected.items():
            body = body.replace(lit, key)
        body = SLASH.sub(r"$\1", body)
        for key, lit in protected.items():
            body = body.replace(key, lit)
    head = f"---\nname: {name}\ndescription: {fields['description']}\n"
    if "short-description" in fields:
        head += f"metadata:\n  short-description: {fields['short-description']}\n"
    return head + "---\n\n" + body


def render(text, host):
    return text.replace("{host}", host).replace("{Host}", HOSTS[host]["Host"])


def fold(text, implementation, heading=None):
    """text with the implementation's Mapping, Observed and Coverage sections appended as H3 sections: under the
    text's last H2, which must be `## Implementation` (heading None), or under a new `## <heading>` section
    added after the end of the text. The implementation's H1 and its `## Read when` are dropped; any other
    section is an error. A missing section is folded as missing (check_ddl.py dist reports it)."""
    parts = {}
    for chunk in implementation.split("\n## ")[1:]:
        title, _, body = chunk.partition("\n")
        title = title.strip()
        if title in FOLDED:
            parts[title] = f"### {title}\n\n{body.strip(chr(10))}\n"
        elif title not in DROPPED:
            raise SystemExit(f"implementation section ## {title}: not foldable (expected {', '.join(DROPPED + FOLDED)})")
    folded = "\n".join(parts[title] for title in FOLDED if title in parts)
    if heading is None:
        last = re.findall(r"(?m)^## (.+?)\s*$", text)
        if not last or last[-1] != IMPLEMENTATION_SECTION:
            raise SystemExit(f"last section is {'## ' + last[-1] if last else 'missing'}, "
                             f"not ## {IMPLEMENTATION_SECTION} (the implementation folds under it)")
        return text.rstrip("\n") + "\n\n" + folded
    return text.rstrip("\n") + f"\n\n## {heading}\n\n" + folded


def relink(text, name):
    """The links of a protocol file (name: SKILL.md or <operation>.md) to hosts/{host}/<implementation>.md pointed
    at the folded sections: start lives in the entry's `## Host`, the others under `## Implementation` of
    their operation. Exact token replacement, never a format."""
    for implementation in IMPLEMENTATIONS:
        token = "(hosts/{host}/" + implementation + ".md)"
        if implementation == "start":
            target = "#host" if name == "SKILL.md" else "SKILL.md#host"
        elif name == f"{implementation}.md":
            target = "#implementation"
        else:
            target = f"{implementation}.md#implementation"
        text = text.replace(token, f"({target})")
    return text


def hidden(rel):
    return any(part.startswith(".") or part == "__pycache__" for part in rel.parts)


def generate(repo):
    """Every output file, keyed by its path relative to dist/ (posix form)."""
    repo = pathlib.Path(repo)
    gate = require(repo, GATE_SOURCE)
    skills = {name: require(repo, f"skills/{name}/SKILL.md").decode("utf-8") for name in COMMANDS}
    for name, text in skills.items():
        split_frontmatter(name, text, short_description=True)
    entry = require(repo, f"protocol/SKILL.md").decode("utf-8")
    split_frontmatter(PROTOCOL, entry, short_description=False)
    for operation in OPERATIONS:
        require(repo, f"protocol/{operation}.md")
    operations = {}
    for path in sorted((repo / "protocol").iterdir()):
        rel = path.relative_to(repo)
        if hidden(pathlib.Path(path.name)):
            continue
        if path.is_symlink():
            raise SystemExit(f"{rel}: symlink (refused)")
        if path.name == "SKILL.md":
            continue
        if not path.is_file() or path.suffix != ".md":
            raise SystemExit(f"{rel}: unexpected (protocol/ holds the entry and the operations only)")
        operations[path.name] = path.read_bytes().decode("utf-8")
    out = {}
    for host, spec in HOSTS.items():
        host_dir = repo / "hosts" / host
        if not host_dir.is_dir():
            raise SystemExit(f"hosts/{host}/: missing")
        implementations = [f"{name}.md" for name in IMPLEMENTATIONS]
        folded = {name: require(repo, f"hosts/{host}/{name}.md").decode("utf-8") for name in IMPLEMENTATIONS}
        out[spec["guidance"]] = require(repo, f"hosts/{host}/{GUIDANCE}")
        for path in sorted(host_dir.rglob("*")):
            rel = path.relative_to(host_dir)
            if hidden(rel):
                continue
            if path.is_symlink():
                raise SystemExit(f"{path.relative_to(repo)}: symlink (refused)")
            if not path.is_file():
                continue
            if rel.parent == pathlib.Path(".") and rel.name in implementations + [GUIDANCE] + NOT_DEPLOYED:
                continue
            out[f"{spec['adapter']}/{rel.as_posix()}"] = path.read_bytes()
        gate_copy = f"{spec['adapter']}/hooks/ddl_gate.py"
        if gate_copy in out:
            raise SystemExit(f"hosts/{host}/hooks/ddl_gate.py: collides with the gate copy of {GATE_SOURCE}")
        out[gate_copy] = gate
        for name, text in skills.items():
            skill = f"{spec['skills']}/{name}"
            if host == "codex":
                out[f"{skill}/SKILL.md"] = to_codex(name, text).encode("utf-8")
                out[f"{skill}/agents/openai.yaml"] = OPENAI_YAML.format(name=name).encode("utf-8")
            else:
                out[f"{skill}/SKILL.md"] = text.encode("utf-8")
        protocol = f"{spec['skills']}/{PROTOCOL}"
        try:
            rendered = render(relink(fold(entry, folded["start"], HOST_SECTION), "SKILL.md"), host)
        except SystemExit as exc:
            raise SystemExit(f"protocol/SKILL.md with hosts/{host}/start.md: {exc}") from None
        if host == "codex":
            out[f"{protocol}/SKILL.md"] = to_codex(PROTOCOL, rendered).encode("utf-8")
            out[f"{protocol}/agents/openai.yaml"] = OPENAI_YAML_PROTOCOL.encode("utf-8")
        else:
            out[f"{protocol}/SKILL.md"] = rendered.encode("utf-8")
        for name, text in operations.items():
            stem = name.removesuffix(".md")
            if stem in folded and stem != "start":
                try:
                    text = fold(text, folded[stem])
                except SystemExit as exc:
                    raise SystemExit(f"protocol/{name} with hosts/{host}/{name}: {exc}") from None
            out[f"{protocol}/{name}"] = render(relink(text, name), host).encode("utf-8")
    return out


def symlink_components(out, files):
    """Symlinks on the generated paths, the output directory included; none is followed."""
    found = set()
    if out.is_symlink():
        found.add(out)
    for rel in files:
        path = out
        for part in pathlib.PurePosixPath(rel).parts:
            path = path / part
            if path.is_symlink():
                found.add(path)
                break
    return sorted(found)


def on_disk(out):
    """Every file and symlink under out/<host> for the hosts, keyed like generate()."""
    present = {}
    for host in HOSTS:
        top = out / host
        if not top.is_dir() or top.is_symlink():
            continue
        for dirpath, dirnames, filenames in os.walk(top):
            directory = pathlib.Path(dirpath)
            for name in filenames + [n for n in dirnames if (directory / n).is_symlink()]:
                path = directory / name
                present[path.relative_to(out).as_posix()] = path
    return present


def refuse_symlinks(out, files):
    unsafe = symlink_components(out, files)
    if unsafe:
        raise SystemExit("\n".join(f"generated path contains symlink: {p} (not followed or removed)" for p in unsafe))


def write(repo, out=None):
    """Write the build under out (default REPO/dist), remove the files under out/claude and out/codex that are
    no longer generated, and return every generated path relative to out."""
    repo = pathlib.Path(repo).resolve()
    out = pathlib.Path(out).resolve() if out is not None else repo / "dist"
    files = generate(repo)
    refuse_symlinks(out, files)
    for rel, path in on_disk(out).items():
        if rel not in files:
            path.unlink()
    for host in HOSTS:
        top = out / host
        if top.is_dir():
            for dirpath, dirnames, _ in os.walk(top, topdown=False):
                for name in dirnames:
                    path = pathlib.Path(dirpath) / name
                    if path.is_dir() and not path.is_symlink() and not any(path.iterdir()):
                        path.rmdir()
    for rel, data in sorted(files.items()):
        dest = out / rel
        if dest.is_file() and dest.read_bytes() == data:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    return sorted(files)


def check(repo, out=None):
    """(problems, count): the lines that describe a stale build, and the number of generated files."""
    repo = pathlib.Path(repo).resolve()
    out = pathlib.Path(out).resolve() if out is not None else repo / "dist"
    files = generate(repo)
    problems = [f"symlink: {p}" for p in symlink_components(out, files)]
    present = on_disk(out)
    for rel, data in sorted(files.items()):
        path = present.get(rel)
        if path is None:
            problems.append(f"missing: {rel}")
        elif path.is_symlink() or not path.is_file():
            problems.append(f"not a file: {rel}")
        elif path.read_bytes() != data:
            problems.append(f"differs: {rel}")
    problems += [f"extra: {rel}" for rel in sorted(present) if rel not in files]
    return problems, len(files)


def main(argv):
    args = list(argv)
    checking = "--check" in args
    if checking:
        args.remove("--check")
    out = None
    if "--out" in args:
        i = args.index("--out")
        if i + 1 >= len(args) or args[i + 1].startswith("--"):
            raise SystemExit("--out needs a directory")
        out = pathlib.Path(args[i + 1])
        del args[i:i + 2]
    unknown = [a for a in args if a.startswith("--")]
    if unknown:
        raise SystemExit(f"unknown option: {' '.join(unknown)}")
    if len(args) > 1:
        raise SystemExit(f"unexpected argument: {' '.join(args[1:])} (usage: build.py [REPO] [--check] [--out DIR])")
    repo = pathlib.Path(args[0]).resolve() if args else pathlib.Path(__file__).resolve().parent.parent
    for needed in ("skills", "protocol", "hosts"):
        if not (repo / needed).is_dir():
            raise SystemExit(f"{repo}: no {needed}/ (not the DDL repository?)")
    if checking:
        problems, count = check(repo, out)
        if problems:
            print("\n".join(problems))
            return 1
        print(f"dist up to date ({count} files)")
        return 0
    written = write(repo, out)
    print(f"built {', '.join(HOSTS)} ({len(written)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
