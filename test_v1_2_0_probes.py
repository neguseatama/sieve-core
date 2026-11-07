"""
Probes for the sieve-core v1.2.0 lane (CO2-T01..T15, red-first).
Standard Library Only (Zero-Dependencies).

The lane adds directed "references" relations (cites / replies / reposts)
and runs Tarjan SCC in its real sense:

  - `relation_mode` (default "similarity") selects the edge source.
    "similarity" builds symmetric similarity edges exactly as before
    (undirected behavior: SCCs coincide with connected components).
    "references" builds directed edges A -> B ("A cites B") from the
    optional `references` argument of GenericItemInput.
  - `cycles` reports the size >= 2 SCCs contained in each fact;
    `cites` reports the citation flow between merged facts (the
    condensation, expressed as fact IDs, sorted ascending).
  - The default path stays byte-identical to v1.1.1 (CO2-T01 mold).

Note on CO2-T01: the mold itself (multiple inputs, no references given)
is the only probe that must already pass on the untouched v1.1.1 tree.
The "references given, default mode unchanged" variant is a separate
method: it red-fails on v1.1.1 (the argument does not exist yet) and
turns green with the feature commit. This keeps the mold green at red
time as required by the lane (order §6-2).
"""

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

from sieve_core import (  # noqa: E402
    FactClusterOutput,
    GenericItemInput,
    SieveCoreEngine,
)

HASH_SEEDS = ("0", "1", "2", "12345")

STATS_KEY_ORDER = [
    "raw_input_count",
    "filtered_input_count",
    "extracted_facts_count",
    "dropped",
    "scc_count",
    "cycle_count",
    "references_dropped",
    "self_references_ignored",
]

# --- CO2-T01 mold pins, measured against the untouched v1.1.1 tree ---
# (json.dumps({"facts": [...existing fields...], "stats": {...existing
#  4 keys...}}, sort_keys=True, ensure_ascii=False), measured 2026-11-08
#  at main 08b20104 (tree 16685f30...).)
PIN_M1 = '{"facts": [{"confidence_score": 0.1824, "fact_id": "FACT-001", "independent_sources_count": 1, "item_ids": ["m1"], "representative_content": "Bridge closed: crews inspect damage near Elm Ave overpass."}, {"confidence_score": 0.1824, "fact_id": "FACT-002", "independent_sources_count": 1, "item_ids": ["m2"], "representative_content": "City council votes 7-2 to approve the new zoning budget proposal."}], "stats": {"dropped": [], "extracted_facts_count": 2, "filtered_input_count": 2, "raw_input_count": 2}}'
PIN_M2 = '{"facts": [{"confidence_score": 0.1824, "fact_id": "FACT-001", "independent_sources_count": 1, "item_ids": ["p1", "p2"], "representative_content": "BREAKING: a major power outage is occurring in the XX district."}], "stats": {"dropped": [{"item_id": "p3", "reason": "low_density"}], "extracted_facts_count": 1, "filtered_input_count": 2, "raw_input_count": 3}}'
PIN_M3 = '{"facts": [{"confidence_score": 0.8176, "fact_id": "FACT-001", "independent_sources_count": 2, "item_ids": ["r1", "r2"], "representative_content": "News item one about flooding in the north ward."}], "stats": {"dropped": [], "extracted_facts_count": 1, "filtered_input_count": 2, "raw_input_count": 2}}'


def _mold_items_m1():
    return [
        GenericItemInput("m1", "u1", "citizen",
                         "Bridge closed: crews inspect damage near Elm Ave overpass."),
        GenericItemInput("m2", "u2", "media",
                         "City council votes 7-2 to approve the new zoning budget proposal."),
    ]


def _mold_items_m2():
    return [
        GenericItemInput("p1", "bot1", "bot",
                         "BREAKING: a major power outage is occurring in the XX district."),
        GenericItemInput("p2", "bot2", "bot",
                         "BREAKING: a major power outage is occurring in the XX district."),
        GenericItemInput("p3", "user_c", "citizen", "!!!!!!!!!!!!!!"),
    ]


def _mold_items_m3(with_references):
    """M3 corpus. with_references=True attaches references=["r2"] / [] to the
    items (only possible after the feature commit); the pinned output must be
    unchanged either way (the default mode never reads references)."""
    r1 = GenericItemInput("r1", "u1", "media",
                          "News item one about flooding in the north ward.",
                          payload={"priority": 1})
    r2 = GenericItemInput("r2", "u2", "citizen",
                          "News item two about flooding in the south ward.")
    if with_references:
        r1.references = ["r2"]
        r2.references = ()
    return [r1, r2]


def _pinned_blob(results, stats):
    """Serialize the v1.1.1-visible surface: existing fact fields and the
    existing 4 stats keys (added keys are asserted separately by CO2-T12)."""
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
        "dropped": stats["dropped"],
    }
    return json.dumps(
        {"facts": facts, "stats": legacy_stats},
        ensure_ascii=False,
        sort_keys=True,
    )


def _facts_by_id(results):
    return {r.fact_id: r for r in results}


class TestCo2T01Mold(unittest.TestCase):
    """CO2-T01: default-mode output stays byte-identical to v1.1.1."""

    def test_co2_t01_mold_matches_v1_1_1_pins(self):
        """The mold: multiple inputs without references give the pinned
        v1.1.1 output byte for byte. Green on the untouched tree."""
        eng = SieveCoreEngine()
        cases = [
            (PIN_M1, _mold_items_m1()),
            (PIN_M2, _mold_items_m2()),
            (PIN_M3, _mold_items_m3(with_references=False)),
        ]
        for expected, items in cases:
            with self.subTest(pin=expected[:40]):
                results, stats = eng.process(items)
                self.assertEqual(_pinned_blob(results, stats), expected)

    def test_co2_t01_mold_unchanged_with_references(self):
        """Giving references (list or tuple, including empty) must not
        change the default-mode output (the argument is never read here)."""
        eng = SieveCoreEngine()
        for refs_case in (True,):
            results, stats = eng.process(
                _mold_items_m3(with_references=refs_case)
            )
            self.assertEqual(_pinned_blob(results, stats), PIN_M3)


class TestCo2T02Construction(unittest.TestCase):
    """CO2-T02: positional construction is preserved; new fields are
    appended with defaults."""

    def test_co2_t02_positional_construction_preserved(self):
        item = GenericItemInput("a", "u", "r", "plain text content here")
        self.assertEqual(item.item_id, "a")
        self.assertIsNone(item.references)

        out = FactClusterOutput("F-1", "rep", ["a"], 1, 0.5)
        self.assertEqual(out.fact_id, "F-1")
        self.assertIsNone(out.cycles)
        self.assertIsNone(out.cites)

    def test_co2_t02_new_fields_are_appended_after_existing_ones(self):
        item = GenericItemInput("a", "u", "r", "text", "pay", ["b"])
        self.assertEqual(item.payload, "pay")
        self.assertEqual(item.references, ["b"])

        out = FactClusterOutput("F-1", "rep", ["a"], 1, 0.5, [["a"]], ["F-2"])
        self.assertEqual(out.cycles, [["a"]])
        self.assertEqual(out.cites, ["F-2"])


class TestCo2T03SccBasics(unittest.TestCase):
    """CO2-T03: a 3-cycle is one SCC; a 3-chain is three SCCs."""

    def test_co2_t03_cycle_collapses_chain_does_not(self):
        """Corpus measured 2026-11-08: all pairwise 2-gram Jaccard values
        are below the 0.15 merge threshold (0.059 / 0.096 / 0.071), so only
        the reference edges shape the outcome."""
        eng = SieveCoreEngine()
        cycle_items = [
            GenericItemInput("A", "u1", "r1",
                             "grain lorries left cyd depot hauling fresh produce",
                             references=["B"]),
            GenericItemInput("B", "u2", "r2",
                             "technicians fitted new relay boards after midnight",
                             references=["C"]),
            GenericItemInput("C", "u3", "r3",
                             "museum curators unveiled bronze artifacts upstairs",
                             references=["A"]),
        ]
        results, stats = eng.process(cycle_items, relation_mode="references")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].item_ids, ["A", "B", "C"])
        self.assertEqual(results[0].cycles, [["A", "B", "C"]])
        self.assertEqual(stats["scc_count"], 1)
        self.assertEqual(stats["cycle_count"], 1)

        chain_items = [
            GenericItemInput("A", "u1", "r1",
                             "grain lorries left cyd depot hauling fresh produce",
                             references=["B"]),
            GenericItemInput("B", "u2", "r2",
                             "technicians fitted new relay boards after midnight",
                             references=["C"]),
            GenericItemInput("C", "u3", "r3",
                             "museum curators unveiled bronze artifacts upstairs"),
        ]
        results_c, stats_c = eng.process(chain_items, relation_mode="references")
        self.assertEqual(len(results_c), 3)
        self.assertEqual(results_c[0].cycles, [])
        self.assertEqual(stats_c["scc_count"], 3)
        self.assertEqual(stats_c["cycle_count"], 0)


class TestCo2T04Direction(unittest.TestCase):
    """CO2-T04: cites follows the edge direction; two cycles joined by a
    one-way edge stay two SCCs."""

    def _two_cycle_items(self, joining_refs):
        x = GenericItemInput("X", "u1", "r1",
                             "x-ray weather balloon launched at dawn")
        y = GenericItemInput("Y", "u2", "r2",
                             "yankee yard crew repairs the fence")
        p = GenericItemInput("P", "u3", "r3",
                             "papa plant produces paper goods")
        q = GenericItemInput("q", "u4", "r4",
                             "quebec quarterfinal scores announced today")
        x.references = ["Y"] + joining_refs.get("X", [])
        y.references = ["X"]
        p.references = ["q"] + joining_refs.get("P", [])
        q.references = ["P"]
        return [x, y, p, q]

    def test_co2_t04_cites_follows_edge_direction(self):
        eng = SieveCoreEngine()
        # Case 1: X cites P (X -> P), plus the intra-cycle pairs.
        results, _ = eng.process(
            self._two_cycle_items({"X": ["P"]}), relation_mode="references"
        )
        self.assertEqual(len(results), 2)
        by_id = _facts_by_id(results)
        self.assertEqual(by_id["FACT-001"].item_ids, ["X", "Y"])
        self.assertEqual(by_id["FACT-002"].item_ids, ["P", "q"])
        self.assertEqual(by_id["FACT-001"].cycles, [["X", "Y"]])
        self.assertEqual(by_id["FACT-002"].cycles, [["P", "q"]])
        self.assertEqual(by_id["FACT-001"].cites, ["FACT-002"])
        self.assertEqual(by_id["FACT-002"].cites, [])

        # Case 2: reverse the joining edge (P -> X); the direction of
        # `cites` flips with it.
        results_rev, _ = eng.process(
            self._two_cycle_items({"P": ["X"]}), relation_mode="references"
        )
        self.assertEqual(len(results_rev), 2)
        by_id_rev = _facts_by_id(results_rev)
        self.assertEqual(by_id_rev["FACT-001"].cites, [])
        self.assertEqual(by_id_rev["FACT-002"].cites, ["FACT-001"])


class TestCo2T05SelfAndDuplicates(unittest.TestCase):
    """CO2-T05: self references are ignored and counted; duplicate
    references collapse to one."""

    def _self_dup_items(self, refs):
        a = GenericItemInput("A", "u1", "r1",
                             "apple orchard harvest begins next week")
        b = GenericItemInput("B", "u2", "r2",
                             "banana boat sails to the island")
        a.references = refs
        return [a, b]

    def test_co2_t05_self_reference_ignored_and_counted(self):
        eng = SieveCoreEngine()
        results, stats = eng.process(
            self._self_dup_items(["A", "B", "B"]),
            relation_mode="references",
        )
        self.assertEqual(stats["self_references_ignored"], 1)
        self.assertEqual(stats["scc_count"], 2)
        self.assertEqual(stats["cycle_count"], 0)
        self.assertEqual(len(results), 2)

    def test_co2_t05_duplicate_references_collapse_to_one(self):
        eng = SieveCoreEngine()
        results_one, stats_one = eng.process(
            self._self_dup_items(["A", "B", "B"]), relation_mode="references"
        )
        results_many, stats_many = eng.process(
            self._self_dup_items(["A", "A", "A", "B", "B"]),
            relation_mode="references",
        )
        self.assertEqual(
            _pinned_blob(results_one, stats_one),
            _pinned_blob(results_many, stats_many),
        )
        self.assertEqual(stats_many["self_references_ignored"], 1)


class TestCo2T06Validation(unittest.TestCase):
    """CO2-T06: unknown reference IDs and bad types raise ValueError
    (fail-closed), listing only item IDs, ascending, never content."""

    def _val_items(self, refs):
        a = GenericItemInput("A", "u1", "r1",
                             "museum curators unveiled bronze artifacts upstairs")
        b = GenericItemInput("B", "u2", "r2",
                             "grain lorries left cyd depot hauling fresh produce")
        a.references = refs
        return [a, b]

    def test_co2_t06_unknown_reference_ids_raise(self):
        eng = SieveCoreEngine()
        with self.assertRaises(ValueError) as ctx:
            eng.process(
                self._val_items(["zzz", "aaa"]), relation_mode="references"
            )
        message = str(ctx.exception)
        self.assertIn("aaa", message)
        self.assertIn("zzz", message)
        # The unknown IDs are listed ascending.
        self.assertLess(message.index("aaa"), message.index("zzz"))
        # No item content in the message.
        self.assertNotIn("museum curators", message)
        self.assertNotIn("grain lorries", message)

    def test_co2_t06_bad_reference_types_raise(self):
        eng = SieveCoreEngine()
        for bad_refs in ("B", [1], {"B": 1}, 5, [None], ["A", 2]):
            with self.subTest(refs=bad_refs):
                with self.assertRaises(ValueError):
                    eng.process(
                        self._val_items(bad_refs), relation_mode="references"
                    )


class TestCo2T07DroppedRefs(unittest.TestCase):
    """CO2-T07: references to density-filtered items are not edges and are
    counted in stats["references_dropped"]."""

    def test_co2_t07_references_to_dropped_items_not_edges(self):
        eng = SieveCoreEngine()
        a = GenericItemInput("A", "u1", "r1",
                             "museum curators unveiled bronze artifacts upstairs",
                             references=["D", "E"])
        b = GenericItemInput("B", "u2", "r2",
                             "grain lorries left cyd depot hauling fresh produce",
                             references=["A"])
        d = GenericItemInput("D", "u4", "r4", "!!!!!")
        e = GenericItemInput("E", "u5", "r5", "wwwww")
        results, stats = eng.process([a, b, d, e], relation_mode="references")
        self.assertEqual(stats["references_dropped"], 2)
        self.assertEqual(stats["scc_count"], 2)
        by_id = _facts_by_id(results)
        self.assertEqual(by_id["FACT-001"].item_ids, ["A"])
        self.assertEqual(by_id["FACT-002"].item_ids, ["B"])
        self.assertEqual(by_id["FACT-001"].cites, [])
        self.assertEqual(by_id["FACT-002"].cites, ["FACT-001"])


class TestCo2T08NoReferences(unittest.TestCase):
    """CO2-T08: an input with no references under "references" mode gives
    single-item SCCs and merges purely by similarity."""

    def test_co2_t08_no_references_merges_by_similarity_only(self):
        eng = SieveCoreEngine()
        text = "Flood water rose above the bridge deck last night."
        items = [
            GenericItemInput("n1", "u1", "bot", text),
            GenericItemInput("n2", "u2", "media", text),
            GenericItemInput("n3", "u3", "citizen", text),
        ]
        results, stats = eng.process(items, relation_mode="references")
        self.assertEqual(stats["scc_count"], 3)
        self.assertEqual(stats["cycle_count"], 0)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].item_ids, ["n1", "n2", "n3"])
        self.assertEqual(results[0].cycles, [])
        self.assertEqual(results[0].cites, [])


class TestCo2T09MergeUnits(unittest.TestCase):
    """CO2-T09: merging works on SCCs as units; intra-fact citations are
    excluded from cites, inter-fact citations appear."""

    def test_co2_t09_merged_fact_hides_internal_citations(self):
        eng = SieveCoreEngine()
        a = GenericItemInput("A", "u1", "official",
                             "Central bank raises the policy rate by 0.25 percent today")
        b = GenericItemInput("B", "u2", "media",
                             "Central bank raises the policy rate by 0.25 percent today")
        c = GenericItemInput("C", "u3", "official",
                             "Central bank lifts the policy rate by 0.25 percent today")
        d = GenericItemInput("D", "u4", "citizen",
                             "Central bank lifts the policy rate by 0.25 percent today")
        e = GenericItemInput("E", "u5", "r5",
                             "Museum extends the weekend opening hours for visitors")
        a.references = ["B", "C"]
        b.references = ["A"]
        c.references = ["D"]
        d.references = ["C"]
        e.references = ["A"]
        results, stats = eng.process(
            [a, b, c, d, e], relation_mode="references"
        )
        self.assertEqual(stats["scc_count"], 3)
        self.assertEqual(stats["cycle_count"], 2)
        self.assertEqual(len(results), 2)
        by_id = _facts_by_id(results)
        self.assertEqual(by_id["FACT-001"].item_ids, ["A", "B", "C", "D"])
        # Two distinct SCCs live inside the merged fact, in input order.
        self.assertEqual(by_id["FACT-001"].cycles, [["A", "B"], ["C", "D"]])
        # A -> C is an intra-fact citation: excluded.
        self.assertEqual(by_id["FACT-001"].cites, [])
        # E cites A: an inter-fact citation, expressed via fact IDs.
        self.assertEqual(by_id["FACT-002"].item_ids, ["E"])
        self.assertEqual(by_id["FACT-002"].cites, ["FACT-001"])


_RUNNER_TEMPLATE_REF = r"""
import hashlib
import json
import sys

from sieve_core import GenericItemInput, SieveCoreEngine

items = [
    GenericItemInput("x", "u1", "bot",
                     "x-ray weather balloon launched at dawn",
                     payload={"i": 1}, references=["y", "p"]),
    GenericItemInput("y", "u2", "bot",
                     "yankee yard crew repairs the fence",
                     references=["x"]),
    GenericItemInput("p", "u3", "citizen",
                     "papa plant produces paper goods",
                     references=["q", "q"]),
    GenericItemInput("q", "u4", "media",
                     "quebec quarterfinal scores announced today",
                     references=["p"]),
]
results, stats = SieveCoreEngine().process(items, relation_mode="references")
payload = {
    "facts": [
        {"fact_id": r.fact_id, "rep": r.representative_content,
         "ids": list(r.item_ids), "conf": r.confidence_score,
         "k": r.independent_sources_count,
         "cycles": r.cycles, "cites": r.cites}
        for r in results
    ],
    "stats": stats,
}
blob = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
print(hashlib.sha256(blob).hexdigest())
"""


def _run_refs_mode_in_subprocess(hash_seed):
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = hash_seed
    proc = subprocess.run(
        [sys.executable, "-c", _RUNNER_TEMPLATE_REF],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if proc.returncode != 0:
        raise AssertionError(
            "subprocess failed (seed=%s): %s" % (hash_seed, proc.stderr[-500:])
        )
    return proc.stdout.strip()


class TestCo2T10Determinism(unittest.TestCase):
    """CO2-T10: references-mode output is byte-identical across hash seeds
    and input reordering follows the appearance rules."""

    def test_co2_t10_byte_identical_across_hash_seeds(self):
        digests = {
            seed: _run_refs_mode_in_subprocess(seed) for seed in HASH_SEEDS
        }
        self.assertEqual(len(set(digests.values())), 1, digests)

    def test_co2_t10_reordering_follows_appearance_rules(self):
        eng = SieveCoreEngine()

        def make_items():
            x = GenericItemInput("X", "u1", "r1",
                                 "x-ray weather balloon launched at dawn")
            y = GenericItemInput("Y", "u2", "r2",
                                 "yankee yard crew repairs the fence")
            p = GenericItemInput("P", "u3", "r3",
                                 "papa plant produces paper goods")
            q = GenericItemInput("Q", "u4", "r4",
                                 "quebec quarterfinal scores announced today")
            x.references = ["Y", "P"]
            y.references = ["X"]
            p.references = ["Q"]
            q.references = ["P"]
            return [x, y, p, q]

        results_fwd, stats_fwd = eng.process(
            make_items(), relation_mode="references"
        )
        self.assertEqual(stats_fwd["scc_count"], 2)
        by_id_fwd = _facts_by_id(results_fwd)
        self.assertEqual(by_id_fwd["FACT-001"].item_ids, ["X", "Y"])
        self.assertEqual(by_id_fwd["FACT-001"].cycles, [["X", "Y"]])
        self.assertEqual(by_id_fwd["FACT-001"].cites, ["FACT-002"])
        self.assertEqual(by_id_fwd["FACT-002"].item_ids, ["P", "Q"])
        self.assertEqual(by_id_fwd["FACT-002"].cycles, [["P", "Q"]])
        self.assertEqual(by_id_fwd["FACT-002"].cites, [])

        results_rev, stats_rev = eng.process(
            list(reversed(make_items())), relation_mode="references"
        )
        self.assertEqual(stats_rev["scc_count"], 2)
        by_id_rev = _facts_by_id(results_rev)
        # In the reversed input Q and P appear first, so the SCC-internal
        # order follows the new appearance order.
        self.assertEqual(by_id_rev["FACT-001"].item_ids, ["Q", "P"])
        self.assertEqual(by_id_rev["FACT-001"].cycles, [["Q", "P"]])
        self.assertEqual(by_id_rev["FACT-001"].cites, [])
        self.assertEqual(by_id_rev["FACT-002"].item_ids, ["Y", "X"])
        self.assertEqual(by_id_rev["FACT-002"].cycles, [["Y", "X"]])
        self.assertEqual(by_id_rev["FACT-002"].cites, ["FACT-001"])


class TestCo2T11Scale(unittest.TestCase):
    """CO2-T11: deep chains and large cycles do not hit RecursionError.
    similarity_fn is injected as a constant to keep the O(N^2) merge stage
    out of the measured path (a legitimate plugin per the README)."""

    def test_co2_t11_deep_chain_no_recursion_error(self):
        eng = SieveCoreEngine()
        n = 10000
        items = [
            GenericItemInput("n%04d" % i, "u%d" % (i % 7), "r%d" % (i % 3),
                             "deep chain item %d body" % i)
            for i in range(n)
        ]
        for i in range(n - 1):
            items[i].references = ["n%04d" % (i + 1)]
        results, stats = eng.process(
            items, similarity_fn=lambda a, b: 0.0, relation_mode="references"
        )
        self.assertEqual(stats["scc_count"], n)
        self.assertEqual(stats["cycle_count"], 0)
        self.assertEqual(len(results), n)

    def test_co2_t11_large_cycle_no_recursion_error(self):
        eng = SieveCoreEngine()
        n = 10000
        items = [
            GenericItemInput("n%04d" % i, "u%d" % (i % 7), "r%d" % (i % 3),
                             "big ring item %d body" % i)
            for i in range(n)
        ]
        for i in range(n):
            items[i].references = ["n%04d" % ((i + 1) % n)]
        results, stats = eng.process(
            items, similarity_fn=lambda a, b: 0.0, relation_mode="references"
        )
        self.assertEqual(stats["scc_count"], 1)
        self.assertEqual(stats["cycle_count"], 1)
        self.assertEqual(len(results), 1)
        cycle = results[0].cycles[0]
        self.assertEqual(len(cycle), n)
        self.assertEqual(cycle[0], "n0000")
        self.assertEqual(cycle[-1], "n9999")


class TestCo2T12ModeValidation(unittest.TestCase):
    """CO2-T12: invalid relation_mode raises; the default mode reports
    cycles/cites as None and the four new stats keys as 0, appended after
    the existing keys."""

    def test_co2_t12_invalid_relation_mode_raises(self):
        eng = SieveCoreEngine()
        items = [GenericItemInput("1", "u1", "r1", "alpha radar signal here")]
        with self.assertRaises(ValueError):
            eng.process(items, relation_mode="citations")

    def test_co2_t12_default_mode_new_fields_and_stats(self):
        eng = SieveCoreEngine()
        items = [
            GenericItemInput("1", "u1", "r1", "alpha radar signal detected"),
            GenericItemInput("2", "u2", "r2", "bravo convoy arrives at pier",
                             references=["1"]),
        ]
        results, stats = eng.process(items)
        self.assertIsNone(results[0].cycles)
        self.assertIsNone(results[1].cites)
        self.assertEqual(stats["scc_count"], 0)
        self.assertEqual(stats["cycle_count"], 0)
        self.assertEqual(stats["references_dropped"], 0)
        self.assertEqual(stats["self_references_ignored"], 0)
        self.assertEqual(list(stats.keys()), STATS_KEY_ORDER)


class TestCo2T13NoContentLeak(unittest.TestCase):
    """CO2-T13: item content and payload never appear in the new fields or
    in stats."""

    def test_co2_t13_no_content_or_payload_in_new_fields(self):
        eng = SieveCoreEngine()
        a = GenericItemInput(
            "A", "u1", "r1", "SECRET_CONTENT_ALPHA_XYZ",
            payload={"note": "SECRET_PAYLOAD_ALPHA_XYZ"}, references=["B"],
        )
        b = GenericItemInput("B", "u2", "r2", "SECRET_CONTENT_BETA_XYZ",
                             references=["A"])
        results, stats = eng.process([a, b], relation_mode="references")
        self.assertEqual(len(results), 1)
        blobs = [
            json.dumps(results[0].cycles, ensure_ascii=False),
            json.dumps(results[0].cites, ensure_ascii=False),
            json.dumps(stats, ensure_ascii=False),
        ]
        for blob in blobs:
            self.assertNotIn("SECRET_CONTENT_ALPHA_XYZ", blob)
            self.assertNotIn("SECRET_CONTENT_BETA_XYZ", blob)
            self.assertNotIn("SECRET_PAYLOAD_ALPHA_XYZ", blob)


class TestCo2T14Docs(unittest.TestCase):
    """CO2-T14: the docstring and both READMEs describe the two modes with
    the right terminology."""

    def test_co2_t14_tarjan_docstring_matches_reality(self):
        source = (REPO_ROOT / "sieve_core.py").read_text(encoding="utf-8")
        self.assertIn("connected components", source)
        self.assertIn("strongly connected components", source)
        self.assertIn('"similarity"', source)
        self.assertIn('"references"', source)

    def test_co2_t14_readmes_describe_both_modes(self):
        for name in ("README.md", "README.ja.md"):
            text = (REPO_ROOT / name).read_text(encoding="utf-8")
            with self.subTest(readme=name):
                self.assertIn("relation_mode", text)
                self.assertIn("references", text)
                self.assertIn("cycles", text)
                self.assertIn("cites", text)


class TestCo2T15Version(unittest.TestCase):
    """CO2-T15: version 1.2.0 is consistent across pyproject, READMEs and
    CHANGELOG."""

    def test_co2_t15_version_consistency(self):
        pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('version = "1.2.0"', pyproject)
        self.assertIn("v1.2.0-MVP", (REPO_ROOT / "README.md").read_text(encoding="utf-8"))
        self.assertIn("v1.2.0-MVP", (REPO_ROOT / "README.ja.md").read_text(encoding="utf-8"))
        changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn("## [1.2.0]", changelog)


if __name__ == "__main__":
    unittest.main()
