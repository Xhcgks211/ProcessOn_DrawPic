#!/usr/bin/env python
"""
po_draw.py — command line helper for the processon-draw skill.

Usage:
  po_draw.py list                       # list files in the account
  po_draw.py quota                      # file quota (used / allowed)
  po_draw.py get <chartId> out.json     # download a chart's drawing definition
  po_draw.py put <chartId> def.json     # upload a drawing definition
  po_draw.py new "<title>" [category]   # create a chart (needs quota)
  po_draw.py rename <chartId> "<title>"
  po_draw.py thumb <chartId> out.png    # server-rendered thumbnail
  po_draw.py apple out.json             # example: build the sample apple

Auth: set PROCESSON_TOKEN to the `token` cookie value.
Optional: PROCESSON_COOKIE="k=v; k2=v2" for sibling cookies.
"""
import io
import json
import math
import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from processon_api import Client, ProcessOnError, blank_def, add, IdGen  # noqa: E402
import shapes  # noqa: E402


def get_client():
    token = os.environ.get("PROCESSON_TOKEN")
    if not token:
        raise SystemExit("PROCESSON_TOKEN is not set (use the `token` cookie value)")
    cookies = {}
    raw = os.environ.get("PROCESSON_COOKIE", "")
    for part in raw.split(";"):
        part = part.strip()
        if "=" in part:
            k, v = part.split("=", 1)
            cookies[k.strip()] = v.strip()
    return Client(token, cookies)


def cmd_list(c, args):
    for f in c.list_files():
        print(f"{f['chartId']}  {f.get('category','?'):10s}  shapes={f.get('shapeCount',0):<4}  {f.get('title','')}")


def cmd_quota(c, args):
    used, allowed = c.file_quota()
    print(f"used={used} allowed={allowed}")
    if used is not None and allowed is not None and used > allowed:
        print("NOTE: over quota -> creating new files fails with code 815.")
        print("      Trashed files still count; empty the trash or reuse an existing file.")


def cmd_get(c, args):
    d = c.get_def(args[0])
    with open(args[1], "w", encoding="utf-8") as fh:
        json.dump(d, fh, ensure_ascii=False, indent=1)
    print(f"{args[1]}  ({len(d.get('elements', {}))} elements)")


def cmd_put(c, args):
    with open(args[1], encoding="utf-8") as fh:
        d = json.load(fh)
    c.save_def(args[0], d)
    print(f"saved {len(d.get('elements', {}))} elements to {args[0]}")


def cmd_new(c, args):
    title = args[0]
    category = args[1] if len(args) > 1 else "flow"
    r = c.create_file(category=category)
    chart = r.get("data") or {}
    cid = chart.get("chartId")
    if cid:
        c.rename(cid, title)
        print(cid)
    else:
        print(json.dumps(r, ensure_ascii=False))


def cmd_rename(c, args):
    c.rename(args[0], args[1])
    print("renamed")


def cmd_thumb(c, args):
    data = c.thumbnail_png(args[0], args[1])
    print(f"{args[1]} ({len(data)} bytes) — may lag behind the latest save")


def cmd_apple(c, args):
    """Build the sample apple drawing into a local def file."""
    ids = IdGen()
    d = blank_def(version=1)
    ox = 470
    add(d, shapes.node("", ox, 335, 225, 235, fill=shapes.FILLS["red_dark"],
                       stroke="186,32,30", z=1, ids=ids, shape_kind="circle"))
    add(d, shapes.node("", ox + 75, 335, 225, 235, fill=shapes.FILLS["red"],
                       stroke="186,32,30", z=2, ids=ids, shape_kind="circle"))
    add(d, shapes.node("", ox + 36, 392, 78, 42, fill="255,255,255", z=5, ids=ids,
                       shape_kind="circle", angle=math.radians(-30)))
    add(d, shapes.node("", ox + 138, 250, 13, 92, fill=shapes.FILLS["brown"], z=6,
                       ids=ids, angle=math.radians(-8)))
    add(d, shapes.node("", ox + 146, 206, 158, 74, fill=shapes.FILLS["green"],
                       stroke="57,123,58", z=7, ids=ids, shape_kind="circle", angle=math.radians(-24)))
    add(d, shapes.node("", ox + 158, 240, 110, 6, fill="46,105,48", z=8, ids=ids, angle=math.radians(-24)))
    add(d, shapes.label("Apple", ox + 74, 626, 180, 44, size=26, bold=True, z=9, ids=ids))
    with open(args[0], "w", encoding="utf-8") as fh:
        json.dump(d, fh, ensure_ascii=False, indent=1)
    print(args[0])


COMMANDS = {
    "list": cmd_list, "quota": cmd_quota, "get": cmd_get, "put": cmd_put,
    "new": cmd_new, "rename": cmd_rename, "thumb": cmd_thumb, "apple": cmd_apple,
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        return 1
    cmd = sys.argv[1]
    if cmd not in COMMANDS:
        print(f"unknown command: {cmd}\n")
        print(__doc__)
        return 1
    args = sys.argv[2:]
    try:
        if cmd == "apple":
            cmd_apple(None, args)
        else:
            COMMANDS[cmd](get_client(), args)
    except ProcessOnError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())



