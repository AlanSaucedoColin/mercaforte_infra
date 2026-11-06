#!/usr/bin/env python3
"""Comprueba que el APK contiene exactamente los recursos verificados del mapa."""
import hashlib
import json
import os
from pathlib import Path
import sys
import zipfile

root = Path(os.environ.get('MERCAFORTE_APP_DIR', Path(__file__).resolve().parents[3] / 'mercaforte_app')).expanduser().resolve()
manifest = json.loads((root / 'assets/maps/morelos-centro/manifest.json').read_text())
apk = Path(sys.argv[1])
with zipfile.ZipFile(apk) as archive:
    prefix = 'assets/maps/morelos-centro/'
    for name, record in manifest['files'].items():
        info = archive.getinfo(prefix + name)
        data = archive.read(info)
        assert len(data) == record['bytes'], name
        assert hashlib.sha256(data).hexdigest() == record['sha256'], name
        if name.endswith('.pmtiles'):
            assert info.compress_type == zipfile.ZIP_STORED, 'PMTiles debe estar sin comprimir dentro del APK'
    bundled = json.loads(archive.read(prefix + 'manifest.json'))
    assert bundled == manifest
    assert 'assets/index.android.bundle' in archive.namelist(), 'El APK de prueba necesita JavaScript empaquetado'
total_map_bytes = manifest['totalResourceBytes'] + (root / 'assets/maps/morelos-centro/manifest.json').stat().st_size
print(f'APK verificado: {apk.stat().st_size / 1e6:.2f} MB; mapa completo: {total_map_bytes / 1e6:.2f} MB.')
