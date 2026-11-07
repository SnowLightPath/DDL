# DDL for Codex

Use DDL in the **Codex GUI** to describe what you want, review recommendations together, and keep the design aligned with the code.

> [!NOTE]
> **CLI notice:** The tested Codex CLI 0.166.0 Default cannot accept approval choices after a response ends.
>
> Use the GUI for decisions that need approval. See [supported use and limitations](#host-limits).

## Quick start

Install once; Python 3 is required.

```bash
git clone https://github.com/SnowLightPath/DDL.git
bash DDL/bin/install.sh --codex
```

If Codex asks about new hooks, review them in `/hooks` before relying on their enforcement.

For a project without an `AGENTS.md`, add the template:

```bash
cp DDL/hosts/codex/guidance.md your-project/AGENTS.md
```

If `AGENTS.md` already exists, merge the DDL guidance rather than overwriting it. Open the project in your Codex GUI and invoke a skill in the prompt:

```text
$draft Search with a Retry button
```

Review the draft before saving it. Use `$realize` when you are ready to review an implementation plan; it ends with the Close stage, which reflects the result into the design, brings the documents up to date, validates, and asks for one Git review before committing. `$reflect` remains available on its own. Start with `$draft` rather than creating an empty `design.md`.

## Skills

| Skill | Use it to… |
|---|---|
| `$draft` | Describe the experience and review the design before saving |
| `$realize` | Implement an approved plan and close the work with one Git review |
| `$reflect` | Propose updates that align the design and implementation |
| `$validate` | Run project checks and mechanical acceptance gates |
| `$resonate` | Reconcile multilingual documents |
| `$docs` | Review documentation and propose corrections |
| `$refactoring` | Review code quality and propose refactors |
| `$commit` | Close the work and commit verified changes; `$commit remote` also proposes a push |

`draft` and `realize` accept a feature; `reflect`, `resonate`, `docs`, and `refactoring` accept a path; `validate` accepts a scope. `ddl-protocol` may appear in the skill list; the command skills read it, and you do not invoke it yourself.

## Scope

The hook acts only in a DDL project: one whose instruction file (`AGENTS.md`, `CLAUDE.md`, or `.claude/CLAUDE.md`, searched from the working directory up to the repository root or `$HOME`) contains the line `→ DDL-PROTOCOL`. The template above carries that line; the presence of `design.md` decides nothing. In any other project the hook returns at once on every event: no STOP state, no Git review, no `design.md` injection at session start, and `git commit` and `git push` run as usual. The decision is cached for the session and recomputed at each prompt and session start. `python3 .codex/hooks/ddl_gate.py status` (the same file sits under `$HOME/.codex/hooks/` with the environment install) prints one line saying whether the current directory is a DDL project and which file and line decided; `bash DDL/bin/doctor.sh --codex` prints the same line.

## Before recording or sending changes

The agent shows the final staged diff, exact commit message, and any requested push destination in one Git review. Approve the ready set once through the native choices. A ready commit and its push share that approval; files and languages do not get separate questions. Before that review, the Close stage brings `design.md` and the documents up to date, so the commit is the last step and no skill follows it.

The hook independently checks the actual contents and submitted choice before ordinary `git commit` and `git push` calls. A general reply or an earlier implementation approval supplies no Git permission. Changed contents, message, destination, or an unprovable answer stop the Git action. Git reads remain available. A native permission policy that shows no command prompt does not skip this content check.

## Decision points

At a required STOP, the report gives one overall recommendation and a visible numbered set of compatible actions with stable IDs. Material impacts, risks, and unknowns stay visible; the complete report, with the detailed evidence, is written to a file before the question. The native question itself carries five lines: what to decide, the recommendation and its reason, the consequence, a confirmation ID, and the absolute path of that report file. It alone is enough to decide, even where the chat text does not reach you. The whole displayed ready set is one review, even when it contains several proposals.

One native interaction offers **approve all current recommendations**, **choose a subset or request changes**, or **hold**, with optional free text. An explicit approve-all covers exactly the displayed ready set and its recommended resolutions, without another approval per file, item, or section. It covers no undisplayed or future work, later STOP, unconfirmed outward action, or silent change to a Binding Decision.

Subset editing starts only when requested and uses the host's actual native capabilities, such as a supported checklist or grouped form. DDL does not invent interface fields, force typed ID lists, or automatically turn the set into separate item-by-item questions. A request receipt, cancellation, dismissal, unanswered question, or timeout approves nothing. If a permitted native interface is unavailable or cannot collect the answer, DDL explains the limitation and stops without a typed-choice fallback.

## Host limits

On 2026-11-01, the Codex desktop host used for verification accepted actual click responses after final messages. This is a result for that host, not a guarantee about every Codex surface.

The tested **Codex CLI 0.166.0 Default** could show a question but could not collect its answer after the response ended. DDL therefore leaves the work unapproved on that route, including Git recording and sending: typed approval cannot replace the missing native Git-review answer. Other versions may behave differently; support depends on whether the interface can collect the required approval.

See the [native question observations](../../docs/maintainers/README.md#native-question-observations) for request receipts, timeout metadata, and the distinction between tool arguments and app-server schema fields.

<details>
<summary>Optional: starting Codex from a terminal</summary>

Where the host supports the required interaction, start in your project:

```bash
codex
```

Then invoke the skill in the prompt. The CLI limitation above still applies to version 0.166.0 Default; starting the CLI does not make that approval route available.

</details>

## Updates and other installation options

After pulling updates in the DDL clone, rerun the installer: it rebuilds the generated layout and refreshes the merged settings fragment. Reinstalling is idempotent and keeps unrelated settings. Doctor also reports when the generated layout is older than its sources.

```bash
bash DDL/bin/install.sh --codex
bash DDL/bin/doctor.sh --codex
```

For a project-contained installation, use the same installer:

```bash
bash DDL/bin/install.sh --project your-project --codex
```

It builds `dist/codex/` and copies it into the project's root: `AGENTS.md` (kept when the project already has one), the adapter under `.codex/`, and the nine skills under `.agents/skills/`. Codex loads project configuration only for a trusted project; review and trust the hooks in `/hooks` when the host asks. Rerun the project install when updating copied files.

Preview with `--dry-run`, or remove DDL's links and settings fragment with `bash DDL/bin/uninstall.sh --codex`. Details and backup behavior are in the [maintainer reference](../../docs/maintainers/README.md#installation-reference).

<details>
<summary>Maintainer details: this directory, the generated layout, and the protocol</summary>

This directory holds everything that is specific to Codex: the four protocol implementations, the instruction-file template, the adapter files, and this guide. Everything else DDL deploys is host-neutral and lives in `skills/`, `protocol/`, and `tools/ddl_gate.py`.

```
hosts/codex/
├── start.md           Phase 0 after the entry: paths, hook events, markers
├── approval.md        the choice tool, receipt and selector limits, mutating tools, permitted calls
├── parallel-work.md   type, spawn, background, completion on Codex subagents
├── git-review.md      the helper path, the native request, the push rule
├── guidance.md        the instruction-file template, deployed as AGENTS.md
├── hooks.json         the adapter's hook wiring
├── config.toml        the agent cap that matches SWARM max: 5
├── agents/            explorer.toml and worker.toml
├── rules/             ddl.rules, the native git push confirmation rule
└── README.md          this guide (not deployed)
```

`python3 tools/build.py` generates the layout a project receives under `dist/codex/`; the environment installer links into it, and `--project` copies it into a project's root:

```
dist/codex/                       → a project's root
├── AGENTS.md                     from hosts/codex/guidance.md
├── .codex/
│   ├── config.toml               from hosts/codex/config.toml
│   ├── hooks.json                from hosts/codex/hooks.json
│   ├── hooks/ddl_gate.py         from tools/ddl_gate.py
│   ├── agents/                   explorer.toml and worker.toml
│   └── rules/ddl.rules           from hosts/codex/rules/ddl.rules
└── .agents/skills/
    ├── <name>/SKILL.md           the eight skills, from skills/<name>/SKILL.md with /name turned into $name
    ├── <name>/agents/openai.yaml no implicit invocation, generated for every skill
    └── ddl-protocol/
        ├── SKILL.md              entry: Start, the instruction set (ten directives), Pending STOP, Reading map, Interruption,
        │                         and Host, folded from hosts/codex/start.md
        ├── agents/openai.yaml    read in Phase 0, never invoked
        ├── approval.md           a STOP report or human gate: present, ask, wait, resume; Implementation folded from hosts/codex/approval.md
        ├── parallel-work.md      a +++SWARM of two or more units: roles, prompts, fallback; Implementation folded from hosts/codex/parallel-work.md
        ├── notebook.md           reading and writing design.md: sections, marks, retirement
        ├── close.md              the Close stage: reflect, docs, resonate, validate, one Git review
        ├── git-review.md         the content review before any ordinary commit or push; Implementation folded from hosts/codex/git-review.md
        └── command-authoring.md  writing a skill: grammar, checks, the template (Example)
```

The installed protocol has no `hosts/` directory: the generator folds this host's four implementations into the entry and the operations, and the other host's implementations are absent.

The skill structure is defined by the shared [DDL protocol](../../protocol/SKILL.md), written as an instruction-set reference and rendered for Codex by the generator. Its entry `SKILL.md` has five sections: Start, Instruction set, Pending STOP, Reading map, and Interruption; the generated entry adds a Host section, folded from `hosts/codex/start.md`. The Instruction set table lists the ten directives a skill uses (`# header`, `## Usage`, `### Phase`, `+++DETECT`, `+++STOP`, `+++SWARM`, `+++NEVER`, `+++Report`, `+++DDL_PHASE`, `+++DDL_REPORT`) with syntax, count, placement, and rule. Phases follow the roles:

`INIT → SURVEY/READ → WORK → REPORT (+++STOP) → EXECUTE → VERIFY`

`+++DDL_PHASE` is required before a mutating phase (recommended in Claude) and `+++DDL_REPORT` heads the report at a STOP, once the report is prepared and before its five-line question. Pending STOP and Interruption state the rules while a decision waits and after a compaction or restart; the adapter supplies mechanical guardrails on dispatched calls rather than complete STOP enforcement, opening a pending STOP from the prepared report, a question carrying its ID or the marker, never from a thinking block or reasoning item.

Six operations beside the entry hold the rules: Approval, Parallel work, Notebook, Close, Git review, and Command authoring. Each has the same eight sections in the same order: Read when, Syntax, Operands, Operation, Formats, Example, Exceptions, Implementation; the Example holds one short worked example, and the Example of Command authoring is the complete command template. The four implementations under `hosts/codex/` have Read when, Mapping, Observed, and Coverage: `start.md` for the entry's Start and one for each operation with host-specific differences (`approval.md`, `parallel-work.md`, `git-review.md`), named after it; Close reads Git review's, and Notebook and Command authoring need only `start.md`, already read. Tool names appear only in the implementations under `hosts/`. Implementations refer to operations by name and carry no links. In the source, the Reading map names the implementation through `{host}` placeholders; the generated skill folds this host's four into the files that read them, `start.md` as the entry's Host section and `approval.md`, `parallel-work.md`, and `git-review.md` as the Implementation section (Mapping, Observed, Coverage) of the operation of the same name, so each generated Reading map row points at an `#implementation` or `#host` fragment. No file under `hosts/codex/` or `hosts/claude/` is named `claude.md`, which Claude reads as a nested `CLAUDE.md` on a case-insensitive filesystem; the instruction-file template is therefore `guidance.md`, and no file in the protocol may ever be named `claude.md` or `CLAUDE.md`.

A skill reads one file in Phase 0, the entry with its Host section, and one file before each action, the operation with its Implementation section: Approval before a STOP report, Parallel work before fan-out, Notebook before writing `design.md`, Close on entering Close, Git review before a commit or push, and Command authoring when writing a skill. These are files within the selected protocol, not additional `$` commands.

Checks: `python3 tools/check_ddl.py source` prints `SOURCE_OK` when the maintained skills, protocol, implementations, and templates have their required structure (the entry table, the fixed sections, the operand and section rows, the literal strings skills write such as `passed <date>`, the exception rows, the dated observations, no tool name outside `hosts/`, no sentence of 60 characters or more twice, and the template in the Example of `command-authoring.md`); `python3 tools/check_ddl.py dist` prints `DIST_OK` when the generated layouts match, each host's protocol folds only its own implementations into the entry and the operations and holds no `hosts/` directory, and the files read on each path and in total stay within their byte budgets; `python3 tools/check_ddl.py docs` prints `DOCUMENTS_OK` for the documents; `tools/test_protocol.py` holds negative cases that must fail.

For source ownership, configuration, session loading, and verification, use the [maintainer reference](../../docs/maintainers/README.md).

</details>

[Read the philosophy](../../docs/README.md) · [Back to DDL](../../README.md)
