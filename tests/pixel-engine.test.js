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

test('importColorsAsLayer REPLACES the palette rather than appending to it', () => {
  const e = new PixelEngine({ gridW: 2, gridH: 2, palette: ['transparent', '#deadbe'] });
  const colors = ['#ff0000', '#ff0000', '#00ff00', 'transparent'];
  e.importColorsAsLayer('down', 2, 2, colors, 'import');
  assert.equal(e.palette.includes('#deadbe'), false, 'old palette colors are discarded, not kept alongside');
  assert.deepEqual(e.palette, ['transparent', '#ff0000', '#00ff00']);
});

test('importColorsAsLayer caps the derived palette at maxPaletteColors, most-frequent first', () => {
  const e = new PixelEngine({ gridW: 1, gridH: 1 });
  // 5 distinct colors with clear, distinct frequencies: a x4, b x3, c x2, d x1, e x1
  const colors = ['a', 'a', 'a', 'a', 'b', 'b', 'b', 'c', 'c', 'd', 'e'];
  const { paletteColors } = e.importColorsAsLayer('down', 1, 1, colors, 'import', 3);
  assert.deepEqual(paletteColors, ['a', 'b', 'c'], 'only the 3 most frequent colors are kept, in frequency order');
  assert.deepEqual(e.palette, ['transparent', 'a', 'b', 'c']);
});

test('dominantColors ranks by frequency and ignores transparent', () => {
  const colors = ['#111', 'transparent', '#222', '#222', '#333', '#333', '#333', null, ''];
  assert.deepEqual(PixelEngine.dominantColors(colors, 10), ['#333', '#222', '#111']);
  assert.deepEqual(PixelEngine.dominantColors(colors, 2), ['#333', '#222'], 'respects the cap');
});

test('PALETTE_SETS ship 4 curated 32-color sets, each starting with transparent', () => {
  const sets = PixelEngine.PALETTE_SETS;
  ['default', 'grayscale', 'retro', 'pastel'].forEach(key => {
    const set = sets[key];
    assert.ok(Array.isArray(set), key + ' set exists');
    assert.equal(set[0], 'transparent', key + ' set starts with transparent');
    assert.equal(set.length, 33, key + ' set has exactly 32 colors + transparent');
    assert.equal(new Set(set).size, set.length, key + ' set has no duplicate colors');
  });
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

test('importColorsAsLayerAt places a smaller image centered without touching canvas size', () => {
  const e = new PixelEngine({ gridW: 8, gridH: 8 });
  const importColors = new Array(4 * 4).fill('#f00'); // solid 4x4 red square
  const { layer, offsetX, offsetY, clipped } = e.importColorsAsLayerAt('down', 4, 4, importColors, 'asset');
  assert.equal(e.gridW, 8, 'canvas width untouched');
  assert.equal(e.gridH, 8, 'canvas height untouched');
  assert.equal(offsetX, 2, 'centered horizontally: (8-4)/2');
  assert.equal(offsetY, 2, 'centered vertically');
  assert.equal(clipped, false);
  // corners of the centered 4x4 block
  assert.equal(layer.data[2 * 8 + 2], '#f00');
  assert.equal(layer.data[5 * 8 + 5], '#f00');
  // outside the placed block stays transparent
  assert.equal(layer.data[0], 'transparent');
  assert.equal(countPainted(layer.data), 16);
});

test('importColorsAsLayerAt clips content that falls outside the canvas and reports it', () => {
  const e = new PixelEngine({ gridW: 4, gridH: 4 });
  const importColors = new Array(6 * 6).fill('#0f0'); // bigger than the canvas
  const { offsetX, clipped } = e.importColorsAsLayerAt('down', 6, 6, importColors, 'big');
  assert.equal(offsetX, -1, 'centering a 6-wide asset on a 4-wide canvas yields a negative offset');
  assert.equal(clipped, true);
  assert.equal(e.gridW, 4, 'canvas still untouched even when the asset overflows it');
});

test('importColorsAsLayerAt does not touch the working palette (unlike importColorsAsLayer)', () => {
  const e = new PixelEngine({ gridW: 8, gridH: 8, palette: ['transparent', '#123456'] });
  e.importColorsAsLayerAt('down', 2, 2, ['#ff0000', '#ff0000', '#ff0000', '#ff0000'], 'asset');
  assert.deepEqual(e.palette, ['transparent', '#123456'], 'palette is left exactly as the caller had it');
});

test('moveLayerContent shifts pixels and drops content pushed past the edge (no wrap)', () => {
  const e = new PixelEngine({ gridW: 4, gridH: 4 });
  const layer = e.getActiveLayer('down');
  layer.data[0] = '#a'; // top-left corner
  e.moveLayerContent('down', 0, 1, 1);
  assert.equal(layer.data[1 * 4 + 1], '#a', 'pixel moved by (1,1)');
  assert.equal(layer.data[0], 'transparent', 'old position is vacated');

  // shove it off the bottom-right edge entirely
  e.moveLayerContent('down', 0, 10, 10);
  assert.equal(countPainted(layer.data), 0, 'content pushed off-canvas is dropped, not wrapped');
});

test('scaleLayerContent scales around the content bounding-box center by default', () => {
  const e = new PixelEngine({ gridW: 8, gridH: 8 });
  const layer = e.getActiveLayer('down');
  layer.data[4 * 8 + 4] = '#a'; // single dot at (4,4)
  const ok = e.scaleLayerContent('down', 0, 2);
  assert.equal(ok, true);
  // a single-pixel dot scaled 2x around its own center becomes a 2x2 block
  assert.equal(countPainted(layer.data), 4);
  assert.equal(layer.data[4 * 8 + 4], '#a');
});

test('scaleLayerContent returns false and leaves an empty layer untouched', () => {
  const e = new PixelEngine({ gridW: 8, gridH: 8 });
  const layer = e.getActiveLayer('down');
  const before = layer.data.slice();
  const ok = e.scaleLayerContent('down', 0, 2);
  assert.equal(ok, false);
  assert.deepEqual(layer.data, before);
});

test('layerContentBounds reports the tight box around painted pixels, or null when empty', () => {
  const e = new PixelEngine({ gridW: 8, gridH: 8 });
  const layer = e.getActiveLayer('down');
  assert.equal(e.layerContentBounds('down', 0), null);
  layer.data[2 * 8 + 3] = '#a';
  layer.data[5 * 8 + 6] = '#a';
  assert.deepEqual(e.layerContentBounds('down', 0), { minX: 3, minY: 2, maxX: 6, maxY: 5 });
});

test('getRegionData extracts a rect and treats out-of-canvas cells as transparent', () => {
  const e = new PixelEngine({ gridW: 4, gridH: 4 });
  const layer = e.getActiveLayer('down');
  // paint a distinct color at every cell so we can tell exactly what got extracted
  for (let i = 0; i < 16; i++) layer.data[i] = 'c' + i;

  // fully in-bounds 2x2 rect starting at (1,1): cells 5,6,9,10
  assert.deepEqual(e.getRegionData('down', 0, { x: 1, y: 1, w: 2, h: 2 }), ['c5', 'c6', 'c9', 'c10']);

  // rect that hangs off the top-left edge — out-of-canvas cells come back transparent
  assert.deepEqual(
    e.getRegionData('down', 0, { x: -1, y: -1, w: 2, h: 2 }),
    ['transparent', 'transparent', 'transparent', 'c0']
  );
});

test('clearRegion only clears the given rect, clipped to canvas bounds', () => {
  const e = new PixelEngine({ gridW: 4, gridH: 4 });
  const layer = e.getActiveLayer('down');
  layer.data.fill('#a');
  e.clearRegion('down', 0, { x: 1, y: 1, w: 2, h: 2 });
  assert.equal(layer.data[1 * 4 + 1], 'transparent');
  assert.equal(layer.data[2 * 4 + 2], 'transparent');
  assert.equal(layer.data[0], '#a', 'outside the rect is untouched');
  assert.equal(countPainted(layer.data), 12, '16 - 4 cleared = 12 remain');
});

test('stampRegion overwrites the destination (including with transparent source cells), clipped to canvas', () => {
  const e = new PixelEngine({ gridW: 4, gridH: 4 });
  const layer = e.getActiveLayer('down');
  layer.data.fill('#bg');
  const patch = ['#x', 'transparent', 'transparent', '#x']; // 2x2, checkerboard
  e.stampRegion('down', 0, 1, 1, 2, 2, patch);
  assert.equal(layer.data[1 * 4 + 1], '#x');
  assert.equal(layer.data[1 * 4 + 2], 'transparent', 'transparent source cells DO overwrite the destination');
  assert.equal(layer.data[2 * 4 + 1], 'transparent');
  assert.equal(layer.data[2 * 4 + 2], '#x');
  assert.equal(layer.data[0], '#bg', 'outside the stamp is untouched');

  // stamping partly off the right/bottom edge clips silently, no throw
  e.stampRegion('down', 0, 3, 3, 2, 2, ['#y', '#y', '#y', '#y']);
  assert.equal(layer.data[3 * 4 + 3], '#y');
});

test('getRegionData -> stampRegion round-trip reproduces a moved region exactly', () => {
  const e = new PixelEngine({ gridW: 6, gridH: 6 });
  const layer = e.getActiveLayer('down');
  layer.data[1 * 6 + 1] = '#p';
  layer.data[2 * 6 + 2] = '#q';
  const rect = { x: 1, y: 1, w: 2, h: 2 };
  const lifted = e.getRegionData('down', 0, rect);
  e.clearRegion('down', 0, rect);
  assert.equal(countPainted(layer.data), 0, 'original spot is fully cleared after lifting');
  e.stampRegion('down', 0, 3, 3, rect.w, rect.h, lifted);
  assert.equal(layer.data[3 * 6 + 3], '#p');
  assert.equal(layer.data[4 * 6 + 4], '#q');
  assert.equal(countPainted(layer.data), 2, 'moved content lands intact at the new spot');
});
