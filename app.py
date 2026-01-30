import streamlit as st
import requests
import re
from urllib.parse import urlparse

# -----------------------------
# Page config
# -----------------------------
st.set_page_config(
    page_title="hh Сегменты — заявка",
    page_icon="🧩",
    layout="wide",
)

# -----------------------------
# Styles
# -----------------------------
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
.small-muted{ color:var(--muted); font-size:0.92rem; }
.hr{ height:1px; background:var(--border); margin:18px 0; }
.card{
  background:var(--card-bg);
  border:1px solid var(--border);
  border-radius:16px;
  padding:16px;
}
.badge{
  display:inline-block;
  padding:6px 10px;
  border:1px solid var(--border);
  border-radius:999px;
  background:#fafafa;
  font-size:0.85rem;
  color:#111827;
}
.demo-wrap{ margin-top:8px; }
.demo-title{ font-weight:800; font-size:1.05rem; margin-bottom:8px; }
.demo-sub{ color:var(--muted); font-size:0.92rem; margin-bottom:10px; }
.ad{
  border:1px solid var(--border);
  border-radius:14px;
  padding:14px;
  background:#fff;
}
.ad-head{ font-weight:800; margin-bottom:6px; }
.ad-text{ color:#111827; margin-bottom:10px; }
.ad-meta{ color:var(--muted); font-size:0.85rem; }
.ad-btn{
  display:inline-block;
  padding:8px 12px;
  border-radius:10px;
  background:#111827;
  color:#fff;
  font-size:0.9rem;
  text-decoration:none;
}
.pill-red{
  color:var(--accent);
  font-weight:700;
}
</style>
""",
    unsafe_allow_html=True,
)

# -----------------------------
# State init
# -----------------------------
DEFAULTS = {
    # navigation
    "nav_page": "0. Старт",
    # internal persistence store (helps prevent accidental resets on reruns/navigation)
    "_persist": {},
    # Screen 1
    "what_advertise": "",
    "campaign_goal": "",
    "landing_url": "",
    "geo": "",
    "segment_desc": "",
    "files_links": "",
    "contact_name": "",
    "landing_context": "",
    # Screen 2 (platforms + formats)
    "pl_yandex": False,
    "pl_vk": False,
    "pl_tgads": False,
    "pl_tgseeding": False,
    "fmt_yandex_img": True,
    "fmt_yandex_video": False,
    "fmt_vk_img": True,
    "fmt_vk_video": False,
    "fmt_tg_text": True,
    "fmt_tg_img": False,
    "fmt_tg_video": False,
    # Screen 3 (owners + content)
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
    # Demo images (base64 data URL)
    "demo_images": {},  # key: "platform|format" -> data_url
}

for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v


# -----------------------------
# Persistence (fix: fields reset when navigating)
# -----------------------------
PERSIST_KEYS = [k for k in DEFAULTS.keys() if k not in {"nav_page", "demo_images", "_persist"}]


def persist_restore(keys):
    """Restore values from st.session_state._persist if widgets unexpectedly reset to defaults."""
    store = st.session_state.get("_persist", {}) or {}
    for k in keys:
        if k not in store:
            continue
        cur = st.session_state.get(k)
        default = DEFAULTS.get(k)
        # Restore only when current value looks like 'default' but we have a non-default saved value
        if isinstance(cur, str):
            if (cur or "") == "" and (store[k] or "") != "":
                st.session_state[k] = store[k]
        else:
            if cur == default and store[k] != default:
                st.session_state[k] = store[k]


def persist_save(keys):
    """Save only meaningful (non-default) values into st.session_state._persist."""
    store = st.session_state.get("_persist", {}) or {}
    for k in keys:
        v = st.session_state.get(k)
        d = DEFAULTS.get(k)
        if isinstance(v, str):
            if (v or "").strip() != "":
                store[k] = v
        else:
            if v != d:
                store[k] = v
    st.session_state["_persist"] = store


def persist_one(key: str):
    """Persist a single key immediately (used in on_change to avoid 'checkbox snaps back')."""
    store = st.session_state.get("_persist", {}) or {}
    store[key] = st.session_state.get(key)
    st.session_state["_persist"] = store


# Restore before any widgets are rendered
persist_restore(PERSIST_KEYS)


# -----------------------------
# Helpers
# -----------------------------
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
    if not re.match(r"^https?://", u, re.I):
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
        # very lightweight "strip html"
        text = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
        text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
        text = re.sub(r"(?s)<.*?>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:6000]  # keep it sane
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
        fmts = []
        if st.session_state.fmt_yandex_img:
            fmts.append("Изображение")
        if st.session_state.fmt_yandex_video:
            fmts.append("Видео")
        return fmts
    if platform == "VK":
        fmts = []
        if st.session_state.fmt_vk_img:
            fmts.append("Изображение")
        if st.session_state.fmt_vk_video:
            fmts.append("Видео")
        return fmts
    if platform == "Telegram Ads":
        fmts = []
        if st.session_state.fmt_tg_text:
            fmts.append("Текст")
        if st.session_state.fmt_tg_img:
            fmts.append("Изображение")
        if st.session_state.fmt_tg_video:
            fmts.append("Видео")
        return fmts
    if platform == "Telegram посевы":
        return ["Пост + изображение с текстом"]
    return []


def openrouter_api_key() -> str:
    try:
        return st.secrets.get("OPENROUTER_API_KEY", "")
    except Exception:
        return ""


def openrouter_chat(model: str, prompt: str, modalities=None, image_config=None, temperature=0.6, max_tokens=1200):
    api_key = openrouter_api_key()
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY не задан в Secrets")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": st.secrets.get("OPENROUTER_REFERER", "https://streamlit.app"),
        "X-Title": st.secrets.get("OPENROUTER_APP_TITLE", "hh-segments-brief"),
    }

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if modalities:
        payload["modalities"] = modalities
    if image_config:
        payload["image_config"] = image_config

    r = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=90)
    if r.status_code != 200:
        raise RuntimeError(f"OpenRouter API error {r.status_code}: {r.text[:500]}")
    return r.json()


def generate_demo_image(prompt: str, aspect_ratio="16:9", image_size="1K"):
    model = st.secrets.get("OPENROUTER_IMAGE_MODEL", "google/gemini-2.5-flash-image-preview")
    data = openrouter_chat(
        model=model,
        prompt=prompt,
        modalities=["image", "text"],
        image_config={"aspect_ratio": aspect_ratio, "image_size": image_size},
        temperature=0.2,
        max_tokens=300,
    )
    msg = data["choices"][0]["message"]
    images = msg.get("images") or []
    if not images:
        return None
    return images[0]["image_url"]["url"]


# -----------------------------
# Sidebar (progress + navigation)
# -----------------------------
PAGES = [
    "0. Старт",
    "1. Основная информация",
    "2. Креативы и площадки",
    "3. Тексты и креативы",
    "4. Примерный вид объявлений",
]

st.sidebar.markdown("## 🧩 hh Сегменты — заявка")
st.sidebar.markdown('<div class="small-muted">Форма → заявка → демо превью</div>', unsafe_allow_html=True)
st.sidebar.markdown('<div class="hr"></div>', unsafe_allow_html=True)

current_page = st.sidebar.radio("Навигация", PAGES, key="nav_page")

# Reset
def reset_form():
    keep = {"nav_page"}
    for k in list(st.session_state.keys()):
        if k not in keep:
            del st.session_state[k]
    # re-init defaults
    for k, v in DEFAULTS.items():
        if k not in st.session_state:
            st.session_state[k] = v
    st.session_state.nav_page = "0. Старт"

st.sidebar.button("↩️ Сбросить форму", on_click=reset_form, use_container_width=True)


# -----------------------------
# Screen 0
# -----------------------------
def screen_0():
    st.title("Заполнение заявки на изготовление материалов для hh Сегментов")
    st.markdown("Заполнение брифа займёт **до 5 минут**.")
    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

    st.markdown(
        """
<div class="card">
  <div class="demo-title">Что вы получите на выходе</div>
  <div class="demo-sub">
    Заполненный бриф по выбранным площадкам и форматам + примерный мокап (как может выглядеть реклама),
    чтобы быстро согласовать направление.
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

    def go_next():
        st.session_state.nav_page = "1. Основная информация"

    st.button("Начать →", on_click=go_next, type="primary", use_container_width=True)


# -----------------------------
# Screen 1
# -----------------------------
def screen_1():
    st.title("Основная информация")

    with st.expander("Справочная информация по hh сегментам (кратко)", expanded=False):
        st.markdown(
            """
- Бриф нужен, чтобы быстро собрать минимально достаточные вводные и избежать разночтений.  
- Важнее всего: **что рекламируем**, **цель**, **гео**, **описание сегмента**, **посадочная**.  
- Контекст посадочной можно **вставить вручную** или попробовать **подтянуть по ссылке** (если доступно).
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
            help="Это аудитория, на которую будет показываться реклама.",
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
    st.caption("Если есть — вставь текст с посадочной. Либо попробуй подтянуть по ссылке кнопкой ниже.")
    st.text_area(
        "Контекст посадочной (текст)",
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


# -----------------------------
# Screen 2
# -----------------------------
def screen_2():
    st.title("Креативы и площадки")
    st.caption("Выберите рекламные площадки и форматы креативов.")

    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Площадки")
        st.checkbox("Яндекс", key="pl_yandex", on_change=persist_one, args=("pl_yandex",))
        st.checkbox("VK", key="pl_vk", on_change=persist_one, args=("pl_vk",))
        st.checkbox("Telegram Ads", key="pl_tgads", on_change=persist_one, args=("pl_tgads",))
        st.checkbox("Telegram посевы", key="pl_tgseeding", on_change=persist_one, args=("pl_tgseeding",))

    with col2:
        st.subheader("Форматы (по площадкам)")
        if st.session_state.pl_yandex:
            st.markdown("**Яндекс**")
            st.checkbox("Изображение", key="fmt_yandex_img", on_change=persist_one, args=("fmt_yandex_img",))
            st.checkbox("Видео", key="fmt_yandex_video", on_change=persist_one, args=("fmt_yandex_video",))
            st.markdown("")

        if st.session_state.pl_vk:
            st.markdown("**VK**")
            st.checkbox("Изображение", key="fmt_vk_img", on_change=persist_one, args=("fmt_vk_img",))
            st.checkbox("Видео", key="fmt_vk_video", on_change=persist_one, args=("fmt_vk_video",))
            st.markdown("")

        if st.session_state.pl_tgads:
            st.markdown("**Telegram Ads**")
            st.checkbox("Текст", key="fmt_tg_text", on_change=persist_one, args=("fmt_tg_text",))
            st.checkbox("Изображение", key="fmt_tg_img", on_change=persist_one, args=("fmt_tg_img",))
            st.checkbox("Видео", key="fmt_tg_video", on_change=persist_one, args=("fmt_tg_video",))
            st.markdown("")

        if st.session_state.pl_tgseeding:
            st.markdown("**Telegram посевы**")
            st.markdown('<span class="small-muted">Формат фиксированный: пост + изображение с текстом</span>', unsafe_allow_html=True)

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


# -----------------------------
# Screen 3
# -----------------------------
def screen_3():
    st.title("Тексты и креативы")
    st.caption("Заполните тексты/креативы по выбранным площадкам и форматам. Данные сохраняются автоматически.")

    selected = get_selected_platforms()
    if not selected:
        st.warning("Сначала выберите площадки на шаге 2.")
        return

    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

    # -------- Yandex --------
    if "Яндекс" in selected:
        fmts = get_selected_formats("Яндекс")
        with st.expander("Яндекс", expanded=True):
            st.markdown("### Тексты")
            st.radio("Кто готовит тексты?", ["Клиент", "Команда hh"], key="yandex_text_owner", horizontal=True)

            if st.session_state.yandex_text_owner == "Клиент":
                limited_text_input("Заголовок (до 56)", "yandex_title", 56, placeholder="Коротко и по делу")
                limited_text_area("Текст (до 81)", "yandex_body", 81, height=90, placeholder="1–2 выгод(ы) + действие")
                st.text_area(
                    "Быстрые ссылки (опц.) — по одной на строку: Название | URL",
                    key="yandex_quicklinks",
                    height=90,
                    placeholder="Карьерный сайт | https://...\nВакансии | https://...",
                )
            else:
                st.text_area(
                    "Пожелания к текстам (1–3 строки)",
                    key="yandex_body",
                    height=90,
                    placeholder="Что важно отразить / какие формулировки избегать",
                )

            st.markdown("### Креативы")
            st.radio("Кто готовит креативы?", ["Клиент", "Команда hh"], key="yandex_creative_owner", horizontal=True)

            if st.session_state.yandex_creative_owner == "Клиент":
                st.text_area(
                    "Ссылки на материалы/исходники",
                    key="yandex_creative_links",
                    height=90,
                    placeholder="Ссылка на папку с исходниками / логотип / брендбук",
                )
            else:
                st.text_area(
                    "Что должно быть на креативе (1–2 строки)",
                    key="yandex_creative_brief",
                    height=90,
                    placeholder="Ключевое сообщение, стиль, обязательные элементы",
                )
                st.text_area(
                    "Референсы/исходники (ссылки, если есть)",
                    key="yandex_creative_links",
                    height=70,
                    placeholder="Ссылки (опционально)",
                )

            st.markdown(f"**Выбранные форматы:** {', '.join(fmts) if fmts else 'не выбраны'}")

    # -------- VK --------
    if "VK" in selected:
        fmts = get_selected_formats("VK")
        with st.expander("VK", expanded=False):
            st.markdown("### Тексты")
            st.radio("Кто готовит тексты?", ["Клиент", "Команда hh"], key="vk_text_owner", horizontal=True)

            if st.session_state.vk_text_owner == "Клиент":
                limited_text_area("Текст поста (до 700)", "vk_post_text", 700, height=130, placeholder="1–2 выгоды + действие")
                st.selectbox("CTA (опц.)", ["Перейти", "Подробнее", "Открыть", "Откликнуться"], key="vk_cta")
            else:
                st.text_area(
                    "Пожелания к текстам (1–3 строки)",
                    key="vk_post_text",
                    height=120,
                    placeholder="Что важно отразить / какой тон / чего избегать",
                )

            st.markdown("### Креативы")
            st.radio("Кто готовит креативы?", ["Клиент", "Команда hh"], key="vk_creative_owner", horizontal=True)
            if st.session_state.vk_creative_owner == "Клиент":
                st.text_area("Ссылки на материалы/исходники", key="vk_creative_links", height=90)
            else:
                st.text_area("Что должно быть на креативе (1–2 строки)", key="vk_creative_brief", height=90)
                st.text_area("Референсы/исходники (ссылки, если есть)", key="vk_creative_links", height=70)

            st.markdown(f"**Выбранные форматы:** {', '.join(fmts) if fmts else 'не выбраны'}")

    # -------- Telegram Ads --------
    if "Telegram Ads" in selected:
        fmts = get_selected_formats("Telegram Ads")
        with st.expander("Telegram Ads", expanded=False):
            if "Текст" in fmts:
                st.markdown("### TG Ads — текст")
                st.radio("Кто готовит текст?", ["Клиент", "Команда hh"], key="tg_text_owner", horizontal=True)
                if st.session_state.tg_text_owner == "Клиент":
                    limited_text_area(
                        "Текст сообщения (до 200)",
                        "tg_message",
                        200,
                        height=110,
                        placeholder="1–2 коротких предложения + CTA в конце",
                    )
                    st.selectbox("CTA (опц.)", ["Подробнее", "Перейти", "Открыть"], key="tg_cta")
                    st.caption("Подсказка: без CAPS LOCK, без неподтверждённых обещаний, минимум эмодзи.")
                else:
                    st.text_area("Пожелания к тексту (1–3 строки)", key="tg_message", height=110)

            if ("Изображение" in fmts) or ("Видео" in fmts):
                st.markdown("### TG Ads — медиа")
                st.radio("Кто готовит медиа?", ["Клиент", "Команда hh"], key="tg_media_owner", horizontal=True)
                if st.session_state.tg_media_owner == "Клиент":
                    st.text_area("Ссылки на материалы/исходники", key="tg_media_links", height=90)
                else:
                    st.text_area("Что должно быть на креативе (1–2 строки)", key="tg_media_brief", height=90)
                    st.text_area("Референсы/исходники (ссылки, если есть)", key="tg_media_links", height=70)

            st.markdown(f"**Выбранные форматы:** {', '.join(fmts) if fmts else 'не выбраны'}")

    # -------- Telegram Seeding --------
    if "Telegram посевы" in selected:
        with st.expander("Telegram посевы", expanded=False):
            st.markdown("Важно: в посевах **картинка обычно с текстом на ней** — укажи ключевое сообщение.")
            st.radio("Кто готовит материалы?", ["Клиент", "Команда hh"], key="seed_owner", horizontal=True)

            if st.session_state.seed_owner == "Клиент":
                limited_text_input("Текст на изображении (1 строка, до 40)", "seed_image_text", 40, placeholder="Короткое УТП/сообщение")
                limited_text_area("Текст поста (до 500)", "seed_post_text", 500, height=150, placeholder="3–5 абзацев: УТП → пояснение → ссылка/CTA")
                st.text_area("Ссылки на материалы/исходники (опц.)", key="seed_links", height=80)
            else:
                st.text_area("Ключевое сообщение / УТП (1–2 формулировки)", key="seed_image_text", height=90)
                st.text_area("Что важно в посте (смыслы/ограничения)", key="seed_post_text", height=140)
                st.text_area("Референсы/исходники (ссылки, если есть)", key="seed_links", height=80)

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


# -----------------------------
# Demo renderers
# -----------------------------
def demo_card_yandex(format_name: str):
    title = st.session_state.yandex_title.strip() or "Заголовок"
    body = st.session_state.yandex_body.strip() or "Текст объявления"
    st.markdown(f"<div class='badge'>Яндекс · {format_name}</div>", unsafe_allow_html=True)
    st.markdown(
        f"""
<div class="demo-wrap">
  <div class="ad">
    <div class="ad-head">{title}</div>
    <div class="ad-text">{body}</div>
    <div class="ad-meta">Ссылка: {st.session_state.landing_url or "https://..."}</div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def demo_card_vk(format_name: str):
    post = st.session_state.vk_post_text.strip() or "Текст поста"
    cta = st.session_state.vk_cta
    st.markdown(f"<div class='badge'>VK · {format_name}</div>", unsafe_allow_html=True)
    st.markdown(
        f"""
<div class="demo-wrap">
  <div class="ad">
    <div class="ad-text">{post}</div>
    <a class="ad-btn" href="#" onclick="return false;">{cta}</a>
    <div class="ad-meta" style="margin-top:10px;">Ссылка: {st.session_state.landing_url or "https://..."}</div>
  </div>
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
<div class="demo-wrap">
  <div class="ad">
    <div class="ad-text">{msg}</div>
    <div class="ad-meta">CTA: {cta}</div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def demo_card_tg_media(format_name: str):
    st.markdown(f"<div class='badge'>Telegram Ads · {format_name}</div>", unsafe_allow_html=True)
    caption = st.session_state.tg_message.strip() or "Подпись/сопроводительный текст (опц.)"
    st.markdown(
        f"""
<div class="demo-wrap">
  <div class="ad">
    <div class="ad-text">{caption}</div>
    <div class="ad-meta">Ссылка: {st.session_state.landing_url or "https://..."}</div>
  </div>
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
<div class="demo-wrap">
  <div class="ad">
    <div class="ad-head">{img_text}</div>
    <div class="ad-text">{post}</div>
    <div class="ad-meta">Ссылка: {st.session_state.landing_url or "https://..."}</div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_demo_images(platform: str, fmt: str):
    key = f"{platform}|{fmt}"
    data_url = st.session_state.demo_images.get(key)

    if data_url:
        st.image(data_url, use_column_width=True)
    else:
        st.info("Демо-визуал пока не сгенерирован (или не задан ключ OpenRouter).")


# -----------------------------
# Screen 4
# -----------------------------
def screen_4():
    st.title("Примерный вид рекламных объявлений")
    st.caption("Покажем, как может выглядеть реклама (быстрый мокап для согласования направления).")

    selected = get_selected_platforms()
    if not selected:
        st.warning("Сначала выберите площадки на шаге 2.")
        return

    st.markdown(
        """
<div class="card">
  <div class="demo-title">Демо-пример</div>
  <div class="demo-sub">
    Финальный вид зависит от модерации и конкретного формата. Здесь — быстрый мокап, чтобы согласовать направление.
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

    # Optional: generate demo visuals via OpenRouter
    api_key = openrouter_api_key()
    with st.expander("AI-генерация демо-визуалов (опционально)", expanded=False):
        if not api_key:
            st.warning("Чтобы генерировать демо-картинки, добавьте OPENROUTER_API_KEY в Streamlit Secrets.")
        else:
            st.caption("Сгенерируем по 1 демо-визуалу на выбранный формат (где уместно).")
            if st.button("🎨 Сгенерировать демо-визуалы", type="primary", use_container_width=True):
                with st.spinner("Генерируем демо-визуалы..."):
                    for p in selected:
                        fmts = get_selected_formats(p)
                        for f in fmts:
                            # generate only for image/video-like
                            if (p in ["Яндекс", "VK"] and f in ["Изображение", "Видео"]) or (p == "Telegram Ads" and f in ["Изображение", "Видео"]) or (p == "Telegram посевы"):
                                # Build prompt
                                core = st.session_state.what_advertise or "HR-кампания"
                                seg = st.session_state.segment_desc or "соискатели"
                                geo = st.session_state.geo or "Россия"
                                utp = ""
                                if p == "Telegram посевы":
                                    utp = st.session_state.seed_image_text or "Ключевое сообщение"
                                elif p == "Яндекс":
                                    utp = st.session_state.yandex_title or "Заголовок"
                                elif p == "VK":
                                    utp = (st.session_state.vk_post_text[:60] if st.session_state.vk_post_text else "Ключевое сообщение")
                                else:
                                    utp = st.session_state.tg_media_brief or "Ключевое сообщение"

                                aspect = "16:9"
                                if p == "Telegram Ads" and f in ["Изображение", "Видео"]:
                                    aspect = "16:9"
                                if p == "Telegram посевы":
                                    aspect = "4:5"

                                prompt = (
                                    "Create a clean modern advertising creative (no real brand logos, use a generic placeholder). "
                                    f"Topic: {core}. Audience: {seg}. Geo: {geo}. "
                                    f"Main message text to show (short, readable): '{utp}'. "
                                    "Style: minimal, corporate, high contrast, large readable typography. "
                                    "Add subtle UI hint 'hh segments demo' in small text. "
                                    "No offensive content."
                                )

                                try:
                                    img = generate_demo_image(prompt, aspect_ratio=aspect, image_size="1K")
                                    if img:
                                        st.session_state.demo_images[f"{p}|{f}"] = img
                                    else:
                                        st.session_state.demo_images[f"{p}|{f}"] = None
                                except Exception as e:
                                    st.warning(f"{p} · {f}: не удалось сгенерировать ({e})")

                st.success("Готово! Пролистайте ниже — демо-визуалы появятся в карточках.")

    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

    # Tabs per platform
    tabs = st.tabs(selected)
    for idx, platform in enumerate(selected):
        with tabs[idx]:
            fmts = get_selected_formats(platform)
            st.markdown(f"### {platform}")

            if not fmts:
                st.info("Форматы не выбраны на шаге 2.")
                continue

            # For each selected format show a demo block
            for fmt in fmts:
                st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

                left, right = st.columns([1.1, 1])

                with left:
                    st.markdown("#### Тексты (как заполнено)")
                    if platform == "Яндекс":
                        demo_card_yandex(fmt)
                    elif platform == "VK":
                        demo_card_vk(fmt)
                    elif platform == "Telegram Ads":
                        if fmt == "Текст":
                            demo_card_tg_text()
                        else:
                            demo_card_tg_media(fmt)
                    elif platform == "Telegram посевы":
                        demo_card_seeding()

                with right:
                    st.markdown("#### Демо-визуал (как может выглядеть)")
                    # Show demo image only where it makes sense
                    if platform == "Яндекс" and fmt in ["Изображение", "Видео"]:
                        render_demo_images(platform, fmt)
                    elif platform == "VK" and fmt in ["Изображение", "Видео"]:
                        render_demo_images(platform, fmt)
                    elif platform == "Telegram Ads" and fmt in ["Изображение", "Видео"]:
                        render_demo_images(platform, fmt)
                    elif platform == "Telegram посевы":
                        render_demo_images(platform, fmt)
                    else:
                        st.info("Для текстового формата визуал не требуется.")

    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)
    c1, c2 = st.columns([1, 1])
    with c1:
        def back():
            st.session_state.nav_page = "3. Тексты и креативы"
        st.button("← Назад", on_click=back, use_container_width=True)

    with c2:
        st.success("Если ок — можно копировать заявку из полей/ссылок и передавать в работу.")


# -----------------------------
# Router
# -----------------------------
if current_page == "0. Старт":
    screen_0()
elif current_page == "1. Основная информация":
    screen_1()
elif current_page == "2. Креативы и площадки":
    screen_2()
elif current_page == "3. Тексты и креативы":
    screen_3()
elif current_page == "4. Примерный вид объявлений":
    screen_4()

# Persist snapshot at the end of the run (prevents accidental resets on navigation)
persist_save(PERSIST_KEYS)
