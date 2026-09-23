plugins {
    alias(libs.plugins.android.application)
}

android {
    enableKotlin = false
    namespace = "dev.j256.binarywatchface.history"
    compileSdk = 37

    defaultConfig {
        applicationId = "dev.j256.binarywatchface.history"
        minSdk = 37
        targetSdk = 37
        versionCode = 1
        versionName = "0.1.0-prototype"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"))
        }
    }

    lint {
        abortOnError = true
        checkReleaseBuilds = true
    }
}

dependencies {
    implementation(libs.health.services)
    implementation(libs.watchface.complications)
    implementation(libs.guava)
    testImplementation(libs.junit)
    androidTestImplementation(libs.android.test.runner)
    androidTestImplementation(libs.android.test.junit)
    androidTestImplementation(libs.health.services.proto)
}
