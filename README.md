# Unified istnhackathon Repository

This repository combines the **chatbot backend** and the **browser extension backend** into a single Flask application.

---

## Project Structure

```
itsnhackathon/
├── backend/                    # Flask backend (all APIs)
│   ├── gem_app.py              # Main Flask entry point (chatbot + extension)
│   ├── templates.json          # Prompt templates for chatbot features
│   ├── requirements.txt        # Python dependencies
│   ├── start_server.sh         # Quick start script
│   └── extension/              # Migrated extension backend code
│       ├── __init__.py         # Blueprint export
│       ├── routes.py           # Flask routes (analyze, detect-fallacies, etc.)
│       ├── ai_client.py        # Google Gemini / OpenRouter AI integration
│       ├── prompts.py          # All prompt templates for reasoning tasks
│       └── reasoning.py        # Toulmin & fallacy model utilities
│
├── extension/                  # Browser extension frontend (Manifest V3)
│   ├── manifest.json
│   ├── background.js
│   ├── content.js
│   ├── popup.html
│   ├── popup.js
│   ├── styles.css
│   └── icons/
│
├── public/                     # Chatbot frontend (HTML/CSS/JS)
│   ├── index.html
│   ├── chat.html
│   ├── fallacies.html
│   ├── styles.css
│   ├── app.js
│   └── data/
│       ├── db.json
│       ├── logicalfallacy.json
│       └── Toulmin.json
│
├── reference/                  # (Optional) Original KU-Hackfest Node.js source
│   └── ku-hackfest/
└── README.md                   # This file
```

---

## Unified API Endpoints

### Chatbot APIs (original Flask routes)

| Endpoint                        | Method | Description                                  |
|---------------------------------|--------|----------------------------------------------|
| `/api/extract_toulmin`          | POST   | Analyze an argument with Toulmin model       |
| `/api/support_mode`             | POST   | Improve an argument (fallacy removal)        |
| `/api/oppose_mode`              | POST   | Generate fallacious counter-argument         |
| `/api/evaluate_user_response`   | POST   | Score user's counter-argument                |
| `/api/get_chat_history`         | GET    | Retrieve saved chat history                  |
| `/api/save_chat`                | POST   | Persist a chat entry                         |

### Extension APIs (migrated from Node.js)

| Endpoint                 | Method | Description                                       |
|--------------------------|--------|---------------------------------------------------|
| `/api/analyze`           | POST   | Full argument analysis (Toulmin + fallacies)      |
| `/api/detect-fallacies`  | POST   | Focused fallacy detection (reading mode)          |
| `/api/generate-reply`    | POST   | Generate counter-argument replies in 3 tones      |
| `/api/rewrite`           | POST   | Rewrite & strengthen an argument                  |
| `/api/models`            | GET    | List loaded Toulmin factors & fallacy definitions |
| `/api/test`              | GET    | Verify AI provider connectivity                   |
| `/api/health`            | GET    | Health check                                      |

---

## Environment Variables

Create a `.env` file inside `backend/`:

```bash
# AI Provider ('openrouter' or 'google')
AI_PROVIDER=openrouter

# OpenRouter (default)
OPENROUTER_API_KEY=your_openrouter_api_key

# Google Gemini (optional fallback or alternative)
GOOGLE_API_KEY=your_google_api_key
GOOGLE_MODEL=gemini-2.0-flash

# Rate limiting (optional)
RATE_LIMIT_WINDOW_MS=60000
RATE_LIMIT_MAX_REQUESTS=15
```

---

## Running the Server

```bash
cd backend
source env/bin/activate    # or create a new venv if needed
pip install -r requirements.txt
python gem_app.py
```

The server starts on **http://localhost:5001**.

---

## Installing the Browser Extension

1. Open **Chrome** (or Chromium-based browser)
2. Navigate to `chrome://extensions/`
3. Enable **Developer mode** (toggle in top-right)
4. Click **Load unpacked**
5. Select the `extension/` folder from this repository

The extension will connect to `http://localhost:5001/api`.

---

## Migration Summary

| Original (Node.js / KU-Hackfest)        | Migrated (Flask / istnhackathon)                      |
|-----------------------------------------|-------------------------------------------------------|
| `server.js`                             | Routes registered via Blueprint in `gem_app.py`       |
| `routes/analyze.js`                     | `backend/extension/routes.py`                         |
| `services/aiService.js`                 | `backend/extension/ai_client.py`                      |
| `services/promptService.js`             | `backend/extension/prompts.py`                        |
| `services/reasoningEngine.js`           | `backend/extension/reasoning.py`                      |
| `middleware/validation.js`              | Inlined in `routes.py` (`_validate_text_field`)       |
| `config/index.js`                       | `os.getenv()` calls in `ai_client.py` & `routes.py`   |
| Extension frontend (`extension/` dir)   | Copied to `extension/`, `API_BASE_URL` updated        |
| `package.json` / npm dependencies       | Removed; Python `requests` used instead               |

### Behavioral Notes

- **AI provider**: Defaults to OpenRouter to match the existing Flask chatbot setup. Google Gemini is used if `AI_PROVIDER=google` and `GOOGLE_API_KEY` is set.
- **Rate limiting**: Implemented in Python (`routes.py`) using an in-memory sliding window (same semantics as the original `express-rate-limit`).
- **CORS**: Handled globally by `flask_cors.CORS(app)`.
- **JSON parsing**: Robust extraction handles both raw JSON and fenced code blocks from LLM responses.

---

## License

MIT – Feel free to use and extend.
