"""Built-in Garmin device catalog for manual creator profiles."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Optional

GARMIN_MANUFACTURER = 1


@dataclass(frozen=True)
class GarminDeviceDefinition:
    """One Garmin model with FIT manufacturer/product identity."""

    key: str
    label: str
    product: int
    manufacturer: int = GARMIN_MANUFACTURER

    def to_public(self) -> dict[str, object]:
        """Return frontend-safe catalog metadata."""
        return {
            "key": self.key,
            "label": self.label,
            "manufacturer": self.manufacturer,
            "product": self.product,
        }


# Curated from Garmin's current FIT SDK GarminProduct enum. This first catalog
# intentionally focuses on popular modern devices; it can grow independently
# from the patcher engine.
GARMIN_DEVICE_CATALOG: tuple[GarminDeviceDefinition, ...] = (
    GarminDeviceDefinition("edge_1040", "Garmin Edge 1040", 3843),
    GarminDeviceDefinition("edge_1050", "Garmin Edge 1050", 4440),
    GarminDeviceDefinition("fenix_7s_pro", "Garmin fēnix 7S Pro", 4374),
    GarminDeviceDefinition("fenix_7_pro", "Garmin fēnix 7 Pro", 4375),
    GarminDeviceDefinition("fenix_7x_pro", "Garmin fēnix 7X Pro", 4376),
    GarminDeviceDefinition("forerunner_965", "Garmin Forerunner 965", 4315),
    GarminDeviceDefinition("forerunner_970", "Garmin Forerunner 970", 4565),
)

_CATALOG_BY_KEY = {device.key: device for device in GARMIN_DEVICE_CATALOG}


def get_device_definition(key: str) -> Optional[GarminDeviceDefinition]:
    """Return one built-in Garmin device definition."""
    return _CATALOG_BY_KEY.get(key)


def public_device_catalog() -> list[dict[str, object]]:
    """Return the built-in catalog sorted by display name."""
    return [
        device.to_public()
        for device in sorted(GARMIN_DEVICE_CATALOG, key=lambda item: item.label.lower())
    ]


def parse_product_id(value: object) -> int:
    """Validate a Garmin FIT Product ID entered manually."""
    text = str(value or "").strip()
    if not text or not text.isdigit():
        raise ValueError("Product ID must contain digits only.")
    product = int(text)
    if not 0 <= product <= 0xFFFF:
        raise ValueError("Product ID must fit in a FIT uint16 field.")
    return product


def parse_serial_number(value: object) -> int:
    """Validate a Garmin/FIT uint32 serial number entered manually."""
    text = str(value or "").strip()
    if not text or not text.isdigit():
        raise ValueError("Serial number must contain digits only.")
    serial = int(text)
    if not 0 <= serial <= 0xFFFFFFFF:
        raise ValueError("Serial number must fit in a FIT uint32 field.")
    return serial


def parse_software_version(value: object) -> int:
    """Convert a display firmware version such as 30.11 to FIT raw hundredths."""
    text = str(value or "").strip().replace(",", ".")
    if not text:
        raise ValueError("Firmware version is required for full identity mode.")

    try:
        decimal_value = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError("Firmware version must be a number such as 30.11.") from exc

    if decimal_value < 0:
        raise ValueError("Firmware version cannot be negative.")

    raw_decimal = decimal_value * 100
    if raw_decimal != raw_decimal.to_integral_value():
        raise ValueError("Firmware version may use at most two decimal places.")

    raw = int(raw_decimal)
    if raw > 0xFFFF:
        raise ValueError("Firmware version is too large for the FIT field.")
    return raw
