const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const zlib = require('node:zlib');

const APP_ROOT = path.resolve(process.env.MERCAFORTE_APP_DIR || path.join(__dirname, '../../../mercaforte_app'));
const DEFAULT_DIRECTORY = path.join(APP_ROOT, 'assets/maps/morelos-centro');
const FONTS = ['Noto Sans Regular', 'Noto Sans Medium', 'Noto Sans Italic'];

function verifyMap(directory = DEFAULT_DIRECTORY) {
  const manifest = JSON.parse(fs.readFileSync(path.join(directory, 'manifest.json')));
  assert.equal(manifest.schemaVersion, 1);
  assert.equal(manifest.id, 'morelos-centro');
  assert.deepEqual(manifest.center, { latitude: 18.860124, longitude: -99.185444 });
  assert.equal(manifest.sideMeters, 50000);
  assert.equal(manifest.coverageMode, 'square');
  assert(!Object.hasOwn(manifest, 'municipalities'));
  assert.equal(manifest.minCameraZoom, 9);
  assert.equal(manifest.minDataZoom, 0);
  assert.equal(manifest.maxDataZoom, 15);
  assert.equal(manifest.maxCameraZoom, 19);
  const [west, south, east, north] = manifest.bounds;
  assert(west < east && south < north && manifest.bounds.every(Number.isFinite));
  assert(Math.abs((west + east) / 2 - manifest.center.longitude) < 1e-8);
  assert(Math.abs((south + north) / 2 - manifest.center.latitude) < 1e-5);
  let bytes = 0;
  for (const [name, record] of Object.entries(manifest.files)) {
    assert(!path.isAbsolute(name) && !name.split('/').includes('..'), `Ruta inválida: ${name}`);
    const data = fs.readFileSync(path.join(directory, name));
    assert.equal(data.length, record.bytes, `Tamaño inválido: ${name}`);
    assert.equal(crypto.createHash('sha256').update(data).digest('hex'), record.sha256, `SHA-256 inválido: ${name}`);
    bytes += data.length;
  }
  assert.equal(bytes, manifest.totalResourceBytes);
  const actual = fs.readdirSync(directory, { recursive: true })
    .filter(name => name !== 'manifest.json' && fs.statSync(path.join(directory, name)).isFile()).sort();
  assert.deepEqual(actual, Object.keys(manifest.files).sort(), 'Archivos no registrados en el manifiesto');
  for (const font of FONTS) {
    // Todos los bloques BMP, incluidos acentos y cualquier etiqueta de los datos.
    for (let first = 0; first < 65536; first += 256) {
      assert(manifest.files[`fonts/${font}/${first}-${first + 255}.pbf`], `Faltan glifos: ${font}/${first}`);
    }
  }
  for (const name of ['sprites/light.json', 'sprites/light.png', 'sprites/light@2x.json', 'sprites/light@2x.png',
    'fonts/OFL.txt', 'sprites/LICENSE.md', 'STYLE-LICENSE.txt', 'ATTRIBUTION.txt']) {
    assert(manifest.files[name], `Falta recurso: ${name}`);
  }
  const archive = fs.readFileSync(path.join(directory, 'map.pmtiles'));
  assert.equal(archive.subarray(0, 7).toString(), 'PMTiles');
  assert.equal(archive[7], 3);
  assert.equal(archive[99], 1, 'Se requieren teselas vectoriales MVT');
  assert.equal(archive[100], 0);
  assert.equal(archive[101], 15);
  manifest.bounds.forEach((value, index) => {
    assert(Math.abs(archive.readInt32LE(102 + index * 4) / 1e7 - value) < 1e-6, 'Cobertura PMTiles diferente');
  });
  const metadataOffset = Number(archive.readBigUInt64LE(24));
  const metadataLength = Number(archive.readBigUInt64LE(32));
  let metadataBytes = archive.subarray(metadataOffset, metadataOffset + metadataLength);
  if (archive[97] === 2) metadataBytes = zlib.gunzipSync(metadataBytes);
  const metadata = JSON.parse(metadataBytes);
  assert.equal(metadata.version, manifest.tilesetVersion);
  assert.equal(metadata['planetiler:osm:osmosisreplicationtime'], manifest.dataDate);
  assert.equal(metadata['mercaforte:coverage'], 'square');
  assert.deepEqual(metadata['mercaforte:center'], manifest.center);
  assert.equal(metadata['mercaforte:side_meters'], 50000);
  const sourceLayers = new Set(metadata.vector_layers.map(layer => layer.id));
  const style = JSON.parse(fs.readFileSync(path.join(directory, 'style.json')));
  const prefix = 'asset://maps/morelos-centro/';
  assert.equal(style.version, 8);
  assert.equal(style.glyphs, `${prefix}fonts/{fontstack}/{range}.pbf`);
  assert.equal(style.sprite, `${prefix}sprites/light`);
  assert.deepEqual(Object.keys(style.sources), ['protomaps']);
  assert.equal(style.sources.protomaps.url, `pmtiles://${prefix}map.pmtiles`);
  assert.equal(style.sources.protomaps.maxzoom, 15);
  for (const layer of style.layers) {
    if (layer.source) assert.equal(layer.source, 'protomaps');
    if (layer['source-layer']) assert(sourceLayers.has(layer['source-layer']), `Capa incompatible: ${layer.id}`);
    const textFonts = JSON.stringify(layer.layout?.['text-font'] ?? []);
    for (const match of textFonts.matchAll(/Noto Sans [A-Za-z]+/g)) assert(FONTS.includes(match[0]));
  }
  assert(!manifest.files['municipalities.osm.json'] && !manifest.files['coverage.geojson'], 'Quedaron recortes municipales');
  assert(manifest.clipping.verifiedFeatures > 0 && manifest.clipping.inputFeatures > manifest.clipping.retainedFeatures);
  return manifest;
}

module.exports = { verifyMap, DEFAULT_DIRECTORY, APP_ROOT };
if (require.main === module) {
  const directory = process.argv[2] ? path.resolve(process.argv[2]) : DEFAULT_DIRECTORY;
  const manifest = verifyMap(directory);
  const totalBytes = manifest.totalResourceBytes + fs.statSync(path.join(directory, 'manifest.json')).size;
  console.log(`Mapa ${manifest.version}: ${Object.keys(manifest.files).length} recursos verificados; paquete completo ${(totalBytes / 1e6).toFixed(2)} MB.`);
}
