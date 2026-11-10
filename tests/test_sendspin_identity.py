import json

from aiosendspin.noise import Identity, b64url_encode

from couchside.sendspin.identity import read_client_id


def test_client_id_matches_identity(tmp_path):
    ident = Identity.generate()
    (tmp_path / "identity-daemon.json").write_text(
        json.dumps({"private_key": b64url_encode(ident.private_bytes)})
    )
    assert read_client_id(tmp_path) == ident.peer_id


def test_missing_identity_returns_none(tmp_path):
    assert read_client_id(tmp_path) is None


def test_corrupt_identity_returns_none(tmp_path):
    p = tmp_path / "identity-daemon.json"
    p.write_text("xx")
    assert read_client_id(tmp_path) is None
    assert p.read_text() == "xx"


def test_bad_key_returns_none(tmp_path):
    p = tmp_path / "identity-daemon.json"
    p.write_text(json.dumps({"private_key": "!!notbase64"}))
    assert read_client_id(tmp_path) is None
