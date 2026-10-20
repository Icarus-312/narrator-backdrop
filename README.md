# narrator-backdrop

Claude Code skill: turn a talking-head video into an animated explainer (light sheet, icon cards, drawn charts, pills, counters, all timed to the spoken words) with the face in a small right-edge bubble, rendered with [HyperFrames](https://hyperframes.dev).

Install: clone into `~/.claude/skills/narrator-backdrop/`, then `/narrator-backdrop` in Claude Code. Full pipeline, rules and scene rubric are in `SKILL.md`.

- `template/` copies into a new HyperFrames project (`build.py`, `helpers.js`, `style.css`, fonts).
- `scripts/make_transcript.py` word-level transcript (whisper, or EDL + real clip durations).
- `scripts/scan_transitions.py` per-frame render gate (half-fades, flashes, missing bubble, audio drift); `--theme dark` for the dark stage.
- `scripts/dryrun.sh` end-to-end smoke test on the 20s `fixture/`.

Pinned to `hyperframes@0.8.166`.

Layouts: big-word, stat, line-chart, checklist, a-to-b, cards, bar-chart, stack, typewriter, pipeline, converge, word-cards, container, timeline-arc. Light and dark themes. Test with `scripts/dryrun.sh <dir> gallery-a|gallery-b`.
