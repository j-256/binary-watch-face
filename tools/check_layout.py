#!/usr/bin/env python3
"""Check Binary's generated geometry against its design clearances"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

if __package__:
    from . import generate_watchface as GENERATOR
else:
    import generate_watchface as GENERATOR

DEFAULT_XML = Path(__file__).resolve().parents[1] / "watchface/src/main/res/raw/watchface.xml"
MIN_CONTENT_GAP = 6


@dataclass(frozen=True)
class Clearance:
    category: str
    elements: str
    gap: float
    minimum: float

    @property
    def passed(self) -> bool:
        return self.gap >= self.minimum


def number(element: ET.Element, attribute: str) -> float:
    value = float(element.attrib[attribute])
    if not math.isfinite(value):
        raise ValueError(f"Non-finite {attribute} in {element.tag}")
    return value


def complication_circle(slot: ET.Element) -> tuple[float, float, float]:
    oval = slot.find("BoundingOval")
    if oval is None:
        raise ValueError(f"Missing BoundingOval for {slot.get('name')}")
    width = number(oval, "width")
    padding = number(oval, "outlinePadding")
    if width <= 0 or width != number(oval, "height") or padding < 0:
        raise ValueError(f"Expected a positive circular complication for {slot.get('name')}")
    return (
        number(slot, "x") + number(oval, "x") + width / 2,
        number(slot, "y") + number(oval, "y") + width / 2,
        width / 2 + padding,
    )


def circle_rectangle_gap(slot: ET.Element, bounds: tuple[float, float, float, float]) -> float:
    left, top, right, bottom = bounds
    center_x, center_y, radius = complication_circle(slot)
    return math.hypot(
        max(left - center_x, 0, center_x - right),
        max(top - center_y, 0, center_y - bottom),
    ) - radius


def native_readouts(root: ET.Element) -> dict[tuple[float, float, float, float], str]:
    result = {}
    families = set()
    for text in root.findall(".//PartText"):
        name = text.get("name", "")
        if not name.startswith(("battery_", "heart_rate_")):
            continue
        family = "battery" if name.startswith("battery_") else "heart_rate"
        families.add(family)
        x, y, width, height = (number(text, key) for key in ("x", "y", "width", "height"))
        if width <= 0 or height <= 0:
            raise ValueError(f"Invalid readout dimensions for {name}")
        result[(x, y, x + width, y + height)] = family
    if families != {"battery", "heart_rate"}:
        raise ValueError("Expected both native battery and heart-rate readouts")
    return result


def layout_clearances(root: ET.Element) -> list[Clearance]:
    if number(root, "width") != GENERATOR.WATCH_SIZE or number(root, "height") != GENERATOR.WATCH_SIZE:
        raise ValueError("Expected Binary's 450-unit design canvas")
    elements = root.findall("./Scene/ComplicationSlot")
    slots = {int(slot.attrib["slotId"]): slot for slot in elements}
    if len(slots) != len(elements) or set(slots) != {slot.slot_id for slot in GENERATOR.COMPLICATION_SLOTS}:
        raise ValueError("Missing, duplicate, or unexpected Binary complication slots")
    readouts = native_readouts(root)
    largest = max(GENERATOR.SIZE_CHOICES, key=lambda size: size.scale)
    base = next(size for size in GENERATOR.SIZE_CHOICES if size.option_id == GENERATOR.BASE_SIZE_ID)
    dot_size, _ = GENERATOR.bit_geometry(len(GENERATOR.SIX_BIT_WEIGHTS), base)
    clock_bottom = max(max(rows) for rows in GENERATOR.CLOCK_ROW_LAYOUT.values()) + dot_size / 2 * (1 + largest.scale)
    checks = []
    for bounds, name in readouts.items():
        checks.append(Clearance("readout-clock", name, bounds[1] - clock_bottom, MIN_CONTENT_GAP))
        for slot in slots.values():
            checks.append(Clearance("readout-complication", f"{name}/{slot.get('name')}", circle_rectangle_gap(slot, bounds), MIN_CONTENT_GAP))
    for count, ids in GENERATOR.COMPLICATION_LAYOUTS.items():
        for index, slot_id in enumerate(ids):
            x, y, radius = complication_circle(slots[slot_id])
            for other_id in ids[index + 1:]:
                other_x, other_y, other_radius = complication_circle(slots[other_id])
                gap = math.hypot(x - other_x, y - other_y) - radius - other_radius
                checks.append(Clearance("complication-pair", f"{count} slots: {slot_id}/{other_id}", gap, MIN_CONTENT_GAP))
    regions = (
        ("system-rectangle", GENERATOR.SYSTEM_INDICATOR_BOUNDS, 0),
        ("system-pill", GENERATOR.SYSTEM_ACTIVITY_PILL_BOUNDS, GENERATOR.SYSTEM_ACTIVITY_PILL_CORNER_RADIUS),
    )
    for name, bounds, radius in regions:
        left, top, right, bottom = bounds
        if left + right != GENERATOR.WATCH_SIZE or bottom != GENERATOR.WATCH_SIZE or not 0 <= 2 * radius <= min(right - left, bottom - top):
            raise ValueError(f"Invalid reserved region: {name}")
        inset = (left + radius, top + radius, right - radius, bottom - radius)
        for slot in slots.values():
            gap = circle_rectangle_gap(slot, inset) - radius
            checks.append(Clearance(name, slot.attrib["name"], gap, GENERATOR.SYSTEM_INDICATOR_CLEARANCE))
        for (readout_left, readout_top, readout_right, readout_bottom), readout in readouts.items():
            gap = math.hypot(
                max(inset[0] - readout_right, 0, readout_left - inset[2]),
                max(inset[1] - readout_bottom, 0, readout_top - inset[3]),
            ) - radius
            checks.append(Clearance(name, readout, gap, GENERATOR.SYSTEM_INDICATOR_CLEARANCE))
    return checks


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Report Binary's minimum clearances in 450-unit design coordinates",
        epilog="Requires Python 3 only. Uses the generator's clock geometry, layout membership, and system reserves. Input must be uncompiled Binary WFF XML. Exit status: 0 all clearances pass, 1 insufficient clearance, 2 invalid input or usage.",
    )
    parser.add_argument("watchface", nargs="?", type=Path, default=DEFAULT_XML, help="WFF XML path (default: generated production XML)")
    parser.add_argument("-j", "--json", action="store_true", help="emit all measured clearances as JSON")
    args = parser.parse_args(argv)
    try:
        checks = layout_clearances(ET.parse(args.watchface).getroot())
    except (OSError, ET.ParseError, ValueError, KeyError) as error:
        print(f"check-layout: {error}", file=sys.stderr)
        return 2
    passed = all(check.passed for check in checks)
    if args.json:
        print(json.dumps({"passed": passed, "units": "design", "checks": [{**asdict(check), "passed": check.passed} for check in checks]}, indent=2))
    else:
        for category in dict.fromkeys(check.category for check in checks):
            check = min((item for item in checks if item.category == category), key=lambda item: item.gap - item.minimum)
            status = "PASS" if check.passed else "FAIL"
            print(f"{status} {category}: {check.gap:.2f} units, minimum {check.minimum:g} ({check.elements})")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
