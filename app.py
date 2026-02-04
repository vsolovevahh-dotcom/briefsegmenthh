# app.py
# Streamlit single-file app: hh сегменты — заявка

import json
import re
import base64
from io import BytesIO
from copy import deepcopy
from typing import Any

import requests
import streamlit as st

# =========================
# Page config
# =========================
st.set_page_config(
    page_title="hh Сегменты — заявка",
    page_icon="🧩",
    layout="wide",
)

# =========================
# Styles
# =========================
st.markdown(
    """
<style>
:root{
  --card-bg:#ffffff;
  --muted:#6b7280;
  --border:#e5e7eb;
  --accent:#ef4444;
}
.app-title{ font-size:2.2rem; font-weight:900; margin:0.2rem 0 0.2rem 0; }
.app-sub{ color:var(--muted); margin-bottom:1.2rem; }
.small-muted{ color:var(--muted); font-size:0.92rem; }
.hr{ height:1px; background:var(--border); margin:18px 0; }
.card{ background:var(--card-bg); border:1px solid var(--border); border-radius:16px; padding:16px; }
.badge{ display:inline-block; padding:6px 10px; border:1px solid var(--border); border-radius:999px; background:#fafafa; font-size:0.85rem; color:#111827; margin-bottom:8px; }
.hint{ background:#fff7ed; border:1px solid #fed7aa; color:#9a3412; border-radius:14px; padding:12px 14px; }
.ok{ background:#ecfdf5; border:1px solid #a7f3d0; color:#065f46; border-radius:14px; padding:12px 14px; margin:12px 0; }
.warning{ background:#fef3c7; border:1px solid #fcd34d; color:#92400e; border-radius:14px; padding:12px 14px; margin:12px 0; }

/* Мокап десктопного объявления (Яндекс) */
.ad-desktop{ 
  border:1px solid var(--border); 
  border-radius:12px; 
  padding:20px; 
  background:#fff; 
  margin-bottom:20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}
.ad-desktop-header{ 
  font-size:0.75rem; 
  color:#888; 
  margin-bottom:8px;
  display:flex;
  align-items:center;
  gap:6px;
}
.ad-desktop-title{ 
  font-weight:900; 
  font-size:1.4rem; 
  margin-bottom:10px; 
  color:#0066ff;
  line-height:1.3;
}
.ad-desktop-body{ 
  color:#374151; 
  margin-bottom:14px; 
  line-height:1.6;
  font-size:0.95rem;
}
.ad-desktop-link{ 
  color:#0066ff; 
  text-decoration:none; 
  font-size:0.9rem;
  display:inline-block;
  margin-bottom:14px;
}
.ad-desktop-image{ 
  border-radius:8px; 
  overflow:hidden; 
  margin-top:12px;
}

/* Мокап мобильного объявления */
.ad-mobile{
  max-width:380px;
  margin:0 auto 24px;
  border:1px solid #ddd;
  border-radius:16px;
  background:#fff;
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
  overflow:hidden;
}
.ad-mobile-header{
  padding:12px 16px;
  border-bottom:1px solid #eee;
  display:flex;
  align-items:center;
  gap:10px;
}
.ad-mobile-avatar{
  width:40px;
  height:40px;
  border-radius:50%;
  background:#e5e7eb;
  display:flex;
  align-items:center;
  justify-content:center;
  font-weight:bold;
  color:#6b7280;
}
.ad-mobile-name{
  font-weight:600;
  font-size:0.95rem;
  color:#111;
}
.ad-mobile-meta{
  font-size:0.75rem;
  color:#888;
}
.ad-mobile-text{
  padding:14px 16px;
  color:#111;
  line-height:1.5;
  font-size:0.95rem;
}
.ad-mobile-image{
  width:100%;
  max-height:280px;
  object-fit:cover;
}
.ad-mobile-footer{
  padding:12px 16px;
  border-top:1px solid #eee;
  display:flex;
  gap:8px;
}
.ad-mobile-btn{
  flex:1;
  padding:10px;
  border-radius:8px;
  background:#0088cc;
  color:#fff;
  text-align:center;
  font-weight:600;
  font-size:0.9rem;
  cursor:pointer;
}

/* Заглушка видео */
.video-placeholder{
  background:linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius:12px;
  padding:40px 20px;
  text-align:center;
  color:#fff;
  margin-top:12px;
}
.video-placeholder-icon{
  font-size:3rem;
  margin-bottom:12px;
}
.video-placeholder-text{
  font-size:1.1rem;
  font-weight:600;
  margin-bottom:6px;
}
.video-placeholder-sub{
  font-size:0.85rem;
  opacity:0.9;
}

/* Прогресс генерации */
.generation-progress{
  background:#f9fafb;
  border:1px solid #e5e7eb;
  border-radius:12px;
  padding:16px;
  margin:16px 0;
}
.progress-item{
  display:flex;
  align-items:center;
  gap:10px;
  padding:8px 0;
  font-size:0.95rem;
}
.progress-icon{
  font-size:1.2rem;
}
</style>
""",
    unsafe_allow_html=True,
)

# =========================
# Constants
# =========================
PAGES = [
    "0. Старт",
    "1. Основная информация",
    "2. Креативы и площадки",
    "3. Генерация текстов",
    "4. Примерный вид объявлений",
]

FORMATS = {
    "Яндекс": ["Изображение", "Видео"],
    "VK": ["Изображение", "Видео"],
    "Telegram Ads": ["Текст", "Изображение", "Видео"],
    "Telegram посевы": ["Пост + изображение с текстом"],
}

LIMITS = {
    "yandex_title": 56,
    "yandex_body": 81,
    "vk_post": 700,
    "tgads_text": 200,
    "seed_post": 500,
    "seed_img_text": 40,
}

# =========================
# Defaults
# =========================
DEFAULT_FORM = {
    "what_advertise": "",
    "campaign_goal": "",
    "landing_url": "",
    "geo": "",
    "segment_desc": "",
    "files_links": "",
    "contact_name": "",
    "landing_context": "",
    "logo_file": None,
    
    "pl_yandex": False,
    "pl_vk": False,
    "pl_tgads": False,
    "pl_tgseeding": False,
    
    "fmt_yandex": [],
    "fmt_vk": [],
    "fmt_tgads": [],
    
    "generated_texts": {},
    "demo_images": {},
    
    "nav_page": PAGES[0],
}

def _deepcopy_if_needed(v: Any) -> Any:
    return deepcopy(v) if isinstance(v, (dict, list)) else v

def init_state():
    for k, v in DEFAULT_FORM.items():
        if k not in st.session_state:
            st.session_state[k] = _deepcopy_if_needed(v)

init_state()

# =========================
# Helpers
# =========================

def normalize_url(u: str) -> str:
    u = (u or "").strip()
    if not u:
        return ""
    if not re.match(r"^https?://", u, flags=re.I):
        u = "https://" + u
    return u

def try_fetch_landing_text(url: str) -> str:
    url = normalize_url(url)
    if not url:
        return ""
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200:
            return f"(Не удалось загрузить страницу: HTTP {r.status_code})"
        html = r.text
        text = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
        text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
        text = re.sub(r"(?s)<.*?>", " ", text)
        text = " ".join(text.split())
        return text[:6000]
    except Exception as e:
        return f"(Не удалось загрузить страницу: {e})"

def get_selected_platforms() -> list:
    res = []
    if st.session_state.get("pl_yandex", False):
        res.append("Яндекс")
    if st.session_state.get("pl_vk", False):
        res.append("VK")
    if st.session_state.get("pl_tgads", False):
        res.append("Telegram Ads")
    if st.session_state.get("pl_tgseeding", False):
        res.append("Telegram посевы")
    return res

def get_selected_formats(platform: str) -> list:
    if platform == "Яндекс":
        return st.session_state.get("fmt_yandex", [])
    if platform == "VK":
        return st.session_state.get("fmt_vk", [])
    if platform == "Telegram Ads":
        return st.session_state.get("fmt_tgads", [])
    if platform == "Telegram посевы":
        return ["Пост + изображение с текстом"]
    return []

def clamp_text(text: str, limit: int) -> str:
    """Обрезает текст до лимита символов, сохраняя целостность слов."""
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    # Обрезаем до последнего пробела перед лимитом
    truncated = text[:limit].rsplit(' ', 1)[0]
    return truncated + "..."

def add_emoji_to_text(text: str, platform: str) -> str:
    """Добавляет эмодзи для Telegram."""
    if platform not in ["Telegram Ads", "Telegram посевы"]:
        return text
    
    # Простая логика: добавляем эмодзи в начало, если их нет
    emoji_map = {
        "работ": "💼",
        "вакан": "📋",
        "карьер": "🚀",
        "команд": "👥",
        "разработ": "💻",
        "IT": "⚡",
        "tech": "🔧",
    }
    
    text_lower = text.lower()
    for keyword, emoji in emoji_map.items():
        if keyword in text_lower and emoji not in text:
            # Добавляем эмодзи в начало первого предложения
            sentences = text.split('. ')
            if sentences:
                sentences[0] = f"{emoji} {sentences[0]}"
                return '. '.join(sentences)
    
    return text

# =========================
# OpenRouter helpers
# =========================

def _secret(name: str, default: str = "") -> str:
    try:
        return (st.secrets.get(name, default) or "").strip()
    except Exception:
        return default

def openrouter_api_key() -> str:
    return _secret("OPENROUTER_API_KEY", "")

def openrouter_text_model() -> str:
    return _secret("OPENROUTER_TEXT_MODEL", "openrouter/auto")

def openrouter_text_fallbacks() -> list:
    raw = _secret("OPENROUTER_TEXT_MODEL_FALLBACKS", "")
    models = [m.strip() for m in raw.split(",") if m.strip()]
    if not models:
        models = ["openrouter/auto", "meta-llama/llama-3.1-8b-instruct", "mistralai/mistral-7b-instruct"]
    return models

def openrouter_image_model() -> str:
    return _secret("OPENROUTER_IMAGE_MODEL", "black-forest-labs/flux-schnell")

def openrouter_image_fallbacks() -> list:
    raw = _secret("OPENROUTER_IMAGE_MODEL_FALLBACKS", "")
    models = [m.strip() for m in raw.split(",") if m.strip()]
    if not models:
        models = ["black-forest-labs/flux-schnell", "black-forest-labs/flux-dev"]
    return models

def openrouter_provider_prefs() -> dict:
    ignore_raw = _secret("OPENROUTER_PROVIDER_IGNORE", "")
    ignore = [x.strip() for x in ignore_raw.split(",") if x.strip()]
    prefs = {"allow_fallbacks": True, "sort": "price"}
    if ignore:
        prefs["ignore"] = ignore
    return prefs

def openrouter_chat(*, model: str, messages: list, temperature: float = 0.6, max_tokens: int = 900, modalities: list = None, image_config: dict = None):
    api_key = openrouter_api_key()
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY не задан в Secrets")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": _secret("OPENROUTER_REFERER", "https://streamlit.app"),
        "X-Title": _secret("OPENROUTER_APP_TITLE", "hh-segments-brief"),
    }

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "provider": openrouter_provider_prefs(),
    }
    if modalities is not None:
        payload["modalities"] = modalities
    if image_config is not None:
        payload["image_config"] = image_config

    r = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=90)

    if r.status_code != 200:
        try:
            detail = r.json()
        except Exception:
            detail = (r.text or "")[:1500]
        raise RuntimeError(f"OpenRouter API error {r.status_code}: {detail}")

    return r.json()

def openrouter_chat_with_fallback(models: list, **kwargs):
    errors = []
    for m in models:
        try:
            return m, openrouter_chat(model=m, **kwargs)
        except Exception as e:
            errors.append(f"{m}: {e}")
    raise RuntimeError(" ; ".join(errors[-3:]) if errors else "OpenRouter: неизвестная ошибка")

def extract_json_obj(text: str) -> dict:
    if not text:
        return {}
    text = text.strip()
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    first = text.find("{")
    last = text.rfind("}")
    if first != -1 and last != -1 and last > first:
        candidate = text[first : last + 1]
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict):
                return obj
        except Exception:
            return {}
    return {}

def ai_generate_one_text(platform: str) -> dict:
    """Генерация ОДНОГО варианта текста для площадки."""
    base = {
        "what_advertise": st.session_state.get("what_advertise", ""),
        "campaign_goal": st.session_state.get("campaign_goal", ""),
        "landing_url": st.session_state.get("landing_url", ""),
        "geo": st.session_state.get("geo", ""),
        "segment_desc": st.session_state.get("segment_desc", ""),
        "landing_context": st.session_state.get("landing_context", ""),
    }
    models = [openrouter_text_model()] + openrouter_text_fallbacks()

    if platform == "Яндекс":
        prompt = f"Ты — PMM/копирайтер. Сгенерируй РОВНО 1 вариант текста для Яндекс объявлений. Верни ТОЛЬКО JSON (без markdown/пояснений). Лимиты: title ≤ {LIMITS['yandex_title']} символов, body ≤ {LIMITS['yandex_body']} символов. Стиль: нейтрально-деловой, без клише и без обещаний типа 'гарантируем'.\n\nВводные: {json.dumps(base, ensure_ascii=False)}\n\nВерни JSON: {{\"title\":\"...\",\"body\":\"...\"}}"
        _, data = openrouter_chat_with_fallback(models=models, messages=[{"role": "user", "content": prompt}], temperature=0.4, max_tokens=260)
        content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
        obj = extract_json_obj(content)
        return {
            "title": clamp_text(obj.get("title", ""), LIMITS["yandex_title"]),
            "body": clamp_text(obj.get("body", ""), LIMITS["yandex_body"]),
        }

    if platform == "VK":
        prompt = f"Ты — PMM/копирайтер. Сгенерируй РОВНО 1 вариант нативного текста для VK. Верни ТОЛЬКО JSON. Лимит: post ≤ {LIMITS['vk_post']} символов. CTA из списка: Перейти / Подробнее / Открыть / Откликнуться.\n\nВводные: {json.dumps(base, ensure_ascii=False)}\n\nВерни JSON: {{\"post\":\"...\",\"cta\":\"Подробнее\"}}"
        _, data = openrouter_chat_with_fallback(models=models, messages=[{"role": "user", "content": prompt}], temperature=0.55, max_tokens=520)
        content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
        obj = extract_json_obj(content)
        return {
            "post": clamp_text(obj.get("post", ""), LIMITS["vk_post"]),
            "cta": obj.get("cta", "Подробнее"),
        }

    if platform == "Telegram Ads":
        prompt = f"Ты — PMM/копирайтер. Сгенерируй РОВНО 1 вариант текста для Telegram Ads с эмодзи. Верни ТОЛЬКО JSON. Лимит: message ≤ {LIMITS['tgads_text']} символов. CTA из списка: Подробнее / Перейти / Открыть. Используй 1-2 уместных эмодзи.\n\nВводные: {json.dumps(base, ensure_ascii=False)}\n\nВерни JSON: {{\"message\":\"...\",\"cta\":\"Подробнее\"}}"
        _, data = openrouter_chat_with_fallback(models=models, messages=[{"role": "user", "content": prompt}], temperature=0.6, max_tokens=320)
        content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
        obj = extract_json_obj(content)
        return {
            "message": clamp_text(obj.get("message", ""), LIMITS["tgads_text"]),
            "cta": obj.get("cta", "Подробнее"),
        }

    # Telegram посевы
    prompt = f"Ты — PMM/копирайтер. Сгенерируй РОВНО 1 вариант для Telegram посевов с эмодзи: 1) image_text — 1 строка (≤ {LIMITS['seed_img_text']} символов) для текста на креативе; 2) post — пост (≤ {LIMITS['seed_post']} символов) нативно, без ощущения баннера. Используй 2-3 уместных эмодзи. Верни ТОЛЬКО JSON.\n\nВводные: {json.dumps(base, ensure_ascii=False)}\n\nВерни JSON: {{\"image_text\":\"...\",\"post\":\"...\"}}"
    _, data = openrouter_chat_with_fallback(models=models, messages=[{"role": "user", "content": prompt}], temperature=0.7, max_tokens=720)
    content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
    obj = extract_json_obj(content)
    return {
        "image_text": clamp_text(obj.get("image_text", ""), LIMITS["seed_img_text"]),
        "post": clamp_text(obj.get("post", ""), LIMITS["seed_post"]),
    }

def extract_image_url(data: dict) -> str:
    if not data or not data.get("choices"):
        return ""
    msg = (data["choices"][0] or {}).get("message", {}) or {}
    images = msg.get("images") or []
    if images:
        img0 = images[0] or {}
        url_obj = img0.get("image_url") or img0.get("imageUrl") or {}
        url = (url_obj or {}).get("url")
        if url:
            return url
    content = msg.get("content")
    if isinstance(content, list):
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "image_url":
                url_obj = part.get("image_url") or part.get("imageUrl") or {}
                url = (url_obj or {}).get("url")
                if url:
                    return url
    if isinstance(content, str):
        m = re.search(r"(data:image/[a-zA-Z]+;base64,[A-Za-z0-9+/=]+)", content)
        if m:
            return m.group(1)
    return ""

def generate_demo_image(prompt: str, aspect_ratio: str = "16:9") -> str:
    """Генерация РЕАЛИСТИЧНОГО изображения БЕЗ текста."""
    models = [openrouter_image_model()] + openrouter_image_fallbacks()
    last_err = None
    for model in models:
        try:
            user_prompt = (
                f"{prompt}\n\n"
                f"Aspect ratio: {aspect_ratio}.\n\n"
                "CRITICAL REQUIREMENTS:\n"
                "- PHOTOREALISTIC style only (professional photography, not illustration)\n"
                "- NO text, letters, words, or numbers anywhere in the image\n"
                "- NO logos, brand names, or typography\n"
                "- NO signs, labels, or written content\n"
                "- Pure visual imagery: real people, real workplace, real objects\n"
                "- High-quality, professional advertising photography\n"
                "- Natural lighting, modern corporate environment"
            )
            _, data = openrouter_chat_with_fallback(
                models=[model], 
                messages=[{"role": "user", "content": user_prompt}], 
                temperature=0.2, 
                max_tokens=200, 
                modalities=["image"], 
                image_config=None
            )
            url = extract_image_url(data)
            if url:
                return url
            last_err = RuntimeError("Пустой ответ (не нашли image_url)")
        except Exception as e:
            last_err = e
    raise RuntimeError(last_err or "Не удалось сгенерировать изображение")

# =========================
# Sidebar
# =========================
st.sidebar.markdown("## 🧩 hh Сегменты — заявка")
st.sidebar.markdown('<div class="small-muted">Форма → заявка → демо превью</div>', unsafe_allow_html=True)
st.sidebar.markdown('<div class="hr"></div>', unsafe_allow_html=True)

current_page = st.sidebar.radio("Навигация", PAGES, index=PAGES.index(st.session_state.get("nav_page", PAGES[0])))
st.session_state.nav_page = current_page

def reset_form():
    nav = st.session_state.get("nav_page", PAGES[0])
    for k, v in DEFAULT_FORM.items():
        st.session_state[k] = _deepcopy_if_needed(v)
    st.session_state["nav_page"] = nav
    st.rerun()

st.sidebar.button("↩️ Сбросить форму", on_click=reset_form, use_container_width=True)

st.markdown('<div class="app-title">hh Сегменты — заявка</div>', unsafe_allow_html=True)
st.markdown('<div class="app-sub">Заполнение брифа займёт до 5 минут.</div>', unsafe_allow_html=True)

# =========================
# Screens
# =========================

def screen_0():
    st.markdown('<div class="card"><div style="font-weight:900; font-size:1.15rem; margin-bottom:6px;">Что это</div><div class="small-muted">Собираем минимально достаточный бриф для запуска hh Сегментов. На последнем шаге покажем мокапы объявлений.</div></div>', unsafe_allow_html=True)
    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)
    def go_next():
        st.session_state.nav_page = "1. Основная информация"
        st.rerun()
    st.button("Начать →", on_click=go_next, type="primary", use_container_width=True)

def screen_1():
    st.title("Основная информация")
    with st.expander("💡 Коротко про hh Сегменты", expanded=False):
        st.markdown("- Важнее всего: **что рекламируем**, **цель**, **гео**, **описание сегмента**, **посадочная**.\n- Контекст посадочной можно вставить вручную или попробовать подтянуть по ссылке.")
    
    col1, col2 = st.columns(2)
    with col1:
        what_advertise = st.text_area("Что рекламируем*", value=st.session_state.get("what_advertise", ""), height=90, placeholder="Коротко: работодатель/вакансии/кампания, в 1–2 предложениях.", key="_what_advertise")
        st.session_state.what_advertise = what_advertise
        
        campaign_goal = st.text_input("Цель кампании*", value=st.session_state.get("campaign_goal", ""), placeholder="Напр.: трафик на вакансии / рост откликов / узнаваемость", key="_campaign_goal")
        st.session_state.campaign_goal = campaign_goal
        
        landing_url = st.text_input("Посадочная ссылка*", value=st.session_state.get("landing_url", ""), placeholder="https://…", key="_landing_url")
        st.session_state.landing_url = landing_url
        
        geo = st.text_input("Гео*", value=st.session_state.get("geo", ""), placeholder="Города/регионы", key="_geo")
        st.session_state.geo = geo
    
    with col2:
        segment_desc = st.text_area("Описание сегмента*", value=st.session_state.get("segment_desc", ""), height=120, placeholder="1–3 сегмента: кто эти люди, опыт/профили/уровень.", key="_segment_desc")
        st.session_state.segment_desc = segment_desc
        
        contact_name = st.text_input("Контактное лицо (кто заполняет)*", value=st.session_state.get("contact_name", ""), placeholder="Имя", key="_contact_name")
        st.session_state.contact_name = contact_name
        
        st.markdown("**Логотип компании (опционально)**")
        logo_file = st.file_uploader("Загрузите логотип (PNG/JPG)", type=["png", "jpg", "jpeg"], key="_logo_upload")
        if logo_file:
            st.session_state.logo_file = logo_file.read()
            st.success("✅ Логотип загружен")
    
    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)
    st.subheader("Контекст посадочной (для генерации текстов)")
    st.caption("Если есть — вставьте текст с посадочной. Либо попробуйте подтянуть по ссылке кнопкой ниже.")
    
    landing_context = st.text_area("Контекст посадочной", value=st.session_state.get("landing_context", ""), height=140, placeholder="Вставьте описание/УТП/ключевые блоки с посадочной…", label_visibility="collapsed", key="_landing_context")
    st.session_state.landing_context = landing_context
    
    c1, c2 = st.columns([1, 1])
    with c1:
        def pull_context():
            fetched = try_fetch_landing_text(st.session_state.landing_url)
            st.session_state.landing_context = fetched
            st.rerun()
        st.button("Подтянуть контекст по ссылке (beta)", on_click=pull_context, use_container_width=True)
    
    with c2:
        def go_next():
            # Валидация обязательных полей
            if not all([
                st.session_state.what_advertise.strip(),
                st.session_state.campaign_goal.strip(),
                st.session_state.landing_url.strip(),
                st.session_state.geo.strip(),
                st.session_state.segment_desc.strip(),
                st.session_state.contact_name.strip(),
            ]):
                st.error("⚠️ Заполните все обязательные поля (отмечены *)")
                return
            st.session_state.nav_page = "2. Креативы и площадки"
            st.rerun()
        st.button("Далее →", on_click=go_next, type="primary", use_container_width=True)

def screen_2():
    st.title("Креативы и площадки")
    st.caption("Выберите рекламные площадки и форматы креативов.")
    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Площадки")
        pl_yandex = st.checkbox("Яндекс", value=st.session_state.get("pl_yandex", False), key="_pl_yandex")
        st.session_state.pl_yandex = pl_yandex
        
        pl_vk = st.checkbox("VK", value=st.session_state.get("pl_vk", False), key="_pl_vk")
        st.session_state.pl_vk = pl_vk
        
        pl_tgads = st.checkbox("Telegram Ads", value=st.session_state.get("pl_tgads", False), key="_pl_tgads")
        st.session_state.pl_tgads = pl_tgads
        
        pl_tgseeding = st.checkbox("Telegram посевы", value=st.session_state.get("pl_tgseeding", False), key="_pl_tgseeding")
        st.session_state.pl_tgseeding = pl_tgseeding
    
    with col2:
        st.subheader("Форматы (по площадкам)")
        if st.session_state.pl_yandex:
            fmt_yandex = st.multiselect("Яндекс", FORMATS["Яндекс"], default=st.session_state.get("fmt_yandex", []), placeholder="Выберите формат(ы)", key="_fmt_yandex")
            st.session_state.fmt_yandex = fmt_yandex
        if st.session_state.pl_vk:
            fmt_vk = st.multiselect("VK", FORMATS["VK"], default=st.session_state.get("fmt_vk", []), placeholder="Выберите формат(ы)", key="_fmt_vk")
            st.session_state.fmt_vk = fmt_vk
        if st.session_state.pl_tgads:
            fmt_tgads = st.multiselect("Telegram Ads", FORMATS["Telegram Ads"], default=st.session_state.get("fmt_tgads", []), placeholder="Выберите формат(ы)", key="_fmt_tgads")
            st.session_state.fmt_tgads = fmt_tgads
        if st.session_state.pl_tgseeding:
            st.info("Telegram посевы: формат фиксированный — пост + изображение с текстом")
    
    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)
    c1, c2 = st.columns([1, 1])
    with c1:
        def back():
            st.session_state.nav_page = "1. Основная информация"
            st.rerun()
        st.button("← Назад", on_click=back, use_container_width=True)
    
    with c2:
        def go_next():
            selected = get_selected_platforms()
            if not selected:
                st.error("⚠️ Выберите хотя бы одну площадку")
                return
            st.session_state.nav_page = "3. Генерация текстов"
            st.rerun()
        st.button("Далее →", on_click=go_next, type="primary", use_container_width=True)

def screen_3():
    st.title("Генерация текстов")
    st.caption("Сгенерируем тексты для выбранных площадок на основе ваших данных.")
    
    selected = get_selected_platforms()
    if not selected:
        st.markdown('<div class="hint">Сначала выберите площадки на шаге 2.</div>', unsafe_allow_html=True)
        def back_to_step2():
            st.session_state.nav_page = "2. Креативы и площадки"
            st.rerun()
        st.button("← Вернуться к шагу 2", on_click=back_to_step2, use_container_width=True)
        return
    
    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)
    
    # Показываем выбранные площадки
    st.markdown("### Выбранные площадки:")
    for p in selected:
        fmts = get_selected_formats(p)
        fmts_str = ", ".join(fmts) if fmts else "все форматы"
        st.markdown(f"✅ **{p}** ({fmts_str})")
    
    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)
    
    # Кнопка генерации
    if not st.session_state.get("generated_texts"):
        if st.button("⚡ Сгенерировать тексты для всех площадок", type="primary", use_container_width=True):
            if not openrouter_api_key():
                st.error("❌ Добавьте OPENROUTER_API_KEY в Secrets, чтобы включить генерацию.")
                return
            
            generated = {}
            errors = []
            
            with st.spinner("🤖 Генерируем тексты..."):
                progress_container = st.empty()
                
                for i, p in enumerate(selected):
                    progress_container.markdown(f'<div class="generation-progress"><div class="progress-item"><span class="progress-icon">⏳</span> Генерируем {p}...</div></div>', unsafe_allow_html=True)
                    
                    try:
                        result = ai_generate_one_text(p)
                        generated[p] = result
                        progress_container.markdown(f'<div class="generation-progress"><div class="progress-item"><span class="progress-icon">✅</span> {p}: готово</div></div>', unsafe_allow_html=True)
                    except Exception as e:
                        errors.append(f"{p}: {e}")
                        progress_container.markdown(f'<div class="generation-progress"><div class="progress-item"><span class="progress-icon">❌</span> {p}: ошибка</div></div>', unsafe_allow_html=True)
            
            if generated:
                st.session_state.generated_texts = generated
                st.markdown('<div class="ok">✅ Готово! Тексты сгенерированы.</div>', unsafe_allow_html=True)
                st.rerun()
            
            if errors:
                st.error("Некоторые тексты не удалось сгенерировать:")
                st.code("\n".join(errors))
    
    # Показываем сгенерированные тексты
    if st.session_state.get("generated_texts"):
        st.markdown("### 📝 Сгенерированные тексты:")
        
        for platform, data in st.session_state.generated_texts.items():
            with st.expander(f"📋 {platform}", expanded=True):
                if platform == "Яндекс":
                    st.markdown(f"**Заголовок** ({len(data.get('title', ''))} / {LIMITS['yandex_title']} символов):")
                    st.code(data.get("title", ""))
                    st.markdown(f"**Текст** ({len(data.get('body', ''))} / {LIMITS['yandex_body']} символов):")
                    st.code(data.get("body", ""))
                
                elif platform == "VK":
                    st.markdown(f"**Текст поста** ({len(data.get('post', ''))} / {LIMITS['vk_post']} символов):")
                    st.code(data.get("post", ""))
                    st.markdown(f"**CTA:** {data.get('cta', 'Подробнее')}")
                
                elif platform == "Telegram Ads":
                    st.markdown(f"**Текст сообщения** ({len(data.get('message', ''))} / {LIMITS['tgads_text']} символов):")
                    st.code(data.get("message", ""))
                    st.markdown(f"**CTA:** {data.get('cta', 'Подробнее')}")
                
                else:  # Telegram посевы
                    st.markdown(f"**Текст на изображении** ({len(data.get('image_text', ''))} / {LIMITS['seed_img_text']} символов):")
                    st.code(data.get("image_text", ""))
                    st.markdown(f"**Текст поста** ({len(data.get('post', ''))} / {LIMITS['seed_post']} символов):")
                    st.code(data.get("post", ""))
        
        st.markdown('<div class="hr"></div>', unsafe_allow_html=True)
        
        c1, c2 = st.columns([1, 1])
        with c1:
            def regenerate():
                st.session_state.generated_texts = {}
                st.rerun()
            st.button("🔄 Перегенерировать все тексты", on_click=regenerate, use_container_width=True)
        
        with c2:
            def go_next():
                st.session_state.nav_page = "4. Примерный вид объявлений"
                st.rerun()
            st.button("Далее →", on_click=go_next, type="primary", use_container_width=True)

def render_yandex_ad(title: str, body: str, url: str, image_url: str = None, is_video: bool = False):
    """Мокап десктопного объявления Яндекс."""
    st.markdown('<div class="ad-desktop">', unsafe_allow_html=True)
    st.markdown('<div class="ad-desktop-header">🔗 Реклама · hh.ru</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="ad-desktop-title">{title}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="ad-desktop-body">{body}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="ad-desktop-link">→ {url}</div>', unsafe_allow_html=True)
    
    if is_video:
        st.markdown('<div class="video-placeholder"><div class="video-placeholder-icon">🎬</div><div class="video-placeholder-text">Видеокреатив</div><div class="video-placeholder-sub">Доступно в полной версии</div></div>', unsafe_allow_html=True)
    elif image_url:
        st.markdown('<div class="ad-desktop-image">', unsafe_allow_html=True)
        try:
            if image_url.startswith("data:image"):
                header, encoded = image_url.split(",", 1)
                image_bytes = base64.b64decode(encoded)
                image_io = BytesIO(image_bytes)
                try:
                    st.image(image_io, use_container_width=True)
                except TypeError:
                    st.image(image_io, use_column_width=True)
            elif image_url.startswith("http"):
                try:
                    st.image(image_url, use_container_width=True)
                except TypeError:
                    st.image(image_url, use_column_width=True)
        except Exception as e:
            st.error(f"Ошибка отображения: {str(e)}")
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

def render_mobile_ad(platform: str, text: str, cta: str, image_url: str = None, is_video: bool = False):
    """Мокап мобильного объявления (VK, TG)."""
    st.markdown('<div class="ad-mobile">', unsafe_allow_html=True)
    
    # Хедер
    st.markdown('<div class="ad-mobile-header">', unsafe_allow_html=True)
    st.markdown('<div class="ad-mobile-avatar">hh</div>', unsafe_allow_html=True)
    st.markdown('<div><div class="ad-mobile-name">hh.ru</div><div class="ad-mobile-meta">Реклама</div></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Текст
    st.markdown(f'<div class="ad-mobile-text">{text}</div>', unsafe_allow_html=True)
    
    # Изображение или видео
    if is_video:
        st.markdown('<div class="video-placeholder"><div class="video-placeholder-icon">🎬</div><div class="video-placeholder-text">Видеокреатив</div><div class="video-placeholder-sub">Доступно в полной версии</div></div>', unsafe_allow_html=True)
    elif image_url:
        try:
            if image_url.startswith("data:image"):
                header, encoded = image_url.split(",", 1)
                image_bytes = base64.b64decode(encoded)
                image_io = BytesIO(image_bytes)
                try:
                    st.image(image_io, use_container_width=True)
                except TypeError:
                    st.image(image_io, use_column_width=True)
            elif image_url.startswith("http"):
                try:
                    st.image(image_url, use_container_width=True)
                except TypeError:
                    st.image(image_url, use_column_width=True)
        except Exception as e:
            st.error(f"Ошибка отображения: {str(e)}")
    
    # Футер с CTA
    st.markdown(f'<div class="ad-mobile-footer"><div class="ad-mobile-btn">{cta}</div></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

def screen_4():
    st.title("Примерный вид объявлений")
    st.caption("Быстрый мокап, чтобы согласовать направление.")
    
    selected = get_selected_platforms()
    if not selected:
        st.markdown('<div class="hint">Сначала выберите площадки на шаге 2.</div>', unsafe_allow_html=True)
        return
    
    if not st.session_state.get("generated_texts"):
        st.markdown('<div class="warning">⚠️ Сначала сгенерируйте тексты на шаге 3.</div>', unsafe_allow_html=True)
        def back_to_step3():
            st.session_state.nav_page = "3. Генерация текстов"
            st.rerun()
        st.button("← Вернуться к генерации текстов", on_click=back_to_step3, use_container_width=True)
        return
    
    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)
    
    # Большая кнопка генерации изображений
    if not st.session_state.get("demo_images"):
        st.markdown("### 🎨 Генерация демо-визуалов")
        st.caption("Сгенерируем реалистичные фотографии для объявлений (без текста и логотипов). Займёт ~30-60 секунд.")
        
        if st.button("🎨 СГЕНЕРИРОВАТЬ ОБЪЯВЛЕНИЯ С ИЗОБРАЖЕНИЯМИ", type="primary", use_container_width=True):
            if not openrouter_api_key():
                st.error("❌ Добавьте OPENROUTER_API_KEY в Secrets.")
                return
            
            errors = []
            with st.spinner("🎨 Генерируем демо-визуалы..."):
                progress_container = st.empty()
                
                for p in selected:
                    fmts = get_selected_formats(p)
                    for f in fmts:
                        if f == "Видео":
                            continue  # Пропускаем видео
                        
                        need_visual = (
                            (p in ["Яндекс", "VK"] and f == "Изображение") or
                            (p == "Telegram Ads" and f == "Изображение") or
                            (p == "Telegram посевы")
                        )
                        
                        if not need_visual:
                            continue
                        
                        progress_container.markdown(f'<div class="generation-progress"><div class="progress-item"><span class="progress-icon">⏳</span> Генерируем изображение для {p}...</div></div>', unsafe_allow_html=True)
                        
                        core = st.session_state.get("what_advertise", "") or "HR-кампания"
                        seg = st.session_state.get("segment_desc", "") or "соискатели"
                        geo = st.session_state.get("geo", "") or "Россия"
                        
                        aspect = "4:5" if p == "Telegram посевы" else "16:9"
                        
                        prompt = f"Professional realistic advertising photography for {core}. Target audience: {seg}. Location: {geo}. Style: modern corporate environment, real people in workplace, natural lighting, high-quality professional photo. Focus on team collaboration, office setting, or relevant business context. Photorealistic, not illustration."
                        
                        try:
                            img = generate_demo_image(prompt, aspect_ratio=aspect)
                            if img:
                                if not isinstance(st.session_state.demo_images, dict):
                                    st.session_state.demo_images = {}
                                st.session_state.demo_images[f"{p}|{f}"] = img
                            progress_container.markdown(f'<div class="generation-progress"><div class="progress-item"><span class="progress-icon">✅</span> {p}: готово</div></div>', unsafe_allow_html=True)
                        except Exception as e:
                            errors.append(f"{p} · {f}: {e}")
                            progress_container.markdown(f'<div class="generation-progress"><div class="progress-item"><span class="progress-icon">❌</span> {p}: ошибка</div></div>', unsafe_allow_html=True)
            
            if errors:
                st.warning("⚠️ Часть визуалов не удалось сгенерировать:")
                st.code("\n".join(errors))
            else:
                st.markdown('<div class="ok">✅ Готово! Пролистайте ниже — объявления готовы.</div>', unsafe_allow_html=True)
            
            st.rerun()
    
    # Показываем мокапы
    if st.session_state.get("demo_images") or st.session_state.get("generated_texts"):
        st.markdown('<div class="hr"></div>', unsafe_allow_html=True)
        st.markdown("### 📱 Примерный вид объявлений:")
        
        texts = st.session_state.get("generated_texts", {})
        images = st.session_state.get("demo_images", {})
        
        for p in selected:
            st.markdown(f'<div class="badge">{p}</div>', unsafe_allow_html=True)
            
            fmts = get_selected_formats(p)
            text_data = texts.get(p, {})
            
            if p == "Яндекс":
                for f in fmts:
                    is_video = (f == "Видео")
                    image_url = images.get(f"{p}|{f}") if not is_video else None
                    render_yandex_ad(
                        title=text_data.get("title", "Заголовок"),
                        body=text_data.get("body", "Текст объявления"),
                        url=st.session_state.get("landing_url", "https://hh.ru"),
                        image_url=image_url,
                        is_video=is_video
                    )
            
            elif p == "VK":
                for f in fmts:
                    is_video = (f == "Видео")
                    image_url = images.get(f"{p}|{f}") if not is_video else None
                    render_mobile_ad(
                        platform="VK",
                        text=text_data.get("post", "Текст поста"),
                        cta=text_data.get("cta", "Подробнее"),
                        image_url=image_url,
                        is_video=is_video
                    )
            
            elif p == "Telegram Ads":
                for f in fmts:
                    if f == "Текст":
                        render_mobile_ad(
                            platform="Telegram",
                            text=text_data.get("message", "Текст сообщения"),
                            cta=text_data.get("cta", "Подробнее"),
                            image_url=None
                        )
                    else:
                        is_video = (f == "Видео")
                        image_url = images.get(f"{p}|{f}") if not is_video else None
                        render_mobile_ad(
                            platform="Telegram",
                            text=text_data.get("message", "Текст сообщения"),
                            cta=text_data.get("cta", "Подробнее"),
                            image_url=image_url,
                            is_video=is_video
                        )
            
            else:  # Telegram посевы
                image_url = images.get(f"{p}|Пост + изображение с текстом")
                render_mobile_ad(
                    platform="Telegram",
                    text=text_data.get("post", "Текст поста"),
                    cta="Подробнее",
                    image_url=image_url
                )
            
            st.markdown('<div class="hr"></div>', unsafe_allow_html=True)
    
    # Кнопки навигации
    c1, c2 = st.columns([1, 1])
    with c1:
        def back():
            st.session_state.nav_page = "3. Генерация текстов"
            st.rerun()
        st.button("← Назад", on_click=back, use_container_width=True)
    
    with c2:
        st.button("✅ Готово", use_container_width=True)

# =========================
# Router
# =========================
page = st.session_state.get("nav_page", PAGES[0])

if page == "0. Старт":
    screen_0()
elif page == "1. Основная информация":
    screen_1()
elif page == "2. Креативы и площадки":
    screen_2()
elif page == "3. Генерация текстов":
    screen_3()
elif page == "4. Примерный вид объявлений":
    screen_4()
else:
    st.session_state.nav_page = "0. Старт"
    screen_0()
