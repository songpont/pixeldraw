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
    '#2a1e18',
    '#f7c8a6',
    '#dea882',
    '#36261e',
    '#f0f0eb',
    '#cccccb',
    '#3c5fa0',
    '#283759',
    '#2d201a',
    '#4b8de0',
    '#e0a24b',
  ];

  function isBlank(c) {
    return !c || c === 'transparent';
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
      return { id: this.layerIdCounter, name: name || ('Layer ' + this.layerIdCounter), visible: true, data: this.newLayerData() };
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

    compositeArray(dir) {
      dir = dir || this.currentDir;
      const f = this.ensureFrameDir(dir);
      const out = new Array(this.gridW * this.gridH).fill('transparent');
      f.layers.forEach(layer => {
        if (!layer.visible) return;
        for (let i = 0; i < out.length; i++) {
          const c = layer.data[i];
          if (!isBlank(c)) out[i] = c;
        }
      });
      return out;
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

    pickColorAt(dir, x, y) {
      const data = this.compositeArray(dir);
      const c = data[y * this.gridW + x];
      return isBlank(c) ? null : c;
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
      const copy = { id: this.layerIdCounter, name: layer.name + ' copy', visible: layer.visible, data: layer.data.slice() };
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
    importColorsAsLayer(dir, w, h, colors, layerName) {
      const sizeChanged = (w !== this.gridW || h !== this.gridH);
      if (sizeChanged) {
        this.gridW = w; this.gridH = h;
        this.dirs.forEach(d => { this.frames[d.key] = this._blankFrame(); });
        this.undoStack = [];
        this.redoStack = [];
      }
      const seen = new Set(this.palette);
      colors.forEach(c => { if (!isBlank(c) && !seen.has(c)) { seen.add(c); this.palette.push(c); } });

      const f = this.ensureFrameDir(dir);
      this.layerIdCounter++;
      const layer = { id: this.layerIdCounter, name: layerName || ('Layer ' + this.layerIdCounter), visible: true, data: colors.slice() };
      f.layers.push(layer);
      f.active = f.layers.length - 1;
      this.undoStack = [];
      this.redoStack = [];
      return { layer, sizeChanged };
    }

    /* ---- serialize / restore (for autosave, export, etc.) ---- */

    serialize() {
      const payload = { v: 1, gridW: this.gridW, gridH: this.gridH, palette: this.palette.slice(), currentDir: this.currentDir, frames: {} };
      this.dirs.forEach(d => {
        const f = this.frames[d.key];
        payload.frames[d.key] = {
          active: f.active,
          layers: f.layers.map(l => ({ name: l.name, visible: l.visible, data: l.data.slice() })),
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
          .map(l => { this.layerIdCounter++; return { id: this.layerIdCounter, name: l.name || 'Layer', visible: l.visible !== false, data: l.data.slice() }; });
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
  PixelEngine.brushExtent = brushExtent;
  PixelEngine.floodFillFrom = floodFillFrom;
  PixelEngine.decodeRGBAToColors = decodeRGBAToColors;

  return PixelEngine;
});
