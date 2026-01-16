/**
 * Aroma-Link Schedule Card v1.7.0
 * 
 * A complete dashboard card for Aroma-Link diffusers including:
 * - Manual controls (Power, Fan, Run)
 * - Schedule matrix with multi-cell editing
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
    this._selectedCells = new Set();
    this._isSaving = false;
    this._statusMessage = null;
    this._editorValues = {
      enabled: true,
      startTime: '09:00',
      endTime: '21:00',
      workSec: 10,
      pauseSec: 120,
      level: 'A'
    };
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

  _isCellSelected(day, program) {
    return this._selectedCells.has(`${day}-${program}`);
  }

  _toggleCell(day, program) {
    const key = `${day}-${program}`;
    if (this._selectedCells.has(key)) {
      this._selectedCells.delete(key);
    } else {
      this._selectedCells.add(key);
    }
    this._editorLoaded = false;
    this.render();
  }

  _selectProgramRow(program) {
    const allSelected = [0,1,2,3,4,5,6].every(day => this._selectedCells.has(`${day}-${program}`));
    
    if (allSelected) {
      for (let day = 0; day < 7; day++) {
        this._selectedCells.delete(`${day}-${program}`);
      }
    } else {
      for (let day = 0; day < 7; day++) {
        this._selectedCells.add(`${day}-${program}`);
      }
    }
    this._editorLoaded = false;
    this.render();
  }

  _selectAll() {
    for (let day = 0; day < 7; day++) {
      for (let prog = 1; prog <= 5; prog++) {
        this._selectedCells.add(`${day}-${prog}`);
      }
    }
    this._editorLoaded = false;
    this.render();
  }

  _clearSelection() {
    this._selectedCells.clear();
    this.render();
  }

  _loadSelectedIntoEditor(sensor) {
    if (this._selectedCells.size === 0) return;
    
    const firstKey = Array.from(this._selectedCells)[0];
    const [day, program] = firstKey.split('-').map(Number);
    const days = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday'];
    const dayName = days[day];
    
    const matrix = sensor.matrix || {};
    const dayData = matrix[dayName] || {};
    const progData = dayData[`program_${program}`] || {};
    
    this._editorValues = {
      enabled: progData.enabled === true || progData.enabled === 1,
      startTime: (progData.start_time || progData.start || '09:00').substring(0, 5),
      endTime: (progData.end_time || progData.end || '21:00').substring(0, 5),
      workSec: progData.work || progData.work_sec || 10,
      pauseSec: progData.pause || progData.pause_sec || 120,
      level: progData.level || 'A'
    };
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
    
    const newStartMin = this._timeToMinutes(newStart);
    const newEndMin = this._timeToMinutes(newEnd);
    
    const overlaps = [];
    
    for (let prog = 1; prog <= 5; prog++) {
      if (prog === programToUpdate) continue;
      if (this._selectedCells.has(`${day}-${prog}`)) continue;
      
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

  _showStatus(message, isError = false) {
    this._statusMessage = { text: message, isError };
    this.render();
    
    setTimeout(() => {
      this._statusMessage = null;
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

  async _saveSelectedCells(sensor) {
    if (this._selectedCells.size === 0) {
      this._showStatus('No cells selected. Click cells in the grid to select them.', true);
      return;
    }

    if (!this._isValidTime(this._editorValues.startTime)) {
      this._showStatus('Invalid start time. Use HH:MM format (e.g., 09:00)', true);
      return;
    }
    if (!this._isValidTime(this._editorValues.endTime)) {
      this._showStatus('Invalid end time. Use HH:MM format (e.g., 21:00)', true);
      return;
    }

    const startMin = this._timeToMinutes(this._editorValues.startTime);
    const endMin = this._timeToMinutes(this._editorValues.endTime);
    if (endMin <= startMin) {
      this._showStatus('End time must be after start time.', true);
      return;
    }

    const daySelections = {};
    for (const key of this._selectedCells) {
      const [day, program] = key.split('-').map(Number);
      if (!daySelections[day]) daySelections[day] = [];
      daySelections[day].push(program);
    }

    if (this._editorValues.enabled) {
      const dayNames = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
      const overlapDays = [];
      
      for (const [dayStr, programs] of Object.entries(daySelections)) {
        const day = parseInt(dayStr);
        for (const program of programs) {
          const overlaps = this._checkOverlaps(
            sensor, day, program,
            this._editorValues.startTime,
            this._editorValues.endTime
          );
          if (overlaps.length > 0 && !overlapDays.includes(dayNames[day])) {
            overlapDays.push(dayNames[day]);
          }
        }
      }

      if (overlapDays.length > 0) {
        this._showStatus(`Schedules in ${overlapDays.join(', ')} are overlapping. Please correct the times.`, true);
        return;
      }
    }

    const deviceId = sensor.deviceId;
    if (!deviceId) {
      this._showStatus('Device ID not found. Cannot save.', true);
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
            await this._hass.callService('switch', this._editorValues.enabled ? 'turn_on' : 'turn_off', {
              entity_id: enabledEntity
            });
          }
          
          const startEntity = `text.${prefix}_program_start_time`;
          if (this._hass.states[startEntity]) {
            await this._hass.callService('text', 'set_value', {
              entity_id: startEntity,
              value: this._editorValues.startTime
            });
          }
          
          const endEntity = `text.${prefix}_program_end_time`;
          if (this._hass.states[endEntity]) {
            await this._hass.callService('text', 'set_value', {
              entity_id: endEntity,
              value: this._editorValues.endTime
            });
          }
          
          const workEntity = `number.${prefix}_program_work_time`;
          if (this._hass.states[workEntity]) {
            await this._hass.callService('number', 'set_value', {
              entity_id: workEntity,
              value: this._editorValues.workSec
            });
          }
          
          const pauseEntity = `number.${prefix}_program_pause_time`;
          if (this._hass.states[pauseEntity]) {
            await this._hass.callService('number', 'set_value', {
              entity_id: pauseEntity,
              value: this._editorValues.pauseSec
            });
          }
          
          const levelEntity = `select.${prefix}_program_level`;
          if (this._hass.states[levelEntity]) {
            await this._hass.callService('select', 'select_option', {
              entity_id: levelEntity,
              option: `Level ${this._editorValues.level}`
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
      this._selectedCells.clear();
      this._showStatus(`✓ Saved ${Object.values(daySelections).flat().length} schedule(s) to Aroma-Link`);
      
    } catch (error) {
      console.error('Error saving schedules:', error);
      this._isSaving = false;
      this._showStatus('Error saving schedules. Check console for details.', true);
    }
  }

  async _pullSchedule(sensor) {
    this._showStatus('Pulling schedule from Aroma-Link...');
    
    const syncButton = `button.${sensor.deviceName}_sync_schedules`;
    if (this._hass.states[syncButton]) {
      await this._hass.callService('button', 'press', { entity_id: syncButton });
    } else {
      await this._hass.callService('aroma_link_integration', 'refresh_all_schedules', {
        device_id: sensor.deviceId
      });
    }
    
    setTimeout(() => {
      this._showStatus('✓ Schedule refreshed from Aroma-Link');
    }, 1000);
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

    for (const sensor of sensors) {
      const matrix = sensor.matrix || {};
      const selectionCount = this._selectedCells.size;
      const controls = this._getControlEntities(sensor.deviceName);

      if (selectionCount > 0 && !this._editorLoaded) {
        this._loadSelectedIntoEditor(sensor);
        this._editorLoaded = true;
      }

      // Get current states for controls
      const powerState = this._hass.states[controls.power];
      const fanState = this._hass.states[controls.fan];
      const workDurState = this._hass.states[controls.workDuration];
      const pauseDurState = this._hass.states[controls.pauseDuration];
      
      const isPowerOn = powerState?.state === 'on';
      const isFanOn = fanState?.state === 'on';
      const workDurValue = workDurState?.state || '10';
      const pauseDurValue = pauseDurState?.state || '120';

      html += `
        <ha-card>
          <div class="card-header">
            <div class="name">🌸 ${sensor.friendlyName} Diffuser</div>
          </div>
          <div class="card-content">
            
            <!-- ===== MANUAL CONTROLS SECTION ===== -->
            <div class="controls-section">
              <div class="section-title">Manual Controls</div>
              <div class="controls-grid">
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
                <div class="control-item">
                  <button class="run-btn" data-action="run" data-entity="${controls.run}">
                    ▶ Run Now
                  </button>
                </div>
              </div>
            </div>
            
            <!-- ===== SCHEDULE SECTION ===== -->
            <div class="schedule-section">
              <div class="section-title">Weekly Schedule</div>
              <div class="instructions">
                Click cells to select • Click P1–P5 to select row • Edit below and save
              </div>
              
              <div class="quick-actions">
                <button class="chip-btn" data-action="select-all">Select All</button>
                <button class="chip-btn" data-action="clear-selection" ${selectionCount === 0 ? 'disabled' : ''}>
                  Clear ${selectionCount > 0 ? `(${selectionCount})` : ''}
                </button>
                <button class="chip-btn pull-btn" data-action="pull" data-device="${sensor.deviceName}">
                  ↓ Pull Schedule
                </button>
              </div>
              
              <div class="schedule-grid">
                <div class="grid-cell header corner"></div>
                ${dayLabels.map((d, idx) => `
                  <div class="grid-cell header ${idx === todayIndex ? 'today' : ''}">${d}</div>
                `).join('')}
                
                ${programs.map(prog => {
                  const allDaysSelected = [0,1,2,3,4,5,6].every(d => this._selectedCells.has(`${d}-${prog}`));
                  return `
                    <div class="grid-cell header program-label ${allDaysSelected ? 'row-selected' : ''}" 
                         data-action="select-row" data-program="${prog}">
                      P${prog}
                    </div>
                    ${days.map((day, dayIdx) => {
                      const dayData = matrix[day] || {};
                      const progData = dayData[`program_${prog}`] || {};
                      const isEnabled = progData.enabled === true || progData.enabled === 1;
                      const startTime = (progData.start_time || progData.start || '--:--').substring(0, 5);
                      const endTime = (progData.end_time || progData.end || '--:--').substring(0, 5);
                      const level = progData.level || 'A';
                      const work = progData.work || progData.work_sec || 0;
                      const pause = progData.pause || progData.pause_sec || 0;
                      const isSelected = this._isCellSelected(dayIdx, prog);
                      const isToday = dayIdx === todayIndex;
                      
                      return `
                        <div class="grid-cell schedule-cell ${isEnabled ? 'enabled' : 'disabled'} ${isSelected ? 'selected' : ''} ${isToday ? 'today-col' : ''}" 
                             data-action="toggle-cell" data-day="${dayIdx}" data-program="${prog}">
                          ${isEnabled ? `
                            <span class="time">${startTime}</span>
                            <span class="time">${endTime}</span>
                            <span class="meta">${work}/${pause} [L${level}]</span>
                          ` : '<span class="off-label">OFF</span>'}
                        </div>
                      `;
                    }).join('')}
                  `;
                }).join('')}
              </div>
              
              ${this._statusMessage ? `
                <div class="status-message ${this._statusMessage.isError ? 'error' : 'success'}">
                  ${this._statusMessage.text}
                </div>
              ` : ''}
              
              <!-- Editor -->
              <div class="editor-section ${selectionCount === 0 ? 'disabled' : ''}">
                <div class="editor-title">
                  ${selectionCount > 0 
                    ? `Editing ${selectionCount} Cell${selectionCount > 1 ? 's' : ''}` 
                    : 'Select cells above to edit'}
                </div>
                
                <div class="editor-grid">
                  <div class="editor-row">
                    <label>Enabled</label>
                    <label class="toggle-switch">
                      <input type="checkbox" data-field="enabled" ${this._editorValues.enabled ? 'checked' : ''}>
                      <span class="toggle-slider"></span>
                    </label>
                  </div>
                  
                  <div class="editor-row">
                    <label>Start</label>
                    <input type="time" class="editor-input" data-field="startTime" value="${this._editorValues.startTime}">
                  </div>
                  
                  <div class="editor-row">
                    <label>End</label>
                    <input type="time" class="editor-input" data-field="endTime" value="${this._editorValues.endTime}">
                  </div>
                  
                  <div class="editor-row">
                    <label>Work (sec)</label>
                    <input type="number" class="editor-input" data-field="workSec" value="${this._editorValues.workSec}" min="1" max="999">
                  </div>
                  
                  <div class="editor-row">
                    <label>Pause (sec)</label>
                    <input type="number" class="editor-input" data-field="pauseSec" value="${this._editorValues.pauseSec}" min="1" max="9999">
                  </div>
                  
                  <div class="editor-row">
                    <label>Level</label>
                    <select class="editor-input" data-field="level">
                      <option value="A" ${this._editorValues.level === 'A' ? 'selected' : ''}>A (Light)</option>
                      <option value="B" ${this._editorValues.level === 'B' ? 'selected' : ''}>B (Medium)</option>
                      <option value="C" ${this._editorValues.level === 'C' ? 'selected' : ''}>C (Strong)</option>
                    </select>
                  </div>
                </div>
                
                <button class="save-btn ${selectionCount === 0 || this._isSaving ? 'disabled' : ''}" 
                        data-action="save" data-device="${sensor.deviceName}">
                  ${this._isSaving ? '⏳ Saving...' : '💾 Save to Aroma-Link'}
                </button>
              </div>
            </div>
            
          </div>
        </ha-card>
      `;
    }

    this.shadowRoot.innerHTML = html;
    this._attachEventListeners(sensors[0]);
  }

  _attachEventListeners(sensor) {
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

    // Run button
    this.shadowRoot.querySelectorAll('[data-action="run"]').forEach(btn => {
      btn.addEventListener('click', () => this._pressButton(btn.dataset.entity));
    });

    // Cell clicks
    this.shadowRoot.querySelectorAll('[data-action="toggle-cell"]').forEach(cell => {
      cell.addEventListener('click', () => {
        if (this._isSaving) return;
        const day = parseInt(cell.dataset.day);
        const program = parseInt(cell.dataset.program);
        this._toggleCell(day, program);
      });
    });

    // Program row clicks
    this.shadowRoot.querySelectorAll('[data-action="select-row"]').forEach(row => {
      row.addEventListener('click', () => {
        if (this._isSaving) return;
        const program = parseInt(row.dataset.program);
        this._selectProgramRow(program);
      });
    });

    // Select all
    this.shadowRoot.querySelectorAll('[data-action="select-all"]').forEach(btn => {
      btn.addEventListener('click', () => {
        if (this._isSaving) return;
        this._selectAll();
      });
    });

    // Clear selection
    this.shadowRoot.querySelectorAll('[data-action="clear-selection"]').forEach(btn => {
      btn.addEventListener('click', () => this._clearSelection());
    });

    // Pull schedule
    this.shadowRoot.querySelectorAll('[data-action="pull"]').forEach(btn => {
      btn.addEventListener('click', () => this._pullSchedule(sensor));
    });

    // Editor field changes
    this.shadowRoot.querySelectorAll('[data-field]').forEach(input => {
      const field = input.dataset.field;
      const eventType = input.type === 'checkbox' ? 'change' : 'input';
      
      input.addEventListener(eventType, (e) => {
        if (input.type === 'checkbox') {
          this._editorValues[field] = e.target.checked;
        } else if (input.type === 'number') {
          this._editorValues[field] = parseInt(e.target.value) || 0;
        } else {
          this._editorValues[field] = e.target.value;
        }
      });
    });

    // Save button
    this.shadowRoot.querySelectorAll('[data-action="save"]').forEach(btn => {
      btn.addEventListener('click', () => {
        if (!btn.classList.contains('disabled')) {
          this._saveSelectedCells(sensor);
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
      
      .run-btn {
        padding: 12px 20px;
        background: var(--color-primary);
        color: white;
        border: none;
        border-radius: var(--radius-sm);
        font-weight: 600;
        cursor: pointer;
        transition: all 150ms ease;
      }
      
      .run-btn:hover {
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
        padding: 4px 2px;
        border-radius: 6px;
        font-size: 0.65em;
        min-height: 48px;
        transition: all 150ms ease;
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
      
      .grid-cell.program-label {
        cursor: pointer;
        user-select: none;
      }
      
      .grid-cell.program-label:hover {
        background: rgba(var(--rgb-primary-color, 3, 169, 244), 0.15);
        color: var(--color-primary);
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
      
      .schedule-cell.disabled {
        background: var(--color-surface);
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
      
      .schedule-cell .time {
        font-weight: 600;
        line-height: 1.3;
      }
      
      .schedule-cell .meta {
        font-size: 0.85em;
        opacity: 0.7;
        margin-top: 2px;
      }
      
      .schedule-cell .off-label {
        font-weight: 500;
        opacity: 0.5;
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
      .save-btn {
        width: 100%;
        padding: 12px;
        background: var(--color-success);
        color: white;
        border: none;
        border-radius: var(--radius-sm);
        font-size: 0.9em;
        font-weight: 600;
        cursor: pointer;
        transition: all 150ms;
      }
      
      .save-btn:hover:not(.disabled) {
        box-shadow: 0 2px 8px rgba(0,0,0,0.2);
      }
      
      .save-btn.disabled {
        background: rgba(0,0,0,0.12);
        color: var(--color-text-secondary);
        cursor: not-allowed;
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

console.info('%c AROMA-LINK-SCHEDULE-CARD %c v1.7.0 ', 
  'color: white; background: #03a9f4; font-weight: bold;',
  'color: #03a9f4; background: white; font-weight: bold;'
);
