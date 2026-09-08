import importlib.util
import sys
import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "update_garmin_catalog.py"
spec = importlib.util.spec_from_file_location("garmin_catalog_generator_test", SCRIPT_PATH)
generator = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = generator
spec.loader.exec_module(generator)


class CatalogGeneratorTests(unittest.TestCase):
    def test_supported_activity_device_families(self):
        for name in (
            "EDGE_850",
            "FR970",
            "FENIX9_PRO_47MM",
            "EPIX_GEN2_PRO_47",
            "VENU4",
            "VIVOACTIVE6",
            "INSTINCT3_SOLAR_50MM",
            "ENDURO3",
            "MARQ_GEN2",
            "TACTIX8_SOLAR",
            "DESCENT_G2",
            "D2_MACH2",
            "LILY2",
            "SWIM2",
            "APPROACHS50",
            "BOUNCE2",
        ):
            with self.subTest(name=name):
                self.assertTrue(generator.is_supported_device(name))

    def test_accessories_and_non_watch_products_are_excluded(self):
        for name in (
            "EDGE_REMOTE",
            "DESCENT_T1",
            "DESCENT_T2",
            "HRM_200",
            "VARIA_RCT715",
            "INDEX_SMART_SCALE_2",
            "CIRQA_SMART_BAND",
            "TACX_NEO2_T_SMART",
        ):
            with self.subTest(name=name):
                self.assertFalse(generator.is_supported_device(name))

    def test_current_label_and_key_examples(self):
        self.assertEqual(generator.label_for("EDGE_850"), "Garmin Edge 850")
        self.assertEqual(
            generator.label_for("FENIX7_PRO_SOLAR"),
            "Garmin fēnix 7 Pro Solar",
        )
        self.assertEqual(generator.label_for("FR965"), "Garmin Forerunner 965")
        self.assertEqual(generator.label_for("APPROACHS44"), "Garmin Approach S44")
        self.assertEqual(generator.key_for("EDGE_1040"), "edge_1040")
        self.assertEqual(generator.key_for("FR970"), "forerunner_970")

    def test_metadata_parser(self):
        source = "// Profile Version = 21.214.0Release\n// Tag = production/release/test\n"
        self.assertEqual(
            generator.parse_metadata(source),
            ("21.214.0Release", "production/release/test"),
        )


if __name__ == "__main__":
    unittest.main()
