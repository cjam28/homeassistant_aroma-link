"""The Aroma-Link integration."""
import logging
from datetime import timedelta

from .AromaLinkAuthCoordinator import AromaLinkAuthCoordinator
from .AromaLinkDeviceCoordinator import AromaLinkDeviceCoordinator

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
import homeassistant.helpers.config_validation as cv
import voluptuous as vol

from .const import (
    DOMAIN,
    CONF_DEVICE_ID,
    SERVICE_SET_SCHEDULER,
    SERVICE_RUN_DIFFUSER,
    SERVICE_LOAD_WORKSET,
    SERVICE_SAVE_WORKSET,
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

    # Use the new method
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True
