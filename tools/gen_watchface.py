#!/usr/bin/env python3
"""
Radix Watch Face generator -- the unified numeral-base family app.

One layout spec -> two outputs (same convention as the sibling projects):
  * app/src/main/res/raw/watchface.xml   Wear OS Watch Face Format (WFF), v4
  * preview.html                          live browser preview, no build needed

First complete face: Quinary (base 5), ported from QuinaryWatchFace, now
wired to the new palette system rather than a single fixed Okabe-Ito theme.
Settings menu order (Paul's spec, 2026-09-24): PALETTE first, then BASE,
then theme/labels. `<UserConfigurations>` declares them in exactly that
order (declaration order = on-device editor order, independent of how the
Scene structurally nests them for rendering).

Structural nesting in <Scene> (a separate concern from the above):
  BooleanConfiguration id="theme"    -- outer, background fill ONLY
  ListConfiguration id="base"        -- one ListOption per numeral base
    -> ListConfiguration id="palette"  (nested, 18 options, this base's
       digit-group colors baked in per option -- see tools/palettes.py)
    -> BooleanConfiguration id="labels" (nested SIBLING of palette, not
       nested inside it -- label text/position depends on base, not on
       which colors are chosen, so keeping it a sibling avoids a 3rd level
       of nesting)
  ComplicationSlot x3 -- Scene-level, added LAST (Quinary's paint-order
    lesson: a background declared after a ComplicationSlot silently paints
    over it), fixed neutral tint (COMPLICATION_TINT -- a ListConfiguration's
    chosen value is a string id, not a resolvable color, so complications
    can't reference the palette directly; same simplification Quinary
    already uses for theme).

Outline dash color and label/cheat-mode text color are fixed neutral grays
rather than theme-dependent, for the same cross-branch-reference reason
complications use a fixed tint -- and this isn't even a new simplification,
Quinary's own THEMES dict already used the identical #FF808080 label color
in both dark and light themes.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wff_common import (
    CANVAS, C, WIDGET_MARGIN_X, WIDGET_W,
    build_heart_icon, wff_complication_date, wff_complication_heart,
    wff_complication_weather, JS_VALUE_FN,
)
from palettes import PALETTE_OPTIONS, palette_for, ANCHOR_COLORS

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "app" / "src" / "main" / "res" / "raw" / "watchface.xml"
PREVIEW = ROOT / "preview.html"
HEART_ICON = ROOT / "app" / "src" / "main" / "res" / "drawable" / "heart_icon.png"
PREVIEW_IMG = ROOT / "app" / "src" / "main" / "res" / "drawable" / "preview.png"

RADIUS = CANVAS / 2
LABEL_COLOR = "#FF808080"          # fixed, theme-independent (see module docstring)
OUTLINE_COLOR = "#80808080"        # fixed, semi-transparent mid-gray -- readable on
                                    # both dark and light backgrounds without needing
                                    # per-theme branching
BG_DARK, BG_LIGHT = "#FF111111", "#FFFFFFFF"

# ---- Quinary (base 5) geometry -- ported verbatim from QuinaryWatchFace ----
QUAD = 72
SUB_GAP = 0
HOUR_RADIUS = 8
MINUTE_RADIUS = 24
QUAD_PITCH = 88
ROW_Y = {0: 162, 1: 249, 2: 336}
RIGHT_EDGE_X = 313
HOUR_H = 72
HOUR_GAP = 24
HOUR_TOTAL_W = 2 * QUAD_PITCH + QUAD
HOUR_W = (HOUR_TOTAL_W - HOUR_GAP) // 2
LABEL_GAP = 10
LABEL_W, LABEL_H = 36, 36
ROW_LEFT_EDGE_X = RIGHT_EDGE_X + QUAD // 2 - HOUR_TOTAL_W
LABEL_X = ROW_LEFT_EDGE_X - LABEL_GAP - LABEL_W // 2
ROW_RIGHT_EDGE_X = RIGHT_EDGE_X + QUAD // 2
DECIMAL_GAP = 10
DECIMAL_W, DECIMAL_H = 44, 36
DECIMAL_X = ROW_RIGHT_EDGE_X + DECIMAL_GAP + DECIMAL_W // 2

POSITIONS = ["TR", "TL", "BL", "BR"]
POS_SIGN = {"TR": (+1, -1), "TL": (-1, -1), "BL": (-1, +1), "BR": (+1, +1)}
POS_ANGLES = {"TR": (0, 90), "BR": (90, 180), "BL": (180, 270), "TL": (270, 360)}


def places_needed(max_value: int) -> int:
    n = 1
    while 5 ** n <= max_value:
        n += 1
    return n


def quad_digit_expr(value_expr: str, place: int) -> str:
    return f"round(floor(({value_expr}) / {5 ** place}) % 5)"


def hour_layout():
    cy = ROW_Y[0]
    total_w = 2 * HOUR_W + HOUR_GAP
    left_x = C - total_w / 2 + HOUR_W / 2
    right_x = C + total_w / 2 - HOUR_W / 2
    for col, cx in enumerate((left_x, right_x)):
        place = 1 - col
        yield dict(x=cx, y=cy, w=HOUR_W, h=HOUR_H, shape="bar", radius=HOUR_RADIUS,
                   place=place, expr="[HOUR_0_23]",
                   label="H" if col == 0 else None, label_x=LABEL_X, label_y=cy)


def quad_layout():
    specs = [(1, "M", "[MINUTE]", 59, "rounded"), (2, "S", "[SECOND]", 59, "pie")]
    for row_i, label, expr, max_value, shape in specs:
        n = places_needed(max_value)
        cy = ROW_Y[row_i]
        radius = MINUTE_RADIUS if shape == "rounded" else 0
        for col in range(n):
            place = n - 1 - col
            cx = RIGHT_EDGE_X - place * QUAD_PITCH
            yield dict(x=cx, y=cy, w=QUAD, h=QUAD, shape=shape, radius=radius,
                       place=place, expr=expr,
                       label=label if col == 0 else None,
                       label_x=LABEL_X, label_y=cy)


def full_layout():
    return list(hour_layout()) + list(quad_layout())


DECIMAL_ROWS = [("[HOUR_0_23]", ROW_Y[0]), ("[MINUTE]", ROW_Y[1]), ("[SECOND]", ROW_Y[2])]


def wff_quad_outlines(layout):
    out = []
    for c in layout:
        x, y = round(c["x"] - c["w"] / 2), round(c["y"] - c["h"] / 2)
        stroke = f'<Stroke color="{OUTLINE_COLOR}" thickness="1.5" dashIntervals="3 5" cap="ROUND"/>'
        if c["shape"] == "pie":
            shape_el = f'<Ellipse x="0" y="0" width="{c["w"]}" height="{c["h"]}">{stroke}</Ellipse>'
        elif c["radius"] > 0:
            shape_el = (f'<RoundRectangle x="0" y="0" width="{c["w"]}" height="{c["h"]}" '
                        f'cornerRadiusX="{c["radius"]}" cornerRadiusY="{c["radius"]}">{stroke}</RoundRectangle>')
        else:
            shape_el = f'<Rectangle x="0" y="0" width="{c["w"]}" height="{c["h"]}">{stroke}</Rectangle>'
        out.append(f'      <PartDraw x="{x}" y="{y}" width="{c["w"]}" height="{c["h"]}">\n        {shape_el}\n      </PartDraw>')
    return "\n".join(out)


def wff_quads(layout, colors):
    out = []
    for c in layout:
        digit_expr = quad_digit_expr(c["expr"], c["place"])
        w, h = c["w"], c["h"]
        if c["shape"] == "pie":
            r = w / 2
            bx, by = round(c["x"] - w / 2), round(c["y"] - h / 2)
            for k, pos in enumerate(POSITIONS):
                start, end = POS_ANGLES[pos]
                name = f"q{c['place']}_{round(c['x'])}_{round(c['y'])}_{k}"
                out.append(
                    f'      <Condition>\n'
                    f'        <Expressions>\n'
                    f'          <Expression name="{name}"><![CDATA[(({digit_expr}) > {k})]]></Expression>\n'
                    f'        </Expressions>\n'
                    f'        <Compare expression="{name}">\n'
                    f'          <PartDraw x="{bx}" y="{by}" width="{w}" height="{h}">\n'
                    f'            <Arc centerX="{w / 2}" centerY="{h / 2}" width="{r}" height="{r}" '
                    f'startAngle="{start}" endAngle="{end}" direction="CLOCKWISE">\n'
                    f'              <WeightedStroke colors="{colors[k]}" thickness="{r}" cap="BUTT"/>\n'
                    f'            </Arc>\n'
                    f'          </PartDraw>\n'
                    f'        </Compare>\n'
                    f'      </Condition>')
            continue
        cell_w, cell_h = round((w - SUB_GAP) / 2), round((h - SUB_GAP) / 2)
        for k, pos in enumerate(POSITIONS):
            sx, sy = POS_SIGN[pos]
            off_x = sx * (cell_w / 2 + SUB_GAP / 2)
            off_y = sy * (cell_h / 2 + SUB_GAP / 2)
            bx = round(c["x"] + off_x - cell_w / 2)
            by = round(c["y"] + off_y - cell_h / 2)
            name = f"q{c['place']}_{round(c['x'])}_{round(c['y'])}_{k}"
            color = colors[k]
            if c["radius"] > 0:
                r = c["radius"]
                corner_xy = {"TL": (0, 0), "TR": (cell_w - r, 0), "BL": (0, cell_h - r), "BR": (cell_w - r, cell_h - r)}
                squares = "".join(
                    f'<Rectangle x="{cx}" y="{cy}" width="{r}" height="{r}"><Fill color="{color}"/></Rectangle>'
                    for corner, (cx, cy) in corner_xy.items() if corner != pos)
                shape_el = (f'<RoundRectangle x="0" y="0" width="{cell_w}" height="{cell_h}" '
                            f'cornerRadiusX="{r}" cornerRadiusY="{r}"><Fill color="{color}"/></RoundRectangle>{squares}')
            else:
                shape_el = f'<Rectangle x="0" y="0" width="{cell_w}" height="{cell_h}"><Fill color="{color}"/></Rectangle>'
            out.append(
                f'      <Condition>\n'
                f'        <Expressions>\n'
                f'          <Expression name="{name}"><![CDATA[(({digit_expr}) > {k})]]></Expression>\n'
                f'        </Expressions>\n'
                f'        <Compare expression="{name}">\n'
                f'          <PartDraw x="{bx}" y="{by}" width="{cell_w}" height="{cell_h}">\n'
                f'            {shape_el}\n'
                f'          </PartDraw>\n'
                f'        </Compare>\n'
                f'      </Condition>')
    return "\n".join(out)


def wff_labels(layout):
    out = []
    for c in layout:
        if not c["label"]:
            continue
        x, y = round(c["label_x"] - LABEL_W / 2), round(c["label_y"] - LABEL_H / 2)
        out.append(
            f'        <PartText x="{x}" y="{y}" width="{LABEL_W}" height="{LABEL_H}">\n'
            f'          <Text align="CENTER"><Font family="SYNC_TO_DEVICE" size="26" '
            f'weight="NORMAL" color="{LABEL_COLOR}">{c["label"].upper()}</Font></Text>\n'
            f'        </PartText>')
    return "\n".join(out)


def wff_decimal_readout():
    out = []
    for expr, cy in DECIMAL_ROWS:
        x, y = round(DECIMAL_X - DECIMAL_W / 2), round(cy - DECIMAL_H / 2)
        out.append(
            f'        <PartText x="{x}" y="{y}" width="{DECIMAL_W}" height="{DECIMAL_H}">\n'
            f'          <Text align="CENTER"><Font family="SYNC_TO_DEVICE" size="26" '
            f'weight="NORMAL" color="{LABEL_COLOR}">\n'
            f'              <Template>%02d<Parameter expression="{expr}"/></Template>\n'
            f'          </Font></Text>\n'
            f'        </PartText>')
    return "\n".join(out)


def quinary_palette_list_option(option_id: str, layout) -> str:
    colors = palette_for(option_id, 4)
    return (f'        <ListOption id="{option_id}">\n'
            f'          <Group name="palette_{option_id}" x="0" y="0" width="{CANVAS}" height="{CANVAS}">\n'
            f'{wff_quads(layout, colors)}\n'
            f'          </Group>\n'
            f'        </ListOption>')


def build_base_quinary() -> str:
    layout = full_layout()
    palette_options = "\n".join(
        quinary_palette_list_option(opt_id, layout) for opt_id, _res, _anchor in PALETTE_OPTIONS)
    # ListOption's schema only permits ONE direct child (confirmed the hard
    # way: validator rejected 3 siblings directly under ListOption) -- same
    # constraint BooleanOption already has, which is why every existing
    # BooleanOption in the sibling projects wraps its content in exactly one
    # Group. Do the same here: one Group holding outlines + palette + labels.
    return f"""    <ListOption id="quinary">
      <Group name="quinary" x="0" y="0" width="{CANVAS}" height="{CANVAS}">
        <Group name="quinary_outlines" x="0" y="0" width="{CANVAS}" height="{CANVAS}">
{wff_quad_outlines(layout)}
        </Group>
        <ListConfiguration id="palette">
{palette_options}
        </ListConfiguration>
        <BooleanConfiguration id="labels">
          <BooleanOption id="TRUE">
            <Group name="quinary_labels" x="0" y="0" width="{CANVAS}" height="{CANVAS}">
{wff_labels(layout)}
{wff_decimal_readout()}
            </Group>
          </BooleanOption>
        </BooleanConfiguration>
      </Group>
    </ListOption>"""


# ======================================================================
# WFF  (res/raw/watchface.xml)
# ======================================================================
def build_user_configurations() -> str:
    # Declaration order = on-device editor order: palette, then base, then
    # theme/labels (Paul's spec, 2026-09-24).
    palette_list_options = "\n".join(
        f'      <ListOption id="{opt_id}" displayName="{res_name}"/>'
        for opt_id, res_name, _anchor in PALETTE_OPTIONS)
    return f"""    <ListConfiguration id="palette" displayName="cfg_palette" defaultValue="colorblind">
{palette_list_options}
    </ListConfiguration>
    <ListConfiguration id="base" displayName="cfg_base" defaultValue="quinary">
      <ListOption id="quinary" displayName="opt_quinary"/>
    </ListConfiguration>
    <BooleanConfiguration id="theme" displayName="cfg_theme" defaultValue="FALSE"/>
    <BooleanConfiguration id="labels" displayName="cfg_labels" defaultValue="TRUE"/>"""


def build_wff() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!-- GENERATED by tools/gen_watchface.py - do not hand-edit. -->
<WatchFace width="{CANVAS}" height="{CANVAS}" clipShape="CIRCLE">
  <Metadata key="CLOCK_TYPE" value="DIGITAL"/>
  <Metadata key="PREVIEW_TIME" value="10:08:32"/>

  <UserConfigurations>
{build_user_configurations()}
  </UserConfigurations>

  <Scene>
    <!-- theme controls ONLY the background fill; digit-group colors come
         entirely from the palette selection now, independent of theme. -->
    <BooleanConfiguration id="theme">
      <BooleanOption id="FALSE">
        <PartDraw x="0" y="0" width="{CANVAS}" height="{CANVAS}">
          <Rectangle x="0" y="0" width="{CANVAS}" height="{CANVAS}"><Fill color="{BG_DARK}"/></Rectangle>
        </PartDraw>
      </BooleanOption>
      <BooleanOption id="TRUE">
        <PartDraw x="0" y="0" width="{CANVAS}" height="{CANVAS}">
          <Rectangle x="0" y="0" width="{CANVAS}" height="{CANVAS}"><Fill color="{BG_LIGHT}"/></Rectangle>
        </PartDraw>
      </BooleanOption>
    </BooleanConfiguration>

    <ListConfiguration id="base">
{build_base_quinary()}
    </ListConfiguration>

    <!-- complications: direct Scene children, declared AFTER the theme/base
         blocks above (Quinary's document-order lesson: a background drawn
         after a ComplicationSlot silently paints over it). -->
{wff_complication_date()}
{wff_complication_heart(WIDGET_MARGIN_X)}
{wff_complication_weather(CANVAS - WIDGET_MARGIN_X - WIDGET_W)}
  </Scene>
</WatchFace>
"""


# ======================================================================
# preview.html  (browser, live clock, no build)
# ======================================================================
_HTML_TMPL = r"""<!doctype html>
<meta charset="utf-8">
<title>Radix Watch Face - preview</title>
<style>
  body { background:#111; color:#ccc; font:14px system-ui; text-align:center; margin:0; padding:24px; }
  svg  { border-radius:50%; box-shadow:0 0 40px #0008; }
  label { margin:0 10px; }
  .wrap { display:inline-block; }
</style>
<div class="wrap">
  <h2>Radix Watch Face</h2>
  <svg id="face" width="360" height="360" viewBox="0 0 __CANVAS__ __CANVAS__"></svg>
  <div style="margin-top:14px">
    <label>palette <select id="palette"></select></label>
    <label>base <select id="base"><option value="quinary">Quinary</option></select></label>
    <label><input type="checkbox" id="theme"> light theme</label>
    <label><input type="checkbox" id="labels" checked> labels</label>
  </div>
  <p id="readout" style="color:#666"></p>
</div>
<script>
const SUB_GAP = __SUB_GAP__, LABEL_W = __LABEL_W__, LABEL_H = __LABEL_H__;
const POS_SIGN = {TR:[1,-1], TL:[-1,-1], BL:[-1,1], BR:[1,1]};
const POS_ANGLES = {TR:[0,90], BR:[90,180], BL:[180,270], TL:[270,360]};
const POSITIONS = ["TR","TL","BL","BR"];
const LAYOUT = __LAYOUT_JS__;
const DECIMAL_X = __DECIMAL_X__;
const DECIMAL_ROWS = __DECIMAL_ROWS_JS__;
const PALETTES = __PALETTES_JS__;     // { optionId: {label, colors:[4]} }
const OUTLINE = "__OUTLINE__", LABEL_COLOR = "__LABEL_COLOR__";
const BG = {dark: "__BG_DARK__", light: "__BG_LIGHT__"};
const svg = document.getElementById("face");
const paletteSel = document.getElementById("palette");
Object.entries(PALETTES).forEach(([id, p]) => {
  const el = document.createElement("option"); el.value = id; el.textContent = p.label;
  if (id === "colorblind") el.selected = true;
  paletteSel.appendChild(el);
});

__JS_VALUE_FN__
function quinaryDigit(src, place, now) { return Math.round(Math.floor(value(src, now) / (5 ** place)) % 5); }
function polar(cx, cy, r, deg) { const rad = deg * Math.PI / 180; return [cx + r * Math.sin(rad), cy - r * Math.cos(rad)]; }
function wedgePath(cx, cy, r, a0, a1) {
  const [x0, y0] = polar(cx, cy, r, a0), [x1, y1] = polar(cx, cy, r, a1);
  return `M ${cx} ${cy} L ${x0} ${y0} A ${r} ${r} 0 0 1 ${x1} ${y1} Z`;
}
function outlineShape(c) {
  const stroke = `fill="none" stroke="${OUTLINE}" stroke-width="1.5" stroke-dasharray="3 5" stroke-linecap="round"`;
  if (c.shape === "pie") return `<circle cx="${c.x}" cy="${c.y}" r="${c.w / 2}" ${stroke}/>`;
  const x = c.x - c.w / 2, y = c.y - c.h / 2;
  if (c.radius > 0) return `<rect x="${x}" y="${y}" width="${c.w}" height="${c.h}" rx="${c.radius}" ry="${c.radius}" ${stroke}/>`;
  return `<rect x="${x}" y="${y}" width="${c.w}" height="${c.h}" ${stroke}/>`;
}
function draw() {
  const now = new Date();
  const light = document.getElementById("theme").checked;
  const showLabels = document.getElementById("labels").checked;
  const colors = PALETTES[paletteSel.value].colors;
  let s = `<rect x="0" y="0" width="__CANVAS__" height="__CANVAS__" fill="${BG[light ? "light" : "dark"]}"/>`;
  for (const c of LAYOUT) {
    s += outlineShape(c);
    const digit = quinaryDigit(c.src, c.place, now);
    if (c.shape === "pie") {
      const r = c.w / 2;
      POSITIONS.forEach((pos, k) => {
        if (digit <= k) return;
        const [a0, a1] = POS_ANGLES[pos];
        s += `<path d="${wedgePath(c.x, c.y, r, a0, a1)}" fill="${colors[k]}"/>`;
      });
    } else {
      const cellW = (c.w - SUB_GAP) / 2, cellH = (c.h - SUB_GAP) / 2;
      POSITIONS.forEach((pos, k) => {
        if (digit <= k) return;
        const [sx, sy] = POS_SIGN[pos];
        const offX = sx * (cellW / 2 + SUB_GAP / 2), offY = sy * (cellH / 2 + SUB_GAP / 2);
        const bx = c.x + offX - cellW / 2, by = c.y + offY - cellH / 2;
        s += `<rect x="${bx}" y="${by}" width="${cellW}" height="${cellH}" rx="${c.radius}" ry="${c.radius}" fill="${colors[k]}"/>`;
      });
    }
    if (showLabels && c.label) {
      s += `<text x="${c.label_x}" y="${c.label_y + 8}" fill="${LABEL_COLOR}" font-size="26" text-anchor="middle" font-family="system-ui">${c.label.toUpperCase()}</text>`;
    }
  }
  if (showLabels) {
    for (const [src, cy] of DECIMAL_ROWS) {
      const v = String(Math.round(value(src, now))).padStart(2, "0");
      s += `<text x="${DECIMAL_X}" y="${cy + 8}" fill="${LABEL_COLOR}" font-size="26" text-anchor="middle" font-family="system-ui">${v}</text>`;
    }
  }
  svg.innerHTML = s;
  document.getElementById("readout").textContent = now.toTimeString().slice(0, 8);
}
setInterval(draw, 250); draw();
</script>
"""


def build_html() -> str:
    def js_layout(layout):
        rows = []
        for c in layout:
            lab = f'"{c["label"]}"' if c["label"] else "null"
            rows.append(
                '{x:%.1f,y:%.1f,w:%.1f,h:%.1f,shape:"%s",radius:%d,place:%d,src:%s,label:%s,label_x:%s,label_y:%s}' % (
                    c["x"], c["y"], c["w"], c["h"], c["shape"], c["radius"], c["place"],
                    repr(c["expr"]).replace("'", '"'), lab, c["label_x"], c["label_y"]))
        return "[" + ",".join(rows) + "]"

    def css(argb):
        return "#" + argb[-6:]

    palettes_js = "{" + ",".join(
        '"%s":{label:"%s",colors:[%s]}' % (
            opt_id, opt_id.capitalize(),
            ",".join(f'"{css(c)}"' for c in palette_for(opt_id, 4)))
        for opt_id, _res, _anchor in PALETTE_OPTIONS) + "}"

    repl = {
        "__CANVAS__": str(CANVAS),
        "__SUB_GAP__": str(SUB_GAP),
        "__LABEL_W__": str(LABEL_W),
        "__LABEL_H__": str(LABEL_H),
        "__LAYOUT_JS__": js_layout(full_layout()),
        "__DECIMAL_X__": str(DECIMAL_X),
        "__DECIMAL_ROWS_JS__": "[" + ",".join(f'["{expr}",{cy}]' for expr, cy in DECIMAL_ROWS) + "]",
        "__PALETTES_JS__": palettes_js,
        "__OUTLINE__": css(OUTLINE_COLOR),
        "__LABEL_COLOR__": css(LABEL_COLOR),
        "__BG_DARK__": css(BG_DARK),
        "__BG_LIGHT__": css(BG_LIGHT),
        "__JS_VALUE_FN__": JS_VALUE_FN,
    }
    out = _HTML_TMPL
    for k, v in repl.items():
        out = out.replace(k, v)
    return out


def _rgb(argb: str):
    return tuple(int(argb[i:i + 2], 16) for i in (3, 5, 7))


def build_preview_image():
    """Gallery/picker thumbnail -- required as its own file
    (watch_face_info.xml's @drawable/preview); its absence silently breaks
    the on-watch gallery listing, the exact bug that cost real debugging
    time on BinaryWatchFace originally. Colorblind palette, a full-ish time
    for a lively icon, same simplified (non-fused) rendering QuinaryWatchFace
    already used for its own thumbnail."""
    from PIL import Image, ImageDraw
    palette = [c for c in palette_for("colorblind", 4)]
    h, m, s = 23, 49, 3   # "a great time (very full)", per Quinary's own precedent
    img = Image.new("RGB", (CANVAS, CANVAS), _rgb(BG_DARK))
    d = ImageDraw.Draw(img)
    values = {"[HOUR_0_23]": h, "[MINUTE]": m, "[SECOND]": s}
    for c in full_layout():
        digit = (values[c["expr"]] // 5 ** c["place"]) % 5
        if c["shape"] == "pie":
            r = c["w"] / 2
            box = [c["x"] - r, c["y"] - r, c["x"] + r, c["y"] + r]
            for k, pos in enumerate(POSITIONS):
                if digit <= k:
                    continue
                start, end = POS_ANGLES[pos]
                pil_start, pil_end = (start - 90) % 360, (end - 90) % 360
                if pil_end <= pil_start:
                    pil_end += 360
                d.pieslice(box, pil_start, pil_end, fill=_rgb(palette[k]))
        else:
            cell_w, cell_h = c["w"] / 2, c["h"] / 2
            radius = min(c["radius"], int(min(cell_w, cell_h) // 2))
            for k, pos in enumerate(POSITIONS):
                if digit <= k:
                    continue
                sx, sy = POS_SIGN[pos]
                cx, cy = c["x"] + sx * cell_w / 2, c["y"] + sy * cell_h / 2
                box = [cx - cell_w / 2, cy - cell_h / 2, cx + cell_w / 2, cy + cell_h / 2]
                if radius > 0:
                    d.rounded_rectangle(box, radius=radius, fill=_rgb(palette[k]))
                else:
                    d.rectangle(box, fill=_rgb(palette[k]))
        if c["label"]:
            d.text((c["label_x"], c["label_y"]), c["label"], fill=_rgb(LABEL_COLOR), anchor="mm")
    PREVIEW_IMG.parent.mkdir(parents=True, exist_ok=True)
    img.save(PREVIEW_IMG)


def main():
    RAW.parent.mkdir(parents=True, exist_ok=True)
    HEART_ICON.parent.mkdir(parents=True, exist_ok=True)
    build_heart_icon(HEART_ICON)
    build_preview_image()
    RAW.write_text(build_wff(), encoding="utf-8")
    PREVIEW.write_text(build_html(), encoding="utf-8")
    print(f"wrote {HEART_ICON.relative_to(ROOT)}")
    print(f"wrote {PREVIEW_IMG.relative_to(ROOT)}")
    print(f"wrote {RAW.relative_to(ROOT)}  ({len(RAW.read_text())} bytes, {len(PALETTE_OPTIONS)} palettes)")
    print(f"wrote {PREVIEW.relative_to(ROOT)}   (open in a browser)")


if __name__ == "__main__":
    main()
