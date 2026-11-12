# Phase 8: Visualizer and Party Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** A subtle pulse behind the artwork that reacts to the beat (toggle in Settings), and a party mode (owner's request, 2026-11-12) that hides the controls and shows big lyrics bouncing with the music.

**Architecture:** `core/beat.py` (Qt-free, numpy) turns blocks of mono audio into a smoothed level (0..1) and beat events: low-band (40–180 Hz) energy, log onset flux against an adaptive threshold, a refractory gap, automatic gain so quiet and loud music both pulse. `core/audio_capture.py` records the default PipeWire output's monitor (`PULSE_SOURCE=@DEFAULT_MONITOR@`, PortAudio's `pulse` device, 22050 Hz mono, 1024-sample blocks, about 21 analyses a second) and runs the detector in the audio callback, keeping only the latest level and a beat counter. The controller polls those at 30 Hz while needed and exposes `audioLevel` / `beatCount`. Capture runs only while the visualizer or party mode is showing and music plays; otherwise the stream is closed (no CPU).

**Spec:** [AGENTS.md](../../../AGENTS.md) Phase 8 ("subtle pulse behind the artwork that reacts to the beat… capture audio from the local PipeWire output, lightweight FFT/onset detection, CPU low enough for a Raspberry Pi, toggleable in Settings"). Party mode: owner's message.

**Branch:** `phase8-visualizer-party`, on top of `phase7-sendspin-update` + `remote-keys` (both unmerged; rebase when they land).

## Decisions (my calls)

- Verified first on the TV: the sandbox (`--socket=pulseaudio`) can record the output monitor; a −60 dB test tone came back at the expected level.
- Visualizer: on by default. A soft glow in the artwork's palette colour behind the artwork card (and behind the small cover in the lyrics layout), its size following the level, with a quick swell on each beat. No pulse when this TV isn't the speaker playing (nothing to hear).
- Party mode: a Party button on the bar (left of Search). Full screen: blurred artwork, big centered lyrics (current line larger), the current line bounces on each beat; without lyrics, the artwork bounces in the middle. Title · artist small at the bottom; the guest QR stays if guest mode is on. Back leaves party mode; media keys keep working; arrows/OK do nothing (no hidden focus). Not remembered across restarts.
- CPU budget: an rfft of 1024 samples 21 times a second plus a 30 Hz poll; measured on the TV.

## Tasks

1. **Beat detector** — `BeatDetector(sample_rate, block)`: `feed(samples) -> (level, beat)`. Tests with synthetic kicks at 120 BPM (beats every 0.5 s), silence, a steady tone, quiet music (gain).
2. **Capture** — `AudioPulse(stream_factory)`: `start()`, `stop()`, `level`, `beats`, `available`; failures leave it unavailable. Tests with a fake stream.
3. **Controller** — `visualizerEnabled` (setting), `partyMode` / `togglePartyMode()`, `audioLevel`, `beatCount`, capture on/off rules. Tests.
4. **QML** — `BeatGlow.qml`, `PartyView.qml`, the Party button, Settings → Visualizer row, Back leaves party mode. TV check with a quiet test signal, CPU measured.
5. **Docs + PR.**
