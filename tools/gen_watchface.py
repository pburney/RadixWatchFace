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
  BooleanConfiguration id="theme"    -- OUTER (2026-09-24: base moved inside
    this, see below), background fill first per branch
    -> ListConfiguration id="base"     -- one ListOption per numeral base,
       DUPLICATED per theme branch, so outline/off-LED colors can be real
       per-branch literals rather than a [CONFIGURATION.theme] read from
       outside its own structural branch (the exact unverified cross-branch
       pattern that silently broke Quinary's complication tinting once
       already -- not gambling on that again for a cosmetic color choice)
      -> ListConfiguration id="palette"  (nested, 18 options, this base's
         digit-group colors baked in per option -- see tools/palettes.py)
      -> BooleanConfiguration id="labels" (nested SIBLING of palette, not
         nested inside it -- label text/position depends on base, not on
         which colors are chosen, so keeping it a sibling avoids a 4th
         level of nesting)
  ComplicationSlot x3 -- Scene-level, added LAST (Quinary's paint-order
    lesson: a background declared after a ComplicationSlot silently paints
    over it), fixed neutral tint (COMPLICATION_TINT -- a ListConfiguration's
    chosen value is a string id, not a resolvable color, so complications
    can't reference the palette directly; same simplification Quinary
    already uses for theme).

Label/cheat-mode text color is still one fixed neutral gray regardless of
theme -- not a simplification made under duress, Quinary's own THEMES dict
already used the identical #FF808080 in both dark and light themes, so
there was never a real reason to duplicate it.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wff_common import (
    CANVAS, C, WIDGET_MARGIN_X, WIDGET_W,
    build_heart_icon, wff_complication_date, wff_complication_heart,
    wff_complication_weather, JS_VALUE_FN,
)
from palettes import (
    PALETTE_OPTIONS, palette_for, ANCHOR_COLORS, OKABE_ITO,
    ROYGBIV_START_DEG, ROYGBIV_END_DEG, ensure_contrast,
)

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "app" / "src" / "main" / "res" / "raw" / "watchface.xml"
PREVIEW = ROOT / "preview.html"
HEART_ICON = ROOT / "app" / "src" / "main" / "res" / "drawable" / "heart_icon.png"
PREVIEW_IMG = ROOT / "app" / "src" / "main" / "res" / "drawable" / "preview.png"

RADIUS = CANVAS / 2
LABEL_COLOR = "#FF808080"          # fixed, theme-independent -- Quinary's own THEMES
                                    # dict already used this identical gray in both
                                    # dark and light, so no duplication needed here
BG_DARK, BG_LIGHT = "#FF111111", "#FFFFFFFF"

# 2026-09-24: outline and off-LED colors DO need to be theme-specific (Paul: light
# mode's solid dark dim-LEDs read as jarring against a white background, and its
# digit-group outlines were washed out compared to dark mode's). Rather than have
# these read [CONFIGURATION.theme] from outside its own structural branch -- the
# exact unverified cross-branch pattern that silently broke Quinary's complication
# tinting once already -- `base` is nested INSIDE each theme BooleanOption branch
# (see build_wff()), so these colors are simple per-branch literals, not a runtime
# config read at all. Matches original QuinaryWatchFace's own per-theme values.
OUTLINE_DARK, OUTLINE_LIGHT = "#99FFFFFF", "#99111111"

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


def wff_quad_outlines(layout, outline_color):
    out = []
    for c in layout:
        x, y = round(c["x"] - c["w"] / 2), round(c["y"] - c["h"] / 2)
        stroke = f'<Stroke color="{outline_color}" thickness="1.5" dashIntervals="3 5" cap="ROUND"/>'
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


# ---- Hexagon (base 7) -- confirmed via this session's geometry spike that
# Quinary's wedge-split-circle technique (Arc + WeightedStroke) generalizes
# to any position count with zero special-casing except n=1 (see the n=1
# degenerate-arc fix in the spike notes / RADIX ticket). Reuses Quinary's
# exact layout positions (full_layout()): base-5 and base-7 both happen to
# need 2 places for H (0-23) and 3 places for M/S (0-59) -- 5^1=5<=23<25=5^2
# and 7^1=7<=23<49=7^2 give the same place count, likewise 5^2=25<=59<125
# and 7^2=49<=59<343 -- so the SAME x/y positions work, only the digit math
# (base 7 instead of 5) and the rendering (6-wedge circle instead of a
# 4-cell quad with per-row bar/rounded/pie shapes) differ. There's no
# 2x2-grid equivalent for 6 positions, so every row renders as a wedge
# circle -- no per-row shape variety the way Quinary has H/M/S look
# different at a glance; row identity here is label + position only, same
# as Binary already relies on.
HEX_POSITIONS = ["P0", "P1", "P2", "P3", "P4", "P5"]
HEX_ANGLES = {f"P{i}": (i * 60, (i + 1) * 60) for i in range(6)}


def hex_digit_expr(value_expr: str, place: int) -> str:
    return f"round(floor(({value_expr}) / {7 ** place}) % 7)"


def wff_hex_outlines(layout, outline_color):
    out = []
    for c in layout:
        r = c["w"] / 2
        x, y = round(c["x"] - r), round(c["y"] - r)
        out.append(
            f'      <PartDraw x="{x}" y="{y}" width="{round(r * 2)}" height="{round(r * 2)}">\n'
            f'        <Ellipse x="0" y="0" width="{round(r * 2)}" height="{round(r * 2)}">'
            f'<Stroke color="{outline_color}" thickness="1.5" dashIntervals="3 5" cap="ROUND"/></Ellipse>\n'
            f'      </PartDraw>')
    return "\n".join(out)


def wff_hex_groups(layout, colors):
    out = []
    for c in layout:
        digit_expr = hex_digit_expr(c["expr"], c["place"])
        r = c["w"] / 2
        bx, by = round(c["x"] - r), round(c["y"] - r)
        for k, pos in enumerate(HEX_POSITIONS):
            start, end = HEX_ANGLES[pos]
            name = f"h{c['place']}_{round(c['x'])}_{round(c['y'])}_{k}"
            out.append(
                f'      <Condition>\n'
                f'        <Expressions>\n'
                f'          <Expression name="{name}"><![CDATA[(({digit_expr}) > {k})]]></Expression>\n'
                f'        </Expressions>\n'
                f'        <Compare expression="{name}">\n'
                f'          <PartDraw x="{bx}" y="{by}" width="{round(r * 2)}" height="{round(r * 2)}">\n'
                f'            <Arc centerX="{r}" centerY="{r}" width="{r}" height="{r}" '
                f'startAngle="{start}" endAngle="{end}" direction="CLOCKWISE">\n'
                f'              <WeightedStroke colors="{colors[k]}" thickness="{r}" cap="BUTT"/>\n'
                f'            </Arc>\n'
                f'          </PartDraw>\n'
                f'        </Compare>\n'
                f'      </Condition>')
    return "\n".join(out)


def hexagon_palette_list_option(option_id: str, layout, theme: str) -> str:
    colors = palette_for(option_id, 6)
    return (f'        <ListOption id="{option_id}">\n'
            f'          <Group name="hex_palette_{option_id}_{theme}" x="0" y="0" width="{CANVAS}" height="{CANVAS}">\n'
            f'{wff_hex_groups(layout, colors)}\n'
            f'          </Group>\n'
            f'        </ListOption>')


def build_base_hexagon(theme: str, outline_color: str) -> str:
    layout = full_layout()   # same positions as Quinary -- see module note above
    palette_options = "\n".join(
        hexagon_palette_list_option(opt_id, layout, theme) for opt_id, _res, _anchor in PALETTE_OPTIONS)
    return f"""    <ListOption id="hexagon">
      <Group name="hexagon_{theme}" x="0" y="0" width="{CANVAS}" height="{CANVAS}">
        <Group name="hexagon_outlines_{theme}" x="0" y="0" width="{CANVAS}" height="{CANVAS}">
{wff_hex_outlines(layout, outline_color)}
        </Group>
        <ListConfiguration id="palette">
{palette_options}
        </ListConfiguration>
        <BooleanConfiguration id="labels">
          <BooleanOption id="TRUE">
            <Group name="hexagon_labels_{theme}" x="0" y="0" width="{CANVAS}" height="{CANVAS}">
{wff_labels(layout)}
{wff_decimal_readout()}
            </Group>
          </BooleanOption>
        </BooleanConfiguration>
      </Group>
    </ListOption>"""


def quinary_palette_list_option(option_id: str, layout, theme: str) -> str:
    colors = palette_for(option_id, 4)
    return (f'        <ListOption id="{option_id}">\n'
            f'          <Group name="palette_{option_id}_{theme}" x="0" y="0" width="{CANVAS}" height="{CANVAS}">\n'
            f'{wff_quads(layout, colors)}\n'
            f'          </Group>\n'
            f'        </ListOption>')


def build_base_quinary(theme: str, outline_color: str) -> str:
    layout = full_layout()
    palette_options = "\n".join(
        quinary_palette_list_option(opt_id, layout, theme) for opt_id, _res, _anchor in PALETTE_OPTIONS)
    # ListOption's schema only permits ONE direct child (confirmed the hard
    # way: validator rejected 3 siblings directly under ListOption) -- same
    # constraint BooleanOption already has, which is why every existing
    # BooleanOption in the sibling projects wraps its content in exactly one
    # Group. Do the same here: one Group holding outlines + palette + labels.
    return f"""    <ListOption id="quinary">
      <Group name="quinary_{theme}" x="0" y="0" width="{CANVAS}" height="{CANVAS}">
        <Group name="quinary_outlines_{theme}" x="0" y="0" width="{CANVAS}" height="{CANVAS}">
{wff_quad_outlines(layout, outline_color)}
        </Group>
        <ListConfiguration id="palette">
{palette_options}
        </ListConfiguration>
        <BooleanConfiguration id="labels">
          <BooleanOption id="TRUE">
            <Group name="quinary_labels_{theme}" x="0" y="0" width="{CANVAS}" height="{CANVAS}">
{wff_labels(layout)}
{wff_decimal_readout()}
            </Group>
          </BooleanOption>
        </BooleanConfiguration>
      </Group>
    </ListOption>"""


# ---- Binary (base 2) geometry -- ported from BinaryWatchFace, raw binary
# mode only (BCD mode stays a BinaryWatchFace-only feature for now; it's a
# secondary mode of base-2 itself, not another numeral base, so folding it
# in here would be scope creep on top of the base picker this app already
# adds). Binary keeps its classic "every lit LED is the same one color"
# look rather than adopting per-position palette colors like Quinary's
# quads -- it requests just ONE color from whichever palette is selected
# (palette_for(id, 1)), so it still participates in the same 18-option
# picker without breaking its own established visual identity. ----
LED_R = 15
GX, GY = 46, 52
OFF_DARK, OFF_LIGHT = "#FF1C1C1C", "#FFDEDEDE"
BINARY_ROWS = [("H", "[HOUR_0_23]", 6), ("M", "[MINUTE]", 6), ("S", "[SECOND]", 6)]


def bit_expr(value_expr: str, k: int) -> str:
    return f"round(floor(({value_expr}) / {1 << k}) % 2)"


def binary_layout():
    n = len(BINARY_ROWS)
    for r, (label, expr, nbits) in enumerate(BINARY_ROWS):
        cy = C + (r - (n - 1) / 2) * GY
        for col in range(nbits):
            k = nbits - 1 - col
            cx = C + (col - (nbits - 1) / 2) * GX
            yield dict(x=cx, y=cy, k=k, expr=expr,
                       label=label if col == 0 else None, label_x=cx - GX, label_y=cy)


def wff_binary_cells(layout, color, off_color):
    d, lit = [], []
    for c in layout:
        x, y = round(c["x"] - LED_R), round(c["y"] - LED_R)
        w = LED_R * 2
        d.append(
            f'      <PartDraw x="{x}" y="{y}" width="{w}" height="{w}">\n'
            f'        <Ellipse x="0" y="0" width="{w}" height="{w}"><Fill color="{off_color}"/></Ellipse>\n'
            f'      </PartDraw>')
        name = f'b{c["k"]}_{round(c["x"])}_{round(c["y"])}'
        lit.append(
            f'      <Condition>\n'
            f'        <Expressions>\n'
            f'          <Expression name="{name}">{bit_expr(c["expr"], c["k"])}</Expression>\n'
            f'        </Expressions>\n'
            f'        <Compare expression="{name}">\n'
            f'          <PartDraw x="{x}" y="{y}" width="{w}" height="{w}">\n'
            f'            <Ellipse x="0" y="0" width="{w}" height="{w}"><Fill color="{color}"/></Ellipse>\n'
            f'          </PartDraw>\n'
            f'        </Compare>\n'
            f'      </Condition>')
    return "\n".join(d + lit)


def wff_binary_labels(layout):
    out = []
    for c in layout:
        if not c["label"]:
            continue
        x, y = round(c["label_x"] - GX / 2), round(c["label_y"] - GY / 2)
        out.append(
            f'        <PartText x="{x}" y="{y}" width="{GX}" height="{GY}">\n'
            f'          <Text align="CENTER"><Font family="SYNC_TO_DEVICE" size="26" '
            f'weight="NORMAL" color="{LABEL_COLOR}">{c["label"].upper()}</Font></Text>\n'
            f'        </PartText>')
    return "\n".join(out)


BINARY_DECIMAL_W, BINARY_DECIMAL_H = 44, 36


def wff_binary_decimal_readout():
    n = len(BINARY_ROWS)
    exprs = {"H": "[HOUR_0_23]", "M": "[MINUTE]", "S": "[SECOND]"}
    out = []
    for r, (label, expr, nbits) in enumerate(BINARY_ROWS):
        cy = C + (r - (n - 1) / 2) * GY
        rightmost_cx = C + (nbits - 1) / 2 * GX
        dx = rightmost_cx + GX
        x, y = round(dx - BINARY_DECIMAL_W / 2), round(cy - BINARY_DECIMAL_H / 2)
        out.append(
            f'        <PartText x="{x}" y="{y}" width="{BINARY_DECIMAL_W}" height="{BINARY_DECIMAL_H}">\n'
            f'          <Text align="CENTER"><Font family="SYNC_TO_DEVICE" size="26" '
            f'weight="NORMAL" color="{LABEL_COLOR}">\n'
            f'              <Template>%02d<Parameter expression="{exprs[label]}"/></Template>\n'
            f'          </Font></Text>\n'
            f'        </PartText>')
    return "\n".join(out)


def binary_palette_list_option(option_id: str, layout, theme: str, off_color: str) -> str:
    color = ensure_contrast(palette_for(option_id, 1)[0], theme)
    return (f'        <ListOption id="{option_id}">\n'
            f'          <Group name="binary_palette_{option_id}_{theme}" x="0" y="0" width="{CANVAS}" height="{CANVAS}">\n'
            f'{wff_binary_cells(layout, color, off_color)}\n'
            f'          </Group>\n'
            f'        </ListOption>')


def build_base_binary(theme: str, off_color: str) -> str:
    layout = list(binary_layout())
    palette_options = "\n".join(
        binary_palette_list_option(opt_id, layout, theme, off_color) for opt_id, _res, _anchor in PALETTE_OPTIONS)
    return f"""    <ListOption id="binary">
      <Group name="binary_{theme}" x="0" y="0" width="{CANVAS}" height="{CANVAS}">
        <ListConfiguration id="palette">
{palette_options}
        </ListConfiguration>
        <BooleanConfiguration id="labels">
          <BooleanOption id="TRUE">
            <Group name="binary_labels_{theme}" x="0" y="0" width="{CANVAS}" height="{CANVAS}">
{wff_binary_labels(layout)}
{wff_binary_decimal_readout()}
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
      <ListOption id="binary" displayName="opt_binary"/>
      <ListOption id="hexagon" displayName="opt_hexagon"/>
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
    <!-- `base` is nested INSIDE each theme branch (not a separate sibling),
         specifically so outline/off-LED colors can be real per-branch
         literals instead of a [CONFIGURATION.theme] read from outside its
         own structural branch, the exact unverified cross-branch pattern
         that silently broke Quinary's complication tinting once already.
         Costs real file size (the whole base x palette tree is now
         duplicated once per theme) in exchange for not gambling on that
         again. Background fill still lives here too, first, per Quinary's
         document-order lesson (painted before the digit content). -->
    <BooleanConfiguration id="theme">
      <BooleanOption id="FALSE">
        <Group name="theme_dark" x="0" y="0" width="{CANVAS}" height="{CANVAS}">
          <PartDraw x="0" y="0" width="{CANVAS}" height="{CANVAS}">
            <Rectangle x="0" y="0" width="{CANVAS}" height="{CANVAS}"><Fill color="{BG_DARK}"/></Rectangle>
          </PartDraw>
          <ListConfiguration id="base">
{build_base_quinary("dark", OUTLINE_DARK)}
{build_base_binary("dark", OFF_DARK)}
{build_base_hexagon("dark", OUTLINE_DARK)}
          </ListConfiguration>
        </Group>
      </BooleanOption>
      <BooleanOption id="TRUE">
        <Group name="theme_light" x="0" y="0" width="{CANVAS}" height="{CANVAS}">
          <PartDraw x="0" y="0" width="{CANVAS}" height="{CANVAS}">
            <Rectangle x="0" y="0" width="{CANVAS}" height="{CANVAS}"><Fill color="{BG_LIGHT}"/></Rectangle>
          </PartDraw>
          <ListConfiguration id="base">
{build_base_quinary("light", OUTLINE_LIGHT)}
{build_base_binary("light", OFF_LIGHT)}
{build_base_hexagon("light", OUTLINE_LIGHT)}
          </ListConfiguration>
        </Group>
      </BooleanOption>
    </BooleanConfiguration>

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
    <label>base <select id="base">
      <option value="quinary">Quinary</option>
      <option value="binary">Binary</option>
      <option value="hexagon">Hexagon</option>
    </select></label>
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
const HEX_POSITIONS = ["P0","P1","P2","P3","P4","P5"];
const HEX_ANGLES = Object.fromEntries(HEX_POSITIONS.map((p, i) => [p, [i * 60, (i + 1) * 60]]));
const QUINARY_LAYOUT = __QUINARY_LAYOUT_JS__;
const DECIMAL_X = __DECIMAL_X__;
const DECIMAL_ROWS = __DECIMAL_ROWS_JS__;
const BINARY_LAYOUT = __BINARY_LAYOUT_JS__;
const BINARY_GX = __BINARY_GX__, BINARY_GY = __BINARY_GY__, LED_R = __LED_R__;
const OFF = {dark: "__OFF_DARK__", light: "__OFF_LIGHT__"};
const BINARY_DECIMAL_W = __BINARY_DECIMAL_W__;
const OUTLINE = {dark: "__OUTLINE_DARK__", light: "__OUTLINE_LIGHT__"};
const LABEL_COLOR = "__LABEL_COLOR__";
const BG = {dark: "__BG_DARK__", light: "__BG_LIGHT__"};
const svg = document.getElementById("face");
const paletteSel = document.getElementById("palette");
const baseSel = document.getElementById("base");

// ---- palette generation, ported verbatim from tools/palettes.py ----
const ANCHORS = __ANCHORS_JS__;
const OKABE_ITO = __OKABE_ITO_JS__;
const ROYGBIV_START_DEG = __ROYGBIV_START__, ROYGBIV_END_DEG = __ROYGBIV_END__;
function hexToHsl(hex) {
  let r = parseInt(hex.slice(1,3),16)/255, g = parseInt(hex.slice(3,5),16)/255, b = parseInt(hex.slice(5,7),16)/255;
  const max = Math.max(r,g,b), min = Math.min(r,g,b);
  let h, s, l = (max+min)/2;
  if (max === min) { h = s = 0; }
  else {
    const d = max - min;
    s = l > 0.5 ? d/(2-max-min) : d/(max+min);
    if (max === r) h = (g-b)/d + (g<b?6:0);
    else if (max === g) h = (b-r)/d + 2;
    else h = (r-g)/d + 4;
    h /= 6;
  }
  return [h, s, l];
}
function hslToHex(h, s, l) {
  function f(n) { const k=(n+h*12)%12; const a=s*Math.min(l,1-l); const c=l-a*Math.max(-1,Math.min(k-3,9-k,1)); return Math.round(255*c); }
  const r=f(0), g=f(8), b=f(4);
  return "#" + [r,g,b].map(v => v.toString(16).padStart(2,"0")).join("").toUpperCase();
}
function monochromePalette(anchorHex, n) {
  const [h,s] = hexToHsl(anchorHex);
  const lo = 0.28, hi = 0.82, out = [];
  for (let i = 0; i < n; i++) { const t = n>1 ? i/(n-1) : 0.5; out.push(hslToHex(h, s, lo+t*(hi-lo))); }
  return out;
}
function rainbowPalette(n) {
  const out = [];
  for (let i = 0; i < n; i++) {
    const t = n>1 ? i/(n-1) : 0.5;
    const hue = (ROYGBIV_START_DEG + t*(ROYGBIV_END_DEG-ROYGBIV_START_DEG)) / 360;
    out.push(hslToHex(hue, 0.85, 0.55));
  }
  return out;
}
function colorblindPalette(n) { return OKABE_ITO.slice(0, n); }
function paletteFor(id, n) {
  if (id === "rainbow") return rainbowPalette(n);
  if (id === "colorblind") return colorblindPalette(n);
  const anchor = ANCHORS.find(a => a[0] === id);
  return monochromePalette(anchor[2], n);
}
function ensureContrast(hex, theme) {
  // Mirrors palettes.py's ensure_contrast() -- single-color bases (Binary)
  // have no outline/neighboring color to fall back on, so a color too close
  // to the background is genuinely invisible, not just subtle.
  const [h, s, l0] = hexToHsl(hex);
  let l = l0;
  if (theme === "light" && l > 0.75) l = 0.35;
  else if (theme === "dark" && l < 0.20) l = 0.65;
  else return hex;
  return hslToHex(h, s, l);
}
const PALETTE_OPTIONS = [["rainbow","Rainbow"],["colorblind","Colorblind-safe"], ...ANCHORS.map(a => [a[0], a[1]+" shades"])];
PALETTE_OPTIONS.forEach(([id, label]) => {
  const el = document.createElement("option"); el.value = id; el.textContent = label;
  if (id === "colorblind") el.selected = true;
  paletteSel.appendChild(el);
});

__JS_VALUE_FN__
function quinaryDigit(src, place, now) { return Math.round(Math.floor(value(src, now) / (5 ** place)) % 5); }
function binaryBit(src, k, now) { return Math.round(Math.floor(value(src, now) / (2 ** k)) % 2); }
function hexDigit(src, place, now) { return Math.round(Math.floor(value(src, now) / (7 ** place)) % 7); }
function polar(cx, cy, r, deg) { const rad = deg * Math.PI / 180; return [cx + r * Math.sin(rad), cy - r * Math.cos(rad)]; }
function wedgePath(cx, cy, r, a0, a1) {
  const [x0, y0] = polar(cx, cy, r, a0), [x1, y1] = polar(cx, cy, r, a1);
  return `M ${cx} ${cy} L ${x0} ${y0} A ${r} ${r} 0 0 1 ${x1} ${y1} Z`;
}
function outlineShape(c, outline) {
  const stroke = `fill="none" stroke="${outline}" stroke-width="1.5" stroke-dasharray="3 5" stroke-linecap="round"`;
  if (c.shape === "pie") return `<circle cx="${c.x}" cy="${c.y}" r="${c.w / 2}" ${stroke}/>`;
  const x = c.x - c.w / 2, y = c.y - c.h / 2;
  if (c.radius > 0) return `<rect x="${x}" y="${y}" width="${c.w}" height="${c.h}" rx="${c.radius}" ry="${c.radius}" ${stroke}/>`;
  return `<rect x="${x}" y="${y}" width="${c.w}" height="${c.h}" ${stroke}/>`;
}

function drawQuinary(colors, outline, showLabels, now) {
  let s = "";
  for (const c of QUINARY_LAYOUT) {
    s += outlineShape(c, outline);
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
      const r = c.radius;
      // Mirrors the real WFF output's corner-squaring trick (RoundRectangle
      // only takes ONE uniform radius for all 4 corners -- there's no
      // per-corner control) -- round every corner, then paint same-color
      // squares over the 3 corners that face the digit group's own center,
      // leaving only the true OUTER corner rounded. That's what makes
      // adjacent lit cells fuse into one seamless rounded shape instead of
      // 4 separate pills.
      const CORNER_XY = {TL: [0, 0], TR: [cellW - r, 0], BL: [0, cellH - r], BR: [cellW - r, cellH - r]};
      POSITIONS.forEach((pos, k) => {
        if (digit <= k) return;
        const [sx, sy] = POS_SIGN[pos];
        const offX = sx * (cellW / 2 + SUB_GAP / 2), offY = sy * (cellH / 2 + SUB_GAP / 2);
        const bx = c.x + offX - cellW / 2, by = c.y + offY - cellH / 2;
        s += `<rect x="${bx}" y="${by}" width="${cellW}" height="${cellH}" rx="${r}" ry="${r}" fill="${colors[k]}"/>`;
        if (r > 0) {
          for (const [corner, [cx, cy]] of Object.entries(CORNER_XY)) {
            if (corner === pos) continue;
            s += `<rect x="${bx + cx}" y="${by + cy}" width="${r}" height="${r}" fill="${colors[k]}"/>`;
          }
        }
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
  return s;
}

function drawHexagon(colors, outline, showLabels, now) {
  // Reuses QUINARY_LAYOUT's x/y/place positions verbatim (base-5 and base-7
  // both need 2 places for H, 3 for M/S -- see the Python-side module note),
  // rendering every group as a 6-wedge circle instead of a 4-cell quad.
  let s = "";
  for (const c of QUINARY_LAYOUT) {
    const r = c.w / 2;
    s += `<circle cx="${c.x}" cy="${c.y}" r="${r}" fill="none" stroke="${outline}" stroke-width="1.5" stroke-dasharray="3 5" stroke-linecap="round"/>`;
    const digit = hexDigit(c.src, c.place, now);
    HEX_POSITIONS.forEach((pos, k) => {
      if (digit <= k) return;
      const [a0, a1] = HEX_ANGLES[pos];
      s += `<path d="${wedgePath(c.x, c.y, r, a0, a1)}" fill="${colors[k]}"/>`;
    });
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
  return s;
}

function drawBinary(color, offColor, showLabels, now) {
  let s = "";
  for (const c of BINARY_LAYOUT) {
    s += `<circle cx="${c.x}" cy="${c.y}" r="${LED_R}" fill="${offColor}"/>`;
    if (binaryBit(c.src, c.k, now)) {
      s += `<circle cx="${c.x}" cy="${c.y}" r="${LED_R}" fill="${color}"/>`;
    }
    if (showLabels && c.label) {
      s += `<text x="${c.x - BINARY_GX}" y="${c.y + 8}" fill="${LABEL_COLOR}" font-size="26" text-anchor="middle" font-family="system-ui">${c.label.toUpperCase()}</text>`;
    }
  }
  if (showLabels) {
    const rows = {};
    for (const c of BINARY_LAYOUT) { if (!(c.src in rows)) rows[c.src] = c.y; }
    for (const [src, cy] of Object.entries(rows)) {
      const rightmost = Math.max(...BINARY_LAYOUT.filter(c => c.src === src).map(c => c.x));
      const v = String(Math.round(value(src, now))).padStart(2, "0");
      s += `<text x="${rightmost + BINARY_GX}" y="${cy + 8}" fill="${LABEL_COLOR}" font-size="26" text-anchor="middle" font-family="system-ui">${v}</text>`;
    }
  }
  return s;
}

function draw() {
  const now = new Date();
  const light = document.getElementById("theme").checked;
  const key = light ? "light" : "dark";
  const showLabels = document.getElementById("labels").checked;
  const base = baseSel.value;
  let s = `<rect x="0" y="0" width="__CANVAS__" height="__CANVAS__" fill="${BG[key]}"/>`;
  if (base === "binary") {
    s += drawBinary(ensureContrast(paletteFor(paletteSel.value, 1)[0], key), OFF[key], showLabels, now);
  } else if (base === "hexagon") {
    s += drawHexagon(paletteFor(paletteSel.value, 6), OUTLINE[key], showLabels, now);
  } else {
    s += drawQuinary(paletteFor(paletteSel.value, 4), OUTLINE[key], showLabels, now);
  }
  svg.innerHTML = s;
  document.getElementById("readout").textContent = now.toTimeString().slice(0, 8) + "  (" + base + ")";
}
setInterval(draw, 250); draw();
</script>
"""


def build_html() -> str:
    def css(argb):
        return "#" + argb[-6:]

    repl = {
        "__CANVAS__": str(CANVAS),
        "__SUB_GAP__": str(SUB_GAP),
        "__LABEL_W__": str(LABEL_W),
        "__LABEL_H__": str(LABEL_H),
        "__QUINARY_LAYOUT_JS__": "[" + ",".join(
            '{x:%.1f,y:%.1f,w:%.1f,h:%.1f,shape:"%s",radius:%d,place:%d,src:%s,label:%s,label_x:%s,label_y:%s}' % (
                c["x"], c["y"], c["w"], c["h"], c["shape"], c["radius"], c["place"],
                repr(c["expr"]).replace("'", '"'), (f'"{c["label"]}"' if c["label"] else "null"),
                c["label_x"], c["label_y"])
            for c in full_layout()) + "]",
        "__DECIMAL_X__": str(DECIMAL_X),
        "__DECIMAL_ROWS_JS__": "[" + ",".join(f'["{expr}",{cy}]' for expr, cy in DECIMAL_ROWS) + "]",
        "__BINARY_LAYOUT_JS__": "[" + ",".join(
            '{x:%.1f,y:%.1f,k:%d,src:%s,label:%s}' % (
                c["x"], c["y"], c["k"], repr(c["expr"]).replace("'", '"'),
                (f'"{c["label"]}"' if c["label"] else "null"))
            for c in binary_layout()) + "]",
        "__BINARY_GX__": str(GX),
        "__BINARY_GY__": str(GY),
        "__LED_R__": str(LED_R),
        "__OFF_DARK__": css(OFF_DARK),
        "__OFF_LIGHT__": css(OFF_LIGHT),
        "__BINARY_DECIMAL_W__": str(BINARY_DECIMAL_W),
        # ANCHOR_COLORS stores WFF-format ARGB ("#FFFF5A5A"); the JS
        # hexToHsl() mirrors palettes.py's monochrome_palette() math, which
        # expects a plain 6-digit "#RRGGBB" string -- strip alpha with css()
        # here, same as every other color fed into the JS. (Caught by
        # actually looking at a screenshot: "Red shades" rendered yellow,
        # because the alpha byte was silently being read as part of red.)
        "__ANCHORS_JS__": "[" + ",".join(f'["{aid}","{name}","{css(argb)}"]' for aid, name, argb in ANCHOR_COLORS) + "]",
        "__OKABE_ITO_JS__": "[" + ",".join(f'"{css(c)}"' for c in OKABE_ITO) + "]",
        "__ROYGBIV_START__": str(ROYGBIV_START_DEG),
        "__ROYGBIV_END__": str(ROYGBIV_END_DEG),
        "__OUTLINE_DARK__": css(OUTLINE_DARK),
        "__OUTLINE_LIGHT__": css(OUTLINE_LIGHT),
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
