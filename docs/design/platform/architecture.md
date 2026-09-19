# SchemaSprint MVP Architecture

**Status legend:** **Confirmed** = user decision; **Proposed** = implementation default needing approval; **Gate** = validate vendor/legal/technical fact before release. This is a Web PWA MVP; future Expo React Native iOS/Android clients use the same contracts, not Web cookies. No Next.js.

## A1. System boundary and deployment

**Confirmed:** Candidate topology is Cloudflare Pages (static PWA) -> Cloudflare Workers/BFF APIs -> Supabase Auth + Postgres. Workers call Groq-hosted LLM for English feedback/problem prose, Jev TypeSafe external typed decision model for semantic decisions, and Google Cloud Translation NMT (not an LLM) for translations. Ollama is optional local development only; there is no always-on AWS GPU. Candidate vendors, capability limits, data terms, regions and current pricing are **release gates**, not claims.

Workers are the sole public application API and policy enforcement point. Pages contains no secret and talks only to same-origin BFF endpoints. Supabase ordinary queries propagate the user JWT into RLS; privileged operations use a separate service credential only on explicitly authorized Worker paths. `service_role` must never be exposed or used as an authorization bypass. Inference/translation providers receive only the minimum content needed and never identity, session/JWT, email, or unnecessary history; auth/payment vendors may receive documented necessary identity data. LLM/Jev receive no tools, no authority, and untrusted content cannot change policy.

**Acceptance:** `ARC-01` Web PWA works with no Next.js; `ARC-02` native clients can adopt versioned APIs with native token/storage handling; `ARC-03` no required always-on GPU/AWS compute.

## A2. Identity, tenancy, and RBAC

Supabase Auth UUID is mapped one-to-one to an internal ULID `user_id`; all domain FKs use ULID. Display names are non-unique. Provider identities are separate records; account linking needs explicit verified ownership proof. Google/GitHub allowlist access is only for approved, verified provider identities. A manually bootstrapped, verified-email initial administrator gets a persistent subject binding; email alone is never authorization. GitHub private/no-email identities must be handled without unsafe implicit linking.

Roles: learner, moderator, admin, owner; expanded moderator/admin/owner privileges are **Proposed** and the initial deployment has only one owner. Server-side policy grants each action; clients cannot set roles, grades, premium, publication, moderation state, or approval. Admin/owner operations require MFA and auditable authorization. The initial 16+ gate is self-declaration, **not** proof of universal legal compliance.

**Acceptance:** `ARC-04` owner/action checks and least-privilege RLS cover every domain action; `ARC-05` a duplicate name or changed email cannot merge/authorize accounts; `ARC-06` admin bootstrap is manual and subject-bound.

## A3. Relational domain (conceptual)

Core immutable/versioned entities:

- `users`, `provider_identities`, `age_declarations`, `roles`, `entitlements`, `session/revocation`;
- `problems`, `problem_versions`, `requirements`, `rubrics`, `solutions`, `publication_calendar`, `publication_events`;
- `workspaces`, `schema_snapshots`, `submissions`, `submission_results`, `feedback_versions`, `translation_cache`;
- `posts`, `reports`, `post_moderation`, `moderation_decisions`; `notices`, `notice_versions`, `notice_reads`, `admin_approvals`;
- `ad_reward_attempts`, `billing_events`, `admin_audit`, `deletion_ledger`, `backup_restore_reapplied_deletions`.

A snapshot includes complete submitted schema/material and immutable evaluation context: problem/rubric version, requirements, deterministic-check output, Jev input/output/version/confidence, weighted per-requirement scores, pass state, and feedback version. Never retroactively overwrite a score or correction. Later feedback/correction is a new linked version. Immutable history is full history, subject to deletion/legal-retention policy in [security-and-privacy.md](../security/security-and-privacy.md#s5-privacy-consent-retention-and-deletion).

Each requirement is scored independently with explicit weight; total is the weighted aggregate, not category scoring. Passing is separate: all critical requirements pass and no contradiction is present. Inferred/derivable requirements cannot be critical. Naming and extensibility feedback is FB-only: it is not numeric scoring and never critical.

**Acceptance:** `ARC-07` result replay identifies its exact inputs/models/versions; `ARC-08` revisions cannot mutate prior snapshots or grades; `ARC-09` pass and score use the stated rules.

## A4. Evaluation and content pipeline

Static parsing, normalization, and deterministic checks run first. Jev receives only residual semantic questions and returns a typed, schema-validated decision (e.g., requirement validity/importance, contradiction, rationale reference); it is not a prose generator. Groq LLM writes problem, rubric, solution, correction-draft, and explanatory feedback prose from structured inputs. There is no expensive-model fallback: low confidence still yields a definitive outcome with disclosed low-confidence status. Inputs/outputs are schema-validated; that is defense-in-depth, not a cure for prompt injection.

A monthly scheduler produces the calendar for the month two months ahead. Static checks plus Jev quality decisions gate each candidate; bounded retries and alerts handle failures. Exact duplicates regenerate; similar problems are permitted. Publication is global at 04:00 JST daily, with idempotent publication events. Admin content/rubric tools remain required; infrastructure monitoring is not a content-management substitute.

**Acceptance:** `ARC-10` deterministic checks precede Jev; `ARC-11` Jev never writes prose; `ARC-12` calendar/publish/retry/alert behavior is testable and idempotent.

## A5. APIs and client behavior

Versioned BFF contracts cover auth/session, profile/age acknowledgement, problem/read, workspace/draft, submission/evaluation, feedback request/read, translation/read, posts/report, notices/read, and privileged admin actions. Mutations carry idempotency keys; authorization uses current server-side identity/privilege. API responses expose stable IDs and content versions, not provider secrets or raw model traces.

Learning content is authenticated-only. Public exceptions are login, age/legal pages, and required account-rights routes. PWA supports cached previously opened questions and local drafts for all users; database-synced drafts are premium-only. Reconnected queued submissions must revalidate authentication, privilege, current problem/rubric compatibility, explicit version, and idempotency. Shared-device settings purge local caches/drafts on logout; offline devices cannot be remotely wiped.

Translation: English source is translated lazily by NMT and cached for public/member content by `(content_version, locale)` across members. Private feedback translations are isolated by owner. Older immutable translations may remain readable. Supported locales: `en`, `ja`, `zh-CN`, `ko`, `es`, `pt-BR`.

Feedback request flow: a workspace action first has the LLM generate English feedback from the selected submission and assessment, then NMT translates the selected language and caches it. First request per `(user, problem)` is free; later requests require one verified rewarded-ad unlock each; premium is ad-free. Existing feedback rereads free. No unlimited-token promise. Reward failure/retry cannot double consume.

Posts are optional 100-point score records only. No comments and no author edit/delete; account/legal/admin deletion exceptions apply. Jev premoderates suspicious content into held state. HTTPS links are allowed but never fetched. Notices require admin approval before revision; approved archived versions stay accessible and unread status gets a badge.

**Acceptance:** `ARC-13` all client mutations use server authorization/idempotency; `ARC-14` cache keys isolate private feedback; `ARC-15` posts and notices obey immutable/moderation rules.

---

# 日本語版

# SchemaSprint MVPアーキテクチャ

**ステータス凡例：** **Confirmed（確定）** = ユーザーの決定；**Proposed（提案）** = 承認が必要な実装上のデフォルト；**Gate（ゲート）** = リリース前にベンダー／法務／技術上の事実を検証するもの。これはWeb PWAのMVPであり、将来のExpo React Native iOS/AndroidクライアントはWeb Cookieではなく同じコントラクトを使用する。Next.jsは使用しない。

## A1. システム境界とデプロイ

**Confirmed（確定）：** 候補トポロジーは Cloudflare Pages（静的PWA） -> Cloudflare Workers/BFF API -> Supabase Auth + Postgres。Workersは英語のフィードバック／問題文についてGroqホストLLMを、意味的判断についてJev TypeSafe外部型付き意思決定モデルを、翻訳についてGoogle Cloud Translation NMT（LLMではない）を呼び出す。Ollamaは任意のローカル開発専用であり、常時稼働AWS GPUは存在しない。候補ベンダー、機能上限、データ規約、リージョン、現在の価格は**リリースゲート**であり、主張ではない。

Workersは唯一の公開アプリケーションAPIかつポリシー適用点である。Pagesには秘密情報を置かず、同一オリジンのBFFエンドポイントとのみ通信する。Supabaseの通常クエリではユーザーJWTをRLSへ伝播し、特権操作では明示的に認可されたWorkerパスでのみ別個のサービス資格情報を使う。`service_role`を公開したり認可バイパスとして使ったりしてはならない。推論／翻訳プロバイダーに渡すのは必要最小限のコンテンツだけで、本人確認情報、セッション／JWT、メールアドレス、不要な履歴は渡さない；認証／決済ベンダーには文書化された必要な本人確認情報を渡す場合がある。LLM/Jevにはツールも権限も与えず、信頼できないコンテンツでポリシーを変更できないようにする。

**Acceptance:** `ARC-01` Web PWAがNext.jsなしで動作する；`ARC-02`ネイティブクライアントがネイティブのトークン／ストレージ処理でバージョン付きAPIを採用できる；`ARC-03`常時稼働GPU／AWSコンピュートを必要としない。

## A2. アイデンティティ、テナンシー、RBAC

Supabase Auth UUIDは内部ULID `user_id`に一対一で対応付け、すべてのドメインFKはULIDを使う。表示名は一意でない。プロバイダーIDは別レコードとし、アカウント連携には明示的に検証された所有権の証明が必要である。Google/GitHubの許可リストアクセスは、承認済みで検証されたプロバイダーIDに限る。手動でブートストラップされた、検証済みメールを持つ初期管理者は永続的なサブジェクト紐付けを得る；メールだけで認可してはならない。GitHubの非公開／メールなしIDは、安全でない暗黙の連携なしに処理する必要がある。

ロールは learner、moderator、admin、owner；moderator/admin/owner権限の拡張は**Proposed（提案）**であり、初期デプロイにはownerが1人だけ存在する。サーバー側ポリシーが各アクションを許可し、クライアントはロール、成績、premium、公開状態、モデレーション状態、承認を設定できない。Admin/owner操作にはMFAと監査可能な認可が必要である。初期の16歳以上ゲートは自己申告であり、普遍的な法令遵守の証明ではない。

**Acceptance:** `ARC-04` owner／アクションチェックと最小権限RLSが全ドメインアクションをカバーする；`ARC-05`重複名や変更されたメールでアカウントを統合／認可できない；`ARC-06`管理者ブートストラップは手動かつサブジェクトに紐付く。

## A3. リレーショナルドメイン（概念）

中核となる不変／バージョン管理エンティティ：

- `users`、`provider_identities`、`age_declarations`、`roles`、`entitlements`、`session/revocation`；
- `problems`、`problem_versions`、`requirements`、`rubrics`、`solutions`、`publication_calendar`、`publication_events`；
- `workspaces`、`schema_snapshots`、`submissions`、`submission_results`、`feedback_versions`、`translation_cache`；
- `posts`、`reports`、`post_moderation`、`moderation_decisions`；`notices`、`notice_versions`、`notice_reads`、`admin_approvals`；
- `ad_reward_attempts`、`billing_events`、`admin_audit`、`deletion_ledger`、`backup_restore_reapplied_deletions`。

スナップショットには、提出されたスキーマ／素材全体と、不変の評価コンテキスト（問題／ルーブリックのバージョン、要件、決定論的チェック出力、Jevの入力／出力／バージョン／信頼度、要件ごとの重み付きスコア、合否状態、フィードバックバージョン）を含める。スコアや訂正を遡及的に上書きしてはならない。後続のフィードバック／訂正は新しいリンク済みバージョンとする。不変履歴は、[security-and-privacy.md](../security/security-and-privacy.md#s5-privacy-consent-retention-and-deletion)の削除／法定保持ポリシーに従う完全な履歴である。

各要件は明示的な重みで独立に採点し、合計はカテゴリ採点ではなく重み付き集計とする。合格は別個に判定し、すべての重要要件に合格し、矛盾がないことを条件とする。推論／導出された要件を重要にはできない。命名と拡張性のフィードバックはFB専用とし、数値採点の対象ではなく、決して重要要件にはしない。

**Acceptance:** `ARC-07`結果のリプレイで正確な入力／モデル／バージョンを特定できる；`ARC-08`改訂で過去のスナップショットや成績を変更できない；`ARC-09`合否とスコアが記載された規則を使う。

## A4. 評価とコンテンツパイプライン

静的解析、正規化、決定論的チェックを最初に実行する。Jevには残った意味的質問だけを渡し、型付きでスキーマ検証済みの判断（例：要件の妥当性／重要性、矛盾、根拠参照）を返させる；Jevは文章生成器ではない。Groq LLMは構造化入力から問題、ルーブリック、解答、訂正ドラフト、説明的フィードバックの文章を作成する。高価なモデルへのフォールバックはない：低信頼でも、低信頼状態を開示した確定済みの結果を返す。入力／出力はスキーマ検証するが、これは多層防御であってプロンプトインジェクションを完全に防ぐものではない。

月次スケジューラは2か月先の月のカレンダーを生成する。静的チェックとJevの品質判断で各候補をゲートし、限定的リトライとアラートで障害を処理する。完全な重複は再生成し、類似問題は許可する。公開は毎日04:00 JSTにグローバルで行い、公開イベントは冪等とする。管理者向けコンテンツ／ルーブリックツールは引き続き必須であり、インフラ監視はコンテンツ管理の代替ではない。

**Acceptance:** `ARC-10`決定論的チェックがJevに先行する；`ARC-11` Jevは文章を書かない；`ARC-12`カレンダー／公開／リトライ／アラートの挙動をテストでき、冪等である。

## A5. APIとクライアント挙動

バージョン付きBFFコントラクトは、認証／セッション、プロフィール／年齢確認、問題／閲覧、ワークスペース／下書き、提出／評価、フィードバック要求／閲覧、翻訳／閲覧、投稿／通報、通知／閲覧、特権管理者操作を対象とする。ミューテーションには冪等キーを付け、認可には現在のサーバー側アイデンティティ／権限を使う。APIレスポンスには安定したIDとコンテンツバージョンを公開し、プロバイダー秘密情報や生のモデルトレースは公開しない。

学習コンテンツは認証済みユーザー専用とする。公開例外はログイン、年齢／法務ページ、必要なアカウント権利ルートである。PWAは全ユーザーについて以前開いた問題とローカル下書きをキャッシュでき、データベース同期下書きはpremium専用とする。再接続時にキューされた提出は、認証、権限、現在の問題／ルーブリック互換性、明示的バージョン、冪等性を再検証する。共有端末設定ではログアウト時にローカルキャッシュ／下書きを消去し、オフライン端末をリモート消去することはできない。

翻訳：英語ソースをNMTで遅延翻訳し、メンバー間で公開／会員コンテンツを`(content_version, locale)`単位でキャッシュする。非公開フィードバックの翻訳は所有者単位で隔離する。古い不変翻訳は引き続き読める場合がある。対応ロケール：`en`、`ja`、`zh-CN`、`ko`、`es`、`pt-BR`。

フィードバック要求フロー：ワークスペースのアクションで、まず選択した提出物と評価からLLMに英語フィードバックを生成させ、その後NMTで選択言語に翻訳してキャッシュする。`(user, problem)`ごとの最初の要求は無料で、その後の要求には検証済みリワード広告アンロックが1回ずつ必要；premiumは広告なし。既存フィードバックの再閲覧は無料。無制限トークンは約束しない。報酬の失敗／リトライで二重消費してはならない。

投稿は任意の100点スコア記録のみとする。コメントも投稿者による編集／削除もない；アカウント／法務／管理者による削除の例外は適用する。Jevは疑わしいコンテンツを保留状態に事前モデレーションする。HTTPSリンクは許可するが、決して取得しない。通知は改訂前に管理者承認が必要で、承認済みアーカイブ版はアクセス可能なままとし、未読状態にはバッジを付ける。

**Acceptance:** `ARC-13`全クライアントミューテーションがサーバー認可／冪等性を使う；`ARC-14`キャッシュキーが非公開フィードバックを隔離する；`ARC-15`投稿と通知が不変／モデレーション規則に従う。
