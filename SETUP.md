# Android dev environment setup (Toussaint)

Identical toolchain to [BinaryWatchFace](https://github.com/pburney/BinaryWatchFace)
and [QuinaryWatchFace](https://github.com/pburney/QuinaryWatchFace) — same
machine, same SDK.

**Android Studio** (`~/bin/android-studio`) provisioned `~/Android/Sdk` —
platform `android-37.0`, build-tools `36.0.0`, `platform-tools` (`adb`).
`local.properties` (gitignored) points at it:
```
sdk.dir=/home/developer/Android/Sdk
```

**Gradle wrapper is committed** (`./gradlew`, `gradle/wrapper/`, pinned to
8.9) — no manual Gradle install needed.

## Build

```bash
cd /data/BUSINESS/Burnilab/RadixWatchFace
./gradlew :app:assembleDebug
# -> app/build/outputs/apk/debug/app-debug.apk
```

## Install on the Pixel Watch (wireless — no USB port)

```bash
ADB=/home/developer/Android/Sdk/platform-tools/adb
$ADB pair <watch-ip>:<pair-port>      # 6-digit code shown on watch
$ADB devices -l
$ADB install -r app/build/outputs/apk/debug/app-debug.apk
```
On the watch: long-press the current face -> **+ Add** -> **Radix**.

**Wireless adb is flaky in practice on this watch** — if a connection drops,
`adb kill-server && adb start-server && adb mdns services` usually
rediscovers it; if `adb connect` still fails, the pairing itself has gone
stale and needs a fresh `Settings -> Developer options -> Wireless
debugging -> Pair new device` code, not just a reconnect.

## Validating watchface.xml offline

Same validator as the sibling projects:
```bash
git clone --depth 1 https://github.com/google/watchface.git /tmp/wff-validator-src
cd /tmp/wff-validator-src/third_party/wff/specification/validator
mkdir out
javac -cp "$(find libs -name '*.jar' | tr '\n' ':')" -d out $(find src/main -name '*.java')
(cd ../documents && zip -qr ../validator/out/docs.zip .)
java -cp "$(find libs -name '*.jar' | tr '\n' ':')out" \
  com.samsung.watchface.DWFValidationApplication 4 \
  /data/BUSINESS/Burnilab/RadixWatchFace/app/src/main/res/raw/watchface.xml
```

## Gotchas confirmed (or re-confirmed) building this one

Everything the sibling projects' `SETUP.md` documents applies unchanged
(`watch_face_info.xml` required, `alpha` can't take a conditional
expression, `ComplicationSlot` must be a direct `<Scene>` child, Scene
paints in document order). New ground specific to Radix's multi-config
architecture:

- **`ListConfiguration`/`ListOption` is real and structurally equivalent to
  `BooleanConfiguration`/`BooleanOption`** — confirmed directly from the WFF
  XSD (`group/groupElement.xsd`'s `ListConfiguration` include,
  `userConfiguration/userConfigurationsElement.xsd` for the declarative
  form), not just documentation prose. `<Scene>` accepts `ListConfiguration`
  as a direct child the same way it accepts `BooleanConfiguration`.
- **`ListOption` (like `BooleanOption`) permits exactly ONE direct child
  element** — the validator rejected three siblings (a `Group`, a
  `ListConfiguration`, a `BooleanConfiguration`) directly under one
  `ListOption` on the first real attempt here. Fix: wrap everything in one
  `<Group>`, same convention both sibling projects already use for
  `BooleanOption`.
- **A `ListConfiguration`'s chosen value is a string option id, not a
  resolvable color** — unlike `ColorConfiguration`'s `[CONFIGURATION.id]`,
  which directly resolves to the picked color. This is why complications
  and the outline/label colors use a fixed neutral tint here rather than
  trying to reference the palette selection directly (same simplification
  QuinaryWatchFace already used for theme-driven complication tinting).
