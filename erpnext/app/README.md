# Mercaforte ERPNext

App única de Frappe para las personalizaciones de ERPNext de Mercaforte.

- **App técnica:** `mercaforte_erpnext`
- **Módulo:** `Mercaforte`
- **Versión:** `0.2.0`
- **Dependencia:** ERPNext

Cada tienda se registra como Cliente. El alta rápida permite elegir estado y municipio o alcaldía, y continuar al formulario completo. El mapa del formulario completo guarda un marcador manual. Los tres campos son opcionales.

El catálogo nacional incluye 32 entidades y 2,478 municipios y alcaldías del corte del 1 de junio de 2026 del INEGI. Los documentos conservan como identificador la clave geoestadística en texto. [Catálogo Único del INEGI](https://www.inegi.org.mx/servicios/catalogounico/)

## Instalación

La app vive dentro del repositorio de Infra y se distribuye en la imagen
personalizada. No se instala con `bench get-app` desde otro repositorio:

```bash
bench --site <sitio> install-app mercaforte_erpnext
```

Desde la carpeta de infraestructura `erpnext/`, construye la imagen con `docker compose -f compose.build.yaml build`. El menú de `manager.sh` permite inicializar el sitio con la app. Para actualizar un sitio existente, respáldalo, inicia los servicios con la nueva imagen y ejecuta `bench --site <sitio> migrate` en su backend. La migración sincroniza los DocTypes, los dos catálogos y los campos de Cliente.

## Convenciones para futuras personalizaciones

- Crea DocTypes y código propio bajo el módulo `Mercaforte`.
- Activa `developer_mode` únicamente en un sitio de desarrollo.
- Versiona los JSON generados por Frappe y revisa el diff antes de publicarlos.
- Declara Custom Fields y otras personalizaciones exportables mediante fixtures
  solo cuando el alcance funcional esté aprobado.
- Usa patches idempotentes para migraciones de datos; no hagas cambios manuales
  de esquema en producción.
- Mantén integraciones externas detrás de módulos propios y nunca versionees
  credenciales.
- Incrementa `mercaforte_erpnext/__init__.py::__version__` y la etiqueta de
  imagen en cada entrega.

## Pruebas

Desde el Bench que contiene la app:

```bash
bench --site <sitio-dev> run-tests \
  --app mercaforte_erpnext \
  --test-category unit
```

El scaffold conserva la configuración oficial de `ruff`, ESLint, Prettier y
pre-commit generada por Frappe.

## Licencia

MIT
