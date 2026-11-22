#!/usr/bin/env bash
set -euo pipefail

env='dev' # dev o prod

dominio='localhost'
correo_letsencrypt=''
password_mariadb='MariaDB-Demo-123!'
password_administrator='Admin-Demo-123!'

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
export COMPOSE_PROJECT_NAME="erpnext-$env"
if [[ "$env" == 'dev' ]]; then
  root="$HOME/erpnext-demo"
  frappe_owner=$(id -u)
  db_owner=$frappe_owner
  frappe_group=$(id -g)
  db_group=$frappe_group
  db_mode=0770
  acceso=noproxy
else
  root="/var/lib/mercaforte/erpnext"
  frappe_owner=1000
  db_owner=999
  frappe_group=0
  db_group=999
  db_mode=0700
  acceso=https
fi
export COMPOSE_FILE="erpnext/compose.yaml:erpnext/overrides/compose.mariadb.yaml:erpnext/overrides/compose.redis.yaml:erpnext/overrides/compose.$acceso.yaml:compose.$env.yaml"
export ERPNEXT_DATA_ROOT="$root"
printf '%s\n' '1) Inicializar' '2) Iniciar' '3) Detener' '4) Detener y purgar los datos'
read -r -p 'Selecciona una opción: ' option

case "$option" in
  1) # Inicializar
    docker info >/dev/null
    docker compose version

    if [[ ! -e .env.erpnext ]]; then
      (
        umask 077
        exec > .env.erpnext
        # En un .env con comillas dobles, proteger \, " y $ de la interpolación.
        clave=${password_mariadb//\\/\\\\}
        clave=${clave//\"/\\\"}
        clave=${clave//\$/\$\$}
        sed -E '/^(ERPNEXT_DATA_ROOT|DB_PASSWORD|LETSENCRYPT_EMAIL|SITES_RULE)=/d' .env.erpnext.example
        printf '\nERPNEXT_DATA_ROOT=%s\nDB_PASSWORD="%s"\nLETSENCRYPT_EMAIL=%s\nSITES_RULE=Host(`%s`)\n' \
          "$root" "$clave" "$correo_letsencrypt" "$dominio"
      )
    fi
    chmod 600 .env.erpnext

    sudo install -d -o "$frappe_owner" -g "$frappe_group" -m 0770 -- \
      "$root/frappe/sites" \
      "$root/frappe/logs/configurator" \
      "$root/frappe/logs/backend" \
      "$root/frappe/logs/frontend" \
      "$root/frappe/logs/websocket" \
      "$root/frappe/logs/queue-short" \
      "$root/frappe/logs/queue-long" \
      "$root/frappe/logs/scheduler"

    sudo install -d -o "$db_owner" -g "$db_group" -m "$db_mode" -- \
      "$root/mariadb" "$root/redis-cache" "$root/redis-queue"

    if [[ "$env" != 'dev' ]]; then
      sudo install -d -o 0 -g 0 -m 0700 -- "$root/traefik"
    fi

    docker compose --env-file .env.erpnext up -d
    docker compose --env-file .env.erpnext exec -T backend bash -eo pipefail -c '
      if [[ ! -f "sites/$1/site_config.json" ]]; then
        bench new-site "$1" --mariadb-user-host-login-scope=% \
          --db-root-password "$2" --admin-password "$3" --install-app erpnext
      fi
      bench --site "$1" list-apps | grep -E "^erpnext([[:space:]]|$)" >/dev/null
    ' bash "$dominio" "$password_mariadb" "$password_administrator"
    printf 'ERPNext listo: https://%s (usuario: Administrator)\n' "$dominio"
    ;;

  2) # Iniciar
    docker compose --env-file .env.erpnext up -d
    ;;

  3) # Detener
    docker compose --env-file .env.erpnext down
    ;;

  4) # Purgar
    if [[ ! -d "$root" || "$root" == / || "$(cd -- "$root" && pwd -P)" != "$root" ]]; then
      printf 'No se purgará la ruta: %s\n' "$root" >&2
      exit 1
    fi
    docker compose --env-file .env.erpnext down
    sudo find "$root" -xdev -depth -mindepth 1 -delete
    printf 'Datos eliminados. Para volver a empezar, ejecuta Inicializar.\n'
    ;;

  *)
    printf 'Opción inválida. Usa 1, 2, 3 o 4.\n' >&2
    exit 1
    ;;
esac
