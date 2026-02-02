# app.py
import json
import re
from copy import deepcopy

import requests
import streamlit as st

# =========================
# Config
# =========================
st.set_page_config(
    page_title="hh Сегменты — заявка",
    page_icon="🧩",
    layout="wide",
)

PAGES = [
    "Старт",
    "Основная информация",
    "Креативы и площадки",
    "Тексты и креативы",
    "Примерный вид объявлений",
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

DEFAULT_FORM = {
    # Step 1 (base)
    "what_advertise": "",
    "campaign_goal": "",
    "landing_url": "",
    "geo": "",
    "segment_desc": "",
    "files_links": "",
    "contact_name": "",
    "landing_context": "",

    # Step 2 (platforms)
    "pl_yandex": False,
    "pl_vk": False,
    "pl_tgads": False,
    "pl_tgseeding": False,

    # Step 2 (formats)
    "fmt_yandex": [],
    "fmt_vk": [],
    "fmt_tgads": [],
    # seeding format fixed by definition

    # Step 3 (texts)
    "yandex_title": "",
    "yandex_body": "",
    "vk_post_text": "",
    "vk_cta": "Перейти",
    "tg_message": "",
    "tg_cta": "Подробнее",
    "seed_image_text": "",
    "seed_post_text": "",

    # demo images: dict key -> url/data_url
    "demo_images": {},

    # last generation logs
    "gen_logs": [],
    "gen_ok": None,
}

# =========================
# Styles
# =========================
st.markdown(
    """
<style>
:root{
  --muted:#6b7280;
  --border:#e5e7eb;
  --card:#ffffff;
  --soft:#f7f7f8;
}
.small-muted{ color:var(--muted); font-size:0.92rem; }
.hr{ height:1px; background:var(--border); margin:18px 0; }
.card{ background:var(--card); border:1px solid var(--border); border-radius:16px; padding:16px; }
.badge{ display:inline-block; padding:6px 10px; border:1px solid var(--border); border-radius:999px; background:#fafafa; font-size:0.85rem; color:#111827; }
.ad{ border:1px solid var(--border); border-radius:14px; padding:14px; background:#fff; }
.ad-head{ font-weight:800; margin-bottom:6px; }
.ad-text{ color:#111827; margin-bottom:10px; white-space:pre-wrap; }
.ad-meta{ color:var(--muted); font-size:0.85rem; }
.ad-btn{ display:inline-block; padding:8px 12px; border-radius:10px; background:#111827; color:#fff; font-size:0.9rem; text-decoration:none; }
.hint{ background:#FFF7E6; border:1px solid #FFE7BA; border-radius:12px; padding:12px 14px; color:#8A5B00; margin:12px 0; }
</style>
""",
    unsafe_allow_html=True,
)

# =========================
# Persistent store (IMPORTANT)
# =========================
def get_form() -> dict:
    if "form_data" not in st.session_state:
        st.session_state["form_data"] = deepcopy(DEFAULT_FORM)
    return st.session_state["form_data"]

def ui_key(field: str) -> str:
    return f"ui_{field}"

def reset_form():
    # удаляем ui_* ключи, чтобы виджеты заново взяли дефолты из form_data
    for k in list(st.session_state.keys()):
        if k.startswith("ui_"):
            del st.session_state[k]
    st.session_state["form_data"] = deepcopy(DEFAULT_FORM)
    st.session_state["nav_page"] = PAGES[0]
    st.session_state["nav_page_ui"] = PAGES[0]

def set_page(page: str):
    st.session_state["nav_page"] = page
    st.session_state["nav_page_ui"] = page

# =========================
# Widget wrappers (read/write through form_data)
# =========================
def w_text_input(label, field, placeholder="", help=None):
    form = get_form()
    val = st.text_input(label, value=form.get(field, ""), key=ui_key(field), placeholder=placeholder, help=help)
    form[field] = val
    return val

def w_text_area(label, field, height=120, placeholder="", help=None, max_chars=None, label_visibility="visible"):
    form = get_form()
    kwargs = {}
    if max_chars is not None:
        kwargs["max_chars"] = max_chars
    val = st.text_area(
        label,
        value=form.get(field, ""),
        key=ui_key(field),
        height=height,
        placeholder=placeholder,
        help=help,
        label_visibility=label_visibility,
        **kwargs,
    )
    form[field] = val
    return val

def w_checkbox(label, field, help=None):
    form = get_form()
    val = st.checkbox(label, value=bool(form.get(field, False)), key=ui_key(field), help=help)
    form[field] = val
    return val

def w_multiselect(label, field, options, placeholder=""):
    form = get_form()
    default = form.get(field, []) or []
    # фильтруем дефолт, чтобы не падало если список опций поменялся
    default = [x for x in default if x in options]
    val = st.multiselect(label, options, default=default, key=ui_key(field), placeholder=placeholder)
    form[field] = val
    return val

def w_selectbox(label, field, options):
    form = get_form()
    cur = form.get(field, options[0] if options else "")
    idx = options.index(cur) if cur in options else 0
    val = st.selectbox(label, options, index=idx, key=ui_key(field))
    form[field] = val
    return val

def remaining(limit: int, value: str) -> int:
    value = value or ""
    return max(limit - len(value), 0)

def limited_text_input(label, field, limit, placeholder=""):
    val = w_text_input(label, field, placeholder=placeholder)
    st.caption(f"Осталось {remaining(limit, val)} / {limit}")
    return val

def limited_text_area(label, field, limit, height=110, placeholder=""):
    val = w_text_area(label, field, height=height, placeholder=placeholder, max_chars=limit)
    st.caption(f"Осталось {remaining(limit, val)} / {limit}")
    return val

# =========================
# Helpers (landing fetch)
# =========================
def normalize_url(u: str) -> str:
    u = (u or "").strip()
    if not u:
        return ""
    if not re.match("^https?://", u, flags=re.I):
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
        text = re.sub("(?is)<script.*?>.*?</script>", " ", html)
        text = re.sub("(?is)<style.*?>.*?</style>", " ", text)
        text = re.sub("(?s)<.*?>", " ", text)
        text = " ".join(text.split())
        return text[:6000]
    except Exception as e:
        return f"(Не удалось загрузить страницу: {e})"

def selected_platforms():
    form = get_form()
    res = []
    if form.get("pl_yandex"):
        res.append("Яндекс")
    if form.get("pl_vk"):
        res.append("VK")
    if form.get("pl_tgads"):
        res.append("Telegram Ads")
    if form.get("pl_tgseeding"):
        res.append("Telegram посевы")
    return res

def selected_formats(platform: str):
    form = get_form()
    if platform == "Яндекс":
        return form.get("fmt_yandex", []) or []
    if platform == "VK":
        return form.get("fmt_vk", []) or []
    if platform == "Telegram Ads":
        return form.get("fmt_tgads", []) or []
    if platform == "Telegram посевы":
        return ["Пост + изображение с текстом"] if form.get("pl_tgseeding") else []
    return []

# =========================
# OpenRouter (texts)
# =========================
def openrouter_api_key() -> str:
    try:
        return (st.secrets.get("OPENROUTER_API_KEY", "") or "").strip()
    except Exception:
        return ""

def openrouter_text_model() -> str:
    return (st.secrets.get("OPENROUTER_TEXT_MODEL", "") or "").strip() or "google/gemini-flash-1.5"

def openrouter_image_model() -> str:
    return (st.secrets.get("OPENROUTER_IMAGE_MODEL", "") or "").strip() or "black-forest-labs/flux.2-flex"

def openrouter_image_fallbacks():
    raw = (st.secrets.get("OPENROUTER_IMAGE_MODEL_FALLBACKS", "") or "").strip()
    models = [m.strip() for m in raw.split(",") if m.strip()]
    if not models:
        models = ["black-forest-labs/flux.2-pro", "openai/gpt-image-1"]
    return models

def openrouter_headers():
    api_key = openrouter_api_key()
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY не задан в Secrets")
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": st.secrets.get("OPENROUTER_REFERER", "https://streamlit.app"),
        "X-Title": st.secrets.get("OPENROUTER_APP_TITLE", "hh-segments-brief"),
    }

def openrouter_chat(model: str, messages: list, temperature=0.6, max_tokens=800):
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    r = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=openrouter_headers(),
        json=payload,
        timeout=90,
    )
    if r.status_code != 200:
        raise RuntimeError(f"OpenRouter API error {r.status_code}: {(r.text or '')[:1200]}")
    return r.json()

def extract_json_obj(text: str) -> dict:
    if not text:
        return {}
    text = text.strip()
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        pass
    # try slice {...}
    a = text.find("{")
    b = text.rfind("}")
    if a != -1 and b != -1 and b > a:
        try:
            obj = json.loads(text[a : b + 1])
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}
    return {}

def clamp(s: str, limit: int) -> str:
    s = (s or "").strip()
    return s[:limit].rstrip() if limit and len(s) > limit else s

def ai_generate_one_text(platform: str) -> dict:
    form = get_form()
    base = {
        "what_advertise": form.get("what_advertise", ""),
        "campaign_goal": form.get("campaign_goal", ""),
        "landing_url": form.get("landing_url", ""),
        "geo": form.get("geo", ""),
        "segment_desc": form.get("segment_desc", ""),
        "landing_context": form.get("landing_context", ""),
        "files_links": form.get("files_links", ""),
    }

    model = openrouter_text_model()

    if platform == "Яндекс":
        prompt = f"""
Ты — PMM/копирайтер.
Сгенерируй РОВНО 1 вариант текста для Яндекс объявлений.
Верни ТОЛЬКО JSON без markdown и без пояснений.
Лимиты: title ≤ {LIMITS["yandex_title"]} символов, body ≤ {LIMITS["yandex_body"]} символов.
Стиль: нейтрально-деловой, без клише, без агрессии, без «гарантируем».

Вводные: {json.dumps(base, ensure_ascii=False)}

Верни JSON:
{{"title":"...","body":"..."}}
""".strip()
        data = openrouter_chat(model, [{"role": "user", "content": prompt}], temperature=0.4, max_tokens=260)
        content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
        obj = extract_json_obj(content)
        return {
            "title": clamp(obj.get("title", ""), LIMITS["yandex_title"]),
            "body": clamp(obj.get("body", ""), LIMITS["yandex_body"]),
        }

    if platform == "VK":
        prompt = f"""
Ты — PMM/копирайтер.
Сгенерируй РОВНО 1 вариант нативного поста для VK.
Верни ТОЛЬКО JSON без пояснений.
Лимит: post ≤ {LIMITS["vk_post"]} символов.
CTA из списка: Перейти / Подробнее / Открыть / Откликнуться.

Вводные: {json.dumps(base, ensure_ascii=False)}

Верни JSON:
{{"post":"...","cta":"Перейти"}}
""".strip()
        data = openrouter_chat(model, [{"role": "user", "content": prompt}], temperature=0.55, max_tokens=520)
        content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
        obj = extract_json_obj(content)
        return {
            "post": clamp(obj.get("post", ""), LIMITS["vk_post"]),
            "cta": clamp(obj.get("cta", "Перейти"), 30) or "Перейти",
        }

    if platform == "Telegram Ads":
        prompt = f"""
Ты — PMM/копирайтер.
Сгенерируй РОВНО 1 вариант текста для Telegram Ads.
Верни ТОЛЬКО JSON без пояснений.
Лимит: message ≤ {LIMITS["tgads_text"]} символов.
CTA из списка: Подробнее / Перейти / Открыть.

Вводные: {json.dumps(base, ensure_ascii=False)}

Верни JSON:
{{"message":"...","cta":"Подробнее"}}
""".strip()
        data = openrouter_chat(model, [{"role": "user", "content": prompt}], temperature=0.6, max_tokens=320)
        content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
        obj = extract_json_obj(content)
        return {
            "message": clamp(obj.get("message", ""), LIMITS["tgads_text"]),
            "cta": clamp(obj.get("cta", "Подробнее"), 30) or "Подробнее",
        }

    # Telegram seeding
    prompt = f"""
Ты — PMM/копирайтер.
Сгенерируй РОВНО 1 вариант для Telegram посевов:
1) image_text — 1 строка (≤ {LIMITS["seed_img_text"]} символов) для текста на креативе
2) post — пост (≤ {LIMITS["seed_post"]} символов) нативно, без ощущения баннера
Верни ТОЛЬКО JSON без пояснений.

Вводные: {json.dumps(base, ensure_ascii=False)}

Верни JSON:
{{"image_text":"...","post":"..."}}
""".strip()
    data = openrouter_chat(model, [{"role": "user", "content": prompt}], temperature=0.7, max_tokens=720)
    content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
    obj = extract_json_obj(content)
    return {
        "image_text": clamp(obj.get("image_text", ""), LIMITS["seed_img_text"]),
        "post": clamp(obj.get("post", ""), LIMITS["seed_post"]),
    }

# =========================
# OpenRouter (images) — IMPORTANT: images endpoint for Flux
# =========================
def aspect_to_size(aspect: str) -> str:
    # best-effort sizes (если провайдер ограничивает — можно заменить на 1024x1024)
    if aspect == "16:9":
        return "1024x576"
    if aspect == "4:5":
        return "1024x1280"
    if aspect == "1:1":
        return "1024x1024"
    return "1024x1024"

def openrouter_image_generate(model: str, prompt: str, aspect: str = "16:9") -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "size": aspect_to_size(aspect),
        "n": 1,
    }
    r = requests.post(
        "https://openrouter.ai/api/v1/images/generations",
        headers=openrouter_headers(),
        json=payload,
        timeout=120,
    )
    if r.status_code != 200:
        raise RuntimeError(f"OpenRouter Images error {r.status_code}: {(r.text or '')[:1200]}")
    data = r.json()

    # most common formats
    if isinstance(data, dict) and data.get("data"):
        item = data["data"][0] or {}
        if isinstance(item, dict):
            if item.get("url"):
                return item["url"]
            if item.get("b64_json"):
                return f"data:image/png;base64,{item['b64_json']}"
            if isinstance(item.get("image_url"), dict) and item["image_url"].get("url"):
                return item["image_url"]["url"]

    # fallback: search data:image...
    txt = json.dumps(data, ensure_ascii=False)
    m = re.search(r"(data:image\/[a-zA-Z]+;base64,[A-Za-z0-9+/=]+)", txt)
    if m:
        return m.group(1)

    raise RuntimeError("Не удалось извлечь изображение из ответа OpenRouter Images")

def generate_demo_image(prompt: str, aspect: str = "16:9") -> str:
    models = [openrouter_image_model()] + openrouter_image_fallbacks()
    last_err = None
    for m in models:
        try:
            return openrouter_image_generate(m, prompt, aspect=aspect)
        except Exception as e:
            last_err = e
    raise last_err or RuntimeError("Не удалось сгенерировать изображение")

# =========================
# Sidebar nav
# =========================
if "nav_page" not in st.session_state:
    st.session_state["nav_page"] = PAGES[0]
if "nav_page_ui" not in st.session_state:
    st.session_state["nav_page_ui"] = st.session_state["nav_page"]

def sync_nav():
    st.session_state["nav_page"] = st.session_state["nav_page_ui"]

st.sidebar.markdown("## 🧩 hh Сегменты — заявка")
st.sidebar.markdown('<div class="small-muted">Форма → заявка → демо превью</div>', unsafe_allow_html=True)
st.sidebar.markdown('<div class="hr"></div>', unsafe_allow_html=True)

idx = PAGES.index(st.session_state["nav_page"]) if st.session_state["nav_page"] in PAGES else 0
st.sidebar.radio("Навигация", PAGES, key="nav_page_ui", index=idx, on_change=sync_nav)

st.sidebar.button("↩️ Сбросить форму", on_click=reset_form, use_container_width=True)

# small progress
form = get_form()
filled_base = sum(bool((form.get(k) or "").strip()) for k in ["what_advertise", "campaign_goal", "landing_url", "segment_desc", "contact_name"])
st.sidebar.markdown(
    f"<div class='small-muted'>Заполнено базы: <b>{filled_base}</b>/5 · Площадки: <b>{len(selected_platforms())}</b></div>",
    unsafe_allow_html=True,
)

# =========================
# Screens
# =========================
def screen_start():
    st.title("Заполнение заявки на изготовление материалов для hh Сегментов")
    st.markdown("Заполнение брифа займёт **до 5 минут**.")
    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

    st.markdown(
        """
<div class="card">
  <div style="font-weight:800; font-size:1.05rem; margin-bottom:6px;">Что вы получите на выходе</div>
  <div class="small-muted">
    Заполненный бриф по выбранным площадкам и форматам + примерный мокап (как может выглядеть реклама),
    чтобы быстро согласовать направление.
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)
    st.button("Начать →", on_click=set_page, args=("Основная информация",), type="primary", use_container_width=True)

def screen_basic():
    st.title("Основная информация")

    with st.expander("Коротко про hh Сегменты", expanded=False):
        st.markdown(
            "• Важнее всего: **что рекламируем**, **цель**, **описание сегмента**, **посадочная**.\n"
            "• Контекст посадочной можно вставить вручную или подтянуть по ссылке (beta)."
        )

    col1, col2 = st.columns(2)
    with col1:
        w_text_area(
            "Что рекламируем*",
            "what_advertise",
            height=90,
            placeholder="Коротко: работодатель/вакансии/кампания, 1–2 предложения.",
        )
        w_text_input("Цель кампании*", "campaign_goal", placeholder="Трафик / рост откликов / узнаваемость")
        w_text_input("Посадочная ссылка*", "landing_url", placeholder="https://…")
        w_text_input("Гео*", "geo", placeholder="Города/регионы")

    with col2:
        w_text_area(
            "Описание сегмента*",
            "segment_desc",
            height=120,
            placeholder="1–3 сегмента: кто эти люди, опыт/профили/уровень.",
            help="Это аудитория, на которую будет показываться реклама.",
        )
        w_text_area("Файлы/материалы (ссылки)", "files_links", height=90, placeholder="Лого/брендбук/референсы/исходники")
        w_text_input("Контактное лицо (кто заполняет)*", "contact_name", placeholder="Имя")

    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)
    st.subheader("Контекст посадочной (для генерации текстов)")
    st.caption("Можно вставить вручную или подтянуть по ссылке (beta).")

    # IMPORTANT: кнопка до поля, чтобы безопасно обновлять значение
    c1, c2 = st.columns([1, 2])

    def pull_context_cb():
        f = get_form()
        url = f.get("landing_url", "")
        text = try_fetch_landing_text(url)
        f["landing_context"] = text
        # сбрасываем ui-ключ, чтобы text_area перерисовался с новым value
        st.session_state.pop(ui_key("landing_context"), None)

    with c1:
        st.button("Подтянуть контекст по ссылке (beta)", on_click=pull_context_cb, use_container_width=True)
    with c2:
        st.caption("Если страница закрыта/тяжёлая — вставь краткие тезисы вручную.")

    w_text_area(
        "Контекст посадочной",
        "landing_context",
        height=160,
        placeholder="УТП, условия, кому подходит, что сделать на странице…",
        label_visibility="collapsed",
    )

    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)
    b1, b2 = st.columns([1, 1])
    with b1:
        st.button("← Назад", on_click=set_page, args=("Старт",), use_container_width=True)
    with b2:
        st.button("Далее →", on_click=set_page, args=("Креативы и площадки",), type="primary", use_container_width=True)

def screen_platforms():
    st.title("Креативы и площадки")
    st.caption("Выберите рекламные площадки и форматы креативов.")
    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Площадки")
        w_checkbox("Яндекс", "pl_yandex")
        w_checkbox("VK", "pl_vk")
        w_checkbox("Telegram Ads", "pl_tgads")
        w_checkbox("Telegram посевы", "pl_tgseeding")

    with col2:
        st.subheader("Форматы (по площадкам)")
        f = get_form()
        if f.get("pl_yandex"):
            w_multiselect("Яндекс", "fmt_yandex", FORMATS["Яндекс"], placeholder="Выберите формат(ы)")
        if f.get("pl_vk"):
            w_multiselect("VK", "fmt_vk", FORMATS["VK"], placeholder="Выберите формат(ы)")
        if f.get("pl_tgads"):
            w_multiselect("Telegram Ads", "fmt_tgads", FORMATS["Telegram Ads"], placeholder="Выберите формат(ы)")
        if f.get("pl_tgseeding"):
            st.info("Telegram посевы: формат фиксированный — пост + изображение с текстом")

    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)
    b1, b2 = st.columns([1, 1])
    with b1:
        st.button("← Назад", on_click=set_page, args=("Основная информация",), use_container_width=True)
    with b2:
        st.button("Далее →", on_click=set_page, args=("Тексты и креативы",), type="primary", use_container_width=True)

def screen_texts():
    st.title("Тексты и креативы")
    st.caption("Заполните тексты по выбранным площадкам и форматам. Данные сохраняются автоматически.")
    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

    form = get_form()
    plats = selected_platforms()
    if not plats:
        st.markdown('<div class="hint">Сначала выберите площадки на шаге «Креативы и площадки».</div>', unsafe_allow_html=True)
        return

    # ---- AI block (must be BEFORE fields to safely set widget keys)
    st.markdown("### AI (опционально)")
    st.caption("Сгенерируем по **1 варианту текста** для выбранных площадок, используя данные из шага 1.")

    overwrite = st.checkbox("Перезаписать уже заполненные поля", value=False, key="ui_overwrite_texts")

    def gen_texts_cb():
        f = get_form()
        f["gen_logs"] = []
        f["gen_ok"] = None

        if not openrouter_api_key():
            f["gen_logs"] = ["Добавьте OPENROUTER_API_KEY в Secrets, чтобы включить генерацию."]
            f["gen_ok"] = False
            return

        # минимально нужное
        if not (f.get("what_advertise", "").strip() and f.get("segment_desc", "").strip() and f.get("landing_url", "").strip()):
            f["gen_logs"] = ["Заполните на шаге 1 минимум: «Что рекламируем», «Описание сегмента», «Посадочная ссылка»."]
            f["gen_ok"] = False
            return

        ok_any = False
        logs = []

        for p in selected_platforms():
            try:
                out = ai_generate_one_text(p)

                if p == "Яндекс":
                    if overwrite or not f.get("yandex_title", "").strip():
                        f["yandex_title"] = out.get("title", "")
                        st.session_state[ui_key("yandex_title")] = f["yandex_title"]
                    if overwrite or not f.get("yandex_body", "").strip():
                        f["yandex_body"] = out.get("body", "")
                        st.session_state[ui_key("yandex_body")] = f["yandex_body"]
                    ok_any = True

                elif p == "VK":
                    if overwrite or not f.get("vk_post_text", "").strip():
                        f["vk_post_text"] = out.get("post", "")
                        st.session_state[ui_key("vk_post_text")] = f["vk_post_text"]
                    if overwrite and out.get("cta"):
                        f["vk_cta"] = out.get("cta", "Перейти")
                        st.session_state[ui_key("vk_cta")] = f["vk_cta"]
                    ok_any = True

                elif p == "Telegram Ads":
                    if overwrite or not f.get("tg_message", "").strip():
                        f["tg_message"] = out.get("message", "")
                        st.session_state[ui_key("tg_message")] = f["tg_message"]
                    if overwrite and out.get("cta"):
                        f["tg_cta"] = out.get("cta", "Подробнее")
                        st.session_state[ui_key("tg_cta")] = f["tg_cta"]
                    ok_any = True

                else:
                    if overwrite or not f.get("seed_image_text", "").strip():
                        f["seed_image_text"] = out.get("image_text", "")
                        st.session_state[ui_key("seed_image_text")] = f["seed_image_text"]
                    if overwrite or not f.get("seed_post_text", "").strip():
                        f["seed_post_text"] = out.get("post", "")
                        st.session_state[ui_key("seed_post_text")] = f["seed_post_text"]
                    ok_any = True

            except Exception as e:
                logs.append(f"{p}: {e}")

        f["gen_logs"] = logs
        f["gen_ok"] = bool(ok_any)

    st.button("⚡ Сгенерировать тексты (1 вариант)", on_click=gen_texts_cb, type="primary", use_container_width=True)

    if form.get("gen_ok") is True:
        st.success("Готово! Тексты подставлены в поля ниже.")
    elif form.get("gen_ok") is False:
        st.warning("Генерация не выполнена — проверьте сообщение ниже.")

    if form.get("gen_logs"):
        st.code("\n".join(form["gen_logs"]))

    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

    # ---- Fields by platform
    if "Яндекс" in plats:
        fmts = selected_formats("Яндекс")
        with st.expander("Яндекс", expanded=True):
            st.markdown(f"<span class='badge'>Выбранные форматы: {', '.join(fmts) if fmts else 'не выбраны'}</span>", unsafe_allow_html=True)
            limited_text_input("Заголовок (до 56)", "yandex_title", LIMITS["yandex_title"], placeholder="Коротко и по делу")
            limited_text_area("Текст (до 81)", "yandex_body", LIMITS["yandex_body"], height=90, placeholder="1–2 выгоды + действие")

    if "VK" in plats:
        fmts = selected_formats("VK")
        with st.expander("VK", expanded=False):
            st.markdown(f"<span class='badge'>Выбранные форматы: {', '.join(fmts) if fmts else 'не выбраны'}</span>", unsafe_allow_html=True)
            limited_text_area("Текст поста (до 700)", "vk_post_text", LIMITS["vk_post"], height=130, placeholder="1–2 выгоды + действие")
            w_selectbox("CTA", "vk_cta", ["Перейти", "Подробнее", "Открыть", "Откликнуться"])

    if "Telegram Ads" in plats:
        fmts = selected_formats("Telegram Ads")
        with st.expander("Telegram Ads", expanded=False):
            st.markdown(f"<span class='badge'>Выбранные форматы: {', '.join(fmts) if fmts else 'не выбраны'}</span>", unsafe_allow_html=True)
            if "Текст" in fmts:
                limited_text_area("Текст сообщения (до 200)", "tg_message", LIMITS["tgads_text"], height=110, placeholder="1–2 предложения + CTA")
                w_selectbox("CTA", "tg_cta", ["Подробнее", "Перейти", "Открыть"])
            else:
                st.info("Текстовый формат не выбран — можно оставить пустым.")

    if "Telegram посевы" in plats:
        with st.expander("Telegram посевы", expanded=False):
            limited_text_input("Текст на изображении (1 строка, до 40)", "seed_image_text", LIMITS["seed_img_text"], placeholder="Короткое УТП")
            limited_text_area("Текст поста (до 500)", "seed_post_text", LIMITS["seed_post"], height=150, placeholder="УТП → пояснение → ссылка/CTA")

    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)
    b1, b2 = st.columns([1, 1])
    with b1:
        st.button("← Назад", on_click=set_page, args=("Креативы и площадки",), use_container_width=True)
    with b2:
        st.button("Далее →", on_click=set_page, args=("Примерный вид объявлений",), type="primary", use_container_width=True)

def demo_card_yandex(fmt: str):
    f = get_form()
    title = f.get("yandex_title", "").strip() or "Заголовок"
    body = f.get("yandex_body", "").strip() or "Текст объявления"
    st.markdown(f"<div class='badge'>Яндекс · {fmt}</div>", unsafe_allow_html=True)
    st.markdown(
        f"""
<div class="ad">
  <div class="ad-head">{title}</div>
  <div class="ad-text">{body}</div>
  <div class="ad-meta">Ссылка: {f.get("landing_url") or "https://..."}</div>
</div>
""",
        unsafe_allow_html=True,
    )

def demo_card_vk(fmt: str):
    f = get_form()
    post = f.get("vk_post_text", "").strip() or "Текст поста"
    cta = f.get("vk_cta", "Перейти")
    st.markdown(f"<div class='badge'>VK · {fmt}</div>", unsafe_allow_html=True)
    st.markdown(
        f"""
<div class="ad">
  <div class="ad-text">{post}</div>
  <a class="ad-btn" href="#" onclick="return false;">{cta}</a>
  <div class="ad-meta" style="margin-top:10px;">Ссылка: {f.get("landing_url") or "https://..."}</div>
</div>
""",
        unsafe_allow_html=True,
    )

def demo_card_tg_text():
    f = get_form()
    msg = f.get("tg_message", "").strip() or "Текст сообщения"
    cta = f.get("tg_cta", "Подробнее")
    st.markdown("<div class='badge'>Telegram Ads · Текст</div>", unsafe_allow_html=True)
    st.markdown(
        f"""
<div class="ad">
  <div class="ad-text">{msg}</div>
  <div class="ad-meta">CTA: {cta}</div>
</div>
""",
        unsafe_allow_html=True,
    )

def demo_card_tg_media(fmt: str):
    f = get_form()
    caption = f.get("tg_message", "").strip() or "Подпись/сопроводительный текст"
    st.markdown(f"<div class='badge'>Telegram Ads · {fmt}</div>", unsafe_allow_html=True)
    st.markdown(
        f"""
<div class="ad">
  <div class="ad-text">{caption}</div>
  <div class="ad-meta">Ссылка: {f.get("landing_url") or "https://..."}</div>
</div>
""",
        unsafe_allow_html=True,
    )

def demo_card_seeding():
    f = get_form()
    img_text = f.get("seed_image_text", "").strip() or "Текст на изображении"
    post = f.get("seed_post_text", "").strip() or "Текст поста"
    st.markdown("<div class='badge'>Telegram посевы · Пост + изображение</div>", unsafe_allow_html=True)
    st.markdown(
        f"""
<div class="ad">
  <div class="ad-head">{img_text}</div>
  <div class="ad-text">{post}</div>
  <div class="ad-meta">Ссылка: {f.get("landing_url") or "https://..."}</div>
</div>
""",
        unsafe_allow_html=True,
    )

def render_demo_image(platform: str, fmt: str):
    f = get_form()
    key = f"{platform}|{fmt}"
    url = (f.get("demo_images") or {}).get(key)
    if url:
        st.image(url, use_container_width=True)
    else:
        st.info("Демо-визуал пока не сгенерирован. Нажмите «🎨 Сгенерировать демо-визуалы» выше.")

def screen_demo():
    st.title("Примерный вид рекламных объявлений")
    st.caption("Быстрый мокап, чтобы согласовать направление.")
    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

    plats = selected_platforms()
    if not plats:
        st.markdown('<div class="hint">Сначала выберите площадки на шаге «Креативы и площадки».</div>', unsafe_allow_html=True)
        return

    st.markdown(
        """
<div class="card">
  <div style="font-weight:800; font-size:1.05rem; margin-bottom:6px;">Демо-пример</div>
  <div class="small-muted">
    Финальный вид зависит от модерации и конкретного формата. Здесь — быстрый мокап.
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

    with st.expander("AI-генерация демо-визуалов (опционально)", expanded=False):
        if not openrouter_api_key():
            st.warning("Чтобы генерировать демо-картинки, добавьте OPENROUTER_API_KEY в Streamlit Secrets.")
        else:
            st.caption(
                "Генерация идёт через OpenRouter Images endpoint. "
                "Основная модель — OPENROUTER_IMAGE_MODEL, фоллбеки — OPENROUTER_IMAGE_MODEL_FALLBACKS."
            )
            st.code(
                """OPENROUTER_IMAGE_MODEL = "black-forest-labs/flux.2-flex"
OPENROUTER_IMAGE_MODEL_FALLBACKS = "black-forest-labs/flux.2-pro, openai/gpt-image-1"
""",
                language="toml",
            )

            def gen_demo_images_cb():
                f = get_form()
                imgs = f.get("demo_images") or {}
                errors = []
                for p in plats:
                    fmts = selected_formats(p)
                    for fmt in fmts:
                        need_visual = (
                            (p in ["Яндекс", "VK"] and fmt in ["Изображение", "Видео"])
                            or (p == "Telegram Ads" and fmt in ["Изображение", "Видео"])
                            or (p == "Telegram посевы")
                        )
                        if not need_visual:
                            continue

                        core = f.get("what_advertise") or "HR-кампания"
                        seg = f.get("segment_desc") or "соискатели"
                        geo = f.get("geo") or "Россия"

                        if p == "Telegram посевы":
                            utp = f.get("seed_image_text") or "Ключевое сообщение"
                            aspect = "4:5"
                        elif p == "Яндекс":
                            utp = f.get("yandex_title") or "Ключевое сообщение"
                            aspect = "16:9"
                        elif p == "VK":
                            utp = (f.get("vk_post_text") or "Ключевое сообщение")[:60]
                            aspect = "16:9"
                        else:
                            utp = (f.get("tg_message") or "Ключевое сообщение")[:60]
                            aspect = "16:9"

                        prompt = (
                            "Create a clean modern advertising creative (no real brand logos; use generic placeholders). "
                            f"Topic: {core}. Audience: {seg}. Geo: {geo}. "
                            f"Main readable headline text: '{utp}'. "
                            "Style: minimal, corporate, high contrast, large readable typography. "
                            "No small unreadable text. No offensive content."
                        )

                        try:
                            img = generate_demo_image(prompt, aspect=aspect)
                            if img:
                                imgs[f"{p}|{fmt}"] = img
                        except Exception as e:
                            errors.append(f"{p} · {fmt}: {e}")

                f["demo_images"] = imgs
                f["gen_logs"] = errors
                f["gen_ok"] = True if imgs else False

            st.button("🎨 Сгенерировать демо-визуалы", on_click=gen_demo_images_cb, type="primary", use_container_width=True)

            f = get_form()
            if f.get("gen_logs"):
                st.warning("Есть ошибки генерации:")
                st.code("\n".join(f["gen_logs"]))
            else:
                st.caption("Если генерация прошла — демо-визуалы появятся ниже в карточках.")

    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

    tabs = st.tabs(plats)
    for idx, platform in enumerate(plats):
        with tabs[idx]:
            fmts = selected_formats(platform)
            st.markdown(f"### {platform}")

            if not fmts:
                st.info("Форматы не выбраны на шаге 2.")
                continue

            for fmt in fmts:
                st.markdown('<div class="hr"></div>', unsafe_allow_html=True)
                left, right = st.columns([1.1, 1])

                with left:
                    st.markdown("#### Тексты")
                    if platform == "Яндекс":
                        demo_card_yandex(fmt)
                    elif platform == "VK":
                        demo_card_vk(fmt)
                    elif platform == "Telegram Ads":
                        if fmt == "Текст":
                            demo_card_tg_text()
                        else:
                            demo_card_tg_media(fmt)
                    else:
                        demo_card_seeding()

                with right:
                    st.markdown("#### Демо-визуал")
                    if platform == "Telegram Ads" and fmt == "Текст":
                        st.info("Для текстового формата визуал не требуется.")
                    elif platform in ["Яндекс", "VK", "Telegram Ads"] and fmt in ["Изображение", "Видео"]:
                        render_demo_image(platform, fmt)
                    elif platform == "Telegram посевы":
                        render_demo_image(platform, fmt)
                    else:
                        st.info("Для выбранного формата визуал не требуется.")

    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)
    b1, b2 = st.columns([1, 1])
    with b1:
        st.button("← Назад", on_click=set_page, args=("Тексты и креативы",), use_container_width=True)
    with b2:
        st.success("Если ок — можно копировать данные из полей и передавать в работу.")

# =========================
# Router
# =========================
page = st.session_state.get("nav_page", PAGES[0])

if page == "Старт":
    screen_start()
elif page == "Основная информация":
    screen_basic()
elif page == "Креативы и площадки":
    screen_platforms()
elif page == "Тексты и креативы":
    screen_texts()
elif page == "Примерный вид объявлений":
    screen_demo()
