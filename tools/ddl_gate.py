#!/usr/bin/env python3
"""DDL gate: the hook's entry, the file the adapters' settings, the protocol and the commands name.

The gate's code is `ddl_gate_core.py` beside this file (symbolic links resolved) and its Run subcommands
are `ddl_run.py`; the core's docstring documents the events, the subcommands and the decisions. This file
takes the same arguments: `<event> --runtime claude|codex` for the hook events, and the subcommands status,
prepare-report, prepare-git-review, report, run-start, run-item and snapshot.

It exists for start-up time: Python compiles a script's source on every start but loads an imported
module's compiled bytecode. The launcher keeps bytecode in the private cache `<state dir>/pycache` (the
state dir is $DDL_GATE_STATE_DIR, else $TMPDIR/ddl-gate, else /tmp/ddl-gate) while that is a directory of
this user that nobody else may enter and this user may write, in a state directory of this user that nobody
else may write; the gate creates it when it acts in a DDL project. While the cache is in use, every module the
gate imports from a source file keeps its bytecode there, and a cached file that cannot be loaded (spoiled or
cut short) is passed over: the module's source is compiled instead, so the cache's content can slow a call but
never change a decision. Otherwise the interpreter's own bytecode settings apply, except that no bytecode is
written beside a source: never a `__pycache__` beside the sources (dist/, a project's copy, the repository).
A gate whose code cannot be loaded at all fails open: a hook event gets a warning and is allowed, a
subcommand exits 2.
"""
import os
import stat  # loaded by os already
import sys

CACHE = "pycache"  # the same name as ddl_gate_core.CACHE
# The words the core answers as subcommands (status, the preparations, and ddl_gate_core.RUN_WORDS). They are
# named here because a missing core cannot name them; tools/test_ddl_run.py pins them to the core's. Any other
# first argument, a hook event or not, fails open when the core is missing: a hook must never deny by accident.
SUBCOMMANDS = ("status", "prepare-report", "prepare-git-review", "report", "run-start", "run-item", "snapshot")


def cache_path():
    """`<state dir>/pycache`, with the state directory found as ddl_gate_core.state_base finds it."""
    base = os.environ.get("DDL_GATE_STATE_DIR") or os.path.join(os.environ.get("TMPDIR") or "/tmp", "ddl-gate")
    return os.path.join(os.path.abspath(base), CACHE)


def usable_cache():
    """The bytecode cache's path while the launcher may use it, else None; nothing is created here."""
    path = cache_path()
    base = os.path.dirname(path)
    try:
        cache, parent = os.lstat(path), os.lstat(base)  # neither may be a symbolic link
    except OSError:
        return None
    uid = os.getuid() if hasattr(os, "getuid") else None
    if uid is None or not (stat.S_ISDIR(cache.st_mode) and stat.S_ISDIR(parent.st_mode)) \
            or (cache.st_uid, parent.st_uid) != (uid, uid) or cache.st_mode & 0o077 or parent.st_mode & 0o022 \
            or not os.access(path, os.W_OK | os.X_OK):
        return None
    return path


def pass_over_bad_bytecode():
    """Make every later import of a module from a source file compile that source when its cached bytecode
    cannot be loaded; False when this interpreter's import system does not allow it (then no cache is used).

    A finder placed just before the standard path finder hands out the standard source loader with one change:
    bytecode that does not unmarshal into code (a valid header, a spoiled body) means the source is compiled,
    where the standard loader would raise and fail the import. Built-in and frozen modules are found first,
    as before; nothing else about an import changes."""
    external = sys.modules.get("_frozen_importlib_external")
    try:
        standard = external.PathFinder
        position = sys.meta_path.index(standard)
        base = external.SourceFileLoader
    except (AttributeError, ValueError):
        return False

    class SourceAfterBadBytecode(base):
        def get_code(self, fullname):
            try:
                return super().get_code(fullname)
            except (EOFError, ValueError, TypeError, ImportError):  # what unmarshalling a spoiled file raises
                path = self.get_filename(fullname)
                return self.source_to_code(self.get_data(path), path)

    class Finder:
        @staticmethod
        def find_spec(name, path=None, target=None):
            spec = standard.find_spec(name, path, target)
            if spec is not None and type(spec.loader) is base:
                spec.loader = SourceAfterBadBytecode(spec.loader.name, spec.loader.path)
            return spec

    sys.meta_path.insert(position, Finder)
    return True


def load_core():
    """ddl_gate_core from beside this file, with every module's bytecode in the cache when it may be used, else
    with the interpreter's own bytecode settings, except that no bytecode is written beside a source (a prefix
    of its own, such as the one macOS /usr/bin/python3 keeps under ~/Library/Caches, stays in use)."""
    here = os.path.dirname(os.path.realpath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    prefix, quiet = sys.pycache_prefix, sys.dont_write_bytecode
    cache = usable_cache()
    if cache is not None and pass_over_bad_bytecode():
        # Bytecode goes only under the private prefix, for the whole run, so it may be written even where the
        # interpreter writes none by default (macOS /usr/bin/python3 with -I).
        sys.pycache_prefix, sys.dont_write_bytecode = cache, False
        try:
            import ddl_gate_core
            return ddl_gate_core
        except Exception:
            pass  # a core that cannot be loaded this way: compile it with the interpreter's own settings
    sys.pycache_prefix, sys.dont_write_bytecode = prefix, quiet or prefix is None
    import ddl_gate_core
    return ddl_gate_core


def main(argv):
    try:
        core = load_core()
    except Exception as exc:  # fail-open: a gate whose code is missing or broken must never deny by accident
        problem = "{}: {}".format(type(exc).__name__, exc)
        if argv[:1] and argv[0] in SUBCOMMANDS:
            print("DDL gate: the gate's code could not be loaded ({}); install DDL again.".format(problem),
                  file=sys.stderr)
            return 2
        import json
        print(json.dumps({"systemMessage": "DDL gate: internal error ({}); the call was allowed (fail-open)."
                          .format(problem)}))
        return 0
    core.ENTRY = __file__
    return core.main(argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
