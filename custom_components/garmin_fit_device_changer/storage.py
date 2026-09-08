"""Local storage for FIT creator profiles."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import LEGACY_STORAGE_KEY, STORAGE_KEY, STORAGE_VERSION
from .patcher import CreatorIdentity, format_software_version, mask_serial


@dataclass(frozen=True)
class DeviceProfile:
    """A saved creator identity used as a patch target."""

    profile_id: str
    label: str
    manufacturer: int
    product: int
    serial_number: Optional[int]
    software_version: Optional[int]
    source: str = "reference"
    identity_mode: str = "full"

    @property
    def identity(self) -> CreatorIdentity:
        """Return the patcher identity."""
        return CreatorIdentity(
            manufacturer=self.manufacturer,
            product=self.product,
            serial_number=self.serial_number,
            software_version=self.software_version,
        )

    @property
    def is_supported(self) -> bool:
        """Return whether this profile has a complete creator identity."""
        return (
            self.identity_mode == "full"
            and self.serial_number is not None
            and self.software_version is not None
        )

    def to_storage(self) -> dict[str, Any]:
        """Serialize the full profile for HA local storage."""
        return {
            "profile_id": self.profile_id,
            "label": self.label,
            "manufacturer": self.manufacturer,
            "product": self.product,
            "serial_number": self.serial_number,
            "software_version": self.software_version,
            "source": self.source,
            "identity_mode": self.identity_mode,
        }

    def to_public(self, is_default: bool = False) -> dict[str, Any]:
        """Return UI-safe profile metadata."""
        return {
            "profile_id": self.profile_id,
            "label": self.label,
            "manufacturer": self.manufacturer,
            "product": self.product,
            "serial_number": mask_serial(self.serial_number),
            "software_version": format_software_version(self.software_version),
            "source": self.source,
            "identity_mode": self.identity_mode,
            "is_full_identity": self.is_supported,
            "is_supported": self.is_supported,
            "is_default": is_default,
        }

    @classmethod
    def from_storage(cls, data: dict[str, Any]) -> "DeviceProfile":
        """Deserialize one stored profile, including pre-release basic profiles."""
        serial_number = (
            int(data["serial_number"])
            if data.get("serial_number") is not None
            else None
        )
        return cls(
            profile_id=str(data["profile_id"]),
            label=str(data["label"]),
            manufacturer=int(data["manufacturer"]),
            product=int(data["product"]),
            serial_number=serial_number,
            software_version=(
                int(data["software_version"])
                if data.get("software_version") is not None
                else None
            ),
            source=str(data.get("source") or "reference"),
            identity_mode=str(
                data.get("identity_mode")
                or ("full" if serial_number is not None else "basic")
            ),
        )


def _profile_id(identity: CreatorIdentity) -> str:
    """Generate a stable id without exposing a physical device serial."""
    serial_token = identity.serial_number if identity.serial_number is not None else "basic"
    digest = sha256(
        f"{identity.manufacturer}:{identity.product}:{serial_token}".encode()
    ).hexdigest()[:12]
    return f"device_{identity.product}_{digest}"


class ProfileStore:
    """Manage creator profiles in Home Assistant's .storage directory."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store[dict[str, Any]] = Store(
            hass,
            STORAGE_VERSION,
            STORAGE_KEY,
        )
        self._legacy_store: Store[dict[str, Any]] = Store(
            hass,
            STORAGE_VERSION,
            LEGACY_STORAGE_KEY,
        )
        self._profiles: dict[str, DeviceProfile] = {}
        self._default_profile_id: Optional[str] = None
        self._loaded = False

    @property
    def default_profile_id(self) -> Optional[str]:
        return self._default_profile_id

    async def async_load(self) -> None:
        """Load saved profiles once."""
        if self._loaded:
            return
        data = await self._store.async_load()
        migrated_legacy = False
        if not data:
            legacy_data = await self._legacy_store.async_load()
            if legacy_data:
                data = legacy_data
                migrated_legacy = True
        data = data or {}
        for raw_profile in data.get("profiles", []):
            profile = DeviceProfile.from_storage(raw_profile)
            self._profiles[profile.profile_id] = profile
        default_profile_id = data.get("default_profile_id")
        if default_profile_id in self._profiles:
            self._default_profile_id = default_profile_id
        self._loaded = True
        if migrated_legacy:
            await self._async_save()

    async def _async_save(self) -> None:
        await self._store.async_save(
            {
                "profiles": [profile.to_storage() for profile in self._profiles.values()],
                "default_profile_id": self._default_profile_id,
            }
        )

    def get(self, profile_id: str) -> Optional[DeviceProfile]:
        return self._profiles.get(profile_id)

    def public_payload(self) -> dict[str, Any]:
        """Return all profiles in UI order."""
        profiles = list(self._profiles.values())
        profiles.sort(
            key=lambda profile: (
                profile.profile_id != self._default_profile_id,
                profile.label.lower(),
            )
        )
        return {
            "default_profile_id": self._default_profile_id,
            "profiles": [
                profile.to_public(profile.profile_id == self._default_profile_id)
                for profile in profiles
            ],
        }

    async def async_upsert(
        self,
        identity: CreatorIdentity,
        label: str,
        *,
        source: str = "reference",
        identity_mode: Optional[str] = None,
    ) -> DeviceProfile:
        """Add or update a complete creator profile."""
        mode = identity_mode or "full"
        if mode != "full":
            raise ValueError("Only full Garmin identity profiles are supported.")
        if identity.serial_number is None or identity.software_version is None:
            raise ValueError(
                "Full Garmin identity requires both serial number and firmware."
            )

        profile_id = _profile_id(identity)
        profile = DeviceProfile(
            profile_id=profile_id,
            label=label.strip() or identity.default_label,
            manufacturer=identity.manufacturer,
            product=identity.product,
            serial_number=identity.serial_number,
            software_version=identity.software_version,
            source=source,
            identity_mode="full",
        )
        self._profiles[profile_id] = profile

        # fēnix 7 Pro is the preferred default whenever it becomes available.
        if (
            self._default_profile_id is None
            or (identity.manufacturer, identity.product) == (1, 4375)
        ):
            self._default_profile_id = profile_id

        await self._async_save()
        return profile

    async def async_set_default(self, profile_id: str) -> bool:
        """Set the default target profile."""
        if profile_id not in self._profiles:
            return False
        self._default_profile_id = profile_id
        await self._async_save()
        return True

    async def async_delete(self, profile_id: str) -> bool:
        """Delete one locally stored creator profile."""
        if profile_id not in self._profiles:
            return False
        del self._profiles[profile_id]
        if self._default_profile_id == profile_id:
            self._default_profile_id = next(iter(self._profiles), None)
        await self._async_save()
        return True
