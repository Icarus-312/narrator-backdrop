#!/bin/bash
# End-to-end smoke test of the skill on the 20s fixture: init -> build -> check -> render -> mux -> scan. ~3 min.
# Usage: dryrun.sh [project_dir] [variant]   (default /Volumes/RURIK-1/hyperframes-projects/nb-dryrun)
#   variant = fixture/scenes.<variant>.json (stack = light + stack layout, dark = dark theme + stack, gallery-a/b = the other layouts; any variant with theme dark scans with --theme dark); omit for the base 4 scenes
set -euo pipefail
SK="$(cd "$(dirname "$0")/.." && pwd)"
HF="hyperframes@0.8.166"
P="${1:-/Volumes/RURIK-1/hyperframes-projects/nb-dryrun}"
rm -rf "$P"; mkdir -p "$(dirname "$P")"; cd "$(dirname "$P")"
npx "$HF" init "$(basename "$P")" --non-interactive --example=blank >/dev/null
cd "$P"
rm -f index.html *.html
cp -R "$SK/template/." . && cp -R "$SK/fixture/." .
VAR="${2:-}"; [ -n "$VAR" ] && cp "scenes.$VAR.json" scenes.json
python3 build.py
npm run check 2>&1 | grep -E "error\(s\)|✖" || true
npx "$HF" render . -q draft -o renders/dry.mp4 --quiet
ffmpeg -v error -y -i renders/dry.mp4 -i media/base.mp4 -map 0:v:0 -map 1:a:0 -c copy -t 20 renders/dry-synced.mp4
SCAN_ARGS=""; grep -q '"theme": *"dark"' scenes.json && SCAN_ARGS="--theme dark"
python3 "$SK/scripts/scan_transitions.py" renders/dry-synced.mp4 --audio-ref media/base.mp4 $SCAN_ARGS
echo "DRYRUN OK -> $P/renders/dry-synced.mp4"
