"""
Probes for the sieve-core v1.1.0 lane (CO-T01..CO-T09, red-first).
Standard Library Only (Zero-Dependencies).

CO-T07 is intentionally absent: C-5 (merge-stage complexity) is measured but
not re-implemented in this lane (measured doubling ratios stayed below 4x),
so the CO-T07 gate does not apply. See the lane report for the measured
numbers.
"""

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

from sieve_core import GenericItemInput, SieveCoreEngine  # noqa: E402


BASE_SENTENCE = "BREAKING a major power outage is occurring in the XX district today"

T_B2 = "Report two: outage reported at main gate zone"
T_B3 = "Report three: landslide blocks the old highway"
T_B4 = "Report four: landslide blocks the old highway"
T_B7 = "Report seven: landslide blocks the old highway"

HIGH_A = "Bridge closed: crews inspect damage near Elm Ave overpass."
HIGH_B = "City council votes 7-2 to approve the new zoning budget proposal."

HASH_SEEDS = ("0", "1", "2", "12345")

# Pins measured against the released 1.0.0 tree on 2026-11-07
# (json.dumps(..., sort_keys=True, ensure_ascii=False) of
#  {"facts": [...], "stats": {raw_input_count, filtered_input_count,
#  extracted_facts_count}}; the added `dropped` key is asserted by CO-T04 and
#  deliberately excluded from the pin comparison).
PIN_SET1 = '{"facts": [{"confidence_score": 0.1824, "fact_id": "FACT-001", "independent_sources_count": 1, "item_ids": ["1"], "representative_content": "Bridge closed: crews inspect damage near Elm Ave overpass."}], "stats": {"extracted_facts_count": 1, "filtered_input_count": 1, "raw_input_count": 1}}'
PIN_SET2 = '{"facts": [{"confidence_score": 0.1824, "fact_id": "FACT-001", "independent_sources_count": 1, "item_ids": ["1"], "representative_content": "Bridge closed: crews inspect damage near Elm Ave overpass."}, {"confidence_score": 0.1824, "fact_id": "FACT-002", "independent_sources_count": 1, "item_ids": ["2"], "representative_content": "City council votes 7-2 to approve the new zoning budget proposal."}], "stats": {"extracted_facts_count": 2, "filtered_input_count": 2, "raw_input_count": 2}}'
PIN_SET3 = '{"facts": [], "stats": {"extracted_facts_count": 0, "filtered_input_count": 0, "raw_input_count": 1}}'
PIN_SET4 = '{"facts": [], "stats": {"extracted_facts_count": 0, "filtered_input_count": 0, "raw_input_count": 2}}'

_RUNNER_TEMPLATE = r"""
import hashlib
import json
import sys

from sieve_core import GenericItemInput, SieveCoreEngine

case = sys.argv[1]
if case == "A":
    base = {base!r}
    items = [GenericItemInput("a%d" % i, "u%d" % i, "role", base) for i in range(8)]
elif case == "B":
    items = [
        GenericItemInput("b2", "u2", "r2", {tb2!r}),
        GenericItemInput("b3", "u3", "r3", {tb3!r}),
        GenericItemInput("b4", "u4", "r4", {tb4!r}),
    ]
else:
    raise SystemExit("unknown case")

results, stats = SieveCoreEngine().process(items)
payload = {{
    "facts": [
        {{
            "fact_id": r.fact_id,
            "rep": r.representative_content,
            "ids": list(r.item_ids),
            "conf": r.confidence_score,
            "k": r.independent_sources_count,
        }}
        for r in results
    ],
    "stats": stats,
}}
blob = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
print(hashlib.sha256(blob).hexdigest())
""".format(
    base=BASE_SENTENCE,
    tb2=T_B2,
    tb3=T_B3,
    tb4=T_B4,
)


def _run_engine_in_subprocess(case: str, hash_seed: str) -> str:
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = hash_seed
    proc = subprocess.run(
        [sys.executable, "-c", _RUNNER_TEMPLATE, case],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if proc.returncode != 0:
        raise AssertionError(
            "subprocess failed (seed=%s case=%s): %s" % (hash_seed, case, proc.stderr[-500:])
        )
    return proc.stdout.strip()


class TestCoT01Determinism(unittest.TestCase):
    def test_co_t01_byte_identical_output_across_hash_seeds(self):
        """CO-T01: same input must give byte-identical output in separate
        processes with different PYTHONHASHSEED values."""
        for case in ("A", "B"):
            digests = {
                seed: _run_engine_in_subprocess(case, seed) for seed in HASH_SEEDS
            }
            with self.subTest(case=case):
                self.assertEqual(
                    len(set(digests.values())),
                    1,
                    "non-deterministic output for case %s: %s" % (case, digests),
                )


class TestCoT02InputOrder(unittest.TestCase):
    def test_co_t02_item_ids_follow_input_appearance_order(self):
        """CO-T02: item_ids are ordered by first appearance in the input, and
        reordering the input reorders the output accordingly."""
        eng = SieveCoreEngine()
        forward = [
            GenericItemInput("a%d" % i, "u%d" % i, "role", BASE_SENTENCE)
            for i in range(8)
        ]
        results, _ = eng.process(forward)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].item_ids, ["a%d" % i for i in range(8)])

        reverse = list(reversed(forward))
        results_rev, _ = eng.process(reverse)
        self.assertEqual(len(results_rev), 1)
        self.assertEqual(
            results_rev[0].item_ids,
            ["a%d" % i for i in range(7, -1, -1)],
        )

    def test_co_t02_tied_representative_breaks_tie_by_input_order(self):
        """CO-T02: when several items tie for the representative choice
        (same maximal length), the one appearing earliest in the input wins.
        T_B3/T_B7 are both 46 chars, collapse into one cluster (measured
        similarity 0.7917 >= 0.65), and tie for the representative choice."""
        eng = SieveCoreEngine()
        forward = [
            GenericItemInput("b3", "u3", "r3", T_B3),
            GenericItemInput("b7", "u7", "r7", T_B7),
        ]
        results, _ = eng.process(forward)
        self.assertEqual(len(results), 1)
        # T_B3 appears earliest among the tied items
        self.assertEqual(results[0].representative_content, T_B3)

        reverse = list(reversed(forward))
        results_rev, _ = eng.process(reverse)
        self.assertEqual(len(results_rev), 1)
        # T_B7 appears earliest in the reversed input
        self.assertEqual(results_rev[0].representative_content, T_B7)


class TestCoT03DuplicateCheck(unittest.TestCase):
    def test_co_t03_duplicate_rejected_even_if_one_would_be_filtered(self):
        """CO-T03: duplicate item_ids are rejected at input validation, before
        the density filter — even when one of the duplicates would be filtered
        out (previously this slipped through)."""
        eng = SieveCoreEngine()
        items = [
            GenericItemInput("dup", "u_low", "r1", "!!!!!!!!!!!!!!"),
            GenericItemInput("dup", "u_high", "r2", HIGH_A),
        ]
        with self.assertRaises(ValueError) as ctx:
            eng.process(items)
        self.assertIn("Duplicate item_id(s) found", str(ctx.exception))

    def test_co_t03_duplicate_free_input_still_accepted(self):
        """CO-T03: duplicate-free input keeps working as before."""
        eng = SieveCoreEngine()
        items = [
            GenericItemInput("x1", "u_low", "r1", "!!!!!!!!!!!!!!"),
            GenericItemInput("x2", "u_high", "r2", HIGH_A),
        ]
        results, stats = eng.process(items)
        self.assertEqual(stats["filtered_input_count"], 1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].item_ids, ["x2"])


class TestCoT04Dropped(unittest.TestCase):
    def test_co_t04_dropped_key_always_present_and_empty_without_drops(self):
        """CO-T04: `dropped` exists in stats and is an empty list when
        nothing was dropped."""
        eng = SieveCoreEngine()
        _, stats = eng.process([GenericItemInput("1", "u1", "r1", HIGH_A)])
        self.assertEqual(stats["dropped"], [])
        _, stats_empty = eng.process([])
        self.assertEqual(stats_empty["dropped"], [])

    def test_co_t04_dropped_lists_id_and_closed_reason_in_input_order(self):
        """CO-T04: each dropped entry carries the item id and a closed
        vocabulary reason, ordered by input appearance; no item content and no
        exception message is included."""
        eng = SieveCoreEngine()
        items = [
            GenericItemInput("keep1", "u1", "r1", HIGH_A),
            GenericItemInput("drop_me", "u2", "r2", "!!!!!"),
            GenericItemInput("drop_me_too", "u3", "r3", "wwwww"),
            GenericItemInput("keep2", "u4", "r4", HIGH_B),
        ]
        _, stats = eng.process(items)
        self.assertEqual(
            stats["dropped"],
            [
                {"item_id": "drop_me", "reason": "low_density"},
                {"item_id": "drop_me_too", "reason": "low_density"},
            ],
        )
        for entry in stats["dropped"]:
            self.assertEqual(set(entry.keys()), {"item_id", "reason"})


def _pinned_blob(results, stats):
    facts = [
        {
            "confidence_score": r.confidence_score,
            "fact_id": r.fact_id,
            "independent_sources_count": r.independent_sources_count,
            "item_ids": list(r.item_ids),
            "representative_content": r.representative_content,
        }
        for r in results
    ]
    legacy_stats = {
        "raw_input_count": stats["raw_input_count"],
        "filtered_input_count": stats["filtered_input_count"],
        "extracted_facts_count": stats["extracted_facts_count"],
    }
    return json.dumps(
        {"facts": facts, "stats": legacy_stats},
        ensure_ascii=False,
        sort_keys=True,
    )


class TestCoT05AddedKeysOnly(unittest.TestCase):
    def test_co_t05_existing_keys_keep_value_and_type(self):
        """CO-T05: only added keys — existing keys keep their values and
        types (beyond the now-fixed ordering)."""
        eng = SieveCoreEngine()
        results, stats = eng.process([GenericItemInput("1", "u1", "r1", HIGH_A)])
        self.assertEqual(len(results), 1)
        r = results[0]
        self.assertIsInstance(r.fact_id, str)
        self.assertEqual(r.fact_id, "FACT-001")
        self.assertIsInstance(r.representative_content, str)
        self.assertEqual(r.representative_content, HIGH_A)
        self.assertIsInstance(r.item_ids, list)
        self.assertEqual(r.item_ids, ["1"])
        self.assertIsInstance(r.independent_sources_count, int)
        self.assertEqual(r.independent_sources_count, 1)
        self.assertIsInstance(r.confidence_score, float)
        self.assertEqual(r.confidence_score, 0.1824)
        self.assertIsInstance(stats["raw_input_count"], int)
        self.assertEqual(stats["raw_input_count"], 1)
        self.assertIsInstance(stats["filtered_input_count"], int)
        self.assertEqual(stats["filtered_input_count"], 1)
        self.assertIsInstance(stats["extracted_facts_count"], int)
        self.assertEqual(stats["extracted_facts_count"], 1)


class TestCoT06Molds(unittest.TestCase):
    def test_co_t06_mold_outputs_byte_identical_to_1_0_0_pins(self):
        """CO-T06: for order-insensitive inputs (single items, nothing to
        merge), the output matches the measured 1.0.0 pins byte for byte."""
        eng = SieveCoreEngine()
        cases = [
            (
                PIN_SET1,
                [GenericItemInput("1", "u1", "r1", HIGH_A)],
            ),
            (
                PIN_SET2,
                [
                    GenericItemInput("1", "u1", "r1", HIGH_A),
                    GenericItemInput("2", "u2", "r2", HIGH_B),
                ],
            ),
            (
                PIN_SET3,
                [GenericItemInput("1", "u1", "r1", "!!!!!")],
            ),
            (
                PIN_SET4,
                [
                    GenericItemInput("1", "u1", "r1", "!!!!!"),
                    GenericItemInput("2", "u2", "r2", "wwwww"),
                ],
            ),
        ]
        for expected, items in cases:
            with self.subTest(pin=expected[:40]):
                results, stats = eng.process(items)
                self.assertEqual(_pinned_blob(results, stats), expected)


class TestCoT08Classification(unittest.TestCase):
    def test_co_t08_pyproject_classification_matches_readme_mvp(self):
        """CO-T08: pyproject's development status matches the README's own
        description (v1.0.0-MVP => Alpha)."""
        pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn("Development Status :: 3 - Alpha", pyproject)
        self.assertNotIn("Development Status :: 5 - Production/Stable", pyproject)
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("MVP", readme)


class TestCoT09VersionChangelog(unittest.TestCase):
    def test_co_t09_version_and_changelog_consistent(self):
        """CO-T09: pyproject version is 1.2.0 and CHANGELOG.md documents it.

        (Version pin follows each release lane: 1.1.0 -> 1.1.1 in the
        packaging/SPDX lane, and -> 1.2.0 in the references/SCC lane.
        The CHANGELOG keeps documenting [1.1.0] too.)
        """
        pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('version = "1.2.0"', pyproject)
        changelog_path = REPO_ROOT / "CHANGELOG.md"
        self.assertTrue(changelog_path.exists(), "CHANGELOG.md must exist")
        changelog = changelog_path.read_text(encoding="utf-8")
        self.assertIn("[1.1.0]", changelog)


if __name__ == "__main__":
    unittest.main()
