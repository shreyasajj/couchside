"""Small display helpers for the Now Playing screen (Qt-free)."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

DEFAULT_BACKGROUND = "#0d0b1a"
PROXY_SIZES = (256, 512, 1024)  # the only sizes MA 2.10's image proxy accepts


def format_time(seconds: float | None) -> str:
    """`m:ss`, or `h:mm:ss` from an hour; 0:00 for unknown or negative."""
    total = int(seconds) if seconds and seconds > 0 else 0
    h, rest = divmod(total, 3600)
    m, s = divmod(rest, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def art_url(url: str | None, size: int) -> str:
    """Ask MA's image proxy for at least `size` pixels (rounded up to a size it
    accepts, capped at the largest); other image URLs are left alone."""
    if not url:
        return ""
    parts = urlsplit(url)
    if "/imageproxy/" not in parts.path:
        return url
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != "size"]
    snapped = next((s for s in PROXY_SIZES if s >= size), PROXY_SIZES[-1])
    query.insert(0, ("size", str(snapped)))
    return urlunsplit(parts._replace(query=urlencode(query)))


def palette_colour(rgb: tuple[int, int, int] | None, fallback: str = DEFAULT_BACKGROUND) -> str:
    """`#rrggbb` from an RGB triple, or `fallback` when missing or out of range."""
    if not rgb or len(rgb) != 3 or not all(isinstance(c, int) and 0 <= c <= 255 for c in rgb):
        return fallback
    return "#{:02x}{:02x}{:02x}".format(*rgb)
