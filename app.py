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
from datetime import datetime, timedelta, timezone
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

# Enhanced visual design with better hierarchy, spacing, and polish
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

/* Base */
html,body,[class*="css"]{
    font-family:'Inter',system-ui,-apple-system,sans-serif!important;
    background:#0A0E18!important;
    color:#E1E8F0!important;
}
.stApp{background:#0A0E18!important;}
#MainMenu,footer,header{visibility:hidden;}
.block-container{padding-top:2rem;padding-bottom:5rem;max-width:1600px;}

/* Sidebar */
[data-testid="stSidebar"]{
    background:linear-gradient(180deg,#0D1117 0%,#0A0E14 100%)!important;
    border-right:1px solid #1A2332!important;
}
[data-testid="stSidebar"] .block-container{padding:1.5rem 1rem!important;}

/* Inputs */
.stTextArea textarea{
    background:#0F1419!important;
    border:1.5px solid #1E2A3E!important;
    color:#E1E8F0!important;
    font-size:15px!important;
    border-radius:12px!important;
    padding:16px!important;
    transition:border-color 0.2s ease!important;
}
.stTextArea textarea:focus{
    border-color:#5B8DEF!important;
    box-shadow:0 0 0 3px rgba(91,141,239,0.1)!important;
}
.stTextInput input{
    background:#0F1419!important;
    border:1.5px solid #1E2A3E!important;
    color:#E1E8F0!important;
    font-size:14px!important;
    border-radius:10px!important;
    padding:12px 14px!important;
}
.stTextInput input:focus{
    border-color:#5B8DEF!important;
    box-shadow:0 0 0 3px rgba(91,141,239,0.1)!important;
}

/* Buttons */
.stButton>button{
    background:linear-gradient(135deg,#5B8DEF 0%,#4A7DD9 100%)!important;
    color:#FFFFFF!important;
    border:none!important;
    border-radius:10px!important;
    font-family:'Inter',sans-serif!important;
    font-size:13px!important;
    font-weight:600!important;
    letter-spacing:0.02em!important;
    padding:12px 24px!important;
    transition:all 0.2s ease!important;
    box-shadow:0 2px 8px rgba(91,141,239,0.25)!important;
}
.stButton>button:hover{
    background:linear-gradient(135deg,#6A9BF4 0%,#5988E3 100%)!important;
    box-shadow:0 4px 12px rgba(91,141,239,0.35)!important;
    transform:translateY(-1px)!important;
}

/* File uploader */
[data-testid="stFileUploader"]{
    background:#0F1419!important;
    border:2px dashed #2A3A52!important;
    border-radius:12px!important;
    padding:20px!important;
}

/* Expander */
.streamlit-expanderHeader{
    background:#0F1419!important;
    border:1px solid #1E2A3E!important;
    border-radius:10px!important;
    color:#5B8DEF!important;
    font-size:13px!important;
    font-weight:600!important;
    padding:14px 18px!important;
}

/* Selectbox */
.stSelectbox>div>div{
    background:#0F1419!important;
    border:1px solid #1E2A3E!important;
    border-radius:8px!important;
}
</style>
""", unsafe_allow_html=True)

# ─── AI Config with enhanced visuals ──────────────────────────────
AI_CONFIG = {
    "claude":     {"name":"Claude",    "maker":"Anthropic",  "color":"#FF8B4E","icon":"🟠","bg":"linear-gradient(135deg,rgba(255,139,78,0.08) 0%,rgba(255,139,78,0.04) 100%)","border":"rgba(255,139,78,0.4)"},
    "gemini":     {"name":"Gemini",    "maker":"Google",     "color":"#5B8DEF","icon":"🔵","bg":"linear-gradient(135deg,rgba(91,141,239,0.08) 0%,rgba(91,141,239,0.04) 100%)","border":"rgba(91,141,239,0.4)"},
    "gpt4":       {"name":"GPT-4",     "maker":"OpenAI",     "color":"#10B981","icon":"🟢","bg":"linear-gradient(135deg,rgba(16,185,129,0.08) 0%,rgba(16,185,129,0.04) 100%)","border":"rgba(16,185,129,0.4)"},
    "perplexity": {"name":"Perplexity","maker":"Perplexity", "color":"#06B6D4","icon":"🔷","bg":"linear-gradient(135deg,rgba(6,182,212,0.08) 0%,rgba(6,182,212,0.04) 100%)","border":"rgba(6,182,212,0.4)"},
    "deepseek":   {"name":"DeepSeek",  "maker":"DeepSeek",   "color":"#A78BFA","icon":"🟣","bg":"linear-gradient(135deg,rgba(167,139,250,0.08) 0%,rgba(167,139,250,0.04) 100%)","border":"rgba(167,139,250,0.4)"},
}
PERSONAS_ORDER = ["claude","gemini","gpt4","perplexity","deepseek"]

PERSONAS = {
    "claude":     {"initial":"You are Claude by Anthropic. Careful reasoning, nuance, intellectual honesty. Thorough yet clear. 3-5 paragraphs.","debate":"You are Claude. Engage genuinely: agree where right, challenge where wrong, add missing angles. 2-4 paragraphs.","followup":"You are Claude in an ongoing multi-AI discussion. Respond thoughtfully, referencing prior discussion. 2-3 paragraphs."},
    "gemini":     {"initial":"You are Gemini by Google. Broad world knowledge, cross-domain connections, practical applications. 3-5 paragraphs.","debate":"You are Gemini. Build on strong points, challenge weak ones, bring cross-domain knowledge. 2-4 paragraphs.","followup":"You are Gemini in an ongoing discussion. Broad cross-domain perspective. 2-3 paragraphs."},
    "gpt4":       {"initial":"You are GPT-4 by OpenAI. Deep logical reasoning, structured analysis, precision. 3-5 paragraphs.","debate":"You are GPT-4. Identify logical gaps, validate sound arguments, bring structured clarity. 2-4 paragraphs.","followup":"You are GPT-4 in an ongoing discussion. Rigorous logical analysis. 2-3 paragraphs."},
    "perplexity": {"initial":"You are Perplexity AI. Direct, fact-focused, research-oriented. Lead with data, verifiable facts, concrete examples. 3-5 paragraphs.","debate":"You are Perplexity. Push back on vagueness, add concrete facts and research. 2-4 paragraphs.","followup":"You are Perplexity in an ongoing discussion. Ground in concrete facts and research. 2-3 paragraphs."},
    "deepseek":   {"initial":"You are DeepSeek. Exceptional STEM, math, coding, scientific reasoning. Rigorous and precise. 3-5 paragraphs.","debate":"You are DeepSeek. Apply mathematical and logical rigour to validate or challenge others arguments. 2-4 paragraphs.","followup":"You are DeepSeek in an ongoing discussion. Analytical precision and STEM-grounded reasoning. 2-3 paragraphs."},
}

SYNTH_SYSTEM = "You are a neutral expert moderator synthesizing a multi-AI discussion between Claude, Gemini, GPT-4, Perplexity, and DeepSeek. Produce the single best comprehensive answer incorporating strongest insights, resolving disagreements. Be definitive and clear."
FOLLOWUP_SYNTH_SYSTEM = "You are a neutral expert moderator. Synthesize the five AIs follow-up responses into the best updated answer, incorporating new insights that refine the previous synthesis."
FACTCHECK_SYSTEM = "You are Perplexity AI, a rigorous fact-checker with real-time web access. Your job: verify the synthesized answer below with healthy skepticism. Check each major claim against current sources. Flag potential hallucinations, outdated info, or unsupported assertions. Cite sources where you verify or contradict claims. If everything checks out, say so. Be constructively critical."

def get_secret(key):
    try: return st.secrets[key]
    except: return None

ANTHROPIC_KEY  = get_secret("ANTHROPIC_API_KEY")
GEMINI_KEY     = get_secret("GEMINI_API_KEY")
OPENAI_KEY     = get_secret("OPENAI_API_KEY")
PERPLEXITY_KEY = get_secret("PERPLEXITY_API_KEY")
DEEPSEEK_KEY   = get_secret("DEEPSEEK_API_KEY")
SUPABASE_URL   = get_secret("SUPABASE_URL")
SUPABASE_KEY   = get_secret("SUPABASE_KEY")

HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nexus_history.json")
STORAGE_MODE = "supabase" if (SUPABASE_URL and SUPABASE_KEY) else "local"

def _supa_headers():
    return {"apikey":SUPABASE_KEY,"Authorization":f"Bearer {SUPABASE_KEY}","Content-Type":"application/json","Prefer":"resolution=merge-duplicates"}

def _supa_url(path=""):
    return f"{SUPABASE_URL.rstrip('/')}/rest/v1/nexus_discussions{path}"

def _sb_load_history():
    try:
        r=requests.get(_supa_url(),headers={**_supa_headers(),"Prefer":""},params={"select":"*","order":"created_at.desc"},timeout=10)
        r.raise_for_status(); rows=r.json()
        for row in rows:
            for col in ("r1","r2","followups"):
                if isinstance(row.get(col),str):
                    try: row[col]=json.loads(row[col])
                    except: pass
        return rows
    except Exception as e: st.warning(f"Supabase read error: {e}"); return []

def _sb_save_discussion(disc):
    payload={"id":disc["id"],"created_at":disc.get("created_at",datetime.now(timezone.utc).replace(tzinfo=None).isoformat()),
             "question":disc.get("question",""),"phase":disc.get("phase",0),"r1":disc.get("r1",{}),"r2":disc.get("r2",{}),
             "synthesis":disc.get("synthesis","") or "","factcheck":disc.get("factcheck","") or "",
             "followups":disc.get("followups",[]),"context_summary":disc.get("context_summary","")}
    try: r=requests.post(_supa_url(),headers={**_supa_headers(),"Prefer":"resolution=merge-duplicates"},json=payload,timeout=10); r.raise_for_status()
    except Exception as e: st.warning(f"Supabase save error: {e}")

def _sb_delete_discussion(disc_id):
    try: r=requests.delete(_supa_url(),headers={**_supa_headers(),"Prefer":""},params={"id":f"eq.{disc_id}"},timeout=10); r.raise_for_status()
    except Exception as e: st.warning(f"Supabase delete error: {e}")

def _local_load_history():
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE,"r",encoding="utf-8") as f: return json.load(f)
    except: pass
    return []

def _local_save_history(history):
    try:
        with open(HISTORY_FILE,"w",encoding="utf-8") as f: json.dump(history,f,ensure_ascii=False,indent=2)
    except Exception as e: st.warning(f"Local save error: {e}")

def _local_save_discussion(disc):
    history=_local_load_history()
    for i,d in enumerate(history):
        if d.get("id")==disc["id"]: history[i]=disc; _local_save_history(history); return
    history.append(disc); _local_save_history(history)

def _local_delete_discussion(disc_id):
    _local_save_history([d for d in _local_load_history() if d.get("id")!=disc_id])

def load_history():
    if STORAGE_MODE=="supabase": return _sb_load_history()
    return _local_load_history()

def save_discussion(disc):
    if STORAGE_MODE=="supabase": _sb_save_discussion(disc)
    else: _local_save_discussion(disc)

def delete_discussion(disc_id):
    if STORAGE_MODE=="supabase": _sb_delete_discussion(disc_id)
    else: _local_delete_discussion(disc_id)

def _parse_dt(s):
    if not s: return datetime(2000,1,1)
    try:
        s=s.replace("Z","+00:00"); dt=datetime.fromisoformat(s)
        if dt.tzinfo is not None: dt=dt.utctimetuple(); dt=datetime(*dt[:6])
        return dt
    except: return datetime(2000,1,1)

def filter_history(days):
    history=load_history()
    if days>0:
        cutoff=datetime.now(timezone.utc).replace(tzinfo=None)-timedelta(days=days)
        history=[d for d in history if _parse_dt(d.get("created_at",""))>=cutoff]
    return sorted(history,key=lambda d:d.get("created_at",""),reverse=True)

def group_by_date(discs):
    now=datetime.now(timezone.utc).replace(tzinfo=None).date(); groups={"Today":[],"Yesterday":[],"This Week":[],"Older":[]}
    for d in discs:
        try: ts=_parse_dt(d.get("created_at","")).date()
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
        with pdfplumber.open(io.BytesIO(fb)) as pdf: text="\n\n".join(p.extract_text() or "" for p in pdf.pages).strip()
        return text[:8000]+("\n[truncated]" if len(text)>8000 else "")
    except Exception as e: return f"[PDF error: {e}]"

def fetch_url_text(url):
    try:
        r=requests.get(url,headers={"User-Agent":"Mozilla/5.0"},timeout=15); r.raise_for_status()
        if BS4_SUPPORT: soup=BeautifulSoup(r.text,"html.parser"); [t.decompose() for t in soup(["script","style","nav","footer","header"])]; text=soup.get_text(separator="\n",strip=True)
        else: text=r.text
        return text[:6000]+("\n[truncated]" if len(text)>6000 else "")
    except Exception as e: return f"[URL error: {e}]"

def build_text_context(items):
    if not items: return ""
    return "[ADDITIONAL CONTEXT]\n"+"".join(f"\n--- {i['label']} ---\n{i['content']}" for i in items)+"\n[END CONTEXT]\n\n"

def call_claude(system,message,image_data=None):
    client=anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    if image_data: content=[{"type":"image","source":{"type":"base64","media_type":img["media_type"],"data":img["data"]}} for img in image_data]; content.append({"type":"text","text":message})
    else: content=message
    resp=client.messages.create(model="claude-opus-4-5-20251101",max_tokens=1000,system=system,messages=[{"role":"user","content":content}])
    return resp.content[0].text

def call_gemini(system,message,image_data=None):
    if not GEMINI_KEY: raise ValueError()
    parts=([{"inline_data":{"mime_type":img["media_type"],"data":img["data"]}} for img in image_data] if image_data else []); parts.append({"text":message})
    r=requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}",json={"system_instruction":{"parts":[{"text":system}]},"contents":[{"parts":parts}]},timeout=60)
    r.raise_for_status(); return r.json()["candidates"][0]["content"]["parts"][0]["text"]

def call_openai_compat(api_key,base_url,model,system,message,image_data=None):
    if image_data: content=[{"type":"image_url","image_url":{"url":f"data:{img['media_type']};base64,{img['data']}"}} for img in image_data]; content.append({"type":"text","text":message})
    else: content=message
    r=requests.post(f"{base_url}/chat/completions",json={"model":model,"messages":[{"role":"system","content":system},{"role":"user","content":content}],"max_tokens":1000},
                    headers={"Authorization":f"Bearer {api_key}","Content-Type":"application/json"},timeout=60)
    r.raise_for_status(); return r.json()["choices"][0]["message"]["content"]

def call_perplexity(system,message,image_data=None):
    if not PERPLEXITY_KEY: raise ValueError()
    r=requests.post("https://api.perplexity.ai/chat/completions",json={"model":"llama-3.1-sonar-small-128k-online","messages":[{"role":"system","content":system},{"role":"user","content":message}]},
                    headers={"Authorization":f"Bearer {PERPLEXITY_KEY}","Content-Type":"application/json"},timeout=60)
    r.raise_for_status(); return r.json()["choices"][0]["message"]["content"]

def call_persona(persona,prompt_type,message,image_data=None):
    system=PERSONAS[persona][prompt_type]
    try:
        if persona=="gemini": return call_gemini(system,message,image_data)
        elif persona=="gpt4": return call_openai_compat(OPENAI_KEY,"https://api.openai.com/v1","gpt-4o",system,message,image_data) if OPENAI_KEY else call_claude(system,message,image_data)
        elif persona=="perplexity": return call_perplexity(system,message,image_data)
        elif persona=="deepseek": return call_openai_compat(DEEPSEEK_KEY,"https://api.deepseek.com/v1","deepseek-chat",system,message,None) if DEEPSEEK_KEY else call_claude(system,message,image_data)
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

# Enhanced AI card with better visual hierarchy
def ai_card_html(persona,text,label=""):
    cfg=AI_CONFIG[persona]; safe=text.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
    lbl=f'<div style="position:absolute;top:16px;right:16px;font-size:9px;color:#5A6A7A;background:rgba(15,20,25,0.8);padding:4px 10px;border-radius:6px;font-weight:600;letter-spacing:0.05em">{label}</div>' if label else ""
    return (f'<div style="position:relative;background:{cfg["bg"]};border:1.5px solid {cfg["border"]};border-radius:16px;padding:24px;min-height:180px;'
            f'box-shadow:0 2px 8px rgba(0,0,0,0.15);transition:all 0.2s ease">'
            f'{lbl}'
            f'<div style="display:flex;align-items:center;gap:12px;margin-bottom:16px">'
            f'<div style="font-size:24px">{cfg["icon"]}</div>'
            f'<div style="flex:1"><div style="color:{cfg["color"]};font-weight:700;font-size:14px;letter-spacing:0.02em">{cfg["name"]}</div>'
            f'<div style="color:#5A6A7A;font-size:11px;font-weight:500;margin-top:2px">{cfg["maker"]}</div></div></div>'
            f'<div style="color:#C5D1DE;font-size:13px;line-height:1.8;white-space:pre-wrap;word-break:break-word">{safe}</div></div>')

def phase_header(num,title,state):
    icons={"waiting":"○","active":"◉","done":"✓"}
    colors={"waiting":"#2A3A4A","active":"#5B8DEF","done":"#10B981"}
    st.markdown(f'<div style="display:flex;align-items:center;gap:16px;margin:32px 0 20px 0">'
                f'<div style="display:flex;align-items:center;justify-content:center;width:36px;height:36px;border-radius:50%;'
                f'background:{"linear-gradient(135deg,rgba(91,141,239,0.15),rgba(91,141,239,0.05))" if state=="active" else "rgba(42,58,74,0.3)"};'
                f'border:2px solid {colors[state]};font-size:16px;font-weight:700;color:{colors[state]}">{icons[state]}</div>'
                f'<div style="flex:1;font-size:15px;font-weight:700;color:{colors[state]};letter-spacing:0.02em">{title}</div>'
                f'<div style="flex:1;height:2px;background:linear-gradient(90deg,{colors[state]} 0%,transparent 100%)"></div></div>',unsafe_allow_html=True)

def divider():
    st.markdown('<div style="height:2px;background:linear-gradient(90deg,transparent 0%,#1E2A3E 50%,transparent 100%);margin:40px 0"></div>',unsafe_allow_html=True)

def key_status_banner():
    checks=[("Claude",ANTHROPIC_KEY,True),("Gemini",GEMINI_KEY,False),("GPT-4",OPENAI_KEY,False),("Perplexity",PERPLEXITY_KEY,False),("DeepSeek",DEEPSEEK_KEY,False)]
    parts=[(f'<span style="color:#10B981;font-weight:600">✓ {n}</span>' if k else f'<span style="color:{"#EF4444" if r else "#4A5A6A"}">✗ {n}</span>') for n,k,r in checks]
    db=f'<span style="color:#10B981;font-weight:600">✓ Supabase</span>' if STORAGE_MODE=="supabase" else '<span style="color:#A78BFA;font-weight:600">◎ Local</span>'
    st.markdown(f'<div style="background:linear-gradient(135deg,#0F1419 0%,#0D1117 100%);border-radius:12px;border:1px solid #1E2A3E;'
                f'padding:16px 20px;margin-bottom:24px;display:flex;align-items:center;gap:24px;flex-wrap:wrap">'
                f'<div style="font-size:11px;font-weight:700;color:#5A6A7A;letter-spacing:0.08em">MODELS</div>'
                f'{"".join(f"<div style=\"font-size:12px\">{p}</div>" for p in parts)}'
                f'<div style="margin-left:auto;font-size:11px;font-weight:700;color:#5A6A7A;letter-spacing:0.08em">STORAGE</div>'
                f'<div style="font-size:12px">{db}</div></div>',unsafe_allow_html=True)

def render_context_inputs(key_suffix="main"):
    c1,c2=st.columns([3,2])
    with c1:
        st.markdown('<div style="font-size:12px;color:#7A8A9A;margin-bottom:8px;font-weight:600">📄 Files</div>',unsafe_allow_html=True)
        uploaded=st.file_uploader("up",type=["pdf","png","jpg","jpeg","webp","gif"],accept_multiple_files=True,label_visibility="collapsed",key=f"upload_{key_suffix}")
    with c2:
        st.markdown('<div style="font-size:12px;color:#7A8A9A;margin-bottom:8px;font-weight:600">🔗 URL</div>',unsafe_allow_html=True)
        url_input=st.text_input("url",placeholder="https://...",label_visibility="collapsed",key=f"url_{key_suffix}")
    text_items,image_data,summary=[],[],[]
    if uploaded:
        for f in uploaded:
            fb=f.read()
            if f.type=="application/pdf": text_items.append({"label":f"PDF:{f.name}","content":extract_pdf_text(fb)}); summary.append(f"📄 {f.name}")
            elif f.type.startswith("image/"): b64=base64.b64encode(fb).decode(); image_data.append({"media_type":f.type,"data":b64,"name":f.name}); text_items.append({"label":f"Image:{f.name}","content":f"[Image '{f.name}' provided]"}); summary.append(f"🖼 {f.name}")
    if url_input and url_input.strip().startswith("http"):
        with st.spinner("Fetching..."): text_items.append({"label":f"URL:{url_input}","content":fetch_url_text(url_input.strip())})
        summary.append(f"🔗 {url_input[:30]}...")
    return build_text_context(text_items),image_data,", ".join(summary)

def render_context_panel():
    with st.expander("📎  Context — attach files, images, or URLs",expanded=False):
        st.markdown('<div style="font-size:12px;color:#5A6A7A;margin-bottom:12px">Passed to all models. Images sent natively to Claude, Gemini, GPT-4.</div>',unsafe_allow_html=True)
        text_ctx,image_data,ctx_summary=render_context_inputs("main")
    if ctx_summary:
        st.markdown(f'<div style="font-size:12px;color:#10B981;background:rgba(16,185,129,0.08);border:1px solid rgba(16,185,129,0.3);'
                    f'border-radius:10px;padding:12px 16px;margin-top:12px;font-weight:600">✓ {ctx_summary}</div>',unsafe_allow_html=True)
    return text_ctx,image_data,ctx_summary

def copy_button_html(text):
    safe=text.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;").replace("'","&#39;")
    return f'<textarea id="nxc" readonly style="position:fixed;top:-9999px;opacity:0">{safe}</textarea><button id="nxb" onclick="var e=document.getElementById(\'nxc\');e.style.position=\'fixed\';e.style.top=\'0\';e.select();try{{navigator.clipboard.writeText(e.value).then(()=>{{document.getElementById(\'nxb\').innerText=\'✓ COPIED!\';document.getElementById(\'nxb\').style.background=\'linear-gradient(135deg,#10B981,#059669)\';setTimeout(()=>{{document.getElementById(\'nxb\').innerText=\'📋 COPY\';document.getElementById(\'nxb\').style.background=\'linear-gradient(135deg,#5B8DEF,#4A7DD9)\';}},2000);}})}}catch(x){{document.execCommand(\'copy\');document.getElementById(\'nxb\').innerText=\'✓ COPIED!\';}}e.style.top=\'-9999px\';" style="width:100%;background:linear-gradient(135deg,#5B8DEF,#4A7DD9);color:#FFF;border:none;border-radius:10px;padding:12px;font-size:13px;font-weight:600;cursor:pointer;transition:all 0.2s;box-shadow:0 2px 8px rgba(91,141,239,0.25)">📋 COPY</button>'

def render_share_panel(q,synth,followups):
    divider()
    st.markdown('<div style="font-size:13px;font-weight:700;color:#5B8DEF;margin-bottom:16px;letter-spacing:0.02em">📤 Share Discussion</div>',unsafe_allow_html=True)
    fu_text="".join(f"\n\nFOLLOW-UP {i+1}: {fu['question']}\n{fu.get('synthesis','')}" for i,fu in enumerate(followups))
    full=f"NEXUS AI — Multi-Model Discussion\n{'='*50}\n\nQUESTION: {q}\n\nSYNTHESIS:\n{synth}{fu_text}\n\nGenerated by Nexus AI"
    short=synth[:280]+("..." if len(synth)>280 else "")
    c1,c2,c3,c4,c5=st.columns(5)
    with c1: st.components.v1.html(copy_button_html(full),height=52)
    with c2: st.download_button("⬇ DOWNLOAD",data=full,file_name="nexus.md",mime="text/markdown",use_container_width=True)
    with c3: st.markdown(f'<a href="mailto:?subject={urllib.parse.quote(q[:50])}&body={urllib.parse.quote(full)}" target="_blank" style="display:block;background:linear-gradient(135deg,#5B8DEF,#4A7DD9);color:#FFF;text-align:center;padding:12px;border-radius:10px;text-decoration:none;font-weight:600;font-size:13px;box-shadow:0 2px 8px rgba(91,141,239,0.25)">📧 EMAIL</a>',unsafe_allow_html=True)
    with c4: st.markdown(f'<a href="https://wa.me/?text={urllib.parse.quote(f"*Nexus AI*\n\n{q}\n\n{short}")}" target="_blank" style="display:block;background:linear-gradient(135deg,#10B981,#059669);color:#FFF;text-align:center;padding:12px;border-radius:10px;text-decoration:none;font-weight:600;font-size:13px;box-shadow:0 2px 8px rgba(16,185,129,0.25)">💬 WHATSAPP</a>',unsafe_allow_html=True)
    with c5: st.markdown(f'<a href="https://twitter.com/intent/tweet?text={urllib.parse.quote(f"Q: {q}\n\n{short}\n\n#NexusAI")}" target="_blank" style="display:block;background:linear-gradient(135deg,#3B82F6,#2563EB);color:#FFF;text-align:center;padding:12px;border-radius:10px;text-decoration:none;font-weight:600;font-size:13px;box-shadow:0 2px 8px rgba(59,130,246,0.25)">𝕏 TWITTER</a>',unsafe_allow_html=True)

def render_history_sidebar():
    with st.sidebar:
        # DACTA logo and branding header
        # Logo should be in same directory as app.py
        logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dacta.png")
        
        if os.path.exists(logo_path):
            col1, col2 = st.columns([0.8, 3.2])
            with col1:
                with open(logo_path, "rb") as f:
                    st.image(f.read(), width=70)
            with col2:
                st.markdown('''
                    <div style="margin-top:-8px">
                        <div style="font-size:16px;font-weight:700;color:#E1E8F0;letter-spacing:0.02em">Nexus AI</div>
                        <div style="font-size:9px;color:#5A6A7A;letter-spacing:0.05em;font-weight:600;margin-top:2px">MULTI-MODEL DISCUSSIONS</div>
                    </div>
                ''', unsafe_allow_html=True)
        else:
            # Fallback without logo
            st.markdown('''
                <div style="margin-bottom:20px">
                    <div style="font-size:16px;font-weight:700;color:#E1E8F0;letter-spacing:0.02em">DACTA Nexus AI</div>
                    <div style="font-size:9px;color:#5A6A7A;letter-spacing:0.05em;font-weight:600;margin-top:2px">MULTI-MODEL DISCUSSIONS</div>
                </div>
            ''', unsafe_allow_html=True)
        if st.button("＋  NEW DISCUSSION",use_container_width=True):
            for k in ["phase","question","r1","r2","synthesis","factcheck","followups","context_summary","active_id"]: st.session_state.pop(k,None)
            st.rerun()
        st.markdown('<div style="height:1px;background:#1E2A3E;margin:20px 0"></div>',unsafe_allow_html=True)
        filter_map={"Today":1,"Last 7 days":7,"Last 30 days":30,"All time":0}
        sel=st.selectbox("Range",list(filter_map.keys()),index=2,label_visibility="collapsed")
        history=filter_history(filter_map[sel])
        if not history:
            st.markdown('<div style="font-size:12px;color:#4A5A6A;padding:16px 0">No discussions yet.<br>Start one above!</div>',unsafe_allow_html=True); return
        groups=group_by_date(history); active_id=st.session_state.get("active_id","")
        for gname,items in groups.items():
            if not items: continue
            st.markdown(f'<div style="font-size:10px;color:#4A5A6A;letter-spacing:0.08em;font-weight:700;margin:20px 0 10px 0">{gname.upper()}</div>',unsafe_allow_html=True)
            for disc in items:
                disc_id=disc.get("id",""); q=disc.get("question","Untitled")[:40]+("..." if len(disc.get("question",""))>40 else "")
                try: tstr=_parse_dt(disc.get("created_at","")).strftime("%H:%M")
                except: tstr=""
                fu_c=len(disc.get("followups",[])); is_active=disc_id==active_id
                bg="linear-gradient(135deg,rgba(91,141,239,0.12),rgba(91,141,239,0.06))" if is_active else "#0F1419"
                bl="2px solid #5B8DEF" if is_active else "2px solid transparent"
                fu_badge=f' <span style="color:#4A5A6A;font-size:10px">+{fu_c}</span>' if fu_c else ""
                ci,cd=st.columns([5,1])
                with ci:
                    st.markdown(f'<div style="background:{bg};border-left:{bl};padding:12px 14px;border-radius:10px;margin-bottom:6px;cursor:pointer;transition:all 0.2s">'
                                f'<div style="font-size:12px;color:{"#E1E8F0" if is_active else "#8A9AAA"};font-weight:600;line-height:1.5">{q}</div>'
                                f'<div style="font-size:10px;color:#4A5A6A;margin-top:4px">{tstr}{fu_badge}</div></div>',unsafe_allow_html=True)
                    if st.button("▶",key=f"open_{disc_id}",help="Resume"): _load_discussion(disc); st.rerun()
                with cd:
                    if st.button("✕",key=f"del_{disc_id}",help="Delete"):
                        delete_discussion(disc_id)
                        if active_id==disc_id:
                            for k in ["phase","question","r1","r2","synthesis","factcheck","followups","active_id"]: st.session_state.pop(k,None)
                        st.rerun()
        mode_col="#10B981" if STORAGE_MODE=="supabase" else "#A78BFA"
        mode_txt="☁ Supabase (cloud)" if STORAGE_MODE=="supabase" else "💾 Local JSON"
        st.markdown(f'<div style="margin-top:24px;padding-top:16px;border-top:1px solid #1E2A3E"><div style="font-size:11px;color:{mode_col};font-weight:600">{mode_txt}</div></div>',unsafe_allow_html=True)

def _load_discussion(disc):
    for k,v in [("active_id",disc.get("id","")),("phase",disc.get("phase",4)),("question",disc.get("question","")),
                ("r1",disc.get("r1",{})),("r2",disc.get("r2",{})),("synthesis",disc.get("synthesis","")),("factcheck",disc.get("factcheck","")),
                ("followups",disc.get("followups",[])),("context_summary",disc.get("context_summary",""))]:
        st.session_state[k]=v

def _current_discussion():
    return {"id":st.session_state.get("active_id",str(uuid.uuid4())),"created_at":st.session_state.get("created_at",datetime.now(timezone.utc).replace(tzinfo=None).isoformat()),
            "question":st.session_state.get("question",""),"phase":st.session_state.get("phase",0),"r1":st.session_state.get("r1",{}),"r2":st.session_state.get("r2",{}),
            "synthesis":st.session_state.get("synthesis",""),"factcheck":st.session_state.get("factcheck",""),"followups":st.session_state.get("followups",[]),
            "context_summary":st.session_state.get("context_summary","")}

def init_state():
    for k,v in {"phase":0,"question":"","r1":{},"r2":{},"synthesis":None,"factcheck":None,"followups":[],"context_summary":"","active_id":None,"created_at":None}.items():
        if k not in st.session_state: st.session_state[k]=v

def main():
    init_state(); render_history_sidebar(); key_status_banner()
    if not ANTHROPIC_KEY: st.error("ANTHROPIC_API_KEY required"); st.stop()

    text_context,image_data,context_summary=render_context_panel()
    question=st.text_area("Question",placeholder="Ask anything — multiple AIs will discuss and synthesize the answer...",height=100,label_visibility="collapsed")
    c1,c2=st.columns([1,4])
    with c1: start=st.button("▶  START DISCUSSION",use_container_width=True)
    with c2:
        note=f"Context: {context_summary} · " if context_summary else ""
        st.markdown(f'<div style="color:#5A6A7A;font-size:12px;padding-top:12px">{note}5 models · parallel reasoning · adversarial fact-check</div>',unsafe_allow_html=True)
    divider()

    if st.session_state.phase==0 and not start:
        st.markdown('<div style="background:linear-gradient(135deg,#0F1419,#0D1117);border-radius:16px;border:1px solid #1E2A3E;padding:32px;text-align:center">'
                    '<div style="font-size:11px;color:#4A5A6A;letter-spacing:0.08em;font-weight:700;margin-bottom:20px">PARTICIPATING MODELS</div>'
                    '<div style="display:flex;justify-content:center;gap:32px;flex-wrap:wrap;margin-bottom:24px">'
                    '<div><div style="font-size:28px">🟠</div><div style="font-size:13px;color:#FF8B4E;font-weight:700;margin-top:8px">Claude</div></div>'
                    '<div><div style="font-size:28px">🔵</div><div style="font-size:13px;color:#5B8DEF;font-weight:700;margin-top:8px">Gemini</div></div>'
                    '<div><div style="font-size:28px">🟢</div><div style="font-size:13px;color:#10B981;font-weight:700;margin-top:8px">GPT-4</div></div>'
                    '<div><div style="font-size:28px">🔷</div><div style="font-size:13px;color:#06B6D4;font-weight:700;margin-top:8px">Perplexity</div></div>'
                    '<div><div style="font-size:28px">🟣</div><div style="font-size:13px;color:#A78BFA;font-weight:700;margin-top:8px">DeepSeek</div></div>'
                    '</div><div style="border-top:1px solid #1E2A3E;padding-top:20px;font-size:12px;color:#5A6A7A">← History in sidebar · Click any discussion to resume</div></div>',unsafe_allow_html=True)
        return

    if start and question.strip():
        disc_id=str(uuid.uuid4())
        st.session_state.update({"phase":1,"question":question.strip(),"r1":{},"r2":{},"synthesis":None,"factcheck":None,
                                  "followups":[],"context_summary":context_summary,"active_id":disc_id,"created_at":datetime.now(timezone.utc).replace(tzinfo=None).isoformat()})

    q=st.session_state.question
    if not q: return
    def with_ctx(msg): return text_context+msg if text_context else msg

    # Round 1
    phase_header(1,"Initial Responses — Each AI answers independently","done" if st.session_state.phase>1 else "active")
    if not st.session_state.r1:
        cols=st.columns(5)
        for i,p in enumerate(PERSONAS_ORDER): cols[i].markdown(ai_card_html(p,"⟳ Thinking...","ROUND 1"),unsafe_allow_html=True)
        with st.spinner("Round 1 — all 5 models answering..."): results=run_parallel([(p,"initial",with_ctx(q),image_data) for p in PERSONAS_ORDER])
        st.session_state.r1=dict(zip(PERSONAS_ORDER,results)); st.session_state.phase=2; save_discussion(_current_discussion()); st.rerun()
    cols=st.columns(5)
    for i,p in enumerate(PERSONAS_ORDER): cols[i].markdown(ai_card_html(p,st.session_state.r1[p],"ROUND 1"),unsafe_allow_html=True)
    divider()

    # Round 2
    phase_header(2,"Open Debate — Each AI critiques and builds on the others","done" if st.session_state.phase>2 else "active")
    def make_debate(me):
        others=[p for p in PERSONAS_ORDER if p!=me]
        return with_ctx(f'Original: "{q}"\n\nMY ANSWER:\n{st.session_state.r1[me]}\n\n'+"\n\n".join(f"{AI_CONFIG[o]['name'].upper()}:\n{st.session_state.r1[o]}" for o in others)+"\n\nEngage genuinely. Agree, challenge, extend.")
    if not st.session_state.r2:
        cols=st.columns(5)
        for i,p in enumerate(PERSONAS_ORDER): cols[i].markdown(ai_card_html(p,"⟳ Reading others...","ROUND 2"),unsafe_allow_html=True)
        with st.spinner("Round 2 — all 5 models debating..."): results=run_parallel([(p,"debate",make_debate(p),None) for p in PERSONAS_ORDER])
        st.session_state.r2=dict(zip(PERSONAS_ORDER,results)); st.session_state.phase=3; save_discussion(_current_discussion()); st.rerun()
    cols=st.columns(5)
    for i,p in enumerate(PERSONAS_ORDER): cols[i].markdown(ai_card_html(p,st.session_state.r2[p],"ROUND 2"),unsafe_allow_html=True)
    divider()

    # Synthesis
    phase_header(3,"Final Synthesis — Best answer from all five voices","done" if st.session_state.phase>=4 else "active")
    if not st.session_state.synthesis:
        sp=f'QUESTION: "{q}"\n\nROUND 1:\n'+"\n\n".join(f"[{AI_CONFIG[p]['name']}]\n{st.session_state.r1[p]}" for p in PERSONAS_ORDER)+"\n\nROUND 2:\n"+"\n\n".join(f"[{AI_CONFIG[p]['name']}]\n{st.session_state.r2[p]}" for p in PERSONAS_ORDER)+"\n\nSynthesize."
        with st.spinner("Synthesizing..."): st.session_state.synthesis=call_claude(SYNTH_SYSTEM,sp)
        st.session_state.phase=4; save_discussion(_current_discussion()); st.rerun()
    safe=st.session_state.synthesis.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
    st.markdown(f'<div style="background:linear-gradient(135deg,rgba(16,185,129,0.08),rgba(16,185,129,0.04));border:2px solid rgba(16,185,129,0.4);border-radius:16px;padding:32px;box-shadow:0 4px 16px rgba(16,185,129,0.15)">'
                f'<div style="display:flex;align-items:center;gap:16px;margin-bottom:20px">'
                f'<div style="width:40px;height:40px;border-radius:50%;background:linear-gradient(135deg,#10B981,#059669);display:flex;align-items:center;justify-content:center;font-size:20px">✦</div>'
                f'<div><div style="font-size:16px;font-weight:700;color:#10B981;letter-spacing:0.02em">SYNTHESIZED ANSWER</div>'
                f'<div style="font-size:11px;color:#5A6A7A;font-weight:600;margin-top:2px">Claude · Gemini · GPT-4 · Perplexity · DeepSeek</div></div></div>'
                f'<div style="color:#C5D1DE;font-size:14.5px;line-height:1.9;white-space:pre-wrap">{safe}</div></div>',unsafe_allow_html=True)

    # Fact-check
    if st.session_state.phase>=4 and not st.session_state.factcheck:
        fc_prompt=f'QUESTION: "{q}"\n\nSYNTHESIS:\n{st.session_state.synthesis}\n\nFact-check with skepticism. Verify claims, flag hallucinations, cite sources. 2-3 paragraphs.'
        try:
            with st.spinner("🔍 Perplexity fact-checking..."):
                if PERPLEXITY_KEY:
                    try:
                        st.session_state.factcheck=call_perplexity(FACTCHECK_SYSTEM,fc_prompt)
                    except Exception:
                        st.session_state.factcheck=call_claude(FACTCHECK_SYSTEM,fc_prompt)
                else:
                    st.session_state.factcheck=call_claude(FACTCHECK_SYSTEM,fc_prompt)
        except Exception as e:
            st.session_state.factcheck=f"Fact-check unavailable: {str(e)[:100]}"
        save_discussion(_current_discussion()); st.rerun()
    if st.session_state.factcheck:
        fc_source = "PERPLEXITY" if (PERPLEXITY_KEY and "unavailable" not in st.session_state.factcheck.lower()) else "CLAUDE"
        with st.expander(f"🔍  FACT-CHECK — Adversarial verification ({fc_source})",expanded=False):
            safe_fc=st.session_state.factcheck.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
            st.markdown(f'<div style="background:linear-gradient(135deg,rgba(251,191,36,0.08),rgba(251,191,36,0.04));border:1.5px solid rgba(251,191,36,0.4);border-radius:12px;padding:24px">'
                       f'<div style="color:#FBB020;font-size:11px;font-weight:700;letter-spacing:0.08em;margin-bottom:12px">⚠ {fc_source} VERIFICATION</div>'
                       f'<div style="color:#C5D1DE;font-size:13px;line-height:1.8;white-space:pre-wrap">{safe_fc}</div></div>',unsafe_allow_html=True)

    # Follow-ups
    if st.session_state.phase>=4:
        divider()
        st.markdown('<div style="font-size:15px;font-weight:700;color:#5B8DEF;margin-bottom:16px;letter-spacing:0.02em">💬 Continue Discussion</div>',unsafe_allow_html=True)
        for i,fu in enumerate(st.session_state.followups):
            with st.expander(f"↩ Follow-up {i+1}: {fu['question'][:50]}{'...' if len(fu['question'])>50 else ''}",expanded=(i==len(st.session_state.followups)-1)):
                cols=st.columns(5)
                for j,p in enumerate(PERSONAS_ORDER): cols[j].markdown(ai_card_html(p,fu["responses"].get(p,""),"FOLLOW-UP"),unsafe_allow_html=True)
                if fu.get("synthesis"):
                    sfu=fu["synthesis"].replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
                    st.markdown(f'<div style="background:linear-gradient(135deg,rgba(91,141,239,0.08),rgba(91,141,239,0.04));border:1.5px solid rgba(91,141,239,0.4);border-radius:12px;padding:24px;margin-top:16px">'
                                f'<div style="font-size:13px;font-weight:700;color:#5B8DEF;margin-bottom:12px">↩ UPDATED SYNTHESIS</div>'
                                f'<div style="color:#C5D1DE;font-size:13.5px;line-height:1.8;white-space:pre-wrap">{sfu}</div></div>',unsafe_allow_html=True)
                # Follow-up fact-check
                if fu.get("factcheck"):
                    with st.expander("🔍  Follow-up fact-check",expanded=False):
                        safe_fufc=fu["factcheck"].replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
                        st.markdown(f'<div style="background:linear-gradient(135deg,rgba(251,191,36,0.08),rgba(251,191,36,0.04));border:1.5px solid rgba(251,191,36,0.4);border-radius:12px;padding:20px">'
                                   f'<div style="color:#FBB020;font-size:11px;font-weight:700;letter-spacing:0.08em;margin-bottom:10px">⚠ VERIFICATION</div>'
                                   f'<div style="color:#C5D1DE;font-size:13px;line-height:1.8;white-space:pre-wrap">{safe_fufc}</div></div>',unsafe_allow_html=True)
        n=len(st.session_state.followups)
        fu_q=st.text_input("fu",placeholder="Ask a follow-up, challenge the synthesis, request clarification...",label_visibility="collapsed",key=f"fu_{n}")
        with st.expander("📎  Attach context to follow-up",expanded=False):
            st.markdown('<div style="font-size:12px;color:#5A6A7A;margin-bottom:12px">Add files, images, or a URL for this follow-up.</div>',unsafe_allow_html=True)
            fu_text_ctx,fu_image_data,fu_ctx_summary=render_context_inputs(f"fu_{n}")
        if fu_ctx_summary:
            st.markdown(f'<div style="font-size:12px;color:#10B981;background:rgba(16,185,129,0.08);border:1px solid rgba(16,185,129,0.3);border-radius:10px;padding:10px 14px;margin-bottom:12px;font-weight:600">✓ {fu_ctx_summary}</div>',unsafe_allow_html=True)
        if st.button("▶  SEND FOLLOW-UP",key=f"send_{n}") and fu_q.strip():
            hctx=f'ORIGINAL: "{q}"\n\nSYNTHESIS:\n{st.session_state.synthesis}\n\n'+("PRIOR:\n"+"".join(f"Q{i+1}: {fu['question']}\nA: {fu.get('synthesis','')}\n\n" for i,fu in enumerate(st.session_state.followups)) if st.session_state.followups else "")+f'NEW: "{fu_q.strip()}"'
            if fu_text_ctx: hctx=fu_text_ctx+hctx
            with st.spinner("All 5 models responding..."): fu_results=run_parallel([(p,"followup",hctx,fu_image_data if fu_image_data else None) for p in PERSONAS_ORDER])
            fu_map=dict(zip(PERSONAS_ORDER,fu_results))
            fu_sp=hctx+"\n\nRESPONSES:\n"+"\n\n".join(f"[{AI_CONFIG[p]['name']}]\n{fu_map[p]}" for p in PERSONAS_ORDER)+"\n\nSynthesize."
            with st.spinner("Synthesizing..."): fu_synth=call_claude(FOLLOWUP_SYNTH_SYSTEM,fu_sp)
            # Fact-check follow-up synthesis
            fu_fc_prompt=f'ORIGINAL: "{q}"\n\nFOLLOW-UP: "{fu_q.strip()}"\n\nFOLLOW-UP SYNTHESIS:\n{fu_synth}\n\nFact-check this follow-up response. Verify claims, cite sources. 2 paragraphs.'
            try:
                with st.spinner("🔍 Fact-checking follow-up..."):
                    if PERPLEXITY_KEY:
                        try:
                            fu_factcheck=call_perplexity(FACTCHECK_SYSTEM,fu_fc_prompt)
                        except Exception:
                            fu_factcheck=call_claude(FACTCHECK_SYSTEM,fu_fc_prompt)
                    else:
                        fu_factcheck=call_claude(FACTCHECK_SYSTEM,fu_fc_prompt)
            except Exception as e:
                fu_factcheck=f"Fact-check unavailable: {str(e)[:100]}"
            st.session_state.followups.append({"question":fu_q.strip(),"responses":fu_map,"synthesis":fu_synth,"factcheck":fu_factcheck,"context_summary":fu_ctx_summary})
            save_discussion(_current_discussion()); st.rerun()

        render_share_panel(q,st.session_state.synthesis,st.session_state.followups)
        st.markdown('<div style="margin-top:32px"></div>',unsafe_allow_html=True)
        if st.button("↺  NEW DISCUSSION"):
            for k in ["phase","question","r1","r2","synthesis","factcheck","followups","context_summary","active_id","created_at"]: st.session_state.pop(k,None)
            st.rerun()

if __name__=="__main__": main()
