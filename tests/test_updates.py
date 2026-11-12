import json

from couchside.core import updates


async def test_latest_sendspin_from_pypi():
    seen = []

    async def http(url, params):
        seen.append(url)
        return 200, {"info": {"version": "9.2.0"}}
    assert await updates.latest_sendspin_version(http) == "9.2.0"
    assert seen == ["https://pypi.org/pypi/sendspin/json"]


async def test_latest_sendspin_failures_are_none():
    async def bad_status(url, params):
        return 503, None

    async def junk(url, params):
        return 200, {"info": {"version": "<script>"}}

    async def boom(url, params):
        raise OSError("offline")
    for http in (bad_status, junk, boom):
        assert await updates.latest_sendspin_version(http) is None


def test_is_newer():
    assert updates.is_newer("9.2.0", "9.1.0")
    assert updates.is_newer("10.0.0", "9.9.9")
    assert not updates.is_newer("9.1.0", "9.1.0")
    assert not updates.is_newer("9.1.0", "9.2.0")
    assert not updates.is_newer(None, "9.1.0") and not updates.is_newer("9.1.0", None)
    assert updates.is_newer("9.2.0rc1", "9.1.0")


def test_bundled_sendspin_version():
    v = updates.bundled_sendspin_version()
    assert v is None or v[0].isdigit()


def test_build_info(tmp_path, monkeypatch):
    monkeypatch.setattr(updates, "BUILD_INFO", tmp_path / "build_info.json")
    assert updates.build_info() == {"version": "dev", "commit": "", "feed": ""}
    (tmp_path / "build_info.json").write_text(json.dumps({"version": "0.7.12", "commit": "abc1234",
                                                          "feed": "https://x.example/latest.json"}))
    assert updates.build_info() == {"version": "0.7.12", "commit": "abc1234", "feed": "https://x.example/latest.json"}
    (tmp_path / "build_info.json").write_text("not json")
    assert updates.build_info()["version"] == "dev"


async def test_latest_app_version_from_the_release_feed():
    seen = []

    async def http(url, params):
        seen.append(url)
        return 200, {"version": "0.7.13"}
    assert await updates.latest_app_version(http, "https://x.example/latest.json") == "0.7.13"
    assert seen == ["https://x.example/latest.json"]


async def test_latest_app_version_failures_are_none():
    async def junk(url, params):
        return 200, {"version": "7; rm -rf"}

    async def boom(url, params):
        raise OSError("offline")
    assert await updates.latest_app_version(junk, "https://x/latest.json") is None
    assert await updates.latest_app_version(boom, "https://x/latest.json") is None
    assert await updates.latest_app_version(junk, "") is None  # dev build: no feed
