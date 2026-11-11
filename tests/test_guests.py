import pytest

from couchside.core.guests import GuestError, GuestRules, GuestSession

DEV = "device-abcdef12"


def session(**rules):
    return GuestSession(GuestRules(**rules))


def test_token_is_random_and_rotates():
    s = session()
    t1 = s.token
    assert len(t1) == 16 and t1.replace("-", "").replace("_", "").isalnum()
    s.new_token()
    assert s.token != t1


def test_rotating_token_forgets_guests_and_credits():
    s = session()
    g = s.join(DEV, "Sam")
    s.note_added(g, "item1", now=0)
    s.new_token()
    assert s.guests == {} and s.added_by("item1") is None


def test_join_validates_name_and_device():
    s = session()
    assert s.join(DEV, "  Sam  ").name == "Sam"
    for bad_name in ("", "   ", "x" * 25, "bad\nname"):
        with pytest.raises(GuestError):
            s.join(DEV, bad_name)
    for bad_dev in ("short", "x" * 65, "has space here!", ""):
        with pytest.raises(GuestError):
            s.join(bad_dev, "Sam")


def test_rejoin_keeps_quota_and_updates_name():
    s = session()
    g = s.join(DEV, "Sam")
    s.use_skip(g)
    g2 = s.join(DEV, "Samuel")
    assert g2 is g and g2.name == "Samuel" and g2.skips_used == 1


def test_unknown_guest():
    with pytest.raises(GuestError):
        session().guest("nobody-123456")


def test_max_waiting_songs():
    s = session(max_waiting=2)
    g = s.join(DEV, "Sam")
    s.note_added(g, "a", now=0)
    s.note_added(g, "b", now=0)
    s.check_add(g, upcoming_ids=["a"], now=10)           # 'b' already played: one waiting
    with pytest.raises(GuestError, match="2 songs waiting"):
        s.check_add(g, upcoming_ids=["a", "b"], now=10)


def test_cooldown_between_adds():
    s = session(cooldown=30)
    g = s.join(DEV, "Sam")
    s.note_added(g, "a", now=100)
    with pytest.raises(GuestError, match="20 s"):
        s.check_add(g, upcoming_ids=[], now=110)
    s.check_add(g, upcoming_ids=[], now=130)


def test_skips_run_out():
    s = session(skips=1)
    g = s.join(DEV, "Sam")
    s.use_skip(g)
    with pytest.raises(GuestError, match="No skips left"):
        s.use_skip(g)


def test_boost_only_own_waiting_songs():
    s = session(boosts=1)
    g = s.join(DEV, "Sam")
    other = s.join("device-other999", "Ana")
    s.note_added(g, "mine", now=0)
    s.note_added(other, "theirs", now=0)
    with pytest.raises(GuestError, match="your own"):
        s.use_boost(g, "theirs", upcoming_ids=["mine", "theirs"])
    with pytest.raises(GuestError, match="already playing|not waiting"):
        s.use_boost(g, "mine", upcoming_ids=["theirs"])
    s.use_boost(g, "mine", upcoming_ids=["theirs", "mine"])
    with pytest.raises(GuestError, match="No boosts left"):
        s.use_boost(g, "mine", upcoming_ids=["mine"])


def test_credits_and_remaining():
    s = session(skips=3, boosts=2, max_waiting=3)
    g = s.join(DEV, "Sam")
    s.note_added(g, "a", now=0)
    s.use_skip(g)
    assert s.added_by("a") == "Sam" and s.added_by("zzz") is None
    assert s.remaining(g, upcoming_ids=["a"]) == {"skips": 2, "boosts": 2, "waiting": 1, "maxWaiting": 3}
