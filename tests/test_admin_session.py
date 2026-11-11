import pytest

from couchside.core.guests import CODE_TRIES, CODE_TTL, GuestError, GuestRules, GuestSession

A, B = "device-aaaaaaaa", "device-bbbbbbbb"


def setup():
    s = GuestSession(GuestRules(skips=1, boosts=0, max_waiting=1, cooldown=60))
    return s, s.join(A, "Ana"), s.join(B, "Ben")


def test_public_ids_are_random_and_not_device_ids():
    s, a, b = setup()
    assert a.public_id and b.public_id and a.public_id != b.public_id
    assert A not in a.public_id
    assert s.by_public_id(a.public_id) is a
    with pytest.raises(GuestError):
        s.by_public_id("nope")


def test_code_is_six_digits_and_one_use():
    s, a, b = setup()
    code = s.new_admin_code(now=0)
    assert len(code) == 6 and code.isdigit() and s.admin_code == code
    s.redeem_code(a, code, now=1)
    assert a.admin and s.admin_code is None
    with pytest.raises(GuestError):
        s.redeem_code(b, code, now=2)
    assert not b.admin


def test_code_expires():
    s, a, _ = setup()
    code = s.new_admin_code(now=0)
    with pytest.raises(GuestError):
        s.redeem_code(a, code, now=CODE_TTL + 1)
    assert not a.admin and s.admin_code is None


def test_no_code_means_no_admin():
    s, a, _ = setup()
    for c in ("", "000000", None, 123456):
        with pytest.raises(GuestError):
            s.redeem_code(a, c, now=0)
    assert not a.admin


def test_wrong_tries_cancel_the_code():
    s, a, b = setup()
    code = s.new_admin_code(now=0)
    wrong = "000000" if code != "000000" else "111111"
    for i in range(CODE_TRIES):
        with pytest.raises(GuestError):
            s.redeem_code(a if i % 2 else b, wrong, now=1)
    assert s.admin_code is None and s.code_cancelled
    with pytest.raises(GuestError):
        s.redeem_code(a, code, now=2)  # the right code no longer works


def test_cancel_code():
    s, a, _ = setup()
    code = s.new_admin_code(now=0)
    s.cancel_admin_code()
    with pytest.raises(GuestError):
        s.redeem_code(a, code, now=1)


def test_promote_and_revoke():
    s, a, _ = setup()
    s.promote(a.public_id)
    assert a.admin
    s.revoke(a.public_id)
    assert not a.admin


def test_admin_survives_rejoin_and_ends_with_the_session():
    s, a, _ = setup()
    s.promote(a.public_id)
    assert s.join(A, "Ana 2").admin
    s.new_token()
    assert s.join(A, "Ana").admin is False


def test_admins_have_no_limits():
    s, a, _ = setup()
    s.promote(a.public_id)
    s.note_added(a, "i1", now=0)
    s.check_add(a, ["i1", "i2"], now=1)  # waiting and cooldown don't apply
    for _ in range(5):
        s.use_skip(a)
    s.use_boost(a, "i1", ["i1"])  # boosts 0 for guests
    assert a.skips_used == 0 and a.boosts_used == 0


def test_reset_gives_limits_back():
    s, _, b = setup()
    s.use_skip(b)
    s.note_added(b, "i1", now=0)
    s.reset(b.public_id)
    assert b.skips_used == 0 and b.boosts_used == 0 and b.last_add is None


def test_remove_bans_the_device_and_keeps_credit():
    s, _, b = setup()
    s.note_added(b, "i1", now=0)
    s.remove(b.public_id)
    assert B not in s.guests
    assert s.added_by("i1") == "Ben"
    with pytest.raises(GuestError):
        s.join(B, "Someone else")
    with pytest.raises(GuestError):
        s.guest(B)
    s.new_token()
    assert s.join(B, "Ben").name == "Ben"  # a new party starts fresh
