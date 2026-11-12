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


def make(fail=False, clock=None, runner=None):
    streams = []

    def open_stream(cb):
        if fail:
            raise OSError("no pulse device")
        streams.append(FakeStream(cb))
        return streams[-1]
    pulse = AudioPulse(open_stream=open_stream, detector_factory=FakeDetector,
                       clock=clock or (lambda: 0.0), runner=runner or (lambda job: job()))
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


def test_health_follows_the_callbacks():
    now = {"t": 0.0}
    pulse, streams = make(clock=lambda: now["t"])
    pulse.start()
    streams[0].active = True
    assert pulse.healthy()               # just started: give it a moment
    now["t"] = 2.0
    assert not pulse.healthy()           # nothing arrived for 2 s
    streams[0].callback(np.zeros((1024, 1), np.float32), 1024, None, None)
    assert pulse.healthy()
    streams[0].active = False            # PortAudio gave up on the stream
    assert not pulse.healthy()


def test_a_stream_that_fails_to_start_is_closed():
    closed = []

    class Broken(FakeStream):
        def start(self):
            raise OSError("device busy")

        def close(self):
            closed.append(1)
    pulse = AudioPulse(open_stream=lambda cb: Broken(cb), detector_factory=FakeDetector,
                       runner=lambda job: job())
    assert pulse.start() is False and closed == [1]


# --- opening the audio device takes up to a second: never on the caller's (UI) thread -----

def test_start_and_stop_return_at_once_and_the_device_opens_on_the_runner():
    jobs = []
    pulse, streams = make(runner=jobs.append)
    assert pulse.start() is True and pulse.running   # wanted; nothing opened yet
    assert streams == [] and pulse.healthy()         # still opening is not "stalled"
    jobs.pop(0)()
    assert streams[0].started
    pulse.stop()
    assert not pulse.running and not streams[0].closed   # closing waits for the runner too
    jobs.pop(0)()
    assert streams[0].closed


def test_stop_before_the_device_opened_leaves_nothing_open():
    jobs = []
    pulse, streams = make(runner=jobs.append)
    pulse.start()
    pulse.stop()
    for job in jobs:
        job()
    assert not pulse.running and all(s.closed for s in streams)


def test_default_runner_is_a_background_thread():
    import threading
    import time
    seen = []

    def open_stream(cb):
        seen.append(threading.current_thread())
        return FakeStream(cb)
    pulse = AudioPulse(open_stream=open_stream, detector_factory=FakeDetector)
    pulse.start()
    end = time.monotonic() + 2
    while not seen and time.monotonic() < end:
        time.sleep(0.01)
    assert seen and seen[0] is not threading.current_thread()
    pulse.stop()
