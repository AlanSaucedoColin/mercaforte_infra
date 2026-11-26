# Mercaforte ERPNext

App única de Frappe para las personalizaciones de ERPNext de Mercaforte.

- **App técnica:** `mercaforte_erpnext`
- **Módulo:** `Mercaforte`
- **Versión:** `0.3.1`
- **Dependencia:** ERPNext

Cada tienda se registra como Cliente. El estado y el municipio son obligatorios en el formulario, el alta rápida y la API. Los clientes nuevos tienen Morelos preseleccionado. El catálogo contiene sus 36 municipios con las claves en texto del corte de junio de 2026. [Catálogo del INEGI](https://gaia.inegi.org.mx/wscatgeo/v2/mgem/17)

En **Cliente → Detalles**, el botón **Ver o editar ubicación** abre el mapa desde el bloque de coordenadas, debajo de **Longitud**. Coloca o mueve el marcador, confirma la selección y guarda el Cliente. Al reabrir el mapa aparece el punto guardado. También puedes borrar el marcador. Las coordenadas son opcionales y el par `(0, 0)` representa una tienda sin ubicación.

El mapa abre con unos 2 km de ancho, centrado en el marcador guardado o en la cabecera del municipio elegido. Si todavía no se eligió municipio, abre en Cuernavaca. Se puede navegar y seleccionar un punto fuera de Morelos.

La API nativa admite estos cuatro campos en el parámetro `fields` de `GET /api/resource/Customer`:

```json
["custom_mercaforte_estado", "custom_mercaforte_municipio", "custom_mercaforte_latitud", "custom_mercaforte_longitud"]
```

Al actualizar desde 0.2.0, la migración convierte los puntos de `custom_mercaforte_ubicacion` a latitud y longitud antes de retirar el campo. Si hay referencias a entidades o municipios fuera de Morelos, hay que resolverlas antes de reducir el catálogo. Los clientes anteriores sin municipio deben completarlo la próxima vez que se guarden.

## Instalación

La app vive dentro del repositorio de Infra y se distribuye en la imagen
personalizada. No se instala con `bench get-app` desde otro repositorio:

```bash
bench --site <sitio> install-app mercaforte_erpnext
```

Desde la carpeta de infraestructura `erpnext/`, las opciones **Inicializar** e **Iniciar** del manager construyen la imagen desde el Dockerfile local. **Inicializar** también instala la app si hace falta. Para actualizar un sitio existente, respáldalo, elige **Iniciar** y ejecuta `bench --site <sitio> migrate` en su backend. La migración sincroniza los DocTypes, los dos catálogos y los campos de Cliente.

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
