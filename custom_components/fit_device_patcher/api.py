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

from .const import DATA_STORE, DOMAIN, MAX_FIT_FILE_SIZE
from .patcher import FitPatchError, extract_creator_identity, patch_fit_bytes
from .storage import ProfileStore


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


class ProfilesView(HomeAssistantView):
    """List locally saved creator profiles."""

    url = "/api/fit_device_patcher/profiles"
    name = "api:fit_device_patcher:profiles"
    requires_auth = True

    async def get(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app[KEY_HASS]
        return self.json(_store(hass).public_payload())


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
            profile = await _store(hass).async_upsert(identity, label)
        except (FitPatchError, ValueError, TypeError) as exc:
            return _json_error(self, str(exc), HTTPStatus.BAD_REQUEST)

        return self.json(
            {
                "profile": profile.to_public(
                    profile.profile_id == _store(hass).default_profile_id
                ),
                **_store(hass).public_payload(),
            }
        )


class DefaultProfileView(HomeAssistantView):
    """Set the default creator profile."""

    url = "/api/fit_device_patcher/profiles/default"
    name = "api:fit_device_patcher:profiles:default"
    requires_auth = True

    async def post(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app[KEY_HASS]
        payload = await request.json()
        profile_id = str(payload.get("profile_id") or "")
        if not await _store(hass).async_set_default(profile_id):
            return _json_error(self, "Unknown profile.", HTTPStatus.NOT_FOUND)
        return self.json(_store(hass).public_payload())


class DeleteProfileView(HomeAssistantView):
    """Delete a locally saved creator profile."""

    url = "/api/fit_device_patcher/profiles/delete"
    name = "api:fit_device_patcher:profiles:delete"
    requires_auth = True

    async def post(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app[KEY_HASS]
        payload = await request.json()
        profile_id = str(payload.get("profile_id") or "")
        if not await _store(hass).async_delete(profile_id):
            return _json_error(self, "Unknown profile.", HTTPStatus.NOT_FOUND)
        return self.json(_store(hass).public_payload())


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
            profile = _store(hass).get(profile_id)
            if profile is None:
                return _json_error(self, "Unknown target profile.", HTTPStatus.NOT_FOUND)

            raw = _decode_fit(payload.get("content_base64"))
            patched, changes = await hass.async_add_executor_job(
                patch_fit_bytes,
                raw,
                profile.identity,
            )
        except (FitPatchError, ValueError, TypeError) as exc:
            return _json_error(self, str(exc), HTTPStatus.BAD_REQUEST)

        return self.json(
            {
                "filename": _safe_output_name(payload.get("filename"), profile.label),
                "content_base64": base64.b64encode(patched).decode("ascii"),
                "profile": profile.to_public(
                    profile.profile_id == _store(hass).default_profile_id
                ),
                "changes": [change.as_public_dict() for change in changes],
                "verified": True,
            }
        )


def register_api_views(hass: HomeAssistant) -> None:
    """Register authenticated integration API endpoints."""
    hass.http.register_view(ProfilesView)
    hass.http.register_view(ImportProfileView)
    hass.http.register_view(DefaultProfileView)
    hass.http.register_view(DeleteProfileView)
    hass.http.register_view(PatchView)
