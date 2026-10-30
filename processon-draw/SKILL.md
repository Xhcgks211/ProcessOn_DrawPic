---
name: processon-draw
description: "Create, read and edit diagrams on ProcessOn (processon.com) — flowcharts, mind maps, org charts — by driving its web API with a session cookie, without opening the browser editor. Use when the user asks to draw/画 a diagram on ProcessOn, generate a 流程图 or 思维导图 there, edit an existing ProcessOn file, or convert content (algorithm steps, architecture, paper figures) into a ProcessOn diagram. Not for other diagramming tools (draw.io, Miro, Excalidraw, mermaid-only tasks)."
---

# ProcessOn Drawing

ProcessOn (processon.com) stores every diagram as a JSON "definition" (`def`): a
map of shape elements plus a page descriptor. The web editor is a JavaScript
canvas; its API accepts and returns that same JSON. So you can draw by
constructing elements and posting them — no browser automation required.

Read `references/api.md` for the endpoint list, the `def` schema, and the
coordinate/rotation rules. Read `references/recipes.md` for worked drawing
patterns.

## Why API-first

The in-app browser path is a trap. Opening the editor page
(`/diagraming/<chartId>`) in a browser makes the editor **auto-save its own
in-memory state**, which silently overwrites anything written via the API —
typically wiping it to empty. Draw through the API and only open the editor
afterwards, when the user wants to hand-edit.

## Workflow

**1. Get credentials.** The user must supply a browser session cookie. Ask for
the `token` cookie value (a JWT) if they do not provide it; it is the only
required credential. Set it in the environment:

```bash
export PROCESSON_TOKEN="eyJ0eXAiOiJKV1Qi..."
export PROCESSON_COOKIE="po-last-platform=personal"   # optional siblings
```

Never hardcode the token into files, scripts, or commits.

**2. Find the target file.** List files and pick by title:

```bash
python scripts/po_draw.py list
```

If the user asked for a *new* diagram, check the quota first:

```bash
python scripts/po_draw.py quota
```

Over quota means `create` fails with code 815 (`文件可用数量不足`). Note that
**trashed files still count** toward the quota — emptying the trash is what
frees space. If you cannot create, reuse an existing file and rename it, and
tell the user.

**3. Build the drawing.** Work in a local `def` JSON, then preview it locally
before touching the cloud. See `references/recipes.md` for the element
vocabulary; `scripts/shapes.py` provides ready-made nodes, arrows, and
connectors.

```python
import sys, math; sys.path.insert(0, "scripts")
from processon_api import blank_def, add, IdGen
import shapes

ids = IdGen()                 # one instance, shared — see gotchas
d = blank_def()

a = add(d, shapes.node("Input", 300, 100, fill=shapes.FILLS["blue"]))
b = add(d, shapes.node("Process", 300, 220, fill=shapes.FILLS["yellow"]))
add(d, shapes.elbow(a, b, ids=ids))
```

`add()` returns the element itself, so it can be passed straight into
`shapes.elbow()` / `shapes.link()`.

**4. Preview locally.** Do this before every upload — it is the only way to
catch geometry mistakes without opening the editor:

```bash
python scripts/render_def.py drawing.json preview.png
```

Show the PNG to the user with a markdown image tag so they can confirm the
result.

**5. Upload and verify.** `put` auto-bumps the version. Then read it back and
compare element counts and names — the save response alone is not evidence
that anything was written:

```bash
python scripts/po_draw.py put <chartId> drawing.json
python scripts/po_draw.py get <chartId> roundtrip.json
```

**6. Report.** Give the user the chart URL
`https://www.processon.com/diagraming/<chartId>` and mention that the
server-side thumbnail may lag, and that opening the editor page will
auto-save — so if they want to keep editing, they should reload first.

## Gotchas that cost real time

Every item below was verified against the live API; all of them fail
**silently** (HTTP 200, "调用成功") rather than raising an error.

- **`def.version` must be NEWER than the server's version.** If it is not,
  the server accepts the request, returns 200, and keeps the old drawing
  untouched. `save_def()` reads the current version and sends `version + 1`
  for you. If your edits "don't appear", check this first.
- **Element `name` must be a native ProcessOn shape name.** The server keeps
  only elements whose `name` matches its built-in registry: `rectangle`,
  `round`, `standardText`, `start`, `process`, `roundRectangle`, `diamond`,
  `linker`, `singleRightArrow`, `leftBraceFlow`, … An element named
  `"Rectangle"` or `"Box"` is discarded without warning. `title` is the
  display label (「矩形」) and is separate from `name`.
- **Path templates must match the native shape.** A `round` element needs
  ProcessOn's own ellipse path (two cubic curves), not a generic circle.
  `scripts/processon_api.py` carries verbatim path templates lifted from real
  saved files — use them rather than inventing paths.
- **`canvasId` must be the chartId**, not the `definitionId`. Passing
  `definitionId` returns code 406 (`权限不足`).
- **Element ids must be unique.** A generator that resets its state per call
  returns the same id every time; elements then overwrite each other and the
  server **silently drops all but one**. Always use a single `IdGen()` instance
  across the whole drawing.
- **`props.angle` is in RADIANS.** `1.5708` = 90°. Passing degrees rotates the
  shape by -30 *radians* (~ -1719°). Use `math.radians(deg)`.
- **`props.x/y` is the top-left corner**; path coordinates inside a shape are
  relative to that origin. Connectors use absolute canvas coordinates.
- **Verify by reading back.** After every upload, `get` the definition and
  compare element counts and names. The save response alone tells you nothing.
- **Auth blips are transient.** Endpoints occasionally return code 408
  (`鉴权失败`); the client retries with backoff. A persistent 401/403 means the
  token expired — ask for a fresh cookie.
- **The client is read-modify-write.** `get` then `put` replaces the entire
  definition. To edit one shape, fetch first, mutate `elements`, then upload.
  Uploading a partial definition erases everything else.

## Scope

Drawing and editing ProcessOn diagrams. This skill does not cover mind-map
specific formats (`mindmap/canvas/*` endpoints), file sharing/permissions, or
the AI-generation endpoints — those need separate API exploration.


