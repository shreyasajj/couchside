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
BARS = 64
BARS_LOW_HZ, BARS_HIGH_HZ = 40.0, 10000.0
BARS_MAX = 1.15         # a bar may overshoot a little on a peak, like the level never does


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
        # spectrum bars: 64 bands, evenly spaced in pitch. Low bands are narrower than one
        # FFT bin, so each bar reads the spectrum at its centre (interpolated) as well as
        # the loudest bin inside it.
        top = min(BARS_HIGH_HZ, sample_rate / 2)
        edges = np.geomspace(BARS_LOW_HZ, top, BARS + 1)
        self._freqs = freqs
        self._centres = np.sqrt(edges[:-1] * edges[1:])
        self._starts = np.minimum(np.searchsorted(freqs, edges[:-1]), len(freqs) - 1)
        self._end = int(min(np.searchsorted(freqs, top) + 1, len(freqs)))
        self._bar_peak = 0.0
        self.bars = np.zeros(BARS, dtype=np.float32)   # 0..BARS_MAX, replaced on every feed

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
        self._update_bars(spectrum)
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

    def _update_bars(self, spectrum) -> None:
        mags = np.maximum(np.interp(self._centres, self._freqs, spectrum),
                          np.maximum.reduceat(spectrum[:self._end], self._starts)) / self._block
        loudest = float(mags.max())
        if loudest < SILENCE:
            bars = self.bars * 0.6
            bars[bars < 0.01] = 0.0
            self.bars = bars.astype(np.float32)
            return
        # against a slowly falling peak, like the level: quiet and loud music both fill
        # the bars. The square root lifts the quieter bands into view.
        self._bar_peak = max(loudest, self._bar_peak * 0.995)
        target = np.minimum(BARS_MAX, np.sqrt(mags / self._bar_peak) * BARS_MAX)
        # quick to rise, slower to fall
        self.bars = np.where(target > self.bars, target, self.bars * 0.75 + target * 0.25).astype(np.float32)
