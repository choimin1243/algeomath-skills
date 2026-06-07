---
name: algeomath
description: Use when working with AlgeoMath Kids 2D shapes or 3D stack blocks, especially when inferring stack-block coordinates from images and placing them in AlgeoMath.
---

# AlgeoMath

Route AlgeoMath Kids work while keeping the default context small.

## Routing

- 3D stack blocks, cubes, layer counts, or image-based block placement: read `references/stackblocks-coordinate.md`.
- Running scripts or browser injection: read `references/execution.md`.
- 2D points, lines, polygons, or coordinate-plane drawings: read `algeo2d.md`.
- For beginner/teacher setup, use `setup_algeomath.ps1` from `references/execution.md` before automatic browser placement.

## Stack-Block Core

- **Always reset the site before injecting.** Pass `--reset` first or call `window.AlgeomathPoly.api.load` with an empty scene before placing any blocks. Never add blocks on top of existing ones.
- Always determine `left/right/front/back/up` before creating coordinates.
- Author coordinates are `x` left to right, `y` front to back, `z` upward.
- Layer counts are reference information only.
- Prefer exact `--blocks '[[x,y,z], ...]'` injection when accuracy matters.
- After finding stack-block coordinates, place them in AlgeoMath and leave the AlgeoMath 3D browser window open for the user.
- Do not pass `--close` for normal stack-block work. Keep the 3D window open unless the user explicitly asks to close it.
- Skip separate verification workflows such as screenshot comparison or top/front/side validation unless the user explicitly asks for verification.
- If multiple answers or interpretations are possible, place all cases in one AlgeoMath scene with clear spacing between them instead of choosing only one.

## Image Workflow

1. Read `references/stackblocks-coordinate.md`.
2. Count both footprint width and footprint depth.
3. Build a height map `[[x,y,h], ...]` or explicit block list `[[x,y,z], ...]`.
4. Inject through `scripts/stackblocks_harness.py` and keep the AlgeoMath 3D window open.
5. When there are several possible arrangements, inject all of them with `--cases` and a gap so they appear separated.

## Known Pattern

Triangular staircase pyramid, 10 blocks:

```json
[[0,0,3],[1,0,2],[2,0,1],[0,1,2],[1,1,1],[0,2,1]]
```

Top view:

```text
3 2 1
2 1 0
1 0 0
```

Front and side views are both `[3,2,1]`.
