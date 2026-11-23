from importlib.metadata import version

from frappe.tests import UnitTestCase

import mercaforte_erpnext
from mercaforte_erpnext import hooks


class TestAppMetadata(UnitTestCase):
	def test_base_app_metadata(self):
		self.assertEqual(mercaforte_erpnext.__version__, version("mercaforte_erpnext"))
		self.assertEqual(hooks.app_title, "Mercaforte ERPNext")
		self.assertEqual(hooks.required_apps, ["erpnext"])
