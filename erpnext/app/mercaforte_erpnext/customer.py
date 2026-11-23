import json
import math

import frappe
from frappe import _


def validate_store_location(doc, method=None):
	estado = doc.get("custom_mercaforte_estado")
	municipio = doc.get("custom_mercaforte_municipio")
	if municipio:
		if not estado or frappe.db.get_value("Mercaforte Municipio", municipio, "estado") != estado:
			frappe.throw(_("Elige un municipio o alcaldía que pertenezca al estado seleccionado."))

	raw = doc.get("custom_mercaforte_ubicacion")
	if raw is None or raw == "":
		return

	try:
		data = json.loads(raw) if isinstance(raw, str) else raw
		point = read_store_point(data)
	except (TypeError, ValueError):
		frappe.throw(_("La ubicación de la tienda debe contener un solo marcador válido o estar vacía."))

	if point is None:
		doc.custom_mercaforte_ubicacion = None
		return

	# Leaflet expects a Feature with a properties object when it redraws saved points.
	feature = {"type": "Feature", "geometry": {"type": "Point", "coordinates": point}, "properties": {}}
	doc.custom_mercaforte_ubicacion = json.dumps({"type": "FeatureCollection", "features": [feature]})


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
