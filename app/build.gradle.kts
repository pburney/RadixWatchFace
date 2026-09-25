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
            isMinifyEnabled = false
        }
    }
}
// No dependencies: a pure Watch Face Format package has no code.
