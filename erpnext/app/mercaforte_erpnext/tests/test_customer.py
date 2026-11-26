from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from mercaforte_erpnext.customer import read_store_point, validate_store_location


class TestStoreLocation(UnitTestCase):
	def setUp(self):
		super().setUp()
		self.doc = frappe._dict(custom_mercaforte_estado="17", custom_mercaforte_municipio="17007")
		self.municipio_estado = self.enterContext(patch.object(frappe.db, "get_value", return_value="17"))

	def test_territory_is_required_and_limited_to_morelos(self):
		for estado, municipio in ((None, "17007"), ("09", "17007"), ("17", None), ("17", "")):
			with self.subTest(estado=estado, municipio=municipio), self.assertRaises(frappe.ValidationError):
				doc = frappe._dict(custom_mercaforte_estado=estado, custom_mercaforte_municipio=municipio)
				validate_store_location(doc)

		for parent_state in (None, "09"):
			self.municipio_estado.return_value = parent_state
			with self.subTest(parent_state=parent_state), self.assertRaises(frappe.ValidationError):
				validate_store_location(self.doc)
		self.municipio_estado.assert_called_with("Mercaforte Municipio", "17007", "estado")

	def test_optional_coordinates_and_valid_points(self):
		for latitude, longitude, expected in (
			(None, None, (0, 0)),
			("", "", (0, 0)),
			(0, 0, (0, 0)),
			("18.9234567", "-99.2212345", (18.9234567, -99.2212345)),
			(0, -99.22, (0, -99.22)),
			(18.92, 0, (18.92, 0)),
			(90, -180, (90, -180)),
			(-90, 180, (-90, 180)),
		):
			with self.subTest(latitude=latitude, longitude=longitude):
				self.doc.custom_mercaforte_latitud = latitude
				self.doc.custom_mercaforte_longitud = longitude
				validate_store_location(self.doc)
				self.assertEqual((self.doc.custom_mercaforte_latitud, self.doc.custom_mercaforte_longitud), expected)

	def test_invalid_coordinates(self):
		for field, limit in (("custom_mercaforte_latitud", 90), ("custom_mercaforte_longitud", 180)):
			for value in (limit + 1, -limit - 1, True, "texto", "nan", "1e999", [], {}, 10**1000):
				doc = self.doc.copy()
				doc[field] = value
				with self.subTest(field=field, value=value), self.assertRaises(frappe.ValidationError):
					validate_store_location(doc)


class TestLegacyStorePoint(UnitTestCase):
	def test_read_existing_geolocation(self):
		point = {"type": "Point", "coordinates": [-99.22, 18.92]}
		feature = {"type": "Feature", "geometry": point, "properties": {}}
		collection = {"type": "FeatureCollection", "features": [feature]}
		for value in (point, feature, collection):
			with self.subTest(value=value):
				self.assertEqual(read_store_point(value), [-99.22, 18.92])
		self.assertIsNone(read_store_point({"type": "FeatureCollection", "features": []}))

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
			with self.subTest(value=value), self.assertRaises(ValueError):
				read_store_point(value)
