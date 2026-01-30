# app.py
import base64
import json
import re
from functools import partial
from datetime import datetime

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

PLATFORMS = ["Яндекс", "VK", "Telegram Ads", "Telegram посевы"]

FORMATS = {
    "Яндекс": ["Изображение", "Видео"],
    "VK": ["Изображение", "Видео"],
    "Telegram Ads": ["Текст", "Изображение", "Видео"],
    "Telegram посевы": ["Пост + креатив"],
}

# Лимиты (можно поправить под ваши реальные требования)
LIMITS = {
    "yandex_title": 56,
    "yandex_text": 81,
    "vk_post": 700,
    "tgads_text": 160,
    "seeding_post": 900,
    "seeding_image_text": 40,
}

# =========================
# Styles
# =========================
st.markdown(
    """
<style>
    .app-title {
        font-size: 2.2rem;
        font-weight: 800;
        margin: 0.2rem 0 0.2rem 0;
    }
    .app-subtitle {
        color: #667085;
        margin-bottom: 1.2rem;
    }
    .hint {
        background: #FFF7E6;
        border: 1px solid #FFE7BA;
        border-radius: 12px;
        padding: 12px 14px;
        color: #8A5B00;
        margin: 12px 0;
    }
    .card {
        border: 1px solid #EAECF0;
        border-radius: 16px;
        padding: 16px 16px;
        background: #FFFFFF;
        box-shadow: 0 1px 2px rgba(16, 24, 40, 0.06);
        margin: 10px 0;
    }
    .badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 999px;
        background: #F2F4F7;
        color: #344054;
        font-size: 0.85rem;
        margin-bottom: 8px;
    }
    .demo-wrap {
        border: 1px dashed #D0D5DD;
        border-radius: 16px;
        padding: 14px;
        background: #FCFCFD;
        margin-top: 8px;
    }
    .muted {
        color: #667085;
        font-size: 0.95rem;
    }
    .small {
        color: #667085;
        font-size: 0.85rem;
    }
    .kpi {
        font-weight: 700;
    }
    .sep {
        height: 1px;
        background: #EAECF0;
        margin: 14px 0;
    }
</style>
""",
    unsafe_allow_html=True,
)

# =========================
# Helpers: state + nav (FIX for nav_page error)
# =========================
def safe_index(options, value, default=0):
    return options.index(value) if value in options else default


def init_state():
    # навигация (ВАЖНО: разделяем ключ radio и "истину" навигации)
    st.session_state.setdefault("nav_page", PAGES[0])
    st.session_state.setdefault("nav_page_ui", st.session_state["nav_page"])

    # базовые поля
    st.session_state.setdefault("basic_what", "")
    st.session_state.setdefault("basic_goal", "")
    st.session_state.setdefault("basic_url", "")
    st.session_state.setdefault("basic_geo", "")
    st.session_state.setdefault("basic_segment", "")
    st.session_state.setdefault("basic_files", "")
    st.session_state.setdefault("basic_contact", "")
    st.session_state.setdefault("landing_context", "")

    # выбор площадок / форматов
    st.session_state.setdefault("sel_yandex", False)
    st.session_state.setdefault("sel_vk", False)
    st.session_state.setdefault("sel_tgads", False)
    st.session_state.setdefault("sel_seeding", False)

    st.session_state.setdefault("fmt_yandex", [])
    st.session_state.setdefault("fmt_vk", [])
    st.session_state.setdefault("fmt_tgads", [])
    st.session_state.setdefault("fmt_seeding", [])

    # тексты / креативы (черновики)
    st.session_state.setdefault("yandex_title", "")
    st.session_state.setdefault("yandex_text", "")
    st.session_state.setdefault("vk_post", "")
    st.session_state.setdefault("tgads_text", "")
    st.session_state.setdefault("tgads_cta", "Подробнее")
    st.session_state.setdefault("seeding_post", "")
    st.session_state.setdefault("seeding_image_text", "")

    # бриф по визуалу
    st.session_state.setdefault("visual_message", "")
    st.session_state.setdefault("visual_style", "")
    st.session_state.setdefault("visual_assets", "")

    # генерации (храним результаты)
    st.session_state.setdefault("gen_texts", {})     # ключ -> markdown
    st.session_state.setdefault("gen_images", {})    # ключ -> base64/data-url


def sync_from_sidebar():
    st.session_state["nav_page"] = st.session_state["nav_page_ui"]


def go(page: str):
    # вызываем ТОЛЬКО из callback (on_click)
    st.session_state["nav_page"] = page
    st.session_state["nav_page_ui"] = page
    st.rerun()


def reset_form():
    keep = {"nav_page", "nav_page_ui"}
    for k in list(st.session_state.keys()):
        if k not in keep:
            del st.session_state[k]
    init_state()
    st.rerun()


def selected_platforms():
    res = []
    if st.session_state.get("sel_yandex"):
        res.append("Яндекс")
    if st.session_state.get("sel_vk"):
        res.append("VK")
    if st.session_state.get("sel_tgads"):
        res.append("Telegram Ads")
    if st.session_state.get("sel_seeding"):
        res.append("Telegram посевы")
    return res


def selected_formats(platform: str):
    key = {
        "Яндекс": "fmt_yandex",
        "VK": "fmt_vk",
        "Telegram Ads": "fmt_tgads",
        "Telegram посевы": "fmt_seeding",
    }[platform]
    return st.session_state.get(key, []) or []


def counter_caption(value: str, limit: int):
    used = len(value or "")
    left = max(0, limit - used)
    st.caption(f"Осталось: {left} / {limit}")


def svg_placeholder(label: str):
    # простой SVG-плейсхолдер без внешних библиотек
    label = (label or "Preview").replace("&", "and")
    svg = f"""
<svg width="900" height="420" viewBox="0 0 900 420" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="g" x1="0" x2="1" y1="0" y2="1">
      <stop offset="0" stop-color="#F2F4F7"/>
      <stop offset="1" stop-color="#FFFFFF"/>
    </linearGradient>
  </defs>
  <rect x="0" y="0" width="900" height="420" rx="24" fill="url(#g)" stroke="#EAECF0"/>
  <rect x="36" y="36" width="828" height="260" rx="18" fill="#FFFFFF" stroke="#EAECF0"/>
  <text x="60" y="110" font-family="Inter, Arial" font-size="32" font-weight="800" fill="#101828">{label}</text>
  <text x="60" y="150" font-family="Inter, Arial" font-size="18" fill="#667085">Примерный мокап для согласования направления</text>
  <rect x="60" y="210" width="240" height="46" rx="12" fill="#F2F4F7" stroke="#EAECF0"/>
  <text x="85" y="240" font-family="Inter, Arial" font-size="16" font-weight="700" fill="#344054">CTA кнопка</text>
  <rect x="36" y="320" width="828" height="64" rx="18" fill="#FCFCFD" stroke="#EAECF0"/>
  <text x="60" y="360" font-family="Inter, Arial" font-size="14" fill="#667085">Финальный вид зависит от модерации и конкретного формата.</text>
</svg>
"""
    b64 = base64.b64encode(svg.encode("utf-8")).decode("utf-8")
    return f"data:image/svg+xml;base64,{b64}"


# =========================
# OpenRouter (optional): texts + image
# =========================
def get_openrouter_key():
    return st.secrets.get("OPENROUTER_API_KEY", "")


def call_openrouter_chat(model: str, messages: list, temperature: float = 0.5, max_tokens: int = 1400):
    api_key = get_openrouter_key()
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY не задан в Secrets.")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://streamlit.app",
        "X-Title": "hh-segments-brief",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
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
            detail = r.text
        raise RuntimeError(f"OpenRouter error {r.status_code}: {detail}")
    return r.json()


def generate_5_text_variants(kind: str, platform: str):
    # kind: "yandex" | "vk" | "tgads" | "seeding"
    base = {
        "Что рекламируем": st.session_state.get("basic_what", ""),
        "Цель": st.session_state.get("basic_goal", ""),
        "Посадочная": st.session_state.get("basic_url", ""),
        "Гео": st.session_state.get("basic_geo", ""),
        "Сегмент": st.session_state.get("basic_segment", ""),
        "Контекст посадочной (если есть)": st.session_state.get("landing_context", ""),
        "Материалы (ссылки)": st.session_state.get("basic_files", ""),
    }

    if kind == "yandex":
        sys = (
            "Ты — специалист по рекламным текстам. Создай РОВНО 5 вариантов для Яндекс. "
            f"Соблюдай лимиты: Заголовок ≤ {LIMITS['yandex_title']} символов, Текст ≤ {LIMITS['yandex_text']} символов. "
            "Без CAPS LOCK, без непроверяемых обещаний."
        )
        fmt = (
            "ФОРМАТ (для каждого варианта):\n"
            "Вариант N:\n"
            "Заголовок: ...\n"
            "Текст: ...\n"
        )
    elif kind == "vk":
        sys = (
            "Ты — специалист по нативным постам для VK. Создай РОВНО 5 коротких вариантов поста "
            f"(≤ {LIMITS['vk_post']} символов), 1–2 ключевые выгоды + действие. Без агрессии."
        )
        fmt = (
            "ФОРМАТ (для каждого варианта):\n"
            "Вариант N:\n"
            "Пост: ...\n"
            "CTA: (коротко)\n"
        )
    elif kind == "tgads":
        sys = (
            "Ты — специалист по Telegram Ads. Создай РОВНО 5 вариантов текста "
            f"(≤ {LIMITS['tgads_text']} символов), на 'вы', 1–2 предложения, CTA в конце."
        )
        fmt = (
            "ФОРМАТ (для каждого варианта):\n"
            "Вариант N:\n"
            "Текст: ...\n"
            "CTA: ...\n"
        )
    else:  # seeding
        sys = (
            "Ты — специалист по нативным посевам в Telegram-каналах. Создай РОВНО 5 вариантов поста "
            f"(≤ {LIMITS['seeding_post']} символов). Органично, без ощущения 'баннера'."
        )
        fmt = (
            "ФОРМАТ (для каждого варианта):\n"
            "Вариант N:\n"
            "Текст на креативе (1 строка): ...\n"
            "Пост: ...\n"
        )

    user = (
        f"Площадка: {platform}\n"
        f"Данные: {json.dumps(base, ensure_ascii=False, indent=2)}\n\n"
        f"{fmt}\n"
        "Сделай варианты различающимися по подаче."
    )

    data = call_openrouter_chat(
        model="google/gemini-2.5-flash",
        messages=[
            {"role": "system", "content": sys},
            {"role": "user", "content": user},
        ],
        temperature=0.7,
        max_tokens=1600,
    )
    content = data["choices"][0]["message"]["content"]
    return content


def extract_image_data_url(openrouter_json):
    """
    Пытаемся достать изображение из ответа (форматы могут отличаться).
    Поддерживаем:
    - content как список блоков (type=image_url)
    - строка с data:image/...;base64,...
    - строка с base64 (находим длинный base64)
    """
    msg = openrouter_json["choices"][0]["message"]
    content = msg.get("content")

    # 1) мультимодальный список
    if isinstance(content, list):
        for part in content:
            if isinstance(part, dict):
                t = part.get("type")
                if t == "image_url" and isinstance(part.get("image_url"), dict):
                    url = part["image_url"].get("url", "")
                    if url.startswith("data:image"):
                        return url
                if t == "image" and "data" in part:
                    b64 = part.get("data", "")
                    if b64:
                        return f"data:image/png;base64,{b64}"

    # 2) строка
    if isinstance(content, str):
        m = re.search(r"(data:image\/[a-zA-Z]+;base64,[A-Za-z0-9+/=]+)", content)
        if m:
            return m.group(1)

        # попытка вытащить "длинный base64"
        m2 = re.search(r"([A-Za-z0-9+/=]{800,})", content)
        if m2:
            return f"data:image/png;base64,{m2.group(1)}"

    return ""


def generate_demo_image(prompt: str):
    data = call_openrouter_chat(
        model="google/gemini-2.5-flash-image",
        messages=[
            {"role": "system", "content": "Сгенерируй одно рекламное изображение. Без текста мелким шрифтом."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.6,
        max_tokens=1200,
    )
    return extract_image_data_url(data)


# =========================
# Sidebar: nav (FIXED)
# =========================
init_state()

st.sidebar.markdown("### 🧩 hh Сегменты — заявка")
st.sidebar.markdown('<div class="small">Форма → заявка → демо превью</div>', unsafe_allow_html=True)
st.sidebar.markdown("---")

st.sidebar.radio(
    "Навигация",
    PAGES,
    key="nav_page_ui",
    index=safe_index(PAGES, st.session_state["nav_page_ui"], 0),
    on_change=sync_from_sidebar,
)

st.sidebar.markdown("---")
st.sidebar.button("↩️ Сбросить форму", on_click=reset_form)

# Простой прогресс: считаем заполненность базовых + площадки
filled_base = sum(
    bool(st.session_state.get(k, "").strip())
    for k in ["basic_what", "basic_goal", "basic_url", "basic_segment", "basic_contact"]
)
filled_platforms = len(selected_platforms())
st.sidebar.markdown(
    f'<div class="small">Заполнено: <span class="kpi">{filled_base}</span>/5 (база) · '
    f'Площадки: <span class="kpi">{filled_platforms}</span></div>',
    unsafe_allow_html=True,
)

# =========================
# Header
# =========================
st.markdown('<div class="app-title">Заполнение заявки на изготовление материалов для hh Сегментов</div>', unsafe_allow_html=True)
st.markdown('<div class="app-subtitle">Заполнение брифа займет до 5 минут.</div>', unsafe_allow_html=True)

# =========================
# Step render helpers
# =========================
def nav_buttons(prev_page=None, next_page=None):
    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        if prev_page:
            st.button("← Назад", on_click=go, args=(prev_page,), use_container_width=True)
    with c2:
        if next_page:
            st.button("Далее →", on_click=go, args=(next_page,), type="primary", use_container_width=True)
    with c3:
        st.caption("Данные сохраняются автоматически (по ключам полей).")


# =========================
# Step 0: Start
# =========================
def step_start():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### Что это")
    st.markdown(
        "- Собираем минимально достаточный бриф для запуска hh Сегментов.\n"
        "- На финальном шаге покажем примерный вид объявлений по выбранным площадкам и форматам.",
    )
    st.markdown("</div>", unsafe_allow_html=True)

    st.button("➡️ Начать заполнение", on_click=go, args=("Основная информация",), type="primary", use_container_width=True)


# =========================
# Step 1: Basic
# =========================
def step_basic():
    with st.expander("Коротко про hh Сегменты", expanded=False):
        st.markdown(
            "• Площадка/форматы зависят от выбранных каналов.\n"
            "• Чем яснее сегмент и посадочная — тем точнее тексты и креативы.\n"
            "• Если нет готового текста посадочной — вставьте тезисы в «Контекст посадочной»."
        )

    col1, col2 = st.columns(2)

    with col1:
        st.text_area(
            "Что рекламируем*",
            key="basic_what",
            height=90,
            placeholder="Коротко: работодатель/вакансии/кампания — фокус.",
        )
        st.text_input(
            "Цель кампании*",
            key="basic_goal",
            placeholder="Трафик / рост откликов / узнаваемость (коротко).",
        )
        st.text_input(
            "Посадочная ссылка*",
            key="basic_url",
            placeholder="https://...",
        )
        st.text_input(
            "Гео",
            key="basic_geo",
            placeholder="Города/регионы (если нужно).",
        )

    with col2:
        st.text_area(
            "Описание сегмента*",
            key="basic_segment",
            height=120,
            placeholder="1–3 сегмента: кто эти люди, опыт/профиль/уровень.",
            help="Это аудитория, на которую будет показываться реклама.",
        )
        st.text_area(
            "Файлы/материалы (ссылки)",
            key="basic_files",
            height=90,
            placeholder="Лого / брендбук / референсы / исходники (ссылки).",
        )
        st.text_input(
            "Контактное лицо (кто заполняет)*",
            key="basic_contact",
            placeholder="Имя + контакт (если нужно).",
        )

    st.markdown('<div class="sep"></div>', unsafe_allow_html=True)
    st.markdown("#### Контекст посадочной (для генерации текстов)")
    st.text_area(
        "Если нет текста посадочной, вставьте сюда основные тезисы/выгоды/условия — это поможет генерации.",
        key="landing_context",
        height=140,
        placeholder="Коротко: УТП, условия, кому подходит, что сделать на странице…",
        label_visibility="visible",
    )

    nav_buttons(prev_page="Старт", next_page="Креативы и площадки")


# =========================
# Step 2: Platforms + formats
# =========================
def step_platforms():
    st.markdown("### Креативы и площадки")
    st.markdown('<div class="muted">Выберите рекламные площадки и форматы креативов.</div>', unsafe_allow_html=True)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.checkbox("Яндекс", key="sel_yandex")
    with c2:
        st.checkbox("VK", key="sel_vk")
    with c3:
        st.checkbox("Telegram Ads", key="sel_tgads")
    with c4:
        st.checkbox("Telegram посевы", key="sel_seeding")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("#### Форматы")

    if st.session_state["sel_yandex"]:
        st.multiselect(
            "Яндекс — форматы",
            FORMATS["Яндекс"],
            key="fmt_yandex",
            placeholder="Выберите формат(ы)",
        )

    if st.session_state["sel_vk"]:
        st.multiselect(
            "VK — форматы",
            FORMATS["VK"],
            key="fmt_vk",
            placeholder="Выберите формат(ы)",
        )

    if st.session_state["sel_tgads"]:
        st.multiselect(
            "Telegram Ads — форматы",
            FORMATS["Telegram Ads"],
            key="fmt_tgads",
            placeholder="Выберите формат(ы)",
        )

    if st.session_state["sel_seeding"]:
        st.multiselect(
            "Telegram посевы — форматы",
            FORMATS["Telegram посевы"],
            key="fmt_seeding",
            placeholder="Выберите формат(ы)",
        )

    nav_buttons(prev_page="Основная информация", next_page="Тексты и креативы")


# =========================
# Step 3: Texts + creatives
# =========================
def step_texts_creatives():
    st.markdown("### Тексты и креативы")
    st.markdown('<div class="muted">Заполните тексты/креативы по выбранным площадкам и форматам.</div>', unsafe_allow_html=True)

    plats = selected_platforms()
    if not plats:
        st.markdown('<div class="hint">Сначала выберите площадки на шаге «Креативы и площадки».</div>', unsafe_allow_html=True)
        nav_buttons(prev_page="Креативы и площадки", next_page="Примерный вид объявлений")
        return

    # Общий бриф по визуалу (если где-то выбран медиа-формат)
    any_media = False
    for p in plats:
        fmts = selected_formats(p)
        if any(f in ["Изображение", "Видео", "Пост + креатив"] for f in fmts):
            any_media = True

    if any_media:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("#### Общий бриф по визуалу (для всех медиа-форматов)")
        st.text_area(
            "Ключевое сообщение / УТП (1–2 формулировки)",
            key="visual_message",
            height=80,
            placeholder="Что должно быть понятно пользователю за 1–2 секунды.",
        )
        st.text_area(
            "Визуальные предпочтения / стиль (и референсы ссылками)",
            key="visual_style",
            height=90,
            placeholder="Стиль, фон/цвета, наличие людей, что точно не использовать…",
        )
        st.text_area(
            "Материалы бренда (ссылки)",
            key="visual_assets",
            height=70,
            placeholder="Лого, брендбук, исходники (ссылки).",
        )
        st.markdown("</div>", unsafe_allow_html=True)

    # Площадки
    for platform in plats:
        fmts = selected_formats(platform)
        if not fmts:
            continue

        with st.expander(f"{platform}: заполнение", expanded=True):
            # ---- Яндекс ----
            if platform == "Яндекс":
                if "Текст" in fmts:
                    # на всякий случай (обычно Яндекс тут медиа; текст даём как объявление)
                    pass

                st.markdown("**Тексты (объявление)**")
                st.text_input("Заголовок", key="yandex_title", placeholder="До 56 символов")
                counter_caption(st.session_state.get("yandex_title", ""), LIMITS["yandex_title"])

                st.text_area("Текст", key="yandex_text", height=90, placeholder="До 81 символа")
                counter_caption(st.session_state.get("yandex_text", ""), LIMITS["yandex_text"])

                c1, c2 = st.columns([1, 2])
                with c1:
                    if st.button("⚡ Сгенерировать 5 вариантов (Яндекс)", use_container_width=True):
                        try:
                            with st.spinner("Генерируем…"):
                                res = generate_5_text_variants("yandex", "Яндекс")
                            st.session_state["gen_texts"]["yandex"] = res
                            st.success("Готово — см. ниже.")
                        except Exception as e:
                            st.error(str(e))
                with c2:
                    if st.session_state["gen_texts"].get("yandex"):
                        st.markdown("**Результат генерации**")
                        st.markdown(st.session_state["gen_texts"]["yandex"])

            # ---- VK ----
            if platform == "VK":
                st.markdown("**Текст поста**")
                st.text_area("Пост", key="vk_post", height=140, placeholder="Коротко: 1–2 выгоды + действие")
                counter_caption(st.session_state.get("vk_post", ""), LIMITS["vk_post"])

                c1, c2 = st.columns([1, 2])
                with c1:
                    if st.button("⚡ Сгенерировать 5 вариантов (VK)", use_container_width=True):
                        try:
                            with st.spinner("Генерируем…"):
                                res = generate_5_text_variants("vk", "VK")
                            st.session_state["gen_texts"]["vk"] = res
                            st.success("Готово — см. ниже.")
                        except Exception as e:
                            st.error(str(e))
                with c2:
                    if st.session_state["gen_texts"].get("vk"):
                        st.markdown("**Результат генерации**")
                        st.markdown(st.session_state["gen_texts"]["vk"])

            # ---- Telegram Ads ----
            if platform == "Telegram Ads":
                if "Текст" in fmts:
                    st.markdown("**TG Ads — текст**")
                    st.text_area("Текст сообщения", key="tgads_text", height=90, placeholder="1–2 предложения, CTA в конце")
                    counter_caption(st.session_state.get("tgads_text", ""), LIMITS["tgads_text"])

                    st.selectbox(
                        "CTA",
                        ["Подробнее", "Перейти", "Открыть", "Узнать больше"],
                        key="tgads_cta",
                    )

                    c1, c2 = st.columns([1, 2])
                    with c1:
                        if st.button("⚡ Сгенерировать 5 вариантов (TG Ads текст)", use_container_width=True):
                            try:
                                with st.spinner("Генерируем…"):
                                    res = generate_5_text_variants("tgads", "Telegram Ads")
                                st.session_state["gen_texts"]["tgads"] = res
                                st.success("Готово — см. ниже.")
                            except Exception as e:
                                st.error(str(e))
                    with c2:
                        if st.session_state["gen_texts"].get("tgads"):
                            st.markdown("**Результат генерации**")
                            st.markdown(st.session_state["gen_texts"]["tgads"])

            # ---- Telegram посевы ----
            if platform == "Telegram посевы":
                st.markdown("**Посев — пост + креатив**")
                st.text_input(
                    "Текст на изображении (1 строка)",
                    key="seeding_image_text",
                    placeholder="Короткое УТП",
                )
                counter_caption(st.session_state.get("seeding_image_text", ""), LIMITS["seeding_image_text"])

                st.text_area(
                    "Текст поста",
                    key="seeding_post",
                    height=160,
                    placeholder="3–5 абзацев: УТП → пояснение/доказательства → ссылка/CTA",
                )
                counter_caption(st.session_state.get("seeding_post", ""), LIMITS["seeding_post"])

                c1, c2 = st.columns([1, 2])
                with c1:
                    if st.button("⚡ Сгенерировать 5 вариантов (Посевы)", use_container_width=True):
                        try:
                            with st.spinner("Генерируем…"):
                                res = generate_5_text_variants("seeding", "Telegram посевы")
                            st.session_state["gen_texts"]["seeding"] = res
                            st.success("Готово — см. ниже.")
                        except Exception as e:
                            st.error(str(e))
                with c2:
                    if st.session_state["gen_texts"].get("seeding"):
                        st.markdown("**Результат генерации**")
                        st.markdown(st.session_state["gen_texts"]["seeding"])

    nav_buttons(prev_page="Креативы и площадки", next_page="Примерный вид объявлений")


# =========================
# Step 4: Demo preview
# =========================
def render_demo_yandex(fmts):
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<span class="badge">DEMO · Яндекс</span>', unsafe_allow_html=True)

    title = st.session_state.get("yandex_title", "").strip() or "Заголовок объявления"
    text = st.session_state.get("yandex_text", "").strip() or "Текст объявления (как пример)."

    st.markdown(f"**{title}**")
    st.markdown(text)
    st.markdown('<div class="small">Быстрые ссылки (если нужны) · · ·</div>', unsafe_allow_html=True)

    if any(f in ["Изображение", "Видео"] for f in fmts):
        st.markdown('<div class="demo-wrap">', unsafe_allow_html=True)
        st.markdown("**Демо-визуал**")
        img_key = "demo_yandex_media"
        if st.session_state["gen_images"].get(img_key):
            st.image(st.session_state["gen_images"][img_key], use_container_width=True)
        else:
            st.image(svg_placeholder("Яндекс · медиа"), use_container_width=True)

        cols = st.columns([1, 2])
        with cols[0]:
            if st.button("✨ Сгенерировать демо-изображение", key="btn_img_yandex", use_container_width=True):
                try:
                    prompt = (
                        f"Рекламный креатив для HR/бренда работодателя. "
                        f"Сообщение: {st.session_state.get('visual_message','') or st.session_state.get('basic_what','')}. "
                        f"Стиль: {st.session_state.get('visual_style','')}. "
                        f"Без мелкого текста. Современный минимализм."
                    )
                    with st.spinner("Генерируем изображение…"):
                        data_url = generate_demo_image(prompt)
                    if not data_url:
                        raise RuntimeError("Не удалось извлечь изображение из ответа модели.")
                    st.session_state["gen_images"][img_key] = data_url
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


def render_demo_vk(fmts):
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<span class="badge">DEMO · VK</span>', unsafe_allow_html=True)

    if any(f in ["Изображение", "Видео"] for f in fmts):
        img_key = "demo_vk_media"
        if st.session_state["gen_images"].get(img_key):
            st.image(st.session_state["gen_images"][img_key], use_container_width=True)
        else:
            st.image(svg_placeholder("VK · медиа"), use_container_width=True)

        if st.button("✨ Сгенерировать демо-изображение", key="btn_img_vk", use_container_width=True):
            try:
                prompt = (
                    f"Креатив для поста VK. "
                    f"Тема: {st.session_state.get('basic_what','')}. "
                    f"Сообщение: {st.session_state.get('visual_message','')}. "
                    f"Стиль: {st.session_state.get('visual_style','')}. "
                    f"Минимализм, без мелкого текста."
                )
                with st.spinner("Генерируем изображение…"):
                    data_url = generate_demo_image(prompt)
                if not data_url:
                    raise RuntimeError("Не удалось извлечь изображение из ответа модели.")
                st.session_state["gen_images"][img_key] = data_url
                st.rerun()
            except Exception as e:
                st.error(str(e))

    post = st.session_state.get("vk_post", "").strip() or "Текст поста (пример). 1–2 выгоды + действие."
    st.markdown(post)
    st.markdown('<div class="small">CTA: Подробнее</div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def render_demo_tgads(fmts):
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<span class="badge">DEMO · Telegram Ads</span>', unsafe_allow_html=True)

    if any(f in ["Изображение", "Видео"] for f in fmts):
        img_key = "demo_tgads_media"
        if st.session_state["gen_images"].get(img_key):
            st.image(st.session_state["gen_images"][img_key], use_container_width=True)
        else:
            st.image(svg_placeholder("Telegram Ads · медиа"), use_container_width=True)

        if st.button("✨ Сгенерировать демо-изображение", key="btn_img_tgads", use_container_width=True):
            try:
                prompt = (
                    f"Premium креатив для Telegram Ads. "
                    f"Тема: {st.session_state.get('basic_what','')}. "
                    f"Сообщение: {st.session_state.get('visual_message','')}. "
                    f"Стиль: {st.session_state.get('visual_style','')}. "
                    f"Чистая композиция, без мелкого текста."
                )
                with st.spinner("Генерируем изображение…"):
                    data_url = generate_demo_image(prompt)
                if not data_url:
                    raise RuntimeError("Не удалось извлечь изображение из ответа модели.")
                st.session_state["gen_images"][img_key] = data_url
                st.rerun()
            except Exception as e:
                st.error(str(e))

    if "Текст" in fmts:
        txt = st.session_state.get("tgads_text", "").strip() or "Короткий текст объявления (пример)."
        cta = st.session_state.get("tgads_cta", "Подробнее")
        st.markdown(f"**Сообщение:** {txt} **{cta}**")
    else:
        st.markdown('<div class="small">Текст не выбран (только медиа).</div>', unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


def render_demo_seeding(fmts):
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<span class="badge">DEMO · Telegram посевы</span>', unsafe_allow_html=True)

    img_key = "demo_seeding_media"
    if st.session_state["gen_images"].get(img_key):
        st.image(st.session_state["gen_images"][img_key], use_container_width=True)
    else:
        headline = st.session_state.get("seeding_image_text", "").strip() or "УТП на креативе"
        st.image(svg_placeholder(f"Посев · {headline}"), use_container_width=True)

    if st.button("✨ Сгенерировать демо-изображение", key="btn_img_seeding", use_container_width=True):
        try:
            prompt = (
                f"Креатив для нативного посева в Telegram. "
                f"УТП: {st.session_state.get('seeding_image_text','') or st.session_state.get('visual_message','')}. "
                f"Тема: {st.session_state.get('basic_what','')}. "
                f"Стиль: {st.session_state.get('visual_style','')}. "
                f"Можно крупный короткий заголовок, но без мелкого текста."
            )
            with st.spinner("Генерируем изображение…"):
                data_url = generate_demo_image(prompt)
            if not data_url:
                raise RuntimeError("Не удалось извлечь изображение из ответа модели.")
            st.session_state["gen_images"][img_key] = data_url
            st.rerun()
        except Exception as e:
            st.error(str(e))

    post = st.session_state.get("seeding_post", "").strip() or "Текст поста (пример): УТП → пояснение → ссылка/CTA."
    st.markdown(post)
    st.markdown("</div>", unsafe_allow_html=True)


def step_demo():
    st.markdown("### Примерный вид рекламных объявлений")
    st.markdown('<div class="muted">Покажем, как может выглядеть реклама по выбранным площадкам и форматам.</div>', unsafe_allow_html=True)

    st.markdown(
        '<div class="card"><div class="muted">'
        "Финальный вид зависит от модерации и конкретного формата. Здесь — быстрый мокап, чтобы согласовать направление."
        "</div></div>",
        unsafe_allow_html=True,
    )

    plats = selected_platforms()
    if not plats:
        st.markdown('<div class="hint">Сначала выберите площадки на шаге «Креативы и площадки».</div>', unsafe_allow_html=True)
        nav_buttons(prev_page="Тексты и креативы", next_page=None)
        return

    # Tabs по площадкам
    tabs = st.tabs(plats)
    for i, platform in enumerate(plats):
        fmts = selected_formats(platform)
        with tabs[i]:
            if platform == "Яндекс":
                render_demo_yandex(fmts)
            elif platform == "VK":
                render_demo_vk(fmts)
            elif platform == "Telegram Ads":
                render_demo_tgads(fmts)
            else:
                render_demo_seeding(fmts)

    nav_buttons(prev_page="Тексты и креативы", next_page=None)


# =========================
# Router
# =========================
page = st.session_state.get("nav_page", PAGES[0])

if page == "Старт":
    step_start()
elif page == "Основная информация":
    step_basic()
elif page == "Креативы и площадки":
    step_platforms()
elif page == "Тексты и креативы":
    step_texts_creatives()
elif page == "Примерный вид объявлений":
    step_demo()

# Footer
st.markdown(
    f"<div class='small' style='text-align:center; padding: 16px 0;'>"
    f"v1 · {datetime.now().strftime('%Y-%m-%d')} · hh segments brief"
    f"</div>",
    unsafe_allow_html=True,
)
