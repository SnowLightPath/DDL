# DDL Commands — Design Document

## Intent

DDLコマンド群（draft, realize, reflect, resonate, commit, docs, refactoring）の設計仕様を定義する。
全コマンドはDDL-PROTOCOL-SKILL.mdに準拠した`+++`ディレクティブ記法で記述される。

## Scopes

| Scope | File | Description |
|-------|------|-------------|
| protocol-skill | .claude/commands/DDL-PROTOCOL-SKILL.md | プロトコル仕様（`+++`記法・SWARM・コマンド構造の定義元） |
| claude-config | .claude/CLAUDE.md | グローバル設定（Detection Targets, Constraints, Behavior） |
| draft | .claude/commands/draft.md | 体験をdesign.mdに記録する |
| realize | .claude/commands/realize.md | design.mdの設計をコードとして実装する |
| reflect | .claude/commands/reflect.md | 実装とdesign.mdの乖離を検出・修正する |
| resonate | .claude/commands/resonate.md | en/ja多言語ドキュメントを同期する |
| refactoring | .claude/commands/refactoring.md | コード品質の監査・修正 |
| docs | .claude/commands/docs.md | ドキュメント品質の監査・修正 |
| commit | .claude/commands/commit.md | 検証済みコード変更のgitコミット |
| examples | examples/claude-commands/*.md | production同期コピー（resonate除外） |

README.mdは本スコープ外とする。

## Principles

### P1: DDL-PROTOCOL-SKILL.mdが単一の定義元

全コマンドの構造（Phase, `+++`ディレクティブ, SWARM構文）はDDL-PROTOCOL-SKILL.mdで定義される。
design.mdは仕様を複製せず、参照する。

ロードを2層で保証する:

**層1: CLAUDE.md冒頭**

`## Protocol`セクションを文書冒頭（Commandsより前）に配置し、Skill読み込みを明示する:

```markdown
## Protocol
→ DDL-PROTOCOL
→ Read `.claude/commands/DDL-PROTOCOL-SKILL.md` before executing any command
```

**層2: 各コマンドのPhase 0: INIT**

全7コマンドのPhase 0冒頭でSkill → CLAUDE.md → design.mdの順にロードする:

```markdown
### Phase 0: INIT
1. Read `.claude/commands/DDL-PROTOCOL-SKILL.md`
2. Read `CLAUDE.md`
3. Read `design.md` — extract ...
```

SWARMブロックはコードブロック（`` ``` ``）で囲む。DDL-PROTOCOL-SKILL.md §2.1の記法に準拠する。

### P2: コマンドの独立性

各コマンドは自己完結した定義を持つ。Phase数・Phase名・Detection Target・Constraintはコマンドファイル内で完結し、外部参照を必要としない。`+++`プレフィクスはPhase本体内の振る舞い指定（ディレクティブ）に付与し、markdown見出しの構造と分離する。

### P3: examples同期ルール

`examples/claude-commands/`はproduction（`.claude/commands/`）の同期コピーである。
以下のルールで差異を管理する:

- resonate.mdはexamplesに含めない（DDLリポジトリ固有）
- reflect.md: `/resonate`への言及を汎用表現に置換
- commit.md: "push to GitHub"を"push"に置換
- CLAUDE.md: プロジェクト固有情報を除外（構造・コマンド名は維持）

## Validation

```bash
cd .claude/commands

# V1: 全コマンドに +++STOP: always が存在する
grep -l "+++STOP: always" draft.md realize.md reflect.md resonate.md refactoring.md docs.md commit.md | wc -l
# 期待値: 7

# V2: +++DETECT ブロックが各コマンドに存在する
grep -l "+++DETECT:" draft.md realize.md reflect.md resonate.md refactoring.md docs.md commit.md | wc -l
# 期待値: 7

# V3: +++NEVER が各コマンドの Constraints に存在する
grep -l "+++NEVER:" draft.md realize.md reflect.md resonate.md refactoring.md docs.md commit.md ../CLAUDE.md | wc -l
# 期待値: 8（7コマンド + CLAUDE.md）

# V4: 全コマンドのPhase 0にSkillロードがある
grep -l "DDL-PROTOCOL-SKILL" draft.md realize.md reflect.md resonate.md refactoring.md docs.md commit.md | wc -l
# 期待値: 7

# V5: 全+++SWARMブロックにteam:フィールドがある
grep -A1 '+++SWARM' draft.md realize.md reflect.md resonate.md refactoring.md docs.md ../CLAUDE.md | grep -c 'team:'
# 期待値: 12（11コマンド + 1 CLAUDE.md）

# V6: DDL-PROTOCOL-SKILL.md が存在する
test -f DDL-PROTOCOL-SKILL.md && echo "EXISTS" || echo "MISSING"
# 期待値: EXISTS
```
