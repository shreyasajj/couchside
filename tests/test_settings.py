import json
import stat
from pathlib import Path

from couchside.core.paths import config_dir, sendspin_settings_dir, state_dir
from couchside.core.settings import (
    AppSettings,
    load_settings,
    load_token,
    save_settings,
    save_token,
)


def test_defaults_when_missing(tmp_path):
    s = load_settings(tmp_path / "settings.json")
    assert s.server_url is None
    assert s.player_name == "Living Room TV"
    assert s.qr_caption == "Scan to add songs"
    assert s.guest_public_url is None
    assert s.autostart_requested is False


def test_roundtrip(tmp_path):
    p = tmp_path / "settings.json"
    s = AppSettings(server_url="http://h:8095", player_name="Den", qr_caption="Hi",
                    guest_public_url="https://party.example.com", autostart_requested=True)
    save_settings(s, p)
    assert load_settings(p) == s


def test_unknown_keys_ignored(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"server_url": "http://x:8095", "bogus": 1}))
    assert load_settings(p).server_url == "http://x:8095"


def test_corrupt_settings_uses_defaults(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text("{not json")
    assert load_settings(p) == AppSettings()


def test_wrong_types_use_defaults(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"player_name": 5, "server_url": "http://x:8095"}))
    s = load_settings(p)
    assert s.player_name == "Living Room TV"
    assert s.server_url == "http://x:8095"


def test_save_creates_parent_dir(tmp_path):
    p = tmp_path / "a" / "b" / "settings.json"
    save_settings(AppSettings(), p)
    assert p.exists()


def test_token_file_is_0600(tmp_path):
    p = tmp_path / "token"
    save_token("secret", p)
    assert stat.S_IMODE(p.stat().st_mode) == 0o600


def test_token_stripped(tmp_path):
    p = tmp_path / "token"
    save_token("  abc\n", p)
    assert load_token(p) == "abc"


def test_missing_or_empty_token_is_none(tmp_path):
    p = tmp_path / "token"
    assert load_token(p) is None
    p.write_text("  \n")
    assert load_token(p) is None


def test_xdg_paths(monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", "/tmp/x")
    monkeypatch.setenv("XDG_STATE_HOME", "/tmp/s")
    assert config_dir() == Path("/tmp/x/couchside")
    assert sendspin_settings_dir() == Path("/tmp/x/sendspin")
    assert state_dir() == Path("/tmp/s/couchside")


def test_xdg_fallbacks(monkeypatch, tmp_path):
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert config_dir() == tmp_path / ".config" / "couchside"
    assert state_dir() == tmp_path / ".local" / "state" / "couchside"


from couchside.core.settings import normalize_server_url  # noqa: E402


def test_normalize_server_url():
    assert normalize_server_url("") is None
    assert normalize_server_url("  ") is None
    assert normalize_server_url("192.168.30.3") == "http://192.168.30.3:8095"
    assert normalize_server_url("http://mass.local/") == "http://mass.local:8095"
    assert normalize_server_url("http://h:9000") == "http://h:9000"
    assert normalize_server_url("https://ma.example.com") == "https://ma.example.com"
