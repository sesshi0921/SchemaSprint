# SchemaSprint

DB設計（要件定義→ER図→採点・フィードバック）を練習するPWAです。現状は実装途中のMVP基盤で、Jev・OAuth・本番決済は未接続です。

## ローカル表示

### 最短（Vite）

```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1
```

`http://127.0.0.1:5173/` を開きます。APIが未起動の場合は、画面に未接続状態を表示します。

### Docker Compose

Docker/Colima/OrbStackをインストール済みの環境で実行します。

```bash
cp infra/local/.env.example infra/local/.env
docker compose --env-file infra/local/.env -f infra/docker-compose.yml up --build
```

`http://localhost:8080/` を開きます。停止は `Ctrl-C`、データ削除を伴う停止は `docker compose ... down -v` です。

## 開発・検証

```bash
# Backend
uv sync
uv run ruff check backend tests
uv run ruff format --check backend tests
uv run mypy backend tests
uv run sqlfluff lint db
uv run python -m openapi_spec_validator openapi.yaml
uv export --locked --format requirements-txt --no-hashes > /tmp/schemasprint-requirements.txt
uvx pip-audit --requirement /tmp/schemasprint-requirements.txt
uv run pytest tests -q

# Frontend
cd frontend
npm ci
npm run lint
npm test -- --run
npm exec tsc -- --noEmit
npm run build
npx playwright install chromium-headless-shell
npm run test:e2e

# Cloudflare Worker configuration (no deployment)
cd infra/cloudflare/gateway
npm ci
npm run typecheck
npx wrangler deploy --config wrangler.staging.jsonc --dry-run --containers-rollout=none
```

The Worker dry-run validates the staging bindings without uploading a Worker or
building/deploying the Container. A real Container rollout additionally needs
Docker-compatible tooling, Cloudflare authentication, and the protected
environment secrets described in `infra/terraform/README.md`.

## 外部サービスと本番前提

- Jevは既定で`unavailable`のため、キー未設定時は採点を実行せず`JEV_UNAVAILABLE`を返します。ローカルのstubはテスト専用です。接続先は`https://api.typesafe.ai`を既定値とし、環境変数で差し替えられます。
- Groqは問題文・フィードバック生成用の任意のサーバー側プロバイダーです。`LLM_MODE=unavailable`（既定）または空の`GROQ_API_KEY`では`GROQ_UNAVAILABLE`として生成せず、キーはブラウザへ公開しません。`LLM_MODE=groq`とAPI URL、モデル、タイムアウトは`infra/local/.env.example`を参照してください。429/5xxは再試行可能な明示的エラーとして上位のジョブ処理に渡します。
- フィードバックは提出済み結果の画面からのみ要求できます。ローカル`LLM_MODE=stub`では検証済みの開発用フィードバックを保存し、初回要求後の再生成はPremiumまたは広告報酬が必要です（MVPでは広告を無効化）。`LLM_MODE=groq`はデータ処理ポリシーを確認した専用ワーカーを別途配備するまで`pending`ジョブとして保持し、未接続なのに成功表示しません。
- Google/GitHub OAuth、Cloudflare Worker/R2、Supabase Auth/PostgreSQL、メール通知、広告、決済は本番のシークレット登録とE2E検証が必要です。
- `docs/design/*/review.md` の未完了ゲート（実BFF/OAuth E2E、アクセシビリティ・モバイル実機、バックアップ・復旧、負荷・ペネトレーション、運用予算監視）を通過するまで本番公開しません。
- 本リポジトリの環境ではDocker実行と本番デプロイを行っていません。

### OAuthの登録

Google/GitHubの開発者コンソールで、実際に配信するHTTPSのcallback URLを正確に登録し、次のサーバー専用Secretを設定します。未設定時は`OAUTH_NOT_CONFIGURED`を返し、成功を偽装しません。

```env
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=https://<公開ホスト>/api/v1/auth/google/callback
GITHUB_CLIENT_ID=...
GITHUB_CLIENT_SECRET=...
GITHUB_REDIRECT_URI=https://<公開ホスト>/api/v1/auth/github/callback
```

OAuthはPKCE、ワンタイムstate、暗号化済み検証子、HTTPS、allowlist済み既存provider identityを要求します。Supabase Authの新規ユーザー自動プロビジョニングとOIDC JWKS検証は本番リリース前ゲートです。

### Groq開発キーの登録

1. [Groq Console](https://console.groq.com/)でアカウントを作成し、開発用Projectを作成する。
2. **API Keys → Create API Key** でキーを発行し、パスワード管理ツールへ一度だけ保存する。
3. `GROQ_API_KEY`として、バックエンドまたはWorkerのSecretへ登録する。`.env`、Git、ブラウザ環境変数、ログには書かない。
4. `LLM_MODE=groq`を設定し、サーバーを再起動する。キー未設定時は成功表示せず`LLM_UNAVAILABLE`となる。

Groqのキー発行・API形式・制限は[公式ドキュメント](https://console.groq.com/docs/openai)を確認する。実キーの登録と本番利用は、データ処理条件・予算・レート上限を確認してから行う。

### Jevの接続先

TypeSafe公式の接続先は`https://api.typesafe.ai/v1/systemone`です。設定値にはホスト部分の`https://api.typesafe.ai`を指定すると、バックエンドが`/v1/systemone`を付加します。公式APIは`Authorization: Bearer`で認証し、`model`・`state`・`questions`をJSONで送信します。[公式クイックスタート](https://docs.typesafe.ai/introduction/quickstart)

```env
JEV_MODE=external
JEV_BASE_URL=https://api.typesafe.ai
JEV_API_KEY=取得したキー
JEV_MODEL=jev-latest
```

### Cloudflare preview deployment

The static PWA preview is published at
`https://800db4b0.schemasprint-web.pages.dev`. The staging Worker shell is
published at `https://schemasprint-gateway-staging.seshimaru-dev.workers.dev`.
The Worker currently returns `PAID_RUNTIME_DISABLED` because the MVP keeps
Cloudflare Containers disabled; the Pages preview therefore truthfully shows
the API-unavailable state until the protected database/secrets and paid-runtime
release gates are approved. No production route or live container rollout was
enabled.
