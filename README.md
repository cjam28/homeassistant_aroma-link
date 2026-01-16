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

- **Switch**: Control the power state of the diffuser (on/off)
- **Button**: Send immediate commands to the diffuser (Run and Save Settings buttons)
- **Number**: Set work duration and pause duration values
- **Sensors**:
  - Work Status (Off/Diffusing/Paused)
  - Work Remaining Time (seconds)
  - Pause Remaining Time (seconds)
  - On Count (total activations)
  - Pump Count (total diffusions)

## Workset Scheduling

The integration supports full workset scheduling with up to 5 time programs per day, similar to the Aroma-Link mobile app. Each program can have:
- Start and end times
- Work duration (seconds the diffuser runs)
- Pause duration (seconds between work cycles)
- Consistency level (A, B, or C)
- Enable/disable toggle

### Setting Up Workset Controls

**✨ Automatic Setup:** Helper entities are automatically created when you set up the integration! No manual configuration needed.

When you add the integration, it automatically creates:
- **Helper entities** for all 5 programs (input_boolean, input_datetime, input_number, input_select)
- **Day selector** helper (input_select) for choosing which day to load/save
- **Dashboard YAML** configuration stored in the integration config entry

The helper prefix is automatically generated from your device name (e.g., "Pool House" becomes `aromalink_pool_house`).

#### Manual Helper Creation (Optional)

If you prefer to create helpers manually, or if automatic creation didn't work, you can create them via the UI (Settings → Devices & Services → Helpers) or use the following YAML configuration in your `configuration.yaml`:

```yaml
# Example for a device named "Pool House"
input_boolean:
  aromalink_poolhouse_program_1_enabled:
    name: "Pool House Program 1 Enabled"
  aromalink_poolhouse_program_2_enabled:
    name: "Pool House Program 2 Enabled"
  aromalink_poolhouse_program_3_enabled:
    name: "Pool House Program 3 Enabled"
  aromalink_poolhouse_program_4_enabled:
    name: "Pool House Program 4 Enabled"
  aromalink_poolhouse_program_5_enabled:
    name: "Pool House Program 5 Enabled"

input_datetime:
  aromalink_poolhouse_program_1_start:
    name: "Pool House Program 1 Start"
    has_date: false
    has_time: true
  aromalink_poolhouse_program_1_end:
    name: "Pool House Program 1 End"
    has_date: false
    has_time: true
  aromalink_poolhouse_program_2_start:
    name: "Pool House Program 2 Start"
    has_date: false
    has_time: true
  aromalink_poolhouse_program_2_end:
    name: "Pool House Program 2 End"
    has_date: false
    has_time: true
  aromalink_poolhouse_program_3_start:
    name: "Pool House Program 3 Start"
    has_date: false
    has_time: true
  aromalink_poolhouse_program_3_end:
    name: "Pool House Program 3 End"
    has_date: false
    has_time: true
  aromalink_poolhouse_program_4_start:
    name: "Pool House Program 4 Start"
    has_date: false
    has_time: true
  aromalink_poolhouse_program_4_end:
    name: "Pool House Program 4 End"
    has_date: false
    has_time: true
  aromalink_poolhouse_program_5_start:
    name: "Pool House Program 5 Start"
    has_date: false
    has_time: true
  aromalink_poolhouse_program_5_end:
    name: "Pool House Program 5 End"
    has_date: false
    has_time: true

input_number:
  aromalink_poolhouse_program_1_work:
    name: "Pool House Program 1 Work (sec)"
    min: 5
    max: 900
    step: 1
    unit_of_measurement: "sec"
  aromalink_poolhouse_program_1_pause:
    name: "Pool House Program 1 Pause (sec)"
    min: 5
    max: 900
    step: 5
    unit_of_measurement: "sec"
  aromalink_poolhouse_program_2_work:
    name: "Pool House Program 2 Work (sec)"
    min: 5
    max: 900
    step: 1
    unit_of_measurement: "sec"
  aromalink_poolhouse_program_2_pause:
    name: "Pool House Program 2 Pause (sec)"
    min: 5
    max: 900
    step: 5
    unit_of_measurement: "sec"
  aromalink_poolhouse_program_3_work:
    name: "Pool House Program 3 Work (sec)"
    min: 5
    max: 900
    step: 1
    unit_of_measurement: "sec"
  aromalink_poolhouse_program_3_pause:
    name: "Pool House Program 3 Pause (sec)"
    min: 5
    max: 900
    step: 5
    unit_of_measurement: "sec"
  aromalink_poolhouse_program_4_work:
    name: "Pool House Program 4 Work (sec)"
    min: 5
    max: 900
    step: 1
    unit_of_measurement: "sec"
  aromalink_poolhouse_program_4_pause:
    name: "Pool House Program 4 Pause (sec)"
    min: 5
    max: 900
    step: 5
    unit_of_measurement: "sec"
  aromalink_poolhouse_program_5_work:
    name: "Pool House Program 5 Work (sec)"
    min: 5
    max: 900
    step: 1
    unit_of_measurement: "sec"
  aromalink_poolhouse_program_5_pause:
    name: "Pool House Program 5 Pause (sec)"
    min: 5
    max: 900
    step: 5
    unit_of_measurement: "sec"

input_select:
  aromalink_poolhouse_program_1_level:
    name: "Pool House Program 1 Level"
    options:
      - "A"
      - "B"
      - "C"
    initial: "A"
  aromalink_poolhouse_program_2_level:
    name: "Pool House Program 2 Level"
    options:
      - "A"
      - "B"
      - "C"
    initial: "A"
  aromalink_poolhouse_program_3_level:
    name: "Pool House Program 3 Level"
    options:
      - "A"
      - "B"
      - "C"
    initial: "A"
  aromalink_poolhouse_program_4_level:
    name: "Pool House Program 4 Level"
    options:
      - "A"
      - "B"
      - "C"
    initial: "A"
  aromalink_poolhouse_program_5_level:
    name: "Pool House Program 5 Level"
    options:
      - "A"
      - "B"
      - "C"
    initial: "A"
```

**Note:** The prefix is automatically generated from your device name (e.g., "Pool House" → `aromalink_pool_house`). You can also specify a custom prefix when calling the load/save services.

#### Step 2: Get Dashboard Configuration

The integration automatically generates a Lovelace dashboard configuration for each device. To retrieve it:

1. **Via Service:** Call `aroma_link_integration_test.get_dashboard_config` service
   - The YAML will be logged and stored in the integration config entry options
   - Check Settings → Devices & Services → Aroma-Link Integration (Test) → Options to view it

2. **Access from Config Entry:** The dashboard YAML is stored in the config entry options under `dashboard_yaml_{device_id}`

**Example Dashboard YAML:**

Here's the automatically generated Lovelace dashboard configuration using Mushroom cards:

```yaml
type: vertical-stack
cards:
  # Header
  - type: custom:mushroom-title-card
    title: Aroma-Link Workset Controls
    subtitle: Pool House

  # Day Selection
  - type: custom:mushroom-chips-card
    title: Select Days
    chips:
      - type: template
        entity: input_select.aromalink_poolhouse_selected_day
        icon: mdi:calendar
        content: "{{ states('input_select.aromalink_poolhouse_selected_day') }}"
  
  # Load/Save Buttons
  - type: horizontal-stack
    cards:
      - type: custom:mushroom-entity-card
        entity: button.load_workset
        tap_action:
          action: call-service
          service: aroma_link_integration.load_workset
          service_data:
            device_id: "419933"
            week_day: 0
            helper_prefix: "aromalink_poolhouse"
        icon: mdi:download
        name: Load from Device
      - type: custom:mushroom-entity-card
        entity: button.save_workset
        tap_action:
          action: call-service
          service: aroma_link_integration.save_workset
          service_data:
            device_id: "419933"
            week_days: [0, 1, 2, 3, 4, 5, 6]
            helper_prefix: "aromalink_poolhouse"
        icon: mdi:upload
        name: Save to Device

  # Program 1
  - type: custom:mushroom-title-card
    title: Program 1
  - type: grid
    square: false
    columns: 2
    cards:
      - type: custom:mushroom-entity-card
        entity: input_boolean.aromalink_poolhouse_program_1_enabled
        name: Enabled
      - type: custom:mushroom-entity-card
        entity: input_select.aromalink_poolhouse_program_1_level
        name: Level
      - type: custom:mushroom-entity-card
        entity: input_datetime.aromalink_poolhouse_program_1_start
        name: Start Time
      - type: custom:mushroom-entity-card
        entity: input_datetime.aromalink_poolhouse_program_1_end
        name: End Time
      - type: custom:mushroom-entity-card
        entity: input_number.aromalink_poolhouse_program_1_work
        name: Work (sec)
      - type: custom:mushroom-entity-card
        entity: input_number.aromalink_poolhouse_program_1_pause
        name: Pause (sec)

  # Program 2
  - type: custom:mushroom-title-card
    title: Program 2
  - type: grid
    square: false
    columns: 2
    cards:
      - type: custom:mushroom-entity-card
        entity: input_boolean.aromalink_poolhouse_program_2_enabled
        name: Enabled
      - type: custom:mushroom-entity-card
        entity: input_select.aromalink_poolhouse_program_2_level
        name: Level
      - type: custom:mushroom-entity-card
        entity: input_datetime.aromalink_poolhouse_program_2_start
        name: Start Time
      - type: custom:mushroom-entity-card
        entity: input_datetime.aromalink_poolhouse_program_2_end
        name: End Time
      - type: custom:mushroom-entity-card
        entity: input_number.aromalink_poolhouse_program_2_work
        name: Work (sec)
      - type: custom:mushroom-entity-card
        entity: input_number.aromalink_poolhouse_program_2_pause
        name: Pause (sec)

  # Programs 3-5 (similar structure)
  # ... repeat for programs 3, 4, and 5
```

#### Step 3: Using the Workset Controls

**Quick Start:**
1. After integration setup, helper entities are automatically available
2. Retrieve the dashboard YAML via the `get_dashboard_config` service or from config entry options
3. Copy the YAML into a new Lovelace card on your dashboard
4. Use the Load/Save buttons in the dashboard to manage schedules

**Detailed Usage:**

1. **Load Schedule**: Call `aroma_link_integration.load_workset` service to fetch the current schedule from your device and populate the helper entities.
2. **Edit Schedule**: Use the helper entities in your dashboard to modify the schedule (enable/disable programs, set times, durations, levels).
3. **Save Schedule**: Call `aroma_link_integration.save_workset` service to apply your changes to the device.

**Example Automation:**

```yaml
automation:
  - alias: "Load Aroma-Link Schedule on Startup"
    trigger:
      - platform: homeassistant
        event: start
    action:
      - service: aroma_link_integration.load_workset
        data:
          device_id: "419933"
          week_day: 0
          helper_prefix: "aromalink_poolhouse"
```

**Day Mapping:**
- 0 = Monday
- 1 = Tuesday
- 2 = Wednesday
- 3 = Thursday
- 4 = Friday
- 5 = Saturday
- 6 = Sunday

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
- **Important**: The integration polls the API every 1 minute to check for device state changes. This means any changes made outside of Home Assistant (e.g., via the Aroma-Link mobile app or website) will be reflected in Home Assistant within 1 minute

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
A: The integration polls the API every 1 minute, so changes made outside Home Assistant will be reflected within 1 minute. However, if you change work duration or pause duration in the app, you may need to update the Number entities in Home Assistant to match.

**Q: Can I set different schedules for different days of the week?**  
A: The API supports per-day scheduling (via the `week_days` parameter in `set_scheduler`), but the current implementation applies the same schedule to all specified days. Per-day scheduling could be added as a future enhancement.

## Version History

- **1.2.0** (This fork): Added full workset scheduling support
  - Added `fetch_workset_for_day()` and `set_workset()` methods for reading/writing complete schedules
  - Added `load_workset` and `save_workset` services for helper-based schedule management
  - Support for up to 5 time programs per day with start/end times, work/pause durations, and consistency levels
  - Multi-day schedule support (apply same schedule to multiple days)
  - Mushroom dashboard example and documentation
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
