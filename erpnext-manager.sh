#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

printf '%s\n' '1) Inicializar ERPNext' '2) Iniciar ERPNext' '3) Detener ERPNext' \
  '4) Detener ERPNext, borrar sus datos (incluidos sitios y certificados) y recrear los contenedores'
read -r -p 'Selecciona una opción: ' option

case "$option" in
  1) # Inicializar
    if [[ ! -e .env.erpnext ]]; then
      (umask 077; cp .env.erpnext.example .env.erpnext)
    fi
    root=$(
      docker compose --project-name erpnext-prod --env-file .env.erpnext \
        -f compose.erpnext.yaml \
        -f erpnext/compose.mariadb.yaml \
        -f erpnext/compose.redis.yaml \
        -f erpnext/compose.https.yaml \
        -f erpnext/compose.bind-mounts.yaml \
        config --environment | sed -n 's/^ERPNEXT_DATA_ROOT=//p'
    )
    root=${root%/}
    if [[ "$root" != /* || "$root/" == *//* || "$root/" == */../* || "$root/" == */./* ]]; then
      printf 'ERPNEXT_DATA_ROOT debe ser una ruta absoluta dedicada, sin componentes relativos.\n' >&2
      exit 1
    fi
    path=$root
    while [[ -n "$path" ]]; do
      if [[ -L "$path" ]]; then
        printf 'Ruta de datos con enlace simbólico: %s\n' "$path" >&2
        exit 1
      fi
      path=${path%/*}
    done
    if [[ -L "$root/frappe" || -L "$root/frappe/sites" || -L "$root/frappe/logs" ||
          -L "$root/frappe/logs/configurator" || -L "$root/frappe/logs/backend" ||
          -L "$root/frappe/logs/frontend" || -L "$root/frappe/logs/websocket" ||
          -L "$root/frappe/logs/queue-short" || -L "$root/frappe/logs/queue-long" ||
          -L "$root/frappe/logs/scheduler" || -L "$root/mariadb" ||
          -L "$root/redis-cache" || -L "$root/redis-queue" || -L "$root/traefik" ]]; then
      printf 'Un directorio de ERPNext es un enlace simbólico.\n' >&2
      exit 1
    fi

    sudo install -d -o 1000 -g 0 -m 0770 -- \
      "$root/frappe/sites" \
      "$root/frappe/logs/configurator" \
      "$root/frappe/logs/backend" \
      "$root/frappe/logs/frontend" \
      "$root/frappe/logs/websocket" \
      "$root/frappe/logs/queue-short" \
      "$root/frappe/logs/queue-long" \
      "$root/frappe/logs/scheduler"
    sudo install -d -o 999 -g 999 -m 0700 -- \
      "$root/mariadb" "$root/redis-cache" "$root/redis-queue"
    sudo install -d -o root -g root -m 0700 -- "$root/traefik"
    printf 'Revisa .env.erpnext antes de iniciar. Si cambias la ruta, vuelve a inicializar.\n'
    ;;

  2) # Iniciar
    docker compose --project-name erpnext-prod --env-file .env.erpnext \
      -f compose.erpnext.yaml \
      -f erpnext/compose.mariadb.yaml \
      -f erpnext/compose.redis.yaml \
      -f erpnext/compose.https.yaml \
      -f erpnext/compose.bind-mounts.yaml \
      up -d
    ;;

  3) # Detener
    docker compose --project-name erpnext-prod --env-file .env.erpnext \
      -f compose.erpnext.yaml \
      -f erpnext/compose.mariadb.yaml \
      -f erpnext/compose.redis.yaml \
      -f erpnext/compose.https.yaml \
      -f erpnext/compose.bind-mounts.yaml \
      down --remove-orphans
    ;;

  4) # Vaciar datos y recrear
    compose=(
      docker compose --project-name erpnext-prod --env-file .env.erpnext
      -f compose.erpnext.yaml
      -f erpnext/compose.mariadb.yaml
      -f erpnext/compose.redis.yaml
      -f erpnext/compose.https.yaml
      -f erpnext/compose.bind-mounts.yaml
    )

    root=$("${compose[@]}" config --environment | sed -n 's/^ERPNEXT_DATA_ROOT=//p')
    root=${root%/}
    if [[ "$root" != /* || "$root/" == *//* || "$root/" == */../* || "$root/" == */./* ]]; then
      printf 'ERPNEXT_DATA_ROOT debe ser una ruta absoluta dedicada, sin componentes relativos.\n' >&2
      exit 1
    fi
    path=$root
    while [[ -n "$path" ]]; do
      if [[ -L "$path" ]]; then
        printf 'Ruta de datos con enlace simbólico: %s\n' "$path" >&2
        exit 1
      fi
      path=${path%/*}
    done
    if [[ -L "$root/frappe" || -L "$root/frappe/sites" || -L "$root/frappe/logs" ||
          -L "$root/frappe/logs/configurator" || -L "$root/frappe/logs/backend" ||
          -L "$root/frappe/logs/frontend" || -L "$root/frappe/logs/websocket" ||
          -L "$root/frappe/logs/queue-short" || -L "$root/frappe/logs/queue-long" ||
          -L "$root/frappe/logs/scheduler" || -L "$root/mariadb" ||
          -L "$root/redis-cache" || -L "$root/redis-queue" || -L "$root/traefik" ]]; then
      printf 'Un directorio de ERPNext es un enlace simbólico.\n' >&2
      exit 1
    fi

    "${compose[@]}" down --remove-orphans

    sudo install -d -o 1000 -g 0 -m 0770 -- \
      "$root/frappe/sites" \
      "$root/frappe/logs/configurator" \
      "$root/frappe/logs/backend" \
      "$root/frappe/logs/frontend" \
      "$root/frappe/logs/websocket" \
      "$root/frappe/logs/queue-short" \
      "$root/frappe/logs/queue-long" \
      "$root/frappe/logs/scheduler"
    sudo install -d -o 999 -g 999 -m 0700 -- \
      "$root/mariadb" "$root/redis-cache" "$root/redis-queue"
    sudo install -d -o root -g root -m 0700 -- "$root/traefik"

    sudo find \
      "$root/frappe/sites" \
      "$root/frappe/logs/configurator" \
      "$root/frappe/logs/backend" \
      "$root/frappe/logs/frontend" \
      "$root/frappe/logs/websocket" \
      "$root/frappe/logs/queue-short" \
      "$root/frappe/logs/queue-long" \
      "$root/frappe/logs/scheduler" \
      "$root/mariadb" \
      "$root/redis-cache" \
      "$root/redis-queue" \
      "$root/traefik" \
      -xdev -depth -mindepth 1 -delete

    "${compose[@]}" up -d --force-recreate
    printf 'Contenedores recreados. Vuelve a crear el sitio ERPNext.\n'
    ;;

  *)
    printf 'Opción inválida. Usa 1, 2, 3 o 4.\n' >&2
    exit 1
    ;;
esac
