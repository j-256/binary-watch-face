#!/usr/bin/env python3
"""Build and capture Binary using an isolated Wear OS emulator"""

import argparse
import os
from pathlib import Path
import platform
import re
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = "dev.j256.binarywatchface"
IMAGE = "system-images;android-37.0;android-wear-signed"
SIZE = 454
TIMEOUT = 180


def run(arguments, **kwargs):
    return subprocess.run(arguments, check=True, timeout=TIMEOUT, **kwargs)


def capture(sdk, apk, output):
    with zipfile.ZipFile(apk) as archive:
        if archive.read("res/raw/watchface.xml") != (ROOT / "watchface/src/main/res/raw/watchface.xml").read_bytes():
            raise RuntimeError("APK watch-face XML differs from the checked-out source")
    abi = "arm64-v8a" if platform.machine() in ("arm64", "aarch64") else "x86_64"
    image = IMAGE + ";" + abi
    if not (sdk / Path(*image.split(";")) / "package.xml").is_file():
        raise FileNotFoundError(f"Install Android SDK image {image}")
    with tempfile.TemporaryDirectory(prefix="binary-cover-") as directory:
        temporary = Path(directory)
        avd_home = temporary / "avd"
        avd_home.mkdir()
        environment = {**os.environ, "ANDROID_HOME": str(sdk), "ANDROID_AVD_HOME": str(avd_home)}
        device = temporary / "device"
        run([str(sdk / "cmdline-tools/latest/bin/avdmanager"), "create", "avd",
             "--name", "binary_cover", "--package", image, "--device", "wearos_large_round",
             "--path", str(device)], input="no\n", text=True, env=environment)
        config = device / "config.ini"
        values = dict(line.split("=", 1) for line in config.read_text().splitlines() if "=" in line)
        values.update({"hw.ramSize": "1536", "hw.lcd.width": str(SIZE), "hw.lcd.height": str(SIZE), "hw.lcd.density": "320"})
        config.write_text("".join(f"{key}={value}\n" for key, value in values.items()))
        for port in range(5580, 5680, 2):
            try:
                with socket.socket() as console, socket.socket() as bridge:
                    console.bind(("127.0.0.1", port))
                    bridge.bind(("127.0.0.1", port + 1))
                break
            except OSError:
                continue
        else:
            raise RuntimeError("No free emulator port pair")
        serial = f"emulator-{port}"
        adb = [str(sdk / "platform-tools/adb"), "-s", serial]

        def shell(*arguments, check=True):
            return subprocess.run(adb + ["shell", *arguments], check=check, capture_output=True, text=True, timeout=30)

        def hierarchy():
            shell("uiautomator", "dump", "/sdcard/cover-ui.xml")
            return ET.fromstring(shell("cat", "/sdcard/cover-ui.xml").stdout)

        log_path = temporary / "emulator.log"
        with log_path.open("w") as log:
            emulator = subprocess.Popen([
                str(sdk / "emulator/emulator"), "-avd", "binary_cover", "-port", str(port),
                "-no-window", "-no-audio", "-no-snapshot", "-wipe-data", "-no-boot-anim", "-gpu", "swiftshader",
            ], env=environment, stdout=log, stderr=subprocess.STDOUT)
            try:
                deadline = time.monotonic() + TIMEOUT
                while shell("getprop", "sys.boot_completed", check=False).stdout.strip() != "1":
                    if emulator.poll() is not None or time.monotonic() > deadline:
                        raise RuntimeError("Wear OS emulator did not boot")
                    time.sleep(1)
                shell("settings", "put", "global", "device_provisioned", "1")
                shell("settings", "put", "secure", "user_setup_complete", "1")
                shell("settings", "put", "system", "screen_off_timeout", "2147483647")
                run(adb + ["install", str(apk)])
                result = shell("am", "broadcast", "-a", "com.google.android.wearable.app.DEBUG_SURFACE",
                               "--es", "operation", "set-watchface", "--es", "watchFaceId", PACKAGE).stdout
                if "result=1" not in result:
                    raise RuntimeError(f"Cannot register Binary as a favorite: {result}")
                shell("dumpsys", "battery", "unplug")
                shell("input", "keyevent", "KEYCODE_WAKEUP")
                shell("input", "keyevent", "KEYCODE_HOME")
                for attempt in range(6):
                    shell("input", "swipe", "227", "227", "227", "227", "1200")
                    tree = hierarchy()
                    if any(node.get("content-desc") == "Watch face picker" for node in tree.iter("node")):
                        break
                    time.sleep(2)
                else:
                    labels = [node.get("text") or node.get("content-desc") for node in tree.iter("node")]
                    raise RuntimeError(f"Watch-face picker did not open: {[label for label in labels if label]}")
                for attempt in range(8):
                    target = next((node for node in hierarchy().iter("node") if node.get("content-desc") == "Activate Binary"), None)
                    if target is not None:
                        left, top, right, bottom = map(int, re.findall(r"\d+", target.get("bounds", "")))
                        shell("input", "tap", str((left + right) // 2), str((top + bottom) // 2))
                        break
                    shell("input", "swipe", "360", "205", "95", "205", "350")
                else:
                    labels = [node.get("text") or node.get("content-desc") for node in hierarchy().iter("node")]
                    raise RuntimeError(f"Binary was not available in the watch-face picker: {[label for label in labels if label]}")
                deadline = time.monotonic() + 30
                while True:
                    wallpaper = shell("dumpsys", "wallpaper").stdout
                    component = re.search(r"mWallpaperComponent=ComponentInfo\{([^}]+)\}", wallpaper)
                    details = shell("dumpsys", "activity", "service", component.group(1)).stdout if component else ""
                    if f"Resource only package name {PACKAGE}" in details and "privIsVisible=true" in details:
                        break
                    if time.monotonic() > deadline:
                        raise RuntimeError("The active renderer is not showing Binary")
                    time.sleep(1)
                time.sleep(1)
                png = run(adb + ["exec-out", "screencap", "-p"], capture_output=True).stdout
                if png[:8] != b"\x89PNG\r\n\x1a\n" or struct.unpack(">II", png[16:24]) != (SIZE, SIZE):
                    raise RuntimeError("Emulator returned an invalid cover image")
                output.parent.mkdir(parents=True, exist_ok=True)
                staged = output.with_suffix(".tmp.png")
                try:
                    staged.write_bytes(png)
                    staged.replace(output)
                finally:
                    staged.unlink(missing_ok=True)
                print(f"Captured Binary from its active Wear OS renderer: {output}")
            except Exception:
                diagnostics = [line for line in log_path.read_text().splitlines() if line.startswith(("ERROR", "WARNING"))]
                print("\n".join(diagnostics[-15:]), file=sys.stderr)
                raise
            finally:
                subprocess.run(adb + ["emu", "kill"], capture_output=True, timeout=15)
                try:
                    emulator.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    emulator.kill()
                    emulator.wait(timeout=15)


def main():
    parser = argparse.ArgumentParser(
        description="Build Binary and render docs/screenshots/cover.png using a fresh Wear OS 7 emulator",
        epilog="Requires Python 3, JDK 17, ANDROID_HOME (or ANDROID_SDK_ROOT), SDK platform 37.0, build-tools 36.0.0, platform-tools, cmdline-tools/latest, emulator, and the signed Wear OS 7 image for the host architecture. JAVA_HOME is passed to Gradle. Exit status: 0 success, 1 build/capture failure, 2 usage error, 3 missing dependency.",
    )
    parser.parse_args()
    location = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    if not location:
        print("capture-cover: set ANDROID_HOME to the Android SDK", file=sys.stderr)
        return 3
    sdk = Path(location).resolve()
    required = ["platform-tools/adb", "cmdline-tools/latest/bin/avdmanager", "emulator/emulator"]
    if any(not os.access(sdk / tool, os.X_OK) for tool in required) or not shutil.which("java"):
        print("capture-cover: install the JDK, Android platform-tools, command-line tools, and emulator", file=sys.stderr)
        return 3
    try:
        run([sys.executable, "tools/generate_watchface.py", "--check"], cwd=ROOT)
        run([str(ROOT / "gradlew"), "--no-daemon", "check", "assembleDebug"], cwd=ROOT)
        capture(sdk, ROOT / "watchface/build/outputs/apk/debug/watchface-debug.apk", ROOT / "docs/screenshots/cover.png")
        return 0
    except FileNotFoundError as error:
        print(f"capture-cover: {error}", file=sys.stderr)
        return 3
    except (OSError, RuntimeError, subprocess.SubprocessError, ET.ParseError) as error:
        print(f"capture-cover: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
