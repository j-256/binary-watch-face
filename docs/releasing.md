# Release process

Local checkpoints, GitHub releases, and Google Play releases are independent operations. A local commit or tag does not authorize a push or publication. Keep automation for these phases in separate commands, with explicit version and artifact inputs, read-only preflight checks, and no implicit handoff to the next phase.

## Local checkpoint

Increase `versionCode` and `versionName` in `watchface/build.gradle.kts`, update the release notes, and complete the checks in the [verification guide](../README.md#verification). Confirm the generated WFF is packaged in the artifacts and retain `android:hasCode="false"`.

Commit the reviewed changes and create an annotated version tag. Preserve the corresponding artifacts and their SHA-256 checksums outside regenerable build directories before continuing development. Label debug APKs and unsigned bundles explicitly; neither is a Play-signed distribution artifact. Record known limitations of a preserved baseline rather than treating a checkpoint as proof of release readiness.

## Google Play closed beta

Use the existing application and closed-testing track. Before building an upload, inspect Play Console for the highest uploaded version code and any pending release. An uploaded version code cannot be reused. Do not discard a pending release or change the tester audience as an incidental part of publishing an update.

Build the AAB using the configured upload key, following the [signing instructions](../README.md#play-release-signing). Verify the upload certificate, version, package identity, and checksums. Create a release in the existing closed-testing track, upload the bundle, add release notes, and review the complete release before submitting it for review and rollout. Preserve the tester group and opt-in link.

An update within closed testing remains a beta release. Production access is a separate application and approval process. Google encourages fixing issues during closed testing; tester opt-in continuity and engagement matter to the production-access requirements. See [testing requirements](https://support.google.com/googleplay/android-developer/answer/14151465?hl=en) and [preparing a release](https://support.google.com/googleplay/android-developer/answer/9859348?hl=en).

Play automation must target the closed-testing track explicitly and distinguish preparing a draft from submitting or rolling out a release. Production promotion requires its own explicit operation and authorization.

## GitHub prerelease

Publish the reviewed source tag and create a GitHub prerelease with release notes and installation guidance. Use a universal APK exported from Google Play so it carries the same app-signing certificate as the Play-installed app, plus its checksum. See [Play App Signing and alternative distribution](https://support.google.com/googleplay/android-developer/answer/9842756?hl=en). Do not substitute a debug APK or an APK signed only with the upload key.

GitHub publication does not alter the Play track or enroll downloaders as Play testers. When publishing on both services, obtain and verify the Play-signed APK before attaching it to the GitHub prerelease. Verify the final release assets and prerelease status after publication.
