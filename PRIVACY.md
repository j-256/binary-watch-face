# Privacy Policy

Effective date: 2026-09-23

Binary Watch Face, shown as **Binary** on Wear OS, is developed and published by **j-256**. This policy describes how Binary handles user and device data.

## Data collection and sharing

Binary does not collect, store, share, sell, or transmit personal or sensitive user data. It has no executable Android code, network access, analytics, advertising, account system, or data-collection permissions.

**Binary Heart History** is an optional, separate prototype application. After explicit heart-rate and background-access permission, it records passive heart-rate readings locally on the watch and supplies a graph to the selected watch face. It has no network permission, account, advertising, analytics, cloud backup, or device-transfer backup. Neither application sends readings to the developer.

## On-device information

Wear OS supplies time, battery, heart rate, and user-selected complication data for local display on the watch. Binary Watch Face does not retain or transmit that data. A complication provider selected by the user is a separate application or system service and is governed by its own privacy practices.

Binary Heart History stores reading timestamps and beats per minute in its private on-watch database, with at most one reading per second. Its graph shows a selected window within the preceding 24 hours. Preview mode uses clearly labeled invented readings and pauses recording without adding sample data to the database. Diagnostic messages contain operation identifiers, outcomes, timings, and sample counts, but no heart-rate values or reading timestamps.

## Optional beta group

Testers may voluntarily join the [Binary Watch Face Testers Google Group](https://groups.google.com/g/binary-watch-face-testers) to become eligible for the Google Play closed beta. Google records the membership and makes the member's Google Account email address and profile information available to the group owner. This information is used only to administer beta access. Posting, conversations, and the member list are restricted to the group owner. Google Groups is governed by Google's own privacy practices.

## Retention and deletion

Binary does not collect or retain user data, so it has no app data to retain or delete. Watch-face settings are managed locally by Wear OS. Optional beta-group membership remains until the tester leaves the group or the group owner removes the membership.

Binary Heart History removes readings outside the 24-hour window when it receives, reads, or maintains history. Background maintenance is requested every six hours and is scheduled by Wear OS; force-stopping the app can delay deletion until it runs again. **Stop and erase history** stops recording and deletes the stored readings. Permission-loss handling also disables recording and clears stored readings. Uninstalling Binary Heart History removes its app data.

Wear OS receives the rendered graph as complication data and may cache that image. The provider requests a refresh after stopping, erasing, or changing preview mode, and limits each image's display validity to ten minutes. This does not promise immediate erasure of system-owned image caches. Removing the graph layout or uninstalling the provider removes its use by the face.

## Security

Binary's resource-only architecture and lack of network access keep its displayed information on the watch. The optional recorder uses Android's private app storage and permission-protected services. Neither application operates a remote data store.

## Policy changes

Material changes will be published at this URL with an updated effective date.

## Contact

Privacy questions can be submitted through the project's [GitHub issue tracker](https://github.com/j-256/binary-watch-face/issues).
