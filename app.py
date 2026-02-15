import streamlit as st
import anthropic
import requests
import concurrent.futures
import base64
import io
import urllib.parse
import json
import os
import uuid
from datetime import datetime, timedelta
from typing import Optional

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

st.set_page_config(page_title="Nexus AI", page_icon="⬡", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&display=swap');
html,body,[class*="css"]{font-family:'JetBrains Mono',monospace!important;background-color:#070B12!important;color:#D0DCE8!important;}
.stApp{background-color:#070B12!important;}
#MainMenu,footer,header{visibility:hidden;}
.block-container{padding-top:1.5rem;padding-bottom:4rem;max-width:1500px;}
[data-testid="stSidebar"]{background:#0A0E18!important;border-right:1px solid #111E2E!important;}
.stTextArea textarea{background:#0D1420!important;border:1px solid #1A2A3A!important;color:#D0DCE8!important;font-family:'JetBrains Mono',monospace!important;font-size:14px!important;border-radius:8px!important;}
.stTextArea textarea:focus{border-color:#3A5A8A!important;box-shadow:0 0 0 1px #3A5A8A!important;}
.stTextInput input{background:#0D1420!important;border:1px solid #1A2A3A!important;color:#D0DCE8!important;font-family:'JetBrains Mono',monospace!important;font-size:13px!important;border-radius:8px!important;}
.stTextInput input:focus{border-color:#7BA7FF!important;}
.stButton>button{background:rgba(123,167,255,0.15)!important;color:#7BA7FF!important;border:1px solid rgba(123,167,255,0.4)!important;border-radius:6px!important;font-family:'JetBrains Mono',monospace!important;font-size:11px!important;font-weight:bold!important;letter-spacing:0.1em!important;}
.stButton>button:hover{background:rgba(123,167,255,0.28)!important;}
[data-testid="stFileUploader"]{background:#0A0F1C!important;border:1px dashed #1E2E42!important;border-radius:8px!important;}
.streamlit-expanderHeader{background:#0D1420!important;border:1px solid #1A2A3A!important;border-radius:6px!important;color:#7BA7FF!important;font-family:'JetBrains Mono',monospace!important;}
</style>
""", unsafe_allow_html=True)

AI_CONFIG = {
    "claude":     {"name":"Claude",    "maker":"Anthropic",  "color":"#FF8B4E","bg":"rgba(255,139,78,0.08)", "border":"rgba(255,139,78,0.35)"},
    "gemini":     {"name":"Gemini",    "maker":"Google",     "color":"#7BA7FF","bg":"rgba(123,167,255,0.08)","border":"rgba(123,167,255,0.35)"},
    "gpt4":       {"name":"GPT-4",     "maker":"OpenAI",     "color":"#A8E6A3","bg":"rgba(168,230,163,0.08)","border":"rgba(168,230,163,0.35)"},
    "perplexity": {"name":"Perplexity","maker":"Perplexity", "color":"#3DFFC0","bg":"rgba(61,255,192,0.08)", "border":"rgba(61,255,192,0.35)"},
    "deepseek":   {"name":"DeepSeek",  "maker":"DeepSeek",   "color":"#C084FC","bg":"rgba(192,132,252,0.08)","border":"rgba(192,132,252,0.35)"},
}
PERSONAS_ORDER = ["claude","gemini","gpt4","perplexity","deepseek"]

PERSONAS = {
    "claude":     {
        "initial":  "You are Claude by Anthropic. Careful reasoning, nuance, intellectual honesty. Thorough yet clear. 3-5 paragraphs.",
        "debate":   "You are Claude. Engage genuinely: agree where right, challenge where wrong, add missing angles. 2-4 paragraphs.",
        "followup": "You are Claude in an ongoing multi-AI discussion. Respond thoughtfully, referencing prior discussion. 2-3 paragraphs.",
    },
    "gemini":     {
        "initial":  "You are Gemini by Google. Broad world knowledge, cross-domain connections, practical applications. 3-5 paragraphs.",
        "debate":   "You are Gemini. Build on strong points, challenge weak ones, bring cross-domain knowledge. 2-4 paragraphs.",
        "followup": "You are Gemini in an ongoing discussion. Broad cross-domain perspective. 2-3 paragraphs.",
    },
    "gpt4":       {
        "initial":  "You are GPT-4 by OpenAI. Deep logical reasoning, structured analysis, precision. 3-5 paragraphs.",
        "debate":   "You are GPT-4. Identify logical gaps, validate sound arguments, bring structured clarity. 2-4 paragraphs.",
        "followup": "You are GPT-4 in an ongoing discussion. Rigorous logical analysis. 2-3 paragraphs.",
    },
    "perplexity": {
        "initial":  "You are Perplexity AI. Direct, fact-focused, research-oriented. Lead with data, verifiable facts, concrete examples. 3-5 paragraphs.",
        "debate":   "You are Perplexity. Push back on vagueness, add concrete facts and research. 2-4 paragraphs.",
        "followup": "You are Perplexity in an ongoing discussion. Ground in concrete facts and research. 2-3 paragraphs.",
    },
    "deepseek":   {
        "initial":  "You are DeepSeek. Exceptional STEM, math, coding, scientific reasoning. Rigorous and precise. 3-5 paragraphs.",
        "debate":   "You are DeepSeek. Apply mathematical and logical rigour to validate or challenge others arguments. 2-4 paragraphs.",
        "followup": "You are DeepSeek in an ongoing discussion. Analytical precision and STEM-grounded reasoning. 2-3 paragraphs.",
    },
}

SYNTH_SYSTEM = "You are a neutral expert moderator synthesizing a multi-AI discussion between Claude, Gemini, GPT-4, Perplexity, and DeepSeek. Produce the single best comprehensive answer incorporating strongest insights, resolving disagreements. Be definitive and clear."
FOLLOWUP_SYNTH_SYSTEM = "You are a neutral expert moderator. Synthesize the five AIs follow-up responses into the best updated answer, incorporating new insights that refine the previous synthesis."

def get_secret(key):
    try: return st.secrets[key]
    except: return None

ANTHROPIC_KEY  = get_secret("ANTHROPIC_API_KEY")
GEMINI_KEY     = get_secret("GEMINI_API_KEY")
OPENAI_KEY     = get_secret("OPENAI_API_KEY")
PERPLEXITY_KEY = get_secret("PERPLEXITY_API_KEY")
DEEPSEEK_KEY   = get_secret("DEEPSEEK_API_KEY")

HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nexus_history.json")

def load_history():
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE,"r",encoding="utf-8") as f: return json.load(f)
    except: pass
    return []

def save_history(history):
    try:
        with open(HISTORY_FILE,"w",encoding="utf-8") as f: json.dump(history,f,ensure_ascii=False,indent=2)
    except Exception as e: st.warning(f"Could not save history: {e}")

def save_discussion(disc):
    history = load_history()
    for i,d in enumerate(history):
        if d.get("id")==disc["id"]: history[i]=disc; save_history(history); return
    history.append(disc); save_history(history)

def delete_discussion(disc_id):
    save_history([d for d in load_history() if d.get("id")!=disc_id])

def filter_history(days):
    history = load_history()
    if days > 0:
        cutoff = datetime.utcnow()-timedelta(days=days)
        history = [d for d in history if datetime.fromisoformat(d.get("created_at","2000-01-01"))>=cutoff]
    return sorted(history,key=lambda d:d.get("created_at",""),reverse=True)

def group_by_date(discs):
    now = datetime.utcnow().date()
    groups = {"Today":[],"Yesterday":[],"This Week":[],"Older":[]}
    for d in discs:
        try: ts=datetime.fromisoformat(d["created_at"]).date()
        except: ts=now
        delta=(now-ts).days
        if delta==0: groups["Today"].append(d)
        elif delta==1: groups["Yesterday"].append(d)
        elif delta<=7: groups["This Week"].append(d)
        else: groups["Older"].append(d)
    return groups

def extract_pdf_text(fb):
    if not PDF_SUPPORT: return "[pdfplumber not installed]"
    try:
        with pdfplumber.open(io.BytesIO(fb)) as pdf:
            text = "\n\n".join(p.extract_text() or "" for p in pdf.pages).strip()
        return text[:8000]+("\n[truncated]" if len(text)>8000 else "")
    except Exception as e: return f"[PDF error: {e}]"

def fetch_url_text(url):
    try:
        r=requests.get(url,headers={"User-Agent":"Mozilla/5.0"},timeout=15); r.raise_for_status()
        if BS4_SUPPORT:
            soup=BeautifulSoup(r.text,"html.parser")
            for t in soup(["script","style","nav","footer","header"]): t.decompose()
            text=soup.get_text(separator="\n",strip=True)
        else: text=r.text
        return text[:6000]+("\n[truncated]" if len(text)>6000 else "")
    except Exception as e: return f"[URL error: {e}]"

def build_text_context(items):
    if not items: return ""
    return "[ADDITIONAL CONTEXT]\n"+"".join(f"\n--- {i['label']} ---\n{i['content']}" for i in items)+"\n[END CONTEXT]\n\n"

def call_claude(system, message, image_data=None):
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    if image_data:
        content=[{"type":"image","source":{"type":"base64","media_type":img["media_type"],"data":img["data"]}} for img in image_data]
        content.append({"type":"text","text":message})
    else: content=message
    resp=client.messages.create(model="claude-opus-4-5-20251101",max_tokens=1000,system=system,messages=[{"role":"user","content":content}])
    return resp.content[0].text

def call_gemini(system, message, image_data=None):
    if not GEMINI_KEY: raise ValueError("No Gemini key")
    parts=([{"inline_data":{"mime_type":img["media_type"],"data":img["data"]}} for img in image_data] if image_data else [])
    parts.append({"text":message})
    r=requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}",
        json={"system_instruction":{"parts":[{"text":system}]},"contents":[{"parts":parts}]},timeout=60)
    r.raise_for_status(); return r.json()["candidates"][0]["content"]["parts"][0]["text"]

def call_openai_compat(api_key, base_url, model, system, message, image_data=None):
    if image_data:
        content=[{"type":"image_url","image_url":{"url":f"data:{img['media_type']};base64,{img['data']}"}} for img in image_data]
        content.append({"type":"text","text":message})
    else: content=message
    r=requests.post(f"{base_url}/chat/completions",
        json={"model":model,"messages":[{"role":"system","content":system},{"role":"user","content":content}],"max_tokens":1000},
        headers={"Authorization":f"Bearer {api_key}","Content-Type":"application/json"},timeout=60)
    r.raise_for_status(); return r.json()["choices"][0]["message"]["content"]

def call_perplexity(system, message, image_data=None):
    if not PERPLEXITY_KEY: raise ValueError("No Perplexity key")
    r=requests.post("https://api.perplexity.ai/chat/completions",
        json={"model":"llama-3.1-sonar-small-128k-online","messages":[{"role":"system","content":system},{"role":"user","content":message}]},
        headers={"Authorization":f"Bearer {PERPLEXITY_KEY}","Content-Type":"application/json"},timeout=60)
    r.raise_for_status(); return r.json()["choices"][0]["message"]["content"]

def call_persona(persona, prompt_type, message, image_data=None):
    system=PERSONAS[persona][prompt_type]
    try:
        if   persona=="gemini":     return call_gemini(system,message,image_data)
        elif persona=="gpt4":
            if not OPENAI_KEY: raise ValueError()
            return call_openai_compat(OPENAI_KEY,"https://api.openai.com/v1","gpt-4o",system,message,image_data)
        elif persona=="perplexity": return call_perplexity(system,message,image_data)
        elif persona=="deepseek":
            if not DEEPSEEK_KEY: raise ValueError()
            return call_openai_compat(DEEPSEEK_KEY,"https://api.deepseek.com/v1","deepseek-chat",system,message,None)
        else: return call_claude(system,message,image_data)
    except: return call_claude(system,message,image_data)

def run_parallel(tasks):
    results=[None]*len(tasks)
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
        fmap={ex.submit(call_persona,*t):i for i,t in enumerate(tasks)}
        for f in concurrent.futures.as_completed(fmap):
            idx=fmap[f]
            try: results[idx]=f.result()
            except Exception as e: results[idx]=f"Error:{e}"
    return results

def ai_card_html(persona, text, label=""):
    cfg=AI_CONFIG[persona]; c,bg,br=cfg["color"],cfg["bg"],cfg["border"]
    safe=text.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
    lbl=(f'<span style="margin-left:auto;font-size:9px;color:#3A4A5A;background:#111820;'
         f'padding:2px 6px;border-radius:3px">{label}</span>') if label else ""
    return (f'<div style="background:{bg};border:1px solid {br};border-radius:10px;padding:16px;min-height:160px;font-family:monospace">'
            f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:12px">'
            f'<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:{c};box-shadow:0 0 8px {c};flex-shrink:0"></span>'
            f'<span style="color:{c};font-weight:bold;font-size:12px;letter-spacing:0.08em">{cfg["name"].upper()}</span>'
            f'<span style="color:#3A4A5A;font-size:10px">{cfg["maker"]}</span>{lbl}</div>'
            f'<div style="color:#B0C4D8;font-size:12.5px;line-height:1.75;white-space:pre-wrap;word-break:break-word">{safe}</div></div>')

def phase_header(num, title, state):
    p={"waiting":("#0D1420","#1E2A3A","#2A3A4A"),"active":("rgba(123,167,255,0.15)","#7BA7FF","#7BA7FF"),"done":("rgba(61,255,192,0.15)","#3DFFC0","#3DFFC0")}
    bg,border,tc=p[state]; icon="✓" if state=="done" else str(num)
    st.markdown(f'<div style="display:flex;align-items:center;gap:12px;margin:20px 0 14px 0">'
                f'<span style="display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;'
                f'border-radius:50%;background:{bg};border:1.5px solid {border};font-size:12px;font-weight:bold;color:{tc}">{icon}</span>'
                f'<span style="font-size:11px;font-weight:bold;letter-spacing:0.1em;color:{tc};font-family:monospace">{title}</span></div>',
                unsafe_allow_html=True)

def divider():
    st.markdown('<hr style="border:none;border-top:1px solid #111E2E;margin:24px 0">',unsafe_allow_html=True)

def key_status_banner():
    checks=[("Claude",ANTHROPIC_KEY,True),("Gemini",GEMINI_KEY,False),("GPT-4",OPENAI_KEY,False),("Perplexity",PERPLEXITY_KEY,False),("DeepSeek",DEEPSEEK_KEY,False)]
    parts=[(f'<span style="color:#3DFFC0">✓ {n}</span>' if k else
            f'<span style="color:{"#FF6B6B" if r else "#3A5060"}">✗ {n} ({"REQUIRED" if r else "simulated"})</span>')
           for n,k,r in checks]
    st.markdown(f'<div style="font-size:11px;padding:10px 14px;background:#090E18;border-radius:6px;border-left:3px solid #1A3A5A;margin-bottom:18px;font-family:monospace">'
                f'API KEYS &nbsp;·&nbsp; {" &nbsp;·&nbsp; ".join(parts)}</div>',unsafe_allow_html=True)

def render_context_inputs(key_suffix="main"):
    """Reusable context input: file upload + URL. Returns (text_ctx, image_data, summary)."""
    c1,c2=st.columns([3,2])
    with c1:
        st.markdown('<div style="font-size:10px;color:#5A7A9A;margin-bottom:6px;font-family:monospace">📄 UPLOAD FILES (PDF / images)</div>',unsafe_allow_html=True)
        uploaded=st.file_uploader("up",type=["pdf","png","jpg","jpeg","webp","gif"],
                                   accept_multiple_files=True,label_visibility="collapsed",key=f"upload_{key_suffix}")
    with c2:
        st.markdown('<div style="font-size:10px;color:#5A7A9A;margin-bottom:6px;font-family:monospace">🔗 URL</div>',unsafe_allow_html=True)
        url_input=st.text_input("url",placeholder="https://...",label_visibility="collapsed",key=f"url_{key_suffix}")

    text_items,image_data,summary=[],[],[]
    if uploaded:
        for f in uploaded:
            fb=f.read()
            if f.type=="application/pdf":
                text_items.append({"label":f"PDF:{f.name}","content":extract_pdf_text(fb)}); summary.append(f"📄 {f.name}")
            elif f.type.startswith("image/"):
                b64=base64.b64encode(fb).decode()
                image_data.append({"media_type":f.type,"data":b64,"name":f.name})
                text_items.append({"label":f"Image:{f.name}","content":f"[Image '{f.name}' provided — analyze in context of the question]"})
                summary.append(f"🖼 {f.name}")
    if url_input and url_input.strip().startswith("http"):
        with st.spinner("Fetching URL..."):
            text_items.append({"label":f"URL:{url_input}","content":fetch_url_text(url_input.strip())})
        summary.append(f"🔗 {url_input[:35]}...")
    return build_text_context(text_items), image_data, ", ".join(summary)

def render_context_panel():
    with st.expander("📎  ADD CONTEXT — documents, images, links  (optional)",expanded=False):
        st.markdown('<div style="font-size:10px;color:#3A5060;margin-bottom:10px;font-family:monospace">Passed to all models. Images sent natively to Claude, Gemini, GPT-4. DeepSeek & Perplexity receive text description.</div>',unsafe_allow_html=True)
        text_ctx,image_data,ctx_summary=render_context_inputs("main")
    if ctx_summary:
        st.markdown(f'<div style="font-size:10px;color:#3DFFC0;padding:6px 12px;background:rgba(61,255,192,0.05);'
                    f'border:1px solid rgba(61,255,192,0.2);border-radius:6px;margin-top:6px;font-family:monospace">✓ Context: {ctx_summary}</div>',
                    unsafe_allow_html=True)
    return text_ctx,image_data,ctx_summary

def copy_button_html(text_to_copy):
    """Reliable copy button using hidden textarea + execCommand fallback."""
    safe = text_to_copy.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;").replace("'","&#39;")
    return f"""
    <div style="position:relative">
      <textarea id="nxcopy" readonly style="position:fixed;top:-9999px;left:-9999px;opacity:0;pointer-events:none">{safe}</textarea>
      <button id="nxbtn" onclick="
        var el=document.getElementById('nxcopy');
        el.style.position='fixed';el.style.top='0';el.style.left='0';
        el.select();el.setSelectionRange(0,999999);
        var ok=false;
        try{{navigator.clipboard.writeText(el.value).then(function(){{
          document.getElementById('nxbtn').innerText='✓ COPIED!';
          document.getElementById('nxbtn').style.color='#3DFFC0';
          document.getElementById('nxbtn').style.borderColor='#3DFFC0';
          setTimeout(function(){{document.getElementById('nxbtn').innerText='📋 COPY';
            document.getElementById('nxbtn').style.color='#7BA7FF';
            document.getElementById('nxbtn').style.borderColor='rgba(123,167,255,0.4)';}},2200);
        }})}}catch(e){{
          document.execCommand('copy');
          document.getElementById('nxbtn').innerText='✓ COPIED!';
          setTimeout(function(){{document.getElementById('nxbtn').innerText='📋 COPY';}},2200);
        }}
        el.style.position='fixed';el.style.top='-9999px';
      "
      style="width:100%;background:rgba(123,167,255,0.15);color:#7BA7FF;
             border:1px solid rgba(123,167,255,0.4);border-radius:6px;
             padding:9px 4px;font-family:monospace;font-size:11px;
             font-weight:bold;cursor:pointer;transition:all 0.2s;letter-spacing:0.08em">
        📋 COPY
      </button>
    </div>
    """

def render_share_panel(question, synthesis, followups):
    divider()
    st.markdown('<div style="font-size:11px;font-weight:bold;letter-spacing:0.1em;color:#FF8B4E;margin-bottom:12px;font-family:monospace">📤 SHARE</div>',unsafe_allow_html=True)
    fu_text="".join(f"\n\nFOLLOW-UP {i+1}: {fu['question']}\n{fu.get('synthesis','')}" for i,fu in enumerate(followups))
    full=(f"NEXUS AI — Multi-Model Discussion\n{'='*50}\n\n"
          f"QUESTION: {question}\n\n"
          f"SYNTHESIZED ANSWER (Claude+Gemini+GPT-4+Perplexity+DeepSeek):\n{synthesis}"
          f"{fu_text}\n\nGenerated by Nexus AI — 5-Model Discussion Engine")
    short=synthesis[:280]+("..." if len(synthesis)>280 else "")
    enc_tw=urllib.parse.quote(f"Q: {question}\n\n{short}\n\n#NexusAI #AI")
    enc_b=urllib.parse.quote(full); enc_s=urllib.parse.quote(f"Nexus AI: {question[:60]}")
    enc_wa=urllib.parse.quote(f"*Nexus AI*\n\n*Q: {question}*\n\n{short}")

    c1,c2,c3,c4,c5=st.columns(5)
    with c1:
        st.components.v1.html(copy_button_html(full), height=52)
    with c2:
        st.download_button("⬇ DOWNLOAD",data=full,file_name="nexus-discussion.md",mime="text/markdown",use_container_width=True)
    with c3:
        st.markdown(f'<a href="mailto:?subject={enc_s}&body={enc_b}" target="_blank">'
                    f'<button style="width:100%;background:rgba(123,167,255,0.15);color:#7BA7FF;border:1px solid rgba(123,167,255,0.4);'
                    f'border-radius:6px;padding:8px 4px;font-family:monospace;font-size:11px;font-weight:bold;cursor:pointer">📧 EMAIL</button></a>',
                    unsafe_allow_html=True)
    with c4:
        st.markdown(f'<a href="https://wa.me/?text={enc_wa}" target="_blank">'
                    f'<button style="width:100%;background:rgba(123,167,255,0.15);color:#7BA7FF;border:1px solid rgba(123,167,255,0.4);'
                    f'border-radius:6px;padding:8px 4px;font-family:monospace;font-size:11px;font-weight:bold;cursor:pointer">💬 WHATSAPP</button></a>',
                    unsafe_allow_html=True)
    with c5:
        st.markdown(f'<a href="https://twitter.com/intent/tweet?text={enc_tw}" target="_blank">'
                    f'<button style="width:100%;background:rgba(123,167,255,0.15);color:#7BA7FF;border:1px solid rgba(123,167,255,0.4);'
                    f'border-radius:6px;padding:8px 4px;font-family:monospace;font-size:11px;font-weight:bold;cursor:pointer">𝕏 TWITTER</button></a>',
                    unsafe_allow_html=True)

def render_history_sidebar():
    with st.sidebar:
        st.markdown('<div style="font-size:14px;font-weight:bold;letter-spacing:0.12em;color:#E0E8F5;margin-bottom:4px;font-family:monospace">⬡ NEXUS AI</div>'
                    '<div style="font-size:9px;color:#3A5A7A;letter-spacing:0.1em;margin-bottom:20px;font-family:monospace">DISCUSSION HISTORY</div>',
                    unsafe_allow_html=True)
        if st.button("＋  NEW DISCUSSION",use_container_width=True):
            for k in ["phase","question","r1","r2","synthesis","followups","context_summary","active_id"]: st.session_state.pop(k,None)
            st.rerun()
        st.markdown('<hr style="border:none;border-top:1px solid #111E2E;margin:14px 0">',unsafe_allow_html=True)
        filter_map={"Today":1,"Last 7 days":7,"Last 30 days":30,"All time":0}
        sel=st.selectbox("Range",list(filter_map.keys()),index=2,label_visibility="collapsed")
        history=filter_history(filter_map[sel])
        if not history:
            st.markdown('<div style="font-size:11px;color:#2A3A4A;padding:12px 0;font-family:monospace">No discussions yet.<br>Start one above!</div>',unsafe_allow_html=True)
            return
        groups=group_by_date(history)
        active_id=st.session_state.get("active_id","")
        for gname,items in groups.items():
            if not items: continue
            st.markdown(f'<div style="font-size:9px;color:#3A5060;letter-spacing:0.1em;margin:14px 0 6px 0;font-family:monospace">{gname.upper()}</div>',unsafe_allow_html=True)
            for disc in items:
                disc_id=disc.get("id",""); q=disc.get("question","Untitled")
                q_short=q[:45]+("..." if len(q)>45 else "")
                try: tstr=datetime.fromisoformat(disc.get("created_at","")).strftime("%H:%M")
                except: tstr=""
                fu_c=len(disc.get("followups",[])); is_active=disc_id==active_id
                bg="rgba(123,167,255,0.1)" if is_active else "transparent"
                bl="2px solid #7BA7FF" if is_active else "2px solid transparent"
                fu_badge=(f' <span style="color:#3A5060;font-size:9px">+{fu_c} follow-up{"s" if fu_c>1 else ""}</span>') if fu_c else ""
                ci,cd=st.columns([6,1])
                with ci:
                    st.markdown(f'<div style="background:{bg};border-left:{bl};padding:8px 10px;border-radius:6px;margin-bottom:4px;font-family:monospace">'
                                f'<div style="font-size:11px;color:{"#E0E8F5" if is_active else "#8090A8"};line-height:1.4">{q_short}</div>'
                                f'<div style="font-size:9px;color:#2A3A4A;margin-top:3px">{tstr}{fu_badge}</div></div>',
                                unsafe_allow_html=True)
                    if st.button("open",key=f"open_{disc_id}",label_visibility="collapsed"):
                        _load_discussion(disc); st.rerun()
                with cd:
                    if st.button("✕",key=f"del_{disc_id}",help="Delete"):
                        delete_discussion(disc_id)
                        if active_id==disc_id:
                            for k in ["phase","question","r1","r2","synthesis","followups","active_id"]: st.session_state.pop(k,None)
                        st.rerun()
        st.markdown('<hr style="border:none;border-top:1px solid #0D1820;margin:20px 0 10px 0">'
                    '<div style="font-size:9px;color:#1E2E3E;line-height:1.6;font-family:monospace">'
                    'History saved to nexus_history.json.<br>On Streamlit Cloud, use Supabase for persistent storage.</div>',
                    unsafe_allow_html=True)

def _load_discussion(disc):
    for k,v in [("active_id",disc.get("id","")),("phase",disc.get("phase",4)),("question",disc.get("question","")),
                ("r1",disc.get("r1",{})),("r2",disc.get("r2",{})),("synthesis",disc.get("synthesis","")),
                ("followups",disc.get("followups",[])),("context_summary",disc.get("context_summary",""))]:
        st.session_state[k]=v

def _current_discussion():
    return {"id":st.session_state.get("active_id",str(uuid.uuid4())),
            "created_at":st.session_state.get("created_at",datetime.utcnow().isoformat()),
            "question":st.session_state.get("question",""),"phase":st.session_state.get("phase",0),
            "r1":st.session_state.get("r1",{}),"r2":st.session_state.get("r2",{}),
            "synthesis":st.session_state.get("synthesis",""),"followups":st.session_state.get("followups",[]),
            "context_summary":st.session_state.get("context_summary","")}

def init_state():
    for k,v in {"phase":0,"question":"","r1":{},"r2":{},"synthesis":None,"followups":[],"context_summary":"","active_id":None,"created_at":None}.items():
        if k not in st.session_state: st.session_state[k]=v

def main():
    init_state()
    render_history_sidebar()
    key_status_banner()
    if not ANTHROPIC_KEY: st.error("ANTHROPIC_API_KEY required in .streamlit/secrets.toml"); st.stop()

    text_context,image_data,context_summary=render_context_panel()
    question=st.text_area("Question",placeholder="Ask anything, or describe what to discuss about your uploaded content...",height=100,label_visibility="collapsed")
    c1,c2=st.columns([1,5])
    with c1: start=st.button("▶  START DISCUSSION",use_container_width=True)
    with c2:
        note=f"Context: {context_summary} · " if context_summary else ""
        st.markdown(f'<div style="color:#2A3A4A;font-size:11px;padding-top:10px;font-family:monospace">{note}5 models in parallel · missing keys fall back to Claude</div>',unsafe_allow_html=True)
    divider()

    if st.session_state.phase==0 and not start:
        st.markdown('<div style="padding:20px;background:#090E18;border-radius:10px;border:1px solid #111E2E;font-family:monospace">'
                    '<div style="font-size:9px;letter-spacing:0.12em;color:#3A5060;margin-bottom:14px">PARTICIPATING MODELS</div>'
                    '<div style="display:flex;flex-wrap:wrap;gap:20px;margin-bottom:14px">'
                    '<span><b style="color:#FF8B4E">● Claude</b> <span style="color:#2A3A4A;font-size:10px">— nuance & honesty</span></span>'
                    '<span><b style="color:#7BA7FF">● Gemini</b> <span style="color:#2A3A4A;font-size:10px">— broad knowledge</span></span>'
                    '<span><b style="color:#A8E6A3">● GPT-4</b> <span style="color:#2A3A4A;font-size:10px">— logical structure</span></span>'
                    '<span><b style="color:#3DFFC0">● Perplexity</b> <span style="color:#2A3A4A;font-size:10px">— live research</span></span>'
                    '<span><b style="color:#C084FC">● DeepSeek</b> <span style="color:#2A3A4A;font-size:10px">— STEM depth</span></span>'
                    '</div><div style="border-top:1px solid #111E2E;padding-top:12px;font-size:10px;color:#2A3A4A">'
                    '← History in sidebar · Click any past discussion to resume it</div></div>',
                    unsafe_allow_html=True)
        return

    if start and question.strip():
        disc_id=str(uuid.uuid4())
        st.session_state.update({"phase":1,"question":question.strip(),"r1":{},"r2":{},"synthesis":None,
                                  "followups":[],"context_summary":context_summary,"active_id":disc_id,
                                  "created_at":datetime.utcnow().isoformat()})

    q=st.session_state.question
    if not q: return

    def with_ctx(msg): return text_context+msg if text_context else msg

    # ── ROUND 1 ──────────────────────────────────────────────────
    phase_header(1,"INITIAL RESPONSES — Each AI answers independently","done" if st.session_state.phase>1 else "active")
    if not st.session_state.r1:
        cols=st.columns(5)
        for i,p in enumerate(PERSONAS_ORDER): cols[i].markdown(ai_card_html(p,"⟳ Thinking...","ROUND 1"),unsafe_allow_html=True)
        with st.spinner("Round 1 — all 5 models answering..."):
            results=run_parallel([(p,"initial",with_ctx(q),image_data) for p in PERSONAS_ORDER])
        st.session_state.r1=dict(zip(PERSONAS_ORDER,results)); st.session_state.phase=2
        save_discussion(_current_discussion()); st.rerun()
    cols=st.columns(5)
    for i,p in enumerate(PERSONAS_ORDER): cols[i].markdown(ai_card_html(p,st.session_state.r1[p],"ROUND 1"),unsafe_allow_html=True)
    divider()

    # ── ROUND 2 ──────────────────────────────────────────────────
    phase_header(2,"OPEN DEBATE — Each AI critiques and builds on the others","done" if st.session_state.phase>2 else "active")
    def make_debate(me):
        others=[p for p in PERSONAS_ORDER if p!=me]
        return with_ctx(f'Original question: "{q}"\n\nMY INITIAL ANSWER:\n{st.session_state.r1[me]}\n\n'+
            "\n\n".join(f"{AI_CONFIG[o]['name'].upper()}'S ANSWER:\n{st.session_state.r1[o]}" for o in others)+
            "\n\nNow engage in genuine discussion. Agree, challenge, extend. What crucial perspectives are missing?")
    if not st.session_state.r2:
        cols=st.columns(5)
        for i,p in enumerate(PERSONAS_ORDER): cols[i].markdown(ai_card_html(p,"⟳ Reading others...","ROUND 2"),unsafe_allow_html=True)
        with st.spinner("Round 2 — all 5 models debating..."):
            results=run_parallel([(p,"debate",make_debate(p),None) for p in PERSONAS_ORDER])
        st.session_state.r2=dict(zip(PERSONAS_ORDER,results)); st.session_state.phase=3
        save_discussion(_current_discussion()); st.rerun()
    cols=st.columns(5)
    for i,p in enumerate(PERSONAS_ORDER): cols[i].markdown(ai_card_html(p,st.session_state.r2[p],"ROUND 2"),unsafe_allow_html=True)
    divider()

    # ── SYNTHESIS ────────────────────────────────────────────────
    phase_header(3,"FINAL SYNTHESIS — Best answer from all five voices","done" if st.session_state.phase>=4 else "active")
    if not st.session_state.synthesis:
        synth_prompt=(f'QUESTION: "{q}"\n\nROUND 1:\n'+
            "\n\n".join(f"[{AI_CONFIG[p]['name']}]\n{st.session_state.r1[p]}" for p in PERSONAS_ORDER)+
            "\n\nROUND 2:\n"+
            "\n\n".join(f"[{AI_CONFIG[p]['name']}]\n{st.session_state.r2[p]}" for p in PERSONAS_ORDER)+
            "\n\nProvide the single best comprehensive answer incorporating all five AIs strongest insights.")
        with st.spinner("Synthesizing final answer..."):
            try: st.session_state.synthesis=call_claude(SYNTH_SYSTEM,synth_prompt)
            except Exception as e: st.session_state.synthesis=f"Synthesis error: {e}"
        st.session_state.phase=4; save_discussion(_current_discussion()); st.rerun()

    safe=st.session_state.synthesis.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
    st.markdown(f'<div style="background:rgba(61,255,192,0.05);border:1px solid rgba(61,255,192,0.25);border-radius:10px;padding:24px;font-family:monospace">'
                f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:14px">'
                f'<div style="width:28px;height:28px;border-radius:50%;background:rgba(61,255,192,0.1);border:1.5px solid rgba(61,255,192,0.4);'
                f'display:flex;align-items:center;justify-content:center;color:#3DFFC0">✦</div>'
                f'<div><div style="font-size:12px;font-weight:bold;color:#3DFFC0">SYNTHESIZED ANSWER</div>'
                f'<div style="font-size:10px;color:#2A5A4A">Claude · Gemini · GPT-4 · Perplexity · DeepSeek</div></div></div>'
                f'<div style="color:#C0D8D0;font-size:13.5px;line-height:1.8;white-space:pre-wrap">{safe}</div></div>',
                unsafe_allow_html=True)

    # ── FOLLOW-UP ────────────────────────────────────────────────
    if st.session_state.phase>=4:
        divider()
        st.markdown('<div style="font-size:11px;font-weight:bold;color:#7BA7FF;margin-bottom:8px;font-family:monospace">💬 CONTINUE THE DISCUSSION</div>',unsafe_allow_html=True)

        for i,fu in enumerate(st.session_state.followups):
            label_preview=fu['question'][:55]+('...' if len(fu['question'])>55 else '')
            with st.expander(f"↩ Follow-up {i+1}: {label_preview}",expanded=(i==len(st.session_state.followups)-1)):
                cols=st.columns(5)
                for j,p in enumerate(PERSONAS_ORDER): cols[j].markdown(ai_card_html(p,fu["responses"].get(p,""),"FOLLOW-UP"),unsafe_allow_html=True)
                if fu.get("synthesis"):
                    sfu=fu["synthesis"].replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
                    st.markdown(f'<div style="background:rgba(123,167,255,0.05);border:1px solid rgba(123,167,255,0.2);'
                                f'border-radius:10px;padding:20px;margin-top:12px;font-family:monospace">'
                                f'<div style="font-size:11px;font-weight:bold;color:#7BA7FF;margin-bottom:10px">↩ UPDATED SYNTHESIS</div>'
                                f'<div style="color:#C0D0E8;font-size:13px;line-height:1.8;white-space:pre-wrap">{sfu}</div></div>',
                                unsafe_allow_html=True)

        # Follow-up input with attachments
        n=len(st.session_state.followups)
        fu_q=st.text_input("fu",placeholder="Ask a follow-up, counter the synthesis, challenge a point...",
                            label_visibility="collapsed",key=f"fu_{n}")

        with st.expander(f"📎  Add attachments to follow-up  (optional)",expanded=False):
            st.markdown('<div style="font-size:10px;color:#3A5060;margin-bottom:8px;font-family:monospace">Attach docs, images, or a URL to give the AIs more context for this follow-up.</div>',unsafe_allow_html=True)
            fu_text_ctx,fu_image_data,fu_ctx_summary=render_context_inputs(f"fu_{n}")
        if fu_ctx_summary:
            st.markdown(f'<div style="font-size:10px;color:#3DFFC0;padding:5px 10px;background:rgba(61,255,192,0.05);border:1px solid rgba(61,255,192,0.15);border-radius:5px;margin-bottom:8px;font-family:monospace">✓ Follow-up context: {fu_ctx_summary}</div>',unsafe_allow_html=True)

        send_fu=st.button("▶  SEND FOLLOW-UP",key=f"send_{n}")

        if send_fu and fu_q.strip():
            hctx=(f'ORIGINAL QUESTION: "{q}"\n\nSYNTHESIS:\n{st.session_state.synthesis}\n\n'+
                  ("PRIOR FOLLOW-UPS:\n"+"".join(f"Q{i+1}: {fu['question']}\nSynthesis: {fu.get('synthesis','')}\n\n" for i,fu in enumerate(st.session_state.followups)) if st.session_state.followups else "")+
                  f'NEW FOLLOW-UP: "{fu_q.strip()}"')
            # Prepend any follow-up context
            if fu_text_ctx: hctx=fu_text_ctx+hctx
            with st.spinner("All 5 models responding to follow-up..."):
                fu_results=run_parallel([(p,"followup",hctx,fu_image_data if fu_image_data else None) for p in PERSONAS_ORDER])
            fu_map=dict(zip(PERSONAS_ORDER,fu_results))
            fu_synth_prompt=(hctx+"\n\nFOLLOW-UP RESPONSES:\n"+
                "\n\n".join(f"[{AI_CONFIG[p]['name']}]\n{fu_map[p]}" for p in PERSONAS_ORDER)+
                "\n\nSynthesize the best updated answer.")
            with st.spinner("Synthesizing updated answer..."):
                try: fu_synth=call_claude(FOLLOWUP_SYNTH_SYSTEM,fu_synth_prompt)
                except Exception as e: fu_synth=f"Synthesis error: {e}"
            st.session_state.followups.append({"question":fu_q.strip(),"responses":fu_map,"synthesis":fu_synth,
                                               "context_summary":fu_ctx_summary})
            save_discussion(_current_discussion()); st.rerun()

        render_share_panel(q,st.session_state.synthesis,st.session_state.followups)
        st.markdown('<div style="margin-top:20px"></div>',unsafe_allow_html=True)
        if st.button("↺  NEW DISCUSSION"):
            for k in ["phase","question","r1","r2","synthesis","followups","context_summary","active_id","created_at"]: st.session_state.pop(k,None)
            st.rerun()

if __name__=="__main__":
    main()
