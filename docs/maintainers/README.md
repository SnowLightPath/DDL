# DDL maintainer reference

This page is for people and agents maintaining DDL, its adapters, and its documentation. For installation and everyday use, start with the [project README](../../README.md), [Codex guide](../../codex/README.md), or [Claude Code guide](../../claude-code/README.md).

## Installation reference

The environment installer symlinks the nine skills (eight commands and `ddl-protocol`), `explorer` and `worker` agents, and the gate hook into each selected runtime's home. Codex also receives the `rules/ddl.rules` link. Without runtime flags, the installer selects the runtime home directories that already exist; if neither exists, select `--claude` or `--codex` explicitly.

| Runtime | Merged file | DDL settings |
|---|---|---|
| Claude Code | `~/.claude/settings.json` | Gate hooks, spawn depth 1, `git push` ask rule, attribution off |
| Codex | `~/.codex/hooks.json` | Gate hooks; the push rule is installed separately |

Existing settings are retained. The first change to a settings file keeps a backup beside it as `settings.json.ddl-backup` or `hooks.json.ddl-backup`. The installer does not write Codex `config.toml`; to match SWARM's `max: 5`, set `[agents] max_concurrent_threads_per_session = 5` there yourself. Doctor reports a missing cap as optional.

The install, doctor, and uninstall scripts accept `--claude`, `--codex`, and `--dry-run`. Uninstall removes DDL-owned links and the merged fragment while leaving unrelated settings and files. The hook requires Python 3 and the standard library; if Python is absent, hook execution fails open and the protocol still applies as instructions.

### Updating a linked installation

Pull updates through Git in the DDL clone. Skill and hook links follow the updated files; merged settings require the installer to run again. For the catch-all matcher update, rerun installation even when the hook link already points at the clone. Review changed Codex hooks in `/hooks` before relying on them.

```bash
bash DDL/bin/install.sh
bash DDL/bin/doctor.sh
```

For project-contained layouts, use `bash DDL/bin/install.sh --project your-project` with an optional runtime flag. It skips READMEs and keeps existing instruction files. Repeat the project install to update the copied files. Claude Code trusts project hooks through folder trust; Codex requires project trust and hook trust.

## Source files and generated files

| Source | Generated output |
|---|---|
| `claude-code/skills/<name>/SKILL.md` | Nine Codex skill files and nine `agents/openai.yaml` files |
| `tools/ddl_gate.py` | `claude-code/hooks/ddl_gate.py` and `codex/.codex/hooks/ddl_gate.py` |

The [mirror generator](../../tools/sync_mirrors.py) produces 20 files. Command bodies translate `/command` invocations to `$command`; the protocol body is copied unchanged because it describes both runtimes. Generated YAML prevents implicit invocation of the command skills; the protocol is read by commands in Phase 0.

Runtime instruction templates, settings, agent definitions, rules, and READMEs are maintained directly in their source directories. The canonical behavior lives in the [shared protocol](../../claude-code/skills/ddl-protocol/SKILL.md); command files refer to it rather than duplicating its rules.

### Project overrides and session context

A project's own command skill takes precedence over the environment-installed command. `commands/<name>.md` can add project facts such as target paths, protected terms, and validation commands. Commands use the project's protocol copy when present, otherwise the user-level copy under `~/.claude/skills/` or `~/.codex/skills/`.

Claude Code loads the instruction file and its `design.md` import at session start and after compaction. Codex loads `AGENTS.md`; trusted SessionStart hooks inject `design.md`, or the skill reads it when the hook is unavailable. A worker receives a self-contained prompt with its scope and approved work; it does not depend on inheriting the lead's conversation. See protocol §2.4–2.5 for worker roles, runtime mappings, and fallback behavior.

`design.md` contains the human-agreed Experience and any Binding Decisions, Direction, Acceptance Gates, principles, scopes, and validation the project needs. Automatic memory is a recall layer, not a source of binding agreement. Protocol §3 defines section ownership, passed marks, approved plans, and retirement rules.

## Batch approval

At a required STOP, present one concise overall recommendation and the complete current review set: visible numbered compatible actions with stable IDs, recommended resolutions, and their material impacts. Keep important risks and unknowns in that report and make detailed evidence separately accessible. A set containing several proposals still receives one native approval interaction by default.

Offer **Approve all current recommendations**, **Choose a subset or request changes**, and **Hold**. Explicit approve-all authorizes exactly the displayed ready set and recommended resolutions. It does not authorize undisplayed or future items, later STOPs, unconfirmed outward actions, or silent changes to Binding Decisions. Apply the approved set without follow-up approvals per file, item, or section.

Subset editing is optional and starts only when requested. Use native multi-select/checklist controls or one grouped form when the host supports them; never impose a typed ID list or an automatic N-item, N-turn approval loop. Use Claude Code's native `multiSelect` only when the exposed schema supports it. The observed Codex asynchronous function accepts only `questions`, `title`, and `options`; do not invent a `multiSelect` property for it. Offer compatible subsets as native choices when a grouped selector is unavailable.

The native question is the final interaction while waiting at that STOP. A synchronous question waits for the actual submitted answer. On an asynchronous host that keeps the question answerable after turn completion, end the turn after the request receipt and wait for that answer. Respect the tool's permitted purpose and mode; do not switch modes to bypass a restriction. A receipt, cancellation, dismissal, no selection, or timeout is not approval. An answer must authorize the current displayed set or an explicitly selected subset.

## Close stage

Work ends in a Close stage (protocol §1.7). `/realize` runs it after the last implementation stage, and `/commit` runs its scan before the Git review: reflect the code into `design.md`, audit the documentation the change set touches, align language pairs, validate, then prepare one Git review of the whole change set. Inside `/realize` the approved plan authorizes the Close edits, and the Git review is where the user sees them. Inside `/commit` the findings form one batch approval first. After the commit, the report states that nothing remains or names leftovers with reasons; no next command is suggested. `/reflect`, `/docs`, and `/resonate` remain standalone commands.

## Runtime boundaries

The catch-all matchers inspect tool calls dispatched through the runtime's hooks. While a report awaits human input, the gate permits exact known read tools, human-question tools, input-free polling where supported, and bounded literal shell reads. Unknown tools, worker follow-ups, general scripts, and unsupported shell forms are denied on covered paths. Use display forms such as `cat`, `head`, `tail`, `rg`, or `sed -n '1,10p' file` to clarify a report.

This is a static guardrail, not complete STOP enforcement or a sandbox for ambient executable and configuration behavior. Runtime paths outside the hooks, asynchronous transcript timing, and unexpected errors limit enforcement. General STOP errors fail open with a warning. The protocol's waiting rule still applies, and the agent judges whether a submitted answer approves the current report and scope. Ordinary commits and pushes also have the independent content review below.

Question invocation or receipt alone does not clear pending state. Compaction summaries, worker notifications, and messages from other agents do not approve work. Protocol §1.5 defines report reconstruction, actual input boundaries, advance approval, and the work that remains prohibited while waiting.

### Git content review

The gate's `prepare-git-review` command snapshots the staged contents, exact message, and requested push targets. It returns complete review detail and a runtime-specific `nativeRequest`; pass that request unchanged to the supported question tool. The report must name its generated review ID. Preparation data contains no approval flag. Before recognized ordinary commit/push calls, the hook checks the actual native request/result association and compares the live Git state with that prepared set, even while STOP is OPEN and under `never`. Hold, revision, timeout, receipts, unrelated answers, changed content, missing proof, and resumed preparations do not authorize those calls. A ready commit and its exact dependent push can share one answer.

This changes the default workflow: stage the proposed set for review, preserve unrelated user changes, then keep that index intact after approval. Supported ordinary forms use `git commit --cleanup=verbatim -m ...` or `-F ...` on a named branch, and one configured push remote with one branch/refspec. Follow-tags and recursive submodule pushes must be explicitly suppressed when configuration would otherwise expand the destination set. Unsupported options and operations stop with the reason; they are not silently removed. Review directories are private and remote credentials are omitted from the saved report and metadata.

Unprovable recognized reviews deny inside a running handler. The handler has a shorter Git-verification budget than the adapter timeout, but a runtime-level hook failure or timeout may still fail open. Arbitrary program internals, aliases, existing-process input, Git hooks that rewrite a commit, and concurrent changes between inspection and execution are outside a universal guarantee. The guard is not a tamper-proof authorization service for a hostile process that can edit its own transcript and state.

Regression tests use native-shaped reply fixtures, real disposable Git repositories and local bare remotes, and the installed adapter commands. These are simulated dispatch tests, not new live choice-submission tests in both apps. A separate live Codex desktop observation confirmed that the existing hook transport denies a call while a diagnostic pending marker exists and permits it after cleanup; it does not by itself prove the new content-review feature was deployed or exercised live.

### Push confirmation

The Codex native rule requests confirmation for literal `git push ...`. A separate hook guard rejects recognized static forms that miss that rule, such as Git global options or explicit wrappers. Use a separate canonical invocation with the tool's working directory set to the intended repository only when it preserves the original meaning; otherwise explain the limitation. The guard never rewrites commands or grants permission. Absolute host Git paths keep native executable resolution; arbitrary scripts, aliases, and dynamically built pushes remain outside this form check.

Explicit `bypassPermissions` and documented `dontAsk` modes waive only the push-form guard, not STOP or the Git content review. Sessions whose approval policy never prompts show no execution-time confirmation; the content review still applies. Claude Code retains its native push permission rule and disables attribution through settings; Codex adds no attribution.

### Native question observations

These observations are dated 2026-11-01 and do not establish support for every version or host.

**Claude Code 2.1.316.** Idle timeout settings are `60s`, `5m`, `10m`, and `never` (the default); Remote Control disables the idle timer. A 60-second timeout returned host-only `afkTimeoutMs: 60000`, even with selected but unsubmitted answers and source `user_temporary`. Explicit submission under the same settings omitted the field. The gate excludes non-null `afkTimeoutMs` results from human-input boundaries; interpreting a genuine answer as approval remains the agent's responsibility.

**Codex hosts.** The desktop host used for verification accepted click replies after final messages. Codex CLI 0.166.0 Default displayed an asynchronous selector, then erased it and restored the composer at turn completion; no answer arrived afterward. That route is not approval-capable. DDL explains the limitation and stops unapproved without typed-choice substitution or a mode switch to bypass permitted use.

The observed asynchronous function exposed only `questions`, `title`, and `options`, with no timeout argument. The app-server schema's deprecated `autoResolutionMs` and required `isBlocking` fields are separate from those function arguments. Neither the schema nor this observation establishes universal timeout behavior. A request receipt such as `accepted: true` is not a human answer.

## Validation

[Doctor](../../bin/ddl_setup.py) checks links and merged settings, runs the gate suite, probes saved hook commands in a disposable home, and checks the Codex native push rule separately. It reports `N OK, M not OK` and exits 1 when a check fails. It does not certify native hook trust, dispatch on every transport, or the interactive approval UI.

For source changes, the repository's [Validation section](../../design.md#validation) is the declared check list. Useful focused checks are:

```bash
python3 tools/sync_mirrors.py . --check
python3 -I tools/test_ddl_gate.py
python3 -I tools/test_ddl_setup.py
```

The setup suite runs separately from doctor so its install/doctor/uninstall rehearsal cannot recurse. Its isolated homes and projects exercise configured hook commands, not the native UI. Preserve that distinction when reporting results.

## Documentation and translation

Keep the English/Japanese philosophy pairs aligned in meaning, heading structure, examples, and dated changelog entries. User-facing navigation points to the explanations, not the translation machinery.

Maintainers and translation agents use the [Japanese terminology reference](../ja/GLOSSARY.md). Its canonical path remains `docs/ja/GLOSSARY.md`. Follow it when maintaining the Japanese documents; operational command and skill instructions remain English except for literal artifact text, examples, and glossary data.

[Documentation](../README.md) · [Project README](../../README.md)
