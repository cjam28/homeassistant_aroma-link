"""Select platform for Aroma-Link."""
from homeassistant.components.select import SelectEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Aroma-Link select entities based on a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    device_coordinators = data["device_coordinators"]

    entities = []
    for device_id, coordinator in device_coordinators.items():
        device_info = coordinator.get_device_info()
        device_name = device_info["name"]
        entities.append(AromaLinkProgramSelector(coordinator, entry, device_id, device_name))
        entities.append(AromaLinkProgramLevel(coordinator, entry, device_id, device_name))

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
