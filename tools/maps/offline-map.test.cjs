const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');
const crypto = require('node:crypto');
const { test } = require('node:test');
const { createRequire } = require('node:module');
const { verifyMap, DEFAULT_DIRECTORY, APP_ROOT } = require('./verify-map.cjs');
const appRequire = createRequire(path.join(APP_ROOT, 'package.json'));
const { transformFileSync } = appRequire('@babel/core');

function loadModule(filename, dependencies) {
  const exports = {};
  const { code } = transformFileSync(path.resolve(APP_ROOT, filename), {
    babelrc: false, configFile: false, plugins: [appRequire.resolve('@babel/plugin-transform-modules-commonjs')],
  });
  vm.runInNewContext(code, {
    exports, require(name) {
      assert(Object.hasOwn(dependencies, name), `Dependencia inesperada: ${name}`);
      return dependencies[name];
    },
  });
  return exports;
}

test('el paquete real contiene cartografía, fuentes, sprites y los ocho municipios', () => {
  const manifest = verifyMap();
  assert.equal(manifest.files['map.pmtiles'].bytes > 0, true);
  assert.equal(manifest.files['fonts/Noto Sans Regular/0-255.pbf'].bytes > 0, true);
});

test('Expo fija el SDK nativo que puede leer rangos PMTiles desde el APK', () => {
  const app = JSON.parse(fs.readFileSync(path.join(APP_ROOT, 'app.json')));
  const plugin = app.expo.plugins.find(value => Array.isArray(value) && value[0] === '@maplibre/maplibre-react-native');
  assert.equal(plugin?.[1]?.android?.nativeVersion, '13.7.1');
});

test('la compilación rechaza archivos ausentes, dañados y estilos que requieren internet', t => {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'mercaforte-map-test-'));
  t.after(() => fs.rmSync(temp, { recursive: true, force: true }));
  fs.cpSync(DEFAULT_DIRECTORY, temp, { recursive: true });
  const target = path.join(temp, 'sprites/light.png');
  const original = fs.readFileSync(target);
  fs.writeFileSync(target, Buffer.from('corrupto'));
  assert.throws(() => verifyMap(temp), /Tamaño inválido/);
  fs.rmSync(target);
  assert.throws(() => verifyMap(temp), /ENOENT/);
  fs.writeFileSync(target, original);
  const stylePath = path.join(temp, 'style.json');
  const style = JSON.parse(fs.readFileSync(stylePath));
  style.glyphs = 'https://example.com/{fontstack}/{range}.pbf';
  fs.writeFileSync(stylePath, JSON.stringify(style));
  const manifestPath = path.join(temp, 'manifest.json');
  const manifest = JSON.parse(fs.readFileSync(manifestPath));
  const data = fs.readFileSync(stylePath);
  manifest.totalResourceBytes += data.length - manifest.files['style.json'].bytes;
  manifest.files['style.json'] = { bytes: data.length, sha256: crypto.createHash('sha256').update(data).digest('hex') };
  fs.writeFileSync(manifestPath, JSON.stringify(manifest));
  assert.throws(() => verifyMap(temp), /glyphs|asset:\/\/maps/);
});

test('las ocho cabeceras están cubiertas; Toluca, CDMX y municipios no incluidos quedan fuera', () => {
  const manifest = JSON.parse(fs.readFileSync(path.join(DEFAULT_DIRECTORY, 'manifest.json')));
  const storage = loadModule('src/storage/offlineMapStorage.js', {
    'react-native': { Platform: { OS: 'android' } },
    '../../assets/maps/morelos-centro/manifest.json': manifest,
  });
  const service = loadModule('src/services/offlineMapService.js', {
    '../storage/offlineMapStorage': storage,
  });
  const definition = service.getOfflineMapDefinition();
  assert.equal(definition.mapStyle, 'asset://maps/morelos-centro/style.json');
  for (const center of [[-99.234, 18.924], [-99.177, 18.884], [-99.067, 18.882],
    [-99.185, 18.840], [-99.226, 18.852], [-99.230, 18.781], [-99.268, 19.029], [-99.101, 18.986]]) {
    assert.equal(service.isPositionInOfflineMap(center, definition.bounds, definition.coverage), true);
  }
  for (const position of [[-99.133, 19.433], [-99.656, 19.283], [-99.326, 18.730]]) {
    assert.equal(service.isPositionInOfflineMap(position, definition.bounds, definition.coverage), false);
  }
  assert.equal(service.isPositionInOfflineMap([null, null], definition.bounds), false);
  assert.equal(service.isPositionInOfflineMap([NaN, 18.9], definition.bounds), false);
  assert.equal(service.isViewportInOfflineMap([-99.25, 18.80, -99.20, 18.90], definition.bounds), true);
  assert.equal(service.isViewportInOfflineMap([-99.50, 18.80, -99.20, 18.90], definition.bounds), false);
  const polygon = { type: 'Polygon', coordinates: [
    [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]],
    [[4, 4], [6, 4], [6, 6], [4, 6], [4, 4]],
  ] };
  assert.equal(service.isPositionInOfflineMap([1, 1], [0, 0, 10, 10], polygon), true);
  assert.equal(service.isPositionInOfflineMap([5, 5], [0, 0, 10, 10], polygon), false);
  assert.equal(service.isPositionInOfflineMap([0, 1], [0, 0, 10, 10], polygon), true);
});
