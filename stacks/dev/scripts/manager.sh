#!/usr/bin/env bash
set -euo pipefail

development_stack_directory="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
data_directory="$development_stack_directory/data"
postgres_data_directory="$data_directory/postgres"
pgadmin_data_directory="$data_directory/pgadmin"

cd -- "$development_stack_directory"

printf '1) Inicializar\n2) Iniciar\n3) Detener\n4) Eliminar (borra toda la carpeta data)\n'
read -r -p 'Selecciona una opción: ' selected_option

case "$selected_option" in
  1)
    mkdir -p -- "$postgres_data_directory"
    mkdir -p -- "$pgadmin_data_directory"

    # Ownership required by postgres:15.
    sudo chown -R 999:999 "$postgres_data_directory"
    sudo chmod 700 "$postgres_data_directory"

    # Ownership required by dpage/pgadmin4:9.17.
    sudo chown -R 5050:0 "$pgadmin_data_directory"
    sudo chmod 700 "$pgadmin_data_directory"
    ;;
  2)
    docker compose -f compose.yml up -d --wait postgres pgadmin
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
