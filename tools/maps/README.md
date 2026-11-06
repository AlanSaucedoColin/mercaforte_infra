# Herramientas del mapa de Morelos Centro

Estas herramientas pertenecen a `mercaforte_infra`, no al código de la app. Descargan, generan y verifican el
paquete que consume `mercaforte_app`. La app conserva únicamente los recursos, su integración visual y el
plugin de Expo necesario para empaquetarlos; compilarla no requiere clonar este repositorio.

Por defecto se busca `mercaforte_app` junto a `mercaforte_infra`. Si está en otra ubicación, define
`MERCAFORTE_APP_DIR=/ruta/a/mercaforte_app`. Esta variable se admite en todas las herramientas, incluidas las
pruebas Node. Las pruebas de integración JS usan Babel desde las dependencias ya instaladas de la app.

La app Android lleva un paquete en su directorio `assets/maps/morelos-centro/`. No descarga cartografía durante el uso,
el bootstrap ni el inicio de sesión. El mapa está en los assets del APK y no se borra al cerrar sesión
o reiniciar la base operativa. El proveedor de datos es Protomaps/OpenStreetMap; el estilo es Light en español.

## Cobertura y recursos

Cuadrado continuo de **50 × 50 km**, centrado en **18.860124, -99.185444**, con 25 km desde el centro hacia
cada dirección cardinal. Se calculan sus límites con GeographicLib/WGS84 y se registran `center`, `sideMeters`
y `bounds` en el manifiesto. No se consultan ni aplican límites municipales o estatales.

La dimensión se eligió a partir de la captura de referencia: una escala de 5 km en unos 146 píxeles de una
imagen de 720 píxeles de ancho equivale a unos 25 km de ancho visible y unos 43 km de alto de mapa. El cuadrado
de 50 km cubre ese encuadre con margen; el número de la barra de escala no representa el lado ni el radio.

Seleccionar teselas con `pmtiles extract --bbox` también incluye geometrías vecinas en zooms generales.
`clip_map.py` elimina únicamente lo que cae fuera del cuadrado. Se verifica el contenido completo del archivo,
incluidos zooms bajos, con tolerancia de una unidad MVT por redondeo. La cámara queda limitada al encuadre
regional, con zoom mínimo 9. Coatetelco y otras zonas antes excluidas por los polígonos se muestran completas.

Los datos llegan hasta zoom 15 y la cámara hasta 19 por ampliación de las teselas existentes; no aparecen
detalles nuevos al ampliar por encima de 15. Fuera del cuadrado solo permanecen las capas operativas y el fondo,
sin intentar cargar cartografía remota.

El paquete contiene el PMTiles, estilo, sprites 1x/2x y los 256 bloques BMP de las tres fuentes Noto Sans usadas,
incluidos acentos y números de marcadores. El manifiesto registra fecha de datos, cobertura y SHA-256 de cada
archivo. No se empaquetan archivos de límites municipales ni máscaras de polígonos.

## Verificar y regenerar

Desde la raíz de `mercaforte_infra`:

```sh
node tools/maps/verify-map.cjs
node --test tools/maps/offline-map.test.cjs
```

Para regenerar se requiere Node, Python >=3.12 y [go-pmtiles 1.31.2](https://github.com/protomaps/go-pmtiles/releases/tag/v1.31.2).
Instala el ejecutable oficial correspondiente a tu plataforma; no se incluye dentro de la app.
El recorte vectorial requiere las dependencias Python de infraestructura:

```sh
python3 -m venv tools/maps/.venv
tools/maps/.venv/bin/pip install -r tools/maps/requirements.txt
tools/maps/.venv/bin/python -m unittest discover -s tools/maps -p 'test_clip_map.py' -v
PMTILES=/ruta/al/ejecutable/pmtiles tools/maps/.venv/bin/python tools/maps/build-map.py
```

El resultado se publica en `assets/maps/morelos-centro/` de la app de destino. El generador verifica la descarga
del paquete de estilos, fija la revisión de sus assets y usa un directorio
temporal: un fallo de descarga o verificación no reemplaza el mapa anterior. No hace falta instalar dependencias
cartográficas nuevas en el runtime JS. Para una actualización, cambia la fecha/URL y versión de datos en
`tools/maps/map-config.json`, incrementa `packageVersion` y regenera. Para cambiar la zona, ajusta `center`
y `sideMeters`. Protomaps retiene un historial limitado de snapshots
diarios; conserva el paquete generado en el repositorio y utiliza un snapshot disponible al actualizar.

El plugin `withOfflineMapAssets` valida y copia el paquete al ejecutar Expo prebuild y añade `noCompress` para
PMTiles. Su validación de integridad es propia del plugin y no importa estas herramientas externas. No se deben
editar sus copias generadas en `android/`. Una actualización del mapa exige recompilar y
distribuir una nueva app; Fast Refresh no reemplaza los assets nativos.

La configuración de Expo fija MapLibre Native Android **13.7.1**: esta versión incluye la corrección de lecturas
por rangos desde los assets del APK ([#4602](https://github.com/maplibre/maplibre-native/pull/4602)). La 13.6.1
predeterminada del wrapper no puede leer este PMTiles directamente. El mapa no se extrae ni se copia a los
documentos del usuario; MapLibre lo lee desde el APK.

Ejecutar Expo prebuild desde `mercaforte_app` con `APP_ENV=development npx expo prebuild --platform android --no-install`.
Después, desde `mercaforte_infra`, comprobar sus artefactos (las rutas del ejemplo asumen repositorios hermanos):

```sh
node tools/maps/verify-map.cjs ../mercaforte_app/android/app/src/main/assets/maps/morelos-centro
python3 tools/maps/verify-apk.py ../mercaforte_app/android/app/build/outputs/apk/release/app-release.apk
```

## Prueba móvil

Comprobar el mapa con un APK que incluya JavaScript, sin Metro y en modo avión, después de cerrar y abrir la app.
Verificar calles y nombres dentro del cuadrado, números/selección de tiendas y recorrido. Conservar SQLite,
sesión y pendientes; no usar `pm clear` ni desinstalar para hacer esta prueba.
No publicar el APK de validación firmado con la clave debug como una distribución de producción.

La prueba nativa reproducible no necesita sesión ni bootstrap:

```sh
python3 tools/maps/android-smoke.py --apk ../mercaforte_app/android/app/build/outputs/apk/release/app-release.apk
```

Requiere el JDK 17, SDK Android 36/build-tools 36.0.0 y el AAR 13.7.1 ya descargado por Gradle. Instala el APK
indicado con `adb install -r`, compila una instrumentación temporal firmada con la clave debug del proyecto,
activa modo avión y renderiza diez localidades interiores y una vista completa del cuadrado usando los assets
del APK. También comprueba que Toluca y CDMX se rendericen vacías. Conserva capturas cartográficas en la caché
`offline-map-smoke` para inspección visual. Al salir
restaura la conectividad previa y desinstala la instrumentación. No inicia sesión ni descarga rutas.

Para el APK autónomo de validación, la configuración HTTP del desarrollo habitual no es válida en el bundle
release. En la comprobación de esta entrega se utilizó `EXPO_PUBLIC_API_BASE_URL=https://127.0.0.1:8080/api`
solo para probar sin red y sin acceder a un backend externo. Ese APK es de validación; la versión dev instalada
al terminar conserva `.env.local` y su backend HTTP local. Los builds de distribución deben usar su URL HTTPS real.

### Comprobación del 5 de noviembre de 2026 (paquete 2026.11.05.3)

- Cuadrado continuo de 50 × 50 km, con centro 18.860124, -99.185444; sin recortes municipales.
- Paquete completo: **18.55 MB** (18,545,432 bytes), incluido el manifiesto y 779 recursos;
  cartografía PMTiles: **7.00 MB** (7,000,819 bytes). Tamaños decimales.
- APK arm64 autónomo de validación: **65.98 MB** (65,979,320 bytes); APK de desarrollo instalado:
  **102.59 MB** (102,591,335 bytes), que también incorpora los cambios actuales del proyecto.
- Cuatro pruebas Python y cuatro Node aprobadas. Se verificaron las 108,631 geometrías retenidas,
  los SHA-256 del paquete y sus recursos en el APK. No hay assets cartográficos duplicados;
  PMTiles está almacenado sin compresión ZIP. Expo prebuild conservó el paquete.
- Samsung SM_S918B: las diez localidades interiores y una vista completa del cuadrado se renderizaron
  en modo avión, directamente desde los assets, sin Metro. Se inspeccionó la vista general: cartografía
  continua, incluidos Coatetelco y Alpuyeca. Toluca y CDMX produjeron imágenes vacías.
- Se reinstaló la app con `adb install -r`, conservando los datos existentes. Al terminar se restauró
  la conectividad y se dejó la versión dev abierta mediante `launch-android.sh`, con su backend HTTP local.
- La interacción con las 16 tiendas, selección y recorrido, y dos aperturas autónomas en modo avión
  se habían validado con el paquete anterior; esta actualización verificó específicamente la cobertura cuadrada.

La implementación de esta entrega es Android. No incluye satélite, navegación giro a giro, búsqueda de
direcciones ni cálculo de rutas sin conexión. Las rutas del bootstrap conservan su geometría existente.
