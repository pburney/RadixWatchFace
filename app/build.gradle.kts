plugins {
    id("com.android.application")
}

android {
    namespace = "com.burnilab.radixwatchface"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.burnilab.radixwatchface"
        // Play's own upload check: "Your Watch Face Format XML includes
        // the features: 'WeightedStroke under Arc, Default heart rate
        // complication'. Based on this, you're required to update your
        // manifest so that the APK or Android App Bundle specifies a
        // min_sdk of at least 36." Real error from an actual submission,
        // not documentation -- those two specific features (used
        // throughout every wedge-split-circle base, and the heart rate
        // complication slot) apparently require a newer WFF runtime than
        // minSdk=33 declares. Bumped straight to 36, Play's stated floor.
        minSdk = 36
        targetSdk = 36
        versionCode = 1
        versionName = "1.0"
    }

    buildTypes {
        release {
            // Play rejects any watch face release bundle containing a dex
            // file at all (confirmed 2025-01-27 per Play's own upload
            // error) -- with isMinifyEnabled=false, AGP still packages a
            // near-empty dex (auto-generated R/BuildConfig stubs) even
            // though there's zero real source (hasCode="false" in the
            // manifest doesn't suppress this). Google's own sample-wf
            // reference project (google/watchface repo) enables R8
            // shrinking specifically to strip that down to nothing.
            isMinifyEnabled = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"))
        }
    }
}
// No dependencies: a pure Watch Face Format package has no code.
