#!/usr/bin/env python3
"""DDL Run subcommands: the counts of `report`, the Run's record (`run-start`, `run-item`) and its
snapshots (`snapshot`).

They run a few times per plan, outside any hook, so they live apart from the gate's code
(`tools/ddl_gate_core.py`, which the hook's entry `tools/ddl_gate.py` loads on every hook call). The
command line is the gate's: `ddl_gate.py report|run-start|run-item|snapshot …` imports this module
beside it for those words only, and `ddl_run.py <word> …` runs the same code with the same output,
errors and exit codes. No hook event (PreToolUse, Stop, UserPromptSubmit, SessionStart) imports this
module.

Usage (from inside the project; the project and its `.ddl/` ledger come from the working directory):
  python3 tools/ddl_run.py run-start [--runtime claude|codex]      (JSON {report, items} on stdin)
  python3 tools/ddl_run.py run-item <N-id> <item id> <status>
  python3 tools/ddl_run.py report (--transcript FILE --runtime claude|codex | --session ID | --run N-ID)
                                  [--language ja|en]
  python3 tools/ddl_run.py snapshot [--run N-ID] [--item ID] [--git-dir DIR --work-tree DIR]
  python3 tools/ddl_run.py snapshot list [--run N-ID] [--git-dir DIR --work-tree DIR]

`run-start` writes `.ddl/runs/<N-id>/run.json` from {report, items} and prints {run, path}; `run-item`
sets one item's status and prints {run, item, status}; `report` prints four lines: questions, waiting,
denials, grant. A Run's lines count its plan's own question too, in the plan's language unless
`--language` names one. A value that cannot be derived is printed as `未計測` (`not measured`). A usage or
input error prints `DDL report: …`, `DDL run: …` or `DDL snapshot: …` on stderr and exits 2. Nothing here
is read back by a hook decision: an item's `done` is never a gate pass.

`snapshot` saves the work tree of the working directory's repository (or of the given Git directory and
work tree) as Git would commit it with `git add -A`: tracked changes, deletions and untracked files,
without what `.gitignore` or `info/exclude` ignores. It builds the tree in a temporary index, commits it
on HEAD (no parent before the first commit) and names the commit
`refs/ddl/snapshots/<N-id | adhoc>/<UTC stamp>-<item | snap>`, refusing a name that exists. The real
index, HEAD, every branch and every file of the work tree stay as they were, and nothing is pushed. It
prints {snapshot (the commit), ref, files (how many paths differ from HEAD), unchanged (the tree is
HEAD's)} and writes a `snapshot` event when the working directory is in a DDL project. `snapshot list`
prints {snapshots: [{ref, commit}, …]}, newest first.

The import boundary: this module imports the gate's code `ddl_gate_core` from its own directory,
symbolic links resolved, so an installed `~/.claude/hooks/ddl_run.py` link finds the gate beside the
file it points at, and reads through it what the hook shares: project detection and the ledger root,
the ledger's directory and event writing, the grant store's records, the prepared report, the parsing
of the native question and its answer, and the count lines' text. Run as a script it writes bytecode
only under the interpreter's own prefix, when it has one; loaded through the gate, only into the gate's
private cache: never a `__pycache__` beside an installed copy.
"""
import json
import os
import re
import secrets
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
if __name__ == "__main__":  # importing the gate leaves no __pycache__ beside an installed copy
    sys.dont_write_bytecode = sys.dont_write_bytecode or sys.pycache_prefix is None
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import ddl_gate_core as gate  # noqa: E402

WORDS = ("report", "run-start", "run-item", "snapshot")
RUN_ID_BYTES = 6  # a Run ID is N- and these random bytes in hex
RUN_ID = re.compile(r"N-[0-9a-f]{%d}" % (2 * RUN_ID_BYTES))
ITEM_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,31}")
ITEM_KEYS = {"id", "kind", "files", "after"}
ITEM_KINDS = ("write", "verify", "explore", "compute")
ITEM_STATUSES = ("ready", "running", "done", "failed", "dropped")
MAX_RUN_ITEMS = 200
REPORT_FLAGS = ("--transcript", "--runtime", "--session", "--run", "--language")
REPORT_USAGE = ("usage: ddl_gate.py report (--transcript FILE --runtime claude|codex | --session ID | --run N-ID) "
                "[--language ja|en]")
RUN_USAGE = "usage: ddl_gate.py run-start (JSON on stdin) | run-item <N-id> <item id> <status>"
SNAPSHOT_USAGE = ("usage: ddl_gate.py snapshot [--run N-ID] [--item ID] [--git-dir DIR --work-tree DIR] "
                  "| snapshot list [--run N-ID] [--git-dir DIR --work-tree DIR]")
USAGE = "usage: ddl_run.py report|run-start|run-item|snapshot … ({}; {}; {})".format(REPORT_USAGE, RUN_USAGE,
                                                                                     SNAPSHOT_USAGE)
SNAPSHOT_REFS = "refs/ddl/snapshots"
SNAPSHOT_FLAGS = {"make": ("--run", "--item", "--git-dir", "--work-tree"), "list": ("--run", "--git-dir", "--work-tree")}
# The identity of a snapshot made where Git has none configured: the tool's, at a domain that cannot exist.
NEUTRAL_IDENTITY = ("DDL snapshot", "snapshot@ddl.invalid")
SNAPSHOT_TIMEOUT = 300  # seconds for one Git command; `add -A` reads every file of a large work tree
# The last part of a snapshot's name: the UTC stamp (milliseconds optional, as a hand-made ref may lack them).
SNAPSHOT_NAME = re.compile(r"(\d{8}T\d{6})(?:\.(\d{1,9}))?Z-")


# --- counts -----------------------------------------------------------------------------------
# They read what the hook recorded and the conversation record; nothing here is read back by a hook decision.

def question_outcome(labels, label, timeout):
    """`timeout`, `approved` (the first option was submitted) or `revised` (anything else was)."""
    return "timeout" if timeout else "approved" if labels and label == labels[0] else "revised"


def refused_by_hook(entry):
    """True when the host recorded that a hook refused the call: such a question was never shown."""
    decision = entry.get("permissionDecision")
    return isinstance(decision, dict) and decision.get("source") == "hook" and decision.get("decision") == "reject"


def claude_questions(path):
    """The questions that carry an ID in a Claude transcript, in order, each with the `timestamp` of the
    entry that holds its tool call and of the entry that holds its answer."""
    asked = {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if '"tool_' not in line:  # neither a tool call nor a tool result
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if not isinstance(entry, dict) or entry.get("isSidechain"):
                continue
            for block in gate.entry_blocks(entry):
                if entry.get("type") == "assistant" and block.get("type") == "tool_use" \
                        and block.get("name") in gate.QUESTION_TOOLS["claude"] and block.get("id") not in asked:
                    ident = gate.question_id(gate.asked_question("claude", block.get("input")))
                    if ident:
                        asked[block.get("id")] = {"id": "-".join(ident), "labels": gate.option_labels(block.get("input")),
                                                  "asked": gate.iso_seconds(entry.get("timestamp")), "outcome": None}
                elif entry.get("type") == "user" and block.get("type") == "tool_result":
                    question = asked.get(block.get("tool_use_id"))
                    if question is None or "closed" in question:
                        continue
                    question["closed"] = not refused_by_hook(entry)
                    close = gate.claude_question_close(entry)
                    if close:
                        question.update(outcome=question_outcome(question["labels"], *close),
                                        answered=gate.iso_seconds(entry.get("timestamp")))
    return [question for question in asked.values() if question.get("closed", True)]


def codex_questions(path):
    """Same for a Codex rollout: the line of the question's call and the line of its reply message, each
    with its top-level `timestamp` when the rollout writes one."""
    asked = {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            payload = entry.get("payload") if isinstance(entry, dict) else None
            if not isinstance(payload, dict):
                continue
            kind, ptype, item = entry.get("type"), payload.get("type"), payload.get("item")
            if kind == "response_item" and ptype == "function_call" \
                    and payload.get("name") in gate.QUESTION_TOOLS["codex"] and payload.get("call_id") not in asked:
                text = gate.asked_question("codex", payload.get("arguments"))
                ident = gate.question_id(text)
                if ident:
                    asked[payload.get("call_id")] = {"id": "-".join(ident), "text": text, "outcome": None,
                                                     "labels": gate.option_labels(payload.get("arguments")),
                                                     "asked": gate.iso_seconds(entry.get("timestamp"))}
            elif kind == "event_msg" and ptype == "item_completed" and isinstance(item, dict) \
                    and item.get("type") == "UserMessage":
                reply = gate.codex_git_reply(gate.codex_text(item))
                question = asked.get(reply[0]) if reply else None
                if question and question["outcome"] is None and isinstance(reply[1], str) \
                        and reply[1].replace("\r\n", "\n") == question["text"].replace("\r\n", "\n"):
                    question.update(outcome=question_outcome(question["labels"], reply[2], False),
                                    answered=gate.iso_seconds(entry.get("timestamp")))
    return list(asked.values())


def ledger_lines(root):
    """The ledger's event objects, first to last; None when the project has no ledger file.

    A line that repeats the session, kind, id and toolUseId of an earlier one is the second install's copy
    of the same hook event and is dropped. Lines without a toolUseId cannot be told apart and all stay."""
    events, seen = [], set()
    try:
        fh = open(os.path.join(root, gate.LEDGER, "events.jsonl"), encoding="utf-8", errors="replace")
    except OSError:
        return None
    with fh:
        for line in fh:
            try:
                event = json.loads(line)
            except ValueError:
                continue  # a torn or foreign line; the lines around it still count
            if not isinstance(event, dict) or event.get("v") != gate.EVENT_VERSION:
                continue
            if event.get("toolUseId") is not None:
                key = json.dumps([event.get(name) for name in ("session", "kind", "id", "toolUseId")])
                if key in seen:
                    continue
                seen.add(key)
            events.append(event)
    return events


def event_questions(events):
    """The questions in a selection of ledger events: each `asked` line, joined with the `answered` line of
    the same session, id and call (of the same id alone when the two hosts' call ids differ)."""
    questions, latest = [], {}
    for event in events:
        ident, kind = event.get("id"), event.get("kind")
        keys = [json.dumps([event.get("session"), ident, call]) for call in (event.get("toolUseId"), None)]
        if kind == "asked" and isinstance(ident, str):
            question = {"id": ident, "asked": gate.iso_seconds(event.get("ts")), "outcome": None}
            questions.append(question)
            latest.update((key, question) for key in keys)
        elif kind == "answered":
            question = latest.get(keys[0]) or latest.get(keys[1])
            if question and question["outcome"] is None:
                question.update(answered=gate.iso_seconds(event.get("ts")),
                                outcome="timeout" if event.get("timeout") else
                                "approved" if event.get("choice") == 0 else "revised")
    return questions


def count_lines(language, questions, denials, grant):
    """The four count lines. `questions` (each with outcome, asked, answered) and `denials` are None when the
    source cannot tell them; `grant` is a grant record, False for none, or None when it cannot be looked up.

    Waiting covers the submitted answers, from the question's call to its answer; a timeout is counted apart
    on the first line. Minutes are rounded to the nearest whole one. Nothing is estimated: a value that
    cannot be derived is printed as not measured."""
    text = gate.COUNT_TEXT[language]
    unmeasured, asked, waiting = text["unmeasured"], text["unmeasured"], text["unmeasured"]

    def minutes(seconds):
        return text["minutes"].format(int((seconds + 30) // 60))

    if questions is not None:
        tally = [sum(q["outcome"] == key for q in questions) for key in ("approved", "revised", "timeout")]
        asked = text["asked"].format(len(questions), *tally)
        waits = [q["answered"] - q["asked"] if q.get("answered") is not None and q["asked"] is not None else None
                 for q in questions if q["outcome"] in ("approved", "revised")]
        if all(wait is not None and wait >= 0 for wait in waits):
            waits.sort()
            middle = len(waits) // 2
            # The median by hand: the middle value, or the mean of the two middle ones.
            median = waits[middle] if len(waits) % 2 else (waits[middle - 1] + waits[middle]) / 2 if waits else None
            waiting = text["waiting"].format(minutes(sum(waits)), minutes(median) if waits else unmeasured,
                                             minutes(waits[-1]) if waits else unmeasured)
    lines = [asked, waiting, unmeasured if denials is None else text["denied"].format(denials),
             unmeasured if grant is None else gate.grant_summary(grant, language) if grant else text["none"]]
    return [label + ": " + line for label, line in zip(text["labels"], lines)]


# --- the Run ----------------------------------------------------------------------------------
# A record for people and reports. No hook reads it.

def run_file(root, run_id):
    return os.path.join(root, gate.LEDGER, "runs", run_id, "run.json")


def load_run(root, run_id):
    """The Run's record; ValueError when the ID is malformed or the project's ledger holds no such Run."""
    if not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id):
        raise ValueError("a Run ID is N- and 12 hexadecimal characters.")
    try:
        with open(run_file(root, run_id), encoding="utf-8") as fh:
            run = json.load(fh)
    except (OSError, ValueError, TypeError):
        run = None
    if not isinstance(run, dict) or run.get("id") != run_id or not isinstance(run.get("items"), list):
        raise ValueError("Run {} is not in this project's ledger.".format(run_id))
    return run


def ledger_runs(root):
    """Every readable Run of the ledger."""
    try:
        names = sorted(os.listdir(os.path.join(root, gate.LEDGER, "runs")))
    except OSError:
        return []
    runs = []
    for name in names:
        try:
            runs.append(load_run(root, name))
        except ValueError:
            continue
    return runs


def report_command(argv):
    """`report`: the four count lines for a conversation record, a session's ledger events, or a Run.

    A Run's events are those the ledger dates from its start until the next Run of the project starts, and
    those that carry the ID of its plan's report whenever they were written: the plan is asked and answered
    before its Run starts. Without `--language` a Run's lines are in its plan's language (Japanese for a
    Japanese code and for a Run that names none, English for any other); the other two default to Japanese."""
    options, rest = {}, list(argv)
    while rest:
        name, equal, value = rest.pop(0).partition("=")
        if name not in REPORT_FLAGS or name in options or not (equal or rest):
            raise ValueError(REPORT_USAGE)
        options[name] = value if equal else rest.pop(0)
    modes = [name for name in ("--transcript", "--session", "--run") if name in options]
    given, runtime = options.get("--language"), options.get("--runtime")
    if len(modes) != 1 or given not in (None, *gate.COUNT_TEXT) or runtime not in (None,) + gate.RUNTIMES \
            or (modes[0] == "--transcript" and runtime is None) or not options[modes[0]]:
        raise ValueError(REPORT_USAGE)
    mode, value, language = modes[0], options[modes[0]], given or "ja"
    if mode == "--transcript":
        try:
            questions = (codex_questions if runtime == "codex" else claude_questions)(value)
        except OSError:
            return count_lines(language, None, None, None)  # an unreadable record: nothing can be derived
        asked = {question["id"] for question in questions}
        grants = [record for record in gate.grant_records() if record["id"] in asked]
        # A record shows no gate decision the gate can tell from another hook's, so denials are not counted here.
        return count_lines(language, questions, None, grants[-1] if grants else False)
    if mode == "--run" and not RUN_ID.fullmatch(value):
        raise ValueError(REPORT_USAGE)
    root, key = gate.cwd_ledger()
    if not root and mode == "--run":
        raise ValueError("Run {} needs its DDL project as the working directory.".format(value))
    if not root:
        return count_lines(language, None, None, None)
    events = ledger_lines(root)
    if mode == "--session":
        chosen = None if events is None else [event for event in events if event.get("session") == value]
        grants = [record for record in gate.grant_records(key) if record.get("session") == value]
    else:
        run = load_run(root, value)
        if given is None and isinstance(run.get("language"), str) and not gate.is_japanese(run["language"]):
            language = "en"
        plan, start = run.get("report"), gate.iso_seconds(run.get("startedAt"))
        later = [moment for moment in (gate.iso_seconds(other.get("startedAt")) for other in ledger_runs(root))
                 if moment is not None and start is not None and moment > start]
        end = min(later) if later else None

        def of_run(event):  # dated within the Run, or about its plan's report; each ledger line is seen once
            moment = gate.iso_seconds(event.get("ts"))
            return (isinstance(plan, str) and event.get("id") == plan) or (
                moment is not None and moment >= start and (end is None or moment < end))

        chosen = None if events is None or start is None else [event for event in events if of_run(event)]
        grants = [record for record in gate.grant_records(key) if record["id"] == plan]
    if chosen is None:
        return count_lines(language, None, None, grants[-1] if grants else False)
    return count_lines(language, event_questions(chosen), sum(event.get("kind") == "denied" for event in chosen),
                       grants[-1] if grants else False)


def run_items(items):
    """The items of a new Run, each with `status: "ready"`; ValueError names the first problem."""
    if not isinstance(items, list) or len(items) > MAX_RUN_ITEMS:
        raise ValueError("items must be a list of at most {} items.".format(MAX_RUN_ITEMS))
    out = []
    for item in items:
        if not isinstance(item, dict) or not {"id", "kind"} <= set(item) <= ITEM_KEYS:
            raise ValueError("each item is {id, kind, files?, after?}.")
        if not isinstance(item["id"], str) or not ITEM_ID.fullmatch(item["id"]):
            raise ValueError("an item id is 1 to 32 letters, digits, dots, hyphens or underscores, such as I1.")
        if item["kind"] not in ITEM_KINDS:
            raise ValueError("item {}: kind must be one of {}.".format(item["id"], ", ".join(ITEM_KINDS)))
        lists = {key: item.get(key, []) for key in ("files", "after")}
        for key, values in lists.items():
            if not isinstance(values, list) or not all(gate.one_line(value) for value in values) \
                    or len(set(values)) != len(values):
                raise ValueError("item {}: {} must be a list of different one-line strings.".format(item["id"], key))
        out.append({"id": item["id"], "kind": item["kind"], **lists, "status": "ready"})
    ids = [item["id"] for item in out]
    if len(set(ids)) != len(ids):
        raise ValueError("item ids must differ.")
    for item in out:
        if item["id"] in item["after"] or not set(item["after"]) <= set(ids):
            raise ValueError("item {}: after names other items of this Run.".format(item["id"]))
    ended = set()
    while len(ended) < len(out):  # every item must be reachable in dependency order
        free = [item["id"] for item in out if item["id"] not in ended and set(item["after"]) <= ended]
        if not free:
            raise ValueError("the after relations form a cycle.")
        ended.update(free)
    return out


def run_start(data, runtime=None):
    """`run-start`: write `.ddl/runs/<N-id>/run.json` for one approved plan's report and print {run, path}.

    The Run names the grant only when the store holds that grant's record, and keeps the plan's language,
    in which `report --run` prints. It is a record for people and reports. No hook reads it: an item's
    `done` is never a gate pass."""
    if not isinstance(data, dict) or set(data) != {"report", "items"}:
        raise ValueError("send one JSON object with report and items.")
    match = gate.PREPARED_ID.fullmatch(data["report"]) if isinstance(data["report"], str) else None
    if not match or match[1] != "R":
        raise ValueError("report must be a prepared report ID such as R-0123456789abcdef.")
    items = run_items(data["items"])
    root, key = gate.cwd_ledger()
    if not root:
        raise ValueError("a Run belongs to a DDL project; start it from inside the project.")
    try:
        record = gate.load_report(match[2], runtime)
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        raise ValueError("report {} is not prepared here ({}).".format(data["report"], exc)) from None
    if record["projectKey"] != key:
        raise ValueError("report {} was prepared in another project.".format(data["report"]))
    for run in ledger_runs(root):
        if run.get("report") == data["report"]:  # one Run per approved plan, also after a compaction or restart
            raise ValueError("report {} already started Run {} ({}).".format(
                data["report"], run["id"], run_file(root, run["id"])))
    granted =gate.read_grant(gate.grant_file(key, data["report"]), data["report"]) is not None
    os.makedirs(os.path.join(gate.ledger_directory(root), "runs"), exist_ok=True)
    while True:
        run_id = "N-" + secrets.token_hex(RUN_ID_BYTES)
        try:
            os.mkdir(os.path.dirname(run_file(root, run_id)))
            break
        except FileExistsError:
            continue
    run = {"id": run_id, "report": data["report"], "grant": data["report"] if granted else None,
           "language": record["language"], "startedAt": gate.utc_stamp(), "items": items}
    with open(run_file(root, run_id), "w", encoding="utf-8") as fh:
        fh.write(json.dumps(run, ensure_ascii=False, indent=2) + "\n")
    gate.ledger_event(root, record["runtime"], None, "prepared", id=run_id, run=run_id)
    return {"run": run_id, "path": run_file(root, run_id)}


def run_item(argv):
    """`run-item <N-id> <item id> <status>`: set one item's status in the Run's record and print it."""
    if len(argv) != 3:
        raise ValueError(RUN_USAGE)
    run_id, item_id, status = argv
    if status not in ITEM_STATUSES:
        raise ValueError("status must be one of {}.".format(", ".join(ITEM_STATUSES)))
    root, _ = gate.cwd_ledger()
    if not root:
        raise ValueError("a Run belongs to a DDL project; run this from inside the project.")
    run = load_run(root, run_id)
    item = next((item for item in run["items"] if isinstance(item, dict) and item.get("id") == item_id), None)
    if item is None:
        raise ValueError("Run {} has no item {}.".format(run_id, item_id))
    item["status"] = status
    path = run_file(root, run_id)
    scratch = "{}.{}.tmp".format(path, os.getpid())
    with open(scratch, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(run, ensure_ascii=False, indent=2) + "\n")
    os.replace(scratch, path)  # readers see the old record or the new one, never half of one
    return {"run": run_id, "item": item_id, "status": status}


# --- snapshots --------------------------------------------------------------------------------
# A commit of the work tree under refs/ddl/snapshots/: it moves no branch, index or file (P20).

class SnapshotGit:
    """Git in the snapshot's repository: the working directory's, or the given Git directory and work tree.

    Every command gets the temporary index (when there is one) as GIT_INDEX_FILE, so the repository's own
    index file is never opened, and it never prompts, takes no optional lock, runs no fsmonitor, writes no
    split index and follows no replacement object."""

    def __init__(self, options, index=None):
        self.pair = []
        if "--git-dir" in options:  # relative paths name directories from the working directory
            self.pair = ["--git-dir=" + os.path.abspath(options["--git-dir"]),
                         "--work-tree=" + os.path.abspath(options["--work-tree"])]
        self.env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0")
        if index is not None:
            self.env["GIT_INDEX_FILE"] = index
        self.cwd = os.getcwd()

    def __call__(self, *args, env=None, optional=False):
        """The command's standard output in bytes; when it fails, None if `optional`, else ValueError."""
        import subprocess
        command = ["git", "--no-pager", "--no-replace-objects", "-c", "core.fsmonitor=false",
                   "-c", "core.splitIndex=false", *self.pair, *args]
        try:
            proc = subprocess.run(command, cwd=self.cwd, stdin=subprocess.DEVNULL, capture_output=True,
                                  env=dict(self.env, **(env or {})), timeout=SNAPSHOT_TIMEOUT)
        except (OSError, subprocess.SubprocessError) as exc:
            raise ValueError("git could not be run ({}).".format(exc)) from None
        if proc.returncode == 0:
            return proc.stdout
        if optional:
            return None
        rest = list(args)
        while rest[:1] == ["-c"]:
            rest = rest[2:]
        said = [line.strip() for line in proc.stderr.decode("utf-8", "replace").splitlines() if line.strip()]
        raise ValueError("git {} failed ({}).".format(rest[0] if rest else "", said[-1] if said else
                                                      "exit status {}".format(proc.returncode)))


def ref_stamp():
    """Now, as the gate writes a time, without the characters a ref name may not hold: 20261124T001200.123Z."""
    return gate.utc_stamp().replace("-", "").replace(":", "")


def snapshot_options(argv, flags):
    """The options of `snapshot` or `snapshot list`, each once, as `--name value` or `--name=value`; the Git
    directory and the work tree come together. ValueError names the first problem."""
    options, rest = {}, list(argv)
    while rest:
        name, equal, value = rest.pop(0).partition("=")
        if name not in flags or name in options or not (equal or rest):
            raise ValueError(SNAPSHOT_USAGE)
        options[name] = value if equal else rest.pop(0)
    if ("--git-dir" in options) != ("--work-tree" in options) or not all(options.values()):
        raise ValueError(SNAPSHOT_USAGE)
    if "--run" in options and not RUN_ID.fullmatch(options["--run"]):
        raise ValueError("a Run ID is N- and 12 hexadecimal characters.")
    item = options.get("--item")
    if item is not None and (not ITEM_ID.fullmatch(item) or ".." in item or item.endswith((".", ".lock"))):
        raise ValueError("an item id is 1 to 32 letters, digits, dots, hyphens or underscores, such as I1, "
                         "and as part of a ref name it holds no '..' and does not end in '.' or '.lock'.")
    return options


def snapshot(options):
    """`snapshot`: commit the work tree as `git add -A` sees it under a new ref and print
    {snapshot, ref, files, unchanged}.

    The tree is built in a temporary index from HEAD's (empty before the first commit), so the real index,
    staged or conflicted, is never read or written. The commit has HEAD as its parent (none before the first
    commit), the message `DDL snapshot <N-id | adhoc> <item | snap>`, and the user's Git identity, or the
    neutral one where Git has none configured (it is never guessed from the system); it is never signed, so
    no key or passphrase is asked for. The ref is created only where none exists. `files` counts the paths
    that differ from HEAD (from the empty tree without it); `unchanged` is true when there are none, that
    is, when the tree is HEAD's."""
    import shutil
    import tempfile
    run, item = options.get("--run"), options.get("--item")
    scratch = tempfile.mkdtemp(prefix="ddl-snapshot-")
    try:
        git = SnapshotGit(options, os.path.join(scratch, "index"))
        top = git("rev-parse", "--show-toplevel", optional=True)
        if not top or not top.strip():
            raise ValueError("this is not inside a Git work tree; run it in one, or name one with --git-dir "
                             "and --work-tree.")
        git.cwd = os.fsdecode(top.rstrip(b"\n"))
        head = git("rev-parse", "--verify", "--quiet", "HEAD^{commit}", optional=True)
        head = head.decode("ascii").strip() if head else None
        identity = {}
        for role in ("AUTHOR", "COMMITTER"):
            if git("-c", "user.useConfigOnly=true", "var", "GIT_{}_IDENT".format(role), optional=True) is None:
                identity.update({"GIT_{}_NAME".format(role): NEUTRAL_IDENTITY[0],
                                 "GIT_{}_EMAIL".format(role): NEUTRAL_IDENTITY[1]})
        if head:
            git("read-tree", head)
        else:
            git("read-tree", "--empty")
        git("add", "-A")
        tree = git("write-tree").decode("ascii").strip()
        message = "DDL snapshot {} {}".format(run or "adhoc", item or "snap")
        commit = git("commit-tree", "--no-gpg-sign", *(("-p", head) if head else ()), "-m", message, tree,
                     env=identity).decode("ascii").strip()
        changed = git("diff-tree", "-r", "--root", "--no-commit-id", "--no-renames", "--ignore-submodules=none",
                      "--name-only", "-z", commit)
        files = sum(1 for name in changed.split(b"\0") if name)
        ref = "{}/{}/{}-{}".format(SNAPSHOT_REFS, run or "adhoc", ref_stamp(), item or "snap")
        try:
            git("update-ref", "--no-deref", ref, commit, "")  # the empty old value: only where no such ref is
        except ValueError:
            if git("rev-parse", "--verify", "--quiet", ref, optional=True) is not None:
                raise ValueError("{} exists already; nothing was changed.".format(ref)) from None
            raise
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    gate.ledger_event(gate.cwd_ledger()[0], None, None, "snapshot", ref=ref, commit=commit, item=item, run=run)
    return {"snapshot": commit, "ref": ref, "files": files, "unchanged": files == 0}


def snapshot_list(options):
    """`snapshot list`: the repository's snapshot refs (one Run's with --run) as {snapshots: [{ref, commit}]},
    newest first by the stamp in their names; a name without a stamp comes last."""
    git = SnapshotGit(options)
    if git("rev-parse", "--git-dir", optional=True) is None:
        raise ValueError("this is not inside a Git repository; run it in one, or name one with --git-dir "
                         "and --work-tree.")
    prefix = SNAPSHOT_REFS + ("/" + options["--run"] if "--run" in options else "")
    found = []
    for line in git("for-each-ref", "--format=%(objectname) %(refname)", prefix).decode("utf-8", "replace").splitlines():
        commit, _, ref = line.partition(" ")
        found.append({"ref": ref, "commit": commit})

    def newest(entry):
        match = SNAPSHOT_NAME.match(entry["ref"].rsplit("/", 1)[-1])
        return (1, match[1], (match[2] or "").ljust(9, "0"), entry["ref"]) if match else (0, "", "", entry["ref"])

    return {"snapshots": sorted(found, key=newest, reverse=True)}


def main(argv) -> int:
    """One of WORDS and its arguments, as `ddl_gate.py` takes them; anything else is a usage error (exit 2)."""
    if argv and argv[0] == "report":
        try:
            lines = report_command(argv[1:])
            sys.stdout.buffer.write(("\n".join(lines) + "\n").encode("utf-8"))  # whatever the locale's encoding
            sys.stdout.flush()
            return 0
        except Exception as exc:
            print("DDL report: " + str(exc), file=sys.stderr)
            return 2
    if argv and argv[0] in ("run-start", "run-item"):
        try:
            if argv[0] == "run-item":
                gate.emit(run_item(argv[1:]))
                return 0
            runtime = None
            if argv[1:]:  # optional, and then it must be the report's own runtime
                _, runtime, problem = gate.parse_args(["session-start", *argv[1:]])
                if problem:
                    raise ValueError(RUN_USAGE)
            try:
                data = json.loads(sys.stdin.read())
            except ValueError as exc:
                raise ValueError("the input is not JSON ({}).".format(exc)) from None
            gate.emit(run_start(data, runtime))
            return 0
        except Exception as exc:
            print("DDL run: " + str(exc), file=sys.stderr)
            return 2
    if argv and argv[0] == "snapshot":
        try:
            listing = argv[1:2] == ["list"]
            options = snapshot_options(argv[2:] if listing else argv[1:], SNAPSHOT_FLAGS["list" if listing else "make"])
            gate.emit(snapshot_list(options) if listing else snapshot(options))
            return 0
        except Exception as exc:
            print("DDL snapshot: " + str(exc), file=sys.stderr)
            return 2
    print(USAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
