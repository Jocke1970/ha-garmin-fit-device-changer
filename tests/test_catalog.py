import importlib.util
import sys
import types
import unittest
from pathlib import Path

COMPONENT_DIR = (
    Path(__file__).parents[1]
    / "custom_components"
    / "garmin_fit_device_changer"
)
PACKAGE = "garmin_fit_device_changer_catalog_test"
package = types.ModuleType(PACKAGE)
package.__path__ = [str(COMPONENT_DIR)]
sys.modules[PACKAGE] = package

spec = importlib.util.spec_from_file_location(
    f"{PACKAGE}.catalog",
    COMPONENT_DIR / "catalog.py",
)
catalog = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = catalog
spec.loader.exec_module(catalog)


class DeviceCatalogTests(unittest.TestCase):
    def test_current_verified_product_ids(self):
        self.assertEqual(catalog.get_device_definition("edge_1040").product, 3843)
        self.assertEqual(catalog.get_device_definition("edge_850").product, 4634)
        self.assertEqual(
            catalog.get_device_definition("fenix_7_pro_solar").product,
            4375,
        )
        self.assertEqual(catalog.get_device_definition("forerunner_970").product, 4565)

    def test_catalog_is_full_sdk_snapshot_not_small_curated_list(self):
        self.assertEqual(len(catalog.GARMIN_DEVICE_CATALOG), 367)
        self.assertEqual(
            len({device.key for device in catalog.GARMIN_DEVICE_CATALOG}),
            len(catalog.GARMIN_DEVICE_CATALOG),
        )
        self.assertEqual(
            len({device.product for device in catalog.GARMIN_DEVICE_CATALOG}),
            len(catalog.GARMIN_DEVICE_CATALOG),
        )

    def test_accessories_are_excluded(self):
        product_ids = {device.product for device in catalog.GARMIN_DEVICE_CATALOG}
        self.assertNotIn(10014, product_ids)  # Edge Remote
        self.assertNotIn(3143, product_ids)   # Descent T1 transmitter
        self.assertNotIn(4442, product_ids)   # Descent T2 transmitter

    def test_catalog_metadata(self):
        metadata = catalog.public_catalog_metadata()
        self.assertEqual(metadata["source"], "Garmin FIT SDK")
        self.assertEqual(metadata["profile_version"], "21.214.0Release")
        self.assertEqual(metadata["generated_at"], "2026-09-08")
        self.assertEqual(metadata["device_count"], len(catalog.GARMIN_DEVICE_CATALOG))

    def test_polished_display_labels(self):
        self.assertEqual(
            catalog.get_device_definition("descent_g1").label,
            "Garmin Descent G1",
        )
        self.assertEqual(
            catalog.get_device_definition("d2airvenu").label,
            "Garmin D2 Air / Venu",
        )

    def test_no_arbitrary_product_id_entry(self):
        self.assertFalse(hasattr(catalog, "parse_product_id"))

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
