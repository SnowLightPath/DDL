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

Review the draft before saving it. Use `/realize` when you are ready to review an implementation plan, then `/reflect` to compare the result with the design.

## Commands

| Command | Use it to… |
|---|---|
| `/draft` | Describe the experience and review the design before saving |
| `/realize` | Implement an approved plan |
| `/reflect` | Propose updates that align the design and implementation |
| `/validate` | Run project checks and mechanical acceptance gates |
| `/resonate` | Reconcile multilingual documents |
| `/docs` | Review documentation and propose corrections |
| `/refactoring` | Review code quality and propose refactors |
| `/commit` | Commit verified changes; `/commit remote` also proposes a push |

`draft` and `realize` accept a feature; `reflect`, `resonate`, `docs`, and `refactoring` accept a path; `validate` accepts a scope. You do not invoke `ddl-protocol` yourself.

## Decision points

The report explains what needs deciding, the recommendation and reason, and what approval authorizes. Material risks and unknowns stay visible; detailed evidence is available separately.

Claude Code presents one native question at a time, with optional free text. Only an explicit submitted answer approving the current report and scope permits work. A cancelled, dismissed, unanswered, or timed-out question approves nothing. Asking for details or revisions leads back to the report and question. If the native interface is unavailable or not permitted, DDL explains the limitation and stops without a typed-choice fallback.

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

The command structure is defined by the shared [DDL protocol](./skills/ddl-protocol/SKILL.md):

`INIT → SURVEY/READ → WORK → REPORT (+++STOP) → EXECUTE → VERIFY`

`+++DDL_PHASE` marks a mutating phase and `+++DDL_REPORT` heads the report at a STOP. The protocol defines approval, resume, compaction, and worker rules; the adapter supplies mechanical guardrails on dispatched calls rather than complete STOP enforcement.

This directory mirrors a project's `.claude/`: [CLAUDE.md](./CLAUDE.md), [settings.json](./settings.json), command skills, agent definitions, and the gate hook. For source ownership, project overlays, session loading, and verification, use the [maintainer reference](../docs/maintainers/README.md).

</details>

[Read the philosophy](../docs/README.md) · [Back to DDL](../README.md)
