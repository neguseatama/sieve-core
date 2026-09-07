# Sieve-Core (v1.0.0-MVP)

**[English](./README.md) | 日本語**

**決定論的な類似性・確信度検証エンジン(Explainable, General-Purpose)**  
*デマ・Bot拡散の自動縮約と、多重ソース検証によるノイズ除去*

[![PyPI Version](https://img.shields.io/pypi/v/sieve-core-engine.svg)](https://pypi.org/project/sieve-core-engine/)
[![Python Version](https://img.shields.io/pypi/pyversions/sieve-core-engine.svg)](https://pypi.org/project/sieve-core-engine/)
[![CI](https://github.com/neguseatama/sieve-core/actions/workflows/test.yml/badge.svg)](https://github.com/neguseatama/sieve-core/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

<!-- 注: このバッジは、neguseatamaアカウント上でリポジトリ名が "sieve-core" であることを前提にしています。別の名前でリポジトリを作成する場合は、上記URLを合わせて変更してください。 -->

---

## 📜 開発者ノート：なぜ「決定論的」にこだわるのか (Developer Notes)



### 1. 背景：情報量の増加とノイズの増加は比例する

デジタル化によるコピペコストの低下、SNSによる拡散の高速化、生成AIによる大量の要約・生成が組み合わさった結果、オンライン上の情報量は増え続けている一方で、その中に占めるコピペ・Bot拡散・裏付けのない主張の割合も増えています。企業や個人によるスピンコントロール(論点をずらす目的での情報の大量投下)や、Botによる組織的な世論誘導も、この「量の増加」を利用する手法の一つです。本プロジェクトは、こうした情報過多とノイズ増大に伴う課題に対し、データやテキストの真価を正確に抽出・フィルタリングする実用的な技術的アプローチを提供するために立ち上げました。



### 2. 問題設定：「要約」では解決しない

生成AIによる「要約」は情報量を圧縮しますが、要約対象そのものにノイズや偏りが多く含まれる場合、要約結果もその偏りを引き継ぎます。また要約は本質的に「新しい文を生成する」処理であり、ハルシネーションのリスクを内包します。



これに対し、本プロジェクトが着目したのは「抽出(Extraction)」というアプローチです。新しい文字列を生成するのではなく、既存のデータ集合から条件に合致する要素だけを機械的に選別する。この発想は、以前に開発した音楽同定AI「Sieve-AI」で採用した「集合論の篩」という設計思想の延長線上にあります。



### 3. 設計判断：LLMを判定の主体にしない

LLMを直接使って「これは真実か」を判定させる実装は多く存在しますが、LLM自身がハルシネーションを起こしうる以上、判定の主体をLLMに置くことは根本的な矛盾を抱えます。



そこで本プロジェクトでは、LLMを含む確率的な手法を判定の主体から外し、グラフ理論(Tarjan の強連結成分分解)と集合演算(n-gram Jaccard/Overlap係数)、そして独立ソース数に基づく決定論的なスコアリングだけで、判定過程を人間が最後まで追跡できる形にすることを優先しました。これにより「なぜこの結論になったか」を、確率的な内部状態を経由せずに説明できます(ただし、決定論的であることは、判定結果が真実であることを保証するものではありません。これはあくまで判定過程の説明可能性を担保する設計判断です)。



「エラトステネスの篩」に着想を得て設計した「集合論の篩」 Sieve-AI の設計思想を、より汎用的なテキスト・データ処理ドメインに適用したコアエンジンが Sieve-Core です。



---

## 💡 概要 (Overview)

**Sieve-Core** は、大量のデータから確定的な数理モデルによって、コピペ・Bot拡散を縮約し、複数の独立した情報源から裏付けられた項目を浮き彫りにする、オープンソースの**決定論的な類似性・確信度検証エンジン**です。ファクトチェックはその代表的な応用例の1つと位置づけています。

ブラックボックスなAI判定に頼らず、**「人間が追跡・説明でき、誰が実行しても同じ結果が得られるアルゴリズム」**によって、スピンコントロールやBot拡散の影響を検知・低減する手がかりを提供します。（内容の真偽そのものを判定するツールではなく、あくまで「独立した複数ソースからの裏付けの有無」を機械的に可視化するものです。）

---

## 💎 技術的ポジションと固有の強み (Core Virtues)

1. **可観測性（Auditability）とブラックボックス排除**
   * 「なぜその結論になったか」をグラフ構造（SCC）と明確な閾値（Jaccard/Sigmoid）で人間が追跡できます。盗用検知や事実確認のような、判定根拠の説明が求められる領域と相性の良い設計です（本MVPは限定的なデータセットでの検証にとどまるため、法的・制度的な運用には別途の検証が必要です）。
2. **Zero-Dependencies（標準ライブラリのみ）というコアの制約**
   * コアエンジン（`sieve_core.py`）はPythonの標準機能のみで完結し、外部ライブラリへの依存はありません。これによりポータビリティが高く、依存パッケージ由来の脆弱性リスクをコア部分に限っては排除できます。ただし、`density_fn`/`similarity_fn`に外部ライブラリ（Embeddingモデル等）を注入して使うこと自体は制限していません（後述のプラグイン拡張例を参照）。
3. **制御者としての決定論**
   * AIを結果の出力者ではなく、最外殻のアルゴリズム（競プロ的アプローチ）で縛る「評価関数/型変換器」として扱う設計思想。

---

## 🛡️ パイプライン構造 (Pipeline Architecture)

```
[ Raw Inputs ] （大量の投稿・報告書・コピペ・Botデータ）
      │
      ▼
┌────────────────────────────────────────┐
│ 1. 密度スコアフィルタ (`density_fn`)    │  ← 煙幕・感嘆文・低情報量ノイズの削除
└────────────────────────────────────────┘
      │
      ▼
┌────────────────────────────────────────┐
│ 2. Tarjan SCC グラフ縮約                │  ← 確定的な強連結成分分解でコピペ/Bot拡散を閉路縮約
└────────────────────────────────────────┘
      │
      ▼
┌────────────────────────────────────────┐
│ 3. 決定論的 n-gram 平均連結法統合        │  ← 確率（LSH）を排除し、クラスタ間平均類似度で表記揺れを統合
└────────────────────────────────────────┘
      │
      ▼
┌────────────────────────────────────────┐
│ 4. シグモイド確信度スコアリング          │  ← 独立ソース数 (k_roles) に基づく数理評価
└────────────────────────────────────────┘
      │
      ▼
[ Verified Outputs ] （独立ソース数に基づく確信度スコア付きの、検証済みファクト候補）
```

---

## 💻 コアアルゴリズム実装 (Engine Architecture)

エンジン本体は [`sieve_core.py`](./sieve_core.py) にあります（外部ライブラリ非依存、単一ファイル）。
README にソース全文を貼り付けると更新のたびに二重管理になりズレるため、
ここでは最小限の使用例のみを示します。

```python
from sieve_core import GenericItemInput, SieveCoreEngine

items = [
    GenericItemInput(item_id="p1", author_id="user_a", author_role="citizen", content="..."),
    GenericItemInput(item_id="p2", author_id="reporter_b", author_role="media", content="..."),
    # ...
]

engine = SieveCoreEngine()
results, stats = engine.process(items)

for fact in results:
    print(fact.fact_id, fact.confidence_score, fact.independent_sources_count)
```

このコード片は API の呼び出し方(=`process()`に渡すデータの形と、結果の受け取り方)を示すための最小構成であり、単発の投稿を数件渡しただけでは独立ソース数が1のままなので、確信度は低めの値になります。複数の独立した情報源が同一の事実を裏付けた場合に確信度が跳ね上がる、という本来の挙動を実際の数値で確認したい場合は [`example.py`](./example.py) を実行してください。

主要クラスは3つです。

| クラス | 役割 |
| :--- | :--- |
| `GenericItemInput` | 投入する1件のデータ（ID・投稿者・独立属性・本文） |
| `SieveCoreEngine` | 密度フィルタ → SCC縮約 → クラスタ統合 → 確信度スコアリングの4段パイプライン本体 |
| `FactClusterOutput` | 抽出結果（代表テキスト・件数・独立ソース数・確信度） |

詳細な内部実装（Tarjan SCC・平均連結法Jaccard／Overlap係数・シグモイド確信度関数など）は `sieve_core.py` を直接参照してください。挙動は以下2つの回帰テストで担保されています。

* `test_sieve_core.py` — コアエンジン単体の挙動（重複ID検出、密度フィルタ、SCC縮約、chaining対策、空入力等）
* `test_multi_domain.py` — SNS短文・ソースコード・長文ニュースという性質の異なる3ドメインを横断した実証テスト

```bash
python3 -m unittest test_sieve_core.py test_multi_domain.py -v
```

---

## ⚙️ プラグイン拡張例 (Advanced Usage: Custom Evaluators)

`Sieve-Core` は `density_fn`（情報密度評価）と `similarity_fn`（類似度評価）の両方にカスタム関数を注入することで、形態素解析やLLM、あるいはコード専用の比較ロジックまで「最外殻アルゴリズムに従う評価パーツ」として利用可能です。

### 例1: LLMを軽量ファクト密度評価器として注入する
```python
def llm_based_density_evaluator(text: str) -> float:
    # LLMには要約や真偽判定を任せず、「テキスト中の具体的な情報事実の割合(0.0〜1.0)」のみを出力させる
    # LLMの出力を決定論的パイプラインの入力値として制御
    response = call_mini_llm(f"Rate factual density of this text from 0.0 to 1.0: {text}")
    try:
        return float(response.strip())
    except ValueError:
        return 0.0

# エンジンに注入
results, stats = engine.process(items, density_fn=llm_based_density_evaluator)
```

### 例2: 日本語向けの密度・類似度評価器を注入する
デフォルトの `density_fn`（文字ユニーク率）や `similarity_fn`（文字n-gram Jaccard）は言語非依存の汎用フォールバックであり、日本語の雑談・感情論ノイズを十分にはフィルタできません。日本語で実運用する場合は、漢字・数値の含有率のような言語特有のヒューリスティックと、助詞・定型句を除去したうえでの類似度評価をセットで注入することを推奨します（`example.py` に完全な実行例があります）。

```python
import re

STOP_PATTERNS = re.compile(r"(拡散希望|拡散|速報|本日|現在|確認中|発生|です|ます|から|より|で|に|を|が|は|の|と)")

def japanese_density_fn(text: str) -> float:
    """漢字・数字の含有率が高いほど、感想文ではなく具体的な報告である可能性が高いという経験則"""
    if not text:
        return 0.0
    return len(re.findall(r"[一-龥0-9]", text)) / len(text)

def japanese_similarity_fn(a: str, b: str) -> float:
    """助詞・定型句を除去したうえでの2-gram重複係数(Overlap Coefficient)。
    Jaccard係数だと、文章量が非対称なペア(短い速報 vs 長い目撃談)で
    共通語があっても和集合が膨らみ過小評価されることを実測で確認したため、
    分母を「短い方の集合サイズ」にする重複係数を採用している。"""
    def grams(text):
        cleaned = STOP_PATTERNS.sub("", text)
        return {cleaned[i:i+2] for i in range(len(cleaned) - 1)} if len(cleaned) >= 2 else {cleaned}
    ga, gb = grams(a), grams(b)
    if not ga or not gb:
        return 0.0
    return len(ga & gb) / min(len(ga), len(gb))

results, stats = engine.process(items, density_fn=japanese_density_fn, similarity_fn=japanese_similarity_fn)
```

### 例3: `similarity_fn` を注入し、コードの重複検出に対応させる
```python
import difflib

def normalized_code_similarity(a: str, b: str) -> float:
    def normalize(code: str) -> str:
        code = re.sub(r"#.*", "", code)          # コメント除去
        code = re.sub(r"\s+", " ", code).strip()  # 空白の正規化
        return code
    return difflib.SequenceMatcher(None, normalize(a), normalize(b)).ratio()

# コード向けは exact_sim_threshold / jaccard_merge_threshold を高めに引き上げる必要がある。
# 実測したところ、`def add(a,b): return a+b` と `def multiply(a,b): return a*b` は
# 演算子1文字しか違わないのに、定型構造(def・括弧・return)を共有するため
# 文字diff比率が0.75まで跳ね上がり、デフォルト閾値(0.65 / 0.15)のままでは
# 誤って同一ファクトに統合されてしまうことを確認した。
code_engine = SieveCoreEngine(exact_sim_threshold=0.9, jaccard_merge_threshold=0.8)
results, stats = code_engine.process(code_items, similarity_fn=normalized_code_similarity)
```

> **注意**: 文字単位のdiff比率は、定型構造を共有しやすいコードのようなドメインでは
> 本質的に脆弱な指標です（上記の例でも閾値0.75〜0.94という狭い隙間に頼っています）。
> 実運用でコードの類似性を厳密に検証したい場合は、`similarity_fn`にASTベースの構造比較
> （関数名や変数名を正規化した上での構文木の一致度など）を注入することを推奨します。

---

## ⚠️ 既知の限界 (Known Limitations)

実装・検証の過程で実際に見つかった、現在の MVP（v1.0）における構造的な限界です。

1. **クラスタ統合における Chaining 問題**
   単連結法（Single-Linkage: 2クラスタ間の「最大」類似度で統合判定）は、AとB、BとCが部分的に似ているだけで無関係なAとCまで連鎖的に統合してしまう弱点がある。現在は平均連結法（Average-Linkage: クラスタ間の「平均」類似度で判定）に切り替えて緩和しているが、閾値のチューニング次第では依然として発生しうる。
2. **Jaccard係数は非対称な文章量のペアを過小評価する**
   短い速報文と長い目撃談のように、片方が大幅に詳細な文章の場合、核心語が共通していてもJaccard係数（`交差 / 和集合`）は和集合の肥大化により類似度を過小評価しやすい。重複係数（Overlap Coefficient: `交差 / min(集合サイズ)`）に切り替えることで緩和できることを実測で確認している（`test_multi_domain.py` 参照）。
3. **定型構造ドメイン（コード等）における類似度算出の脆弱性**
   文字単位や単純なn-gramベースのJaccard/diff比率は、定型構文（`def ...` や括弧、予約語）を多く共有するソースコード等のドメインで誤動作しやすい。AST（抽象構文木）ベースの構造比較関数を `similarity_fn` に注入する必要がある。
4. **閾値パラメータのドメイン依存性**
   `exact_sim_threshold` や `jaccard_merge_threshold` は、いずれのドメインでも実験的に調整が必要であり、汎用的に安全なデフォルト値は存在しない。SNS短文・コード・長文ニュースの3ドメインで動作検証はしているが（`test_multi_domain.py`）、各テストケースは数件規模であり、実データでの大規模な頑健性は未検証。
5. **スケール**: 現状 $O(N^2)$ のペア比較を採用しています。実測(下記ベンチマーク参照)では、件数が増えるとおおむね理論通り $N^2$ で処理時間が伸びるため、快適に使えるのは概ね数百件程度までで、1,000件を超えると数秒〜十数秒の待ち時間が発生し始めます。数千件規模の一括処理を前提とする場合は、下記ロードマップの前処理ブロッキングの実装が事実上必須になります。

**実測ベンチマーク** (手元の検証環境で1回計測した参考値。実行環境・`density_fn`/`similarity_fn`の実装コストにより変動する)

| 件数 (N) | 処理時間 (秒) |
| :--- | :--- |
| 50 | 約0.02 |
| 100 | 約0.08 |
| 250 | 約0.48 |
| 500 | 約1.9 |
| 1,000 | 約7.1 |
| 2,000 | 約28.6 |

N=1,000→2,000で処理時間がおよそ4倍になっており、$O(N^2)$ の理論値と実測がおおむね一致していることを確認している。この表は [`benchmark.py`](./benchmark.py) の実行結果であり、`python3 benchmark.py` で自分の環境でも再現できる。

---

## 🚀 将来的ロードマップ (v2.0 Performance Roadmap)

現在のMVP（v1.0）は決定論的精度を最優先し、$O(N^2)$ のペア比較を採用しています。実測では数百件規模までは実用的な速度で動作しますが、1,000件を超えると処理時間が目に見えて伸びます（詳細は「既知の限界」のベンチマーク表を参照）。数千〜数万件規模の超大規模データへの拡張として、以下の決定論的プレ・スクリーニング構造を計画しています。

* **決定論的バケット分割 (Deterministic Pre-bucket Blocking)**
  * LSH（確率的ハッシュ）に頼らず、出現頻度の低い特徴量キーワード（レアn-gram）やコンテキスト属性をキーとする決定論的バケット（ブロック）へ前処理で分割。
  * 比較対象ペアをブロック内に限定することで、決定論的な100%可観測性を維持したまま、実効計算量を $O(N)$ 〜 $O(N \log N)$ に圧縮します。

---

## 🛠️ パラメータ設定ガイド

| パラメータ名 | 初期値 | 目的・説明 |
| :--- | :--- | :--- |
| `density_threshold` | `0.35` | 情報密度の下限。専門用語の煙幕や感情的ノイズを排除。 |
| `exact_sim_threshold` | `0.65` | Tarjan SCC で強連結（Botコピペ・アストロターフィング）とみなす縮約閾値。 |
| `jaccard_merge_threshold` | `0.15` | 表記揺れ（揺らぎ）を平均連結法でクラスタリング統合する閾値。 |
| `sigmoid_alpha` | `3.0` | 独立ロール数増加に対する確信度上昇の感度（傾き）。 |
| `sigmoid_k0` | `1.5` | 確信度 50% となる独立ロール数の変曲点。 |

---

## 🌐 想定する利用シーン

`Sieve-Core` は、中央集権的なプラットフォームの判定に頼らず、ユーザー自身の手元(ローカル環境)で動作させることを想定しています。

具体的には、大量の投稿やコメントの中から、コピペ・Bot拡散による「見かけ上の量」を差し引いた上で、複数の独立した情報源から裏付けられた項目を機械的に絞り込む、という使い方を想定しています(万能の防御策ではなく、一次的なフィルタとしての位置づけです)。

---

## 📄 ライセンス (License)

本プロジェクトは [MIT License](LICENSE) のもとで公開されています。

---

## 🤝 貢献について (Contributing)

バグ報告・機能提案・プルリクエストを歓迎します。設計原則や貢献の手順は[CONTRIBUTING.md](CONTRIBUTING.md)(英語)、コミュニティ内でのやり取りの行動規範は[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)(英語)を参照してください。セキュリティ上の脆弱性を見つけた場合は、公開のIssueではなく[SECURITY.md](.github/SECURITY.md)(英語)の手順に従ってください。

---

## 👤 Author

* **Kai IWASAKI**
