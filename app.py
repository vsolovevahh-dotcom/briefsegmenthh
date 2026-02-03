# app.py
import json
import re
from copy import deepcopy

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
  --soft:#f3f4f6;
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
# Defaults (single source of truth)
# =========================
DEFAULT_FORM = {
    # Step 1
    "what_advertise": "",
    "campaign_goal": "",
    "landing_url": "",
    "geo": "",
    "segment_desc": "",
    "files_links": "",
    "contact_name": "",
    "landing_context": "",

    # Step 2
    "pl_yandex": False,
    "pl_vk": False,
    "pl_tgads": False,
    "pl_tgseeding": False,

    "fmt_yandex": [],
    "fmt_vk": [],
    "fmt_tgads": [],

    # Step 3
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

    # Step 4 demo
    "demo_images": {},
}


def _deepcopy_if_needed(v):
    return deepcopy(v) if isinstance(v, (dict, list)) else v


def init_state():
    # ВАЖНО: только setdefault/инициализация отсутствующих ключей,
    # иначе любые переходы будут "сбрасывать" данные.
    for k, v in DEFAULT_FORM.items():
        if k not in st.session_state:
            st.session_state[k] = _deepcopy_if_needed(v)

    if "nav_page" not in st.session_state:
        st.session_state["nav_page"] = PAGES[0]


init_state()

# =========================
# Helpers
# =========================

def remaining(max_len: int, value: str) -> int:
    value = value or ""
    return max(max_len - len(value), 0)


def limited_text_input(label, key, max_chars, placeholder=""):
    val = st.text_input(label, key=key, max_chars=max_chars, placeholder=placeholder)
    st.caption(f"Осталось {remaining(max_chars, val)} символов из {max_chars}")
    return val


def limited_text_area(label, key, max_chars, height=110, placeholder=""):
    val = st.text_area(label, key=key, max_chars=max_chars, height=height, placeholder=placeholder)
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


def get_selected_platforms():
    res = []
    if st.session_state.pl_yandex:
        res.append("Яндекс")
    if st.session_state.pl_vk:
        res.append("VK")
    if st.session_state.pl_tgads:
        res.append("Telegram Ads")
    if st.session_state.pl_tgseeding:
        res.append("Telegram посевы")
    return res


def get_selected_formats(platform: str):
    if platform == "Яндекс":
        return st.session_state.fmt_yandex or []
    if platform == "VK":
        return st.session_state.fmt_vk or []
    if platform == "Telegram Ads":
        return st.session_state.fmt_tgads or []
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
    # ВАЖНО: google/gemini-flash-1.5 часто даёт 404 в OpenRouter.
    return _secret("OPENROUTER_TEXT_MODEL", "google/gemini-2.0-flash-lite-001")


def openrouter_text_fallbacks() -> list[str]:
    raw = _secret("OPENROUTER_TEXT_MODEL_FALLBACKS", "")
    models = [m.strip() for m in raw.split(",") if m.strip()]
    if not models:
        models = [
            "google/gemini-2.0-flash-001",
            "openrouter/auto",
        ]
    return models


def openrouter_image_model() -> str:
    return _secret("OPENROUTER_IMAGE_MODEL", "black-forest-labs/flux.2-flex")


def openrouter_image_fallbacks() -> list[str]:
    raw = _secret("OPENROUTER_IMAGE_MODEL_FALLBACKS", "")
    models = [m.strip() for m in raw.split(",") if m.strip()]
    if not models:
        models = [
            "black-forest-labs/flux.1-schnell",
            "openrouter/auto",
        ]
    return models


def openrouter_provider_prefs() -> dict:
    ignore_raw = _secret("OPENROUTER_PROVIDER_IGNORE", "")
    ignore = [x.strip() for x in ignore_raw.split(",") if x.strip()]
    prefs = {"allow_fallbacks": True, "sort": "price"}
    if ignore:
        prefs["ignore"] = ignore
    return prefs


def openrouter_chat(model: str, messages: list, temperature=0.6, max_tokens=900, modalities=None, image_config=None):
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

    r = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=90,
    )

    if r.status_code != 200:
        try:
            detail = r.json()
        except Exception:
            detail = (r.text or "")[:1500]
        raise RuntimeError(f"OpenRouter API error {r.status_code}: {detail}")

    return r.json()


def openrouter_chat_with_fallback(models: list[str], **kwargs):
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
        prompt = (
            "Ты — PMM/копирайтер. Сгенерируй РОВНО 1 вариант текста для Яндекс объявлений. "
            "Верни ТОЛЬКО JSON (без markdown/пояснений). "
            f"Лимиты: title ≤ {LIMITS['yandex_title']} символов, body ≤ {LIMITS['yandex_body']} символов. "
            "Стиль: нейтрально-деловой, без клише, без обещаний «гарантируем».\n\n"
            f"Вводные: {json.dumps(base, ensure_ascii=False)}\n\n"
            "Верни JSON: {\"title\":\"...\",\"body\":\"...\"}"
        )
        _, data = openrouter_chat_with_fallback(
            models=models,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=260,
        )
        content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
        obj = extract_json_obj(content)
        return {
            "title": clamp(obj.get("title", ""), LIMITS["yandex_title"]),
            "body": clamp(obj.get("body", ""), LIMITS["yandex_body"]),
        }

    if platform == "VK":
        prompt = (
            "Ты — PMM/копирайтер. Сгенерируй РОВНО 1 вариант нативного поста для VK. "
            "Верни ТОЛЬКО JSON. "
            f"Лимит: post ≤ {LIMITS['vk_post']} символов. "
            "CTA из списка: Перейти / Подробнее / Открыть / Откликнуться.\n\n"
            f"Вводные: {json.dumps(base, ensure_ascii=False)}\n\n"
            "Верни JSON: {\"post\":\"...\",\"cta\":\"Подробнее\"}"
        )
        _, data = openrouter_chat_with_fallback(
            models=models,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.55,
            max_tokens=520,
        )
        content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
        obj = extract_json_obj(content)
        return {
            "post": clamp(obj.get("post", ""), LIMITS["vk_post"]),
            "cta": clamp(obj.get("cta", "Подробнее"), 30) or "Подробнее",
        }

    if platform == "Telegram Ads":
        prompt = (
            "Ты — PMM/копирайтер. Сгенерируй РОВНО 1 вариант текста для Telegram Ads. "
            "Верни ТОЛЬКО JSON. "
            f"Лимит: message ≤ {LIMITS['tgads_text']} символов. "
            "CTA из списка: Подробнее / Перейти / Открыть.\n\n"
            f"Вводные: {json.dumps(base, ensure_ascii=False)}\n\n"
            "Верни JSON: {\"message\":\"...\",\"cta\":\"Подробнее\"}"
        )
        _, data = openrouter_chat_with_fallback(
            models=models,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
            max_tokens=320,
        )
        content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
        obj = extract_json_obj(content)
        return {
            "message": clamp(obj.get("message", ""), LIMITS["tgads_text"]),
            "cta": clamp(obj.get("cta", "Подробнее"), 30) or "Подробнее",
        }

    # Telegram посевы
    prompt = (
        "Ты — PMM/копирайтер. Сгенерируй РОВНО 1 вариант для Telegram посевов: "
        f"1) image_text — 1 строка (≤ {LIMITS['seed_img_text']} символов) для текста на креативе; "
        f"2) post — пост (≤ {LIMITS['seed_post']} символов) нативно, без ощущения баннера. "
        "Верни ТОЛЬКО JSON.\n\n"
        f"Вводные: {json.dumps(base, ensure_ascii=False)}\n\n"
        "Верни JSON: {\"image_text\":\"...\",\"post\":\"...\"}"
    )
    _, data = openrouter_chat_with_fallback(
        models=models,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=720,
    )
    content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
    obj = extract_json_obj(content)
    return {
        "image_text": clamp(obj.get("image_text", ""), LIMITS["seed_img_text"]),
        "post": clamp(obj.get("post", ""), LIMITS["seed_post"]),
    }


def extract_image_url(data: dict) -> str:
    if not data or not data.get("choices"):
        return ""
    msg = (data["choices"][0] or {}).get("message", {}) or {}

    # Часто OpenRouter возвращает message.images
    images = msg.get("images") or []
    if images:
        img0 = images[0] or {}
        url_obj = img0.get("image_url") or img0.get("imageUrl") or {}
        url = (url_obj or {}).get("url")
        if url:
            return url

    content = msg.get("content")

    # Иногда content — список блоков
    if isinstance(content, list):
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "image_url":
                url_obj = part.get("image_url") or part.get("imageUrl") or {}
                url = (url_obj or {}).get("url")
                if url:
                    return url

    # Иногда content — строка с data:image/..;base64
    if isinstance(content, str):
        m = re.search(r"(data:image/[a-zA-Z]+;base64,[A-Za-z0-9+/=]+)", content)
        if m:
            return m.group(1)

    return ""


def generate_demo_image(prompt: str, aspect_ratio: str = "16:9") -> str:
    """Generate image via OpenRouter.

    Важно: image-модели часто НЕ поддерживают одновременно output modalities ['image','text'].
    Поэтому запрашиваем только ['image'] — это убирает ошибку
    "No endpoints found that support the requested output modalities: image, text".
    """

    models = [openrouter_image_model()] + openrouter_image_fallbacks()

    last_err = None
    for model in models:
        try:
            # Для Flux добавляем аспект в промпт (они часто игнорируют image_config).
            is_gemini = model.startswith("google/")
            user_prompt = prompt
            image_cfg = None
            if is_gemini:
                image_cfg = {"aspect_ratio": aspect_ratio, "image_size": "1K"}
            else:
                user_prompt = f"{prompt}\n\nAspect ratio: {aspect_ratio}."

            _, data = openrouter_chat_with_fallback(
                models=[model],
                messages=[{"role": "user", "content": user_prompt}],
                temperature=0.2,
                max_tokens=200,
                modalities=["image"],
                image_config=image_cfg,
            )

            url = extract_image_url(data)
            if url:
                return url

            last_err = RuntimeError("Пустой ответ (не нашли image_url)")
        except Exception as e:
            last_err = e

    raise RuntimeError(last_err or "Не удалось сгенерировать изображение")


# =========================
# Sidebar (navigation + reset)
# =========================
st.sidebar.markdown("## 🧩 hh Сегменты — заявка")
st.sidebar.markdown('<div class="small-muted">Форма → заявка → демо превью</div>', unsafe_allow_html=True)
st.sidebar.markdown('<div class="hr"></div>', unsafe_allow_html=True)

st.sidebar.radio("Навигация", PAGES, key="nav_page")


def reset_form():
    nav = st.session_state.get("nav_page", PAGES[0])
    for k in list(DEFAULT_FORM.keys()):
        st.session_state[k] = _deepcopy_if_needed(DEFAULT_FORM[k])
    st.session_state["nav_page"] = nav


st.sidebar.button("↩️ Сбросить форму", on_click=reset_form, use_container_width=True)

# Header (main)
st.markdown('<div class="app-title">hh Сегменты — заявка</div>', unsafe_allow_html=True)
st.markdown('<div class="app-sub">Заполнение брифа займёт до 5 минут.</div>', unsafe_allow_html=True)


# =========================
# Screens
# =========================

def screen_0():
    st.markdown(
        """
<div class="card">
  <div style="font-weight:900; font-size:1.15rem; margin-bottom:6px;">Что это</div>
  <div class="small-muted">
    Собираем минимально достаточный бриф для запуска hh Сегментов. На последнем шаге покажем мокапы объявлений.
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

    def go_next():
        st.session_state.nav_page = "1. Основная информация"

    st.button("Начать →", on_click=go_next, type="primary", use_container_width=True)


def screen_1():
    st.title("Основная информация")

    with st.expander("Коротко про hh Сегменты", expanded=False):
        st.markdown(
            """
- Важнее всего: **что рекламируем**, **цель**, **гео**, **описание сегмента**, **посадочная**.
- Контекст посадочной можно вставить вручную или попробовать подтянуть по ссылке.
"""
        )

    col1, col2 = st.columns(2)

    with col1:
        st.text_area(
            "Что рекламируем*",
            key="what_advertise",
            height=90,
            placeholder="Коротко: работодатель/вакансии/кампания, в 1–2 предложениях.",
        )
        st.text_input(
            "Цель кампании*",
            key="campaign_goal",
            placeholder="Напр.: трафик на вакансии / рост откликов / узнаваемость",
        )
        st.text_input(
            "Посадочная ссылка*",
            key="landing_url",
            placeholder="https://…",
        )
        st.text_input(
            "Гео*",
            key="geo",
            placeholder="Города/регионы",
        )

    with col2:
        st.text_area(
            "Описание сегмента*",
            key="segment_desc",
            height=120,
            placeholder="1–3 сегмента: кто эти люди, опыт/профили/уровень.",
        )
        st.text_area(
            "Файлы/материалы (ссылки)",
            key="files_links",
            height=90,
            placeholder="Лого / брендбук / референсы / исходники (ссылки)",
        )
        st.text_input(
            "Контактное лицо (кто заполняет)*",
            key="contact_name",
            placeholder="Имя",
        )

    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

    st.subheader("Контекст посадочной (для генерации текстов)")
    st.caption("Если есть — вставьте текст с посадочной. Либо попробуйте подтянуть по ссылке кнопкой ниже.")

    st.text_area(
        "Контекст посадочной",
        key="landing_context",
        height=140,
        placeholder="Вставьте описание/УТП/ключевые блоки с посадочной…",
        label_visibility="collapsed",
    )

    c1, c2 = st.columns([1, 1])
    with c1:
        def pull_context():
            st.session_state.landing_context = try_fetch_landing_text(st.session_state.landing_url)

        st.button("Подтянуть контекст по ссылке (beta)", on_click=pull_context, use_container_width=True)

    with c2:
        def go_next():
            st.session_state.nav_page = "2. Креативы и площадки"

        st.button("Далее →", on_click=go_next, type="primary", use_container_width=True)


def screen_2():
    st.title("Креативы и площадки")
    st.caption("Выберите рекламные площадки и форматы креативов.")

    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Площадки")
        st.checkbox("Яндекс", key="pl_yandex")
        st.checkbox("VK", key="pl_vk")
        st.checkbox("Telegram Ads", key="pl_tgads")
        st.checkbox("Telegram посевы", key="pl_tgseeding")

    with col2:
        st.subheader("Форматы (по площадкам)")
        if st.session_state.pl_yandex:
            st.multiselect("Яндекс", FORMATS["Яндекс"], key="fmt_yandex", placeholder="Выберите формат(ы)")
        if st.session_state.pl_vk:
            st.multiselect("VK", FORMATS["VK"], key="fmt_vk", placeholder="Выберите формат(ы)")
        if st.session_state.pl_tgads:
            st.multiselect("Telegram Ads", FORMATS["Telegram Ads"], key="fmt_tgads", placeholder="Выберите формат(ы)")
        if st.session_state.pl_tgseeding:
            st.info("Telegram посевы: формат фиксированный — пост + изображение с текстом")

    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

    c1, c2 = st.columns([1, 1])
    with c1:
        def back():
            st.session_state.nav_page = "1. Основная информация"

        st.button("← Назад", on_click=back, use_container_width=True)

    with c2:
        def go_next():
            st.session_state.nav_page = "3. Тексты и креативы"

        st.button("Далее →", on_click=go_next, type="primary", use_container_width=True)


def screen_3():
    st.title("Тексты и креативы")
    st.caption("Заполните тексты и креативы по выбранным площадкам и форматам. Данные сохраняются автоматически.")

    selected = get_selected_platforms()
    if not selected:
        st.markdown('<div class="hint">Сначала выберите площадки на шаге 2.</div>', unsafe_allow_html=True)
        return

    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

    st.markdown("### AI (опционально)")
    st.caption("Сгенерируем по 1 варианту текста для выбранных площадок, используя только данные из шага 1.")
    st.checkbox("Перезаписать уже заполненные поля", key="ai_overwrite")

    if st.button("⚡ Сгенерировать тексты (1 вариант)", use_container_width=True, type="primary"):
        if not openrouter_api_key():
            st.error("Добавьте OPENROUTER_API_KEY в Secrets, чтобы включить генерацию.")
        elif not (
            st.session_state.what_advertise.strip()
            and st.session_state.segment_desc.strip()
            and st.session_state.landing_url.strip()
        ):
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
                            if overwrite or not st.session_state.yandex_title.strip():
                                st.session_state.yandex_title = out.get("title", st.session_state.yandex_title)
                                updated_any = True
                            if overwrite or not st.session_state.yandex_body.strip():
                                st.session_state.yandex_body = out.get("body", st.session_state.yandex_body)
                                updated_any = True

                        elif p == "VK":
                            if overwrite or not st.session_state.vk_post_text.strip():
                                st.session_state.vk_post_text = out.get("post", st.session_state.vk_post_text)
                                updated_any = True
                            if overwrite and out.get("cta"):
                                st.session_state.vk_cta = out.get("cta")
                                updated_any = True

                        elif p == "Telegram Ads":
                            if overwrite or not st.session_state.tg_message.strip():
                                st.session_state.tg_message = out.get("message", st.session_state.tg_message)
                                updated_any = True
                            if overwrite and out.get("cta"):
                                st.session_state.tg_cta = out.get("cta")
                                updated_any = True

                        else:  # Telegram посевы
                            if overwrite or not st.session_state.seed_image_text.strip():
                                st.session_state.seed_image_text = out.get("image_text", st.session_state.seed_image_text)
                                updated_any = True
                            if overwrite or not st.session_state.seed_post_text.strip():
                                st.session_state.seed_post_text = out.get("post", st.session_state.seed_post_text)
                                updated_any = True

                    except Exception as e:
                        logs.append(f"{p}: {e}")

            if updated_any:
                st.markdown('<div class="ok">Готово! Тексты подставлены в поля ниже.</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="hint">Генерация не выполнена — проверьте сообщение ниже.</div>', unsafe_allow_html=True)

            if logs:
                st.code("\n".join(logs))

    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

    if "Яндекс" in selected:
        fmts = get_selected_formats("Яндекс")
        with st.expander("Яндекс", expanded=True):
            st.markdown("### Тексты")
            st.radio("Кто готовит тексты?", ["Клиент", "Команда hh"], key="yandex_text_owner", horizontal=True)
            limited_text_input("Заголовок (до 56)", "yandex_title", LIMITS["yandex_title"], placeholder="Коротко и по делу")
            limited_text_area("Текст (до 81)", "yandex_body", LIMITS["yandex_body"], height=90, placeholder="1–2 выгоды + действие")
            st.text_area(
                "Быстрые ссылки (опц.) — по одной на строку: Название | URL",
                key="yandex_quicklinks",
                height=90,
                placeholder="Карьерный сайт | https://...\nВакансии | https://...",
            )

            st.markdown("### Креативы")
            st.radio("Кто готовит креативы?", ["Клиент", "Команда hh"], key="yandex_creative_owner", horizontal=True)
            if st.session_state.yandex_creative_owner == "Клиент":
                st.text_area("Ссылки на материалы и исходники", key="yandex_creative_links", height=90)
            else:
                st.text_area("Что должно быть на креативе (1–2 строки)", key="yandex_creative_brief", height=90)
                st.text_area("Референсы и исходники (ссылки)", key="yandex_creative_links", height=70)

            st.markdown(f"**Выбранные форматы:** {', '.join(fmts) if fmts else 'не выбраны'}")

    if "VK" in selected:
        fmts = get_selected_formats("VK")
        with st.expander("VK", expanded=False):
            st.markdown("### Тексты")
            st.radio("Кто готовит тексты?", ["Клиент", "Команда hh"], key="vk_text_owner", horizontal=True)
            limited_text_area("Текст поста (до 700)", "vk_post_text", LIMITS["vk_post"], height=130, placeholder="1–2 выгоды + действие")
            st.selectbox("CTA (опц.)", ["Перейти", "Подробнее", "Открыть", "Откликнуться"], key="vk_cta")

            st.markdown("### Креативы")
            st.radio("Кто готовит креативы?", ["Клиент", "Команда hh"], key="vk_creative_owner", horizontal=True)
            if st.session_state.vk_creative_owner == "Клиент":
                st.text_area("Ссылки на материалы и исходники", key="vk_creative_links", height=90)
            else:
                st.text_area("Что должно быть на креативе (1–2 строки)", key="vk_creative_brief", height=90)
                st.text_area("Референсы и исходники (ссылки)", key="vk_creative_links", height=70)

            st.markdown(f"**Выбранные форматы:** {', '.join(fmts) if fmts else 'не выбраны'}")

    if "Telegram Ads" in selected:
        fmts = get_selected_formats("Telegram Ads")
        with st.expander("Telegram Ads", expanded=False):
            if "Текст" in fmts:
                st.markdown("### TG Ads — текст")
                st.radio("Кто готовит текст?", ["Клиент", "Команда hh"], key="tg_text_owner", horizontal=True)
                limited_text_area("Текст сообщения (до 200)", "tg_message", LIMITS["tgads_text"], height=110, placeholder="1–2 предложения + CTA")
                st.selectbox("CTA (опц.)", ["Подробнее", "Перейти", "Открыть"], key="tg_cta")

            if "Изображение" in fmts or "Видео" in fmts:
                st.markdown("### TG Ads — медиа")
                st.radio("Кто готовит медиа?", ["Клиент", "Команда hh"], key="tg_media_owner", horizontal=True)
                if st.session_state.tg_media_owner == "Клиент":
                    st.text_area("Ссылки на материалы и исходники", key="tg_media_links", height=90)
                else:
                    st.text_area("Что должно быть на креативе (1–2 строки)", key="tg_media_brief", height=90)
                    st.text_area("Референсы и исходники (ссылки)", key="tg_media_links", height=70)

            st.markdown(f"**Выбранные форматы:** {', '.join(fmts) if fmts else 'не выбраны'}")

    if "Telegram посевы" in selected:
        with st.expander("Telegram посевы", expanded=False):
            st.markdown("Важно: в посевах картинка обычно с текстом на ней — укажите ключевое сообщение.")
            st.radio("Кто готовит материалы?", ["Клиент", "Команда hh"], key="seed_owner", horizontal=True)
            limited_text_input("Текст на изображении (1 строка, до 40)", "seed_image_text", LIMITS["seed_img_text"], placeholder="Короткое УТП")
            limited_text_area("Текст поста (до 500)", "seed_post_text", LIMITS["seed_post"], height=150, placeholder="УТП → пояснение → ссылка")
            st.text_area("Ссылки на материалы и исходники (опц.)", key="seed_links", height=80)

    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)
    c1, c2 = st.columns([1, 1])
    with c1:
        def back():
            st.session_state.nav_page = "2. Креативы и площадки"

        st.button("← Назад", on_click=back, use_container_width=True)

    with c2:
        def go_next():
            st.session_state.nav_page = "4. Примерный вид объявлений"

        st.button("Далее →", on_click=go_next, type="primary", use_container_width=True)


# =========================
# Demo cards
# =========================

def demo_card_yandex(fmt: str):
    title = st.session_state.yandex_title.strip() or "Заголовок"
    body = st.session_state.yandex_body.strip() or "Текст объявления"
    st.markdown(f"<div class='badge'>Яндекс · {fmt}</div>", unsafe_allow_html=True)
    st.markdown(
        f"""
<div class="ad">
  <div class="ad-head">{title}</div>
  <div class="ad-text">{body}</div>
  <div class="ad-meta">Ссылка: {st.session_state.landing_url or "https://..."}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def demo_card_vk(fmt: str):
    post = st.session_state.vk_post_text.strip() or "Текст поста"
    cta = st.session_state.vk_cta
    st.markdown(f"<div class='badge'>VK · {fmt}</div>", unsafe_allow_html=True)
    st.markdown(
        f"""
<div class="ad">
  <div class="ad-text">{post}</div>
  <a class="ad-btn" href="#" onclick="return false;">{cta}</a>
  <div class="ad-meta" style="margin-top:10px;">Ссылка: {st.session_state.landing_url or "https://..."}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def demo_card_tg_text():
    msg = st.session_state.tg_message.strip() or "Текст сообщения"
    cta = st.session_state.tg_cta
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
    caption = st.session_state.tg_message.strip() or "Подпись / сопроводительный текст"
    st.markdown(f"<div class='badge'>Telegram Ads · {fmt}</div>", unsafe_allow_html=True)
    st.markdown(
        f"""
<div class="ad">
  <div class="ad-text">{caption}</div>
  <div class="ad-meta">Ссылка: {st.session_state.landing_url or "https://..."}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def demo_card_seeding():
    img_text = st.session_state.seed_image_text.strip() or "Текст на изображении"
    post = st.session_state.seed_post_text.strip() or "Текст поста"
    st.markdown("<div class='badge'>Telegram посевы · Пост + изображение</div>", unsafe_allow_html=True)
    st.markdown(
        f"""
<div class="ad">
  <div class="ad-head">{img_text}</div>
  <div class="ad-text">{post}</div>
  <div class="ad-meta">Ссылка: {st.session_state.landing_url or "https://..."}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_demo_image(platform: str, fmt: str):
    key = f"{platform}|{fmt}"
    url = (st.session_state.demo_images or {}).get(key)
    if url:
        st.image(url, use_container_width=True)
    else:
        st.info("Демо-визуал пока не сгенерирован. Нажмите «🎨 Сгенерировать демо-визуалы» выше.")


def screen_4():
    st.title("Примерный вид рекламных объявлений")
    st.caption("Быстрый мокап, чтобы согласовать направление.")

    selected = get_selected_platforms()
    if not selected:
        st.markdown('<div class="hint">Сначала выберите площадки на шаге 2.</div>', unsafe_allow_html=True)
        return

    st.markdown(
        """
<div class="card">
  <div style="font-weight:900; font-size:1.05rem; margin-bottom:6px;">Демо-пример</div>
  <div class="small-muted">Финальный вид зависит от модерации и конкретного формата. Здесь — быстрый мокап.</div>
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
                "Сгенерируем по 1 демо-визуалу на выбранный формат (где уместно). "
                "Основная модель — OPENROUTER_IMAGE_MODEL, фоллбеки — OPENROUTER_IMAGE_MODEL_FALLBACKS."
            )
            st.code(
                """OPENROUTER_IMAGE_MODEL = "black-forest-labs/flux.2-flex"
OPENROUTER_IMAGE_MODEL_FALLBACKS = "black-forest-labs/flux.1-schnell, openrouter/auto"
""",
                language="toml",
            )

            if st.button("🎨 Сгенерировать демо-визуалы", type="primary", use_container_width=True):
                errors = []
                with st.spinner("Генерируем демо-визуалы..."):
                    for p in selected:
                        fmts = get_selected_formats(p)
                        for f in fmts:
                            need_visual = (
                                (p in ["Яндекс", "VK"] and f in ["Изображение", "Видео"])
                                or (p == "Telegram Ads" and f in ["Изображение", "Видео"])
                                or (p == "Telegram посевы")
                            )
                            if not need_visual:
                                continue

                            core = st.session_state.what_advertise or "HR-кампания"
                            seg = st.session_state.segment_desc or "соискатели"
                            geo = st.session_state.geo or "Россия"

                            if p == "Telegram посевы":
                                utp = st.session_state.seed_image_text or "Ключевое сообщение"
                                aspect = "4:5"
                            elif p == "Яндекс":
                                utp = st.session_state.yandex_title or "Ключевое сообщение"
                                aspect = "16:9"
                            elif p == "VK":
                                utp = (st.session_state.vk_post_text[:60] if st.session_state.vk_post_text else "Ключевое сообщение")
                                aspect = "16:9"
                            else:
                                utp = st.session_state.tg_media_brief or st.session_state.tg_message or "Ключевое сообщение"
                                aspect = "16:9"

                            prompt = (
                                "Create a clean modern advertising creative (no real brand logos; use generic placeholders). "
                                f"Topic: {core}. Audience: {seg}. Geo: {geo}. "
                                f"Main readable headline text: '{utp}'. "
                                "Style: minimal, corporate, high contrast, large readable typography. "
                                "No tiny text."
                            )

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

    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

    tabs = st.tabs(selected)
    for idx, platform in enumerate(selected):
        with tabs[idx]:
            fmts = get_selected_formats(platform)
            st.markdown(f"### {platform}")

            if not fmts:
                st.info("Форматы не выбраны на шаге 2.")
                continue

            for fmt in fmts:
                st.markdown('<div class="hr"></div>', unsafe_allow_html=True)
                left, right = st.columns([1.05, 1])

                with left:
                    st.markdown("#### Тексты")
                    if platform == "Яндекс":
                        demo_card_yandex(fmt)
                    elif platform == "VK":
                        demo_card_vk(fmt)
                    elif platform == "Telegram Ads":
                        if fmt == "Текст":
                            demo_card_tg_text()
      
