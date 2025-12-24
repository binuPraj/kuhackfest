# Quick Start Guide

## ✅ System Ready to Use!

Your unified Flask backend is configured and operational.

---

## Starting the Server

```bash
cd "/run/media/prajwal/Prajwal_s Volume/itsnhackathon"
source .venv/bin/activate
python backend/gem_app.py
```

**Expected output:**
```
✅ Loaded 13 fallacy definitions
✅ Loaded 6 Toulmin factors
 * Running on http://127.0.0.1:5001
```

---

## Testing the System

### 1. Health Check

```bash
curl http://localhost:5001/api/health
```

**Expected:**
```json
{
  "status": "ok",
  "provider": {
    "configured": true,
    "model": "meta-llama/llama-3.3-70b-instruct:free",
    "rate_limit": "10 req / 60s"
  }
}
```

### 2. Test Extension Analyze Endpoint

```bash
curl -X POST http://localhost:5001/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "Everyone who disagrees with me is stupid."}'
```

### 3. Test Chatbot Toulmin Endpoint

```bash
curl -X POST http://localhost:5001/api/extract_toulmin \
  -H "Content-Type: application/json" \
  -d '{"argument_text": "We should ban all cars because they pollute."}'
```

---

## Loading the Browser Extension

1. Open Chrome: `chrome://extensions/`
2. Toggle **Developer mode** ON
3. Click **Load unpacked**
4. Navigate to: `/run/media/prajwal/Prajwal_s Volume/itsnhackathon/extension`
5. Click **Select Folder**

**Extension should load successfully!**

---

## Using the Web Chatbot

1. Open in browser: `file:///run/media/prajwal/Prajwal_s%20Volume/itsnhackathon/public/chat.html`
2. Or double-click `public/chat.html`
3. Enter an argument
4. Click analyze

---

## Key Features

### ✅ Security
- API key protected (only in `backend/.env`)
- No key exposure to frontend
- All calls go through Flask backend

### ✅ Rate Limiting
- 10 requests per minute per IP
- Prevents API abuse
- Automatic reset every 60 seconds

### ✅ Free-Tier Protection
- Input limit: 10,000 characters
- Output limit: 1,500 tokens
- 30-second timeout
- Free model: meta-llama/llama-3.3-70b-instruct

---

## API Endpoints Reference

### Chatbot Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/extract_toulmin` | POST | Extract Toulmin model elements |
| `/api/support_mode` | POST | Generate supportive analysis |
| `/api/oppose_mode` | POST | Generate counter-argument |
| `/api/evaluate_user_response` | POST | Evaluate user's response |
| `/api/get_chat_history` | GET | Get saved chat sessions |
| `/api/save_chat` | POST | Save chat session |

### Extension Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/analyze` | POST | Full argument analysis |
| `/api/detect-fallacies` | POST | Detect logical fallacies |
| `/api/generate-reply` | POST | Generate reply (counter/support) |
| `/api/rewrite` | POST | Rewrite text to fix issues |
| `/api/models` | GET | Get available models/fallacies |
| `/api/health` | GET | Health check |
| `/api/test` | GET | Test LLM connection |

---

## Troubleshooting

### Server won't start

**Check Python environment:**
```bash
source .venv/bin/activate
python --version  # Should be 3.x
```

**Check dependencies:**
```bash
pip list | grep -E "flask|requests|dotenv"
```

### "API key not configured"

**Check `.env` file exists:**
```bash
cat backend/.env
```

**Should contain:**
```
OPENROUTER_API_KEY=sk-or-v1-...
```

### "Rate limit exceeded"

**Wait 60 seconds** and try again, or adjust limit in:
`backend/services/llm_client.py` line 29:
```python
self.rate_limiter = RateLimiter(max_requests=10, window_seconds=60)
```

### Extension not working

**Verify:**
1. Flask server is running
2. Extension is loaded in Chrome
3. Extension permissions granted
4. Check browser console for errors

---

## Monitoring Usage

### OpenRouter Dashboard

Visit: https://openrouter.ai/activity

**Check:**
- Total requests today
- Tokens used
- Cost (should be $0)
- Any errors

### Local Logs

**Server logs** show in terminal where you ran `python backend/gem_app.py`

**Look for:**
- Request timestamps
- Endpoint calls
- Any errors

---

## Files to Know

### Configuration

| File | Purpose |
|------|---------|
| `backend/.env` | API key (keep secret!) |
| `backend/templates.json` | Chatbot prompt templates |

### Backend Code

| File | Purpose |
|------|---------|
| `backend/gem_app.py` | Main Flask app |
| `backend/services/llm_client.py` | Unified LLM gateway ⭐ |
| `backend/extension/routes.py` | Extension API routes |
| `backend/extension/ai_client.py` | Extension AI wrapper |

### Frontend Code

| File | Purpose |
|------|---------|
| `extension/background.js` | Extension service worker |
| `extension/manifest.json` | Extension configuration |
| `public/chat.html` | Web chatbot interface |
| `public/app.js` | Web app JavaScript |

### Documentation

| File | Purpose |
|------|---------|
| `COMPLETE.md` | Full refactoring summary |
| `ARCHITECTURE.md` | System architecture details |
| `SECURITY_SUMMARY.md` | Security & cost optimization |
| `QUICKSTART.md` | This file |

---

## Common Commands

### Start Server
```bash
python backend/gem_app.py
```

### Start Server in Background
```bash
python backend/gem_app.py > server.log 2>&1 &
```

### Stop Server
```bash
pkill -f gem_app.py
```

### Check Server Status
```bash
ps aux | grep gem_app | grep -v grep
```

### Test Endpoints
```bash
# Health check
curl http://localhost:5001/api/health

# Test analyze
curl -X POST http://localhost:5001/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "Test argument"}'
```

---

## What's Next?

### Ready to Use ✅
- ✅ Server configured
- ✅ API key protected
- ✅ Rate limiting active
- ✅ Both services operational

### For Production (Future)
- ⬜ Use gunicorn/uwsgi
- ⬜ Enable HTTPS
- ⬜ Add authentication
- ⬜ Set up monitoring
- ⬜ Configure logging

---

## Support

**Documentation:**
- Full details: `ARCHITECTURE.md`
- Security info: `SECURITY_SUMMARY.md`
- Completion summary: `COMPLETE.md`

**Quick Checks:**
1. Is server running? `ps aux | grep gem_app`
2. Is `.env` configured? `cat backend/.env`
3. Are endpoints working? `curl http://localhost:5001/api/health`

---

## System Status: ✅ READY

Everything is configured and operational. Start the server and begin using!

```bash
# One command to start everything:
python backend/gem_app.py
```

**Server will run on: http://127.0.0.1:5001**

Enjoy your unified reasoning assistant system! 🚀
