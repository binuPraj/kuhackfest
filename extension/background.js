/**
 * Background Service Worker (Manifest V3)
 * 
 * Responsibilities:
 * - Handle API communication with backend
 * - Manage rate limiting and retries
 * - Cache recent analyses for performance
 * - Orchestrate message passing between content scripts
 * - Support Toulmin model analysis and verified fallacy detection
 */

const API_BASE_URL = 'http://localhost:5001/api';
const CACHE_DURATION = 5 * 60 * 1000; // 5 minutes
const REQUEST_TIMEOUT = 30000; // 30 seconds
const MAX_RETRIES = 2;
const analysisCache = new Map();

// Extension installation
chrome.runtime.onInstalled.addListener(() => {
  console.log('🧠 Reasoning Assistant installed');
  
  // Set default state - includes independent feature toggles
  chrome.storage.sync.set({
    enabled: true,
    mode: 'writing', // 'writing' | 'reading' | 'reply'
    showSuggestions: true,
    showToulminAnalysis: true,
    autoRewrite: false,
    enableDetection: true,   // Real-time text field detection (independent)
    enableChatbot: true      // Floating chatbot feature (independent)
  });
  
  // Check backend health
  checkBackendHealth();
});

// Check backend health on startup
chrome.runtime.onStartup.addListener(() => {
  console.log('🧠 Reasoning Assistant starting...');
  checkBackendHealth();
});

/**
 * Check if backend is available
 */
async function checkBackendHealth() {
  try {
    const response = await fetchWithTimeout(`${API_BASE_URL}/health`, {
      method: 'GET'
    }, 5000);
    
    if (response.ok) {
      const data = await response.json();
      console.log('✅ Backend connected:', data.provider);
    } else {
      console.warn('⚠️ Backend returned error:', response.status);
    }
  } catch (error) {
    console.warn('⚠️ Backend not available:', error.message);
  }
}

/**
 * Fetch with timeout wrapper
 */
async function fetchWithTimeout(url, options = {}, timeout = REQUEST_TIMEOUT) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);
  
  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal
    });
    clearTimeout(timeoutId);
    return response;
  } catch (error) {
    clearTimeout(timeoutId);
    if (error.name === 'AbortError') {
      throw new Error('Request timed out');
    }
    throw error;
  }
}

/**
 * Make API request with retry logic
 */
async function apiRequest(endpoint, data, retries = MAX_RETRIES) {
  let lastError;
  
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const response = await fetchWithTimeout(`${API_BASE_URL}${endpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(data),
      });
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `API error: ${response.status}`);
      }
      
      return await response.json();
    } catch (error) {
      lastError = error;
      console.warn(`⚠️ API attempt ${attempt + 1} failed:`, error.message);
      
      if (attempt < retries) {
        // Exponential backoff: 1s, 2s
        await new Promise(resolve => setTimeout(resolve, 1000 * (attempt + 1)));
      }
    }
  }
  
  throw lastError;
}

/**
 * Main message handler
 * Routes messages from content scripts to appropriate handlers
 */
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  console.log('📨 Background received:', request.action);
  
  switch (request.action) {
    case 'analyzeText':
      handleAnalyzeText(request.data, sendResponse);
      return true; // Keep channel open for async response
      
    case 'analyzeDualMode':
      // NEW: Dual-mode analysis for floating chatbot
      // Returns both support and defence responses in one request
      handleAnalyzeDualMode(request.data, sendResponse);
      return true;
      
    case 'generateReply':
      handleGenerateReply(request.data, sendResponse);
      return true;
      
    case 'detectFallacies':
      handleDetectFallacies(request.data, sendResponse);
      return true;
      
    case 'rewriteText':
      handleRewriteText(request.data, sendResponse);
      return true;
      
    case 'getModels':
      handleGetModels(sendResponse);
      return true;
      
    case 'getSettings':
      handleGetSettings(sendResponse);
      return true;
      
    case 'updateSettings':
      handleUpdateSettings(request.data, sendResponse);
      return true;
      
    case 'checkHealth':
      handleCheckHealth(sendResponse);
      return true;
      
    default:
      sendResponse({ success: false, error: 'Unknown action' });
  }
});

/**
 * Analyze text for logical fallacies and reasoning issues
 * Returns Toulmin analysis, detected fallacies, and suggestions
 */
async function handleAnalyzeText(data, sendResponse) {
  try {
    const { text, context } = data;
    
    // Check cache first
    const cacheKey = `analyze_${hashText(text)}`;
    const cached = getFromCache(cacheKey);
    if (cached) {
      console.log('📋 Returning cached analysis');
      sendResponse({ success: true, data: cached, fromCache: true });
      return;
    }
    
    // Call backend API with retry logic
    const result = await apiRequest('/analyze', { text, context });
    
    // Cache the result
    setCache(cacheKey, result);
    
    sendResponse({ success: true, data: result });
  } catch (error) {
    console.error('❌ Error analyzing text:', error);
    sendResponse({ success: false, error: error.message });
  }
}

/**
 * DUAL-MODE ANALYSIS for Floating Chatbot
 * 
 * ┌──────────────────────────────────────────────────────────────────┐
 * │ WHY DUAL-MODE:                                                   │
 * │                                                                  │
 * │ - Single API call returns BOTH support and defence responses     │
 * │ - Mode toggling is UI-only (no additional backend requests)      │
 * │ - Reuses the same unified backend endpoint                       │
 * │ - Maintains architectural integrity                              │
 * └──────────────────────────────────────────────────────────────────┘
 */
async function handleAnalyzeDualMode(data, sendResponse) {
  try {
    const { text } = data;
    
    // Check cache first
    const cacheKey = `dual_${hashText(text)}`;
    const cached = getFromCache(cacheKey);
    if (cached) {
      console.log('📋 Returning cached dual-mode analysis');
      sendResponse({ success: true, data: cached, fromCache: true });
      return;
    }
    
    // Call the unified dual-mode endpoint (same as dedicated chatbot)
    // Backend expects 'argument_text' parameter
    const result = await apiRequest('/analyze_dual', { argument_text: text });
    
    // Cache the result
    setCache(cacheKey, result);
    
    sendResponse({ success: true, data: result });
  } catch (error) {
    console.error('❌ Error in dual-mode analysis:', error);
    sendResponse({ success: false, error: error.message });
  }
}

/**
 * Generate counter-argument reply with multiple tone options
 */
async function handleGenerateReply(data, sendResponse) {
  try {
    const { originalPost, draftReply, tone } = data;
    
    const result = await apiRequest('/generate-reply', { 
      originalPost, 
      draftReply, 
      tone: tone || 'neutral' 
    });
    
    sendResponse({ success: true, data: result });
  } catch (error) {
    console.error('❌ Error generating reply:', error);
    sendResponse({ success: false, error: error.message });
  }
}

/**
 * Detect fallacies in existing content (Reading Mode)
 * Validates against the logicalfallacy.json model
 */
async function handleDetectFallacies(data, sendResponse) {
  try {
    const { text } = data;
    
    // Check cache
    const cacheKey = `fallacies_${hashText(text)}`;
    const cached = getFromCache(cacheKey);
    if (cached) {
      console.log('📋 Returning cached fallacy detection');
      sendResponse({ success: true, data: cached, fromCache: true });
      return;
    }
    
    const result = await apiRequest('/detect-fallacies', { text });
    setCache(cacheKey, result);
    
    sendResponse({ success: true, data: result });
  } catch (error) {
    console.error('❌ Error detecting fallacies:', error);
    sendResponse({ success: false, error: error.message });
  }
}

/**
 * Rewrite text with improved reasoning
 * Uses Toulmin model factors to strengthen arguments
 */
async function handleRewriteText(data, sendResponse) {
  try {
    const { text, issues, style } = data;
    
    const result = await apiRequest('/rewrite', { 
      text, 
      issues, 
      style: style || 'academic' 
    });
    
    sendResponse({ success: true, data: result });
  } catch (error) {
    console.error('❌ Error rewriting text:', error);
    sendResponse({ success: false, error: error.message });
  }
}

/**
 * Get available models info (Toulmin factors, fallacy types)
 */
async function handleGetModels(sendResponse) {
  try {
    const response = await fetchWithTimeout(`${API_BASE_URL}/models`, {
      method: 'GET'
    });
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    
    const result = await response.json();
    sendResponse({ success: true, data: result });
  } catch (error) {
    console.error('❌ Error getting models:', error);
    sendResponse({ success: false, error: error.message });
  }
}

/**
 * Check backend health status
 */
async function handleCheckHealth(sendResponse) {
  try {
    const response = await fetchWithTimeout(`${API_BASE_URL}/health`, {
      method: 'GET'
    }, 5000);
    
    if (!response.ok) {
      throw new Error(`Backend returned ${response.status}`);
    }
    
    const result = await response.json();
    sendResponse({ success: true, data: result });
  } catch (error) {
    sendResponse({ success: false, error: error.message, offline: true });
  }
}

/**
 * Get current settings
 */
async function handleGetSettings(sendResponse) {
  try {
    const settings = await chrome.storage.sync.get([
      'enabled',
      'mode',
      'showSuggestions',
      'showToulminAnalysis',
      'autoRewrite',
      'enableDetection',   // Real-time detection toggle
      'enableChatbot'      // Floating chatbot toggle
    ]);
    sendResponse({ success: true, data: settings });
  } catch (error) {
    sendResponse({ success: false, error: error.message });
  }
}

/**
 * Update settings and notify content scripts
 */
async function handleUpdateSettings(data, sendResponse) {
  try {
    await chrome.storage.sync.set(data);
    
    // Notify all tabs about settings change
    const tabs = await chrome.tabs.query({});
    for (const tab of tabs) {
      try {
        await chrome.tabs.sendMessage(tab.id, {
          action: 'settingsUpdated',
          data
        });
      } catch (e) {
        // Tab might not have content script loaded
      }
    }
    
    sendResponse({ success: true });
  } catch (error) {
    sendResponse({ success: false, error: error.message });
  }
}

/**
 * Simple hash function for cache keys
 */
function hashText(text) {
  let hash = 0;
  for (let i = 0; i < text.length; i++) {
    const char = text.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash; // Convert to 32bit integer
  }
  return hash.toString(36);
}

/**
 * Cache management
 */
function getFromCache(key) {
  const item = analysisCache.get(key);
  if (!item) return null;
  
  // Check if expired
  if (Date.now() - item.timestamp > CACHE_DURATION) {
    analysisCache.delete(key);
    return null;
  }
  
  return item.data;
}

function setCache(key, data) {
  analysisCache.set(key, {
    data,
    timestamp: Date.now()
  });
  
  // Limit cache size (LRU-style eviction)
  if (analysisCache.size > 100) {
    const oldestKey = analysisCache.keys().next().value;
    analysisCache.delete(oldestKey);
  }
}

function clearCache() {
  analysisCache.clear();
  console.log('🗑️ Cache cleared');
}

// Periodic cache cleanup
setInterval(() => {
  const now = Date.now();
  let cleared = 0;
  for (const [key, value] of analysisCache.entries()) {
    if (now - value.timestamp > CACHE_DURATION) {
      analysisCache.delete(key);
      cleared++;
    }
  }
  if (cleared > 0) {
    console.log(`🧹 Cleared ${cleared} expired cache entries`);
  }
}, CACHE_DURATION);

console.log('🧠 Reasoning Assistant: Background worker ready');
