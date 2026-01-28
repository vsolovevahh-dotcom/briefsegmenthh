# app.py
# hh segments brief: бриф + демо + генерация текстов и демо-картинок через OpenRouter

import base64
import json
from datetime import datetime

import requests
import streamlit as st


# =========================
# CONFIG
# =========================
st.set_page_config(
    page_title="hh Сегменты — бриф перед запуском",
    page_icon="🧩",
    layout="wide",
)

# Модели OpenRouter
TEXT_MODEL = "google/gemini-2.5-flash"
IMAGE_MODEL = "google/gemini-2.5-flash-image"

# Площадки (в этой версии — 3 штуки, как просила)
PLATFORMS = ["Яндекс", "VK", "Telegram Ads"]

# Лимиты (дефолтные, можно поменять под ваши точные требования)
LIMITS = {
    "yandex_title": 56,
    "yandex_text": 81,
    "vk_post": 600,
    "tgads_text": 160,
}

CTA_OPTIONS = ["Подробнее", "Перейти", "Открыть", "Узнать больше", "Оставить заявку"]

PAGES = {
    0: "Старт / режим",
    1: "Основная информация",
    2: "Площадки",
    3: "Тексты и креативы",
    4: "Демо-превью",
}


# =========================
# STYLES
# =========================
st.markdown(
    """
<style>
:root{
  --hh-accent:#c07a00;
  --hh-muted:#6b7280;
  --hh-border:#e5e7eb;
  --hh-bg:#fafafa;
}
.block-title{
  font-size: 28px;
  font-weight: 760;
  margin: 6px 0 10px 0;
}
.small-muted{
  color: var(--hh-muted);
  font-size: 13px;
}
.hr{
  height:1px;background:var(--hh-border);margin:14px 0;
}
.badge{
  display:inline-block;
  padding:2px 8px;
  border:1px solid var(--hh-border);
  border-radius:999px;
  font-size:12px;
  color:var(--hh-muted);
  background:#fff;
}
.accent{
  color: var(--hh-accent);
  font-weight: 650;
}
.kv{
  background: var(--hh-bg);
  border:1px solid var(--hh-border);
  border-radius:14px;
  padding:14px 14px;
}
.demo-card{
  border:1px solid var(--hh-border);
  background:white;
  border-radius:16px;
  padding:16px;
}
.demo-header{
  font-weight:800;
  letter-spacing:0.2px;
}
.demo-tag{
  color:#ef4444;
  font-weight:800;
  margin-right:8px;
}
.mono{
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
}
</style>
""",
    unsafe_allow_html=True,
)


# =========================
# HELPERS
# =========================
def header_block(title: str, subtitle: str | None = None):
    st.markdown(f'<div class="block-title">{title}</div>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<div class="small-muted">{subtitle}</div>', unsafe_allow_html=True)


def is_client_view() -> bool:
    return st.session_state.mode == "Просмотр для клиента (апрув)"


def set_step(n: int):
    st.session_state.step = n
    st.rerun()


def remaining(limit: int, value: str) -> int:
    return max(limit - len(value or ""), 0)


def ensure_state():
    # Nav / mode
    st.session_state.setdefault("step", 0)
    st.session_state.setdefault("mode", "Заполняет менеджер hh (по умолчанию)")
    st.session_state.setdefault("platforms_selected", [])
    st.session_state.setdefault("submitted_at", None)

    # Base info
    st.session_state.setdefault("base_what", "")
    st.session_state.setdefault("base_goal", "")
    st.session_state.setdefault("base_url", "")
    st.session_state.setdefault("base_geo", "")
    st.session_state.setdefault("base_ta", "")
    st.session_state.setdefault("base_offer", "")
    st.session_state.setdefault("base_files", "")
    st.session_state.setdefault("base_contact", "")

    # Who делает тексты/креативы
    st.session_state.setdefault("yandex_text_who", "Клиент подготовит тексты")
    st.session_state.setdefault("yandex_creative_who", "Клиент предоставит материалы")
    st.session_state.setdefault("vk_text_who", "Клиент подготовит тексты")
    st.session_state.setdefault("vk_creative_who", "Клиент предоставит материалы")
    st.session_state.setdefault("tgads_text_who", "Клиент подготовит тексты")
    st.session_state.setdefault("tgads_creative_who", "Клиент предоставит материалы")

    # Yandex fields
    st.session_state.setdefault("yandex_title", "")
    st.session_state.setdefault("yandex_text", "")
    st.session_state.setdefault("yandex_quicklinks", "")

    st.session_state.setdefault("yandex_text_agree", False)
    st.session_state.setdefault("yandex_creative_agree", False)

    st.session_state.setdefault("yandex_metrika_id", "")
    st.session_state.setdefault("yandex_goals", "")

    # VK fields
    st.session_state.setdefault("vk_post_text", "")
    st.session_state.setdefault("vk_cta", "Подробнее")
    st.session_state.setdefault("vk_cta_custom", "")
    st.session_state.setdefault("vk_text_agree", False)
    st.session_state.setdefault("vk_creative_agree", False)

    # TG Ads fields
    st.session_state.setdefault("tgads_text", "")
    st.session_state.setdefault("tgads_text_agree", False)
    st.session_state.setdefault("tgads_creative_agree", False)

    # Materials links (если клиент даёт)
    st.session_state.setdefault("yandex_materials", "")
    st.session_state.setdefault("vk_materials", "")
    st.session_state.setdefault("tgads_materials", "")

    # AI outputs cache
    st.session_state.setdefault("ai_texts", {})   # platform -> string
    st.session_state.setdefault("ai_images", {})  # platform -> bytes
    st.session_state.setdefault("ai_notes", {})   # platform -> string (опц. текстовое пояснение от модели)


ensure_state()


def validate_step_1() -> list[str]:
    missing = []
    if not st.session_state.base_what.strip():
        missing.append("Что рекламируем*")
    if not st.session_state.base_goal.strip():
        missing.append("Цель кампании*")
    if not st.session_state.base_ta.strip():
        missing.append("ЦА (1–3 сегмента)*")
    if not st.session_state.base_offer.strip():
        missing.append("Оффер / ключевые тезисы*")
    if not st.session_state.base_contact.strip():
        missing.append("Контактное лицо*")
    return missing


def validate_step_2() -> list[str]:
    if not st.session_state.platforms_selected:
        return ["Выберите хотя бы одну площадку"]
    return []


def secrets_get(name: str, default: str = "") -> str:
    try:
        return st.secrets.get(name, default)  # type: ignore
    except Exception:
        return default


def openrouter_headers() -> dict:
    api_key = secrets_get("OPENROUTER_API_KEY")
    if not api_key:
        return {}
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    # опционально
    ref = secrets_get("OPENROUTER_HTTP_REFERER")
    title = secrets_get("OPENROUTER_X_TITLE")
    if ref:
        headers["HTTP-Referer"] = ref
    if title:
        headers["X-Title"] = title
    return headers


def openrouter_chat(prompt: str, model: str = TEXT_MODEL) -> str:
    headers = openrouter_headers()
    if not headers:
        return "⚠️ Нет OPENROUTER_API_KEY в secrets. Добавь ключ в Streamlit → App settings → Secrets."
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 2000,
    }
    r = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=90)
    if r.status_code != 200:
        return f"❌ Ошибка OpenRouter {r.status_code}: {r.text}"
    data = r.json()
    return data["choices"][0]["message"].get("content", "").strip()


def openrouter_image(prompt: str, aspect_ratio: str = "1:1", image_size: str = "1K", model: str = IMAGE_MODEL):
    """
    Возвращает (note_text, image_bytes or None)
    """
    headers = openrouter_headers()
    if not headers:
        return ("⚠️ Нет OPENROUTER_API_KEY в secrets. Добавь ключ в Streamlit → App settings → Secrets.", None)

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "modalities": ["image", "text"],
        "image_config": {
            "aspect_ratio": aspect_ratio,
            "image_size": image_size,
        },
        "temperature": 0.7,
    }

    r = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=120)
    if r.status_code != 200:
        return (f"❌ Ошибка OpenRouter {r.status_code}: {r.text}", None)

    data = r.json()
    msg = data["choices"][0]["message"]
    note = (msg.get("content") or "").strip()

    images = msg.get("images") or []
    if not images:
        return (note or "⚠️ Модель не вернула изображение. Попробуй снова.", None)

    # Обычно: images[0]["image_url"]["url"] == "data:image/png;base64,..."
    url = images[0].get("image_url", {}).get("url") or images[0].get("url")
    if not url or "base64," not in url:
        return (note or "⚠️ Не удалось распарсить data-url изображения.", None)

    b64 = url.split("base64,", 1)[1]
    try:
        img_bytes = base64.b64decode(b64)
        return (note, img_bytes)
    except Exception:
        return (note or "⚠️ Не удалось декодировать base64.", None)


def base_context_block() -> str:
    return f"""
Контекст кампании:
- Что рекламируем: {st.session_state.base_what}
- Цель: {st.session_state.base_goal}
- Посадка: {st.session_state.base_url}
- Гео: {st.session_state.base_geo}
- ЦА: {st.session_state.base_ta}
- Оффер/тезисы: {st.session_state.base_offer}
"""


def prompt_text_yandex() -> str:
    return f"""
Ты — эксперт по рекламным текстам.
Сгенерируй ровно 5 вариантов объявлений для Яндекс.

{base_context_block()}

Требования:
- Заголовок ≤ {LIMITS['yandex_title']} символов
- Текст ≤ {LIMITS['yandex_text']} символов
- Без CAPS LOCK, без непроверяемых обещаний, без агрессии
- CTA в конце (если уместно): "Подробнее", "Перейти", "Открыть"

Формат ответа:
Вариант 1:
Заголовок: ...
Текст: ...
Быстрые ссылки (опц., 2–3): ...

...
Вариант 5:
...

Важно: строго 5 вариантов.
""".strip()


def prompt_text_vk(cta: str) -> str:
    return f"""
Ты — эксперт по рекламным постам.
Сгенерируй ровно 5 вариантов текста поста для VK.

{base_context_block()}

Требования:
- Текст поста ≤ {LIMITS['vk_post']} символов
- Тон: деловой, дружелюбный, без "крика"
- 1–2 ключевые выгоды + действие
- CTA-кнопка: {cta}

Формат ответа:
Вариант 1:
Текст поста: ...

...
Вариант 5:
...

Важно: строго 5 вариантов.
""".strip()


def prompt_text_tgads() -> str:
    return f"""
Ты — эксперт по Telegram Ads.
Сгенерируй ровно 5 вариантов рекламного сообщения для Telegram Ads.

{base_context_block()}

Требования:
- Сообщение ≤ {LIMITS['tgads_text']} символов
- Обращение на "вы"
- 1–2 коротких предложения
- Без лишних эмодзи и CAPS LOCK
- Без непроверяемых цифр/обещаний
- CTA в конце: "Подробнее" / "Перейти" / "Открыть"

Формат ответа:
Вариант 1: ...
...
Вариант 5: ...

Важно: строго 5 вариантов.
""".strip()


def prompt_image_yandex() -> str:
    # Мокап карточки (без логотипов)
    return f"""
Сгенерируй ОДНО изображение: демо-мокап рекламного объявления в стиле "карточка рекламы" (не точная копия интерфейса).
Цель — показать клиенту "как это может выглядеть".

Требования:
- Без логотипов и названий реальных брендов (используй "Бренд" как плейсхолдер)
- Чистый минималистичный дизайн, светлый фон
- Компоновка: маленькая картинка/иллюстрация + заголовок + короткий текст + 2 быстрые ссылки
- Текст крупный и читабельный на мобильном
- Без водяных знаков

Контент (можно перефразировать):
Заголовок по смыслу: {st.session_state.base_offer.splitlines()[0][:60] if st.session_state.base_offer else "Ключевое предложение"}
Короткий текст по смыслу: {st.session_state.base_what[:120] if st.session_state.base_what else "Короткое описание предложения"}
CTA: Подробнее

Сгенерируй 1 изображение.
""".strip()


def prompt_image_vk() -> str:
    return f"""
Сгенерируй ОДНО изображение: демо-мокап поста в соцсети (не точная копия VK, а "в стиле ленты").
Цель — показать "как может выглядеть рекламный пост".

Требования:
- Без логотипов и названий реальных брендов (используй "Бренд")
- Светлый фон, аккуратная карточка поста
- Компоновка: сверху картинка/баннер, ниже текст 2–3 строки, ниже кнопка CTA
- Текст читаемый на мобильном
- Без водяных знаков

Контент по смыслу:
Тема/оффер: {st.session_state.base_offer.splitlines()[0][:80] if st.session_state.base_offer else "Ключевое предложение"}
CTA: {st.session_state.vk_cta_custom.strip() or st.session_state.vk_cta}

Сгенерируй 1 изображение.
""".strip()


def prompt_image_tgads() -> str:
    return f"""
Сгенерируй ОДНО изображение: демо-мокап "спонсорского сообщения" в мессенджере (не точная копия Telegram).
Цель — показать "как может выглядеть Telegram Ads".

Требования:
- Никаких логотипов Telegram и реальных брендов
- Интерфейс: пузырь сообщения, название канала "Бренд", метка "Sponsored" (как текст)
- Текст 1–2 строки + маленькая кнопка/ссылка CTA
- Минимализм, светлый фон, читабельность

Контент (по смыслу):
Сообщение: {st.session_state.base_what[:140] if st.session_state.base_what else "Короткое сообщение"}
CTA: Подробнее

Сгенерируй 1 изображение.
""".strip()


def pick_first_variant(text_block: str) -> str:
    """
    Очень простая эвристика: берём первые 300-400 символов как "пример",
    чтобы подставить в демо, если клиент не заполнил поля.
    """
    if not text_block:
        return ""
    t = text_block.strip()
    return t[:500]


def demo_card(title: str, lines: list[str]):
    st.markdown('<div class="demo-card">', unsafe_allow_html=True)
    st.markdown(
        f'<div class="demo-header"><span class="demo-tag">DEMO</span>• {title}</div>',
        unsafe_allow_html=True,
    )
    st.write("")
    for ln in lines:
        st.write(ln)
    st.markdown("</div>", unsafe_allow_html=True)


# =========================
# SIDEBAR
# =========================
with st.sidebar:
    st.markdown("### 🧩 hh Сегменты — бриф")
    st.caption("Форма → заявка → демо превью + генерация")

    st.session_state.mode = st.radio(
        "Режим",
        options=["Заполняет менеджер hh (по умолчанию)", "Просмотр для клиента (апрув)"],
        index=0 if st.session_state.mode.startswith("Заполняет") else 1,
    )

    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

    st.markdown("**Прогресс**")
    st.progress(st.session_state.step / 4)

    for k, v in PAGES.items():
        active = "✅" if k < st.session_state.step else ("➡️" if k == st.session_state.step else "•")
        st.write(f"{active} {k}. {v}")

    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

    if st.button("↩️ Сбросить форму"):
        keys = list(st.session_state.keys())
        for key in keys:
            if key not in ["_is_running_with_streamlit"]:
                del st.session_state[key]
        ensure_state()
        st.rerun()


# =========================
# SCREEN 0
# =========================
if st.session_state.step == 0:
    header_block("Экран 0. Старт / режим", "Заполнение брифа для hh Сегментов")

    st.markdown(
        """
<div class="kv">
<b>Заполнение брифа для hh Сегментов</b><br><br>
(переключатель)<br>
• <span class="accent">Заполняет менеджер hh</span> (по умолчанию)<br>
• Просмотр для клиента (апрув)<br><br>
</div>
""",
        unsafe_allow_html=True,
    )

    if st.button("Начать →", type="primary", use_container_width=True):
        set_step(1)


# =========================
# SCREEN 1 — BASE INFO
# =========================
if st.session_state.step == 1:
    header_block("Экран 1. Основная информация", "Минимально достаточный бриф")

    disable_all = is_client_view()

    with st.expander("Справочная информация по hh сегментам ▾", expanded=False):
        st.markdown(
            """
- Достаточно заполнить базовые поля, затем выбрать площадки.
- Ограничения/требования к форматам — внутри площадок.
- Демо на следующем шаге поможет быстро согласовать направление.
"""
        )

    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.session_state.base_what = st.text_area(
            "Что рекламируем (1–2 предложения)*",
            value=st.session_state.base_what,
            height=90,
            placeholder="Коротко: работодатель/вакансии/кампания, фокус.",
            disabled=disable_all,
        )
        st.session_state.base_goal = st.text_input(
            "Цель кампании*",
            value=st.session_state.base_goal,
            placeholder="Трафик / рост откликов / узнаваемость",
            disabled=disable_all,
        )
        st.session_state.base_url = st.text_input(
            "Посадочная ссылка",
            value=st.session_state.base_url,
            placeholder="https://…",
            disabled=disable_all,
        )
        st.session_state.base_geo = st.text_input(
            "Гео",
            value=st.session_state.base_geo,
            placeholder="Города/регионы",
            disabled=disable_all,
        )

    with col2:
        st.session_state.base_ta = st.text_area(
            "ЦА (1–3 сегмента)*",
            value=st.session_state.base_ta,
            height=110,
            placeholder="1–3 сегмента: кто эти люди, опыт/профили/уровень.",
            disabled=disable_all,
        )
        st.session_state.base_offer = st.text_area(
            "Оффер / ключевые тезисы (3–5 пунктов)*",
            value=st.session_state.base_offer,
            height=130,
            placeholder="— …\n— …\n— …",
            disabled=disable_all,
        )
        st.session_state.base_files = st.text_area(
            "Файлы/материалы (ссылки)",
            value=st.session_state.base_files,
            height=70,
            placeholder="Лого / брендбук / референсы / исходники (ссылки)",
            disabled=disable_all,
        )
        st.session_state.base_contact = st.text_input(
            "Контактное лицо (кто заполняет)*",
            value=st.session_state.base_contact,
            placeholder="Имя",
            disabled=disable_all,
        )

    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        if st.button("← Назад", use_container_width=True):
            set_step(0)
    with c2:
        if st.button("Далее →", type="primary", use_container_width=True):
            missing = validate_step_1()
            if missing:
                st.error("Заполните обязательные поля: " + ", ".join(missing))
            else:
                set_step(2)


# =========================
# SCREEN 2 — PLATFORMS
# =========================
if st.session_state.step == 2:
    header_block("Экран 2. Блок «Креативы и площадки»", "Выбор площадок")

    disable_all = is_client_view()

    st.markdown("Выберите рекламные площадки:")
    cols = st.columns(3)

    chosen = []
    for i, p in enumerate(PLATFORMS):
        with cols[i]:
            checked = p in st.session_state.platforms_selected
            val = st.checkbox(p, value=checked, disabled=disable_all, key=f"platform_{p}")
            if val:
                chosen.append(p)

    if not disable_all:
        st.session_state.platforms_selected = chosen

    st.caption("После выбора появятся блоки с требованиями к текстам/креативам и демо-превью.")

    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        if st.button("← Назад", use_container_width=True):
            set_step(1)
    with c2:
        if st.button("Далее →", type="primary", use_container_width=True):
            errs = validate_step_2()
            if errs:
                st.error(" / ".join(errs))
            else:
                set_step(3)


# =========================
# SCREEN 3 — PLATFORM BLOCKS
# =========================
def platform_block_yandex():
    disable_all = is_client_view()

    st.markdown("## Яндекс")

    st.markdown("### Тексты")
    st.session_state.yandex_text_who = st.radio(
        "Кто готовит тексты?",
        options=["Клиент подготовит тексты", "Команда hh подготовит тексты"],
        key="yandex_text_who",
        horizontal=True,
        disabled=disable_all,
    )

    if st.session_state.yandex_text_who == "Клиент подготовит тексты":
        st.session_state.yandex_title = st.text_input(
            f"Заголовок (лимит {LIMITS['yandex_title']})",
            value=st.session_state.yandex_title,
            disabled=disable_all,
        )
        st.caption(f"Осталось {remaining(LIMITS['yandex_title'], st.session_state.yandex_title)} символов")

        st.session_state.yandex_text = st.text_area(
            f"Текст (лимит {LIMITS['yandex_text']})",
            value=st.session_state.yandex_text,
            height=90,
            disabled=disable_all,
        )
        st.caption(f"Осталось {remaining(LIMITS['yandex_text'], st.session_state.yandex_text)} символов")

        st.session_state.yandex_quicklinks = st.text_area(
            "Быстрые ссылки (опц.) — каждая с новой строки",
            value=st.session_state.yandex_quicklinks,
            height=80,
            placeholder="https://…\nhttps://…",
            disabled=disable_all,
        )
    else:
        st.session_state.yandex_text_agree = st.checkbox(
            "Согласен(на), чтобы команда hh подготовила тексты (5 вариантов)",
            value=st.session_state.yandex_text_agree,
            disabled=False,
        )

    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

    st.markdown("**Дополнительно (для оптимизации)**")
    st.session_state.yandex_metrika_id = st.text_input(
        "Счётчик Яндекс.Метрики (ID)",
        value=st.session_state.yandex_metrika_id,
        placeholder="Напр.: 12345678",
        disabled=disable_all,
    )
    st.session_state.yandex_goals = st.text_area(
        "Ключевые цели на странице (опц.)",
        value=st.session_state.yandex_goals,
        height=70,
        placeholder="— отправка формы\n— клик по кнопке\n— успешный отклик …",
        disabled=disable_all,
    )
    st.caption("Это нужно для оптимизации рекламных кампаний по конкретным целям на посадочной.")

    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

    st.markdown("### Креативы")
    st.session_state.yandex_creative_who = st.radio(
        "Кто готовит креативы?",
        options=["Клиент предоставит материалы", "Команда hh подготовит креативы"],
        key="yandex_creative_who",
        horizontal=True,
        disabled=disable_all,
    )

    if st.session_state.yandex_creative_who == "Клиент предоставит материалы":
        st.session_state.yandex_materials = st.text_area(
            "Ссылки на материалы",
            value=st.session_state.yandex_materials,
            height=80,
            placeholder="Ссылки на исходники/диск/фигму/креативы",
            disabled=disable_all,
        )
    else:
        st.session_state.yandex_creative_agree = st.checkbox(
            "Согласен(на), чтобы команда hh подготовила креативы",
            value=st.session_state.yandex_creative_agree,
            disabled=False,
        )
        st.caption("Сноска: демо-картинка ниже — пример направления, финальный вид зависит от модерации и формата.")


def platform_block_vk():
    disable_all = is_client_view()

    st.markdown("## VK")

    st.markdown("### Тексты")
    st.session_state.vk_text_who = st.radio(
        "Кто готовит тексты?",
        options=["Клиент подготовит тексты", "Команда hh подготовит тексты"],
        key="vk_text_who",
        horizontal=True,
        disabled=disable_all,
    )

    if st.session_state.vk_text_who == "Клиент подготовит тексты":
        st.session_state.vk_post_text = st.text_area(
            f"Текст поста (лимит {LIMITS['vk_post']})",
            value=st.session_state.vk_post_text,
            height=140,
            disabled=disable_all,
        )
        st.caption(f"Осталось {remaining(LIMITS['vk_post'], st.session_state.vk_post_text)} символов")

        st.markdown("CTA-кнопка (опц.)")
        c1, c2 = st.columns([2, 1])
        with c1:
            st.session_state.vk_cta = st.selectbox(
                "Выберите CTA",
                options=CTA_OPTIONS,
                index=CTA_OPTIONS.index(st.session_state.vk_cta) if st.session_state.vk_cta in CTA_OPTIONS else 0,
                disabled=disable_all,
            )
        with c2:
            st.session_state.vk_cta_custom = st.text_input(
                "Свой вариант",
                value=st.session_state.vk_cta_custom,
                disabled=disable_all,
            )
        st.caption("Подсказка: 1–2 ключевые выгоды + действие.")
    else:
        st.session_state.vk_text_agree = st.checkbox(
            "Согласен(на), чтобы команда hh подготовила тексты (5 вариантов)",
            value=st.session_state.vk_text_agree,
            disabled=False,
        )

    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

    st.markdown("### Креативы")
    st.session_state.vk_creative_who = st.radio(
        "Кто готовит креативы?",
        options=["Клиент предоставит материалы", "Команда hh подготовит креативы"],
        key="vk_creative_who",
        horizontal=True,
        disabled=disable_all,
    )

    if st.session_state.vk_creative_who == "Клиент предоставит материалы":
        st.session_state.vk_materials = st.text_area(
            "Ссылки на материалы",
            value=st.session_state.vk_materials,
            height=80,
            placeholder="Ссылки на исходники/диск/фигму/креативы",
            disabled=disable_all,
        )
    else:
        st.session_state.vk_creative_agree = st.checkbox(
            "Согласен(на), чтобы команда hh подготовила креативы",
            value=st.session_state.vk_creative_agree,
            disabled=False,
        )
        st.caption("Сноска: демо-картинка ниже — пример направления, финальный вид зависит от модерации и формата.")


def platform_block_tgads():
    disable_all = is_client_view()

    st.markdown("## Telegram Ads")

    st.markdown("### Тексты")
    st.session_state.tgads_text_who = st.radio(
        "Кто готовит тексты?",
        options=["Клиент подготовит тексты", "Команда hh подготовит тексты"],
        key="tgads_text_who",
        horizontal=True,
        disabled=disable_all,
    )

    if st.session_state.tgads_text_who == "Клиент подготовит тексты":
        st.session_state.tgads_text = st.text_area(
            f"Текст сообщения (лимит {LIMITS['tgads_text']})",
            value=st.session_state.tgads_text,
            height=110,
            disabled=disable_all,
        )
        st.caption(f"Осталось {remaining(LIMITS['tgads_text'], st.session_state.tgads_text)} символов")

        st.markdown(
            """
**Подсказки:**
- Обращение на “вы”
- 1–2 коротких предложения
- Без CAPS LOCK и без лишних эмодзи
- Без неподтверждённых обещаний
- CTA в конце: “Подробнее”, “Перейти”, “Открыть”
"""
        )
    else:
        st.session_state.tgads_text_agree = st.checkbox(
            "Согласен(на), чтобы команда hh подготовила тексты (5 вариантов)",
            value=st.session_state.tgads_text_agree,
            disabled=False,
        )

    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

    st.markdown("### Креативы")
    st.session_state.tgads_creative_who = st.radio(
        "Кто готовит креативы?",
        options=["Клиент предоставит материалы", "Команда hh подготовит креативы"],
        key="tgads_creative_who",
        horizontal=True,
        disabled=disable_all,
    )

    if st.session_state.tgads_creative_who == "Клиент предоставит материалы":
        st.session_state.tgads_materials = st.text_area(
            "Ссылки на материалы",
            value=st.session_state.tgads_materials,
            height=80,
            placeholder="Ссылки на исходники/диск/фигму/креативы",
            disabled=disable_all,
        )
    else:
        st.session_state.tgads_creative_agree = st.checkbox(
            "Согласен(на), чтобы команда hh подготовила креативы",
            value=st.session_state.tgads_creative_agree,
            disabled=False,
        )
        st.caption("Сноска: демо-картинка ниже — пример направления, финальный вид зависит от модерации и формата.")


if st.session_state.step == 3:
    header_block(
        "Экран 3. Площадка = отдельная вкладка",
        "Для каждой площадки: тексты + креативы (кто делает) + поля при необходимости",
    )

    if not st.session_state.platforms_selected:
        st.warning("Сначала выберите площадки на Экран 2.")
    else:
        tabs = st.tabs(st.session_state.platforms_selected)
        for i, p in enumerate(st.session_state.platforms_selected):
            with tabs[i]:
                if p == "Яндекс":
                    platform_block_yandex()
                elif p == "VK":
                    platform_block_vk()
                elif p == "Telegram Ads":
                    platform_block_tgads()

    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        if st.button("← Назад", use_container_width=True):
            set_step(2)
    with c2:
        if st.button("Демо-превью →", type="primary", use_container_width=True):
            set_step(4)


# =========================
# SCREEN 4 — DEMO + GENERATION
# =========================
def render_demo_yandex():
    # Текст для демо: либо из полей клиента, либо из AI (если есть), либо плейсхолдер
    if st.session_state.yandex_title.strip() or st.session_state.yandex_text.strip():
        demo_title = st.session_state.yandex_title.strip() or "—"
        demo_text = st.session_state.yandex_text.strip() or "—"
        ql = [x.strip() for x in st.session_state.yandex_quicklinks.splitlines() if x.strip()]
    else:
        ai = st.session_state.ai_texts.get("Яндекс", "")
        demo_sample = pick_first_variant(ai) or ""
        demo_title = "Пример заголовка"
        demo_text = demo_sample if demo_sample else "Пример текста объявления"
        ql = ["https://example.com", "https://example.com/jobs"]

    demo_card(
        "Яндекс",
        [
            f"**Заголовок:** {demo_title}",
            f"**Текст:** {demo_text}",
            f"**Быстрые ссылки:** " + (" / ".join(ql) if ql else "—"),
        ],
    )

    img = st.session_state.ai_images.get("Яндекс")
    if img:
        st.write("")
        st.image(img, use_container_width=True)
    else:
        st.caption("Демо-картинка не сгенерирована (можно сгенерировать кнопкой ниже).")


def render_demo_vk():
    cta = st.session_state.vk_cta_custom.strip() or st.session_state.vk_cta

    demo_text = st.session_state.vk_post_text.strip()
    if not demo_text:
        ai = st.session_state.ai_texts.get("VK", "")
        demo_text = pick_first_variant(ai) or "Пример текста поста (2–3 строки)"

    demo_card(
        "VK",
        [
            "(картинка/баннер сверху — пример ниже)",
            f"**Текст поста:** {demo_text}",
            f"**CTA:** {cta or '—'}",
        ],
    )

    img = st.session_state.ai_images.get("VK")
    if img:
        st.write("")
        st.image(img, use_container_width=True)
    else:
        st.caption("Демо-картинка не сгенерирована (можно сгенерировать кнопкой ниже).")


def render_demo_tgads():
    demo_text = st.session_state.tgads_text.strip()
    if not demo_text:
        ai = st.session_state.ai_texts.get("Telegram Ads", "")
        demo_text = pick_first_variant(ai) or "Пример сообщения: 1–2 коротких предложения. Подробнее"

    demo_card(
        "Telegram Ads",
        [
            "**Channel:** Бренд",
            "**Sponsored**",
            f"**Текст:** {demo_text}",
            "**CTA:** Подробнее / Перейти / Открыть",
        ],
    )

    img = st.session_state.ai_images.get("Telegram Ads")
    if img:
        st.write("")
        st.image(img, use_container_width=True)
    else:
        st.caption("Демо-картинка не сгенерирована (можно сгенерировать кнопкой ниже).")


def generate_texts_for_platform(platform: str):
    if platform == "Яндекс":
        prompt = prompt_text_yandex()
    elif platform == "VK":
        cta = st.session_state.vk_cta_custom.strip() or st.session_state.vk_cta
        prompt = prompt_text_vk(cta)
    else:  # Telegram Ads
        prompt = prompt_text_tgads()

    out = openrouter_chat(prompt, model=TEXT_MODEL)
    st.session_state.ai_texts[platform] = out


def generate_image_for_platform(platform: str):
    if platform == "Яндекс":
        prompt = prompt_image_yandex()
        note, img = openrouter_image(prompt, aspect_ratio="1:1", image_size="1K")
    elif platform == "VK":
        prompt = prompt_image_vk()
        note, img = openrouter_image(prompt, aspect_ratio="1:1", image_size="1K")
    else:
        prompt = prompt_image_tgads()
        note, img = openrouter_image(prompt, aspect_ratio="1:1", image_size="1K")

    st.session_state.ai_notes[platform] = note
    if img:
        st.session_state.ai_images[platform] = img


def build_payload() -> dict:
    return {
        "meta": {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "mode": st.session_state.mode,
        },
        "base": {
            "what": st.session_state.base_what,
            "goal": st.session_state.base_goal,
            "landing_url": st.session_state.base_url,
            "geo": st.session_state.base_geo,
            "ta": st.session_state.base_ta,
            "offer": st.session_state.base_offer,
            "files": st.session_state.base_files,
            "contact": st.session_state.base_contact,
        },
        "platforms_selected": st.session_state.platforms_selected,
        "platforms": {
            "yandex": {
                "texts_who": st.session_state.yandex_text_who,
                "creatives_who": st.session_state.yandex_creative_who,
                "title": st.session_state.yandex_title,
                "text": st.session_state.yandex_text,
                "quicklinks": st.session_state.yandex_quicklinks,
                "metrika_id": st.session_state.yandex_metrika_id,
                "goals": st.session_state.yandex_goals,
                "materials": st.session_state.yandex_materials,
                "agree_texts": st.session_state.yandex_text_agree,
                "agree_creatives": st.session_state.yandex_creative_agree,
            },
            "vk": {
                "texts_who": st.session_state.vk_text_who,
                "creatives_who": st.session_state.vk_creative_who,
                "post_text": st.session_state.vk_post_text,
                "cta": st.session_state.vk_cta_custom.strip() or st.session_state.vk_cta,
                "materials": st.session_state.vk_materials,
                "agree_texts": st.session_state.vk_text_agree,
                "agree_creatives": st.session_state.vk_creative_agree,
            },
            "tgads": {
                "texts_who": st.session_state.tgads_text_who,
                "creatives_who": st.session_state.tgads_creative_who,
                "text": st.session_state.tgads_text,
                "materials": st.session_state.tgads_materials,
                "agree_texts": st.session_state.tgads_text_agree,
                "agree_creatives": st.session_state.tgads_creative_agree,
            },
        },
        "ai_outputs": {
            "texts": st.session_state.ai_texts,
            "notes": st.session_state.ai_notes,
            "images_present": {k: bool(v) for k, v in st.session_state.ai_images.items()},
        },
    }


if st.session_state.step == 4:
    header_block("Экран 4. Демо-превью + генерация", "Демо-пример, финальный вид зависит от модерации и формата.")

    st.markdown(
        """
<span class="badge">подпись везде</span><br>
<i>“Демо-пример, финальный вид зависит от модерации и формата.”</i>
""",
        unsafe_allow_html=True,
    )

    if not st.session_state.platforms_selected:
        st.warning("Нет выбранных площадок.")
    else:
        tabs = st.tabs(st.session_state.platforms_selected)

        for i, platform in enumerate(st.session_state.platforms_selected):
            with tabs[i]:
                # кнопки генерации
                b1, b2, b3 = st.columns([1, 1, 2])
                with b1:
                    if st.button("🤖 5 текстов", key=f"gen_texts_{platform}", use_container_width=True):
                        with st.spinner("Генерируем тексты…"):
                            generate_texts_for_platform(platform)
                        st.success("Готово: тексты сгенерированы.")
                with b2:
                    if st.button("🖼️ Демо-картинка", key=f"gen_img_{platform}", use_container_width=True):
                        with st.spinner("Генерируем демо-картинку…"):
                            generate_image_for_platform(platform)
                        st.success("Готово: демо-картинка сгенерирована.")
                with b3:
                    if st.button("♻️ Очистить генерации", key=f"clear_{platform}", use_container_width=True):
                        st.session_state.ai_texts.pop(platform, None)
                        st.session_state.ai_images.pop(platform, None)
                        st.session_state.ai_notes.pop(platform, None)
                        st.rerun()

                # демо карточка + картинка
                st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

                if platform == "Яндекс":
                    render_demo_yandex()
                elif platform == "VK":
                    render_demo_vk()
                else:
                    render_demo_tgads()

                # показать сгенерированные тексты (если есть)
                ai_txt = st.session_state.ai_texts.get(platform)
                if ai_txt:
                    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)
                    with st.expander("Показать 5 сгенерированных вариантов текста", expanded=False):
                        st.write(ai_txt)

                # показать note от image модели (если есть)
                note = st.session_state.ai_notes.get(platform)
                if note:
                    with st.expander("Пояснение модели к демо-картинке", expanded=False):
                        st.write(note)

    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

    # Финальный блок
    st.markdown("### Финальный блок")
    st.markdown(
        """
<div class="kv">
Если вам нравится направление, в течение <b>2–3 рабочих дней</b> мы пришлём <b>5 вариантов</b> на выбор для согласования.<br>
Демо — пример, финальный вид зависит от модерации и формата.
</div>
""",
        unsafe_allow_html=True,
    )

    payload = build_payload()
    payload_json = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")

    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        if st.button("← Назад", use_container_width=True):
            set_step(3)

    with c2:
        st.download_button(
            "Скачать заявку (JSON)",
            data=payload_json,
            file_name=f"hh_segments_brief_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            use_container_width=True,
        )

    with c3:
        if st.button("Передать в команду hh", type="primary", use_container_width=True):
            st.session_state.submitted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            st.success(f"Готово! Заявка сформирована ({st.session_state.submitted_at}).")
            with st.expander("Показать заявку для копирования"):
                st.code(payload_json.decode("utf-8"), language="json")


# =========================
# FOOTER
# =========================
st.markdown(
    """
<div style="text-align:center; color:#6b7280; padding:18px 0;">
  <span class="badge">hh segments brief • streamlit</span>
</div>
""",
    unsafe_allow_html=True,
)
