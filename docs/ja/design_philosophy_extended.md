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
| モデルが何をいつ読み込むかを知る | [§2.5 コンテキストエンジニアリング](#コンテキストエンジニアリング) |
| 運用を体系化したい | [§3 システム化フレームワーク](#-3-システム化フレームワーク) |
| 具体例がほしい | [§4 実践例](#-4-実践例) |
| 導入判断をしたい | [§5 適用判断](#-5-適用判断) |
| 効果を測りたい | [§6 効果測定](#-6-効果測定) |
| 実装の方法を選びたい | [§7 実装オプション](#️-7-実装オプション) |
| 成果物とその寿命を管理したい | [§8 成果物とライフサイクル](#-8-成果物とライフサイクル) |

通読は不要です。必要な箇所だけ拾ってください。

-----

## 🧩 §1 認知科学的基盤

DDLは複数の認知科学・哲学の理論と接点があります。後付けの理論武装ではなく、設計時に参照した考え方を整理したものです。

### 1.1 Extended Mind（拡張された心）

Clark & Chalmers (1998) の「Extended Mind」は、認知が脳内で完結せず外部ツールと一体化するという主張です。

有名な **Inga/Otto 思考実験** があります。Inga は美術館の住所を記憶で覚えており、アルツハイマー病の Otto はノートに記録しています。Clark らは Otto のノートが Inga の記憶と**機能的に等価**だと論じました。

DDL における design.md は、この「Otto のノート」に相当します。

| 機能的等価性の条件 | Otto のノート | design.md |
|-------------------|--------------|-----------|
| 常に利用可能 | 常に携帯 | リポジトリに常駐 |
| 直接アクセス可能 | すぐ参照できる | セッション開始時に読み込む |
| 自動的に信頼 | 疑わずに従う | 設計原則として尊重 |
| 過去に意識的に記録 | 意図的にメモ | Draft/Reflect で明示的に記録 |

この表が DDL の設計根拠です。4条件を満たすことで、design.md は Human-LLM 系の「拡張された記憶」として機能します。

**ハーネスの記憶はノートではありません。** エージェントのハーネスはいまでは記憶を自前で持っています（指示ファイル、自動メモリ、長い会話の要約、次のセッションのために書かれる進捗ファイル）。この記憶はエージェントにとっては最初の2条件を満たしますが、エージェントが書いた部分は人間にとって多くの場合4つ目を満たしません。書いたのはエージェントであり、人間はそれを意識的に承認していないからです。design.md は双方が合意した部分であり、ハーネスの記憶とは補い合う関係にあって、一方が他方を置き換えることはありません。

```
Traditional: Brain -> Thinking -> Action

DDL:  Human Brain <-> design.md <-> LLM
                  |
          One cognitive system
```

### 1.2 SECI モデル

野中郁次郎の SECI モデル（1995）は、暗黙知と形式知の変換サイクルを記述します。

```
+---------------+---------------+
|  Socialization| Externalize   |
|    (share)    |  (articulate) |
| Tacit -> Tacit| Tacit -> Form |
+---------------+---------------+
| Internalize   | Combination   |
|   (embody)    | (systematize) |
| Form -> Tacit | Form -> Form  |
+---------------+---------------+
```

DDL との対応：

| フェーズ | DDLでの具体例 |
|---------|--------------|
| Socialization | Human と LLM の対話で「こんな感じ」を共有 |
| Externalization | Draft で体験を言語化 |
| Combination | design.md を構造化、原則間の関係を整理 |
| Internalization | 次セッションで design.md を読み文脈を復元 |

SECI モデルには「経験的根拠が弱い」という批判もあります（Gourlay, 2006）。DDL では実践で検証可能な具体的手法として提示することで、この批判に応えています。

### 1.3 分散認知

Hutchins (1995) の「分散認知」は、認知がチーム・ツール・環境に分散しているという視点です。

Flor & Hutchins (1991) はペアプログラミングを分析し、システム全体が個々のプログラマとは異なる認知特性を持つことを示しました。DDL はこの分散構造を明示的に設計しています。

```
  Human <-------> Document <-------> LLM
    |                |                |
 Intuition       Shared           Pattern
 Long-term       Memory           Recognition
 Values          Persist          Tech Knowledge
```

どこに何を任せるか。この分担を意識することが DDL の核です。

### 1.4 Human-AI 協調研究

LLM との協調に関する研究が 2024-2025 年に急増しています。

**セッション断絶問題**：チャットのアシスタントは何年も前に記憶を持ち、コーディングのハーネスはいま、指示ファイル、自動メモリ、長い会話の要約（compaction）という自前の記憶を加えています。DDL が扱う問題はモデルが忘れることではなく、ハーネスが覚えたことが人間の合意ではないこと、エージェントやハーネスをまたいで共有されないこと（SWARM のワーカーがリードの会話を引き継ぐかどうかは実行環境と起動のしかたで変わります）、そして有限であって文脈に積むほどモデルがその中身を思い出せなくなることです（Anthropic, 2025b）。design.md はこの三つに答えます。人間が合意したことだけを載せ、すべてのセッションが同じファイルを読み、リードが各ワーカーへの指示をそこから作るので、並列に走る5つのワーカーは指示に書かれたことだけで動けます。

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

### 2.5 AI時代の開発パラダイム（2025–2026）

2025年から2026年にかけて AI 支援開発への3つの構造的アプローチが登場しました。それぞれ異なる出自を持ち、異なる問題を解決します。

| 出自 | パラダイム | 中核的な問題 |
|------|-----------|-------------|
| プロダクト開発 | Spec-Driven Development (SDD) | 仕様なしでは AI が誤ったコードを生成する |
| エンタープライズ開発 | AI-Driven Development Life Cycle (AI-DLC) | SDLC が AI を主要な実行者として想定していない |
| 研究・探索的開発 | Design-Doc Loop (DDL) | セッション間で設計意図が失われる |

三者に共通する背景：非構造的な AI コーディング（"vibe coding"）はスケールしない。それぞれが Human-AI の関係を異なる形で構造化しています。

#### SDD の概要

自然言語で仕様を書き、AI にコードを生成させる。単一の方法論ではなく、複数のツール（GitHub Spec Kit, Kiro, Tessl）が大きく異なります（Thoughtworks, 2025）。仕様が正（source of truth）であり、コードはそこから導出されます。

#### AI-DLC の概要

AWS 発の方法論（Raja SP ら, 2025）で、AI を主要な実行者として SDLC 全体を再設計しています。3フェーズ構成：Inception（モブエラボレーション → 要件）、Construction（モブコンストラクション → コード）、Operation（AI 監視下のデプロイ）。アジャイル用語を再定義：スプリント → ボルト（時間〜日単位）、エピック → 作業単位（Units of Work）。人間の役割は AI の提案を検証・承認することです。

#### ハーネスエンジニアリングの概要

2025年から2026年にかけて、モデルを取り巻くハーネスがそれ自体で工学の対象になりました。Anthropic は長時間動くエージェントのためのハーネスを示しており、そこでは初期化役のエージェントが環境を整え、以後の各セッションが進捗ファイル、機能リスト、git の履歴を読んでから作業を選びます（Anthropic, 2025a）。OpenAI のハーネスエンジニアリングの報告は手書きのコードなしで製品を作った事例を述べています（Lopopolo, 2026）。そこではエンジニアが環境を設計し、意図を示し、フィードバックの仕組みを作る一方で、コードは Codex が書いています。

DDL が扱うのはこうしたハーネスが記録し指定するもののうち人間が合意すべき部分、すなわち体験、それを拘束する決定、人間が見る承認点です。

#### コンテキストエンジニアリング

2025年の終わりには、この分野に名前がつきました。Anthropic の応用 AI チームは文脈を「限りある資源であり、追加するほど見返りが減る」ものとして描きました。窓が埋まるほどモデルは中身を思い出せなくなるので、エージェントは行動に足る最小限の、信号の濃いトークンだけを持ち、残りは必要になった時点で取りに行き、長い会話は要約に畳み、焦点の絞られたサブエージェントにはまっさらな文脈の窓を与えるべきだ、という主張です（Anthropic, 2025b）。Agent Skills は同じ考えを指示に当てはめ、起動時には各スキルの名前と説明だけを読み込み、本文はスキルを使うときに読み込みます（Anthropic, 2025c）。Manus は運用から同じ教訓を報告しています。ファイルシステムを容量に限りがなく消えない文脈として扱うこと、誤った手順の記録を残すこと、いまの目標を文脈の末尾に唱え直すことです（Ji, 2025）。ハーネスは自分が何を読み込むかを文書にしています。Claude Code はセッション開始時にユーザーとプロジェクトの指示ファイルと自動メモリを読み込み、コマンドは呼ばれたときに読み込み、要約のあとはプロジェクトの指示ファイルと自動メモリをディスクから入れ直す一方で、会話そのものは要約します（Anthropic, 2026）。Codex は作業の前に AGENTS.md の連鎖を実行のたびに一度読み、スキルは名前と説明で一覧にし、memories を「常に適用すべき規則の唯一の置き場ではなく、思い出すための補助の層」として扱います（OpenAI, 2026）。

DDL は、人間の側から行うコンテキストエンジニアリングです。「モデルは動く前に何を見るべきか」という問いは、常に文脈にあるもの、コマンドが走るときに載るもの、リードが各ワーカーのために詰めるものの三つに分かれます。

| 層 | 中身 | 読み込み | 持ち主 |
|---|---|---|---|
| 指示ファイル（`CLAUDE.md`、`AGENTS.md`） | ここでの働き方：protocol の探索順、全体の制約、G1〜G7 | セッション開始時。Claude Code は要約のあとに入れ直す | 人間 |
| design.md | 人間が合意したこと：Experience、Binding Decisions、Direction、Acceptance Gates、原則、スコープ、検証 | セッション開始時 | ループを通じた人間と LLM |
| protocol とコマンド | コマンドの動き方 | コマンドを呼んだとき（Phase 0）。Codex のスキル一式は protocol の節を `AGENTS.md` に持ち、セッション開始時から文脈に載せてよい。コマンドは protocol を参照し、複製しない | 方法論 |
| ワーカーへの指示 | 一つのスコープのパス、そのスコープが担う Experience の項目、原則、Binding Decisions、Direction の段階、スコープの検証コマンド、その phase で人間が承認した行（逐語）、`/realize` では承認された計画 | リードが並列に分けるとき。ワーカーは指示が名指しするファイルと design.md の節だけを読む | design.md から作るリード |
| 自動メモリ、会話の要約、進捗ファイル | エージェントの作業状態 | ハーネスが行う | エージェント。決定の出どころにはならない |

ここから三つの帰結が出ます。第一に予算です。ループが片づける節（終わった Direction、受け入れ済みの Acceptance Gates）は、以後のどのセッションも払わずに済む文脈なので、「DDL ドキュメントは一時的である」は文脈の規則でもあります。第二に、会話は残りません。会話の要約はユーザーの発言ではなく何も承認しないので、STOP が問うた報告が文脈に逐語で残っていなければ、コマンドは design.md と git とその報告が述べたファイルからそれを組み立て直して改めて問います。要約のあとに与えられた承認は、その要約のあとに出した報告にだけ効きます。再起動が中断した STOP は再開せず、コマンドは止まった phase からやり直し、ゲートが passed と記された段階は飛ばします。人間が承認したものはその場で書き留めます（下書きは design.md へ、通ったゲートは印へ、委任された選択は表へ）。第三に、記憶は合意ではありません。自動メモリにしかない決定は、design.md が記録するまで提案にとどまります。

#### 構造的比較

| 観点 | SDD | AI-DLC | DDL |
|------|-----|--------|-----|
| 問題 | AI コード品質 | 開発速度 | 認知的連続性 |
| AI の役割 | 生成器 | 成果物を提案するチームメイト | 対等なパートナー |
| 人間の役割 | 仕様の著者 | 検証者・承認者 | 共同思考者; フェーズごとに役割が変化 |
| 方向性 | Spec→Code（一方向） | AI が提案→人間が承認 | Doc⇄Code（双方向） |
| 知識の流れ | 仕様→コード | AI 成果物→人間のレビュー | 設計哲学⇄実装 |
| イテレーション単位 | 仕様のライフサイクル | ボルト（時間〜日単位） | Reflect ループ（固定周期なし） |
| ドキュメントのライフサイクル | 仕様が正 | 成果物はプロセスの副産物 | ドキュメントは一時的; コードが正になる |
| 想定規模 | プロダクト仕様を持つチーム | エンタープライズ（10〜100人以上） | 少人数チーム・個人（1〜5人） |

#### セッション断絶への対応

各アプローチはセッション断絶問題に異なる方法で対処しています：

| パラダイム | 戦略 | メカニズム |
|-----------|------|-----------|
| SDD | 仕様を永続化 | コードは仕様から再生成可能; 仕様がセッションを超えて存続 |
| AI-DLC | プロセス成果物を永続化 | 要件・ストーリー・ユニットをリポジトリに保存 |
| ハーネスエンジニアリング | エージェントの進捗を永続化 | 進捗ファイルと機能リストを各セッションの開始時に読む（Anthropic, 2025a） |
| DDL | 設計を共有記憶として活用 | design.md がセッション間の認知的な橋渡し |

SDD と AI-DLC は永続化をワークフローの副作用として扱い、ハーネスエンジニアリングはエージェントの作業状態を永続化します。一方で、DDL は人間が合意したことの永続化を中心的な設計問題として扱っています。

#### 技術の選択

Spec Kit は技術を仕様から切り離しており、`/speckit.specify` で何をなぜ作るかを書き、`/speckit.plan` でスタックを決めます（GitHub, 2025）。DDL は両方を一つの Draft に置きつつ節を分け、各技術がなぜ体験を拘束するのかを問います。人間が理由とともに挙げた技術（体験が依存している、外部の制約が求めている、人間が好みとして明言した）は Binding Decision になります。LLM の提案、理由なく挙げられた技術、人間が任せた選択は表の下に `Unbound:` として残り、何も拘束しません。`Unbound:` の各行は `/realize` に任された行（delegated to `/realize`）か人間の選択を待つ行（`awaiting choice`）のどちらかです。任された行については `/realize` が計画の中で選んだ技術とその理由を示し、選択を待つ行については人間に選ぶよう求めます。選んだ技術が拘束するのは人間がその計画を承認したときだけであり、承認されると `/realize` が Source を `approved in /realize plan (<date>)` として表に移します。承認の後は design.md が以後のコマンド引数に優先します。そのため、引数で別の技術を挙げることは Binding Decision の変更にあたり、コマンドはそこで止まります。コードにすでにある技術は既存の前提であり、コマンドは報告に示しますが design.md には記録しません。その技術は人間が理由を示したときにだけ Binding Decision になります。

#### 補完関係

これらのパラダイムは異なるレイヤーに位置しており、共存可能です：

- DDL の Realize フェーズでは SDD 的な仕様記述を使える。実装前に仕様を書くことは、Realize の一つの方法である
- AI-DLC のモブエラボレーションに DDL の Reflect を組み込むことで、実装の発見を要件にフィードバックできる
- SDD と AI-DLC は設計哲学の進化（実装を通じて設計原則が変化すること）を扱わない; DDL はそれを扱う
- ハーネスの記憶（進捗ファイル、自動メモリ）はエージェントの作業状態を運び、design.md は人間が合意したことを運ぶ。両者は分けて扱い、エージェントの進捗を design.md に写さず、拘束する決定をエージェントの記憶だけに残さない

「ウォーターフォール批判」（Marmelab, 2025）は SDD の一方向フローに当てはまります。AI-DLC は短いボルトでこれを軽減しています。DDL は双方向ループにより、この問題自体を回避しています。

DDL の役割流動性は少人数の探索的開発の文脈で機能します。監査証跡と明確な説明責任が求められるエンタープライズ文脈では、AI-DLC の固定的な役割分担（AI が提案し、人間が承認する）の方が適切な場合があります。これは弱点ではなく、異なる運用制約を反映しています。

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
    +--------+  +---------+  +------+  +------------+  +---------+
    |VALIDATE|  |RESONATE*|  |COMMIT|  |REFACTORING |  |  DOCS   |
    +--------+  +---------+  +------+  +------------+  +---------+
    * このリポジトリ専用、examples/ には含まない
```

コアループが設計の進化を駆動します。サポートコマンドはその周囲の品質を維持します。

| 状態 | エントリ条件 | 終了条件 |
|------|-------------|---------|
| DRAFT | 新機能・プロジェクト開始 | 体験が言語化され、Binding Decisions・Direction・Acceptance Gates があれば記録された |
| REALIZE | design.md が存在する | コードが原則と Binding Decisions を具現化し、ゲートを通った |
| REFLECT | コードが書かれた | 設計が更新された |

| サポートコマンド | 目的 |
|-----------------|------|
| VALIDATE | design.md で宣言された scope ごとの機械的検証 |
| RESONATE | 多言語ドキュメントの同期（このリポジトリ専用、examples/ には含まない） |
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

いまではハーネス自身がこのようなセッションの状態を保持しています（自動メモリ、会話の要約、進捗ファイル）。design.md には人間が目を通して認めたことだけを残し、未決の技術選択は `Unbound:` 行に、その他の未決の事項は Open Questions に、決まった事項は Experience・Binding Decisions・Principles に書きます。

### 3.3 設計-コード整合性の検証

Reflect を支援する検証の視点：

| タイプ | 内容 | アクション |
|--------|------|-----------|
| DRIFT | コードが原則に違反 | 原則を更新するか、コードを修正 |
| NEW_PATTERN | 未文書化のパターンを発見 | 原則として追加 |
| OUTDATED | 実装のない原則 | 削除するか、実装 |
| BINDING_DRIFT | コードが Binding Decision から外れた | 人間が選ぶ: コードを直すか、決定を変える |
| SPENT_DIRECTION | Direction の段階に passed の記録がついた | 実績で置き換え、全段階が終われば節を消す |
| SPENT_ACCEPTANCE | Acceptance Gates のすべてのゲートに passed の記録がつき、作業が受け入れられた | 残す検証を Validation に移し、節を消す |

これらのカテゴリは、より広範な Detection Targets システム（§3.4）の一部です。

**passed の記録。** `/realize` は通ったゲートごとに `passed <date>` を書き足し、書く場所は Direction では段階の Gate 列のセル（例: `human approval, passed 2026-10-20`）、Acceptance Gates ではゲートの後ろです。人間の承認点が事前承認によって止まらなかったときは、`(approved in advance)` も添えます。作業が受け入れられるのは Acceptance Gates のすべてのゲートに passed の記録がついたときです。`/reflect` はこの記録だけを読み、会話の記憶から通ったと推し量ることはしません。

ゲートを落とすことはありません。統合した段階はゲートを統合後の段階の終わりに残し、飛ばした段階のゲートは次の段階の終わりへ、それが最後の段階なら作業の終わりへ移します。順序を入れ替えた段階はゲートをそのまま保ちます。

### 3.4 Detection Targets

Detection Targets は、コマンドの各フェーズの中で並列に走る自動チェックです。問題が伝播する前に検出します。

各コマンドは目的に応じた独自の D ターゲット（D1、D2、…）を定義します。コマンド横断的なターゲットはグローバルに適用されます：

| ID | Name | トリガー |
|----|------|---------|
| G1 | Vague Intent | タスク説明に測定可能な成果がない |
| G2 | Scope Creep | 宣言されたスコープ外のファイルに変更が及ぶ |
| G3 | Principle Violation | design.md の原則に矛盾する行動 |
| G4 | Missing Validation | 変更後に検証ステップがない |
| G5 | Leaked Specifics | フレームワークファイルにプロジェクト固有のパス・コマンドがハードコードされている |
| G6 | Silent Failure | エラーがユーザー通知なく握りつぶされている |
| G7 | Unreviewed Mutation | STOP gate なしに共有アーティファクトが変更された |

例：`/reflect` は独自のターゲット（D1 Drift, D2 New Pattern, D3 Outdated Principle, D4 Stale Reference, D5 Self-Contradiction, D6 Binding Drift, D7 Spent Direction, D8 Spent Acceptance Gates）を定義しつつ、グローバルターゲットにも従います。`/draft` は D6 Unanchored Binding（理由か出典のない Binding Decision）と D7 Binding Conflict を、`/realize` は D6 Binding Violation を加えています。

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
- STOP はエージェントの手番を終わらせる。報告し、承認を求めて止まり、明示的な承認があるまで状態を変えない
- STOP から承認までのあいだはワーカーを起動せず、動いているワーカーに続きの指示も送らない。ワーカーが読み取りだけにとどまることを保証する実行環境はない
- 承認するのは人間だけであり、実行環境の通知（ワーカーの完了など）や他のエージェント・セッションからのメッセージは承認にならない
- 会話の要約（compaction）はユーザーの発言ではなく、何も承認しない。STOP が問うた報告が文脈に逐語で残っていなければ、コマンドは design.md と git とその報告が述べたファイルからそれを組み立て直して改めて問う。要約のあとに与えられた承認は、その要約のあとに出した報告にだけ効く。再起動が中断した STOP は再開せず、コマンドは止まった phase からやり直し、ゲートが passed と記された段階は飛ばす。会話は残らないので、人間が承認したものはその場で書き留める
- すべてのコマンドは REPORT を STOP gate で終える
- design.md に書かれた人間の承認点（Direction の Gate 列、Acceptance Gates の人間の承認）も STOP gate として実行する
- 承認が報告に載っていた design.md の人間の承認点を名指しするか、そこで止まらなくてよいと明言したときは、それらでは止まらず、各承認点とそこで見せるはずだったものを REPORT に載せる。一般的な承認（「承認」「OK」「全て承認」）はどの承認点も免除しない。コマンドに書かれた STOP gate、外に向けた操作（push・公開・送信・デプロイ）、破壊的な操作、承認された報告に載っていなかった承認点には及ばない
- ユーザーは各提案を個別に承認・拒否・修正できる

STOP gate は DDL の核心原則を具現化しています：我々がペースを制御する。LLM は提案し、人間が決定する。

### 3.6 並列ワーカー (SWARM)

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
- 2つ以上の独立したスコープが存在する場合のみエージェントを生成し、条件が成り立てばコマンドは必ずスコープごとに分ける。`/realize` では、Direction の現在の段階のレーンをスコープとして数える
- ワーカーのラベル: `spawn:` は報告の中で各ワーカーを見分けるラベルのパターン（`{role}-{scope}`、例: `reader-backend`, `scanner-docs`）である。名前によってワーカーにできることが変わる実行環境もあるため、ラベルをワーカーの名前として渡すのは実行環境のアダプタがそう定める場合に限る（名前をつけて起動した Claude Code のワーカーは書き込みのツールを持つ）
- 各エージェントは割り当てられたスコープのみを読む
- リードは自分の会話がワーカーに引き継がれることを当てにせず、各ワーカーへの指示をそれだけで足りるように design.md から作る（スコープのパス、スコープが担う Experience の項目、原則、Binding Decisions、担当する Direction の段階、スコープの検証コマンド、その phase で人間が承認した行（逐語）、`/realize` では承認された計画）。この指示がワーカーの文脈のすべてであり、ワーカーは指示ファイルも design.md 全体も読み直さない。STOP の条件に当たったワーカーは止まって報告し、リードが人間の承認を求めて止まる
- 指示にはワーカーが自分のワーカーを起動しないこと（仕事を並列に分けるのはリードだけである）も書き、読み取り専用の作業ならそのことも書く。どちらの実行環境もワーカーに範囲を越えられる道具を与えているため、ワーカーを範囲の中にとどめるのは指示である（Claude Code ではファイルを編集できないワーカーもシェルのコマンドを実行でき、書き込むワーカーはワーカーを起動できる。Codex のサブエージェントは親セッションのサンドボックスを引き継ぎ、自分のエージェントを起動できる）
- リードが結果を統合し、クロススコープ分析を実行
- 単一スコープのタスクはエージェント生成なしで実行
- protocol が並列実行を各実行環境の仕組み（Claude Code のサブエージェント、Codex のサブエージェント）に対応づける。仕組みがなければリードが割り当てを自分で実行し、読み取りだけの作業は並列の読み取りで、その他は一つずつ処理する。コマンドは実行環境のツール名を書かない

スコープは design.md で定義され、ハードコードしません。これによりフレームワークはプロジェクト非依存を保ちます。

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

design.md に記録：
- Context Manager Pattern
- Authentication Transparency
- Exception-based Error Handling

**Realize:**
```
Human: 認証を実装して
LLM: design.md に「Authentication Transparency」とあるので、
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

design.md に追加：
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

**design.md を逆生成:**
```markdown
## Core Principles
- Result-based Error Handling: 例外を使わない
- Explicit Side Effects: 副作用は関数名で示す
```

Draft なしで Reflect → design.md という流れ。「どの状態からでも遷移可能」の実例です。

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

design.md が頻繁に書き換わります。これは正常です。設計が安定していない証拠であり、DDL が機能している証拠でもあります。

### Example 4: Binding Decisions と Direction を伴う Draft

体験がフレームワークに依存する Web 機能の例です。

**Draft:**
```
Human: 社内ナレッジ検索。回答が書きながら出てくるのが肝。Next.jsでやりたい
LLM:   体験と拘束に分けました。2点確認させてください。App Router に限りますか。
       0件のときと検索に失敗したときは、どう見えるのがよいですか
Human: App Router で。0件なら近い言い換えを3つ、失敗なら入力を残して再試行
```

design.md に記録：
```markdown
## Experience
質問を送ると1秒以内に回答が出始め、書きながら伸びていく。引用元は回答の下に並ぶ。
- 0件: 「見つかりませんでした」と、近い言い換えを3つ
- 失敗: 入力を残したまま「再試行」

## Binding Decisions
| Decision | Why it binds | Source |
|---|---|---|
| Next.js App Router | 書きながら伸びる回答と、画面ごとの読み込み中・エラー表示が体験の中心 | 「Next.jsでやりたい」「App Router で」(2026-10-17) |

## Direction
| Stage | Work (parallel lanes) | Human sees | Gate |
|---|---|---|---|
| S0 | 検索APIをCLIで固める | CLIの出力例 | `npm test` |
| S1 | 画面の3状態を3レーンで | スクリーンショット3枚 | 人間の承認 |
| S2 | 書きながら伸びる表示 | 操作の動画 | `npx playwright test` |
```

**Realize:**
```
LLM: Binding Decisions を確認しました（package.json、app/）。S0 は `npm test` を
     通ったので、Gate 列を「`npm test`, passed 2026-10-20」にしました。
     S1 と S2 を統合し、両方のゲート（`npx playwright test`、続いて人間の承認）を
     統合後の段階の終わりに移しました。
LLM: 停止します。配信基盤が静的ホスティングのみのため、Binding の理由である
     「書きながら伸びる回答」をサーバーから流せません。案は、Node の実行環境を申請する、
     別の API サーバーから流す、完成後にまとめて表示する、Binding Decision を変える、
     の4つです。選んでください。
```

**Reflect:**

人間が Node の実行環境を選んだため、Binding Decisions はコードと一致しています。Direction は全段階に passed の記録がついたので削除し、経緯はバージョン管理に残します。実装中に足した停止ボタンは Experience に追記します。

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
design.md に書くべき:
✓ 概念レベル（なぜ）
  例: "認証は透過的であるべき"
✓ 設計レベル（どう）
  例: "Context Manager Pattern を使う"
△ 実装レベル（重要な判断のみ）
  例: "JWT を選択、理由: ステートレス"
  Binding Decisions はこのレベルに置く: 決定、拘束する理由、出典（人間の言葉と日付、または、その行を載せた報告を人間が承認したこと）

書くべきでない:
✗ すべての API の詳細
✗ コードで自明なこと
```

原則は「次のセッションで文脈を復元できる最小限の情報」です。

### README を共有ノートとして使う代替

design.md は必須ではありません。本質は Human と LLM の間に **共有ノート** が存在することであり、ファイル名はその次です（Otto のノートはどんな形でもよい）。

公開 API そのものが設計となるプロジェクト（OSS ライブラリ、CLI、HTTP API など）では、README に API リファレンスとガイドを合わせて living spec として運用できます。

| 状況 | 推奨される共有ノート |
|------|---------------------|
| アプリケーション・複数成果物・研究プロジェクト | `design.md` |
| 公開ライブラリ（API == 設計） | `README.md` + `docs/`（API リファレンス、ガイド） |
| 小さなツール（単一スクリプト） | ファイル冒頭の docstring |

運用ルール：
- **セッション開始時にロード** され、**変更前に参照** されることが要件であり、ファイル名は問わない
- 共有ノートにするファイルは実行環境の指示ファイル（`CLAUDE.md` や `AGENTS.md`）で指定する。protocol はこの形を認めており、コマンドは design.md と書かれた所で指定されたファイルを読み書きする。これにより、README の更新はそのまま設計の更新になり、`/reflect` は README とガイドに書き込む
- 設計がユーザー向けの説明から乖離した瞬間に design.md を分離する

これは AgenticFlow パターンです。Python の公開ライブラリである AgenticFlow は `CLAUDE.md` と `AGENTS.md` の両方で `README.md` と `docs/en/` を設計ドキュメントとして指定しています。README が契約を文書化し、開発ガイド（AgenticFlow のリポジトリ内の `docs/en/guides/development-workflow.md`）がスコープの表と検証コマンドを載せているため、別途 design.md を持つと冗長になります。Otto のノート4条件（常に利用可能・直接アクセス可能・自動的に信頼・過去に意識的に記録）はこれらのファイル自身で満たされます。

-----

## 📊 §6 効果測定

DDL の効果を把握するためのメトリクスです。数値は目安であり、プロジェクトに応じて調整してください。

| メトリクス | 定義 | 測定方法 | 健全な目安 |
|-----------|------|---------|-----------|
| セッション継続性 | 前セッションの意図を再開できるか | 5分以内に前回の論点を把握し、作業を継続できれば「成功」 | 成功率 > 80% |
| 設計-コード整合性 | 原則がコードに反映されているか | design.md の原則数に対する実装済み原則の割合 | > 70% |
| ドキュメント鮮度 | design.md が現状を反映しているか | 最終更新からの経過日数 | < 1週間 |
| Binding 整合性 | コードがすべての Binding Decision を守っているか | 守られている Binding Decision の割合 | 100% |

「セッション継続性」の補足：厳密に測定する必要はありません。「前回何をしていたか思い出せない」「LLM に一から説明し直している」という状況が頻発するなら、design.md の粒度か更新頻度に問題があります。

-----

## 🛠️ §7 実装オプション

### Option 1: Pure Discipline
ツールなし、規律のみ。最も軽量。まずはここから始めることを推奨します。

### Option 2: Template-Based

```markdown
# design.md Template
## Intent
## Scopes
## Experience
## Binding Decisions
## Direction
## Acceptance Gates
## Core Principles
## Validation
## Open Questions
## Changelog
```

> あくまで出発点です。合わなければ捨ててください。Experience を先に書き、Binding Decisions・Direction・Acceptance Gates は必要なときだけ使います。Scopes と Validation は、コマンドが並列化と検証のために読む節です。

### Option 3: Workflow Integration
PR チェックリストに Reflect を組み込む。チーム開発向け。

### Option 4: Tool-Assisted

コマンドは DDL を Phase ベースのワークフローとして実装し、Detection Targets、STOP gates、並列ワーカー (+++SWARM) をサポートします。

**コアループ** — Draft → Realize → Reflect サイクル：

| コマンド | 目的 |
|---------|------|
| `/draft` | 体験を、それが依存する決定と見通しとともに先に書く |
| `/realize` | 設計原則に基づいてコードを書く |
| `/reflect` | 実装結果をドキュメントに反映する |

**サポートコマンド** — 任意のタイミングで実行可能：

| コマンド | 目的 |
|---------|------|
| `/validate` | scope ごとの機械的検証（lint/test/build） |
| `/resonate`（このリポジトリ専用、examples/ には含まない） | 多言語ドキュメントの同期 |
| `/commit` | 検証済み変更のリポジトリ記録 |
| `/docs` | ドキュメント品質の監査・修正 |
| `/refactoring` | コード品質の監査・修正 |

各コマンドは共通の構造に従います：
1. **Phases** — 順序付きステップ（INIT → SURVEY/READ → WORK → REPORT (+++STOP) → EXECUTE → VERIFY）
2. **Detection Targets** — 各フェーズの中で並列に走る自動チェック（コマンドごとに D1、D2、…）
3. **+++SWARM** — 2つ以上のスコープが存在する場合に、実行環境の仕組み（Claude Code のサブエージェント、Codex のサブエージェント）でスコープごとに並列実行する。仕組みがなければリードが割り当てを自分で実行し、読み取りだけの作業は並列の読み取りで、その他は一つずつ処理する
4. **STOP gates** — 共有アーティファクト変更前の必須人間承認。エージェントは手番を終えて待つ
5. **Constraints** — 決して違反してはならない不変条件
6. **Runtime adapters** — protocol の一つの表がディレクティブを各ハーネスに対応づけるため、コマンドは実行環境のツール名を書かない

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

binding:
  - decision: "Python (asyncio)"
    why: "体験が非同期の利用コードそのもの: async with APIClient(...)"
    source: "「async with で使いたい」(2026-10-17)"

session:
  last_topic: "認証フローの設計"
```

自動検証やセッション継続性の追跡が可能になります。ただし、ツールが目的化すると本末転倒です。

-----

## 📦 §8 成果物とライフサイクル

| Name | Purpose | 永続性 |
|------|---------|--------|
| design.md | 設計思想、概念定義 | 一時的 |
| Direction（design.md 内） | 実装までの見通し | 最も一時的: 全段階が終われば削除 |
| Acceptance Gates（design.md 内） | 完了の定義 | すべてのゲートに passed の記録がつけば作業は受け入れ済みとなり、残す検証を Validation に移してから削除する |
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
- Binding Decisions はコードが具現化したら README の要件や ADR に移す（コードは何を選んだかを示すが、なぜかは示さない）。移すのは `/reflect` で人間が承認したときに限り、移した後はコマンドが照合しなくなる
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

### AI-Era Development Paradigms
- Thoughtworks (2025). [Spec-Driven Development: Unpacking one of 2025's key new AI-assisted engineering practices](https://www.thoughtworks.com/en-us/insights/blog/agile-engineering-practices/spec-driven-development-unpacking-2025-new-engineering-practices).
- Fowler, M. et al. (2025). [Understanding Spec-Driven-Development: Kiro, spec-kit, and Tessl](https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html). *martinfowler.com*.
- Marmelab (2025). [Spec-Driven Development: The Waterfall Strikes Back](https://marmelab.com/blog/2025/11/12/spec-driven-development-waterfall-strikes-back.html).
- AWS (2025). [AI-Driven Development Life Cycle: Reimagining Software Engineering](https://aws.amazon.com/blogs/devops/ai-driven-development-life-cycle/). *AWS DevOps Blog*.
- GitHub (2025). [Spec Kit](https://github.com/github/spec-kit). *GitHub*.
- Anthropic (2025a). [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents). *Anthropic Engineering*.
- Lopopolo, R. (2026). [Harness engineering: leveraging Codex in an agent-first world](https://openai.com/index/harness-engineering/). *OpenAI*.

### Context Engineering
- Anthropic (2025b). [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents). *Anthropic Engineering*.
- Anthropic (2025c). [Equipping agents for the real world with Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills). *Anthropic Engineering*.
- Ji, Y. (2025). [Context Engineering for AI Agents: Lessons from Building Manus](https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus). *Manus*.
- Anthropic (2026). [How Claude remembers your project](https://code.claude.com/docs/en/memory) and [Context window](https://code.claude.com/docs/en/context-window). *Claude Code documentation*（2026-10-17 取得）.
- OpenAI (2026). [Custom instructions with AGENTS.md](https://developers.openai.com/codex/guides/agents-md) and [Memories](https://developers.openai.com/codex/customization/memories). *Codex documentation*（2026-10-17 取得）.

### Related Methodologies
- Knuth, D. (1984). [Literate Programming](https://academic.oup.com/comjnl/article/27/2/97/343244). *The Computer Journal*, 27(2), 97-111.
- Nygard, M. (2011). [Documenting Architecture Decisions](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions). *Cognitect Blog*.
- Beck, K. (1999). [*Extreme Programming Explained*](https://www.oreilly.com/library/view/extreme-programming-explained/0201616416/). Addison-Wesley.
- Meyer, B. (1992). [Applying Design by Contract](https://ieeexplore.ieee.org/document/161279/). *IEEE Computer*, 25(10), 40-51.

-----

## 📝 Changelog

| Date | Change |
|------|--------|
| 2026-10-17 | ハーネス時代の改訂: ハーネスの記憶と design.md（§1.1, §1.4）、ハーネスエンジニアリングと技術の選択（§2.5）、状態モデルの VALIDATE（§3.1）、ハーネスのセッション状態（§3.2）、Binding と Direction の照合（§3.3, §3.4）、G1〜G7 の ID（§3.4）、STOP の意味論と並列ワーカー（§3.5, §3.6）、Example 4、§5・§6・§8 の Binding Decisions、テンプレートの節（§7）、参考文献3件。追補: passed の記録と Acceptance Gates の削除（§3.3, §3.4, Example 4, §8）、STOP 中のワーカーの起動と継続の禁止と通知・他のエージェントによる承認の否定（§3.5）、ワーカーのラベル・それだけで足りる指示・指示に書く読み取り専用と入れ子の起動の禁止（§1.4, §3.6）、用語の統一（§3.6 と §7 の Codex のサブエージェント、§7 の「D1、D2、…」）、実行環境の指示ファイルが指定する共有ノート（§5）、protocol の役割の順に並べた Phases（§7）。共有ノートの名前を design.md に統一。`Unbound:` 行、承認された選択、Binding Decision を変える引数、既存の前提（§2.5）。ゲートを落とさない規則（§3.3）。REPORT を STOP gate で終えることと、承認された報告になかった承認点を事前承認の対象外とすること（§3.5）。並列の仕組みがないときのリードの実行（§3.6, §7）。`/resonate` をこのリポジトリ専用と明記（§3.1, §7）。報告の承認を Binding Decision の出典とすること（§5）。読み方の表に §6〜§8 を追加。`/draft` の目的（§7）、コンテキストエンジニアリング（§1.4, §2.5, §3.5, §3.6）とその参考文献 |
| 2026-04-25 | VALIDATE サポートコマンド（§3.1, §7）、README を共有ノートとして使う代替（§5） |
| 2026-02-14 | §2.5 を三者比較（SDD / AI-DLC / DDL）に拡張 |
| 2026-01-04 | 初版 |