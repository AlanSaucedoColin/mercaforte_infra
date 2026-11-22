#!/usr/bin/env bash
set -euo pipefail

development_stack_directory="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
data_directory="$development_stack_directory/data"
postgres_data_directory="$data_directory/postgres"

cd -- "$development_stack_directory"

initialize() {
  printf 'Preparando directorio y permisos de PostgreSQL: %s\n' "$postgres_data_directory"
  mkdir -p -- "$postgres_data_directory"

  # Keep the host directories accessible to the user running Docker Desktop.
  host_user_id="${SUDO_UID:-$(id -u)}"
  host_group_id="${SUDO_GID:-$(id -g)}"
  sudo chown -R "$host_user_id:$host_group_id" "$postgres_data_directory"

  # Set ownership and permissions as seen inside each container.
  docker compose -f compose.yml run --rm --no-deps --user root --entrypoint sh postgres \
    -ec 'chown -R 999:999 /var/lib/postgresql/data; chmod 700 /var/lib/postgresql/data'
}

start() {
  printf 'Orden de arranque: PostgreSQL -> WildFly -> Nginx -> OSRM -> VROOM\n'
  printf 'Construyendo imagenes y mostrando los logs de todos los servicios\n'
  docker compose --progress plain -f compose.yml up --build
}

stop() {
  printf 'Deteniendo los servicios del stack\n'
  docker compose -f compose.yml down --remove-orphans
}

remove_data() {
  if [[ -L "$postgres_data_directory" ]]; then
    printf 'No se borrarán datos: data/postgres es un enlace simbólico.\n' >&2
    return 1
  fi

  if [[ -d "$postgres_data_directory" ]]; then
    printf 'Eliminando el contenido de PostgreSQL: %s\n' "$postgres_data_directory"
    sudo find "$postgres_data_directory" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
  fi
}

reinitialize() {
  stop
  remove_data
  if [[ -d "$postgres_data_directory" ]]; then
    sudo rmdir -- "$postgres_data_directory"
  fi
  initialize
  printf 'Orden de arranque: PostgreSQL -> WildFly -> Nginx -> OSRM -> VROOM\n'
  printf 'Reconstruyendo imagenes, recreando servicios y mostrando todos los logs\n'
  docker compose --progress plain -f compose.yml up --build --force-recreate
}

printf '1) Inicializar\n2) Iniciar\n3) Detener\n4) Eliminar (borra solo el contenido de data/postgres)\n5) Reinicializar (baja todo el compose, recrea data/postgres y levanta todo con --force-recreate)\n'
read -r -p 'Selecciona una opción: ' selected_option

case "$selected_option" in
  1)
    initialize
    ;;
  2)
    start
    ;;
  3)
    stop
    ;;
  4)
    stop
    remove_data
    ;;
  5)
    reinitialize
    ;;
  *)
    printf 'Opción inválida. Usa 1, 2, 3, 4 o 5.\n' >&2
    exit 1
    ;;
esac
