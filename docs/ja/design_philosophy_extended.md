# Design-Doc Loop (DDL) - Extended

> このドキュメントは [design_philosophy.md](./design_philosophy.md) を補足します。
> DDL の中核の設計を理解したあとに、必要に応じて参照してください。

-----

## 🗺️ 読み方

このドキュメントは辞書のように引いて使うことを想定しています。

| 目的 | 節 |
|------|---------|
| 理論的な背景を理解する | [§1 認知の基盤](#-1-認知の基盤) |
| 既存の方法論と比較する | [§2 関連する方法論](#-2-関連する方法論) |
| モデルが何をいつ読み込むかを知る | [§2.5 コンテキストエンジニアリング](#コンテキストエンジニアリング) |
| ハーネスがどの規則を執行するかを知る | [§2.5 指示と仕組み](#指示と仕組み) |
| 運用を体系化する | [§3 体系化の枠組み](#-3-体系化の枠組み) |
| 具体例を得る | [§4 実践例](#-4-実践例) |
| 導入を判断する | [§5 採用の基準](#-5-採用の基準) |
| 効果を測る | [§6 指標](#-6-指標) |
| DDL の実装方法を選ぶ | [§7 実装の選択肢](#️-7-実装の選択肢) |
| 成果物とそのライフサイクルを管理する | [§8 成果物とライフサイクル](#-8-成果物とライフサイクル) |

通読する必要はなく、必要な箇所だけを拾ってください。

-----

## 🧩 §1 認知の基盤

DDL は認知科学と哲学のいくつかの理論と接点を持ちます。これらは後付けの正当化ではなく、設計の際に参照した枠組みです。

### 1.1 Extended Mind（拡張された心）

Clark & Chalmers (1998) は「Extended Mind（拡張された心）」、すなわち認知は脳の中で完結せず外部のツールと一体になるという考えを提唱しました。

有名な **Inga/Otto の思考実験** では Inga は美術館の住所を生物学的な記憶で覚えており、アルツハイマー病の Otto はそれをノートに記録しています。Clark は Otto のノートが Inga の記憶と**機能的に等価**だと論じました（Clark & Chalmers, 1998; Clark, 2008）。

DDL の design.md はこの「Otto のノート」に相当します。

| 機能的等価の条件 | Otto のノート | design.md |
|------------------|---------------|-----------|
| 常に利用できる | 常に携帯している | リポジトリにある |
| 直接アクセスできる | すぐに参照できる | セッション開始時に読み込まれる |
| 自動的に信頼される | 疑わずに従う | 設計原則として尊重される |
| 過去に意識的に記録された | 意図的に書き留めた | Draft/Reflect で明示的に記録される |

この表が DDL の設計根拠です。design.md はこの四つの条件を満たすことで、人間と LLM からなる系の「拡張された記憶」として機能します。

**ハーネスの記憶はノートではありません。** エージェントのハーネスはいまでは自前の記憶を持っています。指示ファイル、自動メモリ、長い会話の要約、次のセッションのために書かれた進捗ファイルがそれです。その記憶はエージェントにとっては最初の二つの条件を満たします。一方で人間にとっては、エージェントがそこに書いたものは多くの場合四つ目の条件を満たしません。書いたのはエージェントであり、人間はそれを意識的に承認したことがないからです。design.md は双方が合意した部分であり、両者は補い合う関係にあって、一方が他方に取って代わることはありません。

```
Traditional: Brain -> Thinking -> Action

DDL:  Human Brain <-> design.md <-> LLM
                  |
          One cognitive system
```

### 1.2 SECI モデル

野中の SECI モデル（Nonaka & Takeuchi, 1995; Nonaka, Toyama, & Konno, 2000）は、暗黙知と形式知のあいだの変換サイクルを記述します。

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

DDL との対応は次のとおりです。

| フェーズ | DDL での例 |
|----------|------------|
| Socialization | 人間と LLM の対話で「こんな感じ」を共有する |
| Externalization | Draft で体験を言語化する |
| Combination | design.md を構造化し、原則間の関係を整理する |
| Internalization | 次のセッションで design.md を読んでコンテキストを復元する |

SECI には「経験的な根拠が弱い」という批判があります（Gourlay, 2006）。DDL は実践で検証できる具体的な手法を示すことで、この批判に応えます。

### 1.3 Distributed Cognition（分散認知）

Hutchins (1995) は「Distributed Cognition（分散認知）」、すなわち認知はチーム、ツール、環境に分散しているという見方を提唱しました。

Flor & Hutchins (1991) はペアプログラミングを分析し、系全体が個々のプログラマとは異なる認知的な性質を持つことを示しました。DDL はこの分散した構造を明示的に設計します。

```
  Human <-------> Document <-------> LLM
    |                |                |
 Intuition       Shared           Pattern
 Long-term       Memory           Recognition
 Values          Persist          Tech Knowledge
```

何をどこに委ねるかという意識が DDL の核です。

### 1.4 人間と AI の協調研究

LLM との協調に関する研究は 2024-2025 年に急増しました。

**セッションの断絶という問題**: チャットのアシスタントは何年も前から記憶を備えており、コーディングのハーネスもいまでは指示ファイル、自動メモリ、長い会話のコンパクション（会話の圧縮）という自前の記憶を持つようになりました。DDL が扱う問題はモデルが忘れることではありません。ハーネスが覚えていることが人間の合意したものではないこと、エージェントとハーネスをまたいで共有されないこと（SWARM のワーカーがリードの会話を引き継ぐかどうかは実行環境とワーカーの起動のしかたによります）、そして有限であることが問題です。有限なのはコンテキストに載るものが増えるほどモデルがその中身を思い出せなくなるからです（Anthropic, 2025b）。design.md はこの三つすべてに応えます。すなわち、design.md は人間が合意したことだけを載せ、すべてのセッションが同じファイルを読み、リードが各ワーカーのプロンプトをそこから組み立てるので、並列に走る五つのワーカーはプロンプトに書かれたこと以外を必要としません。

**認知の拡張としての LLM**: Sabbah & Li (2025) は LLM が人間の限定合理性を補完できると論じています。

| 人間の制約 | LLM による補完 | DDL での実現 |
|------------|----------------|--------------|
| 限定合理性 | 網羅的な探索 | Draft で選択肢を広げる |
| 満足化 | 最適解の追求 | Realize で原則に照らす |
| 不確実性の回避 | リスク評価 | 対話で検討する |

LLM は人間を置き換えるのではなく補完するものであり、DDL はこの補完関係を構造化します。

-----

## 🔗 §2 関連する方法論

DDL には既存の方法論と重なる部分があるので、車輪の再発明を避けるために違いを明確にします。

### 2.1 Documentation-Driven Development (DocDD)

DocDD は Knuth の Literate Programming (1984) の系譜にあり、「説明しにくいものは設計が悪い」という洞察に基づいています。

| 観点 | DocDD | DDL |
|--------|-------|-----|
| 方向 | 一方向（Doc→Code） | 双方向（Doc⇄Code） |
| 目的 | 仕様を確定する | 共有記憶を維持する |
| 永続性 | ドキュメントは成果物 | ドキュメントは一時的 |

### 2.2 Architecture Decision Records (ADR)

ADR は Nygard (2011) が普及させたもので、設計上の決定とその根拠を記録します。

| 観点 | ADR | DDL |
|--------|-----|-----|
| タイミング | 決定後（静的） | 決定中（動的） |
| 更新 | 追記のみ | 書き換え可能 |
| 粒度 | アーキテクチャのレベル | 概念から実装まで |

DDL のドキュメントが安定した時点で ADR に昇格させるのは妥当なワークフローです。

### 2.3 Test-Driven Development (TDD)

TDD は Beck (1999) による XP の中核のプラクティスです。

| 観点 | TDD | DDL |
|--------|-----|-----|
| 先に定義するもの | テスト | Experience（理想の API） |
| フィードバックループ | Red→Green→Refactor | Draft→Realize→Reflect |

TDD と DDL は直交していて共存でき、Draft → テスト → 実装は自然な流れです。

### 2.4 Design by Contract (DbC)

DbC は Meyer が Eiffel で形式化したものであり（Meyer, 1992）、契約（不変条件）を明示します。

| 観点 | DbC | DDL |
|--------|-----|-----|
| レベル | コード（実行可能） | 設計方針（概念的） |
| 執行 | 実行時の検査 | 規律と対話。アダプタが対応できるところでは、機械的な部分をハーネスが執行する（§2.5） |

### 2.5 AI 時代の開発パラダイム（2025–2026）

AI 支援開発を構造化する三つのアプローチが 2025–2026 年に登場し、それぞれ出自も解く問題も異なります。

| 出自 | パラダイム | 中核の問題 |
|------|------------|------------|
| プロダクト開発 | Spec-Driven Development (SDD) | 仕様がなければ AI は誤ったコードを生成する |
| エンタープライズ開発 | AI-Driven Development Life Cycle (AI-DLC) | SDLC は AI を主たる実行者として想定していない |
| 研究・探索的開発 | Design-Doc Loop (DDL) | 設計意図がセッションをまたいで失われる |

三者には、構造のない AI コーディング（"vibe coding"）はスケールしないという共通の背景があります。それぞれが人間と AI の関係を異なる形で構造化しています。

#### SDD の要点

SDD は自然言語で仕様を書き、そこから AI にコードを生成させる方法です。SDD は単一の方法論ではなく、複数のツール（GitHub Spec Kit, Kiro, Tessl）のあいだで大きく異なります（Thoughtworks, 2025; Fowler et al., 2025）。仕様が正（source of truth）であり、コードはそこから導かれます。

#### AI-DLC の要点

AI-DLC は AWS 発の方法論（Raja SP et al., 2025）であり、AI を主たる実行者として SDLC 全体を設計し直します。フェーズは Inception（モブエラボレーション → 要件）、Construction（モブコンストラクション → コード）、Operation（AI が監視するデプロイ）の三つです。アジャイルの用語も定義し直しており、スプリントはボルト（数時間から数日）に、エピックは作業単位（units of work）になります。人間の役割は AI の提案を検証し承認することです。

#### ハーネスエンジニアリングの要点

2025–2026 年にはモデルを取り巻くハーネスがそれ自体で工学の対象になりました。Anthropic が示した長時間動くエージェントのためのハーネスでは、初期化役のエージェントが環境を整え、以後の各セッションは進捗ファイル、機能リスト、git のログを読んでから作業を選びます（Anthropic, 2025a）。OpenAI のハーネスエンジニアリングの報告が取り上げるのは手で書いたコードが一つもない製品です。そこではエンジニアが環境を設計し、意図を指定し、フィードバックループを作り、コードは Codex が書きます（Lopopolo, 2026）。

これらのハーネスが記録し指定するもののうち、DDL が扱うのは人間が合意しなければならない部分、すなわち体験、それを拘束する決定、人間が確認するゲートです。

#### コンテキストエンジニアリング

2025 年の終わりにはこの分野に名前がついていました。Anthropic の応用 AI チームはコンテキストを「限界収益が逓減する有限の資源」と表現しました。コンテキストウィンドウが埋まるほどモデルはその中身を思い出せなくなるので、エージェントは行動に足るだけの信号の濃いトークンを最小限だけ保ち、残りは必要になった時点で取り出し、長い会話はコンパクションで要約にまとめ、焦点を絞ったサブエージェントにはまっさらなコンテキストウィンドウを与えるべきだというのです（Anthropic, 2025b）。Agent Skills は同じ考えを指示に当てはめており、起動時には各スキルの名前と説明だけが読み込まれ、本文はスキルが使われるときに読み込まれます（Anthropic, 2025c）。Manus は本番運用から同じ教訓を報告しています。その教訓とは、ファイルシステムを容量に限りがなく永続するコンテキストとして扱うこと、誤った道筋の記録を残すこと、いまの目標をコンテキストの末尾に繰り返し書くことです（Ji, 2025）。ハーネスは自分が何を読み込むかを文書で公開しています。Claude Code はセッション開始時にユーザーとプロジェクトの指示ファイルと自動メモリを読み込み、コマンドは呼び出されたときに読み込み、コンパクションのあとは会話そのものが要約される一方でプロジェクトの指示ファイルと自動メモリをディスクから入れ直します（Anthropic, 2026）。Codex は作業の前に AGENTS.md の連鎖を実行ごとに一度読み、スキルを名前と説明で一覧にし、memories を「常に適用されなければならない規則の唯一の出どころではなく、役に立つ想起の層」として扱います（OpenAI, 2026）。

DDL は人間の側から行うコンテキストエンジニアリングです。「モデルは動く前に何を見るべきか」という問いは、常にコンテキストにあるもの、コマンドが走るときに読み込まれるもの、リードが各ワーカーのために用意するものの三つに分かれます。

| 層 | 中身 | 読み込み | 持ち主 |
|----|------|----------|--------|
| 指示ファイル（`CLAUDE.md`、`AGENTS.md`） | ここでの働き方: プロトコルの探索先、全体の制約、G1–G7 | セッション開始時。Claude Code はコンパクションのあとにプロジェクトのファイルを入れ直す | 人間 |
| design.md | 人間が合意したこと: Experience、Binding Decisions、Direction、Acceptance Gates、原則、スコープ、検証 | セッション開始時。コンパクションのあとはアダプタが入れ直し（Claude Code ではプロジェクトの指示ファイルとともに取り込み、Codex では SessionStart の注入）、コンテキストにないときに限りコマンドが Phase 0 で読み直す | ループを通じた人間と LLM |
| プロトコルとコマンド | コマンドの動き方（コマンドはスキルであり、Claude Code では `.claude/skills/<name>/SKILL.md`、Codex では `.agents/skills/<name>/SKILL.md`） | コマンドが呼び出されたとき（Phase 0）と、コンパクションのあとにコンテキストから消えていればもう一度。プロトコルは両方の実行環境で `ddl-protocol` というスキルである（本文は一つで、Codex の写しは生成される）。プロジェクトの写しがあればそれを、なければ利用者レベルの写し（`$HOME/.claude/skills/`、`$HOME/.codex/skills/`）を読む。コマンドはプロトコルを参照し、決して複製しない | 方法論 |
| ワーカーのプロンプト | 一つのスコープのパス、そのスコープが担う Experience の項目、原則、Binding Decisions、Direction の段階、スコープの検証コマンド、そのフェーズで人間が承認した行（逐語）、`/realize` では承認された計画 | リードが並列に割り振るとき。ワーカーはプロンプトが名指しするファイルと design.md の節だけを読む | design.md から組み立てるリード |
| 自動メモリ、コンパクションの要約、進捗ファイル | エージェントの作業状態 | ハーネスによって | エージェント。決して決定の出どころにはならない |

ここから三つの帰結が導かれます。第一に、予算です。ループが退役させる節（使い終えた Direction、受け入れられた Acceptance Gates）はどれも以後のセッションが支払わずに済むコンテキストなので、「DDL のドキュメントは一時的である」はコンテキストの規則でもあります。第二に、会話は永続しません。コンパクションの要約はユーザーの発言ではなく、何も承認しません。STOP が承認を求めた報告がコンテキストに逐語で残っていなければ、コマンドはそれを design.md と git とその報告が挙げたファイルから組み立て直して改めて承認を求めます。要約のあとに与えられた承認はその要約のあとに出された報告にだけ適用されます。再起動で中断された STOP は再開されず、コマンドは止まったフェーズからやり直し、ゲートが `passed` と記された段階は飛ばします。人間が承認したものは何であれその場で書き留められます（下書きは design.md へ、通ったゲートはその印へ、委任された選択は表へ、事前承認はそのゲートへ、承認された計画は Direction へ）。第三に、記憶は合意ではありません。自動メモリにしか存在しない決定は design.md が記録するまで提案にとどまります。

#### 指示と仕組み

いまではハーネス自身がプロトコルの一部を実行します。Claude Code も Codex も、ツール呼び出しの前やセッション開始時にスクリプトを走らせるライフサイクルの hook、ワーカーにできることを固定するエージェント定義、ファイルを毎セッション読み込ませる取り込みや注入、外に出る操作の前で止まる権限規則を備えています（Anthropic, 2026; OpenAI, 2026）。DDL はサブエージェントをすでに使ってきたのと同じやり方でこれらを使います。コマンドとプロトコルが規則を述べ、プロトコルの実行環境の対応表（プロトコルの §2.5）が各実行環境での実装の仕方を示し、実装そのものは実行環境ごとの小さなアダプタ（Claude Code では `.claude/settings.json`、`.claude/agents/`、`.claude/hooks/` と `.claude/CLAUDE.md` の取り込み行、Codex では `.codex/`。利用者レベルの導入では同じファイルが `$HOME/.claude/` と `$HOME/.codex/` の下にある）に置かれます。こうした実装を持つディレクティブは次の四つです。

| ディレクティブ | 規則 | 仕組み |
|----------------|------|--------|
| `+++STOP` | 報告のあと手番は終わり、人間が発言するまで何も変更されない | ゲートの hook が会話の記録を読み、`+++DDL_REPORT` のあと次の人間の発言まで、編集、書き込むシェルコマンド、ワーカーの起動、MCP ツールの呼び出しを拒む |
| Phase 0 | design.md はどの作業の前にもコンテキストにある | 指示ファイルでの取り込み（Claude Code）かセッション開始時の注入（Codex）。どちらもコンパクションのあとに繰り返される |
| `+++SWARM` の `type:` | 読み取り専用のワーカーは何も編集せず、ワーカーも起動しない。どのワーカーもワーカーを起動しない | 両実行環境にある `explorer` と `worker` という名前のエージェント定義。実行環境が許すところでは、定義が `explorer` から編集のツールを、両方からエージェントのツールを外し、起動の深さは1になる |
| `+++NEVER`（外に出る操作、帰属表記） | push は実行時に確認され、コミットに AI の帰属表記を付けない | `git push` の前に確認を求める権限規則と、帰属表記を切る設定 |

三つの規則がこれを後付けではなく有機的なものに保ちます。第一に、仕組みはハーネスが機械的に判定できることだけを執行します。ゲートが知っているのは報告が出たことと、それ以来人間が発言していないことだけです。返事が承認かどうかは言葉の問題であり、エージェントの判断に委ねられます。第二に、規則は仕組みの有無で変わりません。未信頼のプロジェクト、hook のないセッション、アダプタのない実行環境でも、同じコマンドが同じ規則のもとで指示として動きます。アダプタは執行を足すだけで、規則を足すことは決してありません。第三に、人間の操作はどの実行環境でも同じです。止まる場所も、続ける言葉も、design.md に書かれる行も同じです。違うのはエージェントが逸れたときにハーネスがどこまで捕らえるかであり、その差は日付を添えて実行環境の対応表に書かれ、コマンドには書かれません。

#### 構造の比較

| 観点 | SDD | AI-DLC | DDL |
|------|-----|--------|-----|
| 問題 | AI のコード品質 | 開発速度 | 認知の連続性 |
| AI の役割 | 生成器 | 成果物を提案するチームメイト | 対等なパートナー |
| 人間の役割 | 仕様の著者 | 検証者 / 承認者 | 共に考える者。フェーズごとに役割が移る |
| 方向 | Spec→Code（一方向） | AI が提案→人間が承認 | Doc⇄Code（双方向） |
| 知識の流れ | 仕様→コード | AI の成果物→人間のレビュー | 設計哲学⇄実装 |
| イテレーションの単位 | 仕様のライフサイクル | ボルト（数時間から数日） | Reflect のループ（固定の周期なし） |
| ドキュメントのライフサイクル | 仕様が正 | 成果物はプロセスの副産物 | ドキュメントは一時的。コードが正になる |
| 想定する規模 | プロダクト仕様を持つチーム | エンタープライズ（10–100 人以上） | 少人数チーム / 個人（1–5 人） |

#### セッションの断絶

各アプローチはセッションの問題を異なる形で扱います。

| パラダイム | 戦略 | 仕組み |
|------------|------|--------|
| SDD | 仕様を永続させる | コードは仕様から再生成できる。仕様はセッションを超えて残る |
| AI-DLC | プロセスの成果物を永続させる | 要件、ストーリー、ユニットをリポジトリに保存する |
| ハーネスエンジニアリング | エージェントの進捗を永続させる | 進捗ファイルと機能リストを各セッションの開始時に読む（Anthropic, 2025a） |
| DDL | 設計を共有記憶とする | design.md がセッション間の認知の橋になる |

SDD と AI-DLC は永続化をワークフローの副作用として扱い、ハーネスエンジニアリングはエージェントの作業状態を永続させます。DDL が中心の設計問題として扱うのは、人間が合意したことを永続させることです。

#### 技術の選択

Spec Kit は技術を仕様の外に置いており、`/speckit.specify` が何をなぜ作るかを記述し、`/speckit.plan` がスタックを指定します（GitHub, 2025）。DDL は両方を一つの Draft に、ただし別々の節に置き、それぞれの技術について、なぜ体験を拘束するのかを問います。人間が理由とともに挙げた技術（体験がそれに依存する、外部の制約がそれを求める、人間がそれを好むと明言する）は Binding Decision になります。LLM の提案、理由なく挙げられた技術、委任された選択は、表の下に `Unbound:` として列挙され、何も拘束しません。`Unbound:` の行は `/realize` に委任された行か `awaiting choice` の行のどちらかです。委任された行については `/realize` が計画の中で自らの選択とその理由を述べ、選択待ちの行については `/realize` が人間に選ぶよう求めます。選択が拘束するのは人間がその計画を承認したときだけであり、そのとき選択は Source を `approved in /realize plan (<date>)` として表に移ります。いったん承認されると、design.md は以後のコマンド引数に優先します。引数で挙げられた別の技術は Binding Decision の変更にあたり、コマンドはそこで停止します。コードにすでにある技術は既存の前提であり、コマンドは報告でそれを示し、design.md には記録しません。それが Binding Decision になるのは人間が理由を述べたときだけです。

#### 補完的な使い方

これらのパラダイムは異なる層を占めており、共存できます。

- DDL の Realize フェーズは SDD 流の仕様記述を使える。実装の前に仕様を書くことは Realize の一つの方法である
- AI-DLC のモブエラボレーションは DDL の Reflect を取り込み、実装での発見を要件に還流できる
- SDD と AI-DLC は哲学の進化（実装を通じて設計原則が変わること）を扱わない。DDL は扱う
- ハーネスの記憶（進捗ファイル、自動メモリ）はエージェントの作業状態を、design.md は人間が合意したことを収める。両者は分けておく。エージェントの進捗を design.md に写さず、拘束する決定をエージェントの記憶だけに残さない

「ウォーターフォール批判」（Marmelab, 2025）は SDD の一方向の流れに当てはまります。AI-DLC は短いボルトでこれを和らげ、DDL は双方向のループでこれを完全に回避します。

DDL の役割の流動性は少人数チームの探索的な文脈で機能します。監査証跡と明確な説明責任を求めるエンタープライズの文脈では、AI-DLC の固定した役割（AI が提案し、人間が承認する）の方が適切な場合があります。これは弱点ではなく、異なる運用上の制約を反映したものです。

-----

## 🔧 §3 体系化の枠組み

§3 は DDL をより体系的に運用するための枠組みです。理解と運用の補助として使ってください。この枠組みのうち機械的な部分はハーネスのアダプタ（§2.5）が執行し、残りは規律です。

### 3.1 状態モデル

DDL は**コアループ**と**サポートコマンド**の二つの層で動きます。

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

サポートコマンド（どの時点でも呼び出せる）:
    +--------+  +---------+  +------+  +------------+  +---------+
    |VALIDATE|  |RESONATE |  |COMMIT|  |REFACTORING |  |  DOCS   |
    +--------+  +---------+  +------+  +------------+  +---------+
```

コアループが設計の進化を駆動し、サポートコマンドがそれを取り巻く品質を保ちます。

| 状態 | 開始条件 | 終了条件 |
|------|----------|----------|
| DRAFT | 新機能またはプロジェクトの開始 | Experience が言語化され、Binding Decisions、Direction、Acceptance Gates があれば記録されている |
| REALIZE | design.md が存在する | コードが原則と Binding Decisions を体現し、ゲートが通る |
| REFLECT | コードが書かれた | 設計が更新された |

| サポートコマンド | 目的 |
|------------------|------|
| VALIDATE | design.md に宣言されたとおりにスコープごとの機械的な検証を走らせる |
| RESONATE | 多言語のドキュメントの版を同期する |
| COMMIT | 検証済みの変更をリポジトリに記録する |
| DOCS | ドキュメントの品質を監査して直す |
| REFACTORING | コードの品質を監査して直す |

コアループのどの状態からもほかのどの状態へも遷移でき、厳格な順序はありません。サポートコマンドはどの時点でも呼び出せます。

### 3.2 セッションコンテキストの保持

セッションの断絶という問題に対処するために、保持すべき情報を整理します。

```yaml
session:
  last_topic: "認証フローの設計"
  pending_decisions:
    - "JWT トークンの保存場所"
  open_questions:
    - "リフレッシュトークンの有効期限は？"
  state: REALIZE
```

次のセッションは「前回は X について議論していました」から再開します。

いまではハーネス自身がこの種のセッションの状態を保持しています（自動メモリ、会話の要約、進捗ファイル）。design.md には人間が見て受け入れたことだけを残します。すなわち、未決の技術選択は `Unbound:` の行として、ほかの未決の事項は Open Questions に、決まった事項は Experience、Binding Decisions、Principles に書きます。

### 3.3 設計とコードの整合性の検証

Reflect を支える観点は次のとおりです。

| 種類 | 内容 | 対処 |
|------|------|------|
| DRIFT | コードが原則に違反している | 原則を更新するか、コードを直す |
| NEW_PATTERN | 文書化されていないパターンが見つかった | 原則として加える |
| OUTDATED | 実装のない原則 | 削除するか、実装する |
| BINDING_DRIFT | コードが Binding Decision から外れている | 人間が選ぶ: コードを直すか、決定を変える |
| SPENT_DIRECTION | Direction の段階が `passed` と記されている | 結果で置き換えて `Approved plan` の行を消し、すべての段階が終わったら節を消す |
| SPENT_ACCEPTANCE | すべての Acceptance Gate が `passed` と記され、作業が受け入れられている | 長く残る検査を Validation に移し、節を消す |
| EXPERIENCE_GAP | Experience が記述していない状態をコードが扱っている、または Experience の項目をコードが実現していない | その状態を Experience に加えるか、コードにその項目を実現させる |

これらの分類は、より広い Detection Targets の体系（§3.4）の部分集合です。

**`passed` の印**: `/realize` は通ったゲートごとに `passed <date>` を書き足します。その場所は Direction では段階の Gate のセル（例: `human approval, passed 2026-10-20`）であり、Acceptance Gates ではゲートの後ろです。事前承認は人間が与えた時点で同じ場所に `approved in advance (<date>)` として書かれ、段階か作業が終わると `passed <date>` がそれに続きます。承認された `/realize` の計画も同じ理由で Direction の下に `Approved plan (<date>)` として書かれます。あとのセッションやコンパクションを経たセッションがそこからワーカーのプロンプトを組み立て直すためです。作業が受け入れられるのはすべての Acceptance Gate が `passed` と記されたときです。`/reflect` はこれらの印だけを読み、会話の記憶から通ったと推し量ることは決してしません。

ゲートが消えることは決してありません。統合された段階はそのゲートを自分の末尾に残し、飛ばされた段階のゲートは次の段階の末尾へ、それが最後の段階なら作業の末尾へ移り、順序を入れ替えられた段階はそのゲートをそのまま持ちます。

### 3.4 Detection Targets

Detection Targets はコマンドの各フェーズの中で並列に走る自動の検査であり、問題が広がる前に捕らえます。

各コマンドは自分の目的に固有の D ターゲット（D1、D2、…）を定義します。コマンドを横断するターゲットは次のとおり全体に適用されます。

| ID | 名前 | トリガー |
|----|------|----------|
| G1 | Vague Intent | タスクの記述に測定できる成果がない |
| G2 | Scope Creep | 変更が宣言されたスコープの外のファイルに触れている |
| G3 | Principle Violation | 操作が design.md の原則と矛盾している |
| G4 | Missing Validation | 変更のあとに検証の手順がない |
| G5 | Leaked Specifics | プロジェクト固有のパスやコマンドが枠組みのファイルにハードコードされている |
| G6 | Silent Failure | エラーがユーザーへの通知なく握りつぶされている |
| G7 | Unreviewed Mutation | 共有の成果物が STOP ゲートなしに変更されている |

例: `/reflect` は独自のターゲット（D1 Drift, D2 New Pattern, D3 Outdated Principle, D4 Stale Reference, D5 Self-Contradiction, D6 Binding Drift, D7 Spent Direction, D8 Spent Acceptance Gates, D9 Experience Gap）を定義しつつ、全体のターゲットにも従います。`/draft` は D6 Unanchored Binding（理由も出どころもない Binding Decision）と D7 Binding Conflict を加え、`/realize` は D6 Binding Violation と D7 Validation Failure を加えます。

### 3.5 STOP ゲート

STOP ゲートは人間の承認を必須とする地点です。システムは共有の成果物を変更する前に停止し、見つけたことを提示します。

```
Phase N: 分析完了
    ↓
[STOP ゲート]: 報告を提示し、承認を待つ
    ↓
Phase N+1: 承認された変更だけを適用
```

規則は次のとおりです。
- STOP ゲートは**ブロッキング**であり、自動では決して先に進まない
- STOP はエージェントの手番を終える。`+++DDL_REPORT` の見出しの下に報告し、問い、止まる。作業が再開するのは明示的な承認があったときだけであり、そのあいだに変更は一つもない
- STOP からその承認までのあいだはどのワーカーも動き始めず、動き続けもしない。ワーカーが読み取り専用なのは実行環境のアダプタがその書き込みのツールを外すところだけであり、保証されているところはどこにもない。アダプタにゲートの hook があるところ（§2.5）ではハーネスが呼び出しを拒み、ほかではこの規則が指示として成り立つ
- 承認するのは人間だけである。実行環境の通知（たとえばワーカーの完了）や、ほかのエージェントやセッションからのメッセージは承認ではない
- 会話の要約（コンパクション）はユーザーの発言ではなく、何も承認しない。STOP が承認を求めた報告がコンテキストに逐語で残っていなければ、コマンドはそれを design.md と git とその報告が挙げたファイルから組み立て直して改めて承認を求める。要約のあとに与えられた承認はその要約のあとに出された報告にだけ適用される。再起動で中断された STOP は再開されず、コマンドは止まったフェーズからやり直し、ゲートが `passed` と記された段階は飛ばす。会話は永続しないので、人間が承認したものはその場で書き留められる
- すべてのコマンドは REPORT を STOP ゲートで終える
- design.md に書かれた人間のゲート（Direction の Gate 列、Acceptance Gates の中の人間のゲート）は STOP ゲートとして走る
- 承認された報告に載った design.md の人間のゲートを名指しする承認、またはそれらで止まらなくてよいと明言する承認は、そのゲートを止まらずに通す。REPORT は各ゲートを、そこで見せるはずだったものを添えて列挙する。一般的な承認（「承認」「OK」「すべて承認」）はどのゲートも免除しない。名指しの承認も、コマンドに書かれた STOP ゲート、外に出る操作（push、公開、送信、デプロイ）、破壊的な操作、承認された報告になかったゲートには決して及ばない
- ユーザーは提案された変更のそれぞれを個別に承認、却下、修正できる

STOP ゲートは DDL の中核の原則である「人間がペースを制御する」を体現します。LLM が提案し、人間が決めます。

### 3.6 並列ワーカー（SWARM）

タスクが複数の独立したスコープにまたがるとき、エージェントの並列実行は時間を短縮し、カバレッジを高めます。

```
リードエージェント
    ├── survey-{scope-1}  ──┐
    ├── survey-{scope-2}  ──┤── 並列実行
    └── survey-{scope-3}  ──┘
            ↓
    リードが結果を統合
            ↓
    スコープをまたぐ分析
```

規則は次のとおりです。
- エージェントを起動するのは独立したスコープが二つ以上あるときだけであり、その条件が成り立てばコマンドは並列に割り振る。`/realize` では現在の Direction の段階のレーンをスコープとして数える
- ワーカーのラベル: `spawn:` は `{role}-{scope}` のようなラベルのパターン（例: `reader-backend`、`scanner-docs`）であり、報告の中で各ワーカーを識別する。ラベルをワーカーの名前として渡すのは実行環境のアダプタがそう定めるところだけである。名前はワーカーにできることを変えうるからである（名前をつけた Claude Code のワーカーは、アダプタの定義が外さない限り書き込みのツールを得る）
- 各エージェントは割り当てられたスコープだけを読む
- リードはワーカーが自分の会話を引き継ぐことを当てにしない。リードは各プロンプトを design.md から書く（スコープのパス、そのスコープが担う Experience の項目、原則、Binding Decisions、Direction の段階、スコープの検証コマンド、そのフェーズで人間が承認した行（逐語）、`/realize` では承認された計画）ので、プロンプトはそれだけで完結し、ワーカーのコンテキストのすべてになる。すなわちワーカーは指示ファイルも design.md も全体は読み直さない。STOP の条件に当たったワーカーは止まって報告し、そのあとリードも止まって人間を待つ
- プロンプトにはワーカーが自分のワーカーを起動しないこと（並列に割り振るのはリードだけである）も書き、読み取り専用の作業ではその作業が読み取り専用であることも書く。この指示はどの実行環境でも成り立ち、アダプタがツールを外せるところではアダプタがそれを執行もする（Claude Code では `explorer` の定義が編集とエージェントのツールを、`worker` の定義がエージェントのツールを外し、起動の深さは1になる。一方でシェルコマンドは残り、指示によって読み取り専用にとどまる。Codex のサブエージェントは親セッションのサンドボックスを引き継ぎ、自分のエージェントを起動できるので、そこではワーカーを範囲の中にとどめるのは指示だけである）
- リードが結果を統合し、スコープをまたぐ分析を走らせる
- 単一スコープのタスクはエージェントを起動せずに走る
- プロトコルが並列の割り振りを各実行環境（Claude Code のサブエージェント、Codex のサブエージェント）に対応づける。並列の仕組みがなければリードが割り当てを自分で実行し、読み取り専用の作業は並列の読み取りとして、残りは一つずつ処理する。コマンドは実行環境のツールを決して名指ししない

スコープは design.md で定義され、決してハードコードされません。これによって枠組みはプロジェクトから独立したままでいられます。

-----

## 💻 §4 実践例

### 例1: 完全なループ

典型的な Draft → Realize → Reflect の流れです。

**Draft:**
```python
# こういう体験がほしい
async with APIClient("https://api.example.com") as client:
    users = await client.get("/users")
```

design.md に次を記録します。
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

実装中に Token Refresh の必要性が判明しました。

```python
async def _ensure_token(self):
    if self._token_expires_soon():
        await self._refresh_token()
```

design.md に次を追加します。
- Token Refresh: 期限切れの前に透過的にリフレッシュする

### 例2: Draft を飛ばす

仕様はあるものの設計哲学がはっきりしない既存のコードベースの開発に加わる場合です。

**Reflect から開始:**
```
Human: このコードベースの設計哲学を整理したい
LLM: src/ を読んで暗黙のパターンを抽出します
```

発見されたパターンは次のとおりです。
- すべての API は Result 型を返す
- エラーは例外ではなく値である
- 副作用は明示的に印づけられている

**design.md を逆生成:**
```markdown
## Core Principles
- Result-based Error Handling: 例外を使わない
- Explicit Side Effects: 関数名で示す
```

この例は Draft を経ずに Reflect → design.md と進む流れであり、「どの状態からでも遷移可能」の実例です。

### 例3: Realize と Reflect の反復

設計が固まっていない探索的な開発です。

```
[Realize] 原則に従って実装する
    |
[Reflect] 実装してみると原則に無理があった
    |
[Realize] 原則を修正して再実装する
    |
[Reflect] まだ違和感がある
    |
...繰り返し...
```

design.md は頻繁に書き換わりますが、それが正常な状態です。設計がまだ安定していない証拠であり、同時に DDL が機能している証拠でもあります。

### 例4: Binding Decisions と Direction を伴う Draft

体験がフレームワークに依存する Web 機能です。

**Draft:**
```
Human: 社内ナレッジ検索。回答は書かれている途中から見えてほしい。
       Next.js で作りたい。
LLM:   体験と拘束に分けました。質問が二つあります。App Router に
       限定しますか。それから、何も見つからないときや検索が失敗したときに、
       ユーザーには何が見えるべきですか。
Human: はい、App Router で。見つからないとき: 関連する検索語を3つ。失敗: 質問を残して、再試行を出す。
```

design.md に次を記録します。
```markdown
## Experience
質問を送ってから1秒以内に回答が出始め、書きながら伸びていく。
引用元はその下に並ぶ。
- 見つからないとき: 「見つかりませんでした」と、関連する検索語を3つ
- 失敗: 質問は入力欄に残り、「再試行」が出る

## Binding Decisions
| Decision | Why it binds | Source |
|---|---|---|
| Next.js App Router | 回答は書かれるそばから届いて伸びていき、ルートごとの読み込み中・エラー状態が体験の中心だから | 「Next.js で作りたい」、「はい、App Router で」(2026-10-17) |

## Direction
| Stage | Work (parallel lanes) | Human sees | Gate |
|---|---|---|---|
| S0 | 検索 API を CLI として固める | CLI の出力例 | `npm test` |
| S1 | 画面の3状態を1状態1レーンで | スクリーンショット3枚 | 人間の承認 |
| S2 | 書きながら伸びる表示 | 画面の録画 | `npx playwright test` |
```

**Realize:**
```
LLM: Binding Decisions は守られています（package.json、app/）。S0 は `npm test` を通ったので、
     Gate のセルはいま「`npm test`, passed 2026-10-20」になっています。S1 と S2 は統合し、両方の
     ゲート（`npx playwright test`、続いて人間の承認）を統合後の段階の終わりに移しました。
LLM: +++DDL_REPORT
     D6 Binding Violation: ホスティングは静的ファイルしか配信しないので、サーバーは回答を
     書きながら流せません。書きながら伸びる回答こそ、Next.js App Router を拘束にした理由です。選択肢:
     Node の実行環境を申請する、別の API サーバーから流す、回答が完成してからだけ
     表示する、Binding Decision を変える。あなたが選んでください。
     （手番を終える。人間が答えるまで何も動かない）
```

**Reflect:**

人間が Node の実行環境を選んだので、Binding Decisions はコードと一致しています。すべての段階に `passed` の印が付いたため、Direction は `Approved plan` の行ごと削除します（履歴はバージョン管理に残ります）。実装中に足した停止ボタンは Experience に書き加えます。

-----

## 🎯 §5 採用の基準

### 効果的な状況

| 状況 | 理由 |
|------|------|
| 複数のセッションにまたがる | セッションの断絶という問題が起こる |
| 設計上の決定が多い | 決定の根拠を保存することが重要である |
| 探索的な開発 | 試行錯誤の記録が役に立つ |
| LLM との深い協調 | 共有記憶が効果を発揮する |

### 不要な状況

| 状況 | 理由 |
|------|------|
| 単一のセッションで完了する | 断絶の問題がない |
| 明確な仕様がある | すでに形式知化されている |
| バグ修正 / 小さな変更 | オーバーヘッドが大きすぎる |

### 粒度の指針

```
design.md に書くこと:
✓ 概念のレベル（なぜ）
  例: 「認証は透過的であるべき」
✓ 設計のレベル（どう）
  例: 「Context Manager Pattern を使う」
△ 実装のレベル（重要な決定だけ）
  例: 「JWT を選んだ。理由: ステートレス」
  Binding Decisions はこのレベルに置く: 決定、拘束になる理由、出どころ（人間の言葉と日付、またはその決定を載せた報告を人間が承認したこと）

書かないこと:
✗ すべての API の詳細
✗ コードから自明なこと
```

原則は「次のセッションでコンテキストを復元するのに必要な最小限の情報」です。

### README-as-design という代替

design.md は必須ではありません。人間と LLM のあいだに*何らかの*共有ノート、すなわち Otto のノートがあれば、ファイルの形は問いません。

外部に公開する面そのものが設計になるプロジェクト（典型的にはオープンソースのライブラリ、CLI、HTTP API）では、README と API リファレンスとガイドがそのまま生きた仕様になり得ます。

| 状況 | 推奨するノート |
|------|----------------|
| アプリケーション / 複数の成果物 / 研究プロジェクト | `design.md` |
| API == 設計である公開ライブラリ | `README.md` + `docs/`（API リファレンス、ガイド） |
| 小さなツール（単一のスクリプト） | ファイル冒頭の docstring |

経験則は次のとおりです。
- ノートはファイル名が何であれ、**セッション開始時に読み込み**、**変更の前に参照する**
- ノートにするファイルは実行環境の指示ファイル（`CLAUDE.md` か `AGENTS.md`）で名指しする。プロトコルはこれを認めている。コマンドはそれ以降、プロトコルやコマンドが design.md と書いている箇所はすべて名指ししたファイルに読み替えて読み書きするので、README の更新は設計の更新であり、`/reflect` は README とガイドに書き込む
- 設計の内容がユーザー向けの説明から離れ始めたら、別の design.md に切り替える

これが AgenticFlow のパターンです。AgenticFlow は Python の公開ライブラリで、`CLAUDE.md` と `AGENTS.md` が `README.md` + `docs/en/` を設計文書として名指ししています。README に契約が書かれ、開発ガイド（AgenticFlow のリポジトリの `docs/en/guides/development-workflow.md`）にスコープの表と検証コマンドがあるので、別に design.md を置く必要はありません。機能的等価の四つの条件（常に利用できる、直接アクセスできる、自動的に信頼される、意識的に記録された）はこれらのファイルがそのまま満たします。

-----

## 📊 §6 指標

以下は DDL の効果を理解するための指標です。数値は目安であり、プロジェクトごとに調整してください。

| 指標 | 定義 | 測定 | 健全な目標 |
|------|------|------|------------|
| セッションの継続性 | 前のセッションの意図を引き継いで作業を再開できるか | 前回の議論を把握して5分以内に作業を続けられれば「成功」 | 成功率 > 80% |
| 設計とコードの整合 | 原則がコードに反映されているか | design.md の原則の総数に対する実装済みの原則の割合 | > 70% |
| ドキュメントの鮮度 | design.md が現在の状態を反映しているか | 最終更新からの日数 | < 1週間 |
| Binding の整合 | コードがすべての Binding Decision を守っているか | 守られている Binding Decision の割合 | 100% |

「セッションの継続性」についての補足: 厳密に測定する必要はありません。「前回何をしていたか思い出せない」「LLM にすべてを説明し直している」という状況が頻繁にあるなら、design.md の粒度か更新頻度に問題があります。

-----

## 🛠️ §7 実装の選択肢

### 選択肢1: 規律だけ
ツールを使わず規律だけに頼る最も軽量な選択肢であり、出発点として勧めます。

### 選択肢2: テンプレートに基づく

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

> あくまで出発点です。合わなければ捨ててください。Experience を先に書き、Binding Decisions、Direction、Acceptance Gates は任意です。Scopes と Validation はコマンドが読む節で、並列の割り振りと検査に使います。

### 選択肢3: ワークフローへの統合
PR のチェックリストに Reflect を組み込む、チーム開発向けの選択肢です。

### 選択肢4: ツールの支援

コマンドは DDL を Phase 単位のワークフローとして実装し、Detection Targets、STOP ゲート、並列のワーカー（+++SWARM）を備えます。

**コアループ**: Draft → Realize → Reflect のサイクルです。

| コマンド | 意図 |
|----------|------|
| `/draft` | ユーザー側の体験を、その体験が前提とする決定と見通しを添えて先に書く |
| `/realize` | 設計原則と Binding Decisions に基づいてコードを書く |
| `/reflect` | 実装に基づいてドキュメントを更新する |

**サポートコマンド**: どの時点でも呼び出せます。

| コマンド | 意図 |
|----------|------|
| `/validate` | スコープごとに機械的な検証を走らせる: Validation ブロックと Acceptance Gates の中の機械的なゲート |
| `/resonate` | 多言語のドキュメントの版を同期する |
| `/commit` | 検証済みの変更をリポジトリに記録する |
| `/docs` | ドキュメントの品質を監査して直す |
| `/refactoring` | コードの品質を監査して直す |

どのコマンドも構造は同じです。
1. **Phases**: 順序のあるステップ（INIT → SURVEY/READ → WORK → REPORT (+++STOP) → EXECUTE → VERIFY）
2. **Detection Targets**: それぞれのフェーズの中で並列に走る自動検査（コマンドごとに D1、D2、…）
3. **+++SWARM**: スコープが2つ以上あれば、実行環境が備える仕組み（Claude Code のサブエージェント、Codex のサブエージェント）でスコープごとにワーカーを並列に起動する。並列の仕組みがなければリードが割り当てを自分でこなし、読み取り専用の作業は並列に読み、残りは一つずつ行う
4. **STOP ゲート**: 共有の成果物を変更する前には必ず人間の承認を求める。エージェントは手番を終えて待つ
5. **制約**: 決して破ってはならない不変条件
6. **実行環境のアダプタ**: プロトコルの実行環境の対応表がディレクティブを各ハーネスに対応づけるので、コマンドは実行環境のツールを名指しせず、実行環境ごとの小さなアダプタ（hook、エージェント定義、design.md の取り込みか注入、push の規則）が規則の機械的な部分を執行する（§2.5 指示と仕組み）

Claude Code: → [claude-code/](../../claude-code/)
OpenAI Codex: → [codex/](../../codex/)

### 選択肢5: 構造化スキーマ

機械可読な形式は次のようになります。

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
    why: "体験は非同期の利用側コードである: async with APIClient(...)"
    source: '「async with で使いたい」(2026-10-17)'

session:
  last_topic: "認証フローの設計"
```

自動検証とセッションの継続性の追跡ができるようになります。ただし、ツールが目的になったなら本末転倒です。

-----

## 📦 §8 成果物とライフサイクル

| 名前 | 目的 | 永続性 |
|------|------|--------|
| design.md | 設計哲学、概念の定義 | 一時的 |
| Direction（design.md 内） | 実装に至る道筋の見通し | 最も一時的: すべての段階が終わったとき、`Approved plan` 行とともに削除される |
| Acceptance Gates（design.md 内） | 完了の定義 | すべてのゲートが `passed` と記されたとき（作業が受け入れられたとき）に削除される。長く残る検査は先に Validation に移す |
| docs/adr/ | 設計決定の記録 | 永続的 |
| src/ | 具現化されたコード | 永続的 |

```
Creation -> Use -> Integration -> Deletion
```

DDL のドキュメントが長期にわたって残っているのは、設計がまだ安定していない証拠です。

統合のパターンは次のとおりです。
- コードのコメントに吸収する
- README / API ドキュメントに昇格させる
- ADR として永続させる
- Binding Decisions はコードが体現した時点で README の要件か ADR に移す（コードは何を選んだかは示すが、その理由は示さない）。移すのは `/reflect` で人間が承認したときに限り、以後コマンドはコードをその Binding Decision に照らさなくなる
- 削除する（コードから自明になった）

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

### 人間と AI の協調
- Sabbah, J., & Li, F. (2025). [When Humans and Large Language Models Collaborate, Problem-Finding Illuminates](https://doi.org/10.1080/14479338.2025.2504428). *Innovation: Organization and Management*.

### AI 時代の開発パラダイム
- Thoughtworks (2025). [Spec-Driven Development: Unpacking one of 2025's key new AI-assisted engineering practices](https://www.thoughtworks.com/en-us/insights/blog/agile-engineering-practices/spec-driven-development-unpacking-2025-new-engineering-practices).
- Fowler, M. et al. (2025). [Understanding Spec-Driven-Development: Kiro, spec-kit, and Tessl](https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html). *martinfowler.com*.
- Marmelab (2025). [Spec-Driven Development: The Waterfall Strikes Back](https://marmelab.com/blog/2025/11/12/spec-driven-development-waterfall-strikes-back.html).
- AWS, Raja SP et al. (2025). [AI-Driven Development Life Cycle: Reimagining Software Engineering](https://aws.amazon.com/blogs/devops/ai-driven-development-life-cycle/). *AWS DevOps Blog*.
- GitHub (2025). [Spec Kit](https://github.com/github/spec-kit). *GitHub*.
- Anthropic (2025a). [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents). *Anthropic Engineering*.
- Lopopolo, R. (2026). [Harness engineering: leveraging Codex in an agent-first world](https://openai.com/index/harness-engineering/). *OpenAI*.

### コンテキストエンジニアリング
- Anthropic (2025b). [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents). *Anthropic Engineering*.
- Anthropic (2025c). [Equipping agents for the real world with Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills). *Anthropic Engineering*.
- Ji, Y. (2025). [Context Engineering for AI Agents: Lessons from Building Manus](https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus). *Manus*.
- Anthropic (2026). [How Claude remembers your project](https://code.claude.com/docs/en/memory), [Context window](https://code.claude.com/docs/en/context-window), [Hooks reference](https://code.claude.com/docs/en/hooks), [Subagents](https://code.claude.com/docs/en/sub-agents), and [Settings](https://code.claude.com/docs/en/settings)（権限規則）. *Claude Code documentation*（2026-10-18 取得）.
- OpenAI (2026). [Custom instructions with AGENTS.md](https://developers.openai.com/codex/guides/agents-md), [Memories](https://developers.openai.com/codex/customization/memories), [Hooks](https://developers.openai.com/codex/hooks), [Subagents](https://developers.openai.com/codex/subagents), [Rules](https://developers.openai.com/codex/rules), and [Skills](https://developers.openai.com/codex/skills)（`agents/openai.yaml`）. *Codex documentation*（2026-10-18 取得）.

### 関連する方法論
- Knuth, D. (1984). [Literate Programming](https://academic.oup.com/comjnl/article/27/2/97/343244). *The Computer Journal*, 27(2), 97-111.
- Nygard, M. (2011). [Documenting Architecture Decisions](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions). *Cognitect Blog*.
- Beck, K. (1999). [*Extreme Programming Explained*](https://www.oreilly.com/library/view/extreme-programming-explained/0201616416/). Addison-Wesley.
- Meyer, B. (1992). [Applying Design by Contract](https://ieeexplore.ieee.org/document/161279/). *IEEE Computer*, 25(10), 40-51.

-----

## 📝 変更履歴

| 日付 | 変更 |
|------|------|
| 2026-10-18 | 指示と仕組み: +++STOP の機械的な部分、design.md の読み込み、ワーカーの役割、外に出る +++NEVER の項目を、ハーネスが実行環境ごとのアダプタを通じて執行する（§2.5 指示と仕組み、§3.5、§3.6）。読み方の表に1行。正本を `claude-code/` と `codex/` に移し、DDL を環境に導入: コマンドはスキルになり、`ddl-protocol` が両方の実行環境のプロトコルになった（§2.5 のコンテキストの表）。`/resonate` は通常のコマンドに戻った（§3.1、§7）。§7 のリンクを `claude-code/` と `codex/` に。§2.4 の執行のセル、§3 の導入、参考文献の追加 |
| 2026-10-18 | 追補: `passed` の印と事前承認の印の形式の統一（§3.3）、Direction の下の `Approved plan` 行（§3.3、§8、例4）、承認時に書き留めるものとコンパクションのあとに入れ直されるプロジェクトのファイル（§2.5）、D9 Experience Gap と D7 Validation Failure（§3.3、§3.4）、STOP の規則と例4 の `+++DDL_REPORT`（§3.5、§4）、参考文献の整合 |
| 2026-10-17 | ハーネス時代の改訂: ハーネスの記憶と design.md（§1.1、§1.4）、ハーネスエンジニアリングと技術の選択（§2.5）、状態モデルの VALIDATE（§3.1）、ハーネスのセッション状態（§3.2）、Binding と Direction の検査（§3.3、§3.4）、G1–G7 の ID（§3.4）、STOP の意味論と並列のワーカー（§3.5、§3.6）、例4、§5・§6・§8 の Binding Decisions、テンプレートの節（§7）、参考文献3件。追補: `passed` の印と退役させた Acceptance Gates（§3.3、§3.4、例4、§8）、STOP 中はワーカーを起動も継続もしないことと、通知や他のエージェントからの承認を認めないこと（§3.5）、ワーカーのラベル、それだけで足りるプロンプト、各プロンプトに書く読み取り専用と入れ子の禁止の指示（§1.4、§3.6）、用語の統一（§3.6 と §7 の Codex のサブエージェント、§7 の「D1、D2、…」）、実行環境の指示ファイルが名指しするノート（§5）、プロトコルの役割の順に並べた Phases（§7）。ノートの名前を全体で design.md に統一。`Unbound:` 行、承認された選択、Binding Decision を変えることになる引数、既存の前提（§2.5）。ゲートは決して落とさない（§3.3）。どの REPORT も STOP ゲートで終わることと、承認された報告の外にあるゲートは決して事前承認されないこと（§3.5）。並列の仕組みがないときのリードの代替手順（§3.6、§7）。`/resonate` をリポジトリ専用と明記（§3.1、§7）。報告の承認を Binding Decision の出どころとすること（§5）。§6–§8 の読み方の行。`/draft` の意図（§7）。コンテキストエンジニアリング（§1.4、§2.5、§3.5、§3.6）とその参考文献 |
| 2026-04-25 | VALIDATE サポートコマンド（§3.1、§7）。README-as-design という代替（§5） |
| 2026-02-14 | §2.5 を三者比較（SDD / AI-DLC / DDL）に拡張 |
| 2026-01-04 | 初版 |
