"""Button platform for Aroma-Link."""
import logging
from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Aroma-Link button based on a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    device_coordinators = data["device_coordinators"]
    
    entities = []
    for device_id, coordinator in device_coordinators.items():
        device_info = coordinator.get_device_info()
        device_name = device_info["name"]
        entities.append(AromaLinkRunButton(coordinator, entry, device_id, device_name))
        entities.append(AromaLinkSaveSettingsButton(coordinator, entry, device_id, device_name))
        entities.append(AromaLinkSaveProgramButton(coordinator, entry, device_id, device_name))
    
    async_add_entities(entities)

class AromaLinkRunButton(ButtonEntity):
    """Representation of an Aroma-Link run button."""

    def __init__(self, coordinator, entry, device_id, device_name):
        """Initialize the button."""
        self._coordinator = coordinator
        self._entry = entry
        self._device_id = device_id
        self._name = f"{device_name} Run"
        self._unique_id = f"{entry.data['username']}_{device_id}_run"

    @property
    def name(self):
        """Return the name of the button."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique ID for this entity."""
        return self._unique_id

    @property
    def device_info(self):
        """Return device information about this Aroma-Link device."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry.data['username']}_{self._device_id}")},
            name=self._coordinator.device_name,
            manufacturer="Aroma-Link",
            model="Diffuser",
        )

    async def async_press(self):
        """Run the diffuser for a fixed time."""
        work_duration = self._coordinator.work_duration
        pause_duration = self._coordinator.pause_duration
        
        _LOGGER.info(f"Button pressed. Running diffuser with {work_duration}s work and {pause_duration}s pause settings")
        
        await self._coordinator.run_diffuser(work_duration, pause_duration=pause_duration)

class AromaLinkSaveSettingsButton(ButtonEntity):
    """Representation of an Aroma-Link save settings button."""

    def __init__(self, coordinator, entry, device_id, device_name):
        """Initialize the button."""
        self._coordinator = coordinator
        self._entry = entry
        self._device_id = device_id
        self._name = f"{device_name} Save Settings"
        self._unique_id = f"{entry.data['username']}_{device_id}_save_settings"
        self._attr_icon = "mdi:content-save"

    @property
    def name(self):
        """Return the name of the button."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique ID for this entity."""
        return self._unique_id

    @property
    def device_info(self):
        """Return device information about this Aroma-Link device."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry.data['username']}_{self._device_id}")},
            name=self._coordinator.device_name,
            manufacturer="Aroma-Link",
            model="Diffuser",
        )

    async def async_press(self):
        """Save the current work duration and pause duration settings."""
        work_duration = self._coordinator.work_duration
        pause_duration = self._coordinator.pause_duration
        
        _LOGGER.info(f"Saving settings: work_duration={work_duration}s, pause_duration={pause_duration}s")
        
        result = await self._coordinator.set_scheduler(work_duration, pause_duration)
        if result:
            _LOGGER.info(f"Settings saved successfully for {self._coordinator.device_name}")
        else:
            _LOGGER.error(f"Failed to save settings for {self._coordinator.device_name}")


class AromaLinkSaveProgramButton(CoordinatorEntity, ButtonEntity):
    """Save Program button."""

    def __init__(self, coordinator, entry, device_id, device_name):
        """Initialize."""
        super().__init__(coordinator)
        self._entry = entry
        self._device_id = device_id
        self._name = f"{device_name} Save Program"
        self._unique_id = f"{entry.data['username']}_{device_id}_save_program"

    @property
    def name(self):
        """Return the name of the button."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique ID for this entity."""
        return self._unique_id

    @property
    def device_info(self):
        """Return device information about this Aroma-Link device."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry.data['username']}_{self._device_id}")},
            name=self.coordinator.device_name,
            manufacturer="Aroma-Link",
            model="Diffuser",
        )

    async def async_press(self):
        """Save the program to selected days."""
        program_num = self.coordinator._current_program
        selected_days = self.coordinator._selected_days

        # For each selected day, fetch current schedule, replace program, save
        work_time_lists = {}
        for day in selected_days:
            # Fetch current schedule for this day
            schedule = await self.coordinator.async_refresh_schedule(day)
            if not schedule:
                _LOGGER.error("Failed to fetch schedule for day %s", day)
                continue

            # Replace the selected program in the schedule
            schedule[program_num - 1] = {
                "enabled": schedule[program_num - 1].get("enabled", 0),
                "start_time": schedule[program_num - 1].get("start_time", "00:00"),
                "end_time": schedule[program_num - 1].get("end_time", "23:59"),
                "work_sec": schedule[program_num - 1].get("work_sec", 10),
                "pause_sec": schedule[program_num - 1].get("pause_sec", 120),
                "level": schedule[program_num - 1].get("level", 1),
            }

            # Convert to API format
            work_time_list = []
            for prog in schedule:
                level_map = {1: "1", 2: "2", 3: "3"}
                work_time_list.append({
                    "startTime": prog.get("start_time", "00:00"),
                    "endTime": prog.get("end_time", "23:59"),
                    "enabled": prog.get("enabled", 0),
                    "consistenceLevel": level_map.get(prog.get("level", 1), "1"),
                    "workDuration": str(prog.get("work_sec", 10)),
                    "pauseDuration": str(prog.get("pause_sec", 120))
                })

            work_time_lists[day] = work_time_list

        # Save to all selected days at once
        if work_time_lists:
            first_day = selected_days[0]
            if first_day in work_time_lists:
                result = await self.coordinator.set_workset(selected_days, work_time_lists[first_day])
                if result:
                    _LOGGER.info("Saved program %s to days %s", program_num, selected_days)
                else:
                    _LOGGER.error("Failed to save program %s", program_num)
