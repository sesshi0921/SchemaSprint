# SchemaSprint Design Requirements

Bilingual source requirements: English first, followed by the Japanese translation.

## Documents

- [Product requirements](product/requirements.md)
- [Learning, problems, and assessment](learning/problems-and-assessment.md)
- [Editor and community experience](experience/editor-and-community.md)
- [Platform architecture](platform/architecture.md)
- [Security and privacy](security/security-and-privacy.md)
- [Billing and operations](operations/billing-and-operations.md)

## Requirement status

- **Agreed**: confirmed product requirement.
- **Default**: reversible implementation/product assumption; validate before locking it down.
- **Proposal**: intentionally unresolved option; requires a decision.

Acceptance criteria use `AC-*`, `ARC-*`, `SEC-*`, and `OPS-*`. Cross-document controls, privacy, architecture, and operations are specified in their owning documents.

## Condensed Traceability

| Area | Primary requirements | Verification anchors |
|---|---|---|
| Access, daily loop, offline, locale | `product/requirements.md` | AC-PROD-001–009 |
| Problem generation, rubric, grading | `learning/problems-and-assessment.md` | AC-LEARN-001–008 |
| Workspace, schema editor, posts | `experience/editor-and-community.md` | AC-EXP-001–009 |
| System, privacy, operations | owner documents listed above | owning-document acceptance criteria |

Requirements are derived from the product conversation, not external market claims. Source date: 2026-09-20. The Must scope includes all agreed MVP commitments; no unilateral pruning is allowed. The current scope does not require native-store release, live charges, costly grading fallback, comments, or any Should/Could work. “Agreed” captures confirmed decisions; “Default” and “Proposal” remain reversible until validated.

---

# 日本語版

# SchemaSprint 設計要件

英語を先に記載し、その後に日本語訳を付記したバイリンガル原要件。

## 文書

- [製品要件](product/requirements.md)
- [学習、課題、評価](learning/problems-and-assessment.md)
- [エディターとコミュニティ体験](experience/editor-and-community.md)
- [プラットフォームアーキテクチャ](platform/architecture.md)
- [セキュリティとプライバシー](security/security-and-privacy.md)
- [課金と運用](operations/billing-and-operations.md)

## 要件ステータス

- **合意済み**: 確定した製品要件。
- **デフォルト**: 変更可能な実装・製品上の仮定。確定前に検証する。
- **提案**: 意図的に未解決の選択肢。決定が必要。

受け入れ基準では `AC-*`、`ARC-*`、`SEC-*`、`OPS-*` を使用します。文書横断の管理、プライバシー、アーキテクチャ、運用は、それぞれの所管文書に記載します。

## 簡略トレーサビリティ

| 領域 | 主な要件 | 検証アンカー |
|---|---|---|
| アクセス、日次ループ、オフライン、ロケール | `product/requirements.md` | AC-PROD-001–009 |
| 課題生成、ルーブリック、採点 | `learning/problems-and-assessment.md` | AC-LEARN-001–008 |
| ワークスペース、スキーマエディター、投稿 | `experience/editor-and-community.md` | AC-EXP-001–009 |
| システム、プライバシー、運用 | 上記の所管文書 | 所管文書の受け入れ基準 |

要件は外部市場の主張ではなく、製品に関する対話から導出されています。原文日付: 2026-09-20。「Must」スコープには合意済みのすべての MVP コミットメントを含め、独断で削除してはなりません。現行スコープでは、ネイティブストア公開、実課金、高コストの採点フォールバック、コメント、Should/Could 作業は必要ありません。「合意済み」は確認済みの決定を示し、「デフォルト」と「提案」は検証されるまで変更可能です。
