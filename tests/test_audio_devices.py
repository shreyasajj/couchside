import pytest

from couchside.core.audio_devices import (
    AudioChoice,
    capture_source,
    output_choices,
    pactl_json,
    parse_sinks,
    parse_sources,
    source_choices,
)

SINKS = ('[{"name":"alsa_output.hdmi","description":"HDMI Surround",'
         '"monitor_source":"alsa_output.hdmi.monitor"}]')
SOURCES = ('[{"name":"alsa_input.usb","description":"USB Mic"},'
           '{"name":"alsa_output.hdmi.monitor","description":"Monitor of HDMI Surround"}]')


def test_parse_sinks():
    assert parse_sinks(SINKS) == [AudioChoice("sink:alsa_output.hdmi", "HDMI Surround", "Outputs")]


def test_parse_sources_splits_monitors_and_inputs():
    assert parse_sources(SOURCES) == [
        AudioChoice("alsa_output.hdmi.monitor", "HDMI Surround", "Outputs"),
        AudioChoice("alsa_input.usb", "USB Mic", "Inputs")]


@pytest.mark.parametrize("text", ["", "not json", "{}", "[1, null, {\"x\": 1}]"])
def test_garbage_gives_no_choices(text):
    assert parse_sinks(text) == [] and parse_sources(text) == []


def test_a_device_without_a_description_shows_its_name():
    assert parse_sinks('[{"name":"a"}]') == [AudioChoice("sink:a", "a", "Outputs")]


def test_output_choices_order_and_missing_saved():
    got = output_choices(parse_sinks(SINKS), ["HD-Audio Generic: HDMI 1 (hw:0,7)", "pulse"], "sink:gone")
    assert [c.id for c in got] == ["", "sink:alsa_output.hdmi", "HD-Audio Generic: HDMI 1 (hw:0,7)",
                                    "sink:gone"]
    assert got[0] == AudioChoice("", "Default", "")
    assert got[2].section == "Direct (visualizer can't listen)"
    assert got[-1].label == "gone (not connected)"


def test_a_saved_direct_device_that_is_unplugged_stays_listed():
    got = output_choices([], [], "HDMI 9 (hw:0,9)")
    assert got[-1] == AudioChoice("HDMI 9 (hw:0,9)", "HDMI 9 (hw:0,9) (not connected)", "")


def test_source_choices_default_first():
    assert source_choices([], None) == [AudioChoice("", "What this TV is playing", "")]
    got = source_choices(parse_sources(SOURCES), "gone")
    assert [c.id for c in got] == ["", "alsa_output.hdmi.monitor", "alsa_input.usb", "gone"]
    assert got[-1].label == "gone (not connected)"


def test_capture_source():
    assert capture_source(None, None) == "@DEFAULT_MONITOR@"
    assert capture_source(None, "sink:alsa_output.hdmi") == "alsa_output.hdmi.monitor"
    assert capture_source(None, "HD-Audio Generic: HDMI 1 (hw:0,7)") == "@DEFAULT_MONITOR@"
    assert capture_source("alsa_input.usb", "sink:x") == "alsa_input.usb"
    assert capture_source("gone", "sink:x", parse_sources(SOURCES)) == "x.monitor"
    assert capture_source("alsa_input.usb", None, parse_sources(SOURCES)) == "alsa_input.usb"


async def test_pactl_missing_returns_empty(monkeypatch):
    monkeypatch.setenv("PATH", "/nonexistent")
    assert await pactl_json("sinks") == ""
