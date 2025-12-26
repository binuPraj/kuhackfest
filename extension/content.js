/**
 * Content Script - Grammarly-Style Manual Interaction Layer
 * 
 * UX Philosophy:
 * - Passive by default - never interrupts typing
 * - User-invoked analysis only via floating button click
 * - Assistive, not corrective
 * - Silent until asked
 * 
 * Flow:
 * 1. Detect editable fields (textarea, contenteditable)
 * 2. Show floating activation button on focus
 * 3. Analyze text ONLY when user clicks the button
 * 4. Display results in dismissible panel
 * 5. Clean up on blur
 */

// ===== STATE MANAGEMENT =====
let isEnabled = true;
let currentMode = 'writing'; // 'writing' | 'reading' | 'reply'
let activeField = null;
let activeButton = null; // Currently visible activation button
let activePanelField = null; // Field with open results panel
let overlayElements = new Map(); // Track all overlay elements
let buttonElements = new Map(); // Track floating buttons per field

// ===== FEATURE TOGGLES (Independent) =====
// These toggles are independent of each other per the requirements
let enableDetection = true;  // Real-time text field detection
let enableChatbot = true;    // Floating chatbot feature

// ===== FLOATING CHATBOT STATE =====
let floatingChatbotIcon = null;
let floatingChatPanel = null;
let chatHistory = [];        // Message history for the chat panel
let currentDualResponse = null; // Cached dual-mode response (support + defence)
let currentDisplayMode = 'support'; // 'support' | 'defence'

// ===== SELECTION ANALYSE BUTTON STATE =====
let selectionAnalyseButton = null; // Analyse button shown for selected text
let lastSelectedText = null; // Track the last selected text

// Minimum text length for analysis
const MIN_TEXT_LENGTH = 20;

// ===== INITIALIZATION =====
console.log('🧠 Reasoning Assistant: Content script loaded (Manual Mode)');

// Load settings
chrome.runtime.sendMessage(
  { action: 'getSettings' },
  (response) => {
    if (response && response.success) {
      isEnabled = response.data.enabled ?? true;
      currentMode = response.data.mode ?? 'writing';
      enableDetection = response.data.enableDetection ?? true;
      enableChatbot = response.data.enableChatbot ?? true;
      console.log(`📋 Settings loaded: enabled=${isEnabled}, detection=${enableDetection}, chatbot=${enableChatbot}`);
      
      // Initialize features based on settings
      applyFeatureToggles();
    }
  }
);

// Start monitoring the page
initializeExtension();

/**
 * Main initialization function
 */
function initializeExtension() {
  // Inject styles for floating button
  injectStyles();
  
  // Monitor text fields
  observeTextFields();
  
  // Listen for reading mode (hover on content)
  if (currentMode === 'reading') {
    enableReadingMode();
  }
  
  // Listen for text selection - show analyse button
  document.addEventListener('mouseup', handleTextSelection);
  document.addEventListener('touchend', handleTextSelection);
  
  // Hide analyse button when clicking elsewhere (but not on the button itself)
  document.addEventListener('mousedown', (e) => {
    if (selectionAnalyseButton && !selectionAnalyseButton.contains(e.target)) {
      hideSelectionAnalyseButton();
    }
  });
  
  // Listen for messages from background script
  chrome.runtime.onMessage.addListener(handleBackgroundMessage);
  
  console.log('🧠 Reasoning Assistant: Initialized (Grammarly-style passive mode)');
}

/**
 * Inject additional styles for the floating activation button
 */
function injectStyles() {
  const styleId = 'reasoning-assistant-injected-styles';
  if (document.getElementById(styleId)) return;
  
  const style = document.createElement('style');
  style.id = styleId;
  style.textContent = `
    /* Floating Activation Button - Orange Dot */
    .reasoning-activate-btn {
      position: absolute !important;
      width: 14px !important;
      height: 14px !important;
      min-width: 14px !important;
      min-height: 14px !important;
      border-radius: 50% !important;
      background: #c75a2a !important;
      border: 1.5px solid transparent !important;
      cursor: pointer !important;
      z-index: 2147483646 !important;
      display: flex !important;
      align-items: center !important;
      justify-content: center !important;
      box-shadow: 0 2px 6px rgba(199, 90, 42, 0.5) !important;
      transition: all 0.25s ease !important;
      opacity: 0;
      transform: scale(0.8);
      pointer-events: none;
      padding: 0 !important;
      margin: 0 !important;
      overflow: visible !important;
    }
    
    .reasoning-activate-btn.visible {
      opacity: 1;
      transform: scale(1);
      pointer-events: auto;
    }
    
    .reasoning-activate-btn:hover {
      transform: scale(1.4);
      border-color: rgba(255, 255, 255, 0.85);
      box-shadow: 0 0 0 3px rgba(199, 90, 42, 0.25), 0 2px 6px rgba(199, 90, 42, 0.5);
      animation: reasoning-dot-glow 0.4s ease-out;
    }
    
    @keyframes reasoning-dot-glow {
      0% { box-shadow: 0 0 0 0 rgba(255, 255, 255, 0.6), 0 2px 6px rgba(199, 90, 42, 0.5); }
      100% { box-shadow: 0 0 0 3px rgba(199, 90, 42, 0.25), 0 2px 6px rgba(199, 90, 42, 0.5); }
    }
    
    .reasoning-activate-btn:active {
      transform: scale(1.2);
    }
    
    .reasoning-activate-btn.analyzing {
      width: 20px !important;
      height: 20px !important;
      min-width: 20px !important;
      min-height: 20px !important;
      background: #c75a2a !important;
      box-shadow: 0 2px 10px rgba(199, 90, 42, 0.6) !important;
      animation: reasoning-analyzing-pulse 1s ease-in-out infinite !important;
    }
    
    .reasoning-activate-btn .reasoning-spinner-small {
      width: 12px !important;
      height: 12px !important;
      min-width: 12px !important;
      min-height: 12px !important;
      border: 2px solid rgba(255, 255, 255, 0.3) !important;
      border-top-color: #ffffff !important;
      border-right-color: #ffffff !important;
      border-radius: 50% !important;
      animation: reasoning-spin 0.5s linear infinite !important;
      background: transparent !important;
      display: block !important;
      box-sizing: border-box !important;
    }
    
    @keyframes reasoning-analyzing-pulse {
      0%, 100% { transform: scale(1); box-shadow: 0 2px 10px rgba(199, 90, 42, 0.6); }
      50% { transform: scale(1.1); box-shadow: 0 3px 14px rgba(199, 90, 42, 0.8); }
    }
    
    @keyframes reasoning-spin {
      to { transform: rotate(360deg); }
    }

    /* Tooltip for the button */
    .reasoning-activate-btn::after {
      content: 'Analyze';
      position: absolute;
      right: 100%;
      margin-right: 6px;
      padding: 4px 8px;
      background: #3d3a36;
      color: #f8f4ed;
      font-size: 10px;
      font-weight: 500;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      border-radius: 4px;
      white-space: nowrap;
      opacity: 0;
      pointer-events: none;
      transition: opacity 0.2s;
    }
    
    .reasoning-activate-btn:hover::after {
      opacity: 1;
    }
    
    /* Results Panel Header */
    .reasoning-panel-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 14px;
      padding-bottom: 12px;
      border-bottom: 2px solid #c75a2a;
    }
    
    .reasoning-panel-title {
      font-size: 16px;
      font-weight: 700;
      color: #c75a2a !important;
      display: flex;
      align-items: center;
      gap: 10px;
      font-family: Georgia, 'Times New Roman', serif;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    
    .reasoning-panel-title-icon {
      font-size: 20px;
    }
    
    /* Section title styling */
    .reasoning-section-title {
      font-weight: 600;
      color: var(--reasoning-text, #1f2937);
      margin-bottom: 10px;
      font-size: 13px;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    
    /* Toulmin Grid */
    .reasoning-toulmin-grid {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    
    .reasoning-toulmin-item {
      display: flex;
      align-items: center;
      gap: 10px;
    }
    
    .reasoning-toulmin-label {
      width: 90px;
      font-size: 11px;
      font-weight: 500;
      color: var(--reasoning-text-muted, #6b7280);
    }
    
    .reasoning-toulmin-bar {
      flex: 1;
      height: 8px;
      background: #e5e7eb;
      border-radius: 4px;
      overflow: hidden;
    }
    
    .reasoning-toulmin-fill {
      height: 100%;
      border-radius: 4px;
      transition: width 0.5s ease-out;
    }
    
    .reasoning-toulmin-fill.reasoning-good {
      background: linear-gradient(90deg, #34d399, #10b981);
    }
    
    .reasoning-toulmin-fill.reasoning-moderate {
      background: linear-gradient(90deg, #fbbf24, #f59e0b);
    }
    
    .reasoning-toulmin-fill.reasoning-weak {
      background: linear-gradient(90deg, #f87171, #ef4444);
    }
    
    .reasoning-toulmin-score {
      width: 40px;
      font-size: 11px;
      font-weight: 600;
      text-align: right;
      color: var(--reasoning-text, #1f2937);
    }
    
    .reasoning-overall-score {
      margin-top: 12px;
      padding: 8px 12px;
      background: #f0f9ff;
      border-radius: 6px;
      font-size: 12px;
      color: #0369a1;
      text-align: center;
    }
    
    /* Assessment */
    .reasoning-assessment {
      margin-top: 12px;
      padding: 10px 12px;
      background: #f9fafb;
      border-radius: 8px;
      border-left: 3px solid var(--reasoning-info, #3b82f6);
      font-size: 13px;
      line-height: 1.6;
      color: var(--reasoning-text-muted, #6b7280);
    }

    /* Selection Analyse Button */
    .reasoning-selection-analyse-btn {
      position: absolute !important;
      padding: 6px 12px !important;
      background: #c75a2a !important;
      color: white !important;
      border: none !important;
      border-radius: 4px !important;
      font-size: 12px !important;
      font-weight: 600 !important;
      cursor: pointer !important;
      z-index: 2147483647 !important;
      box-shadow: 0 2px 8px rgba(199, 90, 42, 0.5) !important;
      transition: all 0.2s ease !important;
      white-space: nowrap !important;
      opacity: 0;
      transform: scale(0.9);
      pointer-events: none;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
    }

    .reasoning-selection-analyse-btn.visible {
      opacity: 1;
      transform: scale(1);
      pointer-events: auto;
    }

    .reasoning-selection-analyse-btn:hover {
      background: #b8511f !important;
      box-shadow: 0 3px 12px rgba(199, 90, 42, 0.7) !important;
      transform: scale(1.05);
    }

    .reasoning-selection-analyse-btn:active {
      transform: scale(0.98);
    }
  `;
  
  document.head.appendChild(style);
}

/**
 * Observe and attach listeners to text input fields
 * Enhanced with platform-specific selectors for social media
 */
function observeTextFields() {
  // Platform-specific selectors
  const selectors = getPlatformSelectors();
  
  // Find existing text fields (excluding our own chatbot)
  const textFields = document.querySelectorAll(selectors.join(', '));
  textFields.forEach(field => {
    // Skip fields inside our floating chatbot
    if (!field.closest('#LOGICLENS-floating-chat-panel') && 
        !field.closest('.LOGICLENS-chat-panel')) {
      attachFieldListeners(field);
    }
  });
  
  // Watch for dynamically added fields (for SPAs like Twitter, Facebook, Instagram)
  const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      mutation.addedNodes.forEach((node) => {
        if (node.nodeType === 1) { // Element node
          // Skip our own chatbot elements
          if (node.id === 'LOGICLENS-floating-chat-panel' || 
              node.classList?.contains('LOGICLENS-chat-panel') ||
              node.classList?.contains('LOGICLENS-floating-icon') ||
              node.closest?.('#LOGICLENS-floating-chat-panel')) {
            return;
          }
          
          if (node.matches) {
            selectors.forEach(selector => {
              if (node.matches(selector)) {
                attachFieldListeners(node);
              }
            });
          }
          // Check children (but not inside our chatbot)
          if (node.querySelectorAll) {
            const children = node.querySelectorAll(selectors.join(', '));
            children.forEach(child => {
              if (!child.closest('#LOGICLENS-floating-chat-panel') &&
                  !child.closest('.LOGICLENS-chat-panel')) {
                attachFieldListeners(child);
              }
            });
          }
        }
      });
    });
  });
  
  observer.observe(document.body, {
    childList: true,
    subtree: true
  });
}

/**
 * Get platform-specific selectors for text input fields
 */
function getPlatformSelectors() {
  const url = window.location.href;
  
  const baseSelectors = [
    'textarea',
    '[contenteditable="true"]',
    '[role="textbox"]'
  ];
  
  // Twitter/X specific
  if (url.includes('twitter.com') || url.includes('x.com')) {
    return [
      ...baseSelectors,
      '[data-testid="tweetTextarea_0"]',
      '[data-testid="dmComposerTextInput"]',
      '.DraftEditor-editorContainer',
      '.public-DraftEditor-content'
    ];
  }
  
  // Facebook specific
  if (url.includes('facebook.com')) {
    return [
      ...baseSelectors,
      '[aria-label*="Write a comment"]',
      '[aria-label*="What\'s on your mind"]',
      '[aria-label*="Write a post"]',
      '[data-testid="status-attachment-mentions-input"]',
      'div[role="textbox"][contenteditable="true"]',
      '.notranslate[contenteditable="true"]'
    ];
  }
  
  // Instagram specific
  if (url.includes('instagram.com')) {
    return [
      ...baseSelectors,
      '[aria-label*="Add a comment"]',
      '[aria-label*="Write a caption"]',
      '[placeholder*="Add a comment"]',
      '[placeholder*="Write a caption"]',
      'textarea[placeholder*="comment"]'
    ];
  }
  
  // LinkedIn specific
  if (url.includes('linkedin.com')) {
    return [
      ...baseSelectors,
      '.ql-editor[contenteditable="true"]',
      '[data-placeholder*="Start a post"]',
      '[aria-label*="Write a comment"]'
    ];
  }
  
  // Reddit specific
  if (url.includes('reddit.com')) {
    return [
      ...baseSelectors,
      '.public-DraftEditor-content',
      '[role="textbox"]',
      'textarea[name="comment"]'
    ];
  }
  
  return baseSelectors;
}

/**
 * Attach event listeners to a text field
 * GRAMMARLY-STYLE: Only focus/blur handlers - NO input/keyup analysis!
 * For contenteditable fields, button only shows after user types (non-empty content)
 */
function attachFieldListeners(field) {
  // Avoid duplicate listeners
  if (field.dataset.reasoningAssistant) return;
  
  // EXCLUDE floating chatbot's own input field
  if (field.closest('#LOGICLENS-floating-chat-panel') || 
      field.closest('.LOGICLENS-chat-panel') ||
      field.classList.contains('LOGICLENS-chat-input')) {
    return;
  }
  
  field.dataset.reasoningAssistant = 'true';
  
  console.log('🔗 Attaching listeners to field:', field.tagName, field.getAttribute('aria-label') || field.getAttribute('placeholder') || '');
  
  const isContentEditable = field.hasAttribute('contenteditable') || field.getAttribute('role') === 'textbox';
  
  // Focus event - Show floating activation button (if field has content)
  field.addEventListener('focus', (e) => {
    activeField = field;
    
    // For contenteditable fields, only show button if field already has content
    if (isContentEditable) {
      const text = getFieldText(field).trim();
      if (text.length > 0) {
        showActivationButton(field);
      }
    } else {
      // For regular textarea/input, show immediately on focus
      showActivationButton(field);
    }
  });
  
  // Blur event - Hide button with delay (to allow click)
  field.addEventListener('blur', (e) => {
    // Delay hiding to allow button click to register
    setTimeout(() => {
      if (activeField !== field) {
        hideActivationButton(field);
      }
    }, 200);
  });
  
  // For contenteditable fields: Monitor input to show/hide button based on content
  if (isContentEditable) {
    const handleContentChange = () => {
      // Only manage button visibility if field is focused
      if (activeField === field) {
        const text = getFieldText(field).trim();
        const hasButton = buttonElements.has(field);
        
        if (text.length > 0 && !hasButton) {
          // Content exists and no button - show it
          showActivationButton(field);
        } else if (text.length === 0 && hasButton) {
          // Content is empty and button exists - hide it
          hideActivationButton(field);
        }
      }
    };
    
    // Listen to input events (fired when user types)
    field.addEventListener('input', handleContentChange);
    
    // Also use MutationObserver for complex contenteditable fields (like Facebook's Lexical editor)
    const contentObserver = new MutationObserver(handleContentChange);
    contentObserver.observe(field, {
      childList: true,
      subtree: true,
      characterData: true
    });
  }
  
  // NO auto-analysis on input!
  // Analysis happens ONLY when user clicks the activation button
}

/**
 * Get text content from field (handles both textarea and contenteditable)
 */
function getFieldText(field) {
  if (field.tagName === 'TEXTAREA' || field.tagName === 'INPUT') {
    return field.value;
  } else {
    return field.innerText || field.textContent;
  }
}

/**
 * Set text content in field
 */
function setFieldText(field, text) {
  if (field.tagName === 'TEXTAREA' || field.tagName === 'INPUT') {
    field.value = text;
  } else {
    field.innerText = text;
  }
  
  // Trigger input event to notify app
  field.dispatchEvent(new Event('input', { bubbles: true }));
}

/**
 * Insert text into field with proper contenteditable support
 * ✅ FIX: This function properly handles all field types including
 * contenteditable divs used by social media platforms
 */
function insertTextIntoField(field, text) {
  // Focus the field first
  field.focus();
  
  if (field.tagName === 'TEXTAREA' || field.tagName === 'INPUT') {
    // Standard input/textarea
    field.value = text;
    field.dispatchEvent(new Event('input', { bubbles: true }));
    field.dispatchEvent(new Event('change', { bubbles: true }));
  } else {
    // Contenteditable field (Facebook, Twitter, LinkedIn, etc.)
    // Method 1: Try execCommand (works on most browsers)
    const selection = window.getSelection();
    const range = document.createRange();
    
    // Select all content in the field
    range.selectNodeContents(field);
    selection.removeAllRanges();
    selection.addRange(range);
    
    // Try using execCommand to insert text (replaces selection)
    const success = document.execCommand('insertText', false, text);
    
    if (!success) {
      // Method 2: Fallback - directly set content
      field.innerText = text;
    }
    
    // Trigger events to notify the platform's JavaScript
    field.dispatchEvent(new Event('input', { bubbles: true, cancelable: true }));
    field.dispatchEvent(new Event('change', { bubbles: true }));
    
    // Some platforms use custom events
    field.dispatchEvent(new KeyboardEvent('keydown', { bubbles: true, key: 'a' }));
    field.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true, key: 'a' }));
    
    // Move cursor to end
    const newRange = document.createRange();
    newRange.selectNodeContents(field);
    newRange.collapse(false); // false = collapse to end
    selection.removeAllRanges();
    selection.addRange(newRange);
  }
  
  // Keep focus on the field
  field.focus();
}

/**
 * Show the floating activation button for a field
 * Positioned at bottom-right corner, Grammarly-style
 */
function showActivationButton(field) {
  if (!isEnabled) return;
  
  // Remove any existing button for this field first
  hideActivationButton(field);
  
  // Create floating button
  const button = document.createElement('button');
  button.className = 'reasoning-activate-btn';
  button.setAttribute('data-reasoning-assistant', 'activate-btn');
  button.setAttribute('type', 'button');
  button.setAttribute('aria-label', 'Analyze reasoning');
  
  // Brain/reasoning icon (SVG)
  button.innerHTML = `
    <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
    </svg>
  `;
  
  // Position button at bottom-right of field
  positionActivationButton(button, field);
  
  // Add click handler - this is the ONLY trigger for analysis
  button.addEventListener('click', async (e) => {
    e.preventDefault();
    e.stopPropagation();
    
    // Prevent double-click
    if (button.classList.contains('analyzing')) return;
    
    const text = getFieldText(field);
    
    if (text.length < MIN_TEXT_LENGTH) {
      showFeedback(field, `Please write at least ${MIN_TEXT_LENGTH} characters to analyze.`, 'info');
      return;
    }
    
    // Trigger analysis
    await triggerManualAnalysis(field, button);
  });
  
  // Prevent button click from blurring the field
  button.addEventListener('mousedown', (e) => {
    e.preventDefault();
  });
  
  document.body.appendChild(button);
  buttonElements.set(field, button);
  
  // Fade in animation
  requestAnimationFrame(() => {
    button.classList.add('visible');
  });
  
  // Set up resize/scroll observer for repositioning
  setupButtonRepositioning(button, field);
}

/**
 * Position the activation button at center-right of field
 */
function positionActivationButton(button, field) {
  const rect = field.getBoundingClientRect();
  const scrollY = window.scrollY || window.pageYOffset;
  const scrollX = window.scrollX || window.pageXOffset;
  
  // Button dimensions
  const btnSize = 14;
  
  // Calculate center-right position
  // Vertically: center of the field
  // Horizontally: extreme right edge with small inset
  const fieldCenterY = rect.top + (rect.height / 2);
  const rightEdgeX = rect.right - btnSize - 6; // 6px inset from right edge
  
  button.style.position = 'absolute';
  button.style.top = `${fieldCenterY + scrollY - (btnSize / 2)}px`;
  button.style.left = `${rightEdgeX + scrollX}px`;
}

/**
 * Set up repositioning on scroll/resize
 */
function setupButtonRepositioning(button, field) {
  const reposition = () => {
    if (buttonElements.get(field) === button) {
      positionActivationButton(button, field);
    }
  };
  
  // Throttled repositioning
  let ticking = false;
  const throttledReposition = () => {
    if (!ticking) {
      requestAnimationFrame(() => {
        reposition();
        ticking = false;
      });
      ticking = true;
    }
  };
  
  window.addEventListener('scroll', throttledReposition, { passive: true });
  window.addEventListener('resize', throttledReposition, { passive: true });
  
  // Store cleanup function
  button._cleanupReposition = () => {
    window.removeEventListener('scroll', throttledReposition);
    window.removeEventListener('resize', throttledReposition);
  };
}

/**
 * Hide the activation button for a field
 */
function hideActivationButton(field) {
  const button = buttonElements.get(field);
  if (button) {
    button.classList.remove('visible');
    
    // Clean up reposition listener
    if (button._cleanupReposition) {
      button._cleanupReposition();
    }
    
    // Remove after fade out
    setTimeout(() => {
      button.remove();
    }, 200);
    
    buttonElements.delete(field);
  }
  
  // Also clear suggestions panel if field loses focus and panel is open
  if (activePanelField === field) {
    // Don't clear immediately - user might be interacting with panel
  }
}

/**
 * Trigger manual analysis - ONLY called on button click
 */
async function triggerManualAnalysis(field, button) {
  const text = getFieldText(field);
  console.log('🔍 Manual analysis triggered for:', text.substring(0, 50) + '...');
  
  // Show loading state on button
  button.classList.add('analyzing');
  const originalContent = button.innerHTML;
  button.innerHTML = '<div class="reasoning-spinner-small"></div>';
  
  try {
    // Send to background script
    const response = await new Promise((resolve, reject) => {
      chrome.runtime.sendMessage(
        {
          action: 'analyzeText',
          data: { text, context: detectContext(field) }
        },
        (response) => {
          if (chrome.runtime.lastError) {
            reject(new Error(chrome.runtime.lastError.message));
          } else {
            resolve(response);
          }
        }
      );
    });
    
    // Reset button state
    button.classList.remove('analyzing');
    button.innerHTML = originalContent;
    
    if (response && response.success) {
      displayAnalysisResults(response.data, field);
    } else {
      const errorMsg = response?.error || 'Unknown error';
      console.error('Analysis failed:', errorMsg);
      
      // Show more helpful error message
      if (errorMsg.includes('Failed to fetch') || errorMsg.includes('Network')) {
        showError(field, 'Cannot connect to server. Please ensure the backend is running.');
      } else if (errorMsg.includes('402') || errorMsg.includes('credits')) {
        showError(field, 'API credits low. Check your OpenRouter account.');
      } else {
        showError(field, 'Analysis failed. Please try again.');
      }
    }
  } catch (error) {
    // Reset button state
    button.classList.remove('analyzing');
    button.innerHTML = originalContent;
    
    console.error('Error during analysis:', error);
    showError(field, 'Connection error. Please check if the extension is enabled.');
  }
}

/**
 * Display analysis results as panel near the field
 * 
 * ┌──────────────────────────────────────────────────────────────────┐
 * │ ✅ UI PARITY FIX (2024-12-24):                                   │
 * │                                                                  │
 * │ This function now reads the CHATBOT response format directly:    │
 * │   - elements.claim.text / elements.claim.strength                │
 * │   - fallacies_present (array of strings)                         │
 * │   - improved_statement                                           │
 * │   - feedback                                                     │
 * │   - fallacy_resistance_score, logical_consistency_score, etc.    │
 * │                                                                  │
 * │ NO TRANSFORMATION - same data structure as chatbot receives.     │
 * └──────────────────────────────────────────────────────────────────┘
 */
function displayAnalysisResults(data, field) {
  console.log('📊 Analysis results (raw chatbot format):', data);
  
  // ✅ Read CHATBOT format: elements, fallacies_present, fallacy_details, improved_statement, feedback
  const elements = data.elements || {};
  const fallacies_present = data.fallacies_present || [];
  const fallacy_details = data.fallacy_details || [];  // NEW: includes percentage scores
  const improved_statement = data.improved_statement || '';
  const feedback = data.feedback || '';
  const fallacy_resistance_score = data.fallacy_resistance_score || 0;
  const logical_consistency_score = data.logical_consistency_score || 0;
  const clarity_score = data.clarity_score || 0;
  
  // Clear previous panel
  clearSuggestions(field);
  
  // Check if argument is strong (using chatbot's element strength scores)
  const isStrong = isArgumentStrongFromElements(elements);
  
  if (fallacies_present.length === 0 && isStrong) {
    // No issues found - show positive feedback
    showPositiveFeedback(field);
    return;
  }
  
  // Create overlay container (results panel)
  const overlay = createOverlay(field);
  
  // Add panel header
  const header = document.createElement('div');
  header.className = 'reasoning-panel-header';
  header.innerHTML = `
    <div class="reasoning-panel-title">
      <span class="reasoning-panel-title-icon">🧠</span>
      Analysis Complete
    </div>
  `;
  overlay.insertBefore(header, overlay.firstChild.nextSibling);
  
  // ═══════════════════════════════════════════════════════════════════════════
  // SECTION ORDER (Per User Request):
  // 1. Improved Statement (always visible at top)
  // 2. Feedback (collapsible)
  // 3. Toulmin Model (collapsible)
  // 4. Detected Fallacies (collapsible - hidden by default)
  // ═══════════════════════════════════════════════════════════════════════════
  
  // ✅ 1. Display improved statement FIRST (always visible at top)
  if (improved_statement) {
    const suggestionsContainer = document.createElement('div');
    suggestionsContainer.className = 'reasoning-suggestions';
    
    const title = document.createElement('div');
    title.className = 'reasoning-section-title';
    title.innerHTML = '<span class="reasoning-icon">💡</span> Improved Statement';
    suggestionsContainer.appendChild(title);
    
    const textElement = document.createElement('div');
    textElement.className = 'reasoning-suggestion-text-simple';
    textElement.textContent = improved_statement;
    suggestionsContainer.appendChild(textElement);
    
    // Accept button to paste improved statement to field
    const acceptBtn = document.createElement('button');
    acceptBtn.className = 'reasoning-accept-btn';
    acceptBtn.innerHTML = '✓ Accept';
    acceptBtn.addEventListener('click', () => {
      // Paste to the contenteditable field
      if (field) {
        if (field.isContentEditable) {
          field.innerText = improved_statement;
        } else if (field.tagName === 'TEXTAREA' || field.tagName === 'INPUT') {
          field.value = improved_statement;
        }
        // Trigger input event for any listeners
        field.dispatchEvent(new Event('input', { bubbles: true }));
        // Close the overlay after accepting
        removeOverlay(field);
      }
    });
    suggestionsContainer.appendChild(acceptBtn);
    
    overlay.appendChild(suggestionsContainer);
  }
  
  // ✅ 2. Display unified "View More" dropdown with all additional info
  const hasAdditionalContent = feedback || Object.keys(elements).length > 0 || fallacy_details.length > 0 || fallacies_present.length > 0;
  
  if (hasAdditionalContent) {
    const viewMoreSection = createUnifiedViewMoreSection(
      fallacy_details, 
      fallacies_present, 
      feedback, 
      elements
    );
    overlay.appendChild(viewMoreSection);
  }
  
  // Position and show overlay
  positionOverlay(overlay, field);
  overlayElements.set(field, overlay);
  activePanelField = field;
}

/**
 * Check if argument is strong using CHATBOT format (elements.X.strength)
 * 
 * ✅ UI PARITY: Uses chatbot's element.strength (0-10 scale)
 */
function isArgumentStrongFromElements(elements) {
  const factors = ['claim', 'data', 'warrant'];
  let strongCount = 0;
  
  factors.forEach(factor => {
    const element = elements[factor];
    if (element && element.strength >= 7) {
      strongCount++;
    }
  });
  
  return strongCount >= 2;
}

/**
 * Creates a unified "View More" section that contains all additional info
 * 
 * ┌──────────────────────────────────────────────────────────────────┐
 * │ ✅ UNIFIED UI (2024-12-25):                                      │
 * │                                                                  │
 * │ - Single dropdown for all hidden content                         │
 * │ - Order: Fallacies → Feedback → Argument Structure               │
 * │ - Clean, compact layout                                          │
 * └──────────────────────────────────────────────────────────────────┘
 */
function createUnifiedViewMoreSection(fallacy_details, fallacies_present, feedback, elements) {
  const wrapper = document.createElement('div');
  wrapper.className = 'reasoning-viewmore-wrapper';
  
  // ===== CREATE TOGGLE BUTTON =====
  const toggleBtn = document.createElement('div');
  toggleBtn.className = 'reasoning-viewmore-toggle';
  toggleBtn.innerHTML = `
    <div class="reasoning-viewmore-toggle-text">
      <span class="reasoning-viewmore-toggle-icon">📋</span>
      <span>View More</span>
    </div>
    <span class="reasoning-viewmore-toggle-arrow">▼</span>
  `;
  wrapper.appendChild(toggleBtn);
  
  // ===== CREATE COLLAPSIBLE CONTENT =====
  const collapsibleContent = document.createElement('div');
  collapsibleContent.className = 'reasoning-viewmore-collapsible';
  
  // --- 1. DETECTED FALLACIES (compact inline) ---
  const hasFallacies = fallacy_details && fallacy_details.length > 0;
  const fallacySection = document.createElement('div');
  fallacySection.className = 'reasoning-viewmore-section';
  
  const fallacyTitle = document.createElement('div');
  fallacyTitle.className = 'reasoning-viewmore-section-title';
  fallacyTitle.innerHTML = '<span>⚠️</span> Detected Fallacies';
  fallacySection.appendChild(fallacyTitle);
  
  if (hasFallacies) {
    const fallacyList = document.createElement('div');
    fallacyList.className = 'reasoning-fallacy-compact';
    
    fallacy_details.forEach(fallacy => {
      const item = document.createElement('span');
      item.className = 'reasoning-fallacy-tag';
      const percentage = fallacy.score ? Math.round(fallacy.score * 100) : 0;
      item.textContent = `${fallacy.label || 'Unknown'} (${percentage}%)`;
      
      // Color by confidence
      if (percentage >= 70) item.classList.add('high');
      else if (percentage >= 40) item.classList.add('medium');
      else item.classList.add('low');
      
      fallacyList.appendChild(item);
    });
    fallacySection.appendChild(fallacyList);
  } else {
    const noFallacy = document.createElement('div');
    noFallacy.className = 'reasoning-viewmore-none';
    noFallacy.textContent = '✓ No fallacies detected';
    fallacySection.appendChild(noFallacy);
  }
  collapsibleContent.appendChild(fallacySection);
  
  // --- 2. FEEDBACK ---
  if (feedback) {
    const feedbackSection = document.createElement('div');
    feedbackSection.className = 'reasoning-viewmore-section';
    
    const feedbackTitle = document.createElement('div');
    feedbackTitle.className = 'reasoning-viewmore-section-title';
    feedbackTitle.innerHTML = '<span>💬</span> Feedback';
    feedbackSection.appendChild(feedbackTitle);
    
    const feedbackContent = document.createElement('div');
    feedbackContent.className = 'reasoning-viewmore-text';
    feedbackContent.textContent = feedback;
    feedbackSection.appendChild(feedbackContent);
    
    collapsibleContent.appendChild(feedbackSection);
  }
  
  // --- 3. ARGUMENT STRUCTURE (Toulmin) ---
  if (elements && Object.keys(elements).length > 0) {
    const toulminSection = document.createElement('div');
    toulminSection.className = 'reasoning-viewmore-section';
    
    const toulminTitle = document.createElement('div');
    toulminTitle.className = 'reasoning-viewmore-section-title';
    toulminTitle.innerHTML = '<span>📐</span> Argument Structure';
    toulminSection.appendChild(toulminTitle);
    
    const factors = ['claim', 'data', 'warrant', 'backing', 'qualifier', 'rebuttal'];
    const factorLabels = { claim: 'Claim', data: 'Data', warrant: 'Warrant', backing: 'Backing', qualifier: 'Qualifier', rebuttal: 'Rebuttal' };
    
    const grid = document.createElement('div');
    grid.className = 'reasoning-toulmin-grid-compact';
    
    factors.forEach(factor => {
      const element = elements[factor];
      if (!element) return;
      
      const strength = element.strength || 0;
      const scoreClass = strength >= 7 ? 'good' : strength >= 4 ? 'moderate' : 'weak';
      
      const item = document.createElement('div');
      item.className = 'reasoning-toulmin-item-compact';
      item.innerHTML = `
        <div class="reasoning-toulmin-item-header">
          <span class="reasoning-toulmin-label-compact">${factorLabels[factor]}</span>
          <div class="reasoning-toulmin-bar-compact">
            <div class="reasoning-toulmin-fill-compact reasoning-${scoreClass}" style="width: ${strength * 10}%"></div>
          </div>
          <span class="reasoning-toulmin-score-compact">${strength}/10</span>
        </div>
      `;
      
      // ✅ Add full text detail below the bar
      if (element.text) {
        const detailDiv = document.createElement('div');
        detailDiv.className = 'LOGICLENS-toulmin-detail';
        detailDiv.textContent = element.text;
        item.appendChild(detailDiv);
      }
      
      grid.appendChild(item);
    });
    
    toulminSection.appendChild(grid);
    collapsibleContent.appendChild(toulminSection);
  }
  
  wrapper.appendChild(collapsibleContent);
  
  // ===== TOGGLE CLICK HANDLER =====
  toggleBtn.addEventListener('click', () => {
    const isExpanded = toggleBtn.classList.contains('expanded');
    toggleBtn.classList.toggle('expanded');
    collapsibleContent.classList.toggle('expanded');
    toggleBtn.querySelector('.reasoning-viewmore-toggle-text span:last-child').textContent = isExpanded ? 'View More' : 'Hide Details';
  });
  
  return wrapper;
}

/**
 * Creates a collapsible Feedback section
 * 
 * ┌──────────────────────────────────────────────────────────────────┐
 * │ ✅ UI ENHANCEMENT (2024-12-25):                                  │
 * │                                                                  │
 * │ - Hidden by default with small toggle button                     │
 * │ - Click to expand/collapse with smooth animation                 │
 * │ - Clean, unobtrusive UI                                          │
 * └──────────────────────────────────────────────────────────────────┘
 */
function createCollapsibleFeedback(feedbackText) {
  // Create wrapper container
  const wrapper = document.createElement('div');
  wrapper.className = 'reasoning-feedback-wrapper';
  
  // ===== CREATE TOGGLE BUTTON (Visible by default) =====
  const toggleBtn = document.createElement('div');
  toggleBtn.className = 'reasoning-feedback-toggle';
  toggleBtn.innerHTML = `
    <div class="reasoning-feedback-toggle-text">
      <span class="reasoning-feedback-toggle-icon">💬</span>
      <span>View Feedback</span>
    </div>
    <span class="reasoning-feedback-toggle-arrow">▼</span>
  `;
  wrapper.appendChild(toggleBtn);
  
  // ===== CREATE COLLAPSIBLE CONTENT (Hidden by default) =====
  const collapsibleContent = document.createElement('div');
  collapsibleContent.className = 'reasoning-feedback-collapsible';
  
  const feedbackContent = document.createElement('div');
  feedbackContent.className = 'reasoning-feedback-content';
  feedbackContent.textContent = feedbackText;
  collapsibleContent.appendChild(feedbackContent);
  
  wrapper.appendChild(collapsibleContent);
  
  // ===== TOGGLE CLICK HANDLER =====
  toggleBtn.addEventListener('click', () => {
    const isExpanded = toggleBtn.classList.contains('expanded');
    
    if (isExpanded) {
      // Collapse
      toggleBtn.classList.remove('expanded');
      collapsibleContent.classList.remove('expanded');
      toggleBtn.querySelector('.reasoning-feedback-toggle-text span:last-child').textContent = 'View Feedback';
    } else {
      // Expand
      toggleBtn.classList.add('expanded');
      collapsibleContent.classList.add('expanded');
      toggleBtn.querySelector('.reasoning-feedback-toggle-text span:last-child').textContent = 'Hide Feedback';
    }
  });
  
  return wrapper;
}

/**
 * Creates a collapsible Fallacies section - hidden by default
 * 
 * ┌──────────────────────────────────────────────────────────────────┐
 * │ ⚠️ UI ENHANCEMENT:                                               │
 * │                                                                  │
 * │ - Hidden by default with small toggle button                     │
 * │ - Click to expand/collapse with smooth animation                 │
 * │ - Shows fallacy count in toggle button                           │
 * │ - Warning-themed colors (amber/orange)                           │
 * └──────────────────────────────────────────────────────────────────┘
 */
function createCollapsibleFallaciesSection(fallacy_details, fallacies_present) {
  // Create wrapper container
  const wrapper = document.createElement('div');
  wrapper.className = 'reasoning-fallacy-wrapper';
  
  // Count fallacies for display
  const fallacyCount = fallacy_details ? fallacy_details.length : 0;
  const statusText = fallacies_present ? `${fallacyCount} Detected` : 'None Detected';
  
  // ===== CREATE TOGGLE BUTTON (Visible by default) =====
  const toggleBtn = document.createElement('div');
  toggleBtn.className = 'reasoning-fallacy-toggle';
  toggleBtn.innerHTML = `
    <div class="reasoning-fallacy-toggle-text">
      <span class="reasoning-fallacy-toggle-icon">⚠️</span>
      <span>View Detected Fallacies (${statusText})</span>
    </div>
    <span class="reasoning-fallacy-toggle-arrow">▸</span>
  `;
  wrapper.appendChild(toggleBtn);
  
  // ===== CREATE COLLAPSIBLE CONTENT (Hidden by default) =====
  const collapsibleContent = document.createElement('div');
  collapsibleContent.className = 'reasoning-fallacy-collapsible';
  
  // Build fallacy content
  if (fallacies_present && fallacy_details && fallacy_details.length > 0) {
    fallacy_details.forEach(fallacy => {
      const fallacyItem = document.createElement('div');
      fallacyItem.className = 'reasoning-fallacy-item';
      
      const fallacyName = document.createElement('div');
      fallacyName.className = 'reasoning-fallacy-name';
      fallacyName.textContent = fallacy.label || 'Unknown Fallacy';
      
      const fallacyScore = document.createElement('div');
      fallacyScore.className = 'reasoning-fallacy-score';
      const percentage = fallacy.score ? Math.round(fallacy.score * 100) : 0;
      fallacyScore.textContent = `${percentage}% confidence`;
      
      // Color code based on confidence
      if (percentage >= 70) {
        fallacyScore.classList.add('high-confidence');
      } else if (percentage >= 40) {
        fallacyScore.classList.add('medium-confidence');
      } else {
        fallacyScore.classList.add('low-confidence');
      }
      
      fallacyItem.appendChild(fallacyName);
      fallacyItem.appendChild(fallacyScore);
      collapsibleContent.appendChild(fallacyItem);
    });
  } else {
    const noFallacy = document.createElement('div');
    noFallacy.className = 'reasoning-fallacy-none';
    noFallacy.textContent = '✓ No logical fallacies detected in this argument.';
    collapsibleContent.appendChild(noFallacy);
  }
  
  wrapper.appendChild(collapsibleContent);
  
  // ===== TOGGLE CLICK HANDLER =====
  toggleBtn.addEventListener('click', () => {
    const isExpanded = toggleBtn.classList.contains('expanded');
    
    if (isExpanded) {
      // Collapse
      toggleBtn.classList.remove('expanded');
      collapsibleContent.classList.remove('expanded');
      toggleBtn.querySelector('.reasoning-fallacy-toggle-text span:last-child').textContent = `View Detected Fallacies (${statusText})`;
    } else {
      // Expand
      toggleBtn.classList.add('expanded');
      collapsibleContent.classList.add('expanded');
      toggleBtn.querySelector('.reasoning-fallacy-toggle-text span:last-child').textContent = 'Hide Detected Fallacies';
    }
  });
  
  return wrapper;
}

/**
 * Check if Toulmin analysis indicates a strong argument
 * LEGACY: Kept for backward compatibility
 */
function isArgumentStrong(toulminAnalysis) {
  const factors = ['claim', 'data', 'warrant'];
  let strongCount = 0;
  
  factors.forEach(factor => {
    if (toulminAnalysis[factor]?.score >= 7) {
      strongCount++;
    }
  });
  
  return strongCount >= 2;
}

/**
 * Creates a collapsible Toulmin Model section from CHATBOT response format
 * 
 * ┌──────────────────────────────────────────────────────────────────┐
 * │ ✅ UI ENHANCEMENT (2024-12-25):                                  │
 * │                                                                  │
 * │ - Hidden by default with small toggle button                     │
 * │ - Click to expand/collapse with smooth animation                 │
 * │ - Clean, unobtrusive UI                                          │
 * └──────────────────────────────────────────────────────────────────┘
 */
function createToulminSectionFromChatbotFormat(elements) {
  // Create wrapper container
  const wrapper = document.createElement('div');
  wrapper.className = 'reasoning-toulmin-wrapper';
  
  // ===== CREATE TOGGLE BUTTON (Visible by default) =====
  const toggleBtn = document.createElement('div');
  toggleBtn.className = 'reasoning-toulmin-toggle';
  toggleBtn.innerHTML = `
    <div class="reasoning-toulmin-toggle-text">
      <span class="reasoning-toulmin-toggle-icon">📐</span>
      <span>View Argument Structure (Toulmin Model)</span>
    </div>
    <span class="reasoning-toulmin-toggle-arrow">▼</span>
  `;
  wrapper.appendChild(toggleBtn);
  
  // ===== CREATE COLLAPSIBLE CONTENT (Hidden by default) =====
  const collapsibleContent = document.createElement('div');
  collapsibleContent.className = 'reasoning-toulmin-collapsible';
  
  const factors = ['claim', 'data', 'warrant', 'backing', 'qualifier', 'rebuttal'];
  const factorLabels = {
    claim: 'Claim',
    data: 'Data',
    warrant: 'Warrant',
    backing: 'Backing',
    qualifier: 'Qualifier',
    rebuttal: 'Rebuttal'
  };
  
  // Create the grid for scores
  const grid = document.createElement('div');
  grid.className = 'reasoning-toulmin-grid';
  
  factors.forEach(factor => {
    const element = elements[factor];
    if (!element) return;
    
    const item = document.createElement('div');
    item.className = 'reasoning-toulmin-item';
    
    // ✅ Use chatbot's strength (0-10 scale)
    const strength = element.strength || 0;
    const scoreClass = strength >= 7 ? 'good' : strength >= 4 ? 'moderate' : 'weak';
    
    item.innerHTML = `
      <div class="reasoning-toulmin-label">${factorLabels[factor]}</div>
      <div class="reasoning-toulmin-bar">
        <div class="reasoning-toulmin-fill reasoning-${scoreClass}" style="width: ${strength * 10}%"></div>
      </div>
      <div class="reasoning-toulmin-score">${strength}/10</div>
    `;
    
    // ✅ Add tooltip with actual TEXT from chatbot
    if (element.text) {
      item.title = `${factorLabels[factor]}: ${element.text}`;
    }
    
    grid.appendChild(item);
  });
  
  collapsibleContent.appendChild(grid);
  
  // Add detailed text breakdown (matching chatbot display)
  const detailsDiv = document.createElement('div');
  detailsDiv.className = 'reasoning-toulmin-details';
  detailsDiv.style.marginTop = '12px';
  detailsDiv.style.fontSize = '12px';
  detailsDiv.style.lineHeight = '1.6';
  detailsDiv.style.color = 'var(--reasoning-text-muted, #6b7280)';
  
  factors.forEach(factor => {
    const element = elements[factor];
    if (element && element.text) {
      const detailLine = document.createElement('div');
      detailLine.style.marginBottom = '6px';
      detailLine.innerHTML = `<strong style="color: var(--reasoning-text, #1f2937)">${factorLabels[factor]}:</strong> ${element.text}`;
      detailsDiv.appendChild(detailLine);
    }
  });
  
  collapsibleContent.appendChild(detailsDiv);
  wrapper.appendChild(collapsibleContent);
  
  // ===== TOGGLE CLICK HANDLER =====
  toggleBtn.addEventListener('click', () => {
    const isExpanded = toggleBtn.classList.contains('expanded');
    
    if (isExpanded) {
      // Collapse
      toggleBtn.classList.remove('expanded');
      collapsibleContent.classList.remove('expanded');
      toggleBtn.querySelector('.reasoning-toulmin-toggle-text span:last-child').textContent = 'View Argument Structure (Toulmin Model)';
    } else {
      // Expand
      toggleBtn.classList.add('expanded');
      collapsibleContent.classList.add('expanded');
      toggleBtn.querySelector('.reasoning-toulmin-toggle-text span:last-child').textContent = 'Hide Argument Structure (Toulmin Model)';
    }
  });
  
  return wrapper;
}

/**
 * Create Toulmin analysis section
 * LEGACY: Kept for backward compatibility with old format
 */
function createToulminSection(analysis) {
  const section = document.createElement('div');
  section.className = 'reasoning-toulmin-section';
  
  const title = document.createElement('div');
  title.className = 'reasoning-section-title';
  title.innerHTML = `<span class="reasoning-icon">📐</span> Argument Structure`;
  section.appendChild(title);
  
  const factors = ['claim', 'data', 'warrant', 'backing', 'qualifier', 'rebuttal'];
  const factorLabels = {
    claim: 'Claim',
    data: 'Evidence',
    warrant: 'Reasoning',
    backing: 'Support',
    qualifier: 'Hedging',
    rebuttal: 'Counter-arguments'
  };
  
  const grid = document.createElement('div');
  grid.className = 'reasoning-toulmin-grid';
  
  factors.forEach(factor => {
    const factorData = analysis[factor];
    if (!factorData) return;
    
    const item = document.createElement('div');
    item.className = 'reasoning-toulmin-item';
    
    const score = factorData.score || 0;
    const scoreClass = score >= 7 ? 'good' : score >= 4 ? 'moderate' : 'weak';
    
    item.innerHTML = `
      <div class="reasoning-toulmin-label">${factorLabels[factor]}</div>
      <div class="reasoning-toulmin-bar">
        <div class="reasoning-toulmin-fill reasoning-${scoreClass}" style="width: ${score * 10}%"></div>
      </div>
      <div class="reasoning-toulmin-score">${score}/10</div>
    `;
    
    // Add tooltip with feedback
    if (factorData.feedback) {
      item.title = factorData.feedback;
    }
    
    grid.appendChild(item);
  });
  
  section.appendChild(grid);
  
  // Add overall score
  if (analysis.overallScore !== undefined) {
    const overall = document.createElement('div');
    overall.className = 'reasoning-overall-score';
    overall.innerHTML = `Overall Argument Strength: <strong>${analysis.overallScore}/10</strong>`;
    section.appendChild(overall);
  }
  
  return section;
}

/**
 * Create main overlay container (results panel)
 */
function createOverlay(field) {
  const overlay = document.createElement('div');
  overlay.className = 'reasoning-overlay';
  overlay.setAttribute('data-reasoning-assistant', 'overlay');
  
  // Add close button
  const closeBtn = document.createElement('button');
  closeBtn.className = 'reasoning-overlay-close';
  closeBtn.innerHTML = '×';
  closeBtn.setAttribute('aria-label', 'Close panel');
  closeBtn.onclick = () => {
    clearSuggestions(field);
    activePanelField = null;
  };
  overlay.appendChild(closeBtn);
  
  // Prevent clicks inside panel from closing it
  overlay.addEventListener('mousedown', (e) => {
    e.stopPropagation();
  });
  
  document.body.appendChild(overlay);
  return overlay;
}

/**
 * Create individual issue element
 * Enhanced to show verified fallacy information
 */
function createIssueElement(issue, index) {
  const element = document.createElement('div');
  element.className = `reasoning-issue reasoning-${issue.severity || 'warning'}`;
  
  const icon = getSeverityIcon(issue.severity);
  const verifiedBadge = issue.isVerified 
    ? '<span class="reasoning-verified-badge">✓ Verified</span>' 
    : '';
  
  // Get display name - prefer type, fall back to name
  const displayType = issue.type || issue.name || 'Reasoning Issue';
  const alias = issue.alias || issue.modelMatch?.alias || '';
  
  element.innerHTML = `
    <div class="reasoning-issue-header">
      <div class="reasoning-issue-title">
        <span class="reasoning-icon">${icon}</span>
        <span class="reasoning-type">${displayType}</span>
        ${alias ? `<span class="reasoning-alias">(${alias})</span>` : ''}
      </div>
      ${verifiedBadge}
    </div>
    <div class="reasoning-description">${issue.description || issue.explanation || ''}</div>
    ${issue.excerpt || issue.example ? `<div class="reasoning-excerpt">"${issue.excerpt || issue.example}"</div>` : ''}
  `;
  
  // Add model definition tooltip if available
  if (issue.modelMatch?.definition) {
    element.title = `Definition: ${issue.modelMatch.definition}`;
  }
  
  return element;
}

/**
 * Create suggestions container with action buttons
 */
function createSuggestionsContainer(suggestions, field) {
  const container = document.createElement('div');
  container.className = 'reasoning-suggestions';
  
  const title = document.createElement('div');
  title.className = 'reasoning-section-title';
  title.innerHTML = '<span class="reasoning-icon">💡</span> Suggested Improvements';
  container.appendChild(title);
  
  suggestions.forEach((suggestion, index) => {
    const suggestionElement = document.createElement('div');
    suggestionElement.className = 'reasoning-suggestion-item';
    
    // ✅ REMOVED: Edit and Ignore buttons - only Accept button now
    suggestionElement.innerHTML = `
      <div class="reasoning-suggestion-text">${suggestion.text}</div>
      ${suggestion.rationale ? `<div class="reasoning-suggestion-rationale">${suggestion.rationale}</div>` : ''}
      <div class="reasoning-suggestion-actions">
        <button class="reasoning-btn reasoning-btn-accept reasoning-btn-small" data-index="${index}">
          ✓ Accept
        </button>
      </div>
    `;
    
    // Add click handler for Accept button
    const acceptBtn = suggestionElement.querySelector('.reasoning-btn-accept');
    acceptBtn.addEventListener('click', () => {
      // ✅ FIX: Use insertTextIntoField for proper contenteditable support
      insertTextIntoField(field, suggestion.text);
      clearSuggestions(field);
      showFeedback(field, '✓ Suggestion applied!', 'success');
    });
    
    container.appendChild(suggestionElement);
  });
  
  return container;
}

/**
 * Position overlay near the field
 */
function positionOverlay(overlay, field) {
  const rect = field.getBoundingClientRect();
  const scrollY = window.scrollY || window.pageYOffset;
  const scrollX = window.scrollX || window.pageXOffset;
  
  // Calculate available space
  const viewportHeight = window.innerHeight;
  const viewportWidth = window.innerWidth;
  const spaceBelow = viewportHeight - rect.bottom;
  const spaceRight = viewportWidth - rect.right;
  
  // Position below the field by default, above if not enough space
  overlay.style.position = 'absolute';
  
  if (spaceBelow >= 300 || spaceBelow >= rect.top) {
    overlay.style.top = `${rect.bottom + scrollY + 8}px`;
    overlay.style.bottom = 'auto';
  } else {
    overlay.style.bottom = `${viewportHeight - rect.top - scrollY + 8}px`;
    overlay.style.top = 'auto';
  }
  
  // Position at right edge of field, or left if not enough space
  if (spaceRight >= 300) {
    overlay.style.left = `${rect.right + scrollX - 400}px`;
  } else {
    overlay.style.left = `${Math.max(rect.left + scrollX, 10)}px`;
  }
  
  overlay.style.minWidth = `${Math.min(rect.width, 400)}px`;
  overlay.style.maxWidth = '450px';
  overlay.style.zIndex = '2147483647'; // Maximum z-index
}

/**
 * Clear suggestions for a field
 */
function clearSuggestions(field) {
  const overlay = overlayElements.get(field);
  if (overlay) {
    overlay.classList.add('reasoning-overlay-hiding');
    setTimeout(() => {
      overlay.remove();
    }, 200);
    overlayElements.delete(field);
  }
  
  if (activePanelField === field) {
    activePanelField = null;
  }
}

/**
 * Show positive feedback when no issues found
 */
function showPositiveFeedback(field) {
  showFeedback(field, '✓ Strong argument! No significant issues detected.', 'success');
}

/**
 * Show temporary feedback message
 */
function showFeedback(field, message, type = 'info') {
  const feedback = document.createElement('div');
  feedback.className = `reasoning-feedback reasoning-feedback-${type}`;
  feedback.innerHTML = `<span class="reasoning-feedback-icon">${type === 'success' ? '✓' : type === 'error' ? '⚠' : 'ℹ'}</span> ${message}`;
  
  document.body.appendChild(feedback);
  positionOverlay(feedback, field);
  
  setTimeout(() => {
    feedback.classList.add('reasoning-feedback-hiding');
    setTimeout(() => feedback.remove(), 300);
  }, 3000);
}

/**
 * Show error message
 */
function showError(field, message) {
  showFeedback(field, message, 'error');
}

/**
 * Get severity icon
 */
function getSeverityIcon(severity) {
  switch (severity) {
    case 'error': return '🔴';
    case 'warning': return '🟡';
    case 'info': return '🔵';
    default: return '⚠️';
  }
}

/**
 * Detect context (platform, action type)
 */
function detectContext(field) {
  const url = window.location.href;
  let platform = 'generic';
  
  if (url.includes('twitter.com') || url.includes('x.com')) {
    platform = 'twitter';
  } else if (url.includes('facebook.com')) {
    platform = 'facebook';
  } else if (url.includes('instagram.com')) {
    platform = 'instagram';
  } else if (url.includes('reddit.com')) {
    platform = 'reddit';
  } else if (url.includes('linkedin.com')) {
    platform = 'linkedin';
  }
  
  // Detect if it's a reply based on field context
  const isReply = detectIsReply(field, platform);
  
  return {
    platform,
    isReply,
    mode: currentMode,
    url: window.location.href
  };
}

/**
 * Detect if the current field is for a reply
 */
function detectIsReply(field, platform) {
  // Check common reply indicators
  const replyIndicators = [
    '[data-testid*="reply"]',
    '.reply',
    '[aria-label*="reply" i]',
    '[aria-label*="Reply"]',
    '[aria-label*="comment" i]',
    '[aria-label*="Comment"]',
    '[placeholder*="reply" i]',
    '[placeholder*="comment" i]'
  ];
  
  for (const selector of replyIndicators) {
    if (field.matches && field.matches(selector)) return true;
    if (field.closest && field.closest(selector)) return true;
  }
  
  // Platform-specific reply detection
  switch (platform) {
    case 'twitter':
      return field.closest('[data-testid="reply"]') !== null ||
             field.closest('[aria-label*="Reply"]') !== null;
    case 'facebook':
      return field.closest('[aria-label*="Write a comment"]') !== null ||
             field.closest('[aria-label*="Reply"]') !== null ||
             (field.getAttribute('aria-label') || '').toLowerCase().includes('comment');
    case 'instagram':
      return field.closest('[aria-label*="Add a comment"]') !== null ||
             (field.getAttribute('placeholder') || '').toLowerCase().includes('comment');
    case 'reddit':
      return field.closest('.Comment') !== null ||
             field.closest('[data-testid*="comment"]') !== null;
    case 'linkedin':
      return field.closest('[aria-label*="comment" i]') !== null;
    default:
      return false;
  }
}

/**
 * Enable reading mode (hover to analyze)
 */
function enableReadingMode() {
  console.log('📖 Enabling reading mode');
  
  // Find posts/comments on the page
  const contentSelectors = [
    '[data-testid="tweet"]',  // Twitter
    '[data-testid="tweetText"]',
    '.post',                  // Generic
    'article',                // Generic
    '[role="article"]',       // Generic
    '.Comment',               // Reddit
    '.thing',                 // Reddit old
  ];
  
  contentSelectors.forEach(selector => {
    const elements = document.querySelectorAll(selector);
    elements.forEach(element => {
      if (!element.dataset.reasoningReading) {
        element.dataset.reasoningReading = 'true';
        element.addEventListener('mouseenter', handleContentHover);
      }
    });
  });
  
  // Also observe for new content
  const observer = new MutationObserver(() => {
    contentSelectors.forEach(selector => {
      const elements = document.querySelectorAll(selector);
      elements.forEach(element => {
        if (!element.dataset.reasoningReading) {
          element.dataset.reasoningReading = 'true';
          element.addEventListener('mouseenter', handleContentHover);
        }
      });
    });
  });
  
  observer.observe(document.body, { childList: true, subtree: true });
}

/**
 * Handle hover on content (reading mode)
 */
async function handleContentHover(event) {
  const element = event.currentTarget;
  
  // Avoid re-analyzing
  if (element.dataset.analyzed) return;
  
  const text = element.innerText;
  if (text.length < MIN_TEXT_LENGTH) return;
  
  // Mark as being analyzed
  element.dataset.analyzed = 'pending';
  
  try {
    const response = await new Promise((resolve) => {
      chrome.runtime.sendMessage(
        {
          action: 'detectFallacies',
          data: { text }
        },
        resolve
      );
    });
    
    element.dataset.analyzed = 'true';
    
    if (response && response.success && response.data.fallacies && response.data.fallacies.length > 0) {
      highlightFallacies(element, response.data);
    } else {
      // Mark as clean (no badge needed)
      element.dataset.analyzed = 'clean';
    }
  } catch (error) {
    console.error('Error detecting fallacies:', error);
    element.dataset.analyzed = 'error';
  }
}

/**
 * Highlight fallacies in content
 */
function highlightFallacies(element, data) {
  const { fallacies, overallAssessment, reasoningQuality } = data;
  
  // Add visual indicator badge
  const badge = document.createElement('div');
  badge.className = `reasoning-badge reasoning-badge-${reasoningQuality || 'moderate'}`;
  
  const count = fallacies.length;
  badge.innerHTML = `
    <span class="reasoning-badge-icon">⚠️</span>
    <span class="reasoning-badge-text">${count} fallac${count === 1 ? 'y' : 'ies'}</span>
  `;
  
  badge.onclick = (e) => {
    e.stopPropagation();
    showFallacyDetails(element, data);
  };
  
  // Position badge
  element.style.position = element.style.position || 'relative';
  element.appendChild(badge);
}

/**
 * Show fallacy details in modal
 */
function showFallacyDetails(element, data) {
  const { fallacies, overallAssessment } = data;
  
  // Remove any existing modal
  const existingModal = document.querySelector('.reasoning-modal');
  if (existingModal) existingModal.remove();
  
  const modal = document.createElement('div');
  modal.className = 'reasoning-modal';
  modal.innerHTML = `
    <div class="reasoning-modal-content">
      <div class="reasoning-modal-header">
        <h3>🔍 Detected Fallacies</h3>
        <button class="reasoning-modal-close">×</button>
      </div>
      <div class="reasoning-modal-body">
        ${fallacies.map(f => `
          <div class="reasoning-fallacy-item ${f.isVerified ? 'verified' : ''}">
            <div class="reasoning-fallacy-header">
              <h4>${f.type}${f.alias ? ` (${f.alias})` : ''}</h4>
              ${f.isVerified ? '<span class="reasoning-verified-badge">✓ Verified</span>' : ''}
            </div>
            <p class="reasoning-fallacy-explanation">${f.explanation || f.description}</p>
            ${f.excerpt ? `<p class="reasoning-fallacy-excerpt">"${f.excerpt}"</p>` : ''}
            ${f.modelMatch ? `<p class="reasoning-fallacy-definition"><strong>Definition:</strong> ${f.modelMatch.definition}</p>` : ''}
          </div>
        `).join('')}
        ${overallAssessment ? `<div class="reasoning-modal-assessment">${overallAssessment}</div>` : ''}
      </div>
    </div>
  `;
  
  document.body.appendChild(modal);
  
  // Close handlers
  modal.querySelector('.reasoning-modal-close').onclick = () => modal.remove();
  modal.onclick = (e) => {
    if (e.target === modal) modal.remove();
  };
  
  // Close on escape
  const escHandler = (e) => {
    if (e.key === 'Escape') {
      modal.remove();
      document.removeEventListener('keydown', escHandler);
    }
  };
  document.addEventListener('keydown', escHandler);
}

// ═══════════════════════════════════════════════════════════════════════════
// FLOATING CHATBOT FEATURE
// ═══════════════════════════════════════════════════════════════════════════
// 
// This feature provides an opt-in floating chatbot that:
// - Reuses the same unified backend endpoint (/api/analyze_dual)
// - Supports dual-mode responses (Support + Defence)
// - Auto-captures selected text when available
// - Does NOT interfere with real-time detection (independent toggle)
// 
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Inject the floating chatbot icon into the page
 * Only called when enableChatbot is true
 */
function injectFloatingChatbot() {
  // Don't duplicate
  if (floatingChatbotIcon) return;
  
  // Create floating icon button
  floatingChatbotIcon = document.createElement('div');
  floatingChatbotIcon.id = 'LOGICLENS-floating-chatbot-icon';
  floatingChatbotIcon.className = 'LOGICLENS-floating-icon';
  floatingChatbotIcon.innerHTML = `
    <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M12 2C6.48 2 2 6.48 2 12C2 17.52 6.48 22 12 22C13.33 22 14.6 21.73 15.77 21.24L22 22L20.76 18.23C21.53 16.73 22 15.02 22 13.24C22 7.24 17.52 2 12 2Z" fill="currentColor"/>
      <circle cx="8" cy="12" r="1.5" fill="white"/>
      <circle cx="12" cy="12" r="1.5" fill="white"/>
      <circle cx="16" cy="12" r="1.5" fill="white"/>
    </svg>
  `;
  floatingChatbotIcon.title = 'Logic Lens Chat - Analyze Arguments';
  
  // Click handler - captures selection and opens chat
  floatingChatbotIcon.addEventListener('click', handleFloatingIconClick);
  
  document.body.appendChild(floatingChatbotIcon);
  
  // Animate in
  requestAnimationFrame(() => {
    floatingChatbotIcon.classList.add('visible');
  });
  
  console.log('💬 Floating chatbot icon injected');
}

/**
 * Remove the floating chatbot from the page
 */
function removeFloatingChatbot() {
  if (floatingChatbotIcon) {
    floatingChatbotIcon.classList.remove('visible');
    setTimeout(() => {
      floatingChatbotIcon?.remove();
      floatingChatbotIcon = null;
    }, 200);
  }
  
  if (floatingChatPanel) {
    closeChatPanel();
  }
  
  console.log('💬 Floating chatbot removed');
}

/**
 * Handle click on floating chatbot icon
 * 
 * ┌──────────────────────────────────────────────────────────────────┐
 * │ AUTO-CAPTURE SELECTION BEHAVIOR:                                │
 * │                                                                  │
 * │ Step 1: Check for selected text using browser Selection API     │
 * │ Step 2: If selection exists → auto-paste and auto-submit        │
 * │ Step 3: If no selection → open chat for manual input            │
 * │                                                                  │
 * │ IMPORTANT: Selection is treated READ-ONLY, never altered        │
 * └──────────────────────────────────────────────────────────────────┘
 */
function handleFloatingIconClick() {
  // Get any selected text on the page (read-only capture)
  const selection = window.getSelection();
  const selectedText = selection ? selection.toString().trim() : '';
  
  // Open the chat panel
  openChatPanel();
  
  // If there's selected text, auto-fill and auto-submit
  if (selectedText.length >= MIN_TEXT_LENGTH) {
    console.log('📋 Auto-capturing selected text:', selectedText.substring(0, 50) + '...');
    
    // Fill the input with selected text (verbatim, no alteration)
    const input = floatingChatPanel?.querySelector('.LOGICLENS-chat-input');
    if (input) {
      input.value = selectedText;
      // Auto-submit after a brief delay for UX
      setTimeout(() => {
        submitChatMessage(selectedText);
      }, 100);
    }
  }
}

/**
 * Open the floating chat panel
 */
function openChatPanel() {
  // Don't duplicate
  if (floatingChatPanel) {
    floatingChatPanel.classList.add('visible');
    return;
  }
  
  // Create chat panel
  floatingChatPanel = document.createElement('div');
  floatingChatPanel.id = 'LOGICLENS-floating-chat-panel';
  floatingChatPanel.className = 'LOGICLENS-chat-panel';
  
  floatingChatPanel.innerHTML = `
    <div class="LOGICLENS-chat-header">
      <div class="LOGICLENS-chat-title">
        <span class="LOGICLENS-chat-logo">🧠</span>
        <span>Logic Lens Chat</span>
      </div>
      <button class="LOGICLENS-chat-close" aria-label="Close chat">×</button>
    </div>
    
    <div class="LOGICLENS-chat-messages" id="LOGICLENS-chat-messages">
      <div class="LOGICLENS-chat-welcome">
        <p>👋 Welcome! Paste or type an argument to analyze.</p>
        <p class="LOGICLENS-chat-hint">💡 Tip: Select text on the page and click the chat icon to auto-analyze!</p>
      </div>
    </div>
    
    <div class="LOGICLENS-chat-input-area">
      <textarea 
        class="LOGICLENS-chat-input" 
        placeholder="Type or paste an argument to analyze..."
        rows="2"
      ></textarea>
      <button class="LOGICLENS-chat-send" aria-label="Send">
        <span class="LOGICLENS-send-icon">➤</span>
      </button>
    </div>
  `;
  
  // Add event listeners
  floatingChatPanel.querySelector('.LOGICLENS-chat-close').addEventListener('click', closeChatPanel);
  
  const input = floatingChatPanel.querySelector('.LOGICLENS-chat-input');
  const sendBtn = floatingChatPanel.querySelector('.LOGICLENS-chat-send');
  
  sendBtn.addEventListener('click', () => {
    const text = input.value.trim();
    if (text.length >= MIN_TEXT_LENGTH) {
      submitChatMessage(text);
    }
  });
  
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      const text = input.value.trim();
      if (text.length >= MIN_TEXT_LENGTH) {
        submitChatMessage(text);
      }
    }
  });
  
  document.body.appendChild(floatingChatPanel);
  
  // Animate in
  requestAnimationFrame(() => {
    floatingChatPanel.classList.add('visible');
    input.focus();
  });
}

/**
 * Close the chat panel
 */
function closeChatPanel() {
  if (floatingChatPanel) {
    floatingChatPanel.classList.remove('visible');
    setTimeout(() => {
      floatingChatPanel?.remove();
      floatingChatPanel = null;
    }, 200);
  }
}

/**
 * Submit a message to the chat
 * Calls the unified dual-mode backend endpoint
 */
async function submitChatMessage(text) {
  const messagesContainer = floatingChatPanel?.querySelector('#LOGICLENS-chat-messages');
  const input = floatingChatPanel?.querySelector('.LOGICLENS-chat-input');
  const sendBtn = floatingChatPanel?.querySelector('.LOGICLENS-chat-send');
  
  if (!messagesContainer || !input) return;
  
  // Clear welcome message if present
  const welcome = messagesContainer.querySelector('.LOGICLENS-chat-welcome');
  if (welcome) welcome.remove();
  
  // Add user message
  addChatMessage(text, 'user');
  
  // Clear input
  input.value = '';
  input.disabled = true;
  sendBtn.disabled = true;
  
  // Add loading indicator
  const loadingId = addChatMessage('Analyzing your argument...', 'loading');
  
  try {
    // Call the dual-mode endpoint (same as dedicated chatbot)
    // This returns BOTH support and defence in one request
    const response = await new Promise((resolve, reject) => {
      chrome.runtime.sendMessage(
        {
          action: 'analyzeDualMode',
          data: { text }
        },
        (response) => {
          if (chrome.runtime.lastError) {
            reject(new Error(chrome.runtime.lastError.message));
          } else {
            resolve(response);
          }
        }
      );
    });
    
    // Remove loading
    removeChatMessage(loadingId);
    
    if (response.success) {
      // Cache the dual response for mode toggling
      currentDualResponse = response.data;
      currentDisplayMode = 'support'; // Default to support mode
      
      // Display the response (support mode by default)
      addResponseMessage(response.data, 'support');
    } else {
      addChatMessage(`Error: ${response.error}`, 'error');
    }
  } catch (error) {
    removeChatMessage(loadingId);
    addChatMessage(`Error: ${error.message}`, 'error');
  } finally {
    input.disabled = false;
    sendBtn.disabled = false;
    input.focus();
  }
}

/**
 * Add a message to the chat
 */
function addChatMessage(content, type) {
  const messagesContainer = floatingChatPanel?.querySelector('#LOGICLENS-chat-messages');
  if (!messagesContainer) return null;
  
  const messageId = `msg-${Date.now()}`;
  const messageDiv = document.createElement('div');
  messageDiv.id = messageId;
  messageDiv.className = `LOGICLENS-chat-message LOGICLENS-chat-${type}`;
  
  if (type === 'loading') {
    messageDiv.innerHTML = `
      <div class="LOGICLENS-chat-loading">
        <div class="LOGICLENS-chat-spinner"></div>
        <span>${content}</span>
      </div>
    `;
  } else if (type === 'user') {
    messageDiv.innerHTML = `<div class="LOGICLENS-chat-user-text">${escapeHtml(content)}</div>`;
  } else if (type === 'error') {
    messageDiv.innerHTML = `<div class="LOGICLENS-chat-error-text">⚠️ ${escapeHtml(content)}</div>`;
  }
  
  messagesContainer.appendChild(messageDiv);
  messagesContainer.scrollTop = messagesContainer.scrollHeight;
  
  chatHistory.push({ id: messageId, content, type });
  return messageId;
}

/**
 * Remove a message from chat
 */
function removeChatMessage(messageId) {
  const message = floatingChatPanel?.querySelector(`#${messageId}`);
  if (message) message.remove();
  chatHistory = chatHistory.filter(m => m.id !== messageId);
}

/**
 * Add a response message with mode toggle
 * 
 * ┌──────────────────────────────────────────────────────────────────┐
 * │ DUAL-MODE RESPONSE DISPLAY:                                     │
 * │                                                                  │
 * │ - Displays Support mode by default                              │
 * │ - Mode toggle switches WITHOUT additional API calls             │
 * │ - Full response rendered verbatim from backend                  │
 * └──────────────────────────────────────────────────────────────────┘
 */
function addResponseMessage(dualResponse, mode) {
  const messagesContainer = floatingChatPanel?.querySelector('#LOGICLENS-chat-messages');
  if (!messagesContainer) return;
  
  const response = mode === 'support' ? dualResponse.support : dualResponse.defence;
  const messageId = `response-${Date.now()}`;
  
  const messageDiv = document.createElement('div');
  messageDiv.id = messageId;
  messageDiv.className = 'LOGICLENS-chat-message LOGICLENS-chat-response';
  messageDiv.dataset.dualResponse = JSON.stringify(dualResponse);
  
  // Build the response content
  messageDiv.innerHTML = `
    <div class="LOGICLENS-chat-mode-toggle">
      <button class="LOGICLENS-mode-btn ${mode === 'support' ? 'active' : ''}" data-mode="support">
        ✅ Support
      </button>
      <button class="LOGICLENS-mode-btn ${mode === 'defence' ? 'active' : ''}" data-mode="defence">
        ⚔️ Defence
      </button>
    </div>
    <div class="LOGICLENS-chat-response-content">
      ${renderChatResponse(response, mode)}
    </div>
  `;
  
  // Add mode toggle handlers
  messageDiv.querySelectorAll('.LOGICLENS-mode-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const newMode = btn.dataset.mode;
      if (newMode !== currentDisplayMode) {
        currentDisplayMode = newMode;
        // Update the display WITHOUT making a new API call
        updateResponseDisplay(messageDiv, dualResponse, newMode);
      }
    });
  });
  
  // Attach View More toggle handlers
  attachViewMoreHandlers(messageDiv);
  
  messagesContainer.appendChild(messageDiv);
  messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

/**
 * Update response display when mode is toggled
 * NO additional backend request - uses cached dual response
 */
function updateResponseDisplay(messageDiv, dualResponse, mode) {
  const response = mode === 'support' ? dualResponse.support : dualResponse.defence;
  
  // Update toggle buttons
  messageDiv.querySelectorAll('.LOGICLENS-mode-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.mode === mode);
  });
  
  // Update content
  const contentDiv = messageDiv.querySelector('.LOGICLENS-chat-response-content');
  if (contentDiv) {
    contentDiv.innerHTML = renderChatResponse(response, mode);
    // Attach View More toggle handlers
    attachViewMoreHandlers(contentDiv);
  }
}

/**
 * Attach click handlers for View More toggle buttons
 */
function attachViewMoreHandlers(container) {
  container.querySelectorAll('.LOGICLENS-viewmore-toggle').forEach(toggle => {
    toggle.addEventListener('click', () => {
      const targetId = toggle.dataset.target;
      const content = document.getElementById(targetId);
      if (content) {
        const isExpanded = toggle.classList.contains('expanded');
        toggle.classList.toggle('expanded');
        content.classList.toggle('expanded');
        
        // Update arrow and text
        const arrow = toggle.querySelector('.LOGICLENS-viewmore-arrow');
        const text = toggle.querySelector('.LOGICLENS-viewmore-text');
        if (arrow) arrow.textContent = isExpanded ? '▼' : '▲';
        if (text) text.textContent = isExpanded ? 'View More' : 'Hide Details';
      }
    });
  });
}

/**
 * Render the response content (verbatim from backend)
 * Enhanced for better readability in the floating chatbot
 */
function renderChatResponse(response, mode) {
  if (!response) return '<p class="LOGICLENS-no-response">No response available</p>';
  
  const modeLabel = mode === 'support' ? 'Supporting Analysis' : 'Counter-Argument Analysis';
  
  let html = `<div class="LOGICLENS-response-header-label">${modeLabel}</div>`;
  
  // For Defence mode, show counter-argument first
  if (mode === 'defence') {
    // Counter-argument (main content for defence)
    let counterArg = response.response || response.counter_argument || response.raw_response || '';
    
    // Robust parsing to extract clean text from various formats
    if (counterArg) {
      let displayText = counterArg;
      
      // If it's a string, try to parse it
      if (typeof counterArg === 'string') {
        let text = counterArg.trim();
        
        // Try to parse as JSON if it looks like JSON
        if (text.startsWith('{') || text.startsWith('[')) {
          try {
            const parsed = JSON.parse(text);
            
            // Extract text from various possible keys
            if (typeof parsed === 'object' && parsed !== null) {
              displayText = parsed.argument || 
                          parsed.counter_argument || 
                          parsed.response || 
                          parsed.text ||
                          parsed.content ||
                          parsed.message;
              
              // If still an object/array, try to stringify and extract
              if (typeof displayText === 'object') {
                displayText = JSON.stringify(parsed);
              }
            }
          } catch (e) {
            // Not valid JSON, use as-is
            displayText = text;
          }
        }
      }
      
      // Final cleanup: ensure it's a string
      if (typeof displayText !== 'string') {
        displayText = String(displayText);
      }
      
      // Remove any remaining JSON formatting artifacts
      displayText = displayText
        .replace(/^["']|["']$/g, '')  // Remove quotes at start/end
        .replace(/\\n/g, '\n')         // Convert escaped newlines
        .replace(/\\"/g, '"')          // Convert escaped quotes
        .trim();
      
      html += `
        <div class="LOGICLENS-response-block LOGICLENS-defence-block">
          <div class="LOGICLENS-block-header">
            <span class="LOGICLENS-block-icon">⚔️</span>
            <span class="LOGICLENS-block-title">Challenge Initiated</span>
          </div>
          <div class="LOGICLENS-block-content LOGICLENS-counter-text">${escapeHtml(displayText)}</div>
        </div>
      `;
    } else {
      html += `
        <div class="LOGICLENS-response-block">
          <div class="LOGICLENS-block-content LOGICLENS-no-content">No counter-argument generated.</div>
        </div>
      `;
    }
    
    return html;
  }
  
  // SUPPORT MODE: Show Improved Statement by default, rest in collapsible
  
  // Improved Statement (always visible - main content)
  // Try multiple possible locations for improved_statement
  const improvedStatement = response.improved_statement || 
                           response.suggestions?.[0]?.text || 
                           response.raw_response?.improved_statement ||
                           '';
  
  if (improvedStatement) {
    html += `
      <div class="LOGICLENS-response-block LOGICLENS-improved-block">
        <div class="LOGICLENS-block-header">
          <span class="LOGICLENS-block-icon">💡</span>
          <span class="LOGICLENS-block-title">Improved Statement</span>
        </div>
        <div class="LOGICLENS-block-content">${escapeHtml(improvedStatement)}</div>
      </div>
    `;
  } else {
    // Fallback: show that no improved statement was generated
    html += `
      <div class="LOGICLENS-response-block LOGICLENS-improved-block">
        <div class="LOGICLENS-block-header">
          <span class="LOGICLENS-block-icon">💡</span>
          <span class="LOGICLENS-block-title">Improved Statement</span>
        </div>
        <div class="LOGICLENS-block-content LOGICLENS-no-content">No improved statement generated.</div>
      </div>
    `;
  }
  
  // Check if there's any additional content to show
  const hasFeedback = response.feedback;
  const hasInsights = response.insights;
  const hasFallacies = response.fallacy_details && response.fallacy_details.length > 0;
  const hasToulmin = response.elements && Object.keys(response.elements).length > 0;
  const hasAdditionalContent = hasFeedback || hasInsights || hasFallacies || hasToulmin;
  
  if (hasAdditionalContent) {
    // Unique ID for this collapsible section
    const collapseId = `LOGICLENS-collapse-${Date.now()}`;
    
    // View More toggle button
    html += `
      <div class="LOGICLENS-viewmore-toggle" data-target="${collapseId}">
        <div class="LOGICLENS-viewmore-label">
          <span class="LOGICLENS-viewmore-icon">📋</span>
          <span class="LOGICLENS-viewmore-text">View More</span>
        </div>
        <span class="LOGICLENS-viewmore-arrow">▼</span>
      </div>
    `;
    
    // Collapsible content container (hidden by default)
    html += `<div class="LOGICLENS-viewmore-content" id="${collapseId}">`;
    
    // Feedback
    if (hasFeedback) {
      html += `
        <div class="LOGICLENS-response-block">
          <div class="LOGICLENS-block-header">
            <span class="LOGICLENS-block-icon">💬</span>
            <span class="LOGICLENS-block-title">Feedback</span>
          </div>
          <div class="LOGICLENS-block-content LOGICLENS-feedback-text">${escapeHtml(response.feedback)}</div>
        </div>
      `;
    }
    
    // Insights
    if (hasInsights) {
      html += `
        <div class="LOGICLENS-response-block">
          <div class="LOGICLENS-block-header">
            <span class="LOGICLENS-block-icon">💡</span>
            <span class="LOGICLENS-block-title">Insights</span>
          </div>
          <div class="LOGICLENS-block-content LOGICLENS-insights-text">${escapeHtml(response.insights)}</div>
        </div>
      `;
    }
    
    // Fallacies (if any detected)
    if (hasFallacies) {
      html += `
        <div class="LOGICLENS-response-block LOGICLENS-fallacy-block">
          <div class="LOGICLENS-block-header">
            <span class="LOGICLENS-block-icon">⚠️</span>
            <span class="LOGICLENS-block-title">Detected Fallacies</span>
          </div>
          <div class="LOGICLENS-fallacy-list">
            ${response.fallacy_details.map(f => `
              <div class="LOGICLENS-fallacy-item ${getFallacyClass(f.score)}">
                <span class="LOGICLENS-fallacy-name">${escapeHtml(f.label)}</span>
                <span class="LOGICLENS-fallacy-score">${Math.round((f.score || 0) * 100)}%</span>
              </div>
            `).join('')}
          </div>
        </div>
      `;
    }
    
    // Toulmin Elements (compact visual bars)
    if (hasToulmin) {
      html += `
        <div class="LOGICLENS-response-block LOGICLENS-toulmin-block">
          <div class="LOGICLENS-block-header">
            <span class="LOGICLENS-block-icon">📐</span>
            <span class="LOGICLENS-block-title">Argument Structure</span>
          </div>
          <div class="LOGICLENS-toulmin-grid">
            ${renderToulminCompact(response.elements)}
          </div>
        </div>
      `;
    }
    
    html += `</div>`; // Close collapsible content
  }
  
  return html;
}

/**
 * Render Toulmin elements in compact format with visual bars
 */
function renderToulminCompact(elements) {
  const factors = ['claim', 'data', 'warrant', 'backing', 'qualifier', 'rebuttal'];
  const labels = { 
    claim: 'Claim', 
    data: 'Evidence', 
    warrant: 'Warrant', 
    backing: 'Backing', 
    qualifier: 'Qualifier', 
    rebuttal: 'Rebuttal' 
  };
  const icons = {
    claim: '🎯',
    data: '📊',
    warrant: '🔗',
    backing: '🏛️',
    qualifier: '⚖️',
    rebuttal: '🛡️'
  };
  
  return factors.map(factor => {
    const el = elements[factor];
    if (!el) return '';
    const strength = el.strength || 0;
    const scoreClass = strength >= 7 ? 'strong' : strength >= 4 ? 'moderate' : 'weak';
    const percentage = strength * 10;
    const text = el.text || 'No details provided';
    
    return `
      <div class="LOGICLENS-toulmin-row">
        <div class="LOGICLENS-toulmin-label-wrap">
          <span class="LOGICLENS-toulmin-icon">${icons[factor]}</span>
          <span class="LOGICLENS-toulmin-name">${labels[factor]}</span>
        </div>
        <div class="LOGICLENS-toulmin-bar-wrap">
          <div class="LOGICLENS-toulmin-bar">
            <div class="LOGICLENS-toulmin-fill LOGICLENS-${scoreClass}" style="width: ${percentage}%"></div>
          </div>
          <span class="LOGICLENS-toulmin-value">${strength}/10</span>
        </div>
      </div>
      <div class="LOGICLENS-toulmin-detail">${escapeHtml(text)}</div>
    `;
  }).join('');
}

/**
 * Get fallacy CSS class based on confidence score
 */
function getFallacyClass(score) {
  const percentage = (score || 0) * 100;
  if (percentage >= 70) return 'high';
  if (percentage >= 40) return 'medium';
  return 'low';
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

/**
 * Handle messages from background script
 * 
 * ┌──────────────────────────────────────────────────────────────────┐
 * │ SETTINGS REACTIVITY:                                            │
 * │                                                                  │
 * │ - Toggle changes apply instantly without page reload            │
 * │ - Detection and Chatbot toggles are INDEPENDENT                 │
 * │ - Uses message passing for cross-tab synchronization            │
 * └──────────────────────────────────────────────────────────────────┘
 */
function handleBackgroundMessage(message, sender, sendResponse) {
  if (message.action === 'settingsUpdated') {
    isEnabled = message.data.enabled ?? isEnabled;
    currentMode = message.data.mode ?? currentMode;
    
    // Update independent feature toggles
    const prevDetection = enableDetection;
    const prevChatbot = enableChatbot;
    
    enableDetection = message.data.enableDetection ?? enableDetection;
    enableChatbot = message.data.enableChatbot ?? enableChatbot;
    
    console.log(`⚙️ Settings updated: enabled=${isEnabled}, detection=${enableDetection}, chatbot=${enableChatbot}`);
    
    // Apply feature toggles if changed
    if (prevDetection !== enableDetection || prevChatbot !== enableChatbot) {
      applyFeatureToggles();
    }
    
    if (currentMode === 'reading') {
      enableReadingMode();
    }
  }
  
  sendResponse({ received: true });
}

/**
 * Apply feature toggles - inject/remove UI elements based on settings
 * 
 * IMPORTANT: Detection and Chatbot toggles are INDEPENDENT
 * - Toggling chatbot does NOT affect detection
 * - Toggling detection does NOT affect chatbot
 */
function applyFeatureToggles() {
  // Handle floating chatbot toggle
  if (enableChatbot && isEnabled) {
    injectFloatingChatbot();
  } else {
    removeFloatingChatbot();
  }
  
  // Detection toggle affects the text field observers
  // If detection is disabled, hide all activation buttons
  if (!enableDetection || !isEnabled) {
    // Clean up all existing buttons
    buttonElements.forEach((button, field) => {
      hideActivationButton(field);
    });
  }
}

/**
 * Handle text selection - show analyse button
 * This is separate from the floating chatbot button and works for any selected text on the page
 */
function handleTextSelection() {
  // Don't show analyse button if extension or chatbot is disabled
  if (!isEnabled || !enableChatbot) {
    hideSelectionAnalyseButton();
    return;
  }
  
  const selection = window.getSelection();
  
  // Check if there's actual text selected
  if (!selection || selection.toString().trim().length === 0) {
    hideSelectionAnalyseButton();
    return;
  }
  
  const selectedText = selection.toString().trim();
  
  // Only show if text meets minimum length requirement
  if (selectedText.length < MIN_TEXT_LENGTH) {
    hideSelectionAnalyseButton();
    return;
  }
  
  // Store the selected text
  lastSelectedText = selectedText;
  
  // Get the position of the selection
  const range = selection.getRangeAt(0);
  const rect = range.getBoundingClientRect();
  
  // Show the analyse button
  showSelectionAnalyseButton(rect);
}

/**
 * Show the analyse button near the selected text
 */
function showSelectionAnalyseButton(selectionRect) {
  // Create button if it doesn't exist
  if (!selectionAnalyseButton) {
    selectionAnalyseButton = document.createElement('button');
    selectionAnalyseButton.className = 'reasoning-selection-analyse-btn';
    selectionAnalyseButton.textContent = '📋 Analyse';
    selectionAnalyseButton.addEventListener('click', handleSelectionAnalyseClick);
    document.body.appendChild(selectionAnalyseButton);
  }
  
  // Position the button using absolute positioning (document coordinates)
  // Place it above the selection or below if not enough space in viewport
  let top = selectionRect.top + window.scrollY - 40;
  let left = selectionRect.left + window.scrollX + (selectionRect.width / 2) - 45; // center above selection
  
  // Check if button would go off-screen vertically in current viewport
  if (selectionRect.top < 50) {
    // Not enough space above in viewport, place below
    top = selectionRect.bottom + window.scrollY + 10;
  }
  
  // Clamp horizontal position
  const minLeft = window.scrollX + 10;
  const maxLeft = window.scrollX + window.innerWidth - 110;
  
  if (left < minLeft) {
    left = minLeft;
  } else if (left > maxLeft) {
    left = maxLeft;
  }
  
  selectionAnalyseButton.style.top = top + 'px';
  selectionAnalyseButton.style.left = left + 'px';
  
  // Show with animation
  requestAnimationFrame(() => {
    selectionAnalyseButton.classList.add('visible');
  });
}

/**
 * Hide the analyse button
 */
function hideSelectionAnalyseButton() {
  if (selectionAnalyseButton) {
    selectionAnalyseButton.classList.remove('visible');
  }
}

/**
 * Handle click on the selection analyse button
 * Opens the chat panel with the selected text and auto-submits it in support mode
 */
function handleSelectionAnalyseClick() {
  if (!lastSelectedText || lastSelectedText.length === 0) {
    return;
  }
  
  // Hide the analyse button
  hideSelectionAnalyseButton();
  
  // Ensure the chatbot is injected (in case it wasn't already)
  if (!floatingChatbotIcon && enableChatbot && isEnabled) {
    injectFloatingChatbot();
  }
  
  // Open the chat panel
  openChatPanel();
  
  // Auto-fill and auto-submit the selected text
  console.log('📋 Analyse button: Auto-submitting selected text:', lastSelectedText.substring(0, 50) + '...');
  
  // Wait for the panel to be fully rendered and visible
  setTimeout(() => {
    const input = floatingChatPanel?.querySelector('.LOGICLENS-chat-input');
    if (input) {
      input.value = lastSelectedText;
      // Trigger input event to notify any listeners
      input.dispatchEvent(new Event('input', { bubbles: true }));
      
      // Auto-submit the message
      submitChatMessage(lastSelectedText);
    } else {
      console.error('❌ Could not find chat input element');
    }
  }, 150);
}

