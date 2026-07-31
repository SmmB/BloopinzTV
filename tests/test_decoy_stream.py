"""
Tests for the anti-scraper decoy-stream filter (scraping.player._is_decoy_stream).

Some hosts (e.g. french-stream's fsvid.lol) return a "troll" placeholder video
to bots instead of the real content — get_hls_link must reject it so the player
is marked unavailable and playback falls back to a host that works.
"""

from freeflix_cli.scraping import player


def test_troll_stream_is_decoy():
    assert player._is_decoy_stream("https://s1.fsvid.lol/troll/master.m3u8") is True
    assert player._is_decoy_stream("https://host/fake/master.m3u8") is True
    assert player._is_decoy_stream("https://host/decoy/x.m3u8") is True


def test_real_stream_is_not_decoy():
    assert player._is_decoy_stream(
        "https://strm4.uqload.is/hls2/04/02505/p44nkmonx8pe_n/master.m3u8?t=abc"
    ) is False
    assert player._is_decoy_stream("https://cdn.example.com/master.m3u8") is False


def test_empty_or_none_is_not_decoy():
    assert player._is_decoy_stream(None) is False
    assert player._is_decoy_stream("") is False
