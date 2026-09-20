#!/usr/bin/env python3
"""Independent local-tag, Play-bundle, and GitHub-prerelease operations"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "j-256/binary-watch-face"
PACKAGE = "dev.j256.binarywatchface"
BUILD_FILE = "watchface/build.gradle.kts"
FACE_FILE = "watchface/src/main/res/raw/watchface.xml"
ANDROID = "{http://schemas.android.com/apk/res/android}"
JARSIGNER_CERTIFICATE_WARNING = 4


def run(arguments, accepted=(0,)):
    result = subprocess.run([str(arg) for arg in arguments], cwd=ROOT, capture_output=True, timeout=180)
    if result.returncode not in accepted:
        detail = (result.stderr or result.stdout).decode(errors="replace")[-2000:]
        raise RuntimeError(f"{arguments[0]} failed ({result.returncode}): {detail.strip()}")
    return result.stdout


def require(condition, message):
    if not condition:
        raise ValueError(message)


def dependency(name):
    path = shutil.which(name)
    if not path:
        raise FileNotFoundError(f"Install or configure {name}")
    return path


def jdk_tool(name):
    home = os.environ.get("JAVA_HOME")
    return dependency(str(Path(home) / "bin" / name) if home else name)


def version(value):
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?", value):
        raise argparse.ArgumentTypeError("Expected a version such as 0.4.0")
    return value


def fingerprint(value):
    normalized = value.replace(":", "").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", normalized):
        raise argparse.ArgumentTypeError("Expected a SHA-256 certificate fingerprint, optionally colon-separated")
    return normalized


def path_argument(value):
    if not value.strip():
        raise argparse.ArgumentTypeError("Path must not be empty")
    return Path(value).expanduser().resolve()


def source_version(ref, expected):
    source = run(["git", "show", f"{ref}:{BUILD_FILE}"]).decode()
    name = re.search(r'versionName\s*=\s*"([^"]+)"', source)
    code = re.search(r"versionCode\s*=\s*([0-9]+)", source)
    require(name is not None and code is not None, "Cannot read source version")
    require(name.group(1) == expected, "Requested version does not match source")
    return int(code.group(1))


def release_tag(expected):
    tag = f"v{expected}"
    require(run(["git", "tag", "--list", tag]).strip(), "Create the annotated local release tag first")
    require(run(["git", "cat-file", "-t", f"refs/tags/{tag}"]).strip() == b"tag", "Use an annotated local release tag")
    return tag, source_version(tag, expected)


def verify_archive(path, tag, prefix):
    expected = run(["git", "show", f"{tag}:{FACE_FILE}"])
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)), "Artifact contains duplicate entries")
        require(not any(name.endswith(".dex") for name in names), "Resource-only release must not contain DEX")
        require(archive.read(prefix + "res/raw/watchface.xml") == expected, "Artifact WFF does not match the release tag")


def verify_manifest(root, expected, code):
    require(root.get("package") == PACKAGE, "Unexpected package identity")
    require(root.get(ANDROID + "versionName") == expected, "Unexpected artifact version name")
    require(root.get(ANDROID + "versionCode") == str(code), "Unexpected artifact version code")
    app = root.find("application")
    require(app is not None and app.get(ANDROID + "hasCode") == "false", "Expected android:hasCode=false")
    require(app.get(ANDROID + "debuggable", "false") == "false", "Debug artifacts cannot be distributed")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tag_release(args):
    require(not run(["git", "status", "--porcelain"]).strip(), "Commit all changes before tagging")
    code = source_version("HEAD", args.version)
    tag = f"v{args.version}"
    require(not run(["git", "tag", "--list", tag]).strip(), "Tag already exists; tags are never moved")
    run([sys.executable, "tools/generate_watchface.py", "--check"])
    run([sys.executable, "tools/check_layout.py"])
    if not args.dry_run:
        run(["git", "tag", "-a", tag, "-m", f"Binary {args.version} release checkpoint"])
    return {"tag": tag, "versionCode": code, "created": not args.dry_run, "pushed": False}


def prepare_play(args):
    java, jarsigner, keytool = (jdk_tool(name) for name in ("java", "jarsigner", "keytool"))
    require(args.bundle.is_file() and args.bundletool.is_file(), "Bundle and bundletool JAR must exist")
    require(not args.output.exists(), "Output directory already exists; choose a new directory")
    tag, code = release_tag(args.version)
    original_digest = digest(args.bundle)
    verification = run([jarsigner, "-J-Duser.language=en", "-verify", "-strict", args.bundle], accepted=(0, JARSIGNER_CERTIFICATE_WARNING)).decode()
    require("jar verified" in verification.lower(), "AAB signature was not verified")
    certificates = run([keytool, "-printcert", "-rfc", "-jarfile", args.bundle]).decode()
    blocks = re.findall(r"-----BEGIN CERTIFICATE-----(.*?)-----END CERTIFICATE-----", certificates, re.S)
    actual = {hashlib.sha256(base64.b64decode(block)).hexdigest() for block in blocks}
    require(actual == {args.certificate_sha256}, "AAB signer does not match the expected upload certificate")
    manifest = run([java, "-jar", args.bundletool, "dump", "manifest", f"--bundle={args.bundle}"])
    verify_manifest(ET.fromstring(manifest), args.version, code)
    verify_archive(args.bundle, tag, "base/")
    require(digest(args.bundle) == original_digest, "Bundle changed during verification")
    receipt = {"tag": tag, "versionName": args.version, "versionCode": code, "sha256": original_digest,
               "certificateSha256": args.certificate_sha256, "uploaded": False}
    if not args.dry_run:
        args.output.mkdir(parents=True)
        target = args.output / f"binary-watch-face-{args.version}-upload.aab"
        shutil.copyfile(args.bundle, target)
        require(digest(target) == receipt["sha256"], "Bundle changed while being archived")
        (args.output / "SHA256SUMS").write_text(f"{receipt['sha256']}  {target.name}\n")
        (args.output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def verify_apk(args, tag, code):
    aapt = dependency(str(args.build_tools / "aapt2"))
    signer = dependency(str(args.build_tools / "apksigner"))
    jdk_tool("java")
    require(args.apk.is_file(), "Play-exported APK must exist")
    signatures = run([signer, "verify", "--print-certs", args.apk]).decode()
    certificates = re.findall(r"Signer #[0-9]+ certificate SHA-256 digest: ([0-9a-fA-F]+)", signatures)
    require({value.lower() for value in certificates} == {args.certificate_sha256}, "APK signer does not match the expected Play app-signing certificate")
    badging = run([aapt, "dump", "badging", args.apk]).decode()
    package = re.search(r"^package: name='([^']+)' versionCode='([^']+)' versionName='([^']+)'", badging, re.M)
    require(package is not None and package.groups() == (PACKAGE, str(code), args.version), "APK identity does not match the release")
    manifest = run([aapt, "dump", "xmltree", args.apk, "--file", "AndroidManifest.xml"]).decode()
    require(re.search(r":hasCode\([^)]*\)=false(?:\s|$)", manifest), "Expected android:hasCode=false")
    require(not re.search(r":debuggable\([^)]*\)=true", manifest), "Debug APKs cannot be distributed")
    verify_archive(args.apk, tag, "")


def verify_remote_tag(tag):
    local = run(["git", "rev-parse", f"refs/tags/{tag}"]).decode().strip()
    remote = run(["git", "ls-remote", f"https://github.com/{REPOSITORY}.git", f"refs/tags/{tag}"]).decode().split()
    require(remote and remote[0] == local, "Push the exact annotated release tag before publishing")


def verify_assets(release, expected, draft):
    require(release["isPrerelease"] and release["isDraft"] == draft, "Unexpected GitHub release state")
    actual = {asset["name"]: asset.get("digest") for asset in release["assets"]}
    require(actual == expected, "GitHub asset checksums do not match; inspect the release before continuing")


def publish_github(args):
    dependency("gh")
    tag, code = release_tag(args.version)
    require(args.apk.is_file(), "Play-exported APK must exist")
    original_digest = digest(args.apk)
    verify_apk(args, tag, code)
    require(digest(args.apk) == original_digest, "APK changed during verification")
    require(args.notes.is_file() and args.notes.read_text().strip(), "Release notes must be a nonempty UTF-8 file")
    verify_remote_tag(tag)
    releases = json.loads(run(["gh", "release", "list", "--repo", REPOSITORY, "--limit", "1000", "--json", "tagName"]))
    require(not any(item["tagName"] == tag for item in releases), "Release already exists; inspect it instead of overwriting")
    if args.dry_run:
        return {"tag": tag, "sha256": digest(args.apk), "prerelease": True, "published": False}
    with tempfile.TemporaryDirectory(prefix="binary-release-") as directory:
        apk = Path(directory) / "binary-watch-face.apk"
        checksum = Path(directory) / "binary-watch-face.apk.sha256"
        shutil.copyfile(args.apk, apk)
        require(digest(apk) == original_digest, "APK changed while being copied")
        checksum.write_text(f"{digest(apk)}  {apk.name}\n")
        expected = {path.name: "sha256:" + digest(path) for path in (apk, checksum)}
        run(["gh", "release", "create", tag, apk, checksum, "--repo", REPOSITORY, "--verify-tag", "--draft",
             "--prerelease", "--latest=false", "--title", f"Binary {args.version} beta", "--notes-file", args.notes])
        view = ["gh", "release", "view", tag, "--repo", REPOSITORY, "--json", "isDraft,isPrerelease,assets,url"]
        verify_assets(json.loads(run(view)), expected, draft=True)
        run(["gh", "release", "edit", tag, "--repo", REPOSITORY, "--draft=false", "--prerelease", "--latest=false"])
        release = json.loads(run(view))
        verify_assets(release, expected, draft=False)
        return {"tag": tag, "url": release["url"], "prerelease": True, "published": True}


def parser():
    result = argparse.ArgumentParser(description=__doc__, epilog="Run each stage separately. No operation pushes Git or submits a Play release. Complete README verification before tagging. Results are JSON on stdout; errors go to stderr. Exit: 0 success, 1 runtime failure, 2 usage/precondition, 3 missing dependency.")
    commands = result.add_subparsers(dest="operation", required=True)
    for name, handler, description in (
        ("tag", tag_release, "Create an annotated local tag after completed release checks; requires Git and Python"),
        ("prepare-play", prepare_play, "Verify and archive an already signed AAB; requires Git, JDK 17 (JAVA_HOME or PATH), and bundletool; upload in Play Console separately"),
        ("github", publish_github, "Verify and publish a Play-exported APK as a GitHub prerelease; requires Git, authenticated gh, JDK, and Android SDK build-tools"),
    ):
        command = commands.add_parser(name, description=description, help=description, epilog=result.epilog)
        command.set_defaults(handler=handler)
        command.add_argument("version", type=version, help="Release version, without the v tag prefix")
        command.add_argument("-n", "--dry-run", action="store_true", help="Run preflight checks without writing files, tags, or releases")
        if name != "tag":
            command.add_argument("-c", "--certificate-sha256", required=True, type=fingerprint, help="Trusted upload certificate for AAB, or Play app-signing certificate for APK; 64 hex digits, optional colons")
        if name == "prepare-play":
            command.add_argument("-b", "--bundle", required=True, type=path_argument, help="Signed upload AAB built from the release tag")
            command.add_argument("-j", "--bundletool", required=True, type=path_argument, help="Official bundletool-all JAR")
            command.add_argument("-o", "--output", required=True, type=path_argument, help="New archive directory; never overwrites an existing directory")
        if name == "github":
            command.add_argument("-a", "--apk", required=True, type=path_argument, help="Universal APK exported from Play, signed with the app-signing key")
            command.add_argument("-s", "--build-tools", required=True, type=path_argument, help="SDK build-tools directory containing aapt2 and apksigner")
            command.add_argument("-F", "--notes", required=True, type=path_argument, help="Reviewed UTF-8 Markdown release notes")
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        dependency("git")
        print(json.dumps(args.handler(args), indent=2))
        return 0
    except FileNotFoundError as error:
        print(f"release: {error}", file=sys.stderr)
        return 3
    except (ValueError, KeyError, zipfile.BadZipFile, ET.ParseError) as error:
        print(f"release: {error}", file=sys.stderr)
        return 2
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"release: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
