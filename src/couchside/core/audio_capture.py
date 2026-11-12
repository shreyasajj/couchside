"""What this TV is playing, as a level and beats: records the default PipeWire output's
monitor (through the PulseAudio socket the Flatpak already has) and runs the beat detector
in the audio callback. Only the latest level and a beat counter are kept; the UI polls
them. The stream is open only while something on screen uses it. Qt-free.

Opening and closing the device takes up to a second (PortAudio lists every device), so
both happen on a background thread: start() and stop() return at once and never hold up
the screen.
"""

from __future__ import annotations

import logging
import os
import queue
import threading
import time
from typing import Any, Callable

from couchside.core.beat import BeatDetector

log = logging.getLogger(__name__)

SAMPLE_RATE = 22050
BLOCK = 1024
RETRY_AFTER = 30.0  # seconds before trying a missing audio device again
STALL_AFTER = 1.5   # seconds without audio blocks: the stream died (PipeWire restart, …)


def open_monitor_stream(callback) -> Any:
    """A PortAudio input on the `pulse` device, pointed at the default sink's monitor."""
    os.environ["PULSE_SOURCE"] = "@DEFAULT_MONITOR@"  # read when the stream opens
    import sounddevice as sd

    names = [d["name"] for d in sd.query_devices()]
    if "pulse" not in names:
        raise OSError("no PulseAudio/PipeWire device")
    return sd.InputStream(device=names.index("pulse"), channels=1, samplerate=SAMPLE_RATE,
                          blocksize=BLOCK, dtype="float32", callback=callback)


class _Worker:
    """One background thread that runs jobs in order (started on first use)."""

    def __init__(self) -> None:
        self._jobs: queue.Queue = queue.Queue()
        self._thread: threading.Thread | None = None

    def __call__(self, job: Callable[[], None]) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="audio-pulse", daemon=True)
            self._thread.start()
        self._jobs.put(job)

    def _run(self) -> None:
        while True:
            job = self._jobs.get()
            try:
                job()
            except Exception:
                log.exception("audio job failed")


class AudioPulse:
    def __init__(self, open_stream: Callable[[Callable], Any] = open_monitor_stream,
                 detector_factory: Callable[..., Any] = BeatDetector,
                 clock: Callable[[], float] = time.monotonic,
                 runner: Callable[[Callable[[], None]], None] | None = None):
        self._open = open_stream
        self._make_detector = detector_factory
        self._clock = clock
        self._run = runner or _Worker()   # runs the slow open/close jobs, in order
        self._lock = threading.Lock()
        self._wanted = False
        self._stream = None
        self._detector = None
        self._failed_at: float | None = None
        self._last_block = 0.0
        self.level = 0.0   # 0..1, written by the audio thread
        self.beats = 0     # counts up on every beat

    @property
    def running(self) -> bool:
        """Listening, or about to (the device is still opening)."""
        return self._wanted

    def _callback(self, indata, frames, time_info, status) -> None:
        self._last_block = self._clock()
        try:
            level, beat = self._detector.feed(indata)
        except Exception:  # never let an exception reach PortAudio's thread
            return
        self.level = level
        if beat:
            self.beats += 1

    def start(self) -> bool:
        """Start listening; False when there is no audio to listen to (tried again later)."""
        if self._wanted:
            return True
        if self._failed_at is not None and self._clock() - self._failed_at < RETRY_AFTER:
            return False
        self._wanted = True
        self._run(self._open_job)
        return self._wanted

    def _open_job(self) -> None:
        with self._lock:
            if not self._wanted or self._stream is not None:
                return
        stream = None
        try:
            self._detector = self._make_detector(SAMPLE_RATE, BLOCK)
            stream = self._open(self._callback)
            self._last_block = self._clock()
            stream.start()
        except Exception as e:
            log.info("visualizer has no audio to listen to: %s", e)
            self._close(stream)
            self._failed_at = self._clock()
            self._wanted = False
            return
        with self._lock:
            if self._wanted:
                self._stream, self._failed_at = stream, None
                return
        self._close(stream)  # stopped while it was opening

    @staticmethod
    def _close(stream) -> None:
        if stream is None:
            return
        try:
            stream.stop()
        except Exception as e:
            log.debug("stopping the audio stream: %s", e)
        finally:
            try:
                stream.close()
            except Exception as e:
                log.debug("closing the audio stream: %s", e)

    def healthy(self) -> bool:
        """False when the open stream stopped delivering audio (PortAudio gave up, or no
        blocks for a while): the caller stops it and starts again."""
        stream = self._stream
        if stream is None:
            return True
        if getattr(stream, "active", True) is False:
            return False
        return self._clock() - self._last_block < STALL_AFTER

    def stop(self) -> None:
        with self._lock:
            self._wanted = False
            stream, self._stream = self._stream, None
        if stream is not None:
            self._run(lambda: self._close(stream))
        self.level = 0.0
