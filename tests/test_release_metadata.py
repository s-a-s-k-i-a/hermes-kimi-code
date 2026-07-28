from __future__ import annotations

import re
import tomllib
from pathlib import Path

from hermes_kimi_code import __version__


def test_release_versions_agree():
    root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    manifest = (root / "plugin.yaml").read_text(encoding="utf-8")
    match = re.search(r"^version:\s*([^\s#]+)", manifest, re.MULTILINE)

    assert match is not None
    assert project["project"]["version"] == __version__ == match.group(1)


def test_public_release_assets_are_packaged():
    root = Path(__file__).resolve().parents[1]
    manifest = (root / "MANIFEST.in").read_text(encoding="utf-8")

    for filename in ("CHANGELOG.md", "SECURITY.md", "plugin.yaml", "after-install.md"):
        assert f"include {filename}" in manifest
