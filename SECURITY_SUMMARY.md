# Security & Cost Optimization Summary

## ✅ Completed Refactoring

### 1. Unified LLM Gateway

**Created:** `backend/services/llm_client.py`

- Single entry point for ALL OpenRouter calls
- Loads API key once from `.env`
- Never exposes key to frontend
- Enforces rate limits (10 req/min per IP)
- Validates input (2000 chars max)
- Limits output (1500 tokens max)
- 30-second timeout protection

### 2. Updated Chatbot (`gem_app.py`)

**Changes:**
- ✅ Removed direct OpenRouter imports
- ✅ Replaced with `from services.llm_client import llm_client`
- ✅ All endpoints now use `llm_client.chat_completion()`
- ✅ Passes `client_ip` for rate limiting
- ✅ Consistent error handling

**Updated Endpoints:**
- `/api/extract_toulmin`
- `/api/support_mode`
- `/api/oppose_mode`
- `/api/evaluate_user_response`
- `/api/save_chat` (title generation)

### 3. Updated Extension (`extension/ai_client.py`)

**Changes:**
- ✅ Removed direct OpenRouter imports
- ✅ Replaced with unified client wrapper
- ✅ `call_ai()` now routes through `llm_client`
- ✅ Deprecated old provider-specific functions
- ✅ Maintained backward compatibility

**Impact:**
- Extension routes still work unchanged
- All calls go through unified gateway
- Same rate limits as chatbot

### 4. Frontend Verification

**Checked Files:**
- ✅ `extension/background.js` - No API keys
- ✅ `extension/content.js` - No API keys
- ✅ `public/app.js` - No API keys
- ✅ All files only call Flask endpoints

---

## Security Guarantees

### API Key Protection

```
✅ STORED: backend/.env (git-ignored)
✅ LOADED: Once at Flask startup
❌ NEVER: In JavaScript files
❌ NEVER: In network requests
❌ NEVER: In browser console
❌ NEVER: In extension manifest
```

### Request Flow

```
Frontend/Extension
      ↓
   Flask API
      ↓
  llm_client.py (validates, rate limits)
      ↓
 OpenRouter API
```

**At no point is the API key exposed outside the backend server.**

---

## Free-Tier Protection

### Rate Limiting

```python
# services/llm_client.py
RateLimiter(
    max_requests=10,      # 10 requests
    window_seconds=60     # per 60 seconds
)
```

**Per IP address, rolling window**

### Input Protection

```python
MAX_INPUT_LENGTH = 2000  # characters
```

**Validation:**
- Empty input rejected
- Oversized input rejected with clear error

### Output Protection

```python
MAX_OUTPUT_TOKENS = 1500  # tokens
```

**Enforcement:**
- Set in API payload
- Prevents runaway responses

### Timeout Protection

```python
REQUEST_TIMEOUT = 30  # seconds
```

**Behavior:**
- Request fails after 30s
- User gets clear error message
- No hanging connections

---

## Usage Tracking

### OpenRouter Dashboard

Monitor usage at: https://openrouter.ai/activity

**Metrics Available:**
- Total requests per day
- Tokens used per model
- Cost (should be $0 on free tier)
- Error rates

### Local Monitoring

**Check Health:**
```bash
curl http://localhost:5001/api/health
```

**Response:**
```json
{
  "status": "ok",
  "provider": {
    "configured": true,
    "model": "meta-llama/llama-3.3-70b-instruct:free",
    "max_input_length": 2000,
    "max_output_tokens": 1500,
    "rate_limit": "10 req / 60s"
  }
}
```

---

## Testing the Changes

### 1. Verify Configuration

```bash
cd backend
python -c "
from services.llm_client import llm_client
status = llm_client.get_status()
print('Configured:', status['configured'])
print('Model:', status['model'])
print('Rate Limit:', status['rate_limit'])
"
```

**Expected Output:**
```
Configured: True
Model: meta-llama/llama-3.3-70b-instruct:free
Rate Limit: 10 req / 60s
```

### 2. Test Chatbot Endpoint

```bash
curl -X POST http://localhost:5001/api/extract_toulmin \
  -H "Content-Type: application/json" \
  -d '{
    "argument_text": "Climate change is not real because it snowed yesterday."
  }'
```

**Should return:** Toulmin analysis JSON

### 3. Test Extension Endpoint

```bash
curl -X POST http://localhost:5001/api/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "text": "All politicians lie. Therefore, we should not trust any government."
  }'
```

**Should return:** Full analysis with fallacies and suggestions

### 4. Test Rate Limiting

```bash
# Run 15 times quickly
for i in {1..15}; do
  curl -s http://localhost:5001/api/health
  echo ""
done
```

**Expected:** First 10 succeed, then rate limit errors

---

## What Changed vs Original

### Before (Node.js)

```
extension/
  background.js → OpenRouter (with API key!)
  ai_client.js  → Direct API calls

backend/
  server.js  → Express + OpenRouter
  gem_app.py → Flask + OpenRouter (separate key!)
```

**Problems:**
- ❌ Multiple API keys
- ❌ Extension had direct API access
- ❌ No unified rate limiting
- ❌ Key exposure risk

### After (Unified Flask)

```
extension/
  background.js → Flask API only
  
backend/
  gem_app.py              → Flask
  services/llm_client.py  → Single OpenRouter gateway
  extension/routes.py     → Uses llm_client
  extension/ai_client.py  → Wraps llm_client
```

**Benefits:**
- ✅ One API key
- ✅ No frontend exposure
- ✅ Unified rate limiting
- ✅ Centralized protection
- ✅ Easier monitoring

---

## Files Modified

### Created
- ✅ `backend/services/__init__.py`
- ✅ `backend/services/llm_client.py` (unified gateway)
- ✅ `ARCHITECTURE.md` (this file)

### Modified
- ✅ `backend/gem_app.py` (use unified client)
- ✅ `backend/extension/ai_client.py` (wrapper for unified client)

### Verified (No Changes Needed)
- ✅ `extension/background.js` (already calls Flask)
- ✅ `extension/manifest.json` (no API keys)
- ✅ `public/app.js` (already calls Flask)
- ✅ `public/chat.html` (no API keys)

---

## Deployment Checklist

Before going live:

- [ ] `.env` file exists with valid API key
- [ ] `.gitignore` includes `.env`
- [ ] No API keys in any `.js` files
- [ ] Flask server running on port 5001
- [ ] CORS configured for your domain
- [ ] Rate limits appropriate for traffic
- [ ] Error logging enabled
- [ ] Health endpoint accessible
- [ ] Extension loaded and tested
- [ ] Chatbot tested and working

---

## Common Errors & Solutions

### "OpenRouter API key not configured"

**Fix:**
```bash
echo "OPENROUTER_API_KEY=sk-or-v1-your-key" > backend/.env
```

### "Rate limit exceeded"

**Fix:** Wait 60 seconds or increase limit in `llm_client.py`

### "Input too long"

**Fix:** Reduce input size or increase `MAX_INPUT_LENGTH`

### Extension shows "Not Found"

**Fix:** Ensure Flask server is running: `python backend/gem_app.py`

### "Module not found: services"

**Fix:** Run from project root or adjust Python path

---

## Performance Expectations

### Latency

- **Local Flask:** < 10ms
- **OpenRouter API:** 2-5 seconds
- **Total response:** 2-6 seconds

### Throughput

- **Rate limit:** 10 req/min per IP
- **Concurrent users:** ~10-20 (hackathon)
- **Expected load:** ~200 req/hour

### Cost

- **Model:** Free tier (meta-llama/llama-3.3-70b)
- **Expected cost:** $0
- **Monitor:** OpenRouter dashboard

---

## Support & Troubleshooting

### Quick Diagnostics

```bash
# Check server is running
curl http://localhost:5001/

# Check API health
curl http://localhost:5001/api/health

# Check extension endpoint
curl http://localhost:5001/api/test

# View server logs
# (Check terminal where gem_app.py is running)
```

### Logs to Check

1. **Flask server terminal** - Request logs, errors
2. **Browser console** - Extension errors
3. **Network tab** - API call details
4. **OpenRouter dashboard** - Usage & errors

---

## Next Steps

### For Development

1. Test all endpoints with Postman/curl
2. Load extension in Chrome
3. Test chatbot in browser
4. Monitor rate limiting behavior
5. Check error handling

### For Production

1. Use production WSGI server (gunicorn)
2. Enable HTTPS
3. Configure production CORS
4. Set up monitoring/logging
5. Consider Redis for rate limiting
6. Add authentication if needed

---

## Key Takeaways

### ✅ What We Achieved

1. **Single API Key** - One key for entire system
2. **Unified Gateway** - All LLM calls through one service
3. **Zero Frontend Exposure** - No keys in JavaScript
4. **Rate Limiting** - 10 req/min per IP
5. **Free-Tier Safe** - Input/output limits enforced
6. **Easy Monitoring** - One place to check usage

### ✅ Security Improvements

- API key never leaves backend
- Rate limiting prevents abuse
- Input validation prevents exploits
- Timeout protection prevents hanging
- Error messages don't expose secrets

### ✅ Cost Optimization

- Free-tier model used consistently
- Output token limits enforced
- Input size limits enforced
- Rate limiting prevents runaway costs
- Easy to monitor and adjust

---

## Questions?

1. Check `ARCHITECTURE.md` for full documentation
2. Review code comments in `services/llm_client.py`
3. Test with `/api/health` endpoint
4. Check OpenRouter dashboard for usage
5. Review Flask terminal logs for errors
