#!/usr/bin/env bash
set -euo pipefail

stack_directory="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
postgres_data_directory="$stack_directory/data/postgres"

cd -- "$stack_directory"

printf '1) Inicializar\n2) Iniciar\n3) Detener\n4) Detener el stack, vaciar data/postgres y recrear los contenedores\n'
read -r -p 'Selecciona una opción: ' selected_option

case "$selected_option" in
  1)
    mkdir -p -- "$postgres_data_directory"
    if [[ ! -e .env ]]; then
      cp .env.example .env
    fi
    ;;
  2)
    docker compose --progress plain up -d --build
    ;;
  3)
    docker compose down --remove-orphans
    ;;
  4)
    docker compose down --remove-orphans

    if [[ -L "$postgres_data_directory" ]]; then
      printf 'No se borrarán datos: data/postgres es un enlace simbólico.\n' >&2
      exit 1
    fi

    if [[ -d "$postgres_data_directory" ]]; then
      sudo find "$postgres_data_directory" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
    fi

    docker compose up -d --force-recreate
    ;;
  *)
    printf 'Opción inválida. Usa 1, 2, 3 o 4.\n' >&2
    exit 1
    ;;
esac
