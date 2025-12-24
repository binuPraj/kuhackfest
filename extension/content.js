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
      console.log(`📋 Settings loaded: enabled=${isEnabled}, mode=${currentMode}`);
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
    /* Floating Activation Button - Grammarly Style */
    .reasoning-activate-btn {
      position: absolute;
      width: 32px;
      height: 32px;
      border-radius: 50%;
      background: linear-gradient(135deg, #667eea 0%, #5a67d8 100%);
      border: 2px solid rgba(255, 255, 255, 0.9);
      cursor: pointer;
      z-index: 2147483646;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 2px 12px rgba(102, 126, 234, 0.4);
      transition: all 0.2s ease;
      opacity: 0;
      transform: scale(0.8);
      pointer-events: none;
    }
    
    .reasoning-activate-btn.visible {
      opacity: 1;
      transform: scale(1);
      pointer-events: auto;
    }
    
    .reasoning-activate-btn:hover {
      transform: scale(1.1);
      box-shadow: 0 4px 20px rgba(102, 126, 234, 0.5);
    }
    
    .reasoning-activate-btn:active {
      transform: scale(0.95);
    }
    
    .reasoning-activate-btn.analyzing {
      animation: reasoning-pulse 1.5s ease-in-out infinite;
    }
    
    @keyframes reasoning-pulse {
      0%, 100% { box-shadow: 0 2px 12px rgba(102, 126, 234, 0.4); }
      50% { box-shadow: 0 2px 20px rgba(102, 126, 234, 0.7); }
    }
    
    .reasoning-activate-btn svg {
      width: 18px;
      height: 18px;
      fill: white;
    }
    
    .reasoning-activate-btn .reasoning-spinner-small {
      width: 16px;
      height: 16px;
      border: 2px solid rgba(255, 255, 255, 0.3);
      border-top-color: white;
      border-radius: 50%;
      animation: reasoning-spin 0.8s linear infinite;
    }
    
    @keyframes reasoning-spin {
      to { transform: rotate(360deg); }
    }
    
    /* Tooltip for the button */
    .reasoning-activate-btn::after {
      content: 'Analyze Reasoning';
      position: absolute;
      right: 100%;
      margin-right: 8px;
      padding: 6px 10px;
      background: #1f2937;
      color: white;
      font-size: 12px;
      font-weight: 500;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      border-radius: 6px;
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
      margin-bottom: 12px;
      padding-bottom: 10px;
      border-bottom: 1px solid var(--reasoning-border, #e5e7eb);
    }
    
    .reasoning-panel-title {
      font-size: 14px;
      font-weight: 600;
      color: var(--reasoning-text, #1f2937);
      display: flex;
      align-items: center;
      gap: 8px;
    }
    
    .reasoning-panel-title-icon {
      font-size: 18px;
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
  
  // Find existing text fields
  const textFields = document.querySelectorAll(selectors.join(', '));
  textFields.forEach(attachFieldListeners);
  
  // Watch for dynamically added fields (for SPAs like Twitter, Facebook, Instagram)
  const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      mutation.addedNodes.forEach((node) => {
        if (node.nodeType === 1) { // Element node
          if (node.matches) {
            selectors.forEach(selector => {
              if (node.matches(selector)) {
                attachFieldListeners(node);
              }
            });
          }
          // Check children
          if (node.querySelectorAll) {
            const children = node.querySelectorAll(selectors.join(', '));
            children.forEach(attachFieldListeners);
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
 * Position the activation button at bottom-right of field
 */
function positionActivationButton(button, field) {
  const rect = field.getBoundingClientRect();
  const scrollY = window.scrollY || window.pageYOffset;
  const scrollX = window.scrollX || window.pageXOffset;
  
  // Position at bottom-right corner with small offset
  button.style.position = 'absolute';
  button.style.top = `${rect.bottom + scrollY - 40}px`;
  button.style.left = `${rect.right + scrollX - 40}px`;
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
 * Enhanced with Toulmin analysis and verified fallacies
 */
function displayAnalysisResults(data, field) {
  console.log('📊 Analysis results:', data);
  
  const { fallacies = [], issues = [], suggestions = [], toulminAnalysis, overallAssessment } = data;
  
  // Use fallacies if available, otherwise use legacy issues
  const displayIssues = fallacies.length > 0 ? fallacies : issues;
  
  // Clear previous panel
  clearSuggestions(field);
  
  if (displayIssues.length === 0 && (!toulminAnalysis || isArgumentStrong(toulminAnalysis))) {
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
      Analysis Results
    </div>
  `;
  
  // Close button already added in createOverlay
  overlay.insertBefore(header, overlay.firstChild.nextSibling);
  
  // Add Toulmin score if available
  if (toulminAnalysis) {
    const toulminSection = createToulminSection(toulminAnalysis);
    overlay.appendChild(toulminSection);
  }
  
  // Display each fallacy/issue
  if (displayIssues.length > 0) {
    const issuesSection = document.createElement('div');
    issuesSection.className = 'reasoning-issues-section';
    
    const issuesTitle = document.createElement('div');
    issuesTitle.className = 'reasoning-section-title';
    issuesTitle.innerHTML = `<span class="reasoning-icon">⚠️</span> Detected Issues (${displayIssues.length})`;
    issuesSection.appendChild(issuesTitle);
    
    displayIssues.forEach((issue, index) => {
      const issueElement = createIssueElement(issue, index);
      issuesSection.appendChild(issueElement);
    });
    
    overlay.appendChild(issuesSection);
  }
  
  // Display suggestions if available
  if (suggestions && suggestions.length > 0) {
    const suggestionsContainer = createSuggestionsContainer(suggestions, field);
    overlay.appendChild(suggestionsContainer);
  }
  
  // Add overall assessment if available
  if (overallAssessment) {
    const assessmentDiv = document.createElement('div');
    assessmentDiv.className = 'reasoning-assessment';
    assessmentDiv.textContent = overallAssessment;
    overlay.appendChild(assessmentDiv);
  }
  
  // Position and show overlay
  positionOverlay(overlay, field);
  overlayElements.set(field, overlay);
  activePanelField = field;
}

/**
 * Check if Toulmin analysis indicates a strong argument
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
 * Create Toulmin analysis section
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
    
    suggestionElement.innerHTML = `
      <div class="reasoning-suggestion-text">${suggestion.text}</div>
      ${suggestion.rationale ? `<div class="reasoning-suggestion-rationale">${suggestion.rationale}</div>` : ''}
      <div class="reasoning-suggestion-actions">
        <button class="reasoning-btn reasoning-btn-accept" data-index="${index}">
          ✓ Accept
        </button>
        <button class="reasoning-btn reasoning-btn-edit" data-index="${index}">
          ✎ Edit
        </button>
        <button class="reasoning-btn reasoning-btn-ignore" data-index="${index}">
          ✕ Ignore
        </button>
      </div>
    `;
    
    // Add click handlers
    const acceptBtn = suggestionElement.querySelector('.reasoning-btn-accept');
    acceptBtn.addEventListener('click', () => {
      setFieldText(field, suggestion.text);
      clearSuggestions(field);
      showFeedback(field, '✓ Suggestion applied!', 'success');
    });
    
    const editBtn = suggestionElement.querySelector('.reasoning-btn-edit');
    editBtn.addEventListener('click', () => {
      setFieldText(field, suggestion.text);
      field.focus();
      clearSuggestions(field);
    });
    
    const ignoreBtn = suggestionElement.querySelector('.reasoning-btn-ignore');
    ignoreBtn.addEventListener('click', () => {
      suggestionElement.remove();
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

/**
 * Handle messages from background script
 */
function handleBackgroundMessage(message, sender, sendResponse) {
  if (message.action === 'settingsUpdated') {
    isEnabled = message.data.enabled;
    currentMode = message.data.mode;
    
    console.log(`⚙️ Settings updated: enabled=${isEnabled}, mode=${currentMode}`);
    
    if (currentMode === 'reading') {
      enableReadingMode();
    }
  }
  
  sendResponse({ received: true });
}

console.log('🧠 Reasoning Assistant: Content script ready (Grammarly-style manual mode)');
