"""Shared helpers, extracted from BinaryWatchFace/QuinaryWatchFace's
near-identical generator code (confirmed near-byte-identical this session
before extracting). Used by every base's renderer so there's one place to
fix a bug in the complication builders, the heart icon, or the clock-value
JS evaluator rather than N copies."""

import math

CANVAS = 450
C = CANVAS / 2

DATE_X, DATE_Y, DATE_W, DATE_H = 125, 382, 200, 36
WIDGET_W, WIDGET_H = 120, 68
WIDGET_Y = 48
WIDGET_MARGIN_X = 98

# Fixed regardless of theme/palette -- same simplification Quinary already
# uses (complications can't reference a ListConfiguration's chosen option as
# a color, and reading a BooleanConfiguration's value from outside its own
# structural branch was never verified safe; a plain fixed tint sidesteps
# both issues entirely).
COMPLICATION_TINT = "#FF808080"


def build_heart_icon(out_path):
    """Rasterize a heart to `out_path` -- WFF's Image loader only handles
    raster drawables, not VectorDrawable XML (confirmed in BinaryWatchFace's
    history). Same parametric heart curve as both sibling projects."""
    from PIL import Image, ImageDraw
    SS, SIZE = 4, 128
    S = SIZE * SS
    pts = []
    for i in range(240):
        t = 2 * math.pi * i / 240
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((x, y))
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    w, h = maxx - minx, maxy - miny
    pad = 0.06
    scale = (1 - 2 * pad) * S / max(w, h)
    ox, oy = (S - w * scale) / 2, (S - h * scale) / 2

    def to_px(x, y):
        return (x - minx) * scale + ox, S - ((y - miny) * scale + oy)

    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(img).polygon([to_px(x, y) for x, y in pts], fill=(255, 255, 255, 255))
    img.resize((SIZE, SIZE), Image.LANCZOS).save(out_path)


def wff_complication_date() -> str:
    return (
        f'    <ComplicationSlot x="{DATE_X}" y="{DATE_Y}" width="{DATE_W}" height="{DATE_H}" '
        f'slotId="3" displayName="slot_date" supportedTypes="SHORT_TEXT EMPTY">\n'
        f'      <DefaultProviderPolicy defaultSystemProvider="DAY_AND_DATE" defaultSystemProviderType="SHORT_TEXT"/>\n'
        f'      <BoundingRoundBox x="0" y="0" width="{DATE_W}" height="{DATE_H}" cornerRadius="8"/>\n'
        f'      <Complication type="SHORT_TEXT">\n'
        f'        <Condition>\n'
        f'          <Expressions>\n'
        f'            <Expression name="date_on"><![CDATA[[COMPLICATION.TEXT] != null]]></Expression>\n'
        f'          </Expressions>\n'
        f'          <Compare expression="date_on">\n'
        f'            <PartText x="0" y="0" width="{DATE_W}" height="{DATE_H}">\n'
        f'              <Text align="CENTER">\n'
        f'                <Font family="SYNC_TO_DEVICE" size="30" weight="NORMAL" color="{COMPLICATION_TINT}">\n'
        f'                  <Template>%s<Parameter expression="[COMPLICATION.TEXT]"/></Template>\n'
        f'                </Font>\n'
        f'              </Text>\n'
        f'            </PartText>\n'
        f'          </Compare>\n'
        f'        </Condition>\n'
        f'      </Complication>\n'
        f'    </ComplicationSlot>')


def wff_complication_heart(x: int) -> str:
    icon = 36
    text_w = WIDGET_W - icon
    return (
        f'    <ComplicationSlot x="{x}" y="{WIDGET_Y}" width="{WIDGET_W}" height="{WIDGET_H}" '
        f'slotId="1" displayName="slot_heart" supportedTypes="SHORT_TEXT EMPTY">\n'
        f'      <DefaultProviderPolicy defaultSystemProvider="HEART_RATE" defaultSystemProviderType="SHORT_TEXT"/>\n'
        f'      <BoundingRoundBox x="0" y="0" width="{WIDGET_W}" height="{WIDGET_H}" cornerRadius="12"/>\n'
        f'      <Complication type="SHORT_TEXT">\n'
        f'        <Condition>\n'
        f'          <Expressions>\n'
        f'            <Expression name="heart_on">'
        f'<![CDATA[[COMPLICATION.TEXT] != null]]></Expression>\n'
        f'          </Expressions>\n'
        f'          <Compare expression="heart_on">\n'
        f'            <PartImage x="0" y="{(WIDGET_H - icon) // 2}" width="{icon}" height="{icon}" '
        f'tintColor="{COMPLICATION_TINT}">\n'
        f'              <Image resource="heart_icon"/>\n'
        f'            </PartImage>\n'
        f'            <PartText x="{icon}" y="0" width="{text_w}" height="{WIDGET_H}">\n'
        f'              <Text align="CENTER" ellipsis="TRUE">\n'
        f'                <Font family="SYNC_TO_DEVICE" size="30" weight="NORMAL" color="{COMPLICATION_TINT}">\n'
        f'                  <Template>%s<Parameter expression="[COMPLICATION.TEXT]"/></Template>\n'
        f'                </Font>\n'
        f'              </Text>\n'
        f'            </PartText>\n'
        f'          </Compare>\n'
        f'        </Condition>\n'
        f'      </Complication>\n'
        f'    </ComplicationSlot>')


def wff_complication_weather(x: int) -> str:
    icon = 36
    text_w = WIDGET_W - icon
    icon_y = (WIDGET_H - icon) // 2
    return (
        f'    <ComplicationSlot x="{x}" y="{WIDGET_Y}" width="{WIDGET_W}" height="{WIDGET_H}" '
        f'slotId="2" displayName="slot_weather" supportedTypes="SHORT_TEXT EMPTY">\n'
        f'      <BoundingRoundBox x="0" y="0" width="{WIDGET_W}" height="{WIDGET_H}" cornerRadius="12"/>\n'
        f'      <Complication type="SHORT_TEXT">\n'
        f'        <Condition>\n'
        f'          <Expressions>\n'
        f'            <Expression name="weather_icon_text"><![CDATA['
        f'[COMPLICATION.TEXT] != null && [COMPLICATION.MONOCHROMATIC_IMAGE] != null]]></Expression>\n'
        f'            <Expression name="weather_text"><![CDATA['
        f'[COMPLICATION.TEXT] != null && [COMPLICATION.MONOCHROMATIC_IMAGE] == null]]></Expression>\n'
        f'          </Expressions>\n'
        f'          <Compare expression="weather_icon_text">\n'
        f'            <PartText x="0" y="0" width="{text_w}" height="{WIDGET_H}">\n'
        f'              <Text align="CENTER" ellipsis="TRUE">\n'
        f'                <Font family="SYNC_TO_DEVICE" size="30" weight="NORMAL" color="{COMPLICATION_TINT}">\n'
        f'                  <Template>%s<Parameter expression="[COMPLICATION.TEXT]"/></Template>\n'
        f'                </Font>\n'
        f'              </Text>\n'
        f'            </PartText>\n'
        f'            <PartImage x="{text_w}" y="{icon_y}" width="{icon}" height="{icon}" tintColor="{COMPLICATION_TINT}">\n'
        f'              <Image resource="[COMPLICATION.MONOCHROMATIC_IMAGE]"/>\n'
        f'            </PartImage>\n'
        f'          </Compare>\n'
        f'          <Compare expression="weather_text">\n'
        f'            <PartText x="0" y="0" width="{WIDGET_W}" height="{WIDGET_H}">\n'
        f'              <Text align="CENTER" ellipsis="TRUE">\n'
        f'                <Font family="SYNC_TO_DEVICE" size="30" weight="NORMAL" color="{COMPLICATION_TINT}">\n'
        f'                  <Template>%s<Parameter expression="[COMPLICATION.TEXT]"/></Template>\n'
        f'                </Font>\n'
        f'              </Text>\n'
        f'            </PartText>\n'
        f'          </Compare>\n'
        f'        </Condition>\n'
        f'      </Complication>\n'
        f'    </ComplicationSlot>')


# JS mirror of WFF's clock-value expressions, for preview.html -- identical
# in both sibling projects, moved here once.
JS_VALUE_FN = r"""function value(src, now) {
  const H = now.getHours(), M = now.getMinutes(), S = now.getSeconds();
  src = src.replaceAll("[HOUR_0_23]", H).replaceAll("[MINUTE]", M).replaceAll("[SECOND]", S);
  src = src.replace(/floor\(([^()]+)\)/g, (_, e) => "Math.floor(" + e + ")");
  return Function('"use strict";return (' + src + ')')();
}"""
