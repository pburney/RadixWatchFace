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


# ---- Generic grid-group renderer -- generalizes Quinary's 2x2
# corner-squaring trick to any rows x cols grid whose rows*cols == n
# positions. The 2x2 case is the special case where every subcell has
# exactly one true outer corner (matching its own quadrant name); for a
# taller/wider grid, a corner stays rounded only if BOTH of its adjacent
# edges are on the true grid perimeter (row/col at the grid's extreme in
# that direction) -- otherwise it's squared off so adjacent lit cells'
# shared edges fuse flat. This reduces to exactly Quinary's own rule at
# 2x2 and produces a plain rounded-RECTANGLE outline (rounded only at the
# 4 literal grid corners) for any rows x cols -- verified by hand-tracing
# 2x2/2x3/3x2/2x4 before trusting it, then confirmed visually via an SVG
# mockup Paul reviewed before this was ported into real WFF XML.
def wff_grid_outline(cx, cy, w, h, rows, cols, outline_color):
    x, y = round(cx - w / 2), round(cy - h / 2)
    r = min(w / cols, h / rows) * 0.25
    return (f'      <PartDraw x="{x}" y="{y}" width="{round(w)}" height="{round(h)}">\n'
            f'        <RoundRectangle x="0" y="0" width="{round(w)}" height="{round(h)}" '
            f'cornerRadiusX="{r:.1f}" cornerRadiusY="{r:.1f}">'
            f'<Stroke color="{outline_color}" thickness="1.5" dashIntervals="3 5" cap="ROUND"/></RoundRectangle>\n'
            f'      </PartDraw>')


def wff_grid_groups(cx, cy, w, h, rows, cols, radius, digit_expr, colors, name_prefix):
    cell_w, cell_h = w / cols, h / rows
    bx0, by0 = cx - w / 2, cy - h / 2
    out = []
    for k in range(rows * cols):
        row, col = divmod(k, cols)
        bx, by = round(bx0 + col * cell_w), round(by0 + row * cell_h)
        cw, ch = round(cell_w), round(cell_h)
        r = min(radius, cw / 2, ch / 2)
        color = colors[k]
        keep_rounded = {
            "TL": row == 0 and col == 0,
            "TR": row == 0 and col == cols - 1,
            "BL": row == rows - 1 and col == 0,
            "BR": row == rows - 1 and col == cols - 1,
        }
        corner_xy = {"TL": (0, 0), "TR": (cw - r, 0), "BL": (0, ch - r), "BR": (cw - r, ch - r)}
        squares = "".join(
            f'<Rectangle x="{sx:.1f}" y="{sy:.1f}" width="{r:.1f}" height="{r:.1f}"><Fill color="{color}"/></Rectangle>'
            for corner, (sx, sy) in corner_xy.items() if not keep_rounded[corner])
        shape_el = (f'<RoundRectangle x="0" y="0" width="{cw}" height="{ch}" '
                    f'cornerRadiusX="{r:.1f}" cornerRadiusY="{r:.1f}"><Fill color="{color}"/></RoundRectangle>{squares}')
        name = f"{name_prefix}_{k}"
        out.append(
            f'      <Condition>\n'
            f'        <Expressions>\n'
            f'          <Expression name="{name}"><![CDATA[(({digit_expr}) > {k})]]></Expression>\n'
            f'        </Expressions>\n'
            f'        <Compare expression="{name}">\n'
            f'          <PartDraw x="{bx}" y="{by}" width="{cw}" height="{ch}">\n'
            f'            {shape_el}\n'
            f'          </PartDraw>\n'
            f'        </Compare>\n'
            f'      </Condition>')
    return "\n".join(out)


# ---- Pentagon (base 6) -- checked computationally like every other base:
# 6^1=6<=23<36=6^2 and 6^2=36<=59<216=6^3, giving the SAME (2,3,3) place
# pattern as Quinary/Hexagon (5 and 7 give identical place counts for the
# same reason -- see the Hexagon note below). So Pentagon reuses
# full_layout() wholesale too, exactly like Hexagon -- only the digit math
# (base 6) and wedge count (5 positions instead of 4 or 6) differ.
#
# 2026-09-24 fix: Hour cells from hour_layout() are HOUR_W x HOUR_H (112x72,
# NOT square), but the wedge-circle renderer used r=c["w"]/2 unconditionally
# -- ballooning the Hour circle to a 112px diameter instead of respecting
# the 72px row height. Computed the actual overlap rather than guessing:
# that circle's bottom edge lands at row_y+56=218, while the Minute row's
# circle top edge is at row_y-36=213 -- a real 5px overlap, not an illusion,
# and exactly why Pentagon read as "too close together" (Hexagon had this
# identical bug until its Hour row became a grid, which coincidentally
# uses the correct h dimension). Fixed by using r=min(w,h)/2.
# 2026-09-24: Pentagon switched from the wedge-circle to TALLY MARKS, per
# Paul's explicit ask -- base 6's digit range (0-5) maps perfectly onto the
# classic tally system: 4 independent vertical bars for positions 0-3, then
# a single diagonal slash across all 4 for position 4 (lit only when
# digit=5, i.e. every other position is also lit). Confirmed via a static
# SVG mockup (both this and a "WiFi bars" alternative) before writing any
# WFF XML -- Paul picked tally marks. Sized to fit uniformly across every
# row regardless of the underlying cell's own w/h (same "uniform size
# regardless of row" principle as the circle-radius fix above): a plain
# Rectangle's rotation isn't expression-driven here, just Group's own
# static `angle`+`pivotX`/`pivotY` attributes (confirmed real via direct
# XSD read of group/groupElement.xsd -- pivot is normalized [0,1] within
# the Group's own box, angle in degrees). Verified computationally that
# both the bars' and the rotated slash's farthest corners stay within a
# 30.1px radius of the cell center -- safely inside the 36px bound the
# Pentagon row-spacing fix above already proved doesn't collide with
# neighboring rows (a rotated rectangle's farthest-corner distance from its
# own pivot is invariant to the rotation angle, so this bound holds at any
# angle, not just the one chosen below).
PENT_TALLY_BAR_W = 6
PENT_TALLY_BAR_H = 48
PENT_TALLY_GAP = 4
PENT_TALLY_N = 4
_PENT_TALLY_TOTAL_W = PENT_TALLY_N * PENT_TALLY_BAR_W + (PENT_TALLY_N - 1) * PENT_TALLY_GAP
PENT_TALLY_SLASH_LEN = round((_PENT_TALLY_TOTAL_W ** 2 + PENT_TALLY_BAR_H ** 2) ** 0.5)  # spans the block's diagonal
PENT_TALLY_SLASH_ANGLE = -35  # degrees; either diagonal direction reads fine as a tally slash


def pent_digit_expr(value_expr: str, place: int) -> str:
    return f"round(floor(({value_expr}) / {6 ** place}) % 6)"


def _pent_tally_bar_x(k: int) -> float:
    return -_PENT_TALLY_TOTAL_W / 2 + k * (PENT_TALLY_BAR_W + PENT_TALLY_GAP) + PENT_TALLY_BAR_W / 2


def wff_pent_outlines(layout, outline_color):
    stroke = f'<Stroke color="{outline_color}" thickness="1.5" dashIntervals="3 5" cap="ROUND"/>'
    out = []
    for c in layout:
        for k in range(PENT_TALLY_N):
            bx = round(c["x"] + _pent_tally_bar_x(k) - PENT_TALLY_BAR_W / 2)
            by = round(c["y"] - PENT_TALLY_BAR_H / 2)
            out.append(
                f'      <PartDraw x="{bx}" y="{by}" width="{PENT_TALLY_BAR_W}" height="{PENT_TALLY_BAR_H}">\n'
                f'        <RoundRectangle x="0" y="0" width="{PENT_TALLY_BAR_W}" height="{PENT_TALLY_BAR_H}" '
                f'cornerRadiusX="{PENT_TALLY_BAR_W / 2}" cornerRadiusY="{PENT_TALLY_BAR_W / 2}">{stroke}</RoundRectangle>\n'
                f'      </PartDraw>')
        sx = round(c["x"] - PENT_TALLY_SLASH_LEN / 2)
        sy = round(c["y"] - PENT_TALLY_BAR_W / 2)
        out.append(
            f'      <Group name="pent_slash_outline_{round(c["x"])}_{round(c["y"])}" '
            f'x="{sx}" y="{sy}" width="{PENT_TALLY_SLASH_LEN}" height="{PENT_TALLY_BAR_W}" '
            f'pivotX="0.5" pivotY="0.5" angle="{PENT_TALLY_SLASH_ANGLE}">\n'
            f'        <PartDraw x="0" y="0" width="{PENT_TALLY_SLASH_LEN}" height="{PENT_TALLY_BAR_W}">\n'
            f'          <RoundRectangle x="0" y="0" width="{PENT_TALLY_SLASH_LEN}" height="{PENT_TALLY_BAR_W}" '
            f'cornerRadiusX="{PENT_TALLY_BAR_W / 2}" cornerRadiusY="{PENT_TALLY_BAR_W / 2}">{stroke}</RoundRectangle>\n'
            f'        </PartDraw>\n'
            f'      </Group>')
    return "\n".join(out)


def wff_pent_groups(layout, colors):
    out = []
    for c in layout:
        digit_expr = pent_digit_expr(c["expr"], c["place"])
        for k in range(PENT_TALLY_N):
            bx = round(c["x"] + _pent_tally_bar_x(k) - PENT_TALLY_BAR_W / 2)
            by = round(c["y"] - PENT_TALLY_BAR_H / 2)
            name = f"p{c['place']}_{round(c['x'])}_{round(c['y'])}_{k}"
            out.append(
                f'      <Condition>\n'
                f'        <Expressions>\n'
                f'          <Expression name="{name}"><![CDATA[(({digit_expr}) > {k})]]></Expression>\n'
                f'        </Expressions>\n'
                f'        <Compare expression="{name}">\n'
                f'          <PartDraw x="{bx}" y="{by}" width="{PENT_TALLY_BAR_W}" height="{PENT_TALLY_BAR_H}">\n'
                f'            <RoundRectangle x="0" y="0" width="{PENT_TALLY_BAR_W}" height="{PENT_TALLY_BAR_H}" '
                f'cornerRadiusX="{PENT_TALLY_BAR_W / 2}" cornerRadiusY="{PENT_TALLY_BAR_W / 2}">'
                f'<Fill color="{colors[k]}"/></RoundRectangle>\n'
                f'          </PartDraw>\n'
                f'        </Compare>\n'
                f'      </Condition>')
        name5 = f"p{c['place']}_{round(c['x'])}_{round(c['y'])}_4"
        sx = round(c["x"] - PENT_TALLY_SLASH_LEN / 2)
        sy = round(c["y"] - PENT_TALLY_BAR_W / 2)
        out.append(
            f'      <Condition>\n'
            f'        <Expressions>\n'
            f'          <Expression name="{name5}"><![CDATA[(({digit_expr}) > 4)]]></Expression>\n'
            f'        </Expressions>\n'
            f'        <Compare expression="{name5}">\n'
            f'          <Group name="pent_slash_{round(c["x"])}_{round(c["y"])}" '
            f'x="{sx}" y="{sy}" width="{PENT_TALLY_SLASH_LEN}" height="{PENT_TALLY_BAR_W}" '
            f'pivotX="0.5" pivotY="0.5" angle="{PENT_TALLY_SLASH_ANGLE}">\n'
            f'            <PartDraw x="0" y="0" width="{PENT_TALLY_SLASH_LEN}" height="{PENT_TALLY_BAR_W}">\n'
            f'              <RoundRectangle x="0" y="0" width="{PENT_TALLY_SLASH_LEN}" height="{PENT_TALLY_BAR_W}" '
            f'cornerRadiusX="{PENT_TALLY_BAR_W / 2}" cornerRadiusY="{PENT_TALLY_BAR_W / 2}">'
            f'<Fill color="{colors[4]}"/></RoundRectangle>\n'
            f'            </PartDraw>\n'
            f'          </Group>\n'
            f'        </Compare>\n'
            f'      </Condition>')
    return "\n".join(out)


def pentagon_palette_list_option(option_id: str, layout, theme: str) -> str:
    colors = palette_for(option_id, 5)
    return (f'        <ListOption id="{option_id}">\n'
            f'          <Group name="pent_palette_{option_id}_{theme}" x="0" y="0" width="{CANVAS}" height="{CANVAS}">\n'
            f'{wff_pent_groups(layout, colors)}\n'
            f'          </Group>\n'
            f'        </ListOption>')


def build_base_pentagon(theme: str, outline_color: str) -> str:
    layout = full_layout()   # same positions as Quinary/Hexagon -- see module note above
    palette_options = "\n".join(
        pentagon_palette_list_option(opt_id, layout, theme) for opt_id, _res, _anchor in PALETTE_OPTIONS)
    return f"""    <ListOption id="pentagon">
      <Group name="pentagon_{theme}" x="0" y="0" width="{CANVAS}" height="{CANVAS}">
        <Group name="pentagon_outlines_{theme}" x="0" y="0" width="{CANVAS}" height="{CANVAS}">
{wff_pent_outlines(layout, outline_color)}
        </Group>
        <ListConfiguration id="palette">
{palette_options}
        </ListConfiguration>
        <BooleanConfiguration id="labels">
          <BooleanOption id="TRUE">
            <Group name="pentagon_labels_{theme}" x="0" y="0" width="{CANVAS}" height="{CANVAS}">
{wff_labels(layout)}
{wff_decimal_readout()}
            </Group>
          </BooleanOption>
        </BooleanConfiguration>
      </Group>
    </ListOption>"""


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
# 2x2-grid equivalent for 6 positions as a single monolithic shape, BUT
# 6 = 2x3 does factor into a small rectangular grid -- 2026-09-24: Hour and
# Minute now use the generalized grid renderer (wff_grid_groups) for a real
# chunky-tile / blob look, same as Quinary, while Second stays the wedge
# pie (row identity here is now genuinely 3-way, not just label+position).
HEX_POSITIONS = ["P0", "P1", "P2", "P3", "P4", "P5"]
HEX_ANGLES = {f"P{i}": (i * 60, (i + 1) * 60) for i in range(6)}
HEX_GRID_ROWS = {
    "[HOUR_0_23]": dict(rows=2, cols=3, radius=6, prefix="hxt"),    # chunky tile
    "[MINUTE]": dict(rows=3, cols=2, radius=999, prefix="hxb"),     # blob (radius clamped to max)
}


def hex_digit_expr(value_expr: str, place: int) -> str:
    return f"round(floor(({value_expr}) / {7 ** place}) % 7)"


def wff_hex_outlines(layout, outline_color):
    out = []
    for c in layout:
        cfg = HEX_GRID_ROWS.get(c["expr"])
        if cfg:
            out.append(wff_grid_outline(c["x"], c["y"], c["w"], c["h"], cfg["rows"], cfg["cols"], outline_color))
            continue
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
        cfg = HEX_GRID_ROWS.get(c["expr"])
        if cfg:
            prefix = f'{cfg["prefix"]}{c["place"]}_{round(c["x"])}_{round(c["y"])}'
            out.append(wff_grid_groups(c["x"], c["y"], c["w"], c["h"], cfg["rows"], cfg["cols"],
                                        cfg["radius"], digit_expr, colors, prefix))
            continue
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


# ---- Octagon (base 9) -- NOT a reuse of Quinary/Hexagon's layout, unlike
# Hexagon. Checked computationally rather than assumed: base 9 only needs
# 2 places for M/S (0-59), since 9^2=81 > 59 -- unlike base 5/7, which both
# need 3 (25<=59 and 49<=59 respectively). A 3rd place would be permanently
# dark for every valid time value, exactly the "permanently-dark quad"
# outcome Quinary's own original design explicitly avoided. So Octagon gets
# its own simple, uniform layout: every row (H, M, S) has exactly 2 places,
# centered on the canvas rather than right-aligned+stretched the way
# Quinary/Hexagon's asymmetric 2-vs-3-place rows needed.
OCT_QUAD = 72
OCT_PITCH = 88
OCT_LABEL_GAP = 10
OCT_LABEL_W, OCT_LABEL_H = 36, 36
OCT_LEFT_CX = C - OCT_PITCH / 2
OCT_RIGHT_CX = C + OCT_PITCH / 2
OCT_LABEL_X = OCT_LEFT_CX - OCT_QUAD / 2 - OCT_LABEL_GAP - OCT_LABEL_W / 2
OCT_DECIMAL_GAP = 10
OCT_DECIMAL_W, OCT_DECIMAL_H = 44, 36
OCT_DECIMAL_X = OCT_RIGHT_CX + OCT_QUAD / 2 + OCT_DECIMAL_GAP + OCT_DECIMAL_W / 2

OCT_POSITIONS = [f"P{i}" for i in range(8)]
OCT_ANGLES = {f"P{i}": (i * 45, (i + 1) * 45) for i in range(8)}

# 2026-09-24: Octagon (base 9, n=8 positions) gets the same generalized grid
# treatment as Hexagon -- 8 = 2x4 factors cleanly. Octal (base 8, n=7
# positions) shares this SAME layout/outline geometry but is NOT part of
# this -- 7 doesn't factor into a small grid, and it keeps wedge-pie
# throughout. Passed as an explicit optional param (default: no rows get
# grid treatment) rather than a module-level dict, specifically so Octal's
# calls to these same functions are unaffected -- an accidental shared
# mutable default here would silently break Octal's outline/content match.
OCTAGON_GRID_ROWS = {
    "[HOUR_0_23]": dict(rows=2, cols=4, radius=4, prefix="ogt"),   # chunky tile
    "[MINUTE]": dict(rows=4, cols=2, radius=999, prefix="ogb"),    # blob
}


def octagon_digit_expr(value_expr: str, place: int) -> str:
    return f"round(floor(({value_expr}) / {9 ** place}) % 9)"


def octagon_layout():
    specs = [("H", "[HOUR_0_23]", 0), ("M", "[MINUTE]", 1), ("S", "[SECOND]", 2)]
    out = []
    for label, expr, row_i in specs:
        cy = ROW_Y[row_i]
        for col, cx in enumerate((OCT_LEFT_CX, OCT_RIGHT_CX)):
            place = 1 - col
            out.append(dict(x=cx, y=cy, w=OCT_QUAD, h=OCT_QUAD, place=place, expr=expr,
                             label=label if col == 0 else None, label_x=OCT_LABEL_X, label_y=cy))
    return out


OCT_DECIMAL_ROWS = [("[HOUR_0_23]", ROW_Y[0]), ("[MINUTE]", ROW_Y[1]), ("[SECOND]", ROW_Y[2])]


def wff_octagon_decimal_readout():
    out = []
    for expr, cy in OCT_DECIMAL_ROWS:
        x, y = round(OCT_DECIMAL_X - OCT_DECIMAL_W / 2), round(cy - OCT_DECIMAL_H / 2)
        out.append(
            f'        <PartText x="{x}" y="{y}" width="{OCT_DECIMAL_W}" height="{OCT_DECIMAL_H}">\n'
            f'          <Text align="CENTER"><Font family="SYNC_TO_DEVICE" size="26" '
            f'weight="NORMAL" color="{LABEL_COLOR}">\n'
            f'              <Template>%02d<Parameter expression="{expr}"/></Template>\n'
            f'          </Font></Text>\n'
            f'        </PartText>')
    return "\n".join(out)


def wff_octagon_outlines(layout, outline_color, grid_rows=None):
    grid_rows = grid_rows or {}
    out = []
    for c in layout:
        cfg = grid_rows.get(c["expr"])
        if cfg:
            out.append(wff_grid_outline(c["x"], c["y"], c["w"], c["h"], cfg["rows"], cfg["cols"], outline_color))
            continue
        r = c["w"] / 2
        x, y = round(c["x"] - r), round(c["y"] - r)
        out.append(
            f'      <PartDraw x="{x}" y="{y}" width="{round(r * 2)}" height="{round(r * 2)}">\n'
            f'        <Ellipse x="0" y="0" width="{round(r * 2)}" height="{round(r * 2)}">'
            f'<Stroke color="{outline_color}" thickness="1.5" dashIntervals="3 5" cap="ROUND"/></Ellipse>\n'
            f'      </PartDraw>')
    return "\n".join(out)


def wff_octagon_groups(layout, colors, grid_rows=None):
    grid_rows = grid_rows or {}
    out = []
    for c in layout:
        digit_expr = octagon_digit_expr(c["expr"], c["place"])
        cfg = grid_rows.get(c["expr"])
        if cfg:
            prefix = f'{cfg["prefix"]}{c["place"]}_{round(c["x"])}_{round(c["y"])}'
            out.append(wff_grid_groups(c["x"], c["y"], c["w"], c["h"], cfg["rows"], cfg["cols"],
                                        cfg["radius"], digit_expr, colors, prefix))
            continue
        r = c["w"] / 2
        bx, by = round(c["x"] - r), round(c["y"] - r)
        for k, pos in enumerate(OCT_POSITIONS):
            start, end = OCT_ANGLES[pos]
            name = f"o{c['place']}_{round(c['x'])}_{round(c['y'])}_{k}"
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


def octagon_palette_list_option(option_id: str, layout, theme: str) -> str:
    colors = palette_for(option_id, 8)
    return (f'        <ListOption id="{option_id}">\n'
            f'          <Group name="oct_palette_{option_id}_{theme}" x="0" y="0" width="{CANVAS}" height="{CANVAS}">\n'
            f'{wff_octagon_groups(layout, colors, OCTAGON_GRID_ROWS)}\n'
            f'          </Group>\n'
            f'        </ListOption>')


def build_base_octagon(theme: str, outline_color: str) -> str:
    layout = octagon_layout()
    palette_options = "\n".join(
        octagon_palette_list_option(opt_id, layout, theme) for opt_id, _res, _anchor in PALETTE_OPTIONS)
    return f"""    <ListOption id="octagon">
      <Group name="octagon_{theme}" x="0" y="0" width="{CANVAS}" height="{CANVAS}">
        <Group name="octagon_outlines_{theme}" x="0" y="0" width="{CANVAS}" height="{CANVAS}">
{wff_octagon_outlines(layout, outline_color, OCTAGON_GRID_ROWS)}
        </Group>
        <ListConfiguration id="palette">
{palette_options}
        </ListConfiguration>
        <BooleanConfiguration id="labels">
          <BooleanOption id="TRUE">
            <Group name="octagon_labels_{theme}" x="0" y="0" width="{CANVAS}" height="{CANVAS}">
{wff_labels(layout)}
{wff_octagon_decimal_readout()}
            </Group>
          </BooleanOption>
        </BooleanConfiguration>
      </Group>
    </ListOption>"""


# ---- Octal (base 8) -- reuses octagon_layout()'s geometry (identical
# (2,2,2) place pattern to Octagon, all rows square 72x72 cells, no
# Hour/Minute-vs-Second mismatch the way Pentagon had). 2026-09-24: switched
# from wedge-pie to WIFI BARS per Paul's ask, after tally marks worked out
# well for Pentagon -- 7 independent vertical bars, tallest first (leftmost)
# decreasing to shortest (rightmost), each lit independently like the other
# count-encodings (no diagonal/rotation needed here, unlike Pentagon's tally
# 5th mark). Verified computationally that the tallest bar's farthest corner
# stays within a 28.3px radius of the cell center -- comfortably inside the
# 36px bound Octagon's own wedge-pie already proved safe (7.7px margin,
# same ballpark as Trinary's and Quaternary's accepted margins).
OCTAL_WIFI_BAR_W = 4
OCTAL_WIFI_GAP = 2
OCTAL_WIFI_N = 7
OCTAL_WIFI_MAX_H = 40
OCTAL_WIFI_MIN_H = 14
_OCTAL_WIFI_TOTAL_W = OCTAL_WIFI_N * OCTAL_WIFI_BAR_W + (OCTAL_WIFI_N - 1) * OCTAL_WIFI_GAP
_OCTAL_WIFI_STEP = (OCTAL_WIFI_MAX_H - OCTAL_WIFI_MIN_H) / (OCTAL_WIFI_N - 1)


def octal_digit_expr(value_expr: str, place: int) -> str:
    return f"round(floor(({value_expr}) / {8 ** place}) % 8)"


def _octal_wifi_bar_geom(k: int):
    h = OCTAL_WIFI_MAX_H - k * _OCTAL_WIFI_STEP
    x_off = -_OCTAL_WIFI_TOTAL_W / 2 + k * (OCTAL_WIFI_BAR_W + OCTAL_WIFI_GAP) + OCTAL_WIFI_BAR_W / 2
    return h, x_off


def wff_octal_outlines(layout, outline_color):
    stroke = f'<Stroke color="{outline_color}" thickness="1.5" dashIntervals="3 5" cap="ROUND"/>'
    out = []
    for c in layout:
        baseline_y = c["y"] + OCTAL_WIFI_MAX_H / 2
        for k in range(OCTAL_WIFI_N):
            h, x_off = _octal_wifi_bar_geom(k)
            bx = round(c["x"] + x_off - OCTAL_WIFI_BAR_W / 2)
            by = round(baseline_y - h)
            out.append(
                f'      <PartDraw x="{bx}" y="{by}" width="{OCTAL_WIFI_BAR_W}" height="{round(h)}">\n'
                f'        <RoundRectangle x="0" y="0" width="{OCTAL_WIFI_BAR_W}" height="{round(h)}" '
                f'cornerRadiusX="{OCTAL_WIFI_BAR_W / 2}" cornerRadiusY="{OCTAL_WIFI_BAR_W / 2}">{stroke}</RoundRectangle>\n'
                f'      </PartDraw>')
    return "\n".join(out)


def wff_octal_groups(layout, colors):
    out = []
    for c in layout:
        digit_expr = octal_digit_expr(c["expr"], c["place"])
        baseline_y = c["y"] + OCTAL_WIFI_MAX_H / 2
        for k in range(OCTAL_WIFI_N):
            h, x_off = _octal_wifi_bar_geom(k)
            bx = round(c["x"] + x_off - OCTAL_WIFI_BAR_W / 2)
            by = round(baseline_y - h)
            name = f"l{c['place']}_{round(c['x'])}_{round(c['y'])}_{k}"
            out.append(
                f'      <Condition>\n'
                f'        <Expressions>\n'
                f'          <Expression name="{name}"><![CDATA[(({digit_expr}) > {k})]]></Expression>\n'
                f'        </Expressions>\n'
                f'        <Compare expression="{name}">\n'
                f'          <PartDraw x="{bx}" y="{by}" width="{OCTAL_WIFI_BAR_W}" height="{round(h)}">\n'
                f'            <RoundRectangle x="0" y="0" width="{OCTAL_WIFI_BAR_W}" height="{round(h)}" '
                f'cornerRadiusX="{OCTAL_WIFI_BAR_W / 2}" cornerRadiusY="{OCTAL_WIFI_BAR_W / 2}">'
                f'<Fill color="{colors[k]}"/></RoundRectangle>\n'
                f'          </PartDraw>\n'
                f'        </Compare>\n'
                f'      </Condition>')
    return "\n".join(out)


def octal_palette_list_option(option_id: str, layout, theme: str) -> str:
    colors = palette_for(option_id, 7)
    return (f'        <ListOption id="{option_id}">\n'
            f'          <Group name="octal_palette_{option_id}_{theme}" x="0" y="0" width="{CANVAS}" height="{CANVAS}">\n'
            f'{wff_octal_groups(layout, colors)}\n'
            f'          </Group>\n'
            f'        </ListOption>')


def build_base_octal(theme: str, outline_color: str) -> str:
    layout = octagon_layout()   # same geometry as Octagon -- see module note above
    palette_options = "\n".join(
        octal_palette_list_option(opt_id, layout, theme) for opt_id, _res, _anchor in PALETTE_OPTIONS)
    return f"""    <ListOption id="octal">
      <Group name="octal_{theme}" x="0" y="0" width="{CANVAS}" height="{CANVAS}">
        <Group name="octal_outlines_{theme}" x="0" y="0" width="{CANVAS}" height="{CANVAS}">
{wff_octal_outlines(layout, outline_color)}
        </Group>
        <ListConfiguration id="palette">
{palette_options}
        </ListConfiguration>
        <BooleanConfiguration id="labels">
          <BooleanOption id="TRUE">
            <Group name="octal_labels_{theme}" x="0" y="0" width="{CANVAS}" height="{CANVAS}">
{wff_labels(layout)}
{wff_octagon_decimal_readout()}
            </Group>
          </BooleanOption>
        </BooleanConfiguration>
      </Group>
    </ListOption>"""


# ---- Quaternary (base 4) -- checked computationally like Octagon, not
# assumed: base 4 needs 3 places for H too (4^2=16<=23<64=4^3), not just
# M/S -- a NEW place pattern (3,3,3) distinct from both Quinary/Hexagon's
# (2,3,3) and Octagon's (2,2,2). Since H now needs exactly as many places
# as M/S, all three rows can share the same right-aligned-by-place layout
# with no special "stretch H to match width" treatment -- and that layout
# is, conveniently, IDENTICAL to Quinary's existing quad_layout() geometry
# (RIGHT_EDGE_X, QUAD_PITCH, QUAD, ROW_Y all reused unchanged), just with H
# generalized to behave like M/S instead of being a special case. Positions
# 0..2 (n=base-1=3) wedge-split circle, same proven technique as every
# other n>=2 base.
QUAT_POSITIONS = ["P0", "P1", "P2"]
QUAT_ANGLES = {f"P{i}": (i * 120, (i + 1) * 120) for i in range(3)}


def quaternary_digit_expr(value_expr: str, place: int) -> str:
    return f"round(floor(({value_expr}) / {4 ** place}) % 4)"


def quaternary_layout():
    specs = [(0, "H", "[HOUR_0_23]"), (1, "M", "[MINUTE]"), (2, "S", "[SECOND]")]
    out = []
    for row_i, label, expr in specs:
        cy = ROW_Y[row_i]
        for col in range(3):
            place = 2 - col
            cx = RIGHT_EDGE_X - place * QUAD_PITCH
            out.append(dict(x=cx, y=cy, w=QUAD, place=place, expr=expr,
                             label=label if col == 0 else None, label_x=LABEL_X, label_y=cy))
    return out


def wff_quat_outlines(layout, outline_color):
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


def wff_quat_groups(layout, colors):
    out = []
    for c in layout:
        digit_expr = quaternary_digit_expr(c["expr"], c["place"])
        r = c["w"] / 2
        bx, by = round(c["x"] - r), round(c["y"] - r)
        for k, pos in enumerate(QUAT_POSITIONS):
            start, end = QUAT_ANGLES[pos]
            name = f"t{c['place']}_{round(c['x'])}_{round(c['y'])}_{k}"
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


def quaternary_palette_list_option(option_id: str, layout, theme: str) -> str:
    colors = palette_for(option_id, 3)
    return (f'        <ListOption id="{option_id}">\n'
            f'          <Group name="quat_palette_{option_id}_{theme}" x="0" y="0" width="{CANVAS}" height="{CANVAS}">\n'
            f'{wff_quat_groups(layout, colors)}\n'
            f'          </Group>\n'
            f'        </ListOption>')


def build_base_quaternary(theme: str, outline_color: str) -> str:
    layout = quaternary_layout()
    palette_options = "\n".join(
        quaternary_palette_list_option(opt_id, layout, theme) for opt_id, _res, _anchor in PALETTE_OPTIONS)
    return f"""    <ListOption id="quaternary">
      <Group name="quaternary_{theme}" x="0" y="0" width="{CANVAS}" height="{CANVAS}">
        <Group name="quaternary_outlines_{theme}" x="0" y="0" width="{CANVAS}" height="{CANVAS}">
{wff_quat_outlines(layout, outline_color)}
        </Group>
        <ListConfiguration id="palette">
{palette_options}
        </ListConfiguration>
        <BooleanConfiguration id="labels">
          <BooleanOption id="TRUE">
            <Group name="quaternary_labels_{theme}" x="0" y="0" width="{CANVAS}" height="{CANVAS}">
{wff_labels(layout)}
{wff_decimal_readout()}
            </Group>
          </BooleanOption>
        </BooleanConfiguration>
      </Group>
    </ListOption>"""


# ---- Trinary (base 3) -- checked computationally, NOT assumed to be "like
# binary": base 3 needs 3 places for H (3^2=9<=23<27=3^3) and 4 places for
# M/S (3^3=27<=59<81=3^4) -- a FOURTH distinct place pattern, wider than
# anything built so far (Quinary/Hexagon 2,3,3 / Octagon 2,2,2 / Quaternary
# 3,3,3). 4 columns in one row doesn't fit Quinary's existing
# RIGHT_EDGE_X/QUAD_PITCH geometry (label/decimal readout boxes clip outside
# the 225px-radius circle at that spacing -- verified with the same
# farthest-corner check used for every other base, not eyeballed), so
# Trinary gets its OWN smaller, centered layout: QUAD/PITCH shrunk from
# Quinary's 72/88 to 64/70, and the label/decimal boxes shrunk to match
# (36x36/44x36 -> 30x30/36x30, gaps 10->6) -- tightest margin 6.1px on the
# S row's decimal readout, same ballpark as Quaternary's own tightest
# margin. Two positions per digit (n=base-1=2), same wedge-split circle
# technique as every base n>=2 -- NOT the n=1 filled-Ellipse special case
# Binary needed (that's for n=1 only; n=2 is a perfectly normal 2-wedge
# split, already covered by the general spike).
TRI_QUAD = 64
TRI_PITCH = 70
TRI_LABEL_GAP = 6
TRI_LABEL_W, TRI_LABEL_H = 30, 30
TRI_DECIMAL_GAP = 6
TRI_DECIMAL_W, TRI_DECIMAL_H = 36, 30
_TRI_WIDEST_N = 4   # M/S -- widest row sets the shared label/decimal x, like Quinary's LABEL_X
_TRI_LEFT_EDGE = C - (_TRI_WIDEST_N - 1) / 2 * TRI_PITCH - TRI_QUAD / 2
_TRI_RIGHT_EDGE = C + (_TRI_WIDEST_N - 1) / 2 * TRI_PITCH + TRI_QUAD / 2
TRI_LABEL_X = _TRI_LEFT_EDGE - TRI_LABEL_GAP - TRI_LABEL_W / 2
TRI_DECIMAL_X = _TRI_RIGHT_EDGE + TRI_DECIMAL_GAP + TRI_DECIMAL_W / 2

TRI_POSITIONS = ["P0", "P1"]
TRI_ANGLES = {f"P{i}": (i * 180, (i + 1) * 180) for i in range(2)}

# 2026-09-24: Trinary is the ring-variant experiment (Paul: "Let's try the
# ring for Trinary") -- same proven Arc/WeightedStroke element every wedge
# base already uses, just a different `thickness` (ring vs. solid pie) and
# angle padding (gap between wedges) per row. No new element, no new
# geometry, no new fit-check: a thinner/gapped stroke only draws LESS than
# the already-validated bounding circle, never more.
#   thickness_frac=1.0 -> solid pie (the original, unchanged look)
#   thickness_frac<1.0 -> a ring/donut (stroke doesn't reach the center)
#   gap>0              -> shrinks each wedge's angle span, opening a gap
TRI_RING_STYLES = {
    "[HOUR_0_23]": dict(thickness_frac=1.0, gap=0),    # solid pie (unchanged baseline)
    "[MINUTE]": dict(thickness_frac=0.45, gap=0),      # thin ring / donut
    "[SECOND]": dict(thickness_frac=0.45, gap=10),     # segmented ring
}


def trinary_digit_expr(value_expr: str, place: int) -> str:
    return f"round(floor(({value_expr}) / {3 ** place}) % 3)"


def trinary_layout():
    specs = [(0, "H", "[HOUR_0_23]", 3), (1, "M", "[MINUTE]", 4), (2, "S", "[SECOND]", 4)]
    out = []
    for row_i, label, expr, n in specs:
        cy = ROW_Y[row_i]
        for col in range(n):
            place = n - 1 - col
            cx = C + (col - (n - 1) / 2) * TRI_PITCH
            out.append(dict(x=cx, y=cy, w=TRI_QUAD, place=place, expr=expr,
                             label=label if col == 0 else None, label_x=TRI_LABEL_X, label_y=cy))
    return out


TRI_DECIMAL_ROWS = [("[HOUR_0_23]", ROW_Y[0]), ("[MINUTE]", ROW_Y[1]), ("[SECOND]", ROW_Y[2])]


def wff_tri_decimal_readout():
    out = []
    for expr, cy in TRI_DECIMAL_ROWS:
        x, y = round(TRI_DECIMAL_X - TRI_DECIMAL_W / 2), round(cy - TRI_DECIMAL_H / 2)
        out.append(
            f'        <PartText x="{x}" y="{y}" width="{TRI_DECIMAL_W}" height="{TRI_DECIMAL_H}">\n'
            f'          <Text align="CENTER"><Font family="SYNC_TO_DEVICE" size="26" '
            f'weight="NORMAL" color="{LABEL_COLOR}">\n'
            f'              <Template>%02d<Parameter expression="{expr}"/></Template>\n'
            f'          </Font></Text>\n'
            f'        </PartText>')
    return "\n".join(out)


def wff_tri_labels(layout):
    # Own function, not the shared wff_labels() -- Trinary's label box is
    # genuinely smaller (TRI_LABEL_W/H=30x30 vs the 36x36 every other base
    # uses), part of the clip-fit that made 4 columns work at all.
    out = []
    for c in layout:
        if not c["label"]:
            continue
        x, y = round(c["label_x"] - TRI_LABEL_W / 2), round(c["label_y"] - TRI_LABEL_H / 2)
        out.append(
            f'        <PartText x="{x}" y="{y}" width="{TRI_LABEL_W}" height="{TRI_LABEL_H}">\n'
            f'          <Text align="CENTER"><Font family="SYNC_TO_DEVICE" size="26" '
            f'weight="NORMAL" color="{LABEL_COLOR}">{c["label"].upper()}</Font></Text>\n'
            f'        </PartText>')
    return "\n".join(out)


def wff_tri_outlines(layout, outline_color):
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


def wff_tri_groups(layout, colors):
    out = []
    for c in layout:
        digit_expr = trinary_digit_expr(c["expr"], c["place"])
        r = c["w"] / 2
        bx, by = round(c["x"] - r), round(c["y"] - r)
        style = TRI_RING_STYLES[c["expr"]]
        thickness = r * style["thickness_frac"]
        gap = style["gap"]
        for k, pos in enumerate(TRI_POSITIONS):
            start, end = TRI_ANGLES[pos]
            start, end = start + gap / 2, end - gap / 2
            name = f"y{c['place']}_{round(c['x'])}_{round(c['y'])}_{k}"
            out.append(
                f'      <Condition>\n'
                f'        <Expressions>\n'
                f'          <Expression name="{name}"><![CDATA[(({digit_expr}) > {k})]]></Expression>\n'
                f'        </Expressions>\n'
                f'        <Compare expression="{name}">\n'
                f'          <PartDraw x="{bx}" y="{by}" width="{round(r * 2)}" height="{round(r * 2)}">\n'
                f'            <Arc centerX="{r}" centerY="{r}" width="{r}" height="{r}" '
                f'startAngle="{start}" endAngle="{end}" direction="CLOCKWISE">\n'
                f'              <WeightedStroke colors="{colors[k]}" thickness="{thickness:.2f}" cap="BUTT"/>\n'
                f'            </Arc>\n'
                f'          </PartDraw>\n'
                f'        </Compare>\n'
                f'      </Condition>')
    return "\n".join(out)


def trinary_palette_list_option(option_id: str, layout, theme: str) -> str:
    colors = palette_for(option_id, 2)
    return (f'        <ListOption id="{option_id}">\n'
            f'          <Group name="tri_palette_{option_id}_{theme}" x="0" y="0" width="{CANVAS}" height="{CANVAS}">\n'
            f'{wff_tri_groups(layout, colors)}\n'
            f'          </Group>\n'
            f'        </ListOption>')


def build_base_trinary(theme: str, outline_color: str) -> str:
    layout = trinary_layout()
    palette_options = "\n".join(
        trinary_palette_list_option(opt_id, layout, theme) for opt_id, _res, _anchor in PALETTE_OPTIONS)
    return f"""    <ListOption id="trinary">
      <Group name="trinary_{theme}" x="0" y="0" width="{CANVAS}" height="{CANVAS}">
        <Group name="trinary_outlines_{theme}" x="0" y="0" width="{CANVAS}" height="{CANVAS}">
{wff_tri_outlines(layout, outline_color)}
        </Group>
        <ListConfiguration id="palette">
{palette_options}
        </ListConfiguration>
        <BooleanConfiguration id="labels">
          <BooleanOption id="TRUE">
            <Group name="trinary_labels_{theme}" x="0" y="0" width="{CANVAS}" height="{CANVAS}">
{wff_tri_labels(layout)}
{wff_tri_decimal_readout()}
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
    <ListConfiguration id="base" displayName="cfg_base" defaultValue="binary">
      <ListOption id="binary" displayName="opt_binary"/>
      <ListOption id="trinary" displayName="opt_trinary"/>
      <ListOption id="quaternary" displayName="opt_quaternary"/>
      <ListOption id="quinary" displayName="opt_quinary"/>
      <ListOption id="pentagon" displayName="opt_pentagon"/>
      <ListOption id="hexagon" displayName="opt_hexagon"/>
      <ListOption id="octal" displayName="opt_octal"/>
      <ListOption id="octagon" displayName="opt_octagon"/>
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
{build_base_binary("dark", OFF_DARK)}
{build_base_trinary("dark", OUTLINE_DARK)}
{build_base_quaternary("dark", OUTLINE_DARK)}
{build_base_quinary("dark", OUTLINE_DARK)}
{build_base_pentagon("dark", OUTLINE_DARK)}
{build_base_hexagon("dark", OUTLINE_DARK)}
{build_base_octal("dark", OUTLINE_DARK)}
{build_base_octagon("dark", OUTLINE_DARK)}
          </ListConfiguration>
        </Group>
      </BooleanOption>
      <BooleanOption id="TRUE">
        <Group name="theme_light" x="0" y="0" width="{CANVAS}" height="{CANVAS}">
          <PartDraw x="0" y="0" width="{CANVAS}" height="{CANVAS}">
            <Rectangle x="0" y="0" width="{CANVAS}" height="{CANVAS}"><Fill color="{BG_LIGHT}"/></Rectangle>
          </PartDraw>
          <ListConfiguration id="base">
{build_base_binary("light", OFF_LIGHT)}
{build_base_trinary("light", OUTLINE_LIGHT)}
{build_base_quaternary("light", OUTLINE_LIGHT)}
{build_base_quinary("light", OUTLINE_LIGHT)}
{build_base_pentagon("light", OUTLINE_LIGHT)}
{build_base_hexagon("light", OUTLINE_LIGHT)}
{build_base_octal("light", OUTLINE_LIGHT)}
{build_base_octagon("light", OUTLINE_LIGHT)}
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
      <option value="binary">Binary</option>
      <option value="trinary">Trinary</option>
      <option value="quaternary">Quaternary</option>
      <option value="quinary">Quinary</option>
      <option value="pentagon">Pentagon</option>
      <option value="hexagon">Hexagon</option>
      <option value="octal">Octal</option>
      <option value="octagon">Octagon</option>
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
const PENT_TALLY_BAR_W = 6, PENT_TALLY_BAR_H = 48, PENT_TALLY_GAP = 4, PENT_TALLY_N = 4;
const PENT_TALLY_TOTAL_W = PENT_TALLY_N * PENT_TALLY_BAR_W + (PENT_TALLY_N - 1) * PENT_TALLY_GAP;
const PENT_TALLY_SLASH_LEN = Math.round(Math.hypot(PENT_TALLY_TOTAL_W, PENT_TALLY_BAR_H));
const PENT_TALLY_SLASH_ANGLE = -35;
function pentTallyBarX(k) { return -PENT_TALLY_TOTAL_W / 2 + k * (PENT_TALLY_BAR_W + PENT_TALLY_GAP) + PENT_TALLY_BAR_W / 2; }
const HEX_POSITIONS = ["P0","P1","P2","P3","P4","P5"];
const HEX_ANGLES = Object.fromEntries(HEX_POSITIONS.map((p, i) => [p, [i * 60, (i + 1) * 60]]));
const OCT_POSITIONS = Array.from({length: 8}, (_, i) => "P" + i);
const OCT_ANGLES = Object.fromEntries(OCT_POSITIONS.map((p, i) => [p, [i * 45, (i + 1) * 45]]));
const OCTAGON_LAYOUT = __OCTAGON_LAYOUT_JS__;
const OCT_DECIMAL_X = __OCT_DECIMAL_X__;
const OCT_DECIMAL_ROWS = __OCT_DECIMAL_ROWS_JS__;
const OCTAL_WIFI_BAR_W = 4, OCTAL_WIFI_GAP = 2, OCTAL_WIFI_N = 7, OCTAL_WIFI_MAX_H = 40, OCTAL_WIFI_MIN_H = 14;
const OCTAL_WIFI_TOTAL_W = OCTAL_WIFI_N * OCTAL_WIFI_BAR_W + (OCTAL_WIFI_N - 1) * OCTAL_WIFI_GAP;
const OCTAL_WIFI_STEP = (OCTAL_WIFI_MAX_H - OCTAL_WIFI_MIN_H) / (OCTAL_WIFI_N - 1);
function octalWifiBarGeom(k) {
  const h = OCTAL_WIFI_MAX_H - k * OCTAL_WIFI_STEP;
  const xOff = -OCTAL_WIFI_TOTAL_W / 2 + k * (OCTAL_WIFI_BAR_W + OCTAL_WIFI_GAP) + OCTAL_WIFI_BAR_W / 2;
  return [h, xOff];
}
const TRI_POSITIONS = ["P0","P1"];
const TRI_ANGLES = Object.fromEntries(TRI_POSITIONS.map((p, i) => [p, [i * 180, (i + 1) * 180]]));
const TRINARY_LAYOUT = __TRINARY_LAYOUT_JS__;
const TRI_DECIMAL_X = __TRI_DECIMAL_X__;
const TRI_DECIMAL_ROWS = __TRI_DECIMAL_ROWS_JS__;
const QUAT_POSITIONS = ["P0","P1","P2"];
const QUAT_ANGLES = Object.fromEntries(QUAT_POSITIONS.map((p, i) => [p, [i * 120, (i + 1) * 120]]));
const QUATERNARY_LAYOUT = __QUATERNARY_LAYOUT_JS__;
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
function pentDigit(src, place, now) { return Math.round(Math.floor(value(src, now) / (6 ** place)) % 6); }
function hexDigit(src, place, now) { return Math.round(Math.floor(value(src, now) / (7 ** place)) % 7); }
function octDigit(src, place, now) { return Math.round(Math.floor(value(src, now) / (9 ** place)) % 9); }
function quatDigit(src, place, now) { return Math.round(Math.floor(value(src, now) / (4 ** place)) % 4); }
function octalDigit(src, place, now) { return Math.round(Math.floor(value(src, now) / (8 ** place)) % 8); }
function triDigit(src, place, now) { return Math.round(Math.floor(value(src, now) / (3 ** place)) % 3); }
function polar(cx, cy, r, deg) { const rad = deg * Math.PI / 180; return [cx + r * Math.sin(rad), cy - r * Math.cos(rad)]; }
function wedgePath(cx, cy, r, a0, a1) {
  const [x0, y0] = polar(cx, cy, r, a0), [x1, y1] = polar(cx, cy, r, a1);
  return `M ${cx} ${cy} L ${x0} ${y0} A ${r} ${r} 0 0 1 ${x1} ${y1} Z`;
}
function ringWedgePath(cx, cy, rOuter, rInner, a0, a1) {
  const [x0, y0] = polar(cx, cy, rOuter, a0), [x1, y1] = polar(cx, cy, rOuter, a1);
  const [x0i, y0i] = polar(cx, cy, rInner, a0), [x1i, y1i] = polar(cx, cy, rInner, a1);
  return `M ${x0} ${y0} A ${rOuter} ${rOuter} 0 0 1 ${x1} ${y1} L ${x1i} ${y1i} A ${rInner} ${rInner} 0 0 0 ${x0i} ${y0i} Z`;
}
// Generalizes Quinary's 2x2 corner-squaring trick to any rows x cols grid --
// see the Python-side wff_grid_groups() note for the full "why" (a corner
// stays rounded only when BOTH its adjacent edges are on the true grid
// perimeter). Mirrors that function exactly so the preview matches the
// real WFF output.
function gridGroupSvg(cx, cy, w, h, rows, cols, radius, digit, colors) {
  const cellW = w / cols, cellH = h / rows;
  const bx0 = cx - w / 2, by0 = cy - h / 2;
  let s = "";
  for (let k = 0; k < rows * cols; k++) {
    if (digit <= k) continue;
    const row = Math.floor(k / cols), col = k % cols;
    const bx = bx0 + col * cellW, by = by0 + row * cellH;
    const r = Math.min(radius, cellW / 2, cellH / 2);
    const color = colors[k];
    const keep = {
      TL: row === 0 && col === 0,
      TR: row === 0 && col === cols - 1,
      BL: row === rows - 1 && col === 0,
      BR: row === rows - 1 && col === cols - 1,
    };
    s += `<g transform="translate(${bx},${by})">`;
    s += `<rect x="0" y="0" width="${cellW}" height="${cellH}" rx="${r}" ry="${r}" fill="${color}"/>`;
    const corners = { TL: [0, 0], TR: [cellW - r, 0], BL: [0, cellH - r], BR: [cellW - r, cellH - r] };
    for (const [name, [ox, oy]] of Object.entries(corners)) {
      if (!keep[name]) s += `<rect x="${ox}" y="${oy}" width="${r}" height="${r}" fill="${color}"/>`;
    }
    s += `</g>`;
  }
  return s;
}
function gridOutlineSvg(cx, cy, w, h, outline) {
  const x = cx - w / 2, y = cy - h / 2, r = Math.min(w, h) * 0.1;
  return `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${r}" ry="${r}" fill="none" stroke="${outline}" stroke-width="1.5" stroke-dasharray="3 5" stroke-linecap="round"/>`;
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

function drawPentagon(colors, outline, showLabels, now) {
  // Reuses QUINARY_LAYOUT verbatim -- base 6 has the same (2,3,3) place
  // pattern as base 5 and 7. Tally marks instead of wedges: base 6's digit
  // range (0-5) maps onto the classic tally system -- 4 vertical bars for
  // positions 0-3, a diagonal slash across all 4 for position 4 (lit only
  // at digit=5). The slash is a plain rect rotated via SVG transform here,
  // mirroring the real WFF Group's static pivotX/pivotY/angle attributes.
  let s = "";
  for (const c of QUINARY_LAYOUT) {
    const digit = pentDigit(c.src, c.place, now);
    for (let k = 0; k < PENT_TALLY_N; k++) {
      const bx = c.x + pentTallyBarX(k) - PENT_TALLY_BAR_W / 2;
      const by = c.y - PENT_TALLY_BAR_H / 2;
      const on = digit > k;
      const rx = PENT_TALLY_BAR_W / 2;
      if (on) {
        s += `<rect x="${bx}" y="${by}" width="${PENT_TALLY_BAR_W}" height="${PENT_TALLY_BAR_H}" rx="${rx}" ry="${rx}" fill="${colors[k]}"/>`;
      } else {
        s += `<rect x="${bx}" y="${by}" width="${PENT_TALLY_BAR_W}" height="${PENT_TALLY_BAR_H}" rx="${rx}" ry="${rx}" fill="none" stroke="${outline}" stroke-width="1.5" stroke-dasharray="3 5" stroke-linecap="round"/>`;
      }
    }
    const slashOn = digit > 4;
    const slashRx = PENT_TALLY_BAR_W / 2;
    s += `<g transform="translate(${c.x},${c.y}) rotate(${PENT_TALLY_SLASH_ANGLE})">`;
    if (slashOn) {
      s += `<rect x="${-PENT_TALLY_SLASH_LEN / 2}" y="${-PENT_TALLY_BAR_W / 2}" width="${PENT_TALLY_SLASH_LEN}" height="${PENT_TALLY_BAR_W}" rx="${slashRx}" ry="${slashRx}" fill="${colors[4]}"/>`;
    } else {
      s += `<rect x="${-PENT_TALLY_SLASH_LEN / 2}" y="${-PENT_TALLY_BAR_W / 2}" width="${PENT_TALLY_SLASH_LEN}" height="${PENT_TALLY_BAR_W}" rx="${slashRx}" ry="${slashRx}" fill="none" stroke="${outline}" stroke-width="1.5" stroke-dasharray="3 5" stroke-linecap="round"/>`;
    }
    s += `</g>`;
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

const HEX_GRID_ROWS = {
  "[HOUR_0_23]": { rows: 2, cols: 3, radius: 6 },
  "[MINUTE]": { rows: 3, cols: 2, radius: 999 },
};
function drawHexagon(colors, outline, showLabels, now) {
  // Reuses QUINARY_LAYOUT's x/y/place positions verbatim (base-5 and base-7
  // both need 2 places for H, 3 for M/S -- see the Python-side module note).
  // Hour/Minute now use the generalized grid renderer (2x3/3x2 -- 6 factors
  // cleanly), Second stays the wedge pie.
  let s = "";
  for (const c of QUINARY_LAYOUT) {
    const digit = hexDigit(c.src, c.place, now);
    const gridCfg = HEX_GRID_ROWS[c.src];
    if (gridCfg) {
      s += gridOutlineSvg(c.x, c.y, c.w, c.h, outline);
      s += gridGroupSvg(c.x, c.y, c.w, c.h, gridCfg.rows, gridCfg.cols, gridCfg.radius, digit, colors);
    } else {
      const r = c.w / 2;
      s += `<circle cx="${c.x}" cy="${c.y}" r="${r}" fill="none" stroke="${outline}" stroke-width="1.5" stroke-dasharray="3 5" stroke-linecap="round"/>`;
      HEX_POSITIONS.forEach((pos, k) => {
        if (digit <= k) return;
        const [a0, a1] = HEX_ANGLES[pos];
        s += `<path d="${wedgePath(c.x, c.y, r, a0, a1)}" fill="${colors[k]}"/>`;
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

const OCTAGON_GRID_ROWS = {
  "[HOUR_0_23]": { rows: 2, cols: 4, radius: 4 },
  "[MINUTE]": { rows: 4, cols: 2, radius: 999 },
};
function drawOctagon(colors, outline, showLabels, now) {
  // Own layout, unlike Hexagon -- base 9 only needs 2 places for M/S too
  // (9^2=81 > 59), so Octagon uses a simpler, uniform 2-place-per-row
  // layout centered on the canvas rather than Quinary's asymmetric one.
  // Hour/Minute use the generalized grid renderer (2x4/4x2 -- 8 factors
  // cleanly), Second stays the wedge pie. Octal (drawOctal below) reuses
  // this same layout but is NOT part of this -- 7 doesn't factor cleanly.
  let s = "";
  for (const c of OCTAGON_LAYOUT) {
    const digit = octDigit(c.src, c.place, now);
    const gridCfg = OCTAGON_GRID_ROWS[c.src];
    if (gridCfg) {
      s += gridOutlineSvg(c.x, c.y, c.w, c.h, outline);
      s += gridGroupSvg(c.x, c.y, c.w, c.h, gridCfg.rows, gridCfg.cols, gridCfg.radius, digit, colors);
    } else {
      const r = c.w / 2;
      s += `<circle cx="${c.x}" cy="${c.y}" r="${r}" fill="none" stroke="${outline}" stroke-width="1.5" stroke-dasharray="3 5" stroke-linecap="round"/>`;
      OCT_POSITIONS.forEach((pos, k) => {
        if (digit <= k) return;
        const [a0, a1] = OCT_ANGLES[pos];
        s += `<path d="${wedgePath(c.x, c.y, r, a0, a1)}" fill="${colors[k]}"/>`;
      });
    }
    if (showLabels && c.label) {
      s += `<text x="${c.label_x}" y="${c.label_y + 8}" fill="${LABEL_COLOR}" font-size="26" text-anchor="middle" font-family="system-ui">${c.label.toUpperCase()}</text>`;
    }
  }
  if (showLabels) {
    for (const [src, cy] of OCT_DECIMAL_ROWS) {
      const v = String(Math.round(value(src, now))).padStart(2, "0");
      s += `<text x="${OCT_DECIMAL_X}" y="${cy + 8}" fill="${LABEL_COLOR}" font-size="26" text-anchor="middle" font-family="system-ui">${v}</text>`;
    }
  }
  return s;
}

function drawOctal(colors, outline, showLabels, now) {
  // Reuses OCTAGON_LAYOUT verbatim -- base 8 has the same (2,2,2) place
  // pattern as base 9, so the same geometry works. WiFi bars instead of
  // wedge-pie: 7 independent vertical bars, tallest first (leftmost)
  // decreasing to shortest (rightmost), no rotation needed (unlike
  // Pentagon's tally 5th mark).
  let s = "";
  for (const c of OCTAGON_LAYOUT) {
    const digit = octalDigit(c.src, c.place, now);
    const baselineY = c.y + OCTAL_WIFI_MAX_H / 2;
    for (let k = 0; k < OCTAL_WIFI_N; k++) {
      const [h, xOff] = octalWifiBarGeom(k);
      const bx = c.x + xOff - OCTAL_WIFI_BAR_W / 2;
      const by = baselineY - h;
      const rx = OCTAL_WIFI_BAR_W / 2;
      if (digit > k) {
        s += `<rect x="${bx}" y="${by}" width="${OCTAL_WIFI_BAR_W}" height="${h}" rx="${rx}" ry="${rx}" fill="${colors[k]}"/>`;
      } else {
        s += `<rect x="${bx}" y="${by}" width="${OCTAL_WIFI_BAR_W}" height="${h}" rx="${rx}" ry="${rx}" fill="none" stroke="${outline}" stroke-width="1.5" stroke-dasharray="3 5" stroke-linecap="round"/>`;
      }
    }
    if (showLabels && c.label) {
      s += `<text x="${c.label_x}" y="${c.label_y + 8}" fill="${LABEL_COLOR}" font-size="26" text-anchor="middle" font-family="system-ui">${c.label.toUpperCase()}</text>`;
    }
  }
  if (showLabels) {
    for (const [src, cy] of OCT_DECIMAL_ROWS) {
      const v = String(Math.round(value(src, now))).padStart(2, "0");
      s += `<text x="${OCT_DECIMAL_X}" y="${cy + 8}" fill="${LABEL_COLOR}" font-size="26" text-anchor="middle" font-family="system-ui">${v}</text>`;
    }
  }
  return s;
}

const TRI_RING_STYLES = {
  "[HOUR_0_23]": { thicknessFrac: 1.0, gap: 0 },    // solid pie (unchanged baseline)
  "[MINUTE]": { thicknessFrac: 0.45, gap: 0 },      // thin ring / donut
  "[SECOND]": { thicknessFrac: 0.45, gap: 10 },     // segmented ring
};
function drawTrinary(colors, outline, showLabels, now) {
  // Own layout (TRINARY_LAYOUT) -- base 3 needs 3 places for H, 4 for M/S,
  // wider than any other base, so it doesn't reuse anyone else's geometry.
  // Ring-variant experiment: H stays a solid pie, M becomes a thin ring,
  // S becomes a segmented ring -- same Arc technique, just thickness and
  // angle-gap parameters, no new geometry.
  let s = "";
  for (const c of TRINARY_LAYOUT) {
    const r = c.w / 2;
    s += `<circle cx="${c.x}" cy="${c.y}" r="${r}" fill="none" stroke="${outline}" stroke-width="1.5" stroke-dasharray="3 5" stroke-linecap="round"/>`;
    const digit = triDigit(c.src, c.place, now);
    const style = TRI_RING_STYLES[c.src];
    TRI_POSITIONS.forEach((pos, k) => {
      if (digit <= k) return;
      let [a0, a1] = TRI_ANGLES[pos];
      a0 += style.gap / 2; a1 -= style.gap / 2;
      const path = style.thicknessFrac >= 1.0
        ? wedgePath(c.x, c.y, r, a0, a1)
        : ringWedgePath(c.x, c.y, r, r * (1 - style.thicknessFrac), a0, a1);
      s += `<path d="${path}" fill="${colors[k]}"/>`;
    });
    if (showLabels && c.label) {
      s += `<text x="${c.label_x}" y="${c.label_y + 8}" fill="${LABEL_COLOR}" font-size="26" text-anchor="middle" font-family="system-ui">${c.label.toUpperCase()}</text>`;
    }
  }
  if (showLabels) {
    for (const [src, cy] of TRI_DECIMAL_ROWS) {
      const v = String(Math.round(value(src, now))).padStart(2, "0");
      s += `<text x="${TRI_DECIMAL_X}" y="${cy + 8}" fill="${LABEL_COLOR}" font-size="26" text-anchor="middle" font-family="system-ui">${v}</text>`;
    }
  }
  return s;
}

function drawQuaternary(colors, outline, showLabels, now) {
  // Own layout (QUATERNARY_LAYOUT), not a QUINARY_LAYOUT reuse like Hexagon --
  // base 4's H row needs 3 places same as M/S (unlike Quinary's H, which only
  // needs 2), so every row here uses the QUAD-width/3-place treatment instead
  // of Quinary's narrower 2-place hour bars. Rendered as 3-wedge circles.
  let s = "";
  for (const c of QUATERNARY_LAYOUT) {
    const r = c.w / 2;
    s += `<circle cx="${c.x}" cy="${c.y}" r="${r}" fill="none" stroke="${outline}" stroke-width="1.5" stroke-dasharray="3 5" stroke-linecap="round"/>`;
    const digit = quatDigit(c.src, c.place, now);
    QUAT_POSITIONS.forEach((pos, k) => {
      if (digit <= k) return;
      const [a0, a1] = QUAT_ANGLES[pos];
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
  } else if (base === "trinary") {
    s += drawTrinary(paletteFor(paletteSel.value, 2), OUTLINE[key], showLabels, now);
  } else if (base === "quaternary") {
    s += drawQuaternary(paletteFor(paletteSel.value, 3), OUTLINE[key], showLabels, now);
  } else if (base === "pentagon") {
    s += drawPentagon(paletteFor(paletteSel.value, 5), OUTLINE[key], showLabels, now);
  } else if (base === "hexagon") {
    s += drawHexagon(paletteFor(paletteSel.value, 6), OUTLINE[key], showLabels, now);
  } else if (base === "octal") {
    s += drawOctal(paletteFor(paletteSel.value, 7), OUTLINE[key], showLabels, now);
  } else if (base === "octagon") {
    s += drawOctagon(paletteFor(paletteSel.value, 8), OUTLINE[key], showLabels, now);
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
        "__OCTAGON_LAYOUT_JS__": "[" + ",".join(
            '{x:%.1f,y:%.1f,w:%.1f,h:%.1f,place:%d,src:%s,label:%s,label_x:%s,label_y:%s}' % (
                c["x"], c["y"], c["w"], c["h"], c["place"],
                repr(c["expr"]).replace("'", '"'), (f'"{c["label"]}"' if c["label"] else "null"),
                c["label_x"], c["label_y"])
            for c in octagon_layout()) + "]",
        "__OCT_DECIMAL_X__": str(OCT_DECIMAL_X),
        "__OCT_DECIMAL_ROWS_JS__": "[" + ",".join(f'["{expr}",{cy}]' for expr, cy in OCT_DECIMAL_ROWS) + "]",
        "__TRINARY_LAYOUT_JS__": "[" + ",".join(
            '{x:%.1f,y:%.1f,w:%.1f,place:%d,src:%s,label:%s,label_x:%s,label_y:%s}' % (
                c["x"], c["y"], c["w"], c["place"],
                repr(c["expr"]).replace("'", '"'), (f'"{c["label"]}"' if c["label"] else "null"),
                c["label_x"], c["label_y"])
            for c in trinary_layout()) + "]",
        "__TRI_DECIMAL_X__": str(TRI_DECIMAL_X),
        "__TRI_DECIMAL_ROWS_JS__": "[" + ",".join(f'["{expr}",{cy}]' for expr, cy in TRI_DECIMAL_ROWS) + "]",
        "__QUATERNARY_LAYOUT_JS__": "[" + ",".join(
            '{x:%.1f,y:%.1f,w:%.1f,place:%d,src:%s,label:%s,label_x:%s,label_y:%s}' % (
                c["x"], c["y"], c["w"], c["place"],
                repr(c["expr"]).replace("'", '"'), (f'"{c["label"]}"' if c["label"] else "null"),
                c["label_x"], c["label_y"])
            for c in quaternary_layout()) + "]",
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
