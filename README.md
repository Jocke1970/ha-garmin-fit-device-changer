# Garmin FIT Device Changer for Home Assistant

A Home Assistant custom integration that changes the **creator Garmin device identity** in an existing FIT activity file without re-encoding the activity.

The patcher is intentionally surgical: it changes only creator identity fields that already exist in the target FIT file and recalculates the trailing FIT CRC. GPS, timestamps, laps, heart rate, power, cadence, sensor records, developer fields and the rest of the activity remain untouched.

> **Development status:** M1 / pre-release. Do not use on the only copy of an activity. The source file is never overwritten by the integration, but keep your original FIT files until the workflow has been verified in your own Garmin Connect account.

## Device profiles

Garmin Connect does not reliably identify a physical device from `manufacturer` + `product` alone. The most reliable creator identity also includes the device serial number and creator software version.

Garmin FIT Device Changer supports two ways to create a target profile:

1. **Reference FIT (recommended):** import a genuine activity created by the device. The FIT itself is not stored; only its creator profile is saved locally in Home Assistant.
2. **Manual profile:** choose a Garmin model from the built-in Garmin FIT product catalog, then choose either:
   - **Full identity** — manufacturer + product + serial number + firmware version. This matches the creator-identity method verified against Garmin Connect.
   - **Basic Garmin data** — manufacturer + product only. The source FIT serial/software are left unchanged. This is useful when no reference activity or device details are available, but Garmin Connect may not associate the activity with the physical device.

Creator-profile extraction has been tested during development with genuine FIT files from:

- Garmin Edge 1040 (`manufacturer=1`, `product=3843`)
- Garmin fēnix 7 Pro (`manufacturer=1`, `product=4375`)

The Edge 1040 patch path has also been verified by importing the patched activity into Garmin Connect and confirming that Connect identifies it as the real Edge 1040.

Other devices can be imported from a genuine reference FIT as well; unknown products simply get a generic label that can be overridden in the card.

## M1 features

- Config-flow installation in Home Assistant
- Local creator-profile storage; device serial numbers are never committed to this repository
- Import a device profile from a genuine reference FIT
- Create a manual profile from built-in Garmin model/Product ID data
- Choose full manual identity (serial + firmware) or basic Garmin model data only
- fēnix 7 Pro becomes the preferred default when available
- Dropdown for selecting the target device
- Patch `file_id` creator identity, `file_creator.software_version`, and creator `device_info` fields when those fields already exist
- Recalculate FIT CRC
- Byte-level safety verification that no unrelated bytes changed
- Never overwrite the source FIT file
- Swedish and English UI text
- Lovelace card served directly by the integration

### Upgrading from the pre-release `fit_device_patcher` test build

The integration domain was renamed before `v0.1.0` from `fit_device_patcher` to `garmin_fit_device_changer`. Remove the old custom-component folder/config entry and install the new one. Existing locally saved device profiles are automatically migrated from the old `.storage/fit_device_patcher.profiles` store when the new integration starts. The old Lovelace resource URL/card type is temporarily accepted as a compatibility alias during M1 testing.

## Development-branch installation

Until M1 has passed the Home Assistant test and is merged to `main`, install the feature branch manually.

1. Copy `custom_components/garmin_fit_device_changer` from the `feature/m1-ha-integration` branch to:

   ```text
   /config/custom_components/garmin_fit_device_changer
   ```

2. Restart Home Assistant.
3. Go to **Settings → Devices & services → Add integration** and add **Garmin FIT Device Changer**.
4. Add this Lovelace resource as a JavaScript module:

   ```text
   /garmin_fit_device_changer/garmin-fit-device-changer-card.js
   ```

5. Add the card:

   ```yaml
   type: custom:garmin-fit-device-changer-card
   title: Garmin FIT Device Changer
   ```

## Workflow

### 1. Create device profiles

Prefer an untouched activity FIT created by the real Garmin device. For example, import one activity from the fēnix 7 Pro and one from the Edge 1040.

If no reference FIT is available, use **Add device manually**. Pick the Garmin model and choose either full identity or basic data.

The integration stores only the selected profile data:

- manufacturer
- product
- serial number, for full profiles
- software version, for full profiles
- profile source/mode and your chosen display label

The initial built-in catalog is curated from Garmin's FIT SDK and includes Edge 1040/1050, fēnix 7S/7/7X Pro, Forerunner 965 and Forerunner 970.

### 2. Patch an activity

1. Choose the target Garmin device in the dropdown.
2. Choose the FIT file to patch.
3. Press **Patch FIT**.
4. Review the creator fields that changed.
5. Download the newly generated FIT file.

The original upload is never written back or replaced.

## Safety model

M1 refuses to patch when:

- the FIT header or file CRC is invalid
- the file is chained / contains extra FIT data after its CRC
- compressed-timestamp FIT records are present (not supported safely in M1)
- required `file_id.manufacturer` or `file_id.product` fields are missing
- `file_id.serial_number` is missing when a full-identity profile needs to patch it
- an expected creator field has an unsupported byte size
- byte-level verification finds any change outside the intended creator fields and trailing CRC

No messages are inserted or removed in M1.

## Privacy

Physical Garmin serial numbers are stored in Home Assistant's local `.storage` data for this integration. They are not placed in the repository, frontend source, or logs by design. The UI masks serial numbers except for their final four digits.

## Development flow

Development uses feature branches and pull requests:

```text
feature/... → tests → pull request → main → release tag
```

The first public release will be tagged `v0.1.0` only after the integration has been tested in Home Assistant and a patched FIT has successfully imported into Garmin Connect.

## License

MIT
