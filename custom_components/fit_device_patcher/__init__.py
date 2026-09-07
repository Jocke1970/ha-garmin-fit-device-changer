"""FIT Device Patcher integration for Home Assistant."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .api import register_api_views
from .const import CARD_URL, DATA_STORE, DOMAIN
from .storage import ProfileStore


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the integration-wide API, storage and card resource."""
    hass.data.setdefault(DOMAIN, {})

    store = ProfileStore(hass)
    await store.async_load()
    hass.data[DOMAIN][DATA_STORE] = store

    register_api_views(hass)

    card_path = Path(__file__).parent / "www" / "fit-device-patcher-card.js"
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(card_path), cache_headers=False)]
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up FIT Device Patcher from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = True
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the config entry."""
    hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return True
