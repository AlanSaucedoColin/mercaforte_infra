import json
from pathlib import Path

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.model.dynamic_links import get_dynamic_links
from frappe.model.rename_doc import get_link_fields

from mercaforte_erpnext.customer import read_store_point

STATE = "Mercaforte Estado"
MUNICIPALITY = "Mercaforte Municipio"
OLD_MAP = "custom_mercaforte_ubicacion"
LATITUDE = "custom_mercaforte_latitud"
LONGITUDE = "custom_mercaforte_longitud"


def execute():
	"""Conservar los puntos de Cliente y limitar el catálogo territorial a Morelos."""
	keep = {STATE: {"17"}, MUNICIPALITY: {f"17{i:03d}" for i in range(1, 37)}}
	remove = {
		dt: frappe.get_all(dt, filters={"name": ["not in", sorted(keys)]}, pluck="name")
		for dt, keys in keep.items()
	}
	check_catalog_links(remove, keep)
	migrate_points()

	# These are fixture records with no child tables. All references were checked
	# before deleting either list, including links added by other installed apps.
	for dt in (MUNICIPALITY, STATE):
		if remove[dt]:
			frappe.db.delete(dt, {"name": ["in", remove[dt]]})


def check_catalog_links(remove, keep):
	dynamic_fields = get_dynamic_links()
	for target, obsolete in remove.items():
		if not obsolete:
			continue
		for field in get_link_fields(target):
			check_reference(target, obsolete, field.parent, field.fieldname, keep)
		for field in dynamic_fields:
			check_reference(target, obsolete, field.parent, field.fieldname, keep, field.options)
		# File stores its attachment reference in Data fields, outside Link metadata.
		check_reference(target, obsolete, "File", "attached_to_name", keep, "attached_to_doctype")


def check_reference(target, obsolete, source, field, keep, type_field=None):
	meta = frappe.get_meta(source)
	if meta.is_virtual or meta.get_field(field).is_virtual:
		return
	if meta.issingle:
		values = frappe.db.get_singles_dict(source)
		if (type_field and values.get(type_field) != target) or values.get(field) not in obsolete:
			return
		document = source
	else:
		filters = {field: ["in", obsolete]}
		if type_field:
			filters[type_field] = target
		if source in keep:
			# The municipalities leaving the catalog link to their own departing states.
			filters["name"] = ["in", sorted(keep[source])]
		document = frappe.db.get_value(source, filters, "name")
	if document:
		frappe.throw(
			_(
				"El campo {0} de {1} {2} hace referencia a un registro de {3} fuera de Morelos. "
				"Corrige el vínculo y vuelve a migrar."
			).format(field, source, document, target),
			frappe.LinkExistsError,
		)


def migrate_points():
	if not frappe.db.has_column("Customer", OLD_MAP):
		return
	customer = frappe.qb.DocType("Customer")
	with_location = customer[OLD_MAP].notnull() & (customer[OLD_MAP] != "")
	rows = frappe.qb.from_(customer).select(customer.name, customer[OLD_MAP]).where(with_location).run()
	points = {}
	for name, raw in rows:
		try:
			point = read_store_point(json.loads(raw))
		except (TypeError, ValueError):
			frappe.throw(_("Ubicación anterior inválida en el Cliente {0}.").format(name))
		if point is not None:
			longitude, latitude = point[:2]
			pair = (round(latitude, 7), round(longitude, 7))
			if pair == (0, 0):
				frappe.throw(
					_("El marcador anterior de {0} coincide con (0, 0). Corrige o borra el marcador antes de migrar.")
					.format(name)
				)
			points[name] = pair

	if points:
		# Custom Field fixtures normally arrive after post_model_sync patches.
		path = Path(frappe.get_app_path("mercaforte_erpnext", "fixtures", "3_custom_field.json"))
		fields = [df for df in json.loads(path.read_text()) if df["fieldname"] in (LATITUDE, LONGITUDE)]
		create_custom_fields({"Customer": fields}, update=False)
		for name, pair in points.items():
			current = frappe.db.get_value("Customer", name, [LATITUDE, LONGITUDE])
			if current != (0, 0) and tuple(map(float, current)) != pair:
				frappe.throw(_("El Cliente {0} ya tiene coordenadas distintas del marcador.").format(name))
			frappe.db.set_value("Customer", name, {LATITUDE: pair[0], LONGITUDE: pair[1]}, update_modified=False)
			stored = frappe.db.get_value("Customer", name, [LATITUDE, LONGITUDE])
			if tuple(map(float, stored)) != pair:
				frappe.throw(_("No se pudieron verificar las coordenadas del Cliente {0}.").format(name))

	# Frappe retains physical columns after removing a custom field.
	frappe.qb.update(customer).set(customer[OLD_MAP], None).where(with_location).run()
	frappe.delete_doc("Custom Field", f"Customer-{OLD_MAP}")
