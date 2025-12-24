/**
 * Extension Popup UI
 * 
 * Simple control panel for the extension
 * - Toggle on/off
 * - Switch modes
 * - View quick stats
 */

document.addEventListener('DOMContentLoaded', () => {
  loadSettings();
  attachEventListeners();
});

let currentSettings = {
  enabled: true,
  mode: 'writing',
  showSuggestions: true
};

/**
 * Load current settings from storage
 */
async function loadSettings() {
  const response = await chrome.runtime.sendMessage({ action: 'getSettings' });
  
  if (response.success) {
    currentSettings = response.data;
    updateUI();
  }
}

/**
 * Update UI based on current settings
 */
function updateUI() {
  // Update checkboxes
  const enableToggle = document.getElementById('enableToggle');
  const suggestionsToggle = document.getElementById('suggestionsToggle');
  
  enableToggle.checked = currentSettings.enabled;
  suggestionsToggle.checked = currentSettings.showSuggestions;
  
  // Update toggle switch visual states
  const enableSwitch = enableToggle.closest('.toggle-container')?.querySelector('.toggle-switch');
  const suggestionsSwitch = suggestionsToggle.closest('.toggle-container')?.querySelector('.toggle-switch');
  
  if (enableSwitch) {
    enableSwitch.classList.toggle('active', currentSettings.enabled);
  }
  if (suggestionsSwitch) {
    suggestionsSwitch.classList.toggle('active', currentSettings.showSuggestions);
  }
  
  // Update current mode display
  const modeLabels = { writing: '✍️ Writing', reading: '📖 Reading', reply: '💬 Reply' };
  const currentModeSpan = document.getElementById('currentMode');
  if (currentModeSpan) {
    currentModeSpan.textContent = modeLabels[currentSettings.mode] || 'Auto';
  }
  
  // Update status indicator
  const statusDiv = document.getElementById('status');
  statusDiv.className = currentSettings.enabled ? 'status-badge status-active' : 'status-badge status-inactive';
  statusDiv.textContent = currentSettings.enabled ? 'Active' : 'Inactive';
}

/**
 * Attach event listeners to controls
 */
function attachEventListeners() {
  // Enable/disable toggle
  document.getElementById('enableToggle').addEventListener('change', async (e) => {
    currentSettings.enabled = e.target.checked;
    await saveSettings();
    updateUI();
  });
  
  // Suggestions toggle
  document.getElementById('suggestionsToggle').addEventListener('change', async (e) => {
    currentSettings.showSuggestions = e.target.checked;
    await saveSettings();
    updateUI();
  });
  
  // Test button
  document.getElementById('testBtn').addEventListener('click', () => {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs[0]) {
        chrome.tabs.sendMessage(tabs[0].id, { action: 'testExtension' }, (response) => {
          if (response && response.success) {
            showNotification('Extension is working on this page!');
          } else {
            showNotification('Extension ready! Start typing in any text field.');
          }
        });
      }
    });
  });
  
  // Listen for mode updates from content script
  chrome.runtime.onMessage.addListener((message) => {
    if (message.action === 'modeUpdated') {
      currentSettings.mode = message.data.mode;
      updateUI();
    }
  });
}

/**
 * Save settings to storage
 */
async function saveSettings() {
  const response = await chrome.runtime.sendMessage({
    action: 'updateSettings',
    data: currentSettings
  });
  
  if (response.success) {
    showNotification('Settings saved!');
    
    // Notify content scripts
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs[0]) {
        chrome.tabs.sendMessage(tabs[0].id, {
          action: 'settingsUpdated',
          data: currentSettings
        });
      }
    });
  }
}

/**
 * Show temporary notification
 */
function showNotification(message) {
  const notification = document.createElement('div');
  notification.className = 'notification';
  notification.textContent = message;
  document.body.appendChild(notification);
  
  setTimeout(() => {
    notification.remove();
  }, 2000);
}
