// Root build file. AGP 8.5+ needs JDK 17+ (you have 21).
// 2026-09: bumped 8.5.2 -> 8.7.3 -- 8.5.2's bundled SDK tooling only
// understands SDK repository XML schema up to version 3, but the locally
// installed android-37.0 platform uses schema version 4, so compileSdk=37
// (needed for Play's minSdk>=36 requirement, since only 34 and 37.0 are
// installed) failed with "Failed to find Platform SDK" even though the
// directory exists.
plugins {
    id("com.android.application") version "8.7.3" apply false
}
