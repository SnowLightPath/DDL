# DDL for Claude Code

Describe the experience you want, review the plan, and keep the design aligned with the code. DDL adds `/draft`, `/realize`, `/reflect`, and five supporting commands to Claude Code.

## Quick start

Install once; Python 3 is required.

```bash
git clone https://github.com/SnowLightPath/DDL.git
bash DDL/bin/install.sh --claude
```

For a project without a Claude Code instruction file, add the template:

```bash
mkdir -p your-project/.claude
cp DDL/claude-code/CLAUDE.md your-project/.claude/CLAUDE.md
```

Change `# Project Name` in the copied file. If the project already has instructions, merge the DDL guidance rather than overwriting them. The template imports `design.md`; start with `/draft` to create the design instead of adding an empty file.

Open Claude Code in the project, complete its folder-trust prompt when shown, and describe what you want:

```text
/draft Search with a Retry button
```

Review the draft before saving it. Use `/realize` when you are ready to review an implementation plan; it ends with the Close stage, which reflects the result into the design, brings the documents up to date, validates, and asks for one Git review before committing. `/reflect` remains available on its own.

## Commands

| Command | Use it to… |
|---|---|
| `/draft` | Describe the experience and review the design before saving |
| `/realize` | Implement an approved plan and close the work with one Git review |
| `/reflect` | Propose updates that align the design and implementation |
| `/validate` | Run project checks and mechanical acceptance gates |
| `/resonate` | Reconcile multilingual documents |
| `/docs` | Review documentation and propose corrections |
| `/refactoring` | Review code quality and propose refactors |
| `/commit` | Close the work and commit verified changes; `/commit remote` also proposes a push |

`draft` and `realize` accept a feature; `reflect`, `resonate`, `docs`, and `refactoring` accept a path; `validate` accepts a scope. You do not invoke `ddl-protocol` yourself.

## Before recording or sending changes

The agent shows the final staged diff, exact commit message, and any requested push destination in one Git review. Approve the ready set once through the native choices. A ready commit and its push share that approval; files and languages do not get separate questions. Before that review, the Close stage brings `design.md` and the documents up to date, so the commit is the last step and no command follows it.

The hook independently checks the actual contents and submitted choice before ordinary `git commit` and `git push` calls. A general reply or an earlier implementation approval supplies no Git permission. Changed contents, message, destination, or an unprovable answer stop the operation. Git reads remain available. A native permission policy that shows no command prompt does not skip this content check.

## Decision points

At a required STOP, the report gives one overall recommendation and a visible numbered set of compatible actions with stable IDs. Material impacts, risks, and unknowns stay visible; detailed evidence is available separately. The whole displayed ready set is one review, even when it contains several proposals.

Claude Code asks once: **approve all current recommendations**, **choose a subset or request changes**, or **hold**. An explicit approve-all covers exactly that displayed ready set and its recommended resolutions, without another approval per file, item, or section. It covers no undisplayed or future work, later STOP, unconfirmed outward action, or silent change to a Binding Decision.

Only a requested subset or revision opens editing, using a supported native checklist or grouped form with optional free text. DDL does not force typed ID lists or automatically ask about every item in separate turns. A synchronous question waits for the actual answer; a cancelled, dismissed, unanswered, or timed-out question approves nothing. If the native interface is unavailable or not permitted for this purpose, DDL explains the limitation and stops without a typed-choice fallback.

For tested versions, timeout behavior, and technical verification limits, see the [native question notes](../docs/maintainers/README.md#native-question-observations).

## Updates and other installation options

After pulling updates in the DDL clone, rerun the installer when the settings fragment changes. Reinstalling is idempotent and keeps unrelated settings.

```bash
bash DDL/bin/install.sh --claude
bash DDL/bin/doctor.sh --claude
```

For a project-contained installation, use the existing installer:

```bash
bash DDL/bin/install.sh --project your-project --claude
```

It copies the adapter and skills, skips the README, and keeps an existing instruction file. Claude Code runs project hooks after you trust the folder. Rerun the project install when updating copied files.

Preview with `--dry-run`, or remove DDL's links and settings fragment with `bash DDL/bin/uninstall.sh --claude`. Details and backup behavior are in the [maintainer reference](../docs/maintainers/README.md#installation-reference).

<details>
<summary>Maintainer details: phases and runtime files</summary>

The command structure is defined by the shared [DDL protocol](./skills/ddl-protocol/SKILL.md), written as an instruction-set reference. Its entry `SKILL.md` has five sections: Start, Instruction set, Pending STOP, Reading map, and Interruption. The Instruction set table lists the ten directives a command uses (`# header`, `## Usage`, `### Phase`, `+++DETECT`, `+++STOP`, `+++SWARM`, `+++NEVER`, `+++Report`, `+++DDL_PHASE`, `+++DDL_REPORT`) with syntax, count, placement, and rule. Phases follow the roles:

`INIT → SURVEY/READ → WORK → REPORT (+++STOP) → EXECUTE → VERIFY`

`+++DDL_PHASE` marks a mutating phase (recommended in Claude Code, required in Codex) and `+++DDL_REPORT` heads the report at a STOP. Pending STOP and Interruption state the rules while a decision waits and after a compaction or restart; the adapter supplies mechanical guardrails on dispatched calls rather than complete STOP enforcement.

Six references under `references/` hold the procedures: Approval, Parallel work, Notebook, Close, Git review, and Command authoring. Each has the same seven sections in the same order: Read when, Syntax, Fields, Procedure, Formats, Boundaries, Runtime. A seventh file, `examples.md`, holds the worked examples and the complete command template; it is read only when a format is unclear or when writing a command. Eight host files under `references/runtimes/`, one per host and operation (`claude-start.md`, `claude-approval.md`, `claude-parallel.md`, `claude-git.md`, and the `codex-*` set), have Read when, Mapping, Observed, and Coverage; the Mapping is the only place tool names appear. The start files are named `*-start.md` because Claude Code reads a file named `claude.md` as a nested `CLAUDE.md` on a case-insensitive filesystem.

A command reads the entry and `claude-start.md` in Phase 0, then each reference and the matching host file right before the operation: Approval before a STOP report, Parallel work before fan-out, Notebook before writing `design.md`, Close on entering Close, Git review before a commit or push, Command authoring when writing a command, and `examples.md` when a format is unclear. These are files within the selected protocol, not additional slash commands. `python3 tools/check_ddl.py protocol` prints `PROTOCOL_OK` when the entry table, the fixed sections, the operand and section rows, the literal strings commands write (such as `passed <date>`), the boundary rows, and the dated observations are all present, the files read on each path and in total stay within their byte budgets on both hosts, and no sentence of 60 characters or more appears twice; `tools/test_protocol.py` holds negative cases that must fail, and `python3 tools/check_ddl.py commands` also checks the template in `examples.md`.

This directory mirrors a project's `.claude/`: [CLAUDE.md](./CLAUDE.md), [settings.json](./settings.json), command skills, agent definitions, and the gate hook. For source ownership, project overlays, session loading, and verification, use the [maintainer reference](../docs/maintainers/README.md).

</details>

[Read the philosophy](../docs/README.md) · [Back to DDL](../README.md)
