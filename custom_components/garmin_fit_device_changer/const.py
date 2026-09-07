"""Constants for FIT Device Patcher."""

DOMAIN = "fit_device_patcher"
NAME = "FIT Device Patcher"

DATA_STORE = "profile_store"
STORAGE_KEY = f"{DOMAIN}.profiles"
STORAGE_VERSION = 1

# Base64 inflates payloads by ~33%; keep M1 comfortably below normal HA HTTP limits.
MAX_FIT_FILE_SIZE = 8 * 1024 * 1024

CARD_URL = "/fit_device_patcher/fit-device-patcher-card.js"
