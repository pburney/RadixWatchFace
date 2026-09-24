"""Palette generation, spiked and colorblind-checked in scratch work before
landing here (spike_colors.py) -- see project_watchface_distribution.md /
the RADIX ticket for the full writeup. Three families, selectable by the
user via a single 18-option ListConfiguration:

  - "rainbow":     fixed, anchor-independent -- N evenly-spaced hues
                   starting at a constant reference angle.
  - "colorblind":  the original Quinary Okabe-Ito-derived palette, extended
                   to more positions by appending further Okabe-Ito-safe
                   hues in the same spirit.
  - one of the 16 named anchor colors (BinaryWatchFace's original LED-color
    list) -- a monochrome ramp of N lightness steps around that anchor's
    own hue, the anchor sitting near the middle of the ramp.

All produce ARGB hex strings ("#FFRRGGBB", WFF's color format), computed
once at generation time in Python -- WFF has no runtime color math, so
every (base, palette) combination's actual colors are baked into the
generated XML as literal Fill/WeightedStroke values, picked via structural
Condition/ListOption branching, not computed on-device.
"""

import colorsys

# BinaryWatchFace's original 16-option LED color list (tools/gen_watchface.py
# ON_OPTS), reused here as the anchor list for monochrome ramps.
ANCHOR_COLORS = [
    ("green", "Green", "#FF33FF66"),
    ("emerald", "Emerald", "#FF00C853"),
    ("teal", "Teal", "#FF1DE9B6"),
    ("cyan", "Cyan", "#FF33E1FF"),
    ("blue", "Blue", "#FF33B5FF"),
    ("indigo", "Indigo", "#FF5C6BC0"),
    ("violet", "Violet", "#FF9B7BFF"),
    ("purple", "Purple", "#FFC061FF"),
    ("magenta", "Magenta", "#FFFF5CD2"),
    ("pink", "Pink", "#FFFF6EA6"),
    ("red", "Red", "#FFFF5A5A"),
    ("orange", "Orange", "#FFFF9E42"),
    ("amber", "Amber", "#FFFFC24B"),
    ("yellow", "Yellow", "#FFFFE14D"),
    ("olive", "Olive", "#FF8C8F5A"),
    ("white", "White", "#FFF5F5F5"),
]

# Okabe-Ito colorblind-safe set (the original 4 Quinary used, plus 4 more
# from the same standard 8-color Okabe-Ito palette, in the order it's
# usually presented -- extends cleanly to any N up to 8 without inventing
# new hues that haven't been vetted for color-vision deficiencies).
OKABE_ITO = [
    "#FFFFFFFF",  # white (Quinary's TR)
    "#FF56B4E9",  # sky blue (Quinary's TL)
    "#FFE69F00",  # orange (Quinary's BL)
    "#FF009E73",  # bluish green (Quinary's BR)
    "#FFF0E442",  # yellow
    "#FF0072B2",  # blue
    "#FFD55E00",  # vermillion
    "#FFCC79A7",  # reddish purple
]

RAINBOW_START_DEG = 140   # arbitrary fixed reference angle (a green-ish
                          # start), chosen only so "rainbow" isn't identical
                          # to any one anchor's hue by coincidence


def _hex_to_rgb01(h):
    h = h.lstrip("#")
    if len(h) == 8:   # ARGB -> drop alpha
        h = h[2:]
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _rgb01_to_argb_hex(rgb):
    r, g, b = (max(0, min(255, round(c * 255))) for c in rgb)
    return f"#FF{r:02X}{g:02X}{b:02X}"


def monochrome_palette(anchor_argb: str, n: int) -> list[str]:
    r, g, b = _hex_to_rgb01(anchor_argb)
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    lo, hi = 0.28, 0.82
    out = []
    for i in range(n):
        t = i / (n - 1) if n > 1 else 0.5
        lightness = lo + t * (hi - lo)
        out.append(_rgb01_to_argb_hex(colorsys.hls_to_rgb(h, lightness, s)))
    return out


def rainbow_palette(n: int) -> list[str]:
    out = []
    for i in range(n):
        hue = ((RAINBOW_START_DEG / 360) + i / n) % 1.0
        out.append(_rgb01_to_argb_hex(colorsys.hls_to_rgb(hue, 0.55, 0.85)))
    return out


def colorblind_palette(n: int) -> list[str]:
    if n <= len(OKABE_ITO):
        return OKABE_ITO[:n]
    # more positions than the vetted set has entries -- repeat rather than
    # invent unvetted colors (shouldn't happen for any base planned so far;
    # base-9 needs 8, exactly the full set).
    return [OKABE_ITO[i % len(OKABE_ITO)] for i in range(n)]


# id, display-string-resource-name, generator-function-or-None(anchor used instead)
PALETTE_OPTIONS = (
    [("rainbow", "palette_rainbow", None), ("colorblind", "palette_colorblind", None)]
    + [(anchor_id, f"palette_{anchor_id}", anchor_id) for anchor_id, _name, _argb in ANCHOR_COLORS]
)
ANCHOR_ARGB = {aid: argb for aid, _name, argb in ANCHOR_COLORS}


def palette_for(option_id: str, n: int) -> list[str]:
    if option_id == "rainbow":
        return rainbow_palette(n)
    if option_id == "colorblind":
        return colorblind_palette(n)
    return monochrome_palette(ANCHOR_ARGB[option_id], n)
