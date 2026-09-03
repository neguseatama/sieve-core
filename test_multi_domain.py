"""
Multi-Domain Benchmark Test Suite for Sieve-Core (v1.0.0-MVP)
Standard Library Only (Zero-Dependencies)

Note: the SNS and news-article test cases below use real Japanese sample
text on purpose. They exercise `sns_density_fn` / `sns_similarity_fn`,
which are Japanese-specific evaluators (kanji-density heuristics, particle
stripping); translating the sample text to English would defeat the point
of the test. The source-code domain naturally uses English/Python already.
"""

import re
import difflib
import unittest
from sieve_core import GenericItemInput, SieveCoreEngine


STOP_PATTERNS = re.compile(
    r"(拡散希望|拡散|速報|本日|現在|確認中|発生|です|ます|ていま|した|から|より|で|に|を|が|は|の|と|も|や|か|な|ね|よ)"
)

def sns_density_fn(text: str) -> float:
    if not text:
        return 0.0
    return len(re.findall(r"[一-龥0-9]", text)) / len(text)

def sns_similarity_fn(a: str, b: str) -> float:
    """
    Overlap coefficient: |A∩B| / min(|A|,|B|)

    We originally used the Jaccard coefficient (|A∩B|/|A∪B|), but running it
    revealed a real problem: for asymmetric-length pairs like a short
    breaking-news post vs. a long eyewitness account, even when they share
    a core term (e.g. "tsunami warning"), the union grows so much that
    similarity gets underestimated (s1-s4 similarity was only 0.079, which
    dropped the independent-source count from the expected 3 to 2 and broke
    the test). The overlap coefficient avoids this underestimation by
    dividing by the size of the smaller set instead.
    """
    clean_a = STOP_PATTERNS.sub("", a)
    clean_b = STOP_PATTERNS.sub("", b)
    def extract_2gram(text: str):
        if len(text) < 2:
            return {text} if text else set()
        return {text[i:i+2] for i in range(len(text) - 1)}
    grams_a, grams_b = extract_2gram(clean_a), extract_2gram(clean_b)
    if not grams_a or not grams_b:
        return 0.0
    intersection = len(grams_a & grams_b)
    return intersection / min(len(grams_a), len(grams_b))


def code_similarity_fn(a: str, b: str) -> float:
    def normalize(code: str) -> str:
        code = re.sub(r"#.*", "", code)
        code = re.sub(r"\s+", " ", code).strip()
        return code
    return difflib.SequenceMatcher(None, normalize(a), normalize(b)).ratio()


class TestMultiDomainValidation(unittest.TestCase):

    def test_domain_sns_disaster_logs(self):
        """
        Domain: short-form social-media disaster reports.
        Validates that bot/media/citizen (3 independent roles) reporting the
        same event get merged, pushing confidence above 0.90, while an
        unrelated spam post is excluded. Uses real Japanese sample text
        since this exercises the Japanese-specific density/similarity
        functions defined above.
        """
        items = [
            GenericItemInput("s1", "bot_a", "bot", "【速報】〇〇県沖で地震が発生。津波警報が発令されました。"),
            GenericItemInput("s2", "bot_b", "bot", "【速報】〇〇県沖で地震が発生。津波警報が発令されました。"),
            GenericItemInput("s3", "nhk_news", "media", "〇〇県沖で強い地震。気象庁が沿岸部に津波警報を発令。"),
            GenericItemInput("s4", "user_chiba", "citizen", "海岸近くにいますが津波警報のサイレンが鳴っています！高台へ避難中。"),
            GenericItemInput("s5", "spam_bot", "anonymous", "地震ヤバ！無料でコインがもらえるサイトはこちら→ http://example.com"),
        ]
        engine = SieveCoreEngine(density_threshold=0.20, exact_sim_threshold=0.60, jaccard_merge_threshold=0.10)
        results, stats = engine.process(items, density_fn=sns_density_fn, similarity_fn=sns_similarity_fn)
        print("SNS domain stats:", stats)
        for r in results:
            print(" ", r.fact_id, r.confidence_score, r.independent_sources_count, r.item_ids)
        self.assertGreaterEqual(len(results), 1)
        top_fact = results[0]
        self.assertEqual(top_fact.independent_sources_count, 3)
        self.assertGreater(top_fact.confidence_score, 0.90)

    def test_domain_source_code_duplication(self):
        """
        Domain: source-code duplicate detection.
        Validates that a function renamed/reformatted with different
        variable names and comments (c1 vs c2) is still recognized as a
        duplicate via `code_similarity_fn`, while a genuinely different
        function (c3) stays separate.
        """
        code_v1 = """
        def compute_factorial(n: int) -> int:
            # Calculate factorial iteratively
            if n < 0:
                raise ValueError("Negative number")
            res = 1
            for i in range(1, n + 1):
                res *= i
            return res
        """
        code_v2_renamed = """
        def compute_factorial(val: int) -> int:
            # Different comment: compute result
            if val < 0:
                raise ValueError("Negative number")
            total = 1
            for x in range(1, val + 1):
                total *= x
            return total
        """
        code_different = """
        def quick_sort(arr: list) -> list:
            if len(arr) <= 1:
                return arr
            pivot = arr[len(arr) // 2]
            left = [x for x in arr if x < pivot]
            middle = [x for x in arr if x == pivot]
            right = [x for x in arr if x > pivot]
            return quick_sort(left) + middle + quick_sort(right)
        """
        items = [
            GenericItemInput("c1", "dev_a", "repo_main", code_v1),
            GenericItemInput("c2", "dev_b", "repo_fork", code_v2_renamed),
            GenericItemInput("c3", "dev_c", "repo_other", code_different),
        ]
        engine = SieveCoreEngine(density_threshold=0.10, exact_sim_threshold=0.85, jaccard_merge_threshold=0.75)
        results, stats = engine.process(items, density_fn=lambda t: 0.5, similarity_fn=code_similarity_fn)
        print("Code domain stats:", stats)
        for r in results:
            print(" ", r.fact_id, r.item_ids)
        self.assertEqual(len(results), 2)
        top_fact = results[0]
        self.assertIn("c1", top_fact.item_ids)
        self.assertIn("c2", top_fact.item_ids)

    def test_domain_news_articles(self):
        """
        Domain: long-form news articles.
        Validates that two articles covering the same monetary-policy
        decision get merged, while an unrelated local-news article does
        not get chained in. Uses real Japanese sample text since this
        exercises the Japanese-specific density/similarity functions
        defined above.
        """
        article_a = "中央銀行は本日、インフレ抑制を目的として政策金利を0.25%引き上げると発表した。市場関係者の予想通りの決定となった。"
        article_b = "金融政策決定会合にて、中央銀行が0.25%の利上げを決定。インフレへの警戒感が続く中での政策変更となる。"
        article_c = "新しくオープンした市立図書館の利用者が10万人を突破した。地域住民から親しまれる施設となっている。"
        items = [
            GenericItemInput("n1", "paper_x", "official", article_a),
            GenericItemInput("n2", "paper_y", "official", article_b),
            GenericItemInput("n3", "paper_z", "local_news", article_c),
        ]
        engine = SieveCoreEngine(density_threshold=0.20, exact_sim_threshold=0.70, jaccard_merge_threshold=0.15)
        results, stats = engine.process(items, density_fn=sns_density_fn, similarity_fn=sns_similarity_fn)
        print("News domain stats:", stats)
        for r in results:
            print(" ", r.fact_id, r.item_ids)
        self.assertEqual(len(results), 2)
        self.assertEqual(sorted(results[0].item_ids), ["n1", "n2"])


if __name__ == "__main__":
    unittest.main()
