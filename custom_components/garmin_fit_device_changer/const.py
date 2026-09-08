"""Constants for Garmin FIT Device Changer."""

DOMAIN = "garmin_fit_device_changer"
NAME = "Garmin FIT Device Changer"

DATA_STORE = "profile_store"
STORAGE_KEY = f"{DOMAIN}.profiles"
LEGACY_STORAGE_KEY = "fit_device_patcher.profiles"
STORAGE_VERSION = 1

# Base64 inflates payloads by ~33%; keep M1 comfortably below normal HA HTTP limits.
MAX_FIT_FILE_SIZE = 8 * 1024 * 1024

CARD_URL = "/garmin_fit_device_changer/garmin-fit-device-changer-card.js"
LEGACY_CARD_URL = "/fit_device_patcher/fit-device-patcher-card.js"
