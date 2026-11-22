# OSRM: guardado unico de cierres efectivos

El contenedor usa OSRM 26.11.0 y MLD. El coordinador sirve el protocolo OSRM en 5000 y lo reenvia a
osrm-routed, que escucha exclusivamente dentro del contenedor en 127.0.0.1:5002. VROOM sigue usando osrm:5000.
La API interna GET/PUT /active-blocks y GET /elevation/tiles/{z}/{x}/{y}.png escucha en 5001; Compose publica ese puerto solo en 127.0.0.1.
Exige X-Routing-Token con ROUTING_MANAGER_TOKEN, un secreto de al menos 24 caracteres compartido con el backend.
Sin token valido no se inicia el coordinador. La API interna nunca recibe JWT de operadores.

## Guardado y consistencia

- El manifiesto del grafo publicado contiene datasetHash, revision y blockedWayIds
- routing-active publica el directorio del grafo y su manifiesto como una sola referencia durable
- routing-catalog.json identifica el indice SQL y su fuente de elevaciones
- La unica tabla operativa es routing.road_segments; no hay colas, borradores ni historial de autores
- Un solo PUT sustituye el conjunto completo y espera hasta que el grafo este confirmado
- El mismo conjunto vigente es un no-op incluso si la respuesta anterior se perdio
- Una version vieja con otro conjunto produce conflicto; otro guardado simultaneo tambien
- Durante la preparacion sigue funcionando el grafo confirmado
- Durante el corte se rechazan nuevas consultas OSRM con 503 y se espera hasta 120 segundos a las anteriores
- El candidato se comprueba por el puerto privado 5002; el healthcheck publico no se usa para validarlo
- Solo despues de comprobar el candidato se reemplaza el enlace publicado y se confirma el PUT
- Un fallo anterior a la publicacion recupera el anterior y nunca confirma exito
- Un fallo posterior a publicar no revierte silenciosamente un conjunto confirmado: el servicio queda no disponible hasta recuperar esa version
- routing-switch.json permite conciliar una interrupcion; el enlace publicado decide que version se recupera
- routing-bootstrap.json referencia el catalogo preparado antes del commit SQL para reintentar su primera publicacion tras una caida
- Los candidatos fallidos se retiran solo si tienen marca de propiedad y no son activos, anteriores ni referencias de recuperacion
- Se conservan activo y anterior; la poda solo opera sobre directorios con marca .routing-owned.json valida
- Directorios desconocidos o sin marca verificable se dejan intactos; no se borra PBF, GeoTIFF ni archivos de origen

El backend espera hasta 20 minutos por el guardado. La preparacion admite 900 segundos, mas el drenaje y arranque.
Si se pierde la respuesta, consultar la lista efectiva: saving=true indica que sigue guardando; esperar a false y recargar.
Si el proceso se cae, GET devuelve 503 hasta conciliar; un GET antiguo durante saving=true no prueba que se haya cancelado.
Los bloqueos confirmados pueden consultarse aunque el motor quede temporalmente indisponible, con available=false.
La lista efectiva nunca se trunca aunque el conjunto confirmado tenga mas de 1000 vias; el limite de 1000 es para nuevos PUT.

## Instalacion limpia DEV

El esquema inicial v0008 crea solamente routing.road_segments con osm_way_id como clave primaria y las metricas opcionales.
El master carga schema y seed; no hay migraciones incrementales ni compatibilidad con tablas de borradores o trabajos.
El backend debe crear el indice mediante Liquibase antes de que el coordinador pueda importarlo.

1. Configurar ROUTING_MANAGER_TOKEN con el mismo secreto en backend y Compose, y las credenciales de la base
2. Construir/desplegar el backend con su esquema inicial y la imagen de este contenedor en la activacion autorizada
3. El coordinador lee el PBF, prepara el grafo inicial y el indice; routing-bootstrap.json permite reintentar ante caidas
4. Cuando el grafo y catalogo estan listos, el frontend puede consultar y guardar mediante los tres contratos finales

No se registran comentarios de conciliacion, autores, trabajos o versiones deseadas en PostgreSQL.
Los metadatos del catalogo y las elevaciones permanecen en routing-catalog.json, separado del manifiesto efectivo.
No se ejecutan comandos de purga desde el coordinador. El volumen sigue siendo persistente: vaciar solo PostgreSQL no borra
los cierres confirmados guardados en el volumen; si se conserva un grafo publicado del mismo mapa, se reconstruye solo el indice.
Si se empieza con el volumen de versiones vacio, el primer conjunto efectivo queda vacio. PBF y GeoTIFF se conservan como fuente.

## Fuente y elevaciones

El PBF sigue en /data/morelos.osm.pbf. Su huella incluye perfil y bibliotecas car de OSRM. Si cambia, se detiene el uso y guardado
hasta conciliar el indice, evitando aplicar IDs sobre otro mapa. No se modifica OpenStreetMap publico.
Los GeoTIFF se leen de /data/elevation (o ROUTING_ELEVATION_ROOT). elevation.py y GDAL se conservan; alturas y pendiente neta
se precalculan sobre el indice y no modifican velocidades o pesos. La huella de elevaciones queda en routing-catalog.json.
NoData o fuera de cobertura producen NULL; no se inventan ceros. Un error de enriquecimiento conserva el ultimo calculo.
Los contratos publicos estan exclusivamente en la coleccion Postman Routing del backend.

## Capa visual de alturas

El coordinador incorpora elevation_tiles.py y reutiliza los mismos GeoTIFF de ROUTING_ELEVATION_ROOT sin alterarlos.
GDAL crea en memoria un mosaico VRT EPSG:4326, reproyecta cada tile XYZ a EPSG:3857 y codifica PNG RGBA de 256x256.
La paleta es fija por altura, con transparencia para NoData o fuera de cobertura; el contrato y colores se documentan
exclusivamente en Postman Routing. No se agrega un servicio de mapas ni una tabla o cache persistente.

El acceso GDAL de esta capa se serializa y la cache LRU conserva hasta 128 imagenes por proceso. El limite global de
cache de bloques GDAL es 64 MB. Una firma de rutas, tamanos y fechas de modificacion invalida el mosaico y los tiles
si se sustituyen las fuentes. Los GeoTIFF se abren en modo lectura y los temporales permanecen en /vsimem.
La capa no espera la preparacion del catalogo SQL o del grafo y no interviene en el guardado de cierres.

Para activar este codigo es necesario reconstruir la imagen OSRM derivada y desplegar el backend actualizado;
reiniciar solo el contenedor existente no incorpora el nuevo helper. Esta edicion no realiza esa activacion.

Estos archivos solo preparan la siguiente activacion autorizada. Editarlos no compila, construye, migra ni arranca servicios.
