# Radix Watch Face

A Wear OS watch face that counts time in whatever base you pick — every
base from **binary** (2) through **nonary** (9), one app, one settings
picker, instead of a separate app per base. Consolidates
[BinaryWatchFace](https://github.com/pburney/BinaryWatchFace) and
[QuinaryWatchFace](https://github.com/pburney/QuinaryWatchFace) (both kept
public as standalone references, not superseded) plus five more bases
built the same way.

Built entirely from one Python spec — no app code at all. The whole thing
is [Wear OS Watch Face Format](https://developer.android.com/training/wearables/wff)
(WFF): a declarative XML format Android's watch face renderer executes
directly.

**Try it live, no watch required:** [burnilab.com/radix](https://burnilab.com/radix/)

## The eight bases

| base | name | positions | how it reads |
|---|---|---|---|
| 2 | Binary | 1 | raw bits — a row of LEDs, on or off |
| 3 | Trinary | 2 | wedge circle, ring-style: solid pie (H), thin ring (M), segmented ring with a larger hole (S) |
| 4 | Quaternary | 3 | wedge circle |
| 5 | Quinary | 4 | Quinary's original 2×2-grid trick — chunky tile bars (H), a fused rounded blob (M), wedge pie (S) |
| 6 | Senary | 5 | tally marks — 4 vertical bars, a diagonal slash across all 4 for the 5th |
| 7 | Septenary | 6 | chunky tile grid (H), fused blob (M), wedge pie (S) |
| 8 | Octal | 7 | WiFi signal bars — short on the right, growing taller leftward as the digit increases |
| 9 | Nonary | 8 | chunky tile grid (H), fused blob (M), wedge pie (S) |

Every base encodes a digit the same underlying way: **count how many of
`base − 1` positions are lit**. What differs is purely how those positions
are *drawn* — a wedge-split circle, a rectangular grid that fuses into a
rounded blob at full count, a row of vertical bars, or (Senary only) a
literal tally mark. Each base reuses whichever existing layout/rendering
technique its own place-value arithmetic and position count actually match
(checked computationally every time, never assumed) rather than
reinventing geometry per base — see `tools/gen_watchface.py`'s module-level
comments for the specific reasoning behind each one.

## Settings, in on-device editor order

1. **Numeral base** — one of the eight above.
2. **Color scheme** — Rainbow (true ROYGBIV spectral order), Colorblind-safe
   (Okabe-Ito derived), or one of 16 named colors (a monochrome lightness
   ramp built from that color, the color itself sitting near the middle of
   the ramp). All checked against an approximate colorblindness simulation
   before landing here — see `tools/palettes.py`.
3. **Light theme** — background, outlines, and off-state colors invert;
   digit-group colors come entirely from the palette, independent of theme.
4. **Row labels** — also toggles a cheat-mode decimal H/M/S readout next to
   each row, for sanity-checking the reading against the actual time.

Base comes before color on purpose: this app is for people who want to
experiment with different ways of representing time, not primarily to pick
a color scheme.

## How it works

One Python spec → two outputs, same architecture as the sibling projects:

| output | purpose |
|---|---|
| `app/src/main/res/raw/watchface.xml` | the actual Wear OS watch face (WFF v4) |
| `preview.html` | a live browser preview — **no build required** |

```
python3 tools/gen_watchface.py
xdg-open preview.html          # see it now
```

`tools/wff_common.py` holds the complication builders, heart icon
generator, and clock-value JS evaluator shared across the whole family of
sibling projects. `tools/palettes.py` holds all color-scheme generation.
`tools/gen_watchface.py` has one section per base — each documents, in a
comment right above its code, exactly which geometry it reuses from
another base and why (or why it needed its own).

### Real schema constraints worth knowing before touching this file

- **`ListOption` (and `BooleanOption`) can only have one direct child
  element** — confirmed by the offline validator rejecting three siblings
  directly under a `ListOption`. Every option's content is wrapped in
  exactly one `<Group>`.
- **`Group` supports a static rotation** via `pivotX`/`pivotY` (normalized
  [0,1] within its own box) and `angle` (degrees) — used for Senary's tally
  slash. This is a fixed rotation set once at generation time, not an
  expression-driven `Transform` — the right tool when the angle never needs
  to change at runtime.
- **A digit-place's wedge circle takes its radius from its own cell's `w`,
  not its `h`** in every renderer here — a real bug surfaced when Senary's
  Hour cells turned out non-square (112×72), silently ballooning the
  circle to the wrong diameter and overlapping the row below. Fixed with
  `r = min(w, h) / 2`.

## Building and installing

Same toolchain as the sibling projects — see `SETUP.md` for the full
walkthrough (Android Studio SDK, Gradle wrapper, wireless `adb` pairing,
and validating `watchface.xml` offline against Google's WFF schema before
a device round-trip).

```bash
./gradlew :app:assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

Long-press the current face → **+ Add** → pick **Radix**.

## Publishing

Same distribution path as the sibling projects — Google Play (Watch face
category, Play Console account + signed release build + store listing +
privacy policy) and, optionally, F-Droid/IzzyOnDroid: a pure WFF app has no
code, no dependencies, no network, no trackers.

**License:** Apache-2.0 (see `LICENSE`).

## Layout

```
RadixWatchFace/
├── tools/
│   ├── gen_watchface.py        the spec + generator (edit this)
│   ├── palettes.py             color-scheme generation
│   └── wff_common.py           shared complication/helper builders
├── preview.html                generated — open in a browser
├── docs/index.html             privacy policy (GitHub Pages)
├── app/
│   ├── build.gradle.kts
│   └── src/main/
│       ├── AndroidManifest.xml
│       └── res/
│           ├── raw/watchface.xml       generated
│           ├── xml/watch_face_info.xml
│           └── values/strings.xml
├── settings.gradle.kts
├── build.gradle.kts
└── gradle.properties
```
