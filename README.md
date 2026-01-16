# Aroma-Link Integration for Home Assistant (SSL Bypass Fork)

This custom component provides integration with Aroma-Link WiFi diffusers in Home Assistant.

> **⚠️ IMPORTANT: SSL Verification Disabled**  
> This fork disables SSL certificate verification to work around Aroma-Link's expired SSL certificates. While HTTPS encryption is still used, certificate validation is bypassed. This means the connection is encrypted but not authenticated, which could make you vulnerable to man-in-the-middle attacks. Use at your own risk.

> **Note:** The integration appears in Home Assistant as "Aroma-Link Integration" with the domain `aroma_link_integration`

## Features

- Control diffuser power state (on/off)
- Set diffuser work duration
- Set diffuser schedules
- **Full workset scheduling** - Up to 5 time programs per day with customizable start/end times, work/pause durations, and consistency levels
- Multi-day schedule support
- Run diffuser for specific durations
- Automatic device discovery
- Auto-detection of devices in your Aroma-Link account

## Installation

### HACS

1. Ensure HACS is installed in Home Assistant.

2. Open the HACS tab.

3. Click the **three dots** in the top right.

4. Click **Custom repositories**

5. Paste the github repository url `https://github.com/cjam28/ha_aromalink`

6. Select **integration** as the type then click **ADD**

7. Click on the freshly added repository in HACS.

8. Click **Download**

9. Restart Home Assistant

### Manual Installation

1. Copy the `aroma_link_integration` directory to your Home Assistant `custom_components` directory

   - The directory is typically located at `<config>/custom_components/`
   - If the `custom_components` directory doesn't exist, create it

   For example:

   ```bash
   cp -r aroma_link_integration <home_assistant_config>/custom_components/
   ```

2. Restart Home Assistant

### Configuration

1. In Home Assistant, go to **Settings** → **Devices and Services**
2. Click the **+ ADD INTEGRATION** button
3. Search for "Aroma-Link Integration" and select it
4. Enter your Aroma-Link username and password
5. The integration will automatically discover and add all devices in your account

## Services

The integration provides the following services:

### `aroma_link_integration.set_scheduler`

Set the scheduler for the diffuser.

Parameters:

- `work_duration`: Duration in seconds for the diffuser to work (required)
- `week_days`: Days of the week to apply the schedule (optional, defaults to all days)
- `device_id`: The ID of the device to control (optional, required if you have multiple devices)

### `aroma_link_integration.run_diffuser`

Run the diffuser for a specific time.

Parameters:

- `work_duration`: Work duration in seconds for the diffuser (required)
- `diffuse_time`: Total time in seconds for the diffuser to run (required)
- `device_id`: The ID of the device to control (optional, required if you have multiple devices)

### `aroma_link_integration.load_workset`

Load workset schedule from device into helper entities. This allows you to view and edit the current schedule configuration.

Parameters:

- `device_id`: The ID of the device (optional, required if you have multiple devices)
- `week_day`: Day of week to load (0=Monday, 1=Tuesday, ..., 6=Sunday). Defaults to 0.
- `helper_prefix`: Prefix for helper entity IDs (e.g., "aromalink_poolhouse"). If not provided, uses device name.

### `aroma_link_integration.save_workset`

Save workset schedule from helper entities to device. This applies your configured schedule to the device.

Parameters:

- `device_id`: The ID of the device (optional, required if you have multiple devices)
- `week_days`: List of weekdays to apply schedule to (0=Monday, 1=Tuesday, ..., 6=Sunday). Required.
- `helper_prefix`: Prefix for helper entity IDs (e.g., "aromalink_poolhouse"). If not provided, uses device name.

## Entities

The integration adds the following entities for each device:

- **Switches**:
  - Power: Control the power state of the diffuser (on/off)
  - Fan: Control the fan state (on/off)
- **Button**: Send immediate commands to the diffuser (Run and Save Settings buttons)
- **Number**: Set work duration and pause duration values
- **Sensors**:
  - Work Status (Off/Diffusing/Paused)
  - Work Remaining Time (seconds)
  - Pause Remaining Time (seconds)
  - On Count (total activations)
  - Pump Count (total diffusions)
- **Schedule Entities** (per-program editor):
  - Program Selector: Choose which program (1-5) to edit
  - Program Enabled: Enable/disable the selected program
  - Program Start Time: Start time for the program
  - Program End Time: End time for the program
  - Program Work Duration: Work duration in seconds (5-900)
  - Program Pause Duration: Pause duration in seconds (5-900)
  - Program Level: Consistency level (A/B/C)
  - Program Day Switches: 7 switches (one per day) to select which days to apply the program
  - Save Program: Button to save the edited program to selected days

## Workset Scheduling

The integration supports full workset scheduling with up to 5 time programs per day, similar to the Aroma-Link mobile app. Each program can have:
- Start and end times
- Work duration (seconds the diffuser runs)
- Pause duration (seconds between work cycles)
- Consistency level (A, B, or C)
- Enable/disable toggle

### Using Schedule Entities

**✨ Native Entities:** The integration automatically creates native Home Assistant entities for schedule editing. No manual setup required!

All schedule entities appear on your device page automatically. To edit a schedule:

1. **Select a Program**: Use the "Program" selector to choose which program (1-5) you want to edit
2. **Edit Program Settings**: Adjust the enabled state, start/end times, work/pause durations, and consistency level
3. **Select Days**: Toggle the day switches (Monday-Sunday) to choose which days this program should apply to
4. **Save**: Press the "Save Program" button to apply your changes

The integration automatically:
- Loads schedules on-demand when you view the device page
- Merges your edited program into the full 5-program set for each selected day
- Saves all changes to the device via the Aroma-Link API

**Note:** Schedules are cached locally and only refreshed when needed. Changes made outside Home Assistant (via the app) will be reflected when you refresh the schedule or view the device page.

### Legacy Services (Backward Compatibility)

The `load_workset` and `save_workset` services are still available for backward compatibility, but the native entities provide a better user experience. These services work with helper entities if you prefer that approach.

## How It Works

The integration works by:

1. Connecting to the Aroma-Link account using your credentials
2. Automatically discovering all devices in your account
3. Setting up all devices as separate entities in Home Assistant
4. Maintaining a shared authentication session for all devices

### Auto-Discovery Feature

The new auto-discovery feature eliminates the need to manually find your device ID. When setting up:

1. The integration authenticates with the Aroma-Link server
2. It requests a list of all devices registered to your account
3. All devices are automatically added to Home Assistant
4. Each device gets its own set of entities (switch, button, number controls)

### Technical Details

- The integration uses the same API as the official Aroma-Link website
- All communication is done over HTTPS (encrypted but SSL certificate verification is disabled)
- **SSL Verification Bypass**: This fork sets `VERIFY_SSL = False` to bypass certificate validation, allowing the integration to work even when Aroma-Link's SSL certificates are expired or invalid
- Session management is handled with cookies and automatic re-login when needed
- **Important**: The integration polls device state (power, fan, sensors) every 1 minute. Schedule data is loaded on-demand when viewing the device page or when explicitly refreshed. This means any changes made outside of Home Assistant (e.g., via the Aroma-Link mobile app or website) will be reflected in Home Assistant within 1 minute for device state, or immediately when you view/edit schedules.

## Troubleshooting

- If you have issues connecting, verify that your Aroma-Link credentials are correct
- Check the Home Assistant logs for debugging information
- Make sure your diffuser is connected to your WiFi network and accessible from the internet
- If automatic device discovery fails, you can still manually specify your device ID

## FAQ

**Q: Can I control multiple diffusers?**  
A: Yes! The integration now automatically discovers and adds all diffusers in your Aroma-Link account. Each diffuser gets its own set of entities in Home Assistant. When using service calls, you can specify which device to control using the `device_id` parameter, or leave it blank to use the first device if you only have one.

**Q: Why is my diffuser showing as offline?**  
A: Make sure your diffuser is connected to WiFi and properly set up in the Aroma-Link app.

**Q: How do I find my device ID?**  
A: You don't need to! The integration automatically discovers your devices and lets you select which one to use from a list.

**Q: What happens if I change settings in the Aroma-Link app?**  
A: The integration polls device state every 1 minute, so power/fan changes will be reflected within 1 minute. Schedule changes are loaded on-demand when you view the device page or refresh the schedule.

**Q: Can I set different schedules for different days of the week?**  
A: Yes! Each day (Monday-Sunday) has its own set of 5 programs. When you edit a program and save it, you can select which days to apply it to. The integration automatically merges your edited program into the full 5-program set for each selected day.

## Version History

- **1.3.0** (This fork): Native schedule entities and fan control
  - Replaced helper-based system with native Home Assistant entities
  - Added fan switch entity for fan on/off control
  - Per-program editor with program selector, editor fields, and day selection
  - On-demand schedule polling (no automatic polling)
  - Schedule caching for performance
  - All entities appear automatically on device page
- **1.2.0** (This fork): Added full workset scheduling support
  - Added `fetch_workset_for_day()` and `set_workset()` methods for reading/writing complete schedules
  - Added `load_workset` and `save_workset` services for helper-based schedule management
  - Support for up to 5 time programs per day with start/end times, work/pause durations, and consistency levels
  - Multi-day schedule support (apply same schedule to multiple days)
- **1.1.1** (This fork): Added SSL verification bypass to work around expired SSL certificates
  - Added `VERIFY_SSL = False` constant to disable SSL certificate verification
  - Updated all aiohttp requests to use `ssl=VERIFY_SSL` parameter
  - Allows integration to work even when Aroma-Link's SSL certificates are expired
- 1.1.0: Updated to support HACS integration (from [DalyMauldin's fork](https://github.com/DalyMauldin/ha_aromalink))
- 1.0.0: Initial release with automatic device discovery (from [Memberapple's original](https://github.com/Memberapple/ha_aromalink))

## Requirements

- A valid Aroma-Link account
- At least one registered diffuser device
- Home Assistant 2023.3.0 or newer
- An active internet connection

## License

This integration is provided as-is with no warranties.

## Credits

This is a fork of the Aroma-Link integration with SSL verification bypass added to work around expired SSL certificates.

**Fork Chain:**
- Original: [Memberapple/ha_aromalink](https://github.com/Memberapple/ha_aromalink)
- Intermediate: [DalyMauldin/ha_aromalink](https://github.com/DalyMauldin/ha_aromalink)
- This fork: [cjam28/ha_aromalink](https://github.com/cjam28/ha_aromalink)

Developed for Home Assistant community use.

## Links

- [Documentation](https://github.com/cjam28/ha_aromalink#readme)
- [Issue Tracker](https://github.com/cjam28/ha_aromalink/issues)
- [Original Repository](https://github.com/Memberapple/ha_aromalink)
- [DalyMauldin's Fork](https://github.com/DalyMauldin/ha_aromalink)
