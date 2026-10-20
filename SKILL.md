---
name: narrator-backdrop
description: Turn a talking-head video's transcript into animated explainer scenes (light sheet, icon cards, drawn charts, pills, counters, all timed to spoken words) laid over the full-screen face-cam with a small face bubble at the right edge, built in HyperFrames. Use when the user says "/narrator-backdrop", "animated backdrop for my video", "animate my explainer", or hands over a talking video / transcript and wants the animated-graphic look.
---

# narrator-backdrop

Input: a talking-head video (or an EDL + source take). Output: the same video, with animated graphic scenes taking over on the teaching beats (face drops into a right-edge bubble) and full-screen face-cam in between. Style reference: a decoded explainer video, mechanics only. Always write own copy, data and chart shapes.

Files: `template/` (copy whole dir into the project: `build.py`, `helpers.js`, `style.css`, `media/fonts/`), `scripts/make_transcript.py`, `scripts/scan_transitions.py`, `scripts/dryrun.sh`, `fixture/` (20s sample: media + transcript + 4 scenes). HyperFrames pinned at `hyperframes@0.8.166`; `check` passes with 0 errors on that version.

## Pipeline

1. **Project** on `/Volumes/RURIK-1/hyperframes-projects/<name>/` (Mac drive is full): `npx hyperframes@0.8.166 init <name> --non-interactive --example=blank`, delete the scaffold `index.html`, copy `template/*` in. A second root HTML in the project root fails `check`.
2. **Media**: `media/base.mp4` = full final video, faststart, cleaned audio (`highpass=f=80,agate=threshold=0.008:ratio=1.5:attack=15:release=350:makeup=1`, then `loudnorm=I=-14:TP=-1.5:LRA=11`). `media/bubble.mp4` = portrait crop of the face (about 380x634 at 1080p), faststart. Pick the crop from one still; content must stay left of x=1560.
3. **Transcript**: `scripts/make_transcript.py --out <project> --video media/base.mp4` (continuous take, whisper) or `--edl edl.json --words source_words.json --segments clips_dir/` (edited video; uses the real clip durations, sorted numerically, see rule 4). Writes `transcript_full.json` + `script_timed.txt` and prints the `duration` to put in `scenes.json`.
4. **Scenes**: read `script_timed.txt`, write `scenes.json` with the rubric below. Layouts: `big-word`, `stat`, `line-chart`, `checklist`, `a-to-b`, `cards`, `bar-chart`, `stack`, `typewriter`, `pipeline`, `converge`, `word-cards`, `container`, `timeline-arc` (schema = `fixture/scenes.json` + `template/scenes.example.json`, 58 real scenes; `stack` = `fixture/scenes.stack.json`; the newer layouts = `fixture/scenes.gallery-a/b.json`, copy the scene you need). Theme: top-level `"theme": "light"` (default) or `"dark"` (dark navy stage, all colors are CSS tokens in `style.css`; run the scan with `--theme dark`).
5. **Build + preview**: `python3 build.py` (fails on missing anchor, scene < 1.5s, overlap, trigger outside its scene). Then `python3 build.py --preview <start> <end>` on a 30 to 60s window holding the riskiest 2 to 3 scenes (new layout, long pill, chart), `npx hyperframes render . -q draft -o renders/preview.mp4`, watch it (~1 min render). Fix, repeat. Then `python3 build.py` again (full) before the long render. Never ship a preview build.
6. **Render + gate**: `npm run check` (0 errors; nesting warnings are fine), `render -q draft` in the background (~2 min per video minute), mux source audio (rule 3), `scripts/scan_transitions.py renders/out.mp4 --audio-ref media/base.mp4`, exit 0 or do not push. Push with `/video-push --title`.

Smoke test the whole chain after any template change: `scripts/dryrun.sh [dir] [variant]` (~3 min, fixture, ends with the scan). Variants: none = base 4 scenes (light), `stack` = light + stack layout, `dark` = dark theme + stack, `gallery-a/b` = the newer layouts (b is dark). Any variant with `"theme":"dark"` scans with `--theme dark`. Mac disk is often full: run with `TMPDIR=/Volumes/RURIK-1/tmp` or the render stops on "Low disk space".

## Scene rubric (what makes a scene good)

- **One claim per scene.** One number, one list, one comparison, one word. Two ideas = two scenes.
- **Pill text = his spoken words**, 2 to 6 words, trimmed, never paraphrased into marketing copy. Pills pop on the first word of that phrase.
- **Big word = the noun he lands on**, max 3 words; `sub` is the 3 to 6 words he says right before it.
- **Stat only when he says a number.** Count-up starts on the number word, `dur` 0.5 to 1.0s. Two numbers = `dash` ("to", "→").
- **Checklist = 3 to 5 items he enumerates**, in his order, one row per item on its word. `highlight_t` only if he singles one out.
- **a-to-b = cause → effect or before → after** he states explicitly. Line draws over the words between them.
- **Charts show a shape he describes**, not data he didn't say. Bars rise one per spoken item; line draws across the phrase that describes growth.
- **Cards = 2 to 3 parallel options.** `dim_t` when he dismisses one.
- **Stack = a pile or volume of things** ("we read a lot", "every email", "all your notes"). 2 to 6 cards, each lands on one spoken word; optional `pill` under it and `shuffle_t` (first and last card swap, "mixed together"). `side`: left/center/right.
- **Typewriter = a sentence he builds word by word, with a correction.** `lines[].words[]` each on their word; `strikes:[{line,word,t}]` draws a red line through a word he walks back ("limited", "old way"); `red:true` colors a word.
- **Pipeline = 2 to 5 steps he enumerates in order** (arrows draw between tiles); `glow_t` lights the step he stresses; optional `pill`.
- **Converge = many inputs feeding one thing** ("emails, calls, notes all go into the assistant"). 2 to 5 `sources`, one `target`.
- **Word-cards = an acronym he spells out** (Retrieval / Augmented / Generation); first letters are oversized; `big` lands the acronym, `glow_t` outlines the cards.
- **Container = a limit that grows** ("context window", "bigger bucket"): box widens (`w_from` to `w_to` at `grow_t`), then `fill.count` icons pop in.
- **Timeline-arc = a loop of 3 to 6 steps** (idea, draft, edit, ship, learn); arc draws last tile back to first at `arc_t`; optional `pill` on the arc.
- **Scene window = the sentence(s) that carry the claim.** Start on the first content word, end on the end of the last word (`e:word`). 60 to 70% graphic coverage; stories, jokes, asides stay face-only (hold ≥ 3s of face between graphic blocks or close the gap entirely).
- **Layout variety:** no three consecutive scenes of the same layout. Alternate dense (chart, checklist) with light (big-word).

## Hard rules (each one was a real bug)

1. **Hard cuts only between face and graphics. Never fade the scene sheet.** The light `.sheet` stays 100% opaque for the whole scene. Only `.stage` content animates: blur-in on enter, horizontal streak + fade on exit. A fading sheet drops to ~50% and the face shows through; this shipped once at ~100 transitions. The bubble toggles with `tl.set`, never a fade.
2. **Scan every render, push only on exit 0.** `scan_transitions.py` checks every frame: 0 half-faded frames, 0 face flashes < 0.5s, bubble present on every sheet frame, audio lag ≤ 80ms at 3 points. Thresholds and probe boxes are flags (`--sheet --face --corner --bubble`); on a new palette run `--calib` first and pick thresholds where sheet and face luma never overlap. Also snapshot a few boundaries (end-0.3, end, start+0.1) before the long render.
3. **HyperFrames drifts audio on long renders** (~0.22% slow: 1.7s late by minute 13, video unaffected). Mux the source audio after every render: `ffmpeg -i render.mp4 -i media/base.mp4 -map 0:v:0 -map 1:a:0 -c copy -t <dur> out.mp4`. The scan's `--audio-ref` check catches a forgotten mux. Short test renders hide the drift.
4. **Edited timeline = real segment durations**, sorted numerically (`seg_100` sorts before `seg_11` as text). EDL start/end drift ~17ms per cut (2s over 129 cuts). `make_transcript.py --segments` does this; never map by EDL arithmetic alone.
5. **Every trigger is a word anchor** (`w:word`, `w:word#2`, `w:word+0.3`, `e:word`). `build.py` fails on a missing anchor or a trigger outside its scene window. ASR spells oddly (`revenuebased`, `chargeoff`, `longterm`, `blocks` for "B-locks"): grep `transcript_full.json` when an anchor fails.
6. **Hide numbers and connector glyphs until their trigger** (counters, "to", arrows), or "0%" and a lone arrow sit on screen early. The template does this; keep it when adding layouts.
7. **Layout bugs to catch in the preview render:** long pills overflowing cards (center pills over the line in a flex wrapper), chart axes past their card, text clipped at the bubble zone (x > 1560), 5+ checklist rows overflowing.
8. **No face-cam gap under 0.75s between scenes** (reads as a 3 to 14 frame flash). `build.py` auto-holds the earlier scene across such gaps; the scan flags any that remain.
9. **Cost:** ~2 min render per video minute (14:25 = ~28 min). Batch every fix into one render. Preview windows first, full render once.

## Animation spec (decoded)

Stack card: drifts in from 60px left / 40px low, rotates to its slot (±4°), blur 6px to 0, 0.45s `power3.out`, doc icon lights to accent 0.3s after landing; back cards rest at 70% opacity, front at 100%; cards land 0.15 to 0.4s apart on their words. Shuffle: first and last card swap position, rotation and z-order, 0.4s `power2.inOut`.


Newer layouts (frame-stepped from a reference explainer): typewriter words fade+rise 0.15s each, strike bar scaleX 0.3s while the word dims to 40%; pipeline/converge/timeline arrows draw by dashoffset (0.3 to 0.9s, `power2.inOut`) with the target tile popping on its word; glow = accent outline + halo 0.4s; container width tween 0.7s `power2.inOut` then icons pop 0.06s apart.

Pill pop 0.4s (scale 0.6 to 1.03 to 1, gray to solid, blur to sharp). Axes draw 0.25s each. Line draws ease-in with leading dot, area fill follows. Bars rise one per beat, 0.45s. Checklist row activates then last row fills olive. Content exit: SVG horizontal blur streak + drift left + fade, 0.35s. Content enter: blur 8px to 0, 0.35s.
