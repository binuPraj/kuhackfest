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
  mode: 'writing',
  enableDetection: true,    // Real-time text field detection
  enableChatbot: true       // Floating chatbot feature
};

/**
 * Load current settings from storage
 */
async function loadSettings() {
  const response = await chrome.runtime.sendMessage({ action: 'getSettings' });
  
  if (response.success) {
    currentSettings = { ...currentSettings, ...response.data };
    updateUI();
  }
}

/**
 * Update UI based on current settings
 */
function updateUI() {
  // Update checkboxes
  const detectionToggle = document.getElementById('detectionToggle');
  const chatbotToggle = document.getElementById('chatbotToggle');
  
  detectionToggle.checked = currentSettings.enableDetection ?? true;
  chatbotToggle.checked = currentSettings.enableChatbot ?? true;
  
  // Update toggle switch visual states
  const detectionSwitch = detectionToggle.closest('.toggle-container')?.querySelector('.toggle-switch');
  const chatbotSwitch = chatbotToggle.closest('.toggle-container')?.querySelector('.toggle-switch');
  
  if (detectionSwitch) {
    detectionSwitch.classList.toggle('active', currentSettings.enableDetection ?? true);
  }
  if (chatbotSwitch) {
    chatbotSwitch.classList.toggle('active', currentSettings.enableChatbot ?? true);
  }
  
  // Update current mode display
  const modeLabels = { writing: '✍️ Writing', reading: '📖 Reading', reply: '💬 Reply' };
  const currentModeSpan = document.getElementById('currentMode');
  if (currentModeSpan) {
    currentModeSpan.textContent = modeLabels[currentSettings.mode] || 'Auto';
  }
  
  // Update status indicator
  const statusDiv = document.getElementById('status');
  statusDiv.className = 'status-badge status-active';
  statusDiv.textContent = 'Active';
}

/**
 * Attach event listeners to controls
 */
function attachEventListeners() {
  // Real-time detection toggle (independent from chatbot)
  document.getElementById('detectionToggle').addEventListener('change', async (e) => {
    currentSettings.enableDetection = e.target.checked;
    await saveSettings();
    updateUI();
  });
  
  // Floating chatbot toggle (independent from detection)
  document.getElementById('chatbotToggle').addEventListener('change', async (e) => {
    currentSettings.enableChatbot = e.target.checked;
    await saveSettings();
    updateUI();
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
