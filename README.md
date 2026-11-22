# ERPNext en producción

## 1. Inicializar

En el servidor Linux, apunta el DNS del dominio al servidor y permite TCP `80` y `443`. Entra al directorio de ERPNext y prepara una copia privada del manager:

```bash
cd erpnext
install -m 700 manager.sh manager.prod.sh  # solo la primera vez
nano manager.prod.sh
```

Define `entorno='prod'` y completa al principio `dominio` (sin `https://`), `correo_letsencrypt`, `password_mariadb`, `password_administrator` y `forwarded_allow_ips`. Usa contraseñas de una sola línea y `forwarded_allow_ips='*'` cuando solo los servicios de esta pila puedan alcanzar el backend.

```bash
./manager.prod.sh   # 1) Inicializar
```

Esto comprueba Docker y Compose y genera `erpnext/.env` a partir de `.env.example`. Si el archivo ya existe, se conserva y se valida contra la configuración del script. Docker administra los volúmenes persistentes.

La inicialización levanta los servicios, crea el sitio con ERPNext si aún no existe y lo deja en ejecución. Abre `https://TU_DOMINIO` e inicia sesión con `Administrator` y `password_administrator`.

## 2. Iniciar después de una parada

```bash
./manager.prod.sh   # 2) Iniciar
```

Esta opción solo levanta los servicios del sitio existente.

**3) Detener** conserva los volúmenes. **4) Purgar** detiene ERPNext y elimina sus volúmenes, conservando `.env`. Después de purgar, ejecuta **1) Inicializar** para comenzar de nuevo.
