#!/usr/bin/env python3
"""Renderiza el mapa del APK en un Android USB, sin sesión ni descarga de rutas."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('MERCAFORTE_APP_DIR', HERE.parents[2] / 'mercaforte_app')).expanduser().resolve()


def run(command, **kwargs):
    return subprocess.run(list(map(str, command)), check=True, **kwargs)


def main(args):
    sdk = Path(os.environ.get('ANDROID_HOME', '/opt/homebrew/share/android-commandlinetools'))
    java = Path(os.environ.get('JAVA_HOME', '/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home')) / 'bin'
    tools = sdk / 'build-tools/36.0.0'
    platform = sdk / 'platforms/android-36/android.jar'
    library = next((Path.home() / '.gradle/caches/modules-2/files-2.1/org.maplibre.gl/android-sdk-opengl/13.7.1').rglob('*.aar'))
    adb = ['adb', '-s', args.serial] if args.serial else ['adb', '-d']
    with tempfile.TemporaryDirectory(prefix='mercaforte-native-smoke-') as directory:
        directory = Path(directory)
        classes = directory / 'classes'
        dex = directory / 'dex'
        classes.mkdir()
        dex.mkdir()
        with zipfile.ZipFile(library) as archive:
            (directory / 'maplibre.jar').write_bytes(archive.read('classes.jar'))
        (directory / 'AndroidManifest.xml').write_text('''<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="com.mercaforte.offlinetest">
<uses-sdk android:minSdkVersion="24" android:targetSdkVersion="36" />
<application android:label="Mercaforte offline verification" android:debuggable="true" />
<instrumentation android:name="com.mercaforte.offlinetest.OfflineMapSmoke" android:targetPackage="com.mercaforte.app" android:functionalTest="true" />
</manifest>''')
        run([java / 'javac', '-source', '8', '-target', '8', '-cp',
             f'{platform}{os.pathsep}{directory / "maplibre.jar"}', '-d', classes,
             HERE / 'OfflineMapSmoke.java'])
        run([tools / 'd8', '--lib', platform, '--classpath', directory / 'maplibre.jar', '--output', dex,
             classes / 'com/mercaforte/offlinetest/OfflineMapSmoke.class'])
        unsigned = directory / 'unsigned.apk'
        run([tools / 'aapt2', 'link', '-I', platform, '--manifest', directory / 'AndroidManifest.xml', '-o', unsigned])
        with zipfile.ZipFile(unsigned, 'a') as archive:
            archive.write(dex / 'classes.dex', 'classes.dex')
        apk = directory / 'smoke.apk'
        run([tools / 'zipalign', '-f', '4', unsigned, apk])
        run([tools / 'apksigner', 'sign', '--ks', ROOT / 'android/app/debug.keystore', '--ks-key-alias',
             'androiddebugkey', '--ks-pass', 'pass:android', apk])
        run([*adb, 'install', '-r', '-d', '--user', '0', Path(args.apk).resolve()])
        run([*adb, 'install', '-r', apk])
        original = {key: subprocess.check_output([*adb, 'shell', 'settings', 'get', 'global', key], text=True).strip()
                    for key in ['airplane_mode_on', 'wifi_on']}
        try:
            run([*adb, 'shell', 'cmd', 'connectivity', 'airplane-mode', 'enable'])
            run([*adb, 'shell', 'svc', 'wifi', 'disable'])
            completed = run([*adb, 'shell', 'am', 'instrument', '-w', '-r',
                             'com.mercaforte.offlinetest/com.mercaforte.offlinetest.OfflineMapSmoke'],
                            text=True, capture_output=True, timeout=240)
            print(completed.stdout, flush=True)
            assert 'OK: seis municipios' in completed.stdout and 'INSTRUMENTATION_CODE: -1' in completed.stdout
        finally:
            run([*adb, 'shell', 'cmd', 'connectivity', 'airplane-mode',
                 'enable' if original['airplane_mode_on'] == '1' else 'disable'])
            run([*adb, 'shell', 'svc', 'wifi', 'enable' if original['wifi_on'] == '1' else 'disable'])
            subprocess.run([*adb, 'uninstall', 'com.mercaforte.offlinetest'], check=False, capture_output=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apk', required=True, help='APK de validación firmado con la clave debug local')
    parser.add_argument('--serial', help='Serial ADB, si hay varios dispositivos')
    main(parser.parse_args())
