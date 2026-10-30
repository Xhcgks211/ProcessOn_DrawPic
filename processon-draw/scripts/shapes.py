"""
Shape vocabulary for ProcessOn flowcharts: nodes, arrows, connectors.

Everything returns ProcessOn element dicts ready for processon_api.add().

Geometry notes (learned the hard way):
  * `props.x/y` is the shape's TOP-LEFT corner.
  * Path coordinates are RELATIVE to the shape's own origin (0,0) = top-left.
  * `props.angle` is in RADIANS, not degrees. 1.5708 = 90deg. Passing
    degrees (e.g. -30) rotates the shape by -30 RADIANS (~ -1719deg).
    Use math.radians(deg) when you think in degrees.
  * Connectors ("linker") carry ABSOLUTE canvas coordinates in from/to/points
    and reference the shapes they attach to by id.
"""
import math

from processon_api import IdGen, shape

# ---------------------------------------------------------------- connectors


def _center(el):
    p = el["props"]
    return p["x"] + p["w"] / 2.0, p["y"] + p["h"] / 2.0


def link(src, dst, *, ids=None, z=1, line=None, text="", points=None):
    """A straight connector from the edge of `src` to the edge of `dst`.

    src/dst are element dicts. The connector is drawn between the two shape
    centres, clipped to the shape borders.
    """
    ids = ids or IdGen()
    sx, sy = _center(src)
    dx, dy = _center(dst)
    ang = math.atan2(dy - sy, dx - sx)
    # clip to source border (ellipse-ish approximation is fine visually)
    fx = sx + math.cos(ang) * (src["props"]["w"] / 2.0)
    fy = sy + math.sin(ang) * (src["props"]["h"] / 2.0)
    tx = dx - math.cos(ang) * (dst["props"]["w"] / 2.0)
    ty = dy - math.sin(ang) * (dst["props"]["h"] / 2.0)
    mid = [(fx + tx) / 2.0, (fy + ty) / 2.0]
    return {
        "textBlock": [], "fontStyle": {"fontFamily": "Times New Roman"},
        "props": {"zindex": z},
        "dataAttributes": [],
        "points": points if points is not None else [mid],
        "linkerType": "broken",
        "lineStyle": line or {"lineWidth": 1.5},
        "name": "linker",
        "from": {"x": fx, "y": fy, "angle": ang, "id": src["id"]},
        "to": {"x": tx, "y": ty, "angle": ang, "id": dst["id"]},
        "id": ids(""),
        "text": text,
        "locked": False,
        "group": "",
    }


def elbow(src, dst, *, ids=None, z=1, line=None, text="", mode="v"):
    """Orthogonal (elbow) connector — looks like a flowchart arrow.

    mode='v': vertical drop, horizontal run, vertical rise.
    mode='h': horizontal first, vertical, horizontal.
    """
    ids = ids or IdGen()
    sx, sy = _center(src)
    dx, dy = _center(dst)
    if mode == "v":
        # start at the bottom edge of src, end at the top edge of dst
        top_y = sy + src["props"]["h"] / 2.0
        bot_y = dy - dst["props"]["h"] / 2.0
        if bot_y < top_y:                      # dst above src -> route around
            mid_y = (top_y + bot_y) / 2.0
            pts = [[sx, top_y], [sx, mid_y], [dx, mid_y], [dx, bot_y]]
        else:
            pts = [[sx, top_y], [sx, bot_y], [dx, bot_y]]
        f = {"x": sx, "y": top_y, "angle": math.pi / 2, "id": src["id"]}
        t = {"x": dx, "y": bot_y, "angle": -math.pi / 2, "id": dst["id"]}
    else:
        right_x = sx + src["props"]["w"] / 2.0
        left_x = dx - dst["props"]["w"] / 2.0
        if left_x < right_x:                  # dst left of src -> route around
            mid_x = (right_x + left_x) / 2.0
            pts = [[right_x, sy], [mid_x, sy], [mid_x, dy], [left_x, dy]]
        else:
            pts = [[right_x, sy], [left_x, sy], [left_x, dy]]
        f = {"x": right_x, "y": sy, "angle": 0.0, "id": src["id"]}
        t = {"x": left_x, "y": dy, "angle": math.pi, "id": dst["id"]}
    return {
        "textBlock": [], "fontStyle": {"fontFamily": "Times New Roman"},
        "props": {"zindex": z},
        "dataAttributes": [],
        "points": [{"x": p[0], "y": p[1]} for p in pts],
        "linkerType": "broken",
        "lineStyle": line or {"lineWidth": 1.5},
        "name": "linker",
        "from": f, "to": t,
        "id": ids(""),
        "text": text,
        "locked": False,
        "group": "",
    }


# -------------------------------------------------------------------- nodes

FILLS = {
    "red": "242,64,61",
    "red_dark": "235,52,49",
    "green": "83,168,84",
    "green_dark": "57,123,58",
    "orange": "245,126,14",
    "blue": "219,245,245",
    "yellow": "252,249,234",
    "peach": "248,213,181",
    "rose": "250,220,219",
    "grey": "224,224,224",
    "brown": "122,79,42",
}


def node(text, x, y, w=180, h=56, *, fill=None, stroke=None, z=1, ids=None,
         size=16, bold=False, color=None, shape_kind="rect", angle=0):
    """A labelled process box (or circle when shape_kind='circle').

    angle is in RADIANS (ProcessOn native unit).
    """
    font = {"fontFamily": "Times New Roman", "size": size}
    if bold:
        font["bold"] = True
    if color:
        font["color"] = color
    line = {"lineWidth": 1.5}
    if stroke:
        line = {"lineStyle": "solid", "lineColor": stroke, "lineWidth": 1.5}
    return shape(shape_kind, x, y, w, h, z=z, angle=angle,
                 fill=fill, line=line, font=font, text=text, ids=ids)


def label(text, x, y, w=200, h=40, *, size=18, bold=False, color="70,70,70",
          align="left", z=50, ids=None):
    """Borderless text label."""
    font = {"fontFamily": "Times New Roman", "size": size}
    if bold:
        font["bold"] = True
    if color:
        font["color"] = color
    font["textAlign"] = align
    return shape("text", x, y, w, h, z=z, fill=None,
                 line={"lineWidth": 0}, font=font, text=text, ids=ids)


def note(text, x, y, w=220, h=90, *, size=13, z=40, ids=None):
    """Bracket-style side note (ProcessOn 'leftBraceFlow'/'rightBraceFlow')."""
    el = shape("rect", x, y, w, h, z=z, fill=None,
               line={"lineWidth": 1.5}, font={"fontFamily": "微软雅黑", "size": size,
                                             "textAlign": "right"},
               text=text, ids=ids)
    el["name"] = "leftBraceFlow"
    el["title"] = "备注"
    el["category"] = "flow"
    el["path"] = [{
        "actions": [
            {"x": "w", "action": "move", "y": "0"},
            {"y1": "0", "x": "w-Math.min(w*0.1,9)", "action": "quadraticCurve",
             "x1": "w-Math.min(w*0.1,9)", "y": "Math.min(h*0.1,9)"},
            {"x": "w-Math.min(w*0.1,9)", "action": "line", "y": "h*0.5-Math.min(h*0.1,9)"},
            {"y1": "h*0.5", "x": "w-22", "action": "quadraticCurve",
             "x1": "w-Math.min(w*0.1,9)", "y": "Math.min(h*0.1,9)"},
            {"y1": "h*0.5", "x": "w-Math.min(w*0.1,9)", "action": "quadraticCurve",
             "x1": "w-Math.min(w*0.1,9)", "y": "h*0.5+Math.min(h*0.1,9)"},
            {"x": "w-Math.min(w*0.1,9)", "action": "line", "y": "h-Math.min(h*0.1,9)"},
            {"y1": "h", "x": "w", "action": "quadraticCurve",
             "x1": "w-Math.min(w*0.1,9)", "y": "h-Math.min(h*0.1,9)"},
        ],
        "lineStyle": {"lineWidth": 0},
        "fillStyle": {"type": "none"},
    }]
    return el


# ------------------------------------------------------------------ helpers


def stack(items, x, y, *, v_gap=40, h_gap=0, ids=None):
    """Lay out a vertical column of elements; returns (elements, next_y)."""
    ids = ids or IdGen()
    out = []
    cy = y
    for it in items:
        el = it
        p = el["props"]
        p["x"] = x + h_gap
        p["y"] = cy
        out.append(el)
        cy += p["h"] + v_gap
    return out, cy


def grid(items, x, y, cols, *, cell_w=240, cell_h=90, v_gap=40, h_gap=60, ids=None):
    """Lay out elements in a grid; returns (elements, next_y)."""
    out = []
    cy = y
    for i in range(0, len(items), cols):
        row = items[i:i + cols]
        for j, el in enumerate(row):
            p = el["props"]
            p["x"] = x + j * (cell_w + h_gap)
            p["y"] = cy
            out.append(el)
        cy += max(p["h"] for p in [e["props"] for e in row]) + v_gap
    return out, cy





