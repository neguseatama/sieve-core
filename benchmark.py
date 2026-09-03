"""
benchmark.py
============

Measures SieveCoreEngine's processing time as a function of item count N.
The benchmark table in the README's "Known Limitations" section is the
output of this script. Numbers vary by environment, so we recommend
re-running this on your own machine before publishing or after making a
significant change.

Usage: python3 benchmark.py
"""

import random
import time

from sieve_core import GenericItemInput, SieveCoreEngine

random.seed(42)

BASE_TEMPLATES = [
    "An accident was reported near downtown; investigation is ongoing.",
    "A fire in the industrial district is now extinguished, no injuries.",
    "The mayor outlined a new disaster preparedness plan today.",
    "The coastal line is partially suspended due to the approaching typhoon.",
    "Firefighters are checking reports of a strange odor near the plant.",
]

ROLES = ["bot", "citizen", "media", "official", "anonymous"]


def random_text() -> str:
    """Append random noise characters to a template to avoid exact duplicates."""
    template = random.choice(BASE_TEMPLATES)
    noise = "".join(random.choice("abcdefghij") for _ in range(random.randint(0, 8)))
    return template + " " + noise


def build_items(n: int) -> list:
    return [
        GenericItemInput(f"item_{i}", f"user_{i}", random.choice(ROLES), random_text())
        for i in range(n)
    ]


def main() -> None:
    # The density filter's own cost isn't the focus here, so let everything through (threshold 0.0).
    # jaccard_merge_threshold is raised from the 0.15 default: English text shares far more
    # common short words (the, is, near, ...) between unrelated sentences than Japanese
    # kanji-based text does, so at the default threshold these 5 unrelated templates would
    # all merge into a single cluster regardless of scale. Raising the threshold keeps the
    # benchmark's cluster count meaningful (multiple distinct facts) rather than always 1.
    engine = SieveCoreEngine(density_threshold=0.0, jaccard_merge_threshold=0.40)

    print(f"{'N':>6} | {'time(sec)':>10} | {'facts':>6}")
    print("-" * 30)
    for n in [50, 100, 250, 500, 1000, 2000]:
        items = build_items(n)
        t0 = time.perf_counter()
        results, _ = engine.process(items)
        elapsed = time.perf_counter() - t0
        print(f"{n:>6} | {elapsed:>10.3f} | {len(results):>6}")


if __name__ == "__main__":
    main()
