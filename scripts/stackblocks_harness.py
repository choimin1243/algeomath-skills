#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reusable AlgeoMath Kids 3D stackblock injection harness.

Coordinate convention for authoring:
  x = left to right from the viewer's front-facing image
  y = front to back, where y=0 is closest to the viewer
  h = column height

Block coordinate convention:
  (x, y, z) means left/right, front/back, up/down in author space
  x grows to the right, y grows toward the back, z grows upward from 1
"""

import argparse
import importlib.util
import json
import socket
import subprocess
import sys
import time
import traceback
from pathlib import Path


def ensure_playwright():
    """Install Playwright and Chromium on first use when they are missing."""
    if importlib.util.find_spec("playwright") is None:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "playwright"])
    try:
        from playwright.sync_api import sync_playwright as imported_sync_playwright
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "playwright"])
        from playwright.sync_api import sync_playwright as imported_sync_playwright

    with imported_sync_playwright() as p:
        executable = Path(p.chromium.executable_path)
    if not executable.exists():
        subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])

    return imported_sync_playwright


sync_playwright = ensure_playwright()


DEFAULT_COLORS = {1: 0xD89A52, 2: 0xD8893C, 3: 0xC9792F, 4: 0xB96828, 5: 0xA95A20}

CASE_COLORS = [
    {1: 0xD89A52, 2: 0xC9792F, 3: 0xA95A20, 4: 0x8B4513, 5: 0x6B3410},  # orange
    {1: 0x64B5F6, 2: 0x2196F3, 3: 0x1565C0, 4: 0x0D47A1, 5: 0x0A3070},  # blue
    {1: 0x81C784, 2: 0x4CAF50, 3: 0x2E7D32, 4: 0x1B5E20, 5: 0x134018},  # green
    {1: 0xCE93D8, 2: 0xAB47BC, 3: 0x6A1B9A, 4: 0x4A148C, 5: 0x380F6A},  # purple
    {1: 0xFFCC80, 2: 0xFFA726, 3: 0xE65100, 4: 0xBF360C, 5: 0x8D2608},  # amber
    {1: 0x80DEEA, 2: 0x00BCD4, 3: 0x006064, 4: 0x004D50, 5: 0x003538},  # cyan
]

PRESETS = {
    # Matches the common reference image: a front-facing 1-2-3-2-1 pyramid.
    # Author-space coordinates:
    #   x: left -> right
    #   y: front -> back
    #   z: bottom -> top
    "reference-pyramid": {
        (0, 0): 1,
        (1, 0): 2,
        (2, 0): 3,
        (3, 0): 2,
        (4, 0): 1,
    },
    "sample-pyramid": {
        (0, 0): 1,
        (1, 0): 2,
        (2, 0): 3,
        (3, 0): 2,
        (4, 0): 1,
    },
    # Triangular staircase pyramid: 10 blocks, 3×3 footprint, tall at front-left.
    # Front view: [3,2,1]  Side view: [3,2,1]  Top: [[3,2,1],[2,1,0],[1,0,0]]
    # Correct answer for the standard Korean isometric pyramid image.
    "triangular-staircase": {
        (0, 0): 3,
        (1, 0): 2,
        (2, 0): 1,
        (0, 1): 2,
        (1, 1): 1,
        (0, 2): 1,
    },
}


def parse_cases(raw):
    """Parse JSON array of height maps: [ [[x,y,h],...], [[x,y,h],...] ]."""
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError("--cases must be a JSON array of height maps")
    return [parse_height_map(json.dumps(case)) for case in data]


def layout_cases(cases_height_maps, gap=3):
    """Offset multiple cases side by side in x. Returns (combined_blocks, block_color_map)."""
    combined_blocks = []
    block_colors = {}
    x_offset = 0

    for case_idx, hm in enumerate(cases_height_maps):
        norm_hm = normalize_height_map(hm)
        blocks = columns_to_blocks(norm_hm)
        if not blocks:
            continue
        case_max_x = max(x for x, _, _ in blocks)
        colors = CASE_COLORS[case_idx % len(CASE_COLORS)]
        for x, y, z in blocks:
            shifted = (x + x_offset, y, z)
            combined_blocks.append(shifted)
            block_colors[shifted] = colors.get(z, colors[max(colors)])
        x_offset += case_max_x + 1 + gap

    return combined_blocks, block_colors


def build_objects_for_cases(cases_height_maps, gap=3):
    """Build AlgeoMath objects for all cases laid out side by side in x."""
    combined_blocks, block_colors = layout_cases(cases_height_maps, gap=gap)
    if not combined_blocks:
        return []
    max_y = max(y for _, y, _ in combined_blocks)
    objects = []
    for i, (x, y, z) in enumerate(sorted(combined_blocks)):
        col, row, layer = to_algeomath_grid((x, y, z), max_y)
        color = block_colors.get((x, y, z), DEFAULT_COLORS.get(z, 0xFFFFFF))
        objects.append({
            "id": 100 + i,
            "typeName": "STACK_CUBE",
            "name": "stackCube",
            "is2DObject": False,
            "color": color,
            "measurementType": None,
            "visible": True,
            "position": {"x": col + 0.5, "y": -(row + 0.5), "z": layer - 0.5},
            "rotation": {"_x": 0, "_y": 0, "_z": 0, "_order": "XYZ"},
            "scale": {"x": 1, "y": 1, "z": 1},
        })
    return objects


def parse_height_map(raw):
    """Parse [[x,y,h], ...] or {"x,y": h, ...} into {(x, y): h}."""
    data = json.loads(raw)
    height_map = {}
    if isinstance(data, list):
        for item in data:
            if not (isinstance(item, list) and len(item) == 3):
                raise ValueError("list height map items must be [x, y, h]")
            x, y, h = item
            height_map[(int(x), int(y))] = int(h)
    elif isinstance(data, dict):
        for key, value in data.items():
            if "," not in key:
                raise ValueError("dict height map keys must look like 'x,y'")
            x, y = key.split(",", 1)
            height_map[(int(x), int(y))] = int(value)
    else:
        raise ValueError("height map must be a list or dict")

    for (x, y), h in height_map.items():
        if x < 0 or y < 0 or h < 0:
            raise ValueError(f"invalid column {(x, y)} -> {h}")
    return height_map


def parse_blocks(raw):
    """Parse [[x,y,z], ...] into author-space blocks."""
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError("blocks must be a list of [x, y, z] items")
    blocks = []
    for item in data:
        if not (isinstance(item, list) and len(item) == 3):
            raise ValueError("block items must be [x, y, z]")
        x, y, z = (int(item[0]), int(item[1]), int(item[2]))
        if x < 0 or y < 0 or z < 1:
            raise ValueError(f"invalid block {(x, y, z)}")
        blocks.append((x, y, z))
    return sorted(set(blocks))


def normalize_height_map(height_map):
    if not height_map:
        return {}
    min_x = min(x for x, _ in height_map)
    min_y = min(y for _, y in height_map)
    return {(x - min_x, y - min_y): h for (x, y), h in height_map.items() if h > 0}


def normalize_blocks(blocks):
    if not blocks:
        return []
    min_x = min(x for x, _, _ in blocks)
    min_y = min(y for _, y, _ in blocks)
    return sorted({(x - min_x, y - min_y, z) for x, y, z in blocks})


def columns_to_blocks(height_map):
    """Expand {(x, y): h} columns to author-space (x, y, z) blocks."""
    return [
        (x, y, z)
        for (x, y), height in sorted(height_map.items())
        for z in range(1, height + 1)
    ]


def blocks_to_height_map(blocks):
    height_map = {}
    for x, y, z in blocks:
        height_map[(x, y)] = max(height_map.get((x, y), 0), z)
    return height_map


def to_algeomath_grid(block, max_y):
    """Convert author-space (x, y, z) to AlgeoMath grid (col, row, layer)."""
    x, y, z = block
    return x, max_y - y, z


def build_objects_from_blocks(blocks, max_y=None, colors=None):
    colors = colors or DEFAULT_COLORS
    if max_y is None:
        max_y = max((y for _, y, _ in blocks), default=0)
    layout = [to_algeomath_grid(block, max_y) for block in sorted(blocks)]
    return [
        {
            "id": 100 + i,
            "typeName": "STACK_CUBE",
            "name": "stackCube",
            "is2DObject": False,
            "color": colors.get(z, colors[max(colors)]),
            "measurementType": None,
            "visible": True,
            "position": {"x": x + 0.5, "y": -(y + 0.5), "z": z - 0.5},
            "rotation": {"_x": 0, "_y": 0, "_z": 0, "_order": "XYZ"},
            "scale": {"x": 1, "y": 1, "z": 1},
        }
        for i, (x, y, z) in enumerate(layout)
    ]


def build_objects(height_map, colors=None):
    return build_objects_from_blocks(columns_to_blocks(height_map), colors=colors)


def describe_views(height_map):
    if not height_map:
        return {
            "top": [],
            "front": [],
            "back": [],
            "left": [],
            "right": [],
            "layer_counts": {},
            "total_blocks": 0,
        }
    max_x = max(x for x, _ in height_map)
    max_y = max(y for _, y in height_map)
    max_h = max(height_map.values())
    front = [max(height_map.get((x, y), 0) for y in range(max_y + 1)) for x in range(max_x + 1)]
    back = list(reversed(front))
    left = [max(height_map.get((x, y), 0) for x in range(max_x + 1)) for y in range(max_y + 1)]
    right = list(reversed(left))
    top = [
        [height_map.get((x, y), 0) for x in range(max_x + 1)]
        for y in range(max_y + 1)
    ]
    return {
        "top": top,
        "front": front,
        "back": back,
        "left": left,
        "right": right,
        "layer_counts": {
            layer: sum(1 for h in height_map.values() if h >= layer)
            for layer in range(1, max_h + 1)
        },
        "total_blocks": sum(height_map.values()),
    }


def describe_coordinates(height_map):
    """Return author coordinates and the exact AlgeoMath positions that will be loaded."""
    max_y = max((y for _, y in height_map), default=0)
    author_blocks = columns_to_blocks(height_map)
    return [
        {
            "author_xyz": [x, y, z],
            "author_xyz_1_indexed": [x + 1, y + 1, z],
            "direction": {
                "left_right": x,
                "front_back": y,
                "up": z,
            },
            "algeomath_grid": list(to_algeomath_grid((x, y, z), max_y)),
            "algeomath_position": {
                "x": to_algeomath_grid((x, y, z), max_y)[0] + 0.5,
                "y": -(to_algeomath_grid((x, y, z), max_y)[1] + 0.5),
                "z": z - 0.5,
            },
        }
        for x, y, z in author_blocks
    ]


def describe_block_coordinates(blocks):
    """Return explicit author blocks and the exact AlgeoMath positions that will be loaded."""
    max_y = max((y for _, y, _ in blocks), default=0)
    return [
        {
            "author_xyz": [x, y, z],
            "author_xyz_1_indexed": [x + 1, y + 1, z],
            "direction": {
                "left_right": x,
                "front_back": y,
                "up": z,
            },
            "algeomath_grid": list(to_algeomath_grid((x, y, z), max_y)),
            "algeomath_position": {
                "x": to_algeomath_grid((x, y, z), max_y)[0] + 0.5,
                "y": -(to_algeomath_grid((x, y, z), max_y)[1] + 0.5),
                "z": z - 0.5,
            },
        }
        for x, y, z in sorted(blocks)
    ]


def find_poly_frame(page):
    for frame in page.frames:
        try:
            has_api = frame.evaluate(
                "() => !!(window.AlgeomathPoly && window.AlgeomathPoly.api && "
                "window.AlgeomathPoly.api.save && window.AlgeomathPoly.api.load)"
            )
        except Exception:
            has_api = False
        if has_api:
            return frame
    raise RuntimeError("AlgeomathPoly API frame not found")


def wait_for_cdp(port, timeout=20):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return
        except OSError:
            time.sleep(0.25)
    raise RuntimeError(f"Chromium CDP port did not open: {port}")


def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def launch_detached_chromium(playwright, port=None):
    """Launch Chromium independently so the browser can stay open after injection."""
    port = port or find_free_port()
    user_data_dir = Path.home() / ".codex" / "tmp" / "algeomath-stackblocks-profile"
    user_data_dir.mkdir(parents=True, exist_ok=True)
    executable = playwright.chromium.executable_path
    creationflags = 0
    if sys.platform.startswith("win"):
        creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    proc = subprocess.Popen(
        [
            executable,
            f"--remote-debugging-port={port}",
            f"--user-data-dir={user_data_dir}",
            "--no-first-run",
            "--start-maximized",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        creationflags=creationflags,
    )
    wait_for_cdp(port)
    return proc, port


def inject(height_map=None, blocks=None, cases=None, gap=3, screenshot=None, log_path=None, keep_open=True):
    log_file = Path(log_path) if log_path else None

    def log(message):
        if log_file:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            with log_file.open("a", encoding="utf-8") as f:
                f.write(message + "\n")
        else:
            print(message)

    if cases is not None:
        objects = build_objects_for_cases(cases, gap=gap)
        log_detail = f"cases={len(cases)} gap={gap}"
    elif blocks is not None:
        blocks = normalize_blocks(blocks)
        height_map = blocks_to_height_map(blocks)
        objects = build_objects_from_blocks(blocks)
        log_detail = f"height_map={height_map} views={describe_views(height_map)}"
        log_detail += f" coordinates={json.dumps(describe_block_coordinates(blocks), ensure_ascii=False)}"
    else:
        height_map = normalize_height_map(height_map or {})
        blocks = columns_to_blocks(height_map)
        objects = build_objects_from_blocks(blocks)
        log_detail = f"height_map={height_map} views={describe_views(height_map)}"
        log_detail += f" coordinates={json.dumps(describe_coordinates(height_map), ensure_ascii=False)}"

    p = sync_playwright().start()
    browser_proc, cdp_port = launch_detached_chromium(p)
    browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{cdp_port}")
    try:
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = context.new_page()
        page.set_viewport_size({"width": 1400, "height": 900})
        page.goto(
            "https://www.algeomath.kr/kids/algeomath/poly/make",
            wait_until="domcontentloaded",
            timeout=60000,
        )
        time.sleep(6)
        frame = find_poly_frame(page)
        base = json.loads(frame.evaluate("() => JSON.stringify(window.AlgeomathPoly.api.save())"))
        base["scene"]["objectDatas"] = objects
        frame.evaluate("(d) => window.AlgeomathPoly.api.load(d)", base)
        time.sleep(1)

        if screenshot:
            Path(screenshot).parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=screenshot, full_page=True)

        log("status=ready")
        log(log_detail)
        if screenshot:
            log(f"screenshot={screenshot}")
    finally:
        if not keep_open:
            browser.close()
            browser_proc.terminate()
        else:
            browser.disconnect()
        p.stop()


def main():
    parser = argparse.ArgumentParser(description="Inject AlgeoMath Kids 3D stackblocks.")
    parser.add_argument(
        "--preset",
        choices=sorted(PRESETS),
        help="Use a built-in height map. reference-pyramid matches the provided sample image.",
    )
    parser.add_argument(
        "--height-map",
        required=False,
        help='JSON: [[x,y,h], ...] or {"x,y": h}; y=0 is the viewer-facing front row',
    )
    parser.add_argument(
        "--blocks",
        required=False,
        help="JSON: explicit author-space blocks [[x,y,z], ...]. Bypasses height-map expansion.",
    )
    parser.add_argument(
        "--cases",
        required=False,
        help="JSON array of height maps: [ [[x,y,h],...], [[x,y,h],...] ]. Places all cases side by side.",
    )
    parser.add_argument(
        "--gap",
        type=int,
        default=3,
        help="Block gap between cases when using --cases (default: 3).",
    )
    parser.add_argument("--screenshot", help="Optional screenshot path.")
    parser.add_argument("--log", help="Optional log path.")
    parser.add_argument("--reset", action="store_true", help="Accepted for compatibility; the scene is replaced on load.")
    parser.add_argument("--close", action="store_true", help="Close browser after injection.")
    parser.add_argument(
        "--print-coordinates",
        action="store_true",
        help="Print author-space (x,y,z), converted AlgeoMath grid coordinates, and exit.",
    )
    args = parser.parse_args()

    try:
        if args.cases:
            cases = parse_cases(args.cases)
            if args.print_coordinates:
                combined, _ = layout_cases(cases, gap=args.gap)
                print(json.dumps(
                    [{"author_xyz": list(b), "algeomath_position": {
                        "x": to_algeomath_grid(b, max(y for _, y, _ in combined))[0] + 0.5,
                        "y": -(to_algeomath_grid(b, max(y for _, y, _ in combined))[1] + 0.5),
                        "z": b[2] - 0.5,
                    }} for b in sorted(combined)],
                    ensure_ascii=False, indent=2
                ))
                return
            inject(cases=cases, gap=args.gap, screenshot=args.screenshot, log_path=args.log, keep_open=not args.close)
            return

        raw_blocks = None
        if args.blocks:
            raw_blocks = parse_blocks(args.blocks)
        elif args.preset:
            raw_height_map = dict(PRESETS[args.preset])
        elif args.height_map:
            raw_height_map = parse_height_map(args.height_map)
        else:
            parser.error("provide --blocks, --height-map, --cases, or --preset")

        if raw_blocks is not None:
            blocks = normalize_blocks(raw_blocks)
            height_map = blocks_to_height_map(blocks)
        else:
            height_map = normalize_height_map(raw_height_map)
            blocks = None

        if args.print_coordinates:
            coordinates = describe_block_coordinates(blocks) if blocks is not None else describe_coordinates(height_map)
            print(json.dumps(coordinates, ensure_ascii=False, indent=2))
            return

        inject(
            height_map=height_map,
            blocks=blocks,
            screenshot=args.screenshot,
            log_path=args.log,
            keep_open=not args.close,
        )
    except Exception:
        if args.log:
            with open(args.log, "a", encoding="utf-8") as f:
                f.write("status=error\n")
                f.write(traceback.format_exc())
        else:
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
