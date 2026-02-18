---
name: ddl-protocol
description: "Use this skill when executing or authoring DDL commands (draft, realize, reflect, refactoring, docs, commit, resonate). Triggers: any `/command` invocation registered in CLAUDE.md, requests to create new DDL commands, or tasks referencing design.md-driven workflows with Phases, DETECT, STOP, SWARM. Do NOT use for general coding, documentation, or tasks unrelated to DDL workflow execution."
---

# DDL-PROTOCOL

Design-Doc Loop. Human-LLM collaborative workflow protocol.

Commands are programs. This skill is the instruction set. `+++` directives are instructions — when the processor (you) encounters one, execute its defined procedure. Code blocks within directive definitions are tool call templates: resolve variables and execute them.

Markdown headings (`#`, `##`, `###`) mark document structure. `+++` marks executable instructions inside phase bodies.

---

## 1. Directive Reference

| Directive | Syntax | Count | Rule |
|-----------|--------|-------|------|
| `# header` | `# command-name` followed by one-line intent | 1 | Required |
| `## usage` | `## Usage` followed by dash-list of invocations | 1+ lines | Required |
| `### phase` | `### Phase 0: INIT`, `### Phase 1: SURVEY`, etc. | 4–6 | N starts at 0, ascending. Phase 0 INIT is required: load SKILL → CLAUDE.md → design.md in that order. Canonical names: INIT, SURVEY/READ, WORK/IMPLEMENT, REPORT, EXECUTE, VERIFY |
| `+++STOP` | `+++STOP: always` or `+++STOP: on D1` | 1+ | `always` required at REPORT phase. `on D{n}` halts when that DETECT fires. Never auto-proceed past a STOP gate |
| `+++DETECT` | `+++DETECT:` followed by indented `D1: name — trigger` lines | 5–7 | D starts at 1, ascending, unique per command. Trigger must be operationally verifiable. All targets run in parallel within their phase |
| `+++SWARM` | `+++SWARM: condition` followed by `team:`, `spawn:`, `type:`, `max:`, `batch:`, `each:`, `collect:` block. See §2 | 0+ | Instruction: create Agent Team. Evaluate condition against design.md. If false or single scope: execute inline. If true with 2+ scopes: execute §2.4 procedure (TeamCreate → Task × N → Monitor → Collect → Shutdown) |
| `+++NEVER` | `+++NEVER: prohibition in imperative form` | 2–4 | Global constraints in CLAUDE.md. Local constraints in command file |
| `+++Report` | `+++Report:` followed by markdown table rows | 0–1 | Output template presented to human at STOP gate |

---

## 2. +++SWARM Instruction

When you encounter `+++SWARM` in a phase and its condition evaluates to true with 2+ scopes, execute the procedure defined in §2.4. The operand block (`team:`, `spawn:`, `type:`, `max:`, `batch:`, `each:`, `collect:`) provides parameters for each step.

### 2.1 Syntax

```
+++SWARM: 2+ scopes in design.md
  team: command-phase
  spawn: role-{scope}
  type: Explore
  max: 5
  batch: auto
  each: |
    Task description per teammate.
    {scope} resolves to actual scope name at runtime.
    Report findings to team-lead when done.
  collect: lead synthesizes all teammate results
```

### 2.2 Fields

| Field | Position | Required | Description |
|-------|----------|----------|-------------|
| condition | first line after `+++SWARM:` | yes | Predicate evaluated against design.md. If false, skip SWARM and execute inline |
| `team` | block body | yes | Agent Teams team name. Convention: `command-phase` (e.g. `reflect-survey`, `realize-execute`) |
| `spawn` | block body | yes | Teammate name pattern. `{scope}` expands per matching scope in design.md |
| `type` | block body | no | Agent type for teammates. Default: `general-purpose`. Options: `Explore` (read-only, fast), `Plan` (architecture), `Bash` (commands only), or plugin types (e.g. `compound-engineering:review:security-sentinel`) |
| `max` | block body | no | Maximum concurrent teammates. Default: 5. Controls cost and resource usage |
| `batch` | block body | no | How to group scopes when scope count exceeds `max`. Default: `auto`. See §2.3 |
| `each` | block body | yes | Prompt template for each teammate. `{scope}` or `{scopes}` (when batched) resolve at runtime. Must instruct teammate to report results to team-lead |
| `collect` | block body | no | How lead integrates results after all teammates complete. Default: synthesize and present in next phase |

### 2.3 Dynamic Scaling

The team lead evaluates scope count against `max` and `batch` to determine teammate allocation:

```
scope_count = number of design.md scopes matching condition

if scope_count == 0:
    skip SWARM entirely
elif scope_count == 1:
    execute inline, no team
elif scope_count <= max:
    1 teammate per scope
elif batch == "auto":
    lead groups related scopes by proximity/dependency
    ceil(scope_count / max) scopes per teammate
    {scope} in prompt becomes {scopes} (comma-separated list)
elif batch == "none":
    first `max` scopes run in parallel
    remaining scopes queued as tasks, claimed when a teammate finishes
elif batch == "by-tag":
    group scopes by their tag in design.md
    one teammate per tag group (capped at max)
```

| scope_count | max | batch | Result |
|-------------|-----|-------|--------|
| 0 | — | — | Skip SWARM |
| 1 | — | — | Inline, no team |
| 3 | 5 | any | 3 teammates, 1 scope each |
| 8 | 5 | `auto` | 5 teammates, lead groups 8 scopes into 5 batches |
| 8 | 5 | `none` | 5 teammates start, 3 scopes queued as tasks |
| 12 | 4 | `by-tag` | Scopes grouped by tag, up to 4 teammates |

### 2.4 Execution Procedure

+++SWARM の条件が真のとき、以下の手続きを順に実行せよ。
各code blockはツール呼び出しテンプレートである。変数を解決し実行せよ。

**Step 1 — Create team**

TeamCreate でチームを作成する:

```
TeamCreate({ team_name: "{team}" })
```

**Step 2 — Scale**

§2.3 に従いスコープ数を評価し、チームメイト数とスコープ割当を決定する。
`batch: none` でオーバーフローがある場合、タスクを作成する:

```
TaskCreate({ subject: "Process {scope}", description: "{each with scope resolved}" })
```

**Step 3 — Spawn teammates**

Step 2 で決定した各スコープについて、Task でチームメイトを spawn する:

```
Task({
  team_name: "{team}",
  name: "{spawn with scope resolved}",
  subagent_type: "{type}",
  prompt: "{each with scope/scopes resolved}",
  run_in_background: true
})
```

**Step 4 — Monitor**

TaskList と自動配信メッセージでチームメイトの進捗を監視する。
`batch: none` でキュー済みタスクがある場合、チームメイトは完了次第 TaskList から自己claim する。

**Step 5 — Collect**

全チームメイト完了後、`collect:` フィールドの指示に従い結果を統合する。

**Step 6 — Shutdown**

各チームメイトにシャットダウンを要求し、チームリソースを削除する:

```
SendMessage({ type: "shutdown_request", recipient: "{teammate-name}" })
TeamDelete()
```

---

## 3. Command Template

```markdown
# command-name

One-line intent.

## Usage

- `/command` — default behavior
- `/command arg` — specific behavior

## Phases

### Phase 0: INIT

1. Read `.claude/commands/DDL-PROTOCOL-SKILL.md`
2. Read `CLAUDE.md`
3. Read `design.md` — extract relevant items
4. If no `design.md` → fallback behavior

### Phase 1: SURVEY

+++SWARM: 2+ scopes in design.md
  team: command-survey
  spawn: reader-{scope}
  type: Explore
  max: 5
  batch: auto
  each: |
    Scan {scope} for relevant items.
    Report findings to team-lead when done.
  collect: lead merges all scope findings

### Phase 2: WORK

Core activity here.

+++DETECT:
  D1: name — trigger condition
  D2: name — trigger condition
  D3: name — trigger condition
  D4: name — trigger condition
  D5: name — trigger condition

### Phase 3: REPORT

+++STOP: always

+++Report:
| # | col | col | col |

### Phase 4: EXECUTE (if applicable)

+++SWARM: 2+ approved changes across scopes
  team: command-execute
  spawn: writer-{scope}
  type: general-purpose
  max: 5
  batch: auto
  each: |
    Apply approved changes to {scope}.
    Report completion to team-lead when done.
  collect: lead verifies all changes applied

### Phase 5: VERIFY (if applicable)

Re-scan. Summarize. Suggest next command.

## Constraints

+++NEVER: prohibition
+++NEVER: prohibition
+++NEVER: prohibition
```