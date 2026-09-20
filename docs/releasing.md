# Release process

Local checkpoints, GitHub releases, and Google Play releases are independent operations. A local commit or tag does not authorize a push or publication. Keep automation for these phases in separate commands, with explicit version and artifact inputs, read-only preflight checks, and no implicit handoff to the next phase.

`python3 tools/release.py --help` describes the independent release commands. Each supports `--dry-run`; none pushes Git refs or submits a Play release. The GitHub command publishes only prereleases. Results are JSON on stdout, with errors on stderr and exit statuses documented in help.

## Local checkpoint

Increase `versionCode` and `versionName` in `watchface/build.gradle.kts`, update the release notes, and complete the checks in the [verification guide](../README.md#verification). Confirm the generated WFF is packaged in the artifacts and retain `android:hasCode="false"`.

Commit the reviewed changes and create an annotated version tag. Preserve the corresponding artifacts and their SHA-256 checksums outside regenerable build directories before continuing development. Label debug APKs and unsigned bundles explicitly; neither is a Play-signed distribution artifact. Record known limitations of a preserved baseline rather than treating a checkpoint as proof of release readiness.

After completing the Android build, tests, official WFF validation, memory evaluation, and device checks, use:

```sh
python3 tools/release.py tag 0.4.0 --dry-run
python3 tools/release.py tag 0.4.0
```

The tag command requires a clean worktree and matching source version, rechecks generated XML and layout clearances, and refuses to move an existing tag. It does not repeat the full release verification. Push `main` and the explicit tag only when publication is authorized.

## Google Play closed beta

Use the existing application and closed-testing track. Before building an upload, inspect Play Console for the highest uploaded version code and any pending release. An uploaded version code cannot be reused. Do not discard a pending release or change the tester audience as an incidental part of publishing an update.

Build the AAB using the configured upload key, following the [signing instructions](../README.md#play-release-signing). Verify the upload certificate, version, package identity, and checksums. Create a release in the existing closed-testing track, upload the bundle, add release notes, and review the complete release before submitting it for review and rollout. Preserve the tester group and opt-in link.

Archive the signed bundle with the upload certificate's SHA-256 fingerprint from Play Console's app-signing settings. Download the official [bundletool JAR](https://github.com/google/bundletool/releases) and verify its published checksum first. Set `JAVA_HOME` to JDK 17, or put its tools on `PATH`.

```sh
python3 tools/release.py prepare-play 0.4.0 \
    --bundle watchface/build/outputs/bundle/release/watchface-release.aab \
    --bundletool /path/to/bundletool-all.jar \
    --certificate-sha256 "$UPLOAD_CERT_SHA256" \
    --output /path/to/new-release-directory
```

This command verifies the JAR signature and upload certificate, checks the compiled manifest, rejects executable code, and compares the packaged WFF with the annotated tag. It writes the AAB, checksums, and a verification receipt to a new directory. The JDK's certificate-warning status is accepted for the explicitly trusted upload certificate; unsigned entries and other signature failures are rejected. Use Play Console to confirm the upload certificate remains valid and accepted before preparing a release.

Uploading, selecting the Wear OS closed-testing track, reviewing the tester audience and rollout, and submitting for review remain explicit Play Console steps. Use the listing copy and ordered assets in [the store listing guide](store/README.md) when the product presentation changes. A saved release is not a submitted release: verify Publishing overview shows the changes in review, and distinguish that state from availability to testers. Leave unrelated drafts untouched. Add API submission automation only with a configured publishing identity and an explicit closed-track target.

An update within closed testing remains a beta release. Production access is a separate application and approval process. Google encourages fixing issues during closed testing; tester opt-in continuity and engagement matter to the production-access requirements. See [testing requirements](https://support.google.com/googleplay/android-developer/answer/14151465?hl=en) and [preparing a release](https://support.google.com/googleplay/android-developer/answer/9859348?hl=en).

Play automation must target the closed-testing track explicitly and distinguish preparing a draft from submitting or rolling out a release. Production promotion requires its own explicit operation and authorization.

## GitHub prerelease

Publish the reviewed source tag and create a GitHub prerelease with release notes and installation guidance. Use a universal APK exported from Google Play so it carries the same app-signing certificate as the Play-installed app, plus its checksum. See [Play App Signing and alternative distribution](https://support.google.com/googleplay/android-developer/answer/9842756?hl=en). Do not substitute a debug APK or an APK signed only with the upload key.

GitHub publication does not alter the Play track or enroll downloaders as Play testers. When publishing on both services, obtain and verify the Play-signed APK before attaching it to the GitHub prerelease. Verify the final release assets and prerelease status after publication.

Download the **Signed, universal APK** from the uploaded version's **Downloads** tab under **Latest releases and bundles**. Use the Play app-signing certificate fingerprint, which differs from the upload certificate used for the AAB.

```sh
python3 tools/release.py github 0.4.0 \
    --apk /path/to/play-exported.apk \
    --build-tools "$ANDROID_HOME/build-tools/36.0.0" \
    --certificate-sha256 "$PLAY_CERT_SHA256" \
    --notes docs/releases/0.4.0.md \
    --dry-run
```

Remove `--dry-run` for an authorized publication. The command verifies the APK signature, package, version, resource-only manifest, and exact WFF against the tag; confirms the remote annotated tag; and refuses to replace an existing release. It creates a draft with canonical APK and checksum filenames, verifies GitHub's asset digests, and publishes the prerelease only after those checks pass. If upload verification fails, inspect the remaining draft before retrying. The command targets `j-256/binary-watch-face` explicitly and never creates or pushes a remote tag.
