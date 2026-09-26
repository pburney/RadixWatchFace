plugins {
    id("com.android.application")
}

android {
    namespace = "com.burnilab.radixwatchface"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.burnilab.radixwatchface"
        minSdk = 33          // Wear OS 4
        targetSdk = 34
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
