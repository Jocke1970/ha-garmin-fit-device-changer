import importlib.util
import sys
import unittest
from pathlib import Path

CATALOG_PATH = Path(__file__).parents[1] / "custom_components" / "fit_device_patcher" / "catalog.py"
spec = importlib.util.spec_from_file_location("fit_device_patcher_catalog", CATALOG_PATH)
catalog = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = catalog
spec.loader.exec_module(catalog)


class DeviceCatalogTests(unittest.TestCase):
    def test_verified_product_ids(self):
        self.assertEqual(catalog.get_device_definition("edge_1040").product, 3843)
        self.assertEqual(catalog.get_device_definition("fenix_7_pro").product, 4375)

    def test_parse_serial_number(self):
        self.assertEqual(catalog.parse_serial_number("3417487351"), 3417487351)
        with self.assertRaises(ValueError):
            catalog.parse_serial_number("12AB")

    def test_parse_software_version(self):
        self.assertEqual(catalog.parse_software_version("30.11"), 3011)
        self.assertEqual(catalog.parse_software_version("26,09"), 2609)
        self.assertEqual(catalog.parse_software_version("30.1"), 3010)
        with self.assertRaises(ValueError):
            catalog.parse_software_version("30.111")


if __name__ == "__main__":
    unittest.main()
