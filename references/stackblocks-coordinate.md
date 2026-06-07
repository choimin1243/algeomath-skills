# Stack-Block Coordinate Reference

Use this only when placing or explaining AlgeoMath Kids 3D stack-block coordinates.

## Direction Model

- `x`: left to right in the viewed image.
- `y`: front to back; `y=0` is closest to the viewer.
- `z`: bottom to top; `z=1` is the floor layer.
- Height map item `[x,y,h]` expands to blocks `(x,y,1)` through `(x,y,h)`.
- Judge left/right/front/back/up from the image before using layer counts.
- Layer counts are reference information; they do not determine the footprint by themselves.
- Ask for the front side when direction is ambiguous.
- Do not create floating cubes.
- If multiple arrangements fit the prompt, keep every plausible arrangement and show all of them in AlgeoMath.

## Image Analysis Protocol

1. Identify the view direction.
   - Bottom of image is front.
   - Top of image is back.
   - Left of image is left.
   - Right of image is right.
2. Count footprint width and depth. Never collapse a 2D footprint into a single row.
3. Count the height at each ground position.
4. Build `[[x,y,h], ...]` or explicit `[[x,y,z], ...]` blocks.
5. Place the result directly in AlgeoMath. Skip separate verification unless the user asks for it.
6. For multiple possible answers, place all cases side by side with a visible gap.

## AlgeoMath Conversion

`scripts/stackblocks_harness.py` converts author coordinates to AlgeoMath internal positions:

```text
author (x,y,z) -> grid (col=x, row=max_y-y, layer=z)
position = (col+0.5, -(row+0.5), layer-0.5)
```

Prefer explicit block coordinates when accuracy matters:

```powershell
pythonw "C:\Users\choi2\.codex\skills\algeomath-skills\scripts\stackblocks_harness.py" --blocks '[[x,y,z], ...]'
```

Show multiple possible height maps in one open AlgeoMath 3D window:

```powershell
pythonw "C:\Users\choi2\.codex\skills\algeomath-skills\scripts\stackblocks_harness.py" --cases '[[[x,y,h], ...], [[x,y,h], ...]]' --gap 4
```

## Common Patterns

Triangular staircase pyramid, 10 blocks:

```json
[[0,0,3],[1,0,2],[2,0,1],[0,1,2],[1,1,1],[0,2,1]]
```

```text
Top:
3 2 1
2 1 0
1 0 0
Front: [3,2,1]
Side:  [3,2,1]
```

Same pattern with center-back support removed, 9 blocks:

```json
[[0,0,3],[1,0,2],[2,0,1],[0,1,2],[0,2,1]]
```

Projection puzzle example:

```text
Top:
0 1 0
1 1 1
Front: [2,3,1]
Side:  [1,3]
Height map: [[1,0,1],[0,1,2],[1,1,3],[2,1,1]]
```
