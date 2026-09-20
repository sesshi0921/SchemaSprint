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
uv run pytest tests -q

# Frontend
cd frontend
npm ci
npm run lint
npm test -- --run
npm exec tsc -- --noEmit
npm run build
```

## 外部サービスと本番前提

- Jevは外部URL・認証情報・API仕様を設定していないため、既定では採点を実行せず`JEV_UNAVAILABLE`を返します。ローカルのstubはテスト専用です。
- Groqは問題文・フィードバック生成用の任意のサーバー側プロバイダーです。`SCHEMASPRINT_LLM_MODE=unavailable`（既定）または空の`SCHEMASPRINT_GROQ_API_KEY`では`GROQ_UNAVAILABLE`として生成せず、キーはブラウザへ公開しません。`SCHEMASPRINT_LLM_MODE=groq`とAPI URL、モデル、タイムアウトは`infra/local/.env.example`を参照してください。429/5xxは再試行可能な明示的エラーとして上位のジョブ処理に渡します。
- Google/GitHub OAuth、Cloudflare Worker/R2、Supabase Auth/PostgreSQL、メール通知、広告、決済は本番のシークレット登録とE2E検証が必要です。
- `docs/design/*/review.md` の未完了ゲート（実BFF/OAuth E2E、アクセシビリティ・モバイル実機、バックアップ・復旧、負荷・ペネトレーション、運用予算監視）を通過するまで本番公開しません。
- 本リポジトリの環境ではDocker実行と本番デプロイを行っていません。
