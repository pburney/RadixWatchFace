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

# ROYGBIV runs red (0 deg) to violet (~270 deg) and deliberately does NOT
# wrap the rest of the way around the wheel back to red -- that remaining
# arc is magenta/pink, which isn't a spectral color (it's what's "missing"
# when you bend a physical rainbow into a closed wheel), so wrapping through
# it would break the red-to-violet spectrum order Paul asked for.
ROYGBIV_START_DEG = 0     # red
ROYGBIV_END_DEG = 270     # violet


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
    """ROYGBIV order, red to violet -- a linear hue sweep across a fixed
    170-degree arc, not a full 360-degree wrap (see ROYGBIV_END_DEG)."""
    out = []
    for i in range(n):
        t = i / (n - 1) if n > 1 else 0.5
        hue = (ROYGBIV_START_DEG + t * (ROYGBIV_END_DEG - ROYGBIV_START_DEG)) / 360
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


def palette_for(option_id: str, n: int, theme: str = "dark") -> list[str]:
    if option_id == "rainbow":
        return rainbow_palette(n)
    if option_id == "colorblind":
        colors = colorblind_palette(n)
        if n > 1:
            # Position 0 is pure white (OKABE_ITO[0]). In DARK theme it's
            # fine against the page background itself, but every
            # multi-color base also draws a dashed group-outline stroke
            # that's ALSO near-white in dark theme (OUTLINE_DARK). Every
            # OTHER color keeps those dashes visibly distinct on top of its
            # fill (a nice "the guide stays faintly visible even when lit"
            # detail); white-on-white nearly vanishes, so the lit cell's
            # corners/edges read as smudged rather than crisp. Real bug,
            # caught by Paul testing multiple bases on-device, not a
            # screenshot artifact -- the module docstring already flagged
            # this exact weak spot (ensure_contrast() below was written for
            # single-color Binary only) without yet fixing it for the
            # multi-color case. Forcing black gives the white dashes the
            # same clean contrast every other color already gets for free.
            #
            # LIGHT theme has the mirror-image problem, worse: the page
            # background itself (BG_LIGHT) is pure white, so position 0 is
            # simply invisible, not just blended at the edges -- caught by
            # checking this fix's own light-theme case before shipping,
            # same discipline as everywhere else in this project. Black
            # doesn't work here (OUTLINE_LIGHT is near-black, so black would
            # just recreate the identical blend-with-the-outline problem in
            # the other direction) -- a neutral gray, the same lightness
            # target ensure_contrast() already uses for light theme (0.35),
            # is visible against both the white background and the dark
            # outline.
            #
            # n>1 guard keeps this from ever touching Binary's own n=1
            # call, which goes through ensure_contrast() instead and has no
            # outline to blend with either way.
            colors = [("#FF000000" if theme == "dark" else "#FF595959")] + colors[1:]
        return colors
    return monochrome_palette(ANCHOR_ARGB[option_id], n)


def ensure_contrast(argb: str, theme: str) -> str:
    """For bases with only ONE color (Binary) there's no dashed outline or
    neighboring different-colored block to fall back on, so a color that's
    too close to the background is genuinely invisible, not just subtle --
    caught by actually looking at a screenshot: Colorblind-safe's first
    color is pure white (OKABE_ITO[0], chosen to match Quinary's own
    TR position), which nearly vanishes against light theme's white
    background. Clamps lightness away from the background's own lightness,
    preserving hue/saturation -- a saturated color keeps its hue at a
    different lightness; white/gray (s=0) simply becomes a mid-gray, which
    is exactly the legible "on" dot light theme needs. Only ever used for
    single-color bases; multi-color groups have the dashed outline plus
    neighboring colors as legibility anchors -- except position 0's own
    white-on-white blend with the outline itself in dark theme, which
    turned out to be real (Paul caught it on-device across multiple bases)
    and is now handled directly in palette_for(), not here."""
    r, g, b = _hex_to_rgb01(argb)
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    if theme == "light" and l > 0.75:
        l = 0.35
    elif theme == "dark" and l < 0.20:
        l = 0.65
    else:
        return argb
    return _rgb01_to_argb_hex(colorsys.hls_to_rgb(h, l, s))
