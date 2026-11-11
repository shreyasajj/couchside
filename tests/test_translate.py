from couchside.core.translate import DeepLTranslator, GoogleTranslator, LibreTranslator

LINES = ["ਹਾਏ, ਨੀ old school ਜਿਹੀ ਏ", "ਲਾਲ ਗੱਲਾਂ"]


class Http:
    def __init__(self, reply):
        self.reply, self.calls = reply, []

    async def get(self, url, params):
        self.calls.append(("GET", url, params, None))
        return self._r()

    async def post_json(self, url, body, headers=None):
        self.calls.append(("POST", url, body, headers))
        return self._r()

    def _r(self):
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


async def test_google_one_request_split_back_into_lines():
    http = Http((200, [[["Hey, it's not like old school\n", "x"], ["red things", "y"]], None, "pa"]))
    assert await GoogleTranslator(http).translate(LINES) == ["Hey, it's not like old school", "red things"]
    method, url, params, _ = http.calls[0]
    assert method == "GET" and url == "https://translate.googleapis.com/translate_a/single"
    assert params["q"] == "\n".join(LINES) and params["tl"] == "en" and params["sl"] == "auto"


async def test_google_line_count_mismatch_is_none():
    http = Http((200, [[["only one line", "x"]], None, "pa"]))
    assert await GoogleTranslator(http).translate(LINES) is None


async def test_blank_lines_keep_their_place():
    http = Http((200, [[["one\n", "a"], ["two", "b"]], None, "pa"]))
    assert await GoogleTranslator(http).translate(["a", "", "b"]) == ["one", "", "two"]


async def test_deepl_free_and_pro_hosts():
    http = Http((200, {"translations": [{"text": "Hey"}, {"text": "red things"}]}))
    assert await DeepLTranslator(http, "abc:fx").translate(LINES) == ["Hey", "red things"]
    method, url, body, headers = http.calls[0]
    assert url == "https://api-free.deepl.com/v2/translate"
    assert body == {"text": LINES, "target_lang": "EN-US"}
    assert headers == {"Authorization": "DeepL-Auth-Key abc:fx"}
    await DeepLTranslator(http, "pro-key").translate(LINES)
    assert http.calls[1][1] == "https://api.deepl.com/v2/translate"


async def test_deepl_without_key_is_none():
    http = Http((200, {}))
    assert await DeepLTranslator(http, "").translate(LINES) is None and http.calls == []


async def test_libretranslate_request():
    http = Http((200, {"translatedText": ["Hey", "red things"]}))
    t = LibreTranslator(http, "http://pi.local:5000/", api_key="k")
    assert await t.translate(LINES) == ["Hey", "red things"]
    _, url, body, _ = http.calls[0]
    assert url == "http://pi.local:5000/translate"
    assert body == {"q": LINES, "source": "auto", "target": "en", "format": "text", "api_key": "k"}


async def test_libretranslate_without_url_is_none():
    assert await LibreTranslator(Http((200, {})), "").translate(LINES) is None


async def test_errors_are_none():
    for t in (GoogleTranslator(Http(RuntimeError("x"))), DeepLTranslator(Http((403, None)), "k:fx"),
              LibreTranslator(Http((200, {"translatedText": "not a list"})), "http://x")):
        assert await t.translate(LINES) is None
