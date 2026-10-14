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
    for _ in range(150):
        proc = subprocess.run(
            ["xwininfo", "-root", "-tree"],
            capture_output=True, text=True, env=env, check=True,
        )
        for number in re.findall(r'^\s*(0x[0-9a-f]+)\s+"(Fuse[^"\n]*)"', proc.stdout, re.M):
            window_id = number[0]
            info = subprocess.run(
                ["xwininfo", "-id", window_id],
                capture_output=True, text=True, env=env, check=True,
            )
            if "Map State: IsViewable" in info.stdout:
                return int(window_id, 16)
        time.sleep(0.1)
    raise RuntimeError("A viewable Fuse SDL window did not appear in 15 s")


def send_rom_load(display):
    win = visible_fuse_window(display)
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
        time.sleep(0.3)

        def key(name, pressed):
            if not xtst.XTestFakeKeyEvent(ptr, KEYS[name], int(pressed), 0):
                raise RuntimeError("XTestFakeKeyEvent failed for " + name)
            x11.XFlush(ptr)
            time.sleep(0.075)

        def chord(modifier, name):
            key(modifier, True)
            key(name, True)
            key(name, False)
            key(modifier, False)

        key("j", True)
        key("j", False)
        chord("Control_L", "p")
        chord("Control_L", "p")
        key("Return", True)
        key("Return", False)
    finally:
        x11.XCloseDisplay(ptr)
    return {"result": "SENT", "window": hex(win),
            "spectrum_keys": ["J", "Ctrl+P", "Ctrl+P", "Enter"],
            "display": display}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--display", default=":99")
    p.add_argument("--log", type=Path, required=True)
    args = p.parse_args()
    result = send_rom_load(args.display)
    args.log.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
