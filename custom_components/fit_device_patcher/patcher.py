"""Surgical FIT creator-identity parser and patcher.

The patcher deliberately does not re-encode FIT messages. It only overwrites
creator fields that already exist in the target file and then recalculates the
trailing FIT CRC. This keeps activity, GPS, sensor and developer data untouched.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

# FIT global message numbers used by this integration.
MESG_FILE_ID = 0
MESG_DEVICE_INFO = 23
MESG_FILE_CREATOR = 49

# file_id field numbers.
FILE_ID_MANUFACTURER = 1
FILE_ID_PRODUCT = 2
FILE_ID_SERIAL_NUMBER = 3

# device_info field numbers.
DEVICE_INFO_DEVICE_INDEX = 0
DEVICE_INFO_MANUFACTURER = 2
DEVICE_INFO_SERIAL_NUMBER = 3
DEVICE_INFO_PRODUCT = 4
DEVICE_INFO_SOFTWARE_VERSION = 5

# file_creator field numbers.
FILE_CREATOR_SOFTWARE_VERSION = 0

DEVICE_INDEX_CREATOR = 0

# Garmin product labels needed for M1. Unknown products still work and receive
# a generic label when imported from a genuine reference FIT file.
KNOWN_DEVICE_LABELS: dict[tuple[int, int], str] = {
    (1, 3843): "Garmin Edge 1040",
    (1, 4375): "Garmin fēnix 7 Pro",
}

_CRC_TABLE = (
    0x0000,
    0xCC01,
    0xD801,
    0x1400,
    0xF001,
    0x3C00,
    0x2800,
    0xE401,
    0xA001,
    0x6C00,
    0x7800,
    0xB401,
    0x5000,
    0x9C01,
    0x8801,
    0x4400,
)


class FitPatchError(RuntimeError):
    """Raised when a FIT file cannot be safely parsed or patched."""


@dataclass(frozen=True)
class FieldDefinition:
    """One standard FIT field definition."""

    number: int
    size: int
    base_type: int


@dataclass(frozen=True)
class DeveloperFieldDefinition:
    """One developer FIT field definition."""

    number: int
    size: int
    developer_data_index: int


@dataclass(frozen=True)
class MessageDefinition:
    """Decoded FIT local-message definition."""

    local_message_number: int
    global_message_number: int
    little_endian: bool
    fields: Tuple[FieldDefinition, ...]
    developer_fields: Tuple[DeveloperFieldDefinition, ...]

    @property
    def data_size(self) -> int:
        """Return the byte size of one data message using this definition."""
        return sum(field.size for field in self.fields) + sum(
            field.size for field in self.developer_fields
        )


@dataclass
class DataRecord:
    """One parsed FIT data message and its field offsets."""

    definition: MessageDefinition
    payload_start: int
    payload_end: int
    field_offsets: Dict[int, Tuple[int, int]]


@dataclass(frozen=True)
class FitLayout:
    """Top-level offsets for one non-chained FIT file."""

    header_size: int
    data_start: int
    data_end: int
    file_crc_offset: int


@dataclass(frozen=True)
class CreatorIdentity:
    """Creator identity copied from a genuine reference FIT file."""

    manufacturer: int
    product: int
    serial_number: Optional[int]
    software_version: Optional[int]

    @property
    def default_label(self) -> str:
        """Return a human-friendly label for the identity."""
        return KNOWN_DEVICE_LABELS.get(
            (self.manufacturer, self.product),
            f"Device {self.manufacturer}:{self.product}",
        )


@dataclass(frozen=True)
class Patch:
    """Description of one creator field changed in the target FIT file."""

    message_name: str
    field_name: str
    offset: int
    size: int
    old_value: int
    new_value: int

    def as_public_dict(self) -> dict[str, object]:
        """Return a UI-safe representation; serial numbers are masked."""
        old: object = self.old_value
        new: object = self.new_value
        if self.field_name == "serial_number":
            old = mask_serial(self.old_value)
            new = mask_serial(self.new_value)
        elif self.field_name == "software_version":
            old = format_software_version(self.old_value)
            new = format_software_version(self.new_value)
        return {
            "message": self.message_name,
            "field": self.field_name,
            "old": old,
            "new": new,
        }


def mask_serial(value: Optional[int]) -> str:
    """Mask all but the last four digits of a serial number."""
    if value is None:
        return "—"
    text = str(value)
    return ("*" * max(0, len(text) - 4)) + text[-4:]


def format_software_version(raw_value: Optional[int]) -> str:
    """Format the FIT raw software-version field."""
    if raw_value is None:
        return "—"
    return f"{raw_value / 100:.2f}"


def _update_crc(value: int, crc: int) -> int:
    temp = _CRC_TABLE[crc & 0xF]
    crc = (crc >> 4) & 0x0FFF
    crc ^= temp ^ _CRC_TABLE[value & 0xF]

    temp = _CRC_TABLE[crc & 0xF]
    crc = (crc >> 4) & 0x0FFF
    crc ^= temp ^ _CRC_TABLE[(value >> 4) & 0xF]
    return crc


def fit_crc(data: bytes | bytearray, start: int = 0, end: Optional[int] = None) -> int:
    """Calculate the FIT CRC used by Garmin's FIT SDK."""
    if end is None:
        end = len(data)
    crc = 0
    for value in data[start:end]:
        crc = _update_crc(value, crc)
    return crc


def parse_layout(data: bytes | bytearray) -> FitLayout:
    """Validate one ordinary FIT file and return its top-level offsets."""
    if len(data) < 14:
        raise FitPatchError("The file is too short to be a valid FIT file.")

    header_size = data[0]
    if header_size not in (12, 14):
        raise FitPatchError(
            f"Unsupported FIT header size {header_size}; expected 12 or 14 bytes."
        )

    if bytes(data[8:12]) != b".FIT":
        raise FitPatchError("The file does not contain the .FIT header signature.")

    data_size = struct.unpack_from("<I", data, 4)[0]
    data_start = header_size
    data_end = data_start + data_size
    file_crc_offset = data_end

    if file_crc_offset + 2 > len(data):
        raise FitPatchError("The FIT header declares more data than the file contains.")

    if file_crc_offset + 2 != len(data):
        raise FitPatchError(
            "Chained FIT files are not supported yet; refusing to patch extra bytes."
        )

    if header_size == 14:
        expected_header_crc = struct.unpack_from("<H", data, 12)[0]
        actual_header_crc = fit_crc(data, 0, 12)
        if actual_header_crc != expected_header_crc:
            raise FitPatchError(
                "Invalid FIT header CRC "
                f"(file=0x{expected_header_crc:04X}, calculated=0x{actual_header_crc:04X})."
            )

    expected_file_crc = struct.unpack_from("<H", data, file_crc_offset)[0]
    actual_file_crc = fit_crc(data, 0, file_crc_offset)
    if actual_file_crc != expected_file_crc:
        raise FitPatchError(
            "Invalid FIT file CRC "
            f"(file=0x{expected_file_crc:04X}, calculated=0x{actual_file_crc:04X})."
        )

    return FitLayout(
        header_size=header_size,
        data_start=data_start,
        data_end=data_end,
        file_crc_offset=file_crc_offset,
    )


def _read_uint(
    raw: bytes | bytearray,
    offset: int,
    size: int,
    little_endian: bool,
) -> int:
    if size not in (1, 2, 4):
        raise FitPatchError(f"Unsupported integer field size: {size} bytes.")
    return int.from_bytes(
        raw[offset : offset + size],
        "little" if little_endian else "big",
    )


def _write_uint(
    raw: bytearray,
    offset: int,
    size: int,
    little_endian: bool,
    value: int,
) -> None:
    if size not in (1, 2, 4):
        raise FitPatchError(f"Unsupported integer field size: {size} bytes.")
    max_value = (1 << (size * 8)) - 1
    if not 0 <= value <= max_value:
        raise FitPatchError(f"Value {value} does not fit in a {size}-byte FIT field.")
    raw[offset : offset + size] = value.to_bytes(
        size,
        "little" if little_endian else "big",
    )


def iter_data_records(
    data: bytes | bytearray,
    layout: FitLayout,
) -> Iterable[DataRecord]:
    """Yield parsed standard FIT data records without decoding activity values."""
    definitions: Dict[int, MessageDefinition] = {}
    pos = layout.data_start

    while pos < layout.data_end:
        record_header = data[pos]
        pos += 1

        if record_header & 0x80:
            # Compressed timestamp data header: local message number is bits 5-6.
            local_num = (record_header >> 5) & 0x03
            is_definition = False
            has_developer_data = False
        else:
            # Normal header: bit 6 definition, bit 5 developer fields, bits 0-3 local num.
            local_num = record_header & 0x0F
            is_definition = bool(record_header & 0x40)
            has_developer_data = bool(record_header & 0x20)

        if is_definition:
            if pos + 5 > layout.data_end:
                raise FitPatchError("Truncated FIT message definition.")

            pos += 1  # reserved
            architecture = data[pos]
            pos += 1
            if architecture not in (0, 1):
                raise FitPatchError(f"Unknown FIT architecture value {architecture}.")
            little_endian = architecture == 0

            global_num = int.from_bytes(
                data[pos : pos + 2],
                "little" if little_endian else "big",
            )
            pos += 2

            num_fields = data[pos]
            pos += 1
            fields: List[FieldDefinition] = []
            for _ in range(num_fields):
                if pos + 3 > layout.data_end:
                    raise FitPatchError("Truncated FIT field definition.")
                fields.append(
                    FieldDefinition(
                        number=data[pos],
                        size=data[pos + 1],
                        base_type=data[pos + 2],
                    )
                )
                pos += 3

            developer_fields: List[DeveloperFieldDefinition] = []
            if has_developer_data:
                if pos >= layout.data_end:
                    raise FitPatchError("Truncated FIT developer-field definition.")
                num_dev_fields = data[pos]
                pos += 1
                for _ in range(num_dev_fields):
                    if pos + 3 > layout.data_end:
                        raise FitPatchError("Truncated FIT developer-field definition.")
                    developer_fields.append(
                        DeveloperFieldDefinition(
                            number=data[pos],
                            size=data[pos + 1],
                            developer_data_index=data[pos + 2],
                        )
                    )
                    pos += 3

            definitions[local_num] = MessageDefinition(
                local_message_number=local_num,
                global_message_number=global_num,
                little_endian=little_endian,
                fields=tuple(fields),
                developer_fields=tuple(developer_fields),
            )
            continue

        definition = definitions.get(local_num)
        if definition is None:
            raise FitPatchError(
                f"FIT data uses local message {local_num} before it is defined."
            )

        payload_start = pos
        payload_end = payload_start + definition.data_size
        if payload_end > layout.data_end:
            raise FitPatchError("Truncated FIT data message.")

        field_offsets: Dict[int, Tuple[int, int]] = {}
        cursor = payload_start
        for field in definition.fields:
            field_offsets[field.number] = (cursor, field.size)
            cursor += field.size

        yield DataRecord(
            definition=definition,
            payload_start=payload_start,
            payload_end=payload_end,
            field_offsets=field_offsets,
        )
        pos = payload_end

    if pos != layout.data_end:
        raise FitPatchError("FIT parsing ended at an unexpected byte offset.")


def _record_uint(
    raw: bytes | bytearray,
    record: DataRecord,
    field_number: int,
) -> Optional[int]:
    loc = record.field_offsets.get(field_number)
    if loc is None:
        return None
    offset, size = loc
    if size not in (1, 2, 4):
        return None
    return _read_uint(raw, offset, size, record.definition.little_endian)


def extract_creator_identity(data: bytes) -> CreatorIdentity:
    """Extract creator identity from a genuine reference FIT file."""
    layout = parse_layout(data)
    manufacturer: Optional[int] = None
    product: Optional[int] = None
    serial_number: Optional[int] = None
    software_version: Optional[int] = None

    for record in iter_data_records(data, layout):
        global_num = record.definition.global_message_number

        if global_num == MESG_FILE_ID and manufacturer is None:
            manufacturer = _record_uint(data, record, FILE_ID_MANUFACTURER)
            product = _record_uint(data, record, FILE_ID_PRODUCT)
            serial_number = _record_uint(data, record, FILE_ID_SERIAL_NUMBER)

        elif global_num == MESG_FILE_CREATOR and software_version is None:
            software_version = _record_uint(
                data,
                record,
                FILE_CREATOR_SOFTWARE_VERSION,
            )

        elif global_num == MESG_DEVICE_INFO:
            device_index = _record_uint(data, record, DEVICE_INFO_DEVICE_INDEX)
            if device_index != DEVICE_INDEX_CREATOR:
                continue
            if manufacturer is None:
                manufacturer = _record_uint(data, record, DEVICE_INFO_MANUFACTURER)
            if product is None:
                product = _record_uint(data, record, DEVICE_INFO_PRODUCT)
            if serial_number is None:
                serial_number = _record_uint(data, record, DEVICE_INFO_SERIAL_NUMBER)
            if software_version is None:
                software_version = _record_uint(
                    data,
                    record,
                    DEVICE_INFO_SOFTWARE_VERSION,
                )

    if manufacturer is None or product is None:
        raise FitPatchError(
            "The reference FIT does not contain a usable creator manufacturer/product."
        )
    if serial_number is None:
        raise FitPatchError(
            "The reference FIT does not contain a creator serial number. "
            "A genuine activity FIT from the device is required."
        )

    return CreatorIdentity(
        manufacturer=manufacturer,
        product=product,
        serial_number=serial_number,
        software_version=software_version,
    )


def _patch_scalar_field(
    raw: bytearray,
    record: DataRecord,
    field_number: int,
    new_value: int,
    message_name: str,
    field_name: str,
    patches: List[Patch],
) -> bool:
    loc = record.field_offsets.get(field_number)
    if loc is None:
        return False

    offset, size = loc
    if size not in (1, 2, 4):
        raise FitPatchError(
            f"{message_name}.{field_name} has unexpected size {size}; refusing to patch."
        )

    old_value = _read_uint(raw, offset, size, record.definition.little_endian)
    if old_value != new_value:
        _write_uint(raw, offset, size, record.definition.little_endian, new_value)
        patches.append(
            Patch(
                message_name=message_name,
                field_name=field_name,
                offset=offset,
                size=size,
                old_value=old_value,
                new_value=new_value,
            )
        )
    return True


def patch_fit_bytes(
    original: bytes,
    identity: CreatorIdentity,
) -> tuple[bytes, list[Patch]]:
    """Patch creator identity fields that already exist in the target FIT file."""
    raw = bytearray(original)
    layout = parse_layout(raw)
    patches: List[Patch] = []

    found_file_id_manufacturer = False
    found_file_id_product = False
    found_file_id_serial = False

    for record in iter_data_records(raw, layout):
        global_num = record.definition.global_message_number

        if global_num == MESG_FILE_ID:
            found_file_id_manufacturer |= _patch_scalar_field(
                raw,
                record,
                FILE_ID_MANUFACTURER,
                identity.manufacturer,
                "file_id",
                "manufacturer",
                patches,
            )
            found_file_id_product |= _patch_scalar_field(
                raw,
                record,
                FILE_ID_PRODUCT,
                identity.product,
                "file_id",
                "product",
                patches,
            )
            found_file_id_serial |= _patch_scalar_field(
                raw,
                record,
                FILE_ID_SERIAL_NUMBER,
                identity.serial_number,
                "file_id",
                "serial_number",
                patches,
            )

        elif global_num == MESG_FILE_CREATOR and identity.software_version is not None:
            _patch_scalar_field(
                raw,
                record,
                FILE_CREATOR_SOFTWARE_VERSION,
                identity.software_version,
                "file_creator",
                "software_version",
                patches,
            )

        elif global_num == MESG_DEVICE_INFO:
            device_index = _record_uint(raw, record, DEVICE_INFO_DEVICE_INDEX)
            if device_index != DEVICE_INDEX_CREATOR:
                continue

            _patch_scalar_field(
                raw,
                record,
                DEVICE_INFO_MANUFACTURER,
                identity.manufacturer,
                "device_info[creator]",
                "manufacturer",
                patches,
            )
            _patch_scalar_field(
                raw,
                record,
                DEVICE_INFO_PRODUCT,
                identity.product,
                "device_info[creator]",
                "product",
                patches,
            )
            _patch_scalar_field(
                raw,
                record,
                DEVICE_INFO_SERIAL_NUMBER,
                identity.serial_number,
                "device_info[creator]",
                "serial_number",
                patches,
            )
            if identity.software_version is not None:
                _patch_scalar_field(
                    raw,
                    record,
                    DEVICE_INFO_SOFTWARE_VERSION,
                    identity.software_version,
                    "device_info[creator]",
                    "software_version",
                    patches,
                )

    missing = []
    if not found_file_id_manufacturer:
        missing.append("file_id.manufacturer")
    if not found_file_id_product:
        missing.append("file_id.product")
    if not found_file_id_serial:
        missing.append("file_id.serial_number")
    if missing:
        raise FitPatchError(
            "The target FIT is missing required creator fields: " + ", ".join(missing)
        )

    # Data size is unchanged, so the 12/14-byte header and its optional header CRC
    # remain valid. Only the trailing file CRC needs to be recalculated.
    new_crc = fit_crc(raw, 0, layout.file_crc_offset)
    struct.pack_into("<H", raw, layout.file_crc_offset, new_crc)

    # Re-validate the result and verify that only planned creator bytes + CRC changed.
    parse_layout(raw)
    allowed_offsets = {layout.file_crc_offset, layout.file_crc_offset + 1}
    for patch in patches:
        allowed_offsets.update(range(patch.offset, patch.offset + patch.size))

    unexpected = [
        offset
        for offset, (before, after) in enumerate(zip(original, raw))
        if before != after and offset not in allowed_offsets
    ]
    if unexpected:
        raise FitPatchError(
            "Internal safety verification failed at byte offset "
            f"{unexpected[0]}; refusing the result."
        )

    return bytes(raw), patches
