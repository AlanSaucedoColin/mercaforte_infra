#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."

docker compose -f compose.yml down

# Borra la carpeta de la persistencia anterior, si existe.
if [ -d ./data ]; then
  find ./data -depth -delete
fi

# Reinicia solo PostgreSQL; conserva la configuracion de pgAdmin.
if docker volume inspect mercaforte_dev_postgres_data >/dev/null 2>&1; then
  docker volume rm mercaforte_dev_postgres_data
fi

docker compose -f compose.yml up -d --wait postgres pgadmin