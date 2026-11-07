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
    (Tarjan SCC / average-linkage Jaccard). Tarjan's SCC runs over a symmetric
    similarity-edge graph in the default "similarity" mode — where the SCCs
    therefore coincide with undirected connected components — and over a
    directed citation-edge graph in the "references" mode.
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
        references (Optional[List[str]]|Optional[Tuple[str, ...]]): item_ids this
            item cites, replies to, or reposts from (optional). Used only in
            the "references" relation mode; never read in the default mode.
    """
    def __init__(
        self,
        item_id: str,
        author_id: str,
        author_role: str,
        content: str,
        payload: Any = None,
        references: Any = None
    ):
        self.item_id = item_id
        self.author_id = author_id
        self.author_role = author_role
        self.content = content
        self.payload = payload
        self.references = references


class FactClusterOutput:
    """
    A cluster of facts verified and extracted by the Sieve-Core Engine.

    Attributes:
        fact_id (str): ID of the extracted fact
        representative_content (str): the representative (longest) text in the cluster
        item_ids (List[str]): the input item IDs aggregated into this fact
        independent_sources_count (int): number of independent verifying sources (roles)
        confidence_score (float): confidence score computed by the sigmoid function (0.0-1.0)
        cycles (Optional[List[List[str]]]): size >= 2 strongly connected
            components (citation cycles) contained in this fact, in input
            appearance order; None in the default "similarity" mode.
        cites (Optional[List[str]]): fact_ids of other facts this fact's
            items cite, ascending; None in the default "similarity" mode.
    """
    def __init__(
        self,
        fact_id: str,
        representative_content: str,
        item_ids: List[str],
        independent_sources_count: int,
        confidence_score: float,
        cycles: Any = None,
        cites: Any = None
    ):
        self.fact_id = fact_id
        self.representative_content = representative_content
        self.item_ids = item_ids
        self.independent_sources_count = independent_sources_count
        self.confidence_score = confidence_score
        self.cycles = cycles
        self.cites = cites


class SieveCoreEngine:
    """
    A fully deterministic fact-checking / extraction core engine.

    Two relation modes share the same 4-stage pipeline: the default
    "similarity" mode builds symmetric similarity edges (as since v1.0.0,
    so the detected SCCs equal undirected connected components), while the
    "references" mode builds directed citation edges A -> B ("A cites B")
    from the items' optional `references` lists, collapses mutually citing
    cycles (strongly connected components) into single facts, and reports
    the cycles and the citation flow between merged facts (`cycles` and
    `cites` on FactClusterOutput, plus four new `stats` keys).
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
        Tarjan's strongly connected components (SCC) algorithm, implemented
        iteratively (an explicit call-stack simulation) instead of recursively,
        to avoid hitting Python's recursion limit on deep input graphs.

        Terminology follows the relation mode: in the default "similarity"
        mode the edge set is symmetric (every edge is added in both
        directions), so the detected SCCs coincide with undirected connected
        components. In the "references" mode the edges are directed citation
        edges (A -> B means "A cites B"), so the detected SCCs are strongly
        connected components in the strict sense.
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
        similarity_fn: Callable[[str, str], float] = None,
        relation_mode: str = "similarity"
    ) -> Tuple[List[FactClusterOutput], Dict[str, Any]]:
        """
        Run the 4-stage pipeline to extract and score facts.

        Args:
            items: the input items.
            density_fn: optional density evaluator (default: unique-char
                ratio).
            similarity_fn: optional similarity evaluator (default: 2-gram
                Jaccard). Feeds the similarity edges in "similarity" mode
                and the average-linkage merge in both modes.
            relation_mode: "similarity" (default) builds symmetric
                similarity edges exactly as before (the items' `references`
                are never read); "references" builds directed edges
                A -> B ("A cites B") from the items' `references` lists,
                and reports `cycles` / `cites`. Any other value raises
                ValueError.
        """
        if relation_mode not in ("similarity", "references"):
            raise ValueError(
                f"Unknown relation_mode: {relation_mode!r}. "
                'Allowed values are "similarity" (default) and "references".'
            )
        references_mode = relation_mode == "references"
        if density_fn is None:
            density_fn = self._default_density_fn
        if similarity_fn is None:
            similarity_fn = lambda a, b: self._jaccard_similarity(
                self._ngram_extract(a), self._ngram_extract(b)
            )

        # 0. Input validation: duplicate item_ids are rejected BEFORE any
        # filtering, so duplicates among items that would later be filtered
        # out are also caught (previously they slipped through).
        seen_ids: Set[str] = set()
        duplicate_ids: Set[str] = set()
        for item in items:
            if item.item_id in seen_ids:
                duplicate_ids.add(item.item_id)
            seen_ids.add(item.item_id)
        if duplicate_ids:
            raise ValueError(
                f"Duplicate item_id(s) found: {sorted(duplicate_ids)}."
                " item_id must be unique across all input items."
            )

        # 1. Density score filter. Dropped items are recorded as
        # (item_id, reason) pairs in input appearance order, with a closed
        # vocabulary reason and no item content.
        filtered_items: List[GenericItemInput] = []
        dropped: List[Dict[str, str]] = []
        for item in items:
            if density_fn(item.content) >= self.density_threshold:
                filtered_items.append(item)
            else:
                dropped.append({"item_id": item.item_id, "reason": "low_density"})

        item_map = {item.item_id: item for item in filtered_items}
        node_ids = list(item_map.keys())
        # Input appearance order is the global tie-breaking order.
        order_index: Dict[str, int] = {nid: pos for pos, nid in enumerate(node_ids)}

        # 2. Build edges. In the default "similarity" mode the edge set is
        # symmetric (an edge is added in both directions), so the detected
        # SCCs coincide with undirected connected components. In the
        # "references" mode the edges are directed citation edges built
        # from the items' reference lists, so Tarjan SCC works in its
        # strict sense; similarity is not consulted for edges in this mode.
        adj_list: Dict[str, List[str]] = {nid: [] for nid in node_ids}

        if references_mode:
            # 2a. Fail-closed validation of the reference relations on the
            # raw input (surviving and density-filtered items alike).
            # Messages carry only item IDs, never item content.
            known_ids = {item.item_id for item in items}
            for item in items:
                refs = item.references
                if refs is None:
                    continue
                if not isinstance(refs, (list, tuple)) or not all(
                    isinstance(ref, str) for ref in refs
                ):
                    raise ValueError(
                        f"Invalid references for item '{item.item_id}':"
                        " references must be None or a list/tuple of"
                        " item_id strings."
                    )
                unknown = sorted({ref for ref in refs if ref not in known_ids})
                if unknown:
                    raise ValueError(
                        f"Unknown reference item_id(s) for item"
                        f" '{item.item_id}': {unknown}. Each reference must"
                        " name an item_id that exists in the input."
                    )

            # 2b. Directed edges A -> B ("A cites B") from the normalized
            # reference lists (duplicates collapse to their first
            # occurrence). Self references are ignored and counted;
            # references targeting density-filtered items are not edges and
            # are counted; references issued by filtered items are not
            # edges either (their source is not a node of the graph).
            dropped_ids = {entry["item_id"] for entry in dropped}
            reference_edges: List[Tuple[str, str]] = []
            self_references_ignored = 0
            references_dropped = 0
            for item in items:
                refs = item.references
                if refs is None:
                    continue
                seen_refs: Set[str] = set()
                for ref in refs:
                    if ref in seen_refs:
                        continue
                    seen_refs.add(ref)
                    if ref == item.item_id:
                        self_references_ignored += 1
                    elif ref in dropped_ids:
                        references_dropped += 1
                    elif item.item_id not in dropped_ids:
                        reference_edges.append((item.item_id, ref))

            for src, dst in reference_edges:
                adj_list[src].append(dst)
        else:
            for i in range(len(node_ids)):
                for j in range(i + 1, len(node_ids)):
                    id_a, id_b = node_ids[i], node_ids[j]
                    sim = similarity_fn(item_map[id_a].content, item_map[id_b].content)
                    if sim >= self.exact_sim_threshold:
                        adj_list[id_a].append(id_b)
                        adj_list[id_b].append(id_a)

        # Enumerate neighbors in input appearance order so the traversal (and
        # therefore the detected-component order and result assembly) is fully
        # deterministic across runs and PYTHONHASHSEED values.
        ordered_adj_list: Dict[str, List[str]] = {
            nid: sorted(neighbors, key=order_index.__getitem__)
            for nid, neighbors in adj_list.items()
        }

        scc_clusters = self._tarjan_scc(node_ids, ordered_adj_list)

        # 3. Deterministic cluster merging (average-linkage, to mitigate chaining).
        # Each cluster is kept sorted in input appearance order, and the cluster
        # list itself is ordered by each cluster's earliest input position.
        clusters: List[List[str]] = [
            sorted(scc, key=lambda nid: order_index[nid]) for scc in scc_clusters
        ]
        clusters.sort(key=lambda cl: order_index[cl[0]])
        merged = True
        while merged:
            merged = False
            new_clusters: List[List[str]] = []
            visited = [False] * len(clusters)

            for i in range(len(clusters)):
                if visited[i]:
                    continue
                current_cluster = list(clusters[i])
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
                        current_cluster = sorted(
                            current_cluster + clusters[j],
                            key=order_index.__getitem__,
                        )
                        visited[j] = True
                        merged = True

                visited[i] = True
                new_clusters.append(current_cluster)
            clusters = new_clusters

        # 4. Sigmoid confidence scoring and result assembly
        if references_mode:
            # cycles: the size >= 2 SCCs contained in each fact, listed in
            # input appearance order (inside each SCC and across SCCs).
            ordered_sccs = [
                sorted(scc, key=lambda nid: order_index[nid])
                for scc in scc_clusters
            ]
            ordered_sccs.sort(key=lambda cl: order_index[cl[0]])
            cluster_pos: Dict[str, int] = {}
            for pos, cluster in enumerate(clusters):
                for nid in cluster:
                    cluster_pos[nid] = pos
            cycles_by_pos: Dict[int, List[List[str]]] = {}
            for scc in ordered_sccs:
                if len(scc) >= 2:
                    cycles_by_pos.setdefault(cluster_pos[scc[0]], []).append(scc)
            # cites: the citation flow between merged facts (the
            # condensation of the reference graph), expressed with the
            # final fact IDs. Citations inside a merged fact are excluded;
            # facts linked by citations in both directions stay two facts.
            fact_id_by_pos = {
                pos: f"FACT-{pos+1:03d}" for pos in range(len(clusters))
            }
            cites_by_pos: Dict[int, Set[str]] = {
                pos: set() for pos in range(len(clusters))
            }
            for src, dst in reference_edges:
                src_pos = cluster_pos[src]
                dst_pos = cluster_pos[dst]
                if src_pos != dst_pos:
                    cites_by_pos[src_pos].add(fact_id_by_pos[dst_pos])

        results: List[FactClusterOutput] = []
        for idx, cluster in enumerate(clusters):
            # cluster is already sorted by input appearance order: item_ids and
            # the representative tie-break below follow that order.
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
                    cycles=(
                        cycles_by_pos.get(idx, [])
                        if references_mode else None
                    ),
                    cites=(
                        sorted(cites_by_pos[idx]) if references_mode else None
                    ),
                )
            )

        # Deterministic result order: confidence descending; ties keep facts
        # ordered by their earliest input appearance (stable sort).
        results.sort(key=lambda x: order_index[x.item_ids[0]])
        results.sort(key=lambda x: x.confidence_score, reverse=True)

        if references_mode:
            scc_count_value = len(scc_clusters)
            cycle_count_value = sum(
                1 for scc in scc_clusters if len(scc) >= 2
            )
            refs_dropped_value = references_dropped
            self_refs_value = self_references_ignored
        else:
            # The default mode has no directed relations, so the four new
            # stats keys are always present and zero.
            scc_count_value = 0
            cycle_count_value = 0
            refs_dropped_value = 0
            self_refs_value = 0

        stats = {
            "raw_input_count": len(items),
            "filtered_input_count": len(filtered_items),
            "extracted_facts_count": len(results),
            "dropped": dropped,
            "scc_count": scc_count_value,
            "cycle_count": cycle_count_value,
            "references_dropped": refs_dropped_value,
            "self_references_ignored": self_refs_value,
        }

        return results, stats