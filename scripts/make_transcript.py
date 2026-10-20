#!/usr/bin/env python3
"""Word-level transcript -> transcript_full.json ([{"w","s","e"}], seconds in the FINAL video) + script_timed.txt.

  A. unedited video (one continuous take):
       make_transcript.py --video final.mp4 --out <project>          (whisper, word timestamps, ~1x realtime on CPU)
  B. edited video built from an EDL of ranges in a source take:
       make_transcript.py --edl edl.json --words source_words.json --segments clips_dir/ --out <project>
     - source_words: whisper json (segments[].words[]) or ElevenLabs json (words[] with type=="word")
     - segments: the per-range clips actually concatenated (seg_00_*.mp4 ...), sorted NUMERICALLY.
       Their real durations place each range; EDL start/end drift ~17ms per cut and would be ~2s off by the end.

Use B whenever the final video came from a cut list. Use A on the final video itself when it did not.
"""
import argparse
import json
import pathlib
import re
import subprocess
import sys
import tempfile

ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True, help="project dir (writes transcript_full.json + script_timed.txt)")
ap.add_argument("--video", help="mode A: final video to transcribe")
ap.add_argument("--model", default="base", help="whisper model for mode A")
ap.add_argument("--edl", help="mode B: edl.json with ranges[{start,end}] in source seconds")
ap.add_argument("--words", help="mode B: word-level transcript of the SOURCE take")
ap.add_argument("--segments", help="mode B: dir of per-range clips, used for real durations")
A = ap.parse_args()
OUT = pathlib.Path(A.out)


def load_words(path):
    d = json.load(open(path))
    if "segments" in d:  # whisper
        return [{"w": w["word"].strip(), "s": w["start"], "e": w["end"]} for s in d["segments"] for w in s.get("words", [])]
    return [{"w": w["text"], "s": w["start"], "e": w["end"]} for w in d["words"] if w.get("type", "word") == "word"]


def dur_of(p):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]).decode())


def numkey(p):
    return [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", p.name)]


if A.video:
    whisper = pathlib.Path.home() / "Library/Python/3.9/bin/whisper"
    if not whisper.exists():
        whisper = "whisper"
    with tempfile.TemporaryDirectory() as td:
        subprocess.run([str(whisper), A.video, "--model", A.model, "--word_timestamps", "True", "--output_format", "json",
                        "--output_dir", td, "--language", "en"], check=True)
        words = load_words(next(pathlib.Path(td).glob("*.json")))
    total = dur_of(A.video)
elif A.edl and A.words and A.segments:
    E = json.load(open(A.edl))["ranges"]
    src = load_words(A.words)
    segs = sorted(pathlib.Path(A.segments).glob("*.mp4"), key=numkey)
    if len(segs) != len(E):
        sys.exit(f"{len(E)} EDL ranges but {len(segs)} segment clips in {A.segments}")
    words, cum = [], 0.0
    for r, seg in zip(E, segs):
        real = dur_of(seg)
        for w in src:
            if r["start"] - 0.02 <= w["s"] < r["end"] - 0.02:
                words.append({"w": w["w"], "s": round(cum + w["s"] - r["start"], 2), "e": round(cum + min(w["e"], r["end"]) - r["start"], 2)})
        cum += real
    total = round(cum, 2)
else:
    ap.error("need --video, or --edl + --words + --segments")

OUT.mkdir(parents=True, exist_ok=True)
(OUT / "transcript_full.json").write_text(json.dumps(words))
lines, line, start = [], [], None
for w in words:
    if start is None:
        start = w["s"]
    line.append(w["w"])
    if re.search(r"[.?!]$", w["w"]) or len(line) >= 14:
        lines.append(f"[{int(start // 60)}:{start % 60:05.2f}] {' '.join(line)}")
        line, start = [], None
if line:
    lines.append(f"[{int(start // 60)}:{start % 60:05.2f}] {' '.join(line)}")
(OUT / "script_timed.txt").write_text("\n".join(lines) + "\n")
print(f"{len(words)} words, video {total}s -> {OUT / 'transcript_full.json'}  (set \"duration\": {total} in scenes.json)")
