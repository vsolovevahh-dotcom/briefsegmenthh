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
.badge{ display:inline-block; padding:6px 10px; border:1px solid var(--border); border-radius:999px; background:#fafafa; font-size:0.85rem; color:#111827; }
.hint{ background:#fff7ed; border:1px solid #fed7aa; color:#9a3412; border-radius:14px; padding:12px 14px; }
.ok{ background:#ecfdf5; border:1px solid #a7f3d0; color:#065f46; border-radius:14px; padding:12px 14px; }
.ad{ border:1px solid var(--border); border-radius:14px; padding:14px; background:#fff; }
.ad-head{ font-weight:900; margin-bottom:6px; }
.ad-text{ color:#111827; margin-bottom:10px; white-space:pre-wrap; }
.ad-meta{ color:var(--muted); font-size:0.85rem; }
.ad-btn{ display:inline-block; padding:8px 12px; border-radius:10px; background:#111827; color:#fff; font-size:0.9rem; text-decoration:none; }
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
    "3. Тексты и креативы",
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
    "pl_yandex": False,
    "pl_vk": False,
    "pl_tgads": False,
    "pl_tgseeding": False,
    "fmt_yandex": [],
    "fmt_vk": [],
    "fmt_tgads": [],
    "ai_overwrite": False,
    "yandex_text_owner": "Клиент",
    "yandex_title": "",
    "yandex_body": "",
    "yandex_quicklinks": "",
    "yandex_creative_owner": "Клиент",
    "yandex_creative_links": "",
    "yandex_creative_brief": "",
    "vk_text_owner": "Клиент",
    "vk_post_text": "",
    "vk_cta": "Перейти",
    "vk_creative_owner": "Клиент",
    "vk_creative_links": "",
    "vk_creative_brief": "",
    "tg_text_owner": "Клиент",
    "tg_message": "",
    "tg_cta": "Подробнее",
    "tg_media_owner": "Клиент",
    "tg_media_links": "",
    "tg_media_brief": "",
    "seed_owner": "Клиент",
    "seed_image_text": "",
    "seed_post_text": "",
    "seed_links": "",
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

def remaining(max_len: int, value: str) -> int:
    value = value or ""
    return max(max_len - len(value), 0)

def limited_text_input(label: str, key: str, max_chars: int, placeholder: str = ""):
    current_val = st.session_state.get(key, "")
    val = st.text_input(label, value=current_val, max_chars=max_chars, placeholder=placeholder, key=f"_input_{key}")
    st.session_state[key] = val
    st.caption(f"Осталось {remaining(max_chars, val)} символов из {max_chars}")
    return val

def limited_text_area(label: str, key: str, max_chars: int, height: int = 110, placeholder: str = ""):
    current_val = st.session_state.get(key, "")
    val = st.text_area(label, value=current_val, max_chars=max_chars, height=height, placeholder=placeholder, key=f"_input_{key}")
    st.session_state[key] = val
    st.caption(f"Осталось {remaining(max_chars, val)} символов из {max_chars}")
    return val

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

def clamp(s: str, limit: int) -> str:
    s = (s or "").strip()
    if limit and len(s) > limit:
        s = s[:limit].rstrip()
    return s

def ai_generate_one_text(platform: str) -> dict:
    base = {
        "what_advertise": st.session_state.get("what_advertise", ""),
        "campaign_goal": st.session_state.get("campaign_goal", ""),
        "landing_url": st.session_state.get("landing_url", ""),
        "geo": st.session_state.get("geo", ""),
        "segment_desc": st.session_state.get("segment_desc", ""),
        "landing_context": st.session_state.get("landing_context", ""),
        "files_links": st.session_state.get("files_links", ""),
    }
    models = [openrouter_text_model()] + openrouter_text_fallbacks()

    if platform == "Яндекс":
        prompt = f"Ты — PMM/копирайтер. Сгенерируй РОВНО 1 вариант текста для Яндекс объявлений. Верни ТОЛЬКО JSON (без markdown/пояснений). Лимиты: title ≤ {LIMITS['yandex_title']} символов, body ≤ {LIMITS['yandex_body']} символов. Стиль: нейтрально-деловой, без клише и без обещаний типа 'гарантируем'.\n\nВводные: {json.dumps(base, ensure_ascii=False)}\n\nВерни JSON: {{\"title\":\"...\",\"body\":\"...\"}}"
        _, data = openrouter_chat_with_fallback(models=models, messages=[{"role": "user", "content": prompt}], temperature=0.4, max_tokens=260)
        content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
        obj = extract_json_obj(content)
        return {"title": clamp(obj.get("title", ""), LIMITS["yandex_title"]), "body": clamp(obj.get("body", ""), LIMITS["yandex_body"])}

    if platform == "VK":
        prompt = f"Ты — PMM/копирайтер. Сгенерируй РОВНО 1 вариант нативного текста для VK. Верни ТОЛЬКО JSON. Лимит: post ≤ {LIMITS['vk_post']} символов. CTA из списка: Перейти / Подробнее / Открыть / Откликнуться.\n\nВводные: {json.dumps(base, ensure_ascii=False)}\n\nВерни JSON: {{\"post\":\"...\",\"cta\":\"Подробнее\"}}"
        _, data = openrouter_chat_with_fallback(models=models, messages=[{"role": "user", "content": prompt}], temperature=0.55, max_tokens=520)
        content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
        obj = extract_json_obj(content)
        return {"post": clamp(obj.get("post", ""), LIMITS["vk_post"]), "cta": clamp(obj.get("cta", "Подробнее"), 30) or "Подробнее"}

    if platform == "Telegram Ads":
        prompt = f"Ты — PMM/копирайтер. Сгенерируй РОВНО 1 вариант текста для Telegram Ads. Верни ТОЛЬКО JSON. Лимит: message ≤ {LIMITS['tgads_text']} символов. CTA из списка: Подробнее / Перейти / Открыть.\n\nВводные: {json.dumps(base, ensure_ascii=False)}\n\nВерни JSON: {{\"message\":\"...\",\"cta\":\"Подробнее\"}}"
        _, data = openrouter_chat_with_fallback(models=models, messages=[{"role": "user", "content": prompt}], temperature=0.6, max_tokens=320)
        content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
        obj = extract_json_obj(content)
        return {"message": clamp(obj.get("message", ""), LIMITS["tgads_text"]), "cta": clamp(obj.get("cta", "Подробнее"), 30) or "Подробнее"}

    prompt = f"Ты — PMM/копирайтер. Сгенерируй РОВНО 1 вариант для Telegram посевов: 1) image_text — 1 строка (≤ {LIMITS['seed_img_text']} символов) для текста на креативе; 2) post — пост (≤ {LIMITS['seed_post']} символов) нативно, без ощущения баннера. Верни ТОЛЬКО JSON.\n\nВводные: {json.dumps(base, ensure_ascii=False)}\n\nВерни JSON: {{\"image_text\":\"...\",\"post\":\"...\"}}"
    _, data = openrouter_chat_with_fallback(models=models, messages=[{"role": "user", "content": prompt}], temperature=0.7, max_tokens=720)
    content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
    obj = extract_json_obj(content)
    return {"image_text": clamp(obj.get("image_text", ""), LIMITS["seed_img_text"]), "post": clamp(obj.get("post", ""), LIMITS["seed_post"])}

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
    models = [openrouter_image_model()] + openrouter_image_fallbacks()
    last_err = None
    for model in models:
        try:
            user_prompt = f"{prompt}\n\nAspect ratio: {aspect_ratio}."
            _, data = openrouter_chat_with_fallback(models=[model], messages=[{"role": "user", "content": user_prompt}], temperature=0.2, max_tokens=200, modalities=["image"], image_config=None)
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
    with st.expander("Коротко про hh Сегменты", expanded=False):
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
        files_links = st.text_area("Файлы/материалы (ссылки)", value=st.session_state.get("files_links", ""), height=90, placeholder="Лого / брендбук / референсы / исходники (ссылки)", key="_files_links")
        st.session_state.files_links = files_links
        contact_name = st.text_input("Контактное лицо (кто заполняет)*", value=st.session_state.get("contact_name", ""), placeholder="Имя", key="_contact_name")
        st.session_state.contact_name = contact_name
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
            st.session_state.nav_page = "3. Тексты и креативы"
            st.rerun()
        st.button("Далее →", on_click=go_next, type="primary", use_container_width=True)

def screen_3():
    st.title("Тексты и креативы")
    st.caption("Заполните тексты и креативы по выбранным площадкам и форматам. Данные сохраняются автоматически.")
    selected = get_selected_platforms()
    if not selected:
        st.markdown('<div class="hint">Сначала выберите площадки на шаге 2.</div>', unsafe_allow_html=True)
        def back_to_step2():
            st.session_state.nav_page = "2. Креативы и площадки"
            st.rerun()
        st.button("← Вернуться к шагу 2", on_click=back_to_step2, use_container_width=True)
        return
    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)
    st.markdown("### AI (опционально)")
    st.caption("Сгенерируем по 1 варианту текста для выбранных площадок, используя только данные из шага 1.")
    ai_overwrite = st.checkbox("Перезаписать уже заполненные поля", value=st.session_state.get("ai_overwrite", False), key="_ai_overwrite")
    st.session_state.ai_overwrite = ai_overwrite
    if st.button("⚡ Сгенерировать тексты (1 вариант)", use_container_width=True, type="primary"):
        if not openrouter_api_key():
            st.error("Добавьте OPENROUTER_API_KEY в Secrets, чтобы включить генерацию.")
        elif not ((st.session_state.what_advertise or "").strip() and (st.session_state.segment_desc or "").strip() and (st.session_state.landing_url or "").strip()):
            st.error("Заполните на шаге 1 минимум: «Что рекламируем», «Описание сегмента», «Посадочная ссылка». ")
        else:
            logs = []
            updated_any = False
            overwrite = bool(st.session_state.ai_overwrite)
            with st.spinner("Генерируем тексты…"):
                for p in selected:
                    try:
                        out = ai_generate_one_text(p)
                        if p == "Яндекс":
                            if overwrite or not (st.session_state.yandex_title or "").strip():
                                st.session_state.yandex_title = out.get("title", st.session_state.yandex_title)
                                updated_any = True
                            if overwrite or not (st.session_state.yandex_body or "").strip():
                                st.session_state.yandex_body = out.get("body", st.session_state.yandex_body)
                                updated_any = True
                        elif p == "VK":
                            if overwrite or not (st.session_state.vk_post_text or "").strip():
                                st.session_state.vk_post_text = out.get("post", st.session_state.vk_post_text)
                                updated_any = True
                            if overwrite and out.get("cta"):
                                st.session_state.vk_cta = out.get("cta")
                                updated_any = True
                        elif p == "Telegram Ads":
                            if overwrite or not (st.session_state.tg_message or "").strip():
                                st.session_state.tg_message = out.get("message", st.session_state.tg_message)
                                updated_any = True
                            if overwrite and out.get("cta"):
                                st.session_state.tg_cta = out.get("cta")
                                updated_any = True
                        else:
                            if overwrite or not (st.session_state.seed_image_text or "").strip():
                                st.session_state.seed_image_text = out.get("image_text", st.session_state.seed_image_text)
                                updated_any = True
                            if overwrite or not (st.session_state.seed_post_text or "").strip():
                                st.session_state.seed_post_text = out.get("post", st.session_state.seed_post_text)
                                updated_any = True
                    except Exception as e:
                        logs.append(f"{p}: {e}")
            if updated_any:
                st.markdown('<div class="ok">Готово! Тексты подставлены в поля ниже.</div>', unsafe_allow_html=True)
                st.rerun()
            else:
                st.markdown('<div class="hint">Генерация не выполнена — проверьте сообщение ниже.</div>', unsafe_allow_html=True)
            if logs:
                st.code("\n".join(logs))
    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)
    if "Яндекс" in selected:
        fmts = get_selected_formats("Яндекс")
        with st.expander("Яндекс", expanded=True):
            st.markdown("### Тексты")
            yandex_text_owner = st.radio("Кто готовит тексты?", ["Клиент", "Команда hh"], index=0 if st.session_state.get("yandex_text_owner") == "Клиент" else 1, horizontal=True, key="_yandex_text_owner")
            st.session_state.yandex_text_owner = yandex_text_owner
            limited_text_input("Заголовок (до 56)", "yandex_title", LIMITS["yandex_title"], placeholder="Коротко и по делу")
            limited_text_area("Текст (до 81)", "yandex_body", LIMITS["yandex_body"], height=90, placeholder="1–2 выгоды + действие")
            yandex_quicklinks = st.text_area("Быстрые ссылки (опц.) — по одной на строку: Название | URL", value=st.session_state.get("yandex_quicklinks", ""), height=90, placeholder="Карьерный сайт | https://...\nВакансии | https://...", key="_yandex_quicklinks")
            st.session_state.yandex_quicklinks = yandex_quicklinks
            st.markdown("### Креативы")
            yandex_creative_owner = st.radio("Кто готовит креативы?", ["Клиент", "Команда hh"], index=0 if st.session_state.get("yandex_creative_owner") == "Клиент" else 1, horizontal=True, key="_yandex_creative_owner")
            st.session_state.yandex_creative_owner = yandex_creative_owner
            if st.session_state.yandex_creative_owner == "Клиент":
                yandex_creative_links = st.text_area("Ссылки на материалы и исходники", value=st.session_state.get("yandex_creative_links", ""), height=90, key="_yandex_creative_links")
                st.session_state.yandex_creative_links = yandex_creative_links
            else:
                yandex_creative_brief = st.text_area("Что должно быть на креативе (1–2 строки)", value=st.session_state.get("yandex_creative_brief", ""), height=90, key="_yandex_creative_brief")
                st.session_state.yandex_creative_brief = yandex_creative_brief
                yandex_creative_links = st.text_area("Референсы и исходники (ссылки)", value=st.session_state.get("yandex_creative_links", ""), height=70, key="_yandex_creative_links2")
                st.session_state.yandex_creative_links = yandex_creative_links
            st.markdown(f"**Выбранные форматы:** {', '.join(fmts) if fmts else 'не выбраны'}")
    if "VK" in selected:
        fmts = get_selected_formats("VK")
        with st.expander("VK", expanded=False):
            st.markdown("### Тексты")
            vk_text_owner = st.radio("Кто готовит тексты?", ["Клиент", "Команда hh"], index=0 if st.session_state.get("vk_text_owner") == "Клиент" else 1, horizontal=True, key="_vk_text_owner")
            st.session_state.vk_text_owner = vk_text_owner
            limited_text_area("Текст поста (до 700)", "vk_post_text", LIMITS["vk_post"], height=130, placeholder="1–2 выгоды + действие")
            vk_cta = st.selectbox("CTA (опц.)", ["Перейти", "Подробнее", "Открыть", "Откликнуться"], index=["Перейти", "Подробнее", "Открыть", "Откликнуться"].index(st.session_state.get("vk_cta", "Перейти")), key="_vk_cta")
            st.session_state.vk_cta = vk_cta
            st.markdown("### Креативы")
            vk_creative_owner = st.radio("Кто готовит креативы?", ["Клиент", "Команда hh"], index=0 if st.session_state.get("vk_creative_owner") == "Клиент" else 1, horizontal=True, key="_vk_creative_owner")
            st.session_state.vk_creative_owner = vk_creative_owner
            if st.session_state.vk_creative_owner == "Клиент":
                vk_creative_links = st.text_area("Ссылки на материалы и исходники", value=st.session_state.get("vk_creative_links", ""), height=90, key="_vk_creative_links")
                st.session_state.vk_creative_links = vk_creative_links
            else:
                vk_creative_brief = st.text_area("Что должно быть на креативе (1–2 строки)", value=st.session_state.get("vk_creative_brief", ""), height=90, key="_vk_creative_brief")
                st.session_state.vk_creative_brief = vk_creative_brief
                vk_creative_links = st.text_area("Референсы и исходники (ссылки)", value=st.session_state.get("vk_creative_links", ""), height=70, key="_vk_creative_links2")
                st.session_state.vk_creative_links = vk_creative_links
            st.markdown(f"**Выбранные форматы:** {', '.join(fmts) if fmts else 'не выбраны'}")
    if "Telegram Ads" in selected:
        fmts = get_selected_formats("Telegram Ads")
        with st.expander("Telegram Ads", expanded=False):
            if "Текст" in fmts:
                st.markdown("### TG Ads — текст")
                tg_text_owner = st.radio("Кто готовит текст?", ["Клиент", "Команда hh"], index=0 if st.session_state.get("tg_text_owner") == "Клиент" else 1, horizontal=True, key="_tg_text_owner")
                st.session_state.tg_text_owner = tg_text_owner
                limited_text_area("Текст сообщения (до 200)", "tg_message", LIMITS["tgads_text"], height=110, placeholder="1–2 предложения + CTA")
                tg_cta = st.selectbox("CTA (опц.)", ["Подробнее", "Перейти", "Открыть"], index=["Подробнее", "Перейти", "Открыть"].index(st.session_state.get("tg_cta", "Подробнее")), key="_tg_cta")
                st.session_state.tg_cta = tg_cta
            if "Изображение" in fmts or "Видео" in fmts:
                st.markdown("### TG Ads — медиа")
                tg_media_owner = st.radio("Кто готовит медиа?", ["Клиент", "Команда hh"], index=0 if st.session_state.get("tg_media_owner") == "Клиент" else 1, horizontal=True, key="_tg_media_owner")
                st.session_state.tg_media_owner = tg_media_owner
                if st.session_state.tg_media_owner == "Клиент":
                    tg_media_links = st.text_area("Ссылки на материалы и исходники", value=st.session_state.get("tg_media_links", ""), height=90, key="_tg_media_links")
                    st.session_state.tg_media_links = tg_media_links
                else:
                    tg_media_brief = st.text_area("Что должно быть на креативе (1–2 строки)", value=st.session_state.get("tg_media_brief", ""), height=90, key="_tg_media_brief")
                    st.session_state.tg_media_brief = tg_media_brief
                    tg_media_links = st.text_area("Референсы и исходники (ссылки)", value=st.session_state.get("tg_media_links", ""), height=70, key="_tg_media_links2")
                    st.session_state.tg_media_links = tg_media_links
            st.markdown(f"**Выбранные форматы:** {', '.join(fmts) if fmts else 'не выбраны'}")
    if "Telegram посевы" in selected:
        with st.expander("Telegram посевы", expanded=False):
            st.markdown("Важно: в посевах картинка обычно с текстом на ней — укажите ключевое сообщение.")
            seed_owner = st.radio("Кто готовит материалы?", ["Клиент", "Команда hh"], index=0 if st.session_state.get("seed_owner") == "Клиент" else 1, horizontal=True, key="_seed_owner")
            st.session_state.seed_owner = seed_owner
            limited_text_input("Текст на изображении (1 строка, до 40)", "seed_image_text", LIMITS["seed_img_text"], placeholder="Короткое УТП")
            limited_text_area("Текст поста (до 500)", "seed_post_text", LIMITS["seed_post"], height=150, placeholder="УТП → пояснение → ссылка")
            seed_links = st.text_area("Ссылки на материалы и исходники (опц.)", value=st.session_state.get("seed_links", ""), height=80, key="_seed_links")
            st.session_state.seed_links = seed_links
    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)
    c1, c2 = st.columns([1, 1])
    with c1:
        def back():
            st.session_state.nav_page = "2. Креативы и площадки"
            st.rerun()
        st.button("← Назад", on_click=back, use_container_width=True)
    with c2:
        def go_next():
            st.session_state.nav_page = "4. Примерный вид объявлений"
            st.rerun()
        st.button("Далее →", on_click=go_next, type="primary", use_container_width=True)

def demo_card_yandex(fmt: str):
    title = (st.session_state.get("yandex_title", "") or "").strip() or "Заголовок"
    body = (st.session_state.get("yandex_body", "") or "").strip() or "Текст объявления"
    st.markdown(f"<div class='badge'>Яндекс · {fmt}</div>", unsafe_allow_html=True)
    st.markdown(f'<div class="ad"><div class="ad-head">{title}</div><div class="ad-text">{body}</div><div class="ad-meta">Ссылка: {st.session_state.get("landing_url", "") or "https://..."}</div></div>', unsafe_allow_html=True)

def demo_card_vk(fmt: str):
    post = (st.session_state.get("vk_post_text", "") or "").strip() or "Текст поста"
    cta = st.session_state.get("vk_cta", "Перейти")
    st.markdown(f"<div class='badge'>VK · {fmt}</div>", unsafe_allow_html=True)
    st.markdown(f'<div class="ad"><div class="ad-text">{post}</div><a class="ad-btn" href="#" onclick="return false;">{cta}</a><div class="ad-meta" style="margin-top:10px;">Ссылка: {st.session_state.get("landing_url", "") or "https://..."}</div></div>', unsafe_allow_html=True)

def demo_card_tg_text():
    msg = (st.session_state.get("tg_message", "") or "").strip() or "Текст сообщения"
    cta = st.session_state.get("tg_cta", "Подробнее")
    st.markdown("<div class='badge'>Telegram Ads · Текст</div>", unsafe_allow_html=True)
    st.markdown(f'<div class="ad"><div class="ad-text">{msg}</div><div class="ad-meta">CTA: {cta}</div></div>', unsafe_allow_html=True)

def demo_card_tg_media(fmt: str):
    caption = (st.session_state.get("tg_message", "") or "").strip() or "Подпись / сопроводительный текст"
    st.markdown(f"<div class='badge'>Telegram Ads · {fmt}</div>", unsafe_allow_html=True)
    st.markdown(f'<div class="ad"><div class="ad-text">{caption}</div><div class="ad-meta">Ссылка: {st.session_state.get("landing_url", "") or "https://..."}</div></div>', unsafe_allow_html=True)

def demo_card_seeding():
    img_text = (st.session_state.get("seed_image_text", "") or "").strip() or "Текст на изображении"
    post = (st.session_state.get("seed_post_text", "") or "").strip() or "Текст поста"
    st.markdown("<div class='badge'>Telegram посевы · Пост + изображение</div>", unsafe_allow_html=True)
    st.markdown(f'<div class="ad"><div class="ad-head">{img_text}</div><div class="ad-text">{post}</div><div class="ad-meta">Ссылка: {st.session_state.get("landing_url", "") or "https://..."}</div></div>', unsafe_allow_html=True)

def render_demo_image(platform: str, fmt: str):
    """Отображает сгенерированное изображение с поддержкой base64 и старых версий Streamlit."""
    key = f"{platform}|{fmt}"
    images = st.session_state.get("demo_images", {})
    if not isinstance(images, dict):
        images = {}
    
    url = images.get(key)
    
    if not url:
        st.info("Демо-визуал пока не сгенерирован. Нажмите «🎨 Сгенерировать демо-визуалы» выше.")
        return
    
    try:
        # Если это base64 data URL
        if url.startswith("data:image"):
            header, encoded = url.split(",", 1)
            image_bytes = base64.b64decode(encoded)
            image_io = BytesIO(image_bytes)
            
            # Обратная совместимость с разными версиями Streamlit
            try:
                st.image(image_io, use_container_width=True)
            except TypeError:
                st.image(image_io, use_column_width=True)
                
        # Если это обычный URL
        elif url.startswith("http"):
            try:
                st.image(url, use_container_width=True)
            except TypeError:
                st.image(url, use_column_width=True)
        else:
            st.warning(f"Неподдерживаемый формат изображения")
            
    except Exception as e:
        st.error(f"Ошибка отображения изображения: {str(e)}")
        with st.expander("Детали ошибки"):
            st.code(f"URL: {url[:200]}...")

def screen_4():
    st.title("Примерный вид рекламных объявлений")
    st.caption("Быстрый мокап, чтобы согласовать направление.")
    selected = get_selected_platforms()
    if not selected:
        st.markdown('<div class="hint">Сначала выберите площадки на шаге 2.</div>', unsafe_allow_html=True)
        return
    st.markdown('<div class="card"><div style="font-weight:900; font-size:1.05rem; margin-bottom:6px;">Демо-пример</div><div class="small-muted">Финальный вид зависит от модерации и конкретного формата. Здесь — быстрый мокап.</div></div>', unsafe_allow_html=True)
    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)
    with st.expander("AI-генерация демо-визуалов (опционально)", expanded=False):
        if not openrouter_api_key():
            st.warning("Чтобы генерировать демо-картинки, добавьте OPENROUTER_API_KEY в Streamlit Secrets.")
        else:
            st.caption("Сгенерируем по 1 демо-визуалу на выбранный формат (где уместно). Основная модель — OPENROUTER_IMAGE_MODEL, фоллбеки — OPENROUTER_IMAGE_MODEL_FALLBACKS.")
            st.code('OPENROUTER_IMAGE_MODEL = "black-forest-labs/flux-schnell"\nOPENROUTER_IMAGE_MODEL_FALLBACKS = "black-forest-labs/flux-schnell, black-forest-labs/flux-dev"', language="toml")
            if st.button("🎨 Сгенерировать демо-визуалы", type="primary", use_container_width=True):
                errors = []
                with st.spinner("Генерируем демо-визуалы..."):
                    for p in selected:
                        fmts = get_selected_formats(p)
                        for f in fmts:
                            need_visual = ((p in ["Яндекс", "VK"] and f in ["Изображение", "Видео"]) or (p == "Telegram Ads" and f in ["Изображение", "Видео"]) or (p == "Telegram посевы"))
                            if not need_visual:
                                continue
                            core = st.session_state.get("what_advertise", "") or "HR-кампания"
                            seg = st.session_state.get("segment_desc", "") or "соискатели"
                            geo = st.session_state.get("geo", "") or "Россия"
                            if p == "Telegram посевы":
                                utp = st.session_state.get("seed_image_text", "") or "Ключевое сообщение"
                                aspect = "4:5"
                            elif p == "Яндекс":
                                utp = st.session_state.get("yandex_title", "") or "Ключевое сообщение"
                                aspect = "16:9"
                            elif p == "VK":
                                vk_post = st.session_state.get("vk_post_text", "")
                                utp = (vk_post[:60] if vk_post else "Ключевое сообщение")
                                aspect = "16:9"
                            else:
                                utp = st.session_state.get("tg_media_brief", "") or st.session_state.get("tg_message", "") or "Ключевое сообщение"
                                aspect = "16:9"
                            prompt = f"Create a clean modern advertising creative (no real brand logos; use generic placeholders). Topic: {core}. Audience: {seg}. Geo: {geo}. Main readable headline text: '{utp}'. Style: minimal, corporate, high contrast, large readable typography. No tiny text."
                            try:
                                img = generate_demo_image(prompt, aspect_ratio=aspect)
                                if img:
                                    if not isinstance(st.session_state.demo_images, dict):
                                        st.session_state.demo_images = {}
                                    st.session_state.demo_images[f"{p}|{f}"] = img
                            except Exception as e:
                                errors.append(f"{p} · {f}: {e}")
                if errors:
                    st.warning("Часть визуалов не удалось сгенерировать — подробности ниже.")
                    st.code("\n".join(errors))
                else:
                    st.success("Готово! Пролистайте ниже — демо-визуалы появятся в карточках.")
                    st.rerun()
    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)
    tabs = st.tabs(selected)
    for i, p in enumerate(selected):
        with tabs[i]:
            fmts = get_selected_formats(p)
            if p == "Яндекс":
                if not fmts:
                    st.info("На шаге 2 не выбраны форматы для Яндекс.")
                for f in (fmts or []):
                    demo_card_yandex(f)
                    if f in ["Изображение", "Видео"]:
                        render_demo_image("Яндекс", f)
                    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)
            elif p == "VK":
                if not fmts:
                    st.info("На шаге 2 не выбраны форматы для VK.")
                for f in (fmts or []):
                    demo_card_vk(f)
                    if f in ["Изображение", "Видео"]:
                        render_demo_image("VK", f)
                    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)
            elif p == "Telegram Ads":
                if not fmts:
                    st.info("На шаге 2 не выбраны форматы для Telegram Ads.")
                if "Текст" in fmts:
                    demo_card_tg_text()
                    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)
                for f in [x for x in fmts if x in ["Изображение", "Видео"]]:
                    demo_card_tg_media(f)
                    render_demo_image("Telegram Ads", f)
                    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)
            else:
                demo_card_seeding()
                render_demo_image("Telegram посевы", "Пост + изображение с текстом")
    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)
    c1, c2 = st.columns([1, 1])
    with c1:
        def back():
            st.session_state.nav_page = "3. Тексты и креативы"
            st.rerun()
        st.button("← Назад", on_click=back, use_container_width=True)
    with c2:
        st.button("Готово ✅", use_container_width=True)

page = st.session_state.get("nav_page", PAGES[0])
if page == "0. Старт":
    screen_0()
elif page == "1. Основная информация":
    screen_1()
elif page == "2. Креативы и площадки":
    screen_2()
elif page == "3. Тексты и креативы":
    screen_3()
elif page == "4. Примерный вид объявлений":
    screen_4()
else:
    st.session_state.nav_page = "0. Старт"
    screen_0()
