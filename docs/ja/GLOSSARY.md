# 用語集（翻訳・編集用の内部資料）

> このページは翻訳者、編集者、エージェントが日本語版を保守するための内部資料です。DDL を使う方は[基本ガイド](./design_philosophy.md)や[詳説版](./design_philosophy_extended.md)をご覧ください。

この用語集は英語版（`docs/en/`）を正本として日本語版（`docs/ja/`）を訳すときの対応表である。保守者は訳し直すときにこの表に従い、表に無い語を新しく訳したら表に足す。機械検査（design.md の V35）は「使わない訳」の列の語が日本語版に残っていないか、主要な訳語が日本語版に現れているかを確かめる。

## 翻訳・編集の方針

- 節の名前とディレクティブは英語のまま書く。Experience、Binding Decisions、Direction、Acceptance Gates、Validation、Scopes、Principles、Intent、Detection Targets、`+++STOP`、`+++SWARM`、`+++NEVER`、`+++DDL_REPORT`、D1 や G7 の名前、`passed` や `Unbound:` のような印は訳さない。操作と実装の節の名前（Read when、Syntax、Operands、Operation、Formats、Example、Exceptions、Implementation、Mapping、Observed、Coverage）は節を指すときは英語のまま書き、内容を述べるときは表の訳語で書く。
- 固有名詞と文献は原文のまま書く。人名（Clark & Chalmers、Nonaka & Takeuchi など）、組織と製品（Anthropic、OpenAI、Claude Code、Codex、Spec Kit、Kiro、Tessl、Next.js）、方法論の略語（SECI、DocDD、ADR、TDD、DbC、SDD、AI-DLC、MCP）、ファイル名と識別子（design.md、CLAUDE.md、AGENTS.md、`.claude/settings.json`、`explorer`、`worker`）はそのまま。参考文献の節は英語のままにする。
- 見出しは日本語に訳す。ただし節の名前（Experience など）と固有名詞を含む見出しはそのまま残す。訳した見出しの例: In the Harness Era は「ハーネス時代」、Background: The Session Discontinuity Problem は「背景: セッションの断絶という問題」、Core Principle は「中核の原則」、Roles: Human and LLM は「役割: 人間と LLM」、Stay Flexible は「柔軟に」、Anti-Patterns は「アンチパターン」、Summary は「まとめ」、Option 1: Pure Discipline は「選択肢1: 規律だけ」、STOP Gates は「STOP ゲート」。見出しの数と階層は英語版と一致させる（V35）。
- em-dash（—）は使わない。読点、括弧、コロンで書く。コード、表、引用、見出しの構造は英語版に合わせる。
- コードブロック内の図は、概念名だけのもの（§1 の図、The Loop）は英語のまま、文を含むもの（§3 の STOP ゲートや SWARM の図）は訳す。
- 同じ英語の語には同じ日本語を当てる。文脈で訳し分ける語は表の備考に書く。
- 本文は「です・ます」で書く（現行の日本語版と同じ）。
- 地の文は、主題を先に置き、読点は構造の切れ目だけに打ち、完全な述語文で書き、英語の語順や語をなぞった直訳調を避ける。
- 太字ラベルのあとのコロンは半角の「: 」で書く（例: **背景: セッションの断絶という問題**）。
- 日本人研究者の名は本文では日本語で書く（野中）。参考文献の欄は英語のまま。

## 用語

| 英語 | 日本語 | 使わない訳 | 備考 |
|---|---|---|---|
| context window | コンテキストウィンドウ | 窓 | モデルに一度に載る量。「窓が埋まる」は誤訳 |
| context（モデルに載っている内容） | コンテキスト |  | 「in context」は「コンテキストにある」。一般の意味（文脈、背景）だけ「文脈」と書く。context engineering と同じ語族にそろえる |
| context engineering | コンテキストエンジニアリング |  |  |
| compaction | コンパクション |  | 会話を要約してコンテキストを空ける操作。初出に「（会話の圧縮）」を添える。compaction を「要約」と訳さない。summary（要約そのもの）と区別する |
| summary / conversation summary | 要約 / 会話の要約 |  | compaction の結果として残る文章 |
| harness | ハーネス |  |  |
| harness era | ハーネス時代 | ハーネスの時代 |  |
| harness engineering | ハーネスエンジニアリング |  |  |
| harness memory | ハーネスの記憶 |  |  |
| automatic memory | 自動メモリ |  | Claude Code の MEMORY.md、Codex の memories を指す機能名 |
| memory（モデルやハーネスが覚えること） | 記憶 |  | 機能名のときだけ「メモリ」 |
| memories（Codex の機能） | memories |  | 英字のまま |
| runtime | 実行環境 | ランタイム | Claude Code や Codex を指す |
| adapter / runtime adapter | アダプタ / 実行環境のアダプタ | アダプター |  |
| instruction file / runtime guidance | 指示ファイル / 実行環境の指示ファイル |  | CLAUDE.md と AGENTS.md |
| instruction（規則としての指示） | 指示 |  | prompt とは区別する |
| prompt（ワーカーに渡す文） | プロンプト |  | 「ワーカーのプロンプト」。prompt を「指示」と訳さない |
| mechanism | 仕組み | メカニズム |  |
| mechanical | 機械的な |  |  |
| enforce / enforcement | 執行する / 執行 | 強制力 | 指示が規則を述べ、仕組みが執行する |
| gate | ゲート | 門 | STOP gate は「STOP ゲート」、human gate は「人間のゲート」、gate hook は「ゲートの hook」。Acceptance Gates は英語のまま。検査では「専門」のような複合語の「門」を除く |
| human gate | 人間のゲート | 承認点 | 人間が見て承認する地点 |
| hook / lifecycle hook | hook / ライフサイクルの hook | フック | 英字のまま、コード体で書く |
| agent definition | エージェント定義 | エージェントの定義 |  |
| permission rule | 権限規則 |  |  |
| attribution / AI attribution | 帰属表記 / AI の帰属表記 | 署名 | Co-Authored-By のような記名。コミットの署名（signing）とは別物 |
| tool（エージェントが使う操作） | ツール | 道具 |  |
| mutating tool | 変更を伴うツール |  |  |
| mutate / mutation | 変更する / 変更 |  |  |
| read-only | 読み取り専用 | 読み取りだけ |  |
| agent | エージェント |  |  |
| subagent | サブエージェント |  |  |
| worker | ワーカー |  |  |
| lead / lead agent | リード / リードエージェント |  |  |
| spawn（ワーカーを） | 起動する | ワーカーを生成、エージェントを生成 | `spawn:` フィールドは英字のまま |
| spawn depth / nesting | 起動の深さ / 入れ子 |  |  |
| fan out | 並列に割り振る |  | 「スコープごとに割り振る」も可。4通りあった訳を一つに |
| team / team primitive | チーム / チームの基本機能 |  | primitive は実行環境が備える基本機能 |
| role | 役割 | 役目 | 「役」一字でも書かない |
| turn（エージェントの手番） | 手番 |  | 「end the turn」は「手番を終える」 |
| halt | 停止する |  |  |
| blocking | ブロッキング |  |  |
| approval / approve | 承認 / 承認する |  |  |
| advance approval / approved in advance | 事前承認 / `approved in advance` |  | 印としての英字はそのまま |
| passed mark / marked passed | `passed` の印 / `passed` と記された | passed の記録 |  |
| retire（節を） | 退役させる | 片づける | 節を design.md から外すこと。「削除する」とも訳さない |
| durable | 永続する |  | 「会話は永続しない」。「残る」と意訳しない |
| artifact / shared artifact | 成果物 / 共有の成果物 | アーティファクト |  |
| design.md | design.md |  | 手帳の名前。どの実行環境でも同じ |
| notebook / shared notebook / Otto's notebook | ノート / 共有ノート / Otto のノート |  |  |
| shared memory | 共有記憶 |  |  |
| living document / living spec | 生きた文書 / 生きた仕様 |  |  |
| temporary notes | 一時的なメモ |  |  |
| source of truth | 正（source of truth） |  | 初出に英語を添える |
| session | セッション |  |  |
| session discontinuity (problem) | セッションの断絶（という問題） | 記憶の切断 |  |
| import（指示ファイルへの） | 取り込み / 取り込む |  | Claude Code の `@` 行 |
| inject / injection | 注入する / 注入 |  | Codex の SessionStart hook |
| re-inject | 入れ直す |  |  |
| load（コンテキストに） | 読み込む |  |  |
| name（指示ファイルがファイルを） | 名指しする |  |  |
| progressive disclosure | 段階的開示 |  |  |
| skill | スキル |  | Agent Skills は英字のまま |
| command | コマンド |  | `/draft` と `$draft` は英字のまま |
| directive | ディレクティブ |  | 「命令」とは訳さない。ISA のたとえで instruction を「命令」と訳すのとは区別する |
| protocol | プロトコル |  | 英字で protocol と書く箇所は「プロトコル」に統一 |
| protocol lookup | プロトコルの探索先 |  |  |
| instruction set | 命令セット | 指示セット | ISA のたとえ。入口の表（十の命令）。directive は「ディレクティブ」のまま。directive の行（「命令」とは訳さない）と整合させる |
| instruction（ISA のたとえ。`+++` ディレクティブ一つ一つ） | 命令 |  | ISA。directive は「ディレクティブ」のまま。規則としての instruction は「指示」の行に従う |
| specification（protocol の） | 仕様 |  | 命令セット仕様 |
| instruction-set reference | 命令セット仕様 |  | protocol の形式（P16）。「命令セットの参照資料」とは訳さない |
| protocol tree | プロトコルの木 |  | 入口、操作、`hosts/` の実装の三段。「Codex のプロトコルの木」 |
| tier（protocol の木の三段） | 段 |  | 「三段からなる」。Direction の stage は「段階」 |
| entry（protocol の入口。`SKILL.md`） | 入口 | エントリ | 命令セット（十の命令の表）と読み込み地図を持つ。読み込み地図は操作、読む場面、実装の 3 列 |
| reading map | 読み込み地図 | 読み込みマップ |  |
| operation（protocol の操作。入口の隣の 6 本） | 操作 | 参照資料、例の資料 | approval.md、parallel-work.md、notebook.md、close.md、git-review.md、command-authoring.md。各操作は短い例を一つ持ち、別の例集は無い。節の名前 Operation（動作）とは区別する。Git の action や「外に出る操作」のような一般の「操作」は文脈で区別し、protocol の 6 本を指すときだけ「操作」を節やファイルの種類の名前として使う |
| command authoring（操作の名） | コマンド作成 |  | 「コマンド作成の操作」。コマンドのテンプレートはその Example にある |
| command template | コマンドのテンプレート | 雛形 | command-authoring.md の Example にある |
| Read when / Read before（操作と実装の節） | 読む場面 |  | 操作と実装の 1 番目の節。読み込み地図の 2 列目。節を指すときは Read when と英字で書く |
| syntax | 構文 |  | 操作の節 Syntax |
| operands | オペランド |  | SWARM の operand block。操作の節 Operands |
| Operation（操作の節） | 動作 |  | 規則の本体。ファイルとしての operation（操作）とは区別する |
| procedure（一般の手順） | 手順 |  | 節やファイルの名前には使わない。操作の節 Operation は「動作」、protocol のファイルは「操作」 |
| format（literal string） | 形式 |  | コマンドが書き出す文字列の定義。操作の節 Formats |
| example（操作の節 Example） | 例 |  | 各操作に短い例が一つ。節の名前 Example は英字のまま。「例N」（Example N）とは別 |
| Exceptions（操作の節） | 例外 |  | 動作が決めない状況と振る舞いの対 |
| boundary（一般の境界） | 境界 | 境界線 | 入力の境界など。操作の節は Exceptions（例外） |
| Implementation（操作の節） | 実装 |  | 操作の 8 番目の節。`hosts/` の実装（ファイル）とは文脈で区別する |
| `hosts/`（protocol の実装を置くディレクトリ） | `hosts/` |  | ディレクトリ名は英字のまま。中の 8 本は次の行の「実装」 |
| implementation（`hosts/` の 8 本） | 実装 | 実行環境の資料、ホスト資料 | `hosts/claude-code/` と `hosts/codex/` の八つ。ホストごとに 4 本。`start.md` は Start で読み、`approval.md`、`parallel-work.md`、`git-review.md` は同じ名前の操作とともに読む。Read when、Mapping、Observed、Coverage を持つ。節の名前の近くでは「`hosts/` の実装」と書く。`hosts/` は英字のまま。旧称 host file、runtime file は使わない |
| the host's `start.md` | ホストの `start.md` |  | Phase 0 で入口とともに読む実装。「起動資料」とは訳さない |
| observed（dated fact） | 観測 | 観察 | 日付と版つきの事実。「日付つきの観測の行」 |
| coverage | 保証範囲 |  | アダプタが執行することとその限界 |
| phase（固有名: Phase 0 など） | Phase |  |  |
| phase（一般） | フェーズ |  |  |
| scope / cross-scope | スコープ / スコープをまたぐ | クロススコープ |  |
| stage | 段階 |  | 表の見出し Stage は英字のまま |
| lane | レーン |  |  |
| outlook | 見通し |  | Direction の意味 |
| bind / binds / binding | 拘束する / 拘束 |  | 「Why it binds」は表の見出しのまま |
| existing premise | 既存の前提 |  |  |
| delegated | 委任された |  | 「任された」とは書かない（検査では「委任された」と区別できないので備考に置く） |
| stack | スタック |  |  |
| human | 人間 | 我々 | 役割としての human。引用の中は原文どおり |
| user | ユーザー |  |  |
| equal partner | 対等なパートナー | 対等な関係 |  |
| pace | ペース |  |  |
| principle / design principles | 原則 / 設計原則 |  | 「方針」「デザイン」とは訳さない |
| discipline（規律の意味） | 規律 |  |  |
| discipline（分野の意味。the discipline had a name） | 分野 |  |  |
| contract | 契約 | 約束 | DbC も Direction の文脈も「契約」 |
| rigid (process) | 硬直した（プロセス） | 紋切り型 |  |
| hold（ハーネスがループの一部を） | 担う |  | 「守る」とは訳さない |
| fixed（人間が固定したこと） | 固定した |  | 「決めた」に弱めない |
| honored（Binding Decisions が） | 守られている |  | 「確認した」に弱めない |
| feedback loop | フィードバックループ |  | 「仕組み」とは訳さない |
| recall / recall layer | 想起する / 想起の層 |  |  |
| trust / untrusted | 信頼する / 未信頼の |  |  |
| sandbox | サンドボックス |  |  |
| token | トークン |  |  |
| label | ラベル |  |  |
| layer | 層 | レイヤー |  |
| report / `+++DDL_REPORT` | 報告 / `+++DDL_REPORT` | レポート |  |
| check（照らし合わせる） | 照らす / 確かめる |  | 名詞の checks は「検査」 |
| validation / Validation | 検証 / Validation |  | 節の名前は英字のまま |
| verbatim | 逐語で / そのまま |  |  |
| definition of done | 完了の定義 |  |  |
| outward-facing action | 外に出る操作 | 外に向けた操作、外向き |  |
| destructive | 破壊的な |  |  |
| budget（文脈は予算） | 予算 |  |  |
| progress file | 進捗ファイル |  |  |
| feature list | 機能リスト |  |  |
| Core Loop / Support Commands | コアループ / サポートコマンド |  |  |
| Close（Direction の最後の段階） | Close |  | 英字のまま。「Close 段階」と書く。reflect、docs、resonate、validate と 1 回の Git の確認で作業を終える段階 |
| close the work | 作業を閉じる |  | Close 段階で作業を終えること |
| Tool-Assisted Option（短い文書の末尾のラベル） | ツール支援の選択肢 |  | §7 の見出し「選択肢4: ツールの支援」はそのまま |
| stream / streaming | 書きながら伸びる / ストリーミング |  | 例文の中では状況に合わせる |
| Distributed Cognition | 分散認知 |  | 見出しでは英語を添える |
| tacit knowledge / explicit knowledge | 暗黙知 / 形式知 |  |  |
| functional equivalence | 機能的等価 |  |  |
| bounded rationality / satisficing | 限定合理性 / 満足化 |  |  |
| Cognitive Foundations（§1 の見出し） | 認知の基盤 | 認知科学的基盤 | 本文は哲学も含む |
| Nonaka's SECI model | 野中の SECI モデル |  | 文献欄は Nonaka & Takeuchi のまま |
| Human-AI / Human-LLM | 人間と AI / 人間と LLM |  |  |
| bolted on / organic | 後付け / 有機的 |  |  |
| spent（Direction が） | 使い終えた |  |  |
| wrong turns | 誤った道筋 |  |  |
| high-signal tokens | 信号の濃いトークン |  |  |
| role fluidity | 役割の流動性 |  |  |
| co-thinker | 共に考える者 |  |  |
| persist / persistence | 永続させる / 永続化 |  | 表の見出し Persistence は「永続性」 |
| endorse | 承認する |  |  |
| units of work | 作業単位 |  |  |
| sprint / bolt / epic | スプリント / ボルト / エピック |  |  |
| mob elaboration / mob construction | モブエラボレーション / モブコンストラクション |  |  |
| runtime table（protocol の） | 実行環境の対応表 |  | 旧構造の語。現在は Mapping（対応表） |
| Mapping（実装の節） | 対応表 |  | ツールと関心事の対応を書く節。ツールの名前は `hosts/` の実装にだけ現れる |
| vibe coding | vibe coding |  | 英字のまま |
| deliverables | 成果物 |  | artifact と同じ語でよい |
| runtime（実行時の意味。runtime checks） | 実行時 |  | Claude Code や Codex を指す runtime は「実行環境」 |
| design policy | 設計方針 |  | principle の「原則」とは別の語 |
| design philosophy | 設計哲学 | 設計思想 |  |
| fallback | 代替手順 |  |  |
| embody / manifested | 体現する / 具現化された |  |  |
| lasting checks | 長く残る検査 |  |  |
| approved picks | 承認された選択 |  |  |
| STOP semantics | STOP の意味論 |  |  |
| Changelog / Follow-up / Initial version | 変更履歴 / 追補 / 初版 |  |  |
| README-as-design Alternative（§5 の見出し） | README-as-design という代替 |  |  |
| static / dynamic（ADR の比較） | 静的 / 動的 |  |  |
| workflow | ワークフロー |  |  |
| source（Binding Decision の出どころ） | 出どころ | 出典 | 表の見出し Source は英字のまま |
| framework（枠組みの意味） | 枠組み |  | Next.js のような framework は「フレームワーク」 |
| Entry Condition / Exit Condition | 開始条件 / 終了条件 |  |  |
| public surface | 外部に公開する面 |  |  |
| rules of thumb | 経験則 |  |  |
| merge / integration | 統合 |  |  |
| alignment | 整合 |  | terminology alignment は「用語の統一」 |
| Example N | 例N |  | 見出しも本文も |
| where / wherever（場所の意味） | ところ | 所では | 「所では」「所だけ」とは書かない |

## 決定（2026-10-18）

1. gate の訳は「ゲート」に統一する（STOP ゲート、人間のゲート、ゲートの hook）。この repo の design.md は仕組みの名として「門」を使っているが、これは repo 内部の呼び名として残す。
2. モデルに載っている内容としての context は「コンテキスト」、一般の意味だけ「文脈」とする。
3. 見出しは固有名詞と節の名前を除いて日本語に訳す。
