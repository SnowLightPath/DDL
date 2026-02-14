# Design-Doc Loop (DDL) - Extended

> このドキュメントは [design_philosophy.md](./design_philosophy.md) の補足資料です。
> DDLのデザインを理解した後、必要に応じて参照してください。

-----

## 🗺️ 読み方

このドキュメントは辞書的に使うことを想定しています。

| 目的 | 参照セクション |
|------|---------------|
| 理論的背景を知りたい | [§1 認知科学的基盤](#-1-認知科学的基盤) |
| 既存手法との関係を整理したい | [§2 関連する方法論](#-2-関連する方法論) |
| 運用を体系化したい | [§3 システム化フレームワーク](#-3-システム化フレームワーク) |
| 具体例がほしい | [§4 実践例](#-4-実践例) |
| 導入判断をしたい | [§5 適用判断](#-5-適用判断) |

通読は不要です。必要な箇所だけ拾ってください。

-----

## 🧩 §1 認知科学的基盤

DDLは複数の認知科学・哲学の理論と接点があります。後付けの理論武装ではなく、設計時に参照した考え方を整理したものです。

### 1.1 Extended Mind（拡張された心）

Clark & Chalmers (1998) の「Extended Mind」は、認知が脳内で完結せず外部ツールと一体化するという主張です。

有名な **Inga/Otto 思考実験** があります。Inga は美術館の住所を記憶で覚えており、アルツハイマー病の Otto はノートに記録しています。Clark らは Otto のノートが Inga の記憶と**機能的に等価**だと論じました。

DDL における DESIGN.md は、この「Otto のノート」に相当します。

| 機能的等価性の条件 | Otto のノート | DESIGN.md |
|-------------------|--------------|-----------|
| 常に利用可能 | 常に携帯 | リポジトリに常駐 |
| 直接アクセス可能 | すぐ参照できる | セッション開始時に読み込む |
| 自動的に信頼 | 疑わずに従う | 設計原則として尊重 |
| 過去に意識的に記録 | 意図的にメモ | Draft/Reflect で明示的に記録 |

この表が DDL の設計根拠です。4条件を満たすことで、DESIGN.md は Human-LLM 系の「拡張された記憶」として機能します。

```
Traditional: Brain -> Thinking -> Action

DDL:  Human Brain <-> DESIGN.md <-> LLM
                  |
          One cognitive system
```

### 1.2 SECI モデル

野中郁次郎の SECI モデル（1995）は、暗黙知と形式知の変換サイクルを記述します。

```
+---------------+---------------+
| Socialization | External.     |
|    (share)    | (articulate)  |
| Tacit -> Tacit| Tacit -> Form |
+---------------+---------------+
| Internal.     | Combination   |
|   (embody)    | (systematic)  |
| Form -> Tacit | Form -> Form  |
+---------------+---------------+
```

DDL との対応：

| フェーズ | DDLでの具体例 |
|---------|--------------|
| Socialization | Human と LLM の対話で「こんな感じ」を共有 |
| Externalization | Draft で体験を言語化 |
| Combination | DESIGN.md を構造化、原則間の関係を整理 |
| Internalization | 次セッションで DESIGN.md を読み文脈を復元 |

SECI モデルには「経験的根拠が弱い」という批判もあります（Gourlay, 2006）。DDL では実践で検証可能な具体的手法として提示することで、この批判に応えています。

### 1.3 分散認知

Hutchins (1995) の「分散認知」は、認知がチーム・ツール・環境に分散しているという視点です。

Flor & Hutchins (1992) はペアプログラミングを分析し、システム全体が個々のプログラマとは異なる認知特性を持つことを示しました。DDL はこの分散構造を明示的に設計しています。

```
  Human <-------> Document <-------> LLM
    |                |                |
 Intuition       Shared           Pattern
 Long-term       Memory           Recognition
 Values          Persist          Tech Know
```

どこに何を任せるか。この分担を意識することが DDL の核です。

### 1.4 Human-AI 協調研究

LLM との協調に関する研究が 2024-2025 年に急増しています。

**セッション断絶問題**：LLM には長期記憶がありません。長いインタラクション履歴では精度が大幅に低下することが知られています。DESIGN.md はこの問題への実践的解決策です。

**認知拡張としての LLM**：Sabbah & Li (2025) は、人間の限定合理性を LLM が補完できると論じています。

| 人間の制約 | LLM による補完 | DDL での実現 |
|-----------|---------------|-------------|
| 限定合理性 | 網羅的な探索 | Draft で選択肢を広げる |
| 満足化 | 最適解の追求 | Realize で原則に照らす |
| 不確実性回避 | リスク評価 | 対話で検討 |

LLM は人間を置き換えるのではなく、補完します。DDL はその補完関係を構造化したものです。

-----

## 🔗 §2 関連する方法論

DDL は既存手法と重なる部分があります。車輪の再発明を避けるため、差分を整理します。

### 2.1 Documentation-Driven Development (DocDD)

Knuth の Literate Programming（1984）の系譜。「説明に苦労するものは設計が悪い」という洞察に基づきます。

| 観点 | DocDD | DDL |
|------|-------|-----|
| 方向性 | 一方向（Doc→Code） | 双方向（Doc⇄Code） |
| 目的 | 仕様の確定 | 共有記憶の維持 |
| 永続性 | ドキュメントは成果物 | ドキュメントは一時的 |

### 2.2 Architecture Decision Records (ADR)

Nygard (2011) が普及させた手法。設計判断とその根拠を記録します。

| 観点 | ADR | DDL |
|------|-----|-----|
| タイミング | 決定後（事後） | 決定中（動的） |
| 更新 | 追記のみ | 書き換え可能 |
| 粒度 | アーキテクチャレベル | 概念〜実装 |

DDL ドキュメントが安定したら ADR に昇格させる運用は有効です。

### 2.3 Test-Driven Development (TDD)

Beck (1999) による XP の中核プラクティス。

| 観点 | TDD | DDL |
|------|-----|-----|
| 先に定義 | テスト | 体験（理想的なAPI） |
| フィードバック | Red→Green→Refactor | Draft→Realize→Reflect |

TDD と DDL は直交しており、併用可能です。Draft → テスト → 実装という流れが自然です。

### 2.4 Design by Contract (DbC)

Meyer が Eiffel（1986）で形式化。契約（不変条件）を明示します。

| 観点 | DbC | DDL |
|------|-----|-----|
| レベル | コード（実行可能） | 設計方針（概念） |
| 強制力 | ランタイムチェック | 規律・対話 |

### 2.5 Spec-Driven Development (SDD)

SDD は 2025 年に AI 支援コーディングへの対応として登場しました。中核的なアイデア：自然言語で仕様を書き、AI にコードを生成させる。

SDD は単一の方法論ではありません。複数のツール（GitHub Spec Kit, Kiro, Tessl）が SDD を名乗っていますが、ワークフロー、スコープ、野心が大きく異なります。Thoughtworks (2025) はこの断片化を明示的に指摘しています。

| 観点 | SDD | DDL |
|------|-----|-----|
| 解決する問題 | AI コード品質の制御 | セッション間の認知的連続性 |
| 方向性 | 一方向（Spec→Code） | 双方向（Doc⇄Code） |
| 人間の役割 | 仕様の著者; AI が実行 | 対等なパートナー; フェーズごとに役割が変化 |
| 起点 | 仕様が先 | 体験が先（Draft） |
| ドキュメントのライフサイクル | 仕様が正（source of truth） | ドキュメントは一時的; コードが正になる |
| フィードバックループ | Spec→Generate→Validate | Draft→Realize→Reflect |

**SDD が解決し、DDL が扱わない問題：**
SDD は AI コード生成のための構造的ガードレールを提供します — インターフェース契約、スキーマ検証、ドリフト検出。「仕様から正しいコードを生成する」ことが目的なら、SDD ツールはそのために作られています。

**DDL が解決し、SDD が扱わない問題：**
- セッション断絶（LLM がセッション間で文脈を忘れる）
- 設計哲学の進化（設計原則が実装を通じて変化する）
- 双方向の学習（コードが設計にフィードバックする）

**補完的な利用：**
DDL の Realize フェーズで SDD 的な仕様記述を取り入れることは可能です。実装前に仕様を書くことは DDL と矛盾しません — Realize の一つの方法です。違いは、DDL では実装が新たな理解を明らかにした後に仕様が書き換えられること（Reflect）を想定しているのに対し、SDD は仕様を権威的なものとして扱う点です。

「ウォーターフォール批判」（Marmelab, 2025）は SDD の一方向フローには当てはまりますが、DDL のループ構造には当てはまりません。DDL は実装が計画と矛盾するケースを明示的に設計しています。

-----

## 🔧 §3 システム化フレームワーク

DDL をより系統的に運用するための枠組みです。強制ではなく、理解と運用の補助として参照してください。

### 3.1 状態モデル

DDL は **コアループ** と **サポートコマンド** の2層で動作します。

```
コアループ:
        +-----------------------------------+
        |                                   |
        v                                   |
    +-------+     +-------+     +-------+   |
    | DRAFT | --> |REALIZE| <-> |REFLECT|   |
    +-------+     +-------+     +-------+   |
        |                           ^       |
        +---------------------------+-------+
                  (Skip OK)

サポートコマンド（任意のタイミングで実行可能）:
    +--------+  +------+  +------------+  +---------+
    |RESONATE|  |COMMIT|  |REFACTORING |  |  DOCS   |
    +--------+  +------+  +------------+  +---------+
```

コアループが設計の進化を駆動します。サポートコマンドはその周囲の品質を維持します。

| 状態 | エントリ条件 | 終了条件 |
|------|-------------|---------|
| DRAFT | 新機能・プロジェクト開始 | 理想的な体験が言語化された |
| REALIZE | DESIGN.md が存在する | コードが原則を具現化した |
| REFLECT | コードが書かれた | 設計が更新された |

| サポートコマンド | 目的 |
|-----------------|------|
| RESONATE | 多言語ドキュメントの同期 |
| COMMIT | 検証済み変更のリポジトリ記録 |
| DOCS | ドキュメント品質の監査・修正 |
| REFACTORING | コード品質の監査・修正 |

コアループ内はどの状態からでも遷移可能です。厳格な順序はありません。サポートコマンドは任意のタイミングで実行できます。

### 3.2 セッションコンテキストの保存

セッション断絶問題に対応するため、保存すべき情報を整理します。

```yaml
session:
  last_topic: "認証フローの設計"
  pending_decisions:
    - "JWTトークンの保存場所"
  open_questions:
    - "リフレッシュトークンの有効期限は？"
  state: REALIZE
```

次セッションで「前回は X について議論していました」から再開できます。

### 3.3 設計-コード整合性の検証

Reflect を支援する検証の視点：

| タイプ | 内容 | アクション |
|--------|------|-----------|
| DRIFT | コードが原則に違反 | 原則を更新するか、コードを修正 |
| NEW_PATTERN | 未文書化のパターンを発見 | 原則として追加 |
| OUTDATED | 実装のない原則 | 削除するか、実装 |

これらのカテゴリは、より広範な Detection Targets システム（§3.4）の一部です。

### 3.4 Detection Targets

Detection Targets は、各コマンドのフェーズ境界で実行される自動チェックです。問題が伝播する前に検出します。

各コマンドは目的に応じた独自の D1–D7 ターゲットを定義します。コマンド横断的なターゲットはグローバルに適用されます：

| ID | Name | トリガー |
|----|------|---------|
| D1 | Vague Intent | タスク説明に測定可能な成果がない |
| D2 | Scope Creep | 宣言されたスコープ外のファイルに変更が及ぶ |
| D3 | Principle Violation | DESIGN.md の原則に矛盾する行動 |
| D4 | Missing Validation | 変更後に検証ステップがない |
| D5 | Leaked Specifics | フレームワークファイルにプロジェクト固有のパス・コマンドがハードコードされている |
| D6 | Silent Failure | エラーがユーザー通知なく握りつぶされている |
| D7 | Unreviewed Mutation | STOP gate なしに共有アーティファクトが変更された |

例：`/reflect` は独自のターゲット（D1 Drift, D2 New Pattern, D3 Outdated Principle, D4 Stale Reference, D5 Self-Contradiction）を定義しつつ、グローバルターゲットにも従います。

### 3.5 STOP Gates

STOP gate は必須の人間承認ポイントです。共有アーティファクトを変更する前に、システムは停止して分析結果を提示します。

```
Phase N: 分析完了
    ↓
[STOP gate] — レポート提示、承認待ち
    ↓
Phase N+1: 承認された変更のみ適用
```

ルール：
- STOP gate は **ブロッキング** — 自動で進めない
- 共有アーティファクト（DESIGN.md、コード、ドキュメント）を変更するすべてのコマンドに最低1つの STOP gate が必要
- ユーザーは各提案を個別に承認・拒否・修正できる

STOP gate は DDL の核心原則を具現化しています：我々がペースを制御する。LLM は提案し、人間が決定する。

### 3.6 Agent Swarm

タスクが複数の独立したスコープにまたがる場合、エージェントの並列実行で時間を短縮し、カバレッジを向上させます。

```
リードエージェント
    ├── survey-{scope-1}  ──┐
    ├── survey-{scope-2}  ──┤── 並列実行
    └── survey-{scope-3}  ──┘
            ↓
    リードが結果を統合
            ↓
    クロススコープ分析
```

ルール：
- 2つ以上の独立したスコープが存在する場合のみエージェントを生成
- エージェント命名: `{role}-{scope}`（例: `reader-backend`, `scanner-docs`）
- 各エージェントは割り当てられたスコープのみを読む
- リードが結果を統合し、クロススコープ分析を実行
- Swarm はオプション — 単一スコープのタスクはエージェント生成なしで実行

スコープは DESIGN.md で定義され、ハードコードしません。これによりフレームワークはプロジェクト非依存を保ちます。

-----

## 💻 §4 実践例

### Example 1: 完全なループ

典型的な Draft → Realize → Reflect の流れです。

**Draft:**
```python
# こういう体験がほしい
async with APIClient("https://api.example.com") as client:
    users = await client.get("/users")
```

DESIGN.md に記録：
- Context Manager Pattern
- Authentication Transparency
- Exception-based Error Handling

**Realize:**
```
Human: 認証を実装して
LLM: DESIGN.md に「Authentication Transparency」とあるので、
     __aenter__ で自動認証します
```

```python
async def __aenter__(self):
    await self._authenticate()  # 透過的
    return self
```

**Reflect:**

実装中に Token Refresh の必要性が判明。

```python
async def _ensure_token(self):
    if self._token_expires_soon():
        await self._refresh_token()
```

DESIGN.md に追加：
- Token Refresh: 期限切れ前に透過的にリフレッシュ

### Example 2: Draft を飛ばす

既存コードベースに参加するケース。仕様は既に存在するが、設計思想が不明確。

**Reflect から開始:**
```
Human: このコードベースの設計思想を整理したい
LLM: src/ を読んで、暗黙のパターンを抽出します
```

発見されたパターン：
- すべての API は Result 型を返す
- エラーは例外ではなく値として扱う
- 副作用は明示的にマーク

**DESIGN.md を逆生成:**
```markdown
## Core Principles
- Result-based Error Handling: 例外を使わない
- Explicit Side Effects: 副作用は関数名で示す
```

Draft なしで Reflect → DESIGN.md という流れ。「どの状態からでも遷移可能」の実例です。

### Example 3: Realize と Reflect の往復

設計が固まっていない探索的開発。

```
[Realize] 原則に従って実装
    ↓
[Reflect] 実装してみたら原則に無理があった
    ↓
[Realize] 原則を修正して再実装
    ↓
[Reflect] まだ違和感がある
    ↓
...繰り返し...
```

DESIGN.md が頻繁に書き換わります。これは正常です。設計が安定していない証拠であり、DDL が機能している証拠でもあります。

-----

## 🎯 §5 適用判断

### 有効な状況

| 状況 | 理由 |
|------|------|
| 複数セッションにまたがる | セッション断絶問題が発生 |
| 設計判断が多い | 判断根拠の保存が重要 |
| 探索的な開発 | 試行錯誤の記録が有用 |
| LLM と深く協働 | 共有記憶が効果的 |

### 不要な状況

| 状況 | 理由 |
|------|------|
| 単一セッションで完了 | 断絶問題なし |
| 明確な仕様がある | 既に形式知化済み |
| バグ修正・小規模変更 | オーバーヘッドが大きい |

### 粒度ガイドライン

```
DESIGN.md に書くべき:
✓ 概念レベル（なぜ）
  例: "認証は透過的であるべき"
✓ 設計レベル（どう）
  例: "Context Manager Pattern を使う"
△ 実装レベル（重要な判断のみ）
  例: "JWT を選択、理由: ステートレス"

書くべきでない:
✗ すべての API の詳細
✗ コードで自明なこと
```

原則は「次のセッションで文脈を復元できる最小限の情報」です。

-----

## 📊 §6 効果測定

DDL の効果を把握するためのメトリクスです。数値は目安であり、プロジェクトに応じて調整してください。

| メトリクス | 定義 | 測定方法 | 健全な目安 |
|-----------|------|---------|-----------|
| セッション継続性 | 前セッションの意図を再開できるか | 5分以内に前回の論点を把握し、作業を継続できれば「成功」 | 成功率 > 80% |
| 設計-コード整合性 | 原則がコードに反映されているか | DESIGN.md の原則数に対する実装済み原則の割合 | > 70% |
| ドキュメント鮮度 | DESIGN.md が現状を反映しているか | 最終更新からの経過日数 | < 1週間 |

「セッション継続性」の補足：厳密に測定する必要はありません。「前回何をしていたか思い出せない」「LLM に一から説明し直している」という状況が頻発するなら、DESIGN.md の粒度か更新頻度に問題があります。

-----

## 🛠️ §7 実装オプション

### Option 1: Pure Discipline
ツールなし、規律のみ。最も軽量。まずはここから始めることを推奨します。

### Option 2: Template-Based

```markdown
# DESIGN.md Template
## Intent
## Core Principles
## Open Questions
## Changelog
```

> あくまで出発点です。合わなければ捨ててください。

### Option 3: Workflow Integration
PR チェックリストに Reflect を組み込む。チーム開発向け。

### Option 4: Tool-Assisted

コマンドは DDL を Phase ベースのワークフローとして実装し、Detection Targets、STOP gates、Agent Swarm をサポートします。

**コアループ** — Draft → Realize → Reflect サイクル：

| コマンド | 目的 |
|---------|------|
| `/draft` | ユーザー体験を先に書く |
| `/realize` | 設計原則に基づいてコードを書く |
| `/reflect` | 実装結果をドキュメントに反映する |

**サポートコマンド** — 任意のタイミングで実行可能：

| コマンド | 目的 |
|---------|------|
| `/resonate` | 多言語ドキュメントの同期 |
| `/commit` | 検証済み変更のリポジトリ記録 |
| `/docs` | ドキュメント品質の監査・修正 |
| `/refactoring` | コード品質の監査・修正 |

各コマンドは共通の構造に従います：
1. **Phases** — 順序付きステップ（INIT → READ → EXECUTE → VALIDATE）
2. **Detection Targets** — フェーズ境界の自動チェック（コマンドごとに D1–D7）
3. **Swarm triggers** — 2つ以上のスコープが存在する場合の並列エージェント実行
4. **STOP gates** — 共有アーティファクト変更前の必須人間承認
5. **Constraints** — 決して違反してはならない不変条件

Claude Code: → [examples/claude-commands/](../../examples/claude-commands/)
OpenAI Codex: → [examples/codex-skills/](../../examples/codex-skills/)

### Option 5: Structured Schema

機械可読なフォーマット：

```yaml
# DESIGN.yaml
version: "1.0"
intent: "API クライアントライブラリ"

principles:
  - id: P001
    name: "Context Manager Pattern"
    status: implemented
    related_code:
      - src/client.py:15-30

session:
  last_topic: "認証フローの設計"
```

自動検証やセッション継続性の追跡が可能になります。ただし、ツールが目的化すると本末転倒です。

-----

## 📦 §8 成果物とライフサイクル

| Name | Purpose | 永続性 |
|------|---------|--------|
| DESIGN.md | 設計思想、概念定義 | 一時的 |
| docs/adr/ | 設計決定の記録 | 永続的 |
| src/ | 具現化されたコード | 永続的 |

```
生成 → 活用 → 統合 → 削除
```

DDL ドキュメントが長期間残っているのは、設計がまだ安定していない証拠です。

統合のパターン：
- コードコメントに吸収
- README / API ドキュメントに昇格
- ADR として永続化
- 削除（コードで自明になった）

-----

## 📚 参考文献

### Extended Mind
- Clark, A., & Chalmers, D. (1998). [The Extended Mind](https://academic.oup.com/analysis/article-abstract/58/1/7/153111). *Analysis*, 58(1), 7-19.
- Clark, A. (2008). [*Supersizing the Mind*](https://global.oup.com/academic/product/supersizing-the-mind-9780195333213). Oxford University Press.

### SECI Model
- Nonaka, I., & Takeuchi, H. (1995). [*The Knowledge-Creating Company*](https://global.oup.com/academic/product/the-knowledge-creating-company-9780195092691). Oxford University Press.
- Nonaka, I., Toyama, R., & Konno, N. (2000). [SECI, Ba and Leadership](https://www.sciencedirect.com/science/article/abs/pii/S0024630199001156). *Long Range Planning*, 33(1), 5-34.
- Gourlay, S. (2006). [Conceptualizing Knowledge Creation: A Critique of Nonaka's Theory](https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1467-6486.2006.00637.x). *Journal of Management Studies*, 43(7), 1415-1436.

### Distributed Cognition
- Hutchins, E. (1995). [*Cognition in the Wild*](https://mitpress.mit.edu/9780262581462/cognition-in-the-wild/). MIT Press.
- Flor, N. V., & Hutchins, E. (1991). Analyzing Distributed Cognition in Software Teams. *Empirical Studies of Programmers: Fourth Workshop*, 36-64.

### Human-AI Collaboration
- Sabbah, J., & Li, F. (2025). [When Humans and Large Language Models Collaborate, Problem-Finding Illuminates](https://doi.org/10.1080/14479338.2025.2504428). *Innovation: Organization and Management*.

### Spec-Driven Development
- Thoughtworks (2025). [Spec-Driven Development: Unpacking one of 2025's key new AI-assisted engineering practices](https://www.thoughtworks.com/en-us/insights/blog/agile-engineering-practices/spec-driven-development-unpacking-2025-new-engineering-practices).
- Fowler, M. et al. (2025). [Understanding Spec-Driven-Development: Kiro, spec-kit, and Tessl](https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html). *martinfowler.com*.
- InfoQ (2025). [Spec Driven Development: When Architecture Becomes Executable](https://www.infoq.com/articles/spec-driven-development/).
- Marmelab (2025). [Spec-Driven Development: The Waterfall Strikes Back](https://marmelab.com/blog/2025/11/12/spec-driven-development-waterfall-strikes-back.html).

### Related Methodologies
- Knuth, D. (1984). [Literate Programming](https://academic.oup.com/comjnl/article/27/2/97/343244). *The Computer Journal*, 27(2), 97-111.
- Nygard, M. (2011). [Documenting Architecture Decisions](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions). *Cognitect Blog*.
- Beck, K. (1999). [*Extreme Programming Explained*](https://www.oreilly.com/library/view/extreme-programming-explained/0201616416/). Addison-Wesley.
- Meyer, B. (1992). [Applying Design by Contract](https://ieeexplore.ieee.org/document/161279/). *IEEE Computer*, 25(10), 40-51.

-----

## 📝 Changelog

| Date | Change |
|------|--------|
| 2026-02-14 | §2.5 Spec-Driven Development (SDD) 比較を追加 |
| 2026-01-04 | 初版 |