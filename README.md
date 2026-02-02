# Brunata Home Assistant Integration

A Home Assistant integration for Brunata meters, allowing you to monitor your consumption (water and energy) directly in your dashboard. 

NOT OFFICALLY SUPPORTED BY BRUNATA.

## Features
- Automatically discovers your Brunata meters.
- Supports water (m³, l) and energy (kWh, MWh) meters.
- Groups sensors under devices for easy management.
- Uses standard Home Assistant device classes and state classes (Long Term Statistics supported).
- Reliable data fetching using `DataUpdateCoordinator`.

## Installation

### Via HACS (Recommended)
1. Open **HACS** in your Home Assistant instance.
2. Click the three dots in the top right corner and select **Custom repositories**.
3. Paste the URL of this repository (`https://github.com/kimvonmullen/brunata_hacs`).
4. Select **Integration** as the category.
5. Click **Add**.
6. Find **Brunata** in HACS and click **Download**.
7. Restart Home Assistant.

**Note on Branding:**
If the logo/icon does not show up immediately:
- Clear your browser cache or use an incognito window.
- Ensure you have restarted Home Assistant after installation.
- HACS and Home Assistant can sometimes take some time to refresh brand assets.
- For the icon to appear in the official "Add Integration" list, it must be submitted to the [Home Assistant Brands repository](https://github.com/home-assistant/brands).

### Manual Installation
1. Download the `brunata` folder from `custom_components/`.
2. Copy it to your Home Assistant's `custom_components/` directory.
3. Restart Home Assistant.

## Configuration
1. Go to **Settings** -> **Devices & Services**.
2. Click **Add Integration**.
3. Search for **Brunata**.
4. Enter your Brunata email and password.

## Credits
Special thanks to the [brunata-api](https://pypi.org/project/brunata-api/) project for providing the Python library that makes this integration possible.

## License
MIT License. See LICENSE file for details.
