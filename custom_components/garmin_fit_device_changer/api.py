"""Authenticated HTTP API for FIT Device Patcher."""

from __future__ import annotations

import base64
import binascii
from http import HTTPStatus
from pathlib import Path
from typing import Any

from aiohttp import web

from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.core import HomeAssistant

from .catalog import (
    get_device_definition,
    parse_serial_number,
    parse_software_version,
    public_device_catalog,
)
from .const import DATA_STORE, DOMAIN, MAX_FIT_FILE_SIZE
from .patcher import CreatorIdentity, FitPatchError, extract_creator_identity, patch_fit_bytes
from .storage import DeviceProfile, ProfileStore


def _store(hass: HomeAssistant) -> ProfileStore:
    return hass.data[DOMAIN][DATA_STORE]


def _json_error(view: HomeAssistantView, message: str, status: HTTPStatus) -> web.Response:
    return view.json({"error": message}, status_code=status)


def _decode_fit(content_base64: Any) -> bytes:
    if not isinstance(content_base64, str) or not content_base64:
        raise FitPatchError("No FIT file content was supplied.")
    try:
        raw = base64.b64decode(content_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise FitPatchError("The uploaded file content is not valid base64.") from exc
    if len(raw) > MAX_FIT_FILE_SIZE:
        raise FitPatchError(
            f"FIT file is too large ({len(raw)} bytes); maximum is {MAX_FIT_FILE_SIZE} bytes."
        )
    return raw


def _safe_output_name(filename: Any, label: str) -> str:
    source_name = Path(str(filename or "activity.fit")).name
    stem = Path(source_name).stem or "activity"
    suffix = Path(source_name).suffix.lower()
    if suffix != ".fit":
        suffix = ".fit"
    device_slug = "".join(
        char.lower() if char.isalnum() else "_" for char in label
    ).strip("_")
    while "__" in device_slug:
        device_slug = device_slug.replace("__", "_")
    return f"{stem}_{device_slug or 'patched'}{suffix}"


def _public_payload(store: ProfileStore) -> dict[str, Any]:
    """Return profile state together with Garmin's built-in manual catalog."""
    return {
        **store.public_payload(),
        "device_catalog": public_device_catalog(),
    }


def _profile_response(store: ProfileStore, profile: DeviceProfile) -> dict[str, Any]:
    return {
        "profile": profile.to_public(profile.profile_id == store.default_profile_id),
        **_public_payload(store),
    }


class ProfilesView(HomeAssistantView):
    """List locally saved creator profiles and manual Garmin model data."""

    url = "/api/fit_device_patcher/profiles"
    name = "api:fit_device_patcher:profiles"
    requires_auth = True

    async def get(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app[KEY_HASS]
        return self.json(_public_payload(_store(hass)))


class ImportProfileView(HomeAssistantView):
    """Import creator identity from a genuine reference FIT file."""

    url = "/api/fit_device_patcher/profiles/import"
    name = "api:fit_device_patcher:profiles:import"
    requires_auth = True

    async def post(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app[KEY_HASS]
        try:
            payload = await request.json()
            raw = _decode_fit(payload.get("content_base64"))
            identity = await hass.async_add_executor_job(extract_creator_identity, raw)
            label = str(payload.get("label") or identity.default_label).strip()
            store = _store(hass)
            profile = await store.async_upsert(
                identity,
                label,
                source="reference",
                identity_mode="full",
            )
        except (FitPatchError, ValueError, TypeError) as exc:
            return _json_error(self, str(exc), HTTPStatus.BAD_REQUEST)

        return self.json(_profile_response(store, profile))


class ManualProfileView(HomeAssistantView):
    """Create a profile from Garmin model data, optionally with full identity."""

    url = "/api/fit_device_patcher/profiles/manual"
    name = "api:fit_device_patcher:profiles:manual"
    requires_auth = True

    async def post(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app[KEY_HASS]
        try:
            payload = await request.json()
            device_key = str(payload.get("device_key") or "").strip()
            definition = get_device_definition(device_key)
            if definition is None:
                raise ValueError("Unknown Garmin device model.")

            identity_mode = str(payload.get("identity_mode") or "basic").strip().lower()
            if identity_mode not in ("basic", "full"):
                raise ValueError("Identity mode must be 'basic' or 'full'.")

            serial_number = None
            software_version = None
            if identity_mode == "full":
                serial_number = parse_serial_number(payload.get("serial_number"))
                software_version = parse_software_version(payload.get("software_version"))

            identity = CreatorIdentity(
                manufacturer=definition.manufacturer,
                product=definition.product,
                serial_number=serial_number,
                software_version=software_version,
            )
            label = str(payload.get("label") or definition.label).strip()
            store = _store(hass)
            profile = await store.async_upsert(
                identity,
                label,
                source="manual",
                identity_mode=identity_mode,
            )
        except (ValueError, TypeError) as exc:
            return _json_error(self, str(exc), HTTPStatus.BAD_REQUEST)

        return self.json(_profile_response(store, profile))


class DefaultProfileView(HomeAssistantView):
    """Set the default creator profile."""

    url = "/api/fit_device_patcher/profiles/default"
    name = "api:fit_device_patcher:profiles:default"
    requires_auth = True

    async def post(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app[KEY_HASS]
        payload = await request.json()
        profile_id = str(payload.get("profile_id") or "")
        store = _store(hass)
        if not await store.async_set_default(profile_id):
            return _json_error(self, "Unknown profile.", HTTPStatus.NOT_FOUND)
        return self.json(_public_payload(store))


class DeleteProfileView(HomeAssistantView):
    """Delete a locally saved creator profile."""

    url = "/api/fit_device_patcher/profiles/delete"
    name = "api:fit_device_patcher:profiles:delete"
    requires_auth = True

    async def post(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app[KEY_HASS]
        payload = await request.json()
        profile_id = str(payload.get("profile_id") or "")
        store = _store(hass)
        if not await store.async_delete(profile_id):
            return _json_error(self, "Unknown profile.", HTTPStatus.NOT_FOUND)
        return self.json(_public_payload(store))


class PatchView(HomeAssistantView):
    """Patch one uploaded FIT file and return a new FIT file."""

    url = "/api/fit_device_patcher/patch"
    name = "api:fit_device_patcher:patch"
    requires_auth = True

    async def post(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app[KEY_HASS]
        try:
            payload = await request.json()
            profile_id = str(payload.get("profile_id") or "")
            store = _store(hass)
            profile = store.get(profile_id)
            if profile is None:
                return _json_error(self, "Unknown target profile.", HTTPStatus.NOT_FOUND)

            raw = _decode_fit(payload.get("content_base64"))
            patch_identity = profile.identity
            if profile.identity_mode == "basic":
                # Basic mode keeps the source FIT's physical creator identity
                # while replacing only Garmin manufacturer/product model data.
                source_identity = await hass.async_add_executor_job(
                    extract_creator_identity, raw
                )
                patch_identity = CreatorIdentity(
                    manufacturer=profile.manufacturer,
                    product=profile.product,
                    serial_number=source_identity.serial_number,
                    software_version=source_identity.software_version,
                )

            patched, changes = await hass.async_add_executor_job(
                patch_fit_bytes,
                raw,
                patch_identity,
            )
        except (FitPatchError, ValueError, TypeError) as exc:
            return _json_error(self, str(exc), HTTPStatus.BAD_REQUEST)

        return self.json(
            {
                "filename": _safe_output_name(payload.get("filename"), profile.label),
                "content_base64": base64.b64encode(patched).decode("ascii"),
                "profile": profile.to_public(
                    profile.profile_id == store.default_profile_id
                ),
                "changes": [change.as_public_dict() for change in changes],
                "verified": True,
            }
        )


def register_api_views(hass: HomeAssistant) -> None:
    """Register authenticated integration API endpoints."""
    hass.http.register_view(ProfilesView)
    hass.http.register_view(ImportProfileView)
    hass.http.register_view(ManualProfileView)
    hass.http.register_view(DefaultProfileView)
    hass.http.register_view(DeleteProfileView)
    hass.http.register_view(PatchView)
