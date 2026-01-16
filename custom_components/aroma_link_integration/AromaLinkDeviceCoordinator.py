import asyncio
import logging
from datetime import timedelta
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .const import (
    DOMAIN,
    DEFAULT_DIFFUSE_TIME,
    DEFAULT_WORK_DURATION,
    DEFAULT_PAUSE_DURATION,
    VERIFY_SSL,
)

_LOGGER = logging.getLogger(__name__)


class AromaLinkDeviceCoordinator(DataUpdateCoordinator):
    """Coordinator for handling device data and control."""

    def __init__(self, hass, auth_coordinator, device_id, device_name, update_interval_seconds=60):
        """Initialize the device coordinator."""
        self.hass = hass
        self.auth_coordinator = auth_coordinator
        self.device_id = device_id
        self.device_name = device_name
        self._diffuse_time = DEFAULT_DIFFUSE_TIME
        self._work_duration = DEFAULT_WORK_DURATION
        self._pause_duration = DEFAULT_PAUSE_DURATION
        self._schedule_cache = {}  # Cache schedules per day (0-6)
        # Editor state for schedule entities
        self._current_program = 1  # Currently selected program (1-5)
        self._current_day = 0  # Currently selected day for viewing (0-6)
        self._selected_days = [0]  # Days selected for saving (list of 0-6)
        
        # Oil tracking - cycle detection approach
        import time
        self._oil_tracking_active = False
        self._oil_tracking_start_time = None
        self._baseline_pump_count = None
        self._accumulated_work_seconds = 0.0
        self._completed_cycles = 0
        
        # Previous poll state for cycle detection
        self._prev_device_on = False
        self._prev_work_status = 0  # 0=off, 1=pausing, 2=working
        self._prev_work_remain = 0
        self._prev_pause_remain = 0
        self._prev_work_duration = 5  # Current work setting
        self._prev_pause_duration = 900  # Current pause setting
        
        # Event log for debugging
        self._oil_events = []  # List of (timestamp, event, details)
        
        # Oil calibration data (persists until recalibration)
        self._oil_calibration = {
            "bottle_capacity": 100,  # Max bottle size in ml
            "fill_volume": 100,  # Volume at last fill in ml
            "measured_remaining": 0,  # User-measured remaining (for calibration)
            "usage_rate": None,  # ml per work-second (calculated)
            "calibrated": False,  # Has calibration been done?
            "calibration_runtime": 0,  # Runtime at calibration point
        }

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{device_id}",
            update_interval=timedelta(seconds=update_interval_seconds),
        )

    @property
    def diffuse_time(self):
        """Return the diffuse time."""
        return self._diffuse_time

    @diffuse_time.setter
    def diffuse_time(self, value):
        """Set the diffuse time."""
        self._diffuse_time = value

    @property
    def work_duration(self):
        """Return the work duration."""
        return self._work_duration

    @work_duration.setter
    def work_duration(self, value):
        """Set the work duration."""
        self._work_duration = value

    @property
    def pause_duration(self):
        """Return the pause duration."""
        return self._pause_duration

    @pause_duration.setter
    def pause_duration(self, value):
        """Set the pause duration."""
        self._pause_duration = value

    # ============================================================
    # OIL TRACKING METHODS (cycle detection from workRemain/pauseRemain)
    # ============================================================
    
    def reset_oil_tracking(self, current_pump_count=None):
        """Reset oil tracking (call when refilling oil).
        
        Uses cycle detection from workRemainTime/pauseRemainTime changes
        to accurately count completed work cycles.
        """
        import time
        self._oil_tracking_active = True
        self._oil_tracking_start_time = time.time()
        self._accumulated_work_seconds = 0.0
        self._completed_cycles = 0
        self._oil_events = []
        
        # Reset previous state
        self._prev_device_on = False
        self._prev_work_status = 0
        self._prev_work_remain = 0
        self._prev_pause_remain = 0
        
        # Capture pumpCount as reference
        if current_pump_count is not None:
            self._baseline_pump_count = current_pump_count
        elif self.data and "pumpCount" in self.data:
            self._baseline_pump_count = self.data.get("pumpCount", 0)
        else:
            self._baseline_pump_count = 0
        
        self._log_oil_event("RESET", f"Started tracking. Baseline pumpCount: {self._baseline_pump_count}")
        
        _LOGGER.info(
            "Reset oil tracking for device %s. Baseline pumpCount: %s",
            self.device_id, self._baseline_pump_count
        )
    
    def _log_oil_event(self, event_type: str, details: str):
        """Log an oil tracking event for debugging."""
        import time
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._oil_events.append((timestamp, event_type, details))
        # Keep only last 50 events
        if len(self._oil_events) > 50:
            self._oil_events = self._oil_events[-50:]
        _LOGGER.debug(f"Oil event [{self.device_id}] {event_type}: {details}")
    
    def update_oil_tracking(
        self,
        device_on: bool,
        work_status: int,
        work_remain: int,
        pause_remain: int,
        work_duration: int,
        pause_duration: int,
    ):
        """Update oil tracking using cycle detection.
        
        Detects completed work cycles by monitoring:
        - workStatus transitions (working → pausing)
        - workRemainTime resets (indicates new cycle)
        - pauseRemainTime jumps (indicates work just completed)
        
        Args:
            device_on: Whether device is on
            work_status: 0=off, 1=pausing, 2=working
            work_remain: Seconds remaining in current work cycle
            pause_remain: Seconds remaining in current pause cycle
            work_duration: Current work setting (seconds per spray)
            pause_duration: Current pause setting
        """
        if not self._oil_tracking_active:
            # Update state but don't track
            self._prev_device_on = device_on
            self._prev_work_status = work_status
            self._prev_work_remain = work_remain
            self._prev_pause_remain = pause_remain
            self._prev_work_duration = work_duration
            self._prev_pause_duration = pause_duration
            return
        
        cycle_completed = False
        work_seconds_to_add = 0
        
        # Detection Case 1: Device turned OFF
        if self._prev_device_on and not device_on:
            self._log_oil_event("OFF", "Device turned off")
        
        # Detection Case 2: Device turned ON
        elif not self._prev_device_on and device_on:
            self._log_oil_event("ON", f"Device turned on. Status={work_status}")
        
        # Detection Case 3: Device was ON and still ON - check for cycle completion
        elif self._prev_device_on and device_on:
            
            # Case 3a: Was working (2), now pausing (1) → work cycle completed!
            if self._prev_work_status == 2 and work_status == 1:
                cycle_completed = True
                work_seconds_to_add = self._prev_work_duration
                self._log_oil_event(
                    "CYCLE", 
                    f"Work→Pause transition. +{work_seconds_to_add}s"
                )
            
            # Case 3b: workRemain jumped UP (e.g., 2 → 10) → new cycle started
            elif work_status == 2 and work_remain > self._prev_work_remain + 2:
                # Only count if we were previously in a work cycle
                if self._prev_work_status == 2:
                    cycle_completed = True
                    work_seconds_to_add = self._prev_work_duration
                    self._log_oil_event(
                        "CYCLE",
                        f"workRemain reset {self._prev_work_remain}→{work_remain}. +{work_seconds_to_add}s"
                    )
            
            # Case 3c: pauseRemain jumped UP significantly → new pause started after work
            elif work_status == 1 and self._prev_work_status == 1:
                if pause_remain > self._prev_pause_remain + 100:
                    # Pause timer reset = new cycle started
                    cycle_completed = True
                    work_seconds_to_add = self._prev_work_duration
                    self._log_oil_event(
                        "CYCLE",
                        f"pauseRemain reset {self._prev_pause_remain}→{pause_remain}. +{work_seconds_to_add}s"
                    )
            
            # Case 3d: Settings changed
            if work_duration != self._prev_work_duration or pause_duration != self._prev_pause_duration:
                self._log_oil_event(
                    "SETTINGS",
                    f"Changed: work {self._prev_work_duration}→{work_duration}s, "
                    f"pause {self._prev_pause_duration}→{pause_duration}s"
                )
        
        # Apply detected cycle
        if cycle_completed:
            self._accumulated_work_seconds += work_seconds_to_add
            self._completed_cycles += 1
            _LOGGER.info(
                "Oil tracking [%s]: Cycle #%d completed. +%ds work. Total: %.1fs",
                self.device_id, self._completed_cycles, 
                work_seconds_to_add, self._accumulated_work_seconds
            )
        
        # Update previous state for next poll
        self._prev_device_on = device_on
        self._prev_work_status = work_status
        self._prev_work_remain = work_remain
        self._prev_pause_remain = pause_remain
        self._prev_work_duration = work_duration
        self._prev_pause_duration = pause_duration
    
    def get_cumulative_work_seconds(self):
        """Get accumulated work seconds since last fill."""
        return self._accumulated_work_seconds
    
    def get_completed_cycles(self):
        """Get number of completed work/spray cycles."""
        return self._completed_cycles
    
    def get_pump_count_delta(self):
        """Get pumpCount change since fill (API reference)."""
        if self._baseline_pump_count is None:
            return None
        current = self.data.get("pumpCount", 0) if self.data else 0
        return current - self._baseline_pump_count
    
    def get_oil_tracking_info(self):
        """Get comprehensive oil tracking data."""
        import time
        tracking_duration = 0
        if self._oil_tracking_start_time:
            tracking_duration = time.time() - self._oil_tracking_start_time
        
        return {
            "tracking_active": self._oil_tracking_active,
            "tracking_duration_seconds": tracking_duration,
            "accumulated_work_seconds": self._accumulated_work_seconds,
            "completed_cycles": self._completed_cycles,
            "baseline_pump_count": self._baseline_pump_count,
            "pump_count_delta": self.get_pump_count_delta(),
            "current_work_duration": self._prev_work_duration,
            "current_pause_duration": self._prev_pause_duration,
            "recent_events": self._oil_events[-10:] if self._oil_events else [],
        }
    
    def get_oil_events_log(self):
        """Get the full event log for debugging."""
        return self._oil_events.copy()
    
    def set_accumulated_work_seconds(self, seconds):
        """Set accumulated work seconds (for restoring state)."""
        self._accumulated_work_seconds = seconds
    
    def set_completed_cycles(self, cycles):
        """Set completed cycles (for restoring state)."""
        self._completed_cycles = cycles
    
    def set_oil_tracking_start_time(self, timestamp):
        """Set tracking start time (for restoring state)."""
        self._oil_tracking_start_time = timestamp
        self._oil_tracking_active = timestamp is not None
    
    # ============================================================
    # OIL CALIBRATION METHODS
    # ============================================================
    
    def get_oil_calibration(self):
        """Get current oil calibration data."""
        return self._oil_calibration.copy()
    
    def set_oil_calibration(self, **kwargs):
        """Update oil calibration values."""
        for key, value in kwargs.items():
            if key in self._oil_calibration:
                self._oil_calibration[key] = value
        _LOGGER.debug("Oil calibration updated: %s", self._oil_calibration)
    
    def perform_oil_calibration(self):
        """Calculate usage rate from fill volume, measured remaining, and runtime.
        
        Call this after user enters measured_remaining value.
        Returns the calculated usage rate in ml/second of work time.
        """
        fill_vol = self._oil_calibration["fill_volume"]
        remaining = self._oil_calibration["measured_remaining"]
        runtime = self._accumulated_work_seconds
        
        if runtime <= 0:
            _LOGGER.warning("Cannot calibrate: no runtime recorded")
            return None
        
        oil_used = fill_vol - remaining
        if oil_used <= 0:
            _LOGGER.warning("Cannot calibrate: oil used is zero or negative")
            return None
        
        usage_rate = oil_used / runtime  # ml per second of work
        
        self._oil_calibration["usage_rate"] = usage_rate
        self._oil_calibration["calibrated"] = True
        self._oil_calibration["calibration_runtime"] = runtime
        
        _LOGGER.info(
            "Oil calibration complete for %s: %.6f ml/sec (%.2f ml/hour of spray)",
            self.device_id, usage_rate, usage_rate * 3600
        )
        
        return usage_rate
    
    def get_estimated_oil_remaining(self):
        """Calculate estimated remaining oil based on calibration and runtime.
        
        Returns remaining ml, or None if not calibrated.
        """
        if not self._oil_calibration["calibrated"] or self._oil_calibration["usage_rate"] is None:
            return None
        
        fill_vol = self._oil_calibration["fill_volume"]
        usage_rate = self._oil_calibration["usage_rate"]
        runtime = self._accumulated_work_seconds
        
        oil_used = runtime * usage_rate
        remaining = fill_vol - oil_used
        
        return max(0, remaining)  # Don't go negative
    
    def get_oil_level_percent(self):
        """Get oil level as percentage of bottle capacity.
        
        Returns percentage (0-100), or None if not calibrated.
        """
        remaining = self.get_estimated_oil_remaining()
        if remaining is None:
            return None
        
        capacity = self._oil_calibration["bottle_capacity"]
        if capacity <= 0:
            return None
        
        return min(100, (remaining / capacity) * 100)
    
    def reset_oil_fill(self):
        """Mark oil as just filled (resets runtime tracking).
        
        Sets fill_volume = bottle_capacity and resets tracking.
        Preserves calibrated usage_rate if already calibrated.
        """
        capacity = self._oil_calibration["bottle_capacity"]
        self._oil_calibration["fill_volume"] = capacity
        
        # Reset runtime tracking
        import time
        self._oil_tracking_active = True
        self._oil_tracking_start_time = time.time()
        self._accumulated_work_seconds = 0.0
        self._completed_cycles = 0
        self._oil_events = []
        
        # Capture baseline
        if self.data:
            self._baseline_pump_count = self.data.get("pumpCount", 0)
        
        self._log_oil_event("FILL", f"Oil filled to {capacity}ml. Tracking reset.")
        
        _LOGGER.info("Oil fill reset for %s. Capacity: %d ml", self.device_id, capacity)
    
    def get_oil_status(self):
        """Get comprehensive oil status for display."""
        remaining = self.get_estimated_oil_remaining()
        level_pct = self.get_oil_level_percent()
        cal = self._oil_calibration
        
        return {
            "bottle_capacity_ml": cal["bottle_capacity"],
            "fill_volume_ml": cal["fill_volume"],
            "calibrated": cal["calibrated"],
            "usage_rate_ml_per_sec": cal["usage_rate"],
            "usage_rate_ml_per_hour": cal["usage_rate"] * 3600 if cal["usage_rate"] else None,
            "estimated_remaining_ml": round(remaining, 1) if remaining is not None else None,
            "level_percent": round(level_pct, 1) if level_pct is not None else None,
            "runtime_since_fill_sec": self._accumulated_work_seconds,
            "runtime_since_fill_hours": round(self._accumulated_work_seconds / 3600, 2),
            "completed_cycles": self._completed_cycles,
        }

    async def fetch_work_time_settings(self, week_day=0):
        """Fetch current work time settings from API."""
        await self.auth_coordinator._ensure_login()
        jsessionid = self.auth_coordinator.jsessionid

        url = f"https://www.aroma-link.com/device/workTime/{self.device_id}?week={week_day}"

        headers = {
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://www.aroma-link.com",
            "Referer": f"https://www.aroma-link.com/device/command/{self.device_id}",
        }

        if jsessionid and not jsessionid.startswith("temp_"):
            headers["Cookie"] = f"languagecode={self.auth_coordinator.language_code}; JSESSIONID={jsessionid}"

        try:
            _LOGGER.debug(
                "Fetching work time settings for device %s day %s (url=%s)",
                self.device_id,
                week_day,
                url,
            )
            async with self.auth_coordinator.session.get(url, headers=headers, timeout=15, ssl=VERIFY_SSL) as response:
                if response.status == 200:
                    response_json = await response.json()
                    _LOGGER.debug(
                        "Work time response for device %s day %s: %s",
                        self.device_id,
                        week_day,
                        response_json,
                    )

                    if response_json.get("code") == 200 and "data" in response_json and response_json["data"]:
                        # Find the enabled setting (enabled: 1)
                        for setting in response_json["data"]:
                            if setting.get("enabled") == 1:
                                self._work_duration = setting.get(
                                    "workSec", self._work_duration)
                                self._pause_duration = setting.get(
                                    "pauseSec", self._pause_duration)
                                _LOGGER.debug(
                                    f"Found settings: work={self._work_duration}s, pause={self._pause_duration}s")
                                return {
                                    "work_duration": self._work_duration,
                                    "pause_duration": self._pause_duration,
                                    "week_day": week_day
                                }

                    _LOGGER.warning(
                        f"No enabled work time settings found for device {self.device_id}")
                    return None
                elif response.status in [401, 403]:
                    _LOGGER.warning(
                        f"Authentication error on fetch_work_time_settings ({response.status}).")
                    self.auth_coordinator.jsessionid = None
                    return None
                else:
                    _LOGGER.error(
                        f"Failed to fetch work time settings for device {self.device_id}: {response.status}")
                    return None
        except Exception as e:
            _LOGGER.error(
                f"Error fetching work time settings for device {self.device_id}: {e}")
            return None

    async def async_fetch_schedule(self, week_day):
        """Fetch schedule for a day, using cache if available.
        
        Args:
            week_day: Day of week (0=Monday, 1=Tuesday, ..., 6=Sunday)
            
        Returns:
            List of 5 program dictionaries, or None on error.
        """
        # Check cache first
        if week_day in self._schedule_cache:
            _LOGGER.debug(f"Using cached schedule for day {week_day}")
            return self._schedule_cache[week_day]
        
        # Fetch from API
        return await self.async_refresh_schedule(week_day)
    
    async def async_refresh_schedule(self, week_day):
        """Refresh schedule for a day from API (on-demand).
        
        Args:
            week_day: Day of week (0=Monday, 1=Tuesday, ..., 6=Sunday)
            
        Returns:
            List of 5 program dictionaries, or None on error.
        """
        workset = await self.fetch_workset_for_day(week_day)
        if workset:
            self._schedule_cache[week_day] = workset
            _LOGGER.debug(f"Cached schedule for day {week_day}")
        return workset

    async def async_fetch_all_schedules(self):
        """Fetch schedules for all 7 days in parallel.
        
        Returns:
            Dict mapping day (0-6) to list of 5 program dictionaries.
        """
        _LOGGER.debug(f"Fetching all schedules for device {self.device_id}")
        
        # Fetch all 7 days in parallel
        tasks = [self.fetch_workset_for_day(day) for day in range(7)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results and update cache
        for day, result in enumerate(results):
            if isinstance(result, Exception):
                _LOGGER.error(f"Error fetching day {day}: {result}")
            elif result:
                self._schedule_cache[day] = result
        
        _LOGGER.info(f"Fetched all schedules for device {self.device_id}: {len(self._schedule_cache)} days cached")
        return self._schedule_cache.copy()

    def get_schedule_matrix(self):
        """Return the cached schedule matrix (7 days × 5 programs).
        
        Returns:
            Dict mapping day (0-6) to list of 5 program dictionaries.
            Days without cached data return None.
        """
        return {day: self._schedule_cache.get(day) for day in range(7)}

    def get_current_program_data(self):
        """Get the current program data from cache for the selected day/program.
        
        Returns:
            Dict with program settings, or None if not cached.
        """
        day = self._current_day
        program = self._current_program
        if day in self._schedule_cache and self._schedule_cache[day]:
            programs = self._schedule_cache[day]
            if 0 < program <= len(programs):
                return programs[program - 1]
        return None

    def set_editor_program(self, day, program):
        """Set the editor to a specific day and program.
        
        Args:
            day: Day of week (0=Monday, 1=Tuesday, ..., 6=Sunday)
            program: Program number (1-5)
        """
        self._current_day = day
        self._current_program = program
        # Also update selected_days to include this day by default
        if day not in self._selected_days:
            self._selected_days = [day]
        _LOGGER.debug(f"Set editor to day {day}, program {program}")
        # Notify listeners
        self.async_update_listeners()

    async def fetch_workset_for_day(self, week_day=0):
        """Fetch full workset (all 5 programs) for a specific day.
        
        Args:
            week_day: Day of week (0=Monday, 1=Tuesday, ..., 6=Sunday)
            
        Returns:
            List of 5 program dictionaries with keys: enabled, start_time, end_time, 
            work_sec, pause_sec, level, setting_id. Returns None on error.
        """
        await self.auth_coordinator._ensure_login()
        jsessionid = self.auth_coordinator.jsessionid

        url = f"https://www.aroma-link.com/device/workTime/{self.device_id}?week={week_day}"

        headers = {
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://www.aroma-link.com",
            "Referer": f"https://www.aroma-link.com/device/command/{self.device_id}",
        }

        if jsessionid and not jsessionid.startswith("temp_"):
            headers["Cookie"] = f"languagecode={self.auth_coordinator.language_code}; JSESSIONID={jsessionid}"

        try:
            _LOGGER.debug(
                "Fetching workset for device %s day %s (url=%s)",
                self.device_id,
                week_day,
                url,
            )
            async with self.auth_coordinator.session.get(url, headers=headers, timeout=15, ssl=VERIFY_SSL) as response:
                if response.status == 200:
                    response_json = await response.json()
                    _LOGGER.debug(
                        "Workset response for device %s day %s: %s",
                        self.device_id,
                        week_day,
                        response_json,
                    )

                    if response_json.get("code") == 200 and "data" in response_json and response_json["data"]:
                        workset = []
                        # API returns up to 5 programs, ensure we have exactly 5
                        data = response_json["data"]
                        for i, setting in enumerate(data[:5]):  # Limit to 5
                            workset.append({
                                "enabled": setting.get("enabled", 0),
                                "start_time": setting.get("startHour", "00:00"),
                                "end_time": setting.get("endHour", "23:59"),
                                "work_sec": setting.get("workSec", 10),
                                "pause_sec": setting.get("pauseSec", 120),
                                "level": setting.get("consistenceLevel", 1),
                                "setting_id": setting.get("settingId"),
                            })
                        
                        # Pad to 5 if fewer returned
                        while len(workset) < 5:
                            workset.append({
                                "enabled": 0,
                                "start_time": "00:00",
                                "end_time": "23:59",
                                "work_sec": 10,
                                "pause_sec": 120,
                                "level": 1,
                                "setting_id": None,
                            })
                        
                        _LOGGER.debug(
                            "Fetched workset for device %s day %s: %s",
                            self.device_id,
                            week_day,
                            workset,
                        )
                        return workset
                    else:
                        _LOGGER.warning(
                            f"No workset data found for device {self.device_id} day {week_day}")
                        # Return empty workset (5 disabled programs)
                        return [
                            {"enabled": 0, "start_time": "00:00", "end_time": "23:59", 
                             "work_sec": 10, "pause_sec": 120, "level": 1, "setting_id": None}
                            for _ in range(5)
                        ]
                elif response.status in [401, 403]:
                    _LOGGER.warning(
                        f"Authentication error on fetch_workset_for_day ({response.status}).")
                    self.auth_coordinator.jsessionid = None
                    return None
                else:
                    _LOGGER.error(
                        f"Failed to fetch workset for device {self.device_id}: {response.status}")
                    return None
        except Exception as e:
            _LOGGER.error(
                f"Error fetching workset for device {self.device_id}: {e}")
            return None

    async def set_workset(self, week_days, work_time_list):
        """Set workset schedule for specified days.
        
        Args:
            week_days: List of day numbers (0=Monday, 1=Tuesday, ..., 6=Sunday)
            work_time_list: List of 5 program dictionaries, each with:
                - enabled: 0 or 1
                - startTime: "HH:MM" format
                - endTime: "HH:MM" format
                - workDuration: string (seconds)
                - pauseDuration: string (seconds)
                - consistenceLevel: "1", "2", or "3" (A, B, or C)
                
        Returns:
            True if successful, False otherwise
        """
        await self.auth_coordinator._ensure_login()
        jsessionid = self.auth_coordinator.jsessionid

        url = "https://www.aroma-link.com/device/workSet"

        # Ensure we have exactly 5 programs
        if len(work_time_list) < 5:
            # Pad with disabled programs
            work_time_list = list(work_time_list)
            while len(work_time_list) < 5:
                work_time_list.append({
                    "startTime": "00:00",
                    "endTime": "23:59",
                    "enabled": 0,
                    "consistenceLevel": "1",
                    "workDuration": "10",
                    "pauseDuration": "120"
                })
        elif len(work_time_list) > 5:
            work_time_list = work_time_list[:5]

        payload = {
            "deviceId": str(self.device_id),
            "type": "workTime",
            "week": week_days,
            "workTimeList": work_time_list
        }

        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://www.aroma-link.com",
            "Referer": f"https://www.aroma-link.com/device/command/{self.device_id}",
        }

        if jsessionid and not jsessionid.startswith("temp_"):
            headers["Cookie"] = f"languagecode={self.auth_coordinator.language_code}; JSESSIONID={jsessionid}"

        try:
            _LOGGER.debug(
                "Setting workset for device %s on days %s (payload=%s)",
                self.device_id,
                week_days,
                payload,
            )
            async with self.auth_coordinator.session.post(url, json=payload, headers=headers, timeout=10, ssl=VERIFY_SSL) as response:
                if response.status == 200:
                    response_json = await response.json()
                    _LOGGER.debug(
                        "Workset save response for device %s: %s",
                        self.device_id,
                        response_json,
                    )
                    if response_json.get("code") == 200:
                        _LOGGER.info(
                            f"Successfully set workset for device {self.device_id} to days {week_days}")
                        # Clear cache for updated days
                        for day in week_days:
                            if day in self._schedule_cache:
                                del self._schedule_cache[day]
                                _LOGGER.debug(f"Cleared schedule cache for day {day}")
                        await self.async_request_refresh()
                        return True
                    else:
                        _LOGGER.error(
                            f"API error setting workset: {response_json.get('msg', 'Unknown error')}")
                        return False
                elif response.status in [401, 403]:
                    _LOGGER.warning(
                        f"Authentication error on set_workset ({response.status}).")
                    self.auth_coordinator.jsessionid = None
                    return False
                else:
                    _LOGGER.error(
                        f"Failed to set workset for device {self.device_id}: {response.status}")
                    return False
        except Exception as e:
            _LOGGER.error(f"Error setting workset for device {self.device_id}: {e}")
            return False

    def get_device_info(self):
        """Get device info for entity setup."""
        return {
            "id": self.device_id,
            "name": self.device_name
        }

    async def _async_update_data(self):
        """Fetch current device state from API."""
        # Ensure auth is valid
        await self.auth_coordinator._ensure_login()
        jsessionid = self.auth_coordinator.jsessionid

        url = f"https://www.aroma-link.com/device/deviceInfo/now/{self.device_id}?timeout=1000"

        headers = {
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://www.aroma-link.com",
            "Referer": f"https://www.aroma-link.com/device/command/{self.device_id}",
        }

        # Only add Cookie header if we have a valid JSESSIONID
        if jsessionid and not jsessionid.startswith("temp_"):
            headers["Cookie"] = f"languagecode={self.auth_coordinator.language_code}; JSESSIONID={jsessionid}"

        try:
            _LOGGER.debug(
                "Fetching device info for device %s (url=%s)",
                self.device_id,
                url,
            )
            async with self.auth_coordinator.session.get(url, headers=headers, timeout=15, ssl=VERIFY_SSL) as response:
                if response.status == 200:
                    response_json = await response.json()
                    _LOGGER.debug(
                        "Device info response for device %s: %s",
                        self.device_id,
                        response_json,
                    )

                    if response_json.get("code") == 200 and "data" in response_json:
                        device_data = response_json["data"]
                        is_on = device_data.get("onOff") == 1
                        fan_on = device_data.get("fan") == 1
                        work_status = device_data.get("workStatus", 0)
                        pump_count = device_data.get("pumpCount", 0)
                        
                        # Get timing values from API
                        work_remain = device_data.get("workRemainTime", 0) or 0
                        pause_remain = device_data.get("pauseRemainTime", 0) or 0
                        
                        # Get work/pause duration settings
                        # API may return workSec/pauseSec, or we infer from schedule
                        work_duration = device_data.get("workSec", self._prev_work_duration)
                        pause_duration = device_data.get("pauseSec", self._prev_pause_duration)
                        
                        # If workStatus=2 and workRemain > stored duration, update it
                        if work_status == 2 and work_remain > work_duration:
                            work_duration = work_remain
                        
                        # Update oil tracking with cycle detection
                        self.update_oil_tracking(
                            device_on=is_on,
                            work_status=work_status,
                            work_remain=work_remain,
                            pause_remain=pause_remain,
                            work_duration=work_duration,
                            pause_duration=pause_duration,
                        )
                        
                        # Get comprehensive oil tracking info
                        oil_info = self.get_oil_tracking_info()
                        
                        return {
                            "state": is_on,
                            "onOff": device_data.get("onOff"),
                            "fan": device_data.get("fan", 0),
                            "fan_state": fan_on,
                            "workStatus": work_status,
                            "workRemainTime": work_remain,
                            "pauseRemainTime": pause_remain,
                            "workSec": work_duration,
                            "pauseSec": pause_duration,
                            "raw_device_data": device_data,
                            "device_id": self.device_id,
                            "device_name": self.device_name,
                            "pumpCount": pump_count,
                            "runCount": device_data.get("runCount", 0),
                            # Oil tracking data
                            **oil_info,
                        }
                    else:
                        error_msg = response_json.get("msg", "Unknown error")
                        _LOGGER.error(
                            f"API error for device {self.device_id}: {error_msg}")
                        raise UpdateFailed(f"API error: {error_msg}")
                elif response.status in [401, 403]:
                    _LOGGER.warning(
                        f"Authentication error ({response.status}) for device {self.device_id}. Forcing re-login.")
                    self.auth_coordinator.jsessionid = None
                    raise UpdateFailed(f"Authentication error")
                else:
                    _LOGGER.error(
                        f"Failed to fetch device {self.device_id} info, status: {response.status}")
                    raise UpdateFailed(
                        f"Error fetching device info: status {response.status}")
        except Exception as e:
            _LOGGER.error(f"Error fetching device {self.device_id} info: {e}")
            raise UpdateFailed(f"Error: {e}")

    async def api_request(self, url, method="GET", params=None, data=None, json_body=None):
        """Make an authenticated API request for diagnostics/testing."""
        await self.auth_coordinator._ensure_login()
        jsessionid = self.auth_coordinator.jsessionid

        headers = {
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://www.aroma-link.com",
            "Referer": f"https://www.aroma-link.com/device/command/{self.device_id}",
        }

        if jsessionid and not jsessionid.startswith("temp_"):
            headers["Cookie"] = (
                f"languagecode={self.auth_coordinator.language_code}; JSESSIONID={jsessionid}"
            )

        if json_body is not None:
            headers["Content-Type"] = "application/json"
        elif data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"

        _LOGGER.debug("API diagnostics request: %s %s", method, url)

        async with self.auth_coordinator.session.request(
            method=method,
            url=url,
            params=params,
            data=data,
            json=json_body,
            timeout=15,
            ssl=VERIFY_SSL,
            headers=headers,
        ) as response:
            content_type = response.headers.get("Content-Type", "")
            response_text = await response.text()

            try:
                response_json = await response.json()
            except Exception:
                response_json = None

            return {
                "status": response.status,
                "content_type": content_type,
                "json": response_json,
                "text": response_text if response_json is None else None,
            }

    async def turn_on_off(self, state_to_set):
        """Turn the diffuser on or off."""
        await self.auth_coordinator._ensure_login()
        jsessionid = self.auth_coordinator.jsessionid

        url = "https://www.aroma-link.com/device/switch"

        data = {
            "deviceId": self.device_id,
            "onOff": 1 if state_to_set else 0
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://www.aroma-link.com",
            "Referer": f"https://www.aroma-link.com/device/command/{self.device_id}",
        }

        if jsessionid and not jsessionid.startswith("temp_"):
            headers["Cookie"] = f"languagecode={self.auth_coordinator.language_code}; JSESSIONID={jsessionid}"

        try:
            _LOGGER.debug(
                "Switch request for device %s (data=%s)",
                self.device_id,
                data,
            )
            async with self.auth_coordinator.session.post(url, data=data, headers=headers, timeout=10, ssl=VERIFY_SSL) as response:
                if response.status == 200:
                    response_text = await response.text()
                    _LOGGER.debug(
                        "Switch response for device %s: %s",
                        self.device_id,
                        response_text,
                    )
                    _LOGGER.info(
                        f"Successfully commanded device {self.device_id} to {'on' if state_to_set else 'off'}")
                    await self.async_request_refresh()
                    return True
                elif response.status in [401, 403]:
                    _LOGGER.warning(
                        f"Authentication error on turn_on_off ({response.status}).")
                    self.auth_coordinator.jsessionid = None
                    return False
                else:
                    _LOGGER.error(
                        f"Failed to control device {self.device_id}: {response.status}")
                    return False
        except Exception as e:
            _LOGGER.error(f"Control error for device {self.device_id}: {e}")
            return False

    async def fan_control(self, state_to_set):
        """Turn the fan on or off."""
        await self.auth_coordinator._ensure_login()
        jsessionid = self.auth_coordinator.jsessionid

        url = "https://www.aroma-link.com/device/switch"

        data = {
            "deviceId": self.device_id,
            "fan": 1 if state_to_set else 0
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://www.aroma-link.com",
            "Referer": f"https://www.aroma-link.com/device/command/{self.device_id}",
        }

        if jsessionid and not jsessionid.startswith("temp_"):
            headers["Cookie"] = f"languagecode={self.auth_coordinator.language_code}; JSESSIONID={jsessionid}"

        try:
            _LOGGER.debug(
                "Fan request for device %s (data=%s)",
                self.device_id,
                data,
            )
            async with self.auth_coordinator.session.post(url, data=data, headers=headers, timeout=10, ssl=VERIFY_SSL) as response:
                if response.status == 200:
                    response_text = await response.text()
                    _LOGGER.debug(
                        "Fan response for device %s: %s",
                        self.device_id,
                        response_text,
                    )
                    _LOGGER.info(
                        f"Successfully commanded fan for device {self.device_id} to {'on' if state_to_set else 'off'}")
                    await self.async_request_refresh()
                    return True
                elif response.status in [401, 403]:
                    _LOGGER.warning(
                        f"Authentication error on fan_control ({response.status}).")
                    self.auth_coordinator.jsessionid = None
                    return False
                else:
                    _LOGGER.error(
                        f"Failed to control fan for device {self.device_id}: {response.status}")
                    return False
        except Exception as e:
            _LOGGER.error(f"Fan control error for device {self.device_id}: {e}")
            return False

    async def set_scheduler(self, work_duration=None, pause_duration=None, week_days=None):
        """Set the scheduler for the diffuser."""
        await self.auth_coordinator._ensure_login()
        jsessionid = self.auth_coordinator.jsessionid

        url = "https://www.aroma-link.com/device/workSet"

        if week_days is None:
            week_days = [0, 1, 2, 3, 4, 5, 6]  # Default to all days

        # Use provided values or fall back to stored values
        work_duration = work_duration if work_duration is not None else self._work_duration
        pause_duration = pause_duration if pause_duration is not None else self._pause_duration

        payload = {
            "deviceId": self.device_id,
            "type": "workTime",
            "week": week_days,
            "workTimeList": [
                {
                    "startTime": "00:00",
                    "endTime": "23:59",
                    "enabled": 1,
                    "consistenceLevel": "1",
                    "workDuration": str(work_duration),
                    "pauseDuration": str(pause_duration)
                },
                {
                    "startTime": "00:00",
                    "endTime": "24:00",
                    "enabled": 0,
                    "consistenceLevel": "1",
                    "workDuration": "10",
                    "pauseDuration": "900"
                },
                {
                    "startTime": "00:00",
                    "endTime": "24:00",
                    "enabled": 0,
                    "consistenceLevel": "1",
                    "workDuration": "10",
                    "pauseDuration": "900"
                },
                {
                    "startTime": "00:00",
                    "endTime": "24:00",
                    "enabled": 0,
                    "consistenceLevel": "1",
                    "workDuration": "10",
                    "pauseDuration": "900"
                },
                {
                    "startTime": "00:00",
                    "endTime": "24:00",
                    "enabled": 0,
                    "consistenceLevel": "1",
                    "workDuration": "10",
                    "pauseDuration": "900"
                }
            ]
        }

        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://www.aroma-link.com",
            "Referer": f"https://www.aroma-link.com/device/command/{self.device_id}",
        }

        if jsessionid and not jsessionid.startswith("temp_"):
            headers["Cookie"] = f"languagecode={self.auth_coordinator.language_code}; JSESSIONID={jsessionid}"

        try:
            _LOGGER.debug(
                "Scheduler request for device %s (payload=%s)",
                self.device_id,
                payload,
            )
            async with self.auth_coordinator.session.post(url, json=payload, headers=headers, timeout=10, ssl=VERIFY_SSL) as response:
                if response.status == 200:
                    response_text = await response.text()
                    _LOGGER.debug(
                        "Scheduler response for device %s: %s",
                        self.device_id,
                        response_text,
                    )
                    _LOGGER.info(
                        f"Successfully set scheduler for device {self.device_id}")
                    await self.async_request_refresh()
                    return True
                elif response.status in [401, 403]:
                    _LOGGER.warning(
                        f"Authentication error on set_scheduler ({response.status}).")
                    self.auth_coordinator.jsessionid = None
                    return False
                else:
                    _LOGGER.error(
                        f"Failed to set scheduler for device {self.device_id}: {response.status}")
                    return False
        except Exception as e:
            _LOGGER.error(f"Scheduler error for device {self.device_id}: {e}")
            return False

    async def run_diffuser(self, work_duration=None, pause_duration=None):
        """Run the diffuser for a specific time."""
        # Use default values if specific ones aren't provided
        current_work_duration = work_duration if work_duration is not None else self._work_duration
        current_pause_duration = pause_duration if pause_duration is not None else self._pause_duration
        buffertime = current_work_duration + 5  # Add buffer time

        _LOGGER.info(
            f"Setting up device {self.device_id} to run for {current_work_duration} seconds with {current_work_duration} second diffusion cycles and {current_pause_duration} second pauses")

        # Set scheduler
        if not await self.set_scheduler(current_work_duration, current_pause_duration):
            _LOGGER.error(
                f"Failed to set scheduler for device {self.device_id}")
            return False

        await asyncio.sleep(1)  # Allow time for scheduler settings to apply

        if not await self.turn_on_off(True):
            _LOGGER.error(f"Failed to turn on device {self.device_id}")
            return False

        _LOGGER.info(
            f"Device {self.device_id} turned on. Will turn off automatically after {buffertime} seconds.")

        # Schedule turn off after the specified time
        async def turn_off_later():
            await asyncio.sleep(buffertime)
            _LOGGER.info(
                f"Timer complete for device {self.device_id}. Attempting to turn off.")
            if not await self.turn_on_off(False):
                _LOGGER.error(
                    f"Failed to automatically turn off device {self.device_id}")
            else:
                _LOGGER.info(
                    f"Device {self.device_id} turned off successfully after timer")

        self.hass.async_create_task(turn_off_later())

        return True
