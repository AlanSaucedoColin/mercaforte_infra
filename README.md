# ERPNext de Mercaforte

Este repositorio despliega ERPNext `v16.60.0` con la app `mercaforte_erpnext`. El proyecto Python vive en [erpnext/app/](erpnext/app/). Los formularios, los catálogos y las pruebas se encuentran en [app/mercaforte_erpnext/](erpnext/app/mercaforte_erpnext/).

## Construir la imagen

Las opciones **Inicializar** e **Iniciar** construyen la imagen desde `erpnext/Dockerfile` antes de levantar los servicios. Compose la construye una vez para los siete servicios de Frappe. El perfil de desarrollo usa ARM64 en Mac y el de producción usa AMD64 en Debian.

Docker reutiliza las capas vigentes. Al editar `app/`, vuelve a copiar la app y a instalarla. Para forzar una construcción completa en un arranque, ejecuta tu copia del manager desde `erpnext/` con esta variable y selecciona **Inicializar** o **Iniciar**.

```bash
ERPNEXT_BUILD_NO_CACHE=true ./manager.local.sh
```

Si quieres construir sin caché en cada arranque de ese equipo, guarda `ERPNEXT_BUILD_NO_CACHE=true` en `erpnext/.env` después de inicializarlo.

## Inicializar e iniciar el sitio

Desde `erpnext/`, crea una copia privada del manager la primera vez para configurar ese equipo. En producción puedes llamarla `manager.prod.sh`.

```bash
install -m 700 manager.sh manager.prod.sh
```

Configura `entorno='prod'`, `dominio`, `correo_letsencrypt`, `password_mariadb`, `password_administrator` y `forwarded_allow_ips` en esa copia. El dominio de producción debe apuntar al servidor, con TCP 80 y 443 disponibles para HTTPS. Para desarrollo puedes usar `manager.local.sh` con `entorno='dev'` y el dominio `localhost`. Ambas copias y `.env` están excluidos de Git.

Ejecuta tu copia (`./manager.prod.sh` o `./manager.local.sh`). Elige la acción correspondiente en el menú.

1. **Inicializar** crea `.env` desde `.env.example`, o comprueba el existente, y le da permisos `600`. Levanta los servicios, crea el sitio si hace falta y comprueba que ERPNext y la app estén instalados.
2. **Iniciar** construye la imagen con el código actual y levanta los servicios conservando los volúmenes.
3. **Detener** baja los servicios y conserva los volúmenes.
4. **Detener y purgar los datos** elimina los volúmenes de esa pila tras confirmar con `PURGAR`.

## Actualizar un sitio y migrar

Los siguientes comandos se ejecutan desde `erpnext/` con Bash o Zsh. Para el sitio local usa las tres variables del ejemplo. En producción asigna `perfil=prod`, `proxy=https` y el dominio real a `sitio`.

```bash
perfil=dev
proxy=noproxy
sitio=localhost

erp_compose() {
  docker compose --project-name "erpnext-$perfil" --env-file .env \
    -f compose.yaml \
    -f overrides/compose.mariadb.yaml \
    -f overrides/compose.redis.yaml \
    -f "overrides/compose.$proxy.yaml" \
    -f "overrides/compose.$perfil.yaml" "$@"
}
```

Con el sitio en ejecución, respalda la base y los archivos antes de actualizar. Ejecuta la construcción, el arranque y la migración después de confirmar que el respaldo terminó correctamente.

```bash
erp_compose exec -T backend bench --site "$sitio" backup --with-files --compress
erp_compose up -d
erp_compose exec -T backend bench --site "$sitio" migrate
erp_compose exec -T backend bench --site "$sitio" list-apps
```

La migración sincroniza los DocTypes, el catálogo y los campos de Cliente. Los respaldos quedan en el directorio privado del sitio dentro de su volumen. Para volver a una entrega anterior, recupera el código y el Dockerfile de esa versión antes de levantarla y, si la migración cambió datos o esquema de forma incompatible, restaura también el respaldo correspondiente.

## Desarrollo y pruebas

Después de editar `app/`, ejecuta `erp_compose up -d` para incorporar los cambios a la imagen y recrear los servicios que los necesitan. Si exportas personalizaciones desde el sitio de desarrollo, copia los JSON generados en el backend a la carpeta del módulo bajo `app/mercaforte_erpnext/` antes de recrear el contenedor.

En el sitio de desarrollo puedes habilitar el modo desarrollador y ejecutar las pruebas de la app.

```bash
erp_compose exec -T backend bench --site "$sitio" set-config developer_mode 1
erp_compose exec -T backend bench --site "$sitio" clear-cache
erp_compose exec -T backend bench --site "$sitio" set-config allow_tests true
erp_compose exec -T backend bench --site "$sitio" run-tests --app mercaforte_erpnext --test-category unit
```

Antes de una entrega puedes validar el perfil con `erp_compose config --quiet` y consultar el estado de sus servicios con `erp_compose ps`. Al cambiar la versión de la app, mantén la misma etiqueta en el Compose de construcción y en el de ejecución. [Documentación de la app](erpnext/app/README.md)
