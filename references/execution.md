# AlgeoMath Execution Reference

Open this only when you need to run the local scripts.

## Stack Blocks

Preferred flow: compute stack-block coordinates, inject them into AlgeoMath, and leave the AlgeoMath 3D browser window open for the user.

## Beginner Setup

For a teacher or first-time user, run the setup script once. It installs Playwright and the Chromium browser used by the automatic AlgeoMath placement script. It is safe to run again because already-installed items are skipped.

```powershell
powershell -ExecutionPolicy Bypass -File "C:\Users\choi2\.codex\skills\algeomath-skills\setup_algeomath.ps1"
```

Do not pass `--close` during normal stack-block work. The harness keeps the browser open by default.

Inject explicit block coordinates:

```powershell
pythonw "C:\Users\choi2\.codex\skills\algeomath-skills\scripts\stackblocks_harness.py" `
  --blocks '[[x,y,z], ...]'
```

Inject custom height map:

```powershell
pythonw "C:\Users\choi2\.codex\skills\algeomath-skills\scripts\stackblocks_harness.py" `
  --height-map '[[x,y,h], ...]'
```

Show every possible case separated in one scene:

```powershell
pythonw "C:\Users\choi2\.codex\skills\algeomath-skills\scripts\stackblocks_harness.py" `
  --cases '[[[x,y,h], ...], [[x,y,h], ...]]' `
  --gap 4
```

Inject preset:

```powershell
pythonw "C:\Users\choi2\.codex\skills\algeomath-skills\scripts\stackblocks_harness.py" `
  --preset reference-pyramid
```

Use screenshots, logs, coordinate printing, or `--close` only when the user explicitly asks for verification, diagnostics, or closing the browser.

## 2D

Use `scripts/algeo2d.py` and `algeo2d.md` only for flat AlgeoMath Kids 2D point, line, polygon, and coordinate-plane work.
