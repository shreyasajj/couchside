import importlib.util
import json
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("stamp_release", ROOT / "flatpak/stamp-release.py")
stamp_release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stamp_release)


def tree(tmp_path):
    (tmp_path / "flatpak").mkdir()
    (tmp_path / "src/couchside").mkdir(parents=True)
    shutil.copy(stamp_release.METAINFO, tmp_path / "flatpak" / stamp_release.METAINFO.name)
    return tmp_path


def test_stamp_writes_build_info_and_metainfo(tmp_path):
    root = tree(tmp_path)
    stamp_release.stamp("0.7.12", "abcdef1234567890", "2026-11-12", root=root)
    assert json.loads((root / "src/couchside/build_info.json").read_text()) == {"version": "0.7.12", "commit": "abcdef123456"}
    assert '<release version="0.7.12" date="2026-11-12"' in (root / "flatpak" / stamp_release.METAINFO.name).read_text()


def test_stamp_refuses_bad_input(tmp_path):
    root = tree(tmp_path)
    with pytest.raises(SystemExit):
        stamp_release.stamp("0.7.x", "abc", "2026-11-12", root=root)


def test_release_workflow_signs_and_publishes_only_the_app():
    wf = (ROOT / ".github/workflows/release.yml").read_text()
    assert "--gpg-sign" in wf and "FLATPAK_GPG_PRIVATE_KEY" in wf
    assert "build-export" in wf and "Debug" in wf  # refuses a repo with debug refs
    assert "summary.sig" in wf  # refuses an unsigned repo


def test_build_info_is_packaged():
    text = (ROOT / "pyproject.toml").read_text()
    assert "build_info.json" in text
