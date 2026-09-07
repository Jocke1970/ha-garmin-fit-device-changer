import importlib.util
import struct
import sys
import unittest
from pathlib import Path

PATCHER_PATH = Path(__file__).parents[1] / "custom_components" / "fit_device_patcher" / "patcher.py"
spec = importlib.util.spec_from_file_location("fit_device_patcher_patcher", PATCHER_PATH)
patcher = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = patcher
spec.loader.exec_module(patcher)

CreatorIdentity = patcher.CreatorIdentity
extract_creator_identity = patcher.extract_creator_identity
fit_crc = patcher.fit_crc
parse_layout = patcher.parse_layout
patch_fit_bytes = patcher.patch_fit_bytes


def make_fit(
    manufacturer=1,
    product=999,
    serial=123456789,
    software=123,
    include_creator_device=True,
) -> bytes:
    data = bytearray()

    # local 0: file_id with type/manufacturer/product/serial/time_created
    data += bytes([
        0x40, 0x00, 0x00, 0x00, 0x00, 0x05,
        0x00, 0x01, 0x00,
        0x01, 0x02, 0x84,
        0x02, 0x02, 0x84,
        0x03, 0x04, 0x8C,
        0x04, 0x04, 0x86,
    ])
    data += bytes([0x00, 0x04])
    data += struct.pack("<HHII", manufacturer, product, serial, 1_000_000)

    # local 1: file_creator software_version
    data += bytes([
        0x41, 0x00, 0x00, 0x31, 0x00, 0x01,
        0x00, 0x02, 0x84,
    ])
    data += bytes([0x01]) + struct.pack("<H", software)

    if include_creator_device:
        # local 2: device_info index/manufacturer/serial/product/software
        data += bytes([
            0x42, 0x00, 0x00, 0x17, 0x00, 0x05,
            0x00, 0x01, 0x02,
            0x02, 0x02, 0x84,
            0x03, 0x04, 0x8C,
            0x04, 0x02, 0x84,
            0x05, 0x02, 0x84,
        ])
        data += bytes([0x02, 0x00])
        data += struct.pack("<HIHH", manufacturer, serial, product, software)
        # accessory record: must remain untouched
        data += bytes([0x02, 0x01])
        data += struct.pack("<HIHH", 1, 555555, 1234, 777)

    header = bytearray(14)
    header[0] = 14
    header[1] = 0x20
    struct.pack_into("<H", header, 2, 0x08D6)
    struct.pack_into("<I", header, 4, len(data))
    header[8:12] = b".FIT"
    struct.pack_into("<H", header, 12, fit_crc(header, 0, 12))

    out = header + data
    out += struct.pack("<H", fit_crc(out, 0, len(out)))
    return bytes(out)


class FitDevicePatcherTests(unittest.TestCase):
    def test_extract_reference_identity(self):
        reference = make_fit(1, 3843, 3417487351, 3011)
        self.assertEqual(
            extract_creator_identity(reference),
            CreatorIdentity(1, 3843, 3417487351, 3011),
        )

    def test_patch_only_creator_metadata(self):
        original = make_fit(331, 3570, 3313379353, 29)
        identity = CreatorIdentity(1, 3843, 3417487351, 3011)
        patched, changes = patch_fit_bytes(original, identity)
        parse_layout(patched)

        changed_names = {(change.message_name, change.field_name) for change in changes}
        self.assertIn(("file_id", "manufacturer"), changed_names)
        self.assertIn(("file_id", "product"), changed_names)
        self.assertIn(("file_id", "serial_number"), changed_names)
        self.assertIn(("file_creator", "software_version"), changed_names)
        self.assertIn(("device_info[creator]", "serial_number"), changed_names)

        # Accessory metadata remains byte-for-byte present.
        self.assertIn(struct.pack("<I", 555555), patched)
        self.assertIn(struct.pack("<H", 1234), patched)
        self.assertIn(struct.pack("<H", 777), patched)

        layout = parse_layout(patched)
        allowed = {layout.file_crc_offset, layout.file_crc_offset + 1}
        for change in changes:
            allowed.update(range(change.offset, change.offset + change.size))
        diffs = {i for i, (a, b) in enumerate(zip(original, patched)) if a != b}
        self.assertTrue(diffs <= allowed)

    def test_no_message_insertion_when_device_info_missing(self):
        original = make_fit(331, 3570, 3313379353, 29, include_creator_device=False)
        identity = CreatorIdentity(1, 4375, 3511528293, 2609)
        patched, _ = patch_fit_bytes(original, identity)
        self.assertEqual(len(patched), len(original))
        parse_layout(patched)


if __name__ == "__main__":
    unittest.main()
