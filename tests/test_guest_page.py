import re
from pathlib import Path

PAGE = Path(__file__).parents[1] / "src/couchside/web/guest.html"


def test_page_is_self_contained():
    html = PAGE.read_text()
    # no external requests: no absolute URLs, scripts or styles from elsewhere
    assert not re.search(r"""(src|href)=["']https?://""", html)
    assert "<script src" not in html and "<link" not in html


def test_page_uses_relative_api_paths():
    html = PAGE.read_text()
    assert 'new URL("api/" + p, location.href)' in html
    assert "fetch(\"/" not in html and "fetch('/" not in html


def test_page_never_renders_server_text_as_html():
    html = PAGE.read_text()
    assert "innerHTML" not in html


def test_page_is_packaged():
    text = (Path(__file__).parents[1] / "pyproject.toml").read_text()
    assert "web/*.html" in text
