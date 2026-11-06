# Mapa incluido de Morelos Centro

La app Android lleva un paquete en `assets/maps/morelos-centro/`. No descarga cartografía durante el uso,
el bootstrap ni el inicio de sesión. El mapa está en los assets del APK y no se borra al cerrar sesión
o reiniciar la base operativa. El proveedor de datos es Protomaps/OpenStreetMap; el estilo es Light en español.

## Cobertura y recursos

Rectángulo que engloba los límites OSM de Cuernavaca, Jiutepec, Yautepec, Emiliano Zapata, Temixco y Xochitepec,
con al menos 2 km de margen. Incluye zonas vecinas dentro del rectángulo. Fuera de él se muestran las capas
operativas y un aviso, sin intentar cargar cartografía remota. Los datos llegan hasta zoom 15 y la cámara hasta
19 por ampliación de las teselas existentes; no aparecen detalles nuevos al ampliar por encima de 15.

El paquete contiene el PMTiles, estilo, sprites 1x/2x y los 256 bloques BMP de las tres fuentes Noto Sans usadas,
incluidos acentos y números de marcadores. El manifiesto registra fecha de datos, cobertura y SHA-256 de cada
archivo. `municipalities.osm.json` conserva las relaciones y límites devueltos por Overpass.

## Verificar y regenerar

Desde la raíz del proyecto:

```sh
npm run maps:verify
node --test scripts/maps/offline-map.test.cjs
```

Para regenerar se requiere Node, Python >=3.12 y [go-pmtiles 1.31.2](https://github.com/protomaps/go-pmtiles/releases/tag/v1.31.2).
Instala el ejecutable oficial correspondiente a tu plataforma; no se incluye dentro de la app.

```sh
PMTILES=/ruta/al/ejecutable/pmtiles npm run maps:build
# Para actualizar los límites administrativos además de los datos:
python3 scripts/maps/build-map.py --pmtiles /ruta/al/ejecutable/pmtiles --refresh-boundaries
```

El generador verifica la descarga del paquete de estilos, fija la revisión de sus assets y usa un directorio
temporal: un fallo de descarga o verificación no reemplaza el mapa anterior. No hace falta instalar dependencias
cartográficas nuevas en el runtime JS. Para una actualización, cambia la fecha/URL y versión de datos en
`map-config.json`, incrementa `packageVersion` y regenera. Protomaps retiene un historial limitado de snapshots
diarios; conserva el paquete generado en el repositorio y utiliza un snapshot disponible al actualizar.

El plugin `withOfflineMapAssets` valida y copia el paquete al ejecutar Expo prebuild y añade `noCompress` para
PMTiles. No se deben editar sus copias generadas en `android/`. Una actualización del mapa exige recompilar y
distribuir una nueva app; Fast Refresh no reemplaza los assets nativos.

La configuración de Expo fija MapLibre Native Android **13.7.1**: esta versión incluye la corrección de lecturas
por rangos desde los assets del APK ([#4602](https://github.com/maplibre/maplibre-native/pull/4602)). La 13.6.1
predeterminada del wrapper no puede leer este PMTiles directamente. El mapa no se extrae ni se copia a los
documentos del usuario; MapLibre lo lee desde el APK.

```sh
APP_ENV=development npx expo prebuild --platform android --no-install
node scripts/maps/verify-map.cjs android/app/src/main/assets/maps/morelos-centro
python3 scripts/maps/verify-apk.py android/app/build/outputs/apk/release/app-release.apk
```

## Prueba móvil

Comprobar el mapa con un APK que incluya JavaScript, sin Metro y en modo avión, después de cerrar y abrir la app.
Verificar calles y nombres en los seis municipios, números/selección de tiendas, recorrido y aviso fuera de la
cobertura. Conservar SQLite, sesión y pendientes; no usar `pm clear` ni desinstalar para hacer esta prueba.
No publicar el APK de validación firmado con la clave debug como una distribución de producción.

La prueba nativa reproducible no necesita sesión ni bootstrap:

```sh
python3 scripts/maps/android-smoke.py --apk android/app/build/outputs/apk/release/app-release.apk
```

Requiere el JDK 17, SDK Android 36/build-tools 36.0.0 y el AAR 13.7.1 ya descargado por Gradle. Instala el APK
indicado con `adb install -r`, compila una instrumentación temporal firmada con la clave debug del proyecto,
activa modo avión y renderiza las seis cabeceras usando los assets del APK. Comprueba que las imágenes no
estén vacías y conserva capturas cartográficas en la caché `offline-map-smoke` para inspección visual. Al salir
restaura la conectividad previa y desinstala la instrumentación. No inicia sesión ni descarga rutas.

Para el APK autónomo de validación, la configuración HTTP del desarrollo habitual no es válida en el bundle
release. En la comprobación de esta entrega se utilizó `EXPO_PUBLIC_API_BASE_URL=https://127.0.0.1:8080/api`
solo para probar sin red y sin acceder a un backend externo. Ese APK es de validación; la versión dev instalada
al terminar conserva `.env.local` y su backend HTTP local. Los builds de distribución deben usar su URL HTTPS real.

### Comprobación realizada el 5 de noviembre de 2026

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
