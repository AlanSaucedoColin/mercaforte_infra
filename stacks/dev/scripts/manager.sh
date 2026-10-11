#!/usr/bin/env bash
set -euo pipefail

development_stack_directory="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
data_directory="$development_stack_directory/data"
postgres_data_directory="$data_directory/postgres"

cd -- "$development_stack_directory"

printf '1) Inicializar\n2) Iniciar\n3) Detener\n4) Eliminar (borra toda la carpeta data)\n'
read -r -p 'Selecciona una opción: ' selected_option

case "$selected_option" in
  1)
    mkdir -p -- "$postgres_data_directory"

    # Keep the host directories accessible to the user running Docker Desktop.
    host_user_id="${SUDO_UID:-$(id -u)}"
    host_group_id="${SUDO_GID:-$(id -g)}"
    sudo chown -R "$host_user_id:$host_group_id" "$postgres_data_directory"

    # Set ownership and permissions as seen inside each container.
    docker compose -f compose.yml run --rm --no-deps --user root --entrypoint sh postgres \
      -ec 'chown -R 999:999 /var/lib/postgresql/data; chmod 700 /var/lib/postgresql/data'
    ;;
  2)
    docker compose -f compose.yml up -d --wait postgres
    ;;
  3)
    docker compose -f compose.yml down --remove-orphans
    ;;
  4)
    docker compose -f compose.yml down --remove-orphans
    sudo rm -rf -- "$data_directory"
    ;;
  *)
    printf 'Opción inválida. Usa 1, 2, 3 o 4.\n' >&2
    exit 1
    ;;
esac
