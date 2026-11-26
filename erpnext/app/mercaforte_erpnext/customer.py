import math

import frappe
from frappe import _


def validate_store_location(doc, method=None):
	if doc.get("custom_mercaforte_estado") != "17":
		frappe.throw(_("Selecciona Morelos como estado de la tienda."))

	municipio = doc.get("custom_mercaforte_municipio")
	if not municipio or frappe.db.get_value("Mercaforte Municipio", municipio, "estado") != "17":
		frappe.throw(_("Selecciona un municipio de Morelos."))

	doc.custom_mercaforte_latitud = _coordinate(doc.get("custom_mercaforte_latitud"), _("Latitud"), 90)
	doc.custom_mercaforte_longitud = _coordinate(doc.get("custom_mercaforte_longitud"), _("Longitud"), 180)


def _coordinate(value, label, limit):
	if value is None or value == "":
		return 0.0

	# Frappe's Float conversion accepts invalid strings as zero. Validate before persistence.
	try:
		number = float(value)
	except (TypeError, ValueError, OverflowError):
		number = None

	if isinstance(value, bool) or number is None or not -limit <= number <= limit:
		frappe.throw(_("{0} debe ser un número entre {1} y {2}.").format(label, -limit, limit))
	return number


def read_store_point(data):
	"""Read a GeoJSON Point, Feature or native Geolocation FeatureCollection."""
	if not isinstance(data, dict):
		raise ValueError
	if data.get("type") == "FeatureCollection":
		features = data.get("features")
		if not isinstance(features, list) or len(features) > 1:
			raise ValueError
		if not features:
			return None
		data = features[0]
		if not isinstance(data, dict) or data.get("type") != "Feature":
			raise ValueError
	if data.get("type") == "Feature":
		properties = data.get("properties")
		if properties is not None and (
			not isinstance(properties, dict) or properties.get("point_type") in ("circle", "circlemarker")
		):
			raise ValueError
		data = data.get("geometry")
	if not isinstance(data, dict) or data.get("type") != "Point":
		raise ValueError
	coords = data.get("coordinates")
	if not isinstance(coords, list) or len(coords) not in (2, 3):
		raise ValueError
	for value in coords:
		if type(value) not in (int, float) or (isinstance(value, float) and not math.isfinite(value)):
			raise ValueError
	if not (-180 <= coords[0] <= 180 and -90 <= coords[1] <= 90):
		raise ValueError
	return coords
