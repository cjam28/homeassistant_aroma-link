"""The Aroma-Link integration."""
import logging
from datetime import timedelta

from .AromaLinkAuthCoordinator import AromaLinkAuthCoordinator
from .AromaLinkDeviceCoordinator import AromaLinkDeviceCoordinator

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers import entity_registry as er
import homeassistant.helpers.config_validation as cv
import voluptuous as vol

from .const import (
    DOMAIN,
    CONF_DEVICE_ID,
    SERVICE_SET_SCHEDULER,
    SERVICE_RUN_DIFFUSER,
    SERVICE_LOAD_WORKSET,
    SERVICE_SAVE_WORKSET,
    SERVICE_GET_DASHBOARD_CONFIG,
    ATTR_WORK_DURATION,
    ATTR_PAUSE_DURATION,
    ATTR_WEEK_DAYS,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["switch", "button", "number", "sensor"]

SET_SCHEDULER_SCHEMA = vol.Schema({
    vol.Required(ATTR_WORK_DURATION): vol.All(vol.Coerce(int), vol.Range(min=5, max=900)),
    vol.Optional(ATTR_PAUSE_DURATION): vol.All(vol.Coerce(int), vol.Range(min=5, max=900)),
    vol.Optional(ATTR_WEEK_DAYS): vol.All(
        cv.ensure_list, [vol.All(vol.Coerce(int), vol.Range(min=0, max=6))]
    ),
    vol.Optional("device_id"): cv.string,
})

RUN_DIFFUSER_SCHEMA = vol.Schema({
    vol.Optional(ATTR_WORK_DURATION): vol.All(vol.Coerce(int), vol.Range(min=5, max=900)),
    vol.Optional(ATTR_PAUSE_DURATION): vol.All(vol.Coerce(int), vol.Range(min=5, max=900)),
    vol.Optional("device_id"): cv.string,
})


async def _create_helper_entities(hass: HomeAssistant, device_name: str, entry: ConfigEntry):
    """Create helper entities for workset scheduling for a device."""
    # Generate prefix from device name
    helper_prefix = f"aromalink_{device_name.lower().replace(' ', '_').replace('-', '_')}"
    
    entity_registry = er.async_get(hass)
    created_count = [0]  # Use list to allow modification in nested function
    
    # Helper function to check if entity exists
    def entity_exists(domain: str, entity_id: str) -> bool:
        """Check if entity exists in registry or states."""
        full_entity_id = f"{domain}.{entity_id}"
        if full_entity_id in hass.states.async_entity_ids():
            return True
        if entity_registry.async_get_entity_id(domain, DOMAIN, f"{entry.entry_id}_{entity_id}"):
            return True
        return False
    
    # Helper function to create entity if it doesn't exist
    async def create_if_not_exists(domain: str, entity_id: str, service_data: dict):
        """Create helper entity if it doesn't exist."""
        full_entity_id = f"{domain}.{entity_id}"
        if not entity_exists(domain, entity_id):
            try:
                await hass.services.async_call(domain, "create", service_data)
                created_count[0] += 1
                _LOGGER.debug(f"Created {full_entity_id}")
                return True
            except Exception as e:
                _LOGGER.warning(f"Failed to create {full_entity_id} via service: {e}")
                # Fallback: try to create via direct state creation if service doesn't exist
                try:
                    if domain == "input_boolean":
                        hass.states.async_set(full_entity_id, "off", {"friendly_name": service_data.get("name", entity_id)})
                    elif domain == "input_datetime":
                        hass.states.async_set(full_entity_id, "2024-01-01 00:00:00", {"friendly_name": service_data.get("name", entity_id), "has_date": False, "has_time": True})
                    elif domain == "input_number":
                        hass.states.async_set(full_entity_id, service_data.get("initial", 10), {
                            "friendly_name": service_data.get("name", entity_id),
                            "min": service_data.get("min", 5),
                            "max": service_data.get("max", 900),
                            "step": service_data.get("step", 1),
                            "unit_of_measurement": service_data.get("unit_of_measurement", "sec")
                        })
                    elif domain == "input_select":
                        hass.states.async_set(full_entity_id, service_data.get("options", ["A"])[0], {
                            "friendly_name": service_data.get("name", entity_id),
                            "options": service_data.get("options", ["A", "B", "C"])
                        })
                    created_count[0] += 1
                    _LOGGER.debug(f"Created {full_entity_id} via direct state")
                    return True
                except Exception as e2:
                    _LOGGER.error(f"Failed to create {full_entity_id} via fallback: {e2}")
                    return False
        return False
    
    # Create helper entities for 5 programs
    for program_num in range(1, 6):
        # Input boolean for enabled
        await create_if_not_exists(
            "input_boolean",
            f"{helper_prefix}_program_{program_num}_enabled",
            {
                "name": f"{device_name} Program {program_num} Enabled",
            }
        )
        
        # Input datetime for start time
        await create_if_not_exists(
            "input_datetime",
            f"{helper_prefix}_program_{program_num}_start",
            {
                "name": f"{device_name} Program {program_num} Start Time",
                "has_date": False,
                "has_time": True,
            }
        )
        
        # Input datetime for end time
        await create_if_not_exists(
            "input_datetime",
            f"{helper_prefix}_program_{program_num}_end",
            {
                "name": f"{device_name} Program {program_num} End Time",
                "has_date": False,
                "has_time": True,
            }
        )
        
        # Input number for work duration
        await create_if_not_exists(
            "input_number",
            f"{helper_prefix}_program_{program_num}_work",
            {
                "name": f"{device_name} Program {program_num} Work (sec)",
                "min": 5,
                "max": 900,
                "step": 1,
                "initial": 10,
                "unit_of_measurement": "sec",
            }
        )
        
        # Input number for pause duration
        await create_if_not_exists(
            "input_number",
            f"{helper_prefix}_program_{program_num}_pause",
            {
                "name": f"{device_name} Program {program_num} Pause (sec)",
                "min": 5,
                "max": 900,
                "step": 5,
                "initial": 120,
                "unit_of_measurement": "sec",
            }
        )
        
        # Input select for consistency level
        await create_if_not_exists(
            "input_select",
            f"{helper_prefix}_program_{program_num}_level",
            {
                "name": f"{device_name} Program {program_num} Level",
                "options": ["A", "B", "C"],
                "initial": "A",
            }
        )
    
    if created_count[0] > 0:
        _LOGGER.info(f"Created {created_count[0]} helper entities for {device_name} (prefix: {helper_prefix})")
    else:
        _LOGGER.debug(f"Helper entities for {device_name} already exist (prefix: {helper_prefix})")
    
    return helper_prefix


def _generate_dashboard_yaml(device_name: str, device_id: str, helper_prefix: str) -> str:
    """Generate Lovelace dashboard YAML for workset controls."""
    # Sanitize device name for display
    display_name = device_name.replace('_', ' ').title()
    
    # Generate YAML for Mushroom dashboard
    yaml_content = f"""type: vertical-stack
cards:
  # Header
  - type: custom:mushroom-title-card
    title: Aroma-Link Workset Controls
    subtitle: {display_name}

  # Day Selection Helper
  - type: custom:mushroom-entity-card
    entity: input_select.{helper_prefix}_selected_day
    name: Selected Day
    icon: mdi:calendar
    secondary: |-
      {{% set day_num = states('input_select.{helper_prefix}_selected_day') | int %}}
      {{% set days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'] %}}
      {{{{ days[day_num] if day_num < 7 else 'Unknown' }}}}
    tap_action:
      action: none

  # Load/Save Buttons
  - type: horizontal-stack
    cards:
      - type: button
        name: Load from Device
        icon: mdi:download
        tap_action:
          action: call-service
          service: {DOMAIN}.load_workset
          service_data:
            device_id: "{device_id}"
            week_day: "{{{{ states('input_select.{helper_prefix}_selected_day') | int }}}}"
            helper_prefix: "{helper_prefix}"
      - type: button
        name: Save to Device
        icon: mdi:upload
        tap_action:
          action: call-service
          service: {DOMAIN}.save_workset
          service_data:
            device_id: "{device_id}"
            week_days: [0, 1, 2, 3, 4, 5, 6]
            helper_prefix: "{helper_prefix}"

"""
    
    # Generate cards for each program (1-5)
    for program_num in range(1, 6):
        yaml_content += f"""  # Program {program_num}
  - type: custom:mushroom-title-card
    title: Program {program_num}
  - type: grid
    square: false
    columns: 2
    cards:
      - type: custom:mushroom-entity-card
        entity: input_boolean.{helper_prefix}_program_{program_num}_enabled
        name: Enabled
        icon: mdi:toggle-switch
      - type: custom:mushroom-entity-card
        entity: input_select.{helper_prefix}_program_{program_num}_level
        name: Level
        icon: mdi:gauge
      - type: custom:mushroom-entity-card
        entity: input_datetime.{helper_prefix}_program_{program_num}_start
        name: Start Time
        icon: mdi:clock-start
      - type: custom:mushroom-entity-card
        entity: input_datetime.{helper_prefix}_program_{program_num}_end
        name: End Time
        icon: mdi:clock-end
      - type: custom:mushroom-entity-card
        entity: input_number.{helper_prefix}_program_{program_num}_work
        name: Work (sec)
        icon: mdi:spray
      - type: custom:mushroom-entity-card
        entity: input_number.{helper_prefix}_program_{program_num}_pause
        name: Pause (sec)
        icon: mdi:timer-outline

"""
    
    return yaml_content


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Aroma-Link component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Aroma-Link from a config entry."""
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    devices = entry.data.get("devices", [])

    if not devices and CONF_DEVICE_ID in entry.data:
        # Support for old configuration format with single device
        device_id = entry.data[CONF_DEVICE_ID]
        device_name = entry.data.get("device_name", "Unknown")
        devices = [{CONF_DEVICE_ID: device_id, "device_name": device_name}]

    if not devices:
        _LOGGER.error("No devices found in config entry")
        return False

    _LOGGER.info(
        f"Setting up Aroma-Link integration with {len(devices)} devices")

    # Create a single shared coordinator for authentication
    auth_coordinator = AromaLinkAuthCoordinator(
        hass,
        username=username,
        password=password
    )

    # Force first login and initialization
    await auth_coordinator.async_config_entry_first_refresh()

    # Store coordinators for each device
    device_coordinators = {}

    # Create coordinator for each device
    for device in devices:
        device_id = device[CONF_DEVICE_ID]
        device_name = device.get("device_name", f"Device {device_id}")

        _LOGGER.info(
            f"Initializing device coordinator for {device_name} ({device_id})")

        device_coordinator = AromaLinkDeviceCoordinator(
            hass,
            auth_coordinator=auth_coordinator,
            device_id=device_id,
            device_name=device_name
        )

        # Do first refresh for each device
        try:
            await device_coordinator.async_config_entry_first_refresh()
            device_coordinators[device_id] = device_coordinator
            
            # Auto-create helper entities for workset scheduling
            try:
                helper_prefix = await _create_helper_entities(hass, device_name, entry)
                _LOGGER.info(f"Helper entities created/verified for {device_name} (prefix: {helper_prefix})")
            except Exception as e:
                _LOGGER.warning(f"Failed to create helper entities for {device_name}: {e}")
        except Exception as e:
            _LOGGER.error(f"Error initializing device {device_id}: {e}")

    if not device_coordinators:
        _LOGGER.error("Failed to initialize any devices")
        return False

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "auth_coordinator": auth_coordinator,
        "device_coordinators": device_coordinators,
    }

    # Register services
    async def set_scheduler_service(call: ServiceCall):
        """Service to set diffuser scheduler."""
        device_id = call.data.get("device_id")
        work_duration = call.data.get(ATTR_WORK_DURATION)
        pause_duration = call.data.get(ATTR_PAUSE_DURATION)
        week_days = call.data.get(ATTR_WEEK_DAYS, [0, 1, 2, 3, 4, 5, 6])

        # If device_id specified, use that coordinator
        if device_id and device_id in device_coordinators:
            await device_coordinators[device_id].set_scheduler(work_duration, pause_duration, week_days)
        elif len(device_coordinators) == 1:
            # If only one device, use that
            first_device_id = list(device_coordinators.keys())[0]
            await device_coordinators[first_device_id].set_scheduler(work_duration, pause_duration, week_days)
        else:
            _LOGGER.error("Multiple devices available, must specify device_id")

    async def run_diffuser_service(call: ServiceCall):
        """Service to run diffuser for a specific time."""
        device_id = call.data.get("device_id")
        work_duration = call.data.get(ATTR_WORK_DURATION)
        pause_duration = call.data.get(ATTR_PAUSE_DURATION)

        # If device_id specified, use that coordinator
        if device_id and device_id in device_coordinators:
            await device_coordinators[device_id].run_diffuser(work_duration, pause_duration=pause_duration)
        elif len(device_coordinators) == 1:
            # If only one device, use that
            first_device_id = list(device_coordinators.keys())[0]
            await device_coordinators[first_device_id].run_diffuser(work_duration, pause_duration=pause_duration)
        else:
            _LOGGER.error("Multiple devices available, must specify device_id")

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_SCHEDULER,
        set_scheduler_service,
        schema=SET_SCHEDULER_SCHEMA
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_RUN_DIFFUSER,
        run_diffuser_service,
        schema=RUN_DIFFUSER_SCHEMA
    )

    async def load_workset_service(call: ServiceCall):
        """Service to load workset from device into helper entities."""
        device_id = call.data.get("device_id")
        week_day = call.data.get("week_day", 0)
        helper_prefix = call.data.get("helper_prefix")
        
        # Get coordinator
        coordinator = None
        if device_id and device_id in device_coordinators:
            coordinator = device_coordinators[device_id]
        elif len(device_coordinators) == 1:
            coordinator = list(device_coordinators.values())[0]
        else:
            _LOGGER.error("Multiple devices available, must specify device_id")
            return
        
        if not helper_prefix:
            # Use device name as prefix, sanitized
            helper_prefix = f"aromalink_{coordinator.device_name.lower().replace(' ', '_').replace('-', '_')}"
        
        # Fetch workset from device
        workset = await coordinator.fetch_workset_for_day(week_day)
        if not workset:
            _LOGGER.error(f"Failed to load workset for device {coordinator.device_id}")
            return
        
        # Update helper entities
        for i, program in enumerate(workset, 1):
            # Enabled toggle
            enabled_entity = f"input_boolean.{helper_prefix}_program_{i}_enabled"
            if enabled_entity in hass.states.async_entity_ids():
                hass.states.async_set(enabled_entity, "on" if program["enabled"] == 1 else "off")
            
            # Start time
            start_entity = f"input_datetime.{helper_prefix}_program_{i}_start"
            if start_entity in hass.states.async_entity_ids():
                start_time = program["start_time"]
                hass.states.async_set(start_entity, f"2024-01-01 {start_time}:00")
            
            # End time
            end_entity = f"input_datetime.{helper_prefix}_program_{i}_end"
            if end_entity in hass.states.async_entity_ids():
                end_time = program["end_time"]
                hass.states.async_set(end_entity, f"2024-01-01 {end_time}:00")
            
            # Work duration
            work_entity = f"input_number.{helper_prefix}_program_{i}_work"
            if work_entity in hass.states.async_entity_ids():
                hass.states.async_set(work_entity, program["work_sec"])
            
            # Pause duration
            pause_entity = f"input_number.{helper_prefix}_program_{i}_pause"
            if pause_entity in hass.states.async_entity_ids():
                hass.states.async_set(pause_entity, program["pause_sec"])
            
            # Level
            level_entity = f"input_select.{helper_prefix}_program_{i}_level"
            if level_entity in hass.states.async_entity_ids():
                level_map = {1: "A", 2: "B", 3: "C"}
                level = level_map.get(program["level"], "A")
                hass.states.async_set(level_entity, level)
        
        _LOGGER.info(f"Loaded workset for device {coordinator.device_id} day {week_day} into helpers with prefix {helper_prefix}")

    async def save_workset_service(call: ServiceCall):
        """Service to save workset from helper entities to device."""
        device_id = call.data.get("device_id")
        week_days = call.data.get("week_days", [0, 1, 2, 3, 4, 5, 6])
        helper_prefix = call.data.get("helper_prefix")
        
        # Get coordinator
        coordinator = None
        if device_id and device_id in device_coordinators:
            coordinator = device_coordinators[device_id]
        elif len(device_coordinators) == 1:
            coordinator = list(device_coordinators.values())[0]
        else:
            _LOGGER.error("Multiple devices available, must specify device_id")
            return
        
        if not helper_prefix:
            # Use device name as prefix, sanitized
            helper_prefix = f"aromalink_{coordinator.device_name.lower().replace(' ', '_').replace('-', '_')}"
        
        # Build workTimeList from helper entities
        work_time_list = []
        for i in range(1, 6):  # 5 programs
            # Get values from helpers
            enabled_entity = f"input_boolean.{helper_prefix}_program_{i}_enabled"
            start_entity = f"input_datetime.{helper_prefix}_program_{i}_start"
            end_entity = f"input_datetime.{helper_prefix}_program_{i}_end"
            work_entity = f"input_number.{helper_prefix}_program_{i}_work"
            pause_entity = f"input_number.{helper_prefix}_program_{i}_pause"
            level_entity = f"input_select.{helper_prefix}_program_{i}_level"
            
            enabled = 0
            if enabled_entity in hass.states.async_entity_ids():
                state = hass.states.get(enabled_entity)
                enabled = 1 if state and state.state == "on" else 0
            
            start_time = "00:00"
            if start_entity in hass.states.async_entity_ids():
                state = hass.states.get(start_entity)
                if state and state.state:
                    # Extract time from datetime string
                    try:
                        dt_str = state.state
                        if " " in dt_str:
                            start_time = dt_str.split(" ")[1][:5]  # Extract HH:MM
                    except:
                        pass
            
            end_time = "23:59"
            if end_entity in hass.states.async_entity_ids():
                state = hass.states.get(end_entity)
                if state and state.state:
                    try:
                        dt_str = state.state
                        if " " in dt_str:
                            end_time = dt_str.split(" ")[1][:5]  # Extract HH:MM
                    except:
                        pass
            
            work_duration = "10"
            if work_entity in hass.states.async_entity_ids():
                state = hass.states.get(work_entity)
                if state and state.state:
                    work_duration = str(int(float(state.state)))
            
            pause_duration = "120"
            if pause_entity in hass.states.async_entity_ids():
                state = hass.states.get(pause_entity)
                if state and state.state:
                    pause_duration = str(int(float(state.state)))
            
            level = "1"
            if level_entity in hass.states.async_entity_ids():
                state = hass.states.get(level_entity)
                if state and state.state:
                    level_map = {"A": "1", "B": "2", "C": "3"}
                    level = level_map.get(state.state, "1")
            
            work_time_list.append({
                "startTime": start_time,
                "endTime": end_time,
                "enabled": enabled,
                "consistenceLevel": level,
                "workDuration": work_duration,
                "pauseDuration": pause_duration
            })
        
        # Save to device
        result = await coordinator.set_workset(week_days, work_time_list)
        if result:
            _LOGGER.info(f"Saved workset for device {coordinator.device_id} to days {week_days}")
        else:
            _LOGGER.error(f"Failed to save workset for device {coordinator.device_id}")

    LOAD_WORKSET_SCHEMA = vol.Schema({
        vol.Optional("device_id"): cv.string,
        vol.Optional("week_day", default=0): vol.All(vol.Coerce(int), vol.Range(min=0, max=6)),
        vol.Optional("helper_prefix"): cv.string,
    })

    SAVE_WORKSET_SCHEMA = vol.Schema({
        vol.Optional("device_id"): cv.string,
        vol.Required("week_days"): vol.All(cv.ensure_list, [vol.All(vol.Coerce(int), vol.Range(min=0, max=6))]),
        vol.Optional("helper_prefix"): cv.string,
    })

    hass.services.async_register(
        DOMAIN,
        SERVICE_LOAD_WORKSET,
        load_workset_service,
        schema=LOAD_WORKSET_SCHEMA
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SAVE_WORKSET,
        save_workset_service,
        schema=SAVE_WORKSET_SCHEMA
    )

    # Service to get dashboard YAML configuration
    async def get_dashboard_config_service(call: ServiceCall):
        """Service to generate and return dashboard YAML configuration."""
        device_id = call.data.get("device_id")
        helper_prefix = call.data.get("helper_prefix")
        
        # Get coordinator
        coordinator = None
        device_name = "Device"
        if device_id and device_id in device_coordinators:
            coordinator = device_coordinators[device_id]
            device_name = coordinator.device_name
        elif len(device_coordinators) == 1:
            coordinator = list(device_coordinators.values())[0]
            device_name = coordinator.device_name
            device_id = coordinator.device_id
        else:
            _LOGGER.error("Multiple devices available, must specify device_id")
            return
        
        if not helper_prefix:
            helper_prefix = f"aromalink_{device_name.lower().replace(' ', '_').replace('-', '_')}"
        
        # Generate dashboard YAML
        yaml_config = _generate_dashboard_yaml(device_name, device_id, helper_prefix)
        
        # Store in config entry options for easy access
        hass.config_entries.async_update_entry(
            entry,
            options={**entry.options, f"dashboard_yaml_{device_id}": yaml_config}
        )
        
        _LOGGER.info(f"Dashboard YAML generated for {device_name}. Access via config entry options.")
        _LOGGER.info("Dashboard YAML:\n" + yaml_config)

    GET_DASHBOARD_CONFIG_SCHEMA = vol.Schema({
        vol.Optional("device_id"): cv.string,
        vol.Optional("helper_prefix"): cv.string,
    })

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_DASHBOARD_CONFIG,
        get_dashboard_config_service,
        schema=GET_DASHBOARD_CONFIG_SCHEMA
    )

    # Auto-generate dashboard config for each device and create day selector helper
    for device_id, coordinator in device_coordinators.items():
        helper_prefix = f"aromalink_{coordinator.device_name.lower().replace(' ', '_').replace('-', '_')}"
        
        # Create day selector helper if it doesn't exist
        day_selector_entity_id = f"input_select.{helper_prefix}_selected_day"
        if day_selector_entity_id not in hass.states.async_entity_ids():
            try:
                # Try to create via service first
                await hass.services.async_call(
                    "input_select",
                    "create",
                    {
                        "name": f"{coordinator.device_name} Selected Day",
                        "options": ["0", "1", "2", "3", "4", "5", "6"],
                        "initial": "0",
                    }
                )
            except Exception:
                # Fallback: create direct state (numbers 0-6 for Monday-Sunday)
                try:
                    hass.states.async_set(day_selector_entity_id, "0", {
                        "friendly_name": f"{coordinator.device_name} Selected Day",
                        "options": ["0", "1", "2", "3", "4", "5", "6"]
                    })
                    _LOGGER.debug(f"Created day selector helper: {day_selector_entity_id}")
                except Exception as e:
                    _LOGGER.warning(f"Failed to create day selector helper: {e}")
        
        # Generate and store dashboard YAML
        try:
            yaml_config = _generate_dashboard_yaml(coordinator.device_name, device_id, helper_prefix)
            hass.config_entries.async_update_entry(
                entry,
                options={**entry.options, f"dashboard_yaml_{device_id}": yaml_config}
            )
            _LOGGER.info(f"Dashboard YAML auto-generated for {coordinator.device_name}")
        except Exception as e:
            _LOGGER.warning(f"Failed to generate dashboard YAML for {coordinator.device_name}: {e}")

    # Use the new method
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True
