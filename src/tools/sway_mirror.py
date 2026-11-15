#!/usr/bin/env python3
"""Mirror one sway output onto others; run when a layout in Mirror mode is applied.

    sway_mirror.py SOURCE TARGET [TARGET...]

Sway has no native mirroring, so wl-mirror shows SOURCE full screen on each
TARGET. Before that, every workspace on the targets is moved to SOURCE and the
one the user was looking at is shown there. Otherwise they'd stay on the
targets, hidden behind wl-mirror, while the source shows the empty workspace
sway created when it was turned on.

Standalone (no project imports): run as a detached process.
"""

import json
import subprocess
import sys
import time


def swaymsg(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["swaymsg", *args], capture_output=True, text=True)


def quote(name: str) -> str:
    return '"' + name.replace("\\", "\\\\").replace('"', '\\"') + '"'


def get(kind: str) -> list:
    try:
        return json.loads(swaymsg("-t", kind, "-r").stdout or "[]")
    except json.JSONDecodeError:
        return []


def wait_for_outputs(names, timeout=3.0) -> None:
    """Run right after applying; give sway a moment to have them all on"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        active = {o["name"] for o in get("get_outputs") if o.get("active")}
        if all(n in active for n in names):
            return
        time.sleep(0.1)


APP_ID = "microcontrol"


def scan_windows():
    """(workspace with the MicroControl window or None, {workspace: window count})"""
    app_ws = None
    counts = {}

    def walk(node, workspace=None):
        nonlocal app_ws
        if node.get("type") == "workspace":
            workspace = node.get("name")
        if node.get("pid") and workspace:
            counts[workspace] = counts.get(workspace, 0) + 1
            if app_ws is None and (node.get("app_id") == APP_ID
                                   or (node.get("name") or "").startswith("MicroControl")):
                app_ws = workspace
        for child in node.get("nodes", []) + node.get("floating_nodes", []):
            walk(child, workspace)

    try:
        walk(json.loads(swaymsg("-t", "get_tree", "-r").stdout or "{}"))
    except json.JSONDecodeError:
        pass
    if app_ws == "__i3_scratch":  # hidden in the scratchpad: not shown anywhere
        app_ws = None
    return app_ws, counts


def move_workspaces(source: str, targets: list) -> None:
    workspaces = get("get_workspaces")
    focused = next((w["name"] for w in workspaces if w.get("focused")), None)
    on_targets = [w for w in workspaces if w.get("output") in targets]
    app_ws, window_counts = scan_windows()

    # --no-auto-back-and-forth: with workspace_auto_back_and_forth on, switching
    # to the current workspace would jump to the previous one instead
    for ws in on_targets:
        swaymsg(f"workspace --no-auto-back-and-forth {quote(ws['name'])}; "
                f"move workspace to output {quote(source)}")

    # Show the workspace with the MicroControl window (where the user just
    # chose Mirror). Without it (e.g. re-applied on hotplug), show what
    # the user was looking at: the focused workspace, unless it's the empty one
    # sway created when the source was turned on; then the one that was
    # visible on a target.
    moved = [w["name"] for w in on_targets]
    if app_ws:
        shown = app_ws
    elif focused and (focused in moved or window_counts.get(focused)):
        shown = focused
    elif moved:
        shown = next((w["name"] for w in on_targets if w.get("visible")), moved[0])
    else:
        return
    swaymsg(f"workspace --no-auto-back-and-forth {quote(shown)}")


def main(argv: list) -> int:
    if len(argv) < 3:
        print(__doc__, file=sys.stderr)
        return 2
    source, targets = argv[1], argv[2:]

    subprocess.run(["pkill", "-x", "wl-mirror"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    wait_for_outputs([source] + targets)
    move_workspaces(source, targets)

    for target in targets:
        subprocess.Popen(
            ["wl-mirror", "--fullscreen-output", target, source],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
