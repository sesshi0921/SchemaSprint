# Editor and Community Experience Requirements

## 1. Workspace

### 1.1 Layout and panels
- **Agreed**: The workspace provides a foldable, resizable problem panel, official-answer panel, and community-answer panel.
- **Agreed**: The workspace contains an ER editor.
- **Agreed**: The feedback button appears only in the workspace and applies to the selected submission.
- **Agreed**: Official answer access is available before submission without penalty.

### 1.2 Editor capabilities
- **Agreed**: The editor supports GUI canvas editing, a distinct table-definition form, Mermaid, SQL DDL, and DBML.
- **Agreed**: Valid syntax synchronizes those representations through a canonical internal schema.
- **Agreed**: Invalid syntax leaves the last valid diagram in place and shows real-time static errors.
- **Agreed**: Exports include JSON, DDL, Mermaid, and DBML.
- **Agreed**: Lossy format round trips show a limitation warning and never silently discard canonical schema features.
- **Agreed**: The schema model supports columns, data types, and function/expression metadata, plus PostgreSQL features including indexes, ENUM, CHECK, DEFAULT, composite PK/FK, delete rules, views, triggers, RLS, and partitions.
- **Agreed**: Mermaid and DBML do not represent every SQL/PostgreSQL feature; canonical schema metadata remains authoritative and lossy conversion warns.
- **Agreed**: Crow’s Foot rendering includes optionality and multiplicity, including physical join tables.
- **Agreed**: Layout uses layered ELK/elkjs only when the user explicitly selects Arrange; Arrange may replace the current layout, which is then preserved until the next Arrange or manual edit, and undo restores the prior layout. ELK layout is a heuristic and does not promise an exact design optimum.

### 1.3 Interaction quality
- **Agreed**: The editor supports keyboard use and touch-mobile recovery behavior.
- **Default**: Undo/redo and search/navigation details are proposed and require validation before being fixed.
- **Agreed**: A first-use tutorial covers table, column, relation, Arrange, and submit actions; it is skippable and replayable.
- **Default**: Advanced-control disclosure details are proposed and must be validated before being fixed.
- **Agreed**: The experience must maintain baseline semantic accessibility; no separate colorblind or screen-reader project is requested.

## 2. Submissions and Feedback

- **Agreed**: Users can make unlimited submissions, subject to separate abuse controls.
- **Agreed**: Selected-submission feedback is English LLM output followed by NMT translation, with identifiers preserved.
- **Agreed**: Feedback output is versioned/cached and reread without cost.
- **Agreed**: Results surface atomic fulfilled/missing requirements, impact, and confidence without claiming guaranteed correctness.

## 3. Community Answers

### 3.1 Publishing
- **Agreed**: A user may voluntarily publish a selected exact-100-point submission to the member community.
- **Agreed**: The official answer appears before community posts in the answer panel.
- **Agreed**: Posts include detailed explanation and client-rendered ER structural data.
- **Agreed**: Posts are visible to members.
- **Agreed**: There are no comments.
- **Agreed**: Users cannot edit or delete posts.
- **Agreed**: Administrative, legal, and account-deletion exceptions may remove or alter visibility as required.
- **Agreed**: Community posts retain old-version tags after problem corrections.

### 3.2 Community safety and translation
- **Agreed**: Jev premoderates spam, abuse, PII, and suspicious content; held content is not published until handling resolves it.
- **Agreed**: External HTTPS links are validated and rendered with `noopener`; the system does not fetch those links.
- **Agreed**: Post content uses NMT translation with cached original-language toggle.

## 4. Validation Gates

- **Agreed**: Editor synchronization accepts only valid syntax into the canonical schema; invalid edits must not overwrite the last valid rendered state.
- **Agreed**: Export logic must issue a visible warning before a target format would be lossy.
- **Agreed**: Arrange must be user-initiated; it may replace the current layout when explicitly requested, preserves that result until the next Arrange or manual edit, and undo restores the prior layout.
- **Agreed**: Community publishing requires selected-submission ownership, exact full score, member visibility eligibility, and successful premoderation.
- **Agreed**: Any rendered external link must satisfy HTTPS validation and safe link attributes.

## 5. Acceptance Criteria

- **AC-EXP-001**: A user can create an equivalent valid schema using GUI, Mermaid, SQL DDL, or DBML and see synchronized representations from the canonical schema.
- **AC-EXP-002**: Introducing invalid textual syntax shows a real-time static error while retaining the last valid diagram.
- **AC-EXP-003**: Exporting a schema to JSON, DDL, Mermaid, or DBML preserves canonical features where supported and warns before any lossy conversion.
- **AC-EXP-004**: A schema using columns, types, functions/expressions, and the listed PostgreSQL constructs retains supported metadata in canonical form; Mermaid/DBML loss is warned, and unsupported static proof of expression/function semantics is not represented as proven.
- **AC-EXP-005**: Arrange runs layered ELK only after a button action, may replace the current layout when explicitly requested, preserves the arranged result until the next Arrange or manual edit, supports undo to restore the prior layout, and makes no claim of an optimal layout.
- **AC-EXP-006**: Workspace panels fold/resize, editor undo/redo and keyboard operations work, and touch users can recover editing state.
- **AC-EXP-007**: Only a selected exact-100-point submission can be voluntarily published; a 99.96 score displayed as 100.0 is rejected.
- **AC-EXP-008**: Community answer panels put the official answer first; member posts show explanation and client-rendered ER structure, have no comments, and cannot be user-edited/deleted.
- **AC-EXP-009**: Content flagged as spam, abuse, PII, or suspicious remains held; external links are HTTPS-validated, use `noopener`, and are never fetched.

---

# 日本語版

# エディターとコミュニティ体験の要件

## 1. ワークスペース

### 1.1 レイアウトとパネル
- **合意済み**: ワークスペースには、折りたたみ・サイズ変更可能な課題パネル、公式解答パネル、コミュニティ解答パネルを提供する。
- **合意済み**: ワークスペースには ER エディターを含める。
- **合意済み**: フィードバックボタンはワークスペース内にのみ表示し、選択された提出に適用する。
- **合意済み**: 公式解答には提出前にペナルティなしでアクセスできる。

### 1.2 エディターの機能
- **合意済み**: エディターは GUI キャンバス編集、独立したテーブル定義フォーム、Mermaid、SQL DDL、DBML をサポートする。
- **合意済み**: 有効な構文は正規の内部スキーマを通じて各表現を同期する。
- **合意済み**: 無効な構文では最後の有効な図を維持し、リアルタイムの静的エラーを表示する。
- **合意済み**: エクスポートには JSON、DDL、Mermaid、DBML を含める。
- **合意済み**: 情報を失う形式のラウンドトリップでは制限警告を表示し、正規スキーマの機能を黙って破棄しない。
- **合意済み**: スキーマモデルはカラム、データ型、関数／式メタデータに加え、インデックス、ENUM、CHECK、DEFAULT、複合 PK/FK、削除ルール、ビュー、トリガー、RLS、パーティションを含む PostgreSQL 機能をサポートする。
- **合意済み**: Mermaid と DBML はすべての SQL/PostgreSQL 機能を表現するわけではない。正規スキーマメタデータを権威とし、情報を失う変換では警告する。
- **合意済み**: Crow’s Foot の描画には、物理的な結合テーブルを含む任意性と多重度を含める。
- **合意済み**: レイアウトはユーザーが明示的に Arrange を選択した場合のみ階層型 ELK/elkjs を使用する。Arrange は現在のレイアウトを置き換えてよく、その後は次の Arrange または手動編集まで保持し、Undo で以前のレイアウトを復元する。ELK レイアウトはヒューリスティックであり、正確な設計最適解を約束しない。

### 1.3 インタラクション品質
- **合意済み**: エディターはキーボード操作とタッチモバイルでの復旧動作をサポートする。
- **デフォルト**: Undo/Redo と検索／ナビゲーションの詳細は提案であり、固定前に検証する。
- **合意済み**: 初回利用チュートリアルは、テーブル、カラム、リレーション、Arrange、提出の操作を扱い、スキップと再実行が可能である。
- **デフォルト**: 高度な操作の開示詳細は提案であり、固定前に検証しなければならない。
- **合意済み**: 体験はベースラインの意味的アクセシビリティを維持しなければならない。色覚多様性やスクリーンリーダーについて別プロジェクトは要求しない。

## 2. 提出とフィードバック

- **合意済み**: ユーザーは、別途の濫用対策に従いつつ、無制限に提出できる。
- **合意済み**: 選択された提出へのフィードバックは英語の LLM 出力に続く NMT 翻訳であり、識別子を保持する。
- **合意済み**: フィードバック出力はバージョン管理・キャッシュされ、無料で再読できる。
- **合意済み**: 結果には原子的な充足／不足要件、影響、信頼度を表示し、正しさを保証するとは主張しない。

## 3. コミュニティ解答

### 3.1 公開
- **合意済み**: ユーザーは選択した正確な 100 点の提出をメンバーコミュニティへ任意で公開できる。
- **合意済み**: 解答パネルでは公式解答をコミュニティ投稿より先に表示する。
- **合意済み**: 投稿には詳細な解説とクライアント描画の ER 構造データを含める。
- **合意済み**: 投稿はメンバーから閲覧できる。
- **合意済み**: コメントは設けない。
- **合意済み**: ユーザーは投稿を編集・削除できない。
- **合意済み**: 管理、法的要件、アカウント削除の例外により、必要に応じて表示を削除または変更できる。
- **合意済み**: 課題訂正後も、コミュニティ投稿は旧バージョンのタグを保持する。

### 3.2 コミュニティの安全性と翻訳
- **合意済み**: Jev はスパム、濫用、PII、疑わしいコンテンツを事前モデレーションし、保留中のコンテンツは処理が解決するまで公開しない。
- **合意済み**: 外部 HTTPS リンクを検証し、`noopener` 付きで描画する。システムはそれらのリンクを取得しない。
- **合意済み**: 投稿コンテンツは NMT 翻訳を使用し、原言語への切り替えをキャッシュする。

## 4. 検証ゲート

- **合意済み**: エディター同期は有効な構文のみを正規スキーマへ受け入れ、無効な編集で最後に有効な描画状態を上書きしない。
- **合意済み**: エクスポート処理は、対象形式が情報損失を伴う前に見える警告を出す。
- **合意済み**: Arrange はユーザーが開始しなければならない。明示的に要求された場合は現在のレイアウトを置き換えてよく、その結果を次の Arrange または手動編集まで保持し、Undo で以前のレイアウトを復元する。
- **合意済み**: コミュニティ公開には、選択された提出の所有権、正確な満点、メンバー閲覧資格、事前モデレーションの成功が必要である。
- **合意済み**: 描画される外部リンクは HTTPS 検証と安全なリンク属性を満たさなければならない。

## 5. 受け入れ基準

- **AC-EXP-001**: ユーザーは GUI、Mermaid、SQL DDL、DBML のいずれかで同等の有効なスキーマを作成し、正規スキーマから同期された表現を確認できる。
- **AC-EXP-002**: 無効なテキスト構文を導入するとリアルタイムの静的エラーを表示し、最後の有効な図を保持する。
- **AC-EXP-003**: スキーマを JSON、DDL、Mermaid、DBML にエクスポートすると、対応する正規機能を保持し、情報損失の前に警告する。
- **AC-EXP-004**: カラム、型、関数／式、列挙された PostgreSQL 構造を使用するスキーマは、対応メタデータを正規形式で保持する。Mermaid/DBML の損失を警告し、関数／式の意味について対応しない静的証明を証明済みとして表現しない。
- **AC-EXP-005**: Arrange はボタン操作の後にのみ階層型 ELK を実行し、明示的に要求された場合は現在のレイアウトを置き換えてよく、次の Arrange または手動編集まで結果を保持し、Undo で以前のレイアウトを復元し、最適レイアウトであると主張しない。
- **AC-EXP-006**: ワークスペースのパネルを折りたたみ・サイズ変更でき、エディターの Undo/Redo とキーボード操作が機能し、タッチユーザーが編集状態を復元できる。
- **AC-EXP-007**: 選択した正確な 100 点の提出だけを任意公開でき、99.96 と表示されたスコアを 100.0 として扱う場合は拒否する。
- **AC-EXP-008**: コミュニティ解答パネルは公式解答を最初に置き、メンバー投稿には解説とクライアント描画の ER 構造を表示し、コメントを設けず、ユーザーによる編集・削除を許可しない。
- **AC-EXP-009**: スパム、濫用、PII、疑わしいものとしてフラグ付けされたコンテンツは保留されたままとし、外部リンクは HTTPS 検証済みで `noopener` を使用し、取得しない。
