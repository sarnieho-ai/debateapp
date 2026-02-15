import streamlit as st
import anthropic
import requests
import concurrent.futures
from typing import Optional

# ─── Page Config ────────────────────────────────────────────────
st.set_page_config(
    page_title="Nexus AI — Multi-Model Discussion Engine",
    page_icon="⬡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── Custom CSS ─────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&display=swap');

html, body, [class*="css"] {
    font-family: 'JetBrains Mono', 'Courier New', monospace;
    background-color: #070B12;
    color: #D0DCE8;
}

.stApp { background-color: #070B12; }

/* Hide default streamlit elements */
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 2rem; padding-bottom: 4rem; max-width: 1400px; }

/* Header */
.nexus-header {
    background: rgba(10,14,24,0.97);
    border-bottom: 1px solid #111E2E;
    padding: 20px 32px;
    margin: -2rem -4rem 2rem -4rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.nexus-logo { font-size: 22px; font-weight: bold; letter-spacing: 0.15em; color: #E0E8F5; }
.nexus-sub  { font-size: 10px; color: #3A5A7A; letter-spacing: 0.1em; margin-top: 4px; }

/* Input area */
.input-box {
    background: #0D1420;
    border: 1px solid #1A2A3A;
    border-radius: 10px;
    padding: 20px;
    margin-bottom: 24px;
}

/* Phase headers */
.phase-header {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 16px;
    margin-top: 8px;
}
.phase-num {
    width: 28px; height: 28px; border-radius: 50%;
    display: inline-flex; align-items: center; justify-content: center;
    font-size: 12px; font-weight: bold;
    flex-shrink: 0;
}
.phase-num-active  { background: rgba(123,167,255,0.15); border: 1.5px solid #7BA7FF; color: #7BA7FF; }
.phase-num-done    { background: rgba(61,255,192,0.15);  border: 1.5px solid #3DFFC0; color: #3DFFC0; }
.phase-num-waiting { background: #0D1420;                border: 1.5px solid #1E2A3A; color: #2A3A4A; }
.phase-title { font-size: 11px; font-weight: bold; letter-spacing: 0.1em; }

/* AI Cards */
.ai-card {
    border-radius: 10px;
    padding: 16px;
    height: 100%;
    min-height: 180px;
    font-size: 12.5px;
    line-height: 1.75;
    white-space: pre-wrap;
    word-break: break-word;
}
.ai-card-header {
    display: flex; align-items: center; gap: 8px;
    margin-bottom: 12px; font-size: 12px;
    font-weight: bold; letter-spacing: 0.08em;
}
.ai-card-maker { font-size: 10px; font-weight: normal; color: #3A4A5A; margin-left: 4px; }
.ai-card-label {
    margin-left: auto; font-size: 9px; color: #3A4A5A;
    background: #111820; padding: 2px 6px; border-radius: 3px;
    letter-spacing: 0.06em;
}
.pulse {
    display: inline-block; width: 8px; height: 8px; border-radius: 50%;
    flex-shrink: 0;
}

/* Claude */
.card-claude  { background: rgba(255,139,78,0.08);  border: 1px solid rgba(255,139,78,0.3);  }
.head-claude  { color: #FF8B4E; }
.pulse-claude { background: #FF8B4E; box-shadow: 0 0 8px #FF8B4E; }

/* Gemini */
.card-gemini  { background: rgba(123,167,255,0.08); border: 1px solid rgba(123,167,255,0.3); }
.head-gemini  { color: #7BA7FF; }
.pulse-gemini { background: #7BA7FF; box-shadow: 0 0 8px #7BA7FF; }

/* GPT-4 */
.card-gpt4    { background: rgba(168,230,163,0.08); border: 1px solid rgba(168,230,163,0.3); }
.head-gpt4    { color: #A8E6A3; }
.pulse-gpt4   { background: #A8E6A3; box-shadow: 0 0 8px #A8E6A3; }

/* Perplexity */
.card-pplx    { background: rgba(61,255,192,0.08);  border: 1px solid rgba(61,255,192,0.3);  }
.head-pplx    { color: #3DFFC0; }
.pulse-pplx   { background: #3DFFC0; box-shadow: 0 0 8px #3DFFC0; }

/* Synthesis box */
.synth-box {
    background: rgba(61,255,192,0.05);
    border: 1px solid rgba(61,255,192,0.25);
    border-radius: 10px; padding: 24px; margin-top: 8px;
}
.synth-title { font-size: 12px; font-weight: bold; color: #3DFFC0; letter-spacing: 0.08em; }
.synth-sub   { font-size: 10px; color: #2A5A4A; margin-top: 2px; }
.synth-text  { color: #C0D8D0; font-size: 13.5px; line-height: 1.8; white-space: pre-wrap; margin-top: 12px; }

/* Stanza divider */
.divider { border: none; border-top: 1px solid #111E2E; margin: 28px 0; }

/* Textarea override */
.stTextArea textarea {
    background: #0D1420 !important;
    border: 1px solid #1A2A3A !important;
    color: #D0DCE8 !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 14px !important;
    border-radius: 8px !important;
}
.stTextArea textarea:focus {
    border-color: #3A5A8A !important;
    box-shadow: 0 0 0 1px #3A5A8A !important;
}

/* Button */
.stButton > button {
    background: rgba(123,167,255,0.15) !important;
    color: #7BA7FF !important;
    border: 1px solid rgba(123,167,255,0.4) !important;
    border-radius: 6px !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 11px !important;
    font-weight: bold !important;
    letter-spacing: 0.1em !important;
    padding: 8px 24px !important;
    transition: all 0.2s !important;
}
.stButton > button:hover {
    background: rgba(123,167,255,0.25) !important;
    border-color: #7BA7FF !important;
}
.stButton > button:disabled {
    background: #0D1420 !important;
    color: #2A3A4A !important;
    border-color: #1A2A3A !important;
}

/* Info / warning boxes */
.info-box {
    font-size: 11px; color: #3A5060; padding: 10px 14px;
    background: #090E18; border-radius: 6px;
    border-left: 3px solid #1A3A5A; margin-bottom: 20px;
    letter-spacing: 0.02em;
}
.legend-box {
    padding: 20px; background: #090E18;
    border-radius: 10px; border: 1px solid #111E2E;
    margin-top: 32px;
}
.legend-title { font-size: 9px; letter-spacing: 0.12em; color: #3A5060; margin-bottom: 14px; }
.legend-item  { display: inline-flex; align-items: center; gap: 8px; margin-right: 24px; }
</style>
""", unsafe_allow_html=True)

# ─── AI Config ──────────────────────────────────────────────────
AI_CONFIG = {
    "claude":     {"name": "Claude",     "maker": "Anthropic",   "css": "claude", "label": "CLAUDE"},
    "gemini":     {"name": "Gemini",     "maker": "Google",      "css": "gemini", "label": "GEMINI"},
    "gpt4":       {"name": "GPT-4",      "maker": "OpenAI",      "css": "gpt4",   "label": "GPT-4"},
    "perplexity": {"name": "Perplexity", "maker": "Perplexity",  "css": "pplx",   "label": "PERPLEXITY"},
}

PERSONAS = {
    "claude": {
        "initial": "You are Claude by Anthropic. Respond with careful reasoning, nuance, and intellectual honesty. Acknowledge uncertainty. Be thorough yet clear. Show analytical depth. 3-5 paragraphs.",
        "debate":  "You are Claude by Anthropic. You gave an initial answer. Now engage in genuine multi-AI discussion. Agree where others are right, challenge where they are wrong or incomplete, and add important angles they missed. Be specific and direct. 2-4 paragraphs.",
    },
    "gemini": {
        "initial": "You are Gemini by Google. Leverage broad world knowledge. Provide comprehensive coverage, draw connections across domains, highlight practical applications. Be informative and structured. 3-5 paragraphs.",
        "debate":  "You are Gemini by Google. You gave an initial answer. Engage with the other AIs: build on strong points, challenge weak ones, bring in cross-domain knowledge they may have missed. 2-4 paragraphs.",
    },
    "gpt4": {
        "initial": "You are GPT-4 by OpenAI. Excel at deep logical reasoning, structured step-by-step analysis, and synthesis of complex ideas. Be precise, systematic, and authoritative. Show your reasoning chain clearly. 3-5 paragraphs.",
        "debate":  "You are GPT-4 by OpenAI. You gave an initial answer. Now reason rigorously through the other AIs responses. Identify logical gaps, validate sound arguments, and bring structured clarity to the discussion. 2-4 paragraphs.",
    },
    "perplexity": {
        "initial": "You are Perplexity, an AI research engine. Be direct, fact-focused, and research-oriented. Lead with specific data, verifiable facts, and concrete examples. Be precise and concise. 3-5 paragraphs.",
        "debate":  "You are Perplexity AI. You gave an initial answer. Now engage: push back on vagueness, validate accurate points, add concrete facts or research that others missed. Ground the discussion in verifiable reality. 2-4 paragraphs.",
    },
}

SYNTH_SYSTEM = (
    "You are a neutral expert moderator synthesizing a multi-AI discussion between Claude, Gemini, GPT-4, and Perplexity. "
    "Produce the single best, most comprehensive answer by incorporating the strongest insights from all AIs, "
    "resolving disagreements with sound reasoning, and eliminating redundancy. Be definitive, well-structured, and clear."
)

# ─── Load Keys from Streamlit Secrets ───────────────────────────
def get_secret(key: str) -> Optional[str]:
    try:
        return st.secrets[key]
    except (KeyError, FileNotFoundError):
        return None

ANTHROPIC_KEY  = get_secret("ANTHROPIC_API_KEY")
GEMINI_KEY     = get_secret("GEMINI_API_KEY")
OPENAI_KEY     = get_secret("OPENAI_API_KEY")
PERPLEXITY_KEY = get_secret("PERPLEXITY_API_KEY")

# ─── API Callers ─────────────────────────────────────────────────
def call_claude(system: str, message: str) -> str:
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    response = client.messages.create(
        model="claude-opus-4-5-20251101",
        max_tokens=1000,
        system=system,
        messages=[{"role": "user", "content": message}],
    )
    return response.content[0].text

def call_gemini(system: str, message: str) -> str:
    if not GEMINI_KEY:
        raise ValueError("GEMINI_API_KEY not set")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
    payload = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"parts": [{"text": message}]}],
    }
    r = requests.post(url, json=payload, timeout=60)
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]

def call_gpt4(system: str, message: str) -> str:
    if not OPENAI_KEY:
        raise ValueError("OPENAI_API_KEY not set")
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {OPENAI_KEY}"}
    payload = {
        "model": "gpt-4o",
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": message}],
        "max_tokens": 1000,
    }
    r = requests.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers, timeout=60)
    r.raise_for_status()
    return r.choices[0].message.content if hasattr(r, "choices") else r.json()["choices"][0]["message"]["content"]

def call_perplexity(system: str, message: str) -> str:
    if not PERPLEXITY_KEY:
        raise ValueError("PERPLEXITY_API_KEY not set")
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {PERPLEXITY_KEY}"}
    payload = {
        "model": "llama-3.1-sonar-small-128k-online",
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": message}],
    }
    r = requests.post("https://api.perplexity.ai/chat/completions", json=payload, headers=headers, timeout=60)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

def call_persona(persona: str, prompt_type: str, message: str) -> str:
    system = PERSONAS[persona][prompt_type]
    try:
        if persona == "gemini":
            return call_gemini(system, message)
        elif persona == "gpt4":
            return call_gpt4(system, message)
        elif persona == "perplexity":
            return call_perplexity(system, message)
        else:
            return call_claude(system, message)
    except Exception as e:
        # Fallback to Claude simulation with the same persona system prompt
        try:
            return call_claude(system, message)
        except Exception as e2:
            return f"⚠ Error calling {persona}: {str(e)} | Fallback also failed: {str(e2)}"

# ─── Parallel Execution ──────────────────────────────────────────
def run_parallel(tasks: list) -> list:
    """Run list of (persona, prompt_type, message) tuples in parallel threads."""
    results = [None] * len(tasks)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        future_to_idx = {
            executor.submit(call_persona, p, pt, msg): i
            for i, (p, pt, msg) in enumerate(tasks)
        }
        for future in concurrent.futures.as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                results[idx] = future.result()
            except Exception as e:
                results[idx] = f"⚠ Error: {str(e)}"
    return results

# ─── UI Helpers ──────────────────────────────────────────────────
def render_ai_card(persona: str, text: str, label: str = ""):
    cfg = AI_CONFIG[persona]
    css = cfg["css"]
    pulse_html = f'<span class="pulse pulse-{css}"></span>'
    label_html = f'<span class="ai-card-label">{label}</span>' if label else ""
    header_html = f"""
    <div class="ai-card-header head-{css}">
        {pulse_html}
        {cfg["label"]}
        <span class="ai-card-maker">{cfg["maker"]}</span>
        {label_html}
    </div>"""
    content_html = text.replace("<", "&lt;").replace(">", "&gt;")
    card_html = f"""
    <div class="ai-card card-{css}">
        {header_html}
        <div style="color:#B0C4D8">{content_html}</div>
    </div>"""
    st.markdown(card_html, unsafe_allow_html=True)

def render_phase_header(num: int, title: str, state: str):
    """state: 'waiting' | 'active' | 'done'"""
    css_class = f"phase-num-{state}"
    icon = "✓" if state == "done" else str(num)
    color = {"waiting": "#2A3A4A", "active": "#E0E8F5", "done": "#3DFFC0"}[state]
    st.markdown(f"""
    <div class="phase-header">
        <span class="phase-num {css_class}">{icon}</span>
        <span class="phase-title" style="color:{color}">{title}</span>
    </div>
    """, unsafe_allow_html=True)

# ─── Key Status Banner ───────────────────────────────────────────
def render_key_status():
    statuses = {
        "Claude (Anthropic)": ANTHROPIC_KEY,
        "Gemini (Google)":    GEMINI_KEY,
        "GPT-4 (OpenAI)":     OPENAI_KEY,
        "Perplexity":         PERPLEXITY_KEY,
    }
    parts = []
    for name, key in statuses.items():
        if key:
            parts.append(f'<span style="color:#3DFFC0">✓ {name}</span>')
        else:
            mode = "SIMULATED" if name != "Claude (Anthropic)" else "⚠ REQUIRED"
            color = "#3A5060" if name != "Claude (Anthropic)" else "#FF6B6B"
            parts.append(f'<span style="color:{color}">✗ {name} ({mode})</span>')
    st.markdown(
        f'<div class="info-box">API KEY STATUS &nbsp;·&nbsp; {" &nbsp;·&nbsp; ".join(parts)}</div>',
        unsafe_allow_html=True,
    )

# ─── Main App ────────────────────────────────────────────────────
def main():
    # Header
    st.markdown("""
    <div class="nexus-header">
        <div>
            <div class="nexus-logo">⬡ NEXUS AI</div>
            <div class="nexus-sub">4-MODEL DISCUSSION ENGINE &nbsp;·&nbsp; CLAUDE &nbsp;·&nbsp; GEMINI &nbsp;·&nbsp; GPT-4 &nbsp;·&nbsp; PERPLEXITY</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    render_key_status()

    if not ANTHROPIC_KEY:
        st.error("⚠ ANTHROPIC_API_KEY is required. Add it to `.streamlit/secrets.toml`.")
        st.stop()

    # Question input
    question = st.text_area(
        label="",
        placeholder="Enter your question or topic...\ne.g. What is the best programming language to learn in 2025?\ne.g. Should AI systems be open source?",
        height=100,
        label_visibility="collapsed",
    )

    col_btn, col_info = st.columns([1, 5])
    with col_btn:
        run = st.button("▶  START DISCUSSION", use_container_width=True)
    with col_info:
        st.markdown('<div style="color:#2A3A4A;font-size:11px;padding-top:10px;">All 4 models run in parallel per round · Missing API keys fall back to Claude simulation</div>', unsafe_allow_html=True)

    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    if not run or not question.strip():
        # Legend when idle
        st.markdown("""
        <div class="legend-box">
            <div class="legend-title">PARTICIPATING MODELS</div>
            <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:14px">
                <span style="color:#FF8B4E;font-size:12px;font-weight:bold">● Claude</span> <span style="color:#2A3A4A;font-size:10px">Anthropic — careful nuance, intellectual honesty</span> &nbsp;
                <span style="color:#7BA7FF;font-size:12px;font-weight:bold">● Gemini</span> <span style="color:#2A3A4A;font-size:10px">Google — broad cross-domain knowledge</span> &nbsp;
                <span style="color:#A8E6A3;font-size:12px;font-weight:bold">● GPT-4</span> <span style="color:#2A3A4A;font-size:10px">OpenAI — deep logical reasoning & structure</span> &nbsp;
                <span style="color:#3DFFC0;font-size:12px;font-weight:bold">● Perplexity</span> <span style="color:#2A3A4A;font-size:10px">Perplexity AI — real-time facts & research grounding</span>
            </div>
            <div style="border-top:1px solid #111E2E;padding-top:12px;font-size:10px;color:#2A3A4A">
                <b style="color:#3A5060">ROUND 1</b> — Independent answers &nbsp;·&nbsp;
                <b style="color:#3A5060">ROUND 2</b> — Cross-examination &nbsp;·&nbsp;
                <b style="color:#3A5060">SYNTHESIS</b> — Unified best answer
            </div>
        </div>
        """, unsafe_allow_html=True)
        return

    personas = ["claude", "gemini", "gpt4", "perplexity"]

    # ── ROUND 1 ──────────────────────────────────────────────────
    render_phase_header(1, "INITIAL RESPONSES — Each AI answers independently", "active")

    cols1 = st.columns(4)
    placeholders_r1 = [c.empty() for c in cols1]

    for i, p in enumerate(personas):
        with placeholders_r1[i]:
            render_ai_card(p, "⟳ Thinking...", "ROUND 1")

    with st.spinner(""):
        tasks_r1 = [(p, "initial", question) for p in personas]
        r1 = run_parallel(tasks_r1)

    r1_map = dict(zip(personas, r1))
    for i, p in enumerate(personas):
        with placeholders_r1[i]:
            render_ai_card(p, r1_map[p], "ROUND 1")

    render_phase_header(1, "INITIAL RESPONSES — Each AI answers independently", "done")
    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    # ── ROUND 2 ──────────────────────────────────────────────────
    render_phase_header(2, "OPEN DEBATE — Each AI critiques and builds on the others", "active")

    cols2 = st.columns(4)
    placeholders_r2 = [c.empty() for c in cols2]

    for i, p in enumerate(personas):
        with placeholders_r2[i]:
            render_ai_card(p, "⟳ Reading others' responses...", "ROUND 2")

    def make_debate_prompt(me: str) -> str:
        others = [p for p in personas if p != me]
        return (
            f'Original question: "{question}"\n\n'
            f"MY INITIAL ANSWER:\n{r1_map[me]}\n\n"
            + "\n\n".join(f"{AI_CONFIG[o]['name'].upper()}'S ANSWER:\n{r1_map[o]}" for o in others)
            + "\n\nNow engage in genuine discussion. What do you agree with? "
              "What is incorrect or incomplete? What crucial perspectives are missing?"
        )

    with st.spinner(""):
        tasks_r2 = [(p, "debate", make_debate_prompt(p)) for p in personas]
        r2 = run_parallel(tasks_r2)

    r2_map = dict(zip(personas, r2))
    for i, p in enumerate(personas):
        with placeholders_r2[i]:
            render_ai_card(p, r2_map[p], "ROUND 2")

    render_phase_header(2, "OPEN DEBATE — Each AI critiques and builds on the others", "done")
    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    # ── SYNTHESIS ────────────────────────────────────────────────
    render_phase_header(3, "FINAL SYNTHESIS — Best answer distilled from all four voices", "active")

    synth_placeholder = st.empty()
    synth_placeholder.markdown('<div class="synth-box"><div style="color:#2A5A4A;font-size:12px">⟳ Synthesizing insights from all four AIs...</div></div>', unsafe_allow_html=True)

    synth_prompt = (
        f'QUESTION: "{question}"\n\n'
        "ROUND 1 INITIAL RESPONSES:\n"
        + "\n\n".join(f"[{AI_CONFIG[p]['name']}]\n{r1_map[p]}" for p in personas)
        + "\n\nROUND 2 DISCUSSION AND DEBATE:\n"
        + "\n\n".join(f"[{AI_CONFIG[p]['name']}]\n{r2_map[p]}" for p in personas)
        + "\n\nBased on this complete multi-AI discussion involving Claude, Gemini, GPT-4, and Perplexity, "
          "provide the single best comprehensive answer. Incorporate the strongest insights, "
          "resolve disagreements, and be definitive and clear."
    )

    with st.spinner(""):
        try:
            synthesis = call_claude(SYNTH_SYSTEM, synth_prompt)
        except Exception as e:
            synthesis = f"⚠ Synthesis error: {str(e)}"

    safe_synthesis = synthesis.replace("<", "&lt;").replace(">", "&gt;")
    synth_placeholder.markdown(f"""
    <div class="synth-box">
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px">
            <div style="width:28px;height:28px;border-radius:50%;background:rgba(61,255,192,0.1);border:1.5px solid rgba(61,255,192,0.4);display:flex;align-items:center;justify-content:center;font-size:14px;color:#3DFFC0">✦</div>
            <div>
                <div class="synth-title">SYNTHESIZED ANSWER</div>
                <div class="synth-sub">Moderated consensus · Claude · Gemini · GPT-4 · Perplexity</div>
            </div>
        </div>
        <div class="synth-text">{safe_synthesis}</div>
    </div>
    """, unsafe_allow_html=True)

    render_phase_header(3, "FINAL SYNTHESIS — Best answer distilled from all four voices", "done")

if __name__ == "__main__":
    main()
