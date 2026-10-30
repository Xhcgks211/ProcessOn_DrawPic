# Drawing recipes

All recipes assume:

```python
import sys, math; sys.path.insert(0, "scripts")
from processon_api import blank_def, add, IdGen
import shapes

ids = IdGen()          # ONE instance for the whole drawing
d = blank_def()
```

`d["elements"][id]` gives an element back for wiring connectors.

## Vertical flowchart

```python
steps = [("Input", "blue"), ("Validate", "yellow"),
         ("Transform", "peach"), ("Output", "rose")]
prev = None
for i, (text, fill) in enumerate(steps):
    el = add(d, shapes.node(text, 320, 100 + i * 110,
                            fill=shapes.FILLS[fill]))
    if prev:
        add(d, shapes.elbow(prev, el, ids=ids))
    prev = el
```

`shapes.elbow` produces an orthogonal arrow (vertical drop, horizontal run);
`shapes.link` produces a straight arrow. Both need the *element dicts*, so
look them up from `d["elements"]`.

## Horizontal pipeline

```python
prev = None
for i, text in enumerate(["Input", "Encode", "Decode", "Output"]):
    el = add(d, shapes.node(text, 120 + i * 250, 200,
                            fill=shapes.FILLS["blue"]))
    if prev:
        add(d, shapes.link(prev, el, ids=ids))
    prev = el
```

## Branching / decision

Use two paths from a diamond-ish node. `shapes.node(..., shape_kind="circle")`
gives an ellipse; for a real diamond, build the element and swap its path
for a four-point polygon.

```python
core = add(d, shapes.node("Decision", 320, 200, 160, 80,
                           fill=shapes.FILLS["orange"]))
yes = add(d, shapes.node("Yes", 160, 340, fill=shapes.FILLS["green"]))
no  = add(d, shapes.node("No", 480, 340, fill=shapes.FILLS["red_dark"]))
add(d, shapes.elbow(core, yes, ids=ids, text="yes"))
add(d, shapes.elbow(core, no,  ids=ids, text="no"))
```

Connector `text` renders as a caption near the arrow.

## Layers / grouping with brace notes

```python
add(d, shapes.note("Conv Layer", 120, 180, 120, 220))
add(d, shapes.note("Recurrent", 120, 430, 120, 200))
```

`note()` produces the `leftBraceFlow` element with a brace path.

## Icon-ish composition

Overlap two ellipses for an apple body, add a stem rectangle and a rotated
leaf ellipse:

```python
add(d, shapes.node("", 470, 335, 225, 235, fill=shapes.FILLS["red_dark"],
                   stroke="186,32,30", z=1, ids=ids, shape_kind="circle"))
add(d, shapes.node("", 545, 335, 225, 235, fill=shapes.FILLS["red"],
                   stroke="186,32,30", z=2, ids=ids, shape_kind="circle"))
add(d, shapes.node("", 608, 250, 13, 92, fill=shapes.FILLS["brown"], z=6,
                   ids=ids, angle=math.radians(-8)))
add(d, shapes.node("", 616, 206, 158, 74, fill=shapes.FILLS["green"],
                   stroke="57,123,58", z=7, ids=ids, shape_kind="circle",
                   angle=math.radians(-24)))
```

Remember `angle` is radians — always wrap degrees in `math.radians()`.

## Editing an existing diagram

`get` returns the live definition; mutate it and upload the whole thing.
`save_def()` handles the version bump automatically.

```python
from processon_api import Client
c = Client(token)
d = c.get_def(chart_id)
el = d["elements"]["someId"]
el["textBlock"][0]["text"] = "New caption"
c.save_def(chart_id, d)
```

Adding a shape to an existing drawing:

```python
new = shapes.node("Extra", 400, 700, fill=shapes.FILLS["blue"], ids=ids)
d["elements"][new["id"]] = new
c.save_def(chart_id, d)
```

## Converting prose or code into a flowchart

1. Extract the ordered steps (numbered list, pseudocode, function body).
2. One node per step, short labels — put long text in a `shapes.note`.
3. Vertical layout for sequences, horizontal for parallel branches.
4. Render locally, show the user, adjust, then upload.

For algorithm figures, keep node labels to the operation (`predict`, `abs diff`,
`argsort`) and put formulas in a note or a `shapes.label` with a larger font.

