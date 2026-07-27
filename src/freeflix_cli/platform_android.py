"""
Android / Termux integration.

FreeFlix runs on Android inside Termux (or a proot Debian userland). There's no
display for a subprocess mpv/vlc, so playback is delegated to an EXTERNAL
Android video player (mpv-android first, then VLC) via an ``am start`` intent.
The external player reads FreeFlix's local proxy over the shared Android
loopback, so header injection + m3u8 rewriting still work exactly as on desktop.

Everything degrades gracefully : on a non-Android box every function is a
cheap no-op / False, so importing this module is always safe.
"""

from __future__ import annotations

import os
import shutil
import subprocess

# mpv-android is the best target : it honours the "video/any" MIME (forces
# playback regardless of extension) and handles HLS + headers. VLC is the
# fallback. Order matters — first installed wins.
ANDROID_PLAYER_PACKAGES = [
    ("is.xyz.mpv", "mpv-android"),
    ("org.videolan.vlc", "VLC"),
]


def is_termux() -> bool:
    """True when running inside the Termux app itself."""
    if os.environ.get("TERMUX_VERSION"):
        return True
    return "com.termux" in (os.environ.get("PREFIX", "") or "")


def is_android() -> bool:
    """True on Android — Termux directly, or a proot distro on top of Android."""
    if is_termux():
        return True
    if os.environ.get("ANDROID_ROOT") or os.environ.get("ANDROID_DATA"):
        return True
    # proot Debian/Ubuntu : the Android system partition is still mounted.
    return os.path.exists("/system/build.prop") or os.path.exists("/system/bin/am")


def _am_binary() -> str | None:
    """Path to Android's `am` (activity manager) — on PATH in Termux, at
    /system/bin/am inside a proot distro."""
    found = shutil.which("am")
    if found:
        return found
    for cand in ("/system/bin/am", "/system/xbin/am"):
        if os.path.exists(cand):
            return cand
    return None


def available() -> bool:
    """True if we can actually hand off playback to an Android player."""
    return is_android() and _am_binary() is not None


def _looks_like_error(output: str) -> bool:
    low = (output or "").lower()
    return (
        "error" in low
        or "does not exist" in low
        or "unable to resolve" in low
        or "no activities found" in low
    )


def launch_player(url: str, title: str | None = None) -> tuple[bool, str]:
    """
    Hand *url* to an Android video player via an intent. Tries mpv-android then
    VLC then a generic chooser. Returns (ok, player_label).
    """
    am = _am_binary()
    if not am:
        return False, ""

    for pkg, label in ANDROID_PLAYER_PACKAGES:
        cmd = [
            am, "start",
            "-a", "android.intent.action.VIEW",
            "-t", "video/any",
            "-p", pkg,
            "-d", url,
        ]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        except Exception:
            continue
        out = (r.stdout or "") + (r.stderr or "")
        if r.returncode == 0 and not _looks_like_error(out):
            return True, label

    # Last resort : no explicit package → let Android show its player chooser.
    try:
        subprocess.run(
            [am, "start", "-a", "android.intent.action.VIEW", "-t", "video/any", "-d", url],
            capture_output=True, text=True, timeout=15,
        )
        return True, "Android"
    except Exception:
        return False, ""
