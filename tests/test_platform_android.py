"""
Tests for the Android/Termux playback delegation (freeflix_cli.platform_android).

We mock Android's `am` so these run on any CI runner : verify detection, and
that launch_player tries mpv-android first, falls back to VLC, and reports the
player it succeeded with.
"""

import subprocess
import types

from freeflix_cli import platform_android as pa


def test_is_termux_via_env(monkeypatch):
    monkeypatch.setenv("TERMUX_VERSION", "0.118")
    assert pa.is_termux() is True
    assert pa.is_android() is True


def test_not_android_on_plain_linux(monkeypatch):
    monkeypatch.delenv("TERMUX_VERSION", raising=False)
    monkeypatch.delenv("PREFIX", raising=False)
    monkeypatch.delenv("ANDROID_ROOT", raising=False)
    monkeypatch.delenv("ANDROID_DATA", raising=False)
    monkeypatch.setattr(pa.os.path, "exists", lambda p: False)
    assert pa.is_termux() is False
    assert pa.is_android() is False


def test_launch_prefers_mpv_android(monkeypatch):
    monkeypatch.setattr(pa, "_am_binary", lambda: "/fake/am")
    monkeypatch.setattr(pa.shutil, "which", lambda b: None)  # no termux-open
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        # success only for mpv-android
        rc = 0 if "is.xyz.mpv" in cmd else 1
        out = "Starting: Intent {...}" if rc == 0 else "Error: does not exist"
        return types.SimpleNamespace(returncode=rc, stdout=out, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    ok, label, diag = pa.launch_player("http://127.0.0.1:5000/stream?url=x")
    assert ok is True
    assert label == "mpv-android"
    assert any("is.xyz.mpv" in c for c in calls)
    assert any("-d" in c and "127.0.0.1" in c[c.index("-d") + 1] for c in calls)


def test_launch_falls_back_to_vlc(monkeypatch):
    monkeypatch.setattr(pa, "_am_binary", lambda: "/fake/am")
    monkeypatch.setattr(pa.shutil, "which", lambda b: None)

    def fake_run(cmd, **kw):
        rc = 0 if "org.videolan.vlc" in cmd else 1
        out = "Starting" if rc == 0 else "Error: no activities found"
        return types.SimpleNamespace(returncode=rc, stdout=out, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    ok, label, diag = pa.launch_player("http://127.0.0.1:5000/stream?url=x")
    assert ok is True
    assert label == "VLC"


def test_proot_linker_failure_is_reported_not_silent(monkeypatch):
    # am under proot fails to link app_process → must NOT report success.
    monkeypatch.setattr(pa, "_am_binary", lambda: "/system/bin/am")
    monkeypatch.setattr(pa.shutil, "which", lambda b: None)

    def fake_run(cmd, **kw):
        return types.SimpleNamespace(
            returncode=1, stdout="",
            stderr="CANNOT LINK EXECUTABLE ... app_process ... libnativeloader.so",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    ok, label, diag = pa.launch_player("http://127.0.0.1:5000/stream?url=x")
    assert ok is False
    assert "app_process" in diag or "link" in diag.lower()


def test_termux_open_success_without_starting(monkeypatch):
    monkeypatch.setattr(pa, "_am_binary", lambda: None)
    monkeypatch.setattr(pa.shutil, "which", lambda b: "/usr/bin/termux-open" if b == "termux-open" else None)
    monkeypatch.setattr(subprocess, "run",
                        lambda cmd, **kw: types.SimpleNamespace(returncode=0, stdout="", stderr=""))
    ok, label, diag = pa.launch_player("http://127.0.0.1:5000/stream?url=x")
    assert ok is True
    assert label == "termux-open"


def test_is_proot_detection(monkeypatch):
    monkeypatch.setattr(pa, "is_android", lambda: True)
    monkeypatch.setattr(pa, "is_termux", lambda: False)
    assert pa.is_proot() is True
    monkeypatch.setattr(pa, "is_termux", lambda: True)
    assert pa.is_proot() is False


def test_available_needs_launcher(monkeypatch):
    monkeypatch.setattr(pa, "is_android", lambda: True)
    monkeypatch.setattr(pa, "_am_binary", lambda: None)
    monkeypatch.setattr(pa.shutil, "which", lambda b: None)
    assert pa.available() is False
    monkeypatch.setattr(pa, "_am_binary", lambda: "/fake/am")
    assert pa.available() is True
