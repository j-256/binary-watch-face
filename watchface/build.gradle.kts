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
    namespace = "dev.j256.binarywatchface"
    compileSdk = 37

    defaultConfig {
        applicationId = "dev.j256.binarywatchface"
        minSdk = 37
        targetSdk = 37
        versionCode = 2
        versionName = "0.2.0"
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
            isShrinkResources = false
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
