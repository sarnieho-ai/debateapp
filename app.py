import streamlit as st
import anthropic
import requests
import concurrent.futures
import base64
import io
import urllib.parse
from typing import Optional

# Optional imports with graceful degradation
try:
    import pdfplumber
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

try:
    from bs4 import BeautifulSoup
    BS4_SUPPORT = True
except ImportError:
    BS4_SUPPORT = False

# ─── Page Config ────────────────────────────────────────────────
st.set_page_config(
    page_title="Nexus AI — Multi-Model Discussion Engine",
    page_icon="⬡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── Global CSS ─────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&display=swap');
html, body, [class*="css"] {
    font-family: 'JetBrains Mono', 'Courier New', monospace !important;
    background-color: #070B12 !important;
    color: #D0DCE8 !important;
}
.stApp { background-color: #070B12 !important; }
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 1.5rem; padding-bottom: 4rem; max-width: 1400px; }
.stTextArea textarea {
    background: #0D1420 !important; border: 1px solid #1A2A3A !important;
    color: #D0DCE8 !important; font-family: 'JetBrains Mono', monospace !important;
    font-size: 14px !important; border-radius: 8px !important;
}
.stTextArea textarea:focus { border-color: #3A5A8A !important; box-shadow: 0 0 0 1px #3A5A8A !important; }
.stTextInput input {
    background: #0D1420 !important; border: 1px solid #1A2A3A !important;
    color: #D0DCE8 !important; font-family: 'JetBrains Mono', monospace !important;
    font-size: 13px !important; border-radius: 8px !important;
}
.stTextInput input:focus { border-color: #7BA7FF !important; box-shadow: 0 0 0 1px #7BA7FF !important; }
.stButton > button {
    background: rgba(123,167,255,0.15) !important; color: #7BA7FF !important;
    border: 1px solid rgba(123,167,255,0.4) !important; border-radius: 6px !important;
    font-family: 'JetBrains Mono', monospace !important; font-size: 11px !important;
    font-weight: bold !important; letter-spacing: 0.1em !important; transition: all 0.2s !important;
}
.stButton > button:hover { background: rgba(123,167,255,0.28) !important; border-color: #7BA7FF !important; }
[data-testid="stFileUploader"] {
    background: #0A0F1C !important; border: 1px dashed #1E2E42 !important;
    border-radius: 8px !important; padding: 8px !important;
}
[data-testid="stFileUploader"] label { color: #3A5A7A !important; font-size: 11px !important; }
.streamlit-expanderHeader {
    background: #0D1420 !important; border: 1px solid #1A2A3A !important;
    border-radius: 6px !important; color: #7BA7FF !important;
    font-family: 'JetBrains Mono', monospace !important; font-size: 11px !important;
}
</style>
""", unsafe_allow_html=True)

# ─── AI Config ──────────────────────────────────────────────────
AI_CONFIG = {
    "claude":     {"name": "Claude",     "maker": "Anthropic",  "color": "#FF8B4E", "bg": "rgba(255,139,78,0.08)",  "border": "rgba(255,139,78,0.35)"},
    "gemini":     {"name": "Gemini",     "maker": "Google",     "color": "#7BA7FF", "bg": "rgba(123,167,255,0.08)", "border": "rgba(123,167,255,0.35)"},
    "gpt4":       {"name": "GPT-4",      "maker": "OpenAI",     "color": "#A8E6A3", "bg": "rgba(168,230,163,0.08)", "border": "rgba(168,230,163,0.35)"},
    "perplexity": {"name": "Perplexity", "maker": "Perplexity", "color": "#3DFFC0", "bg": "rgba(61,255,192,0.08)",  "border": "rgba(61,255,192,0.35)"},
}
PERSONAS_ORDER = ["claude", "gemini", "gpt4", "perplexity"]

PERSONAS = {
    "claude": {
        "initial":  "You are Claude by Anthropic. Respond with careful reasoning, nuance, and intellectual honesty. Acknowledge uncertainty. Be thorough yet clear. Show analytical depth. 3-5 paragraphs.",
        "debate":   "You are Claude by Anthropic. You gave an initial answer. Now engage in genuine multi-AI discussion. Agree where others are right, challenge where they are wrong or incomplete, add important angles they missed. 2-4 paragraphs.",
        "followup": "You are Claude by Anthropic in an ongoing multi-AI discussion. Respond thoughtfully to the follow-up, referencing the prior discussion where relevant. 2-3 paragraphs.",
    },
    "gemini": {
        "initial":  "You are Gemini by Google. Leverage broad world knowledge. Provide comprehensive coverage, draw connections across domains, highlight practical applications. 3-5 paragraphs.",
        "debate":   "You are Gemini by Google. Engage with the other AIs: build on strong points, challenge weak ones, bring in cross-domain knowledge they missed. 2-4 paragraphs.",
        "followup": "You are Gemini by Google in an ongoing multi-AI discussion. Respond to the follow-up with your broad cross-domain perspective. 2-3 paragraphs.",
    },
    "gpt4": {
        "initial":  "You are GPT-4 by OpenAI. Excel at deep logical reasoning, structured step-by-step analysis, and synthesis of complex ideas. Be precise and systematic. 3-5 paragraphs.",
        "debate":   "You are GPT-4 by OpenAI. Reason rigorously through the other AIs responses. Identify logical gaps, validate sound arguments, bring structured clarity. 2-4 paragraphs.",
        "followup": "You are GPT-4 by OpenAI in an ongoing multi-AI discussion. Apply rigorous logical analysis to the follow-up, referencing prior discussion. 2-3 paragraphs.",
    },
    "perplexity": {
        "initial":  "You are Perplexity, an AI research engine. Be direct, fact-focused, research-oriented. Lead with specific data, verifiable facts, concrete examples. 3-5 paragraphs.",
        "debate":   "You are Perplexity AI. Push back on vagueness, validate accurate points, add concrete facts or research others missed. 2-4 paragraphs.",
        "followup": "You are Perplexity AI in an ongoing multi-AI discussion. Ground the follow-up in concrete facts and research, referencing what was established. 2-3 paragraphs.",
    },
}

SYNTH_SYSTEM = (
    "You are a neutral expert moderator synthesizing a multi-AI discussion between Claude, Gemini, GPT-4, and Perplexity. "
    "Produce the single best, most comprehensive answer by incorporating the strongest insights, "
    "resolving disagreements with sound reasoning, and eliminating redundancy. Be definitive, well-structured, and clear."
)

FOLLOWUP_SYNTH_SYSTEM = (
    "You are a neutral expert moderator in an ongoing multi-AI discussion. "
    "A follow-up question has been raised. Synthesize the four AIs follow-up responses into the best possible answer, "
    "incorporating new insights and how they update or refine the previous synthesis."
)

# ─── Secrets ────────────────────────────────────────────────────
def get_secret(key: str) -> Optional[str]:
    try:
        return st.secrets[key]
    except Exception:
        return None

ANTHROPIC_KEY  = get_secret("ANTHROPIC_API_KEY")
GEMINI_KEY     = get_secret("GEMINI_API_KEY")
OPENAI_KEY     = get_secret("OPENAI_API_KEY")
PERPLEXITY_KEY = get_secret("PERPLEXITY_API_KEY")

# ─── Context Processing ──────────────────────────────────────────
def extract_pdf_text(file_bytes: bytes) -> str:
    if not PDF_SUPPORT:
        return "[PDF support not available — install pdfplumber]"
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
        text = "\n\n".join(pages).strip()
        # Trim to ~8000 chars to keep within context limits
        return text[:8000] + ("\n\n[...truncated for length]" if len(text) > 8000 else "")
    except Exception as e:
        return f"[PDF extraction error: {e}]"

def fetch_url_text(url: str) -> str:
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; NexusAI/1.0)"}
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        if BS4_SUPPORT:
            soup = BeautifulSoup(r.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            text = soup.get_text(separator="\n", strip=True)
        else:
            text = r.text
        # Trim to ~6000 chars
        return text[:6000] + ("\n\n[...truncated for length]" if len(text) > 6000 else "")
    except Exception as e:
        return f"[URL fetch error: {e}]"

def image_to_base64(file_bytes: bytes, media_type: str) -> str:
    return base64.b64encode(file_bytes).decode("utf-8")

def build_text_context(context_items: list) -> str:
    """Build a text block from non-image context items."""
    if not context_items:
        return ""
    parts = ["[ADDITIONAL CONTEXT PROVIDED BY USER]"]
    for item in context_items:
        parts.append(f"\n--- {item['label']} ---\n{item['content']}")
    parts.append("[END OF CONTEXT]\n\n")
    return "\n".join(parts)

# ─── API Callers ─────────────────────────────────────────────────
def call_claude(system: str, message: str, image_data: list = None) -> str:
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    if image_data:
        content = []
        for img in image_data:
            content.append({"type": "image", "source": {"type": "base64", "media_type": img["media_type"], "data": img["data"]}})
        content.append({"type": "text", "text": message})
    else:
        content = message
    response = client.messages.create(
        model="claude-opus-4-5-20251101",
        max_tokens=1000,
        system=system,
        messages=[{"role": "user", "content": content}],
    )
    return response.content[0].text

def call_gemini(system: str, message: str, image_data: list = None) -> str:
    if not GEMINI_KEY:
        raise ValueError("No Gemini key")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
    parts = []
    if image_data:
        for img in image_data:
            parts.append({"inline_data": {"mime_type": img["media_type"], "data": img["data"]}})
    parts.append({"text": message})
    payload = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"parts": parts}],
    }
    r = requests.post(url, json=payload, timeout=60)
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]

def call_gpt4(system: str, message: str, image_data: list = None) -> str:
    if not OPENAI_KEY:
        raise ValueError("No OpenAI key")
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {OPENAI_KEY}"}
    if image_data:
        content = []
        for img in image_data:
            content.append({"type": "image_url", "image_url": {"url": f"data:{img['media_type']};base64,{img['data']}"}})
        content.append({"type": "text", "text": message})
    else:
        content = message
    r = requests.post("https://api.openai.com/v1/chat/completions", json={
        "model": "gpt-4o",
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": content}],
        "max_tokens": 1000,
    }, headers=headers, timeout=60)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

def call_perplexity(system: str, message: str, image_data: list = None) -> str:
    # Perplexity doesn't support vision — image context described in text
    if not PERPLEXITY_KEY:
        raise ValueError("No Perplexity key")
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {PERPLEXITY_KEY}"}
    r = requests.post("https://api.perplexity.ai/chat/completions", json={
        "model": "llama-3.1-sonar-small-128k-online",
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": message}],
    }, headers=headers, timeout=60)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

def call_persona(persona: str, prompt_type: str, message: str, image_data: list = None) -> str:
    system = PERSONAS[persona][prompt_type]
    try:
        if persona == "gemini":
            return call_gemini(system, message, image_data)
        elif persona == "gpt4":
            return call_gpt4(system, message, image_data)
        elif persona == "perplexity":
            return call_perplexity(system, message, image_data)
        else:
            return call_claude(system, message, image_data)
    except Exception:
        return call_claude(system, message, image_data)

def run_parallel(tasks: list) -> list:
    results = [None] * len(tasks)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        future_to_idx = {executor.submit(call_persona, *t): i for i, t in enumerate(tasks)}
        for future in concurrent.futures.as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                results[idx] = future.result()
            except Exception as e:
                results[idx] = f"Error: {str(e)}"
    return results

# ─── UI Helpers ──────────────────────────────────────────────────
def ai_card_html(persona: str, text: str, label: str = "") -> str:
    cfg = AI_CONFIG[persona]
    c, bg, br = cfg["color"], cfg["bg"], cfg["border"]
    safe_text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    label_html = f'<span style="margin-left:auto;font-size:9px;color:#3A4A5A;background:#111820;padding:2px 6px;border-radius:3px;letter-spacing:0.06em">{label}</span>' if label else ""
    return (
        f'<div style="background:{bg};border:1px solid {br};border-radius:10px;padding:16px;min-height:160px;font-family:monospace">'
        f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:12px">'
        f'<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:{c};box-shadow:0 0 8px {c};flex-shrink:0"></span>'
        f'<span style="color:{c};font-weight:bold;font-size:12px;letter-spacing:0.08em">{cfg["name"].upper()}</span>'
        f'<span style="color:#3A4A5A;font-size:10px">{cfg["maker"]}</span>'
        f'{label_html}</div>'
        f'<div style="color:#B0C4D8;font-size:12.5px;line-height:1.75;white-space:pre-wrap;word-break:break-word">{safe_text}</div>'
        f'</div>'
    )

def phase_header(num: int, title: str, state: str):
    colors = {
        "waiting": ("#0D1420", "#1E2A3A", "#2A3A4A"),
        "active":  ("rgba(123,167,255,0.15)", "#7BA7FF", "#7BA7FF"),
        "done":    ("rgba(61,255,192,0.15)",  "#3DFFC0", "#3DFFC0"),
    }
    bg, border, tc = colors[state]
    icon = "✓" if state == "done" else str(num)
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:12px;margin:20px 0 14px 0">'
        f'<span style="display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;'
        f'border-radius:50%;background:{bg};border:1.5px solid {border};font-size:12px;font-weight:bold;'
        f'color:{tc};flex-shrink:0;font-family:monospace">{icon}</span>'
        f'<span style="font-size:11px;font-weight:bold;letter-spacing:0.1em;color:{tc};font-family:monospace">{title}</span>'
        f'</div>',
        unsafe_allow_html=True
    )

def divider():
    st.markdown('<hr style="border:none;border-top:1px solid #111E2E;margin:24px 0">', unsafe_allow_html=True)

def key_status_banner():
    checks = [("Claude", ANTHROPIC_KEY, True), ("Gemini", GEMINI_KEY, False), ("GPT-4", OPENAI_KEY, False), ("Perplexity", PERPLEXITY_KEY, False)]
    parts = []
    for name, key, required in checks:
        if key:
            parts.append(f'<span style="color:#3DFFC0">✓ {name}</span>')
        else:
            color = "#FF6B6B" if required else "#3A5060"
            note  = "REQUIRED" if required else "simulated"
            parts.append(f'<span style="color:{color}">✗ {name} ({note})</span>')
    st.markdown(
        f'<div style="font-size:11px;color:#3A5060;padding:10px 14px;background:#090E18;border-radius:6px;'
        f'border-left:3px solid #1A3A5A;margin-bottom:18px;font-family:monospace">'
        f'API KEYS &nbsp;·&nbsp; {" &nbsp;·&nbsp; ".join(parts)}</div>',
        unsafe_allow_html=True
    )

# ─── Context Upload UI ───────────────────────────────────────────
def render_context_panel() -> tuple:
    """
    Renders the upload/URL section.
    Returns (text_context: str, image_data: list, context_summary: str)
    """
    with st.expander("📎  ADD CONTEXT — documents, images, or links  (optional)", expanded=False):
        st.markdown(
            '<div style="font-size:10px;color:#3A5060;margin-bottom:12px;font-family:monospace">'
            'All context is passed to every AI model. Images are sent to vision-capable models (Claude, Gemini, GPT-4). '
            'Perplexity receives a text description of any image.</div>',
            unsafe_allow_html=True
        )

        col_file, col_url = st.columns([3, 2])

        with col_file:
            st.markdown('<div style="font-size:10px;color:#5A7A9A;margin-bottom:6px;font-family:monospace">📄 UPLOAD FILES</div>', unsafe_allow_html=True)
            uploaded = st.file_uploader(
                label="Upload files",
                type=["pdf", "png", "jpg", "jpeg", "webp", "gif"],
                accept_multiple_files=True,
                label_visibility="collapsed",
            )

        with col_url:
            st.markdown('<div style="font-size:10px;color:#5A7A9A;margin-bottom:6px;font-family:monospace">🔗 ADD URL</div>', unsafe_allow_html=True)
            url_input = st.text_input(
                label="URL",
                placeholder="https://example.com/article",
                label_visibility="collapsed",
            )

    # Process context
    text_context_items = []
    image_data = []
    context_summary_parts = []

    if uploaded:
        for f in uploaded:
            file_bytes = f.read()
            if f.type == "application/pdf":
                text = extract_pdf_text(file_bytes)
                text_context_items.append({"label": f"PDF: {f.name}", "content": text})
                context_summary_parts.append(f"📄 {f.name}")
            elif f.type.startswith("image/"):
                b64 = image_to_base64(file_bytes, f.type)
                image_data.append({"media_type": f.type, "data": b64, "name": f.name})
                context_summary_parts.append(f"🖼 {f.name}")
                # For Perplexity (no vision), add a text note
                text_context_items.append({"label": f"Image: {f.name}", "content": f"[An image file named '{f.name}' has been provided. Please analyze it based on the question.]"})

    if url_input and url_input.strip().startswith("http"):
        with st.spinner(f"Fetching {url_input[:50]}..."):
            url_text = fetch_url_text(url_input.strip())
        text_context_items.append({"label": f"URL: {url_input.strip()}", "content": url_text})
        context_summary_parts.append(f"🔗 {url_input.strip()[:40]}...")

    text_context = build_text_context(text_context_items)
    context_summary = ", ".join(context_summary_parts) if context_summary_parts else ""

    if context_summary:
        st.markdown(
            f'<div style="font-size:10px;color:#3DFFC0;padding:6px 12px;background:rgba(61,255,192,0.05);'
            f'border:1px solid rgba(61,255,192,0.2);border-radius:6px;margin-top:8px;font-family:monospace">'
            f'✓ Context loaded: {context_summary}</div>',
            unsafe_allow_html=True
        )

    return text_context, image_data, context_summary

# ─── Share Panel ─────────────────────────────────────────────────
def render_share_panel(question: str, synthesis: str, followups: list):
    divider()
    st.markdown(
        '<div style="font-size:11px;font-weight:bold;letter-spacing:0.1em;color:#FF8B4E;margin-bottom:14px;font-family:monospace">📤 SHARE THIS DISCUSSION</div>',
        unsafe_allow_html=True
    )

    # Build full shareable text
    fu_text = ""
    for i, fu in enumerate(followups):
        fu_text += f"\n\nFOLLOW-UP {i+1}: {fu['question']}\n{fu.get('synthesis', '')}"

    full_text = (
        f"NEXUS AI — Multi-Model Discussion\n"
        f"{'='*50}\n\n"
        f"QUESTION: {question}\n\n"
        f"SYNTHESIZED ANSWER (Claude + Gemini + GPT-4 + Perplexity):\n{synthesis}"
        f"{fu_text}\n\n"
        f"Generated by Nexus AI — 4-Model Discussion Engine"
    )

    short_summary = synthesis[:280] + "..." if len(synthesis) > 280 else synthesis
    encoded_text   = urllib.parse.quote(f"Q: {question}\n\n{short_summary}\n\n#NexusAI #AI")
    encoded_email_body = urllib.parse.quote(full_text)
    encoded_email_subj = urllib.parse.quote(f"Nexus AI Discussion: {question[:60]}")
    encoded_wa    = urllib.parse.quote(f"*Nexus AI Discussion*\n\n*Q: {question}*\n\n{short_summary}")

    col1, col2, col3, col4, col5 = st.columns(5)

    # 1. Copy to clipboard (JS)
    with col1:
        escaped = full_text.replace("`", "'").replace("\\", "\\\\").replace("\n", "\\n")
        st.components.v1.html(
            f"""
            <button onclick="navigator.clipboard.writeText(`{escaped}`).then(()=>{{
                this.innerText='✓ COPIED!';this.style.color='#3DFFC0';this.style.borderColor='#3DFFC0';
                setTimeout(()=>{{this.innerText='📋 COPY';this.style.color='#7BA7FF';this.style.borderColor='rgba(123,167,255,0.4)';}},2000);
            }})" style="width:100%;background:rgba(123,167,255,0.15);color:#7BA7FF;border:1px solid rgba(123,167,255,0.4);
            border-radius:6px;padding:8px 4px;font-family:monospace;font-size:11px;font-weight:bold;
            letter-spacing:0.08em;cursor:pointer;transition:all 0.2s">
            📋 COPY
            </button>
            """,
            height=42,
        )

    # 2. Download as Markdown
    with col2:
        st.download_button(
            label="⬇ DOWNLOAD",
            data=full_text,
            file_name="nexus-ai-discussion.md",
            mime="text/markdown",
            use_container_width=True,
        )

    # 3. Email
    with col3:
        st.markdown(
            f'<a href="mailto:?subject={encoded_email_subj}&body={encoded_email_body}" target="_blank">'
            f'<button style="width:100%;background:rgba(123,167,255,0.15);color:#7BA7FF;border:1px solid rgba(123,167,255,0.4);'
            f'border-radius:6px;padding:8px 4px;font-family:monospace;font-size:11px;font-weight:bold;'
            f'letter-spacing:0.08em;cursor:pointer">📧 EMAIL</button></a>',
            unsafe_allow_html=True
        )

    # 4. WhatsApp
    with col4:
        st.markdown(
            f'<a href="https://wa.me/?text={encoded_wa}" target="_blank">'
            f'<button style="width:100%;background:rgba(123,167,255,0.15);color:#7BA7FF;border:1px solid rgba(123,167,255,0.4);'
            f'border-radius:6px;padding:8px 4px;font-family:monospace;font-size:11px;font-weight:bold;'
            f'letter-spacing:0.08em;cursor:pointer">💬 WHATSAPP</button></a>',
            unsafe_allow_html=True
        )

    # 5. Twitter/X
    with col5:
        st.markdown(
            f'<a href="https://twitter.com/intent/tweet?text={encoded_text}" target="_blank">'
            f'<button style="width:100%;background:rgba(123,167,255,0.15);color:#7BA7FF;border:1px solid rgba(123,167,255,0.4);'
            f'border-radius:6px;padding:8px 4px;font-family:monospace;font-size:11px;font-weight:bold;'
            f'letter-spacing:0.08em;cursor:pointer">𝕏 TWITTER</button></a>',
            unsafe_allow_html=True
        )

# ─── Session State ───────────────────────────────────────────────
def init_state():
    for k, v in {"phase": 0, "question": "", "r1": {}, "r2": {}, "synthesis": None, "followups": [], "context_summary": ""}.items():
        if k not in st.session_state:
            st.session_state[k] = v

# ─── Main App ────────────────────────────────────────────────────
def main():
    init_state()

    # Header
    st.markdown(
        '<div style="background:rgba(10,14,24,0.97);border-bottom:1px solid #111E2E;padding:18px 32px;margin:-1.5rem -4rem 1.5rem -4rem">'
        '<div style="font-size:20px;font-weight:bold;letter-spacing:0.15em;color:#E0E8F5;font-family:monospace">⬡ NEXUS AI</div>'
        '<div style="font-size:10px;color:#3A5A7A;letter-spacing:0.1em;margin-top:4px;font-family:monospace">'
        '4-MODEL DISCUSSION ENGINE &nbsp;·&nbsp; CLAUDE &nbsp;·&nbsp; GEMINI &nbsp;·&nbsp; GPT-4 &nbsp;·&nbsp; PERPLEXITY</div></div>',
        unsafe_allow_html=True
    )

    key_status_banner()

    if not ANTHROPIC_KEY:
        st.error("ANTHROPIC_API_KEY is required. Add it to .streamlit/secrets.toml")
        st.stop()

    # ── Context panel ────────────────────────────────────────────
    text_context, image_data, context_summary = render_context_panel()

    # ── Question Input ───────────────────────────────────────────
    question = st.text_area(
        label="Question",
        placeholder="Ask anything — or describe what you want the AIs to discuss about your uploaded content...",
        height=100,
        label_visibility="collapsed",
    )

    col_btn, col_note = st.columns([1, 5])
    with col_btn:
        start = st.button("▶  START DISCUSSION", use_container_width=True)
    with col_note:
        note = f"Context: {context_summary} · " if context_summary else ""
        st.markdown(
            f'<div style="color:#2A3A4A;font-size:11px;padding-top:10px;font-family:monospace">{note}4 models run in parallel · missing keys fall back to Claude simulation</div>',
            unsafe_allow_html=True
        )

    divider()

    # ── Idle state ───────────────────────────────────────────────
    if st.session_state.phase == 0 and not start:
        st.markdown(
            '<div style="padding:20px;background:#090E18;border-radius:10px;border:1px solid #111E2E;font-family:monospace">'
            '<div style="font-size:9px;letter-spacing:0.12em;color:#3A5060;margin-bottom:14px">PARTICIPATING MODELS</div>'
            '<div style="display:flex;flex-wrap:wrap;gap:20px;margin-bottom:14px">'
            '<span><b style="color:#FF8B4E">● Claude</b> <span style="color:#2A3A4A;font-size:10px">— nuance, intellectual honesty</span></span>'
            '<span><b style="color:#7BA7FF">● Gemini</b> <span style="color:#2A3A4A;font-size:10px">— broad cross-domain knowledge</span></span>'
            '<span><b style="color:#A8E6A3">● GPT-4</b> <span style="color:#2A3A4A;font-size:10px">— deep logical reasoning</span></span>'
            '<span><b style="color:#3DFFC0">● Perplexity</b> <span style="color:#2A3A4A;font-size:10px">— real-time facts & research</span></span>'
            '</div>'
            '<div style="border-top:1px solid #111E2E;padding-top:12px;font-size:10px;color:#2A3A4A">'
            'ROUND 1 — independent answers &nbsp;·&nbsp; ROUND 2 — cross-examination &nbsp;·&nbsp; '
            'SYNTHESIS — unified best answer &nbsp;·&nbsp; FOLLOW-UP — continue the discussion &nbsp;·&nbsp; '
            'SHARE — copy, download, email, WhatsApp, Twitter'
            '</div></div>',
            unsafe_allow_html=True
        )
        return

    # ── Start ────────────────────────────────────────────────────
    if start and question.strip():
        st.session_state.phase          = 1
        st.session_state.question       = question.strip()
        st.session_state.r1             = {}
        st.session_state.r2             = {}
        st.session_state.synthesis      = None
        st.session_state.followups      = []
        st.session_state.context_summary = context_summary

    q = st.session_state.question
    if not q:
        return

    # Prepend context to message
    def with_ctx(msg: str) -> str:
        return text_context + msg if text_context else msg

    # ── ROUND 1 ──────────────────────────────────────────────────
    phase_header(1, "INITIAL RESPONSES — Each AI answers independently",
                 "done" if st.session_state.phase > 1 else "active")

    if not st.session_state.r1:
        cols = st.columns(4)
        for i, p in enumerate(PERSONAS_ORDER):
            cols[i].markdown(ai_card_html(p, "⟳ Thinking...", "ROUND 1"), unsafe_allow_html=True)
        with st.spinner("Round 1 — all models answering..."):
            results = run_parallel([(p, "initial", with_ctx(q), image_data) for p in PERSONAS_ORDER])
        st.session_state.r1 = dict(zip(PERSONAS_ORDER, results))
        st.session_state.phase = 2
        st.rerun()

    cols = st.columns(4)
    for i, p in enumerate(PERSONAS_ORDER):
        cols[i].markdown(ai_card_html(p, st.session_state.r1[p], "ROUND 1"), unsafe_allow_html=True)

    divider()

    # ── ROUND 2 ──────────────────────────────────────────────────
    phase_header(2, "OPEN DEBATE — Each AI critiques and builds on the others",
                 "done" if st.session_state.phase > 2 else "active")

    def make_debate(me: str) -> str:
        others = [p for p in PERSONAS_ORDER if p != me]
        return with_ctx(
            f'Original question: "{q}"\n\nMY INITIAL ANSWER:\n{st.session_state.r1[me]}\n\n'
            + "\n\n".join(f"{AI_CONFIG[o]['name'].upper()}'S ANSWER:\n{st.session_state.r1[o]}" for o in others)
            + "\n\nNow engage in genuine discussion. Agree, challenge, extend. What crucial perspectives are missing?"
        )

    if not st.session_state.r2:
        cols = st.columns(4)
        for i, p in enumerate(PERSONAS_ORDER):
            cols[i].markdown(ai_card_html(p, "⟳ Reading others' responses...", "ROUND 2"), unsafe_allow_html=True)
        with st.spinner("Round 2 — models debating each other..."):
            results = run_parallel([(p, "debate", make_debate(p), None) for p in PERSONAS_ORDER])
        st.session_state.r2 = dict(zip(PERSONAS_ORDER, results))
        st.session_state.phase = 3
        st.rerun()

    cols = st.columns(4)
    for i, p in enumerate(PERSONAS_ORDER):
        cols[i].markdown(ai_card_html(p, st.session_state.r2[p], "ROUND 2"), unsafe_allow_html=True)

    divider()

    # ── SYNTHESIS ────────────────────────────────────────────────
    phase_header(3, "FINAL SYNTHESIS — Best answer distilled from all four voices",
                 "done" if st.session_state.phase >= 4 else "active")

    if not st.session_state.synthesis:
        synth_prompt = (
            f'QUESTION: "{q}"\n\n'
            "ROUND 1:\n" + "\n\n".join(f"[{AI_CONFIG[p]['name']}]\n{st.session_state.r1[p]}" for p in PERSONAS_ORDER)
            + "\n\nROUND 2:\n" + "\n\n".join(f"[{AI_CONFIG[p]['name']}]\n{st.session_state.r2[p]}" for p in PERSONAS_ORDER)
            + "\n\nProvide the single best comprehensive answer. Incorporate strongest insights. Be definitive and clear."
        )
        with st.spinner("Synthesizing final answer..."):
            try:
                st.session_state.synthesis = call_claude(SYNTH_SYSTEM, synth_prompt)
            except Exception as e:
                st.session_state.synthesis = f"Synthesis error: {str(e)}"
        st.session_state.phase = 4
        st.rerun()

    safe_synth = st.session_state.synthesis.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    st.markdown(
        f'<div style="background:rgba(61,255,192,0.05);border:1px solid rgba(61,255,192,0.25);border-radius:10px;padding:24px;font-family:monospace">'
        f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:14px">'
        f'<div style="width:28px;height:28px;border-radius:50%;background:rgba(61,255,192,0.1);border:1.5px solid rgba(61,255,192,0.4);'
        f'display:flex;align-items:center;justify-content:center;color:#3DFFC0;font-size:14px">✦</div>'
        f'<div><div style="font-size:12px;font-weight:bold;color:#3DFFC0;letter-spacing:0.08em">SYNTHESIZED ANSWER</div>'
        f'<div style="font-size:10px;color:#2A5A4A">Moderated consensus · Claude · Gemini · GPT-4 · Perplexity</div></div></div>'
        f'<div style="color:#C0D8D0;font-size:13.5px;line-height:1.8;white-space:pre-wrap">{safe_synth}</div></div>',
        unsafe_allow_html=True
    )

    # ── FOLLOW-UP CHAT ───────────────────────────────────────────
    if st.session_state.phase >= 4:
        divider()
        st.markdown(
            '<div style="font-size:11px;font-weight:bold;letter-spacing:0.1em;color:#7BA7FF;margin-bottom:8px;font-family:monospace">💬 CONTINUE THE DISCUSSION</div>'
            '<div style="font-size:11px;color:#2A3A4A;margin-bottom:14px;font-family:monospace">Ask a follow-up, counter-propose, or challenge any part of the synthesis.</div>',
            unsafe_allow_html=True
        )

        for i, fu in enumerate(st.session_state.followups):
            with st.expander(f"↩ Follow-up {i+1}: {fu['question'][:60]}{'...' if len(fu['question']) > 60 else ''}", expanded=(i == len(st.session_state.followups) - 1)):
                cols = st.columns(4)
                for j, p in enumerate(PERSONAS_ORDER):
                    cols[j].markdown(ai_card_html(p, fu["responses"].get(p, ""), "FOLLOW-UP"), unsafe_allow_html=True)
                if fu.get("synthesis"):
                    safe_fu = fu["synthesis"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    st.markdown(
                        f'<div style="background:rgba(123,167,255,0.05);border:1px solid rgba(123,167,255,0.2);border-radius:10px;'
                        f'padding:20px;margin-top:12px;font-family:monospace">'
                        f'<div style="font-size:11px;font-weight:bold;color:#7BA7FF;margin-bottom:10px">↩ UPDATED SYNTHESIS</div>'
                        f'<div style="color:#C0D0E8;font-size:13px;line-height:1.8;white-space:pre-wrap">{safe_fu}</div></div>',
                        unsafe_allow_html=True
                    )

        col_input, col_send = st.columns([5, 1])
        with col_input:
            followup_q = st.text_input(
                label="Follow-up",
                placeholder="Ask a follow-up, counter the synthesis, or challenge a specific point...",
                label_visibility="collapsed",
                key=f"fu_input_{len(st.session_state.followups)}",
            )
        with col_send:
            send_fu = st.button("▶  SEND", use_container_width=True, key=f"send_{len(st.session_state.followups)}")

        if send_fu and followup_q.strip():
            history_ctx = (
                f'ORIGINAL QUESTION: "{q}"\n\nINITIAL SYNTHESIS:\n{st.session_state.synthesis}\n\n'
                + (
                    "PRIOR FOLLOW-UPS:\n" + "\n\n".join(
                        f"Q{i+1}: {fu['question']}\nSynthesis: {fu.get('synthesis', '')}"
                        for i, fu in enumerate(st.session_state.followups)
                    ) + "\n\n" if st.session_state.followups else ""
                )
                + f'NEW FOLLOW-UP: "{followup_q.strip()}"'
            )
            with st.spinner("All 4 models responding..."):
                fu_results = run_parallel([(p, "followup", history_ctx, None) for p in PERSONAS_ORDER])
            fu_map = dict(zip(PERSONAS_ORDER, fu_results))
            fu_synth_prompt = (
                f"{history_ctx}\n\nFOLLOW-UP RESPONSES:\n"
                + "\n\n".join(f"[{AI_CONFIG[p]['name']}]\n{fu_map[p]}" for p in PERSONAS_ORDER)
                + "\n\nSynthesize the best updated answer incorporating these follow-up responses."
            )
            with st.spinner("Synthesizing updated answer..."):
                try:
                    fu_synthesis = call_claude(FOLLOWUP_SYNTH_SYSTEM, fu_synth_prompt)
                except Exception as e:
                    fu_synthesis = f"Synthesis error: {str(e)}"
            st.session_state.followups.append({"question": followup_q.strip(), "responses": fu_map, "synthesis": fu_synthesis})
            st.rerun()

        # ── SHARE ────────────────────────────────────────────────
        render_share_panel(q, st.session_state.synthesis, st.session_state.followups)

        # Reset
        st.markdown('<div style="margin-top:20px"></div>', unsafe_allow_html=True)
        if st.button("↺  NEW DISCUSSION"):
            for key in ["phase", "question", "r1", "r2", "synthesis", "followups", "context_summary"]:
                del st.session_state[key]
            st.rerun()

if __name__ == "__main__":
    main()
