# Nginx de MERCAFORTE

La web se sirve en `/`. Sus llamadas a `/mercaforte/...` se envian a
`http://wildfly:8080/api/v1/...` por la red del Compose.
Las consultas de optimizacion usan `/mercaforte/vroom/` y Nginx las envia a
`http://vroom:3000/` sin pasar por el backend.

Ningun servicio publica puertos del host. Todos usan la red externa
`main`, definida directamente en `stacks/dev/compose.yml`. El destino del proxy
es `http://${NGINX_CONTAINER_NAME}:80`, cuyo nombre se define en
`stacks/dev/.env`. El dominio publico se configura en ese proxy externo. La red
debe existir; este Compose no la crea.

- `Dockerfile`: incluye la configuracion y el contenido de `../configs/dist/` en la imagen
- `templates/default.conf.template`: define el proxy y el fallback de la web
- `../configs/dist/`: contiene el frontend compilado, incluido `index.html`

Los valores del proxy se definen en `stacks/dev/.env`. Las URLs internas de
WildFly y VROOM se construyen con `WILDFLY_CONTAINER_NAME` y
`VROOM_CONTAINER_NAME`, respectivamente.
La imagen oficial genera la configuracion al arrancar el contenedor.
No copiar archivos `.env` privados dentro de `../configs/dist/`.

Para actualizar el frontend:

```bash
cd /Users/alansaucedocolin/Documents/projects/mercaforte_web
npm run build
rsync -a --delete dist/ /Users/alansaucedocolin/Documents/projects/mercaforte_infra/stacks/dev/configs/dist/
```

Despues, usar la opcion `Iniciar` de `stacks/dev/scripts/manager.sh`.
El administrador reconstruye las imagenes y muestra los logs en primer plano.
Cambiar `VITE_API_URL` requiere volver a compilar y copiar el `dist`.
Su valor debe coincidir con `NGINX_API_PREFIX`, actualmente `/mercaforte`.
