#!/usr/bin/env bash
set -euo pipefail

# Configuración
entorno='dev' # dev o prod
erpnext_version='v16.60.0'
dominio='localhost'
correo_letsencrypt=''
password_mariadb='Saca95-2015pwd'
password_administrator='adminadminAlan'

# En producción, usa * cuando solo los servicios de esta pila pueden alcanzar
# el backend. En desarrollo directo puede conservarse el valor predeterminado.
forwarded_allow_ips='127.0.0.1,::1'

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

case "$entorno" in
  dev)
    proyecto='erpnext-dev'
    url="http://$dominio:8080"
    archivos_compose=(
      -f compose.yaml
      -f overrides/compose.mariadb.yaml
      -f overrides/compose.redis.yaml
      -f overrides/compose.noproxy.yaml
      -f overrides/compose.dev.yaml
    )
    ;;
  prod)
    proyecto='erpnext-prod'
    url="https://$dominio"
    archivos_compose=(
      -f compose.yaml
      -f overrides/compose.mariadb.yaml
      -f overrides/compose.redis.yaml
      -f overrides/compose.https.yaml
      -f overrides/compose.prod.yaml
    )
    ;;
  *)
    printf 'Entorno inválido: %s. Usa dev o prod.\n' "$entorno" >&2
    exit 1
    ;;
esac

printf '%s\n' \
  '1) Inicializar' \
  '2) Iniciar' \
  '3) Detener' \
  '4) Detener y purgar los datos'
read -r -p 'Selecciona una opción: ' opcion

case "$opcion" in
  1) # Inicializar
    docker info >/dev/null
    docker compose version

    if [[ ! -f .env.example ]]; then
      printf 'No existe la plantilla .env.example.\n' >&2
      exit 1
    fi

    if [[ -z "$dominio" ]]; then
      printf 'Debes definir dominio al inicio del script.\n' >&2
      exit 1
    fi

    if [[ -z "$password_mariadb" ]]; then
      printf 'Debes definir password_mariadb al inicio del script.\n' >&2
      exit 1
    fi

    if [[ -z "$password_administrator" ]]; then
      printf 'Debes definir password_administrator al inicio del script.\n' >&2
      exit 1
    fi

    if [[ "$entorno" == 'prod' && -z "$correo_letsencrypt" ]]; then
      printf 'Debes definir correo_letsencrypt para producción.\n' >&2
      exit 1
    fi

    if [[ "$entorno" == 'prod' && "$dominio" == 'localhost' ]]; then
      printf 'Debes definir un dominio público para producción.\n' >&2
      exit 1
    fi

    if [[ "$entorno" == 'prod' && "$forwarded_allow_ips" == '127.0.0.1,::1' ]]; then
      printf '%s\n' \
        'Debes definir forwarded_allow_ips para producción.' \
        'Usa * para esta pila controlada o una lista que incluya la IP del frontend.' >&2
      exit 1
    fi

    clave_env=${password_mariadb//\\/\\\\}
    clave_env=${clave_env//\"/\\\"}
    clave_env=${clave_env//\$/\$\$}

    printf -v linea_version 'ERPNEXT_VERSION=%s' "$erpnext_version"
    printf -v linea_password 'DB_PASSWORD="%s"' "$clave_env"
    printf -v linea_forwarded 'FORWARDED_ALLOW_IPS=%s' "$forwarded_allow_ips"
    printf -v linea_correo 'LETSENCRYPT_EMAIL=%s' "$correo_letsencrypt"
    printf -v linea_sitio 'SITES_RULE=Host(`%s`)' "$dominio"

    if [[ ! -e .env ]]; then
      (
        umask 077
        exec > .env
        sed -E '/^(ERPNEXT_VERSION|DB_PASSWORD|FORWARDED_ALLOW_IPS|LETSENCRYPT_EMAIL|SITES_RULE)=/d' \
          .env.example
        printf '\n%s\n%s\n%s\n%s\n%s\n' \
          "$linea_version" \
          "$linea_password" \
          "$linea_forwarded" \
          "$linea_correo" \
          "$linea_sitio"
      )
    else
      if ! grep -Fqx "$linea_version" .env ||
        ! grep -Fqx "$linea_password" .env ||
        ! grep -Fqx "$linea_forwarded" .env ||
        ! grep -Fqx "$linea_correo" .env ||
        ! grep -Fqx "$linea_sitio" .env; then
        printf '%s\n' \
          '.env ya existe y no coincide con la configuración del script.' \
          'Se conservó sin cambios. Ajusta los valores del script o elimina el archivo para regenerarlo.' >&2
        exit 1
      fi
    fi

    chmod 600 .env

    docker compose \
      --project-name "$proyecto" \
      --env-file .env \
      "${archivos_compose[@]}" \
      config --quiet

    docker compose \
      --project-name "$proyecto" \
      --env-file .env \
      "${archivos_compose[@]}" \
      up -d

    docker compose \
      --project-name "$proyecto" \
      --env-file .env \
      "${archivos_compose[@]}" \
      exec -T backend bash -eo pipefail -c '
        sitio=$1
        password_db=$2
        password_admin=$3

        if [[ ! -f "sites/$sitio/site_config.json" ]]; then
          bench new-site "$sitio" \
            --mariadb-user-host-login-scope=% \
            --db-root-password "$password_db" \
            --admin-password "$password_admin" \
            --install-app erpnext
        elif ! bench --site "$sitio" list-apps |
          grep -E "^erpnext([[:space:]]|$)" >/dev/null; then
          bench --site "$sitio" install-app erpnext
        fi

        bench --site "$sitio" list-apps |
          grep -E "^erpnext([[:space:]]|$)" >/dev/null
      ' bash "$dominio" "$password_mariadb" "$password_administrator"

    printf 'ERPNext listo: %s (usuario: Administrator)\n' "$url"
    ;;

  2) # Iniciar
    docker info >/dev/null
    docker compose version

    if [[ ! -f .env ]]; then
      printf 'No existe .env. Ejecuta primero Inicializar.\n' >&2
      exit 1
    fi

    docker compose \
      --project-name "$proyecto" \
      --env-file .env \
      "${archivos_compose[@]}" \
      config --quiet

    docker compose \
      --project-name "$proyecto" \
      --env-file .env \
      "${archivos_compose[@]}" \
      up -d

    printf 'ERPNext iniciado: %s\n' "$url"
    ;;

  3) # Detener
    docker info >/dev/null
    docker compose version

    if [[ ! -f .env ]]; then
      printf 'No existe .env. No se puede identificar la configuración.\n' >&2
      exit 1
    fi

    docker compose \
      --project-name "$proyecto" \
      --env-file .env \
      "${archivos_compose[@]}" \
      down

    printf 'ERPNext detenido. Los volúmenes se conservaron.\n'
    ;;

  4) # Detener y purgar
    docker info >/dev/null
    docker compose version

    if [[ ! -f .env ]]; then
      printf 'No existe .env. No se puede identificar la configuración.\n' >&2
      exit 1
    fi

    printf 'Se eliminarán los volúmenes y todos los datos de %s.\n' "$proyecto"
    read -r -p 'Escribe PURGAR para continuar: ' confirmacion

    if [[ "$confirmacion" != 'PURGAR' ]]; then
      printf 'Purga cancelada.\n'
      exit 0
    fi

    docker compose \
      --project-name "$proyecto" \
      --env-file .env \
      "${archivos_compose[@]}" \
      down --volumes --remove-orphans

    printf 'Datos eliminados. .env se conservó.\n'
    ;;

  *)
    printf 'Opción inválida. Usa 1, 2, 3 o 4.\n' >&2
    exit 1
    ;;
esac
