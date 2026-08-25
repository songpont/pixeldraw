# Sprite Forge — Pixel Editor

A browser-based pixel art editor built for 4-direction character sprites (Down / Up / Left / Right), with layers, mirrored drawing, a rectangular selection tool, and a curated palette-set system. No build step, no dependencies — open `pixel_editor.html` and start drawing.

## Features

- **4-direction pose sheet** — draw Down/Up/Left/Right poses independently, export as a single sprite sheet
- **Layers** — add, delete, duplicate, reorder, rename, show/hide, per-layer opacity slider (real alpha compositing, not a flat overwrite)
- **Tools** — pen, eraser, fill, eyedropper (`Alt`+click from any tool), line, rectangle, ellipse, rectangular selection (`S`)
- **Selection tool** — drag to select, drag-from-inside to move, arrow keys to nudge, copy/cut/paste a region (or the whole layer when nothing's selected), works across directions and layers
- **Mirror X / Mirror Y** — symmetric drawing for characters and tiles
- **Move / scale a layer's content** — nudge or 2×/½× scale around the content's own center, independent of the whole canvas
- **Import as Layer** — bring in a differently-sized image as a new layer without resizing the project canvas (auto-centered, clipped if it doesn't fit)
- **Open File** — load an image as the project's starting point (resizes the canvas to match)
- **Palette sets** — switch between curated 32-color sets (Default, Grayscale, Retro, Pastel), auto-derive a capped 32-color palette from an opened file, or build and save your own named palette from any reference image
- **Canvas background preview** — dark / white / gray / green checker presets to preview your sprite against different backdrops (preview only, doesn't affect exports)
- **Zoom / pan** with a lock toggle to prevent accidental scroll-zoom while drawing
- **Undo/redo**, autosave to the browser (`localStorage`), and PNG export (single frame or full 4-direction sheet)

Press `?` in the app for the full keyboard shortcut list.

## Quick start

Just open `pixel_editor.html` in a browser — it works directly from the filesystem (`file://`), no server required.

```bash
open pixel_editor.html          # macOS
# or serve it locally if you prefer:
python3 -m http.server 8080
```

`pixel_editor.html` must stay in the same folder as `pixel-engine.js` (it's loaded as a plain `<script src="pixel-engine.js">`, not a module).

## Project structure

```
pixel_editor.html    UI: canvas rendering, event handling, toolbar — consumes window.PixelEngine
pixel-engine.js       Core: layers, frames, undo/redo, drawing/compositing algorithms — zero DOM/Canvas
                       dependencies, usable as a plain <script> or a Node module
tests/                Unit tests for pixel-engine.js (Node's built-in test runner)
```

The drawing/data core is deliberately kept separate from the DOM so it can be unit-tested without a browser and reused independently.

## Testing

```bash
npm test
# or
node --test
```

## License

Licensed under [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/) (Attribution-NonCommercial) — see [LICENSE](LICENSE). Commercial use is not permitted.
