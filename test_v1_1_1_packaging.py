"""
Probes for the sieve-core v1.1.1 lane (packaging metadata, red-first).
Standard Library Only (Zero-Dependencies).

What this lane fixes: setuptools (>= 77) emits deprecation warnings for the
v1.1.0 packaging metadata and announces removal by 2027-02-18:

  - WARNING `project.license` as a TOML table is deprecated
  - WARNING License classifiers are deprecated.

sieve-referee already uses the target PEP 639 form, so this lane moves
sieve-core to the same shape:

  - `license` is a plain SPDX expression string (`license = "MIT"`)
  - the LICENSE file is declared via `license-files`
  - the deprecated `License :: OSI Approved :: MIT License` classifier is
    removed (the SPDX expression carries the licensing information)
  - the build backend requires setuptools >= 77 (first release that
    understands PEP 639)
  - the version is bumped to 1.1.1 with a matching CHANGELOG entry

No runtime code changes: sieve_core.py is untouched and the whole existing
suite keeps passing unchanged.

The probes assert on raw file text (not tomllib) so they run on every
Python in the CI matrix, including 3.8, where tomllib does not exist.
"""

import os
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
PYPROJECT = REPO_ROOT / "pyproject.toml"
CHANGELOG = REPO_ROOT / "CHANGELOG.md"


def _read(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


class TestV1_1_1PackagingSPDXLicense(unittest.TestCase):
    """Packaging metadata must use the PEP 639 (SPDX) form, referee-style."""

    def test_license_is_spdx_expression(self):
        text = _read(PYPROJECT)
        self.assertIn('license = "MIT"', text)
        self.assertIsNone(
            re.search(r"(?m)^license\s*=\s*\{", text),
            "project.license must be a plain SPDX string, not a TOML table",
        )

    def test_license_files_declared(self):
        text = _read(PYPROJECT)
        self.assertRegex(
            text,
            r'(?m)^license-files\s*=\s*\["LICENSE"\]',
            "the LICENSE file must be declared via license-files",
        )

    def test_license_classifier_removed(self):
        text = _read(PYPROJECT)
        self.assertNotIn(
            "License :: OSI Approved",
            text,
            "the SPDX expression replaces the deprecated License classifier",
        )

    def test_build_backend_supports_pep639(self):
        text = _read(PYPROJECT)
        self.assertRegex(
            text,
            r"setuptools>=77",
            "build-system requires must ask for a PEP 639 capable setuptools",
        )

    def test_version_and_changelog_consistent(self):
        text = _read(PYPROJECT)
        self.assertRegex(text, r'(?m)^version\s*=\s*"1\.1\.1"')
        self.assertIn("## [1.1.1]", _read(CHANGELOG))


if __name__ == "__main__":
    unittest.main()
