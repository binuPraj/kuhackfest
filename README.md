# 🔍 LogicLens - AI-Powered Reasoning Assistant

**Think clearer, argue better.**

LogicLens is an intelligent reasoning assistant that helps users detect logical fallacies, strengthen arguments, and improve critical thinking skills. It combines a local ELECTRA-based ML model with LLM capabilities to provide comprehensive argument analysis using the Toulmin argumentation framework.

---

## 🌟 Features

### 🎯 Core Capabilities
- **Fallacy Detection**: Local ML model trained on 4000+ samples, detecting 13 types of logical fallacies
- **Toulmin Analysis**: Break down arguments into Claim, Data, Warrant, Backing, Qualifier, and Rebuttal
- **Dual-Mode Analysis**: 
  - **Support Mode**: Get constructive feedback to strengthen your argument
  - **Defence Mode**: Receive counter-arguments to stress-test your reasoning
- **Real-time Scoring**: Clarity, Logical Consistency, and Fallacy Resistance metrics

### 🧩 Components
1. **Web Application** - Full-featured chat interface for argument analysis
2. **Browser Extension** - Analyze arguments anywhere on the web with a floating chatbot
3. **REST API** - Unified backend serving both web and extension

---

## 📁 Project Structure

```
LogicLens/
├── backend/                    # Flask API Server
│   ├── gem_app.py             # Main Flask application
│   ├── services/
│   │   ├── core_service.py    # Core analysis logic
│   │   └── llm_client.py      # LLM integration (OpenRouter)
│   ├── extension/
│   │   └── routes.py          # Extension API routes
│   └── templates.json         # Prompt templates
│
├── extension/                  # Chrome Extension (Manifest V3)
│   ├── manifest.json
│   ├── popup.html/js          # Extension popup UI
│   ├── content.js             # Content script with floating chatbot
│   ├── background.js          # Service worker
│   └── styles.css
│
├── public/                     # Web Frontend
│   ├── index.html             # Landing page
│   ├── chat.html              # Main chat interface
│   ├── fallacies.html         # Fallacy reference guide
│   └── data/
│       └── db.json            # Chat history & insights storage
│
├── saved_models/               # Local ML Models
│   └── electra-logic/         # Fine-tuned ELECTRA for fallacy detection
│
└── requirements.txt            # Python dependencies
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Node.js (optional, for development)
- Chrome/Edge browser (for extension)

### 1. Backend Setup

```bash
# Clone the repository
git clone <repository-url>
cd LogicLens

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
.\venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cd backend
cp .env.example .env
# Edit .env with your API key (OpenRouter)
```

### 2. Configure API Key

Create `backend/.env`:
```env
OPENROUTER_API_KEY=your_openrouter_api_key_here
```

### 3. Start the Backend

```bash
cd backend
python gem_app.py
```

Server runs at: `http://localhost:5001`

### 4. Start the Frontend

```bash
cd public
python -m http.server 3000
```

Web app available at: `http://localhost:3000`

### 5. Install Browser Extension

1. Open Chrome → `chrome://extensions/`
2. Enable "Developer mode"
3. Click "Load unpacked"
4. Select the `extension/` folder

---

## 🔧 API Endpoints

### Chatbot API
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/analyze_dual` | POST | Full dual-mode analysis (support + defence) |
| `/api/support_mode` | POST | Supportive analysis only |
| `/api/oppose_mode` | POST | Counter-argument generation |
| `/api/evaluate_user_response` | POST | Evaluate user's response to counter-argument |

### Extension API
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/analyze` | POST | Quick argument analysis |
| `/api/detect-fallacies` | POST | Fallacy detection only |
| `/api/rewrite` | POST | Improve argument phrasing |

### Utility
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/recalculate_insights` | GET/POST | Recalculate global performance metrics |

---

## 🧠 Toulmin Model

LogicLens uses the Toulmin argumentation model to analyze arguments:

| Element | Description |
|---------|-------------|
| **Claim** | The main assertion or conclusion |
| **Data** | Evidence or facts supporting the claim |
| **Warrant** | The logical connection between data and claim |
| **Backing** | Additional support for the warrant |
| **Qualifier** | Words that limit the claim's strength |
| **Rebuttal** | Conditions where the claim might not hold |

---

## 📊 Detected Fallacies

The local ML model detects 13 types of logical fallacies:

1. **Ad Hominem** - Personal attacks
2. **Ad Populum** - Appeal to popularity
3. **Appeal to Emotion** - Emotional manipulation
4. **Circular Reasoning** - Assuming the conclusion
5. **Equivocation** - Ambiguous terms
6. **Fallacy of Credibility** - False authority
7. **Fallacy of Extension** - Straw man
8. **Fallacy of Logic** - Non-sequitur
9. **Fallacy of Relevance** - Red herring
10. **False Causality** - Correlation ≠ causation
11. **False Dilemma** - Either/or fallacy
12. **Faulty Generalization** - Hasty conclusions
13. **Intentional Fallacy** - Misrepresenting intent

---

## 🎨 Tech Stack

- **Backend**: Flask, Python 3.10+
- **ML Model**: ELECTRA (fine-tuned), PyTorch, Transformers
- **LLM**: OpenRouter API (Gemma 3 27B)
- **Frontend**: Vanilla HTML/CSS/JS, Chart.js
- **Extension**: Chrome Manifest V3
- **Database**: JSON file storage

---

## 📈 Performance Insights

The app tracks your argumentation skills over time:
- **Fallacy Resistance Score** - How well you avoid logical fallacies
- **Logical Consistency Score** - Coherence of your arguments
- **Clarity Score** - How clearly you express ideas
- **Radar Chart** - Toulmin element strengths

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project was created for **KU Hackfest 2025**.

---

## 👥 Team

GENESIS

---

## 🔗 Links

- **Live Demo**: [Try LogicLens](http://localhost:3000)
- **API Documentation**: See API Endpoints section above
- **Fallacy Guide**: [Fallacies Reference](http://localhost:3000/fallacies.html)
