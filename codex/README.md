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
cp DDL/codex/AGENTS.md your-project/AGENTS.md
```

If `AGENTS.md` already exists, merge the DDL guidance rather than overwriting it. Open the project in your Codex GUI and invoke a skill in the prompt:

```text
$draft Search with a Retry button
```

Review the draft before saving it. Use `$realize` when you are ready to review an implementation plan, then `$reflect` to compare the result with the design. Start with `$draft` rather than creating an empty `design.md`.

## Skills

| Skill | Use it to… |
|---|---|
| `$draft` | Describe the experience and review the design before saving |
| `$realize` | Implement an approved plan |
| `$reflect` | Propose updates that align the design and implementation |
| `$validate` | Run project checks and mechanical acceptance gates |
| `$resonate` | Reconcile multilingual documents |
| `$docs` | Review documentation and propose corrections |
| `$refactoring` | Review code quality and propose refactors |
| `$commit` | Commit verified changes; `$commit remote` also proposes a push |

`draft` and `realize` accept a feature; `reflect`, `resonate`, `docs`, and `refactoring` accept a path; `validate` accepts a scope. `ddl-protocol` may appear in the skill list; the command skills read it, and you do not invoke it yourself.

## Decision points

At a required STOP, the report gives one overall recommendation and a visible numbered set of compatible actions with stable IDs. Material impacts, risks, and unknowns stay visible; detailed evidence is available separately. The whole displayed ready set is one review, even when it contains several proposals.

One native interaction offers **approve all current recommendations**, **choose a subset or request changes**, or **hold**, with optional free text. An explicit approve-all covers exactly the displayed ready set and its recommended resolutions, without another approval per file, item, or section. It covers no undisplayed or future work, later STOP, unconfirmed outward action, or silent change to a Binding Decision.

Subset editing starts only when requested and uses the host's actual native capabilities, such as a supported checklist or grouped form. DDL does not invent interface fields, force typed ID lists, or automatically turn the set into separate item-by-item questions. A request receipt, cancellation, dismissal, unanswered question, or timeout approves nothing. If a permitted native interface is unavailable or cannot collect the answer, DDL explains the limitation and stops without a typed-choice fallback.

## Host limits

On 2026-11-01, the Codex desktop host used for verification accepted actual click responses after final messages. This is a result for that host, not a guarantee about every Codex surface.

The tested **Codex CLI 0.166.0 Default** could show a question but could not collect its answer after the response ended. DDL therefore leaves the work unapproved on that route. Other versions may behave differently; support depends on whether the interface can collect the required approval.

See the [native question observations](../docs/maintainers/README.md#native-question-observations) for request receipts, timeout metadata, and the distinction between tool arguments and app-server schema fields.

<details>
<summary>Optional: starting Codex from a terminal</summary>

Where the host supports the required interaction, start in your project:

```bash
codex
```

Then invoke the skill in the prompt. The CLI limitation above still applies to version 0.166.0 Default; starting the CLI does not make that approval route available.

</details>

## Updates and other installation options

After pulling updates in the DDL clone, rerun the installer when the settings fragment changes. Reinstalling is idempotent and keeps unrelated settings.

```bash
bash DDL/bin/install.sh --codex
bash DDL/bin/doctor.sh --codex
```

For a project-contained installation, use the existing installer:

```bash
bash DDL/bin/install.sh --project your-project --codex
```

It copies the adapter and skills, skips the README, and keeps an existing `AGENTS.md`. Codex loads project configuration only for a trusted project; review and trust the hooks in `/hooks` when the host asks. Rerun the project install when updating copied files.

Preview with `--dry-run`, or remove DDL's links and settings fragment with `bash DDL/bin/uninstall.sh --codex`. Details and backup behavior are in the [maintainer reference](../docs/maintainers/README.md#installation-reference).

<details>
<summary>Maintainer details: phases and runtime files</summary>

The skill structure is defined by the shared [DDL protocol](./.agents/skills/ddl-protocol/SKILL.md):

`INIT → SURVEY/READ → WORK → REPORT (+++STOP) → EXECUTE → VERIFY`

`+++DDL_PHASE` is required before a mutating phase and `+++DDL_REPORT` heads the report at a STOP. The protocol defines approval, resume, compaction, and worker rules; the adapter supplies mechanical guardrails on dispatched calls rather than complete STOP enforcement.

This directory mirrors a project's root: [AGENTS.md](./AGENTS.md), generated skills under `.agents/skills/`, and the adapter under `.codex/`. For source ownership, configuration, session loading, and verification, use the [maintainer reference](../docs/maintainers/README.md).

</details>

[Read the philosophy](../docs/README.md) · [Back to DDL](../README.md)
