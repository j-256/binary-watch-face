plugins {
    alias(libs.plugins.android.application)
}

val releaseStoreFileEnvironment = "BINARY_WATCH_FACE_UPLOAD_STORE_FILE"
val releasePasswordEnvironment = "BINARY_WATCH_FACE_UPLOAD_PASSWORD"
val releaseKeyAlias = "upload"
val releaseStoreFile = providers.environmentVariable(releaseStoreFileEnvironment).orNull?.takeIf(String::isNotBlank)
val releasePassword = providers.environmentVariable(releasePasswordEnvironment).orNull?.takeIf(String::isNotBlank)
val releaseSigningConfigured = releaseStoreFile != null && releasePassword != null

check((releaseStoreFile == null) == (releasePassword == null)) {
    "Set both $releaseStoreFileEnvironment and $releasePasswordEnvironment, or neither"
}

android {
    enableKotlin = false
    namespace = "dev.j256.binarywatchface.history"
    compileSdk = 37

    defaultConfig {
        applicationId = "dev.j256.binarywatchface.history"
        minSdk = 37
        targetSdk = 37
        versionCode = 5
        versionName = "0.3.1-prototype"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    signingConfigs {
        if (releaseSigningConfigured) {
            create("release") {
                storeFile = rootProject.file(requireNotNull(releaseStoreFile))
                storePassword = releasePassword
                keyAlias = releaseKeyAlias
                keyPassword = releasePassword
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"))
            if (releaseSigningConfigured) {
                signingConfig = signingConfigs.getByName("release")
            }
        }
    }

    lint {
        abortOnError = true
        checkReleaseBuilds = true
    }
}

dependencies {
    implementation(libs.android.core)
    implementation(libs.health.services)
    implementation(libs.watchface.complications)
    implementation(libs.guava)
    testImplementation(libs.junit)
    androidTestImplementation(libs.android.test.runner)
    androidTestImplementation(libs.android.test.junit)
    androidTestImplementation(libs.health.services.proto)
}
