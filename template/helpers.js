const E = "power3.out";
// theme colors come from the CSS tokens on #root (style.css), so light and dark share one set of helpers
const CV = (n) => getComputedStyle(document.getElementById("root")).getPropertyValue(n).trim();
const C = { ink: CV("--ink"), accent: CV("--accent"), onAccent: CV("--on-accent"), rowOn: CV("--row-on"), pillBg: CV("--pill-bg"),
            pillFrom: CV("--pill-from"), oliveFrom: CV("--pill-olive-from"), red: CV("--red"), inkIco: CV("--ink-ico"), glow: CV("--glow") };
// scene enter: hard cut onto the sheet, content blurs in (~0.35s)
function enter(sc, st, t) {
  tl.fromTo(st, { filter: "blur(8px)" }, { filter: "blur(0px)", duration: 0.35, ease: E }, t);
}
// scene exit: content streaks out horizontally (SVG directional blur) + drifts left + fades; the sheet itself never fades
function exit(sc, st, t) {
  tl.set(st, { filter: "url(#hblur)" }, t);
  tl.fromTo("#hb", { attr: { stdDeviation: "0 0" } }, { attr: { stdDeviation: "70 0" }, duration: 0.35, ease: "power2.in" }, t);
  tl.to(st, { x: -90, scaleX: 1.06, opacity: 0, duration: 0.35, ease: "power2.in" }, t);
}
// pill pop: scale 0.6 -> 1 with overshoot, gray -> solid, blur -> sharp (~0.4s)
function pop(sel, t, olive) {
  tl.fromTo(sel,
    { opacity: 0, scale: 0.6, filter: "blur(3px)", backgroundColor: olive ? C.oliveFrom : C.pillFrom },
    { opacity: 1, scale: 1, filter: "blur(0px)", backgroundColor: olive ? C.accent : C.pillBg, duration: 0.4, ease: "back.out(1.7)" }, t);
}
function popdot(sel, t) { tl.fromTo(sel, { opacity: 0, scale: 0.3 }, { opacity: 1, scale: 1, duration: 0.35, ease: "back.out(2)" }, t); }
function rise(sel, t, y) { tl.fromTo(sel, { opacity: 0, y: y || 24, filter: "blur(4px)" }, { opacity: 1, y: 0, filter: "blur(0px)", duration: 0.4, ease: E }, t); }
function cardIn(sel, t) { tl.fromTo(sel, { opacity: 0, scale: 0.92, filter: "blur(6px)" }, { opacity: 1, scale: 1, filter: "blur(0px)", duration: 0.35, ease: E }, t); }
// stack: a card drifts in from lower-left with a small rotation and settles into its slot in the pile (~0.45s).
// f = final {x, y, r, o}: offset px, rotation deg, resting opacity (back cards dimmer). The doc icon lights up once settled.
function fan(sel, t, f) {
  tl.fromTo(sel, { opacity: 0, x: f.x - 60, y: f.y + 40, rotation: 0, scale: 0.94, filter: "blur(6px)" },
    { opacity: f.o, x: f.x, y: f.y, rotation: f.r, scale: 1, filter: "blur(0px)", duration: 0.45, ease: E }, t);
  tl.to(sel + " .ico", { color: C.accent, duration: 0.25 }, t + 0.3);
}
// stack shuffle: two cards swap slots (position + rotation + z-order) so the pile reads as being mixed (~0.4s)
function swap(a, fa, b, fb, t) {
  tl.set(a, { zIndex: fb.z }, t + 0.2);
  tl.set(b, { zIndex: fa.z }, t + 0.2);
  tl.to(a, { x: fb.x, y: fb.y, rotation: fb.r, duration: 0.4, ease: "power2.inOut" }, t);
  tl.to(b, { x: fa.x, y: fa.y, rotation: fa.r, duration: 0.4, ease: "power2.inOut" }, t);
}
function count(sel, t, dur, to, pre, suf) {
  const el = document.querySelector(sel), o = { v: 0 };
  const fmt = (v) => pre + Math.round(v) + suf;
  el.textContent = fmt(0);
  tl.fromTo(o, { v: 0 }, { v: to, duration: dur, ease: "power2.out", onUpdate() { el.textContent = fmt(o.v); } }, t);
}
// line chart draw: dash-offset stroke, leading dot, area clip follows the dot; ease-in = slow start, accelerates
function drawline(id, t, dur) {
  const path = document.getElementById(id + "-line"), dot = document.getElementById(id + "-dot"), cr = document.getElementById(id + "-cr");
  const len = path.getTotalLength(), o = { p: 0 };
  path.style.strokeDasharray = len;
  path.style.strokeDashoffset = len;
  tl.fromTo(o, { p: 0 }, { p: 1, duration: dur, ease: "power2.in", onUpdate() {
    path.style.strokeDashoffset = len * (1 - o.p);
    const pt = path.getPointAtLength(len * o.p);
    dot.setAttribute("cx", pt.x); dot.setAttribute("cy", pt.y);
    cr.setAttribute("width", pt.x + 20);
  } }, t);
}
// glow: accent outline + halo on a card
function glow(sel, t) { tl.to(sel, { borderColor: C.accent, boxShadow: "0 0 0 2px " + C.accent + ", 0 0 44px " + C.glow, duration: 0.4, ease: "power2.out" }, t); }
// floating pill: drifts up into place with a small overshoot (~0.45s)
function floatpop(sel, t) { tl.fromTo(sel, { opacity: 0, scale: 0.8, y: 16 }, { opacity: 1, scale: 1, y: 0, duration: 0.45, ease: "back.out(1.6)" }, t); }
// text blur-in (heavier blur than rise)
function blurin(sel, t) { tl.fromTo(sel, { opacity: 0, y: 18, filter: "blur(12px)" }, { opacity: 1, y: 0, filter: "blur(0px)", duration: 0.55, ease: E }, t); }
// strike-through: red bar scales in left to right while the word dims
function strike(bar, word, t) { tl.fromTo(bar, { scaleX: 0 }, { scaleX: 1, duration: 0.3, ease: "power2.out" }, t); if (word) tl.to(word, { opacity: 0.4, duration: 0.3 }, t); }
// draw an SVG stroke (element needs pathLength=1)
function stroke(sel, t, dur, ease) { tl.fromTo(sel, { strokeDasharray: 1, strokeDashoffset: 1 }, { strokeDashoffset: 0, duration: dur, ease: ease || "power2.inOut" }, t); }
// terminal typing: reveals text one character at a time
function typeline(sel, t, dur, text) {
  const el = document.querySelector(sel), o = { p: 0 };
  el.textContent = "";
  tl.fromTo(o, { p: 0 }, { p: 1, duration: dur, ease: "none", onUpdate() { el.textContent = text.slice(0, Math.round(text.length * o.p)); } }, t);
}
// slider: moves the marker elements by dx while the number counts v0 -> v1
function slide(sels, numSel, t, dur, dx, v0, v1, dec, pre, suf) {
  const el = document.querySelector(numSel), o = { v: v0 };
  const fmt = (v) => pre + v.toFixed(dec) + suf;
  el.textContent = fmt(v0);
  tl.to(sels, { x: dx, duration: dur, ease: "power2.inOut" }, t);
  tl.fromTo(o, { v: v0 }, { v: v1, duration: dur, ease: "power2.inOut", onUpdate() { el.textContent = fmt(o.v); } }, t);
}
