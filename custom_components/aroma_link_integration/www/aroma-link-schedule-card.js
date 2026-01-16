/**
 * Aroma-Link Schedule Card v1.9.0
 * 
 * A complete dashboard card for Aroma-Link diffusers including:
 * - Manual controls (Power, Fan, Run Continuously, Run Timed with countdown)
 * - Schedule matrix with multi-cell editing (per-device selections)
 * - Copy schedule from another diffuser
 * 
 * Styled to match Mushroom/button-card aesthetics.
 * 
 * Usage:
 *   type: custom:aroma-link-schedule-card
 */

class AromaLinkScheduleCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._initialized = false;
    // Per-device selection state: Map<deviceName, Set<"day-program">>
    this._selectedCellsByDevice = new Map();
    this._isSaving = false;
    this._statusMessage = null;
    this._statusDevice = null; // Track which device the status is for
    this._editorValuesByDevice = new Map(); // Per-device editor values
    // Timer state: Map<deviceName, { endTime: number, intervalId: number, remainingSeconds: number }>
    this._timersByDevice = new Map();
    // Default timed run duration in minutes per device
    this._timedRunMinutesByDevice = new Map();
  }

  _getTimedRunMinutes(deviceName) {
    if (!this._timedRunMinutesByDevice.has(deviceName)) {
      this._timedRunMinutesByDevice.set(deviceName, 30); // Default 30 minutes
    }
    return this._timedRunMinutesByDevice.get(deviceName);
  }

  _setTimedRunMinutes(deviceName, minutes) {
    this._timedRunMinutesByDevice.set(deviceName, minutes);
  }

  _getTimerState(deviceName) {
    return this._timersByDevice.get(deviceName);
  }

  _formatCountdown(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  }

  async _startTimedRun(deviceName, controls, minutes) {
    // First, turn on power and apply settings
    await this._applySettingsAndRun(deviceName, controls);
    
    // Set up the timer
    const endTime = Date.now() + (minutes * 60 * 1000);
    const timerState = {
      endTime,
      remainingSeconds: minutes * 60,
      intervalId: null
    };
    
    // Start countdown interval
    timerState.intervalId = setInterval(() => {
      const remaining = Math.max(0, Math.ceil((timerState.endTime - Date.now()) / 1000));
      timerState.remainingSeconds = remaining;
      
      if (remaining <= 0) {
        this._stopTimedRun(deviceName, controls);
      } else {
        this.render();
      }
    }, 1000);
    
    this._timersByDevice.set(deviceName, timerState);
    this._showStatus(`Timer started: ${minutes} minutes`, false, deviceName);
  }

  async _stopTimedRun(deviceName, controls) {
    const timerState = this._timersByDevice.get(deviceName);
    if (timerState?.intervalId) {
      clearInterval(timerState.intervalId);
    }
    this._timersByDevice.delete(deviceName);
    
    // Turn off the power
    if (this._hass.states[controls.power]?.state === 'on') {
      await this._hass.callService('switch', 'turn_off', { entity_id: controls.power });
    }
    
    this._showStatus('Timer complete - turned off', false, deviceName);
  }

  _cancelTimer(deviceName) {
    const timerState = this._timersByDevice.get(deviceName);
    if (timerState?.intervalId) {
      clearInterval(timerState.intervalId);
    }
    this._timersByDevice.delete(deviceName);
    this.render();
  }

  async _applySettingsAndRun(deviceName, controls) {
    // Save work/pause settings first
    const saveSettingsBtn = `button.${deviceName}_save_settings`;
    if (this._hass.states[saveSettingsBtn]) {
      await this._hass.callService('button', 'press', { entity_id: saveSettingsBtn });
      await new Promise(resolve => setTimeout(resolve, 200));
    }
    
    // Then press the run button (which turns on power)
    if (this._hass.states[controls.run]) {
      await this._hass.callService('button', 'press', { entity_id: controls.run });
    }
  }

  async _runContinuously(deviceName, controls) {
    await this._applySettingsAndRun(deviceName, controls);
    this._showStatus('Running continuously', false, deviceName);
  }

  _getEditorValues(deviceName) {
    if (!this._editorValuesByDevice.has(deviceName)) {
      this._editorValuesByDevice.set(deviceName, {
        enabled: true,
        startTime: '09:00',
        endTime: '21:00',
        workSec: 10,
        pauseSec: 120,
        level: 'A'
      });
    }
    return this._editorValuesByDevice.get(deviceName);
  }

  _getSelectedCells(deviceName) {
    if (!this._selectedCellsByDevice.has(deviceName)) {
      this._selectedCellsByDevice.set(deviceName, new Set());
    }
    return this._selectedCellsByDevice.get(deviceName);
  }

  setConfig(config) {
    this.config = config || {};
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._initialized) {
      this._initialized = true;
    }
    this.render();
  }

  get hass() {
    return this._hass;
  }

  _getCurrentDayIndex() {
    return new Date().getDay();
  }

  _findScheduleMatrixSensors() {
    if (!this._hass) return [];
    
    const sensors = [];
    for (const entityId of Object.keys(this._hass.states)) {
      if (entityId.startsWith('sensor.') && entityId.endsWith('_schedule_matrix')) {
        const state = this._hass.states[entityId];
        if (state.attributes && state.attributes.matrix) {
          const deviceName = entityId.replace('sensor.', '').replace('_schedule_matrix', '');
          const friendlyName = deviceName
            .split('_')
            .map(word => word.charAt(0).toUpperCase() + word.slice(1))
            .join(' ');
          sensors.push({
            entityId,
            deviceName,
            friendlyName,
            matrix: state.attributes.matrix,
            deviceId: state.attributes.device_id
          });
        }
      }
    }
    
    if (this.config.device) {
      return sensors.filter(s => s.deviceName.toLowerCase().includes(this.config.device.toLowerCase()));
    }
    
    return sensors;
  }

  // Get device control entities
  _getControlEntities(deviceName) {
    return {
      power: `switch.${deviceName}_power`,
      fan: `switch.${deviceName}_fan`,
      workDuration: `number.${deviceName}_work_duration`,
      pauseDuration: `number.${deviceName}_pause_duration`,
      run: `button.${deviceName}_run`,
      saveSettings: `button.${deviceName}_save_settings`,
    };
  }

  _isCellSelected(deviceName, day, program) {
    return this._getSelectedCells(deviceName).has(`${day}-${program}`);
  }

  _toggleCell(deviceName, day, program, sensor = null) {
    const cells = this._getSelectedCells(deviceName);
    const key = `${day}-${program}`;
    if (cells.has(key)) {
      cells.delete(key);
    } else {
      cells.add(key);
      // Load the clicked cell's data into the editor
      if (sensor) {
        this._loadCellIntoEditor(sensor, day, program);
      }
    }
    this.render();
  }

  _loadCellIntoEditor(sensor, day, program) {
    const days = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday'];
    const dayName = days[day];
    
    const matrix = sensor.matrix || {};
    const dayData = matrix[dayName] || {};
    const progData = dayData[`program_${program}`] || {};
    
    const editorValues = this._getEditorValues(sensor.deviceName);
    editorValues.enabled = progData.enabled === true || progData.enabled === 1;
    editorValues.startTime = (progData.start_time || progData.start || '09:00').substring(0, 5);
    editorValues.endTime = (progData.end_time || progData.end || '21:00').substring(0, 5);
    editorValues.workSec = progData.work || progData.work_sec || 10;
    editorValues.pauseSec = progData.pause || progData.pause_sec || 120;
    editorValues.level = progData.level || 'A';
  }

  _selectProgramRow(deviceName, program) {
    const cells = this._getSelectedCells(deviceName);
    const allSelected = [0,1,2,3,4,5,6].every(day => cells.has(`${day}-${program}`));
    
    if (allSelected) {
      for (let day = 0; day < 7; day++) {
        cells.delete(`${day}-${program}`);
      }
    } else {
      for (let day = 0; day < 7; day++) {
        cells.add(`${day}-${program}`);
      }
    }
    this.render();
  }

  _selectAll(deviceName) {
    const cells = this._getSelectedCells(deviceName);
    for (let day = 0; day < 7; day++) {
      for (let prog = 1; prog <= 5; prog++) {
        cells.add(`${day}-${prog}`);
      }
    }
    this.render();
  }

  _selectDayColumn(deviceName, day) {
    const cells = this._getSelectedCells(deviceName);
    const allSelected = [1,2,3,4,5].every(prog => cells.has(`${day}-${prog}`));
    
    if (allSelected) {
      for (let prog = 1; prog <= 5; prog++) {
        cells.delete(`${day}-${prog}`);
      }
    } else {
      for (let prog = 1; prog <= 5; prog++) {
        cells.add(`${day}-${prog}`);
      }
    }
    this.render();
  }

  // Check if selection has multiple programs on same day (disables time editing)
  _hasMultipleProgramsSameDay(deviceName) {
    const cells = this._getSelectedCells(deviceName);
    const dayProgramCount = {};
    
    for (const key of cells) {
      const [day] = key.split('-').map(Number);
      dayProgramCount[day] = (dayProgramCount[day] || 0) + 1;
      if (dayProgramCount[day] > 1) return true;
    }
    return false;
  }

  _clearSelection(deviceName) {
    this._getSelectedCells(deviceName).clear();
    this.render();
  }

  _isValidTime(time) {
    return /^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$/.test(time);
  }

  _timeToMinutes(time) {
    const [h, m] = time.split(':').map(Number);
    return h * 60 + m;
  }

  _checkOverlaps(sensor, day, programToUpdate, newStart, newEnd) {
    const days = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday'];
    const dayName = days[day];
    const matrix = sensor.matrix || {};
    const dayData = matrix[dayName] || {};
    const cells = this._getSelectedCells(sensor.deviceName);
    
    const newStartMin = this._timeToMinutes(newStart);
    const newEndMin = this._timeToMinutes(newEnd);
    
    const overlaps = [];
    
    for (let prog = 1; prog <= 5; prog++) {
      if (prog === programToUpdate) continue;
      if (cells.has(`${day}-${prog}`)) continue;
      
      const progData = dayData[`program_${prog}`] || {};
      const isEnabled = progData.enabled === true || progData.enabled === 1;
      if (!isEnabled) continue;
      
      const existingStart = (progData.start_time || progData.start || '00:00').substring(0, 5);
      const existingEnd = (progData.end_time || progData.end || '23:59').substring(0, 5);
      const existingStartMin = this._timeToMinutes(existingStart);
      const existingEndMin = this._timeToMinutes(existingEnd);
      
      if (newStartMin < existingEndMin && newEndMin > existingStartMin) {
        overlaps.push({ program: prog, start: existingStart, end: existingEnd });
      }
    }
    
    return overlaps;
  }

  _showStatus(message, isError = false, deviceName = null) {
    this._statusMessage = { text: message, isError };
    this._statusDevice = deviceName;
    this.render();
    
    setTimeout(() => {
      this._statusMessage = null;
      this._statusDevice = null;
      this.render();
    }, 4000);
  }

  // Toggle power/fan
  async _toggleSwitch(entityId) {
    const state = this._hass.states[entityId];
    if (state) {
      await this._hass.callService('switch', state.state === 'on' ? 'turn_off' : 'turn_on', {
        entity_id: entityId
      });
    }
  }

  // Press a button
  async _pressButton(entityId) {
    if (this._hass.states[entityId]) {
      await this._hass.callService('button', 'press', { entity_id: entityId });
    }
  }

  // Set number value
  async _setNumber(entityId, value) {
    if (this._hass.states[entityId]) {
      await this._hass.callService('number', 'set_value', {
        entity_id: entityId,
        value: value
      });
    }
  }

  async _clearSelectedSchedules(sensor) {
    const cells = this._getSelectedCells(sensor.deviceName);
    
    if (cells.size === 0) {
      this._showStatus('No cells selected.', true, sensor.deviceName);
      return;
    }

    // Set editor to disabled state
    const editorValues = this._getEditorValues(sensor.deviceName);
    editorValues.enabled = false;
    
    // Now save with enabled=false
    await this._saveSelectedCells(sensor);
    
    this._showStatus(`✓ Cleared ${cells.size} schedule(s)`, false, sensor.deviceName);
  }

  async _saveSelectedCells(sensor) {
    const cells = this._getSelectedCells(sensor.deviceName);
    const editorValues = this._getEditorValues(sensor.deviceName);
    
    if (cells.size === 0) {
      this._showStatus('No cells selected. Click cells in the grid to select them.', true, sensor.deviceName);
      return;
    }

    if (!this._isValidTime(editorValues.startTime)) {
      this._showStatus('Invalid start time. Use HH:MM format (e.g., 09:00)', true, sensor.deviceName);
      return;
    }
    if (!this._isValidTime(editorValues.endTime)) {
      this._showStatus('Invalid end time. Use HH:MM format (e.g., 21:00)', true, sensor.deviceName);
      return;
    }

    const startMin = this._timeToMinutes(editorValues.startTime);
    const endMin = this._timeToMinutes(editorValues.endTime);
    if (endMin <= startMin) {
      this._showStatus('End time must be after start time.', true, sensor.deviceName);
      return;
    }

    const daySelections = {};
    for (const key of cells) {
      const [day, program] = key.split('-').map(Number);
      if (!daySelections[day]) daySelections[day] = [];
      daySelections[day].push(program);
    }

    if (editorValues.enabled) {
      const dayNames = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
      const overlapDays = [];
      
      for (const [dayStr, programs] of Object.entries(daySelections)) {
        const day = parseInt(dayStr);
        for (const program of programs) {
          const overlaps = this._checkOverlaps(
            sensor, day, program,
            editorValues.startTime,
            editorValues.endTime
          );
          if (overlaps.length > 0 && !overlapDays.includes(dayNames[day])) {
            overlapDays.push(dayNames[day]);
          }
        }
      }

      if (overlapDays.length > 0) {
        this._showStatus(`Schedules in ${overlapDays.join(', ')} are overlapping. Please correct the times.`, true, sensor.deviceName);
        return;
      }
    }

    const deviceId = sensor.deviceId;
    if (!deviceId) {
      this._showStatus('Device ID not found. Cannot save.', true, sensor.deviceName);
      return;
    }

    this._isSaving = true;
    this.render();

    try {
      for (const [dayStr, programs] of Object.entries(daySelections)) {
        const day = parseInt(dayStr);
        
        for (const program of programs) {
          await this._hass.callService('aroma_link_integration', 'set_editor_program', {
            device_id: deviceId,
            day: day,
            program: program
          });
          
          await new Promise(resolve => setTimeout(resolve, 100));
          
          const prefix = sensor.deviceName;
          
          const enabledEntity = `switch.${prefix}_program_enabled`;
          if (this._hass.states[enabledEntity]) {
            await this._hass.callService('switch', editorValues.enabled ? 'turn_on' : 'turn_off', {
              entity_id: enabledEntity
            });
          }
          
          const startEntity = `text.${prefix}_program_start_time`;
          if (this._hass.states[startEntity]) {
            await this._hass.callService('text', 'set_value', {
              entity_id: startEntity,
              value: editorValues.startTime
            });
          }
          
          const endEntity = `text.${prefix}_program_end_time`;
          if (this._hass.states[endEntity]) {
            await this._hass.callService('text', 'set_value', {
              entity_id: endEntity,
              value: editorValues.endTime
            });
          }
          
          const workEntity = `number.${prefix}_program_work_time`;
          if (this._hass.states[workEntity]) {
            await this._hass.callService('number', 'set_value', {
              entity_id: workEntity,
              value: editorValues.workSec
            });
          }
          
          const pauseEntity = `number.${prefix}_program_pause_time`;
          if (this._hass.states[pauseEntity]) {
            await this._hass.callService('number', 'set_value', {
              entity_id: pauseEntity,
              value: editorValues.pauseSec
            });
          }
          
          const levelEntity = `select.${prefix}_program_level`;
          if (this._hass.states[levelEntity]) {
            await this._hass.callService('select', 'select_option', {
              entity_id: levelEntity,
              option: editorValues.level
            });
          }
          
          await new Promise(resolve => setTimeout(resolve, 100));
        }
        
        const daySwitches = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday'];
        
        for (let d = 0; d < 7; d++) {
          const switchEntity = `switch.${sensor.deviceName}_program_${daySwitches[d]}`;
          if (this._hass.states[switchEntity]) {
            await this._hass.callService('switch', 'turn_off', { entity_id: switchEntity });
          }
        }
        
        const daySwitch = `switch.${sensor.deviceName}_program_${daySwitches[day]}`;
        if (this._hass.states[daySwitch]) {
          await this._hass.callService('switch', 'turn_on', { entity_id: daySwitch });
        }
        
        await new Promise(resolve => setTimeout(resolve, 100));
        
        const saveButton = `button.${sensor.deviceName}_save_program`;
        if (this._hass.states[saveButton]) {
          await this._hass.callService('button', 'press', { entity_id: saveButton });
        }
        
        await new Promise(resolve => setTimeout(resolve, 500));
      }
      
      this._isSaving = false;
      cells.clear();
      this._showStatus(`✓ Saved ${Object.values(daySelections).flat().length} schedule(s) to Aroma-Link`, false, sensor.deviceName);
      
    } catch (error) {
      console.error('Error saving schedules:', error);
      this._isSaving = false;
      this._showStatus('Error saving schedules. Check console for details.', true, sensor.deviceName);
    }
  }

  async _pullSchedule(sensor) {
    this._showStatus('Pulling schedule from Aroma-Link...', false, sensor.deviceName);
    
    const syncButton = `button.${sensor.deviceName}_sync_schedules`;
    if (this._hass.states[syncButton]) {
      await this._hass.callService('button', 'press', { entity_id: syncButton });
    } else {
      await this._hass.callService('aroma_link_integration', 'refresh_all_schedules', {
        device_id: sensor.deviceId
      });
    }
    
    setTimeout(() => {
      this._showStatus('✓ Schedule refreshed from Aroma-Link', false, sensor.deviceName);
    }, 1000);
  }

  async _copyScheduleFrom(targetSensor, sourceSensor) {
    if (!sourceSensor || !targetSensor) {
      this._showStatus('Please select a source diffuser.', true, targetSensor.deviceName);
      return;
    }

    if (sourceSensor.deviceName === targetSensor.deviceName) {
      this._showStatus('Cannot copy to the same device.', true, targetSensor.deviceName);
      return;
    }

    this._showStatus(`Copying schedule from ${sourceSensor.friendlyName}...`, false, targetSensor.deviceName);
    this._isSaving = true;
    this.render();

    try {
      const sourceMatrix = sourceSensor.matrix || {};
      const days = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday'];
      const daySwitches = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday'];

      // For each day, copy all 5 programs from source to target
      for (let day = 0; day < 7; day++) {
        const dayName = days[day];
        const sourceDayData = sourceMatrix[dayName] || {};

        // For each program
        for (let prog = 1; prog <= 5; prog++) {
          const sourceProgData = sourceDayData[`program_${prog}`] || {};
          
          // Set the editor program on target device
          await this._hass.callService('aroma_link_integration', 'set_editor_program', {
            device_id: targetSensor.deviceId,
            day: day,
            program: prog
          });
          await new Promise(resolve => setTimeout(resolve, 100));

          const prefix = targetSensor.deviceName;
          const isEnabled = sourceProgData.enabled === true || sourceProgData.enabled === 1;
          const startTime = (sourceProgData.start_time || sourceProgData.start || '00:00').substring(0, 5);
          const endTime = (sourceProgData.end_time || sourceProgData.end || '23:59').substring(0, 5);
          const workSec = sourceProgData.work || sourceProgData.work_sec || 10;
          const pauseSec = sourceProgData.pause || sourceProgData.pause_sec || 120;
          const level = sourceProgData.level || 'A';

          // Set enabled state
          const enabledEntity = `switch.${prefix}_program_enabled`;
          if (this._hass.states[enabledEntity]) {
            await this._hass.callService('switch', isEnabled ? 'turn_on' : 'turn_off', {
              entity_id: enabledEntity
            });
          }

          // Set times
          const startEntity = `text.${prefix}_program_start_time`;
          if (this._hass.states[startEntity]) {
            await this._hass.callService('text', 'set_value', {
              entity_id: startEntity,
              value: startTime
            });
          }

          const endEntity = `text.${prefix}_program_end_time`;
          if (this._hass.states[endEntity]) {
            await this._hass.callService('text', 'set_value', {
              entity_id: endEntity,
              value: endTime
            });
          }

          // Set work/pause
          const workEntity = `number.${prefix}_program_work_time`;
          if (this._hass.states[workEntity]) {
            await this._hass.callService('number', 'set_value', {
              entity_id: workEntity,
              value: workSec
            });
          }

          const pauseEntity = `number.${prefix}_program_pause_time`;
          if (this._hass.states[pauseEntity]) {
            await this._hass.callService('number', 'set_value', {
              entity_id: pauseEntity,
              value: pauseSec
            });
          }

          // Set level
          const levelEntity = `select.${prefix}_program_level`;
          if (this._hass.states[levelEntity]) {
            await this._hass.callService('select', 'select_option', {
              entity_id: levelEntity,
              option: level
            });
          }

          await new Promise(resolve => setTimeout(resolve, 50));
        }

        // Turn off all day switches first
        for (let d = 0; d < 7; d++) {
          const switchEntity = `switch.${targetSensor.deviceName}_program_${daySwitches[d]}`;
          if (this._hass.states[switchEntity]) {
            await this._hass.callService('switch', 'turn_off', { entity_id: switchEntity });
          }
        }

        // Turn on only the current day
        const daySwitch = `switch.${targetSensor.deviceName}_program_${daySwitches[day]}`;
        if (this._hass.states[daySwitch]) {
          await this._hass.callService('switch', 'turn_on', { entity_id: daySwitch });
        }

        // Save this day
        const saveButton = `button.${targetSensor.deviceName}_save_program`;
        if (this._hass.states[saveButton]) {
          await this._hass.callService('button', 'press', { entity_id: saveButton });
        }

        await new Promise(resolve => setTimeout(resolve, 500));
      }

      this._isSaving = false;
      this._showStatus(`✓ Copied full schedule from ${sourceSensor.friendlyName}`, false, targetSensor.deviceName);

    } catch (error) {
      console.error('Error copying schedule:', error);
      this._isSaving = false;
      this._showStatus('Error copying schedule. Check console for details.', true, targetSensor.deviceName);
    }
  }

  render() {
    if (!this._hass) {
      this.shadowRoot.innerHTML = `<ha-card><div class="loading">Loading...</div></ha-card>`;
      return;
    }

    const sensors = this._findScheduleMatrixSensors();
    
    if (sensors.length === 0) {
      this.shadowRoot.innerHTML = `
        <ha-card>
          <div class="card-content">
            <div class="no-devices">
              No Aroma-Link devices found.<br>
              Make sure the integration is set up and schedules are synced.
            </div>
          </div>
        </ha-card>
      `;
      return;
    }

    const days = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday'];
    const dayLabels = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
    const programs = [1, 2, 3, 4, 5];
    const todayIndex = this._getCurrentDayIndex();

    let html = `<style>${this._getStyles()}</style>`;

    // Build list of other devices for "Copy from" feature
    const allDeviceNames = sensors.map(s => ({ deviceName: s.deviceName, friendlyName: s.friendlyName }));

    for (const sensor of sensors) {
      const matrix = sensor.matrix || {};
      const cells = this._getSelectedCells(sensor.deviceName);
      const selectionCount = cells.size;
      const editorValues = this._getEditorValues(sensor.deviceName);
      const controls = this._getControlEntities(sensor.deviceName);

      // Get current states for controls
      const powerState = this._hass.states[controls.power];
      const fanState = this._hass.states[controls.fan];
      const workDurState = this._hass.states[controls.workDuration];
      const pauseDurState = this._hass.states[controls.pauseDuration];
      
      const isPowerOn = powerState?.state === 'on';
      const isFanOn = fanState?.state === 'on';
      const workDurValue = workDurState?.state || '10';
      const pauseDurValue = pauseDurState?.state || '120';

      // Other devices for copy dropdown
      const otherDevices = allDeviceNames.filter(d => d.deviceName !== sensor.deviceName);

      // Status message for this device only
      const showStatus = this._statusMessage && (this._statusDevice === sensor.deviceName || this._statusDevice === null);

      // Get timer state for this device
      const timerState = this._getTimerState(sensor.deviceName);
      const isTimerRunning = !!timerState;
      const timedRunMinutes = this._getTimedRunMinutes(sensor.deviceName);

      html += `
        <ha-card>
          <div class="card-header">
            <div class="name">🌸 ${sensor.friendlyName} Diffuser</div>
          </div>
          <div class="card-content">
            
            <!-- ===== MANUAL CONTROLS SECTION ===== -->
            <div class="controls-section">
              <div class="section-title">Manual Controls</div>
              
              <!-- Power & Fan Row -->
              <div class="controls-row">
                <div class="control-item">
                  <button class="control-btn ${isPowerOn ? 'on' : 'off'}" 
                          data-action="toggle-power" data-entity="${controls.power}">
                    <span class="control-icon">${isPowerOn ? '⚡' : '○'}</span>
                    <span class="control-label">Power</span>
                    <span class="control-state">${isPowerOn ? 'ON' : 'OFF'}</span>
                  </button>
                </div>
                <div class="control-item">
                  <button class="control-btn ${isFanOn ? 'on' : 'off'}" 
                          data-action="toggle-fan" data-entity="${controls.fan}">
                    <span class="control-icon">${isFanOn ? '🌀' : '○'}</span>
                    <span class="control-label">Fan</span>
                    <span class="control-state">${isFanOn ? 'ON' : 'OFF'}</span>
                  </button>
                </div>
              </div>

              <!-- Work/Pause Settings Row -->
              <div class="controls-row settings-row">
                <div class="control-item duration-control">
                  <label>Work</label>
                  <input type="number" class="duration-input" data-entity="${controls.workDuration}" 
                         value="${workDurValue}" min="1" max="999">
                  <span class="unit">sec</span>
                </div>
                <div class="control-item duration-control">
                  <label>Pause</label>
                  <input type="number" class="duration-input" data-entity="${controls.pauseDuration}" 
                         value="${pauseDurValue}" min="1" max="9999">
                  <span class="unit">sec</span>
                </div>
              </div>

              <!-- Apply Settings and Run Section -->
              <div class="run-section">
                <div class="run-section-title">Apply Settings and...</div>
                
                ${isTimerRunning ? `
                  <!-- Timer Running State -->
                  <div class="timer-display">
                    <div class="timer-countdown">
                      <span class="timer-icon">⏱️</span>
                      <span class="timer-time">${this._formatCountdown(timerState.remainingSeconds)}</span>
                      <span class="timer-label">remaining</span>
                    </div>
                    <button class="cancel-timer-btn" data-action="cancel-timer" data-device="${sensor.deviceName}">
                      ✕ Cancel Timer
                    </button>
                  </div>
                ` : `
                  <!-- Run Buttons -->
                  <div class="run-buttons">
                    <button class="run-btn continuous" data-action="run-continuous" data-device="${sensor.deviceName}">
                      ▶ Run Continuously
                    </button>
                    <div class="timed-run-group">
                      <button class="run-btn timed" data-action="run-timed" data-device="${sensor.deviceName}">
                        ⏱ Run Timed
                      </button>
                      <div class="timed-input-group">
                        <input type="number" class="timed-minutes-input" data-device="${sensor.deviceName}"
                               value="${timedRunMinutes}" min="1" max="480" title="Minutes to run">
                        <span class="unit">min</span>
                      </div>
                    </div>
                  </div>
                `}
              </div>
            </div>
            
            <!-- ===== SCHEDULE SECTION ===== -->
            <div class="schedule-section">
              <div class="section-title">Weekly Schedule</div>
              <div class="instructions">
                Click cells to select • Click P1–P5 to select row • Edit below and save
              </div>
              
              <div class="quick-actions">
                <button class="chip-btn" data-action="select-all" data-device="${sensor.deviceName}">Select All</button>
                <button class="chip-btn" data-action="clear-selection" data-device="${sensor.deviceName}" ${selectionCount === 0 ? 'disabled' : ''}>
                  Clear ${selectionCount > 0 ? `(${selectionCount})` : ''}
                </button>
                <button class="chip-btn pull-btn" data-action="pull" data-device="${sensor.deviceName}">
                  ↓ Pull Aroma-Link App Schedule
                </button>
              </div>
              
              <!-- Color Legend -->
              <div class="legend">
                <span class="legend-item"><span class="legend-dot enabled"></span> Enabled</span>
                <span class="legend-item"><span class="legend-dot has-settings"></span> Disabled (has settings)</span>
                <span class="legend-item"><span class="legend-dot empty"></span> Empty</span>
                <span class="legend-item"><span class="legend-dot selected"></span> Selected</span>
              </div>

              <div class="schedule-grid" data-device="${sensor.deviceName}">
                <div class="grid-cell header corner"></div>
                ${dayLabels.map((d, idx) => {
                  const allProgsSelected = [1,2,3,4,5].every(p => cells.has(`${idx}-${p}`));
                  return `
                    <div class="grid-cell header day-header ${idx === todayIndex ? 'today' : ''} ${allProgsSelected ? 'col-selected' : ''}" 
                         data-action="select-day" data-day="${idx}" data-device="${sensor.deviceName}"
                         title="Click to select all programs for ${d}">
                      ${d}
                    </div>
                  `;
                }).join('')}
                
                ${programs.map(prog => {
                  const allDaysSelected = [0,1,2,3,4,5,6].every(d => cells.has(`${d}-${prog}`));
                  return `
                    <div class="grid-cell header program-label ${allDaysSelected ? 'row-selected' : ''}" 
                         data-action="select-row" data-program="${prog}" data-device="${sensor.deviceName}">
                      P${prog}
                    </div>
                    ${days.map((day, dayIdx) => {
                      const dayData = matrix[day] || {};
                      const progData = dayData[`program_${prog}`] || {};
                      const isEnabled = progData.enabled === true || progData.enabled === 1;
                      const startTime = (progData.start_time || progData.start || '00:00').substring(0, 5);
                      const endTime = (progData.end_time || progData.end || '23:59').substring(0, 5);
                      const level = progData.level || 'A';
                      const work = progData.work || progData.work_sec || 0;
                      const pause = progData.pause || progData.pause_sec || 0;
                      const isSelected = this._isCellSelected(sensor.deviceName, dayIdx, prog);
                      const isToday = dayIdx === todayIndex;
                      
                      // Check if cell has non-default settings
                      const hasSettings = startTime !== '00:00' || endTime !== '23:59' || work > 0 || pause > 0;
                      const cellClass = isEnabled ? 'enabled' : (hasSettings ? 'has-settings' : 'empty');
                      
                      return `
                        <div class="grid-cell schedule-cell ${cellClass} ${isSelected ? 'selected' : ''} ${isToday ? 'today-col' : ''}" 
                             data-action="toggle-cell" data-day="${dayIdx}" data-program="${prog}" data-device="${sensor.deviceName}">
                          ${isEnabled || hasSettings ? `
                            <span class="cell-time">${startTime}-${endTime}</span>
                            <span class="cell-meta">${work}/${pause} [L${level}]</span>
                          ` : '<span class="off-label">OFF</span>'}
                        </div>
                      `;
                    }).join('')}
                  `;
                }).join('')}
              </div>
              
              ${showStatus ? `
                <div class="status-message ${this._statusMessage.isError ? 'error' : 'success'}">
                  ${this._statusMessage.text}
                </div>
              ` : ''}
              
              <!-- Editor -->
              ${(() => {
                const multiProgSameDay = this._hasMultipleProgramsSameDay(sensor.deviceName);
                const timeDisabled = multiProgSameDay ? 'disabled' : '';
                const timeDisabledClass = multiProgSameDay ? 'time-disabled' : '';
                return `
              <div class="editor-section ${selectionCount === 0 ? 'disabled' : ''}" data-device="${sensor.deviceName}">
                <div class="editor-title">
                  ${selectionCount > 0 
                    ? `Editing ${selectionCount} Cell${selectionCount > 1 ? 's' : ''}` 
                    : 'Select cells above to edit'}
                </div>
                ${multiProgSameDay ? `
                  <div class="time-warning">
                    ⚠️ Multiple programs on same day selected - times locked (schedules can't overlap)
                  </div>
                ` : ''}
                
                <div class="editor-grid">
                  <div class="editor-row">
                    <label>Enabled</label>
                    <label class="toggle-switch">
                      <input type="checkbox" data-field="enabled" data-device="${sensor.deviceName}" ${editorValues.enabled ? 'checked' : ''}>
                      <span class="toggle-slider"></span>
                    </label>
                  </div>
                  
                  <div class="editor-row ${timeDisabledClass}">
                    <label>Start</label>
                    <input type="time" class="editor-input" data-field="startTime" data-device="${sensor.deviceName}" value="${editorValues.startTime}" ${timeDisabled}>
                  </div>
                  
                  <div class="editor-row ${timeDisabledClass}">
                    <label>End</label>
                    <input type="time" class="editor-input" data-field="endTime" data-device="${sensor.deviceName}" value="${editorValues.endTime}" ${timeDisabled}>
                  </div>
                  
                  <div class="editor-row">
                    <label>Work (sec)</label>
                    <input type="number" class="editor-input" data-field="workSec" data-device="${sensor.deviceName}" value="${editorValues.workSec}" min="1" max="999">
                  </div>
                  
                  <div class="editor-row">
                    <label>Pause (sec)</label>
                    <input type="number" class="editor-input" data-field="pauseSec" data-device="${sensor.deviceName}" value="${editorValues.pauseSec}" min="1" max="9999">
                  </div>
                  
                  <div class="editor-row">
                    <label>Level</label>
                    <select class="editor-input" data-field="level" data-device="${sensor.deviceName}">
                      <option value="A" ${editorValues.level === 'A' ? 'selected' : ''}>A (Light)</option>
                      <option value="B" ${editorValues.level === 'B' ? 'selected' : ''}>B (Medium)</option>
                      <option value="C" ${editorValues.level === 'C' ? 'selected' : ''}>C (Strong)</option>
                    </select>
                  </div>
                </div>`;
              })()}
                
                <div class="editor-buttons">
                  <button class="push-btn ${selectionCount === 0 || this._isSaving ? 'disabled' : ''}" 
                          data-action="save" data-device="${sensor.deviceName}">
                    ${this._isSaving ? '⏳ Pushing...' : '↑ Push to Aroma-Link App'}
                  </button>
                  <button class="clear-schedule-btn ${selectionCount === 0 || this._isSaving ? 'disabled' : ''}" 
                          data-action="clear-schedule" data-device="${sensor.deviceName}">
                    🗑 Clear Selected
                  </button>
                </div>
              </div>

              <!-- Copy Schedule Section -->
              ${otherDevices.length > 0 ? `
                <div class="copy-section">
                  <div class="copy-title">📋 Copy Schedule From</div>
                  <div class="copy-row">
                    <select class="copy-select" data-device="${sensor.deviceName}">
                      <option value="">Select a diffuser...</option>
                      ${otherDevices.map(d => `
                        <option value="${d.deviceName}">${d.friendlyName}</option>
                      `).join('')}
                    </select>
                    <button class="copy-btn ${this._isSaving ? 'disabled' : ''}" 
                            data-action="copy-schedule" data-device="${sensor.deviceName}">
                      Copy
                    </button>
                  </div>
                  <div class="copy-hint">Copies all 7 days × 5 programs from another diffuser</div>
                </div>
              ` : ''}
            </div>
            
          </div>
        </ha-card>
      `;
    }

    this.shadowRoot.innerHTML = html;
    this._attachEventListeners(sensors);
  }

  _attachEventListeners(sensors) {
    // Create a lookup for sensors by deviceName
    const sensorLookup = {};
    for (const s of sensors) {
      sensorLookup[s.deviceName] = s;
    }

    // Power toggle
    this.shadowRoot.querySelectorAll('[data-action="toggle-power"]').forEach(btn => {
      btn.addEventListener('click', () => this._toggleSwitch(btn.dataset.entity));
    });

    // Fan toggle
    this.shadowRoot.querySelectorAll('[data-action="toggle-fan"]').forEach(btn => {
      btn.addEventListener('click', () => this._toggleSwitch(btn.dataset.entity));
    });

    // Duration inputs
    this.shadowRoot.querySelectorAll('.duration-input').forEach(input => {
      input.addEventListener('change', (e) => {
        this._setNumber(input.dataset.entity, parseFloat(e.target.value));
      });
    });

    // Timed run minutes input
    this.shadowRoot.querySelectorAll('.timed-minutes-input').forEach(input => {
      input.addEventListener('change', (e) => {
        const deviceName = input.dataset.device;
        const minutes = Math.max(1, Math.min(480, parseInt(e.target.value) || 30));
        this._setTimedRunMinutes(deviceName, minutes);
      });
    });

    // Run Continuously button
    this.shadowRoot.querySelectorAll('[data-action="run-continuous"]').forEach(btn => {
      btn.addEventListener('click', () => {
        const deviceName = btn.dataset.device;
        const sensor = sensorLookup[deviceName];
        if (sensor) {
          const controls = this._getControlEntities(deviceName);
          this._runContinuously(deviceName, controls);
        }
      });
    });

    // Run Timed button
    this.shadowRoot.querySelectorAll('[data-action="run-timed"]').forEach(btn => {
      btn.addEventListener('click', () => {
        const deviceName = btn.dataset.device;
        const sensor = sensorLookup[deviceName];
        if (sensor) {
          const controls = this._getControlEntities(deviceName);
          const minutes = this._getTimedRunMinutes(deviceName);
          this._startTimedRun(deviceName, controls, minutes);
        }
      });
    });

    // Cancel Timer button
    this.shadowRoot.querySelectorAll('[data-action="cancel-timer"]').forEach(btn => {
      btn.addEventListener('click', () => {
        const deviceName = btn.dataset.device;
        const controls = this._getControlEntities(deviceName);
        this._stopTimedRun(deviceName, controls);
      });
    });

    // Cell clicks (per-device)
    this.shadowRoot.querySelectorAll('[data-action="toggle-cell"]').forEach(cell => {
      cell.addEventListener('click', () => {
        if (this._isSaving) return;
        const day = parseInt(cell.dataset.day);
        const program = parseInt(cell.dataset.program);
        const deviceName = cell.dataset.device;
        const sensor = sensorLookup[deviceName];
        this._toggleCell(deviceName, day, program, sensor);
      });
    });

    // Program row clicks (per-device)
    this.shadowRoot.querySelectorAll('[data-action="select-row"]').forEach(row => {
      row.addEventListener('click', () => {
        if (this._isSaving) return;
        const program = parseInt(row.dataset.program);
        const deviceName = row.dataset.device;
        this._selectProgramRow(deviceName, program);
      });
    });

    // Day column clicks (per-device)
    this.shadowRoot.querySelectorAll('[data-action="select-day"]').forEach(header => {
      header.addEventListener('click', () => {
        if (this._isSaving) return;
        const day = parseInt(header.dataset.day);
        const deviceName = header.dataset.device;
        this._selectDayColumn(deviceName, day);
      });
    });

    // Select all (per-device)
    this.shadowRoot.querySelectorAll('[data-action="select-all"]').forEach(btn => {
      btn.addEventListener('click', () => {
        if (this._isSaving) return;
        const deviceName = btn.dataset.device;
        this._selectAll(deviceName);
      });
    });

    // Clear selection (per-device)
    this.shadowRoot.querySelectorAll('[data-action="clear-selection"]').forEach(btn => {
      btn.addEventListener('click', () => {
        const deviceName = btn.dataset.device;
        this._clearSelection(deviceName);
      });
    });

    // Pull schedule (per-device)
    this.shadowRoot.querySelectorAll('[data-action="pull"]').forEach(btn => {
      btn.addEventListener('click', () => {
        const deviceName = btn.dataset.device;
        const sensor = sensorLookup[deviceName];
        if (sensor) this._pullSchedule(sensor);
      });
    });

    // Editor field changes (per-device)
    this.shadowRoot.querySelectorAll('[data-field]').forEach(input => {
      const field = input.dataset.field;
      const deviceName = input.dataset.device;
      const eventType = input.type === 'checkbox' ? 'change' : 'input';
      
      input.addEventListener(eventType, (e) => {
        const editorValues = this._getEditorValues(deviceName);
        if (input.type === 'checkbox') {
          editorValues[field] = e.target.checked;
        } else if (input.type === 'number') {
          editorValues[field] = parseInt(e.target.value) || 0;
        } else {
          editorValues[field] = e.target.value;
        }
      });
    });

    // Save button (per-device)
    this.shadowRoot.querySelectorAll('[data-action="save"]').forEach(btn => {
      btn.addEventListener('click', () => {
        if (!btn.classList.contains('disabled')) {
          const deviceName = btn.dataset.device;
          const sensor = sensorLookup[deviceName];
          if (sensor) this._saveSelectedCells(sensor);
        }
      });
    });

    // Clear schedule button (per-device)
    this.shadowRoot.querySelectorAll('[data-action="clear-schedule"]').forEach(btn => {
      btn.addEventListener('click', () => {
        if (!btn.classList.contains('disabled')) {
          const deviceName = btn.dataset.device;
          const sensor = sensorLookup[deviceName];
          if (sensor) this._clearSelectedSchedules(sensor);
        }
      });
    });

    // Copy schedule (per-device)
    this.shadowRoot.querySelectorAll('[data-action="copy-schedule"]').forEach(btn => {
      btn.addEventListener('click', () => {
        if (this._isSaving) return;
        const targetDeviceName = btn.dataset.device;
        const targetSensor = sensorLookup[targetDeviceName];
        
        // Find the selected source from the dropdown
        const selectEl = this.shadowRoot.querySelector(`.copy-select[data-device="${targetDeviceName}"]`);
        const sourceDeviceName = selectEl?.value;
        const sourceSensor = sourceDeviceName ? sensorLookup[sourceDeviceName] : null;
        
        if (targetSensor) {
          this._copyScheduleFrom(targetSensor, sourceSensor);
        }
      });
    });
  }

  _getStyles() {
    return `
      :host {
        --spacing: 12px;
        --radius: 12px;
        --radius-sm: 8px;
        --color-primary: var(--primary-color, #03a9f4);
        --color-success: #4caf50;
        --color-error: #f44336;
        --color-warning: #ff9800;
        --color-text: var(--primary-text-color, #212121);
        --color-text-secondary: var(--secondary-text-color, #757575);
        --color-bg: var(--card-background-color, #fff);
        --color-surface: rgba(0,0,0,0.04);
      }
      
      ha-card {
        border-radius: var(--ha-card-border-radius, var(--radius));
        overflow: hidden;
      }
      
      .card-header {
        padding: var(--spacing);
        background: var(--color-surface);
        border-bottom: 1px solid rgba(0,0,0,0.08);
      }
      
      .card-header .name {
        font-size: 1.1em;
        font-weight: 600;
        color: var(--color-text);
      }
      
      .card-content {
        padding: var(--spacing);
      }
      
      .loading, .no-devices {
        padding: 32px;
        text-align: center;
        color: var(--color-text-secondary);
      }
      
      /* ===== MANUAL CONTROLS ===== */
      .controls-section {
        margin-bottom: var(--spacing);
        padding-bottom: var(--spacing);
        border-bottom: 1px solid rgba(0,0,0,0.08);
      }
      
      .section-title {
        font-size: 0.8em;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        color: var(--color-text-secondary);
        margin-bottom: 10px;
      }
      
      .controls-grid {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        align-items: center;
      }
      
      .control-btn {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 12px 20px;
        border: none;
        border-radius: var(--radius-sm);
        cursor: pointer;
        transition: all 150ms ease;
        min-width: 70px;
      }
      
      .control-btn.off {
        background: var(--color-surface);
        color: var(--color-text-secondary);
      }
      
      .control-btn.on {
        background: var(--color-success);
        color: white;
      }
      
      .control-btn:hover {
        transform: scale(1.02);
        box-shadow: 0 2px 8px rgba(0,0,0,0.15);
      }
      
      .control-btn:active {
        transform: scale(0.98);
      }
      
      .control-icon {
        font-size: 1.4em;
        margin-bottom: 4px;
      }
      
      .control-label {
        font-size: 0.7em;
        font-weight: 600;
        text-transform: uppercase;
      }
      
      .control-state {
        font-size: 0.65em;
        opacity: 0.8;
      }
      
      .duration-control {
        display: flex;
        align-items: center;
        gap: 6px;
      }
      
      .duration-control label {
        font-size: 0.75em;
        color: var(--color-text-secondary);
        font-weight: 500;
      }
      
      .duration-input {
        width: 60px;
        padding: 8px;
        border: 1px solid rgba(0,0,0,0.12);
        border-radius: var(--radius-sm);
        font-size: 0.9em;
        text-align: center;
      }
      
      .duration-control .unit {
        font-size: 0.7em;
        color: var(--color-text-secondary);
      }

      /* Controls layout */
      .controls-row {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        align-items: center;
        margin-bottom: 12px;
      }

      .settings-row {
        padding: 10px 12px;
        background: var(--color-surface);
        border-radius: var(--radius-sm);
      }

      /* Run Section */
      .run-section {
        margin-top: 12px;
        padding: 12px;
        background: linear-gradient(135deg, rgba(3, 169, 244, 0.08), rgba(76, 175, 80, 0.08));
        border-radius: var(--radius-sm);
        border: 1px solid rgba(0,0,0,0.06);
      }

      .run-section-title {
        font-size: 0.75em;
        font-weight: 600;
        color: var(--color-text-secondary);
        margin-bottom: 10px;
        text-transform: uppercase;
        letter-spacing: 0.3px;
      }

      .run-buttons {
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
        align-items: stretch;
      }

      .run-btn {
        padding: 12px 20px;
        border: none;
        border-radius: var(--radius-sm);
        font-weight: 600;
        font-size: 0.85em;
        cursor: pointer;
        transition: all 150ms ease;
        display: flex;
        align-items: center;
        gap: 6px;
      }

      .run-btn.continuous {
        background: var(--color-success);
        color: white;
        flex: 1;
        justify-content: center;
      }

      .run-btn.timed {
        background: var(--color-primary);
        color: white;
      }

      .run-btn:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.2);
      }

      .run-btn:active {
        transform: translateY(0);
      }

      .timed-run-group {
        display: flex;
        flex: 1;
        gap: 8px;
        align-items: center;
      }

      .timed-input-group {
        display: flex;
        align-items: center;
        gap: 4px;
        background: white;
        padding: 4px 8px;
        border-radius: var(--radius-sm);
        border: 1px solid rgba(0,0,0,0.12);
      }

      .timed-minutes-input {
        width: 50px;
        padding: 6px;
        border: none;
        font-size: 0.9em;
        text-align: center;
        background: transparent;
      }

      .timed-minutes-input:focus {
        outline: none;
      }

      .timed-input-group .unit {
        font-size: 0.75em;
        color: var(--color-text-secondary);
      }

      /* Timer Display */
      .timer-display {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        padding: 8px;
        background: linear-gradient(135deg, rgba(255, 152, 0, 0.15), rgba(255, 87, 34, 0.15));
        border-radius: var(--radius-sm);
        border: 1px solid var(--color-warning);
      }

      .timer-countdown {
        display: flex;
        align-items: center;
        gap: 8px;
      }

      .timer-icon {
        font-size: 1.5em;
        animation: pulse 1s ease-in-out infinite;
      }

      @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
      }

      .timer-time {
        font-size: 1.8em;
        font-weight: 700;
        font-family: 'SF Mono', 'Monaco', 'Inconsolata', monospace;
        color: var(--color-warning);
        letter-spacing: 1px;
      }

      .timer-label {
        font-size: 0.75em;
        color: var(--color-text-secondary);
        font-weight: 500;
      }

      .cancel-timer-btn {
        padding: 8px 16px;
        background: var(--color-error);
        color: white;
        border: none;
        border-radius: var(--radius-sm);
        font-size: 0.8em;
        font-weight: 600;
        cursor: pointer;
        transition: all 150ms;
      }

      .cancel-timer-btn:hover {
        background: #d32f2f;
        box-shadow: 0 2px 8px rgba(0,0,0,0.2);
      }
      
      /* ===== SCHEDULE SECTION ===== */
      .schedule-section {
        /* container */
      }
      
      .instructions {
        font-size: 0.75em;
        color: var(--color-text-secondary);
        margin-bottom: 10px;
      }
      
      .quick-actions {
        display: flex;
        gap: 8px;
        margin-bottom: var(--spacing);
        flex-wrap: wrap;
      }
      
      .chip-btn {
        padding: 6px 14px;
        border: none;
        border-radius: 20px;
        background: var(--color-surface);
        color: var(--color-text);
        font-size: 0.75em;
        font-weight: 500;
        cursor: pointer;
        transition: all 150ms ease;
      }
      
      .chip-btn:hover:not(:disabled) {
        background: rgba(var(--rgb-primary-color, 3, 169, 244), 0.15);
        color: var(--color-primary);
      }
      
      .chip-btn:disabled {
        opacity: 0.4;
        cursor: not-allowed;
      }
      
      .chip-btn.pull-btn {
        margin-left: auto;
        background: rgba(var(--rgb-primary-color, 3, 169, 244), 0.1);
        color: var(--color-primary);
      }

      /* ===== LEGEND ===== */
      .legend {
        display: flex;
        flex-wrap: wrap;
        gap: 12px;
        margin-bottom: 10px;
        font-size: 0.7em;
        color: var(--color-text-secondary);
      }

      .legend-item {
        display: flex;
        align-items: center;
        gap: 4px;
      }

      .legend-dot {
        width: 12px;
        height: 12px;
        border-radius: 3px;
        border: 1px solid rgba(0,0,0,0.1);
      }

      .legend-dot.enabled {
        background: rgba(76, 175, 80, 0.3);
        border-color: rgba(76, 175, 80, 0.5);
      }

      .legend-dot.has-settings {
        background: rgba(158, 158, 158, 0.3);
        border-color: rgba(158, 158, 158, 0.5);
      }

      .legend-dot.empty {
        background: var(--color-surface);
        border-color: rgba(0,0,0,0.1);
      }

      .legend-dot.selected {
        background: rgba(3, 169, 244, 0.3);
        border-color: var(--color-primary);
      }
      
      /* ===== SCHEDULE GRID ===== */
      .schedule-grid {
        display: grid;
        grid-template-columns: 30px repeat(7, 1fr);
        gap: 3px;
        margin-bottom: var(--spacing);
      }
      
      .grid-cell {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 6px 4px;
        border-radius: 6px;
        min-height: clamp(52px, 8vw, 68px);
        transition: all 150ms ease;
        text-align: center;
      }
      
      .grid-cell.header {
        background: var(--color-surface);
        color: var(--color-text-secondary);
        font-weight: 600;
        font-size: 0.7em;
        min-height: 26px;
        text-transform: uppercase;
      }
      
      .grid-cell.header.today {
        background: var(--color-warning);
        color: white;
      }
      
      .grid-cell.corner {
        background: transparent;
      }
      
      .grid-cell.program-label,
      .grid-cell.day-header {
        cursor: pointer;
        user-select: none;
      }
      
      .grid-cell.program-label:hover,
      .grid-cell.day-header:hover {
        background: rgba(var(--rgb-primary-color, 3, 169, 244), 0.15);
        color: var(--color-primary);
      }

      .grid-cell.day-header.col-selected {
        background: rgba(3, 169, 244, 0.2);
        color: var(--color-primary);
        box-shadow: inset 0 0 0 2px var(--color-primary);
      }

      .grid-cell.day-header.today.col-selected {
        background: rgba(255, 152, 0, 0.4);
      }
      
      .grid-cell.program-label.row-selected {
        background: rgba(var(--rgb-primary-color, 3, 169, 244), 0.2);
        color: var(--color-primary);
        box-shadow: inset 0 0 0 2px var(--color-primary);
      }
      
      /* Schedule cells */
      .schedule-cell {
        cursor: pointer;
        user-select: none;
        border: 2px solid transparent;
      }
      
      .schedule-cell.empty {
        background: var(--color-surface);
        color: var(--color-text-secondary);
      }

      .schedule-cell.has-settings {
        background: rgba(158, 158, 158, 0.2);
        border-color: rgba(158, 158, 158, 0.4);
        color: var(--color-text-secondary);
      }
      
      .schedule-cell.enabled {
        background: rgba(76, 175, 80, 0.15);
        border-color: rgba(76, 175, 80, 0.4);
        color: var(--color-text);
      }
      
      .schedule-cell.today-col {
        background: rgba(255, 152, 0, 0.08);
      }
      
      .schedule-cell.today-col.enabled {
        background: rgba(76, 175, 80, 0.2);
      }

      .schedule-cell.today-col.has-settings {
        background: rgba(158, 158, 158, 0.25);
      }
      
      .schedule-cell.selected {
        background: rgba(3, 169, 244, 0.2) !important;
        border-color: var(--color-primary) !important;
        box-shadow: 0 0 0 2px var(--color-primary);
      }
      
      .schedule-cell:hover {
        transform: scale(1.04);
        box-shadow: 0 2px 8px rgba(0,0,0,0.12);
        z-index: 1;
      }
      
      .schedule-cell .cell-time {
        font-weight: 700;
        font-size: clamp(0.65rem, 1.8vw, 0.85rem);
        line-height: 1.2;
        white-space: nowrap;
        letter-spacing: -0.3px;
      }
      
      .schedule-cell .cell-meta {
        font-size: clamp(0.55rem, 1.5vw, 0.75rem);
        opacity: 0.75;
        margin-top: 2px;
        font-weight: 500;
        white-space: nowrap;
      }
      
      .schedule-cell .off-label {
        font-weight: 600;
        font-size: clamp(0.6rem, 1.6vw, 0.8rem);
        opacity: 0.5;
        text-transform: uppercase;
      }
      
      /* ===== STATUS MESSAGE ===== */
      .status-message {
        padding: 10px 14px;
        border-radius: var(--radius-sm);
        margin-bottom: var(--spacing);
        font-size: 0.85em;
        font-weight: 500;
        animation: slideIn 200ms ease;
      }
      
      @keyframes slideIn {
        from { opacity: 0; transform: translateY(-8px); }
        to { opacity: 1; transform: translateY(0); }
      }
      
      .status-message.success {
        background: rgba(76, 175, 80, 0.12);
        color: #2e7d32;
      }
      
      .status-message.error {
        background: rgba(244, 67, 54, 0.12);
        color: #c62828;
      }
      
      /* ===== EDITOR ===== */
      .editor-section {
        background: var(--color-surface);
        border-radius: var(--radius-sm);
        padding: var(--spacing);
        transition: opacity 200ms;
      }
      
      .editor-section.disabled {
        opacity: 0.5;
        pointer-events: none;
      }
      
      .editor-title {
        font-weight: 600;
        margin-bottom: 12px;
        font-size: 0.9em;
      }

      .time-warning {
        background: rgba(255, 152, 0, 0.15);
        border: 1px solid var(--color-warning);
        border-radius: var(--radius-sm);
        padding: 8px 12px;
        margin-bottom: 12px;
        font-size: 0.75em;
        color: #e65100;
        line-height: 1.4;
      }

      .editor-row.time-disabled {
        opacity: 0.4;
        pointer-events: none;
      }

      .editor-row.time-disabled input {
        background: rgba(0,0,0,0.05);
        cursor: not-allowed;
      }
      
      .editor-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
        gap: 12px;
        margin-bottom: 12px;
      }
      
      .editor-row {
        display: flex;
        flex-direction: column;
        gap: 4px;
      }
      
      .editor-row > label:first-child {
        font-size: 0.7em;
        color: var(--color-text-secondary);
        font-weight: 600;
        text-transform: uppercase;
      }
      
      .editor-input {
        padding: 8px 10px;
        border: 1px solid rgba(0,0,0,0.12);
        border-radius: var(--radius-sm);
        background: var(--color-bg);
        font-size: 0.9em;
        width: 100%;
        box-sizing: border-box;
      }
      
      .editor-input:focus {
        outline: none;
        border-color: var(--color-primary);
        box-shadow: 0 0 0 2px rgba(3, 169, 244, 0.2);
      }
      
      /* Toggle */
      .toggle-switch {
        position: relative;
        display: inline-block;
        width: 44px;
        height: 22px;
      }
      
      .toggle-switch input {
        opacity: 0;
        width: 0;
        height: 0;
      }
      
      .toggle-slider {
        position: absolute;
        cursor: pointer;
        inset: 0;
        background: rgba(0,0,0,0.2);
        transition: background 200ms;
        border-radius: 22px;
      }
      
      .toggle-slider:before {
        position: absolute;
        content: "";
        height: 16px;
        width: 16px;
        left: 3px;
        bottom: 3px;
        background: white;
        transition: transform 200ms;
        border-radius: 50%;
        box-shadow: 0 1px 3px rgba(0,0,0,0.3);
      }
      
      .toggle-switch input:checked + .toggle-slider {
        background: var(--color-success);
      }
      
      .toggle-switch input:checked + .toggle-slider:before {
        transform: translateX(22px);
      }
      
      /* Save button */
      .editor-buttons {
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
        margin-top: 12px;
      }

      .push-btn, .clear-schedule-btn {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 8px 16px;
        border: none;
        border-radius: 20px;
        font-size: 0.8em;
        font-weight: 600;
        cursor: pointer;
        transition: all 150ms;
      }

      .push-btn {
        background: var(--color-success);
        color: white;
      }
      
      .push-btn:hover:not(.disabled) {
        transform: translateY(-1px);
        box-shadow: 0 3px 10px rgba(76, 175, 80, 0.3);
      }

      .clear-schedule-btn {
        background: var(--color-error);
        color: white;
      }
      
      .clear-schedule-btn:hover:not(.disabled) {
        transform: translateY(-1px);
        box-shadow: 0 3px 10px rgba(244, 67, 54, 0.3);
      }
      
      .push-btn.disabled, .clear-schedule-btn.disabled {
        background: rgba(0,0,0,0.12);
        color: var(--color-text-secondary);
        cursor: not-allowed;
      }

      /* ===== COPY SECTION ===== */
      .copy-section {
        margin-top: var(--spacing);
        padding-top: var(--spacing);
        border-top: 1px dashed rgba(0,0,0,0.12);
      }

      .copy-title {
        font-size: 0.85em;
        font-weight: 600;
        color: var(--color-text);
        margin-bottom: 8px;
      }

      .copy-row {
        display: flex;
        gap: 8px;
        align-items: center;
      }

      .copy-select {
        flex: 1;
        padding: 10px 12px;
        border: 1px solid rgba(0,0,0,0.12);
        border-radius: var(--radius-sm);
        background: var(--color-bg);
        font-size: 0.9em;
        color: var(--color-text);
        cursor: pointer;
      }

      .copy-select:focus {
        outline: none;
        border-color: var(--color-primary);
      }

      .copy-btn {
        padding: 10px 18px;
        background: var(--color-primary);
        color: white;
        border: none;
        border-radius: var(--radius-sm);
        font-size: 0.85em;
        font-weight: 600;
        cursor: pointer;
        transition: all 150ms;
        white-space: nowrap;
      }

      .copy-btn:hover:not(.disabled) {
        box-shadow: 0 2px 8px rgba(0,0,0,0.2);
        transform: scale(1.02);
      }

      .copy-btn.disabled {
        background: rgba(0,0,0,0.12);
        color: var(--color-text-secondary);
        cursor: not-allowed;
      }

      .copy-hint {
        font-size: 0.7em;
        color: var(--color-text-secondary);
        margin-top: 6px;
        font-style: italic;
      }
    `;
  }

  getCardSize() {
    return 8;
  }

  static getConfigElement() {
    return document.createElement('aroma-link-schedule-card-editor');
  }

  static getStubConfig() {
    return {};
  }
}

class AromaLinkScheduleCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = config || {};
    this.render();
  }

  render() {
    this.innerHTML = `
      <style>
        .editor { padding: 16px; }
        .row { margin-bottom: 12px; }
        label { display: block; margin-bottom: 4px; font-weight: 500; }
        input[type="text"] { width: 100%; padding: 8px; box-sizing: border-box; }
      </style>
      <div class="editor">
        <div class="row">
          <label for="device">Device filter (optional)</label>
          <input type="text" id="device" value="${this._config.device || ''}" 
                 placeholder="e.g., main_house (leave empty for all)">
        </div>
      </div>
    `;

    this.querySelector('#device').addEventListener('change', (e) => {
      this._config = { ...this._config, device: e.target.value || undefined };
      this._fireEvent();
    });
  }

  _fireEvent() {
    this.dispatchEvent(new CustomEvent('config-changed', {
      detail: { config: this._config },
      bubbles: true,
      composed: true
    }));
  }
}

customElements.define('aroma-link-schedule-card', AromaLinkScheduleCard);
customElements.define('aroma-link-schedule-card-editor', AromaLinkScheduleCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: 'aroma-link-schedule-card',
  name: 'Aroma-Link Schedule',
  description: 'Complete dashboard card for Aroma-Link diffusers with controls and scheduling',
  preview: true,
  documentationURL: 'https://github.com/cjam28/ha_aromalink'
});

console.info('%c AROMA-LINK-SCHEDULE-CARD %c v1.9.0 ', 
  'color: white; background: #03a9f4; font-weight: bold;',
  'color: #03a9f4; background: white; font-weight: bold;'
);
