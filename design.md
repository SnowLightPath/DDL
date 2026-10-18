# DDL Commands — Design Document

## Intent

DDLコマンド群（draft, realize, reflect, validate, resonate, commit, docs, refactoring）の設計仕様を定義する。
全コマンドは protocol（DDL-PROTOCOL。`claude-code/skills/ddl-protocol/SKILL.md`。Codex には同文の `ddl-protocol` スキルを生成する）に準拠した`+++`ディレクティブ記法で記述される。

2026-10-17 に、ハーネス（Claude Code、Codex など）が記憶・並列実行・承認の仕組みを標準で持つ時代に合わせた改訂を承認した。/draft は体験に加えて、体験と切り離せない技術の決定（Binding Decisions）、実装の見通し（Direction）、完了の条件（Acceptance Gates）を書き分ける。コマンドは意味だけを書き、ハーネスごとの実行手段は protocol の対応表（§2.5）に置く。

同日、コンテキストエンジニアリング時代の改訂を承認した。主題はコーディングツール側のハーネス（指示ファイル、自動メモリ、会話の要約、サブエージェント、スキルの段階的開示）である。モデル内のメモリはチャット時代からあり、DDL が新たに扱う問題ではない。DDL が扱うのは、ハーネスが覚えたことが (a) 人間の合意ではない、(b) エージェントやハーネスをまたいで共有されない、(c) 有限で、積むほど劣化する、の3点である。

2026-10-18 に、指示と仕組みの改訂を承認し、同日に実装した。+++STOP、Phase 0 の design.md 読み込み、+++SWARM の `type:`、外向きの +++NEVER の四つの命令に protocol §2.5 の実装の行と実行環境ごとのアダプタ（Claude Code は `.claude/settings.json`・`.claude/agents/`・`.claude/hooks/`、Codex は `.codex/`）を与え、唯一の新しい仕組みとして門（`tools/ddl_gate.py`）を置き、Claude Code の呼び出しを `.claude/skills/<name>/SKILL.md` に移した。規則の本文は変えていない（P13）。

同日、DDL を環境に入れる改訂を承認した。正本は DDL リポジトリ（公開）の `claude-code/` と `codex/` に一か所だけ置き、design.md を含めて全てを git で追跡する。利用者は `bin/install.sh` で `$HOME/.claude` と `$HOME/.codex` に導入し、プロジェクトには design.md と短い指示ファイルだけを置く。個人環境リポジトリ（Harness、旧 Skills。非公開）は DDL を git submodule で取り込む。`examples/` という写し、dogfood の生成、リポジトリ間の追従スクリプトは無くなった。Codex の protocol は Claude Code と同文の `ddl-protocol` スキルになり、`AGENTS.md` は `.claude/CLAUDE.md` と対になる短い指示ファイルになった。

この改訂の Direction（T0 記録、T1 正本化、T2 導入スクリプト、T3 Harness への移行、T4 日本語文書の再訳、T5 締め）と Acceptance Gates は 2026-10-18 にすべて通過し、同日 /reflect で退役した。続けて使う検査は Validation の V49（導入の往復）、V50（用語集）、V51（旧配置の名前）に残る。

## Experience

2026-10-17 の /draft（ハーネス時代の DDL）で承認した、DDL を使う人の体験。

1. **技術が体験と切り離せないとき。** `/draft 社内ナレッジ検索。回答が書きながら出てくるのが肝。Next.jsでやりたい` に対し、/draft は発言を体験・拘束・見通しに分け、足りない点だけを聞く（例: App Router に限るか、0件と失敗のときの見え方）。承認後は `## Experience` と `## Binding Decisions`（Decision / Why it binds / Source）に入る。人間が決めていない技術（例: TypeScript）は表の下に `Unbound:` として書く。/realize に委任されたものは計画で選択と理由を示し、承認されたら Binding Decisions に入る。
2. **言語がそのまま体験のとき。** ライブラリでは使う側のコードの言語が体験そのものなので、/draft はその言語で使用例を書き、言語を Binding Decisions に記録する。型の補完が使い勝手の中心なら、TypeScript を拘束する理由は「補完だけで使い方が分かる」になる。
3. **実装の見通しを持っているとき。** 「CLI で API を固めてから画面へ。3状態は並列に作り、途中でスクショを見せて」は `## Direction` の表（Stage / Work (parallel lanes) / Human sees / Gate）になる。見通しであり拘束ではない。
4. **/realize が守る。** 計画で各 Binding Decision の守り方と、Direction のどの段階から始めるかを示す。段取りの変更は報告に載るだけで止まらない。段階を統合したら、人間の承認点は統合後の段階の終わりに移す。Binding の理由が崩れたら（例: 静的ホスティングしか使えず、書きながら伸びる回答をサーバーから流せない）止まって選択肢を出す。Binding Decision を変えるのは人間だけ。段階の Gate が通ったら、Gate 欄に `passed <日付>` を書く。
5. **/reflect が照合する。** Binding Decisions とコードの一致、終わった Direction の削除、実装で見つかった体験の追記を、Target 列つきの表で出す。Binding Decision から外れたコードは Binding Drift として報告し、REPORT で止まる。解決は人間だけが選ぶ。
6. **どのハーネスでも同じ。** Claude Code の `/draft` も Codex の `$draft` も同じ節を読み書きし、同じ所で止まる。並列実行と承認の実行方法は protocol §2.5 の対応表と、その実行環境のアダプタ（Claude Code なら `.claude/settings.json`・`.claude/agents/`・`.claude/hooks/`、Codex なら `.codex/`）にあり、ハーネスが変わってもコマンドファイルは変えない。サブエージェントが lead の会話を引き継ぐとは限らないので、lead は design.md の Experience・Binding Decisions・担当スコープから、それだけで足りる指示を作る。ワーカーがさらにワーカーを起動することはない。
7. **完了の条件を先に書くとき。** 「npm test が通り、3画面のスクリーンショットを見て承認したら完了」は `## Acceptance Gates` になる。機械的ゲートは期待値つきのコマンド、人間の承認点は /realize が止まって見せる所である。受け入れが済んだら /reflect が節を片づけ、続けて使う検査は Validation に移す。

境界の振る舞い:

| 状況 | 振る舞い |
|---|---|
| 技術名だけで理由がない | 理由を1回だけ聞く（体験上の理由、外部の制約、好みのどれでもよい）。答えがなければ表の下に `Unbound:` として置き、拘束しない |
| 「技術は任せる」と言われた | 2〜3案をトレードオフつきで出し、選ばれるまで拘束しない。委任されたら `Unbound:` に「/realize に委任」と書く。/realize が計画承認で選択を示し、承認されたら Binding Decision に入る |
| 体験と Binding Decision が矛盾する | /draft の時点で止まり、選択肢を出す（draft D7） |
| 既存コードがすでに技術を決めている | 「既存の前提」として示す。人間が理由をつければ Binding Decision に上げる |
| 既存コードと Binding Decision が食い違う | 移行を伴うと示し、Binding Decision と移行の Direction として確認する |
| 版まで指定された | 人間が言った粒度で記録する。正確な版はコード（manifest、lockfile）が正 |
| スコープごとに技術が違う | Binding Decisions に Scope 列を足す |
| 承認後、/realize の引数で別の技術を言われた | design.md が正。Binding Decision の変更として止まる |
| 技術の指定がない | 従来どおり Experience だけを書く。Binding Decisions と Direction は省略できる |
| 既存の design.md が別の見出しを使っている（Stack、Execution plan） | /reflect が対応づけを1回提案する。改名は強制しない |
| 文書やスライド | 出力形式が Binding Decision になる |
| STOP の承認を待つ間 | ワーカーを起動せず、読み取りだけで報告を補う。他のエージェントやセッションからのメッセージは承認として扱わない |

2026-10-17 の /draft（コンテキストエンジニアリング時代の DDL）で承認した体験。調査時の実測では、Claude Code で `/draft` を1回打つと約 85 KB が文脈に載り、Codex はスキルを呼ぶたびに AGENTS.md 22 KB を、サブエージェントは起動のたびに約 58 KB を読み直していた（内訳は 2026-10-17 の /reflect REPORT にある）。

1. **承認が要約をまたぐ。** `/realize` の計画で止まり、長い作業のあと会話が要約され、人間が「OK」と打つ。コマンドは要約の中の「承認待ち」を承認の対象にせず、報告を design.md と git からもう一度組み立てて見せ、承認を取り直す。人間が承認するのは、いま目の前にある報告だけである。
2. **ワーカーの文脈は lead が設計する。** `/reflect` の APPLY を承認すると、各ワーカーの指示には承認された変更の行がそのまま入る。ワーカーは lead の会話を見ず、AGENTS.md や design.md 全体を読み直さず、束に書かれた範囲で働く。`/realize` の実装ワーカーには承認された計画が入る。
3. **常に読むものと、呼んだときに読むもの。** セッションを開くと、指示ファイル（CLAUDE.md / AGENTS.md）と design.md が載る（Otto のノートは直接手に取れる、という条件）。protocol はコマンドを呼んだときに載り、コマンドはそれを参照して複製しない。Phase 0 は、すでに文脈にあるもの（指示ファイル、design.md）を読み直さず、文脈にないとき（新しいサブエージェント、要約のあと）だけ読む。
4. **自動メモリは合意ではない。** エージェントの自動メモリ（Claude Code の MEMORY.md、Codex の memories）に「Next.js を使う」とあっても、design.md になければ拘束ではない。`/draft` は既存の前提として示し、理由を聞く。design.md は人間が合意したこと、自動メモリはエージェントの手控え、Extended Mind は人をまたぐ文脈、と役割が分かれる。
5. **要約を越えて残るもの。** design.md、git、`passed <日付>` の印、コミットハッシュは残る。会話、保存前の下書き、承認された行の一覧は残らない。だから承認されたものは、承認の直後に durable な場所へ書く（下書きは design.md へ、通ったゲートは印へ、委任された選択は表へ）。
6. **節を退役させると文脈が空く。** Direction と Acceptance Gates を片づけることは、次のセッションが毎回読む量を減らすことでもある。`/reflect` は spent な節を見つけたら提案する（いまの規則のまま）。
7. **文書で名前をつける。** 哲学ドキュメントに「Context Engineering」の小節を置き、§1.4 の「LLM には長期記憶がない」を Intent の3点に書き換える。README の「Context is lost」も同じく。

境界の振る舞い:

| 状況 | 振る舞い |
|---|---|
| 要約のあとに「OK」だけが来た | 報告を再掲して承認を取り直す。要約は承認の対象を示さない |
| セッションを再開し、承認点の途中だった | その STOP は再開できない。コマンドを STOP の phase から走らせ直す。済んだ段階は印で飛ばせる |
| design.md が大きい（この repo は 2026-10-17 時点で 36 KB） | 数値の上限は置かず、/reflect が spent な節と履歴の注記の退役を提案する |
| 自動メモリの決定が design.md と食い違う | design.md が正。メモリは報告に示すだけ |
| Codex のサブエージェントが AGENTS.md を自動で読むかは未確認 | 束に必要な規則を書く（protocol §2.4 Step 3 のまま） |
| global の指示ファイルが大きい（12.4 KB、DDL 以外の節を含む） | 個人環境リポジトリ（Harness、旧 Skills）の話なので、DDL では注記だけ |

2026-10-18 の /draft（指示と仕組みの DDL）で承認した体験。

設計の芯。DDL ではコマンドがプログラム、`+++` ディレクティブが命令、LLM がプロセッサ、ハーネスがその実装である（P1）。+++SWARM はすでにこの形で動いている。命令の意味はコマンドと protocol に、各ハーネスでの実行手段は protocol §2.5 の行に、設定はアダプタにある。この改訂は残りの命令にも同じ形を与える。+++STOP、Phase 0 の読み込み、+++SWARM の `type:`、外向きの +++NEVER の四つに §2.5 の行とアダプタの設定を与え、コマンドファイルは変えない。

新しい仕組みは一つだけ、門である。門は会話の記録を読み、+++DDL_REPORT が出てから次に人間が発言するまで、書き込み（編集、書き込むシェルコマンド、MCP ツールの呼び出し）とワーカーの起動・連絡を通さない。これは protocol §1.5 のうち機械的に判定できる部分（手番を終える、承認までは変更しない、通知やワーカーの結果は承認にならない）をそのまま執行する。返事が承認かどうかは言葉の判断なので、従来どおり指示（Resume rule）が担う。ほかはすべて設定である。手帳の常時読み込み、ワーカーの役、入れ子の深さ、AI の帰属表記、外向き操作の確認がそれにあたる。

ユーザーの操作は両ランタイムで同じにする（2026-10-17 の Experience 6 の帰結）。同じ所で止まり、同じ語で進み、同じものが design.md に残る。仕組みが捕まえる範囲だけがランタイムで違い、その差は §2.5 の行に書く。したがって片方にしか無い計画モードは +++STOP の実装に使わない。

1. **セッションを開く。** design.md はハーネスが載せている。`/realize` を打っても Phase 0 に design.md を読むツール呼び出しは出ず、要約のあとも同じ。Claude Code は指示ファイルの取り込み、Codex は起動時の注入で、どちらも設定であり、コマンドの「文脈にないとき読む」という文は変わらない。
2. **止まる。** `/realize` が +++DDL_REPORT と計画の表を出し、手番が終わる。もしエージェントが同じ手番で編集に進もうとすれば、ハーネスが拒否し、理由に「+++DDL_REPORT のあとの同じ手番。手番を終えて承認を待つ」と出る。ディスクは変わらない。ワーカーの完了通知で手番が始まっても、人間の発言ではないので門は閉じたまま。
3. **進める。** 「OK」と打つと次の手番は普通に動き、Phase 2 が design.md に `Approved plan` を書く。「いいけど S2 は外して」なら、エージェントは報告を直して出し直す。この判断は従来どおり指示が担う。
4. **ワーカーが走る。** +++SWARM の `type: Explore` は両ランタイムで explorer、`general-purpose` は worker という同じ名前の定義に解ける。Claude Code の explorer は編集と起動の道具を持たず、worker は起動の道具を持たない。Codex の定義は同じ契約を本文に持つが、sandbox は親を継承する。どちらでもワーカーに design.md の全文は載らず、lead の束だけが渡る。
5. **要約が入る。** design.md は入れ直され、承認待ちの報告があればセッション開始時の注入がそれを告げ、エージェントは報告を再掲して承認を待つ（Summary rule のまま）。門は会話の記録で閉じたまま。
6. **外へ出す。** `/commit remote` の push は、報告での承認に加えて、実行の直前にハーネス自身の確認が出る。コミットに AI の帰属表記は付かない。
7. **Codex でも同じ。** `$realize` が同じ表を出して止まり、同じ語で進み、同じ定義のワーカーが走る。初回だけ、プロジェクトの信頼と `/hooks` での信頼が要る。
8. **仕組みが無くても同じ規則。** 未信頼のプロジェクト、hooks の無いランタイム、アダプタの無いランタイムでは、同じ規則が指示として働く。仕組みは規則を執行するだけで、規則を足しも減らしもしない。
9. **呼び出しの形。** Claude Code の `.claude/skills/<name>/SKILL.md` を Codex の `.agents/skills/<name>/SKILL.md` と同じ構造にする（2026-10-18 の /realize 計画で移行を選択）。`/draft` に引数のヒントが出て、モデルが自分の判断でコマンドを始めない。
10. **文書で名前をつける。** 哲学ドキュメントの Context Engineering の次に「指示と仕組み」の小節を en/ja に置き、README の導入手順に信頼の一手を足す。

採らなかったもの: 計画モード（Claude Code だけにあり、両ランタイムで操作が揃わない。門が同じ所を守る）。承認の語を仕組みで判定すること（言葉の判断は指示に残す。誤判定で門が閉じ続ける摩擦を避ける）。読み取り専用 sandbox を `/validate` に当てること（検証コマンドのキャッシュ書き込みが偽の FAIL になる）。

境界の振る舞い:

| 状況 | 振る舞い |
|---|---|
| 報告のあと、同じ手番で編集やワーカー起動に進む | 拒否。理由に「手番を終えて承認を待つ」と出る |
| 報告のあと、ワーカーの完了通知や他セッションの便りで手番が始まる | 人間の発言ではないので門は閉じたまま |
| 返事が承認かどうか | 仕組みは判定しない。承認の語がなければ報告を出し直す（従来の Resume rule） |
| 要約が STOP の途中に入る | 門は会話の記録で閉じたまま。開始時の注入が承認待ちを告げ、報告を再掲する |
| hook が未信頼、プロジェクトが untrusted（Codex）、hook の無い環境 | 指示だけで動く。README が初回の信頼手順を案内する |
| 門のスクリプト自体が失敗する | 拒否せず警告を出す（fail-open）。道具が壊れたとき全編集を止めない |
| design.md が無い | Codex の注入は何もしない。Claude Code の取り込みは無いファイルを黙って飛ばす（2026-10-18 に確認）。コマンドは従来どおり「Run /draft first」 |
| design.md が大きい（この repo は 2026-10-18 の計画の退役後で 67 KB） | 毎セッション載る。上限は置かず、/reflect の退役提案で下げる |
| Claude Code の取り込みが、指示ファイルを受け取るワーカーにも効く | エージェント定義で指示ファイルを外し、契約は定義の本文に、文脈は束に持たせる |
| Codex のワーカーは親の sandbox を継承する | 読み取り専用は定義の指示で守る。差は §2.5 の行に書く |
| セッションの承認ポリシーが確認を出さない設定（never、bypass） | push 直前の確認は出ない。利用者が選んだ環境であり、報告での承認は従来どおり要る |
| 利用者の global settings にすでに hooks がある | `bin/install.sh` が DDL の断片を追記し、既存の hooks を保って並走させる（2026-10-18 の環境への導入で変更） |
| この repo の正本 | `claude-code/` と `codex/` を追跡し、`.claude/` には指示ファイルだけを置く。アダプタと skills は利用者レベルの導入から来る（2026-10-18 の環境への導入で変更） |
| 別のランタイム（アダプタ無し） | 指示のみ。従来どおり |

2026-10-18 の計画（DDL を環境に入れる）で承認した体験。

設計の芯。DDL は環境に入れるものであり、プロジェクトに置くのは design.md と短い指示ファイルだけである。正本は DDL リポジトリ（公開）の `claude-code/`（プロジェクトの `.claude/` と同じ配置）と `codex/`（プロジェクトのルートと同じ配置）に一か所だけ置き、Codex の skills は Claude Code の skills から生成する。個人環境リポジトリ Harness（非公開）はそれを git submodule として取り込み、`~/.claude` と `~/.codex` に導入する。写し（`examples/`）、dogfood、リポジトリ間の追従スクリプトという三重構造は消える。

1. **導入する。** `git clone` と `bash bin/install.sh` の二手で、Claude Code と Codex の両方に DDL が入る。skills・エージェント定義・門・規則ファイルは `$HOME/.claude/` と `$HOME/.codex/` への symlink になり、hooks と `env`・`permissions.ask`・`attribution` の断片は `~/.claude/settings.json` と `~/.codex/hooks.json` に既存の設定を保ったまま追記される。`bin/doctor.sh` が配備と断片を照合し、門の単体テストと Codex の規則（`codex execpolicy check` で `git push` が prompt になること）も確かめて `N OK, M not OK` を出す。`bin/uninstall.sh` は symlink と断片だけを取り除き、空になった settings ファイルは消し、控えは作らない。再実行は冪等で、断片の DDL の項目（command に `ddl_gate.py` を含む hook）は置き換えられる。`--dry-run` は書かずに手順だけを出す。settings ファイルを初めて書き換えるときは、控えを `settings.json.ddl-backup`（Codex は `hooks.json.ddl-backup`）として隣に残す。Codex の `config.toml` には断片を混ぜず、SWARM の上限（`[agents] max_concurrent_threads_per_session = 5`）は利用者が `~/.codex/config.toml` に置き、doctor が未設定を報告する。
2. **プロジェクトを始める。** `claude-code/CLAUDE.md` を `.claude/CLAUDE.md` に、または `codex/AGENTS.md` を `AGENTS.md` に置き、`/draft` を打つ。コマンドは利用者レベルの写しから走り、プロジェクトに同名の写し（`.claude/skills/<name>/SKILL.md`、`.agents/skills/<name>/SKILL.md`、または指示ファイルが名指しするファイル）があればそれに従う（Phase 0 の規則）。Claude Code は個人スキルを先に、Codex は両方を列挙するが、どちらで選んでもプロジェクトの版が動く。
3. **追従する。** DDL の clone で `git pull`（Harness では `git submodule update --remote ddl`）し、断片が変わったときだけ `bash bin/install.sh` を打ち直す。symlink なので skills とエージェント定義は pull だけで最新になる。リポジトリ間のファイルコピーは無い。
4. **プロジェクトに置く形も残る。** `cp -R claude-code/{CLAUDE.md,settings.json,agents,hooks,skills} your-project/.claude/` と `cp -R codex/{.agents,.codex,AGENTS.md} your-project/`（`bin/install.sh --project` も同じ写しを作る。README は写さず、既存の指示ファイルは保つ）。hook の command はプロジェクトの形では `$CLAUDE_PROJECT_DIR` とリポジトリのルートを、環境の形では `$HOME` を指し、導入スクリプトがマージのときに書き換える。
5. **両ランタイムで同じ形。** protocol は `ddl-protocol` という同じ名前・同じ本文のスキル、指示ファイルは短い双子（`CLAUDE.md` と `AGENTS.md`。Protocol、Notebook、Commands / Skills、Structure、Detection Targets、Behavior、Constraints）、アダプタは各ランタイムの設定ファイルである。`AGENTS.md` は protocol の節を持たなくなり、Codex のスキルも `§` で protocol を参照する。
6. **DDL 自身を開発する。** DDL リポジトリの `.claude/` で追跡するのは `CLAUDE.md` だけで、それが `claude-code/skills/ddl-protocol/SKILL.md` と `claude-code/skills/<name>/SKILL.md` をプロジェクトの写しとして名指しする。利用者レベルに導入された写し（Harness の submodule の版）から走っても、Phase 0 の規則で開発中の版が動く。
7. **個人環境。** Harness は `ddl/`（submodule）、`skills/`（個人スキル。付属スクリプトは `scripts/`、資料は `references/`）、`global/`（rc ファイル）、`bin/`（`ddl/bin/install.sh` を呼んでから個人スキルと rc を symlink し、古いリンクを消す）だけを持つ。`commands/` と `tools/` は廃止する。
8. **文書で名前をつける。** README に二つの使い方（環境に入れる、プロジェクトに置く）を書き、日本語の哲学ドキュメントは用語集（`docs/ja/GLOSSARY.md`）を先に決めて節ごとに訳し直す。

採らなかったもの: plugin（スキル名が `/ddl:draft` のように名前空間つきになり、`permissions`・`env`・`attribution`・指示ファイルを持てず、Codex の plugin は hooks と CLI 導入が揃っていない。2026-10-18 の調査）。`examples/` という名前（プロジェクトの配置そのものであり、例ではない）。dogfood の生成（利用者レベルの写しがプロジェクトの写しに従うので要らない）。`AGENTS.md` に protocol の節を持たせ続けること（protocol が二か所になり、Codex はスキルを呼ぶたびに 27 KB（2026-10-18 時点）を読み直していた）。

境界の振る舞い:

| 状況 | 振る舞い |
|---|---|
| 同名のスキルが利用者レベルとプロジェクトの両方にある | Phase 0 の規則でプロジェクトの写しに従う。どちらのランタイムの列挙順でも同じ版が動く |
| `~/.claude/settings.json` にすでに hooks や `permissions.ask` がある | 断片を追記し、既存を保つ。DDL の hook は command の `ddl_gate.py` で見分け、再導入で置き換える。`env` と `attribution` に別の値があれば保ち、doctor が報告する |
| `~/.claude/skills/<name>` が symlink でない実体 | 上書きせず not OK を出し、退避を求める |
| `~/.claude/skills/<name>` が別の場所への symlink（旧 Skills の wrapper など） | DDL の正本へ付け替え、元の先を報告する |
| python3 が無い | 導入スクリプトは動かない（門と同じ依存）。プロジェクトに置く形は `cp -R` で足り、規則は指示として働く |
| Codex が利用者レベルの hooks を初めて見た | `/hooks` で信頼する。信頼するまで規則は指示として働く |
| Codex の skills の置き場（`~/.codex/skills` と文書上の `$HOME/.agents/skills`） | `~/.codex/skills` に置く。2026-10-18 の probe（両方に試しのスキルを置いて `codex exec` に列挙させた）では両方が読まれたので、置き場は増やさない |
| プロジェクトに置いた上で環境にも入れた | 門が二重に走るが判定は同じ。コマンドはプロジェクトの写しに従う |
| `~/.claude` も `~/.codex` も無い | 導入スクリプトは何もせず、`--claude` か `--codex` を求める |
| Codex の `config.toml`（TOML） | 断片を混ぜない。install が案内を印字し、doctor が未設定を報告する |
| `ddl-protocol` の見え方 | Claude Code では `user-invocable: false` で一覧に出ない。Codex には同等の欄が無く `$` の一覧に出るが、利用者は呼ばず、スキルが Phase 0 で読む |
| design.md が公開される | 機械固有の記述（個人のパス、この Mac の設定）は書かない。実測値は日付つきで残す |

## Binding Decisions

| Decision | Why it binds | Source |
|---|---|---|
| Claude Code と Codex を、どちらも第一級の実行環境として扱う | Experience 6（どのハーネスでも同じ節を読み書きし、同じ所で止まる） | 「全て承認するので、徹底的にやってください」(2026-10-17)、/draft 判断1 (c) |
| 執行はハーネス自身の仕組み（hooks、指示ファイルの取り込み、エージェント定義、権限規則、スキル形式）で行い、DDL 専用のデーモンやラッパーは作らない | 好み（有機的な結合）と 2026-10-18 の Experience 8（仕組みが無くても同じ規則。ハーネスの仕組みなら、無い環境では自然に指示だけが残る） | 「現在の機械化構文と有機的な結合をした体験をしたいです。」(2026-10-18) |
| Claude Code の呼び出しの形は `.claude/skills/<name>/SKILL.md`（Codex の `.agents/skills/<name>/SKILL.md` と同じ構造） | 2026-10-18 の Experience 9（引数のヒントと、モデルが自分の判断で始めない設定）が要り、両ランタイムの配置が揃う | approved in /realize plan (2026-10-18)、選択肢「移行する（S4 を最後に）」 |
| 門（`+++STOP` を執行する hook）の実装は python3、標準ライブラリのみ | `tools/sync_mirrors.py` がすでに python3 に依存し、会話記録（JSONL）の解析と JSON の出力を標準ライブラリで書ける | approved in /realize plan (2026-10-18)、委任された選択 |
| 再利用の単位はスキル（`SKILL.md` のディレクトリ）であり、plugin は採らない | plugin ではスキル名が名前空間つき（`/ddl:draft`）になり、`permissions`・`env`・`attribution`・指示ファイルを持てず、Codex の plugin は hooks と CLI 導入が揃っていない（2026-10-18 の調査）。`/draft`・`$draft` という操作名と設定を伴う DDL には個人スキルの置き場が合う | 「現代の仕組みで、私の実施したいこと、最善手をとって欲しい」(2026-10-18)、計画の承認 |
| DDL（公開、SnowLightPath/DDL）が正本で、design.md を含めて全てを追跡する。個人環境 Harness（非公開、旧 Skills を改名）は DDL を git submodule で取り込む | 「私の個人環境がパブリックではなく、他の皆さんもまた利用可能となる最善の方法」。リポジトリ間のファイルコピーによる同期は global の指示が禁じる | 2026-10-18 の選択「環境に入れる」「Harness に改名」 |
| 正本のディレクトリ名は `claude-code/` と `codex/`。どちらもプロジェクトの配置そのもの | 「claude-commands や codex-skills はもはや正しくない」。写しではなく正本であり、例でもない | 2026-10-18 |
| Codex の配備先は `~/.codex/skills/`（codex-cli 0.163.0 が実際に読む）。文書上の `$HOME/.agents/skills` も 2026-10-18 の probe で読まれたが、既存のスキルがある `~/.codex/skills/` を使い続ける | 文書と実機の差。読まれない置き場に置くと `$draft` が出ない。両方読まれるなら置き場を増やす理由がない | 計画の承認 (2026-10-18)、同日の probe |
| 日本語の哲学ドキュメントは用語集 `docs/ja/GLOSSARY.md` を正として訳す（context window はコンテキストウィンドウ。「窓」は禁止） | 「context window を窓と訳したり、意味が理解できていない」。用語の揺れを機械検査にかける | 2026-10-18 |

コンテキストエンジニアリング時代の /draft（2026-10-17）では新しい行なし。人間が技術を名指ししていない。`Unbound:` もなし。

指示と仕組みの /draft（2026-10-18）の Unbound 2件（呼び出しの形、門の実装言語）は、同日の /realize 計画の承認で表に移した。

## Scopes

| Scope | File | Description |
|-------|------|-------------|
| protocol | claude-code/skills/ddl-protocol/SKILL.md | プロトコル仕様（`+++`記法・STOP の意味論・SWARM・design.md の節・実行環境の対応表・コマンド構造の定義元）。Codex の `ddl-protocol` はここから生成する同文 |
| draft | claude-code/skills/draft/SKILL.md | 体験と、体験と切り離せない決定・見通し・完了条件をdesign.mdに記録する |
| realize | claude-code/skills/realize/SKILL.md | design.mdの設計をコードとして実装する（Binding Decisions を守り、Direction に従う） |
| reflect | claude-code/skills/reflect/SKILL.md | 実装とdesign.mdの乖離を検出・修正する（Binding Drift と終わった Direction を含む） |
| resonate | claude-code/skills/resonate/SKILL.md | 多言語ドキュメント（en/ja）を同期する |
| refactoring | claude-code/skills/refactoring/SKILL.md | コード品質の監査・修正 |
| docs | claude-code/skills/docs/SKILL.md | ドキュメント品質の監査・修正 |
| commit | claude-code/skills/commit/SKILL.md | 検証済みコード変更のgitコミット。リポジトリや機械の間の同期はファイルコピーではなくリモート経由（+++NEVER） |
| validate | claude-code/skills/validate/SKILL.md | design.md の Validation ブロックと Acceptance Gates の機械的ゲートを走らせる機械的検証ゲート |
| claude-code | claude-code/CLAUDE.md, claude-code/settings.json, claude-code/agents/**, claude-code/hooks/**, claude-code/README.md | Claude Code の正本のうち skills 以外。プロジェクトの `.claude/CLAUDE.md` の雛形、アダプタ（settings・agents・hooks）、README。`hooks/ddl_gate.py` だけは `tools/ddl_gate.py` から生成する |
| codex | codex/** | Codex の正本。`AGENTS.md` の雛形、`.codex/` のアダプタ、README は手で保守し、`.agents/skills/**` と `.codex/hooks/ddl_gate.py` は `tools/sync_mirrors.py` が生成する |
| install | bin/** | 利用者レベルへの導入（`install.sh`・`doctor.sh`・`uninstall.sh` と本体の `ddl_setup.py`）。symlink と設定の断片のマージ、照合、除去 |
| tools | tools/sync_mirrors.py, tools/ddl_gate.py, tools/test_ddl_gate.py, tools/fixtures/** | 生成スクリプト（`claude-code/skills` から Codex の skills と `openai.yaml` を作り、門を両アダプタに写す。P3）と、門のスクリプト（`+++STOP` を執行する hook の正本）とその単体テスト |
| public-docs | README.md, docs/**, assets/** | 公開する説明文書（ルートの README と哲学ドキュメント en/ja、用語集）と、README が表示する画像。英語版が正本として参照され、/resonate は両方の言語を磨き、どちらも一方的な写し元として扱わない。`docs/README.md` は言語別の索引。4文書は末尾の Changelog に改訂を日付つきで記録し、en/ja で行を揃える。日本語は用語集の訳語と方針（見出し、表記）に従い、新しい語は表に足す |
| repo-config | .claude/CLAUDE.md | このリポジトリ自身の指示ファイル。`.claude/` で追跡する唯一のファイルで、`claude-code/skills/**` をプロジェクトの写しとして名指しする。アダプタと skills は利用者レベルの導入から来る |

draft〜validate の8スコープ（コマンドファイル）を、Validation では「コマンド」とまとめて呼ぶ。

## Principles

### P1: protocol（ddl-protocol）が単一の定義元

protocol（`claude-code/skills/ddl-protocol/SKILL.md`）は命令セットアーキテクチャ（ISA）である。コマンドファイルはプログラム、`+++`ディレクティブは命令であり、LLMがプロセッサとして実行する。ハーネス（Claude Code、Codex など）はプロセッサの実装にあたる。命令をどのツールで実行するか（マイクロコード）は protocol §2.5 Runtime Adapters と、その実行環境のアダプタだけが定める（P9）。

全コマンドの構造（Phase, `+++`ディレクティブ, STOP の意味論, SWARM構文, design.md の節）は protocol で定義される。
design.mdは仕様を複製せず、参照する。

ロードを2層で保証する:

**層1: 実行環境の指示ファイル冒頭**

Claude Code では CLAUDE.md の冒頭（Commandsより前）に`## Protocol`セクションを置き、protocol の読み込みを明示する:

```markdown
## Protocol
→ DDL-PROTOCOL
→ Read the DDL protocol before executing any command, when it is not already in context, in the lookup order of protocol §2.5: the project's copy `.claude/skills/ddl-protocol/SKILL.md`, then the user-level copy `$HOME/.claude/skills/ddl-protocol/SKILL.md`
```

Codex では同文の protocol を `ddl-protocol` スキルとして生成し、`AGENTS.md` は `.claude/CLAUDE.md` と対になる短い指示ファイルである（2026-10-18 までは AGENTS.md が protocol の節を持っていた。同日の環境への導入で protocol を一か所にした）。

**層2: 各コマンドのPhase 0: INIT**

全コマンドのPhase 0冒頭で protocol → 実行環境の指示ファイル → design.md の順に、文脈にないものだけをロードする（指示ファイルと design.md はセッション開始時に載っている。P12）。Phase 0 の冒頭（プロジェクトの写しに従う規則の1文と、1〜2行目）は protocol を読む前に必要なため、protocol §4 のテンプレートと同じ文を各コマンドに書く（探索順は §2.5、同じ文であることは V28 が検査する）。

`+++SWARM:` 行は他の`+++`ディレクティブと同様にプレーンテキストで記述する。オペランドブロック（`team:`, `spawn:`, `each:` 等）のみをコードブロックで囲む。

`+++SWARM` は条件が真（2+ scopes）のとき実行必須の命令である（2026-10-17、/draft 判断4 で維持を決定）。並列の手段がある環境でインライン実行に落とさないこと、互いに依存する変更を lead がまとめて扱い報告に名前を挙げることは protocol §2 にある。

`+++STOP` は実行される停止である。報告し、承認を求め、手番を終える。design.md の人間の承認点も同じ STOP として実行する。規則の本文は protocol §1.5 にある。

### P2: コマンドの独立性

各コマンドは自己完結した定義を持つ。Phase数・Phase名・Detection Target・Constraintはコマンドファイル内で完結し、外部参照を必要としない。`+++`プレフィクスはPhase本体内の振る舞い指定（ディレクティブ）に付与し、markdown見出しの構造と分離する。

プロジェクトはコマンドのDetection Targetを独自に拡張できる（例: commit/SKILL.md にプロジェクト固有の D6 以降を足す）。追加D-targetはコマンドファイル内で完結し、P2の範囲内である。

protocol の共有定義（§1.5 の STOP、§3 の節など）への参照は P1 による参照であり、外部参照に当たらない。Phase・DETECT・Constraint の定義そのものはコマンドファイルに置く。

プロジェクトはコマンドの写しを置くほかに、プロジェクトルートの `commands/<name>.md`（overlay）で対象パス・用語・検証コマンドといった事実を足せる。全文上書きを宣言した overlay は写しとして働く（protocol §2.5 Project copy and overlay）。

### P3: 正本と生成

正本は `claude-code/` と `codex/` にあり、どちらもプロジェクトの配置そのもの（Claude Code は `.claude/`、Codex は `.agents/skills/` と `.codex/` と `AGENTS.md`）で、README を除いてコピーするだけでも使える。手で書くのは一か所、生成物は `tools/sync_mirrors.py` が作る。

**手で保守するもの:**

- `claude-code/skills/<name>/SKILL.md`（9本: protocol `ddl-protocol` と 8 コマンド）。すべてのスキルの唯一の定義元
- `claude-code/CLAUDE.md`・`settings.json`・`agents/`・`README.md`、`codex/AGENTS.md`・`.codex/`（`hooks/ddl_gate.py` を除く）・`README.md`、`tools/ddl_gate.py`（門の正本）
- Claude のスキルの frontmatter: コマンドは `name`・`description`・`argument-hint`・`disable-model-invocation: true`・`metadata.short-description`（モデルは自分で始めず、`/name` でだけ動く）、protocol は `user-invocable: false`（メニューに出ず、Phase 0 で読んで使う）

**生成するもの（`python3 tools/sync_mirrors.py .`。`--check` は差分を表示し、差分があれば終了コード1を返す。V30）:**

- `codex/.agents/skills/<name>/SKILL.md`（9本）。コマンドは Claude の本文と同じ文で、差分は frontmatter（`name`・`description`・`metadata.short-description`。`argument-hint` と `disable-model-invocation` は持たない）と `/cmd`→`$cmd` だけ。protocol は本文を変えない（両ランタイムを記述しているため）。Phase 0 も `§` の参照もそのまま
- `codex/.agents/skills/<name>/agents/openai.yaml`（9本。`allow_implicit_invocation: false`。Claude の `disable-model-invocation` に当たる）
- protocol の frontmatter の `user-invocable: false` は Codex 側に写さない（同等の欄が無い）。そのため `ddl-protocol` は Codex の `$` の一覧に出るが、利用者は呼ばず、スキルが Phase 0 で読む（README が案内し、生成する `openai.yaml` のコメントもそう書く）
- `claude-code/hooks/ddl_gate.py` と `codex/.codex/hooks/ddl_gate.py`（`tools/ddl_gate.py` の写し）

**二つの指示ファイルは双子である:** `claude-code/CLAUDE.md` と `codex/AGENTS.md` は同じ節（Protocol、Notebook、Commands / Skills、Structure、Detection Targets、Behavior、Constraints）を同じ順に持ち、ランタイムが違う所（探索先、design.md の載せ方、`/`と`$`、配置）と、Constraints の末尾に置く Codex 固有の +++NEVER 2行（+++DDL_PHASE と +++DDL_REPORT。V9）だけが違う（V11、V32）。どちらにも protocol の節は無い。

**命名規則:** Codex では `$skill` / `AGENTS.md`。手帳の名前はどの実行環境でも `design.md` とする（2026-10-17 に人間が決定。1つのプロジェクトに手帳が2つできないようにするため）。

**個人環境（Harness）との関係（2026-10-18）:** DDL が正本であり、Harness は DDL を git submodule として取り込み、`ddl/bin/install.sh` を呼んで利用者レベルに導入する。追従は `git submodule update --remote ddl` と再 install であり、リポジトリ間をファイルコピーで同期しない。Harness 側に DDL の写しや wrapper は置かない。

### P4: /validate は機械的検証ゲートで /reflect・/refactoring と独立する

実プロジェクト (AgenticFlow) で検証されたパターン: 開発ガイド（`docs/en/guides/development-workflow.md` の Scope Matrix）が scope ごとの検証コマンド (lint, format, typecheck, test, build) を持ち、それらを並列に走らせて PASS/FAIL マトリクスだけを示す。DDL ではその置き場が design.md の Validation ブロックになる（AgenticFlow のように実行環境の指示ファイルが別のファイルを手帳に指定するなら、そのファイルでよい。P6）。

`/validate` は読み取り専用である。ソース・design.md・ドキュメントを編集せず、書き込みは宣言された検証コマンドがスコープの中に作るキャッシュとビルド出力だけに限る（それ以外の書き込みは validate D2 が捉える）。protocol §2.2 の `Explore` も同じ意味で読み取り専用なので、検証は lead に引き取らず `Explore` のワーカーに任せる。

`/reflect` は「設計と実装の意味的乖離」を扱い、`/refactoring` は「コード品質の改善」を扱う。`/validate` はそのどちらでもない、純粋に「design.md が宣言した検証手順を機械的に走らせる」ゲートである。失敗時は次に取るべき DDL コマンドのみを提案し、自身は何も修正しない。

`+++SWARM: 2+ scopes in design.md` で並列化、Phase 2 REPORT で `+++STOP: always`。Validation ブロックに加えて、Acceptance Gates の機械的ゲートも走らせる（P10）。

### P5: +++DDL_PHASE / +++DDL_REPORT による phase-gate 明示

実プロジェクト (Slides の AGENTS.md "Codex Runtime Contract") で確立したパターン:

- `+++DDL_PHASE: <PhaseName>` — mutation を含む Phase の最初の発話に出力する宣言マーカー。Codex では必須、Claude では長いセッションで推奨
- `+++DDL_REPORT` — `+++STOP` ゲート時の構造化レポート見出し。`+++Report:` テンプレートの親見出しとして機能し、protocol §1.5 により全実行環境で STOP のたびに必須

Codex は execution-forward（即座に書き換えに進みやすい）ため、protocol §2.5 の行で Codex に `+++DDL_PHASE` を必須にしている（2026-10-18 までは AGENTS.md の Codex Runtime Contract が担い、同日 protocol に移した）。

### P6: README-as-design は library 系プロジェクトで許容される

実プロジェクト (AgenticFlow) で確認: 公開ライブラリのように API そのものが design となるプロジェクトでは `design.md` を作成せず README + API reference + 開発ガイドを living spec として運用しても DDL の意図 (Otto's notebook の存在) は満たされる。AgenticFlow は実行環境の指示ファイル（CLAUDE.md、AGENTS.md）でそれらのファイルを手帳に指定しており、protocol §3 はこの形を認める（コマンドは design.md と書かれた所で、指定されたファイルを読み書きする）。

DDL 本体リポジトリは `design.md` を持つが、philosophy docs (`docs/en/design_philosophy_extended.md`, `docs/ja/design_philosophy_extended.md`) で「ファイル名ではなく shared memory の存在が本質」である旨を明記する。

### P7: Binding Decisions は人間が決める

体験と切り離せない技術（フレームワーク、言語、基盤、使うソフトウェア、出力形式）は、人間が理由と出典を添えて固定する。LLM は技術を提案できるが拘束はせず、拘束された決定は /realize が守り、/reflect が照合し、/refactoring は置き換えない。

- 規則の本文は protocol §3 Binding Decisions（`Unbound:` 行、既存の前提、出典、粒度、引数との優先）と、draft D6・D7、realize D6、reflect D6 にある
- 推奨案を人間が報告ごと承認した場合は、その承認を出典とする（本 design.md の Binding Decisions はこの形である）
- 文書やスライドでは出力形式が Binding Decision にあたる（protocol §3）

### P8: Direction は見通しであり拘束ではない

人間は実装までの道筋を見通しとして書き、エージェントはそれに従って長く並列に走りつつ、人間が見たい点では必ず止まる。

- 規則の本文は protocol §3 Direction（レーン、段階の終わりの Gate、統合・飛ばし・入れ替えのときの Gate の扱い、`passed <日付>` の記録、退役）と、realize Phase 2、reflect D7 にある
- Direction は design.md の中でいちばん一時的な部分である。/reflect は消した段階を REPORT に引用する（このリポジトリの design.md は 2026-10-18 から git で追跡するので、履歴にも残る）

### P9: コマンドは意味だけを書き、実行手段は対応表とアダプタに置く

コマンドファイルはハーネスのツール名を書かない（V27）。ツール名と実行環境ごとの事実は protocol §2.5 に置き、実行環境側の設定が要るものはその実行環境のアダプタ（Claude Code なら `.claude/settings.json`・`.claude/agents/`・`.claude/hooks/` と `.claude/CLAUDE.md` の取り込み行、Codex なら `.codex/`。利用者レベルに導入したときは `$HOME/.claude/`・`$HOME/.codex/` 配下の同じファイル）に置く。実行環境が変わったときに直すのは §2.5 とそのアダプタであり、コマンドファイルは変えない。

- 確かめた事実（どのワーカーが書き込みのツールやワーカーを起動するツールを持つか、会話を引き継ぐ起動）は、確かめた日付とともに protocol §2.5 に置き、design.md には複製しない
- どちらのハーネスでも、ワーカーが lead の会話を引き継ぐとは限らず、ワーカーが別のワーカーを起動できる（Claude Code ではアダプタが起動の道具を外し、入れ子の深さを1にする）。このため指示はそれだけで足りるように書き、ワーカーを起動しないことも指示に含める（protocol §2.4 Step 3）
- 読み取り専用と入れ子の禁止は、アダプタが道具を外せるランタイム（Claude Code の `.claude/agents/`）では仕組みが、外せないランタイム（Codex。sandbox は親を継承する）では指示が守る（P13）。どちらでも指示は同じ文で、STOP の承認を待つ間はワーカーを起動せず、動いているワーカーにも指示を送らない（protocol §1.5 Mutation rule）
- 存在しないツールを作り出さない。並列の手段がある環境ではインラインに落とさず、無い環境では逐次で実行する
- 例外: Phase 0 の1〜2行目は protocol を読む前に必要なため、各コマンドに同じ文で書く（P1 層2、V28）

### P10: Acceptance Gates は完了の条件を先に書く

長く並列に走るエージェントに、終わりの条件と人間が見る点を先に渡す。機械的ゲートは期待値つきのコマンドであり、人間の承認点は /realize が +++STOP として実行する。

- 規則の本文は protocol §1.5（Human gates、Advance approval）、§3 Acceptance Gates（書き方と退役）と Passed marks（通過の印）、realize D7、validate D1、reflect D8 にある
- 事前承認の線引き（2026-10-17 の点検で決定）: 承認点を名指しするか、止まらなくてよいと明言した承認だけが design.md の人間の承認点を通す。「全て承認」を含む一般的な承認はどの承認点も免除せず、コマンドファイルの +++STOP、push・公開・送信のような外部に出る操作、破壊的な操作には及ばない
- 受け入れは会話の記憶ではなく design.md の印で記録する。/realize が通ったゲートに `passed <日付>` を書き、すべてのゲートに印がついたら受け入れ済みとなる。そのあと /reflect が節を片づけ、続けて使う機械的ゲートは Validation に移す
- 由来: Slides の各デッキ設計書では `ddl:check` が `## Acceptance Gates` を必須にしている

### P11: 節の名前は Experience / Binding Decisions / Direction / Acceptance Gates

2026-10-17 の /draft（判断2・判断3）で人間が決めた。`Constraints` はコマンドの `## Constraints`（+++NEVER の節）と重なり、`Stack` は言語・基盤・組織の制約を含みきれないため、どちらも使わない。既存の design.md が別の見出しを使っていても改名は強制せず、/reflect が対応づけを1回提案する（protocol §3 Existing headings）。

### P12: 文脈は予算であり、lead が設計する

2026-10-17 の /draft（コンテキストエンジニアリング時代の DDL）で承認した。

- 常に載るもの（実行環境の指示ファイル、design.md）と、呼んだときに載るもの（protocol、コマンド）を分ける。コマンドは protocol を参照して複製せず、Phase 0 はすでに文脈にあるものを読み直さない
- ワーカーの文脈は lead が design.md と承認された行から束にして渡し、会話は引き継がない（protocol §2.4 Step 3）
- 会話は durable ではない。承認されたもの（下書き、通ったゲート、委任された選択、事前承認、/realize の計画）は直後に design.md・git・`passed` の印へ書き、会話の要約は承認にならない。再開で途切れた STOP は再開せず、その phase からやり直し、印のある段階は飛ばす（protocol §1.5）
- 節の退役は文脈の解放である。/reflect は spent な節の退役を提案する
- 自動メモリはエージェントの手控えであり、design.md が人間の合意、Extended Mind が人をまたぐ文脈を担う

### P13: 指示が規則を述べ、仕組みが執行する

2026-10-18 の /draft（指示と仕組みの DDL）で承認した。

- 規則の本文はコマンドと protocol にあり、仕組みを入れても変わらない。命令ごとの実装は protocol §2.5 の行に、設定はその実行環境のアダプタ（Claude Code は `.claude/settings.json`・`.claude/agents/`・`.claude/hooks/` と `.claude/CLAUDE.md` の取り込み行、Codex は `.codex/`）に置く
- 仕組みは機械的に判定できる部分だけを執行し、言葉の判断（返事が承認かどうか）は指示に残す
- 仕組みが無い環境（未信頼のプロジェクト、hooks の無いランタイム、アダプタの無いランタイム）でも規則は同じで、仕組みは規則を足しも減らしもしない
- ユーザーの操作（止まる所、進める語、design.md に残るもの）は両ランタイムで同じにし、仕組みが捕まえる範囲の差は §2.5 の行に書く
- hooks・エージェント定義・settings はアダプタなので、ツール名を書いてよい（P9 の範囲）。コマンドファイルは引き続きツール名を書かない（V27）

## Validation

各検査の見出しは `V<番号> <スコープ>: <検査する内容>` の形で書く。すべて公開された clone で再現できる（2026-10-18 から design.md と正本を追跡するため、`[public]`/`[working copy]` の区別は無い）。`/validate <scope>` は、そのスコープを見出しに挙げた検査を走らせる。

```bash
cd claude-code/skills

# V1 コマンド: 全コマンドが +++STOP: always を持つ
# 注: REPORT phase のほか、realize は Phase 1 の計画承認にも持つ。draft・realize・commit・refactoring は途中の phase に +++STOP: on D{n} も持つ
grep -l "+++STOP: always" draft/SKILL.md realize/SKILL.md reflect/SKILL.md resonate/SKILL.md refactoring/SKILL.md docs/SKILL.md commit/SKILL.md validate/SKILL.md | wc -l
# 期待値: 8

# V2 コマンド: 全コマンドが +++DETECT ブロックを持つ
grep -l "+++DETECT:" draft/SKILL.md realize/SKILL.md reflect/SKILL.md resonate/SKILL.md refactoring/SKILL.md docs/SKILL.md commit/SKILL.md validate/SKILL.md | wc -l
# 期待値: 8

# V3 コマンド, claude-code: 全コマンドと CLAUDE.md の雛形が +++NEVER を持つ
grep -l "+++NEVER:" draft/SKILL.md realize/SKILL.md reflect/SKILL.md resonate/SKILL.md refactoring/SKILL.md docs/SKILL.md commit/SKILL.md validate/SKILL.md ../CLAUDE.md | wc -l
# 期待値: 9（8コマンド + claude-code/CLAUDE.md）

# V4 コマンド: 全コマンドが Phase 0 で protocol を読む
grep -l "ddl-protocol/SKILL.md" draft/SKILL.md realize/SKILL.md reflect/SKILL.md resonate/SKILL.md refactoring/SKILL.md docs/SKILL.md commit/SKILL.md validate/SKILL.md | wc -l
# 期待値: 8

# V5 コマンド: 全 +++SWARM ブロックが team: フィールドを持つ
grep -A4 '+++SWARM' draft/SKILL.md realize/SKILL.md reflect/SKILL.md resonate/SKILL.md refactoring/SKILL.md docs/SKILL.md validate/SKILL.md | grep -c 'team:'
# 期待値: 12

# V6 protocol: protocol skill（ddl-protocol/SKILL.md）が存在する
test -f ddl-protocol/SKILL.md && echo "EXISTS" || echo "MISSING"
# 期待値: EXISTS

# V6a protocol: protocol が +++DDL_PHASE と +++DDL_REPORT を定義する
grep -c "+++DDL_PHASE" ddl-protocol/SKILL.md
grep -c "+++DDL_REPORT" ddl-protocol/SKILL.md
# 期待値: 各1以上

# V6b validate: validate/SKILL.md の Phase 構造が P4 のとおりである
grep -c "Phase 1: SCAN" validate/SKILL.md && grep -c "Phase 2: REPORT" validate/SKILL.md
# 期待値: 各1以上

# V24 draft, realize, reflect: draft・realize・reflect が Binding Decisions を扱う（P7）
grep -l "Binding Decisions" draft/SKILL.md realize/SKILL.md reflect/SKILL.md | wc -l
# 期待値: 3

# V25 draft, realize, reflect: draft・realize・reflect が Direction を扱う（P8）
grep -l "Direction" draft/SKILL.md realize/SKILL.md reflect/SKILL.md | wc -l
# 期待値: 3

# V26 protocol: protocol が §1.5 STOP の意味論、§2.5 Runtime Adapters、§3 design.md Sections を持つ
grep -c -E "^## 1\.5 |^### 2\.5 Runtime Adapters|^## 3\. design\.md Sections" ddl-protocol/SKILL.md
# 期待値: 3

# V27 コマンド: コマンドファイルが実行環境のツール名を書かない（P9）
grep -l -E "TeamCreate|TaskCreate|TaskList|TeamDelete|SendMessage|NotebookEdit|apply_patch|team-lead" draft/SKILL.md realize/SKILL.md reflect/SKILL.md resonate/SKILL.md refactoring/SKILL.md docs/SKILL.md commit/SKILL.md validate/SKILL.md | wc -l
# 期待値: 0

# V28 コマンド, protocol: 全コマンドの Phase 0 の冒頭（プロジェクトの写しに従う規則、1行目、2行目）が protocol §4 のテンプレートと同じ文である（P1 層2）
grep -l '^A command run from a user-level install' draft/SKILL.md realize/SKILL.md reflect/SKILL.md resonate/SKILL.md refactoring/SKILL.md docs/SKILL.md commit/SKILL.md validate/SKILL.md | wc -l
grep -h '^A command run from a user-level install' draft/SKILL.md realize/SKILL.md reflect/SKILL.md resonate/SKILL.md refactoring/SKILL.md docs/SKILL.md commit/SKILL.md validate/SKILL.md ddl-protocol/SKILL.md | sort -u | wc -l
grep -l '^1\. Read the DDL protocol' draft/SKILL.md realize/SKILL.md reflect/SKILL.md resonate/SKILL.md refactoring/SKILL.md docs/SKILL.md commit/SKILL.md validate/SKILL.md | wc -l
grep -h '^1\. Read the DDL protocol' draft/SKILL.md realize/SKILL.md reflect/SKILL.md resonate/SKILL.md refactoring/SKILL.md docs/SKILL.md commit/SKILL.md validate/SKILL.md ddl-protocol/SKILL.md | sort -u | wc -l
grep -l '^2\. Read project-local runtime guidance' draft/SKILL.md realize/SKILL.md reflect/SKILL.md resonate/SKILL.md refactoring/SKILL.md docs/SKILL.md commit/SKILL.md validate/SKILL.md | wc -l
grep -h '^2\. Read project-local runtime guidance' draft/SKILL.md realize/SKILL.md reflect/SKILL.md resonate/SKILL.md refactoring/SKILL.md docs/SKILL.md commit/SKILL.md validate/SKILL.md ddl-protocol/SKILL.md | sort -u | wc -l
# 期待値: 8、1、8、1、8、1

# V29 protocol: protocol §3 が4つの節を定義する（P7・P8・P10）
grep -c -E '^\| `## (Experience|Binding Decisions|Direction|Acceptance Gates)`' ddl-protocol/SKILL.md
# 期待値: 4

# V37 コマンド: +++STOP: always のあとの phase が Pre-condition を持つ（protocol §1 の +++STOP 行）
grep -l "Pre-condition" draft/SKILL.md realize/SKILL.md reflect/SKILL.md resonate/SKILL.md refactoring/SKILL.md docs/SKILL.md commit/SKILL.md | wc -l
# 期待値: 7（validate は STOP のあとに phase を持たない）

cd ../..

# V7 codex: 全 Codex コマンドスキルが +++STOP: always を持つ
grep -l "+++STOP: always" codex/.agents/skills/{draft,realize,reflect,resonate,refactoring,docs,commit,validate}/SKILL.md | wc -l
# 期待値: 8

# V8 codex: 全 Codex コマンドスキルが +++DETECT ブロックを持つ
grep -l "+++DETECT:" codex/.agents/skills/{draft,realize,reflect,resonate,refactoring,docs,commit,validate}/SKILL.md | wc -l
# 期待値: 8

# V9 codex: 全 Codex コマンドスキルと AGENTS.md の雛形が +++NEVER を持つ
grep -l "+++NEVER:" codex/.agents/skills/{draft,realize,reflect,resonate,refactoring,docs,commit,validate}/SKILL.md | wc -l
grep -c "+++NEVER:" codex/AGENTS.md
# 期待値: 8 と 6（Claude の4行に、Codex の +++DDL_PHASE と +++DDL_REPORT の2行を足したもの）

# V10 codex: 全 Codex コマンドスキルの +++SWARM ブロックが team: フィールドを持つ
grep -A4 '+++SWARM' codex/.agents/skills/{draft,realize,reflect,resonate,refactoring,docs,validate}/SKILL.md | grep -c 'team:'
# 期待値: 12

# V11 claude-code, codex: 二つの指示ファイルの雛形が同じ節を同じ順に持つ（P3 双子）
diff <(grep '^## ' claude-code/CLAUDE.md) <(grep '^## ' codex/AGENTS.md | sed 's/^## Skills$/## Commands/') > /dev/null && echo "SAME" || echo "DIFF"
# 期待値: SAME

# V22 codex: Codex の設定ファイルが存在する
test -f codex/.codex/config.toml && echo "EXISTS" || echo "MISSING"
# 期待値: EXISTS

# V23 codex: Codex のエージェント定義が存在する
test -f codex/.codex/agents/explorer.toml && test -f codex/.codex/agents/worker.toml && echo "EXISTS" || echo "MISSING"
# 期待値: EXISTS

# V30 tools, claude-code, codex: 生成物が正本と P3 の規則どおりに一致する
python3 tools/sync_mirrors.py . --check 2>&1 >/dev/null; echo "exit $?"
# 期待値: 20 generated, 0 differ と exit 0（Codex の SKILL.md 9本と openai.yaml 9本、門の写し2本）

# V32 claude-code, codex, repo-config: 指示ファイルの雛形とこの repo の指示ファイルの Commands / Skills 表が 8 コマンドをすべて載せる
grep -c -E '^\| `/(draft|realize|reflect|validate|resonate|commit|docs|refactoring)` \|' claude-code/CLAUDE.md .claude/CLAUDE.md
grep -c -E '^\| `\$(draft|realize|reflect|validate|resonate|commit|docs|refactoring)` \|' codex/AGENTS.md
# 期待値: 各8

# V33 protocol, claude-code, codex, repo-config: SWARM の義務の言い回しが protocol と指示ファイルにある（P1）
grep -c "mandatory when condition is true" claude-code/CLAUDE.md codex/AGENTS.md .claude/CLAUDE.md
grep -c "running the assignments inline instead is not allowed" claude-code/skills/ddl-protocol/SKILL.md
# 期待値: 各1

# V34 codex: Codex の draft・realize・reflect が Binding Decisions を扱う
grep -l "Binding Decisions" codex/.agents/skills/{draft,realize,reflect}/SKILL.md | wc -l
# 期待値: 3

# V35 public-docs: 哲学ドキュメント en/ja の4ファイルが Binding Decisions を扱い、2組とも見出し構造が一致する（/resonate）
grep -l "Binding Decisions" docs/en/design_philosophy.md docs/ja/design_philosophy.md docs/en/design_philosophy_extended.md docs/ja/design_philosophy_extended.md | wc -l
for f in design_philosophy design_philosophy_extended; do diff <(grep '^#' docs/en/$f.md | sed -E 's/^(#+).*/\1/') <(grep '^#' docs/ja/$f.md | sed -E 's/^(#+).*/\1/') > /dev/null && echo "SAME" || echo "DIFF $f"; done
# 期待値: 4、SAME、SAME

# V36 protocol, codex: Codex の protocol スキルが Claude Code のものと同文である（P1、P3）
diff <(sed '1,/^---$/d' claude-code/skills/ddl-protocol/SKILL.md) <(sed '1,/^---$/d' codex/.agents/skills/ddl-protocol/SKILL.md) > /dev/null && echo "SAME" || echo "DIFF"
# 期待値: SAME

# V39 codex: Codex の設定が現行のキーと独立したエージェント定義を使う（P3）
grep -c "max_concurrent_threads_per_session" codex/.codex/config.toml
grep -l '^name = ' codex/.codex/agents/explorer.toml codex/.codex/agents/worker.toml | wc -l
# 期待値: 1 と 2

# V40 claude-code, codex, public-docs: README と哲学ドキュメントが Phases を protocol §1 の役割の順で書く
grep -rl "INIT → SURVEY/READ → WORK → REPORT (+++STOP) → EXECUTE → VERIFY" claude-code/README.md codex/README.md docs/ | wc -l
grep -rn "EXECUTE → VALIDATE" README.md claude-code/README.md codex/README.md docs/ | wc -l
# 期待値: 4 と 0

# V41 protocol, realize, reflect: 通過の印を protocol §3 が定義し、realize が書き、reflect が読む（P10）
grep -c '^\*\*Passed marks\.\*\*' claude-code/skills/ddl-protocol/SKILL.md
grep -l "Mark each gate that passes" claude-code/skills/realize/SKILL.md | wc -l
grep -l "marked passed" claude-code/skills/reflect/SKILL.md | wc -l
# 期待値: 各1

# V42 claude-code, codex, public-docs, tools, install, repo-config: 手帳の名前がどこでも design.md である（P3 命名規則）
grep -rl "DESIGN\.md" README.md docs claude-code codex tools bin .claude/CLAUDE.md | wc -l
# 期待値: 0

# V43 protocol: protocol §1.5 が要約の規則（Summary rule）を持つ（P12）
grep -c "conversation summary" claude-code/skills/ddl-protocol/SKILL.md
grep -c '^\*\*Summary rule\.\*\*' claude-code/skills/ddl-protocol/SKILL.md
# 期待値: 1以上 と 1

# V44 public-docs: 哲学ドキュメント en/ja が Context Engineering の小節を持ち、古い「LLM には長期記憶がない」の言い回しを含まない（P12）
grep -c "^#### Context Engineering" docs/en/design_philosophy_extended.md; grep -c "^#### コンテキストエンジニアリング" docs/ja/design_philosophy_extended.md
grep -c "LLMs lack long-term memory" docs/en/design_philosophy_extended.md; grep -c "LLM には長期記憶がありません" docs/ja/design_philosophy_extended.md
# 期待値: 各1 と 各0

# V45 protocol: protocol §2.5 が四つの命令の実装の行、protocol の探索の行、プロジェクトの写しの行と、Claude Code のアダプタ名を持つ（P13）
grep -c -E '^\| (\+\+\+STOP enforcement|design\.md loading|Worker roles|Outward actions and attribution|Protocol lookup|Project copy and overlay)' claude-code/skills/ddl-protocol/SKILL.md
grep -c '`.claude/settings.json`, `.claude/agents/`, and `.claude/hooks/`' claude-code/skills/ddl-protocol/SKILL.md
# 期待値: 6 と 1以上

# V46 claude-code, codex: 両ランタイムのアダプタ（門の配線と写し、エージェント定義、規則）が正本に揃う（P3、P13）
for f in claude-code/settings.json claude-code/agents/explorer.md claude-code/agents/worker.md claude-code/hooks/ddl_gate.py codex/.codex/config.toml codex/.codex/hooks.json codex/.codex/hooks/ddl_gate.py codex/.codex/agents/explorer.toml codex/.codex/agents/worker.toml codex/.codex/rules/ddl.rules; do test -f "$f" || echo "MISSING $f"; done; echo "checked"
# 期待値: checked だけ（MISSING の行なし）

# V47 public-docs: 哲学ドキュメント en/ja が「指示と仕組み」の小節を持つ（P13）
grep -c "^#### Instructions and Mechanisms" docs/en/design_philosophy_extended.md; grep -c "^#### 指示と仕組み" docs/ja/design_philosophy_extended.md
# 期待値: 各1

# V48 tools: 門の単体テストが通る（P13）
python3 tools/test_ddl_gate.py 2>&1 | tail -1
# 期待値: OK

# V49 install: 導入スクリプトが文法検査を通り、一時 HOME で install → doctor → uninstall を往復する（P13）
bash -n bin/install.sh bin/uninstall.sh bin/doctor.sh && echo "SYNTAX_OK"
H=$(mktemp -d); mkdir -p "$H/.claude" "$H/.codex"; HOME="$H" bash bin/install.sh > /dev/null && HOME="$H" bash bin/doctor.sh | tail -1; HOME="$H" bash bin/uninstall.sh > /dev/null; find "$H" -type l | wc -l; rm -rf "$H"
# 期待値: SYNTAX_OK、「… 0 not OK」、0

# V50 public-docs: 用語集の「使わない訳」が日本語の哲学ドキュメントに残らず、主要な訳語が現れる（Binding Decisions の用語集。T4 で通す）
python3 - <<'PY'
import pathlib, re
rows = [l for l in pathlib.Path("docs/ja/GLOSSARY.md").read_text().splitlines() if l.startswith("| ") and not l.startswith("| 英語")]
forbidden = []
for r in rows:
    cells = [c.strip() for c in r.strip().strip("|").split("|")]
    if len(cells) >= 3:
        forbidden += [x.strip() for x in cells[2].split("、") if x.strip()]
docs = {p: pathlib.Path(p).read_text() for p in ("docs/ja/design_philosophy.md", "docs/ja/design_philosophy_extended.md")}
def found(tok, text):
    return re.search(r"(?<![専部名])門", text) is not None if tok == "門" else tok in text
left = sorted({tok for tok in forbidden for text in docs.values() if found(tok, text)})
missing = [tok for tok in ("コンテキストウィンドウ", "コンパクション", "帰属表記", "ゲート") if not any(tok in text for text in docs.values())]
print("forbidden-left:", left); print("required-missing:", missing)
PY
# 期待値: forbidden-left: [] と required-missing: []

# V51 claude-code, codex, public-docs, tools, install, repo-config: 旧配置の名前（examples/、commands の写し、Codex Runtime Contract、dogfood）が残っていない
grep -rn -E "examples/|\.codex/commands|\.claude/commands|DDL-PROTOCOL-SKILL|Codex Runtime Contract|dogfood" README.md docs claude-code codex tools bin .claude/CLAUDE.md | wc -l
# 期待値: 0
```
