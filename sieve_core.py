"""
Sieve-Core (v1.0.0-MVP)
Deterministic Fact-Checking & Extraction Engine

Author: Kai IWASAKI
License: MIT
Description:
    A core engine that, in response to the flood of misinformation, copy-paste,
    and spin control driven by AI (generative AI and black-box judgments),
    deliberately avoids using AI and instead extracts only verified facts using
    a fully deterministic mathematical model and graph theory
    (Tarjan SCC / average-linkage Jaccard).
"""

import math
from typing import Callable, List, Dict, Set, Tuple, Any


class GenericItemInput:
    """
    A single input data element to feed into the Sieve-Core Engine.

    Attributes:
        item_id (str): unique identifier for this item
        author_id (str): identifier of the poster/source
        author_role (str): the poster's independent attribute (e.g. "citizen", "media", "official")
        content (str): the text content to analyze
        payload (Any): arbitrary metadata (optional)
    """
    def __init__(
        self,
        item_id: str,
        author_id: str,
        author_role: str,
        content: str,
        payload: Any = None
    ):
        self.item_id = item_id
        self.author_id = author_id
        self.author_role = author_role
        self.content = content
        self.payload = payload


class FactClusterOutput:
    """
    A cluster of facts verified and extracted by the Sieve-Core Engine.

    Attributes:
        fact_id (str): ID of the extracted fact
        representative_content (str): the representative (longest) text in the cluster
        item_ids (List[str]): the input item IDs aggregated into this fact
        independent_sources_count (int): number of independent verifying sources (roles)
        confidence_score (float): confidence score computed by the sigmoid function (0.0-1.0)
    """
    def __init__(
        self,
        fact_id: str,
        representative_content: str,
        item_ids: List[str],
        independent_sources_count: int,
        confidence_score: float
    ):
        self.fact_id = fact_id
        self.representative_content = representative_content
        self.item_ids = item_ids
        self.independent_sources_count = independent_sources_count
        self.confidence_score = confidence_score


class SieveCoreEngine:
    """
    A fully deterministic fact-checking / extraction core engine.
    """
    def __init__(
        self,
        density_threshold: float = 0.35,
        exact_sim_threshold: float = 0.65,
        jaccard_merge_threshold: float = 0.15,
        sigmoid_alpha: float = 3.0,
        sigmoid_k0: float = 1.5
    ):
        """
        Initialize the engine's various thresholds.

        Args:
            density_threshold (float): minimum information density; removes low-density
                text (filler expressions, smokescreen noise).
            exact_sim_threshold (float): similarity threshold above which Tarjan SCC treats
                two items as identical wording / a copy-paste cycle.
            jaccard_merge_threshold (float): threshold at which clusters are merged to
                account for paraphrasing/variation.
            sigmoid_alpha (float): the steepness of the confidence sigmoid curve.
            sigmoid_k0 (float): the inflection point (independent role count) at which
                confidence crosses 0.5.
        """
        self.density_threshold = density_threshold
        self.exact_sim_threshold = exact_sim_threshold
        self.jaccard_merge_threshold = jaccard_merge_threshold
        self.sigmoid_alpha = sigmoid_alpha
        self.sigmoid_k0 = sigmoid_k0

    def _default_density_fn(self, text: str) -> float:
        """Default information-density calculation, based on the ratio of unique characters."""
        if not text:
            return 0.0
        return len(set(text)) / len(text)

    def _ngram_extract(self, text: str, n: int = 2) -> Set[str]:
        """Extract n-gram features."""
        if len(text) < n:
            return {text}
        return {text[i:i + n] for i in range(len(text) - n + 1)}

    def _jaccard_similarity(self, set_a: Set[str], set_b: Set[str]) -> float:
        """Exact Jaccard similarity computation (O(1)-O(N))."""
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return intersection / union if union > 0 else 0.0

    def calculate_confidence(self, k_roles: int) -> float:
        """
        Compute a confidence score (0.0-1.0) from the independent source count (k_roles).

        Formula:
            f(k) = 1 / (1 + exp(-alpha * (k - k0)))

        This is factored out as its own method rather than inlined in process() so
        that the sigmoid curve's mathematical properties (monotonic increase, point
        symmetry around the inflection point, saturating behavior at the extremes)
        can be unit-tested directly, without going through an end-to-end run.
        """
        confidence = 1.0 / (1.0 + math.exp(-self.sigmoid_alpha * (k_roles - self.sigmoid_k0)))
        return round(confidence, 4)

    def _tarjan_scc(self, nodes: List[str], adj_list: Dict[str, Set[str]]) -> List[List[str]]:
        """
        Tarjan's strongly-connected-components (SCC) algorithm, implemented
        iteratively (an explicit call-stack simulation) instead of recursively,
        to avoid hitting Python's recursion limit on deep input graphs.
        """
        index = 0
        stack: List[str] = []
        indices: Dict[str, int] = {}
        lowlink: Dict[str, int] = {}
        on_stack: Dict[str, bool] = {node: False for node in nodes}
        sccs: List[List[str]] = []

        for node in nodes:
            if node not in indices:
                work_stack = [(node, 0, list(adj_list.get(node, [])))]
                indices[node] = index
                lowlink[node] = index
                index += 1
                stack.append(node)
                on_stack[node] = True

                while work_stack:
                    v, i, neighbors = work_stack[-1]
                    if i < len(neighbors):
                        w = neighbors[i]
                        work_stack[-1] = (v, i + 1, neighbors)
                        if w not in indices:
                            indices[w] = index
                            lowlink[w] = index
                            index += 1
                            stack.append(w)
                            on_stack[w] = True
                            work_stack.append((w, 0, list(adj_list.get(w, []))))
                        elif on_stack[w]:
                            lowlink[v] = min(lowlink[v], indices[w])
                    else:
                        work_stack.pop()
                        if work_stack:
                            parent = work_stack[-1][0]
                            lowlink[parent] = min(lowlink[parent], lowlink[v])

                        if lowlink[v] == indices[v]:
                            scc = []
                            while True:
                                w = stack.pop()
                                on_stack[w] = False
                                scc.append(w)
                                if w == v:
                                    break
                            sccs.append(scc)
        return sccs

    def process(
        self,
        items: List[GenericItemInput],
        density_fn: Callable[[str], float] = None,
        similarity_fn: Callable[[str, str], float] = None
    ) -> Tuple[List[FactClusterOutput], Dict[str, Any]]:
        """
        Run the 4-stage pipeline to extract and score facts.
        """
        if density_fn is None:
            density_fn = self._default_density_fn
        if similarity_fn is None:
            similarity_fn = lambda a, b: self._jaccard_similarity(
                self._ngram_extract(a), self._ngram_extract(b)
            )

        # 1. Density score filter
        filtered_items = [item for item in items if density_fn(item.content) >= self.density_threshold]

        # Explicitly detect duplicate item_ids (to preserve full auditability).
        seen_ids: Set[str] = set()
        duplicate_ids: Set[str] = set()
        for item in filtered_items:
            if item.item_id in seen_ids:
                duplicate_ids.add(item.item_id)
            seen_ids.add(item.item_id)
        if duplicate_ids:
            raise ValueError(
                f"Duplicate item_id(s) found: {sorted(duplicate_ids)}."
                " item_id must be unique across all input items."
            )

        item_map = {item.item_id: item for item in filtered_items}
        node_ids = list(item_map.keys())

        # 2. Build a directed graph & collapse copy-paste/bot-amplification cycles via Tarjan SCC
        adj_list: Dict[str, Set[str]] = {nid: set() for nid in node_ids}

        for i in range(len(node_ids)):
            for j in range(i + 1, len(node_ids)):
                id_a, id_b = node_ids[i], node_ids[j]
                sim = similarity_fn(item_map[id_a].content, item_map[id_b].content)
                if sim >= self.exact_sim_threshold:
                    adj_list[id_a].add(id_b)
                    adj_list[id_b].add(id_a)

        scc_clusters = self._tarjan_scc(node_ids, adj_list)

        # 3. Deterministic cluster merging (average-linkage, to mitigate chaining)
        clusters: List[Set[str]] = [set(scc) for scc in scc_clusters]
        merged = True
        while merged:
            merged = False
            new_clusters: List[Set[str]] = []
            visited = [False] * len(clusters)

            for i in range(len(clusters)):
                if visited[i]:
                    continue
                current_cluster = set(clusters[i])
                for j in range(i + 1, len(clusters)):
                    if visited[j]:
                        continue
                    total_sim = sum(
                        similarity_fn(item_map[id_a].content, item_map[id_b].content)
                        for id_a in current_cluster
                        for id_b in clusters[j]
                    )
                    avg_sim = total_sim / (len(current_cluster) * len(clusters[j]))
                    if avg_sim >= self.jaccard_merge_threshold:
                        current_cluster.update(clusters[j])
                        visited[j] = True
                        merged = True

                visited[i] = True
                new_clusters.append(current_cluster)
            clusters = new_clusters

        # 4. Sigmoid confidence scoring and result assembly
        results: List[FactClusterOutput] = []
        for idx, cluster in enumerate(clusters):
            cluster_items = [item_map[nid] for nid in cluster]
            unique_roles = {item.author_role for item in cluster_items}
            k_roles = len(unique_roles)

            confidence = self.calculate_confidence(k_roles)
            rep_item = max(cluster_items, key=lambda x: len(x.content))

            results.append(
                FactClusterOutput(
                    fact_id=f"FACT-{idx+1:03d}",
                    representative_content=rep_item.content,
                    item_ids=[item.item_id for item in cluster_items],
                    independent_sources_count=k_roles,
                    confidence_score=round(confidence, 4),
                )
            )

        results.sort(key=lambda x: x.confidence_score, reverse=True)

        stats = {
            "raw_input_count": len(items),
            "filtered_input_count": len(filtered_items),
            "extracted_facts_count": len(results),
        }

        return results, stats