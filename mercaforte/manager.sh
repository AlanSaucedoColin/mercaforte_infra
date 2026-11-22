#!/usr/bin/env bash
set -euo pipefail

stack_directory="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

cd -- "$stack_directory"

printf '1) Inicializar\n2) Iniciar\n3) Detener\n4) Detener el stack, eliminar los datos de PostgreSQL y recrear los contenedores\n'
read -r -p 'Selecciona una opción: ' selected_option

case "$selected_option" in
  1)
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
    docker compose down --volumes --remove-orphans
    docker compose up -d --force-recreate
    ;;
  *)
    printf 'Opción inválida. Usa 1, 2, 3 o 4.\n' >&2
    exit 1
    ;;
esac
