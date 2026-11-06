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

Unión de los límites OSM de **Cuernavaca, Huitzilac, Tepoztlán, Emiliano Zapata, Jiutepec, Yautepec, Temixco y
Xochitepec**, intersectada con el estado de Morelos. No se agrega margen externo. `coverage.geojson` y el
manifiesto conservan este polígono; sus límites rectangulares se usan únicamente como encuadre máximo.

Seleccionar teselas con `pmtiles extract --region` no elimina las ciudades vecinas contenidas en sus zooms
generales. Por eso `clip_map.py` también recorta las geometrías de cada tesela MVT y elimina los puntos externos.
Se verifica el contenido completo del archivo, incluidos zooms bajos, con tolerancia de una unidad MVT por
redondeo. Toluca y Ciudad de México no se conservan como lugares del mapa. El aviso de cobertura de la app
consulta el polígono municipal y la cámara queda limitada al encuadre regional, con zoom mínimo 9.

Los datos llegan hasta zoom 15 y la cámara hasta 19 por ampliación de las teselas existentes; no aparecen
detalles nuevos al ampliar por encima de 15. Fuera del polígono solo permanecen las capas operativas y el fondo,
sin intentar cargar cartografía remota.

El paquete contiene el PMTiles, estilo, sprites 1x/2x y los 256 bloques BMP de las tres fuentes Noto Sans usadas,
incluidos acentos y números de marcadores. El manifiesto registra fecha de datos, cobertura y SHA-256 de cada
archivo. `municipalities.osm.json` conserva las relaciones y límites devueltos por Overpass.

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
# Para actualizar los límites administrativos además de los datos:
tools/maps/.venv/bin/python tools/maps/build-map.py --pmtiles /ruta/al/ejecutable/pmtiles --refresh-boundaries
```

El resultado se publica en `assets/maps/morelos-centro/` de la app de destino. El generador verifica la descarga
del paquete de estilos, fija la revisión de sus assets y usa un directorio
temporal: un fallo de descarga o verificación no reemplaza el mapa anterior. No hace falta instalar dependencias
cartográficas nuevas en el runtime JS. Para una actualización, cambia la fecha/URL y versión de datos en
`tools/maps/map-config.json`, incrementa `packageVersion` y regenera. Protomaps retiene un historial limitado de snapshots
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
Verificar calles y nombres en los ocho municipios, números/selección de tiendas, recorrido y aviso fuera de la
cobertura. Conservar SQLite, sesión y pendientes; no usar `pm clear` ni desinstalar para hacer esta prueba.
No publicar el APK de validación firmado con la clave debug como una distribución de producción.

La prueba nativa reproducible no necesita sesión ni bootstrap:

```sh
python3 tools/maps/android-smoke.py --apk ../mercaforte_app/android/app/build/outputs/apk/release/app-release.apk
```

Requiere el JDK 17, SDK Android 36/build-tools 36.0.0 y el AAR 13.7.1 ya descargado por Gradle. Instala el APK
indicado con `adb install -r`, compila una instrumentación temporal firmada con la clave debug del proyecto,
activa modo avión y renderiza las ocho cabeceras usando los assets del APK. También comprueba que Toluca y CDMX
se rendericen vacías. Conserva capturas cartográficas en la caché `offline-map-smoke` para inspección visual. Al salir
restaura la conectividad previa y desinstala la instrumentación. No inicia sesión ni descarga rutas.

Para el APK autónomo de validación, la configuración HTTP del desarrollo habitual no es válida en el bundle
release. En la comprobación de esta entrega se utilizó `EXPO_PUBLIC_API_BASE_URL=https://127.0.0.1:8080/api`
solo para probar sin red y sin acceder a un backend externo. Ese APK es de validación; la versión dev instalada
al terminar conserva `.env.local` y su backend HTTP local. Los builds de distribución deben usar su URL HTTPS real.

### Comprobación inicial del 5 de noviembre de 2026 (paquete 2026.11.05.1)

- Samsung SM_S918B, Android 16: MapLibre Native 13.7.1 lee PMTiles directamente desde los assets, sin extracción.
- Paquete completo: **19.28 MB**, incluido el manifiesto y 780 recursos verificados; cartografía PMTiles: **7.71 MB**.
- APK arm64 autónomo de validación: **65.35 MB**; APK de desarrollo instalado: **95.58 MB**. Tamaños decimales.
- Cuatro pruebas Node aprobadas, verificación SHA-256 del paquete y de su copia nativa, y comprobación de todos
  los archivos dentro del APK. PMTiles está almacenado sin compresión ZIP.
- Las seis cabeceras se renderizaron en modo avión mediante instrumentación; se inspeccionaron las imágenes,
  incluidos calles, nombres, acentos e iconos.
- Después de la instalación limpia solicitada, el usuario inició sesión y descargó su jornada. Se comprobaron
  sus 16 tiendas y recorrido; la selección de una tienda abrió su ficha en modo avión.
- El APK autónomo abrió la jornada y el mapa en modo avión, sin reenvío a Metro, incluyendo un cierre forzado
  y una segunda apertura. Al terminar se dejó la app dev con la jornada vigente y la conectividad restaurada.

La implementación de esta entrega es Android. No incluye satélite, navegación giro a giro, búsqueda de
direcciones ni cálculo de rutas sin conexión. Las rutas del bootstrap conservan su geometría existente.
