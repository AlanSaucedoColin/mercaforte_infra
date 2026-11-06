#!/usr/bin/env python3
"""Genera el paquete regional. Descargas solo en desarrollo; nunca en el móvil."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import time
import urllib.request
import zipfile
from clip_map import square_coverage, clip_archive, verify_clipped_archive

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('MERCAFORTE_APP_DIR', HERE.parents[2] / 'mercaforte_app')).expanduser().resolve()
CONFIG = json.loads((HERE / 'map-config.json').read_text())
OUTPUT = ROOT / 'assets/maps' / CONFIG['id']
USER_AGENT = 'Mercaforte-offline-map-build/1.0'


def download(url, destination):
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
            with urllib.request.urlopen(request, timeout=120) as response:
                destination.write_bytes(response.read())
            return
        except Exception:
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


def build(args):
    if not (ROOT / 'package.json').is_file():
        raise SystemExit('No se encontró mercaforte_app; configura MERCAFORTE_APP_DIR con su ruta.')
    pmtiles = args.pmtiles or os.environ.get('PMTILES') or shutil.which('pmtiles')
    if not pmtiles:
        raise SystemExit('Instala go-pmtiles 1.31.2 o usa --pmtiles /ruta/pmtiles (ver README.md).')
    # Construir fuera del paquete instalado: un fallo conserva la versión anterior.
    with tempfile.TemporaryDirectory(prefix='mercaforte-map-') as temp:
        temp = Path(temp)
        output = temp / 'package'
        output.mkdir()
        region = square_coverage(CONFIG['center'], CONFIG['sideMeters'])
        bounds = list(region.bounds)
        print('Cobertura:', bounds, flush=True)
        extracted = temp / 'unclipped.pmtiles'
        subprocess.run([pmtiles, 'extract', CONFIG['sourceUrl'], str(extracted),
                        '--bbox=' + ','.join(map(str, bounds)), '--maxzoom=15', '--download-threads=4'], check=True)
        clipping = clip_archive(extracted, output / 'map.pmtiles', region, CONFIG)
        print('Recorte de geometrías:', clipping, flush=True)
        clipping['verifiedFeatures'] = verify_clipped_archive(output / 'map.pmtiles', region)
        subprocess.run([pmtiles, 'verify', str(output / 'map.pmtiles')], check=True)
        metadata = json.loads(subprocess.check_output([pmtiles, 'show', str(output / 'map.pmtiles'), '--metadata']))
        assert metadata['version'] == CONFIG['tilesetVersion'], 'Versión de datos inesperada'
        (output / 'tileset-metadata.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + '\n')

        archive = temp / 'style.tgz'
        version = CONFIG['stylePackageVersion']
        download(f'https://registry.npmjs.org/@protomaps/basemaps/-/basemaps-{version}.tgz', archive)
        assert hashlib.sha1(archive.read_bytes()).hexdigest() == CONFIG['stylePackageSha1'], 'Checksum del generador inválido'
        with tarfile.open(archive) as tar:
            tar.extractall(temp / 'style', filter='data')
        subprocess.run(['node', str(HERE / 'generate-style.cjs'),
                        str(temp / 'style/package/dist/cjs/index.cjs'), str(output / 'style.json')], check=True)

        revision = CONFIG['assetsRevision']
        archive = temp / 'assets.zip'
        download(f'https://github.com/protomaps/basemaps-assets/archive/{revision}.zip', archive)
        with zipfile.ZipFile(archive) as z:
            z.extractall(temp / 'assets')
        assets = next((temp / 'assets').iterdir())
        (output / 'fonts').mkdir()
        for font in ['Noto Sans Regular', 'Noto Sans Medium', 'Noto Sans Italic']:
            shutil.copytree(assets / 'fonts' / font, output / 'fonts' / font)
        shutil.copyfile(assets / 'fonts/OFL.txt', output / 'fonts/OFL.txt')
        (output / 'sprites').mkdir()
        for name in ['light.png', 'light.json', 'light@2x.png', 'light@2x.json']:
            shutil.copyfile(assets / 'sprites/v4' / name, output / 'sprites' / name)
        download('https://raw.githubusercontent.com/tangrams/icons/master/LICENSE.md', output / 'sprites/LICENSE.md')
        download('https://raw.githubusercontent.com/protomaps/basemaps/main/LICENSE.md', output / 'STYLE-LICENSE.txt')
        (output / 'ATTRIBUTION.txt').write_text(
            'Cartografía: Protomaps, OpenStreetMap contributors y Natural Earth.\n'
            'https://www.openstreetmap.org/copyright — ODbL 1.0\n'
            'https://docs.protomaps.com/basemaps/downloads\n'
            'Estilo: @protomaps/basemaps (BSD-3-Clause; STYLE-LICENSE.txt).\n'
            'Fuentes: Noto Sans (SIL OFL; fonts/OFL.txt).\n'
            'Sprites: basemaps-assets / Tangram Icons (MIT; sprites/LICENSE.md).\n')
        files = {}
        for file in sorted(output.rglob('*')):
            if file.is_file():
                data = file.read_bytes()
                files[file.relative_to(output).as_posix()] = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
        manifest = {
            'schemaVersion': 1, 'id': CONFIG['id'], 'version': CONFIG['packageVersion'],
            'bounds': bounds, 'center': CONFIG['center'], 'sideMeters': CONFIG['sideMeters'],
            'coverageMode': CONFIG['coverageMode'], 'clipping': clipping,
            'minDataZoom': 0, 'maxDataZoom': 15, 'maxCameraZoom': 19,
            'minCameraZoom': CONFIG['minCameraZoom'],
            'sourceUrl': CONFIG['sourceUrl'], 'tilesetVersion': metadata['version'],
            'dataDate': metadata['planetiler:osm:osmosisreplicationtime'],
            'stylePackageVersion': version, 'assetsRevision': revision,
            'generatedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'totalResourceBytes': sum(f['bytes'] for f in files.values()), 'files': files,
        }
        (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
        subprocess.run(['node', str(HERE / 'verify-map.cjs'), str(output)], check=True)
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        previous = OUTPUT.with_name(OUTPUT.name + '.previous')
        if previous.exists():
            raise RuntimeError(f'Ya existe {previous}; revísalo antes de regenerar.')
        if OUTPUT.exists():
            OUTPUT.rename(previous)
        try:
            shutil.copytree(output, OUTPUT)
        except Exception:
            if OUTPUT.exists():
                shutil.rmtree(OUTPUT)
            if previous.exists():
                previous.rename(OUTPUT)
            raise
        if previous.exists():
            shutil.rmtree(previous)
        print(f'Paquete listo: {manifest["totalResourceBytes"] / 1e6:.2f} MB de recursos', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pmtiles', help='Ejecutable go-pmtiles 1.31.2')
    build(parser.parse_args())
