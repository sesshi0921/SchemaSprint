# Learning, Problems, and Assessment Requirements

## 1. Learning Scope

### 1.1 Supported design domains
- **Agreed**: Problems cover web OLTP design.
- **Agreed**: Problems cover analytics star schemas, including explicit grain and aggregation reasoning.
- **Agreed**: Problems cover normalization and redesign.
- **Agreed**: Multiple different valid schemas are accepted; an exact match to the official schema is not required, including when appropriate analysis denormalization is used.
- **Agreed**: Problems cover translating mathematical, set, and graph concepts into database designs.

### 1.2 Difficulty expectations
- **Agreed**: Easy problems require some database knowledge and may include many-to-many relationships.
- **Agreed**: Mid problems target users with service-development experience.
- **Agreed**: Hard problems may be tiny schemas whose reasoning is difficult.
- **Agreed**: Scale generally grows with difficulty, but entity/table counts must not be the definition of hard difficulty.

## 2. Problem Generation and Publication

### 2.1 Generation schedule
- **Agreed**: A monthly batch generates the complete calendar month two months ahead; for example, September generation produces November problems.
- **Default**: At launch, bootstrap generation fills intervening months required to avoid a calendar gap.
- **Agreed**: Static checks and Jev quality checks run on every generated candidate.
- **Agreed**: Failed candidates and exact duplicates are regenerated; similar problems are allowed.
- **Agreed**: Retries are bounded and exhaustion alerts an administrator.

### 2.2 Generation responsibilities
- **Agreed**: An LLM generates the English problem, solution, and rubric.
- **Agreed**: Static validation performs parsable, normalized, and objective checks first.
- **Agreed**: Jev evaluates quality, consistency, and difficulty after static preprocessing.
- **Agreed**: Jev is not a prose generator.
- **Agreed**: No expensive LLM fallback is used for grading in the current scope.

### 2.3 Content quality requirements
- **Agreed**: Each published problem has a versioned statement, official answer, explanation, rubric, difficulty, genre, format, and publication date.
- **Agreed**: The official answer/explanation is available before submission without penalty.
- **Agreed**: Exact duplicate detection blocks publication; semantic similarity alone does not.
- **Proposal**: Define configurable quality and confidence thresholds after calibration; no threshold value is agreed yet.

## 3. Rubric Model

### 3.1 Atomic requirements
- **Agreed**: Every problem rubric is a weighted list of atomic requirements relevant to that problem.
- **Agreed**: Applicable requirements may cover entities, attributes, keys, relationships, cardinality, normalization, and constraints.
- **Agreed**: Rubrics have no fixed category budgets.
- **Agreed**: The requirement-to-score mapping is configurable and frozen before assessment; every atomic weight is positive and the denominator is positive.
- **Agreed**: Before publication, Jev selects candidate importance categories for the problem and the selection is frozen.
- **Agreed**: Naming and extensibility are feedback-only; naming similarity is not a scoring proxy.
- **Agreed**: An implicit requirement must have sufficient textual derivation.
- **Agreed**: Implicit requirements can affect score and feedback but cannot be critical for passing.

### 3.2 Scoring
- **Agreed**: Score is calculated in deterministic arithmetic code:

`100 × sum(weights of satisfied atomic requirements) / sum(weights of all atomic requirements)`

- **Agreed**: No satisfied requirement yields 0; all satisfied requirements yield 100.
- **Agreed**: Display score to one decimal place only after calculating the exact score.
- **Agreed**: Jev pass/fail is separate from numeric scoring: pass requires all critical requirements and no design contradiction.
- **Agreed**: Missing noncritical requirements may still pass.

### 3.3 Assessment pipeline
- **Agreed**: Static preprocessing parses and normalizes the submission and performs objective checks first.
- **Agreed**: Jev makes only remaining semantic judgments.
- **Agreed**: Expression/function semantics that cannot be fully statically proven may require semantic handling rather than false certainty.
- **Agreed**: The result displays fulfilled and missing requirements, impact, confidence level (high/medium/low), and confidence percentage. Static checks are labeled “static verified” or “static not met” and receive no fabricated probability.
- **Agreed**: Confidence is explicitly presented as a warning, not a correctness guarantee.
- **Agreed**: Low-confidence assessment is still final; it does not trigger an expensive LLM fallback.

## 4. Versions, Integrity, and Corrections

- **Agreed**: Submission snapshots preserve the exact problem, rubric, and version used for scoring.
- **Agreed**: A correction produces future-version behavior only and does not rescore old submissions.
- **Agreed**: Translation and feedback caches use content version keys and invalidate when corrections are approved.

## 5. Validation Gates

- **Agreed**: Candidate generation must complete static validation before Jev evaluation.
- **Agreed**: Candidate publication requires passing quality/consistency/difficulty evaluation, no exact duplicate, and no exhausted retry state.
- **Agreed**: Rubric atomicity, weights, critical flags, textual derivations, and frozen category choices must validate before publication.
- **Agreed**: Result computation must finish the combined static and Jev satisfaction decisions before deterministic score arithmetic is stored.

## 6. Acceptance Criteria

- **AC-LEARN-001**: A monthly run creates candidates for the full month two months ahead, regenerates failures/exact duplicates within a bounded retry budget, and alerts an administrator if the budget is exhausted.
- **AC-LEARN-002**: Published problems collectively support the stated domains and daily randomization is independent for difficulty, genre, and format, without asserting an exact short-period balance.
- **AC-LEARN-003**: Easy, mid, and hard classification follows the stated knowledge/reasoning expectations and never relies solely on schema size or time bucket.
- **AC-LEARN-004**: Every published rubric contains weighted atomic requirements and validates that implicit requirements are textually derived and noncritical.
- **AC-LEARN-005**: Given a known satisfaction vector, the stored score equals the specified weighted formula; display rounding cannot convert a non-full score into 100-point eligibility, and a full score does not require the same answer or identical diagram as the official schema.
- **AC-LEARN-006**: A design with all critical requirements and no contradiction passes even with a missing noncritical item; a design missing a critical item or containing a contradiction fails.
- **AC-LEARN-007**: Results list fulfilled/missing requirements, impact, confidence label, and percentage, including for low-confidence final outcomes.
- **AC-LEARN-008**: A corrected problem version does not modify any historical submission snapshot or result.

---

# 日本語版

# 学習、課題、評価の要件

## 1. 学習スコープ

### 1.1 対応する設計領域
- **合意済み**: 課題は Web OLTP 設計を扱う。
- **合意済み**: 課題は、明示的な粒度と集計の推論を含む分析用スター スキーマを扱う。
- **合意済み**: 課題は正規化と再設計を扱う。
- **合意済み**: 異なる複数の有効なスキーマを受け入れ、公式スキーマとの完全一致は要求しない。適切な分析用非正規化を使用する場合も同様とする。
- **合意済み**: 課題は数学、集合、グラフの概念をデータベース設計へ変換することを扱う。

### 1.2 難易度の期待値
- **合意済み**: Easy の課題には一定のデータベース知識が必要で、多対多リレーションを含めることがある。
- **合意済み**: Mid の課題はサービス開発経験のあるユーザーを対象とする。
- **合意済み**: Hard の課題はスキーマが小さくても推論が難しい場合がある。
- **合意済み**: 規模は概して難易度とともに増えるが、エンティティ／テーブル数を Hard の定義にしてはならない。

## 2. 課題生成と公開

### 2.1 生成スケジュール
- **合意済み**: 月次バッチで 2 か月先の暦月全体を生成する。例として、9 月の生成では 11 月の課題を生成する。
- **デフォルト**: ローンチ時には、暦の空白を避けるために必要な中間月をブートストラップ生成で埋める。
- **合意済み**: 生成された候補ごとに静的チェックと Jev の品質チェックを実行する。
- **合意済み**: 失敗した候補と完全重複は再生成し、類似課題は許容する。
- **合意済み**: 再試行には上限を設け、枯渇時には管理者へアラートする。

### 2.2 生成の責務
- **合意済み**: LLM が英語の課題、解答、ルーブリックを生成する。
- **合意済み**: 静的検証で、解析可能性、正規化、客観性のチェックを先に行う。
- **合意済み**: Jev は静的前処理後に品質、一貫性、難易度を評価する。
- **合意済み**: Jev は文章生成器ではない。
- **合意済み**: 現行スコープでは採点に高コストの LLM フォールバックを使用しない。

### 2.3 コンテンツ品質要件
- **合意済み**: 公開される各課題には、バージョン付きの問題文、公式解答、解説、ルーブリック、難易度、ジャンル、形式、公開日がある。
- **合意済み**: 公式解答／解説は提出前にペナルティなしで利用できる。
- **合意済み**: 完全重複の検出は公開を阻止するが、意味的類似性だけでは阻止しない。
- **提案**: 調整後に設定可能な品質・信頼度のしきい値を定義する。しきい値の値はまだ合意されていない。

## 3. ルーブリックモデル

### 3.1 原子的要件
- **合意済み**: すべての課題のルーブリックは、その課題に関連する原子的要件の重み付きリストである。
- **合意済み**: 適用可能な要件は、エンティティ、属性、キー、リレーション、カーディナリティ、正規化、制約を対象にできる。
- **合意済み**: ルーブリックに固定カテゴリ予算はない。
- **合意済み**: 要件からスコアへのマッピングは設定可能で、評価前に凍結する。すべての原子的重みは正で、分母も正である。
- **合意済み**: 公開前に Jev が課題の候補重要カテゴリを選択し、その選択を凍結する。
- **合意済み**: 命名と拡張性はフィードバック専用であり、命名の類似性を採点の代替指標にしない。
- **合意済み**: 暗黙的要件には十分な本文上の導出が必要である。
- **合意済み**: 暗黙的要件はスコアとフィードバックに影響できるが、合格の必須条件にはできない。

### 3.2 採点
- **合意済み**: スコアは決定論的な算術コードで計算する:

`100 × sum(weights of satisfied atomic requirements) / sum(weights of all atomic requirements)`

- **合意済み**: 満たされた要件が 0 件なら 0、すべて満たせば 100 とする。
- **合意済み**: 表示スコアは正確なスコアを計算した後にのみ小数第 1 位へ丸める。
- **合意済み**: Jev の合否は数値採点とは別であり、合格にはすべてのクリティカル要件と設計上の矛盾がないことが必要である。
- **合意済み**: クリティカルでない要件が欠けていても合格できる場合がある。

### 3.3 評価パイプライン
- **合意済み**: 静的前処理で提出を解析・正規化し、客観的チェックを先に行う。
- **合意済み**: Jev は残った意味的判断のみを行う。
- **合意済み**: 完全に静的証明できない式／関数の意味は、誤った確実性を示すのではなく、意味処理が必要になる場合がある。
- **合意済み**: 結果には、満たした要件と不足要件、影響、信頼度レベル（high/medium/low）、信頼度パーセントを表示する。静的チェックには「static verified」または「static not met」とラベルを付け、確率を捏造しない。
- **合意済み**: 信頼度は正しさの保証ではなく、警告として明示する。
- **合意済み**: 信頼度の低い評価も最終結果であり、高コストの LLM フォールバックを起動しない。

## 4. バージョン、完全性、訂正

- **合意済み**: 提出スナップショットは採点に使用した正確な課題、ルーブリック、バージョンを保持する。
- **合意済み**: 訂正は将来のバージョンにのみ反映し、過去の提出を再採点しない。
- **合意済み**: 翻訳とフィードバックのキャッシュはコンテンツバージョンキーを使用し、訂正承認時に無効化する。

## 5. 検証ゲート

- **合意済み**: 候補生成は Jev 評価前に静的検証を完了しなければならない。
- **合意済み**: 候補公開には、品質／一貫性／難易度評価の合格、完全重複がないこと、再試行状態が枯渇していないことが必要である。
- **合意済み**: ルーブリックの原子性、重み、クリティカルフラグ、本文上の導出、凍結されたカテゴリ選択は公開前に検証しなければならない。
- **合意済み**: 結果計算は、決定論的なスコア算術を保存する前に、静的および Jev の満足判定を統合して完了しなければならない。

## 6. 受け入れ基準

- **AC-LEARN-001**: 月次実行で 2 か月先の 1 か月全体の候補を作成し、失敗／完全重複を上限付き再試行予算内で再生成し、予算枯渇時に管理者へアラートする。
- **AC-LEARN-002**: 公開課題全体で指定領域を支え、日次ランダム化は難易度、ジャンル、形式ごとに独立し、短期間の完全な均衡を主張しない。
- **AC-LEARN-003**: Easy、Mid、Hard の分類は指定された知識／推論の期待値に従い、スキーマサイズや時間帯だけに依存しない。
- **AC-LEARN-004**: 公開されるすべてのルーブリックに重み付き原子的要件が含まれ、暗黙的要件が本文から導出され、非クリティカルであることを検証する。
- **AC-LEARN-005**: 既知の満足ベクトルに対し、保存されたスコアが指定の重み付き公式と一致し、表示上の丸めで満点でないスコアが 100 点対象に変わらない。また、満点には公式スキーマと同じ解答や同一図であることを要求しない。
- **AC-LEARN-006**: すべてのクリティカル要件を満たし矛盾がない設計は、非クリティカル項目が欠けていても合格し、クリティカル項目の欠落または矛盾を含む設計は不合格となる。
- **AC-LEARN-007**: 結果には、信頼度の低い最終結果を含め、満たした／不足要件、影響、信頼度ラベル、パーセントを列挙する。
- **AC-LEARN-008**: 訂正された課題バージョンは、過去の提出スナップショットや結果を変更しない。
