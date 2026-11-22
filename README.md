# ERPNext en producción

## 1. Inicializar

En el servidor Linux, apunta el DNS del dominio al servidor y permite TCP `80` y `443`. Desde la raíz de `mercaforte_infra`, prepara una copia privada del manager:

```bash
install -m 700 erpnext-manager.sh erpnext-manager.prod.sh  # solo la primera vez
nano erpnext-manager.prod.sh
```

Completa al principio `root`, `dominio` (sin `https://`), `correo_letsencrypt`, `password_mariadb` y `password_administrator`. Usa contraseñas de una sola línea.

```bash
./erpnext-manager.prod.sh   # 1) Inicializar
```

Esto comprueba Docker y Compose, prepara las carpetas y genera `.env.erpnext`. Si el archivo ya existe, se conserva: verifica que `ERPNEXT_DATA_ROOT`, `SITES_RULE` y `LETSENCRYPT_EMAIL` coincidan con tu configuración. Para crear el sitio, `password_mariadb` del script y `DB_PASSWORD` de `.env.erpnext` deben coincidir con la contraseña de `root` de MariaDB.

La inicialización levanta los servicios, crea el sitio con ERPNext si aún no existe y lo deja en ejecución. Abre `https://TU_DOMINIO` e inicia sesión con `Administrator` y `password_administrator`.

## 2. Iniciar después de una parada

```bash
./erpnext-manager.prod.sh   # 2) Iniciar
```

Esta opción solo levanta los servicios del sitio existente.

**3) Detener** conserva los datos. **4) Purgar** detiene ERPNext y vacía `root`, conservando `.env.erpnext`. Después de purgar, ejecuta **1) Inicializar** para comenzar de nuevo.
