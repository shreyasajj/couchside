import asyncio

from dbus_next import Message, MessageType, Variant

from couchside.core import flatpak_portal as fp

MON = "/org/freedesktop/portal/Flatpak/update_monitor/1_42/couchside1"


class FakeBus:
    def __init__(self):
        self.calls, self.handlers = [], []
        self.disconnected = False

    async def call(self, msg):
        self.calls.append(msg)
        if msg.member == "CreateUpdateMonitor":
            return Message(message_type=MessageType.METHOD_RETURN, reply_serial=1, signature="o", body=[MON])
        if msg.member == "Spawn":
            return Message(message_type=MessageType.METHOD_RETURN, reply_serial=1, signature="u", body=[4242])
        return Message(message_type=MessageType.METHOD_RETURN, reply_serial=1)

    def add_message_handler(self, h):
        self.handlers.append(h)

    def disconnect(self):
        self.disconnected = True

    def emit(self, member, info, path=MON):
        sig = Message.new_signal(path, fp.MONITOR_IFACE, member, "a{sv}", [info])
        for h in self.handlers:
            h(sig)


async def started():
    bus = FakeBus()
    events = []
    up = fp.PortalUpdater(bus_factory=lambda: _ret(bus))
    ok = await up.start(on_available=lambda info: events.append(("available", info)),
                        on_progress=lambda p: events.append(("progress", p)))
    return up, bus, events, ok


async def _ret(x):
    return x


async def test_start_creates_a_monitor_and_listens_to_it():
    up, bus, events, ok = await started()
    assert ok
    create = next(m for m in bus.calls if m.member == "CreateUpdateMonitor")
    assert (create.destination, create.path, create.interface) == (fp.PORTAL, fp.PATH, fp.PORTAL_IFACE)
    rules = [m.body[0] for m in bus.calls if m.member == "AddMatch"]
    assert any(MON in r and fp.MONITOR_IFACE in r for r in rules)


async def test_signals_become_callbacks():
    up, bus, events, _ = await started()
    bus.emit("UpdateAvailable", {"remote-commit": Variant("s", "abc"), "running-commit": Variant("s", "old")})
    bus.emit("Progress", {"n_ops": Variant("u", 2), "op": Variant("u", 1), "progress": Variant("u", 40),
                          "status": Variant("u", 0)})
    bus.emit("Progress", {"status": Variant("u", 3), "error_message": Variant("s", "no space")})
    bus.emit("Progress", {"status": Variant("u", 2)}, path="/some/other/monitor")  # not ours
    assert events == [
        ("available", {"remote-commit": "abc", "running-commit": "old"}),
        ("progress", fp.Progress("running", 70, "")),
        ("progress", fp.Progress("failed", 0, "no space")),
    ]


async def test_update_calls_the_monitor():
    up, bus, _, _ = await started()
    await up.update()
    m = bus.calls[-1]
    assert (m.path, m.interface, m.member, m.signature) == (MON, fp.MONITOR_IFACE, "Update", "sa{sv}")


async def test_spawn_latest_version():
    up, bus, _, _ = await started()
    pid = await up.spawn_latest(["couchside-sendspin"], {"QT_QPA_PLATFORM": "wayland"})
    m = bus.calls[-1]
    assert pid == 4242 and m.member == "Spawn" and m.signature == "ayaaya{uh}a{ss}ua{sv}"
    cwd, argv, fds, env, flags, opts = m.body
    assert argv == [b"couchside-sendspin\0"] and cwd.endswith(b"\0")
    assert flags & fp.SPAWN_LATEST_VERSION and env == {"QT_QPA_PLATFORM": "wayland"}


async def test_no_portal_means_no_updates():
    async def no_bus():
        raise OSError("no session bus")
    up = fp.PortalUpdater(bus_factory=no_bus)
    assert await up.start(lambda i: None, lambda p: None) is False
    assert await up.update() is False


async def test_portal_error_reply_is_handled():
    bus = FakeBus()

    async def err(msg):
        bus.calls.append(msg)
        return Message.new_error(msg, "org.freedesktop.DBus.Error.ServiceUnknown", "nope") \
            if msg.member == "CreateUpdateMonitor" else Message(message_type=MessageType.METHOD_RETURN, reply_serial=1)
    bus.call = err
    up = fp.PortalUpdater(bus_factory=lambda: _ret(bus))
    assert await up.start(lambda i: None, lambda p: None) is False
