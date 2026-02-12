import os
import json
import base64
from datetime import datetime, timedelta
from io import BytesIO
import uuid
import random

import streamlit as st
import yaml
import pandas as pd
import altair as alt
from pypdf import PdfReader

try:
    from docx import Document  # python-docx
except ImportError:
    Document = None

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
except ImportError:
    canvas = None
    letter = None

from openai import OpenAI
import google.generativeai as genai
from anthropic import Anthropic
import httpx


# =========================
# Constants & configuration
# =========================

ALL_MODELS = [
    # OpenAI
    "gpt-4o-mini",
    "gpt-4.1-mini",
    # Gemini
    "gemini-2.5-flash",
    "gemini-3-flash-preview",
    "gemini-2.5-flash-lite",
    "gemini-3-pro-preview",
    # Anthropic (representative set; user can also define via agents.yaml)
    "claude-3-5-sonnet-20241022",
    "claude-3-5-haiku-20241022",
    "claude-3-opus-20240229",
    # Grok (xAI)
    "grok-4-fast-reasoning",
    "grok-3-mini",
]

OPENAI_MODELS = {"gpt-4o-mini", "gpt-4.1-mini"}
GEMINI_MODELS = {
    "gemini-2.5-flash",
    "gemini-3-flash-preview",
    "gemini-2.5-flash-lite",
    "gemini-3-pro-preview",
}
ANTHROPIC_MODELS = {
    "claude-3-5-sonnet-20241022",
    "claude-3-5-haiku-20241022",
    "claude-3-opus-20240229",
}
GROK_MODELS = {"grok-4-fast-reasoning", "grok-3-mini"}

PAINTER_STYLES = [
    "Van Gogh", "Monet", "Picasso", "Da Vinci", "Rembrandt",
    "Matisse", "Kandinsky", "Hokusai", "Yayoi Kusama", "Frida Kahlo",
    "Salvador Dali", "Rothko", "Pollock", "Chagall", "Basquiat",
    "Haring", "Georgia O'Keeffe", "Turner", "Seurat", "Escher",
]

LABELS = {
    # Tabs
    "Dashboard": {"English": "Dashboard", "繁體中文": "儀表板"},
    "TW Premarket": {"English": "TW Premarket Application", "繁體中文": "第二、三等級醫療器材查驗登記"},
    "510k_tab": {"English": "510(k) Intelligence", "繁體中文": "510(k) 智能分析"},
    "PDF → Markdown": {"English": "PDF → Markdown", "繁體中文": "PDF → Markdown"},
    "Checklist & Report": {"English": "510(k) Review Pipeline", "繁體中文": "510(k) 審查全流程"},
    "Note Keeper & Magics": {"English": "Note Keeper & Magics", "繁體中文": "筆記助手與魔法"},
    "Agents Config": {"English": "Agents Config Studio", "繁體中文": "代理設定工作室"},
    "Agent Workflow Studio": {"English": "Agent Workflow Studio", "繁體中文": "代理工作流工作室"},
    "WOW AI Lab": {"English": "WOW AI Lab", "繁體中文": "WOW AI 實驗室"},
    # Common UI
    "Global Settings": {"English": "Global Settings", "繁體中文": "全域設定"},
    "Theme": {"English": "Theme", "繁體中文": "主題"},
    "Language": {"English": "Language", "繁體中文": "語言"},
    "Painter Style": {"English": "Painter Style", "繁體中文": "畫家風格"},
    "Default Model": {"English": "Default Model", "繁體中文": "預設模型"},
    "Default max_tokens": {"English": "Default max_tokens", "繁體中文": "預設 max_tokens"},
    "Temperature": {"English": "Temperature", "繁體中文": "溫度"},
    "API Keys": {"English": "API Keys", "繁體中文": "API 金鑰"},
    "Upload custom agents.yaml": {"English": "Upload custom agents.yaml", "繁體中文": "上傳自訂 agents.yaml"},
    "Run Agent": {"English": "Run Agent", "繁體中文": "執行代理"},
    "View mode": {"English": "View mode", "繁體中文": "檢視模式"},
    "Markdown": {"English": "Markdown", "繁體中文": "Markdown"},
    "Plain text": {"English": "Plain text", "繁體中文": "純文字"},
}

# A WOW theming engine: palette + gradient background per painter.
STYLE_THEME = {
    "Van Gogh": {"bg": "radial-gradient(circle at top left, #243B55, #141E30)", "primary": "#60a5fa", "accent": "#fbbf24"},
    "Monet": {"bg": "linear-gradient(120deg, #a1c4fd, #c2e9fb)", "primary": "#2563eb", "accent": "#22c55e"},
    "Picasso": {"bg": "linear-gradient(135deg, #ff9a9e, #fecfef)", "primary": "#db2777", "accent": "#f59e0b"},
    "Da Vinci": {"bg": "radial-gradient(circle, #f9f1c6, #c9a66b)", "primary": "#92400e", "accent": "#1d4ed8"},
    "Rembrandt": {"bg": "radial-gradient(circle, #2c1810, #0b090a)", "primary": "#f59e0b", "accent": "#eab308"},
    "Matisse": {"bg": "linear-gradient(135deg, #ffecd2, #fcb69f)", "primary": "#ea580c", "accent": "#2563eb"},
    "Kandinsky": {"bg": "linear-gradient(135deg, #00c6ff, #0072ff)", "primary": "#38bdf8", "accent": "#a78bfa"},
    "Hokusai": {"bg": "linear-gradient(135deg, #2b5876, #4e4376)", "primary": "#93c5fd", "accent": "#f472b6"},
    "Yayoi Kusama": {"bg": "radial-gradient(circle, #ffdd00, #ff6a00)", "primary": "#111827", "accent": "#ef4444"},
    "Frida Kahlo": {"bg": "linear-gradient(135deg, #f8b195, #f67280, #c06c84)", "primary": "#7c3aed", "accent": "#22c55e"},
    "Salvador Dali": {"bg": "linear-gradient(135deg, #1a2a6c, #b21f1f, #fdbb2d)", "primary": "#fbbf24", "accent": "#60a5fa"},
    "Rothko": {"bg": "linear-gradient(135deg, #141E30, #243B55)", "primary": "#e11d48", "accent": "#f59e0b"},
    "Pollock": {"bg": "repeating-linear-gradient(45deg,#222,#222 10px,#333 10px,#333 20px)", "primary": "#e5e7eb", "accent": "#22c55e"},
    "Chagall": {"bg": "linear-gradient(135deg, #a18cd1, #fbc2eb)", "primary": "#7c3aed", "accent": "#06b6d4"},
    "Basquiat": {"bg": "linear-gradient(135deg, #f7971e, #ffd200)", "primary": "#111827", "accent": "#ef4444"},
    "Haring": {"bg": "linear-gradient(135deg, #ff512f, #dd2476)", "primary": "#111827", "accent": "#22c55e"},
    "Georgia O'Keeffe": {"bg": "linear-gradient(135deg, #ffefba, #ffffff)", "primary": "#1d4ed8", "accent": "#ea580c"},
    "Turner": {"bg": "linear-gradient(135deg, #f8ffae, #43c6ac)", "primary": "#0f766e", "accent": "#f97316"},
    "Seurat": {"bg": "radial-gradient(circle, #e0eafc, #cfdef3)", "primary": "#1d4ed8", "accent": "#a855f7"},
    "Escher": {"bg": "linear-gradient(135deg, #232526, #414345)", "primary": "#93c5fd", "accent": "#f59e0b"},
}


# =========================
# Helper: localization & style
# =========================

def t(key: str) -> str:
    lang = st.session_state.settings.get("language", "English")
    return LABELS.get(key, {}).get(lang, key)


def apply_style(theme: str, painter_style: str):
    palette = STYLE_THEME.get(painter_style, STYLE_THEME["Van Gogh"])
    bg = palette["bg"]
    primary = palette["primary"]
    accent = palette["accent"]

    # Theme-specific tokens
    if theme == "Dark":
        text = "#e5e7eb"
        card = "rgba(15, 23, 42, 0.62)"
        panel = "rgba(2, 6, 23, 0.55)"
        border = "rgba(148,163,184,0.35)"
        input_bg = "rgba(17, 24, 39, 0.92)"
        shadow = "0 18px 42px rgba(0,0,0,0.55)"
    else:
        text = "#0f172a"
        card = "rgba(255,255,255,0.72)"
        panel = "rgba(255,255,255,0.55)"
        border = "rgba(15,23,42,0.12)"
        input_bg = "rgba(255,255,255,0.95)"
        shadow = "0 18px 42px rgba(15,23,42,0.18)"

    css = f"""
    :root {{
      --wow-bg: {bg};
      --wow-text: {text};
      --wow-card: {card};
      --wow-panel: {panel};
      --wow-border: {border};
      --wow-primary: {primary};
      --wow-accent: {accent};
      --wow-input: {input_bg};
      --wow-shadow: {shadow};
    }}

    .stApp {{
      background: var(--wow-bg);
      color: var(--wow-text);
    }}

    /* Top header (WOＷ UI) */
    .wow-hero {{
      border: 1px solid var(--wow-border);
      background: linear-gradient(135deg, rgba(255,255,255,0.10), rgba(0,0,0,0.15));
      border-radius: 22px;
      padding: 16px 18px;
      box-shadow: var(--wow-shadow);
      margin-bottom: 0.9rem;
    }}
    .wow-hero-title {{
      font-size: 1.35rem;
      font-weight: 800;
      letter-spacing: 0.02em;
    }}
    .wow-hero-sub {{
      margin-top: 6px;
      font-size: 0.95rem;
      opacity: 0.9;
      line-height: 1.35;
    }}
    .wow-chip {{
      display:inline-flex;
      align-items:center;
      gap: 8px;
      padding: 4px 10px;
      border-radius: 999px;
      border: 1px solid var(--wow-border);
      background: rgba(15, 23, 42, 0.14);
      font-size: 0.82rem;
      margin-right: 8px;
    }}
    .wow-dot {{
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: var(--wow-accent);
      box-shadow: 0 0 18px rgba(255,255,255,0.18);
    }}

    /* Cards */
    .wow-card {{
      border-radius: 18px;
      padding: 14px 18px;
      margin-bottom: 0.75rem;
      border: 1px solid var(--wow-border);
      background: var(--wow-card);
      box-shadow: var(--wow-shadow);
      backdrop-filter: blur(8px);
    }}
    .wow-card-title {{
      font-size: 0.82rem;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      opacity: 0.86;
    }}
    .wow-card-main {{
      font-size: 1.5rem;
      font-weight: 800;
      margin-top: 4px;
    }}
    .wow-badge {{
      display:inline-flex;
      align-items:center;
      padding:2px 10px;
      border-radius:999px;
      font-size:0.75rem;
      font-weight:650;
      background: rgba(15, 23, 42, 0.18);
      border:1px solid rgba(148,163,184,0.55);
    }}

    /* Inputs */
    .stTextInput input, .stTextArea textarea {{
      background: var(--wow-input) !important;
      color: var(--wow-text) !important;
      border-radius: 12px !important;
      border: 1px solid var(--wow-border) !important;
    }}
    .stSelectbox > div > div {{
      background: var(--wow-input) !important;
      border-radius: 12px !important;
      border: 1px solid var(--wow-border) !important;
    }}

    /* Buttons */
    .stButton > button {{
      border-radius: 999px !important;
      border: 1px solid rgba(255,255,255,0.15) !important;
      background: linear-gradient(135deg, var(--wow-primary), var(--wow-accent)) !important;
      color: white !important;
      font-weight: 700 !important;
      box-shadow: 0 18px 38px rgba(15,23,42,0.25);
    }}
    .stButton > button:hover {{
      filter: brightness(1.06);
      transform: translateY(-1px);
      transition: 140ms ease;
    }}

    /* WOW status pill */
    .wow-status {{
      display:flex;
      align-items:center;
      justify-content: space-between;
      gap: 10px;
      padding: 10px 12px;
      border-radius: 14px;
      border: 1px solid var(--wow-border);
      background: var(--wow-panel);
      box-shadow: 0 12px 26px rgba(15,23,42,0.12);
      margin-bottom: 0.6rem;
    }}
    .wow-status-left {{
      display:flex;
      align-items:center;
      gap: 10px;
    }}
    .wow-pulse {{
      width: 10px;
      height: 10px;
      border-radius: 999px;
      background: #94a3b8;
    }}
    .wow-pulse.running {{
      background: #f59e0b;
      box-shadow: 0 0 0 rgba(245,158,11,0.55);
      animation: wowPulse 1.2s infinite;
    }}
    @keyframes wowPulse {{
      0% {{ box-shadow: 0 0 0 0 rgba(245,158,11,0.55); }}
      70% {{ box-shadow: 0 0 0 12px rgba(245,158,11,0); }}
      100% {{ box-shadow: 0 0 0 0 rgba(245,158,11,0); }}
    }}
    """
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def render_wow_hero():
    s = st.session_state
    lang = s.settings.get("language", "English")
    title = "WOＷ Agentic Medical Device Doc Intelligence"
    sub = (
        "A multi-provider, multi-agent workspace for TFDA premarket, 510(k) intelligence, "
        "PDF→Markdown, Note Keeper, and agent workflows — with painter-style UI."
        if lang == "English"
        else
        "多模型、多代理的醫療器材文件工作台：TFDA 查驗登記、510(k) 智能分析、PDF→Markdown、筆記助手與代理工作流 — 支援畫家風格介面。"
    )

    last = s.wow.get("last_event")
    last_chip = ""
    if last:
        last_chip = f"""
        <span class="wow-chip"><span class="wow-dot"></span>
          Last: <b>{last.get('tab','')}</b> · {last.get('agent','')} · {last.get('model','')}
        </span>
        """

    st.markdown(
        f"""
        <div class="wow-hero">
          <div class="wow-hero-title">{title}</div>
          <div class="wow-hero-sub">{sub}</div>
          <div style="margin-top:10px;">
            <span class="wow-chip"><span class="wow-dot"></span> Theme: <b>{s.settings.get('theme')}</b></span>
            <span class="wow-chip"><span class="wow-dot"></span> Lang: <b>{s.settings.get('language')}</b></span>
            <span class="wow-chip"><span class="wow-dot"></span> Style: <b>{s.settings.get('painter_style')}</b></span>
            {last_chip}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# =========================
# LLM routing
# =========================

def get_provider(model: str) -> str:
    if model in OPENAI_MODELS:
        return "openai"
    if model in GEMINI_MODELS:
        return "gemini"
    if model in ANTHROPIC_MODELS:
        return "anthropic"
    if model in GROK_MODELS:
        return "grok"
    # allow unknown models defined by user in agents.yaml: infer by prefix
    if model.startswith("gpt-"):
        return "openai"
    if model.startswith("gemini-"):
        return "gemini"
    if model.startswith("claude-"):
        return "anthropic"
    if model.startswith("grok-"):
        return "grok"
    raise ValueError(f"Unknown model: {model}")


def call_llm(
    model: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 12000,
    temperature: float = 0.2,
    api_keys: dict | None = None,
) -> str:
    provider = get_provider(model)
    api_keys = api_keys or {}

    def get_key(name: str, env_var: str) -> str:
        # IMPORTANT: do not require storing env keys in session_state
        return (api_keys.get(name) or "").strip() or (os.getenv(env_var) or "").strip()

    if provider == "openai":
        key = get_key("openai", "OPENAI_API_KEY")
        if not key:
            raise RuntimeError("Missing OpenAI API key.")
        client = OpenAI(api_key=key)
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt or ""},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return resp.choices[0].message.content

    if provider == "gemini":
        key = get_key("gemini", "GEMINI_API_KEY")
        if not key:
            raise RuntimeError("Missing Gemini API key.")
        genai.configure(api_key=key)
        llm = genai.GenerativeModel(model)
        resp = llm.generate_content(
            (system_prompt or "") + "\n\n" + user_prompt,
            generation_config={
                "max_output_tokens": max_tokens,
                "temperature": temperature,
            },
        )
        return resp.text

    if provider == "anthropic":
        key = get_key("anthropic", "ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError("Missing Anthropic API key.")
        client = Anthropic(api_key=key)
        resp = client.messages.create(
            model=model,
            system=system_prompt or "",
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return resp.content[0].text

    if provider == "grok":
        key = get_key("grok", "GROK_API_KEY")
        if not key:
            raise RuntimeError("Missing Grok (xAI) API key.")
        with httpx.Client(base_url="https://api.x.ai/v1", timeout=90) as client:
            resp = client.post(
                "/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt or ""},
                        {"role": "user", "content": user_prompt},
                    ],
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
            )
            resp.raise_for_status()
            data = resp.json()
        return data["choices"][0]["message"]["content"]

    raise RuntimeError(f"Unsupported provider for model {model}")


# =========================
# Generic helpers
# =========================

def wow_set_run_state(state: str, label: str = "", extra: dict | None = None, error: str = ""):
    st.session_state.wow["run_state"] = state  # pending/running/done/error
    st.session_state.wow["run_label"] = label
    st.session_state.wow["run_ts"] = datetime.utcnow().isoformat()
    st.session_state.wow["run_error"] = error
    if extra:
        st.session_state.wow.update(extra)


def show_status(step_name: str, status: str, right_text: str = ""):
    # WOW status indicator with animated pulse for "running"
    pulse_class = "wow-pulse"
    if status == "running":
        pulse_class += " running"

    status_map = {
        "pending": ("Pending", "#94a3b8"),
        "running": ("Running", "#f59e0b"),
        "done": ("Done", "#22c55e"),
        "error": ("Error", "#ef4444"),
    }
    label, color = status_map.get(status, ("Pending", "#94a3b8"))
    st.markdown(
        f"""
        <div class="wow-status">
          <div class="wow-status-left">
            <div class="{pulse_class}"></div>
            <div>
              <div style="font-weight:800;">{step_name}</div>
              <div style="font-size:0.86rem;opacity:0.85;">
                <span class="wow-badge" style="border-color:{color};">{label}</span>
              </div>
            </div>
          </div>
          <div style="font-size:0.86rem;opacity:0.9;">{right_text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def log_event(tab: str, agent: str, model: str, tokens_est: int):
    evt = {
        "tab": tab,
        "agent": agent,
        "model": model,
        "tokens_est": tokens_est,
        "ts": datetime.utcnow().isoformat(),
    }
    st.session_state["history"].append(evt)
    st.session_state.wow["last_event"] = evt


def extract_pdf_pages_to_text(file, start_page: int, end_page: int) -> str:
    reader = PdfReader(file)
    n = len(reader.pages)
    start = max(0, start_page - 1)
    end = min(n, end_page)
    texts = []
    for i in range(start, end):
        try:
            texts.append(reader.pages[i].extract_text() or "")
        except Exception:
            texts.append("")
    return "\n\n".join(texts)


def extract_docx_to_text(file) -> str:
    if Document is None:
        return ""
    try:
        bio = BytesIO(file.read())
        doc = Document(bio)
        return "\n".join(p.text for p in doc.paragraphs)
    except Exception:
        return ""


def create_pdf_from_text(text: str) -> bytes:
    if canvas is None or letter is None:
        raise RuntimeError(
            "PDF generation library 'reportlab' is not installed. "
            "Please add 'reportlab' to requirements.txt."
        )
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    width, height = letter
    margin = 72
    line_height = 14
    y = height - margin
    for line in text.splitlines():
        if y < margin:
            c.showPage()
            y = height - margin
        c.drawString(margin, y, line[:2000])
        y -= line_height
    c.save()
    buf.seek(0)
    return buf.getvalue()


def show_pdf(pdf_bytes: bytes, height: int = 600):
    if not pdf_bytes:
        return
    b64 = base64.b64encode(pdf_bytes).decode("utf-8")
    pdf_html = f"""
    <iframe src="data:application/pdf;base64,{b64}"
            width="100%" height="{height}" type="application/pdf"></iframe>
    """
    st.markdown(pdf_html, unsafe_allow_html=True)


# =========================
# Agent UI runner (single step)
# =========================

def agent_run_ui(
    agent_id: str,
    tab_key: str,
    default_prompt: str,
    default_input_text: str = "",
    allow_model_override: bool = True,
    tab_label_for_history: str | None = None,
):
    agents_cfg = st.session_state.get("agents_cfg", {})
    agents_dict = agents_cfg.get("agents", {})

    if agent_id in agents_dict:
        agent_cfg = agents_dict[agent_id]
    else:
        agent_cfg = {
            "name": agent_id,
            "model": st.session_state.settings["model"],
            "system_prompt": "",
            "max_tokens": st.session_state.settings["max_tokens"],
        }

    status_key = f"{tab_key}_status"
    if status_key not in st.session_state:
        st.session_state[status_key] = "pending"

    show_status(
        agent_cfg.get("name", agent_id),
        st.session_state[status_key],
        right_text=f"Agent ID: {agent_id}",
    )

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        user_prompt = st.text_area(
            "Prompt",
            value=st.session_state.get(f"{tab_key}_prompt", default_prompt),
            height=160,
            key=f"{tab_key}_prompt",
        )
    with col2:
        base_model = agent_cfg.get("model", st.session_state.settings["model"])
        model_list = list(dict.fromkeys(ALL_MODELS + [base_model]))
        model_index = model_list.index(base_model) if base_model in model_list else 0
        model = st.selectbox(
            "Model",
            model_list,
            index=model_index,
            disabled=not allow_model_override,
            key=f"{tab_key}_model",
        )
    with col3:
        max_tokens = st.number_input(
            "max_tokens",
            min_value=1000,
            max_value=120000,
            value=int(agent_cfg.get("max_tokens", st.session_state.settings["max_tokens"])),
            step=1000,
            key=f"{tab_key}_max_tokens",
        )

    input_text = st.text_area(
        "Input Text / Markdown",
        value=st.session_state.get(f"{tab_key}_input", default_input_text),
        height=260,
        key=f"{tab_key}_input",
    )

    run = st.button(t("Run Agent"), key=f"{tab_key}_run")

    if run:
        st.session_state[status_key] = "running"
        wow_set_run_state("running", label=f"{tab_label_for_history or tab_key} · {agent_cfg.get('name', agent_id)}")
        show_status(agent_cfg.get("name", agent_id), "running", right_text="Dispatching request...")

        api_keys = st.session_state.get("api_keys", {})
        system_prompt = agent_cfg.get("system_prompt", "")
        user_full = f"{user_prompt}\n\n---\n\n{input_text}"

        with st.spinner("Running agent..."):
            try:
                out = call_llm(
                    model=model,
                    system_prompt=system_prompt,
                    user_prompt=user_full,
                    max_tokens=max_tokens,
                    temperature=st.session_state.settings["temperature"],
                    api_keys=api_keys,
                )
                st.session_state[f"{tab_key}_output"] = out
                st.session_state[status_key] = "done"
                wow_set_run_state("done", label=f"{tab_label_for_history or tab_key} · {agent_cfg.get('name', agent_id)}")
                token_est = int(len(user_full + out) / 4)
                log_event(
                    tab_label_for_history or tab_key,
                    agent_cfg.get("name", agent_id),
                    model,
                    token_est,
                )
            except Exception as e:
                st.session_state[status_key] = "error"
                wow_set_run_state("error", label=f"{tab_label_for_history or tab_key}", error=str(e))
                st.error(f"Agent error: {e}")

    output = st.session_state.get(f"{tab_key}_output", "")
    view_mode = st.radio(
        t("View mode"),
        [t("Markdown"), t("Plain text")],
        horizontal=True,
        key=f"{tab_key}_viewmode",
    )
    edited = st.text_area(
        "Output (editable)",
        value=output,
        height=320,
        key=f"{tab_key}_output_edited",
    )
    st.session_state[f"{tab_key}_output_edited_value"] = edited


# =========================
# Sidebar (WOＷ UI controls + keys + agents)
# =========================

def render_sidebar():
    with st.sidebar:
        st.markdown(f"### {t('Global Settings')}")

        st.session_state.settings["theme"] = st.radio(
            t("Theme"),
            ["Light", "Dark"],
            index=0 if st.session_state.settings["theme"] == "Light" else 1,
        )

        st.session_state.settings["language"] = st.radio(
            t("Language"),
            ["English", "繁體中文"],
            index=0 if st.session_state.settings["language"] == "English" else 1,
        )

        col1, col2 = st.columns([3, 1])
        with col1:
            style = st.selectbox(
                t("Painter Style"),
                PAINTER_STYLES,
                index=PAINTER_STYLES.index(st.session_state.settings["painter_style"]),
            )
        with col2:
            if st.button("Jackpot!"):
                style = random.choice(PAINTER_STYLES)
                st.session_state.wow["style_jackpot_ts"] = datetime.utcnow().isoformat()
        st.session_state.settings["painter_style"] = style

        st.session_state.settings["model"] = st.selectbox(
            t("Default Model"),
            ALL_MODELS,
            index=ALL_MODELS.index(st.session_state.settings["model"])
            if st.session_state.settings["model"] in ALL_MODELS
            else 0,
        )
        st.session_state.settings["max_tokens"] = st.number_input(
            t("Default max_tokens"),
            min_value=1000,
            max_value=120000,
            value=int(st.session_state.settings["max_tokens"]),
            step=1000,
        )
        st.session_state.settings["temperature"] = st.slider(
            t("Temperature"),
            0.0,
            1.0,
            float(st.session_state.settings["temperature"]),
            0.05,
        )

        st.markdown("---")
        st.markdown(f"### {t('API Keys')}")
        st.caption(
            "Keys are never displayed. If a key exists in environment variables, input fields are hidden."
            if st.session_state.settings["language"] == "English"
            else "金鑰不會顯示。若環境變數已提供金鑰，則不顯示輸入欄位。"
        )

        keys = {}

        # IMPORTANT: if env key exists, do NOT store it in session_state
        if os.getenv("OPENAI_API_KEY"):
            st.caption("OpenAI: using environment key.")
        else:
            keys["openai"] = st.text_input("OpenAI API Key", type="password")

        if os.getenv("GEMINI_API_KEY"):
            st.caption("Gemini: using environment key.")
        else:
            keys["gemini"] = st.text_input("Gemini API Key", type="password")

        if os.getenv("ANTHROPIC_API_KEY"):
            st.caption("Anthropic: using environment key.")
        else:
            keys["anthropic"] = st.text_input("Anthropic API Key", type="password")

        if os.getenv("GROK_API_KEY"):
            st.caption("Grok(xAI): using environment key.")
        else:
            keys["grok"] = st.text_input("Grok API Key", type="password")

        st.session_state["api_keys"] = keys

        st.markdown("---")
        st.markdown("### WOW Status Dock")

        state = st.session_state.wow.get("run_state", "pending")
        label = st.session_state.wow.get("run_label", "")
        ts = st.session_state.wow.get("run_ts", "")
        err = st.session_state.wow.get("run_error", "")

        show_status("System Run State", state, right_text=(label or "—"))
        if ts:
            st.caption(f"UTC: {ts}")
        if err:
            st.error(err)

        st.markdown("---")
        st.markdown("### Agents Catalog (agents.yaml)")
        uploaded_agents = st.file_uploader(
            t("Upload custom agents.yaml"),
            type=["yaml", "yml"],
            key="sidebar_agents_yaml",
        )
        if uploaded_agents is not None:
            try:
                cfg = yaml.safe_load(uploaded_agents.read())
                if "agents" in cfg:
                    st.session_state["agents_cfg"] = cfg
                    st.success("Custom agents.yaml loaded for this session.")
                else:
                    st.warning("Uploaded YAML has no top-level 'agents' key. Using previous config.")
            except Exception as e:
                st.error(f"Failed to parse uploaded YAML: {e}")


# =========================
# Dashboard (interactive + WOW wall)
# =========================

def render_dashboard():
    st.title(t("Dashboard"))
    hist = st.session_state["history"]
    if not hist:
        st.info("No runs yet." if st.session_state.settings["language"] == "English" else "尚無執行紀錄。")
        return

    df = pd.DataFrame(hist)
    df["ts"] = pd.to_datetime(df["ts"], errors="coerce")

    # Filters
    st.markdown("### Filters")
    colf1, colf2, colf3 = st.columns([1, 2, 2])
    with colf1:
        horizon = st.selectbox(
            "Time Range",
            ["All", "Last 24h", "Last 7d", "Last 30d"],
            index=2,
        )
    with colf2:
        tabs_sel = st.multiselect("Tabs", sorted(df["tab"].dropna().unique().tolist()), default=None)
    with colf3:
        models_sel = st.multiselect("Models", sorted(df["model"].dropna().unique().tolist()), default=None)

    df_f = df.copy()
    now = pd.Timestamp.utcnow()
    if horizon == "Last 24h":
        df_f = df_f[df_f["ts"] >= (now - pd.Timedelta(hours=24))]
    elif horizon == "Last 7d":
        df_f = df_f[df_f["ts"] >= (now - pd.Timedelta(days=7))]
    elif horizon == "Last 30d":
        df_f = df_f[df_f["ts"] >= (now - pd.Timedelta(days=30))]

    if tabs_sel:
        df_f = df_f[df_f["tab"].isin(tabs_sel)]
    if models_sel:
        df_f = df_f[df_f["model"].isin(models_sel)]

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Runs", len(df_f))
    with col2:
        st.metric("Unique Tabs", int(df_f["tab"].nunique()) if len(df_f) else 0)
    with col3:
        st.metric("Approx Tokens Processed", int(df_f["tokens_est"].sum()) if len(df_f) else 0)

    # WOW Status Wall (latest)
    st.markdown("### WOW Status Wall – Latest Activity")
    last = df.sort_values("ts", ascending=False).iloc[0]
    wow_color = "linear-gradient(135deg,#22c55e,#16a34a)"
    if int(last["tokens_est"]) > 40000:
        wow_color = "linear-gradient(135deg,#f97316,#ea580c)"
    if int(last["tokens_est"]) > 80000:
        wow_color = "linear-gradient(135deg,#ef4444,#b91c1c)"

    st.markdown(
        f"""
        <div class="wow-card" style="background:{wow_color};border:0;color:white;">
          <div class="wow-card-title">LATEST RUN SNAPSHOT</div>
          <div class="wow-card-main">{last['tab']} · {last['agent']}</div>
          <div style="margin-top:6px;font-size:0.95rem;opacity:0.95;">
            Model: <b>{last['model']}</b> · Tokens ≈ <b>{int(last['tokens_est'])}</b><br>
            Time (UTC): {str(last['ts'])}
          </div>
          <div style="margin-top:8px;"><span class="wow-badge">Status: active</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if len(df_f) == 0:
        st.info("No data under current filters.")
        return

    st.markdown("### Runs by Tab")
    chart_tab = alt.Chart(df_f).mark_bar().encode(
        x=alt.X("tab:N", sort="-y"),
        y="count():Q",
        color="tab:N",
        tooltip=["tab", "count()"],
    )
    st.altair_chart(chart_tab, use_container_width=True)

    st.markdown("### Runs by Model")
    chart_model = alt.Chart(df_f).mark_bar().encode(
        x=alt.X("model:N", sort="-y"),
        y="count():Q",
        color="model:N",
        tooltip=["model", "count()"],
    )
    st.altair_chart(chart_model, use_container_width=True)

    st.markdown("### Model × Tab Usage Heatmap")
    heat_df = df_f.groupby(["tab", "model"]).size().reset_index(name="count")
    heatmap = (
        alt.Chart(heat_df)
        .mark_rect()
        .encode(
            x=alt.X("model:N", title="Model"),
            y=alt.Y("tab:N", title="Tab"),
            color=alt.Color("count:Q", scale=alt.Scale(scheme="blues"), title="Runs"),
            tooltip=["tab", "model", "count"],
        )
        .properties(height=280)
    )
    st.altair_chart(heatmap, use_container_width=True)

    st.markdown("### Token Usage Over Time")
    chart_time = alt.Chart(df_f).mark_line(point=True).encode(
        x=alt.X("ts:T", title="UTC Time"),
        y=alt.Y("tokens_est:Q", title="Approx Tokens"),
        color="tab:N",
        tooltip=["ts", "tab", "agent", "model", "tokens_est"],
    )
    st.altair_chart(chart_time, use_container_width=True)

    st.markdown("### Recent Activity")
    st.dataframe(df_f.sort_values("ts", ascending=False).head(50), use_container_width=True)


# =========================
# Helper for TW application schema
# =========================

TW_APP_FIELDS = [
    "doc_no", "e_no", "apply_date", "case_type", "device_category", "case_kind",
    "origin", "product_class", "similar", "replace_flag", "prior_app_no",
    "name_zh", "name_en", "indications", "spec_comp",
    "main_cat", "item_code", "item_name",
    "uniform_id", "firm_name", "firm_addr",
    "resp_name", "contact_name", "contact_tel", "contact_fax", "contact_email",
    "confirm_match", "cert_raps", "cert_ahwp", "cert_other",
    "manu_type", "manu_name", "manu_country", "manu_addr", "manu_note",
    "auth_applicable", "auth_desc",
    "cfs_applicable", "cfs_desc",
    "qms_applicable", "qms_desc",
    "similar_info", "labeling_info", "tech_file_info",
    "preclinical_info", "preclinical_replace",
    "clinical_just", "clinical_info",
]


def build_tw_app_dict_from_session() -> dict:
    s = st.session_state
    apply_date = s.get("tw_apply_date")
    apply_date_str = apply_date.strftime("%Y-%m-%d") if apply_date else ""
    return {
        "doc_no": s.get("tw_doc_no", ""),
        "e_no": s.get("tw_e_no", ""),
        "apply_date": apply_date_str,
        "case_type": s.get("tw_case_type", ""),
        "device_category": s.get("tw_device_category", ""),
        "case_kind": s.get("tw_case_kind", ""),
        "origin": s.get("tw_origin", ""),
        "product_class": s.get("tw_product_class", ""),
        "similar": s.get("tw_similar", ""),
        "replace_flag": s.get("tw_replace_flag", ""),
        "prior_app_no": s.get("tw_prior_app_no", ""),
        "name_zh": s.get("tw_dev_name_zh", ""),
        "name_en": s.get("tw_dev_name_en", ""),
        "indications": s.get("tw_indications", ""),
        "spec_comp": s.get("tw_spec_comp", ""),
        "main_cat": s.get("tw_main_cat", ""),
        "item_code": s.get("tw_item_code", ""),
        "item_name": s.get("tw_item_name", ""),
        "uniform_id": s.get("tw_uniform_id", ""),
        "firm_name": s.get("tw_firm_name", ""),
        "firm_addr": s.get("tw_firm_addr", ""),
        "resp_name": s.get("tw_resp_name", ""),
        "contact_name": s.get("tw_contact_name", ""),
        "contact_tel": s.get("tw_contact_tel", ""),
        "contact_fax": s.get("tw_contact_fax", ""),
        "contact_email": s.get("tw_contact_email", ""),
        "confirm_match": bool(s.get("tw_confirm_match", False)),
        "cert_raps": bool(s.get("tw_cert_raps", False)),
        "cert_ahwp": bool(s.get("tw_cert_ahwp", False)),
        "cert_other": s.get("tw_cert_other", ""),
        "manu_type": s.get("tw_manu_type", ""),
        "manu_name": s.get("tw_manu_name", ""),
        "manu_country": s.get("tw_manu_country", ""),
        "manu_addr": s.get("tw_manu_addr", ""),
        "manu_note": s.get("tw_manu_note", ""),
        "auth_applicable": s.get("tw_auth_app", ""),
        "auth_desc": s.get("tw_auth_desc", ""),
        "cfs_applicable": s.get("tw_cfs_app", ""),
        "cfs_desc": s.get("tw_cfs_desc", ""),
        "qms_applicable": s.get("tw_qms_app", ""),
        "qms_desc": s.get("tw_qms_desc", ""),
        "similar_info": s.get("tw_similar_info", ""),
        "labeling_info": s.get("tw_labeling_info", ""),
        "tech_file_info": s.get("tw_tech_file_info", ""),
        "preclinical_info": s.get("tw_preclinical_info", ""),
        "preclinical_replace": s.get("tw_preclinical_replace", ""),
        "clinical_just": s.get("tw_clinical_app", ""),
        "clinical_info": s.get("tw_clinical_info", ""),
    }


def apply_tw_app_dict_to_session(data: dict):
    s = st.session_state
    s["tw_doc_no"] = data.get("doc_no", "")
    s["tw_e_no"] = data.get("e_no", "")
    from datetime import date
    try:
        if data.get("apply_date"):
            y, m, d = map(int, str(data["apply_date"]).split("-"))
            s["tw_apply_date"] = date(y, m, d)
    except Exception:
        pass
    s["tw_case_type"] = data.get("case_type", "")
    s["tw_device_category"] = data.get("device_category", "")
    s["tw_case_kind"] = data.get("case_kind", "")
    s["tw_origin"] = data.get("origin", "")
    s["tw_product_class"] = data.get("product_class", "")
    s["tw_similar"] = data.get("similar", "")
    s["tw_replace_flag"] = data.get("replace_flag", "")
    s["tw_prior_app_no"] = data.get("prior_app_no", "")
    s["tw_dev_name_zh"] = data.get("name_zh", "")
    s["tw_dev_name_en"] = data.get("name_en", "")
    s["tw_indications"] = data.get("indications", "")
    s["tw_spec_comp"] = data.get("spec_comp", "")
    s["tw_main_cat"] = data.get("main_cat", "")
    s["tw_item_code"] = data.get("item_code", "")
    s["tw_item_name"] = data.get("item_name", "")
    s["tw_uniform_id"] = data.get("uniform_id", "")
    s["tw_firm_name"] = data.get("firm_name", "")
    s["tw_firm_addr"] = data.get("firm_addr", "")
    s["tw_resp_name"] = data.get("resp_name", "")
    s["tw_contact_name"] = data.get("contact_name", "")
    s["tw_contact_tel"] = data.get("contact_tel", "")
    s["tw_contact_fax"] = data.get("contact_fax", "")
    s["tw_contact_email"] = data.get("contact_email", "")
    s["tw_confirm_match"] = bool(data.get("confirm_match", False))
    s["tw_cert_raps"] = bool(data.get("cert_raps", False))
    s["tw_cert_ahwp"] = bool(data.get("cert_ahwp", False))
    s["tw_cert_other"] = data.get("cert_other", "")
    s["tw_manu_type"] = data.get("manu_type", "")
    s["tw_manu_name"] = data.get("manu_name", "")
    s["tw_manu_country"] = data.get("manu_country", "")
    s["tw_manu_addr"] = data.get("manu_addr", "")
    s["tw_manu_note"] = data.get("manu_note", "")
    s["tw_auth_app"] = data.get("auth_applicable", "")
    s["tw_auth_desc"] = data.get("auth_desc", "")
    s["tw_cfs_app"] = data.get("cfs_applicable", "")
    s["tw_cfs_desc"] = data.get("cfs_desc", "")
    s["tw_qms_app"] = data.get("qms_applicable", "")
    s["tw_qms_desc"] = data.get("qms_desc", "")
    s["tw_similar_info"] = data.get("similar_info", "")
    s["tw_labeling_info"] = data.get("labeling_info", "")
    s["tw_tech_file_info"] = data.get("tech_file_info", "")
    s["tw_preclinical_info"] = data.get("preclinical_info", "")
    s["tw_preclinical_replace"] = data.get("preclinical_replace", "")
    s["tw_clinical_app"] = data.get("clinical_just", "")
    s["tw_clinical_info"] = data.get("clinical_info", "")


def standardize_tw_app_info_with_llm(raw_obj) -> dict:
    api_keys = st.session_state.get("api_keys", {})
    model = "gemini-2.5-flash"
    if not (api_keys.get("gemini") or os.getenv("GEMINI_API_KEY")):
        raise RuntimeError("No Gemini API key available for standardizing application info.")

    raw_json = json.dumps(raw_obj, ensure_ascii=False, indent=2)
    fields_str = ", ".join(TW_APP_FIELDS)

    system_prompt = f"""
You are a data normalization assistant for a Taiwanese TFDA medical device premarket application.

Goal:
Map arbitrary JSON or CSV-like key/value structures into a STANDARD JSON object
that uses EXACTLY the following top-level keys (all strings except where noted):

{fields_str}

Rules:
- Output MUST be a single JSON object (no markdown, no comments).
- Every key above MUST appear in the JSON.
- If information for a field is clearly not present, set it to an empty string,
  or for boolean-like fields use `false`.
- Map semantically similar keys to the standard key names.
- `apply_date` should be string like 'YYYY-MM-DD' if you can infer; otherwise empty string.
- Do NOT invent new facts; just reorganize/rename what exists.
"""

    user_prompt = f"Here is the raw data to normalize:\n\n{raw_json}"

    out = call_llm(
        model=model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=4000,
        temperature=0.1,
        api_keys=api_keys,
    )

    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        start = out.find("{")
        end = out.rfind("}")
        if start != -1 and end != -1 and end > start:
            data = json.loads(out[start:end + 1])
        else:
            raise RuntimeError("LLM did not return valid JSON for application info.")

    if not isinstance(data, dict):
        raise RuntimeError("Standardized application info is not a JSON object.")

    for k in TW_APP_FIELDS:
        if k not in data:
            data[k] = "" if k not in ("confirm_match", "cert_raps", "cert_ahwp") else False
    return data


def compute_tw_app_completeness() -> float:
    s = st.session_state
    required_keys = [
        "tw_e_no", "tw_case_type", "tw_device_category",
        "tw_origin", "tw_product_class",
        "tw_dev_name_zh", "tw_dev_name_en",
        "tw_uniform_id", "tw_firm_name", "tw_firm_addr",
        "tw_resp_name", "tw_contact_name", "tw_contact_tel",
        "tw_contact_email",
        "tw_manu_name", "tw_manu_addr",
    ]
    filled = 0
    for k in required_keys:
        v = s.get(k, "")
        if isinstance(v, str):
            if v.strip():
                filled += 1
        else:
            if v:
                filled += 1
    return filled / len(required_keys) if required_keys else 0.0


# =========================
# TW Premarket Tab
# =========================

def render_tw_premarket_tab():
    st.title(t("TW Premarket"))
    st.markdown(
        """
        <div class="wow-card">
          <div style="font-weight:900;font-size:1.0rem;margin-bottom:6px;">WOW Guided Flow</div>
          <div style="opacity:0.92;line-height:1.5;">
            <b>Step 1.</b> 線上填寫或由 JSON/CSV 匯入申請主要欄位。<br>
            <b>Step 2.</b> 貼上或上傳預審/形式審查指引。<br>
            <b>Step 3.</b> 產出預審摘要報告（可編輯）。<br>
            <b>Step 4.</b> 以 AI 協助編修申請書內容，並可串到下一個 agent。
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### Application Info 匯入 / 匯出 (JSON / CSV)")
    col_ie1, col_ie2 = st.columns(2)
    with col_ie1:
        app_file = st.file_uploader(
            "Upload Application Info (JSON / CSV)",
            type=["json", "csv"],
            key="tw_app_upload",
        )
        if app_file is not None:
            try:
                if app_file.name.lower().endswith(".json"):
                    raw_data = json.load(app_file)
                else:
                    df = pd.read_csv(app_file)
                    if len(df) == 0:
                        st.error("CSV 檔案為空。")
                        raw_data = None
                    else:
                        raw_data = df.to_dict(orient="records")[0]

                if raw_data is not None:
                    if isinstance(raw_data, dict) and all(k in raw_data for k in TW_APP_FIELDS):
                        standardized = raw_data
                    else:
                        with st.spinner("使用 LLM 將欄位轉為標準 TFDA 申請書格式..."):
                            standardized = standardize_tw_app_info_with_llm(raw_data)

                    apply_tw_app_dict_to_session(standardized)
                    st.success("已將上傳資料轉換並套用至申請表單。")
                    st.session_state["tw_app_last_loaded"] = standardized
                    st.rerun()
            except Exception as e:
                st.error(f"上傳或標準化失敗：{e}")

    with col_ie2:
        app_dict = build_tw_app_dict_from_session()
        json_bytes = json.dumps(app_dict, ensure_ascii=False, indent=2).encode("utf-8")
        st.download_button(
            "Download JSON",
            data=json_bytes,
            file_name="tw_premarket_application.json",
            mime="application/json",
            key="tw_app_download_json",
        )
        df_app = pd.DataFrame([app_dict])
        csv_bytes = df_app.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download CSV",
            data=csv_bytes,
            file_name="tw_premarket_application.csv",
            mime="text/csv",
            key="tw_app_download_csv",
        )

    if "tw_app_last_loaded" in st.session_state:
        st.markdown("**最近載入/標準化之 Application JSON 預覽**")
        st.json(st.session_state["tw_app_last_loaded"], expanded=False)

    st.markdown("---")

    completeness = compute_tw_app_completeness()
    pct = int(completeness * 100)
    if pct >= 80:
        card_grad = "linear-gradient(135deg,#22c55e,#16a34a)"
        txt = "申請基本欄位完成度高，適合進行預審。"
    elif pct >= 50:
        card_grad = "linear-gradient(135deg,#f97316,#ea580c)"
        txt = "部分關鍵欄位仍待補齊，建議補足後再送預審。"
    else:
        card_grad = "linear-gradient(135deg,#ef4444,#b91c1c)"
        txt = "多數基本欄位尚未填寫，請先充實申請資訊。"

    st.markdown(
        f"""
        <div class="wow-card" style="background:{card_grad};border:0;color:white;">
          <div class="wow-card-title">APPLICATION COMPLETENESS</div>
          <div class="wow-card-main">{pct}%</div>
          <div style="margin-top:6px;font-size:0.95rem;opacity:0.95;">{txt}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.progress(completeness)

    # The remainder of TW Premarket UI is kept as original (feature parity)
    # ---- Original form content ----
    if "tw_app_status" not in st.session_state:
        st.session_state["tw_app_status"] = "pending"
    show_status("申請書填寫", st.session_state["tw_app_status"])

    st.markdown("### Step 1 – 線上填寫申請書（草稿）")
    st.markdown("#### 一、案件基本資料")
    col_a1, col_a2, col_a3 = st.columns(3)
    with col_a1:
        doc_no = st.text_input("公文文號", key="tw_doc_no")
        e_no = st.text_input("電子流水號", value=st.session_state.get("tw_e_no", "MDE"), key="tw_e_no")
    with col_a2:
        apply_date = st.date_input("申請日", key="tw_apply_date")
        case_type = st.selectbox(
            "案件類型*",
            ["一般申請案", "同一產品不同品名", "專供外銷", "許可證有效期限屆至後六個月內重新申請"],
            key="tw_case_type",
        )
    with col_a3:
        device_category = st.selectbox(
            "醫療器材類型*",
            ["一般醫材", "體外診斷器材(IVD)"],
            key="tw_device_category",
        )
        case_kind = st.selectbox("案件種類*", ["新案", "變更案", "展延案"], index=0, key="tw_case_kind")

    col_a4, col_a5, col_a6 = st.columns(3)
    with col_a4:
        origin = st.selectbox("產地*", ["國產", "輸入", "陸輸"], key="tw_origin")
    with col_a5:
        product_class = st.selectbox("產品等級*", ["第二等級", "第三等級"], key="tw_product_class")
    with col_a6:
        similar = st.selectbox("有無類似品*", ["有", "無", "全球首創"], key="tw_similar")

    col_a7, col_a8 = st.columns(2)
    with col_a7:
        replace_flag = st.radio(
            "是否勾選「替代臨床前測試及原廠品質管制資料」？*",
            ["否", "是"],
            index=0 if st.session_state.get("tw_replace_flag", "否") == "否" else 1,
            key="tw_replace_flag",
        )
    with col_a8:
        prior_app_no = st.text_input("（非首次申請）前次申請案號", key="tw_prior_app_no")

    st.markdown("#### 二、醫療器材基本資訊")
    col_b1, col_b2 = st.columns(2)
    with col_b1:
        name_zh = st.text_input("醫療器材中文名稱*", key="tw_dev_name_zh")
        name_en = st.text_input("醫療器材英文名稱*", key="tw_dev_name_en")
    with col_b2:
        indications = st.text_area("效能、用途或適應症說明", value=st.session_state.get("tw_indications", "詳如核定之中文說明書"), key="tw_indications")
        spec_comp = st.text_area("型號、規格或主要成分說明", value=st.session_state.get("tw_spec_comp", "詳如核定之中文說明書"), key="tw_spec_comp")

    st.markdown("**分類分級品項（依《醫療器材分類分級管理辦法》附表填列）**")
    col_b3, col_b4, col_b5 = st.columns(3)
    with col_b3:
        main_cat = st.selectbox(
            "主類別",
            [
                "",
                "A.臨床化學及臨床毒理學", "B.血液學及病理學", "C.免疫學及微生物學", "D.麻醉學",
                "E.心臟血管醫學", "F.牙科學", "G.耳鼻喉科學", "H.胃腸病科學及泌尿科學",
                "I.一般及整形外科手術", "J.一般醫院及個人使用裝置", "K.神經科學", "L.婦產科學",
                "M.眼科學", "N.骨科學", "O.物理醫學科學", "P.放射學科學",
            ],
            key="tw_main_cat",
        )
    with col_b4:
        item_code = st.text_input("分級品項代碼（例：A.1225）", key="tw_item_code")
    with col_b5:
        item_name = st.text_input("分級品項名稱（例：肌氨酸酐試驗系統）", key="tw_item_name")

    st.markdown("#### 三、醫療器材商資料")
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        uniform_id = st.text_input("統一編號*", key="tw_uniform_id")
        firm_name = st.text_input("醫療器材商名稱*", key="tw_firm_name")
        firm_addr = st.text_area("醫療器材商地址*", height=80, key="tw_firm_addr")
    with col_c2:
        resp_name = st.text_input("負責人姓名*", key="tw_resp_name")
        contact_name = st.text_input("聯絡人姓名*", key="tw_contact_name")
        contact_tel = st.text_input("電話*", key="tw_contact_tel")
        contact_fax = st.text_input("聯絡人傳真", key="tw_contact_fax")
        contact_email = st.text_input("電子郵件*", key="tw_contact_email")

    confirm_match = st.checkbox(
        "我已確認上述資料與最新版醫療器材商證照資訊(名稱、地址、負責人)相符",
        key="tw_confirm_match",
    )

    st.markdown("**其它佐證（承辦人訓練證明等）**")
    col_c3, col_c4 = st.columns(2)
    with col_c3:
        cert_raps = st.checkbox("RAPS", key="tw_cert_raps")
        cert_ahwp = st.checkbox("AHWP", key="tw_cert_ahwp")
    with col_c4:
        cert_other = st.text_input("其它，請敘明", key="tw_cert_other")

    st.markdown("#### 四、製造廠資訊（含委託製造）")
    manu_type = st.radio(
        "製造方式",
        ["單一製造廠", "全部製程委託製造", "委託非全部製程之製造/包裝/貼標/滅菌及最終驗放"],
        index=0,
        key="tw_manu_type",
    )
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        manu_name = st.text_input("製造廠名稱*", key="tw_manu_name")
        manu_country = st.selectbox(
            "製造國別*",
            ["TAIWAN， ROC", "UNITED STATES", "EU (Member State)", "JAPAN", "CHINA", "KOREA， REPUBLIC OF", "OTHER"],
            key="tw_manu_country",
        )
    with col_d2:
        manu_addr = st.text_area("製造廠地址*", height=80, key="tw_manu_addr")
        manu_note = st.text_area("製造廠相關說明（如(O)/(P)製造、委託範圍）", height=80, key="tw_manu_note")

    with st.expander("附件摘要：原廠授權、出產國製售證明、QMS/QSD、技術檔案、臨床資料等", expanded=False):
        auth_applicable = st.selectbox("原廠授權登記書", ["不適用", "適用"], key="tw_auth_app")
        auth_desc = st.text_area("原廠授權登記書資料說明", height=80, key="tw_auth_desc")

        cfs_applicable = st.selectbox("出產國製售證明", ["不適用", "適用"], key="tw_cfs_app")
        cfs_desc = st.text_area("出產國製售證明資料說明", height=80, key="tw_cfs_desc")

        qms_applicable = st.selectbox("QMS/QSD", ["不適用", "適用"], key="tw_qms_app")
        qms_desc = st.text_area("QMS/QSD 資料說明（含案號、登錄狀態）", height=80, key="tw_qms_desc")

        similar_info = st.text_area("類似品與比較表摘要（如無類似品則說明理由）", height=80, key="tw_similar_info")
        labeling_info = st.text_area("標籤、說明書或包裝擬稿重點", height=100, key="tw_labeling_info")
        tech_file_info = st.text_area("產品結構、材料、規格、性能、用途、圖樣等技術檔案摘要", height=120, key="tw_tech_file_info")
        preclinical_info = st.text_area("臨床前測試 & 原廠品質管制檢驗摘要（生物相容性、電氣安全、EMC、滅菌、安定性、功能測試、軟體確效等）", height=140, key="tw_preclinical_info")
        preclinical_replace = st.text_area("如本案適用「替代臨床前測試及原廠品質管制資料」之說明", height=100, key="tw_preclinical_replace")
        clinical_just = st.selectbox("臨床證據是否適用？", ["不適用", "適用"], key="tw_clinical_app")
        clinical_info = st.text_area("臨床證據摘要（研究報告、臨床評估、臨床試驗、FDA/歐盟核定資料等）", height=140, key="tw_clinical_info")

    if st.button("生成申請書 Markdown 草稿", key="tw_generate_md_btn"):
        missing = []
        def _miss(label, val): 
            if not str(val or "").strip(): missing.append(label)

        _miss("電子流水號", e_no)
        _miss("案件類型", case_type)
        _miss("醫療器材類型", device_category)
        _miss("產地", origin)
        _miss("產品等級", product_class)
        _miss("醫療器材中文名稱", name_zh)
        _miss("醫療器材英文名稱", name_en)
        _miss("統一編號", uniform_id)
        _miss("醫療器材商名稱", firm_name)
        _miss("醫療器材商地址", firm_addr)
        _miss("負責人姓名", resp_name)
        _miss("聯絡人姓名", contact_name)
        _miss("電話", contact_tel)
        _miss("電子郵件", contact_email)
        _miss("製造廠名稱", manu_name)
        _miss("製造廠地址", manu_addr)

        if missing:
            st.warning("以下基本欄位尚未填寫完整（形式檢查）：\n- " + "\n- ".join(missing))
            st.session_state["tw_app_status"] = "error"
        else:
            st.session_state["tw_app_status"] = "done"

        apply_date_str = apply_date.strftime("%Y-%m-%d") if apply_date else ""

        app_md = f"""# 第二、三等級醫療器材查驗登記申請書（線上草稿）

## 一、案件基本資料
- 公文文號：{doc_no or "（未填）"}
- 電子流水號：{e_no or "（未填）"}
- 申請日：{apply_date_str or "（未填）"}
- 案件類型：{case_type}
- 醫療器材類型：{device_category}
- 案件種類：{case_kind}
- 產地：{origin}
- 產品等級：{product_class}
- 有無類似品：{similar}
- 是否勾選「替代臨床前測試及原廠品質管制資料」：{replace_flag}
- 前次申請案號（如適用）：{prior_app_no or "不適用"}

## 二、醫療器材基本資訊
- 中文名稱：{name_zh}
- 英文名稱：{name_en}
- 效能、用途或適應症說明：{indications}
- 型號、規格或主要成分：{spec_comp}

### 分類分級品項
- 主類別：{main_cat or "（未填）"}
- 分級品項代碼：{item_code or "（未填）"}
- 分級品項名稱：{item_name or "（未填）"}

## 三、醫療器材商資料
- 統一編號：{uniform_id}
- 醫療器材商名稱：{firm_name}
- 地址：{firm_addr}
- 負責人姓名：{resp_name}
- 聯絡人姓名：{contact_name}
- 電話：{contact_tel}
- 傳真：{contact_fax or "（未填）"}
- 電子郵件：{contact_email}
- 已確認與最新醫療器材商證照資訊相符：{"是" if confirm_match else "否"}

### 其它佐證
- RAPS：{"有" if cert_raps else "無"}
- AHWP：{"有" if cert_ahwp else "無"}
- 其它訓練/證書：{cert_other or "無"}

## 四、製造廠資訊
- 製造方式：{manu_type}
- 製造廠名稱：{manu_name}
- 製造國別：{manu_country}
- 製造廠地址：{manu_addr}
- 製造相關說明：{manu_note or "（未填）"}

## 五～七、原廠授權、出產國製售證明、QMS/QSD
- 原廠授權登記書適用性：{auth_applicable}
- 原廠授權登記書資料說明：{auth_desc or "（未填）"}
- 出產國製售證明適用性：{cfs_applicable}
- 出產國製售證明資料說明：{cfs_desc or "（未填）"}
- QMS/QSD 適用性：{qms_applicable}
- QMS/QSD 資料說明：{qms_desc or "（未填）"}

## 十～十二、類似品、標籤/說明書擬稿、產品技術檔案摘要
### 類似品相關資訊
{similar_info or "（未填）"}

### 標籤／說明書／包裝擬稿重點
{labeling_info or "（未填）"}

### 產品結構、材料、規格、性能、用途、圖樣等技術檔案摘要
{tech_file_info or "（未填）"}

## 十三～十七、特定安全性要求與臨床前測試及品質管制資料
### 臨床前測試與原廠品質管制資料摘要
{preclinical_info or "（未填）"}

### 替代「臨床前測試及原廠品質管制資料」之說明
{preclinical_replace or "（未填）"}

## 十八、臨床證據資料
- 臨床證據適用性：{clinical_just}
- 臨床證據摘要：
{clinical_info or "（未填）"}
"""
        st.session_state["tw_app_markdown"] = app_md

    st.markdown("##### 申請書 Markdown（可編輯）")
    app_md_current = st.session_state.get("tw_app_markdown", "")
    app_view_mode = st.radio("申請書檢視模式", ["Markdown", "純文字"], horizontal=True, key="tw_app_viewmode")
    app_md_edited = st.text_area("申請書內容", value=app_md_current, height=320, key="tw_app_md_edited")
    st.session_state["tw_app_effective_md"] = app_md_edited

    st.markdown("---")
    st.markdown("### Step 2 – 輸入預審/形式審查指引（Screen Review Guidance）")

    col_g1, col_g2 = st.columns(2)
    with col_g1:
        guidance_file = st.file_uploader("上傳預審指引 (PDF / TXT / MD)", type=["pdf", "txt", "md"], key="tw_guidance_file")
        guidance_text_from_file = ""
        if guidance_file is not None:
            suffix = guidance_file.name.lower().rsplit(".", 1)[-1]
            if suffix == "pdf":
                guidance_text_from_file = extract_pdf_pages_to_text(guidance_file, 1, 9999)
            else:
                guidance_text_from_file = guidance_file.read().decode("utf-8", errors="ignore")
    with col_g2:
        guidance_text_manual = st.text_area("或直接貼上預審/形式審查指引文字或 Markdown", height=200, key="tw_guidance_manual")

    guidance_text = guidance_text_from_file or guidance_text_manual
    st.session_state["tw_guidance_text"] = guidance_text

    if guidance_text:
        st.success("已載入預審/形式審查指引文字。")
    else:
        st.info("尚未提供預審指引。可先填寫申請書草稿，稍後再補。")

    st.markdown("---")
    st.markdown("### Step 3 – 形式審查 / 完整性檢核（Agent）")

    if not st.session_state.get("tw_app_effective_md", "").strip():
        st.warning("尚未產生申請書 Markdown。請先於 Step 1 填寫並點擊「生成申請書 Markdown 草稿」。")
        return

    base_app_md = st.session_state.get("tw_app_effective_md", "")
    base_guidance = st.session_state.get("tw_guidance_text", "")

    combined_input = f"""=== 申請書草稿（Markdown） ===
{base_app_md}

=== 預審 / 形式審查指引（文字/Markdown） ===
{base_guidance or "（尚未提供指引，請依一般法規常規進行形式檢核）"}
"""

    default_screen_prompt = """你是一位熟悉臺灣「第二、三等級醫療器材查驗登記」的形式審查(預審)審查員。

請根據：
1. 上述「申請書草稿（Markdown）」內容
2. 上述「預審 / 形式審查指引」(如有)

執行下列任務，並以 **繁體中文 Markdown** 輸出預審報告：

1. 形式完整性檢核（表格）
2. 重要欄位檢核（問題項目/疑慮/建議補充）
3. 預審評語摘要（300–600 字）
4. 避免臆測；無從判斷請註記「依現有輸入無法判斷」
"""

    agent_run_ui(
        agent_id="tw_screen_review_agent",
        tab_key="tw_screen",
        default_prompt=default_screen_prompt,
        default_input_text=combined_input,
        allow_model_override=True,
        tab_label_for_history="TW Premarket Screen Review",
    )

    st.markdown("---")
    st.markdown("### Step 4 – AI 協助編修申請書內容")

    helper_default_prompt = """你是一位協助臺灣醫療器材查驗登記申請人的文件撰寫助手。

請在 **不改變實際技術與法規內容** 的前提下，針對以下「申請書草稿（Markdown）」：
1. 優化段落結構與標題層級
2. 修正文句語病（不得新增不存在的重要資訊）
3. 資訊不足請以「※待補：...」標註
4. 保持輸出為 Markdown
"""
    agent_run_ui(
        agent_id="tw_app_doc_helper",
        tab_key="tw_app_helper",
        default_prompt=helper_default_prompt,
        default_input_text=st.session_state.get("tw_app_effective_md", ""),
        allow_model_override=True,
        tab_label_for_history="TW Application Doc Helper",
    )


# =========================
# 510(k) Tab
# =========================

def render_510k_tab():
    st.title(t("510k_tab"))
    col1, col2 = st.columns(2)
    with col1:
        device_name = st.text_input("Device Name")
        k_number = st.text_input("510(k) Number (e.g., K123456)")
    with col2:
        sponsor = st.text_input("Sponsor / Manufacturer (optional)")
        product_code = st.text_input("Product Code (optional)")
    extra_info = st.text_area("Additional context (indications, technology, etc.)")

    default_prompt = f"""
You are assisting an FDA 510(k) reviewer.

Task:
1. Summarize the publicly available information (or emulate such) for:
   - Device: {device_name}
   - 510(k) number: {k_number}
   - Sponsor: {sponsor}
   - Product code: {product_code}
2. Produce a detailed, review-oriented summary (about 2000–3000 words).
3. Provide several markdown tables (e.g., device overview, indications, performance testing, risks).

Language: {st.session_state.settings["language"]}.
"""
    combined_input = f"""
=== Device Inputs ===
Device name: {device_name}
510(k) number: {k_number}
Sponsor: {sponsor}
Product code: {product_code}

Additional context:
{extra_info}
"""
    agent_run_ui(
        agent_id="fda_510k_intel_agent",
        tab_key="510k",
        default_prompt=default_prompt,
        default_input_text=combined_input,
        tab_label_for_history="510(k) Intelligence",
    )


# =========================
# PDF → Markdown Tab
# =========================

def render_pdf_to_md_tab():
    st.title(t("PDF → Markdown"))

    uploaded = st.file_uploader(
        "Upload PDF to convert selected pages to Markdown",
        type=["pdf"],
        key="pdf_to_md_uploader",
    )
    if uploaded:
        col1, col2 = st.columns(2)
        with col1:
            num_start = st.number_input("From page", min_value=1, value=1, key="pdf_to_md_from")
        with col2:
            num_end = st.number_input("To page", min_value=1, value=5, key="pdf_to_md_to")

        if st.button("Extract Text", key="pdf_to_md_extract_btn"):
            text = extract_pdf_pages_to_text(uploaded, int(num_start), int(num_end))
            st.session_state["pdf_raw_text"] = text

    raw_text = st.session_state.get("pdf_raw_text", "")
    if raw_text:
        default_prompt = f"""
You are converting part of a regulatory PDF into markdown.

- Goal: produce clean, structured markdown preserving headings, lists,
  and tables (as markdown tables) as much as reasonably possible.
- Do not hallucinate content that is not in the text.

Language: {st.session_state.settings["language"]}.
"""
        agent_run_ui(
            agent_id="pdf_to_markdown_agent",
            tab_key="pdf_to_md",
            default_prompt=default_prompt,
            default_input_text=raw_text,
            tab_label_for_history="PDF → Markdown",
        )
    else:
        st.info("Upload a PDF and click 'Extract Text' to begin.")


# =========================
# 510(k) Review Pipeline Tab
# =========================

def render_510k_review_pipeline_tab():
    st.title(t("Checklist & Report"))

    st.markdown("### Step 1 – 提交資料 → 結構化 Markdown")
    raw_subm = st.text_area(
        "Paste 510(k) submission material (text/markdown)",
        height=200,
        key="subm_paste",
    )
    default_subm_prompt = """You are a 510(k) submission organizer.

Restructure the following content into organized markdown with sections such as:
- Device & submitter information
- Device description and technology
- Indications for use
- Predicate/comparator information
- Performance testing
- Risks and risk controls

Do not invent new facts; only reorganize and clarify.
"""
    if st.button("Structure Submission", key="subm_run_btn"):
        if not raw_subm.strip():
            st.warning("Please paste submission material first.")
        else:
            api_keys = st.session_state.get("api_keys", {})
            try:
                out = call_llm(
                    model=st.session_state.settings["model"],
                    system_prompt="You structure a 510(k) submission.",
                    user_prompt=default_subm_prompt + "\n\n=== SUBMISSION ===\n" + raw_subm,
                    max_tokens=st.session_state.settings["max_tokens"],
                    temperature=0.15,
                    api_keys=api_keys,
                )
                st.session_state["subm_struct_md"] = out
                token_est = int(len(raw_subm + out) / 4)
                log_event("510(k) Review Pipeline", "Submission Structurer", st.session_state.settings["model"], token_est)
            except Exception as e:
                st.error(f"Error: {e}")

    subm_md = st.session_state.get("subm_struct_md", "")
    if subm_md:
        st.markdown("#### Structured Submission (editable)")
        st.text_area("Submission (Markdown)", value=subm_md, height=220, key="subm_struct_md_edited")
    else:
        st.info("Structured submission will appear here.")

    st.markdown("---")
    st.markdown("### Step 2 – Checklist & Step 3 – Review Report")

    chk_md = st.text_area("Paste checklist (markdown or text)", height=200, key="chk_md")

    if st.button("Build Review Report", key="rep_run_btn"):
        if not subm_md or not chk_md.strip():
            st.warning("Need both structured submission and checklist.")
        else:
            api_keys = st.session_state.get("api_keys", {})
            rep_prompt = """You are drafting an internal FDA 510(k) review memo.

Using the checklist and structured submission, write a concise review report with:
- Introduction & scope
- Device and submission overview
- Summary of key differences vs. predicate(s)
- Checklist-based assessment (use headings or tables)
- Overall conclusion and recommendations.
"""
            user_prompt = rep_prompt + "\n\n=== CHECKLIST ===\n" + chk_md + "\n\n=== STRUCTURED SUBMISSION ===\n" + subm_md
            try:
                out = call_llm(
                    model=st.session_state.settings["model"],
                    system_prompt="You are an FDA 510(k) reviewer.",
                    user_prompt=user_prompt,
                    max_tokens=st.session_state.settings["max_tokens"],
                    temperature=0.18,
                    api_keys=api_keys,
                )
                st.session_state["rep_md"] = out
                token_est = int(len(user_prompt + out) / 4)
                log_event("510(k) Review Pipeline", "Review Memo Builder", st.session_state.settings["model"], token_est)
            except Exception as e:
                st.error(f"Error: {e}")

    rep_md = st.session_state.get("rep_md", "")
    if rep_md:
        st.markdown("#### Review Report (editable)")
        st.text_area("Review Report (Markdown)", value=rep_md, height=260, key="rep_md_edited")


# =========================
# Note Keeper & Magics
# =========================

def highlight_keywords(text: str, keywords: list[str], color: str) -> str:
    if not text or not keywords:
        return text
    out = text
    for kw in sorted(set([k for k in keywords if k.strip()]), key=len, reverse=True):
        safe_kw = kw.strip()
        if not safe_kw:
            continue
        span = f'<span style="color:{color};font-weight:800;">{safe_kw}</span>'
        out = out.replace(safe_kw, span)
    return out


def render_note_keeper_tab():
    st.title(t("Note Keeper & Magics"))

    st.markdown("### Step 1 – Paste Notes & Transform to Structured Markdown")
    raw_notes = st.text_area("Paste your notes (text or markdown)", height=220, key="notes_raw")

    col_n1, col_n2 = st.columns(2)
    with col_n1:
        note_model = st.selectbox(
            "Model for Note → Markdown",
            ALL_MODELS,
            index=ALL_MODELS.index(st.session_state.settings["model"]) if st.session_state.settings["model"] in ALL_MODELS else 0,
            key="note_model",
        )
    with col_n2:
        note_max_tokens = st.number_input(
            "max_tokens",
            min_value=2000,
            max_value=120000,
            value=12000,
            step=1000,
            key="note_max_tokens",
        )

    default_note_prompt = """你是一位協助醫療器材/510(k)/TFDA 審查員整理個人筆記的助手。

請將下列雜亂或半結構化的筆記，整理成：
1. 清晰的 Markdown 結構（標題、子標題、條列）。
2. 保留所有技術與法規重點，不要憑空新增內容。
3. 顯示出：關鍵技術要點、主要風險與疑問、待釐清/追問事項
"""
    note_struct_prompt = st.text_area("Prompt for Note → Markdown", value=default_note_prompt, height=180, key="note_struct_prompt")

    if st.button("Transform notes to structured Markdown", key="note_run_btn"):
        if not raw_notes.strip():
            st.warning("Please paste notes first.")
        else:
            api_keys = st.session_state.get("api_keys", {})
            user_prompt = note_struct_prompt + "\n\n=== RAW NOTES ===\n" + raw_notes
            try:
                out = call_llm(
                    model=note_model,
                    system_prompt="You organize reviewer's notes into clean markdown.",
                    user_prompt=user_prompt,
                    max_tokens=note_max_tokens,
                    temperature=0.15,
                    api_keys=api_keys,
                )
                st.session_state["note_md"] = out
                token_est = int(len(user_prompt + out) / 4)
                log_event("Note Keeper", "Note Structurer", note_model, token_est)
            except Exception as e:
                st.error(f"Error: {e}")

    note_md = st.session_state.get("note_md", raw_notes)
    st.markdown("#### Structured Note (editable)")
    note_view = st.radio("View mode for base note", ["Markdown", "Plain text"], horizontal=True, key="note_view_mode")
    note_md_edited = st.text_area("Note (editable)", value=note_md, height=260, key="note_md_edited")
    st.session_state["note_effective"] = note_md_edited
    base_note = st.session_state.get("note_effective", "")

    # Magic 1 – AI Formatting
    st.markdown("---")
    st.markdown("### Magic 1 – AI Formatting")
    fmt_model = st.selectbox("Model (Formatting)", ALL_MODELS, index=ALL_MODELS.index(st.session_state.settings["model"]) if st.session_state.settings["model"] in ALL_MODELS else 0, key="fmt_model")
    fmt_prompt = st.text_area("Prompt for AI Formatting", value="請在不改變內容的前提下，統一標題層級與條列格式，讓此筆記更易讀（輸出 Markdown）。", height=120, key="fmt_prompt")

    if st.button("Run AI Formatting", key="fmt_run_btn"):
        if not base_note.strip():
            st.warning("No base note available.")
        else:
            api_keys = st.session_state.get("api_keys", {})
            user_prompt = fmt_prompt + "\n\n=== NOTE ===\n" + base_note
            try:
                out = call_llm(fmt_model, "You are a formatting-only assistant for markdown notes.", user_prompt, 12000, 0.1, api_keys)
                st.session_state["fmt_note"] = out
                log_event("Note Keeper", "AI Formatting", fmt_model, int(len(user_prompt + out) / 4))
            except Exception as e:
                st.error(f"Error: {e}")

    fmt_note = st.session_state.get("fmt_note", "")
    if fmt_note:
        st.text_area("Formatted Note (Markdown)", value=fmt_note, height=220, key="fmt_note_edited")

    # Magic 2 – AI Keywords (Manual highlight)
    st.markdown("---")
    st.markdown("### Magic 2 – AI Keywords (Manual highlight)")
    kw_input = st.text_input("Keywords (comma-separated)", key="kw_input", value="510(k), TFDA, QMS, biocompatibility")
    kw_color = st.color_picker("Color for keywords", "#ff7f50", key="kw_color")

    if st.button("Apply Keyword Highlighting", key="kw_run_btn"):
        if not base_note.strip():
            st.warning("No base note available.")
        else:
            keywords = [k.strip() for k in kw_input.split(",") if k.strip()]
            st.session_state["kw_note"] = highlight_keywords(base_note, keywords, kw_color)

    kw_note = st.session_state.get("kw_note", "")
    if kw_note:
        st.markdown("#### Note with Highlighted Keywords (Markdown rendering)")
        st.markdown(kw_note, unsafe_allow_html=True)

    # Magic 3 – AI Summary
    st.markdown("---")
    st.markdown("### Magic 3 – AI Summary")
    sum_model = st.selectbox("Model (Summary)", ALL_MODELS, index=ALL_MODELS.index("gpt-4o-mini") if "gpt-4o-mini" in ALL_MODELS else 0, key="note_sum_model")
    sum_prompt = st.text_area("Prompt for Summary", value="請將以下審查筆記摘要為 5–10 個重點 bullet，並附上一段 3–5 句的整體摘要（使用繁體中文）。", height=150, key="note_sum_prompt")
    if st.button("Run AI Summary", key="note_sum_run_btn"):
        if not base_note.strip():
            st.warning("No base note available.")
        else:
            api_keys = st.session_state.get("api_keys", {})
            user_prompt = sum_prompt + "\n\n=== NOTE ===\n" + base_note
            try:
                out = call_llm(sum_model, "You write executive-style regulatory summaries.", user_prompt, 12000, 0.2, api_keys)
                st.session_state["note_summary"] = out
                log_event("Note Keeper", "AI Summary", sum_model, int(len(user_prompt + out) / 4))
            except Exception as e:
                st.error(f"Error: {e}")

    note_summary = st.session_state.get("note_summary", "")
    if note_summary:
        st.text_area("Summary", value=note_summary, height=200, key="note_summary_edited")

    # Magic 4 – AI Action Items
    st.markdown("---")
    st.markdown("### Magic 4 – AI Action Items")
    act_model = st.selectbox("Model (Action Items)", ALL_MODELS, index=ALL_MODELS.index(st.session_state.settings["model"]) if st.session_state.settings["model"] in ALL_MODELS else 0, key="note_act_model")
    act_prompt = st.text_area("Prompt for Action Items", value="請從以下筆記中萃取需要後續行動的事項（補件、澄清、內部會議等），並以 Markdown 表格輸出：項目、負責人(可留空)、優先順序、說明。", height=150, key="note_act_prompt")
    if st.button("Run AI Action Items", key="note_act_run_btn"):
        if not base_note.strip():
            st.warning("No base note available.")
        else:
            api_keys = st.session_state.get("api_keys", {})
            user_prompt = act_prompt + "\n\n=== NOTE ===\n" + base_note
            try:
                out = call_llm(act_model, "You extract action items from regulatory review notes.", user_prompt, 12000, 0.2, api_keys)
                st.session_state["note_actions"] = out
                log_event("Note Keeper", "AI Action Items", act_model, int(len(user_prompt + out) / 4))
            except Exception as e:
                st.error(f"Error: {e}")

    note_actions = st.session_state.get("note_actions", "")
    if note_actions:
        st.text_area("Action Items", value=note_actions, height=220, key="note_actions_edited")

    # Magic 5 – AI Glossary
    st.markdown("---")
    st.markdown("### Magic 5 – AI Glossary (術語表)")
    glo_model = st.selectbox("Model (Glossary)", ALL_MODELS, index=ALL_MODELS.index("gemini-2.5-flash") if "gemini-2.5-flash" in ALL_MODELS else 0, key="note_glo_model")
    glo_prompt = st.text_area("Prompt for Glossary", value="請從以下筆記中找出重要專有名詞 (英文縮寫、標準、指引文件名稱、專業術語)，製作 Markdown 表格：Term, Full Name/Chinese, Explanation。", height=150, key="note_glo_prompt")
    if st.button("Run AI Glossary", key="note_glo_run_btn"):
        if not base_note.strip():
            st.warning("No base note available.")
        else:
            api_keys = st.session_state.get("api_keys", {})
            user_prompt = glo_prompt + "\n\n=== NOTE ===\n" + base_note
            try:
                out = call_llm(glo_model, "You build glossaries for regulatory/technical notes.", user_prompt, 12000, 0.2, api_keys)
                st.session_state["note_glossary"] = out
                log_event("Note Keeper", "AI Glossary", glo_model, int(len(user_prompt + out) / 4))
            except Exception as e:
                st.error(f"Error: {e}")

    note_glossary = st.session_state.get("note_glossary", "")
    if note_glossary:
        st.text_area("Glossary", value=note_glossary, height=220, key="note_glossary_edited")


# =========================
# NEW: Agent Workflow Studio (chaining step-by-step)
# =========================

def _get_agents_for_picker():
    agents_cfg = st.session_state.get("agents_cfg", {})
    agents_dict = agents_cfg.get("agents", {}) or {}
    items = []
    for aid, acfg in agents_dict.items():
        name = acfg.get("name", aid)
        items.append((aid, name))
    items.sort(key=lambda x: x[1].lower())
    return items


def render_agent_workflow_studio_tab():
    st.title(t("Agent Workflow Studio"))
    st.markdown(
        """
        <div class="wow-card">
          <div style="font-weight:900;margin-bottom:6px;">WOW Chain Mode</div>
          <div style="opacity:0.92;line-height:1.5;">
            Build a step-by-step pipeline. You can edit each agent’s prompt/model/max_tokens before running,
            and you can edit each output as the input to the next step.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if "workflow_steps" not in st.session_state:
        st.session_state["workflow_steps"] = []

    agents_items = _get_agents_for_picker()
    if not agents_items:
        st.warning("No agents found in agents.yaml. Upload one in sidebar or Agents Config tab.")
        return

    colw1, colw2, colw3 = st.columns([2, 1, 1])
    with colw1:
        selected_agent = st.selectbox(
            "Add agent step",
            options=[a for a, _ in agents_items],
            format_func=lambda x: dict(agents_items).get(x, x),
            key="workflow_add_agent",
        )
    with colw2:
        if st.button("Add Step", key="workflow_add_step_btn"):
            st.session_state["workflow_steps"].append(
                {
                    "id": str(uuid.uuid4()),
                    "agent_id": selected_agent,
                    "prompt": "",
                    "model": "",
                    "max_tokens": 12000,
                    "input": "",
                    "output": "",
                    "status": "pending",
                }
            )
            st.rerun()
    with colw3:
        if st.button("Reset Workflow", key="workflow_reset_btn"):
            st.session_state["workflow_steps"] = []
            st.rerun()

    steps = st.session_state["workflow_steps"]
    if not steps:
        st.info("Add steps to begin.")
        return

    agents_dict = (st.session_state.get("agents_cfg", {}) or {}).get("agents", {}) or {}

    for idx, step in enumerate(steps):
        aid = step["agent_id"]
        acfg = agents_dict.get(aid, {})
        name = acfg.get("name", aid)

        st.markdown(f"## Step {idx+1}: {name}")

        show_status(
            f"Step {idx+1} – {name}",
            step.get("status", "pending"),
            right_text=f"Model: {step.get('model') or acfg.get('model') or st.session_state.settings['model']}",
        )

        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            default_prompt = step["prompt"] or f"(You can edit) Default goal: run agent {aid}."
            step["prompt"] = st.text_area(
                f"Prompt (Step {idx+1})",
                value=default_prompt,
                height=120,
                key=f"wf_prompt_{step['id']}",
            )
        with col2:
            base_model = step["model"] or acfg.get("model") or st.session_state.settings["model"]
            model_list = list(dict.fromkeys(ALL_MODELS + [base_model]))
            step["model"] = st.selectbox(
                f"Model (Step {idx+1})",
                model_list,
                index=model_list.index(base_model) if base_model in model_list else 0,
                key=f"wf_model_{step['id']}",
            )
        with col3:
            step["max_tokens"] = st.number_input(
                f"max_tokens (Step {idx+1})",
                min_value=1000,
                max_value=120000,
                value=int(step.get("max_tokens") or acfg.get("max_tokens") or 12000),
                step=1000,
                key=f"wf_maxtok_{step['id']}",
            )

        # Default chaining: input = previous output if empty
        if idx > 0 and not step.get("input", "").strip():
            prev_out = steps[idx - 1].get("output", "")
            if prev_out:
                step["input"] = prev_out

        step["input"] = st.text_area(
            f"Input (Step {idx+1})",
            value=step.get("input", ""),
            height=180,
            key=f"wf_input_{step['id']}",
        )

        colr1, colr2, colr3 = st.columns([1, 1, 2])
        with colr1:
            if st.button(f"Run Step {idx+1}", key=f"wf_run_{step['id']}"):
                step["status"] = "running"
                wow_set_run_state("running", label=f"Workflow · Step {idx+1} · {name}")
                st.rerun()
        with colr2:
            if st.button(f"Delete Step {idx+1}", key=f"wf_del_{step['id']}"):
                st.session_state["workflow_steps"] = [s for s in steps if s["id"] != step["id"]]
                st.rerun()
        with colr3:
            st.caption("Tip: Edit output below; it becomes the next step’s default input.")

        if step.get("status") == "running":
            api_keys = st.session_state.get("api_keys", {})
            sys_prompt = acfg.get("system_prompt", "")
            user_full = f"{step['prompt']}\n\n---\n\n{step['input']}"
            try:
                with st.spinner(f"Running Step {idx+1}..."):
                    out = call_llm(
                        model=step["model"],
                        system_prompt=sys_prompt,
                        user_prompt=user_full,
                        max_tokens=int(step["max_tokens"]),
                        temperature=st.session_state.settings["temperature"],
                        api_keys=api_keys,
                    )
                step["output"] = out
                step["status"] = "done"
                wow_set_run_state("done", label=f"Workflow · Step {idx+1} · {name}")
                log_event("Agent Workflow Studio", f"Workflow Step {idx+1}: {name}", step["model"], int(len(user_full + out) / 4))
                st.rerun()
            except Exception as e:
                step["status"] = "error"
                wow_set_run_state("error", label=f"Workflow · Step {idx+1}", error=str(e))
                st.error(f"Step {idx+1} error: {e}")

        step["output"] = st.text_area(
            f"Output (editable, Step {idx+1})",
            value=step.get("output", ""),
            height=220,
            key=f"wf_out_{step['id']}",
        )

    st.session_state["workflow_steps"] = steps


# =========================
# NEW: WOW AI Lab (3 additional AI features)
# =========================

def render_wow_ai_lab_tab():
    st.title(t("WOW AI Lab"))
    st.markdown(
        """
        <div class="wow-card">
          <div style="font-weight:900;margin-bottom:6px;">3 New AI Features</div>
          <div style="opacity:0.92;line-height:1.5;">
            1) Requirement→Evidence Traceability Matrix<br>
            2) Risk Register Builder (hazards, harms, mitigations, verification)<br>
            3) Change Log Generator (compare two versions and summarize changes)
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("## Feature 1 — Requirement → Evidence Traceability Matrix")
    req_text = st.text_area("Requirements / Checklist (paste)", height=180, key="lab_req")
    ev_text = st.text_area("Evidence / Submission excerpts (paste)", height=180, key="lab_ev")

    default_prompt_trace = """You are building a regulatory traceability matrix.

Input:
- Requirements / checklist text
- Evidence / submission text

Output (Markdown):
- A traceability table with columns:
  Requirement ID/Statement | Evidence location/quote | Coverage (Full/Partial/None) | Gap description | Follow-up question
- Do not invent evidence. If not found, mark Coverage=None and explain the gap.
"""
    combined_trace_input = f"=== REQUIREMENTS ===\n{req_text}\n\n=== EVIDENCE ===\n{ev_text}"
    agent_run_ui(
        agent_id="traceability_matrix_agent",
        tab_key="lab_trace",
        default_prompt=default_prompt_trace,
        default_input_text=combined_trace_input,
        allow_model_override=True,
        tab_label_for_history="WOW AI Lab · Traceability Matrix",
    )

    st.markdown("---")
    st.markdown("## Feature 2 — Risk Register Builder")
    risk_in = st.text_area("Paste device description / intended use / key tech / hazards (any)", height=220, key="lab_risk_in")

    default_prompt_risk = """You are a medical device risk management assistant (ISO 14971 style).

From the input text, produce a Risk Register in Markdown table with columns:
Hazard | Foreseeable sequence of events | Harm | Severity (Low/Med/High) | Probability (Low/Med/High) |
Risk control (mitigation) | Verification/Validation evidence needed | Residual risk note

Rules:
- Do not fabricate device facts; only infer generic hazards when clearly applicable from the input.
- If uncertain, label as "Needs confirmation".
"""
    agent_run_ui(
        agent_id="risk_register_agent",
        tab_key="lab_risk",
        default_prompt=default_prompt_risk,
        default_input_text=risk_in,
        allow_model_override=True,
        tab_label_for_history="WOW AI Lab · Risk Register",
    )

    st.markdown("---")
    st.markdown("## Feature 3 — Change Log Generator (Compare two versions)")
    colc1, colc2 = st.columns(2)
    with colc1:
        old_v = st.text_area("Old version (markdown/text)", height=220, key="lab_old")
    with colc2:
        new_v = st.text_area("New version (markdown/text)", height=220, key="lab_new")

    default_prompt_changelog = """You are a documentation change reviewer.

Compare OLD vs NEW and output Markdown:
1) Executive change summary (5–12 bullets)
2) Risky changes / compliance-impacting changes (if any)
3) Section-by-section diff narrative (not a raw diff)
4) Suggested commit message / change note
If content is identical, say so.
"""
    combined_diff = f"=== OLD ===\n{old_v}\n\n=== NEW ===\n{new_v}"
    agent_run_ui(
        agent_id="changelog_agent",
        tab_key="lab_diff",
        default_prompt=default_prompt_changelog,
        default_input_text=combined_diff,
        allow_model_override=True,
        tab_label_for_history="WOW AI Lab · Change Log",
    )


# =========================
# Agents Config Tab
# =========================

def render_agents_config_tab():
    st.title(t("Agents Config"))
    agents_cfg = st.session_state["agents_cfg"]
    agents_dict = agents_cfg.get("agents", {})

    st.subheader("1. Current Agents Overview")
    if not agents_dict:
        st.warning("No agents found in current agents.yaml.")
    else:
        df = pd.DataFrame(
            [
                {"agent_id": aid, "name": acfg.get("name", ""), "model": acfg.get("model", ""), "category": acfg.get("category", "")}
                for aid, acfg in agents_dict.items()
            ]
        )
        st.dataframe(df, use_container_width=True, height=260)

    st.markdown("---")
    st.subheader("2. Edit Full agents.yaml (raw text)")
    yaml_str_current = yaml.dump(st.session_state["agents_cfg"], allow_unicode=True, sort_keys=False)

    edited_yaml_text = st.text_area(
        "agents.yaml (editable)",
        value=yaml_str_current,
        height=320,
        key="agents_yaml_text_editor",
    )

    col_a1, col_a2, col_a3 = st.columns(3)
    with col_a1:
        if st.button("Apply edited YAML to session", key="apply_edited_yaml"):
            try:
                cfg = yaml.safe_load(edited_yaml_text)
                if not isinstance(cfg, dict) or "agents" not in cfg:
                    st.error("Parsed YAML does not contain top-level key 'agents'. No changes applied.")
                else:
                    st.session_state["agents_cfg"] = cfg
                    st.success("Updated agents.yaml in current session.")
            except Exception as e:
                st.error(f"Failed to parse edited YAML: {e}")

    with col_a2:
        uploaded_agents_tab = st.file_uploader("Upload agents.yaml file", type=["yaml", "yml"], key="agents_yaml_tab_uploader")
        if uploaded_agents_tab is not None:
            try:
                cfg = yaml.safe_load(uploaded_agents_tab.read())
                if "agents" in cfg:
                    st.session_state["agents_cfg"] = cfg
                    st.success("Uploaded agents.yaml applied to this session.")
                else:
                    st.warning("Uploaded file has no top-level 'agents' key. Ignoring.")
            except Exception as e:
                st.error(f"Failed to parse uploaded YAML: {e}")

    with col_a3:
        st.download_button(
            "Download current agents.yaml",
            data=yaml_str_current.encode("utf-8"),
            file_name="agents.yaml",
            mime="text/yaml",
            key="download_agents_yaml_current",
        )


# =========================
# Main
# =========================

st.set_page_config(page_title="WOＷ Agentic Medical Device Reviewer", layout="wide")

if "settings" not in st.session_state:
    st.session_state["settings"] = {
        "theme": "Light",
        "language": "繁體中文",
        "painter_style": "Van Gogh",
        "model": "gpt-4o-mini",
        "max_tokens": 12000,
        "temperature": 0.2,
    }
if "history" not in st.session_state:
    st.session_state["history"] = []
if "wow" not in st.session_state:
    st.session_state["wow"] = {
        "run_state": "pending",
        "run_label": "",
        "run_ts": "",
        "run_error": "",
        "last_event": None,
    }

# Load agents.yaml or default minimal
if "agents_cfg" not in st.session_state:
    try:
        with open("agents.yaml", "r", encoding="utf-8") as f:
            st.session_state["agents_cfg"] = yaml.safe_load(f)
    except Exception:
        st.session_state["agents_cfg"] = {
            "agents": {
                "fda_510k_intel_agent": {
                    "name": "510(k) Intelligence Agent",
                    "model": "gpt-4o-mini",
                    "system_prompt": "You are an FDA 510(k) analyst.",
                    "max_tokens": 12000,
                    "category": "FDA 510(k)",
                },
                "pdf_to_markdown_agent": {
                    "name": "PDF to Markdown Agent",
                    "model": "gemini-2.5-flash",
                    "system_prompt": "You convert PDF-extracted text into clean markdown.",
                    "max_tokens": 12000,
                    "category": "文件前處理",
                },
                "tw_screen_review_agent": {
                    "name": "TFDA 預審形式審查代理",
                    "model": "gemini-2.5-flash",
                    "system_prompt": "You are a TFDA premarket screen reviewer.",
                    "max_tokens": 12000,
                    "category": "TFDA Premarket",
                },
                "tw_app_doc_helper": {
                    "name": "TFDA 申請書撰寫助手",
                    "model": "gpt-4o-mini",
                    "system_prompt": "You help improve TFDA application documents.",
                    "max_tokens": 12000,
                    "category": "TFDA Premarket",
                },
                # NEW LAB agents (fallback ids; can be overwritten by uploaded agents.yaml)
                "traceability_matrix_agent": {
                    "name": "Traceability Matrix Builder",
                    "model": "gpt-4o-mini",
                    "system_prompt": "You build requirement-to-evidence traceability matrices.",
                    "max_tokens": 12000,
                    "category": "WOW AI Lab",
                },
                "risk_register_agent": {
                    "name": "Risk Register Builder",
                    "model": "gemini-2.5-flash",
                    "system_prompt": "You draft ISO 14971-style risk registers from input text.",
                    "max_tokens": 12000,
                    "category": "WOW AI Lab",
                },
                "changelog_agent": {
                    "name": "Change Log Generator",
                    "model": "claude-3-5-sonnet-20241022",
                    "system_prompt": "You compare two document versions and summarize changes for reviewers.",
                    "max_tokens": 12000,
                    "category": "WOW AI Lab",
                },
            }
        }

render_sidebar()
apply_style(st.session_state.settings["theme"], st.session_state.settings["painter_style"])
render_wow_hero()

tab_labels = [
    t("Dashboard"),
    t("TW Premarket"),
    t("510k_tab"),
    t("PDF → Markdown"),
    t("Checklist & Report"),
    t("Note Keeper & Magics"),
    t("Agent Workflow Studio"),
    t("WOW AI Lab"),
    t("Agents Config"),
]
tabs = st.tabs(tab_labels)

with tabs[0]:
    render_dashboard()
with tabs[1]:
    render_tw_premarket_tab()
with tabs[2]:
    render_510k_tab()
with tabs[3]:
    render_pdf_to_md_tab()
with tabs[4]:
    render_510k_review_pipeline_tab()
with tabs[5]:
    render_note_keeper_tab()
with tabs[6]:
    render_agent_workflow_studio_tab()
with tabs[7]:
    render_wow_ai_lab_tab()
with tabs[8]:
    render_agents_config_tab()
