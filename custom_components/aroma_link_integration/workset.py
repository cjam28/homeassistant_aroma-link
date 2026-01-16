"""Workset platform for Aroma-Link."""
import logging

from homeassistant.components.select import SelectEntity
from homeassistant.components.switch import SwitchEntity
from homeassistant.components.number import NumberEntity
from homeassistant.components.text import TextEntity
from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.core import callback
import re

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Aroma-Link workset entities based on a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    device_coordinators = data["device_coordinators"]
    _LOGGER.info("Setting up workset entities for %s devices", len(device_coordinators))

    entities = []
    for device_id, coordinator in device_coordinators.items():
        device_info = coordinator.get_device_info()
        device_name = device_info["name"]
        _LOGGER.info("Creating workset entities for %s (%s)", device_name, device_id)

        # Program selector
        entities.append(AromaLinkProgramSelector(coordinator, entry, device_id, device_name))

        # Editor fields (one set per device, shows current program)
        entities.append(AromaLinkProgramEnabled(coordinator, entry, device_id, device_name))
        entities.append(AromaLinkProgramStartTime(coordinator, entry, device_id, device_name))
        entities.append(AromaLinkProgramEndTime(coordinator, entry, device_id, device_name))
        entities.append(AromaLinkProgramWorkDuration(coordinator, entry, device_id, device_name))
        entities.append(AromaLinkProgramPauseDuration(coordinator, entry, device_id, device_name))
        entities.append(AromaLinkProgramLevel(coordinator, entry, device_id, device_name))

        # Day selection switches (one per day)
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        for day_num, day_name in enumerate(day_names):
            entities.append(AromaLinkProgramDaySwitch(coordinator, entry, device_id, device_name, day_num, day_name))

        # Save button
        entities.append(AromaLinkSaveProgramButton(coordinator, entry, device_id, device_name))

    async_add_entities(entities)


class AromaLinkProgramSelector(CoordinatorEntity, SelectEntity):
    """Program selector entity (1-5)."""

    def __init__(self, coordinator, entry, device_id, device_name):
        """Initialize the program selector."""
        super().__init__(coordinator)
        self._entry = entry
        self._device_id = device_id
        self._device_name = device_name
        self._name = f"{device_name} Program"
        self._unique_id = f"{entry.data['username']}_{device_id}_program_selector"
        self._current_program = 1  # Default to Program 1
        self._current_day = 0  # Default to Monday

    @property
    def name(self):
        """Return the name."""
        return self._name

    @property
    def unique_id(self):
        """Return unique ID."""
        return self._unique_id

    @property
    def options(self):
        """Return the options."""
        return ["1", "2", "3", "4", "5"]

    @property
    def current_option(self):
        """Return the current option."""
        return str(self._current_program)

    @property
    def device_info(self):
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry.data['username']}_{self._device_id}")},
            name=self.coordinator.device_name,
            manufacturer="Aroma-Link",
            model="Diffuser",
        )

    async def async_select_option(self, option: str):
        """Select a program."""
        self._current_program = int(option)
        self.coordinator._current_program = int(option)
        # Trigger update of editor entities
        self.async_write_ha_state()
        # Load schedule for current day if not cached
        if self.coordinator._current_day not in self.coordinator._schedule_cache:
            await self.coordinator.async_refresh_schedule(self.coordinator._current_day)

    def _get_current_program_data(self):
        """Get data for currently selected program from cache."""
        if self._current_day not in self.coordinator._schedule_cache:
            return None
        schedule = self.coordinator._schedule_cache[self._current_day]
        if len(schedule) >= self._current_program:
            return schedule[self._current_program - 1]
        return None


class AromaLinkProgramEnabled(CoordinatorEntity, SwitchEntity):
    """Program enabled/disabled switch."""

    def __init__(self, coordinator, entry, device_id, device_name):
        """Initialize."""
        super().__init__(coordinator)
        self._entry = entry
        self._device_id = device_id
        self._device_name = device_name
        self._name = f"{device_name} Program Enabled"
        self._unique_id = f"{entry.data['username']}_{device_id}_program_enabled"
        self._program_selector = None

    @property
    def name(self):
        """Return the name."""
        return self._name

    @property
    def unique_id(self):
        """Return unique ID."""
        return self._unique_id

    @property
    def is_on(self):
        """Return if enabled."""
        program_num = self.coordinator._current_program
        day = self.coordinator._current_day

        if day in self.coordinator._schedule_cache:
            schedule = self.coordinator._schedule_cache[day]
            if len(schedule) >= program_num:
                return schedule[program_num - 1].get("enabled", 0) == 1
        return False

    @property
    def device_info(self):
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry.data['username']}_{self._device_id}")},
            name=self.coordinator.device_name,
            manufacturer="Aroma-Link",
            model="Diffuser",
        )

    async def async_turn_on(self, **kwargs):
        """Enable the program."""
        # Store locally, will be saved when Save button is pressed
        program_num = self.coordinator._current_program
        day = self.coordinator._current_day
        if day not in self.coordinator._schedule_cache:
            await self.coordinator.async_refresh_schedule(day)
        if day in self.coordinator._schedule_cache:
            schedule = self.coordinator._schedule_cache[day]
            if len(schedule) >= program_num:
                schedule[program_num - 1]["enabled"] = 1
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Disable the program."""
        program_num = self.coordinator._current_program
        day = self.coordinator._current_day
        if day not in self.coordinator._schedule_cache:
            await self.coordinator.async_refresh_schedule(day)
        if day in self.coordinator._schedule_cache:
            schedule = self.coordinator._schedule_cache[day]
            if len(schedule) >= program_num:
                schedule[program_num - 1]["enabled"] = 0
        self.async_write_ha_state()


class AromaLinkProgramStartTime(CoordinatorEntity, TextEntity):
    """Program start time (HH:MM format)."""

    def __init__(self, coordinator, entry, device_id, device_name):
        """Initialize."""
        super().__init__(coordinator)
        self._entry = entry
        self._device_id = device_id
        self._device_name = device_name
        self._name = f"{device_name} Program Start Time"
        self._unique_id = f"{entry.data['username']}_{device_id}_program_start_time"
        self._attr_native_min = 0
        self._attr_native_max = 5  # "23:59" is 5 chars
        self._attr_pattern = r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$"  # HH:MM format

    @property
    def name(self):
        """Return the name."""
        return self._name

    @property
    def unique_id(self):
        """Return unique ID."""
        return self._unique_id

    @property
    def native_value(self):
        """Return the current time as HH:MM string."""
        program_num = self.coordinator._current_program
        day = self.coordinator._current_day
        if day in self.coordinator._schedule_cache:
            schedule = self.coordinator._schedule_cache[day]
            if len(schedule) >= program_num:
                return schedule[program_num - 1].get("start_time", "00:00")
        return "00:00"

    @property
    def device_info(self):
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry.data['username']}_{self._device_id}")},
            name=self.coordinator.device_name,
            manufacturer="Aroma-Link",
            model="Diffuser",
        )

    async def async_set_value(self, value):
        """Set the start time."""
        # Validate format
        if not re.match(self._attr_pattern, value):
            _LOGGER.warning(f"Invalid time format: {value}, expected HH:MM")
            return
        program_num = self.coordinator._current_program
        day = self.coordinator._current_day
        if day not in self.coordinator._schedule_cache:
            await self.coordinator.async_refresh_schedule(day)
        if day in self.coordinator._schedule_cache:
            schedule = self.coordinator._schedule_cache[day]
            if len(schedule) >= program_num:
                schedule[program_num - 1]["start_time"] = value
        self.async_write_ha_state()


class AromaLinkProgramEndTime(CoordinatorEntity, TextEntity):
    """Program end time (HH:MM format)."""

    def __init__(self, coordinator, entry, device_id, device_name):
        """Initialize."""
        super().__init__(coordinator)
        self._entry = entry
        self._device_id = device_id
        self._device_name = device_name
        self._name = f"{device_name} Program End Time"
        self._unique_id = f"{entry.data['username']}_{device_id}_program_end_time"
        self._attr_native_min = 0
        self._attr_native_max = 5  # "23:59" is 5 chars
        self._attr_pattern = r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$"  # HH:MM format

    @property
    def name(self):
        """Return the name."""
        return self._name

    @property
    def unique_id(self):
        """Return unique ID."""
        return self._unique_id

    @property
    def native_value(self):
        """Return the current time as HH:MM string."""
        program_num = self.coordinator._current_program
        day = self.coordinator._current_day
        if day in self.coordinator._schedule_cache:
            schedule = self.coordinator._schedule_cache[day]
            if len(schedule) >= program_num:
                return schedule[program_num - 1].get("end_time", "23:59")
        return "23:59"

    @property
    def device_info(self):
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry.data['username']}_{self._device_id}")},
            name=self.coordinator.device_name,
            manufacturer="Aroma-Link",
            model="Diffuser",
        )

    async def async_set_value(self, value):
        """Set the end time."""
        # Validate format
        if not re.match(self._attr_pattern, value):
            _LOGGER.warning(f"Invalid time format: {value}, expected HH:MM")
            return
        program_num = self.coordinator._current_program
        day = self.coordinator._current_day
        if day not in self.coordinator._schedule_cache:
            await self.coordinator.async_refresh_schedule(day)
        if day in self.coordinator._schedule_cache:
            schedule = self.coordinator._schedule_cache[day]
            if len(schedule) >= program_num:
                schedule[program_num - 1]["end_time"] = value
        self.async_write_ha_state()


class AromaLinkProgramWorkDuration(CoordinatorEntity, NumberEntity):
    """Program work duration."""

    def __init__(self, coordinator, entry, device_id, device_name):
        """Initialize."""
        super().__init__(coordinator)
        self._entry = entry
        self._device_id = device_id
        self._device_name = device_name
        self._name = f"{device_name} Program Work Duration"
        self._unique_id = f"{entry.data['username']}_{device_id}_program_work_duration"
        self._attr_native_min_value = 5
        self._attr_native_max_value = 900
        self._attr_native_step = 1
        self._attr_native_unit_of_measurement = "sec"

    @property
    def name(self):
        """Return the name."""
        return self._name

    @property
    def unique_id(self):
        """Return unique ID."""
        return self._unique_id

    @property
    def native_value(self):
        """Return the current value."""
        program_num = self.coordinator._current_program
        day = self.coordinator._current_day
        if day in self.coordinator._schedule_cache:
            schedule = self.coordinator._schedule_cache[day]
            if len(schedule) >= program_num:
                return float(schedule[program_num - 1].get("work_sec", 10))
        return 10.0

    @property
    def device_info(self):
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry.data['username']}_{self._device_id}")},
            name=self.coordinator.device_name,
            manufacturer="Aroma-Link",
            model="Diffuser",
        )

    async def async_set_native_value(self, value):
        """Set the work duration."""
        program_num = self.coordinator._current_program
        day = self.coordinator._current_day
        if day not in self.coordinator._schedule_cache:
            await self.coordinator.async_refresh_schedule(day)
        if day in self.coordinator._schedule_cache:
            schedule = self.coordinator._schedule_cache[day]
            if len(schedule) >= program_num:
                schedule[program_num - 1]["work_sec"] = int(value)
        self.async_write_ha_state()


class AromaLinkProgramPauseDuration(CoordinatorEntity, NumberEntity):
    """Program pause duration."""

    def __init__(self, coordinator, entry, device_id, device_name):
        """Initialize."""
        super().__init__(coordinator)
        self._entry = entry
        self._device_id = device_id
        self._device_name = device_name
        self._name = f"{device_name} Program Pause Duration"
        self._unique_id = f"{entry.data['username']}_{device_id}_program_pause_duration"
        self._attr_native_min_value = 5
        self._attr_native_max_value = 900
        self._attr_native_step = 5
        self._attr_native_unit_of_measurement = "sec"

    @property
    def name(self):
        """Return the name."""
        return self._name

    @property
    def unique_id(self):
        """Return unique ID."""
        return self._unique_id

    @property
    def native_value(self):
        """Return the current value."""
        program_num = self.coordinator._current_program
        day = self.coordinator._current_day
        if day in self.coordinator._schedule_cache:
            schedule = self.coordinator._schedule_cache[day]
            if len(schedule) >= program_num:
                return float(schedule[program_num - 1].get("pause_sec", 120))
        return 120.0

    @property
    def device_info(self):
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry.data['username']}_{self._device_id}")},
            name=self.coordinator.device_name,
            manufacturer="Aroma-Link",
            model="Diffuser",
        )

    async def async_set_native_value(self, value):
        """Set the pause duration."""
        program_num = self.coordinator._current_program
        day = self.coordinator._current_day
        if day not in self.coordinator._schedule_cache:
            await self.coordinator.async_refresh_schedule(day)
        if day in self.coordinator._schedule_cache:
            schedule = self.coordinator._schedule_cache[day]
            if len(schedule) >= program_num:
                schedule[program_num - 1]["pause_sec"] = int(value)
        self.async_write_ha_state()


class AromaLinkProgramLevel(CoordinatorEntity, SelectEntity):
    """Program consistency level."""

    def __init__(self, coordinator, entry, device_id, device_name):
        """Initialize."""
        super().__init__(coordinator)
        self._entry = entry
        self._device_id = device_id
        self._device_name = device_name
        self._name = f"{device_name} Program Level"
        self._unique_id = f"{entry.data['username']}_{device_id}_program_level"

    @property
    def name(self):
        """Return the name."""
        return self._name

    @property
    def unique_id(self):
        """Return unique ID."""
        return self._unique_id

    @property
    def options(self):
        """Return the options."""
        return ["A", "B", "C"]

    @property
    def current_option(self):
        """Return the current option."""
        program_num = self.coordinator._current_program
        day = self.coordinator._current_day
        if day in self.coordinator._schedule_cache:
            schedule = self.coordinator._schedule_cache[day]
            if len(schedule) >= program_num:
                level = schedule[program_num - 1].get("level", 1)
                level_map = {1: "A", 2: "B", 3: "C"}
                return level_map.get(level, "A")
        return "A"

    @property
    def device_info(self):
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry.data['username']}_{self._device_id}")},
            name=self.coordinator.device_name,
            manufacturer="Aroma-Link",
            model="Diffuser",
        )

    async def async_select_option(self, option: str):
        """Select a level."""
        program_num = self.coordinator._current_program
        day = self.coordinator._current_day
        if day not in self.coordinator._schedule_cache:
            await self.coordinator.async_refresh_schedule(day)
        if day in self.coordinator._schedule_cache:
            schedule = self.coordinator._schedule_cache[day]
            if len(schedule) >= program_num:
                level_map = {"A": 1, "B": 2, "C": 3}
                schedule[program_num - 1]["level"] = level_map.get(option, 1)
        self.async_write_ha_state()


class AromaLinkProgramDaySwitch(CoordinatorEntity, SwitchEntity):
    """Day selection switch (one per day)."""

    def __init__(self, coordinator, entry, device_id, device_name, day_num, day_name):
        """Initialize."""
        super().__init__(coordinator)
        self._entry = entry
        self._device_id = device_id
        self._device_name = device_name
        self._day_num = day_num
        self._day_name = day_name
        self._name = f"{device_name} Program Day {day_name}"
        self._unique_id = f"{entry.data['username']}_{device_id}_program_day_{day_num}"

    @property
    def name(self):
        """Return the name."""
        return self._name

    @property
    def unique_id(self):
        """Return unique ID."""
        return self._unique_id

    @property
    def is_on(self):
        """Return if day is selected."""
        return self._day_num in self.coordinator._selected_days

    @property
    def device_info(self):
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry.data['username']}_{self._device_id}")},
            name=self.coordinator.device_name,
            manufacturer="Aroma-Link",
            model="Diffuser",
        )

    async def async_turn_on(self, **kwargs):
        """Select this day."""
        if self._day_num not in self.coordinator._selected_days:
            self.coordinator._selected_days.append(self._day_num)
            self.coordinator._selected_days.sort()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Deselect this day."""
        if self._day_num in self.coordinator._selected_days:
            self.coordinator._selected_days.remove(self._day_num)
        self.async_write_ha_state()


class AromaLinkSaveProgramButton(CoordinatorEntity, ButtonEntity):
    """Save Program button."""

    def __init__(self, coordinator, entry, device_id, device_name):
        """Initialize."""
        super().__init__(coordinator)
        self._entry = entry
        self._device_id = device_id
        self._device_name = device_name
        self._name = f"{device_name} Save Program"
        self._unique_id = f"{entry.data['username']}_{device_id}_save_program"

    @property
    def name(self):
        """Return the name."""
        return self._name

    @property
    def unique_id(self):
        """Return unique ID."""
        return self._unique_id

    @property
    def device_info(self):
        """Return device information."""
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
                _LOGGER.error(f"Failed to fetch schedule for day {day}")
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
        # The API accepts multiple days, so we can send all at once
        if work_time_lists:
            # Use the first day's work_time_list format (all days get same programs)
            first_day = selected_days[0]
            if first_day in work_time_lists:
                result = await self.coordinator.set_workset(selected_days, work_time_lists[first_day])
                if result:
                    _LOGGER.info(f"Saved program {program_num} to days {selected_days}")
                else:
                    _LOGGER.error(f"Failed to save program {program_num}")
