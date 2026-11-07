# DDL for Claude

Describe the experience you want, review the plan, and keep the design aligned with the code. DDL adds `/draft`, `/realize`, `/reflect`, and five supporting commands to Claude.

## Quick start

Install once; Python 3 is required.

```bash
git clone https://github.com/SnowLightPath/DDL.git
bash DDL/bin/install.sh --claude
```

For a project without a Claude instruction file, add the template:

```bash
mkdir -p your-project/.claude
cp DDL/hosts/claude/guidance.md your-project/.claude/CLAUDE.md
```

Change `# Project Name` in the copied file. If the project already has instructions, merge the DDL guidance rather than overwriting them. The template imports `design.md`; start with `/draft` to create the design instead of adding an empty file.

Open Claude in the project, complete its folder-trust prompt when shown, and describe what you want:

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

## Scope

The hook acts only in a DDL project: one whose instruction file (`CLAUDE.md`, `.claude/CLAUDE.md`, or `AGENTS.md`, searched from the working directory up to the repository root or `$HOME`) contains the line `→ DDL-PROTOCOL`. The template above carries that line; the presence of `design.md` decides nothing. In any other project the hook returns at once on every event: no STOP state, no Git review, and `git commit` and `git push` run as usual. The decision is cached for the session and recomputed at each prompt and session start. `python3 .claude/hooks/ddl_gate.py status` (the same file sits under `$HOME/.claude/hooks/` with the environment install) prints one line saying whether the current directory is a DDL project and which file and line decided; `bash DDL/bin/doctor.sh --claude` prints the same line.

## Before recording or sending changes

The agent shows the final staged diff, exact commit message, and any requested push destination in one Git review. Approve the ready set once through the native choices. A ready commit and its push share that approval; files and languages do not get separate questions. Before that review, the Close stage brings `design.md` and the documents up to date, so the commit is the last step and no command follows it.

The hook independently checks the actual contents and submitted choice before ordinary `git commit` and `git push` calls. A general reply or an earlier implementation approval supplies no Git permission. Changed contents, message, destination, or an unprovable answer stop the Git action. Git reads remain available. A native permission policy that shows no command prompt does not skip this content check. Inside a DDL project the hook itself asks natively before the reviewed push; DDL installs no separate `git push` permission rule, and the hook's behavior under modes that bypass permissions is unverified.

## Decision points

At a required STOP, the report gives one overall recommendation and a visible numbered set of compatible actions with stable IDs. Material impacts, risks, and unknowns stay visible; the complete report, with the detailed evidence, is written to a file before the question. The native question itself carries five lines: what to decide, the recommendation and its reason, the consequence, a confirmation ID, and the absolute path of that report file. It alone is enough to decide, even where the chat text does not reach you. The whole displayed ready set is one review, even when it contains several proposals.

Claude asks once: **approve all current recommendations**, **choose a subset or request changes**, or **hold**. An explicit approve-all covers exactly that displayed ready set and its recommended resolutions, without another approval per file, item, or section. It covers no undisplayed or future work, later STOP, unconfirmed outward action, or silent change to a Binding Decision.

Only a requested subset or revision opens editing, using a supported native checklist or grouped form with optional free text. DDL does not force typed ID lists or automatically ask about every item in separate turns. A synchronous question waits for the actual answer; a cancelled, dismissed, unanswered, or timed-out question approves nothing. If the native interface is unavailable or not permitted for this purpose, DDL explains the limitation and stops without a typed-choice fallback.

For tested versions, timeout behavior, and technical verification limits, see the [native question notes](../../docs/maintainers/README.md#native-question-observations).

## Updates and other installation options

After pulling updates in the DDL clone, rerun the installer: it rebuilds the generated layout and refreshes the merged settings fragment. Reinstalling is idempotent and keeps unrelated settings. Doctor also reports when the generated layout is older than its sources.

```bash
bash DDL/bin/install.sh --claude
bash DDL/bin/doctor.sh --claude
```

For a project-contained installation, use the same installer:

```bash
bash DDL/bin/install.sh --project your-project --claude
```

It builds `dist/claude/` and copies its `.claude/` into the project: the instruction file (kept when the project already has one), `settings.json`, `agents/`, `hooks/`, and the nine skills. Claude runs project hooks after you trust the folder. Rerun the project install when updating copied files.

Preview with `--dry-run`, or remove DDL's links and settings fragment with `bash DDL/bin/uninstall.sh --claude`. Details and backup behavior are in the [maintainer reference](../../docs/maintainers/README.md#installation-reference).

<details>
<summary>Maintainer details: this directory, the generated layout, and the protocol</summary>

This directory holds everything that is specific to Claude: the four protocol implementations, the instruction-file template, the adapter files, and this guide. Everything else DDL deploys is host-neutral and lives in `skills/`, `protocol/`, and `tools/ddl_gate.py`.

```
hosts/claude/
├── start.md           Phase 0 after the entry: paths, hook events, markers
├── approval.md        the choice tool, its timeout, mutating tools, permitted calls
├── parallel-work.md   type, spawn, background, completion on Claude subagents
├── git-review.md      the helper path, the native request, the hook's ask for the reviewed push
├── guidance.md        the instruction-file template, deployed as .claude/CLAUDE.md
├── settings.json      the adapter: hook wiring, plus spawn depth 1 and attribution off, which stay global in the merged user-level settings
├── agents/            explorer.md and worker.md
└── README.md          this guide (not deployed)
```

`python3 tools/build.py` generates the layout a project receives under `dist/claude/.claude/`; the environment installer links into it, and `--project` copies it into a project's `.claude/`:

```
dist/claude/.claude/              → a project's .claude/
├── CLAUDE.md                     from hosts/claude/guidance.md
├── settings.json                 from hosts/claude/settings.json
├── agents/                       explorer.md and worker.md
├── hooks/ddl_gate.py             from tools/ddl_gate.py
└── skills/
    ├── <name>/SKILL.md           the eight commands, from skills/<name>/SKILL.md, byte for byte
    └── ddl-protocol/
        ├── SKILL.md              entry: Start, the instruction set (ten directives), Pending STOP, Reading map, Interruption,
        │                         and Host, folded from hosts/claude/start.md
        ├── approval.md           a STOP report or human gate: present, ask, wait, resume; Implementation folded from hosts/claude/approval.md
        ├── parallel-work.md      a +++SWARM of two or more units: roles, prompts, fallback; Implementation folded from hosts/claude/parallel-work.md
        ├── notebook.md           reading and writing design.md: sections, marks, retirement
        ├── close.md              the Close stage: reflect, docs, resonate, validate, one Git review
        ├── git-review.md         the content review before any ordinary commit or push; Implementation folded from hosts/claude/git-review.md
        └── command-authoring.md  writing a command: grammar, checks, the template (Example)
```

The installed protocol has no `hosts/` directory: the generator folds this host's four implementations into the entry and the operations, and the other host's implementations are absent.

The command structure is defined by the shared [DDL protocol](../../protocol/SKILL.md), written as an instruction-set reference. Its entry `SKILL.md` has five sections: Start, Instruction set, Pending STOP, Reading map, and Interruption; the generated entry adds a Host section, folded from `hosts/claude/start.md`. The Instruction set table lists the ten directives a command uses (`# header`, `## Usage`, `### Phase`, `+++DETECT`, `+++STOP`, `+++SWARM`, `+++NEVER`, `+++Report`, `+++DDL_PHASE`, `+++DDL_REPORT`) with syntax, count, placement, and rule. Phases follow the roles:

`INIT → SURVEY/READ → WORK → REPORT (+++STOP) → EXECUTE → VERIFY`

`+++DDL_PHASE` marks a mutating phase (recommended in Claude, required in Codex) and `+++DDL_REPORT` heads the report at a STOP, once the report is prepared and before its five-line question. Pending STOP and Interruption state the rules while a decision waits and after a compaction or restart; the adapter supplies mechanical guardrails on dispatched calls rather than complete STOP enforcement, opening a pending STOP from the prepared report, a question carrying its ID or the marker, never from a thinking block or reasoning item.

Six operations beside the entry hold the rules: Approval, Parallel work, Notebook, Close, Git review, and Command authoring. Each has the same eight sections in the same order: Read when, Syntax, Operands, Operation, Formats, Example, Exceptions, Implementation; the Example holds one short worked example, and the Example of Command authoring is the complete command template. The four implementations under `hosts/claude/` have Read when, Mapping, Observed, and Coverage: `start.md` for the entry's Start and one for each operation with host-specific differences (`approval.md`, `parallel-work.md`, `git-review.md`), named after it; Close reads Git review's, and Notebook and Command authoring need only `start.md`, already read. Tool names appear only in the implementations under `hosts/`. Implementations refer to operations by name and carry no links. In the source, the Reading map names the implementation through `{host}` placeholders; the generated skill folds this host's four into the files that read them, `start.md` as the entry's Host section and `approval.md`, `parallel-work.md`, and `git-review.md` as the Implementation section (Mapping, Observed, Coverage) of the operation of the same name, so each generated Reading map row points at an `#implementation` or `#host` fragment. No file under `hosts/claude/` is named `claude.md`, which Claude reads as a nested `CLAUDE.md` on a case-insensitive filesystem; the instruction-file template is therefore `guidance.md`, and no file in the protocol may ever be named `claude.md` or `CLAUDE.md`.

A command reads one file in Phase 0, the entry with its Host section, and one file before each action, the operation with its Implementation section: Approval before a STOP report, Parallel work before fan-out, Notebook before writing `design.md`, Close on entering Close, Git review before a commit or push, and Command authoring when writing a command. These are files within the selected protocol, not additional slash commands.

Checks: `python3 tools/check_ddl.py source` prints `SOURCE_OK` when the maintained skills, protocol, implementations, and templates have their required structure (the entry table, the fixed sections, the operand and section rows, the literal strings commands write such as `passed <date>`, the exception rows, the dated observations, no tool name outside `hosts/`, no sentence of 60 characters or more twice, and the template in the Example of `command-authoring.md`); `python3 tools/check_ddl.py dist` prints `DIST_OK` when the generated layouts match, each host's protocol folds only its own implementations into the entry and the operations and holds no `hosts/` directory, and the files read on each path and in total stay within their byte budgets; `python3 tools/check_ddl.py docs` prints `DOCUMENTS_OK` for the documents; `tools/test_protocol.py` holds negative cases that must fail.

For source ownership, project overlays, session loading, and verification, use the [maintainer reference](../../docs/maintainers/README.md).

</details>

[Read the philosophy](../../docs/README.md) · [Back to DDL](../../README.md)
