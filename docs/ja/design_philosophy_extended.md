# Design-Doc Loop (DDL) - Extended

> このドキュメントは [design_philosophy.md](./design_philosophy.md) の補足資料です。
> DDLのデザインを理解した後、必要に応じて参照してください。すべてを読む必要はありません。

-----

## Cognitive Foundation

### Extended Mind（拡張された心）

哲学者 Andy Clark と David Chalmers は「Extended Mind（拡張された心）」という概念を提唱しました。認知は脳の中だけで完結せず、外部のツールや環境と一体化して機能するという考えです。

DDLにおける DESIGN.md は、この「拡張された心」として機能します。

```
従来の認知モデル:
  脳 → 思考 → 行動

DDL の認知モデル:
  脳 ←→ DESIGN.md ←→ LLM
            ↓
      一つの認知システム
```

### SECI モデルとの関係

野中郁次郎の SECI モデルは知識創造のプロセスを説明します。

| フェーズ | 変換 | DDLとの対応 |
|---------|-----|------------|
| **S**ocialization | 暗黙知→暗黙知 | Human と LLM の対話 |
| **E**xternalization | 暗黙知→形式知 | Draft（言語化） |
| **C**ombination | 形式知→形式知 | DESIGN.md の構造化 |
| **I**nternalization | 形式知→暗黙知 | 次のセッションでの復元 |

### 分散認知としての DDL

```
Human ←→ Document ←→ LLM
  │          │          │
直感・判断  共有記憶   パターン認識
長期視野              言語化能力

      → 一つのシステムとして機能
```

-----

## Related Concepts

DDLは既存のソフトウェア設計の方法論と重なる部分があります。

### Documentation-Driven Development (DocDD)

**共通点：** ドキュメントを先に書く

**DDLの違い：** DocDDは一方向（Doc→Code）、DDLは双方向（Doc⇄Code）

### Architecture Decision Records (ADR)

**共通点：** 設計判断の根拠を残す

**DDLの違い：** ADRは静的（決定後）、DDLは動的（ループする）

### Test-Driven Development (TDD)

**共通点：** 実装前に「あるべき姿」を定義

**DDLの違い：** TDDは「テスト」が先、DDLは「体験（Draft）」が先。共存可能

### Design by Contract (Meyer)

**共通点：** 契約（不変条件）を明示

**DDLの違い：** コードレベル vs 設計方針レベル。補完関係

-----

## Practical Examples

### Example 1: 完全なループの流れ

#### Draft
```python
# Human: こういう体験がほしい
async with APIClient("https://api.example.com") as client:
    users = await client.get("/users")
```

DESIGN.mdに保存：
- Context Manager Pattern
- Authentication Transparency
- Exception-based Error Handling

#### Realize (Design → Dialogue → Code)

**Design:**
```
DESIGN.md:
- Context Manager Pattern
- Authentication Transparency
```

**Dialogue:**
```
Human: 認証を実装して
LLM: 透過的な認証なので、__aenter__で自動認証します
```

**Code:**
```python
async def __aenter__(self):
    await self._authenticate()  # 透過的
    return self
```

#### Reflect (Code → Dialogue → Design)

**Code:**
```python
async def _ensure_token(self):
    if self._token_expires_soon():
        await self._refresh_token()
```

**Dialogue:**
```
Human: これ、DESIGN.md に反映して
LLM: Core Principles に追加します
```

**Design:**
```
DESIGN.md に追加:
- Token Refresh: 期限切れ前に透過的にリフレッシュ
```

-----

## When to Use DDL

### 有効な状況
- 複数セッションにまたがるプロジェクト
- 設計判断が多い
- 探索的な開発
- LLMと深く協働

### 不要な状況
- 単一セッションで完了
- 明確な仕様がある
- バグ修正・小規模変更

-----

## Granularity Guide

```
DESIGN.md に書くべき:
✓ 概念レベル（なぜ）
✓ 設計レベル（どう）
△ 実装レベル（重要な判断のみ）

書くべきでない:
✗ すべてのAPIの詳細
✗ コードで自明なこと
```

### 原則
「次のセッションで文脈を復元できる最小限の情報」

-----

## Implementation Options

### Option 1: Pure Discipline
ツールなし、規律のみ。最も軽量。

### Option 2: Template-Based

> **Warning**: This is a starting point, not a requirement. Adapt or discard as needed.

```markdown
# DESIGN.md Template
## Intent
## Core Principles
## Open Questions
## Changelog
```

### Option 3: Workflow Integration
PRチェックリストにReflectを組み込む。

### Option 4: Tool-Assisted
```
/draft, /realize, /reflect
```

See [examples/claude-commands/](../../examples/claude-commands/) for ready-to-use Claude Code slash commands.

**Warning:** Tools can become shackles. If they obstruct the Intent, discard them.

-----

## Artifacts

| Name      | Purpose            | 永続性 |
|-----------|--------------------|--------|
| DESIGN.md | 設計思想、概念定義   | 一時的 |
| docs/adr/ | 設計決定の記録      | 永続的 |
| src/      | 具現化されたコード   | 永続的 |

-----

## Lifecycle of DDL Documents

```
生成 → 活用 → 統合 → 削除
```

DDLドキュメントが永続化しているのは設計がまだ安定していない証拠。

-----

## Changelog

| Date       | Change                    |
|------------|---------------------------|
| 2025-01-4 | 初版 |
