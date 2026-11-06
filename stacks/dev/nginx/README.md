# Nginx de MERCAFORTE

La web se sirve en `/`. Sus llamadas a `/mercaforte/...` se envian a
`http://wildfly:8080/api/v1/...` por la red del Compose.

- `Dockerfile`: incluye la configuracion y el contenido de `dist/` en la imagen
- `templates/default.conf.template`: define el proxy y el fallback de la web
- `dist/`: contiene el frontend compilado, incluido `index.html`

Los valores del proxy se definen en `stacks/dev/.env`: `NGINX_API_PREFIX`,
`NGINX_BACKEND_URL`, `NGINX_BACKEND_API_PATH` y `NGINX_CLIENT_MAX_BODY_SIZE`.
La imagen oficial genera la configuracion al arrancar el contenedor.
No copiar archivos `.env` privados dentro de `dist/`.

Para actualizar el frontend:

```bash
cd /Users/alansaucedocolin/Documents/projects/mercaforte_web
npm run build
rsync -a --delete dist/ /Users/alansaucedocolin/Documents/projects/mercaforte_infra/stacks/dev/nginx/dist/
```

Despues, usar la opcion `Iniciar` de `stacks/dev/scripts/manager.sh`.
El administrador reconstruye las imagenes y muestra los logs en primer plano.
Cambiar `VITE_API_URL` requiere volver a compilar y copiar el `dist`.
Su valor debe coincidir con `NGINX_API_PREFIX`, actualmente `/mercaforte`.
