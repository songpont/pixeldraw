// Render still 3D views of every story stage for the printed case book.
// Usage: node scripts/render_views.js web/honnokhuk-3d.html output/views [three.min.js OrbitControls.js]
// The optional local copies of three.js are used when the CDN is not reachable.
const {chromium} = require('playwright');
const path = require('path'), fs = require('fs');
const [html, outDir, threeLocal, orbitLocal] = process.argv.slice(2);
fs.mkdirSync(outDir, {recursive: true});
(async () => {
  const b = await chromium.launch({args: ['--use-gl=swiftshader', '--enable-webgl', '--ignore-gpu-blocklist']});
  const p = await b.newPage({viewport: {width: 1500, height: 960}, deviceScaleFactor: 1.5, reducedMotion: 'reduce'});
  p.on('pageerror', e => console.error('page error:', e.message));
  if (threeLocal) {
    await p.route(/three\.min\.js/, r => r.fulfill({path: threeLocal, contentType: 'text/javascript'}));
    await p.route(/OrbitControls\.js/, r => r.fulfill({path: orbitLocal, contentType: 'text/javascript'}));
  }
  await p.route(/fonts\.(googleapis|gstatic)/, r => r.abort());
  await p.goto('file://' + path.resolve(html));
  await p.waitForFunction(() => window.HNK);
  await p.evaluate(() => HNK.capture(true));
  await p.waitForTimeout(1500);
  const shots = [];
  const n = await p.evaluate(() => HNK.stages);
  const CLOSE = ['overview', 'overview', 'm4', 'm2', 'm3', 'temple', 'm1', 'overview'];
  for (let i = 0; i < n; i++) {
    shots.push([`stage${i + 1}`, i, CLOSE[i]]);
    if (CLOSE[i] !== 'overview') shots.push([`stage${i + 1}-overview`, i, 'overview']);
  }
  for (const [name, i, cam] of shots) {
    await p.evaluate(([i, cam]) => HNK.stage(i, cam), [i, cam]);
    await p.waitForTimeout(900);
    await p.screenshot({path: path.join(outDir, name + '.jpg'), type: 'jpeg', quality: 85});
    console.log('rendered', name);
  }
  await b.close();
})();
