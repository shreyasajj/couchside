"""The choices behind two Settings lists: where Sendspin plays, and what the visualizer
listens to. Outputs and sources come from PipeWire through `pactl` (it works inside the
Flatpak with the PulseAudio socket); Sendspin's own device list is raw ALSA hardware that
bypasses PipeWire, so nothing can listen to it: those are offered last, as "direct". Qt-free.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)

DEFAULT_MONITOR = "@DEFAULT_MONITOR@"
SINK_PREFIX = "sink:"
DIRECT = "Direct (visualizer can't listen)"
OUTPUTS, INPUTS = "Outputs", "Inputs"


@dataclass(frozen=True)
class AudioChoice:
    id: str        # "" = automatic; "sink:<name>"; a direct device name; a source name
    label: str
    section: str


def _devices(text: str) -> list[dict]:
    try:
        data = json.loads(text)
    except ValueError:
        return []
    if not isinstance(data, list):
        return []
    return [d for d in data if isinstance(d, dict) and isinstance(d.get("name"), str) and d["name"]]


def _label(device: dict) -> str:
    desc = device.get("description")
    return desc.strip() if isinstance(desc, str) and desc.strip() else device["name"]


def parse_sinks(text: str) -> list[AudioChoice]:
    """`pactl -f json list sinks` -> the outputs Sendspin can play to."""
    return [AudioChoice(SINK_PREFIX + d["name"], _label(d), OUTPUTS) for d in _devices(text)]


def parse_sources(text: str) -> list[AudioChoice]:
    """`pactl -f json list sources` -> what can be listened to: outputs first, then inputs."""
    monitors, inputs = [], []
    for d in _devices(text):
        label = _label(d)
        if d["name"].endswith(".monitor"):
            if label.startswith("Monitor of "):
                label = label[len("Monitor of "):]
            monitors.append(AudioChoice(d["name"], label, OUTPUTS))
        else:
            inputs.append(AudioChoice(d["name"], label, INPUTS))
    return monitors + inputs


async def pactl_json(kind: str, timeout: float = 5.0) -> str:
    """`pactl -f json list <kind>` ("sinks" or "sources"); "" when it can't be asked."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "pactl", "-f", "json", "list", kind,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
    except OSError as e:
        log.info("pactl is not available: %s", e)
        return ""
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return ""
    return out.decode(errors="replace") if proc.returncode == 0 else ""


def _with_saved(choices: list[AudioChoice], saved: str | None) -> list[AudioChoice]:
    """Keep a saved choice that isn't there right now (unplugged) in the list."""
    if saved and all(c.id != saved for c in choices):
        name = saved[len(SINK_PREFIX):] if saved.startswith(SINK_PREFIX) else saved
        choices.append(AudioChoice(saved, f"{name} (not connected)", ""))
    return choices


def output_choices(sinks: list[AudioChoice], direct: list[str], saved: str | None) -> list[AudioChoice]:
    choices = [AudioChoice("", "Default", "")] + list(sinks)
    # "pulse" is the PipeWire route, which the outputs above already are
    choices += [AudioChoice(name, name, DIRECT) for name in direct if name != "pulse"]
    return _with_saved(choices, saved)


def source_choices(sources: list[AudioChoice], saved: str | None) -> list[AudioChoice]:
    return _with_saved([AudioChoice("", "What this TV is playing", "")] + list(sources), saved)


def capture_source(visualizer_source: str | None, output: str | None,
                   sources: list[AudioChoice] | None = None) -> str:
    """The PulseAudio source to record: the chosen one while it exists (or when the list
    is unknown), else the monitor of the output Sendspin plays to, else the default
    output's monitor."""
    if visualizer_source and (sources is None or any(s.id == visualizer_source for s in sources)):
        return visualizer_source
    if output and output.startswith(SINK_PREFIX):
        return output[len(SINK_PREFIX):] + ".monitor"
    return DEFAULT_MONITOR
