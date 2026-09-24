# Radix Watch Face

The unified numeral-base watch face family — one app, one base picker,
instead of a separate app per number base. Consolidates
[BinaryWatchFace](https://github.com/pburney/BinaryWatchFace) and
[QuinaryWatchFace](https://github.com/pburney/QuinaryWatchFace) (both kept
public as standalone references, not superseded) and is where base-6/7/9
and beyond will land as they're built.

## Settings, in on-device editor order

1. **Color scheme** — Rainbow (fixed, anchor-independent hue wheel),
   Colorblind-safe (Okabe-Ito derived), or one of 16 named colors (a
   monochrome lightness ramp built from that color, the color itself sitting
   near the middle of the ramp). All spiked and checked against an
   approximate colorblindness simulation before landing here — see
   `tools/palettes.py`'s docstring and the RADIX ticket for the writeup.
2. **Numeral base** — currently Quinary (base 5); Binary and the wedge-based
   bases (6/7/9) follow the same pattern once ported in.
3. **Light theme** — background only; digit-group colors come entirely from
   the palette now, independent of theme.
4. **Row labels** — also toggles the cheat-mode decimal H/M/S readout.

## How it works

One Python spec, two outputs — same architecture as the sibling projects:

| output | purpose |
|---|---|
| `app/src/main/res/raw/watchface.xml` | the actual Wear OS watch face (WFF v4) |
| `preview.html` | a live browser preview — **no build required** |

```
python3 tools/gen_watchface.py
xdg-open preview.html          # see it now
```

`tools/wff_common.py` holds the complication builders, heart icon generator,
and clock-value JS evaluator shared with the sibling projects (extracted
after confirming they were near-byte-identical across both). `tools/
palettes.py` holds the color-scheme generation. `tools/gen_watchface.py`
itself currently has Quinary's geometry ported in directly; as more bases
land, expect this to split into one module per base behind a small shared
interface (see the RADIX ticket / project plan for the intended shape).

### A real schema constraint worth knowing before touching this file

`ListOption` (and `BooleanOption`) can only have **one direct child
element** — confirmed by the offline validator rejecting three siblings
directly under a `ListOption` on the first attempt here. Every option's
content has to be wrapped in exactly one `<Group>`, same as both sibling
projects already do for `BooleanOption`.

## Building and installing

Same toolchain as the sibling projects — see `SETUP.md`.

```bash
./gradlew :app:assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

Long-press the current face → **+ Add** → pick **Radix**.

## Status

Active development. First complete base (Quinary) wired to the new
palette/base/theme/labels config architecture, offline-validated and
preview-confirmed; on-device install pending (watch unreachable as of this
commit). Not yet open-sourced or submitted anywhere — see
`RADIX-2026-0924-UnifiedAppFoundation` in the `bws` graph for status.
