#!/usr/bin/env python3
"""Generate the bundled Garmin device catalog from Garmin's FIT SDK."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import re
import sys
from urllib.request import Request, urlopen

SOURCE_URL = (
    "https://raw.githubusercontent.com/garmin/fit-java-sdk/main/"
    "src/main/java/com/garmin/fit/GarminProduct.java"
)
DEFAULT_OUTPUT = Path(
    "custom_components/garmin_fit_device_changer/generated_catalog.py"
)

DECL_RE = re.compile(r"public static final int ([A-Z0-9_]+)\s*=\s*(\d+)\s*;")
VERSION_RE = re.compile(r"Profile Version = ([^\r\n]+)")
TAG_RE = re.compile(r"Tag = ([^\r\n]+)")

REGION_SUFFIXES = {
    "ASIA": "Asia",
    "APAC": "APAC",
    "JAPAN": "Japan",
    "JPN": "Japan",
    "CHINA": "China",
    "CHN": "China",
    "KOREA": "Korea",
    "KOR": "Korea",
    "TAIWAN": "Taiwan",
    "TWN": "Taiwan",
    "SEA": "SE Asia",
    "RUSSIA": "Russia",
    "THAI": "Thailand",
    "HEBREW": "Hebrew",
    "WW": "Worldwide",
}

EXCLUDED_EXACT = {
    "EDGE_REMOTE",
    "DESCENT_T1",
    "DESCENT_T2",
}


def fetch_source(url: str = SOURCE_URL) -> str:
    """Fetch GarminProduct.java for development-time catalog generation."""
    request = Request(url, headers={"User-Agent": "ha-garmin-fit-device-changer-catalog"})
    with urlopen(request, timeout=30) as response:  # noqa: S310 - fixed trusted URL by default
        return response.read().decode("utf-8")


def parse_metadata(source: str) -> tuple[str, str]:
    """Return Garmin FIT profile version and upstream tag."""
    version_match = VERSION_RE.search(source)
    tag_match = TAG_RE.search(source)
    if not version_match or not tag_match:
        raise ValueError("Could not parse Garmin FIT profile version/tag.")
    return version_match.group(1).strip(), tag_match.group(1).strip()


def parse_products(source: str) -> list[tuple[str, int]]:
    """Parse numeric GarminProduct enum declarations in upstream order."""
    products = [(name, int(product)) for name, product in DECL_RE.findall(source)]
    if len(products) < 100:
        raise ValueError(
            f"Parsed only {len(products)} Garmin products; upstream format may have changed."
        )
    if len({name for name, _ in products}) != len(products):
        raise ValueError("Duplicate GarminProduct names found.")
    return products


def is_supported_device(name: str) -> bool:
    """Return whether an SDK product belongs in the activity-device catalog."""
    if name in EXCLUDED_EXACT or "SINGLE_BYTE_PRODUCT_ID" in name:
        return False

    if name.startswith("EDGE"):
        return True
    if re.match(r"^FR\d", name):
        return True

    prefixes = (
        "FENIX",
        "EPIX",
        "VIVOACTIVE",
        "VIVO_ACTIVE",
        "VENU",
        "VENUSQ",
        "INSTINCT",
        "ENDURO",
        "MARQ",
        "TACTIX",
        "DESCENT",
        "D2",
        "LILY",
        "SWIM",
        "VIVO_MOVE",
        "VIVOMOVE",
        "LEGACY_",
    )
    if name.startswith(prefixes):
        return True

    # Approach S-series are wrist watches. Other Approach products are handheld,
    # rangefinder or accessory devices and are intentionally excluded.
    if name.startswith("APPROACH_S") or name.startswith("APPROACHS"):
        return True

    # Current SDK watch products with names outside the long-lived families.
    return name in {"BOUNCE2", "APPROACH_J1"}


def split_region(name: str) -> tuple[str, str | None]:
    """Split a known regional suffix from an SDK enum name."""
    for suffix, label in REGION_SUFFIXES.items():
        token = f"_{suffix}"
        if name.endswith(token):
            return name[: -len(token)], label
    return name, None


def words(text: str) -> str:
    """Convert SDK token text into a compact human-readable suffix."""
    replacements = {
        "MUSIC": "Music",
        "SOLAR": "Solar",
        "SPORT": "Sport",
        "SMALL": "Small",
        "LARGE": "Large",
        "PRO": "Pro",
        "PLUS": "Plus",
        "AMOLED": "AMOLED",
        "LTE": "LTE",
        "CROSSOVER": "Crossover",
        "ESPORTS": "Esports",
        "CHRONOS": "Chronos",
        "TITANIUM": "Titanium",
        "PREMIUM": "Premium",
        "ATHLETE": "Athlete",
        "DRIVER": "Driver",
        "AVIATOR": "Aviator",
        "CAPTAIN": "Captain",
        "COMMANDER": "Commander",
        "EXPEDITION": "Expedition",
        "ADVENTURER": "Adventurer",
        "GOLFER": "Golfer",
        "BRAVO": "Bravo",
        "CHARLIE": "Charlie",
        "MACH1": "Mach 1",
        "MACH2": "Mach 2",
        "AIR": "Air",
        "EXPLORE": "Explore",
        "TOURING": "Touring",
        "MTB": "MTB",
        "DAIMLER": "Daimler",
        "HR": "HR",
        "GPS": "GPS",
        "OLED": "OLED",
        "TREND": "Trend",
    }
    text = text.replace("NO_WIFI", "NOWIFI")
    tokens = [token for token in text.strip("_").split("_") if token]
    out: list[str] = []
    for token in tokens:
        if token == "NOWIFI":
            out.append("No Wi-Fi")
            continue
        if token in replacements:
            out.append(replacements[token])
            continue
        if re.fullmatch(r"\d+MM", token):
            out.append(token.lower())
            continue
        token = re.sub(r"(?<=[A-Za-z])(?=\d)", " ", token)
        token = re.sub(r"(?<=\d)(?=[A-Za-z])", "", token)
        out.append(token)
    return " ".join(out)


def label_for(name: str) -> str:
    """Create a user-facing Garmin model label from an SDK enum name."""
    base, region = split_region(name)

    if base.startswith("EDGE"):
        suffix = base[4:].lstrip("_")
        label = f"Garmin Edge {words(suffix)}"
    elif re.match(r"^FR\d", base):
        suffix = base[2:]
        suffix = re.sub(r"^(\d+)M$", r"\1_MUSIC", suffix)
        label = f"Garmin Forerunner {words(suffix)}"
    elif base.startswith("FENIX"):
        label = f"Garmin fēnix {words(base[5:])}"
    elif base.startswith("EPIX"):
        label = f"Garmin epix {words(base[4:])}"
    elif base.startswith("VIVOACTIVE"):
        label = f"Garmin vívoactive {words(base[10:])}"
    elif base.startswith("VIVO_ACTIVE"):
        label = f"Garmin vívoactive {words(base[11:])}"
    elif base.startswith("VENUSQ"):
        label = f"Garmin Venu Sq {words(base[6:])}"
    elif base.startswith("VENU"):
        label = f"Garmin Venu {words(base[4:])}"
    elif base.startswith("INSTINCT"):
        label = f"Garmin Instinct {words(base[8:])}"
    elif base.startswith("ENDURO"):
        label = f"Garmin Enduro {words(base[6:])}"
    elif base.startswith("MARQ"):
        label = f"Garmin MARQ {words(base[4:])}"
    elif base.startswith("TACTIX"):
        label = f"Garmin tactix {words(base[6:])}"
    elif base.startswith("DESCENT"):
        label = f"Garmin Descent {words(base[7:])}"
    elif base.startswith("D2"):
        label = f"Garmin D2 {words(base[2:])}"
    elif base.startswith("LILY"):
        label = f"Garmin Lily {words(base[4:])}"
    elif base.startswith("SWIM"):
        label = f"Garmin Swim {words(base[4:])}"
    elif base.startswith("VIVO_MOVE"):
        label = f"Garmin vívomove {words(base[9:])}"
    elif base.startswith("VIVOMOVE"):
        label = f"Garmin vívomove {words(base[8:])}"
    elif base.startswith("LEGACY_"):
        label = f"Garmin Legacy {words(base[7:])}"
    elif base.startswith("APPROACH_S"):
        label = f"Garmin Approach S{words(base[10:])}"
    elif base.startswith("APPROACHS"):
        label = f"Garmin Approach S{words(base[9:])}"
    elif base == "APPROACH_J1":
        label = "Garmin Approach J1"
    elif base == "BOUNCE2":
        label = "Garmin Bounce 2"
    else:
        raise ValueError(f"No label rule for supported Garmin product {name}.")

    label = re.sub(r"\s+", " ", label).strip()
    if region:
        label += f" ({region})"
    return label


def key_for(name: str) -> str:
    """Create a stable readable catalog key from the SDK enum name."""
    base = name.lower()
    base = re.sub(r"^fr(?=\d)", "forerunner_", base)
    base = re.sub(r"^edge(?=\d)", "edge_", base)
    base = re.sub(r"^fenix(?=\d)", "fenix_", base)
    base = re.sub(r"^epix(?=\d)", "epix_", base)
    base = re.sub(r"^vivoactive(?=\d)", "vivoactive_", base)
    base = re.sub(r"^venusq(?=\d)", "venu_sq_", base)
    base = re.sub(r"^venu(?=\d)", "venu_", base)
    base = re.sub(r"^instinct(?=\d)", "instinct_", base)
    base = re.sub(r"^enduro(?=\d)", "enduro_", base)
    base = re.sub(r"^lily(?=\d)", "lily_", base)
    base = re.sub(r"^swim(?=\d)", "swim_", base)
    base = re.sub(r"^tactix(?=\d)", "tactix_", base)
    base = re.sub(r"^approachs(?=\d)", "approach_s", base)
    base = re.sub(r"__+", "_", base)
    return base.strip("_")


def build_rows(products: list[tuple[str, int]]) -> list[tuple[str, str, int, str]]:
    """Filter and normalize supported activity devices."""
    rows: list[tuple[str, str, int, str]] = []
    seen_keys: set[str] = set()
    seen_products: set[int] = set()
    for name, product in products:
        if not is_supported_device(name):
            continue
        if not 0 <= product <= 0xFFFF:
            raise ValueError(f"Product {name}={product} is outside FIT uint16 range.")
        key = key_for(name)
        if key in seen_keys:
            raise ValueError(f"Duplicate generated key: {key}")
        if product in seen_products:
            raise ValueError(f"Duplicate supported Product ID: {product}")
        rows.append((key, label_for(name), product, name))
        seen_keys.add(key)
        seen_products.add(product)
    if len(rows) < 100:
        raise ValueError(f"Generated only {len(rows)} supported devices; filter looks too narrow.")
    return rows


def render_catalog(
    version: str,
    tag: str,
    generated_at: str,
    rows: list[tuple[str, str, int, str]],
) -> str:
    """Render the generated Python data module."""
    lines = [
        '"""Auto-generated Garmin activity-device catalog. Do not edit manually."""',
        "",
        "# Source: Garmin FIT SDK GarminProduct.java",
        f"GARMIN_FIT_PROFILE_VERSION = {version!r}",
        f"GARMIN_FIT_PROFILE_TAG = {tag!r}",
        f"GARMIN_CATALOG_GENERATED_AT = {generated_at!r}",
        "",
        "# (key, display label, FIT Product ID, upstream GarminProduct enum name)",
        "GENERATED_DEVICE_CATALOG = (",
    ]
    for row in rows:
        lines.append(f"    {row!r},")
    lines.extend([")", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-file",
        type=Path,
        help="Use a local GarminProduct.java instead of downloading.",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--generated-at", help="Override generated snapshot date (YYYY-MM-DD).")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if the existing output differs from current SDK data.",
    )
    args = parser.parse_args()

    source = (
        args.source_file.read_text(encoding="utf-8")
        if args.source_file
        else fetch_source()
    )
    version, tag = parse_metadata(source)
    rows = build_rows(parse_products(source))

    generated_at = args.generated_at or datetime.now(timezone.utc).date().isoformat()
    if args.check and args.output.exists():
        existing = args.output.read_text(encoding="utf-8")
        date_match = re.search(
            r"GARMIN_CATALOG_GENERATED_AT = ['\"]([^'\"]+)", existing
        )
        if date_match:
            generated_at = date_match.group(1)

    rendered = render_catalog(version, tag, generated_at, rows)
    if args.check:
        if not args.output.exists() or args.output.read_text(encoding="utf-8") != rendered:
            print("Generated Garmin catalog is out of date.", file=sys.stderr)
            return 1
        print(f"Garmin catalog is current: {len(rows)} devices, FIT SDK {version}.")
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(f"Wrote {len(rows)} devices from FIT SDK {version} to {args.output}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
