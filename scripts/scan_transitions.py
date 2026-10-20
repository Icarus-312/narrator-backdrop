#!/usr/bin/env python3
"""Gate for narrator-backdrop renders. Exit 0 = clean, 1 = problems. Never push a render that exits 1.

  scan_transitions.py render.mp4 [--theme light|dark] [--audio-ref media/base.mp4] [--sheet 216] [--face 90]
                                 [--corner X,Y,W,H] [--bubble X,Y,W,H | --no-bubble]

Checks every frame:
  BLEND     corner luma between --face and --sheet = half-faded sheet, face shows through (the 41s bug)
  FLASH     full-screen face run shorter than 0.5s between two scenes (gap in scenes.json)
  NO-BUBBLE sheet frame whose bubble box is light (bubble hidden while a scene is up)
  AUDIO     with --audio-ref: envelope cross-correlation at 3 timestamps, fails if |lag| > 80ms (HyperFrames drift)

Calibrate on a new design: run `--calib` to print the corner/bubble luma histogram instead of judging it,
then pick --sheet/--face so sheet frames and face frames never overlap.
"""
import argparse
import math
import subprocess
import sys

ap = argparse.ArgumentParser()
ap.add_argument("src")
ap.add_argument("--audio-ref", help="source video/audio the render should match (media/base.mp4)")
ap.add_argument("--theme", choices=("light", "dark"), default="light", help="light: bright sheet, face is darker. dark: dark sheet, face is brighter")
ap.add_argument("--sheet", type=int, default=None, help="light: corner luma >= this = solid sheet. dark: corner luma <= this = solid sheet")
ap.add_argument("--face", type=int, default=None, help="light: corner luma <= this = full-screen face. dark: corner luma >= this = full-screen face")
ap.add_argument("--corner", default=None, help="probe box that is bare sheet on scenes and face-cam on full-screen shots. Default: light 0,0,120,80; dark 1800,0,120,120 (a face-cam top-left can be as dark as the dark sheet, so dark probes the top-right). Re-check with --calib on new footage")
ap.add_argument("--bubble", default="1730,420,140,240", help="probe box inside the face bubble")
ap.add_argument("--no-bubble", action="store_true")
ap.add_argument("--min-face", type=float, default=0.5, help="face runs shorter than this (s) = flash")
ap.add_argument("--max-lag", type=float, default=0.08, help="audio lag tolerance in seconds")
ap.add_argument("--calib", action="store_true", help="print luma histograms, no verdict")
A = ap.parse_args()
DARK = A.theme == "dark"
# defaults per theme; recalibrate with --calib if the palette changes (dark fixture: sheet probe ~20 luma, full-screen face probe ~190)
if A.sheet is None:
    A.sheet = 45 if DARK else 216
if A.face is None:
    A.face = 100 if DARK else 90
if A.corner is None:
    A.corner = "1800,0,120,120" if DARK else "0,0,120,80"


def luma_series(src, box):
    x, y, w, h = box.split(",")
    out = subprocess.run(["ffmpeg", "-v", "error", "-i", src, "-an", "-vf", f"crop={w}:{h}:{x}:{y},scale=1:1:flags=area,format=gray",
                          "-f", "rawvideo", "-"], check=True, capture_output=True).stdout
    return list(out)


def fps_of(src):
    num, _, den = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate",
                                           "-of", "csv=p=0", src]).decode().strip().partition("/")
    return float(num) / float(den or 1)


def dur_of(src):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", src]).decode().strip())


def runs(seq):
    out, i = [], 0
    while i < len(seq):
        j = i
        while j < len(seq) and seq[j] == seq[i]:
            j += 1
        out.append((seq[i], i, j))
        i = j
    return out


def envelope(src, at, secs=8.0, hz=100):
    """RMS envelope at `hz` of mono audio starting at `at`"""
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{at:.3f}", "-t", f"{secs}", "-i", src, "-vn", "-ac", "1", "-ar", "8000",
                          "-f", "s16le", "-"], check=True, capture_output=True).stdout
    n = len(pcm) // 2
    step = 8000 // hz
    env = []
    for k in range(0, n - step, step):
        acc = 0
        for m in range(k, k + step):
            v = int.from_bytes(pcm[2 * m:2 * m + 2], "little", signed=True)
            acc += v * v
        env.append(math.sqrt(acc / step))
    mean = sum(env) / max(len(env), 1)
    return [e - mean for e in env], hz


def best_lag(a, b, hz, max_shift=2.5):
    """lag (s) of b relative to a; positive = b is late"""
    L = int(max_shift * hz)
    best, best_c = 0, -1e18
    for lag in range(-L, L + 1):
        c = 0.0
        for i in range(max(0, -lag), min(len(a), len(b) - lag)):
            c += a[i] * b[i + lag]
        if c > best_c:
            best_c, best = c, lag
    return best / hz


fps = fps_of(A.src)
corner = luma_series(A.src, A.corner)
ts = lambda f: f"{int(f / fps // 60)}:{f / fps % 60:05.2f}"

if A.calib:
    hist = [0] * 16
    for v in corner:
        hist[v // 16] += 1
    print("corner luma histogram (16 bins of 16):", hist)
    if not A.no_bubble:
        bub = luma_series(A.src, A.bubble)
        hist = [0] * 16
        for v in bub:
            hist[v // 16] += 1
        print("bubble luma histogram:", hist)
    sys.exit(0)

if DARK:
    cls = ["S" if v <= A.sheet else "F" if v >= A.face else "B" for v in corner]
else:
    cls = ["S" if v >= A.sheet else "F" if v <= A.face else "B" for v in corner]
R = runs(cls)
blend = [(a, b) for k, a, b in R if k == "B"]
# a face run touching the very start or end of the video is legitimate
flash = [(a, b) for k, a, b in R if k == "F" and (b - a) / fps < A.min_face and a > 0 and b < len(cls)]

nob = []
if not A.no_bubble:
    bub = luma_series(A.src, A.bubble)
    # bubble missing = the probe box shows bare sheet (light is bright, dark is dark)
    miss = [k for k in range(min(len(cls), len(bub))) if cls[k] == "S" and (bub[k] <= 40 if DARK else bub[k] > 205)]
    i = 0
    while i < len(miss):
        j = i
        while j + 1 < len(miss) and miss[j + 1] == miss[j] + 1:
            j += 1
        nob.append((miss[i], miss[j] + 1))
        i = j + 1

lags = []
if A.audio_ref:
    d = min(dur_of(A.src), dur_of(A.audio_ref))
    for at in (d * 0.1, d * 0.5, d * 0.9 - 8):
        a, hz = envelope(A.audio_ref, at)
        b, _ = envelope(A.src, at)
        lags.append((at, best_lag(a, b, hz)))
bad_lag = [(at, lg) for at, lg in lags if abs(lg) > A.max_lag]

print(f"frames {len(cls)}  blend/half-fade runs: {len(blend)}  short face flashes: {len(flash)}  "
      f"scene frames missing bubble: {len(nob)}  audio lag: {[f'{lg:+.2f}s@{int(at)}s' for at, lg in lags] or 'not checked'}")
for a, b in nob[:40]: print(f"  NO-BUBBLE {ts(a)} ({(b - a) / fps:.2f}s)")
for a, b in blend[:40]: print(f"  BLEND {ts(a)} ({(b - a) / fps:.2f}s)")
for a, b in flash[:40]: print(f"  FLASH {ts(a)} ({(b - a) / fps:.2f}s)")
for at, lg in bad_lag: print(f"  AUDIO {int(at)}s: render audio {lg:+.2f}s vs source (mux source audio over the render)")
sys.exit(1 if blend or flash or nob or bad_lag else 0)
