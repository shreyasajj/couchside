"""What this TV is playing, as a level and beats: records the default PipeWire output's
monitor (through the PulseAudio socket the Flatpak already has) and runs the beat detector
in the audio callback. Only the latest level and a beat counter are kept; the UI polls
them. The stream is open only while something on screen uses it. Qt-free.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Callable

from couchside.core.beat import BeatDetector

log = logging.getLogger(__name__)

SAMPLE_RATE = 22050
BLOCK = 1024
RETRY_AFTER = 30.0  # seconds before trying a missing audio device again


def open_monitor_stream(callback) -> Any:
    """A PortAudio input on the `pulse` device, pointed at the default sink's monitor."""
    os.environ["PULSE_SOURCE"] = "@DEFAULT_MONITOR@"  # read when the stream opens
    import sounddevice as sd

    names = [d["name"] for d in sd.query_devices()]
    if "pulse" not in names:
        raise OSError("no PulseAudio/PipeWire device")
    return sd.InputStream(device=names.index("pulse"), channels=1, samplerate=SAMPLE_RATE,
                          blocksize=BLOCK, dtype="float32", callback=callback)


class AudioPulse:
    def __init__(self, open_stream: Callable[[Callable], Any] = open_monitor_stream,
                 detector_factory: Callable[..., Any] = BeatDetector,
                 clock: Callable[[], float] = time.monotonic):
        self._open = open_stream
        self._make_detector = detector_factory
        self._clock = clock
        self._stream = None
        self._detector = None
        self._failed_at: float | None = None
        self.level = 0.0   # 0..1, written by the audio thread
        self.beats = 0     # counts up on every beat

    @property
    def running(self) -> bool:
        return self._stream is not None

    def _callback(self, indata, frames, time_info, status) -> None:
        try:
            level, beat = self._detector.feed(indata)
        except Exception:  # never let an exception reach PortAudio's thread
            return
        self.level = level
        if beat:
            self.beats += 1

    def start(self) -> bool:
        if self._stream is not None:
            return True
        if self._failed_at is not None and self._clock() - self._failed_at < RETRY_AFTER:
            return False
        try:
            self._detector = self._make_detector(SAMPLE_RATE, BLOCK)
            stream = self._open(self._callback)
            stream.start()
        except Exception as e:
            log.info("visualizer has no audio to listen to: %s", e)
            self._failed_at = self._clock()
            return False
        self._stream, self._failed_at = stream, None
        return True

    def stop(self) -> None:
        stream, self._stream = self._stream, None
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception as e:
                log.debug("closing the audio stream: %s", e)
        self.level = 0.0
