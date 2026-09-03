# Contributing to Sieve-Core

Thanks for your interest in contributing to `Sieve-Core`! Bug reports, feature proposals, documentation improvements, and code contributions are all welcome.

By participating in this project, you are expected to uphold our [Code of Conduct](CODE_OF_CONDUCT.md).

## Design principles

Sieve-Core is developed under a strict set of design principles:

1. **Deterministic**: no probabilistic behavior. The same input must always produce the same output.
2. **Zero-Dependencies**: the core engine (`sieve_core.py`) must be implemented using only the Python standard library.
3. **Auditability**: the decision process must be traceable by a human, via explicit graph structure and mathematical models.

---

## Setting up a development environment

No special setup is required. Anything running Python 3.8+ will work.

```bash
# Clone the repository
git clone https://github.com/neguseatama/sieve-core.git
cd sieve-core

# Run the tests (no external dependencies needed)
python3 -m unittest discover -v
```

## How to contribute

### 1. Open or check an Issue

For any significant feature addition or change in behavior, please open an Issue to discuss it first, to avoid duplicate or conflicting work.

### 2. Create a branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

### 3. Make your changes and test them

* If you change the core engine, make sure the existing tests (`test_sieve_core.py`, `test_multi_domain.py`) still pass.
* Add a corresponding unit test for any new feature or bug fix.

### 4. Submit a pull request

* Fill out the PR template with a description of your change.
* Confirm that all tests pass locally before submitting.
* Once opened, your PR will also run automatically against the CI workflow (`.github/workflows/tests.yml`), which tests across Python 3.8-3.12. A red CI check means something needs fixing before merge.
