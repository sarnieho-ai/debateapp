# ⬡ Nexus AI — 4-Model Discussion Engine

A Streamlit app that makes Claude, Gemini, GPT-4, and Perplexity debate any question across two rounds, then synthesizes the best final answer.

---

## How It Works

| Round | What Happens |
|-------|-------------|
| **Round 1** | All 4 AIs answer your question independently in parallel |
| **Round 2** | Each AI reads the others' answers and debates — agreeing, challenging, extending |
| **Synthesis** | Claude moderates and distills the single best answer from the full discussion |

---

## Setup (Local)

### 1. Clone and install

```bash
git clone <your-repo>
cd nexus-ai
pip install -r requirements.txt
```

### 2. Add your API keys

Create `.streamlit/secrets.toml` (already in `.gitignore` — safe):

```toml
ANTHROPIC_API_KEY  = "sk-ant-..."   # Required
GEMINI_API_KEY     = "AIza..."      # Optional (falls back to Claude simulation)
OPENAI_API_KEY     = "sk-..."       # Optional (falls back to Claude simulation)
PERPLEXITY_API_KEY = "pplx-..."     # Optional (falls back to Claude simulation)
```

### 3. Run

```bash
streamlit run app.py
```

Open `http://localhost:8501`

---

## Deploy to Streamlit Cloud (Free)

1. Push to a **GitHub repo** (`.streamlit/secrets.toml` is gitignored — never pushed)
2. Go to [share.streamlit.io](https://share.streamlit.io) → **New app**
3. Select your repo → `app.py`
4. Go to **Settings → Secrets** and paste:

```toml
ANTHROPIC_API_KEY  = "sk-ant-..."
GEMINI_API_KEY     = "AIza..."
OPENAI_API_KEY     = "sk-..."
PERPLEXITY_API_KEY = "pplx-..."
```

5. Deploy — your keys are stored encrypted by Streamlit, never exposed in code.

---

## Where to Get API Keys

| Model | Provider | URL |
|-------|----------|-----|
| Claude | Anthropic | https://console.anthropic.com |
| Gemini | Google AI Studio | https://aistudio.google.com/apikey |
| GPT-4 | OpenAI | https://platform.openai.com/api-keys |
| Perplexity | Perplexity AI | https://www.perplexity.ai/settings/api |

---

## Fallback Behavior

Only the **Anthropic key is required**. If Gemini, OpenAI, or Perplexity keys are missing or their APIs fail, those personas automatically fall back to Claude running their specific system prompt — so the app always works.

---

## Project Structure

```
nexus-ai/
├── app.py                    # Main Streamlit app
├── requirements.txt          # Python dependencies
├── .gitignore                # Protects secrets.toml
├── README.md
└── .streamlit/
    └── secrets.toml          # ← Your API keys (gitignored)
```
