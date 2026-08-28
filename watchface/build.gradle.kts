plugins {
    alias(libs.plugins.android.application)
}

android {
    enableKotlin = false
    namespace = "com.j256.binarywatchface"
    compileSdk = 37

    defaultConfig {
        applicationId = "com.j256.binarywatchface"
        minSdk = 33
        targetSdk = 37
        versionCode = 1
        versionName = "0.1.0"
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = false
        }
    }

    lint {
        abortOnError = true
        checkReleaseBuilds = true
    }
}
