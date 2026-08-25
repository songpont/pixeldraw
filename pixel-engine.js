/*
 * PixelEngine — pure data/drawing core for Sprite Forge.
 * No DOM, no Canvas, no localStorage. Safe to run in Node for tests
 * or in the browser as a plain <script> (attaches window.PixelEngine).
 */
(function (root, factory) {
  const mod = factory();
  if (typeof module === 'object' && module.exports) {
    module.exports = mod;
  } else {
    root.PixelEngine = mod;
  }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  const DIRS = [
    { key: 'down', label: 'Down' },
    { key: 'up', label: 'Up' },
    { key: 'left', label: 'Left' },
    { key: 'right', label: 'Right' },
  ];

  const DEFAULT_PALETTE = [
    'transparent',
    '#000000', '#1a1a1a', '#333333', '#4d4d4d', '#666666', '#999999', '#cccccc', '#ffffff',
    '#2a1e18', '#5a3d2b', '#8a5a3c', '#c1875a', '#e8b183', '#f7c8a6',
    '#7a1f1f', '#c1272d', '#e8563c', '#f2994a', '#f6c445', '#fff275',
    '#234d3a', '#2f7a3c', '#57a659', '#8fd18a',
    '#14213d', '#1d4ed8', '#3fa7f7', '#9ecbff',
    '#3c1f5e', '#7b3fa0', '#b06cd9', '#e63980',
  ];

  const PALETTE_SETS = {
    default: DEFAULT_PALETTE,
    grayscale: (function () {
      const set = ['transparent'];
      for (let i = 0; i < 32; i++) {
        const v = Math.round(i * 255 / 31);
        const h = v.toString(16).padStart(2, '0');
        set.push('#' + h + h + h);
      }
      return set;
    })(),
    retro: [
      'transparent',
      '#0f0f1e', '#ffffff', '#ff3355', '#ff8c42', '#ffd23f', '#b4e33d', '#4dff88', '#2de1c2',
      '#2ea3ff', '#4361ee', '#7b2ff7', '#d63aff', '#ff5cad', '#8b5a2b', '#c68642', '#ffdca8',
      '#3a5a40', '#588157', '#a3b18a', '#dad7cd', '#1b263b', '#415a77', '#778da9', '#e0e1dd',
      '#6a040f', '#9d0208', '#d00000', '#dc2f02', '#e85d04', '#f48c06', '#faa307', '#ffba08',
    ],
    pastel: [
      'transparent',
      '#f5f5f5', '#e0e0e0', '#c2c2c2', '#4a4a4a',
      '#ffd6e8', '#ffb3d1', '#ff8fb3', '#f76c9c',
      '#ffe0c2', '#ffcb99', '#ffb366', '#ffa14d',
      '#fff3b0', '#ffe97a', '#ffdd57', '#f4c430',
      '#d9f2d0', '#b8e6a3', '#93d675', '#6fbf4f',
      '#c2f0e6', '#94e0d1', '#66d0bc', '#3cb6a3',
      '#cde0ff', '#a3c6ff', '#7aa8ff', '#5c8df6',
      '#e0c2ff', '#c99bff', '#b17bff', '#9a5cff',
    ],
  };

  function isBlank(c) {
    return !c || c === 'transparent';
  }

  function hexToRgb(hex) {
    const n = parseInt(hex.slice(1), 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }

  function rgbToHex(r, g, b) {
    const clamp = v => Math.max(0, Math.min(255, Math.round(v)));
    return '#' + [clamp(r), clamp(g), clamp(b)].map(v => v.toString(16).padStart(2, '0')).join('');
  }

  /* ---- stateless helpers (also exposed as statics) ---- */

  function brushExtent(size) {
    const r0 = Math.floor((size - 1) / 2);
    const r1 = size - 1 - r0;
    return [r0, r1];
  }

  function floodFillFrom(x, y, color, data, w, h) {
    const target = data[y * w + x];
    if (target === color) return;
    const stack = [[x, y]];
    while (stack.length) {
      const c = stack.pop();
      const cx = c[0], cy = c[1];
      if (cx < 0 || cx >= w || cy < 0 || cy >= h) continue;
      const idx = cy * w + cx;
      if (data[idx] !== target) continue;
      data[idx] = color;
      stack.push([cx + 1, cy], [cx - 1, cy], [cx, cy + 1], [cx, cy - 1]);
    }
  }

  // Frequency-ranked distinct colors, most common first, capped at maxCount.
  // Ties keep first-seen order (Array#sort is stable) for deterministic output.
  function dominantColors(colors, maxCount) {
    const freq = new Map();
    const order = [];
    colors.forEach(c => {
      if (isBlank(c)) return;
      if (!freq.has(c)) { freq.set(c, 0); order.push(c); }
      freq.set(c, freq.get(c) + 1);
    });
    order.sort((a, b) => freq.get(b) - freq.get(a));
    return order.slice(0, maxCount);
  }

  // Uint8ClampedArray-like RGBA buffer (w*h*4) -> flat array of hex/'transparent' strings.
  // Pure computation — no Canvas/Image needed, so it's directly unit-testable.
  function decodeRGBAToColors(rgba, w, h) {
    const out = new Array(w * h).fill('transparent');
    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        const idx = (y * w + x) * 4;
        const a = rgba[idx + 3];
        if (a === 0) {
          out[y * w + x] = 'transparent';
        } else {
          out[y * w + x] = '#' + [rgba[idx], rgba[idx + 1], rgba[idx + 2]]
            .map(v => v.toString(16).padStart(2, '0')).join('');
        }
      }
    }
    return out;
  }

  class PixelEngine {
    constructor(opts) {
      opts = opts || {};
      this.gridW = opts.gridW || 32;
      this.gridH = opts.gridH || 32;
      this.dirs = opts.dirs || DIRS;
      this.palette = (opts.palette && opts.palette.slice()) || DEFAULT_PALETTE.slice();
      this.mirrorX = false;
      this.mirrorY = false;
      this.layerIdCounter = 1;
      this.currentDir = this.dirs[0].key;
      this.frames = {};
      this.undoStack = [];
      this.redoStack = [];
      this.dirs.forEach(d => { this.frames[d.key] = this._blankFrame(); });
    }

    /* ---- layer/frame data ---- */

    newLayerData() {
      return new Array(this.gridW * this.gridH).fill('transparent');
    }

    newLayer(name) {
      this.layerIdCounter++;
      return { id: this.layerIdCounter, name: name || ('Layer ' + this.layerIdCounter), visible: true, opacity: 1, data: this.newLayerData() };
    }

    _blankFrame() {
      return { layers: [this.newLayer('Layer 1')], active: 0 };
    }

    ensureFrameDir(dir) {
      const f = this.frames[dir];
      if (!f || !f.layers.length || f.layers[0].data.length !== this.gridW * this.gridH) {
        this.frames[dir] = this._blankFrame();
      }
      return this.frames[dir];
    }

    getActiveLayer(dir) {
      dir = dir || this.currentDir;
      const f = this.ensureFrameDir(dir);
      if (f.active >= f.layers.length) f.active = f.layers.length - 1;
      return f.layers[f.active];
    }

    // Composites all visible layers bottom-to-top using standard Porter-Duff
    // "over" alpha blending, so partial layer.opacity actually shows through
    // to whatever is beneath it (or to nothing, if nothing is beneath it yet).
    // Returns 'transparent', a plain '#rrggbb' hex when the result is fully
    // opaque, or an 'rgba(r,g,b,a)' string when it's partially transparent —
    // all three are valid Canvas fillStyle values, so callers that just draw
    // the result (render, export) need no changes to consume this.
    compositeArray(dir) {
      dir = dir || this.currentDir;
      const f = this.ensureFrameDir(dir);
      const n = this.gridW * this.gridH;
      const accR = new Float64Array(n), accG = new Float64Array(n), accB = new Float64Array(n), accA = new Float64Array(n);
      f.layers.forEach(layer => {
        if (!layer.visible) return;
        const layerOpacity = layer.opacity == null ? 1 : layer.opacity;
        if (layerOpacity <= 0) return;
        for (let i = 0; i < n; i++) {
          const c = layer.data[i];
          if (isBlank(c)) continue;
          const [r, g, b] = hexToRgb(c);
          const srcA = layerOpacity;
          const dstA = accA[i];
          const outA = srcA + dstA * (1 - srcA);
          if (outA <= 0) continue;
          accR[i] = (r * srcA + accR[i] * dstA * (1 - srcA)) / outA;
          accG[i] = (g * srcA + accG[i] * dstA * (1 - srcA)) / outA;
          accB[i] = (b * srcA + accB[i] * dstA * (1 - srcA)) / outA;
          accA[i] = outA;
        }
      });
      const out = new Array(n);
      for (let i = 0; i < n; i++) {
        if (accA[i] <= 0) out[i] = 'transparent';
        else if (accA[i] >= 1) out[i] = rgbToHex(accR[i], accG[i], accB[i]);
        else out[i] = 'rgba(' + Math.round(accR[i]) + ',' + Math.round(accG[i]) + ',' + Math.round(accB[i]) + ',' + accA[i].toFixed(3) + ')';
      }
      return out;
    }

    setLayerOpacity(dir, idx, opacity) {
      const f = this.ensureFrameDir(dir);
      f.layers[idx].opacity = Math.max(0, Math.min(1, opacity));
    }

    isEmpty(dir) {
      const f = this.frames[dir];
      if (!f) return true;
      return f.layers.every(l => l.data.every(isBlank));
    }

    filledDirCount() {
      return this.dirs.filter(d => !this.isEmpty(d.key)).length;
    }

    setCurrentDir(dir) {
      this.currentDir = dir;
    }

    /* ---- undo/redo ---- */

    cloneFrame(f) {
      return { active: f.active, layers: f.layers.map(l => ({ id: l.id, name: l.name, visible: l.visible, data: l.data.slice() })) };
    }

    snapshotFrame(dir) {
      return this.cloneFrame(this.frames[dir || this.currentDir]);
    }

    pushUndo() {
      this.undoStack.push(this.snapshotFrame());
      if (this.undoStack.length > 60) this.undoStack.shift();
      this.redoStack = [];
    }

    undo() {
      if (!this.undoStack.length) return false;
      this.redoStack.push(this.snapshotFrame());
      this.frames[this.currentDir] = this.undoStack.pop();
      return true;
    }

    redo() {
      if (!this.redoStack.length) return false;
      this.undoStack.push(this.snapshotFrame());
      this.frames[this.currentDir] = this.redoStack.pop();
      return true;
    }

    // Discards the most recent pushUndo() snapshot back onto the current
    // frame WITHOUT touching redoStack — used to cancel an in-progress stroke.
    discardLastUndo() {
      if (!this.undoStack.length) return false;
      this.frames[this.currentDir] = this.undoStack.pop();
      return true;
    }

    /* ---- resize ---- */

    resize(w, h) {
      this.gridW = w;
      this.gridH = h;
      this.dirs.forEach(d => { this.frames[d.key] = this._blankFrame(); });
      this.undoStack = [];
      this.redoStack = [];
    }

    /* ---- painting primitives ---- */

    setCell(layer, x, y, color) {
      if (x < 0 || x >= this.gridW || y < 0 || y >= this.gridH) return;
      layer.data[y * this.gridW + x] = color;
    }

    setCellMirror(layer, x, y, color) {
      this.setCell(layer, x, y, color);
      if (this.mirrorX) this.setCell(layer, this.gridW - 1 - x, y, color);
      if (this.mirrorY) this.setCell(layer, x, this.gridH - 1 - y, color);
      if (this.mirrorX && this.mirrorY) this.setCell(layer, this.gridW - 1 - x, this.gridH - 1 - y, color);
    }

    brush(layer, x, y, color, size) {
      const [r0, r1] = brushExtent(size);
      for (let dy = -r0; dy <= r1; dy++) {
        for (let dx = -r0; dx <= r1; dx++) {
          this.setCellMirror(layer, x + dx, y + dy, color);
        }
      }
    }

    drawLine(layer, x0, y0, x1, y1, color, size) {
      let dx = Math.abs(x1 - x0), sx = x0 < x1 ? 1 : -1;
      let dy = -Math.abs(y1 - y0), sy = y0 < y1 ? 1 : -1;
      let err = dx + dy;
      while (true) {
        this.brush(layer, x0, y0, color, size);
        if (x0 === x1 && y0 === y1) break;
        const e2 = 2 * err;
        if (e2 >= dy) { err += dy; x0 += sx; }
        if (e2 <= dx) { err += dx; y0 += sy; }
      }
    }

    drawRectOutline(layer, x0, y0, x1, y1, color, size) {
      const xa = Math.min(x0, x1), xb = Math.max(x0, x1);
      const ya = Math.min(y0, y1), yb = Math.max(y0, y1);
      for (let x = xa; x <= xb; x++) { this.brush(layer, x, ya, color, size); this.brush(layer, x, yb, color, size); }
      for (let y = ya; y <= yb; y++) { this.brush(layer, xa, y, color, size); this.brush(layer, xb, y, color, size); }
    }

    drawEllipse(layer, x0, y0, x1, y1, color, size) {
      const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
      const rx = Math.abs(x1 - x0) / 2, ry = Math.abs(y1 - y0) / 2;
      if (rx < 0.5 && ry < 0.5) { this.brush(layer, x0, y0, color, size); return; }
      const steps = Math.max(32, Math.round((rx + ry) * 4));
      let px = null, py = null;
      for (let i = 0; i <= steps; i++) {
        const t = (i / steps) * Math.PI * 2;
        const x = Math.round(cx + rx * Math.cos(t));
        const y = Math.round(cy + ry * Math.sin(t));
        if (px !== null) this.drawLine(layer, px, py, x, y, color, size);
        else this.brush(layer, x, y, color, size);
        px = x; py = y;
      }
    }

    floodFill(layer, x, y, color) {
      const w = this.gridW, h = this.gridH;
      floodFillFrom(x, y, color, layer.data, w, h);
      if (this.mirrorX) floodFillFrom(w - 1 - x, y, color, layer.data, w, h);
      if (this.mirrorY) floodFillFrom(x, h - 1 - y, color, layer.data, w, h);
      if (this.mirrorX && this.mirrorY) floodFillFrom(w - 1 - x, h - 1 - y, color, layer.data, w, h);
    }

    // Picks the flattened, fully-opaque color at (x,y) — if compositing left that
    // pixel partially transparent (an rgba() string), the alpha is dropped so the
    // picked color paints as a normal solid swatch, same as any other palette color.
    pickColorAt(dir, x, y) {
      const data = this.compositeArray(dir);
      const c = data[y * this.gridW + x];
      if (isBlank(c)) return null;
      if (c[0] === '#') return c;
      const m = /rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)/.exec(c);
      return m ? rgbToHex(parseFloat(m[1]), parseFloat(m[2]), parseFloat(m[3])) : c;
    }

    /* ---- layer CRUD ---- */

    addLayer(dir, name) {
      const f = this.ensureFrameDir(dir);
      const layer = this.newLayer(name);
      f.layers.push(layer);
      f.active = f.layers.length - 1;
      return layer;
    }

    deleteLayer(dir, idx) {
      const f = this.ensureFrameDir(dir);
      if (f.layers.length <= 1) return false;
      f.layers.splice(idx, 1);
      if (f.active >= f.layers.length) f.active = f.layers.length - 1;
      return true;
    }

    duplicateLayer(dir, idx) {
      const f = this.ensureFrameDir(dir);
      const layer = f.layers[idx];
      this.layerIdCounter++;
      const copy = { id: this.layerIdCounter, name: layer.name + ' copy', visible: layer.visible, opacity: layer.opacity == null ? 1 : layer.opacity, data: layer.data.slice() };
      f.layers.splice(idx + 1, 0, copy);
      f.active = idx + 1;
      return copy;
    }

    moveLayer(dir, idx, delta) {
      const f = this.ensureFrameDir(dir);
      const j = idx + delta;
      if (j < 0 || j >= f.layers.length) return false;
      const tmp = f.layers[idx]; f.layers[idx] = f.layers[j]; f.layers[j] = tmp;
      if (f.active === idx) f.active = j;
      else if (f.active === j) f.active = idx;
      return true;
    }

    renameLayer(dir, idx, name) {
      const f = this.ensureFrameDir(dir);
      if (!name || !name.trim()) return false;
      f.layers[idx].name = name.trim();
      return true;
    }

    toggleLayerVisibility(dir, idx) {
      const f = this.ensureFrameDir(dir);
      f.layers[idx].visible = !f.layers[idx].visible;
      return f.layers[idx].visible;
    }

    setActiveLayerIndex(dir, idx) {
      const f = this.ensureFrameDir(dir);
      f.active = idx;
    }

    clearActiveLayerData(dir) {
      this.getActiveLayer(dir).data = this.newLayerData();
    }

    pasteLayerData(dir, data, name) {
      const f = this.ensureFrameDir(dir);
      this.layerIdCounter++;
      const layer = { id: this.layerIdCounter, name: name || 'Pasted', visible: true, data: data.slice() };
      f.layers.push(layer);
      f.active = f.layers.length - 1;
      return layer;
    }

    /* ---- palette ---- */

    addPaletteColor(hex) {
      if (!this.palette.includes(hex)) this.palette.push(hex);
    }

    /* ---- import from decoded pixels ---- */

    // colors: flat array (w*h) of hex/'transparent' strings, already decoded by the caller
    // (see decodeRGBAToColors for the pure RGBA->hex step).
    // The working palette is REPLACED (not appended to) with the imported image's
    // own top maxPaletteColors most-frequent colors, so opening a busy/large image
    // never floods the palette with hundreds of one-off colors.
    importColorsAsLayer(dir, w, h, colors, layerName, maxPaletteColors) {
      maxPaletteColors = maxPaletteColors || 32;
      const sizeChanged = (w !== this.gridW || h !== this.gridH);
      if (sizeChanged) {
        this.gridW = w; this.gridH = h;
        this.dirs.forEach(d => { this.frames[d.key] = this._blankFrame(); });
        this.undoStack = [];
        this.redoStack = [];
      }
      const dominant = dominantColors(colors, maxPaletteColors);
      this.palette = ['transparent', ...dominant];

      const f = this.ensureFrameDir(dir);
      this.layerIdCounter++;
      const layer = { id: this.layerIdCounter, name: layerName || ('Layer ' + this.layerIdCounter), visible: true, data: colors.slice() };
      f.layers.push(layer);
      f.active = f.layers.length - 1;
      this.undoStack = [];
      this.redoStack = [];
      return { layer, sizeChanged, paletteColors: dominant };
    }

    // Places an importW x importH image as a NEW layer at the CURRENT canvas size —
    // unlike importColorsAsLayer, gridW/gridH/undo history/palette are never touched.
    // Defaults to centering the asset; content that falls outside the canvas is
    // clipped (dropped), which the returned `clipped` flag reports.
    importColorsAsLayerAt(dir, importW, importH, colors, layerName, offsetX, offsetY) {
      if (offsetX === undefined) offsetX = Math.floor((this.gridW - importW) / 2);
      if (offsetY === undefined) offsetY = Math.floor((this.gridH - importH) / 2);

      const w = this.gridW, h = this.gridH;
      const data = new Array(w * h).fill('transparent');
      let clipped = false;
      for (let y = 0; y < importH; y++) {
        const dy = y + offsetY;
        if (dy < 0 || dy >= h) { clipped = true; continue; }
        for (let x = 0; x < importW; x++) {
          const dx = x + offsetX;
          if (dx < 0 || dx >= w) { clipped = true; continue; }
          data[dy * w + dx] = colors[y * importW + x];
        }
      }

      const f = this.ensureFrameDir(dir);
      this.layerIdCounter++;
      const layer = { id: this.layerIdCounter, name: layerName || ('Layer ' + this.layerIdCounter), visible: true, data };
      f.layers.push(layer);
      f.active = f.layers.length - 1;
      return { layer, offsetX, offsetY, clipped };
    }

    /* ---- layer content transform (move / scale pixels within the canvas) ---- */

    // Bounding box of a layer's non-transparent pixels, or null if the layer is empty.
    layerContentBounds(dir, idx) {
      const f = this.ensureFrameDir(dir);
      const layer = f.layers[idx];
      const w = this.gridW, h = this.gridH;
      let minX = w, minY = h, maxX = -1, maxY = -1;
      for (let y = 0; y < h; y++) {
        for (let x = 0; x < w; x++) {
          if (!isBlank(layer.data[y * w + x])) {
            if (x < minX) minX = x;
            if (x > maxX) maxX = x;
            if (y < minY) minY = y;
            if (y > maxY) maxY = y;
          }
        }
      }
      if (maxX < 0) return null;
      return { minX, minY, maxX, maxY };
    }

    // Shifts a layer's pixel content by (dx, dy) canvas cells. Content shifted past
    // the canvas edge is dropped; vacated cells become transparent. No wrap-around.
    moveLayerContent(dir, idx, dx, dy) {
      const f = this.ensureFrameDir(dir);
      const layer = f.layers[idx];
      const w = this.gridW, h = this.gridH;
      const src = layer.data;
      const dst = new Array(w * h).fill('transparent');
      for (let y = 0; y < h; y++) {
        const sy = y - dy;
        if (sy < 0 || sy >= h) continue;
        for (let x = 0; x < w; x++) {
          const sx = x - dx;
          if (sx < 0 || sx >= w) continue;
          dst[y * w + x] = src[sy * w + sx];
        }
      }
      layer.data = dst;
    }

    // Scales a layer's pixel content by `factor` (nearest-neighbor), anchored on
    // (originX, originY) — defaults to the content's own bounding-box center so it
    // stays put wherever it currently sits, rather than drifting toward canvas center.
    // Returns false without modifying anything if the layer has no content to scale.
    scaleLayerContent(dir, idx, factor, originX, originY) {
      const f = this.ensureFrameDir(dir);
      const layer = f.layers[idx];
      const w = this.gridW, h = this.gridH;
      if (originX === undefined || originY === undefined) {
        const b = this.layerContentBounds(dir, idx);
        if (!b) return false;
        originX = (b.minX + b.maxX + 1) / 2;
        originY = (b.minY + b.maxY + 1) / 2;
      }
      const src = layer.data;
      const dst = new Array(w * h).fill('transparent');
      for (let y = 0; y < h; y++) {
        for (let x = 0; x < w; x++) {
          const sx = Math.floor(originX + (x + 0.5 - originX) / factor);
          const sy = Math.floor(originY + (y + 0.5 - originY) / factor);
          if (sx < 0 || sx >= w || sy < 0 || sy >= h) continue;
          dst[y * w + x] = src[sy * w + sx];
        }
      }
      layer.data = dst;
      return true;
    }

    /* ---- rectangular region ops (backs the marquee selection tool) ---- */

    // Copies a rect {x,y,w,h} of a layer's pixels out (row-major, w*h long).
    // Cells outside the canvas come back as 'transparent' rather than throwing,
    // so a selection dragged partway off-canvas can still be read cleanly.
    getRegionData(dir, idx, rect) {
      const f = this.ensureFrameDir(dir);
      const layer = f.layers[idx];
      const w = this.gridW, h = this.gridH;
      const out = new Array(rect.w * rect.h).fill('transparent');
      for (let ry = 0; ry < rect.h; ry++) {
        const cy = rect.y + ry;
        if (cy < 0 || cy >= h) continue;
        for (let rx = 0; rx < rect.w; rx++) {
          const cx = rect.x + rx;
          if (cx < 0 || cx >= w) continue;
          out[ry * rect.w + rx] = layer.data[cy * w + cx];
        }
      }
      return out;
    }

    // Clears a rect {x,y,w,h} of a layer to transparent, clipped to canvas bounds.
    clearRegion(dir, idx, rect) {
      const f = this.ensureFrameDir(dir);
      const layer = f.layers[idx];
      const w = this.gridW, h = this.gridH;
      for (let ry = 0; ry < rect.h; ry++) {
        const cy = rect.y + ry;
        if (cy < 0 || cy >= h) continue;
        for (let rx = 0; rx < rect.w; rx++) {
          const cx = rect.x + rx;
          if (cx < 0 || cx >= w) continue;
          layer.data[cy * w + cx] = 'transparent';
        }
      }
    }

    // Writes rw x rh `data` (row-major) onto a layer at (x, y), clipped to canvas
    // bounds. Every destination cell in range is overwritten — including with
    // 'transparent' source cells — matching how a moved/pasted rectangular
    // selection is expected to replace whatever was underneath it.
    stampRegion(dir, idx, x, y, rw, rh, data) {
      const f = this.ensureFrameDir(dir);
      const layer = f.layers[idx];
      const w = this.gridW, h = this.gridH;
      for (let ry = 0; ry < rh; ry++) {
        const cy = y + ry;
        if (cy < 0 || cy >= h) continue;
        for (let rx = 0; rx < rw; rx++) {
          const cx = x + rx;
          if (cx < 0 || cx >= w) continue;
          layer.data[cy * w + cx] = data[ry * rw + rx];
        }
      }
    }

    /* ---- serialize / restore (for autosave, export, etc.) ---- */

    serialize() {
      const payload = { v: 1, gridW: this.gridW, gridH: this.gridH, palette: this.palette.slice(), currentDir: this.currentDir, frames: {} };
      this.dirs.forEach(d => {
        const f = this.frames[d.key];
        payload.frames[d.key] = {
          active: f.active,
          layers: f.layers.map(l => ({ name: l.name, visible: l.visible, opacity: l.opacity == null ? 1 : l.opacity, data: l.data.slice() })),
        };
      });
      return payload;
    }

    // Merges a serialized payload into this engine. Returns true if anything was restored.
    loadSerialized(payload) {
      if (!payload || !payload.frames || !payload.gridW || !payload.gridH) return false;

      this.gridW = Math.max(1, Math.min(256, Math.round(payload.gridW) || this.gridW));
      this.gridH = Math.max(1, Math.min(256, Math.round(payload.gridH) || this.gridH));
      if (Array.isArray(payload.palette) && payload.palette.length) this.palette = payload.palette.slice();

      let restoredAny = false;
      const cellCount = this.gridW * this.gridH;
      this.dirs.forEach(d => {
        const fd = payload.frames[d.key];
        const layers = (fd && Array.isArray(fd.layers) ? fd.layers : [])
          .filter(l => Array.isArray(l.data) && l.data.length === cellCount)
          .map(l => { this.layerIdCounter++; return { id: this.layerIdCounter, name: l.name || 'Layer', visible: l.visible !== false, opacity: typeof l.opacity === 'number' ? Math.max(0, Math.min(1, l.opacity)) : 1, data: l.data.slice() }; });
        if (layers.length) {
          this.frames[d.key] = { active: Math.min(fd.active || 0, layers.length - 1), layers };
          restoredAny = true;
        }
      });
      if (!restoredAny) return false;

      if (payload.currentDir && this.dirs.some(d => d.key === payload.currentDir)) this.currentDir = payload.currentDir;
      return true;
    }
  }

  PixelEngine.DIRS = DIRS;
  PixelEngine.DEFAULT_PALETTE = DEFAULT_PALETTE;
  PixelEngine.PALETTE_SETS = PALETTE_SETS;
  PixelEngine.brushExtent = brushExtent;
  PixelEngine.floodFillFrom = floodFillFrom;
  PixelEngine.decodeRGBAToColors = decodeRGBAToColors;
  PixelEngine.dominantColors = dominantColors;
  PixelEngine.hexToRgb = hexToRgb;
  PixelEngine.rgbToHex = rgbToHex;

  return PixelEngine;
});
