#!/usr/bin/env bash
set -euo pipefail

development_stack_directory="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
data_directory="$development_stack_directory/data"
postgres_data_directory="$data_directory/postgres"

cd -- "$development_stack_directory"

configure_routing_token() {
  local routing_manager_token="${ROUTING_MANAGER_TOKEN:-}"
  local routing_token_file="$data_directory/routing-manager.token"
  local backend_environment_file="$development_stack_directory/../../../mercaforte_back/.env"

  # Reuse the backend secret so both local services authenticate with the same value.
  if [[ -z "$routing_manager_token" && -f "$backend_environment_file" ]]; then
    routing_manager_token="$(sed -n 's/^[[:space:]]*ROUTING_MANAGER_TOKEN[[:space:]]*=[[:space:]]*//p' "$backend_environment_file" | tail -n 1)"
  fi
  if [[ -z "$routing_manager_token" && -s "$routing_token_file" ]]; then
    routing_manager_token="$(cat -- "$routing_token_file")"
  fi
  if [[ -z "$routing_manager_token" ]]; then
    mkdir -p -- "$data_directory"
    (umask 077; openssl rand -hex 32 > "$routing_token_file")
    routing_manager_token="$(cat -- "$routing_token_file")"
  fi
  if [[ ${#routing_manager_token} -lt 24 ]]; then
    printf 'ROUTING_MANAGER_TOKEN debe contener al menos 24 caracteres.\n' >&2
    return 1
  fi
  export ROUTING_MANAGER_TOKEN="$routing_manager_token"
}

# Coordinador de bloqueos pausado; OSRM no necesita el token para servir el mapa
# configure_routing_token

initialize() {
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
  docker compose -f compose.yml up -d --wait
}

stop() {
  docker compose -f compose.yml down --remove-orphans
}

remove_data() {
  if [[ -L "$postgres_data_directory" ]]; then
    printf 'No se borrarán datos: data/postgres es un enlace simbólico.\n' >&2
    return 1
  fi

  if [[ -d "$postgres_data_directory" ]]; then
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
  docker compose -f compose.yml up -d --force-recreate --wait
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
