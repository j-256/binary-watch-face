plugins {
    alias(libs.plugins.android.application)
}

val releaseStoreFileEnvironment = "BINARY_WATCH_FACE_UPLOAD_STORE_FILE"
val releasePasswordEnvironment = "BINARY_WATCH_FACE_UPLOAD_PASSWORD"
val releaseKeyAlias = "upload"
val prototypeVersionCode = 6
val prototypeVersionNameSuffix = "-history-prototype.2"
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
        versionCode = 4
        versionName = "0.4.0"
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
        create("prototype") {
            initWith(getByName("debug"))
            applicationIdSuffix = ".prototype"
            versionNameSuffix = prototypeVersionNameSuffix
            matchingFallbacks += listOf("debug")
        }
        create("screenshot") {
            initWith(getByName("debug"))
            applicationIdSuffix = ".screenshot"
            versionNameSuffix = "-screenshot"
            matchingFallbacks += listOf("debug")
        }
        release {
            isMinifyEnabled = true
            isShrinkResources = false
            if (releaseSigningConfigured) {
                signingConfig = signingConfigs.getByName("release")
            }
        }
        create("prototypeRelease") {
            initWith(getByName("release"))
            applicationIdSuffix = ".prototype"
            versionNameSuffix = prototypeVersionNameSuffix
        }
    }

    sourceSets.getByName("prototypeRelease").res.srcDir("src/prototype/res")

    lint {
        abortOnError = true
        checkReleaseBuilds = true
    }
}

androidComponents {
    listOf("prototype", "prototypeRelease").forEach { buildType ->
        onVariants(selector().withBuildType(buildType)) { variant ->
            variant.outputs.forEach { output ->
                output.versionCode.set(prototypeVersionCode)
            }
        }
    }
}
