# Product Requirements

## 1. Product Definition

### 1.1 Purpose
- **Agreed**: SchemaSprint is a professional, LeetCode-like daily database-design practice product with beginner-friendly onboarding.
- **Agreed**: The product teaches and evaluates database design, not merely SQL syntax.
- **Agreed**: The complete user scope remains in MVP; broad scope must not be cut merely because it is an MVP.

### 1.2 Platforms and delivery
- **Agreed**: MVP is a web Progressive Web App (PWA).
- **Agreed**: The design must preserve a future simultaneous iOS and Android delivery path using Expo React Native.
- **Agreed**: The web client must support mobile touch use without removing professional desktop capability.
- **Agreed**: Light and dark themes are supported; initial theme follows the operating-system preference.

### 1.3 Audience, access, and eligibility
- **Agreed**: Beta access is private and allowlisted.
- **Agreed**: Sign-in uses Google or GitHub and requires verified identity.
- **Agreed**: Users must be at least 16 years old.
- **Agreed**: Display names are independent of Google/GitHub identity and may duplicate.
- **Agreed**: The server maps each application account to a unique internal ULID; linked provider identities for the same account use the same ULID.
- **Default**: Display names may be freely chosen by the user; the default is a neutral generated name and must not copy a Google/GitHub provider handle. Record this behavior as an explicit product decision.

### 1.4 Locales and content language
- **Agreed**: Supported UI locales are English, Japanese, Simplified Chinese, Korean, Spanish, and Brazilian Portuguese.
- **Agreed**: Initial locale uses browser detection and users can override it in Settings.
- **Agreed**: Source problems and generated feedback are English.
- **Agreed**: UI locale assets are bundled. Problem statements, explanations, generated feedback, and community posts are lazily translated by NMT and cached by content version and locale.
- **Agreed**: Translation preserves identifiers.
- **Agreed**: Corrections invalidate affected translation caches.

## 2. Core Practice Loop

### 2.1 Daily problem
- **Agreed**: All users receive one common daily problem at 04:00 JST.
- **Agreed**: Difficulty selection is independently uniform among easy, mid, and hard; this is a random distribution, not a guarantee of exact balance in every short period.
- **Agreed**: Genre and representation format are randomized independently of difficulty; random selection does not guarantee an exactly balanced short-period mix.
- **Agreed**: The guideline duration is 5–30 minutes for every difficulty; difficulty must not be represented as separate time buckets.
- **Agreed**: All historical problems remain playable.
- **Agreed**: Users may view the official answer and explanation before submission without penalty.
- **Default**: Calendar attribution is the problem publication date in JST; global 04:00 daily boundary and actual user activity timestamps remain separate concepts.

### 2.2 Offline behavior
- **Agreed**: Downloaded problems and editing work offline.
- **Agreed**: Every user has local cache support.
- **Agreed**: Offline submissions enter a durable queue and submit when connectivity returns.
- **Agreed**: Queued submissions preserve the selected problem and assessment-version reference needed for immutable grading.

### 2.3 Submission and result rules
- **Agreed**: Submissions are unlimited; abuse controls are separate from the product allowance.
- **Agreed**: Every submission is an immutable snapshot retaining problem, rubric, version, score, and verdict context.
- **Agreed**: Corrections never retroactively alter prior submission results.
- **Agreed**: A displayed score has one decimal place.
- **Agreed**: A community-post-eligible result requires the exact full score under the stored rubric; rounding 99.96 to 100.0 does not qualify.

## 3. Information Architecture

### 3.1 Home
- **Agreed**: The top screen presents today’s problem, announcements, and login/start entry points.

### 3.2 Problem library
- **Agreed**: The problem list is searchable by title and tags.
- **Agreed**: Filters include date, difficulty, genre, format, passed, not passed, and unsubmitted.
- **Agreed**: List entries expose title and tags.

### 3.3 Dashboard
- **Agreed**: Dashboard includes a calendar and unique passed-problem count.
- **Agreed**: Dashboard totals include weekday and difficulty views.
- **Agreed**: Dashboard does not present an accuracy metric.

### 3.4 Settings and announcements
- **Agreed**: Settings include language, theme, account deletion, export, and membership.
- **Agreed**: An announcements archive exists and unread announcements show a badge.
- **Agreed**: An admin area exists for authorized administration workflows.

## 4. Membership and Feedback Economy

### 4.1 MVP membership boundary
- **Agreed**: Future paid monthly and annual memberships are in scope as product design.
- **Agreed**: Actual billing is disabled in MVP; use sandbox-only billing behavior.
- **Agreed**: Administrators can grant or revoke premium access with auditability.
- **Agreed**: Premium benefits include database drafts and ad-free feedback.
- **Agreed**: Ad-free feedback does not automatically imply unlimited feedback-generation cost.

### 4.2 Generated feedback entitlement
- **Agreed**: The feedback entry point exists only in the workspace for a selected submission.
- **Default**: The first feedback request per user and problem is free.
- **Agreed**: Subsequent feedback requests require a voluntary rewarded advertisement unless an applicable premium entitlement removes ads.
- **Agreed**: Existing generated feedback can be reread free of charge.
- **Agreed**: Feedback is generated in English by an LLM, then NMT-translated with identifiers preserved.

## 5. Administration, Corrections, and Reporting

### 5.1 Reports
- **Agreed**: Users can report a problem, official answer, grading, translation, or other issue.
- **Agreed**: A reported issue is evaluated by Jev for validity; an LLM may create a correction draft. For reported problems, a report alone does not force nonpublication; pending review, the current version remains available.
- **Agreed**: Administrator approval is required for both a correction and its announcement.

### 5.2 Versioning consequences
- **Agreed**: Old attempts and community posts are retained and visibly tagged with their old version when applicable.
- **Agreed**: Corrected content publishes as a new version rather than overwriting historical assessment evidence.

## 6. Validation Gates

- **Agreed**: Private-beta allowlist, verified identity, and age gate must succeed before normal product access.
- **Agreed**: A problem is not publishable until its generation and quality validation gates pass.
- **Agreed**: A submission result must reference a frozen problem/rubric/version snapshot before it is stored or surfaced.
- **Agreed**: Translation cache output must be version-aware before display.

## 7. Validation and success proposal

- **Proposal**: Before launch, the owner validates that an allowlisted learner can open, edit, submit, view results, and optionally request feedback without data loss. This is an acceptance-oriented product check, not a business target.

## 8. Acceptance Criteria

- **AC-PROD-001**: An allowlisted, verified, age-eligible user can sign in through Google or GitHub and receives one internal ULID; duplicate display names do not block access.
- **AC-PROD-002**: At 04:00 JST, the same published daily problem is available to every eligible user; prior problems remain accessible.
- **AC-PROD-003**: A downloaded problem can be edited offline and a queued submission is sent after reconnection without losing its version reference.
- **AC-PROD-004**: The official answer can be opened before submission and does not reduce attempts, score, or posting eligibility.
- **AC-PROD-005**: Each stored submission retains immutable problem, rubric, version, score, and verdict data; a subsequent correction leaves it unchanged.
- **AC-PROD-006**: Search and all specified library filters work together; dashboard shows calendar and unique passed count without accuracy.
- **AC-PROD-007**: UI locale can be browser-selected then manually changed among all six supported locales, while identifiers remain unchanged in translated content.
- **AC-PROD-008**: Feedback is requestable only for a selected workspace submission; the first user/problem request is free, rereads are free, and later requests enforce the configured ad/premium entitlement.
- **AC-PROD-009**: No correction or correction announcement becomes public without separate administrator approvals; affected historical records remain tagged and preserved.

---

# 日本語版

# 製品要件

## 1. 製品定義

### 1.1 目的
- **合意済み**: SchemaSprint は、初心者に配慮したオンボーディングを備える、プロフェッショナル向けの LeetCode 型の日次データベース設計練習プロダクトである。
- **合意済み**: プロダクトは単なる SQL 構文ではなく、データベース設計を教え、評価する。
- **合意済み**: 完全なユーザースコープを MVP に残す。MVP であることだけを理由に広いスコープを削ってはならない。

### 1.2 プラットフォームと提供形態
- **合意済み**: MVP は Web Progressive Web App (PWA) である。
- **合意済み**: 設計は、Expo React Native を使用した将来の iOS と Android の同時提供経路を維持しなければならない。
- **合意済み**: Web クライアントはプロフェッショナルなデスクトップ機能を損なわずに、モバイルのタッチ操作をサポートしなければならない。
- **合意済み**: ライトテーマとダークテーマをサポートし、初期テーマは OS の設定に従う。

### 1.3 対象者、アクセス、利用資格
- **合意済み**: ベータアクセスは非公開で、許可リスト方式である。
- **合意済み**: サインインには Google または GitHub を使用し、本人確認済みの身元を必要とする。
- **合意済み**: ユーザーは 16 歳以上でなければならない。
- **合意済み**: 表示名は Google/GitHub の身元情報から独立し、重複してよい。
- **合意済み**: サーバーは各アプリケーションアカウントを一意の内部 ULID に対応付け、同一アカウントにリンクされたプロバイダー ID には同じ ULID を使用する。
- **デフォルト**: 表示名はユーザーが自由に選択できる。デフォルトは中立的に生成した名前とし、Google/GitHub のプロバイダーのハンドルをコピーしてはならない。この動作を明示的な製品決定として記録する。

### 1.4 ロケールと言語コンテンツ
- **合意済み**: 対応 UI ロケールは英語、日本語、簡体字中国語、韓国語、スペイン語、ブラジル・ポルトガル語である。
- **合意済み**: 初期ロケールはブラウザー検出を使用し、ユーザーは Settings で上書きできる。
- **合意済み**: 原文の課題と生成されるフィードバックは英語である。
- **合意済み**: UI ロケールアセットはバンドルする。課題文、解説、生成フィードバック、コミュニティ投稿は NMT により遅延翻訳し、コンテンツバージョンとロケール単位でキャッシュする。
- **合意済み**: 翻訳では識別子を保持する。
- **合意済み**: 訂正により、影響を受ける翻訳キャッシュを無効化する。

## 2. 中核の練習ループ

### 2.1 日次課題
- **合意済み**: すべてのユーザーに 04:00 JST に共通の日次課題を 1 問提供する。
- **合意済み**: 難易度の選択は easy、mid、hard の間で独立に一様である。これはランダム分布であり、短期間ごとの正確な均衡を保証するものではない。
- **合意済み**: ジャンルと表現形式は難易度から独立してランダム化する。ランダム選択は短期間の組み合わせが完全に均衡することを保証しない。
- **合意済み**: 指針となる所要時間はすべての難易度で 5–30 分とし、難易度を別個の時間帯として表現してはならない。
- **合意済み**: 過去のすべての課題をプレイできる。
- **合意済み**: ユーザーは提出前にペナルティなしで公式解答と解説を閲覧できる。
- **デフォルト**: カレンダー上の帰属は JST の課題公開日とする。世界共通の 04:00 の日次境界と、実際のユーザー活動のタイムスタンプは別概念として扱う。

### 2.2 オフライン動作
- **合意済み**: ダウンロードした課題の閲覧と編集はオフラインで行える。
- **合意済み**: すべてのユーザーにローカルキャッシュを提供する。
- **合意済み**: オフライン提出は永続キューに入り、接続が戻ると送信される。
- **合意済み**: キューに入った提出は、不変の採点に必要な選択課題と評価バージョン参照を保持する。

### 2.3 提出と結果のルール
- **合意済み**: 提出回数は無制限とする。濫用対策はプロダクトの許容量とは別である。
- **合意済み**: 各提出は、課題、ルーブリック、バージョン、スコア、判定コンテキストを保持する不変スナップショットである。
- **合意済み**: 訂正によって過去の提出結果を遡及変更しない。
- **合意済み**: 表示スコアは小数第 1 位までとする。
- **合意済み**: コミュニティ投稿の対象となる結果には、保存されたルーブリックに基づく正確な満点が必要である。99.96 を 100.0 に丸めても対象にはならない。

## 3. 情報アーキテクチャ

### 3.1 ホーム
- **合意済み**: 最上位画面には今日の課題、告知、ログイン／開始の入口を表示する。

### 3.2 課題ライブラリ
- **合意済み**: 課題一覧をタイトルとタグで検索できる。
- **合意済み**: フィルターには日付、難易度、ジャンル、形式、合格済み、不合格、未提出を含める。
- **合意済み**: 一覧項目にはタイトルとタグを表示する。

### 3.3 ダッシュボード
- **合意済み**: ダッシュボードにはカレンダーと合格した一意の課題数を含める。
- **合意済み**: ダッシュボードの集計には曜日別と難易度別の表示を含める。
- **合意済み**: ダッシュボードには正答率指標を表示しない。

### 3.4 設定と告知
- **合意済み**: Settings には言語、テーマ、アカウント削除、エクスポート、メンバーシップを含める。
- **合意済み**: 告知アーカイブを設け、未読告知にはバッジを表示する。
- **合意済み**: 権限を持つ管理ワークフローのための管理者エリアを設ける。

## 4. メンバーシップとフィードバック経済

### 4.1 MVP のメンバーシップ境界
- **合意済み**: 将来の有料月額・年額メンバーシップを製品設計の対象に含める。
- **合意済み**: MVP では実際の課金を無効にし、サンドボックス限定の課金動作を使用する。
- **合意済み**: 管理者は監査可能な形でプレミアムアクセスを付与・取り消しできる。
- **合意済み**: プレミアム特典にはデータベース下書きと広告なしフィードバックを含める。
- **合意済み**: 広告なしフィードバックは、フィードバック生成コストの無制限化を自動的に意味しない。

### 4.2 生成フィードバックの利用権
- **合意済み**: フィードバック入口は、選択した提出に対するワークスペース内にのみ存在する。
- **デフォルト**: ユーザーおよび課題ごとの最初のフィードバック要求は無料とする。
- **合意済み**: プレミアム特典によって広告が除外されない限り、2 回目以降のフィードバック要求には任意視聴のリワード広告を必要とする。
- **合意済み**: 既存の生成済みフィードバックは無料で再読できる。
- **合意済み**: フィードバックは LLM により英語で生成し、その後 NMT で翻訳する。識別子は保持する。

## 5. 管理、訂正、報告

### 5.1 報告
- **合意済み**: ユーザーは課題、公式解答、採点、翻訳、その他の問題を報告できる。
- **合意済み**: 報告された問題は Jev が妥当性を評価し、LLM が訂正案を作成してよい。報告された課題については、報告だけで非公開を強制せず、審査中は現行バージョンを利用可能なままにする。
- **合意済み**: 訂正とその告知の双方に管理者承認を必要とする。

### 5.2 バージョニングの結果
- **合意済み**: 過去の試行とコミュニティ投稿は保持し、該当する場合は旧バージョンであることを目に見える形でタグ付けする。
- **合意済み**: 訂正済みコンテンツは過去の評価証拠を上書きせず、新しいバージョンとして公開する。

## 6. 検証ゲート

- **合意済み**: 通常のプロダクトアクセスの前に、非公開ベータの許可リスト、本人確認済みの身元、年齢ゲートを通過しなければならない。
- **合意済み**: 課題は生成と品質の検証ゲートを通過するまで公開可能にしてはならない。
- **合意済み**: 提出結果は保存または表示される前に、凍結された課題／ルーブリック／バージョンのスナップショットを参照しなければならない。
- **合意済み**: 翻訳キャッシュの出力は、表示前にバージョンを認識できなければならない。

## 7. 検証と成功に関する提案

- **提案**: 公開前に、許可リスト登録済みの学習者がデータ損失なく課題を開き、編集し、提出し、結果を確認し、任意でフィードバックを要求できることをオーナーが検証する。これは受け入れ指向の製品チェックであり、事業目標ではない。

## 8. 受け入れ基準

- **AC-PROD-001**: 許可リスト登録済みで、本人確認済みかつ年齢条件を満たすユーザーは Google または GitHub でサインインでき、1 つの内部 ULID を受け取る。重複する表示名はアクセスを妨げない。
- **AC-PROD-002**: 04:00 JST に、同じ公開済みの日次課題をすべての対象ユーザーが利用でき、過去の課題にも引き続きアクセスできる。
- **AC-PROD-003**: ダウンロードした課題をオフラインで編集でき、再接続後にキュー済み提出がバージョン参照を失わず送信される。
- **AC-PROD-004**: 公式解答を提出前に開け、試行回数、スコア、投稿資格を減少させない。
- **AC-PROD-005**: 保存された各提出は不変の課題、ルーブリック、バージョン、スコア、判定データを保持し、その後の訂正によって変更されない。
- **AC-PROD-006**: 検索と指定されたすべてのライブラリフィルターを組み合わせて機能させ、ダッシュボードにはカレンダーと一意の合格数を表示し、正答率は表示しない。
- **AC-PROD-007**: UI ロケールはブラウザーで選択した後、6 つの対応ロケール間で手動変更でき、翻訳コンテンツ内の識別子は変わらない。
- **AC-PROD-008**: フィードバックは選択されたワークスペース提出に対してのみ要求でき、ユーザー／課題ごとの初回要求と再読は無料で、後続要求には設定された広告／プレミアム利用権を適用する。
- **AC-PROD-009**: 訂正または訂正告知は、管理者による個別の承認なしに公開されず、影響を受ける過去の記録はタグ付けされ保持される。
