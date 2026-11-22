# ERPNext en producción

## 1. Inicialización (una sola vez)

Apunta el DNS del dominio al servidor. Deja los puertos TCP `80` y `443` libres y accesibles desde Internet.

Desde la carpeta `erpnext-prod`:

```bash
docker info >/dev/null
docker compose version
cp -n .env.example .env
chmod 600 .env
nano .env
```

En `.env`, cambia `DB_PASSWORD` por una contraseña fuerte, `LETSENCRYPT_EMAIL` por tu correo y el dominio de ``SITES_RULE=Host(`erp.example.com`)`` por el tuyo.

Define `ERPNEXT_DATA_ROOT` con la ruta absoluta deseada (por defecto `/srv/erpnext`). En el servidor Linux, prepara los directorios:

```bash
ROOT=$(docker compose -f compose.yaml config --environment | sed -n 's/^ERPNEXT_DATA_ROOT=//p')
(
  set -eu
  case "$ROOT" in /) exit 1 ;; /*) ;; *) exit 1 ;; esac
  sudo install -d -o 1000 -g 0 -m 0770 "$ROOT/frappe/sites"
  for svc in configurator backend frontend websocket queue-short queue-long scheduler; do
    sudo install -d -o 1000 -g 0 -m 0770 "$ROOT/frappe/logs/$svc"
  done
  sudo install -d -o 999 -g 999 -m 0700 "$ROOT/mariadb" "$ROOT/redis-cache" "$ROOT/redis-queue"
  sudo install -d -o root -g root -m 0700 "$ROOT/traefik"
)
```

Si ya hay datos, detén el entorno y copia o restaura los datos en las nuevas rutas antes de arrancar. Cambiar la ruta no migra los datos.

## 2. Levantar producción

```bash
docker compose -p erpnext-prod -f compose.yaml \
  -f overrides/compose.mariadb.yaml \
  -f overrides/compose.redis.yaml \
  -f overrides/compose.https.yaml \
  -f overrides/compose.bind-mounts.yaml up -d
docker compose -p erpnext-prod ps -a
```

Cuando `db` esté `healthy` y `configurator` muestre `Exited (0)`, crea el sitio **solo la primera vez**. Sustituye `erp.example.com` por el dominio de `SITES_RULE`:

```bash
docker compose -p erpnext-prod exec backend bench new-site erp.example.com \
  --mariadb-user-host-login-scope='%' --install-app erpnext
```

Cuando lo solicite, introduce `DB_PASSWORD` como contraseña root de MariaDB y elige una contraseña para `Administrator`. Abre `https://TU_DOMINIO` e inicia sesión con `Administrator`.
