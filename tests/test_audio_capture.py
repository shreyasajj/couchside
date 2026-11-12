import numpy as np

from couchside.core.audio_capture import AudioPulse


class FakeStream:
    def __init__(self, callback):
        self.callback, self.started, self.closed = callback, False, False

    def start(self):
        self.started = True

    def stop(self):
        self.started = False

    def close(self):
        self.closed = True


class FakeDetector:
    def __init__(self, *a):
        self.n = 0

    def feed(self, block):
        self.n += 1
        return 0.5, self.n % 2 == 0


def make(fail=False, clock=None):
    streams = []

    def open_stream(cb):
        if fail:
            raise OSError("no pulse device")
        streams.append(FakeStream(cb))
        return streams[-1]
    pulse = AudioPulse(open_stream=open_stream, detector_factory=FakeDetector,
                       clock=clock or (lambda: 0.0))
    return pulse, streams


def test_blocks_become_level_and_beats():
    pulse, streams = make()
    assert pulse.start() and streams[0].started
    for _ in range(4):
        streams[0].callback(np.zeros((1024, 1), np.float32), 1024, None, None)
    assert pulse.level == 0.5 and pulse.beats == 2


def test_start_twice_opens_one_stream_and_stop_closes_it():
    pulse, streams = make()
    pulse.start()
    pulse.start()
    assert len(streams) == 1
    pulse.stop()
    assert streams[0].closed and pulse.level == 0.0 and not pulse.running
    pulse.stop()  # twice is fine


def test_no_audio_device_is_not_fatal_and_retried_later():
    now = {"t": 0.0}
    pulse, _ = make(fail=True, clock=lambda: now["t"])
    assert pulse.start() is False and not pulse.running
    calls = []
    pulse._open = lambda cb: calls.append(1) or (_ for _ in ()).throw(OSError("still none"))
    assert pulse.start() is False and calls == []  # not hammered
    now["t"] = 31.0
    pulse.start()
    assert calls == [1]


def test_a_crashing_detector_does_not_kill_the_audio_thread():
    pulse, streams = make()
    pulse.start()

    def boom(block):
        raise ValueError("bad block")
    pulse._detector.feed = boom
    streams[0].callback(np.zeros((1024, 1), np.float32), 1024, None, None)  # no exception
