"""
ProcessOn API client + flowchart shape builder.

Used by the processon-draw skill. No third-party deps beyond requests (already
present in most Python envs); falls back to urllib if requests is missing.
"""
import json
import os
import random
import string
import time
import urllib.parse
import urllib.request

BASE = "https://www.processon.com"
API = BASE + "/api/personal"

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")


class ProcessOnError(Exception):
    pass


def _opener():
    if os.name != "nt":
        return urllib.request.build_opener()
    # avoid proxy env interfering on Windows
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


class Client:
    """Thin ProcessOn web-API client.

    Auth is a browser session cookie. The caller must supply the raw
    `token` JWT value (from the `token` cookie) plus any sibling cookies.
    """

    def __init__(self, token, cookies=None, user_agent=_UA):
        self.token = token.strip()
        self.cookies = dict(cookies or {})
        self.cookies["token"] = self.token
        self.user_agent = user_agent
        self._ids = random.Random()

    # ---------- plumbing ----------
    def _cookie_header(self):
        return "; ".join(f"{k}={v}" for k, v in self.cookies.items())

    def _headers(self, extra=None):
        h = {
            "Cookie": self._cookie_header(),
            "User-Agent": self.user_agent,
            "Accept": "application/json, text/plain, */*",
            "Referer": BASE + "/diagrams",
            "Origin": BASE,
            "token": self.token,
        }
        h.update(extra or {})
        return h

    def request(self, method, url, params=None, data=None, json_body=None,
                headers=None, retries=4, timeout=30):
        """Returns parsed JSON (dict). Raises ProcessOnError on API-level errors."""
        if url.startswith("/"):
            url = API + url
        elif not url.startswith("http"):
            url = API + "/" + url
        if params:
            url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
        body = None
        hdrs = self._headers(headers)
        if json_body is not None:
            body = json.dumps(json_body).encode("utf-8")
            hdrs["Content-Type"] = "application/json;charset=UTF-8"
        elif data is not None:
            body = urllib.parse.urlencode(data).encode("utf-8")
            hdrs["Content-Type"] = "application/x-www-form-urlencoded;charset=UTF-8"
        last = None
        for attempt in range(retries):
            try:
                req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
                with _opener().open(req, timeout=timeout) as resp:
                    raw = resp.read().decode("utf-8", "replace")
                try:
                    out = json.loads(raw)
                except json.JSONDecodeError:
                    return {"_raw": raw}
                code = str(out.get("code", ""))
                if code and code != "200":
                    msg = out.get("msg", "")
                    # transient auth blips / rate limits are worth one retry
                    if code in ("408", "509") and attempt < retries - 1:
                        time.sleep(1.2 * (attempt + 1))
                        continue
                    raise ProcessOnError(f"{method} {url} -> code={code} msg={msg}")
                return out
            except ProcessOnError:
                raise
            except Exception as exc:  # network hiccup
                last = exc
                if attempt < retries - 1:
                    time.sleep(1.2 * (attempt + 1))
                    continue
                raise ProcessOnError(f"{method} {url} failed: {last}") from last

    # ---------- account ----------
    def privilege(self):
        return self.request("GET", "/user/privilege")["data"]["privilege"]

    def profile(self):
        return self.request("GET", "/user/setting/getProfile")["data"]["user"]

    def file_quota(self):
        """Returns (used, allowed). ProcessOn counts trashed files against quota."""
        p = self.privilege()
        return p.get("usedFileCount"), p.get("fileCount")

    # ---------- files ----------
    def list_files(self, page=1, page_size=50):
        d = self.request("GET", "/folder/load_files",
                         params={"page": page, "pageSize": page_size})["data"]
        return d.get("charts", [])

    def list_trash(self, page=1, page_size=50):
        d = self.request("GET", "/folder/trash_files",
                         params={"page": page, "pageSize": page_size})["data"]
        return d.get("charts", [])

    def find_file(self, title=None, chart_id=None, category=None):
        """Locate a file by exact title or id; falls back to a substring match."""
        if chart_id:
            for c in self.list_files():
                if c["chartId"] == chart_id:
                    return c
            return None
        files = self.list_files()
        if category:
            files = [c for c in files if c.get("category") == category]
        if title:
            exact = [c for c in files if c.get("title") == title]
            if exact:
                return exact[0]
            loose = [c for c in files if title.lower() in (c.get("title") or "").lower()]
            if loose:
                return loose[0]
            return None
        return files[0] if files else None

    def create_file(self, folder_id="root", category="flow", template_id=None):
        """Create a new chart. Raises on quota errors (code 815)."""
        data = {"folderId": folder_id, "category": category}
        if template_id:
            data["templateId"] = template_id
        return self.request("POST", "/diagraming/create", data=data)

    def rename(self, chart_id, title):
        return self.request("POST", "/chart/rename",
                            data={"chartId": chart_id, "title": title, "ignore": "title"})

    def to_trash(self, file_id, file_type="chart"):
        return self.request("POST", "/folder/to_trash",
                            data={"fileId": file_id, "fileType": file_type})

    def restore(self, file_id, file_type="chart"):
        return self.request("POST", "/folder/restore",
                            data={"fileId": file_id, "fileType": file_type})

    def remove_from_trash(self, file_id, file_type="chart"):
        return self.request("POST", "/folder/remove_from_trash",
                            data={"fileId": file_id, "fileType": file_type})

    # ---------- chart content ----------
    def chart_meta(self, chart_id):
        d = self.request("GET", "/canvas/get/chartdefids",
                         params={"chartId": chart_id})["data"]
        return d.get("chart"), d.get("canvas")

    def get_def(self, chart_id):
        """Return the parsed drawing definition (dict with elements/page/...)."""
        d = self.request("GET", "/diagraming/get/chart/def",
                         params={"chartId": chart_id})["data"]
        raw = d.get("def")
        if not raw:
            raise ProcessOnError(f"no def for chart {chart_id}")
        return json.loads(raw)

    def save_def(self, chart_id, definition, version=None):
        """Overwrite a chart's drawing.

        IMPORTANT: `canvasId` must be the chartId, NOT the definitionId.
        Passing definitionId returns code 406 "权限不足".

        IMPORTANT: `def.version` must be GREATER than the server's current
        chart version. The server replies 200 "调用成功" but silently keeps
        the old drawing when the version is not newer. When `version` is
        None the current server version + 1 is used automatically.
        """
        if version is None:
            try:
                version = int(self.chart_meta(chart_id)[0].get("version") or 0) + 1
            except Exception:
                version = int(definition.get("version") or 0) + 1
        definition = dict(definition)
        definition["version"] = version
        body = {
            "def": json.dumps(definition, ensure_ascii=False),
            "chartId": chart_id,
            "canvasId": chart_id,
            "shapecount": str(len(definition.get("elements", {}))),
            "ignore": "def",
        }
        return self.request("POST", "/diagraming/canvas/v2/saveonline", data=body)

    def thumbnail_png(self, chart_id, path=None):
        """Download the server-rendered thumbnail. May lag behind the latest save."""
        meta, _ = self.chart_meta(chart_id)
        thumb = meta.get("thumbnail")
        if not thumb:
            raise ProcessOnError("no thumbnail id")
        url = f"{BASE}/chart_image/thumb/{thumb}.png"
        req = urllib.request.Request(url, headers=self._headers({"Referer": BASE + "/diagrams"}))
        with _opener().open(req, timeout=30) as resp:
            data = resp.read()
        if path:
            with open(path, "wb") as fh:
                fh.write(data)
        return data

    def history_list(self, chart_id, pages=1):
        d = self.request("POST", "/hst/ver/list",
                         json_body={"chartId": chart_id, "pages": pages})["data"]
        return d.get("rsList", [])


# --------------------------------------------------------------------------
# Shape construction
# --------------------------------------------------------------------------

# Authoritative path templates taken verbatim from real saved files.
# 'round' is ProcessOn's ellipse; 'standardText' is the borderless label.
_CIRCLE_PATH = [{
    "actions": [
        {"x": "0", "action": "move", "y": "h/2"},
        {"y1": "-h/6", "x": "w", "action": "curve",
         "x1": "0", "y2": "-h/6", "y": "h/2", "x2": "w"},
        {"y1": "h+h/6", "x": "0", "action": "curve",
         "x1": "w", "y2": "h+h/6", "y": "h/2", "x2": "0"},
        {"action": "close"},
    ],
}]

_RECT_PATH = [{
    "actions": [
        {"x": "0", "action": "move", "y": "0"},
        {"x": "w", "action": "line", "y": "0"},
        {"x": "w", "action": "line", "y": "h"},
        {"x": "0", "action": "line", "y": "h"},
        {"action": "close"},
    ],
}]

_TEXT_PATH = [{
    "lineStyle": {"lineWidth": 0},
    "fillStyle": {"type": "none"},
    "actions": [
        {"x": "0", "action": "move", "y": "0"},
        {"x": "w", "action": "line", "y": "0"},
        {"x": "w", "action": "line", "y": "h"},
        {"x": "0", "action": "line", "y": "h"},
        {"action": "close"},
    ],
}]


class IdGen:
    """Collision-free element ids.

    A naive generator that resets its state per call returns the SAME id every
    time; elements then overwrite each other server-side and all but one are
    silently dropped. Always use an instance with advancing state.
    """

    ALPHABET = string.ascii_letters + string.digits

    def __init__(self, seed=None):
        self.rng = random.Random(seed)
        self._n = 0

    def __call__(self, prefix=""):
        """Return a fresh 17-char id.

        Real ProcessOn files use plain 17-char ids with no prefix, so the
        default prefix is empty. A non-empty prefix is fine too, but keep it
        short.
        """
        self._n += 1
        s = ""
        for _ in range(17):
            s += self.rng.choice(self.ALPHABET)
        return prefix + s


# ProcessOn only persists elements whose `name` matches one of its built-in
# shape registry names. Emitting e.g. "Rectangle" (capital R) or "linker"
# from a hand-built template makes the server SILENTLY DROP the element.
# These are the names observed in real saved files.
NATIVE_NAMES = {
    "rect": ("rectangle", "矩形"),
    "circle": ("round", "圆形"),
    "text": ("standardText", ""),
}


def shape(kind, x, y, w, h, *, z=1, angle=0, fill=None, line=None, font=None,
          text="", ids=None, name=None):
    """Build one ProcessOn element.

    kind: 'rect' | 'circle' | 'text'
    fill: "r,g,b" string or None (transparent)
    line: dict like {"lineColor": "r,g,b", "lineWidth": 2}
    """
    ids = ids or IdGen()
    if kind == "circle":
        path = _CIRCLE_PATH
        nm, title = NATIVE_NAMES["circle"]
    elif kind == "text":
        path = _TEXT_PATH
        nm, title = NATIVE_NAMES["text"]
    else:
        path = _RECT_PATH
        nm, title = NATIVE_NAMES["rect"]
    el = {
        "parent": "", "link": "", "shapeStyle": {"alpha": 1},
        "textBlock": [{"position": {"w": "w-20", "x": 10, "h": "h", "y": 0}, "text": text}],
        "anchors": [{"x": "w/2", "y": "0"}, {"x": "w/2", "y": "h"},
                    {"x": "0", "y": "h/2"}, {"x": "w", "y": "h/2"}],
        "title": title,
        "fontStyle": font or {"fontFamily": "Times New Roman", "size": 16},
        "dataAttributes": [{"name": n, "id": ids(""), "type": t,
                            "category": "default", "value": ""}
                           for n, t in (("序号", "number"), ("名称", "string"),
                                        ("所有者", "string"), ("连接", "link"),
                                        ("便笺", "string"))],
        "props": {"zindex": z, "w": w, "x": x, "y": y, "h": h, "angle": angle},
        "path": json.loads(json.dumps(path)),
        "lineStyle": line if line is not None else {"lineWidth": 1.5},
        "children": [],
        "resizeDir": ["tl", "tr", "br", "bl", "l", "t", "r", "b"],
        "name": name or nm,
        "fillStyle": ({"color": fill, "type": "solid"} if fill
                      else ({"type": "none"} if kind == "text" else {})),
        "theme": {},
        "id": ids(""),
        "attribute": {"container": False, "rotatable": True, "visible": True,
                      "fixedLink": False, "collapsable": False, "collapsed": False,
                      "linkable": True, "markerOffset": 5},
        "category": "basic",
        "locked": False,
        "group": "",
    }
    return el


def blank_def(width=1500, height=2100, version=1):
    return {
        "comments": [], "plugins": {}, "elements": {},
        "page": {"padding": 20, "backgroundColor": "transparent",
                 "orientation": "portrait", "gridSize": 15, "width": width,
                 "showGrid": True, "lineJumps": False, "height": height},
        "version": version,
    }


def add(definition, element):
    """Insert an element into the definition and RETURN THE ELEMENT itself.

    Returning the element (not its id) makes connector code read naturally:
        prev = add(d, shapes.node(...))
        add(d, shapes.elbow(prev, nxt))
    """
    definition["elements"][element["id"]] = element
    return element







