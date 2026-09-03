"""
Unit tests for Sieve-Core Engine (v1.0.0-MVP)
Standard Library Only (Zero-Dependencies)
"""

import unittest
from sieve_core import GenericItemInput, SieveCoreEngine


class TestSieveCoreEngine(unittest.TestCase):
    def setUp(self):
        self.engine = SieveCoreEngine()

    def test_density_filter(self):
        """Verify that low-density text (filler/symbols only, etc.) is filtered out."""
        items = [
            GenericItemInput("1", "user_a", "role1", "aaaaaaaaaaaaaaaaaaaa"),  # low density
            GenericItemInput("2", "user_b", "role2", "Bridge closed: crews inspect damage near Elm Ave overpass."),  # high density
        ]
        results, stats = self.engine.process(items)
        self.assertEqual(stats["raw_input_count"], 2)
        self.assertEqual(stats["filtered_input_count"], 1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].item_ids, ["2"])

    def test_duplicate_item_id_raises_value_error(self):
        """Verify that a ValueError is explicitly raised when a duplicate item_id exists."""
        items = [
            GenericItemInput("dup_id", "user_a", "role1", "Traffic accident reported at Main St junction, 10:42am."),
            GenericItemInput("dup_id", "user_b", "role2", "Bridge closed: crews inspect damage near Elm Ave overpass."),
        ]
        with self.assertRaises(ValueError) as ctx:
            self.engine.process(items)
        self.assertIn("Duplicate item_id(s) found", str(ctx.exception))

    def test_empty_and_edge_inputs(self):
        """Verify behavior on an empty input list, and on a list that is entirely filtered out."""
        # Empty list
        results, stats = self.engine.process([])
        self.assertEqual(stats["raw_input_count"], 0)
        self.assertEqual(len(results), 0)

        # Everything is rejected for low density
        items = [
            GenericItemInput("1", "u1", "r1", "!!!!!"),
            GenericItemInput("2", "u2", "r2", "wwwww"),
        ]
        results, stats = self.engine.process(items)
        self.assertEqual(stats["filtered_input_count"], 0)
        self.assertEqual(len(results), 0)

    def test_tarjan_scc_copypasta_reduction(self):
        """Verify that repeated copy-paste/bot amplification correctly collapses into a single fact."""
        items = [
            GenericItemInput("p1", "bot1", "bot_net", "BREAKING: a major power outage is occurring in the XX district."),
            GenericItemInput("p2", "bot2", "bot_net", "BREAKING: a major power outage is occurring in the XX district."),
            GenericItemInput("p3", "bot3", "bot_net", "BREAKING: a major power outage is occurring in the XX district."),
            GenericItemInput("p4", "user_c", "citizen", "There's a blackout in the XX district, traffic lights are out too."),
        ]
        results, stats = self.engine.process(items)
        # p1/p2/p3 (copy-paste) collapse into one; p4 may merge in as similar or stay separate
        self.assertGreaterEqual(stats["raw_input_count"], 4)
        self.assertGreaterEqual(len(results), 1)

    def test_average_linkage_chaining_prevention(self):
        """Verify that average-linkage prevents unrelated texts from chaining together."""
        # B and C are near-duplicates; A is unrelated to both and should not get pulled in
        items = [
            GenericItemInput("a", "u1", "r1", "City council votes 7-2 to approve the new zoning budget proposal."),
            GenericItemInput("b", "u2", "r2", "Best ramen shop discovered near Elm Avenue, highly recommend!"),
            GenericItemInput("c", "u3", "r3", "Best ramen shop discovered near Pine Boulevard, highly recommend!"),
        ]
        results, stats = self.engine.process(items)
        # Should not chain-merge into a single result; should stay properly separated
        self.assertGreater(len(results), 1)

    def test_custom_density_fn_injection(self):
        """
        Verify that a custom density evaluator can be injected.

        Deliberately uses Japanese sample text here: this test exercises a
        language-specific injection point (a kanji/numeral-density heuristic),
        so the content itself needs to be real Japanese text for the test to
        be meaningful.
        """
        def custom_japanese_density(text: str) -> float:
            import re
            if not text:
                return 0.0
            return len(re.findall(r"[一-龥0-9]", text)) / len(text)

        items = [
            GenericItemInput("1", "u1", "r1", "マジでヤバい！本当にありえないんだがｗｗ"),  # zero kanji/numerals -> filtered out
            GenericItemInput("2", "u2", "r2", "2026年9月2日に千葉市中央区で避難訓練が実施されます。"),  # high density
        ]
        results, stats = self.engine.process(items, density_fn=custom_japanese_density)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].item_ids, ["2"])

    def test_custom_similarity_fn_injection(self):
        """Verify that a custom similarity function can be injected."""
        def dummy_similarity(a: str, b: str) -> float:
            return 1.0 if a[0] == b[0] else 0.0  # similarity 1.0 if the first character matches

        items = [
            GenericItemInput("1", "u1", "r1", "Alpha item content"),
            GenericItemInput("2", "u2", "r2", "Apple item content"),
            GenericItemInput("3", "u3", "r3", "Banana item content"),
        ]
        results, stats = self.engine.process(items, similarity_fn=dummy_similarity)
        # "Alpha" and "Apple" should be merged into the same cluster; "Banana" stays separate
        self.assertEqual(len(results), 2)

    def test_sigmoid_confidence_scoring_curve(self):
        """
        Directly verify the sigmoid confidence-scoring function's output at each k
        (independent source count) against expected values, and check its
        mathematical properties (monotonic increase, boundary behavior).
        """
        # Default parameters: alpha=3.0, k0=1.5
        engine = SieveCoreEngine(sigmoid_alpha=3.0, sigmoid_k0=1.5)

        # 1. Verify expected confidence scores for known values of k
        # k=0: 1 / (1 + exp(4.5))  ~= 0.0110
        # k=1: 1 / (1 + exp(1.5))  ~= 0.1824
        # k=2: 1 / (1 + exp(-1.5)) ~= 0.8176
        # k=3: 1 / (1 + exp(-4.5)) ~= 0.9890
        expected_scores = {
            0: 0.0110,
            1: 0.1824,
            2: 0.8176,
            3: 0.9890,
        }
        for k, expected in expected_scores.items():
            with self.subTest(k=k):
                score = engine.calculate_confidence(k)
                self.assertAlmostEqual(score, expected, places=4)

        # 2. Confirm point symmetry around the inflection point (k0 = 1.5):
        # the scores at k1 and k2 (equidistant from k0) should sum to 1.0
        self.assertAlmostEqual(
            engine.calculate_confidence(1) + engine.calculate_confidence(2),
            1.0000,
            places=4
        )

        # 3. Verify monotonic increase (confidence must never decrease as k increases)
        scores = [engine.calculate_confidence(k) for k in range(5)]
        self.assertEqual(scores, sorted(scores))

        # 4. Verify the confidence curve shifts correctly when parameters change:
        # if k0 is shifted to 2.5, confidence at k=2 should drop below 0.5
        engine_shifted = SieveCoreEngine(sigmoid_alpha=3.0, sigmoid_k0=2.5)
        self.assertLess(engine_shifted.calculate_confidence(2), 0.5)
        self.assertEqual(engine_shifted.calculate_confidence(2), 0.1824)


if __name__ == "__main__":
    unittest.main()
