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
    truncated = text[:limit].rsplit(' ', 1)[0]
    return truncated + "..."

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
    """Генерация текста БЕЗ упоминания возраста и пола."""
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
        prompt = (
            f"Ты — PMM/копирайтер. Сгенерируй РОВНО 1 вариант текста для Яндекс объявлений. "
            f"Верни ТОЛЬКО JSON (без markdown/пояснений). "
            f"Лимиты: title ≤ {LIMITS['yandex_title']} символов, body ≤ {LIMITS['yandex_body']} символов. "
            f"Стиль: нейтрально-деловой, без клише и без обещаний типа 'гарантируем'. "
            f"ВАЖНО: НЕ упоминай возраст, пол, национальность соискателей. Фокус на профессии и условиях.\n\n"
            f"Вводные: {json.dumps(base, ensure_ascii=False)}\n\n"
            f"Верни JSON: {{\"title\":\"...\",\"body\":\"...\"}}"
        )
        _, data = openrouter_chat_with_fallback(models=models, messages=[{"role": "user", "content": prompt}], temperature=0.4, max_tokens=260)
        content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
        obj = extract_json_obj(content)
        return {
            "title": clamp_text(obj.get("title", ""), LIMITS["yandex_title"]),
            "body": clamp_text(obj.get("body", ""), LIMITS["yandex_body"]),
        }

    if platform == "VK":
        prompt = (
            f"Ты — PMM/копирайтер. Сгенерируй РОВНО 1 вариант нативного текста для VK. "
            f"Верни ТОЛЬКО JSON. Лимит: post ≤ {LIMITS['vk_post']} символов. "
            f"CTA из списка: Перейти / Подробнее / Открыть / Откликнуться. "
            f"ВАЖНО: НЕ упоминай возраст, пол соискателей. Фокус на вакансии и компании.\n\n"
            f"Вводные: {json.dumps(base, ensure_ascii=False)}\n\n"
            f"Верни JSON: {{\"post\":\"...\",\"cta\":\"Подробнее\"}}"
        )
        _, data = openrouter_chat_with_fallback(models=models, messages=[{"role": "user", "content": prompt}], temperature=0.55, max_tokens=520)
        content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
        obj = extract_json_obj(content)
        return {
            "post": clamp_text(obj.get("post", ""), LIMITS["vk_post"]),
            "cta": obj.get("cta", "Подробнее"),
        }

    if platform == "Telegram Ads":
        prompt = (
            f"Ты — PMM/копирайтер. Сгенерируй РОВНО 1 вариант текста для Telegram Ads с эмодзи. "
            f"Верни ТОЛЬКО JSON. Лимит: message ≤ {LIMITS['tgads_text']} символов. "
            f"CTA из списка: Подробнее / Перейти / Открыть. Используй 1-2 уместных эмодзи. "
            f"ВАЖНО: НЕ упоминай возраст, пол соискателей.\n\n"
            f"Вводные: {json.dumps(base, ensure_ascii=False)}\n\n"
            f"Верни JSON: {{\"message\":\"...\",\"cta\":\"Подробнее\"}}"
        )
        _, data = openrouter_chat_with_fallback(models=models, messages=[{"role": "user", "content": prompt}], temperature=0.6, max_tokens=320)
        content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
        obj = extract_json_obj(content)
        return {
            "message": clamp_text(obj.get("message", ""), LIMITS["tgads_text"]),
            "cta": obj.get("cta", "Подробнее"),
        }

    # Telegram посевы
    prompt = (
        f"Ты — PMM/копирайтер. Сгенерируй РОВНО 1 вариант для Telegram посевов с эмодзи: "
        f"1) image_text — 1 строка (≤ {LIMITS['seed_img_text']} символов) для текста на креативе; "
        f"2) post — пост (≤ {LIMITS['seed_post']} символов) нативно, без ощущения баннера. "
        f"Используй 2-3 уместных эмодзи. "
        f"ВАЖНО: НЕ упоминай возраст, пол соискателей. Верни ТОЛЬКО JSON.\n\n"
        f"Вводные: {json.dumps(base, ensure_ascii=False)}\n\n"
        f"Верни JSON: {{\"image_text\":\"...\",\"post\":\"...\"}}"
    )
    _, data = openrouter_chat_with_fallback(models=models, messages=[{"role": "user", "content": prompt}], temperature=0.7, max_tokens=720)
    content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
    obj = extract_json_obj(content)
    return {
        "image_text": clamp_text(obj.get("image_text", ""), LIMITS["seed_img_text"]),
        "post": clamp_text(obj.get("post", ""), LIMITS["seed_post"]),
    }

def analyze_context_for_image(context: str, segment: str) -> dict:
    """
    Анализирует контекст посадочной и описание сегмента для определения типа работы.
    Возвращает параметры для генерации изображения.
    """
    context_lower = (context + " " + segment).lower()
    
    office_keywords = ["офис", "it", "разработ", "программ", "менеджер", "аналитик", "маркетолог", "hr", "бухгалтер", "дизайнер", "компьютер", "ноутбук"]
    production_keywords = ["производств", "завод", "цех", "станок", "сборк", "монтаж", "строител", "инженер", "технолог", "слесар", "сварщик", "рабочий"]
    service_keywords = ["продав", "кассир", "официант", "повар", "администратор", "консультант", "клиент", "магазин", "ресторан", "кафе"]
    medical_keywords = ["врач", "медсестра", "медицин", "больниц", "клиник", "здоровье", "пациент"]
    logistics_keywords = ["водитель", "курьер", "логист", "склад", "доставк", "грузчик", "экспедитор"]
    
    work_type = "office"
    
    if any(kw in context_lower for kw in production_keywords):
        work_type = "production"
    elif any(kw in context_lower for kw in service_keywords):
        work_type = "service"
    elif any(kw in context_lower for kw in medical_keywords):
        work_type = "medical"
    elif any(kw in context_lower for kw in logistics_keywords):
        work_type = "logistics"
    elif any(kw in context_lower for kw in office_keywords):
        work_type = "office"
    
    age_group = "mixed"
    gender = "mixed"
    
    if any(word in context_lower for word in ["молод", "студент", "junior", "начинающ", "без опыта"]):
        age_group = "young"
    elif any(word in context_lower for word in ["опытн", "senior", "руководител", "директор"]):
        age_group = "middle"
    
    male_professions = ["программист", "разработчик", "инженер", "водитель", "слесарь", "сварщик"]
    female_professions = ["бухгалтер", "hr", "секретарь", "администратор"]
    
    if any(prof in context_lower for prof in male_professions):
        gender = "male"
    elif any(prof in context_lower for prof in female_professions):
        gender = "female"
    
    return {
        "work_type": work_type,
        "age_group": age_group,
        "gender": gender
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

def generate_demo_image_smart(context: str, segment: str, aspect_ratio: str = "16:9") -> str:
    """
    Генерация изображения с учётом контекста посадочной.
    """
    params = analyze_context_for_image(context, segment)
    
    scene_descriptions = {
        "office": "modern corporate office environment, people working with computers and laptops, team collaboration at desk, bright natural lighting through windows, professional business attire",
        "production": "industrial production facility, workers in safety helmets and uniforms, manufacturing floor with equipment, technical environment, safety gear, industrial lighting",
        "service": "retail or service environment, customer service setting, friendly staff interaction, clean modern interior, welcoming atmosphere",
        "medical": "medical facility, healthcare professionals in medical attire, clean clinical environment, professional medical setting",
        "logistics": "warehouse or logistics center, workers in uniform, organized storage area, delivery and transportation context"
    }
    
    age_descriptions = {
        "young": "young professionals aged 20-30",
        "middle": "experienced professionals aged 30-45",
        "mixed": "diverse age group of professionals"
    }
    
    gender_descriptions = {
        "male": "male professionals",
        "female": "female professionals",
        "mixed": "diverse team of male and female professionals"
    }
    
    scene = scene_descriptions.get(params["work_type"], scene_descriptions["office"])
    age_desc = age_descriptions.get(params["age_group"], age_descriptions["mixed"])
    gender_desc = gender_descriptions.get(params["gender"], gender_descriptions["mixed"])
    
    models = [openrouter_image_model()] + openrouter_image_fallbacks()
    last_err = None
    
    for model in models:
        try:
            user_prompt = (
                f"Professional PHOTOREALISTIC advertising photography. "
                f"Scene: {scene}. "
                f"People: {gender_desc}, {age_desc}. "
                f"Aspect ratio: {aspect_ratio}.\n\n"
                "CRITICAL REQUIREMENTS:\n"
                "- PHOTOREALISTIC style only (real photography, NOT illustration or 3D render)\n"
                "- NO text, letters, words, numbers, or typography anywhere\n"
                "- NO logos, brand names, or company signs\n"
                "- NO labels, captions, or written content\n"
                "- Real people in authentic work environment\n"
                "- Natural professional lighting\n"
                "- High-quality advertising photography aesthetic\n"
                "- Focus on people and workplace atmosphere"
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

def screen_0
