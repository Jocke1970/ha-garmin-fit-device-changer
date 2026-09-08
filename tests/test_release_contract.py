import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
COMPONENT = ROOT / "custom_components" / "garmin_fit_device_changer"
API = (COMPONENT / "api.py").read_text(encoding="utf-8")
STORAGE = (COMPONENT / "storage.py").read_text(encoding="utf-8")
CARD = (COMPONENT / "www" / "garmin-fit-device-changer-card.js").read_text(
    encoding="utf-8"
)


class ReleaseContractTests(unittest.TestCase):
    def test_sdk_profiles_require_full_identity(self):
        self.assertIn('requested_mode != "full"', API)
        self.assertIn("Serial number and firmware are required", API)
        self.assertNotIn('profile.identity_mode == "basic"', API)

    def test_reference_profiles_require_complete_identity(self):
        self.assertIn("Reference FIT does not contain a complete Garmin creator identity", API)

    def test_storage_does_not_create_new_basic_profiles(self):
        self.assertIn('if mode != "full"', STORAGE)
        self.assertIn("Full Garmin identity requires both serial number and firmware", STORAGE)

    def test_card_has_no_basic_creation_mode(self):
        self.assertNotIn('id="manual-mode"', CARD)
        self.assertNotIn('<option value="basic"', CARD)
        self.assertIn('identity_mode: "full"', CARD)
        self.assertIn("legacyBasic", CARD)
        self.assertIn('CARD_VERSION = "0.1.0-m1.14"', CARD)


if __name__ == "__main__":
    unittest.main()
