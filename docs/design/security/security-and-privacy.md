# Security and Privacy Requirements

## S1. Threat model and trust boundaries

Assets: identities, sessions, authorization/roles, private drafts/submissions/feedback, immutable records, entitlements/reward state, source content, secrets, audit/deletion records. Actors: learner, approved identity, moderator/admin/owner, browser/native client, Worker, Supabase, model/NMT/ad/payment providers, and external attackers. Boundaries: browser↔BFF, Worker↔database, Worker↔each provider, admin↔production, and production↔development.

Primary abuse cases: account takeover/linking, privilege escalation, cross-user/RLS read-write, CSRF/XSS/injection, malformed/oversize work, model prompt injection, grading/reward replay, ad fraud, post abuse/link attacks, provider/secret compromise, DDoS/cost exhaustion, deletion/backup leakage, and supply-chain vulnerabilities. Each release must update the threat model for changed boundary/data/exposure, assign owner/verification/residual risk, and block exploitable critical/high issues absent explicit accepted risk.

**Acceptance:** `SEC-01` threat-model review and targeted negative authorization tests are release evidence.

## S2. Identity, session, authorization

Web uses BFF-managed Secure, HttpOnly, SameSite cookies with short-lived session design; OAuth uses PKCE, state, validated exact redirect allowlists, and issuer/audience/expiry/signature JWT checks. Logout revokes server sessions. CORS is not authorization and cookies require CSRF protections. Native future clients use platform-secure storage/token flow, not the Web cookie model.

Every protected Worker action performs owner-and-action authorization, deny-by-default validation, and RLS-enforced least privilege. Database policies mirror, not replace, Worker checks. No arbitrary client role assignment; no client grade/premium/publish mutation. MFA is mandatory for admin/owner. Sensitive admin actions use step-up/recent-auth where feasible and tamper-resistant audit events.

## S3. Surface and data protection

Strict CSP, HSTS, clickjacking protection, secure headers, exact CORS origins, CSP-safe rendering, output encoding and parameterized queries are mandatory. Validate/normalize input types, formats, sizes, nesting, body/time/concurrency limits at edges. Render Markdown/Mermaid/LLM content as untrusted safe output. User-supplied DDL, triggers, scripts, or migrations never execute on the service database; MVP supports static parsing only. Any future executable sandbox is a separate security release gate.

Use WAF/DDoS controls, Turnstile and risk-based rate limits by user/IP/action, plus global concurrency/body/time caps and circuit breakers. Cap provider calls and retry budgets. External HTTPS post links are displayed safely and not fetched. Errors avoid revealing authorization/database/provider internals.

## S4. Secrets, environments, vendors

Production, staging/development, admin access and keys are isolated. Secrets live only in approved secret stores/CI injection, are never shipped/logged, are scoped least-privilege and rotated on exposure/on schedule. Provider credentials use service identities and short-lived credentials where supported. Restrict provider egress to required endpoints.

Before production, validate Groq/Jev/Google Translation/Cloudflare/Supabase/ad/billing vendors for capability, pricing, availability, data processing/retention/deletion commitments, regions, security controls, webhook mechanics and support. Do not assert unavailable vendor properties. Schema validation of model I/O does not solve prompt injection; models receive no tools/authority and only necessary ER/requirements content, not identities/tokens.

## S5. Privacy, consent, retention and deletion

Collect only service-needed data. Encrypt in transit and at rest; redact tokens, answers and sensitive content from logs. Privacy notice, ToS, and community policy are not drafted or legally complete; proposed legal/product gates must be completed before relying on them; these are required deliverables for pre-release review, and these requirements are not legal advice or completed policies. Add version/time acknowledgements once approved. Policy updates block learning until acknowledgement, but logout, deletion and legal-rights access remain available. Privacy acknowledgement is not blanket consent.

For EU/other applicable jurisdictions, refusal of cookies does not automatically allow non-personalized advertising: nonessential tracking stays disabled; serve only legally permitted limited ads or no-ad fallback, without consent coercion. Legal review is a release gate for advertising/cookies, cross-border transfer, minors, retention/deletion, taxes and accessibility. A global 16+ gate is not universal legal compliance.

Account deletion immediately deletes live account records, drafts, submissions and community data; revokes sessions; clears local cache best-effort. Offline other devices cannot be remotely wiped. Namespace caches per account and purge on logout. Encrypted backups retain at most 30 days, restore tests verify that limit, restored deleted data is re-deleted from the minimal deletion ledger, and vendor backup/deletion support must be verified. A documented legal/accounting-retention exception needs legal approval; it cannot silently contradict deletion.

## S6. Secure delivery and observability

Lockfiles, dependency/SAST/secret scans, proportionate SBOM/license review and vulnerability gates are mandatory. Build artifacts are immutable; no unverified remote build scripts. Pre-public release requires independent penetration testing appropriate to the exposed product, with critical/high remediation or explicit authorized risk.

Monitor redacted authentication/authorization failures, admin actions, abuse/rate limits, provider failure, publication/evaluation failures, latency/errors, breaker state, backup/restore and cost signals. Audit trails are append-only/tamper-resistant and omit raw tokens/answers. Alerts have an owner/action. Baseline accessibility: keyboard operation, labels, contrast and visible focus; no separate specialized initiative is assumed.

**Acceptance:** `SEC-02` session/OAuth/CSRF and RLS negative tests pass; `SEC-03` secret/dependency/SAST scans and independent penetration test gate release; `SEC-04` deletion/backup restore/reapplied-deletion test passes; `SEC-05` consent fallback and policy acknowledgement behavior undergo legal/product review.

---

# 日本語版

# セキュリティとプライバシー要件

## S1. 脅威モデルと信頼境界

資産：アイデンティティ、セッション、認可／ロール、非公開の下書き／提出／フィードバック、不変レコード、権利／報酬状態、ソースコンテンツ、秘密情報、監査／削除記録。アクター：learner、承認済みID、moderator/admin/owner、ブラウザ／ネイティブクライアント、Worker、Supabase、モデル／NMT／広告／決済プロバイダー、外部攻撃者。境界：ブラウザ↔BFF、Worker↔データベース、Worker↔各プロバイダー、管理者↔本番、本番↔開発。

主な悪用事例：アカウント乗っ取り／連携、権限昇格、ユーザー間のRLS読み書き、CSRF/XSS/インジェクション、不正な／過大な作業、モデルプロンプトインジェクション、採点／報酬のリプレイ、広告詐欺、投稿悪用／リンク攻撃、プロバイダー／秘密情報の侵害、DDoS／コスト枯渇、削除／バックアップ漏洩、サプライチェーン脆弱性。各リリースでは変更された境界／データ／露出について脅威モデルを更新し、所有者／検証／残存リスクを割り当て、明示的に受容したリスクがない限り悪用可能なcritical/high問題をブロックする。

**Acceptance:** `SEC-01`脅威モデルレビューと対象を絞った認可ネガティブテストがリリース証跡となる。

## S2. アイデンティティ、セッション、認可

WebはBFF管理のSecure、HttpOnly、SameSite Cookieと短期セッション設計を使う；OAuthはPKCE、state、検証済みの厳密なリダイレクト許可リスト、issuer/audience/expiry/signature JWTチェックを使う。ログアウトではサーバーセッションを失効させる。CORSは認可ではなく、CookieにはCSRF対策が必要である。将来のネイティブクライアントはWeb Cookieモデルではなく、プラットフォーム安全ストレージ／トークンフローを使う。

保護されたWorkerアクションはすべて、所有者とアクションの認可、デフォルト拒否の検証、RLSで強制された最小権限を実施する。データベースポリシーはWorkerチェックを補完するものであり、置き換えない。任意のクライアントロール設定は禁止し、クライアントによる成績／premium／公開状態の変更も禁止する。Admin/ownerにはMFAが必須。機微な管理者アクションには、可能な限りステップアップ／最近の認証を用い、改ざん耐性のある監査イベントを残す。

## S3. 攻撃面とデータ保護

厳格なCSP、HSTS、クリックジャッキング対策、安全なヘッダー、厳密なCORSオリジン、CSPセーフなレンダリング、出力エンコーディング、パラメータ化クエリを必須とする。エッジで入力の型、形式、サイズ、ネスト、本文／時間／同時実行数の上限を検証／正規化する。Markdown/Mermaid/LLMコンテンツは信頼できない安全な出力としてレンダリングする。ユーザー提供のDDL、トリガー、スクリプト、マイグレーションをサービスデータベース上で実行してはならない；MVPは静的解析のみをサポートする。将来実行可能なサンドボックスは別個のセキュリティリリースゲートとする。

WAF/DDoS制御、Turnstile、ユーザー／IP／アクション別のリスクベースレート制限に加え、グローバルな同時実行数／本文／時間上限とサーキットブレーカーを使う。プロバイダー呼び出しとリトライ予算に上限を設ける。外部HTTPS投稿リンクは安全に表示し、取得しない。エラーで認可／データベース／プロバイダー内部情報を明らかにしない。

## S4. 秘密情報、環境、ベンダー

本番、ステージング／開発、管理者アクセス、キーを分離する。秘密情報は承認済みのシークレットストア／CI注入にのみ置き、出荷／ログ出力せず、最小権限にスコープし、漏洩時／スケジュールに従ってローテーションする。プロバイダー資格情報にはサービスIDと、対応している場合は短期資格情報を使う。プロバイダーへの外向き通信を必要なエンドポイントに制限する。

本番前に、Groq/Jev/Google Translation/Cloudflare/Supabase/広告／課金ベンダーについて、機能、価格、可用性、データ処理／保持／削除の約束、リージョン、セキュリティ制御、Webhookの仕組み、サポートを検証する。利用できないベンダー特性を主張しない。モデルI/Oのスキーマ検証はプロンプトインジェクションを解決しない；モデルにはツール／権限を与えず、必要なER／要件コンテンツだけを渡し、ID／トークンは渡さない。

## S5. プライバシー、同意、保持、削除

サービスに必要なデータだけを収集する。転送中と保存時に暗号化し、ログからトークン、解答、機微コンテンツを編集／除去する。プライバシー通知、ToS、コミュニティポリシーは未起草または法的に完了しておらず、これらに依拠する前に提案された法務／プロダクトゲートを完了する；これらはリリース前レビューに必要な成果物であり、本要件は法的助言でも完成済みポリシーでもない。承認後はバージョン／時刻付きの確認を持たせる。ポリシー更新では確認まで学習をブロックするが、ログアウト、削除、法的権利へのアクセスは引き続き可能とする。プライバシー確認は包括的同意ではない。

EUその他の適用法域では、Cookie拒否が自動的に非パーソナライズ広告を許可するわけではない：必須でないトラッキングは無効のままとし、法的に許された限定広告のみ、または同意を強制しない広告なしフォールバックを提供する。広告／Cookie、越境移転、未成年者、保持／削除、税、アクセシビリティについて法務レビューをリリースゲートとする。グローバルな16歳以上ゲートは普遍的な法令遵守ではない。

アカウント削除では、稼働中のアカウントレコード、下書き、提出、コミュニティデータを即時削除し、セッションを失効させ、ベストエフォートでローカルキャッシュを消去する。オフラインの他端末をリモート消去することはできない。キャッシュをアカウント単位で名前空間化し、ログアウト時に消去する。暗号化バックアップの保持は最大30日とし、復元テストでこの上限を検証する。復元された削除済みデータは最小限の削除台帳から再削除し、ベンダーのバックアップ／削除対応を検証する。文書化された法務／会計保持例外には法務承認が必要であり、削除と黙って矛盾してはならない。

## S6. 安全なデリバリーと可観測性

ロックファイル、依存関係／SAST／秘密情報スキャン、比例的なSBOM／ライセンスレビュー、脆弱性ゲートを必須とする。ビルド成果物は不変とし、未検証のリモートビルドスクリプトを使わない。公開前リリースでは、公開製品に適した独立ペネトレーションテストを行い、critical/highの修正または明示的な承認済みリスクが必要である。

機密情報を除去した認証／認可失敗、管理者アクション、悪用／レート制限、プロバイダー障害、公開／評価障害、レイテンシ／エラー、ブレーカー状態、バックアップ／復元、コストシグナルを監視する。監査証跡は追記専用／改ざん耐性とし、生のトークン／解答を含めない。アラートには所有者／アクションを持たせる。アクセシビリティのベースラインは、キーボード操作、ラベル、コントラスト、可視フォーカスであり、別個の専門施策は想定しない。

**Acceptance:** `SEC-02`セッション／OAuth／CSRFとRLSネガティブテストが合格する；`SEC-03`秘密情報／依存関係／SASTスキャンと独立ペネトレーションテストがリリースをゲートする；`SEC-04`削除／バックアップ復元／削除再適用テストが合格する；`SEC-05`同意フォールバックとポリシー確認の挙動が法務／プロダクトレビューを受ける。
