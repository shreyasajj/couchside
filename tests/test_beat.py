import numpy as np

from couchside.core.beat import BeatDetector

SR, BLOCK = 22050, 1024


def kicks(seconds=6.0, bpm=120, amp=0.8, seed=1):
    """A kick drum (decaying 60 Hz thump) on every beat, over a steady chord and noise."""
    rng = np.random.default_rng(seed)
    n = int(SR * seconds)
    t = np.arange(n) / SR
    out = 0.15 * amp * (np.sin(2 * np.pi * 440 * t) + np.sin(2 * np.pi * 660 * t))
    out += 0.03 * amp * rng.standard_normal(n)
    period = 60.0 / bpm
    kick_t = np.arange(int(0.15 * SR)) / SR
    kick = amp * np.sin(2 * np.pi * 60 * kick_t) * np.exp(-kick_t * 30)
    for start in np.arange(0.25, seconds - 0.2, period):
        i = int(start * SR)
        out[i:i + len(kick)] += kick[: n - i]
    return out.astype(np.float32)


def run(signal):
    d = BeatDetector(SR, BLOCK)
    beats, levels = [], []
    for k in range(len(signal) // BLOCK):
        level, beat = d.feed(signal[k * BLOCK:(k + 1) * BLOCK])
        levels.append(level)
        if beat:
            beats.append(k * BLOCK / SR)
    return beats, levels


def test_finds_the_beat_at_120_bpm():
    beats, _ = run(kicks())
    assert 9 <= len(beats) <= 12, beats
    gaps = np.diff(beats[1:])
    assert abs(float(np.median(gaps)) - 0.5) < 0.06


def test_quiet_music_still_pulses():
    beats, levels = run(kicks(amp=0.01))
    assert 9 <= len(beats) <= 12
    assert max(levels[40:]) > 0.5  # automatic gain


def test_silence_is_still():
    beats, levels = run(np.zeros(SR * 4, np.float32))
    assert beats == [] and max(levels) == 0.0


def test_a_steady_tone_has_no_beat():
    t = np.arange(SR * 4) / SR
    beats, _ = run((0.5 * np.sin(2 * np.pi * 80 * t)).astype(np.float32))
    assert len(beats) <= 1


def test_level_is_between_0_and_1_and_follows_the_kicks():
    _, levels = run(kicks())
    assert all(0.0 <= v <= 1.0 for v in levels)
    assert max(levels[20:]) - min(levels[20:]) > 0.3  # it moves with the music


def test_stereo_or_odd_blocks_are_accepted():
    d = BeatDetector(SR, BLOCK)
    level, beat = d.feed(np.zeros((BLOCK, 2), np.float32))
    assert level == 0.0 and beat is False
    d.feed(np.zeros(300, np.float32))  # a short block doesn't crash
