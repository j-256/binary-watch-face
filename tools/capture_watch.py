#!/usr/bin/env python3
"""Capture a connected watch without changing its state"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys

PACKAGE = "dev.j256.binarywatchface"
SCHEMA_VERSION = 1
COMMAND_TIMEOUT = 30
RENDER_MODES = {
    "active": "INTERACTIVE",
    "ambient": "AMBIENT",
    "low-battery": "LOW_BATTERY_INTERACTIVE",
}


class PreconditionError(ValueError):
    pass


def nonempty(value: str) -> str:
    if not value.strip():
        raise argparse.ArgumentTypeError("value must not be empty")
    return value


def single(pattern: str, text: str, label: str) -> str:
    values = set(re.findall(pattern, text, re.MULTILINE))
    if len(values) != 1:
        raise PreconditionError(f"Cannot identify a unique {label} in the runtime dump")
    return values.pop()


def wallpaper_component(text: str) -> str:
    match = re.search(r"^System wallpaper state:\s*\n(.*?)(?=^(?:Lock|Fallback) wallpaper state:|\Z)", text, re.MULTILINE | re.DOTALL)
    if match is None:
        raise PreconditionError("Cannot identify the system wallpaper state")
    return single(r"mWallpaperComponent=ComponentInfo\{([^}]+)\}", match.group(1), "system wallpaper component")


def parse_runtime(text: str, package: str, mode: str, version: str) -> dict:
    identity = single(r"^\s*## .* / (\S+ \S+ \(\d+\))\s*$", text, "watch-face identity")
    actual_package, actual_version, code = identity.split()
    if actual_package != package or actual_version != version:
        raise PreconditionError(f"Expected {package} {version}; renderer reports {identity}")
    resource_package = single(r"Resource only package name (\S+)", text, "resource package")
    visible = single(r"privIsVisible=(true|false)", text, "visibility")
    ambient = single(r"\bisAmbient=(true|false)", text, "ambient state")
    draw_mode = single(r"\bdrawMode=(\w+)", text, "draw mode")
    if resource_package != package or visible != "true":
        raise PreconditionError(f"The visible watch face is not {package}")
    if draw_mode != RENDER_MODES[mode] or (ambient == "true") != (mode == "ambient"):
        raise PreconditionError(f"Expected {mode}; renderer reports isAmbient={ambient}, drawMode={draw_mode}")
    style_text = single(r"currentUserStyleRepository.userStyle=UserStyle\[([^\n]*)\]", text, "user style")
    style = {}
    for entry in style_text.split(", "):
        parts = entry.split(" -> ", 1)
        if len(parts) != 2 or not all(parts) or parts[0] in style:
            raise PreconditionError("Cannot parse the selected watch-face style")
        style[parts[0]] = parts[1]
    providers = {}
    parts = re.split(r"ComplicationSlot (\d+):", text)
    for index in range(1, len(parts), 2):
        slot_id, block = parts[index:index + 2]
        if slot_id in providers:
            raise PreconditionError(f"Duplicate complication slot {slot_id}")
        enabled = single(r"\benabled=(true|false)", block, f"slot {slot_id} enabled state")
        sources = set(re.findall(r"dataSource=ComponentInfo\{([^}]+)\}", block))
        if len(sources) > 1:
            raise PreconditionError(f"Conflicting provider identities for slot {slot_id}")
        providers[slot_id] = {"enabled": enabled == "true", "data_source": next(iter(sources), None)}
    if not providers:
        raise PreconditionError("No complication slots found in the runtime dump")
    return {"package": package, "version": actual_version, "version_code": int(code[1:-1]), "mode": mode, "style": style, "providers": providers}


def selection_changes(before: dict, after: dict) -> list[str]:
    changes = []
    for section in ("style", "providers"):
        for key in sorted(set(before[section]) | set(after[section])):
            if before[section].get(key) != after[section].get(key):
                changes.append(f"{section}.{key}")
    return changes


def unknown_providers(*snapshots: dict) -> list[str]:
    return sorted({slot for snapshot in snapshots for slot, provider in snapshot["providers"].items() if provider["enabled"] and provider["data_source"] is None})


def read_baseline(path: Path) -> dict:
    try:
        data = json.loads(path.read_text())
        if data.get("schema_version") != SCHEMA_VERSION or not all(isinstance(data.get(key), dict) and data[key] for key in ("style", "providers")):
            raise ValueError("expected a capture_watch.py schema-version-1 snapshot")
        if not all(isinstance(data.get(key), str) and data[key] for key in ("serial", "package")):
            raise ValueError("snapshot is missing device or package identity")
        if not all(isinstance(value, str) for value in data["style"].values()):
            raise ValueError("snapshot style values must be strings")
        for provider in data["providers"].values():
            if not isinstance(provider, dict) or not isinstance(provider.get("enabled"), bool) or "data_source" not in provider:
                raise ValueError("snapshot provider entries need enabled and data_source fields")
            if provider["data_source"] is not None and not isinstance(provider["data_source"], str):
                raise ValueError("snapshot provider identity must be a string or null")
        return data
    except (OSError, ValueError, AttributeError) as error:
        raise PreconditionError(f"Cannot read comparison snapshot: {error}") from error


def find_adb(explicit: str | None) -> str:
    if explicit:
        candidate = shutil.which(explicit)
    else:
        sdk = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
        candidate = str(Path(sdk) / "platform-tools/adb") if sdk else shutil.which("adb")
    if not candidate or not os.access(candidate, os.X_OK) or not Path(candidate).is_file():
        raise FileNotFoundError("Install Android platform-tools; set ANDROID_HOME, put adb on PATH, or pass --adb")
    return candidate


def capture(args, adb: str, baseline: dict | None) -> dict:
    command = [adb, "-s", args.serial]

    def run(*parts: str) -> bytes:
        return subprocess.run(command + list(parts), check=True, capture_output=True, timeout=COMMAND_TIMEOUT).stdout

    def state() -> dict:
        wallpaper = run("shell", "dumpsys", "wallpaper").decode()
        component = wallpaper_component(wallpaper)
        runtime = run("shell", "dumpsys", "activity", "service", component).decode()
        return parse_runtime(runtime, args.package, args.mode, args.expected_version)

    before = state()
    png = run("exec-out", "screencap", "-p")
    if len(png) < 33 or png[:8] != b"\x89PNG\r\n\x1a\n" or png[12:16] != b"IHDR":
        raise RuntimeError("adb returned an invalid PNG capture")
    width, height = struct.unpack(">II", png[16:24])
    if not width or not height:
        raise RuntimeError("adb returned empty image dimensions")
    after = state()
    if before != after:
        raise RuntimeError("Renderer state changed during capture; leave Binary visible and retry")
    result = {"schema_version": SCHEMA_VERSION, "captured_at": datetime.now(timezone.utc).isoformat(), "serial": args.serial, "image": "watch.png", "width": width, "height": height, **after}
    if baseline:
        result["selection_changes"] = selection_changes(baseline, result)
    result["unverified_provider_slots"] = unknown_providers(result, *([baseline] if baseline else []))
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "watch.png").write_bytes(png)
    (args.output / "snapshot.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Capture Binary and its verified renderer state from an explicitly selected watch",
        epilog="Requires Python 3 and Android platform-tools. Resolve adb with --adb, ANDROID_HOME/ANDROID_SDK_ROOT, or PATH. Leave Binary visible in the requested mode with the activity indicator present. No install, input, or settings commands are sent. --output must be a new directory; captures may contain personal watch data. Comparison input is this command's schema-version-1 snapshot.json. Exit status: 0 captured (comparison passed if requested), 1 device/capture failure or changed/unverifiable selections, 2 usage/precondition error, 3 missing adb.",
    )
    parser.add_argument("-s", "--serial", required=True, type=nonempty, help="adb device serial")
    parser.add_argument("-m", "--mode", required=True, choices=RENDER_MODES, help="required renderer mode")
    parser.add_argument("-e", "--expected-version", required=True, type=nonempty, help="required versionName, e.g. 0.4.0")
    parser.add_argument("-o", "--output", required=True, type=lambda value: Path(nonempty(value)), help="new directory for watch.png and snapshot.json")
    parser.add_argument("-p", "--package", default=PACKAGE, type=nonempty, help=f"resource-only package (default: {PACKAGE})")
    parser.add_argument("-a", "--adb", type=nonempty, help="adb executable path or name")
    parser.add_argument("-c", "--compare-with", type=lambda value: Path(nonempty(value)), help="prior snapshot.json; fail if selected style or providers changed")
    arguments = sys.argv[1:] if argv is None else argv
    if arguments[-1:] == ["--"]:
        arguments = arguments[:-1]
    args = parser.parse_args(arguments)
    try:
        if args.output.exists():
            raise PreconditionError(f"Output already exists: {args.output}")
        baseline = read_baseline(args.compare_with) if args.compare_with else None
        if baseline and (baseline["serial"] != args.serial or baseline["package"] != args.package):
            raise PreconditionError("Comparison snapshot belongs to another device or package")
        adb = find_adb(args.adb)
        result = capture(args, adb, baseline)
        print(json.dumps({"snapshot": str(args.output / "snapshot.json"), **result}, indent=2))
        if result.get("selection_changes"):
            print("capture-watch: selected style or providers changed: " + ", ".join(result["selection_changes"]), file=sys.stderr)
            return 1
        if baseline and result["unverified_provider_slots"]:
            print("capture-watch: cannot verify provider identity for enabled slots: " + ", ".join(result["unverified_provider_slots"]), file=sys.stderr)
            return 1
        return 0
    except PreconditionError as error:
        print(f"capture-watch: {error}", file=sys.stderr)
        return 2
    except FileNotFoundError as error:
        print(f"capture-watch: {error}", file=sys.stderr)
        return 3
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        details = error.stderr.decode(errors="replace").strip() if isinstance(error, subprocess.CalledProcessError) else str(error)
        print(f"capture-watch: {details}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
