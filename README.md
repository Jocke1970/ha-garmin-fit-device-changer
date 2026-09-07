# FIT Device Patcher for Home Assistant

A Home Assistant custom integration that changes the **creator Garmin device identity** in an existing FIT activity file without re-encoding the activity.

The patcher is intentionally surgical: it changes only creator identity fields that already exist in the target FIT file and recalculates the trailing FIT CRC. GPS, timestamps, laps, heart rate, power, cadence, sensor records, developer fields and the rest of the activity remain untouched.

> **Development status:** M1 / pre-release. Do not use on the only copy of an activity. The source file is never overwritten by the integration, but keep your original FIT files until the workflow has been verified in your own Garmin Connect account.

## Why reference FIT files?

Garmin Connect does not reliably identify a device from `manufacturer` + `product` alone. A working creator identity also includes the physical device serial number and, when present, the creator software version.

FIT Device Patcher therefore learns each target device from a **genuine FIT activity created by that device**. The reference FIT itself is not stored. Only its creator profile is saved locally in Home Assistant storage.

Creator-profile extraction has been tested during development with genuine FIT files from:

- Garmin Edge 1040 (`manufacturer=1`, `product=3843`)
- Garmin fēnix 7 Pro (`manufacturer=1`, `product=4375`)

The Edge 1040 patch path has also been verified by importing the patched activity into Garmin Connect and confirming that Connect identifies it as the real Edge 1040.

Other devices can be imported from a genuine reference FIT as well; unknown products simply get a generic label that can be overridden in the card.

## M1 features

- Config-flow installation in Home Assistant
- Local creator-profile storage; device serial numbers are never committed to this repository
- Import a device profile from a genuine reference FIT
- fēnix 7 Pro becomes the preferred default when available
- Dropdown for selecting the target device
- Patch `file_id` creator identity, `file_creator.software_version`, and creator `device_info` fields when those fields already exist
- Recalculate FIT CRC
- Byte-level safety verification that no unrelated bytes changed
- Never overwrite the source FIT file
- Swedish and English UI text
- Lovelace card served directly by the integration

## Development-branch installation

Until M1 has passed the Home Assistant test and is merged to `main`, install the feature branch manually.

1. Copy `custom_components/fit_device_patcher` from the `feature/m1-ha-integration` branch to:

   ```text
   /config/custom_components/fit_device_patcher
   ```

2. Restart Home Assistant.
3. Go to **Settings → Devices & services → Add integration** and add **FIT Device Patcher**.
4. Add this Lovelace resource as a JavaScript module:

   ```text
   /fit_device_patcher/fit-device-patcher-card.js
   ```

5. Add the card:

   ```yaml
   type: custom:fit-device-patcher-card
   title: FIT Device Patcher
   ```

## Workflow

### 1. Import device profiles

Use an untouched activity FIT created by the real Garmin device. For example, import one activity from the fēnix 7 Pro and one from the Edge 1040.

The integration stores only:

- manufacturer
- product
- serial number
- software version, when available
- your chosen display label

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
- required `file_id.manufacturer`, `file_id.product`, or `file_id.serial_number` fields are missing
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
