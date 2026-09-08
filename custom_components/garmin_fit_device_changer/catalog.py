"""Garmin device catalog helpers for manual creator profiles."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Optional

from .generated_catalog import (
    GARMIN_CATALOG_GENERATED_AT,
    GARMIN_FIT_PROFILE_TAG,
    GARMIN_FIT_PROFILE_VERSION,
    GENERATED_DEVICE_CATALOG,
)

GARMIN_MANUFACTURER = 1


@dataclass(frozen=True)
class GarminDeviceDefinition:
    """One Garmin model with FIT manufacturer/product identity."""

    key: str
    label: str
    product: int
    sdk_name: str
    manufacturer: int = GARMIN_MANUFACTURER

    def to_public(self) -> dict[str, object]:
        """Return frontend-safe catalog metadata."""
        return {
            "key": self.key,
            "label": self.label,
            "manufacturer": self.manufacturer,
            "product": self.product,
        }


def _polish_generated_label(label: str, sdk_name: str) -> str:
    """Apply small branding/readability fixes to generated SDK labels."""
    if sdk_name == "D2AIRVENU":
        return "Garmin D2 Air / Venu"
    if sdk_name == "LILY_ATHLETE":
        return "Garmin Lily 2 Active"

    replacements = (
        (" MK ", " Mk"),
        (" GEN ", " Gen "),
        (" G 1", " G1"),
        (" G 2", " G2"),
        (" X 1", " X1"),
        (" X 10", " X10"),
        (" X 15", " X15"),
        (" EXPLORE ", " Explore "),
        (" 2MUSIC", " 2 Music"),
        (" V 2", " v2"),
        (" FIRST AVENGER", " First Avenger"),
        (" DARTH VADER", " Darth Vader"),
        (" REY", " Rey"),
        (" Captain MARVEL", " Captain Marvel"),
    )
    for old, new in replacements:
        label = label.replace(old, new)
    return label


GARMIN_DEVICE_CATALOG: tuple[GarminDeviceDefinition, ...] = tuple(
    GarminDeviceDefinition(
        key=key,
        label=_polish_generated_label(label, sdk_name),
        product=product,
        sdk_name=sdk_name,
    )
    for key, label, product, sdk_name in GENERATED_DEVICE_CATALOG
)

_CATALOG_BY_KEY = {device.key: device for device in GARMIN_DEVICE_CATALOG}


def get_device_definition(key: str) -> Optional[GarminDeviceDefinition]:
    """Return one bundled Garmin SDK device definition."""
    return _CATALOG_BY_KEY.get(key)


def public_device_catalog() -> list[dict[str, object]]:
    """Return the bundled SDK-derived catalog sorted by display name."""
    return [
        device.to_public()
        for device in sorted(
            GARMIN_DEVICE_CATALOG,
            key=lambda item: (item.label.casefold(), item.product),
        )
    ]


def public_catalog_metadata() -> dict[str, object]:
    """Return traceability metadata for the bundled Garmin FIT SDK snapshot."""
    return {
        "source": "Garmin FIT SDK",
        "profile_version": GARMIN_FIT_PROFILE_VERSION,
        "profile_tag": GARMIN_FIT_PROFILE_TAG,
        "generated_at": GARMIN_CATALOG_GENERATED_AT,
        "device_count": len(GARMIN_DEVICE_CATALOG),
    }


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
