"""Beat detection light enough for a Raspberry Pi: one FFT per block of audio.

Per block (1024 samples at 22050 Hz, about 21 a second): the energy of the low band
(40-180 Hz, where kicks and bass live), log-compressed. A beat is a jump in that energy
(onset flux) well above the recent average, at least `min_gap` after the previous one.
The level (0..1) is the low band against a slowly decaying peak, so quiet and loud
music both fill the range; true silence stays at 0. Qt-free.
"""

from __future__ import annotations

from collections import deque

import numpy as np

SILENCE = 1e-5          # low-band RMS below this is silence
LOW_HZ, HIGH_HZ = 40.0, 180.0


class BeatDetector:
    def __init__(self, sample_rate: int = 22050, block: int = 1024, min_gap: float = 0.28,
                 history: float = 1.5, sensitivity: float = 1.4):
        self._sr = sample_rate
        self._block = block
        self._window = np.hanning(block).astype(np.float32)
        freqs = np.fft.rfftfreq(block, 1.0 / sample_rate)
        self._band = (freqs >= LOW_HZ) & (freqs <= HIGH_HZ)
        self._dt = block / sample_rate
        self._min_gap = min_gap
        self._sensitivity = sensitivity
        self._flux = deque(maxlen=max(4, int(history / self._dt)))
        self._prev = None
        self._since_beat = 1e9
        self._peak = 0.0
        self._level = 0.0

    def feed(self, samples) -> tuple[float, bool]:
        """One block of audio (mono, or the first channel is used) -> (level, beat)."""
        x = np.asarray(samples, dtype=np.float32)
        if x.ndim > 1:
            x = x[:, 0]
        if len(x) < self._block:
            x = np.pad(x, (0, self._block - len(x)))
        elif len(x) > self._block:
            x = x[-self._block:]
        spectrum = np.abs(np.fft.rfft(x * self._window))
        rms = float(np.sqrt(np.mean(spectrum[self._band] ** 2)) / self._block)
        self._since_beat += self._dt

        # log: loudness changes count the same at any volume; the floor keeps a kick after
        # a quiet gap a jump (rather than forgetting what came before)
        energy = float(np.log(max(rms, SILENCE)))
        flux = max(0.0, energy - self._prev) if self._prev is not None else 0.0
        self._prev = energy

        if rms < SILENCE:
            self._flux.append(flux)
            self._level *= 0.6
            if self._level < 0.01:
                self._level = 0.0
            return self._level, False

        beat = False
        if len(self._flux) >= 4:
            mean = float(np.mean(self._flux))
            std = float(np.std(self._flux))
            if (flux > mean + self._sensitivity * std and flux > 0.35
                    and self._since_beat >= self._min_gap):
                beat = True
                self._since_beat = 0.0
        self._flux.append(flux)

        # level: against a peak that falls slowly (about a tenth per two seconds)
        self._peak = max(rms, self._peak * 0.995)
        target = min(1.0, rms / self._peak) if self._peak > 0 else 0.0
        # quick to rise, slower to fall: a pulse rather than a flicker
        self._level += (target - self._level) * (0.7 if target > self._level else 0.25)
        return max(0.0, min(1.0, self._level)), beat
