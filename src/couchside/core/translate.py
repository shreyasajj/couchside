"""Line-by-line English translation of lyrics through a choosable service (Qt-free).

Each translator makes one request per song and returns one translation per input line
(blank lines stay blank), or None if anything goes wrong or the line count doesn't match:
a missing translation never breaks the lyrics themselves.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

log = logging.getLogger(__name__)

GOOGLE_URL = "https://translate.googleapis.com/translate_a/single"
DEEPL_FREE = "https://api-free.deepl.com/v2/translate"
DEEPL_PRO = "https://api.deepl.com/v2/translate"


class Http(Protocol):
    async def get(self, url: str, params: dict) -> tuple[int, Any]: ...
    async def post_json(self, url: str, body: dict, headers: dict | None = None) -> tuple[int, Any]: ...


class Translator:
    name = "base"

    def __init__(self, http: Http):
        self._http = http

    async def translate(self, lines: list[str]) -> list[str] | None:
        """Translations aligned with `lines`; None on any failure."""
        texts = [line for line in lines if line.strip()]
        if not texts:
            return [""] * len(lines)
        try:
            out = await self._translate(texts)
        except Exception as e:
            log.info("%s translation failed: %s", self.name, e or type(e).__name__)
            return None
        if out is None or len(out) != len(texts):
            if out is not None:
                log.info("%s returned %d lines for %d", self.name, len(out), len(texts))
            return None
        it = iter(t.strip() for t in out)
        return [next(it) if line.strip() else "" for line in lines]

    async def _translate(self, texts: list[str]) -> list[str] | None:
        raise NotImplementedError


class GoogleTranslator(Translator):
    """No setup; Google's unofficial endpoint (can be rate-limited or change)."""

    name = "google"

    async def _translate(self, texts):
        status, data = await self._http.get(GOOGLE_URL, {
            "client": "gtx", "sl": "auto", "tl": "en", "dt": "t", "q": "\n".join(texts)})
        if status != 200 or not isinstance(data, list) or not data or not isinstance(data[0], list):
            return None
        joined = "".join(seg[0] for seg in data[0] if isinstance(seg, list) and seg and isinstance(seg[0], str))
        return joined.rstrip("\n").split("\n")


class DeepLTranslator(Translator):
    """Free API keys end in ':fx' and use the api-free host."""

    name = "deepl"

    def __init__(self, http: Http, key: str):
        super().__init__(http)
        self._key = (key or "").strip()

    async def _translate(self, texts):
        if not self._key:
            return None
        url = DEEPL_FREE if self._key.endswith(":fx") else DEEPL_PRO
        status, data = await self._http.post_json(
            url, {"text": texts, "target_lang": "EN-US"},
            headers={"Authorization": f"DeepL-Auth-Key {self._key}"})
        if status != 200 or not isinstance(data, dict):
            return None
        return [t.get("text", "") for t in data.get("translations", []) if isinstance(t, dict)]


class LibreTranslator(Translator):
    """Self-hosted LibreTranslate at `url` (optional API key)."""

    name = "libretranslate"

    def __init__(self, http: Http, url: str, api_key: str | None = None):
        super().__init__(http)
        self._url = (url or "").strip().rstrip("/")
        self._key = api_key

    async def _translate(self, texts):
        if not self._url:
            return None
        body = {"q": texts, "source": "auto", "target": "en", "format": "text"}
        if self._key:
            body["api_key"] = self._key
        status, data = await self._http.post_json(f"{self._url}/translate", body)
        if status != 200 or not isinstance(data, dict) or not isinstance(data.get("translatedText"), list):
            return None
        return data["translatedText"]
