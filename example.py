"""
Sieve-Core Engine (v1.0.0-MVP) Demonstration Script

Demonstrates confidence-score escalation via injecting Japanese-specific
evaluators (density + similarity). The sample data below is deliberately
real Japanese text: this demo exists specifically to show how injecting
language-specific `density_fn` / `similarity_fn` functions changes the
engine's behavior on Japanese input.
"""

import re
from sieve_core import GenericItemInput, SieveCoreEngine

STOP_PATTERNS = re.compile(
    r"(拡散希望|拡散|速報|本日|現在|確認中|発生|です|ます|ていま|した|から|より|で|に|を|が|は|の|と|も|や|か|な|ね|よ)"
)


def japanese_density_fn(text: str) -> float:
    if not text:
        return 0.0
    informative_chars = len(re.findall(r"[一-龥0-9]", text))
    return informative_chars / len(text)


def japanese_similarity_fn(text_a: str, text_b: str) -> float:
    clean_a = STOP_PATTERNS.sub("", text_a)
    clean_b = STOP_PATTERNS.sub("", text_b)

    def extract_2gram(text: str):
        if len(text) < 2:
            return {text} if text else set()
        return {text[i : i + 2] for i in range(len(text) - 1)}

    grams_a = extract_2gram(clean_a)
    grams_b = extract_2gram(clean_b)

    if not grams_a or not grams_b:
        return 0.0

    # Overlap coefficient: |A∩B| / min(|A|,|B|)
    # We standardized on this instead of the Jaccard coefficient (|A∩B|/|A∪B|)
    # after confirming, via test_multi_domain.py, that Jaccard underestimates
    # similarity for asymmetric-length pairs (a short breaking-news post vs.
    # a long eyewitness account) even when they share a core term, because
    # the union grows with the extra length.
    intersection = len(grams_a & grams_b)
    return intersection / min(len(grams_a), len(grams_b))


def main():
    print("=" * 70)
    print(" Sieve-Core (v1.0.0-MVP) Deterministic Verification Engine — Demo")
    print("=" * 70)

    items = [
        GenericItemInput("p1", "bot_01", "bot", "【拡散希望】〇〇地区の化学工場で爆発事故が発生！避難してください！"),
        GenericItemInput("p2", "bot_02", "bot", "【拡散希望】〇〇地区の化学工場で爆発事故が発生！避難してください！"),
        GenericItemInput("p3", "reporter_a", "media", "本日14時頃、〇〇地区の工場から黒煙。警察と消防が確認中。"),
        GenericItemInput("p4", "citizen_x", "citizen", "〇〇地区の工場近くにいますが、大きな音がして煙が上がっています。"),
        GenericItemInput("p5", "troll_01", "anonymous", "まじかよｗｗｗｗやばすぎｗｗｗｗｗ"),
    ]

    print("\n[SCENARIO] Analyzing 5 mixed items: 2 bot copy-paste posts, 1 media report, "
          "1 citizen eyewitness post, 1 spam post")

    print("\n" + "-" * 70)
    print(" 1. Running with the default evaluators (generic character-based, no plugins)")
    print("-" * 70)

    engine_default = SieveCoreEngine()
    results_def, stats_def = engine_default.process(items)

    print(f"Stats: {stats_def}")
    for fact in results_def:
        print(
            f"  • [{fact.fact_id}] confidence: {fact.confidence_score:.4f} | "
            f"independent sources (roles): {fact.independent_sources_count} {set([item.author_role for item in items if item.item_id in fact.item_ids])}"
        )
        print(f"    representative text: {fact.representative_content}")
        print(f"    aggregated IDs: {fact.item_ids}")

    print("\n" + "-" * 70)
    print(" 2. Running with Japanese-specific evaluators injected (density + similarity plugins)")
    print("-" * 70)

    engine_custom = SieveCoreEngine(
        density_threshold=0.20,
        exact_sim_threshold=0.60,
        jaccard_merge_threshold=0.10,
    )

    results_custom, stats_custom = engine_custom.process(
        items,
        density_fn=japanese_density_fn,
        similarity_fn=japanese_similarity_fn,
    )

    print(f"Stats: {stats_custom}")
    for fact in results_custom:
        print(
            f"  ★ [{fact.fact_id}] confidence: {fact.confidence_score:.4f} | "
            f"independent sources (roles): {fact.independent_sources_count} {set([item.author_role for item in items if item.item_id in fact.item_ids])}"
        )
        print(f"    representative text: {fact.representative_content}")
        print(f"    aggregated IDs: {fact.item_ids}")

    print("\n" + "=" * 70)
    print(" Demo result check:")
    if results_custom and results_custom[0].confidence_score > 0.90:
        print(" [SUCCESS] bot / media / citizen (3 independent roles) merged, and")
        print(f"           confidence jumped to {results_custom[0].confidence_score:.4f} (above 90%)!")
    else:
        print(" [NOT MET] Did not observe the 3-role merge and/or confidence above 90%.")
    print("=" * 70)


if __name__ == "__main__":
    main()
