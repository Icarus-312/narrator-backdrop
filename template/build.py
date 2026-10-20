#!/usr/bin/env python3
"""scenes.json + transcript_full.json -> index.html (HyperFrames). Generated output, never hand-edit index.html.

Times in scenes.json are seconds or word anchors:
  "w:word" / "w:word#2" / "w:word+0.3"  = start of the Nth spoken word at/after the scene start
  "e:word"                              = END of that word
  "=prev"  (scene start)                = previous scene's end ;  "end" (scene end) = end of video

Preview:  build.py --preview 60 100   -> index.html holds only 60s..100s (times shifted, base/bubble offset with data-media-start).
          Render that (~1 min), look, then run build.py again WITHOUT --preview before the full render.
"""
import argparse
import json
import pathlib
import re
import sys

ap = argparse.ArgumentParser()
ap.add_argument("--preview", nargs=2, type=float, metavar=("START", "END"), help="build only this time range")
ARGS = ap.parse_args()

R = pathlib.Path(__file__).parent
S = json.loads((R / "scenes.json").read_text())
TR = json.loads((R / "transcript_full.json").read_text())
D = S["duration"]
THEME = S.get("theme", "light")  # "light" (default) | "dark"; colors live in style.css tokens
if THEME not in ("light", "dark"):
    sys.exit(f"unknown theme {THEME!r}: use light or dark")
TIME_KEYS = re.compile(r"^(t|.*_t|draw_end)$")


def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


NW = [(norm(w["w"]), w["s"], w["e"]) for w in TR]
MISSING = []


def at(spec, after, where=""):
    if isinstance(spec, (int, float)):
        return float(spec)
    m = re.match(r"([we]):([^#+]+)(?:#(\d+))?(?:\+([\d.]+))?$", spec)
    if not m:
        MISSING.append(f"bad spec {spec!r} {where}")
        return after
    kind, word, nth, off = m.group(1), norm(m.group(2)), int(m.group(3) or 1), float(m.group(4) or 0)
    c = 0
    for nw, s, e in NW:
        if s >= after - 0.05 and nw == word:
            c += 1
            if c == nth:
                return round((s if kind == "w" else e) + off, 2)
    MISSING.append(f"anchor not found: {spec!r} after {after:.1f}s {where}")
    return after


def resolve(obj, after, where):
    if isinstance(obj, dict):
        for k, v in list(obj.items()):
            if isinstance(v, str) and TIME_KEYS.match(k):
                obj[k] = at(v, after, f"[{where}.{k}]")
            else:
                resolve(v, after, where)
    elif isinstance(obj, list):
        for v in obj:
            resolve(v, after, where)


# resolve scene boundaries first (sequentially), then inner triggers
prev_start, prev_end = 0.0, 0.0
for sc in S["scenes"]:
    st = sc["start"]
    sc["start"] = prev_end if st == "=prev" else at(st, prev_start, f"[{sc['id']}.start]")
    en = sc["end"]
    sc["end"] = D if en == "end" else at(en, sc["start"], f"[{sc['id']}.end]")
    resolve(sc, sc["start"], sc["id"])
    for k in ("start", "end"):
        sc[k] = float(sc[k])
    if sc["end"] - sc["start"] < 1.5:
        MISSING.append(f"{sc['id']} too short: {sc['start']:.1f}-{sc['end']:.1f}")
    if sc["start"] < prev_end - 0.05:
        MISSING.append(f"{sc['id']} overlaps previous scene: starts {sc['start']:.1f}, prev ended {prev_end:.1f}")
    prev_start, prev_end = sc["start"], sc["end"]

# a face-cam gap under 0.75s between two scenes reads as a one-frame flash: hold the earlier scene until the next starts
for a, b in zip(S["scenes"], S["scenes"][1:]):
    if 0 < b["start"] - a["end"] < 0.75:
        a["end"] = b["start"]


def times(obj, where, out):
    """every resolved trigger time in a scene, as (path, value)"""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if TIME_KEYS.match(k) and isinstance(v, (int, float)):
                out.append((f"{where}.{k}", float(v)))
            else:
                times(v, f"{where}.{k}", out)
    elif isinstance(obj, list):
        for n, v in enumerate(obj):
            times(v, f"{where}[{n}]", out)
    return out


# every trigger must fire inside its own scene window (a 0.35s exit streak starts at end-0.35, so nothing new after that)
for sc in S["scenes"]:
    for path, t in times({k: v for k, v in sc.items() if k not in ("start", "end")}, sc["id"], []):
        late = -0.01 if path.endswith("draw_end") else 0.35  # draw_end is an end time, may equal the scene end
        if t < sc["start"] - 0.01 or t > sc["end"] - late:
            MISSING.append(f"trigger outside scene: {path}={t:.2f} but {sc['id']} runs {sc['start']:.2f}-{sc['end']:.2f}")

if MISSING:
    print("\n".join(MISSING))
    sys.exit(1)

MEDIA_START = 0.0
if ARGS.preview:
    p0, p1 = ARGS.preview
    keep = []
    for sc in S["scenes"]:
        if sc["end"] <= p0 or sc["start"] >= p1:
            continue
        sc["start"], sc["end"] = max(sc["start"], p0), min(sc["end"], p1)
        keep.append(sc)
    S["scenes"] = keep

    def shift(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if (TIME_KEYS.match(k) or k in ("start", "end")) and isinstance(v, (int, float)):
                    obj[k] = round(min(max(v - p0, 0.0), p1 - p0), 3)
                else:
                    shift(v)
        elif isinstance(obj, list):
            for v in obj:
                shift(v)
    shift(S["scenes"])
    D, MEDIA_START = round(p1 - p0, 3), p0
    print(f"PREVIEW BUILD {p0}-{p1}s ({len(keep)} scenes). Re-run build.py without --preview before the full render.")

ICONS = {
    "building": '<path d="M6 22V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18Z"/><path d="M6 12H4a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h2"/>'
                '<path d="M18 9h2a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-2"/><path d="M10 6h4M10 10h4M10 14h4M10 18h4"/>',
    "rocket": '<path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/>'
              '<path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"/>'
              '<path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    "x": '<path d="M18 6 6 18M6 6l12 12"/>',
    "flag": '<path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><path d="M4 22v-7"/>',
    "chart": '<path d="M3 3v18h18"/><path d="M18 17V9M13 17V5M8 17v-3"/>',
    "clock": '<path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20z"/><path d="M12 6v6l4 2"/>',
    "card": '<path d="M2 7a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2z"/><path d="M2 10h20"/>',
    "doc": '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 9H8M16 13H8M16 17H8"/>',
    "search": '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    "bot": '<path d="M12 8V4H8"/><rect width="16" height="12" x="4" y="8" rx="2"/><path d="M2 14h2M20 14h2M15 13v2M9 13v2"/>',
    "db": '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14a9 3 0 0 0 18 0V5"/><path d="M3 12a9 3 0 0 0 18 0"/>',
    "bolt": '<path d="M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z"/>',
    "user": '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    "book": '<path d="M12 7v14"/><path d="M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z"/>',
    "key": '<path d="m21 2-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0 3 3L22 7l-3-3m-3.5 3.5L19 4"/>',
    "layers": '<path d="m12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83Z"/><path d="m22 17.65-9.17 4.16a2 2 0 0 1-1.66 0L2 17.65"/><path d="m22 12.65-9.17 4.16a2 2 0 0 1-1.66 0L2 12.65"/>',
    "users": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    "chat": '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
    "terminal": '<path d="m4 17 6-6-6-6"/><path d="M12 19h8"/>',
    "alert": '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4M12 17h.01"/>',
    "wrench": '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94z"/>',
    "bulb": '<path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/><path d="M9 18h6M10 22h4"/>',
    "refresh": '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/>',
    "mail": '<rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>',
    "globe": '<circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/>',
    "tag": '<path d="M12.586 2.586A2 2 0 0 0 11.172 2H4a2 2 0 0 0-2 2v7.172a2 2 0 0 0 .586 1.414l8.704 8.704a2.426 2.426 0 0 0 3.42 0l6.58-6.58a2.426 2.426 0 0 0 0-3.42z"/><circle cx="7.5" cy="7.5" r=".5" fill="currentColor"/>',
    "calendar": '<path d="M8 2v4M16 2v4"/><rect width="18" height="18" x="3" y="4" rx="2"/><path d="M3 10h18"/>',
    "sparkles": '<path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3z"/>',
    "folder": '<path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/>',
}


def icon(name, size, cls=""):
    return (f'<svg class="ico {cls}" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
            f'stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">{ICONS[name]}</svg>')


def pill_html(i, key, p, extra=""):
    return f'<div id="{i}-{key}" class="pill{" olive" if p.get("olive") else ""}{extra}">{p["text"]}</div>'


def abs_pill(i, key, p):
    return pill_html(i, key, p, " abs").replace('class="pill', f'style="left:{p["x"]}px;top:{p["y"]}px" class="pill', 1)


def wrap(sc, body):
    i = sc["id"]
    dur = round(sc["end"] - sc["start"], 3)
    return (f'<div id="{i}" class="scene clip" data-start="{sc["start"]}" data-duration="{dur}" data-track-index="1">'
            f'<div id="{i}-sc" class="sc"><div class="sheet"></div><div id="{i}-in" class="stage">{body}</div></div></div>')


def big_word(sc):
    i = sc["id"]
    w = sc["word"]
    size = 300 if len(w) <= 8 else 210 if len(w) <= 14 else 150 if len(w) <= 24 else 112
    parts, js = "", []
    if sc.get("sub"):
        parts += f'<div id="{i}-sub" class="serif sub">{sc["sub"]}</div>'
        js.append(f'rise("#{i}-sub",{sc["sub_t"]},16);')
        js.append(f'tl.to("#{i}-sub",{{opacity:0,duration:.25}},{sc["word_t"]});')
    parts += f'<div id="{i}-word" class="serif bigword" style="font-size:{size}px">{w}</div>'
    js.append(f'rise("#{i}-word",{sc["word_t"]},40);')
    if sc.get("pill"):
        parts += f'<div id="{i}-pill" class="pill{" olive" if sc.get("olive") else ""}">{sc["pill"]}</div>'
        js.append(f'pop("#{i}-pill",{sc["pill_t"]},{str(bool(sc.get("olive"))).lower()});')
    return f'<div class="col">{parts}</div>', js


def stat(sc):
    i = sc["id"]
    n_html, js = "", []
    for k, n in enumerate(sc["nums"]):
        if k:
            n_html += f'<span id="{i}-dash{k}" class="serif dash">{sc.get("dash", "")}</span>'
            js.append(f'rise("#{i}-dash{k}",{round(n["t"] - 0.15, 2)},18);')
        n_html += f'<span id="{i}-n{k}" class="serif num"></span>'
        js.append(f'rise("#{i}-n{k}",{round(n["t"] - 0.15, 2)},18);')
        js.append(f'count("#{i}-n{k}",{n["t"]},{n["dur"]},{n["to"]},"{sc.get("prefix", "")}","{sc.get("suffix", "")}");')
    body = '<div class="card statcard">'
    if sc.get("label"):
        body += f'<div id="{i}-label" class="eyebrow">{sc["label"]}</div>'
        js.append(f'rise("#{i}-label",{sc["label_t"]},12);')
    body += f'<div class="numrow">{n_html}</div>'
    if sc.get("pill"):
        body += f'<div id="{i}-pill" class="pill olive">{sc["pill"]}</div>'
        js.append(f'pop("#{i}-pill",{sc["pill_t"]},true);')
    if sc.get("sub"):
        body += f'<div id="{i}-sub" class="serif substat">{sc["sub"]}</div>'
        js.append(f'rise("#{i}-sub",{sc["sub_t"]},16);')
    return body + "</div>", js


CURVE = ("M0 470 C80 468 140 450 200 445 C280 440 300 455 380 430 C470 400 500 360 560 350 "
         "C640 338 640 300 700 270 C770 235 800 150 870 110 C920 82 960 40 1000 20")


def line_chart(sc):
    i = sc["id"]
    pills, js = "", []
    for k, p in enumerate(sc["pills"]):
        pills += abs_pill(i, f"p{k}", p)
        js.append(f'pop("#{i}-p{k}",{p["t"]},{str(bool(p.get("olive"))).lower()});')
    body = (f'<div class="card chartcard">'
            f'<div id="{i}-title" class="serif ctitle">{sc["title"]}</div>'
            f'<svg id="{i}-svg" class="chart" viewBox="-20 -20 1040 540" width="1040" height="540">'
            f'<defs><clipPath id="{i}-clip"><rect id="{i}-cr" x="-20" y="-20" width="0" height="560"/></clipPath></defs>'
            f'<path id="{i}-ghost" d="{CURVE} L1000 500 L0 500 Z" style="fill:var(--ghost)"/>'
            f'<path id="{i}-area" d="{CURVE} L1000 500 L0 500 Z" style="fill:var(--accent-soft)" clip-path="url(#{i}-clip)"/>'
            f'<line id="{i}-yax" x1="0" y1="500" x2="0" y2="0" style="stroke:var(--axis)" stroke-width="5" stroke-linecap="round" pathLength="1"/>'
            f'<line id="{i}-xax" x1="0" y1="500" x2="1000" y2="500" style="stroke:var(--axis)" stroke-width="5" stroke-linecap="round" pathLength="1"/>'
            f'<path id="{i}-line" d="{CURVE}" fill="none" style="stroke:var(--accent)" stroke-width="6" stroke-linecap="round"/>'
            f'<circle id="{i}-dot" r="10" cx="0" cy="470" style="fill:var(--accent)"/></svg>'
            f'<div class="xlab serif">time</div>{pills}</div>')
    st = sc["start"]
    js += [f'rise("#{i}-title",{sc["title_t"]},12);',
           f'tl.fromTo("#{i}-yax",{{strokeDasharray:1,strokeDashoffset:1}},{{strokeDashoffset:0,duration:.25,ease:"power2.out"}},{st + 0.25});',
           f'tl.fromTo("#{i}-xax",{{strokeDasharray:1,strokeDashoffset:1}},{{strokeDashoffset:0,duration:.3,ease:"power2.out"}},{st + 0.4});',
           f'tl.fromTo("#{i}-ghost",{{opacity:0}},{{opacity:1,duration:.5}},{st + 0.9});',
           f'tl.fromTo("#{i}-dot",{{opacity:0}},{{opacity:1,duration:.2}},{st + 0.7});',
           f'drawline("{i}",{sc["draw_t"]},{round(sc["draw_end"] - sc["draw_t"], 2)});']
    return body, js


def checklist(sc):
    i = sc["id"]
    rows, js = "", []
    if sc.get("title"):
        js.append(f'rise("#{i}-title",{sc["title_t"]},12);')
    for k, r in enumerate(sc["rows"]):
        rows += (f'<div id="{i}-r{k}" class="row"><span class="rowico">{icon("check", 40)}</span>'
                 f'<span id="{i}-t{k}" class="rowtxt">{r["text"]}</span><span id="{i}-d{k}" class="dot"></span></div>')
        js += [f'tl.to("#{i}-t{k}",{{color:C.ink,duration:.25}},{r["t"]});',
               f'tl.to("#{i}-r{k}",{{backgroundColor:C.rowOn,duration:.2}},{r["t"]});',
               f'popdot("#{i}-d{k}",{r["t"] + 0.1});']
    if sc.get("highlight_t") is not None:
        last = len(sc["rows"]) - 1
        js += [f'tl.to("#{i}-r{last}",{{backgroundColor:C.accent,duration:.25}},{sc["highlight_t"]});',
               f'tl.to("#{i}-t{last}",{{color:C.onAccent,duration:.25}},{sc["highlight_t"]});']
    title = f'<div id="{i}-title" class="serif ctitle">{sc["title"]}</div>' if sc.get("title") else ""
    return f'<div class="card listcard">{title}<div class="rows">{rows}</div></div>', js


def a_to_b(sc):
    i = sc["id"]
    a, b = sc["a"], sc["b"]
    body = (f'<div id="{i}-a" class="card nodecard na">{icon(a["icon"], 110, a.get("tone", "olive"))}<div class="serif nlabel">{a["text"]}</div></div>'
            f'<div id="{i}-line" class="hline"></div>'
            f'<div id="{i}-b" class="card nodecard nb">{icon(b["icon"], 110, b.get("tone", "olive"))}<div class="serif nlabel">{b["text"]}</div></div>')
    js = [f'cardIn("#{i}-a",{a["t"]});',
          f'tl.fromTo("#{i}-line",{{scaleX:0}},{{scaleX:1,duration:{sc["line_dur"]},ease:"power2.inOut"}},{sc["line_t"]});',
          f'cardIn("#{i}-b",{b["t"]});']
    if sc.get("top_pill"):
        body += f'<div id="{i}-top" class="pill abs" style="left:150px;top:190px">{sc["top_pill"]["text"]}</div>'
        js.append(f'pop("#{i}-top",{sc["top_pill"]["t"]});')
    if sc.get("mid_pill"):
        body += f'<div class="midwrap"><div id="{i}-mid" class="pill olive">{sc["mid_pill"]["text"]}</div></div>'
        js.append(f'pop("#{i}-mid",{sc["mid_pill"]["t"]},true);')
    return body, js


def cards(sc):
    i = sc["id"]
    items = sc["items"]
    n = len(items)
    w = min(440, int((1380 - (n - 1) * 50) / n))
    head, js, cols = "", [], ""
    if sc.get("heading"):
        head = f'<div id="{i}-h" class="serif chead">{sc["heading"]}</div>'
        js.append(f'rise("#{i}-h",{sc["heading_t"]},12);')
    for k, it in enumerate(items):
        pill = pill_html(i, f"cp{k}", it["pill"]) if it.get("pill") else ""
        sub = f'<div class="csub">{it["sub"]}</div>' if it.get("sub") else ""
        cols += (f'<div class="cwrap"><div id="{i}-c{k}" class="card ccard" style="width:{w}px">'
                 f'{icon(it["icon"], 100, it.get("tone", "olive"))}<div class="serif ctt">{it["title"]}</div>{sub}</div>{pill}</div>')
        js.append(f'cardIn("#{i}-c{k}",{it["t"]});')
        if it.get("pill"):
            js.append(f'pop("#{i}-cp{k}",{it["pill"]["t"]},{str(bool(it["pill"].get("olive"))).lower()});')
        if it.get("dim_t") is not None:
            js.append(f'tl.to("#{i}-c{k}",{{opacity:.35,duration:.3}},{it["dim_t"]});')
    return f'<div class="col">{head}<div class="cardrow">{cols}</div></div>', js


def bar_chart(sc):
    i = sc["id"]
    bars = sc["bars"]
    mx = max(b["value"] for b in bars)
    H = 400
    cols, labs, js = "", "", []
    for k, b in enumerate(bars):
        h = round(b["value"] / mx * H)
        cols += (f'<div class="barcol"><div id="{i}-v{k}" class="barval">{b["value"]}{sc.get("unit", "")}</div>'
                 f'<div id="{i}-b{k}" class="bar{" hot" if b.get("hot") else ""}"></div></div>')
        labs += f'<div class="barlab">{b.get("label", "")}</div>'
        js += [f'tl.fromTo("#{i}-b{k}",{{height:0}},{{height:{h},duration:.45,ease:"power3.out"}},{b["t"]});',
               f'rise("#{i}-v{k}",{round(b["t"] + 0.25, 2)},10);']
    pills = ""
    for k, p in enumerate(sc.get("pills", [])):
        pills += abs_pill(i, f"p{k}", p)
        js.append(f'pop("#{i}-p{k}",{p["t"]},{str(bool(p.get("olive"))).lower()});')
    js.append(f'rise("#{i}-title",{sc["title_t"]},12);')
    body = (f'<div class="card barcard"><div id="{i}-title" class="serif ctitle">{sc["title"]}</div>'
            f'<div class="bars">{cols}</div><div class="barlabs">{labs}</div>{pills}</div>')
    return body, js


# resting pose of each card in the pile (px offset from the pile origin, rotation deg); fixed so renders are deterministic
STACK_SLOTS = [(-190, 70, -4), (-75, -25, 3), (40, 60, -2), (155, -35, 4), (270, 50, -3), (385, -10, 2)]
SKEL_W = [(100, 82, 64), (88, 100, 70), (76, 92, 58), (100, 68, 84), (84, 100, 62), (92, 74, 100)]


def stack(sc):
    """doc cards fly in one by one and fan into a pile; optional shuffle swaps first/last; pill drops under it"""
    i = sc["id"]
    items = sc["items"]
    n = len(items)
    if not 2 <= n <= 6:
        MISSING.append(f"{i}: stack needs 2 to 6 items, got {n}")
        return "", []
    slots = STACK_SLOTS[:n]
    base_l = int(500 - 165 - sum(x for x, _, _ in slots) / n)
    dx = {"left": -230, "right": 230}.get(sc.get("side", "center"), 0)
    cards, js, poses = "", [], []
    for k, it in enumerate(items):
        x, y, r = slots[k]
        pose = {"x": x, "y": y, "r": r, "o": round(0.7 + 0.3 * k / (n - 1), 2), "z": k + 1}
        poses.append(pose)
        skel = "".join(f'<div class="skel" style="width:{w}%"></div>' for w in SKEL_W[k])
        cards += (f'<div id="{i}-c{k}" class="card doccard" style="left:{base_l}px;top:110px;z-index:{k + 1}">'
                  f'{icon(it.get("icon", "doc"), 56)}{skel}</div>')
        js.append(f'fan("#{i}-c{k}",{it["t"]},{json.dumps(pose)});')
    if sc.get("shuffle_t") is not None:
        js.append(f'swap("#{i}-c0",{json.dumps(poses[0])},"#{i}-c{n - 1}",{json.dumps(poses[-1])},{sc["shuffle_t"]});')
    pill = ""
    if sc.get("pill"):
        pill = f'<div class="stackpill"><div id="{i}-pill" class="pill">{sc["pill"]["text"]}</div></div>'
        js.append(f'pop("#{i}-pill",{sc["pill"]["t"]},false);')
    return f'<div class="stackwrap" style="transform:translateX({dx}px)">{cards}{pill}</div>', js


def under_pill(sc, js):
    """optional pill centered under the layout: sc["pill"] = {text, t, olive?}"""
    p = sc.get("pill")
    if not p:
        return ""
    js.append(f'pop("#{sc["id"]}-pill",{p["t"]},{str(bool(p.get("olive"))).lower()});')
    return pill_html(sc["id"], "pill", p)


def typewriter(sc):
    """words type in one by one on their anchors; strikes draw a red line through a word"""
    i = sc["id"]
    js, html = [], ""
    strikes = {(s["line"], s["word"]): s for s in sc.get("strikes", [])}
    longest = max(sum(len(w["text"]) + 1 for w in ln["words"]) for ln in sc["lines"])
    size = 112 if longest <= 24 else 96 if longest <= 28 else 80 if longest <= 34 else 64
    for a, ln in enumerate(sc["lines"]):
        ws = ""
        for b, w in enumerate(ln["words"]):
            pid = f"{i}-w{a}_{b}"
            bar = ""
            if (a, b) in strikes:
                bar = f'<i id="{pid}-bar" class="strike"></i>'
                js.append(f'strike("#{pid}-bar","#{pid}-t",{strikes[(a, b)]["t"]});')
            ws += f'<span id="{pid}" class="w{" red" if w.get("red") else ""}"><span id="{pid}-t">{w["text"]}</span>{bar}</span>'
            js.append(f'tl.fromTo("#{pid}",{{opacity:0,y:10}},{{opacity:1,y:0,duration:.15,ease:"power2.out"}},{w["t"]});')
        html += f'<div class="serif twline">{ws}</div>'
    return f'<div class="twblock" style="font-size:{size}px">{html}</div>', js


def pipeline(sc):
    """tile cards in a row; an arrow draws into each tile; glow_t lights a tile up"""
    i = sc["id"]
    nodes = sc["nodes"]
    n = len(nodes)
    if not 2 <= n <= 5:
        MISSING.append(f"{i}: pipeline needs 2 to 5 nodes, got {n}")
        return "", []
    w = min(300, int((1380 - (n - 1) * 100) / n))
    html, js = "", []
    for k, nd in enumerate(nodes):
        if k:
            t0 = round(max(nodes[k - 1]["t"] + 0.15, nd["t"] - 0.3), 2)
            html += (f'<svg class="plarrow" viewBox="0 0 100 30"><path id="{i}-a{k}" d="M6 15H92M80 5L92 15L80 25" fill="none" '
                     f'style="stroke:var(--accent)" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" pathLength="1"/></svg>')
            js.append(f'stroke("#{i}-a{k}",{t0},.3);')
        sub = f'<div class="csub">{nd["sub"]}</div>' if nd.get("sub") else ""
        html += (f'<div id="{i}-n{k}" class="card plnode" style="width:{w}px">{icon(nd["icon"], 90, "olive")}'
                 f'<div class="serif ctt">{nd["label"]}</div>{sub}</div>')
        js.append(f'cardIn("#{i}-n{k}",{nd["t"]});')
        if nd.get("glow_t") is not None:
            js.append(f'glow("#{i}-n{k}",{nd["glow_t"]});')
    pill = under_pill(sc, js)
    return f'<div class="col"><div class="plrow">{html}</div>{pill}</div>', js


def converge(sc):
    """sources on the left each draw a line into one target on the right"""
    i = sc["id"]
    src, tg = sc["sources"], sc["target"]
    n = len(src)
    if not 2 <= n <= 5:
        MISSING.append(f"{i}: converge needs 2 to 5 sources, got {n}")
        return "", []
    step = (700 - 110) / (n - 1)
    svg, cards, js = "", "", []
    for k, s in enumerate(src):
        y = round(k * step)
        cards += f'<div id="{i}-s{k}" class="card cvsrc" style="top:{y}px">{icon(s["icon"], 64, "olive")}<div class="serif lbl">{s["label"]}</div></div>'
        svg += (f'<path id="{i}-l{k}" d="M380 {y + 55} C615 {y + 55} 615 350 850 350" fill="none" style="stroke:var(--accent)" '
                f'stroke-width="4" stroke-linecap="round" pathLength="1" opacity=".85"/>')
        js += [f'cardIn("#{i}-s{k}",{s["t"]});', f'stroke("#{i}-l{k}",{round(s["t"] + 0.15, 2)},.55);']
    cards += f'<div id="{i}-tg" class="card cvtgt">{icon(tg["icon"], 110, "olive")}<div class="serif nlabel">{tg["label"]}</div></div>'
    js.append(f'cardIn("#{i}-tg",{tg["t"]});')
    return f'<div class="cvwrap"><svg class="cvsvg" width="1250" height="700" viewBox="0 0 1250 700">{svg}</svg>{cards}</div>', js


def word_cards(sc):
    """one card per word with an oversized accent first letter, then the big acronym"""
    i = sc["id"]
    words = sc["words"]
    size = 76 if len(words) <= 3 else 60
    cards, js = "", []
    for k, w in enumerate(words):
        t = w["text"]
        cards += f'<div id="{i}-w{k}" class="card wcard serif" style="font-size:{size}px"><span class="fl">{t[0]}</span>{t[1:]}</div>'
        js.append(f'cardIn("#{i}-w{k}",{w["t"]});')
        if sc.get("glow_t") is not None:
            js.append(f'glow("#{i}-w{k}",{sc["glow_t"]});')
    big = ""
    if sc.get("big"):
        big = f'<div id="{i}-big" class="serif wbig">{sc["big"]["text"]}</div>'
        js.append(f'rise("#{i}-big",{sc["big"]["t"]},40);')
    return f'<div class="col" style="gap:60px"><div class="wcards">{cards}</div>{big}</div>', js


FLOAT_POS = [(70, 150), (930, 130), (60, 690), (940, 700), (500, 30), (470, 810)]




def container(sc):
    """glass box grows wider, then icons pop in to fill it"""
    i = sc["id"]
    f = sc["fill"]
    icons = f.get("icons") or [f.get("icon", "doc")]
    tiles, js = "", [f'cardIn("#{i}-box",{sc["t"]});',
                     f'tl.fromTo("#{i}-box",{{width:{sc["w_from"]}}},{{width:{sc["w_to"]},duration:.7,ease:"power2.inOut"}},{sc["grow_t"]});']
    for k in range(f["count"]):
        tiles += f'<div id="{i}-g{k}" class="gtile">{icon(icons[k % len(icons)], 48)}</div>'
        js.append(f'popdot("#{i}-g{k}",{round(f["t"] + k * f.get("stagger", 0.06), 2)});')
    pill = under_pill(sc, js)
    box = (f'<div id="{i}-box" class="card gbox" style="width:{sc["w_from"]}px"><div class="gb-label mono">{sc.get("label", "")}</div>'
           f'<div class="gb-grid">{tiles}</div></div>')
    return f'<div class="col">{box}{pill}</div>', js






def timeline_arc(sc):
    """tiles in a row, then an arc loops from the last back to the first"""
    i = sc["id"]
    tiles = sc["tiles"]
    n = len(tiles)
    if not 3 <= n <= 6:
        MISSING.append(f"{i}: timeline-arc needs 3 to 6 tiles, got {n}")
        return "", []
    cx = [round(100 + k * 1100 / (n - 1)) for k in range(n)]
    html, js = "", []
    for k, tl_ in enumerate(tiles):
        html += (f'<div id="{i}-t{k}" class="card tltile" style="left:{cx[k] - 100}px">{icon(tl_["icon"], 70, "olive")}'
                 f'<div class="serif lbl">{tl_["label"]}</div></div>')
        js.append(f'cardIn("#{i}-t{k}",{tl_["t"]});')
    xl, x0 = cx[-1], cx[0]
    dur = sc.get("arc_dur", 0.8)
    svg = (f'<svg class="tlsvg" width="1300" height="560" viewBox="0 0 1300 560">'
           f'<path id="{i}-arc" d="M{xl} 280 C{xl} 20 {x0} 20 {x0} 280" fill="none" style="stroke:var(--accent)" stroke-width="6" stroke-linecap="round" pathLength="1"/>'
           f'<path id="{i}-head" d="M{x0 - 20} 246 L{x0} 284 L{x0 + 20} 246" fill="none" style="stroke:var(--accent)" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/></svg>')
    js += [f'stroke("#{i}-arc",{sc["arc_t"]},{dur});',
           f'tl.fromTo("#{i}-head",{{opacity:0}},{{opacity:1,duration:.15}},{round(sc["arc_t"] + dur - 0.1, 2)});']
    pill = ""
    if sc.get("pill"):
        pill = f'<div class="tlpillwrap"><div id="{i}-pill" class="pill olive">{sc["pill"]["text"]}</div></div>'
        js.append(f'pop("#{i}-pill",{sc["pill"]["t"]},true);')
    return f'<div class="tlwrap">{svg}{html}{pill}</div>', js










LAYOUTS = {"big-word": big_word, "stat": stat, "line-chart": line_chart, "checklist": checklist,
           "a-to-b": a_to_b, "cards": cards, "bar-chart": bar_chart, "stack": stack,
           "typewriter": typewriter, "pipeline": pipeline, "converge": converge, "word-cards": word_cards, "container": container,
           "timeline-arc": timeline_arc,}

scenes_html, scene_js, spans = [], [], []
for sc in S["scenes"]:
    body, js = LAYOUTS[sc["layout"]](sc)
    scenes_html.append(wrap(sc, body))
    i = sc["id"]
    scene_js.append(f'enter("#{i}-sc","#{i}-in",{sc["start"]});')
    scene_js += js
    if sc["end"] < D - 0.01:
        scene_js.append(f'exit("#{i}-sc","#{i}-in",{round(sc["end"] - 0.35, 3)});')
    spans.append([sc["start"], sc["end"]])

# face bubble shows only while a scene covers the full-screen face; merge touching scenes
merged = []
for s, e in spans:
    if merged and s <= merged[-1][1] + 0.05:
        merged[-1][1] = max(merged[-1][1], e)
    else:
        merged.append([s, e])
if merged[0][0] > 0.01:
    scene_js.append('tl.set("#facewrap",{opacity:0},0);')
for s, e in merged:
    scene_js.append(f'tl.set("#facewrap",{{opacity:1}},{s});')
    if e < D - 0.01:
        scene_js.append(f'tl.set("#facewrap",{{opacity:0}},{e});')

CSS = (R / "style.css").read_text()
JS_HELPERS = (R / "helpers.js").read_text()

html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=1920, height=1080" />
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>
{CSS}
</style>
</head>
<body>
<div id="root" class="theme-{THEME}" data-composition-id="main" data-start="0" data-duration="{D}" data-width="1920" data-height="1080">
<video id="base" src="media/base.mp4" data-start="0" data-duration="{D}" data-media-start="{MEDIA_START}" data-track-index="0" data-has-audio="true" playsinline></video>
<svg width="0" height="0" style="position:absolute"><filter id="hblur" x="-30%" y="-10%" width="160%" height="120%"><feGaussianBlur id="hb" stdDeviation="0 0"/></filter></svg>
{chr(10).join(scenes_html)}
<div id="facewrap"><video id="bubble" src="media/bubble.mp4" data-start="0" data-duration="{D}" data-media-start="{MEDIA_START}" data-track-index="2" data-has-audio="false" muted playsinline></video></div>
</div>
<script>
const tl = gsap.timeline({{ paused: true }});
{JS_HELPERS}
{chr(10).join(scene_js)}
window.__timelines["main"] = tl;
tl.seek(0);
</script>
</body>
</html>
"""
(R / "index.html").write_text(html)
cover = sum(e - s for s, e in merged)
print(f"index.html written: {len(S['scenes'])} scenes, {D}s, graphics cover {cover:.0f}s ({cover / D * 100:.0f}%)")
(R / "resolved.json").write_text(json.dumps(S, indent=1))
