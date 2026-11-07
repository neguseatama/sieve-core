# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2026-11-08

### Added
- **Directed reference relations**: `GenericItemInput` accepts an optional
  `references` argument (appended after the existing arguments) — a list or
  tuple of `item_id` strings this item cites, replies to, or reposts.
  Validation is fail-closed and raises `ValueError` for non list/tuple values,
  non-string elements, and references to unknown `item_id`s (listed ascending,
  never item content). Duplicate references collapse to their first
  occurrence; self references are ignored and counted.
- **`relation_mode` argument on `SieveCoreEngine.process()`** (appended after
  the existing arguments, default `"similarity"`):
  - `"similarity"` keeps the v1.1.1 behavior byte for byte; the
    `references` argument is never read.
  - `"references"` builds directed edges `A -> B` ("A cites B") from the
    reference lists and runs Tarjan SCC in its strict sense. Similarity is
    not consulted for edges in this mode (`exact_sim_threshold` is unused
    there); the average-linkage merge still works on the detected SCCs as
    units, by similarity, exactly as before. Inputs without any `references`
    yield single-item SCCs and merge purely by similarity.
- **`cycles` / `cites` output fields** (appended to `FactClusterOutput` with
  defaults, so positional construction is preserved): `cycles` lists the
  size >= 2 SCCs (mutually citing cycles) contained in each fact, in input
  appearance order — `None` in "similarity" mode. `cites` lists the
  `fact_id`s of the other facts this fact's items cite, ascending, excluding
  citations inside a merged fact; facts linked by citations in both
  directions stay separate facts — `None` in "similarity" mode.
- **Four new `stats` keys**, always present (0 in "similarity" mode):
  `scc_count`, `cycle_count`, `references_dropped` (references targeting
  density-filtered items are not edges and are counted here), and
  `self_references_ignored`.

### Changed
- **Docs terminology aligned with the two modes**: the `_tarjan_scc`
  docstring, the class/module descriptions and both READMEs now state that
  "similarity" mode detects undirected connected components (its edge set is
  symmetric), while "references" mode detects strongly connected components
  of directed citation edges. The default-mode code behavior is unchanged.
- **Version bumped to 1.2.0**.

### Notes
- Determinism rules are unchanged: neighbor traversal, cluster ordering and
  fact ordering keep following input appearance order, and outputs are
  byte-identical across `PYTHONHASHSEED` values in both modes. Item content
  and `payload` never appear in the new fields, `stats`, or error messages.

## [1.1.1] - 2026-11-07

### Changed
- **Packaging metadata migrated to the PEP 639 (SPDX) form**:
  `project.license` is now the plain SPDX expression `"MIT"` with
  `license-files = ["LICENSE"]`, and the deprecated
  `License :: OSI Approved :: MIT License` classifier was removed (the
  SPDX expression carries the licensing information). The `build-system`
  requirement is now `setuptools>=77.0`, the first release that
  understands PEP 639. This eliminates both setuptools deprecation
  warnings emitted since the 1.1.0 builds (`project.license` as a TOML
  table / License classifiers), whose announced removal deadline is
  2027-02-18. The packaging form mirrors sieve-referee.
- **Version bumped to 1.1.1**. A packaging-metadata-only release: no
  runtime code changes, the whole existing suite passes unchanged. PyPI
  artifacts are immutable, so the corrected metadata ships as a new
  version rather than a rebuild of 1.1.0.

## [1.1.0] - 2026-11-07

### Added
- **Deterministic output order**: `item_ids` are ordered by first appearance
  in the input, and the representative (longest content) is the
  earliest-appearing item among ties. Every remaining dependence on Python's
  set iteration order (graph-traversal neighbor order, cluster ordering, and
  fact ordering on confidence ties) is resolved by the same
  input-appearance rule. Outputs for the same input are byte-identical
  across processes and `PYTHONHASHSEED` values (pinned regression tests).
- **`dropped` list in `stats`**: every item removed from the results is
  reported as `{"item_id": ..., "reason": ...}` in input appearance order.
  The reason comes from a closed vocabulary — `low_density` is the only
  removal stage in the current pipeline (density filter). The key is always
  present and is an empty list when nothing was dropped. Item content and
  exception messages are never included.

### Changed
- **Duplicate `item_id`s are now rejected before the density filter.**
  Inputs whose duplicate-ID items would all have been filtered out previously
  slipped through; they now raise `ValueError` like any other input error.
  Inputs with a single occurrence of each ID behave exactly as before.
- **Version bumped to 1.1.0**, and the `pyproject.toml` development-status
  classifier corrected to `Development Status :: 3 - Alpha` to match the
  README's own MVP description.

### Fixed
- **Docs terminology**: the graph-reduction stage was documented as "Tarjan
  strongly connected components", but the code builds an undirected graph
  (edges are added in both directions), so the detected groups are undirected
  connected components. The documents now describe this accurately; the code
  itself is unchanged.
