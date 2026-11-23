import json
from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from mercaforte_erpnext.customer import validate_store_location


class TestStoreLocation(UnitTestCase):
	def test_geolocation_round_trip(self):
		point = {"type": "Point", "coordinates": [-99.22, 18.92]}
		feature = {"type": "Feature", "geometry": point, "properties": {}}
		collection = {"type": "FeatureCollection", "features": [feature]}
		for value in (point, feature, collection, json.dumps(collection)):
			with self.subTest(value=value):
				doc = frappe._dict(custom_mercaforte_ubicacion=value)
				validate_store_location(doc)
				self.assertEqual(json.loads(doc.custom_mercaforte_ubicacion), collection)

	def test_empty_location(self):
		for value in (None, "", {"type": "FeatureCollection", "features": []}):
			doc = frappe._dict(custom_mercaforte_ubicacion=value)
			validate_store_location(doc)
			self.assertFalse(doc.custom_mercaforte_ubicacion)

	def test_invalid_map(self):
		point = {"type": "Point", "coordinates": [0, 0]}
		feature = {"type": "Feature", "geometry": point, "properties": {}}
		invalid = [
			"invalid JSON", [], {}, {"type": "LineString", "coordinates": []},
			{"type": "FeatureCollection", "features": [feature, feature]},
			{"type": "FeatureCollection", "features": [point]},
			{**feature, "properties": {"point_type": "circle", "radius": 10}},
		]
		for coords in ([181, 0], [0, -91], [True, 2], [0], [1, 2, float("nan")], ["-99", 19]):
			invalid.append({"type": "Point", "coordinates": coords})
		for value in invalid:
			with self.subTest(value=value), self.assertRaises(frappe.ValidationError):
				validate_store_location(frappe._dict(custom_mercaforte_ubicacion=value))

	def test_state_and_municipality(self):
		with patch("mercaforte_erpnext.customer.frappe.db.get_value", return_value="17"):
			for state in ("09", None):
				with self.subTest(state=state), self.assertRaises(frappe.ValidationError):
					validate_store_location(
						frappe._dict(custom_mercaforte_estado=state, custom_mercaforte_municipio="17007")
					)
			validate_store_location(frappe._dict(custom_mercaforte_estado="17", custom_mercaforte_municipio="17007"))
			validate_store_location(frappe._dict(custom_mercaforte_estado="17"))
