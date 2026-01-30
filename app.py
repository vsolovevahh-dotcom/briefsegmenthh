import streamlit as st
import requests
import json
from datetime import datetime
from urllib.parse import quote

# =========================
# Конфиг / константы
# =========================
st.set_page_config(
    page_title="hh Сегменты — заявка",
    page_icon="🧩",
    layout="wide",
)

STEPS = [
    "Старт",
    "Основная информация",
    "Креативы и площадки",
    "Тексты и креативы",
    "Примерный вид объявлений",
]

PLATFORMS = ["Яндекс", "VK", "Telegram Ads", "Telegram посевы"]

# Лимиты (можно поменять под ваши стандарты)
LIMITS = {
    "yandex_title": 56,
    "yandex_text": 81,
    "vk_text": 700,
    "tga_text": 220,            # текстовое объявление TG Ads
    "seed_image_text": 40,      # текст на изображении для посевов
    "seed_post_text": 1200,     # пост для посевов
}

# =========================
# Стили
# =========================
st.markdown(
    """
<style>
/* Общий тон */
.block-container {padding-top: 2.0rem;}
h1,h2,h3 {letter-spacing:-0.02em;}
.small-muted {color:#7a7a7a; font-size:0.95rem;}
.hr {height:1px; background:#efefef; margin:18px 0;}
.badge {display:inline-block; padding:6px 10px; border-radius:999px; background:#f3f4f6; font-size:0.9rem;}
.card {
  border:1px solid #eee; border-radius:16px; padding:16px; background:#fff;
}
.demo-wrap {border:1px solid #eee; border-radius:18px; padding:18px; background:#fff;}
.demo-title {font-weight:700; font-size:1.05rem; margin-bottom:6px;}
.demo-sub {color:#7a7a7a; font-size:0.95rem; margin-bottom:14px;}
.warn {background:#fff8db; border-left:6px solid #ffd24a; padding:12px 14px; border-radius:12px;}
.ok {background:#e9f7ef; border-left:6px solid #34c759; padding:12px 14px; border-radius:12px;}
</style>
""",
    unsafe_allow_html=True,
)

# =========================
# Session state init
# =========================
ALL_STATE_KEYS = [
    "nav_page",
    # step1
    "product_what",
    "campaign_goal",
    "landing_url",
    "geo",
    "segment_desc",
    "files_links",
    "contact_name",
    "landing_context",
    # step2
    "platforms_selected",
    "formats_selected",
    # step2 format checkboxes
    "fmt_yandex_img", "fmt_yandex_vid",
    "fmt_vk_img", "fmt_vk_vid",
    "fmt_tg_text", "fmt_tg_img", "fmt_tg_vid",
    # step3 inputs
    "yandex_title", "yandex_text",
    "vk_post_text",
    "tga_message_text",
    "seed_image_text", "seed_post_text",
    # generation cache
    "gen_yandex", "gen_tga", "gen_seed",
]

def init_state():
    defaults = {
        "nav_page": "Старт",
        "platforms_selected": [],
        "formats_selected": {},
        "product_what": "",
        "campaign_goal": "",
        "landing_url": "",
        "geo": "",
        "segment_desc": "",
        "files_links": "",
        "contact_name": "",
        "landing_context": "",
        "yandex_title": "",
        "yandex_text": "",
        "vk_post_text": "",
        "tga_message_text": "",
        "seed_image_text": "",
        "seed_post_text": "",
        "gen_yandex": "",
        "gen_tga": "",
        "gen_seed": "",
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)

init_state()

def reset_form():
    for k in list(st.session_state.keys()):
        # оставим служебные ключи streamlit
        if k in ALL_STATE_KEYS or k.startswith("fmt_"):
            try:
                del st.session_state[k]
            except Exception:
                pass
    init_state()

# =========================
# Helpers
# =========================
def remaining(limit_key: str, value: str) -> int:
    lim = LIMITS.get(limit_key, 999999)
    return lim - len(value or "")

def input_with_counter(label, key, limit_key, kind="text_input", placeholder=""):
    lim = LIMITS.get(limit_key)
    if kind == "text_input":
        val = st.text_input(label, key=key, placeholder=placeholder)
    else:
        val = st.text_area(label, key=key, placeholder=placeholder, height=120)
    if lim is not None:
        rem = remaining(limit_key, val)
        st.caption(f"Осталось {rem} символов из {lim}.")
    return val

def svg_data_uri(title: str, subtitle: str = "", w: int = 900, h: int = 420):
    # Неброский SVG-плейсхолдер "картинка"
    title = (title or "").replace("&", "and")
    subtitle = (subtitle or "").replace("&", "and")
    svg = f"""
<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">
  <defs>
    <linearGradient id="g" x1="0" x2="1" y1="0" y2="1">
      <stop offset="0%" stop-color="#f6f7fb"/>
      <stop offset="100%" stop-color="#eef1f7"/>
    </linearGradient>
  </defs>
  <rect x="0" y="0" width="{w}" height="{h}" rx="28" fill="url(#g)"/>
  <rect x="42" y="42" width="{w-84}" height="{h-84}" rx="22" fill="#ffffff" opacity="0.9"/>
  <text x="{w/2}" y="{h/2 - 10}" text-anchor="middle" font-size="34" font-family="Inter, Arial" fill="#111827" font-weight="700">{title}</text>
  <text x="{w/2}" y="{h/2 + 40}" text-anchor="middle" font-size="20" font-family="Inter, Arial" fill="#6b7280">{subtitle}</text>
  <circle cx="{w-90}" cy="90" r="26" fill="#f3f4f6"/>
  <path d="M{w-102} 90 L{w-84} 80 L{w-84} 100 Z" fill="#9ca3af"/>
</svg>
""".strip()
    return "data:image/svg+xml;utf8," + quote(svg)

def build_formats_from_widget_state(platforms: list[str]) -> dict:
    fmts = {}

    if "Яндекс" in platforms:
        fmts["Яндекс"] = []
        if st.session_state.get("fmt_yandex_img", False):
            fmts["Яндекс"].append("image")
        if st.session_state.get("fmt_yandex_vid", False):
            fmts["Яндекс"].append("video")

    if "VK" in platforms:
        fmts["VK"] = []
        if st.session_state.get("fmt_vk_img", False):
            fmts["VK"].append("image")
        if st.session_state.get("fmt_vk_vid", False):
            fmts["VK"].append("video")

    if "Telegram Ads" in platforms:
        fmts["Telegram Ads"] = []
        if st.session_state.get("fmt_tg_text", False):
            fmts["Telegram Ads"].append("text")
        if st.session_state.get("fmt_tg_img", False):
            fmts["Telegram Ads"].append("image")
        if st.session_state.get("fmt_tg_vid", False):
            fmts["Telegram Ads"].append("video")

    if "Telegram посевы" in platforms:
        fmts["Telegram посевы"] = ["post"]  # фикс

    return fmts

def openrouter_key_present() -> bool:
    return bool(st.secrets.get("OPENROUTER_API_KEY", "").strip())

def openrouter_generate_text(system_prompt: str, user_prompt: str, model: str = "google/gemini-2.5-flash") -> str:
    """
    Генерация текста через OpenRouter (опционально).
    Если ключ не задан — не вызываем.
    """
    api_key = st.secrets.get("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        return "⚠️ OPENROUTER_API_KEY не задан в Secrets."

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://streamlit.io",
        "X-Title": "hh-segments-brief",
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.7,
        "max_tokens": 1400,
    }

    r = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=60)
    if r.status_code != 200:
        try:
            return f"Ошибка API ({r.status_code}): {json.dumps(r.json(), ensure_ascii=False, indent=2)}"
        except Exception:
            return f"Ошибка API ({r.status_code}): {r.text}"
    data = r.json()
    return data["choices"][0]["message"]["content"]

def summary_block():
    # маленькое резюме в сайдбаре
    req_ok = 0
    req_total = 4
    if (st.session_state.get("product_what") or "").strip(): req_ok += 1
    if (st.session_state.get("campaign_goal") or "").strip(): req_ok += 1
    if (st.session_state.get("landing_url") or "").strip(): req_ok += 1
    if (st.session_state.get("segment_desc") or "").strip(): req_ok += 1

    p = st.session_state.get("platforms_selected", [])
    fmts = st.session_state.get("formats_selected", {})
    p_ok = 1 if len(p) > 0 else 0
    total = req_total + 1
    done = req_ok + p_ok
    prog = done / total

    st.sidebar.markdown("### Прогресс")
    st.sidebar.progress(prog)
    st.sidebar.caption(f"Заполнено: {done}/{total} (база + площадки)")

# =========================
# Sidebar
# =========================
st.sidebar.markdown("## 🧩 hh Сегменты — заявка")
st.sidebar.caption("Форма → заявка → демо превью")
st.sidebar.markdown('<div class="hr"></div>', unsafe_allow_html=True)

summary_block()

st.sidebar.markdown("### Навигация")
st.sidebar.radio(
    label="",
    options=STEPS,
    key="nav_page",
)

st.sidebar.markdown('<div class="hr"></div>', unsafe_allow_html=True)
if st.sidebar.button("↩️ Сбросить форму", use_container_width=True):
    reset_form()
    st.rerun()

# =========================
# Step 0 — Старт
# =========================
def step_0_start():
    st.title("Заполнение заявки на изготовление материалов для hh Сегментов")
    st.caption("Заполнение брифа займет до 5 минут.")
    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

    st.markdown(
        """
<div class="card">
  <div style="font-weight:700; font-size:1.05rem; margin-bottom:6px;">Что вы получите</div>
  <div class="small-muted">После заполнения формы вы увидите примерный вид объявлений по выбранным площадкам и форматам — чтобы быстро согласовать направление.</div>
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("➡️ Перейти к основной информации", type="primary", use_container_width=True):
            st.session_state["nav_page"] = "Основная информация"
            st.rerun()
    with c2:
        st.caption("Данные сохраняются автоматически. Можно возвращаться назад без потери заполненного.")

# =========================
# Step 1 — Основная информация
# =========================
def step_1_basic():
    st.title("Основная информация")
    st.caption("Минимально достаточный бриф для запуска. Данные сохраняются автоматически.")
    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

    with st.expander("Справка по hh Сегментам (коротко)"):
        st.markdown(
            """
- Заполняем ключевую информацию о размещении и аудитории.
- Далее выбираем площадки и форматы, потом — тексты/креативы и демо-превью.
            """.strip()
        )

    col1, col2 = st.columns(2)

    with col1:
        st.text_area(
            "Что рекламируем*",
            key="product_what",
            height=110,
            placeholder="Коротко: работодатель / вакансии / кампания. 1–3 предложения.",
        )
        st.text_input(
            "Цель кампании*",
            key="campaign_goal",
            placeholder="Например: трафик на вакансии / рост откликов / узнаваемость",
        )
        st.text_input(
            "Посадочная ссылка*",
            key="landing_url",
            placeholder="https://…",
        )
        st.text_input(
            "Гео",
            key="geo",
            placeholder="Города / регионы",
        )

    with col2:
        st.text_area(
            "Описание сегмента*",
            key="segment_desc",
            height=150,
            placeholder="Кто аудитория, опыт/профиль/уровень, важные признаки.",
            help="Это аудитория, на которую будет показываться реклама.",
        )
        st.text_area(
            "Файлы/материалы (ссылки)",
            key="files_links",
            height=110,
            placeholder="Лого / брендбук / референсы / исходники (ссылки)",
        )
        st.text_input(
            "Контактное лицо (кто заполняет)*",
            key="contact_name",
            placeholder="Имя",
        )

    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)
    st.subheader("Контекст посадочной страницы (для генерации текстов)")
    st.caption("Если нужно — вставьте короткий контекст с посадочной: УТП, преимущества, условия, важные формулировки.")
    st.text_area(
        "Контекст (опционально)",
        key="landing_context",
        height=160,
        placeholder="Коротко: что важно учесть при написании объявлений…",
        label_visibility="collapsed",
    )

# =========================
# Step 2 — Креативы и площадки
# =========================
def step_2_platforms():
    st.title("Креативы и площадки")
    st.caption("Выберите рекламные площадки и форматы креативов. Данные сохраняются автоматически.")
    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

    st.multiselect(
        "Рекламные площадки",
        PLATFORMS,
        key="platforms_selected",
    )
    platforms = st.session_state.get("platforms_selected", [])

    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

    if not platforms:
        st.markdown('<div class="warn">Выберите хотя бы одну площадку, чтобы появились форматы.</div>', unsafe_allow_html=True)
        st.session_state["formats_selected"] = {}
        return

    # Форматы по площадкам
    if "Яндекс" in platforms:
        st.subheader("Яндекс — форматы креативов")
        c1, c2 = st.columns(2)
        with c1:
            st.checkbox("Изображение", key="fmt_yandex_img")
        with c2:
            st.checkbox("Видео", key="fmt_yandex_vid")

    if "VK" in platforms:
        st.subheader("VK — форматы креативов")
        c1, c2 = st.columns(2)
        with c1:
            st.checkbox("Изображение", key="fmt_vk_img")
        with c2:
            st.checkbox("Видео", key="fmt_vk_vid")

    if "Telegram Ads" in platforms:
        st.subheader("Telegram Ads — форматы креативов")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.checkbox("Текст", key="fmt_tg_text")
        with c2:
            st.checkbox("Изображение", key="fmt_tg_img")
        with c3:
            st.checkbox("Видео", key="fmt_tg_vid")

    if "Telegram посевы" in platforms:
        st.subheader("Telegram посевы — формат")
        st.info("Формат фиксированный: пост + креатив с текстом на изображении.")

    # ✅ Ключевой фикс: сохраняем форматы в session_state на каждом rerun
    st.session_state["formats_selected"] = build_formats_from_widget_state(platforms)

    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)
    st.markdown("**Выбрано:**")
    for p in platforms:
        fm = st.session_state["formats_selected"].get(p, [])
        st.markdown(f"- {p}: `{', '.join(fm) if fm else 'форматы не выбраны'}`")

# =========================
# Step 3 — Тексты и креативы
# =========================
def step_3_texts():
    st.title("Тексты и креативы")
    st.caption("Заполните тексты/креативы по выбранным площадкам и форматам. Данные сохраняются автоматически.")
    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

    platforms = st.session_state.get("platforms_selected", [])
    formats = st.session_state.get("formats_selected", {})

    if not platforms:
        st.markdown('<div class="warn">Сначала выберите площадки на шаге 2.</div>', unsafe_allow_html=True)
        return

    # Если платформа выбрана, но форматов нет (кроме посевов)
    empty_fmt = [p for p in platforms if p != "Telegram посевы" and len(formats.get(p, [])) == 0]
    if empty_fmt:
        st.markdown(
            f'<div class="warn">Для площадок: <b>{", ".join(empty_fmt)}</b> не выбраны форматы. Вернитесь на шаг 2 и отметьте нужные форматы.</div>',
            unsafe_allow_html=True,
        )
        return

    # Яндекс (если выбран)
    if "Яндекс" in platforms:
        st.subheader("Яндекс")
        st.caption("Текстовые поля применимы для большинства объявлений; визуал — на шаге демо-превью.")
        input_with_counter("Заголовок", key="yandex_title", limit_key="yandex_title", kind="text_input", placeholder="До 56 символов")
        input_with_counter("Текст", key="yandex_text", limit_key="yandex_text", kind="text_area", placeholder="До 81 символа")

        if openrouter_key_present():
            if st.button("✨ Сгенерировать 5 вариантов для Яндекс", use_container_width=True, key="btn_gen_yandex"):
                system = "Ты пишешь рекламные объявления для Яндекс. Строго соблюдай лимиты."
                user = f"""
Дано:
Что рекламируем: {st.session_state.get("product_what")}
Цель: {st.session_state.get("campaign_goal")}
Посадочная: {st.session_state.get("landing_url")}
Гео: {st.session_state.get("geo")}
Сегмент: {st.session_state.get("segment_desc")}
Контекст посадочной: {st.session_state.get("landing_context")}

Сгенерируй ровно 5 вариантов:
Формат каждого:
Вариант N
Заголовок (<=56)
Текст (<=81)
"""
                with st.spinner("Генерируем…"):
                    st.session_state["gen_yandex"] = openrouter_generate_text(system, user)
        else:
            st.caption("Чтобы включить генерацию: добавьте OPENROUTER_API_KEY в Streamlit → Settings → Secrets.")

        if st.session_state.get("gen_yandex"):
            st.markdown("**Сгенерированные варианты (Яндекс):**")
            st.code(st.session_state["gen_yandex"])

        st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

    # VK
    if "VK" in platforms:
        st.subheader("VK")
        st.caption("Пост: 1–3 абзаца, 1–2 выгоды + действие.")
        input_with_counter("Текст поста", key="vk_post_text", limit_key="vk_text", kind="text_area", placeholder="Текст поста для VK")

        st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

    # Telegram Ads
    if "Telegram Ads" in platforms:
        st.subheader("Telegram Ads")
        st.caption("Коротко и по делу: 1–2 предложения, без CAPS, без неподтвержденных обещаний, CTA в конце.")
        input_with_counter("Текст сообщения", key="tga_message_text", limit_key="tga_text", kind="text_area", placeholder="Например: … Подробнее / Перейти")

        if openrouter_key_present():
            if st.button("✨ Сгенерировать 5 вариантов для Telegram Ads", use_container_width=True, key="btn_gen_tga"):
                system = "Ты пишешь нативные рекламные тексты для Telegram Ads. Без агрессии. CTA в конце."
                user = f"""
Дано:
Что рекламируем: {st.session_state.get("product_what")}
Цель: {st.session_state.get("campaign_goal")}
Посадочная: {st.session_state.get("landing_url")}
Гео: {st.session_state.get("geo")}
Сегмент: {st.session_state.get("segment_desc")}
Контекст посадочной: {st.session_state.get("landing_context")}

Сгенерируй ровно 5 вариантов текста (каждый <= {LIMITS["tga_text"]} символов).
В конце CTA: "Подробнее" / "Перейти" / "Открыть".
"""
                with st.spinner("Генерируем…"):
                    st.session_state["gen_tga"] = openrouter_generate_text(system, user)
        else:
            st.caption("Чтобы включить генерацию: добавьте OPENROUTER_API_KEY в Streamlit → Settings → Secrets.")

        if st.session_state.get("gen_tga"):
            st.markdown("**Сгенерированные варианты (Telegram Ads):**")
            st.code(st.session_state["gen_tga"])

        st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

    # Telegram посевы
    if "Telegram посевы" in platforms:
        st.subheader("Telegram посевы")
        st.caption("Важно: в посевах креатив обычно с текстом на изображении. Укажите ключевое сообщение.")
        input_with_counter("Текст на изображении (1 строка)", key="seed_image_text", limit_key="seed_image_text", kind="text_input", placeholder="Короткое УТП")
        input_with_counter("Текст поста", key="seed_post_text", limit_key="seed_post_text", kind="text_area", placeholder="3–5 абзацев: УТП → пояснение → ссылка/CTA")

        if openrouter_key_present():
            if st.button("✨ Сгенерировать 5 вариантов для посевов", use_container_width=True, key="btn_gen_seed"):
                system = "Ты пишешь нативные посты для посевов в Telegram-каналах. Органично, без рекламного тона."
                user = f"""
Дано:
Что рекламируем: {st.session_state.get("product_what")}
Цель: {st.session_state.get("campaign_goal")}
Посадочная: {st.session_state.get("landing_url")}
Гео: {st.session_state.get("geo")}
Сегмент: {st.session_state.get("segment_desc")}
Текст на изображении: {st.session_state.get("seed_image_text")}
Контекст посадочной: {st.session_state.get("landing_context")}

Сгенерируй ровно 5 вариантов:
- Текст на изображении (<= {LIMITS["seed_image_text"]})
- Текст поста (<= {LIMITS["seed_post_text"]})
В конце CTA со ссылкой.
"""
                with st.spinner("Генерируем…"):
                    st.session_state["gen_seed"] = openrouter_generate_text(system, user)
        else:
            st.caption("Чтобы включить генерацию: добавьте OPENROUTER_API_KEY в Streamlit → Settings → Secrets.")

        if st.session_state.get("gen_seed"):
            st.markdown("**Сгенерированные варианты (посевы):**")
            st.code(st.session_state["gen_seed"])

# =========================
# Step 4 — Примерный вид объявлений (демо)
# =========================
def demo_yandex(formats):
    st.markdown("### Яндекс — демо")
    title = (st.session_state.get("yandex_title") or "Заголовок объявления").strip()
    text = (st.session_state.get("yandex_text") or "Текст объявления (пример).").strip()

    if "image" in formats:
        uri = svg_data_uri("Yandex: Image", "визуал (пример)")
        st.markdown('<div class="demo-wrap">', unsafe_allow_html=True)
        st.markdown('<div class="demo-title">Формат: изображение</div>', unsafe_allow_html=True)
        st.markdown(f'<img src="{uri}" style="width:100%; border-radius:16px;"/>', unsafe_allow_html=True)
        st.markdown(f"**{title}**")
        st.markdown(text)
        st.caption("Быстрые ссылки: Вакансии · О компании · Откликнуться")
        st.markdown("</div>", unsafe_allow_html=True)

    if "video" in formats:
        uri = svg_data_uri("Yandex: Video", "видео (пример)")
        st.markdown('<div class="demo-wrap">', unsafe_allow_html=True)
        st.markdown('<div class="demo-title">Формат: видео</div>', unsafe_allow_html=True)
        st.markdown(f'<img src="{uri}" style="width:100%; border-radius:16px;"/>', unsafe_allow_html=True)
        st.markdown(f"**{title}**")
        st.markdown(text)
        st.markdown("</div>", unsafe_allow_html=True)

def demo_vk(formats):
    st.markdown("### VK — демо")
    txt = (st.session_state.get("vk_post_text") or "Текст поста (пример): 1–2 выгоды + действие.").strip()

    if "image" in formats:
        uri = svg_data_uri("VK: Image", "пост с изображением (пример)")
        st.markdown('<div class="demo-wrap">', unsafe_allow_html=True)
        st.markdown('<div class="demo-title">Пост + изображение</div>', unsafe_allow_html=True)
        st.markdown(f'<img src="{uri}" style="width:100%; border-radius:16px;"/>', unsafe_allow_html=True)
        st.markdown(txt)
        st.caption("Кнопка/CTA (опционально): Перейти / Подробнее")
        st.markdown("</div>", unsafe_allow_html=True)

    if "video" in formats:
        uri = svg_data_uri("VK: Video", "пост с видео (пример)")
        st.markdown('<div class="demo-wrap">', unsafe_allow_html=True)
        st.markdown('<div class="demo-title">Пост + видео</div>', unsafe_allow_html=True)
        st.markdown(f'<img src="{uri}" style="width:100%; border-radius:16px;"/>', unsafe_allow_html=True)
        st.markdown(txt)
        st.markdown("</div>", unsafe_allow_html=True)

def demo_tg_ads(formats):
    st.markdown("### Telegram Ads — демо")
    msg = (st.session_state.get("tga_message_text") or "Текст сообщения (пример). CTA в конце: Подробнее / Перейти.").strip()

    if "text" in formats:
        st.markdown('<div class="demo-wrap">', unsafe_allow_html=True)
        st.markdown('<div class="demo-title">Формат: текст</div>', unsafe_allow_html=True)
        st.markdown(
            f"""
<div style="max-width:680px; padding:14px 16px; border-radius:16px; background:#f3f4f6;">
  <div style="font-weight:700; margin-bottom:6px;">Рекламное сообщение</div>
  <div style="white-space:pre-wrap;">{msg}</div>
</div>
""",
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

    if "image" in formats:
        uri = svg_data_uri("TG Ads: Image", "медиа (пример)")
        st.markdown('<div class="demo-wrap">', unsafe_allow_html=True)
        st.markdown('<div class="demo-title">Формат: изображение</div>', unsafe_allow_html=True)
        st.markdown(f'<img src="{uri}" style="width:100%; border-radius:16px;"/>', unsafe_allow_html=True)
        st.markdown(msg)
        st.markdown("</div>", unsafe_allow_html=True)

    if "video" in formats:
        uri = svg_data_uri("TG Ads: Video", "медиа (пример)")
        st.markdown('<div class="demo-wrap">', unsafe_allow_html=True)
        st.markdown('<div class="demo-title">Формат: видео</div>', unsafe_allow_html=True)
        st.markdown(f'<img src="{uri}" style="width:100%; border-radius:16px;"/>', unsafe_allow_html=True)
        st.markdown(msg)
        st.markdown("</div>", unsafe_allow_html=True)

def demo_tg_seeding():
    st.markdown("### Telegram посевы — демо")
    img_txt = (st.session_state.get("seed_image_text") or "Ключевое сообщение").strip()
    post = (st.session_state.get("seed_post_text") or "Пост (пример): УТП → пояснение → ссылка/CTA.").strip()

    uri = svg_data_uri("TG Seeding", f"текст на изображении: {img_txt}")
    st.markdown('<div class="demo-wrap">', unsafe_allow_html=True)
    st.markdown('<div class="demo-title">Пост + креатив с текстом</div>', unsafe_allow_html=True)
    st.markdown(f'<img src="{uri}" style="width:100%; border-radius:16px;"/>', unsafe_allow_html=True)
    st.markdown(post)
    st.markdown("</div>", unsafe_allow_html=True)

def step_4_demo():
    st.title("Примерный вид объявлений")
    st.caption("Покажем, как может выглядеть реклама по выбранным площадкам и форматам.")
    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

    platforms = st.session_state.get("platforms_selected", [])
    formats = st.session_state.get("formats_selected", {})

    st.markdown(
        """
<div class="card">
  <div class="demo-title">Демо-пример</div>
  <div class="demo-sub">Финальный вид зависит от модерации и конкретного формата. Здесь — быстрый макет, чтобы согласовать направление.</div>
</div>
""",
        unsafe_allow_html=True,
    )
    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

    if not platforms:
        st.markdown('<div class="warn">Сначала выберите площадки и форматы на шаге 2.</div>', unsafe_allow_html=True)
        return

    # Tabs только по выбранным площадкам
    tabs = st.tabs(platforms)

    for i, p in enumerate(platforms):
        with tabs[i]:
            fm = formats.get(p, [])
            if p != "Telegram посевы" and not fm:
                st.markdown('<div class="warn">Для этой площадки не выбраны форматы (шаг 2).</div>', unsafe_allow_html=True)
                continue

            if p == "Яндекс":
                demo_yandex(fm)
            elif p == "VK":
                demo_vk(fm)
            elif p == "Telegram Ads":
                demo_tg_ads(fm)
            elif p == "Telegram посевы":
                demo_tg_seeding()

# =========================
# Router
# =========================
page = st.session_state.get("nav_page", "Старт")

if page == "Старт":
    step_0_start()
elif page == "Основная информация":
    step_1_basic()
elif page == "Креативы и площадки":
    step_2_platforms()
elif page == "Тексты и креативы":
    step_3_texts()
elif page == "Примерный вид объявлений":
    step_4_demo()
else:
    step_0_start()
