# Repository guidance

This repository contains a resource-only Wear OS watch face implemented with Watch Face Format. Keep `android:hasCode="false"` and do not add executable Android code unless the product architecture is explicitly reconsidered.

Use `./gradlew check assembleDebug bundleRelease` for the normal project checks. Run the official WFF validator and memory evaluator before a release checkpoint.

Use Conventional Commits. Never push or publish without explicit approval.
