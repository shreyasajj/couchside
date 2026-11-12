import importlib.util
import urllib.error
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("gen_python_deps", ROOT / "flatpak/gen-python-deps.py")
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)


def test_pypi_lookups_retry_network_blips():
    calls, slept = [], []

    def flaky(url):
        calls.append(url)
        if len(calls) < 3:
            raise urllib.error.URLError("SSL: UNEXPECTED_EOF_WHILE_READING")
        return {"ok": True}
    assert gen.fetch_json("https://pypi.org/x", get=flaky, sleep=slept.append) == {"ok": True}
    assert len(calls) == 3 and slept == [2, 4]


def test_pypi_lookups_give_up_eventually():
    def down(url):
        raise urllib.error.URLError("down")
    with pytest.raises(urllib.error.URLError):
        gen.fetch_json("https://pypi.org/x", get=down, sleep=lambda s: None, attempts=4)
