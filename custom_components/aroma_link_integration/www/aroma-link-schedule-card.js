/**
 * Aroma-Link Schedule Card
 * A custom Lovelace card for Home Assistant that displays and edits
 * Aroma-Link diffuser schedules in a 7x5 matrix format.
 * 
 * Usage: Add to dashboard with just:
 *   type: custom:aroma-link-schedule-card
 * 
 * Optional config:
 *   type: custom:aroma-link-schedule-card
 *   device: main_house  # Only show specific device (optional)
 *   show_editor: true   # Show inline editor (default: true)
 */

class AromaLinkScheduleCard extends HTMLElement {
  static get properties() {
    return {
      hass: {},
      config: {},
    };
  }

  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._initialized = false;
  }

  setConfig(config) {
    this.config = {
      show_editor: true,
      ...config
    };
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

  // Find all schedule matrix sensors dynamically
  _findScheduleMatrixSensors() {
    if (!this._hass) return [];
    
    const sensors = [];
    for (const entityId of Object.keys(this._hass.states)) {
      if (entityId.startsWith('sensor.') && entityId.endsWith('_schedule_matrix')) {
        const state = this._hass.states[entityId];
        if (state.attributes && state.attributes.matrix) {
          // Extract device name from entity_id
          const deviceName = entityId.replace('sensor.', '').replace('_schedule_matrix', '');
          sensors.push({
            entityId,
            deviceName,
            friendlyName: state.attributes.friendly_name || deviceName.replace(/_/g, ' '),
            matrix: state.attributes.matrix
          });
        }
      }
    }
    
    // Filter by config.device if specified
    if (this.config.device) {
      return sensors.filter(s => s.deviceName.toLowerCase().includes(this.config.device.toLowerCase()));
    }
    
    return sensors;
  }

  // Find device_id from the schedule_matrix sensor attributes
  _findDeviceId(deviceName) {
    // The schedule_matrix sensor exposes device_id in its attributes
    const matrixEntity = `sensor.${deviceName}_schedule_matrix`;
    const state = this._hass.states[matrixEntity];
    if (state && state.attributes && state.attributes.device_id) {
      return state.attributes.device_id;
    }
    return null;
  }

  // Get related entities for a device
  _getDeviceEntities(deviceName) {
    const entities = {};
    const prefix = deviceName;
    
    // Map entity types
    const entityMap = {
      programDay: `select.${prefix}_program_day`,
      program: `select.${prefix}_program`,
      enabled: `switch.${prefix}_program_enabled`,
      startTime: `text.${prefix}_program_start_time`,
      endTime: `text.${prefix}_program_end_time`,
      workTime: `number.${prefix}_program_work_time`,
      pauseTime: `number.${prefix}_program_pause_time`,
      level: `select.${prefix}_program_level`,
      saveProgram: `button.${prefix}_save_program`,
      syncSchedules: `button.${prefix}_sync_schedules`,
    };
    
    for (const [key, entityId] of Object.entries(entityMap)) {
      if (this._hass.states[entityId]) {
        entities[key] = entityId;
      }
    }
    
    return entities;
  }

  _handleCellClick(deviceName, dayIndex, programIndex) {
    const deviceId = this._findDeviceId(deviceName);
    
    if (deviceId) {
      this._hass.callService('aroma_link_integration', 'set_editor_program', {
        device_id: deviceId,
        day: dayIndex,
        program: programIndex
      });
    } else {
      // Fallback: try setting via the select entities directly
      const entities = this._getDeviceEntities(deviceName);
      const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
      
      if (entities.programDay) {
        this._hass.callService('select', 'select_option', {
          entity_id: entities.programDay,
          option: days[dayIndex]
        });
      }
      if (entities.program) {
        this._hass.callService('select', 'select_option', {
          entity_id: entities.program,
          option: `Program ${programIndex}`
        });
      }
    }
  }

  _handleButtonClick(entityId) {
    this._hass.callService('button', 'press', {
      entity_id: entityId
    });
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

    let html = `<style>${this._getStyles()}</style>`;

    for (const sensor of sensors) {
      const entities = this._getDeviceEntities(sensor.deviceName);
      const matrix = sensor.matrix || {};

      html += `
        <ha-card>
          <div class="card-header">
            <div class="name">${sensor.friendlyName} Schedule</div>
            <div class="subtitle">Click a cell to edit</div>
          </div>
          <div class="card-content">
            <div class="schedule-grid">
              <!-- Header Row -->
              <div class="grid-cell header corner"></div>
              ${dayLabels.map(d => `<div class="grid-cell header">${d}</div>`).join('')}
              
              <!-- Program Rows -->
              ${programs.map(prog => `
                <div class="grid-cell header program-label">P${prog}</div>
                ${days.map((day, dayIdx) => {
                  const dayData = matrix[day] || {};
                  const progData = dayData[`program_${prog}`] || {};
                  // Handle both boolean true and integer 1 for enabled
                  const isEnabled = progData.enabled === true || progData.enabled === 1;
                  const startTime = progData.start_time || progData.start || '--:--';
                  const endTime = progData.end_time || progData.end || '--:--';
                  const level = progData.level || '-';
                  
                  const displayText = isEnabled 
                    ? `${startTime.substring(0,5)}<br>${endTime.substring(0,5)}`
                    : 'OFF';
                  
                  return `
                    <div class="grid-cell schedule-cell ${isEnabled ? 'enabled' : ''}" 
                         data-device="${sensor.deviceName}" 
                         data-day="${dayIdx}" 
                         data-program="${prog}">
                      ${displayText}
                      ${isEnabled ? `<span class="level">L${level}</span>` : ''}
                    </div>
                  `;
                }).join('')}
              `).join('')}
            </div>
            
            ${this.config.show_editor ? this._renderEditor(sensor.deviceName, entities) : ''}
          </div>
        </ha-card>
      `;
    }

    this.shadowRoot.innerHTML = html;
    this._attachEventListeners();
  }

  _renderEditor(deviceName, entities) {
    if (Object.keys(entities).length === 0) {
      return '<div class="no-editor">Editor entities not found</div>';
    }

    const getState = (entityId) => {
      const state = this._hass.states[entityId];
      return state ? state.state : '--';
    };

    const getOptions = (entityId) => {
      const state = this._hass.states[entityId];
      return state && state.attributes ? state.attributes.options || [] : [];
    };

    return `
      <div class="editor-section">
        <div class="editor-title">Edit Program</div>
        <div class="editor-grid">
          ${entities.programDay ? `
            <div class="editor-row">
              <label>Day</label>
              <select class="editor-select" data-entity="${entities.programDay}">
                ${getOptions(entities.programDay).map(opt => 
                  `<option value="${opt}" ${getState(entities.programDay) === opt ? 'selected' : ''}>${opt}</option>`
                ).join('')}
              </select>
            </div>
          ` : ''}
          
          ${entities.program ? `
            <div class="editor-row">
              <label>Program</label>
              <select class="editor-select" data-entity="${entities.program}">
                ${getOptions(entities.program).map(opt => 
                  `<option value="${opt}" ${getState(entities.program) === opt ? 'selected' : ''}>${opt}</option>`
                ).join('')}
              </select>
            </div>
          ` : ''}
          
          ${entities.enabled ? `
            <div class="editor-row">
              <label>Enabled</label>
              <input type="checkbox" class="editor-toggle" data-entity="${entities.enabled}" 
                     ${getState(entities.enabled) === 'on' ? 'checked' : ''}>
            </div>
          ` : ''}
          
          ${entities.startTime ? `
            <div class="editor-row">
              <label>Start</label>
              <input type="text" class="editor-input" data-entity="${entities.startTime}" 
                     value="${getState(entities.startTime)}" placeholder="HH:MM">
            </div>
          ` : ''}
          
          ${entities.endTime ? `
            <div class="editor-row">
              <label>End</label>
              <input type="text" class="editor-input" data-entity="${entities.endTime}" 
                     value="${getState(entities.endTime)}" placeholder="HH:MM">
            </div>
          ` : ''}
          
          ${entities.workTime ? `
            <div class="editor-row">
              <label>Work (sec)</label>
              <input type="number" class="editor-input" data-entity="${entities.workTime}" 
                     value="${getState(entities.workTime)}" min="1" max="999">
            </div>
          ` : ''}
          
          ${entities.pauseTime ? `
            <div class="editor-row">
              <label>Pause (sec)</label>
              <input type="number" class="editor-input" data-entity="${entities.pauseTime}" 
                     value="${getState(entities.pauseTime)}" min="1" max="9999">
            </div>
          ` : ''}
          
          ${entities.level ? `
            <div class="editor-row">
              <label>Level</label>
              <select class="editor-select" data-entity="${entities.level}">
                ${getOptions(entities.level).map(opt => 
                  `<option value="${opt}" ${getState(entities.level) === opt ? 'selected' : ''}>${opt}</option>`
                ).join('')}
              </select>
            </div>
          ` : ''}
        </div>
        
        <div class="button-row">
          ${entities.saveProgram ? `
            <button class="action-button save" data-entity="${entities.saveProgram}">
              💾 Save Program
            </button>
          ` : ''}
          ${entities.syncSchedules ? `
            <button class="action-button sync" data-entity="${entities.syncSchedules}">
              🔄 Sync with Aroma-Link
            </button>
          ` : ''}
        </div>
      </div>
    `;
  }

  _attachEventListeners() {
    // Schedule cell clicks
    this.shadowRoot.querySelectorAll('.schedule-cell').forEach(cell => {
      cell.addEventListener('click', () => {
        const device = cell.dataset.device;
        const day = parseInt(cell.dataset.day);
        const program = parseInt(cell.dataset.program);
        this._handleCellClick(device, day, program);
      });
    });

    // Select changes
    this.shadowRoot.querySelectorAll('.editor-select').forEach(select => {
      select.addEventListener('change', (e) => {
        const entityId = e.target.dataset.entity;
        this._hass.callService('select', 'select_option', {
          entity_id: entityId,
          option: e.target.value
        });
      });
    });

    // Toggle changes (switch)
    this.shadowRoot.querySelectorAll('.editor-toggle').forEach(toggle => {
      toggle.addEventListener('change', (e) => {
        const entityId = e.target.dataset.entity;
        this._hass.callService('switch', e.target.checked ? 'turn_on' : 'turn_off', {
          entity_id: entityId
        });
      });
    });

    // Text/Number input changes
    this.shadowRoot.querySelectorAll('.editor-input').forEach(input => {
      input.addEventListener('change', (e) => {
        const entityId = e.target.dataset.entity;
        if (entityId.startsWith('text.')) {
          this._hass.callService('text', 'set_value', {
            entity_id: entityId,
            value: e.target.value
          });
        } else if (entityId.startsWith('number.')) {
          this._hass.callService('number', 'set_value', {
            entity_id: entityId,
            value: parseFloat(e.target.value)
          });
        }
      });
    });

    // Button clicks
    this.shadowRoot.querySelectorAll('.action-button').forEach(button => {
      button.addEventListener('click', (e) => {
        const entityId = e.target.dataset.entity;
        this._handleButtonClick(entityId);
      });
    });
  }

  _getStyles() {
    return `
      :host {
        --cell-size: 48px;
        --header-bg: var(--primary-color, #03a9f4);
        --enabled-bg: rgba(76, 175, 80, 0.25);
        --enabled-border: rgba(76, 175, 80, 0.6);
      }
      
      ha-card {
        margin-bottom: 16px;
      }
      
      .card-header {
        padding: 16px 16px 8px;
      }
      
      .card-header .name {
        font-size: 1.2em;
        font-weight: 500;
        color: var(--primary-text-color);
      }
      
      .card-header .subtitle {
        font-size: 0.85em;
        color: var(--secondary-text-color);
        margin-top: 4px;
      }
      
      .card-content {
        padding: 0 16px 16px;
      }
      
      .loading, .no-devices, .no-editor {
        padding: 24px;
        text-align: center;
        color: var(--secondary-text-color);
      }
      
      /* Schedule Grid */
      .schedule-grid {
        display: grid;
        grid-template-columns: 40px repeat(7, 1fr);
        gap: 2px;
        margin-bottom: 16px;
      }
      
      .grid-cell {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 4px 2px;
        border-radius: 4px;
        font-size: 10px;
        min-height: 40px;
        background: var(--card-background-color, #fff);
        box-sizing: border-box;
      }
      
      .grid-cell.header {
        background: var(--header-bg);
        color: white;
        font-weight: bold;
        font-size: 11px;
        min-height: 28px;
      }
      
      .grid-cell.corner {
        background: transparent;
      }
      
      .grid-cell.program-label {
        background: var(--secondary-background-color, #f5f5f5);
        color: var(--primary-text-color);
      }
      
      .schedule-cell {
        cursor: pointer;
        transition: all 0.15s ease;
        border: 2px solid transparent;
        position: relative;
      }
      
      .schedule-cell:hover {
        transform: scale(1.05);
        box-shadow: 0 2px 8px rgba(0,0,0,0.15);
        z-index: 1;
      }
      
      .schedule-cell.enabled {
        background: var(--enabled-bg);
        border-color: var(--enabled-border);
      }
      
      .schedule-cell .level {
        font-size: 8px;
        opacity: 0.7;
        margin-top: 2px;
      }
      
      /* Editor Section */
      .editor-section {
        background: var(--secondary-background-color, #f5f5f5);
        border-radius: 8px;
        padding: 12px;
        margin-top: 8px;
      }
      
      .editor-title {
        font-weight: 500;
        margin-bottom: 12px;
        color: var(--primary-text-color);
      }
      
      .editor-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
        gap: 8px;
        margin-bottom: 12px;
      }
      
      .editor-row {
        display: flex;
        flex-direction: column;
        gap: 4px;
      }
      
      .editor-row label {
        font-size: 11px;
        color: var(--secondary-text-color);
        font-weight: 500;
      }
      
      .editor-select, .editor-input {
        padding: 8px;
        border: 1px solid var(--divider-color, #e0e0e0);
        border-radius: 4px;
        background: var(--card-background-color, #fff);
        color: var(--primary-text-color);
        font-size: 14px;
      }
      
      .editor-toggle {
        width: 20px;
        height: 20px;
        cursor: pointer;
      }
      
      .button-row {
        display: flex;
        gap: 8px;
        flex-wrap: wrap;
      }
      
      .action-button {
        flex: 1;
        min-width: 120px;
        padding: 10px 16px;
        border: none;
        border-radius: 6px;
        font-size: 14px;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.15s ease;
      }
      
      .action-button.save {
        background: var(--success-color, #4caf50);
        color: white;
      }
      
      .action-button.sync {
        background: var(--info-color, #2196f3);
        color: white;
      }
      
      .action-button:hover {
        opacity: 0.9;
        transform: translateY(-1px);
      }
      
      .action-button:active {
        transform: translateY(0);
      }
    `;
  }

  getCardSize() {
    return 6;
  }

  static getConfigElement() {
    return document.createElement('aroma-link-schedule-card-editor');
  }

  static getStubConfig() {
    return {
      show_editor: true
    };
  }
}

// Simple config editor
class AromaLinkScheduleCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = config;
    this.render();
  }

  render() {
    this.innerHTML = `
      <style>
        .editor { padding: 16px; }
        .row { margin-bottom: 12px; }
        label { display: block; margin-bottom: 4px; font-weight: 500; }
        input[type="text"] { width: 100%; padding: 8px; box-sizing: border-box; }
        input[type="checkbox"] { margin-right: 8px; }
      </style>
      <div class="editor">
        <div class="row">
          <label>
            <input type="checkbox" id="show_editor" ${this._config.show_editor !== false ? 'checked' : ''}>
            Show inline editor
          </label>
        </div>
        <div class="row">
          <label for="device">Device filter (optional)</label>
          <input type="text" id="device" value="${this._config.device || ''}" 
                 placeholder="e.g., main_house (leave empty for all)">
        </div>
      </div>
    `;

    this.querySelector('#show_editor').addEventListener('change', (e) => {
      this._config = { ...this._config, show_editor: e.target.checked };
      this._fireEvent();
    });

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

// Register the cards
customElements.define('aroma-link-schedule-card', AromaLinkScheduleCard);
customElements.define('aroma-link-schedule-card-editor', AromaLinkScheduleCardEditor);

// Register with HA's custom card picker
window.customCards = window.customCards || [];
window.customCards.push({
  type: 'aroma-link-schedule-card',
  name: 'Aroma-Link Schedule',
  description: 'Interactive schedule matrix for Aroma-Link diffusers',
  preview: true,
  documentationURL: 'https://github.com/cjam28/ha_aromalink'
});

console.info('%c AROMA-LINK-SCHEDULE-CARD %c v1.6.0 ', 
  'color: white; background: #03a9f4; font-weight: bold;',
  'color: #03a9f4; background: white; font-weight: bold;'
);
