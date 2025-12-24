# System Architecture - Unified Flask Backend

## Overview

This repository contains a **unified Flask backend** that powers two AI services:
1. **Web Chatbot** - Interactive argument analysis training
2. **Browser Extension** - Real-time text analysis

Both services share:
- ✅ **One API key** (OpenRouter)
- ✅ **One LLM gateway** (`services/llm_client.py`)
- ✅ **Unified rate limiting** (10 req/min per IP)
- ✅ **Consistent free-tier protection**

---

## Security Architecture

### API Key Protection

```
┌─────────────────────────────────────────────┐
│         Frontend / Extension                │
│   ❌ NO API KEYS                            │
│   ✅ Only calls Flask endpoints             │
└──────────────┬──────────────────────────────┘
               │
               │ HTTP Requests
               │
┌──────────────▼──────────────────────────────┐
│         Flask Backend (Port 5001)           │
│                                             │
│  ┌─────────────────────────────────────┐   │
│  │   services/llm_client.py            │   │
│  │   ✅ API key loaded from .env       │   │
│  │   ✅ Rate limiting (10/min)         │   │
│  │   ✅ Input validation (2000 chars)  │   │
│  │   ✅ Output limits (1500 tokens)    │   │
│  └─────────────────┬───────────────────┘   │
└────────────────────┼───────────────────────┘
                     │
                     │ Authorized Request
                     │
┌────────────────────▼───────────────────────┐
│          OpenRouter API                    │
│    (meta-llama/llama-3.3-70b-instruct)    │
└────────────────────────────────────────────┘
```

### Key Points

1. **API Key Storage**
   - Location: `backend/.env`
   - Variable: `OPENROUTER_API_KEY`
   - Loaded once at Flask startup
   - Never exposed to frontend

2. **Frontend Security**
   - Extension: Only calls `http://localhost:5001/api/*`
   - Web app: Only calls `http://localhost:5001/api/*`
   - No API credentials in JavaScript files
   - No credentials in network requests

3. **Backend Security**
   - Single entry point: `services/llm_client.py`
   - All LLM calls MUST go through this module
   - Enforces rate limits per IP address
   - Validates input/output sizes

---

## Directory Structure

```
backend/
├── .env                          # API key (NOT in git)
├── gem_app.py                    # Main Flask app
├── templates.json                # Prompt templates for chatbot
├── services/
│   ├── __init__.py
│   └── llm_client.py            # ⭐ UNIFIED LLM GATEWAY
└── extension/
    ├── __init__.py
    ├── routes.py                # Extension API endpoints
    ├── ai_client.py             # Wrapper (calls llm_client)
    ├── prompts.py               # Extension prompt templates
    └── reasoning.py             # Toulmin & fallacy utilities

extension/                        # Browser extension (Manifest V3)
├── manifest.json
├── background.js                # Calls Flask API only
├── content.js
└── popup.js

public/                          # Web frontend
├── index.html
├── chat.html
├── app.js                       # Calls Flask API only
└── data/
    ├── db.json                  # Chat history
    ├── logicalfallacy.json      # 13 fallacy definitions
    └── Toulmin.json             # 6 Toulmin factors
```

---

## API Endpoints

### Chatbot Endpoints (`gem_app.py`)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/extract_toulmin` | POST | Extract Toulmin elements from argument |
| `/api/support_mode` | POST | Generate supportive analysis with fallacy fix |
| `/api/oppose_mode` | POST | Generate counter-argument |
| `/api/evaluate_user_response` | POST | Evaluate user's rebuttal |
| `/api/get_chat_history` | GET | Retrieve saved chats |
| `/api/save_chat` | POST | Save chat session |

### Extension Endpoints (`extension/routes.py`)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/analyze` | POST | Full Toulmin analysis of text |
| `/api/detect-fallacies` | POST | Detect logical fallacies only |
| `/api/generate-reply` | POST | Generate counter or support reply |
| `/api/rewrite` | POST | Rewrite text to fix fallacies |
| `/api/models` | GET | Get available fallacy/Toulmin models |
| `/api/health` | GET | Health check & provider status |
| `/api/test` | GET | Test LLM connection |

---

## Unified LLM Client (`services/llm_client.py`)

### Purpose

Single gateway for ALL OpenRouter API calls. Ensures:
- One API key for entire system
- Consistent rate limiting
- Free-tier protection
- Centralized error handling

### Features

```python
class LLMClient:
    # Free-tier limits
    MAX_INPUT_LENGTH = 2000      # characters
    MAX_OUTPUT_TOKENS = 1500     # tokens
    REQUEST_TIMEOUT = 30         # seconds
    
    def chat_completion(messages, client_ip, temperature=0.7, json_mode=True):
        """
        Main entry point for all LLM calls.
        
        Enforces:
        - Rate limiting: 10 req/min per IP
        - Input validation
        - Output limits
        - Timeout protection
        """
```

### Rate Limiting

```python
class RateLimiter:
    def __init__(max_requests=10, window_seconds=60):
        """
        Simple in-memory rate limiter.
        Tracks requests per IP address.
        No database required.
        """
```

### Usage in Chatbot

```python
from services.llm_client import llm_client

def some_endpoint():
    client_ip = request.remote_addr or "127.0.0.1"
    
    messages = [
        {"role": "system", "content": "You are..."},
        {"role": "user", "content": "Analyze this..."}
    ]
    
    response = llm_client.chat_completion(
        messages=messages,
        client_ip=client_ip,
        temperature=0.7,
        json_mode=True
    )
```

### Usage in Extension

```python
# extension/ai_client.py wraps the unified client
from services.llm_client import llm_client

def call_ai(system_prompt, user_prompt, options):
    """Routes to unified LLM client"""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    return llm_client.chat_completion(
        messages=messages,
        client_ip=get_client_ip(),
        temperature=options.get("temperature", 0.7),
        json_mode=options.get("jsonMode", False)
    )
```

---

## Free-Tier Protection

### Input Limits

- **Max input:** 2000 characters
- **Validation:** Automatic truncation with error message
- **Purpose:** Prevent excessive token usage

### Output Limits

- **Max tokens:** 1500
- **Enforcement:** Set in API payload
- **Purpose:** Keep responses concise

### Rate Limiting

- **Limit:** 10 requests per minute per IP
- **Window:** Rolling 60-second window
- **Storage:** In-memory (no database)
- **Scope:** Per client IP address

### Timeout Protection

- **Timeout:** 30 seconds per request
- **Behavior:** Graceful failure with error message
- **Purpose:** Prevent hanging requests

---

## Configuration

### Environment Variables

Create `backend/.env`:

```bash
# Required
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxx

# Optional (defaults shown)
RATE_LIMIT_WINDOW_MS=60000        # 60 seconds
RATE_LIMIT_MAX_REQUESTS=15        # 15 requests
```

### Get Free API Key

1. Visit [OpenRouter](https://openrouter.ai/)
2. Sign up for free account
3. Generate API key
4. Copy to `backend/.env`

---

## Running the System

### 1. Install Dependencies

```bash
source .venv/bin/activate
pip install flask flask-cors python-dotenv requests
```

### 2. Configure API Key

```bash
echo "OPENROUTER_API_KEY=your-key-here" > backend/.env
```

### 3. Start Flask Server

```bash
python backend/gem_app.py
```

Server runs on: `http://localhost:5001`

### 4. Load Browser Extension

1. Open Chrome: `chrome://extensions/`
2. Enable **Developer mode**
3. Click **Load unpacked**
4. Select the `extension/` folder

### 5. Open Web Chatbot

Open `public/chat.html` in browser or navigate to `http://localhost:5001`

---

## Security Checklist

Before deploying:

- ✅ API key in `backend/.env` (not in git)
- ✅ `.gitignore` includes `.env`
- ✅ No API keys in JavaScript files
- ✅ All frontend calls go to Flask backend
- ✅ Rate limiting enabled
- ✅ Input/output limits enforced
- ✅ Error messages don't expose key
- ✅ CORS properly configured

---

## Testing

### Test Unified Client

```bash
cd backend
python -c "
from services.llm_client import llm_client
print(llm_client.get_status())
"
```

### Test Chatbot Endpoint

```bash
curl -X POST http://localhost:5001/api/extract_toulmin \
  -H "Content-Type: application/json" \
  -d '{"argument_text": "The death penalty deters crime because statistics show lower murder rates in states with capital punishment."}'
```

### Test Extension Endpoint

```bash
curl -X POST http://localhost:5001/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "All politicians are corrupt. I saw one take a bribe, so they all must be the same."}'
```

### Test Health Check

```bash
curl http://localhost:5001/api/health
```

---

## Troubleshooting

### "Rate limit exceeded"

**Cause:** Too many requests from same IP  
**Solution:** Wait 60 seconds or increase `RATE_LIMIT_MAX_REQUESTS`

### "OpenRouter API key not configured"

**Cause:** Missing `.env` file or wrong key name  
**Solution:** 
```bash
echo "OPENROUTER_API_KEY=sk-or-v1-..." > backend/.env
```

### "Input too long"

**Cause:** Text exceeds 2000 characters  
**Solution:** Use shorter input or increase `MAX_INPUT_LENGTH` in `llm_client.py`

### Extension shows "Connection failed"

**Cause:** Flask server not running  
**Solution:** Start server: `python backend/gem_app.py`

---

## Cost Optimization

### Current Settings

- Model: `meta-llama/llama-3.3-70b-instruct:free`
- Rate: 10 requests/min per IP
- Input: 2000 chars max
- Output: 1500 tokens max

### Expected Usage (Hackathon)

- **Users:** ~10 concurrent
- **Requests/user:** ~20/hour
- **Total:** ~200 requests/hour
- **Cost:** $0 (free tier)

### Monitoring

Check OpenRouter dashboard:
- [OpenRouter Activity](https://openrouter.ai/activity)
- Track usage per model
- Set up alerts if approaching limits

---

## Migration Notes

### From Node.js to Flask

**Removed:**
- ❌ `server.js` (Node.js Express)
- ❌ Separate API keys in extension
- ❌ Duplicate rate limiting logic
- ❌ Multiple OpenRouter clients

**Added:**
- ✅ `services/llm_client.py` (unified gateway)
- ✅ Single API key in Flask
- ✅ Shared rate limiter
- ✅ Consistent error handling

**Updated:**
- ✅ `extension/background.js` → calls Flask API
- ✅ `extension/ai_client.py` → wraps unified client
- ✅ `gem_app.py` → uses unified client

---

## Development Guidelines

### Adding New Endpoints

1. **Always use unified client:**
   ```python
   from services.llm_client import llm_client
   
   @app.route("/api/new-feature", methods=["POST"])
   def new_feature():
       client_ip = request.remote_addr or "127.0.0.1"
       response = llm_client.chat_completion(...)
   ```

2. **Never bypass the gateway:**
   ```python
   # ❌ WRONG - Direct OpenRouter call
   requests.post("https://openrouter.ai/...", headers={"Authorization": ...})
   
   # ✅ CORRECT - Through unified client
   llm_client.chat_completion(messages, client_ip)
   ```

### Modifying Rate Limits

Edit `services/llm_client.py`:

```python
class LLMClient:
    def __init__(self):
        # Adjust these values
        self.rate_limiter = RateLimiter(
            max_requests=10,    # Change this
            window_seconds=60   # Or this
        )
```

### Adding New AI Providers

Current: OpenRouter only  
Future: Add to `llm_client.py` as fallback provider

---

## License

MIT License - See LICENSE file

---

## Support

For issues or questions:
1. Check this documentation
2. Review error logs in terminal
3. Test with `/api/health` endpoint
4. Verify `.env` configuration
