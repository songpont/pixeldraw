const test = require('node:test');
const assert = require('node:assert/strict');
const PixelEngine = require('../pixel-engine.js');

function countPainted(colors) {
  return colors.filter(c => c !== 'transparent').length;
}

test('brush footprint matches size exactly (regression: even sizes used to collapse)', () => {
  const e = new PixelEngine({ gridW: 10, gridH: 10 });
  const layer = e.getActiveLayer('down');
  e.brush(layer, 5, 5, '#ffffff', 1);
  assert.equal(countPainted(layer.data), 1, 'size 1 -> 1x1');

  layer.data = e.newLayerData();
  e.brush(layer, 5, 5, '#ffffff', 2);
  assert.equal(countPainted(layer.data), 4, 'size 2 -> 2x2');

  layer.data = e.newLayerData();
  e.brush(layer, 5, 5, '#ffffff', 3);
  assert.equal(countPainted(layer.data), 9, 'size 3 -> 3x3');

  layer.data = e.newLayerData();
  e.brush(layer, 5, 5, '#ffffff', 4);
  assert.equal(countPainted(layer.data), 16, 'size 4 -> 4x4');
});

test('brush respects mirrorX/mirrorY/both', () => {
  const e = new PixelEngine({ gridW: 10, gridH: 10 });
  const layer = e.getActiveLayer('down');

  e.mirrorX = true;
  e.brush(layer, 2, 2, '#fff', 1);
  assert.equal(layer.data[2 * 10 + 2], '#fff');
  assert.equal(layer.data[2 * 10 + 7], '#fff', 'mirrored across X');

  e.mirrorX = false;
  e.mirrorY = true;
  layer.data = e.newLayerData();
  e.brush(layer, 2, 2, '#fff', 1);
  assert.equal(layer.data[7 * 10 + 2], '#fff', 'mirrored across Y');

  e.mirrorX = true;
  layer.data = e.newLayerData();
  e.brush(layer, 2, 2, '#fff', 1);
  assert.equal(countPainted(layer.data), 4, 'both mirrors -> 4 painted cells');
});

test('drawLine connects two points with no gaps (Bresenham)', () => {
  const e = new PixelEngine({ gridW: 20, gridH: 20 });
  const layer = e.getActiveLayer('down');
  e.drawLine(layer, 0, 0, 10, 5, '#000', 1);
  // every row between y=0..5 should have at least one painted cell
  for (let y = 0; y <= 5; y++) {
    const rowHasPaint = layer.data.slice(y * 20, y * 20 + 20).some(c => c !== 'transparent');
    assert.ok(rowHasPaint, `row ${y} should have a painted cell`);
  }
});

test('drawRectOutline paints only the border, not the interior', () => {
  const e = new PixelEngine({ gridW: 10, gridH: 10 });
  const layer = e.getActiveLayer('down');
  e.drawRectOutline(layer, 2, 2, 6, 6, '#f00', 1);
  assert.equal(layer.data[2 * 10 + 2], '#f00', 'corner painted');
  assert.equal(layer.data[4 * 10 + 4], 'transparent', 'interior stays empty');
});

test('floodFill only replaces contiguous matching color, respects mirror', () => {
  const e = new PixelEngine({ gridW: 6, gridH: 6 });
  const layer = e.getActiveLayer('down');
  // wall down the middle so fill from the left doesn't leak right
  for (let y = 0; y < 6; y++) layer.data[y * 6 + 3] = '#wall';
  e.floodFill(layer, 0, 0, '#blue');
  assert.equal(layer.data[0 * 6 + 0], '#blue');
  assert.equal(layer.data[0 * 6 + 3], '#wall', 'wall untouched');
  assert.equal(layer.data[0 * 6 + 4], 'transparent', 'fill did not leak past the wall');

  e.mirrorX = true;
  layer.data = e.newLayerData();
  e.floodFill(layer, 0, 0, '#blue');
  assert.equal(countPainted(layer.data), 36, 'mirrored fill covers whole 6x6 grid');
});

test('undo/redo round-trip restores exact pixel data', () => {
  const e = new PixelEngine({ gridW: 5, gridH: 5 });
  const dir = 'down';
  e.pushUndo();
  e.brush(e.getActiveLayer(dir), 1, 1, '#a', 1);
  assert.equal(countPainted(e.compositeArray(dir)), 1);

  assert.equal(e.undo(), true);
  assert.equal(countPainted(e.compositeArray(dir)), 0);

  assert.equal(e.redo(), true);
  assert.equal(countPainted(e.compositeArray(dir)), 1);

  assert.equal(e.undo(), true);
  assert.equal(e.undo(), false, 'undo stack empty returns false, does not throw');
});

test('discardLastUndo cancels an in-progress stroke without touching redo', () => {
  const e = new PixelEngine({ gridW: 5, gridH: 5 });
  const dir = 'down';
  e.pushUndo();
  e.brush(e.getActiveLayer(dir), 1, 1, '#a', 1);
  assert.equal(e.discardLastUndo(), true);
  assert.equal(countPainted(e.compositeArray(dir)), 0, 'stroke was discarded');
  assert.equal(e.redoStack.length, 0, 'redo stack untouched by cancel');
});

test('layer CRUD: add, duplicate, move, delete, rename, visibility', () => {
  const e = new PixelEngine({ gridW: 4, gridH: 4 });
  const dir = 'down';
  e.addLayer(dir, 'Sky');
  const f = e.ensureFrameDir(dir);
  assert.equal(f.layers.length, 2);
  assert.equal(f.active, 1);

  e.getActiveLayer(dir).data[0] = '#fff';
  const dup = e.duplicateLayer(dir, 1);
  assert.equal(dup.data[0], '#fff', 'duplicate copies pixel data');
  assert.equal(f.layers.length, 3);
  assert.equal(f.active, 2, 'active moves to the new duplicate');

  assert.equal(e.moveLayer(dir, 2, -1), true);
  assert.equal(f.layers[1].name, 'Sky copy', 'duplicate moved down one slot');

  assert.equal(e.moveLayer(dir, 0, -1), false, 'cannot move bottom layer further down');

  const vis = e.toggleLayerVisibility(dir, 0);
  assert.equal(vis, false);
  assert.equal(f.layers[0].visible, false);

  assert.equal(e.renameLayer(dir, 0, '  Ground  '), true);
  assert.equal(f.layers[0].name, 'Ground', 'name is trimmed');
  assert.equal(e.renameLayer(dir, 0, '   '), false, 'blank name rejected');

  assert.equal(e.deleteLayer(dir, 0), true);
  assert.equal(f.layers.length, 2);
  assert.equal(e.deleteLayer(dir, 0), true);
  assert.equal(e.deleteLayer(dir, 0), false, 'cannot delete the last remaining layer');
});

test('resize wipes all directions and clears undo history', () => {
  const e = new PixelEngine({ gridW: 8, gridH: 8 });
  e.pushUndo();
  e.brush(e.getActiveLayer('down'), 1, 1, '#a', 1);
  assert.equal(e.undoStack.length, 1);

  e.resize(16, 16);
  assert.equal(e.gridW, 16);
  assert.equal(e.gridH, 16);
  assert.equal(e.undoStack.length, 0);
  assert.equal(countPainted(e.compositeArray('down')), 0);
  assert.equal(e.getActiveLayer('down').data.length, 256);
});

test('serialize -> loadSerialized round-trip preserves pixel data and palette', () => {
  const e = new PixelEngine({ gridW: 4, gridH: 4 });
  e.brush(e.getActiveLayer('down'), 0, 0, '#123456', 1);
  e.addPaletteColor('#123456');
  const payload = e.serialize();

  const e2 = new PixelEngine({ gridW: 4, gridH: 4 });
  const ok = e2.loadSerialized(payload);
  assert.equal(ok, true);
  assert.deepEqual(e2.compositeArray('down'), e.compositeArray('down'));
  assert.ok(e2.palette.includes('#123456'));
});

test('loadSerialized rejects payloads whose layer size does not match declared grid', () => {
  const e = new PixelEngine({ gridW: 4, gridH: 4 });
  const bad = { v: 1, gridW: 4, gridH: 4, palette: [], currentDir: 'down', frames: { down: { active: 0, layers: [{ name: 'x', visible: true, data: new Array(9).fill('transparent') }] } } };
  assert.equal(e.loadSerialized(bad), false, 'mismatched layer length is dropped, restore reports failure');
});

test('importColorsAsLayer resizes the grid when the imported image size differs', () => {
  const e = new PixelEngine({ gridW: 4, gridH: 4 });
  const colors = new Array(6 * 6).fill('transparent');
  colors[0] = '#ff0000';
  const { sizeChanged } = e.importColorsAsLayer('down', 6, 6, colors, 'import');
  assert.equal(sizeChanged, true);
  assert.equal(e.gridW, 6);
  assert.equal(e.gridH, 6);
  assert.ok(e.palette.includes('#ff0000'));
});

test('decodeRGBAToColors turns alpha=0 into transparent and others into hex', () => {
  // 2x1 image: first pixel transparent, second pixel opaque red
  const rgba = new Uint8ClampedArray([10, 20, 30, 0, 255, 0, 0, 255]);
  const colors = PixelEngine.decodeRGBAToColors(rgba, 2, 1);
  assert.deepEqual(colors, ['transparent', '#ff0000']);
});

test('isEmpty / filledDirCount track painted directions', () => {
  const e = new PixelEngine({ gridW: 4, gridH: 4 });
  assert.equal(e.filledDirCount(), 0);
  e.brush(e.getActiveLayer('down'), 0, 0, '#a', 1);
  assert.equal(e.isEmpty('down'), false);
  assert.equal(e.filledDirCount(), 1);
});
