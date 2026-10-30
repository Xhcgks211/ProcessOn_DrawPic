"""
Render a ProcessOn `def` (JSON) to PNG locally.

The server thumbnail is regenerated asynchronously and can lag behind a save,
so this gives an immediate visual check of what you just wrote.

Requires Pillow.
"""
import json
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

FONT_CANDIDATES = {
    (False,): ["C:/Windows/Fonts/times.ttf", "C:/Windows/Fonts/arial.ttf"],
    (True,): ["C:/Windows/Fonts/timesbd.ttf", "C:/Windows/Fonts/arialbd.ttf"],
}


def _font(size, bold):
    for path in FONT_CANDIDATES[(bool(bold),)]:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()


def _eval(expr, w, h):
    """Evaluate a path coordinate like 'w*0.5' or 'h*0.22'."""
    if isinstance(expr, (int, float)):
        return float(expr)
    t = str(expr).replace("w", "(%r)" % float(w)).replace("h", "(%r)" % float(h))
    t = "".join(c for c in t if c.isdigit() or c in "().+-*/ ")
    try:
        return float(eval(t))
    except Exception:
        return 0.0


def _bezier(p0, p1, p2, p3, steps=40):
    out = []
    for i in range(steps + 1):
        t = i / steps
        m = 1 - t
        out.append((
            m ** 3 * p0[0] + 3 * m * m * t * p1[0] + 3 * m * t * t * p2[0] + t ** 3 * p3[0],
            m ** 3 * p0[1] + 3 * m * m * t * p1[1] + 3 * m * t * t * p2[1] + t ** 3 * p3[1],
        ))
    return out


def _trace(element):
    """Absolute canvas polyline for one element."""
    p = element["props"]
    w, h, x, y = p["w"], p["h"], p["x"], p["y"]
    pts = []
    cur = (0.0, 0.0)
    for path in element.get("path", []):
        for a in path.get("actions", []):
            X = _eval(a.get("x"), w, h)
            Y = _eval(a.get("y"), w, h)
            act = a.get("action")
            if act == "move":
                cur = (X, Y)
                pts.append(cur)
            elif act == "line":
                cur = (X, Y)
                pts.append(cur)
            elif act == "curve":
                p1 = (_eval(a.get("x1"), w, h), _eval(a.get("y1"), w, h))
                p2 = (_eval(a.get("x2"), w, h), _eval(a.get("y2"), w, h))
                seg = _bezier(cur, p1, p2, (X, Y))
                pts.extend(seg[1:])
                cur = (X, Y)
            elif act == "quadraticCurve":
                p1 = (_eval(a.get("x1"), w, h), _eval(a.get("y1"), w, h))
                seg = []
                for i in range(1, 25):
                    t = i / 24
                    m = 1 - t
                    seg.append((m * m * cur[0] + 2 * m * t * p1[0] + t * t * X,
                                m * m * cur[1] + 2 * m * t * p1[1] + t * t * Y))
                pts.extend(seg)
                cur = (X, Y)
            elif act == "close":
                if pts and (abs(cur[0] - pts[0][0]) > 1e-6 or abs(cur[1] - pts[0][1]) > 1e-6):
                    pts.append(pts[0])
    # shift to absolute position
    pts = [(px + x, py + y) for px, py in pts]
    # rotate about the shape centre
    # ProcessOn stores angle in RADIANS (values like 1.5708 = 90deg).
    ang = p.get("angle", 0)
    if ang:
        cx, cy = x + w / 2.0, y + h / 2.0
        ca, sa = math.cos(ang), math.sin(ang)
        pts = [(cx + (px - cx) * ca - (py - cy) * sa,
                cy + (px - cx) * sa + (py - cy) * ca) for px, py in pts]
    return pts


def _arrow_head(draw, p_from, p_to, color):
    ang = math.atan2(p_to[1] - p_from[1], p_to[0] - p_from[0])
    size = 9
    tip = p_to
    b1 = (tip[0] - size * math.cos(ang - 0.42), tip[1] - size * math.sin(ang - 0.42))
    b2 = (tip[0] - size * math.cos(ang + 0.42), tip[1] - size * math.sin(ang + 0.42))
    draw.polygon([tip, b1, b2], fill=color)


def render(definition, out_path, width=None, height=None, bg=(255, 255, 255)):
    elements = list(definition.get("elements", {}).values())
    if not elements:
        raise SystemExit("definition has no elements")
    page = definition.get("page", {})
    W = width or int(page.get("width", 1500))
    H = height or int(page.get("height", 2100))
    img = Image.new("RGBA", (W, H), bg + (255,))
    draw = ImageDraw.Draw(img, "RGBA")

    for e in sorted(elements, key=lambda e: e["props"].get("zindex", 0)):
        if e.get("name") == "linker":
            line = e.get("lineStyle") or {}
            color = tuple(int(v) for v in (line.get("lineColor") or "120,120,120").split(",")) + (255,)
            lw = max(1, int(round(line.get("lineWidth", 1.5))))
            pts = [(p["x"], p["y"]) for p in e.get("points", [])]
            if len(pts) >= 2:
                draw.line(pts, fill=color, width=lw, joint="curve")
            f, t = e.get("from"), e.get("to")
            if f and t:
                _arrow_head(draw, (f["x"], f["y"]), (t["x"], t["y"]), color)
            ltext = e.get("text") or ""
            if ltext:
                draw.text((f["x"] + 6, f["y"] - 16), ltext, font=_font(13, False), fill=color)
            continue

        pts = _trace(e)
        fill = e.get("fillStyle") or {}
        line = e.get("lineStyle") or {}
        if fill.get("type") == "none" or not fill.get("color"):
            fillc = None
        else:
            fillc = tuple(int(v) for v in fill["color"].split(",")) + \
                    (int(255 * fill.get("fillalpha", 1)),)
        lw = line.get("lineWidth", 1.5)
        stroke = None if lw == 0 else tuple(
            int(v) for v in (line.get("lineColor") or "120,120,120").split(",")) + (255,)
        if pts and fillc is not None:
            draw.polygon(pts, fill=fillc)
        if pts and stroke is not None:
            draw.line(pts, fill=stroke, width=max(1, int(round(lw))), joint="curve")

        txt = ""
        blocks = e.get("textBlock") or []
        if blocks:
            txt = blocks[0].get("text") or ""
        if txt:
            f = e.get("fontStyle") or {}
            size = int(f.get("size", 14))
            font = _font(size, f.get("bold"))
            col = (70, 70, 70, 255)
            if f.get("color"):
                col = tuple(int(v) for v in f["color"].split(",")) + (255,)
            p = e["props"]
            clean = txt.replace("<br>", "\n").replace("<div>", "\n").replace("</div>", "")
            clean = __import__("re").sub(r"<[^>]+>", "", clean)
            draw.multiline_text((p["x"] + 10, p["y"] + size * 0.4), clean,
                                font=font, fill=col, spacing=4)

    img.convert("RGB").save(out_path)
    return out_path


def main():
    if len(sys.argv) < 3:
        print("usage: render_def.py <def.json> <out.png> [width] [height]")
        return 1
    src, dst = sys.argv[1], sys.argv[2]
    w = int(sys.argv[3]) if len(sys.argv) > 3 else None
    h = int(sys.argv[4]) if len(sys.argv) > 4 else None
    with open(src, encoding="utf-8") as fh:
        definition = json.load(fh)
    render(definition, dst, w, h)
    print(dst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

