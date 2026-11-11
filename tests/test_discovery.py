from couchside.core.discovery import choose_server, MassServer, _dedupe, parse_mass_service

REAL_TXT = {
    b"server_id": b"9cc41ff7c04e48e6a502301970c5af11",
    b"server_version": b"2.10.9",
    b"schema_version": b"65",
    b"base_url": b"http://192.168.30.3:8095",
    b"name": b"Music Assistant (d5369777-music-assistant)",
    b"external_url": None,
}


def test_parse_uses_base_url_txt():
    s = parse_mass_service(REAL_TXT, ["10.0.0.9"], 8095)
    assert s == MassServer(
        server_id="9cc41ff7c04e48e6a502301970c5af11",
        name="Music Assistant (d5369777-music-assistant)",
        base_url="http://192.168.30.3:8095",
        version="2.10.9",
    )


def test_parse_falls_back_to_address():
    txt = {k: v for k, v in REAL_TXT.items() if k != b"base_url"}
    assert parse_mass_service(txt, ["10.0.0.9"], 8095).base_url == "http://10.0.0.9:8095"


def test_parse_brackets_ipv6_address():
    txt = {k: v for k, v in REAL_TXT.items() if k != b"base_url"}
    assert parse_mass_service(txt, ["fe80::1"], 8095).base_url == "http://[fe80::1]:8095"


def test_parse_returns_none_without_address_or_url():
    txt = {k: v for k, v in REAL_TXT.items() if k != b"base_url"}
    assert parse_mass_service(txt, [], 8095) is None


def test_discover_returns_all_servers():
    a = MassServer("a", "A", "http://a:8095", "2.10.9")
    b = MassServer("b", "B", "http://b:8095", "2.10.9")
    a2 = MassServer("a", "A again", "http://a2:8095", "2.10.9")
    assert _dedupe([a, b, a2]) == [a, b]


def _srv(sid, url):
    return MassServer(server_id=sid, name=sid, base_url=url, version="2.10.9")


def test_choose_server_prefers_the_one_used_before():
    servers = [_srv("a", "http://a:8095"), _srv("b", "http://b:8095")]
    assert choose_server(servers, "b").server_id == "b"


def test_choose_server_first_when_no_preference_or_gone():
    servers = [_srv("a", "http://a:8095"), _srv("b", "http://b:8095")]
    assert choose_server(servers, None).server_id == "a"
    assert choose_server(servers, "zzz").server_id == "a"
    assert choose_server([], "a") is None
