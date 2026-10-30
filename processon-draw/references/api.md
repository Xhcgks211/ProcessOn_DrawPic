# ProcessOn API reference

Base: `https://www.processon.com/api/personal`
Auth: `token` header + `token` cookie (browser session JWT).
All endpoints accept `application/x-www-form-urlencoded` unless noted.

## Endpoints

| Purpose | Method | Path | Notes |
|---|---|---|---|
| List files | GET | `/folder/load_files?page=1&pageSize=50` | root folder by default |
| List trash | GET | `/folder/trash_files?page=1&pageSize=50` | trash still counts vs quota |
| File quota | GET | `/user/privilege` | `fileCount` allowed, `usedFileCount` used |
| Profile | GET | `/user/setting/getProfile` | userId, fullName |
| Create file | POST | `/diagraming/create` | `folderId`, `category`; code 815 when over quota |
| Rename | POST | `/chart/rename` | `chartId`, `title` |
| Move to trash | POST | `/folder/to_trash` | `fileId`, `fileType` |
| Restore | POST | `/folder/restore` | `fileId`, `fileType` |
| Purge from trash | POST | `/folder/remove_from_trash` | `fileId`, `fileType` |
| Chart meta | GET | `/canvas/get/chartdefids?chartId=` | `chart`, `canvas.mainCanvasId` |
| Get drawing | GET | `/diagraming/get/chart/def?chartId=` | `data.def` is a JSON **string** |
| Save drawing | POST | `/diagraming/canvas/v2/saveonline` | `def`, `chartId`, `canvasId`, `shapecount`, `ignore` |
| History list | POST | `/hst/ver/list` | JSON body `{chartId, pages}` |
| Thumbnail | GET | `https://www.processon.com/chart_image/thumb/<thumbnailId>.png` | async, may lag |

## Save parameters

```
def       = json.dumps(definition)      # the whole drawing as one JSON string
chartId   = <chart id>
canvasId  = <chart id>                   # NOT the definitionId -> else 406
shapecount= <number of elements>
ignore    = "def"
```

Content type: `application/x-www-form-urlencoded;charset=UTF-8`.

## Definition schema

```json
{
  "comments": [],
  "plugins": {},
  "elements": { "<elementId>": { ...element... } },
  "page": {
    "padding": 20, "backgroundColor": "transparent",
    "orientation": "portrait", "gridSize": 15,
    "width": 1500, "showGrid": true, "lineJumps": false,
    "height": 2100
  },
  "version": 1
}
```

### Element (shape)

```json
{
  "parent": "", "link": "", "shapeStyle": {"alpha": 1},
  "textBlock": [{"position": {"w": "w-20", "x": 10, "h": "h", "y": 0}, "text": "Label"}],
  "anchors": [{"x":"w/2","y":"0"},{"x":"w/2","y":"h"},{"x":"0","y":"h/2"},{"x":"w","y":"h/2"}],
  "title": "矩形",
  "fontStyle": {"fontFamily": "Times New Roman", "size": 16},
  "dataAttributes": [],
  "props": {"zindex": 1, "w": 180, "x": 300, "y": 100, "h": 56, "angle": 0},
  "path": [{"actions": [ ...path commands... ]}],
  "lineStyle": {"lineStyle": "solid", "lineColor": "186,32,30", "lineWidth": 1.5},
  "children": [], "resizeDir": ["tl","tr","br","bl","l","t","r","b"],
  "name": "Rectangle",
  "fillStyle": {"color": "242,64,61", "type": "solid"},
  "theme": {},
  "id": "<elementId>",
  "attribute": {"container": false, "rotatable": true, "visible": true,
                "fixedLink": false, "collapsable": false, "collapsed": false,
                "linkable": true, "markerOffset": 5},
  "category": "basic", "locked": false, "group": ""
}
```

### Path commands

`path` is a list of sub-paths, each with `actions`:

| action | fields |
|---|---|
| `move` | `x`, `y` |
| `line` | `x`, `y` |
| `curve` | `x`, `y` (end) + `x1,y1,x2,y2` (control points) |
| `quadraticCurve` | `x`, `y` + `x1,y1` |
| `close` | — |

Coordinates are **relative to the shape origin** (0,0 = top-left) and may be
expressions over `w` and `h`, e.g. `"w*0.5"`, `"h*0.22"`.

Circle path (four cubic segments, the ProcessOn native circle):

```
move (0, h*0.5)
curve -> (w*0.5, 0)     ctrl (0,0) (w*0.22,0)
curve -> (w, h*0.5)     ctrl (w*0.78,0) (w,h*0.22)
curve -> (w*0.5, h)     ctrl (w,h*0.78) (w*0.78,h)
curve -> (0, h*0.5)     ctrl (w*0.22,h*0.78) (0,h)
close
```

Rectangle path: `move (0,0) -> line (w,0) -> line (w,h) -> line (0,h) -> close`.

### Element (connector)

```json
{
  "textBlock": [], "fontStyle": {"fontFamily": "Times New Roman"},
  "props": {"zindex": 5},
  "dataAttributes": [],
  "points": [{"x": 390, "y": 196}],
  "linkerType": "broken",
  "lineStyle": {"lineWidth": 1.5},
  "name": "linker",
  "from": {"x": 390, "y": 177, "angle": 1.5708, "id": "<srcShapeId>"},
  "to":   {"x": 390, "y": 214, "angle": 4.7124, "id": "<dstShapeId>"},
  "id": "<linkerId>",
  "text": "", "locked": false, "group": ""
}
```

Connector `from`/`to`/`points` use **absolute canvas coordinates** and cite the
attached shapes by id. `linkerType` is `broken` (polyline through `points`) or
`normal`.

### Other shape names seen in real files

`rectangle`, `round` (circle/ellipse), `start` (rounded pill), `process`,
`roundRectangle`, `diamond`, `standardText` (borderless label),
`standardImage`, `singleRightArrow`, `singleDownArrow`, `leftBraceFlow`,
`rightBraceFlow`, `flowFinal`, `maybe`, `directData`, `onPageReference`.

`leftBraceFlow` / `rightBraceFlow` carry a brace path (not a rectangle) —
`scripts/shapes.py` has a working `note()` builder.

## Coordinates and rotation

- `props.x`, `props.y` = top-left of the shape.
- `props.w`, `props.h` = size.
- `props.angle` = **radians**. Values seen in real files: 1.570796 (90°),
  3.141593 (180°), 4.712389 (270°). Passing `-30` rotates by -30 radians.
- `props.zindex` controls draw order; larger = on top.
- Fill colour is `"r,g,b"` strings, e.g. `"242,64,61"`. Transparency via
  `"fillalpha": 0.5`.

## Error codes

| code | meaning |
|---|---|
| 200 | ok |
| 401 | 参数错误 — usually a missing required parameter |
| 408 | 鉴权失败 — transient; retry |
| 406 | 权限不足 — usually wrong `canvasId` |
| 509 | 请求过于频繁 — rate limited; retry |
| 801 | 文件不存在 — wrong chartId, or file is in trash |
| 815 | 文件可用数量不足 — over file quota |

## Reverse-engineering notes

The endpoint list was recovered from the site's own bundles
(`/js/main.*.js` for the file list, `/v5_editor/compile/designer.*.js` for the
editor). Searching those for `saveonline`, `get/chart/def`, and `ApiPrefix`
is the fastest way to discover new endpoints.
