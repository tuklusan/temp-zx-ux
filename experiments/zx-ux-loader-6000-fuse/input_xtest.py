#!/usr/bin/env python3
"""Inject Fuse SDL's verified ROM LOAD "" keystrokes over XTEST.

Adapted from tests/fuse_boot.py:send_rom_load(). This avoids guessing at
the GTK input window and keeps ZX Spectrum quotes as Ctrl+P, not host ".
The Xvfb US keyboard map supplies fixed keycodes for deterministic tests.
"""
import argparse
import ctypes
import json
import os
from pathlib import Path
import re
import subprocess
import time

KEYS = {"j": 44, "Control_L": 37, "p": 33, "Return": 36}


def visible_fuse_window(display):
    env = dict(os.environ, DISPLAY=display)
    last_error = "No viewable Fuse window"
    for _ in range(600):
        proc = subprocess.run(
            ["xwininfo", "-root", "-tree"],
            capture_output=True, text=True, env=env, check=False,
        )
        if proc.returncode:
            last_error = proc.stderr.strip() or f"xwininfo root exit {proc.returncode}"
            time.sleep(0.1)
            continue
        for number in re.findall(r'^\s*(0x[0-9a-f]+)\s+"(Fuse[^"\n]*)"', proc.stdout, re.M | re.I):
            window_id = number[0]
            info = subprocess.run(
                ["xwininfo", "-id", window_id],
                capture_output=True, text=True, env=env, check=False,
            )
            if info.returncode:
                last_error = info.stderr.strip() or f"xwininfo window exit {info.returncode}"
                continue
            if "Map State: IsViewable" in info.stdout:
                return int(window_id, 16)
        time.sleep(0.1)
    # Preserve the last visible candidate inventory on failure.
    x = subprocess.run(["xwininfo", "-root", "-tree"], env=env,
                       text=True, capture_output=True, check=False)
    candidates = [line.strip() for line in x.stdout.splitlines()
                  if '"fuse"' in line.lower()][:5]
    raise RuntimeError(
        f"A viewable Fuse SDL window did not appear in 60 s: "
        f"{last_error}; candidates={candidates!r}")


def send_rom_load(display, outdir):
    outdir.mkdir(parents=True, exist_ok=True)
    win = visible_fuse_window(display)

    def snapshot(stage):
        destination = outdir / f"key-{stage}.png"
        xwd = subprocess.run(
            ["xwd", "-root", "-silent"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=dict(os.environ, DISPLAY=display), check=True,
        )
        subprocess.run(
            ["convert", "xwd:-", str(destination)],
            input=xwd.stdout, capture_output=True, check=True,
        )
        return destination.stat().st_size

    x11 = ctypes.CDLL("libX11.so.6")
    xtst = ctypes.CDLL("libXtst.so.6")
    x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x11.XOpenDisplay.restype = ctypes.c_void_p
    x11.XSetInputFocus.argtypes = [
        ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong
    ]
    x11.XFlush.argtypes = [ctypes.c_void_p]
    x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
    xtst.XTestFakeKeyEvent.argtypes = [
        ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong
    ]
    xtst.XTestFakeKeyEvent.restype = ctypes.c_int
    ptr = x11.XOpenDisplay(display.encode())
    if not ptr:
        raise RuntimeError("Unable to open Xvfb display")
    try:
        x11.XSetInputFocus(ptr, win, 1, 0)
        x11.XFlush(ptr)
        time.sleep(2)
        snapshot("00-ready")

        def key(name, pressed):
            if not xtst.XTestFakeKeyEvent(ptr, KEYS[name], int(pressed), 0):
                raise RuntimeError("XTestFakeKeyEvent failed for " + name)
            x11.XFlush(ptr)
            time.sleep(0.2)

        def chord(modifier, name):
            key(modifier, True)
            key(name, True)
            key(name, False)
            key(modifier, False)

        key("j", True)
        key("j", False)
        time.sleep(0.6)
        snapshot("01-load-key")
        chord("Control_L", "p")
        chord("Control_L", "p")
        time.sleep(0.6)
        snapshot("02-quotes")
        key("Return", True)
        key("Return", False)
        time.sleep(1)
        snapshot("03-return")
        # Official Fuse real-tape workflow: with --no-traps, start playback
        # explicitly using F8 once the real BASIC LOAD command is active.
        subprocess.run(
            ["xdotool", "key", "--clearmodifiers", "F8"],
            env=dict(os.environ, DISPLAY=display), capture_output=True,
            text=True, check=True,
        )
        time.sleep(0.5)
        snapshot("03a-play")
        time.sleep(5)
        snapshot("04-wait")
    finally:
        x11.XCloseDisplay(ptr)
    return {"result": "SENT", "window": hex(win),
            "spectrum_keys": ["J", "Ctrl+P", "Ctrl+P", "Enter", "F8 (Tape Play)"],
            "display": display}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--display", default=":99")
    p.add_argument("--log", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args()
    try:
        result = send_rom_load(args.display, args.output_dir)
    except Exception as error:
        failure = {"result": "ERROR", "error": str(error), "display": args.display}
        args.log.write_text(json.dumps(failure, indent=2) + "\n")
        raise
    args.log.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
