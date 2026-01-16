"""Sensor platform for Aroma-Link."""
import logging
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.const import UnitOfTime
from homeassistant.util import dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Aroma-Link sensor based on a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    device_coordinators = data["device_coordinators"]
    
    entities = []
    for device_id, coordinator in device_coordinators.items():
        device_info = coordinator.get_device_info()
        
        # Add all the requested sensors
        entities.append(AromaLinkWorkStatusSensor(coordinator, entry, device_id, device_info["name"]))
        entities.append(AromaLinkWorkRemainingTimeSensor(coordinator, entry, device_id, device_info["name"]))
        entities.append(AromaLinkPauseRemainingTimeSensor(coordinator, entry, device_id, device_info["name"]))
        entities.append(AromaLinkOnCountSensor(coordinator, entry, device_id, device_info["name"]))
        entities.append(AromaLinkPumpCountSensor(coordinator, entry, device_id, device_info["name"]))
        entities.append(AromaLinkSignalStrengthSensor(coordinator, entry, device_id, device_info["name"]))
        entities.append(AromaLinkFirmwareVersionSensor(coordinator, entry, device_id, device_info["name"]))
        entities.append(AromaLinkLastUpdateSensor(coordinator, entry, device_id, device_info["name"]))
        entities.append(AromaLinkScheduleMatrixSensor(coordinator, entry, device_id, device_info["name"]))
    
    async_add_entities(entities)

class AromaLinkSensorBase(CoordinatorEntity, SensorEntity):
    """Base class for Aroma-Link sensors."""

    def __init__(self, coordinator, entry, device_id, device_name, sensor_type, icon=None, unit=None):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._device_id = device_id
        self._sensor_type = sensor_type
        self._name = f"{device_name} {sensor_type}"
        self._unique_id = f"{entry.data['username']}_{device_id}_{sensor_type.lower().replace(' ', '_')}"
        self._attr_icon = icon
        self._attr_native_unit_of_measurement = unit

    @property
    def name(self):
        """Return the name of the sensor."""
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


def _get_first_value(raw_data, keys):
    """Return the first non-None value for the provided keys."""
    for key in keys:
        if key in raw_data and raw_data.get(key) is not None:
            return raw_data.get(key)
    return None


def _parse_timestamp(value):
    """Parse a timestamp in seconds or milliseconds to a datetime."""
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = float(value)
        except ValueError:
            return None
    if isinstance(value, (int, float)):
        if value > 1_000_000_000_000:
            value = value / 1000.0
        if value > 1_000_000_000:
            return dt_util.utc_from_timestamp(value)
    return None

class AromaLinkWorkStatusSensor(AromaLinkSensorBase):
    """Sensor showing the current work status."""

    def __init__(self, coordinator, entry, device_id, device_name):
        """Initialize the work status sensor."""
        super().__init__(
            coordinator, 
            entry, 
            device_id, 
            device_name, 
            "Work Status", 
            icon="mdi:state-machine"
        )

    @property
    def native_value(self):
        """Return the current work status."""
        work_status = self.coordinator.data.get("workStatus")
        if work_status == 0:
            return "Off"
        elif work_status == 1:
            return "Diffusing"
        elif work_status == 2:
            return "Paused"
        else:
            return "Unknown"

class AromaLinkWorkRemainingTimeSensor(AromaLinkSensorBase):
    """Sensor showing the remaining time in the current work cycle."""

    def __init__(self, coordinator, entry, device_id, device_name):
        """Initialize the work remaining time sensor."""
        super().__init__(
            coordinator, 
            entry, 
            device_id, 
            device_name, 
            "Work Remaining Time", 
            icon="mdi:timer-outline",
            unit=UnitOfTime.SECONDS
        )

    @property
    def native_value(self):
        """Return the remaining time in work cycle."""
        return self.coordinator.data.get("workRemainTime")

class AromaLinkPauseRemainingTimeSensor(AromaLinkSensorBase):
    """Sensor showing the remaining time in the current pause cycle."""

    def __init__(self, coordinator, entry, device_id, device_name):
        """Initialize the pause remaining time sensor."""
        super().__init__(
            coordinator, 
            entry, 
            device_id, 
            device_name, 
            "Pause Remaining Time", 
            icon="mdi:timer-pause-outline",
            unit=UnitOfTime.SECONDS
        )

    @property
    def native_value(self):
        """Return the remaining time in pause cycle."""
        return self.coordinator.data.get("pauseRemainTime")

class AromaLinkOnCountSensor(AromaLinkSensorBase):
    """Sensor showing how many times the device has been turned on."""

    def __init__(self, coordinator, entry, device_id, device_name):
        """Initialize the on count sensor."""
        super().__init__(
            coordinator, 
            entry, 
            device_id, 
            device_name, 
            "On Count", 
            icon="mdi:counter",
            unit="activations"
        )

    @property
    def native_value(self):
        """Return the on count value."""
        raw_data = self.coordinator.data.get("raw_device_data", {})
        return raw_data.get("onCount")

class AromaLinkPumpCountSensor(AromaLinkSensorBase):
    """Sensor showing the number of times the pump has operated (diffusions)."""

    def __init__(self, coordinator, entry, device_id, device_name):
        """Initialize the pump count sensor."""
        super().__init__(
            coordinator, 
            entry, 
            device_id, 
            device_name, 
            "Pump Count", 
            icon="mdi:shimmer",
            unit="diffusions"
        )

    @property
    def native_value(self):
        """Return the pump count value."""
        raw_data = self.coordinator.data.get("raw_device_data", {})
        return raw_data.get("pumpCount")


class AromaLinkSignalStrengthSensor(AromaLinkSensorBase):
    """Sensor showing signal strength (if provided by the API)."""

    def __init__(self, coordinator, entry, device_id, device_name):
        """Initialize the signal strength sensor."""
        super().__init__(
            coordinator,
            entry,
            device_id,
            device_name,
            "Signal Strength",
            icon="mdi:wifi",
        )

    @property
    def native_value(self):
        """Return the signal strength value."""
        raw_data = self.coordinator.data.get("raw_device_data", {})
        value = _get_first_value(
            raw_data,
            ["rssi", "signalStrength", "signal", "signalLevel", "wifiSignal", "wifiLevel"],
        )
        if isinstance(value, str) and value.strip().isdigit():
            return int(value)
        return value


class AromaLinkFirmwareVersionSensor(AromaLinkSensorBase):
    """Sensor showing firmware version (if provided by the API)."""

    def __init__(self, coordinator, entry, device_id, device_name):
        """Initialize the firmware version sensor."""
        super().__init__(
            coordinator,
            entry,
            device_id,
            device_name,
            "Firmware Version",
            icon="mdi:chip",
        )

    @property
    def native_value(self):
        """Return the firmware version value."""
        raw_data = self.coordinator.data.get("raw_device_data", {})
        return _get_first_value(
            raw_data,
            ["firmwareVersion", "firmware", "fwVersion", "deviceVersion", "version"],
        )


class AromaLinkLastUpdateSensor(AromaLinkSensorBase):
    """Sensor showing the last update timestamp (if provided by the API)."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator, entry, device_id, device_name):
        """Initialize the last update sensor."""
        super().__init__(
            coordinator,
            entry,
            device_id,
            device_name,
            "Last Update",
            icon="mdi:clock-outline",
        )

    @property
    def native_value(self):
        """Return the last update timestamp."""
        raw_data = self.coordinator.data.get("raw_device_data", {})
        value = _get_first_value(
            raw_data,
            ["updateTime", "lastUpdate", "lastUpdateTime", "update_time", "updateTimestamp"],
        )
        return _parse_timestamp(value)


class AromaLinkScheduleMatrixSensor(AromaLinkSensorBase):
    """Sensor exposing the full schedule matrix as attributes for dashboard cards."""

    def __init__(self, coordinator, entry, device_id, device_name):
        """Initialize the schedule matrix sensor."""
        super().__init__(
            coordinator,
            entry,
            device_id,
            device_name,
            "Schedule Matrix",
            icon="mdi:calendar-clock",
        )

    @property
    def native_value(self):
        """Return number of days with cached schedules."""
        return len(self.coordinator._schedule_cache)

    @property
    def extra_state_attributes(self):
        """Return the full schedule matrix as attributes."""
        day_names = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]
        matrix = {}
        
        for day_num in range(7):
            day_name = day_names[day_num]
            if day_num in self.coordinator._schedule_cache:
                programs = self.coordinator._schedule_cache[day_num]
                day_data = {}
                for prog_num, prog in enumerate(programs, 1):
                    day_data[f"program_{prog_num}"] = {
                        "enabled": prog.get("enabled", 0) == 1,
                        "start": prog.get("start_time", "00:00"),
                        "end": prog.get("end_time", "23:59"),
                        "work": prog.get("work_sec", 10),
                        "pause": prog.get("pause_sec", 120),
                        "level": ["A", "B", "C"][prog.get("level", 1) - 1] if prog.get("level") in [1, 2, 3] else "A",
                    }
                matrix[day_name] = day_data
            else:
                matrix[day_name] = None
        
        return {
            "matrix": matrix,
            "current_day": self.coordinator._current_day,
            "current_program": self.coordinator._current_program,
            "selected_days": self.coordinator._selected_days,
            "device_id": self.coordinator.device_id,
        }