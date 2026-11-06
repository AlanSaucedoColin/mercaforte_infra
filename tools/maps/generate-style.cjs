const fs = require('node:fs');
const path = require('node:path');

// La dependencia se descarga y verifica en un directorio temporal, no en la app.
const { layers, namedFlavor } = require(path.resolve(process.argv[2]));
const prefix = 'asset://maps/morelos-centro/';
const style = {
  version: 8,
  name: 'Morelos Centro — mapa incluido',
  glyphs: `${prefix}fonts/{fontstack}/{range}.pbf`,
  sprite: `${prefix}sprites/light`,
  sources: {
    protomaps: {
      type: 'vector',
      url: `pmtiles://${prefix}map.pmtiles`,
      minzoom: 0,
      maxzoom: 15,
      attribution: '<a href="https://protomaps.com">Protomaps</a> © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    },
  },
  layers: layers('protomaps', namedFlavor('light'), { lang: 'es' }),
};
fs.writeFileSync(process.argv[3], `${JSON.stringify(style, null, 2)}\n`);
