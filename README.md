# Sieve-Core (v1.0.0-MVP)

**English | [日本語](./README.ja.md)**

**A deterministic similarity / confidence verification engine (Explainable, General-Purpose)**  
*Deterministic collapsing of copy-paste and bot amplification, and noise reduction via multi-source corroboration*

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Dependencies](https://img.shields.io/badge/dependencies-zero-success.svg)](#)
[![Tests](https://github.com/neguseatama/sieve-core/actions/workflows/tests.yml/badge.svg)](https://github.com/neguseatama/sieve-core/actions/workflows/tests.yml)

<!-- NOTE: this badge assumes the repo is named "sieve-core" under the neguseatama account. If you name the repo something else on GitHub, update the URL above to match. -->

---

## 📜 Developer Notes: Why "Deterministic"?

### 1. Background: information volume and noise grow together
The combination of falling copy-paste costs (digitization), faster amplification (social media), and large-scale summarization/generation (generative AI) means the total volume of information online keeps increasing. At the same time, the share of that volume made up of copy-paste, bot amplification, and unsubstantiated claims is also increasing. Spin control by companies or individuals (flooding a topic with information to shift the conversation) and coordinated bot-driven opinion manipulation are both techniques that exploit this growth in sheer volume.

### 2. The problem: "summarization" doesn't solve this
AI-generated "summarization" compresses information, but if the source material itself contains a lot of noise or bias, the summary inherits that bias. Summarization is also, by nature, a process of "generating a new sentence," which carries an inherent risk of hallucination.

This project instead focuses on "extraction": rather than generating new sentences, it mechanically selects only the elements from an existing data set that satisfy given conditions. This idea is a direct extension of the "sieve of set theory" design used in an earlier project of mine, a music-identification AI called "Sieve-AI."

### 3. Design decision: LLMs are not the decision-maker
Many existing implementations use an LLM directly to judge "is this true or not." But since an LLM can itself hallucinate, putting the LLM at the center of that judgment creates a fundamental contradiction.

So this project deliberately keeps LLMs and other probabilistic methods out of the decision-making core. Judgments are made entirely through graph theory (Tarjan's strongly connected components), set operations (n-gram Jaccard / overlap coefficient), and a deterministic scoring function based on the count of independent sources — so that a human can trace the entire decision path. This lets us explain "why this conclusion was reached" without going through any probabilistic internal state. (To be clear: being deterministic does not guarantee that the output is true. It is a design choice that guarantees the explainability of the decision process, not the correctness of its content.)

`Sieve-Core` applies the thinking behind Sieve-AI — itself inspired by the Sieve of Eratosthenes — to the more general domain of text/data processing.

---

## 💡 Overview

**Sieve-Core** is an open-source **deterministic similarity / confidence verification engine** that uses deterministic mathematical models to collapse copy-paste and bot amplification within a large data set, and surface items that are corroborated by multiple independent sources. Fact-checking is one representative application, not the only one.

Instead of relying on black-box AI judgments, it provides a way to detect and reduce the influence of spin control and bot amplification using **"an algorithm a human can trace and explain, that produces the same result no matter who runs it."** (This is not a tool that judges the truth of content itself — it mechanically visualizes whether or not something is corroborated by multiple independent sources.)

---

## 💎 Core Virtues

1. **Auditability, with no black box**
   * Every conclusion can be traced by a human through explicit graph structure (SCC) and explicit thresholds (Jaccard / Sigmoid). This design fits domains such as plagiarism detection or fact-checking where the reasoning behind a judgment needs to be explainable (this MVP has only been validated on limited data sets, so any legal or institutional use would require separate validation).
2. **Zero-Dependencies as a constraint on the core**
   * The core engine (`sieve_core.py`) is self-contained using only Python's standard library, with no external dependencies. This gives it strong portability and removes, for the core itself, any risk from third-party package vulnerabilities. This does not restrict you from injecting external libraries (e.g. an embedding model) into `density_fn` / `similarity_fn` — see the plugin examples below.
3. **Determinism as a controller**
   * A design philosophy in which AI is not the source of the final output, but is instead constrained by the outermost algorithm (a competitive-programming-style approach) acting as an "evaluation function / type converter."

---

## 🛡️ Pipeline Architecture

```
[ Raw Inputs ] (a large volume of posts, reports, copy-paste, bot data)
      │
      ▼
┌────────────────────────────────────────┐
│ 1. Density score filter (`density_fn`)  │  ← removes smokescreen text, filler, low-information noise
└────────────────────────────────────────┘
      │
      ▼
┌────────────────────────────────────────┐
│ 2. Tarjan SCC graph reduction           │  ← deterministic strongly-connected-components collapse of copy-paste / bot loops
└────────────────────────────────────────┘
      │
      ▼
┌────────────────────────────────────────┐
│ 3. Deterministic average-linkage merge  │  ← no probabilistic (LSH) step; merges paraphrases via inter-cluster average similarity
└────────────────────────────────────────┘
      │
      ▼
┌────────────────────────────────────────┐
│ 4. Sigmoid confidence scoring           │  ← mathematical scoring based on independent source count (k_roles)
└────────────────────────────────────────┘
      │
      ▼
[ Verified Outputs ] (verified fact candidates with a confidence score based on independent source count)
```

---

## 💻 Engine Architecture

The engine itself lives in [`sieve_core.py`](./sieve_core.py) (no external dependencies, single file).
Pasting the full source into the README would create a second copy that drifts out of sync every time the code changes, so only a minimal usage example is shown here.

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

This snippet is the minimal shape of the API call (the input data shape passed to `process()`, and how results are read back). With only a handful of single, unrelated posts, the independent source count stays at 1, so the confidence score will be low. To see the actual behavior that Sieve-Core is built around — confidence spiking once multiple independent sources corroborate the same fact — run [`example.py`](./example.py).

There are three main classes:

| Class | Role |
| :--- | :--- |
| `GenericItemInput` | One unit of input data (ID, author, independent attribute, content) |
| `SieveCoreEngine` | The 4-stage pipeline body: density filter → SCC reduction → cluster merge → confidence scoring |
| `FactClusterOutput` | The extraction result (representative text, item count, independent source count, confidence) |

For the internal implementation details (Tarjan SCC, average-linkage Jaccard / overlap coefficient, the sigmoid confidence function, etc.), read `sieve_core.py` directly. Its behavior is backed by two regression test suites:

* `test_sieve_core.py` — behavior of the core engine in isolation (duplicate-ID detection, density filter, SCC reduction, chaining mitigation, empty input, etc.)
* `test_multi_domain.py` — cross-domain validation across three qualitatively different domains: short-form SNS text, source code, and long-form news articles

```bash
python3 -m unittest test_sieve_core.py test_multi_domain.py -v
```

---

## ⚙️ Plugin Extension Examples (Advanced Usage: Custom Evaluators)

`Sieve-Core` lets you inject custom functions into both `density_fn` (information density evaluation) and `similarity_fn` (similarity evaluation), so anything from a morphological analyzer to an LLM, or a code-specific comparison routine, can be plugged in as "an evaluation part that answers to the outermost algorithm."

### Example 1: Injecting an LLM as a lightweight fact-density evaluator
```python
def llm_based_density_evaluator(text: str) -> float:
    # Don't let the LLM summarize or judge truth — have it output only
    # "what fraction of this text is concrete, factual content (0.0-1.0)"
    # so its output becomes a controlled input value inside the deterministic pipeline.
    response = call_mini_llm(f"Rate factual density of this text from 0.0 to 1.0: {text}")
    try:
        return float(response.strip())
    except ValueError:
        return 0.0

# Inject into the engine
results, stats = engine.process(items, density_fn=llm_based_density_evaluator)
```

### Example 2: Injecting density/similarity evaluators for Japanese
The default `density_fn` (unique-character ratio) and `similarity_fn` (character n-gram Jaccard) are language-agnostic, general-purpose fallbacks, and they do not adequately filter Japanese chit-chat or emotional noise. For real-world use with Japanese text, we recommend injecting a language-specific heuristic (kanji/numeral density) together with a similarity function that strips particles and boilerplate phrases before comparing (see `example.py` for a complete working example).

```python
import re

STOP_PATTERNS = re.compile(r"(拡散希望|拡散|速報|本日|現在|確認中|発生|です|ます|から|より|で|に|を|が|は|の|と)")

def japanese_density_fn(text: str) -> float:
    """Heuristic: the higher the ratio of kanji/numerals, the more likely
    this is a concrete report rather than an opinion or reaction."""
    if not text:
        return 0.0
    return len(re.findall(r"[一-龥0-9]", text)) / len(text)

def japanese_similarity_fn(a: str, b: str) -> float:
    """2-gram overlap coefficient after stripping particles/boilerplate.
    We measured that plain Jaccard underestimates similarity for
    asymmetric-length pairs (a short breaking-news post vs. a long
    eyewitness account) even when they share the core vocabulary,
    because the union grows with the extra detail. The overlap
    coefficient (dividing by the smaller set's size) avoids this."""
    def grams(text):
        cleaned = STOP_PATTERNS.sub("", text)
        return {cleaned[i:i+2] for i in range(len(cleaned) - 1)} if len(cleaned) >= 2 else {cleaned}
    ga, gb = grams(a), grams(b)
    if not ga or not gb:
        return 0.0
    return len(ga & gb) / min(len(ga), len(gb))

results, stats = engine.process(items, density_fn=japanese_density_fn, similarity_fn=japanese_similarity_fn)
```

### Example 3: Injecting `similarity_fn` for source-code duplicate detection
```python
import difflib

def normalized_code_similarity(a: str, b: str) -> float:
    def normalize(code: str) -> str:
        code = re.sub(r"#.*", "", code)          # strip comments
        code = re.sub(r"\s+", " ", code).strip()  # normalize whitespace
        return code
    return difflib.SequenceMatcher(None, normalize(a), normalize(b)).ratio()

# For code, exact_sim_threshold / jaccard_merge_threshold need to be raised.
# We measured that `def add(a,b): return a+b` and `def multiply(a,b): return a*b`
# differ by a single operator, yet because they share so much boilerplate
# (def, parentheses, return), their character-diff ratio reaches 0.75 —
# high enough that the default thresholds (0.65 / 0.15) would incorrectly
# merge them into the same fact.
code_engine = SieveCoreEngine(exact_sim_threshold=0.9, jaccard_merge_threshold=0.8)
results, stats = code_engine.process(code_items, similarity_fn=normalized_code_similarity)
```

> **Note**: character-level diff ratios are fundamentally fragile in domains like source
> code, where boilerplate structure is heavily shared (the example above relies on a narrow
> 0.75–0.94 gap between thresholds). If you need rigorous code-similarity comparison in
> production, we recommend injecting an AST-based structural comparison into `similarity_fn`
> (e.g. matching syntax trees after normalizing function/variable names).

---

## ⚠️ Known Limitations

These are structural limitations of the current MVP (v1.0), found through actual implementation and testing.

1. **Chaining in cluster merging**
   Single-linkage merging (deciding to merge two clusters based on the *maximum* similarity between any pair of members) can transitively merge unrelated items A and C just because A-B and B-C are each partially similar. The current implementation mitigates this by using average-linkage (deciding based on the *average* similarity across all cross-cluster pairs), but the problem can still resurface depending on threshold tuning.
2. **Jaccard similarity underestimates asymmetric-length pairs**
   When one text is much more detailed than the other (e.g. a short breaking-news post vs. a long eyewitness account), Jaccard similarity (`intersection / union`) tends to underestimate similarity because the union grows with the extra length, even when the core vocabulary is shared. We confirmed, empirically, that switching to the overlap coefficient (`intersection / min(set sizes)`) mitigates this (see `test_multi_domain.py`).
3. **Fragility of similarity scoring in boilerplate-heavy domains (e.g. code)**
   Character-level or naive n-gram-based Jaccard/diff similarity tends to misfire in domains like source code, which shares a lot of fixed syntax (`def ...`, parentheses, reserved words). You need to inject an AST-based structural comparison into `similarity_fn` for that domain.
4. **Threshold parameters are domain-dependent**
   `exact_sim_threshold` and `jaccard_merge_threshold` both require empirical tuning for any given domain; there is no universally safe default. We have validated behavior across three domains (short-form SNS text, source code, long-form news — see `test_multi_domain.py`), but each test case is only a handful of items, and robustness at real-world scale is untested.
5. **Scale**: the engine currently uses $O(N^2)$ pairwise comparison. Measured (see the benchmark below), processing time grows roughly with $N^2$ as the item count increases, so it stays comfortable up to roughly a few hundred items; past 1,000 items you start seeing wait times of several seconds to tens of seconds. If you need to process on the order of thousands of items in one batch, the pre-filtering block structure described in the roadmap below becomes effectively mandatory.

**Measured benchmark** (a single measurement from a local development environment; actual numbers will vary with your environment and the cost of your `density_fn` / `similarity_fn` implementations. Note also that the true complexity is closer to $O(N^2 \times L)$, where $L$ is average text length — these numbers were measured on English text, which needs roughly 2-3x more characters than Japanese to express the same content, so per-pair comparison cost is correspondingly higher than the Japanese-text benchmark in [README.ja.md](./README.ja.md))

| N (items) | Time (sec) |
| :--- | :--- |
| 50 | ~0.04 |
| 100 | ~0.14 |
| 250 | ~0.87 |
| 500 | ~3.5 |
| 1,000 | ~14.3 |
| 2,000 | ~57.2 |

Going from N=1,000 to N=2,000 roughly quadruples the processing time, which is consistent with the theoretical $O(N^2)$ scaling. This table is the output of [`benchmark.py`](./benchmark.py); run `python3 benchmark.py` to reproduce it on your own machine.

---

## 🚀 Roadmap (v2.0 Performance Roadmap)

The current MVP (v1.0) prioritizes deterministic precision and uses $O(N^2)$ pairwise comparison. Measured performance is practical up to roughly a few hundred items, but processing time grows noticeably past 1,000 items (see the benchmark table under "Known Limitations"). To scale to tens of thousands of items or more, the following deterministic pre-screening structure is planned:

* **Deterministic Pre-bucket Blocking**
  * Instead of relying on LSH (probabilistic hashing), pre-partition items into deterministic buckets keyed on low-frequency feature keywords (rare n-grams) or context attributes.
  * By limiting comparisons to pairs within the same bucket, this compresses the effective complexity to roughly $O(N)$–$O(N \log N)$ while preserving full deterministic observability.

---

## 🛠️ Parameter Guide

| Parameter | Default | Purpose |
| :--- | :--- | :--- |
| `density_threshold` | `0.35` | Minimum information density. Filters out smokescreen jargon and emotional noise. |
| `exact_sim_threshold` | `0.65` | The similarity threshold above which Tarjan SCC treats two items as strongly connected (bot copy-paste / astroturfing). |
| `jaccard_merge_threshold` | `0.15` | The threshold at which average-linkage merges clusters to account for paraphrasing/variation. |
| `sigmoid_alpha` | `3.0` | The steepness of the confidence curve's response to an increase in independent role count. |
| `sigmoid_k0` | `1.5` | The inflection point: the independent role count at which confidence crosses 50%. |

---

## 🌐 Intended Use Cases

`Sieve-Core` is designed to run on the user's own machine, rather than depending on judgments made by a centralized platform.

Concretely, it is intended for cases like: given a large volume of posts or comments, discount the "apparent volume" created by copy-paste and bot amplification, and mechanically narrow down to items corroborated by multiple independent sources (this is not a silver-bullet defense — it is meant as a first-pass filter).

---

## 📄 License

This project is released under the [MIT License](LICENSE).

---

## 🤝 Contributing

Bug reports, feature proposals, and pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for the project's design principles and the contribution workflow, and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for the standards we hold community interactions to. If you find a security vulnerability, please follow the process in [SECURITY.md](.github/SECURITY.md) rather than filing a public issue.

---

## 👤 Author

* **Kai IWASAKI**
