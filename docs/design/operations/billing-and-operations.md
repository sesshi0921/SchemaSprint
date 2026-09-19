# Billing and Operations Requirements

## O1. Cost controls and vendor gates

**Confirmed:** MVP has no actual charge, payment CTA, or promised unlimited infrastructure/model use. Billing machinery is sandbox-only. Future subscription cadence is monthly and annual; price is intentionally unspecified. Candidate architecture is Cloudflare Pages/Workers + Supabase + Groq/Jev/Google NMT. Vendor capability/pricing must be checked at release, not assumed.

**Proposed defaults:** tag resources `product=schemasprint`, environment, owner and expiry; estimate baseline/variable cost for Worker requests/CPU, Supabase, storage/backups, model/NMT calls, ads, logging/monitoring and egress before production. Set cost alerts at 50%, 75%, 90%, 100% of approved monthly budget. The monthly budget amount remains unresolved and requires owner decision before paid infrastructure is enabled; 90% alerts owner by email, 100% activates a reviewed global breaker/degraded path. Exact budgets and degraded behavior need owner approval. Limit model/NMT calls, retries, request body/time/concurrency and log retention; cache immutable public translations. Cost controls may not reduce security, backups or required observability.

Successful daily publication, original user-required events, failures and near-limit costs send owner email; do not silently omit required publication/event work. Content/rubric admin tooling remains separate from infrastructure console.

**Acceptance:** `OPS-01` preproduction cost model and vendor validation exist; `OPS-02` alerts/breaker are tested without losing required data; `OPS-03` monthly cost review examines usage, cache, retention, idle/orphaned resources and anomalies.

## O2. Advertising and rewarded feedback

Google Ad Manager is a candidate only; inventory, consent, policy, callback and pricing feasibility are release gates. A no-fill response is not automatically a blocker, but if ads appear to be blocked, show the warning “Ads appear to be blocked...” and stop the reward flow; for inventory exhaustion, show the truthful “No rewarded ad is available...” retry/no-inventory path. Do not claim signed server attestation exists for browser GPT callbacks. Before launch, prove secure reward-verification feasibility, replay resistance, callback/server validation as supported, and per-user/provider abuse budgets.

Each reward grants one feedback request only. Persist an idempotent reward-attempt lifecycle; consume only after verified success, never consume twice on failure/retry, and rereads are free. Premium is ad-free and does not authorize unlimited model spend.

**Acceptance:** `OPS-04` reward failure, duplicate callback, replay and no-fill tests preserve correct entitlement.

## O3. Future payments and entitlement authority

Future entitlement aggregation candidate: RevenueCat. Web payment candidate: Stripe Checkout/Billing, or a merchant-of-record solution after global-tax review; future native payments use Apple/Google stores. The product never handles card data. Validate each provider’s current webhook authentication: RevenueCat commonly uses an authorization header, not a universal signed-webhook assumption. Verify provider-specific authorization, deduplicate event IDs/order, reconcile delayed/out-of-order events, and process expiry/refund/revocation.

Only verified provider events or audited admin actions change entitlement. Client state is never authority. Admin premium grant/revoke is controlled, MFA-protected, reasoned and audited. Sandbox-only MVP must keep all payment endpoints/CTAs disabled in production until the payment release gate is approved.

**Acceptance:** `OPS-05` provider webhook/auth assumptions are documented from current official sources before enabling; `OPS-06` entitlement reconciliation and refund/expiry tests pass; `OPS-07` admin actions audit actor/reason/time.

## O4. Release, recovery, and operations

Separate dev/staging/prod configurations and credentials. Release uses immutable versioned artifacts, CI security gates, preflight checks, staged exposure/canary or feature flag where feasible, and explicit success/error/rollback thresholds. Migrations require backup, compatibility window, forward/rollback-or-roll-forward steps, validation and owner. No destructive production operation without authorization.

Backups are encrypted and automated. Retention maximum is 30 days; restoration is periodically tested, including deletion-ledger reapplied removal. Define health/readiness checks, redacted structured logs, metrics for traffic/latency/errors/saturation/core journeys, bounded retry/backoff/timeouts, idempotency and graceful dependency degradation. On incident: contain, preserve evidence, rotate exposed credentials, assess impact, recover known-good state, communicate accurately, then document cause/prevention.

**Acceptance:** `OPS-08` restore and rollback drills have evidence; `OPS-09` each alert has owner/runbook action; `OPS-10` publication/evaluation/provider outage follows tested graceful failure behavior.

---

# 日本語版

# 課金と運用要件

## O1. コスト管理とベンダーゲート

**Confirmed（確定）：** MVPには実際の課金、決済CTA、無制限のインフラ／モデル利用の約束はない。課金機構はサンドボックス専用である。将来のサブスクリプション周期は月次と年次とし、価格は意図的に未指定とする。候補アーキテクチャはCloudflare Pages/Workers + Supabase + Groq/Jev/Google NMT。ベンダーの機能／価格はリリース時に確認し、仮定しない。

**Proposed defaults（提案デフォルト）：** リソースに`product=schemasprint`、環境、所有者、有効期限をタグ付けする；本番前にWorkerリクエスト／CPU、Supabase、ストレージ／バックアップ、モデル／NMT呼び出し、広告、ログ／監視、エグレスのベースライン／変動コストを見積もる。承認済み月間予算の50%、75%、90%、100%でコストアラートを設定する。月間予算額は未解決であり、有料インフラを有効化する前に所有者の決定が必要である。90%では所有者にメール通知、100%ではレビュー済みのグローバルブレーカー／縮退経路を有効化する。正確な予算と縮退挙動には所有者の承認が必要である。モデル／NMT呼び出し、リトライ、リクエスト本文／時間／同時実行数、ログ保持を制限し、不変の公開翻訳をキャッシュする。コスト管理でセキュリティ、バックアップ、必須の可観測性を低下させてはならない。

成功した毎日の公開、ユーザーが要求した本来のイベント、障害、上限間近のコストは所有者にメール送信し、必須の公開／イベント作業を黙って省略しない。コンテンツ／ルーブリック管理ツールはインフラコンソールから分離したままとする。

**Acceptance:** `OPS-01`本番前のコストモデルとベンダー検証が存在する；`OPS-02`必須データを失わずにアラート／ブレーカーをテストする；`OPS-03`月次コストレビューで使用量、キャッシュ、保持、アイドル／孤立リソース、異常を検討する。

## O2. 広告とリワード付きフィードバック

Google Ad Managerは候補にすぎず、在庫、同意、ポリシー、コールバック、価格の実現可能性はリリースゲートである。no-fill応答は自動的にブロッカーではないが、広告がブロックされているように見える場合は警告「Ads appear to be blocked...」を表示して報酬フローを停止し、在庫枯渇の場合は真実に基づく「No rewarded ad is available...」リトライ／在庫なし経路を表示する。ブラウザGPTコールバックに署名済みサーバー証明が存在すると主張してはならない。ローンチ前に、安全な報酬検証の実現可能性、リプレイ耐性、対応範囲内のコールバック／サーバー検証、ユーザー／プロバイダーごとの悪用対策用の利用上限を立証する。

各報酬はフィードバック要求を1回だけ付与する。冪等な報酬試行ライフサイクルを永続化し、検証済み成功後にのみ消費し、失敗／リトライで二度消費せず、再閲覧は無料とする。Premiumは広告なしであり、無制限のモデル利用を認可するものではない。

**Acceptance:** `OPS-04`報酬失敗、重複コールバック、リプレイ、no-fillテストが正しい権利状態を維持する。

## O3. 将来の決済と利用権限の正本管理

将来の権利集約候補はRevenueCat。Web決済候補はStripe Checkout/Billing、またはグローバル税務レビュー後のmerchant-of-recordソリューション；将来のネイティブ決済はApple/Googleストアを使う。プロダクトはカードデータを扱わない。各プロバイダーの現在のWebhook認証を検証する：RevenueCatは一般に、普遍的な署名付きWebhookという前提ではなく、認可ヘッダーを使う。プロバイダー固有の認可、イベントID／注文の重複排除、遅延／順不同イベントの照合、期限切れ／返金／取消を検証する。

検証済みプロバイダーイベントまたは監査済み管理者アクションだけが権利を変更する。クライアントの状態を正本として扱わない。管理者によるpremium付与／取消は管理され、MFAで保護され、理由を付け、監査する。サンドボックス専用MVPでは、決済リリースゲートが承認されるまで、本番のすべての決済エンドポイント／CTAを無効のままにする。

**Acceptance:** `OPS-05`有効化前に、プロバイダーWebhook／認証の前提を現在の公式情報に基づき文書化する；`OPS-06`権利の照合と返金／期限切れテストが合格する；`OPS-07`管理者アクションが実行者／理由／時刻を監査する。

## O4. リリース、復旧、運用

開発／ステージング／本番の設定と資格情報を分離する。リリースでは、不変のバージョン付き成果物、CIセキュリティゲート、プレフライトチェック、可能な場合は段階的公開／カナリアまたは機能フラグ、明示的な成功／エラー／ロールバックしきい値を使う。マイグレーションにはバックアップ、互換性ウィンドウ、前進／ロールバックまたはロールフォワード手順、検証、所有者を必要とする。認可なしに破壊的な本番操作を行わない。

バックアップは暗号化し、自動化する。保持期間の最大は30日とし、削除台帳の再適用による削除を含め、復元を定期的にテストする。ヘルス／レディネスチェック、機密情報を除去した構造化ログ、トラフィック／レイテンシ／エラー／飽和度／主要ジャーニーのメトリクス、上限付きリトライ／バックオフ／タイムアウト、冪等性、依存関係の適切な縮退を定義する。インシデント時は、封じ込め、証拠保全、漏洩資格情報のローテーション、影響評価、既知の正常状態への復旧、正確なコミュニケーションを行い、その後に原因／防止策を文書化する。

**Acceptance:** `OPS-08`復元とロールバック訓練に証跡がある；`OPS-09`各アラートに所有者／ランブックアクションがある；`OPS-10`公開／評価／プロバイダー障害がテスト済みの適切な失敗処理に従う。
