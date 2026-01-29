import base64
import json
import textwrap
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import requests
import streamlit as st

# =========================
# CONFIG
# =========================
APP_TITLE = "hh Сегменты — бриф"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Текстовые лимиты (можно менять)
LIMITS = {
    "yandex_headline": 56,
    "yandex_text": 81,
    "tgads_text": 220,          # дружелюбный лимит под TG Ads (текст)
    "vk_post": 600,             # пост ВК (рекомендованный максимум для лаконичности)
    "tg_seed_image_text": 40,   # короткая строка на картинке
    "tg_seed_post": 600,        # пост для посевов
}

PLATFORMS = [
    ("yandex", "Яндекс"),
    ("vk", "VK"),
    ("tgads", "Telegram Ads"),
    ("tgseed", "Telegram посевы"),
]

TEXT_MODEL = "google/gemini-flash-1.5"  # для текстов (быстро/дёшево)
IMAGE_MODEL = "google/gemini-2.5-flash-image"  # для демо-картинок


# =========================
# PAGE
# =========================
st.set_page_config(page_title=APP_TITLE, page_icon="🧩", layout="wide")

st.markdown(
    """
<style>
/* общая типографика */
h1, h2, h3 { letter-spacing: -0.02em; }
.small-muted { color: rgba(0,0,0,0.55); font-size: 0.9rem; }
.hr { height: 1px; background: rgba(0,0,0,0.08); margin: 16px 0; }

/* карточки */
.card {
  background: #ffffff;
  border: 1px solid rgba(0,0,0,0.08);
  border-radius: 14px;
  padding: 16px;
}
.card-title {
  font-weight: 700;
  font-size: 1.05rem;
  margin-bottom: 6px;
}
.badge {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  border: 1px solid rgba(0,0,0,0.12);
  background: rgba(0,0,0,0.03);
  font-size: 0.8rem;
  margin-right: 6px;
}
.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
}
</style>
""",
    unsafe_allow_html=True,
)


# =========================
# STATE HELPERS
# =========================
def ss_get(key: str, default: Any = None) -> Any:
    return st.session_state.get(key, default)


def ss_init():
    st.session_state.setdefault("step", 0)
    st.session_state.setdefault("selected_platforms", {"yandex": True, "vk": False, "tgads": True, "tgseed": False})

    # Экран 1 — базовая инфа
    st.session_state.setdefault("what_advertise", "")
    st.session_state.setdefault("campaign_goal", "")
    st.session_state.setdefault("landing_url", "")
    st.session_state.setdefault("geo", "")
    st.session_state.setdefault("audience", "")
    st.session_state.setdefault("offer_points", ["", "", "", "", ""])
    st.session_state.setdefault("files_links", "")
    st.session_state.setdefault("contact_name", "")

    # Экран 3 — решения "кто делает"
    # значения: "client" / "hh"
    st.session_state.setdefault("who_text_yandex", "hh")
    st.session_state.setdefault("who_creative_yandex", "hh")
    st.session_state.setdefault("who_text_vk", "hh")
    st.session_state.setdefault("who_creative_vk", "hh")
    st.session_state.setdefault("who_text_tgads", "hh")
    st.session_state.setdefault("who_creative_tgads", "hh")
    st.session_state.setdefault("who_text_tgseed", "hh")
    st.session_state.setdefault("who_creative_tgseed", "hh")

    # согласия, если "hh"
    st.session_state.setdefault("consent_text_yandex", False)
    st.session_state.setdefault("consent_creative_yandex", False)
    st.session_state.setdefault("consent_text_vk", False)
    st.session_state.setdefault("consent_creative_vk", False)
    st.session_state.setdefault("consent_text_tgads", False)
    st.session_state.setdefault("consent_creative_tgads", False)
    st.session_state.setdefault("consent_text_tgseed", False)
    st.session_state.setdefault("consent_creative_tgseed", False)

    # поля, если "client"
    st.session_state.setdefault("yandex_headline", "")
    st.session_state.setdefault("yandex_text", "")
    st.session_state.setdefault("yandex_fastlinks", ["", "", ""])
    st.session_state.setdefault("yandex_metrika_id", "")
    st.session_state.setdefault("yandex_goals", "")

    st.session_state.setdefault("vk_post_text", "")
    st.session_state.setdefault("vk_cta", "Перейти")
    st.session_state.setdefault("vk_cta_custom", "")

    st.session_state.setdefault("tgads_message_text", "")
    st.session_state.setdefault("tgads_cta", "Подробнее")

    st.session_state.setdefault("tgseed_key_message", "")
    st.session_state.setdefault("tgseed_post_text", "")
    st.session_state.setdefault("tgseed_image_text", "")
    st.session_state.setdefault("tgseed_bullets", ["", "", "", "", ""])

    # генерации
    st.session_state.setdefault("generated_texts", {})   # platform -> parsed data/raw
    st.session_state.setdefault("generated_images", {})  # platform -> bytes/png
    st.session_state.setdefault("last_error", "")


ss_init()


# =========================
# OPENROUTER
# =========================
def get_openrouter_headers() -> Dict[str, str]:
    api_key = st.secrets.get("OPENROUTER_API_KEY", "")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    referer = st.secrets.get("OPENROUTER_HTTP_REFERER", "")
    title = st.secrets.get("OPENROUTER_X_TITLE", "")
    if referer:
        headers["HTTP-Referer"] = referer
    if title:
        headers["X-Title"] = title
    return headers


def openrouter_call(model: str, messages: List[Dict[str, Any]], temperature: float = 0.5, max_tokens: int = 2000) -> Dict[str, Any]:
    api_key = st.secrets.get("OPENROUTER_API_KEY", "")
    if not api_key:
        raise RuntimeError("Не найден OPENROUTER_API_KEY в Secrets (Streamlit Cloud → App settings → Secrets).")

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    r = requests.post(OPENROUTER_URL, headers=get_openrouter_headers(), json=payload, timeout=120)
    if r.status_code != 200:
        try:
            detail = r.json()
        except Exception:
            detail = {"text": r.text}
        raise RuntimeError(f"OpenRouter API error {r.status_code}: {json.dumps(detail, ensure_ascii=False)[:1500]}")
    return r.json()


def extract_text_from_response(resp: Dict[str, Any]) -> str:
    try:
        return resp["choices"][0]["message"]["content"]
    except Exception:
        return json.dumps(resp, ensure_ascii=False)


def extract_image_bytes(resp: Dict[str, Any]) -> Optional[bytes]:
    """
    Пытаемся достать data:image/...;base64,... из разных форматов ответа.
    """
    try:
        msg = resp["choices"][0]["message"]
    except Exception:
        return None

    # Вариант 1: content строка с data URI
    content = msg.get("content")
    if isinstance(content, str):
        if "data:image" in content and "base64," in content:
            # вытащить первую data-uri
            start = content.find("data:image")
            end = content.find(")", start)
            chunk = content[start:] if end == -1 else content[start:end]
            b64 = chunk.split("base64,", 1)[-1].strip()
            try:
                return base64.b64decode(b64)
            except Exception:
                return None

    # Вариант 2: content список объектов (multimodal)
    if isinstance(content, list):
        for part in content:
            if isinstance(part, dict):
                if part.get("type") in ("image_url", "input_image", "output_image"):
                    img = part.get("image_url") or part.get("image") or {}
                    url = img.get("url") if isinstance(img, dict) else None
                    if isinstance(url, str) and "base64," in url:
                        b64 = url.split("base64,", 1)[-1]
                        try:
                            return base64.b64decode(b64)
                        except Exception:
                            continue

    # Вариант 3: некоторые провайдеры кладут images отдельно
    images = msg.get("images") or resp.get("images")
    if isinstance(images, list) and images:
        first = images[0]
        if isinstance(first, str) and "base64," in first:
            b64 = first.split("base64,", 1)[-1]
            try:
                return base64.b64decode(b64)
            except Exception:
                return None

    return None


# =========================
# UX HELPERS
# =========================
def header_block(title: str, subtitle: Optional[str] = None):
    st.markdown(f"# {title}")
    if subtitle:
        st.markdown(f"<div class='small-muted'>{subtitle}</div>", unsafe_allow_html=True)
    st.markdown("<div class='hr'></div>", unsafe_allow_html=True)


def remaining(label: str, value: str, limit: int):
    n = len(value or "")
    left = max(limit - n, 0)
    st.caption(f"Лимит {limit} · осталось {left}")


def required_ok() -> bool:
    # минимально достаточные поля
    return all(
        [
            bool(ss_get("what_advertise", "").strip()),
            bool(ss_get("campaign_goal", "").strip()),
            bool(ss_get("audience", "").strip()),
            any([x.strip() for x in ss_get("offer_points", []) if isinstance(x, str)]),
            bool(ss_get("contact_name", "").strip()),
        ]
    )


def selected_platform_keys() -> List[str]:
    sel = ss_get("selected_platforms", {})
    return [k for k, _ in PLATFORMS if sel.get(k)]


def step2_ok() -> bool:
    return len(selected_platform_keys()) > 0


def go_step(n: int):
    st.session_state["step"] = n
    st.rerun()


def reset_all():
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    ss_init()
    st.rerun()


def make_brief_summary() -> str:
    offer = [x.strip() for x in ss_get("offer_points", []) if x and x.strip()]
    platforms = [name for key, name in PLATFORMS if ss_get("selected_platforms", {}).get(key)]
    return f"""HH Сегменты — заявка (черновик)
Дата: {datetime.now().strftime("%Y-%m-%d %H:%M")}

1) Основная информация
- Что рекламируем: {ss_get("what_advertise", "")}
- Цель: {ss_get("campaign_goal", "")}
- Посадочная: {ss_get("landing_url", "")}
- Гео: {ss_get("geo", "")}
- ЦА: {ss_get("audience", "")}
- Оффер/тезисы:
{chr(10).join([f"  - {x}" for x in offer])}
- Файлы/материалы: {ss_get("files_links", "")}
- Контакт: {ss_get("contact_name", "")}

2) Площадки
- {", ".join(platforms) if platforms else "не выбраны"}

3) Ввод по площадкам
(см. поля в форме / генерации)

4) Согласование
Если ок — передаём в команду hh, и за 2–3 рабочих дня пришлём 5 вариантов для согласования.
"""


# =========================
# PROMPTS
# =========================
def base_context_block() -> str:
    offer = [x.strip() for x in ss_get("offer_points", []) if x and x.strip()]
    return f"""
ОБЩИЙ КОНТЕКСТ БРИФА:
- Что рекламируем: {ss_get("what_advertise", "")}
- Цель кампании: {ss_get("campaign_goal", "")}
- Посадочная ссылка: {ss_get("landing_url", "")}
- Гео: {ss_get("geo", "")}
- ЦА: {ss_get("audience", "")}
- Оффер/ключевые тезисы: {", ".join(offer) if offer else "—"}
- Файлы/материалы: {ss_get("files_links", "")}
- Контактное лицо: {ss_get("contact_name", "")}
""".strip()


def prompt_text_yandex() -> Tuple[str, str]:
    sys = "Ты — эксперт по рекламным текстам для Яндекс (РСЯ/медийные форматы)."
    user = f"""
{base_context_block()}

Сгенерируй РОВНО 5 вариантов объявления.
Формат ответа — строго JSON без комментариев:

{{
  "variants": [
    {{
      "headline": "до {LIMITS['yandex_headline']} символов",
      "text": "до {LIMITS['yandex_text']} символов",
      "fastlinks": ["опционально 0-3 коротких пункта"]
    }}
  ]
}}

Правила:
- Без caps lock, без агрессии, без неподтверждённых обещаний.
- Должно быть понятно, что это HR/вакансии/работодатель (если применимо).
- Заголовок и текст — разные по смыслу (не дублировать).
""".strip()
    return sys, user


def prompt_text_vk() -> Tuple[str, str]:
    sys = "Ты — эксперт по текстам для постов ВК (рекламный пост, лаконично)."
    user = f"""
{base_context_block()}

Сгенерируй РОВНО 5 вариантов текста поста для ВК.
Формат — строго JSON:

{{
  "variants": [
    {{
      "post": "до {LIMITS['vk_post']} символов",
      "cta": "одна из: Перейти / Подробнее / Откликнуться / Смотреть вакансии"
    }}
  ]
}}

Правила:
- 1–2 ключевые выгоды + действие.
- Без лишних эмодзи (0–2 максимум).
- Без неподтвержденных цифр/обещаний.
""".strip()
    return sys, user


def prompt_text_tgads() -> Tuple[str, str]:
    sys = "Ты — эксперт по рекламным текстам для Telegram Ads (естественно в ленте)."
    user = f"""
{base_context_block()}

Сгенерируй РОВНО 5 вариантов сообщения для Telegram Ads.
Формат — строго JSON:

{{
  "variants": [
    {{
      "message": "до {LIMITS['tgads_text']} символов",
      "cta": "одна из: Подробнее / Перейти / Открыть"
    }}
  ]
}}

Правила:
- Обращение на «вы».
- 1–2 коротких предложения.
- Без CAPS LOCK и без лишних эмодзи.
- CTA в конце.
""".strip()
    return sys, user


def prompt_text_tgseed() -> Tuple[str, str]:
    sys = "Ты — эксперт по нативным рекламным постам для Telegram посевов."
    user = f"""
{base_context_block()}

Сгенерируй РОВНО 5 вариантов для посевов:
- строка на изображении (коротко)
- текст поста 3–5 абзацев, нативно

Формат — строго JSON:

{{
  "variants": [
    {{
      "image_text": "до {LIMITS['tg_seed_image_text']} символов",
      "post": "до {LIMITS['tg_seed_post']} символов",
      "bullets": ["опционально 0-5 смыслов/акцентов"]
    }}
  ]
}}

Правила:
- Главное: УТП + пояснение/доказательства + ссылка/CTA.
- Пост не должен выглядеть как «баннер», стиль телеграмный, живой.
- Эмодзи умеренно (0–3).
""".strip()
    return sys, user


def prompt_image(platform_key: str) -> str:
    # универсальный промпт под "мокап, как это может выглядеть"
    base = base_context_block()
    if platform_key == "yandex":
        return f"""
Сделай демо-мокап "как может выглядеть реклама" для Яндекс (карточка объявления).
Стиль: минималистичный clean UI, светлый фон, аккуратная карточка.
Внутри карточки:
- небольшая иллюстрация/фото-замена (нейтральная, без логотипов)
- заголовок (крупно)
- 1–2 строки текста
- 2–3 короткие "быстрые ссылки" внизу (как теги/пункты)
Важно: НЕ копируй точный интерфейс Яндекс, без брендинга/логотипов/водяных знаков.
Текст — на русском.
Контекст:
{base}
""".strip()

    if platform_key == "vk":
        return f"""
Сделай демо-мокап "как может выглядеть рекламный пост" для VK (универсальная соцсеть).
Стиль: чистый UI, светлый фон, карточка поста.
Композиция:
- сверху прямоугольная картинка/баннер (без логотипов)
- ниже 2–4 строки текста поста
- внизу кнопка CTA (например "Подробнее" / "Перейти")
Важно: НЕ копируй точный интерфейс VK, без логотипов/водяных знаков.
Текст — на русском.
Контекст:
{base}
""".strip()

    if platform_key == "tgads":
        return f"""
Сделай демо-мокап "как может выглядеть Telegram Ads" (сообщение в стиле мессенджера).
Стиль: clean UI, пузырь сообщения, светлая тема.
Композиция:
- название/лейбл канала (нейтрально)
- текст 1–2 предложения
- CTA в конце (например "Подробнее")
Важно: НЕ копируй точный интерфейс Telegram, без логотипов/водяных знаков.
Текст — на русском.
Контекст:
{base}
""".strip()

    # tgseed
    return f"""
Сделай демо-мокап "как может выглядеть посев в Telegram-канале".
Стиль: clean UI, пост в канале (универсально, без брендинга).
Композиция:
- изображение сверху с крупным текстом (1 строка УТП)
- ниже текст поста 3–5 коротких абзацев
- в конце ссылка/CTA
Важно: НЕ копируй точный интерфейс Telegram, без логотипов/водяных знаков.
Текст — на русском.
Контекст:
{base}
""".strip()


# =========================
# GENERATION
# =========================
def generate_texts_for(platform_key: str) -> Dict[str, Any]:
    if platform_key == "yandex":
        sys, user = prompt_text_yandex()
    elif platform_key == "vk":
        sys, user = prompt_text_vk()
    elif platform_key == "tgads":
        sys, user = prompt_text_tgads()
    else:
        sys, user = prompt_text_tgseed()

    messages = [
        {"role": "system", "content": sys},
        {"role": "user", "content": user},
    ]
    resp = openrouter_call(TEXT_MODEL, messages, temperature=0.6, max_tokens=2500)
    raw = extract_text_from_response(resp)

    # пытаемся распарсить JSON
    try:
        data = json.loads(raw)
        return {"ok": True, "data": data, "raw": raw}
    except Exception:
        return {"ok": True, "data": None, "raw": raw}


def generate_image_for(platform_key: str) -> bytes:
    prompt = prompt_image(platform_key)
    messages = [{"role": "user", "content": prompt}]
    resp = openrouter_call(IMAGE_MODEL, messages, temperature=0.4, max_tokens=1200)
    img_bytes = extract_image_bytes(resp)
    if not img_bytes:
        # если модель вернула текст — покажем ошибку понятнее
        raw = extract_text_from_response(resp)
        raise RuntimeError("Не удалось извлечь картинку из ответа модели. Ответ (обрезано):\n" + raw[:800])
    return img_bytes


# =========================
# SIDEBAR (NAV)
# =========================
with st.sidebar:
    st.markdown(f"## 🧩 {APP_TITLE}")
    st.markdown("<div class='small-muted'>Форма → заявка → демо-превью + генерация</div>", unsafe_allow_html=True)

    st.markdown("<div class='hr'></div>", unsafe_allow_html=True)

    # Прогресс
    st.markdown("### Прогресс")
    progress_val = (ss_get("step", 0) + 1) / 5
    st.progress(progress_val)

    def step_label(i: int, title: str) -> str:
        if i < ss_get("step", 0):
            return f"✅ {i}. {title}"
        if i == ss_get("step", 0):
            return f"➡️ {i}. {title}"
        return f"• {i}. {title}"

    # навигация кликом
    if st.button(step_label(0, "Старт"), use_container_width=True):
        go_step(0)
    if st.button(step_label(1, "Основная информация"), use_container_width=True):
        go_step(1)
    if st.button(step_label(2, "Площадки"), use_container_width=True):
        go_step(2)
    if st.button(step_label(3, "Тексты и креативы"), use_container_width=True):
        go_step(3)
    if st.button(step_label(4, "Демо-превью"), use_container_width=True):
        go_step(4)

    st.markdown("<div class='hr'></div>", unsafe_allow_html=True)
    if st.button("↩️ Сбросить форму", use_container_width=True):
        reset_all()


# =========================
# MAIN
# =========================
step = ss_get("step", 0)

# -------------------------
# STEP 0
# -------------------------
if step == 0:
    header_block("Экран 0. Старт", "Один режим: форма всегда редактируемая.")

    st.markdown(
        """
<div class="card">
  <div class="card-title">Заполнение брифа для hh Сегментов</div>
  <div class="small-muted">
    Цель — быстро собрать минимально достаточную заявку и сразу показать демо, как может выглядеть реклама.
  </div>
  <div style="margin-top:12px;">
    <span class="badge">минимум вопросов</span>
    <span class="badge">фиксируем кто делает тексты/креативы</span>
    <span class="badge">демо-превью</span>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown("<div class='hr'></div>", unsafe_allow_html=True)

    c1, c2 = st.columns([1, 1])
    with c1:
        st.markdown("### Что будет дальше")
        st.markdown(
            """
1) Основная информация (бренд/цель/ЦА/оффер)  
2) Выбор площадок (Яндекс / VK / Telegram Ads / Telegram посевы)  
3) Тексты и креативы: клиент сам или команда hh (с согласием)  
4) Демо-превью + генерации (5 вариантов и пример визуала)  
"""
        )
    with c2:
        st.markdown("### Минимум, чтобы запустить")
        st.markdown(
            """
- что рекламируем  
- цель кампании  
- ЦА (1–3 сегмента)  
- оффер (3–5 тезисов)  
- контактное лицо  
"""
        )

    if st.button("Начать →", type="primary", use_container_width=True):
        go_step(1)


# -------------------------
# STEP 1
# -------------------------
elif step == 1:
    header_block("Экран 1. Основная информация", "Минимально достаточный бриф (без лишних дисклэймеров).")

    with st.expander("Справочная информация по hh сегментам", expanded=False):
        st.markdown(
            """
- Здесь собираем основу заявки: что рекламируем, цель, ЦА, оффер, гео, посадочную.  
- Дальше — выберем площадки и решим, кто готовит тексты/креативы.  
- На демо-превью показываем «как может выглядеть» (мокап, не точная копия интерфейсов).  
"""
        )

    col1, col2 = st.columns(2)

    with col1:
        st.text_area(
            "Что рекламируем (1–2 предложения)*",
            key="what_advertise",
            height=90,
            placeholder="Коротко: работодатель/вакансии/кампания, фокус.",
        )
        st.text_input(
            "Цель кампании*",
            key="campaign_goal",
            placeholder="Трафик / рост откликов / узнаваемость / брендовый эффект...",
        )
        st.text_input(
            "Посадочная ссылка",
            key="landing_url",
            placeholder="https://...",
        )
        st.text_input(
            "Гео",
            key="geo",
            placeholder="Города/регионы",
        )
        st.text_area(
            "ЦА (1–3 сегмента)*",
            key="audience",
            height=110,
            placeholder="1–3 сегмента: кто эти люди, опыт/профили/уровень.",
        )

    with col2:
        st.markdown("Оффер / ключевые тезисы (3–5 пунктов)*")
        offer_points = ss_get("offer_points", ["", "", "", "", ""])
        for i in range(5):
            st.text_input(f"— пункт {i+1}", key=f"offer_points_{i}", value=offer_points[i] if i < len(offer_points) else "")
        # синхронизируем в массив
        st.session_state["offer_points"] = [ss_get(f"offer_points_{i}", "") for i in range(5)]

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

    st.markdown("<div class='hr'></div>", unsafe_allow_html=True)

    c1, c2 = st.columns([1, 1])
    with c1:
        if not required_ok():
            st.warning("Заполните обязательные поля (*) — иначе дальше будет сложно генерировать демо и тексты.")
    with c2:
        if st.button("Далее →", type="primary", use_container_width=True):
            go_step(2)


# -------------------------
# STEP 2
# -------------------------
elif step == 2:
    header_block("Экран 2. Креативы и площадки", "Выберите рекламные площадки — появятся блоки требований.")

    st.markdown("### Выберите рекламные площадки:")
    sel = ss_get("selected_platforms", {})

    cols = st.columns(4)
    for idx, (k, name) in enumerate(PLATFORMS):
        with cols[idx]:
            st.checkbox(name, key=f"plat_{k}", value=bool(sel.get(k)))

    st.session_state["selected_platforms"] = {k: bool(ss_get(f"plat_{k}", False)) for k, _ in PLATFORMS}

    st.info("После выбора площадок на следующем шаге появятся блоки по текстам и креативам.")

    st.markdown("<div class='hr'></div>", unsafe_allow_html=True)

    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("← Назад", use_container_width=True):
            go_step(1)
    with c2:
        if st.button("Далее →", type="primary", use_container_width=True):
            if not step2_ok():
                st.warning("Выберите хотя бы одну площадку.")
            else:
                go_step(3)


# -------------------------
# STEP 3
# -------------------------
elif step == 3:
    header_block("Экран 3. Тексты и креативы", "Для каждой площадки — кто делает тексты и креативы.")

    selected = selected_platform_keys()
    if not selected:
        st.warning("Площадки не выбраны. Вернитесь на шаг 2.")
    else:
        st.markdown(
            """
<div class="card">
  <div class="card-title">Логика</div>
  <div class="small-muted">
    Для каждой площадки есть два подпункта: <b>Тексты</b> и <b>Креативы</b>.
    Выберите: клиент готовит сам (тогда заполняем поля), или команда hh (тогда ставим согласие — обещаем 5 вариантов на выбор).
  </div>
</div>
""",
            unsafe_allow_html=True,
        )

        st.markdown("<div class='hr'></div>", unsafe_allow_html=True)

        def who_block(platform_key: str, platform_name: str):
            st.markdown(f"## {platform_name}")
            st.markdown("<div class='hr'></div>", unsafe_allow_html=True)

            # -------- ТЕКСТЫ
            st.markdown("### Тексты")
            who_text_key = f"who_text_{platform_key}"
            consent_text_key = f"consent_text_{platform_key}"

            who_text = st.radio(
                "Кто готовит тексты?",
                ["Клиент подготовит тексты", "Команда hh подготовит тексты"],
                index=1 if ss_get(who_text_key, "hh") == "hh" else 0,
                key=f"radio_text_{platform_key}",
            )
            st.session_state[who_text_key] = "hh" if who_text.startswith("Команда") else "client"

            if ss_get(who_text_key) == "hh":
                st.checkbox("Согласен(на), чтобы команда hh подготовила тексты (5 вариантов на выбор)", key=consent_text_key)
                st.caption("После оформления брифа предложим 5 вариантов (сгенерированных) на выбор.")
            else:
                # Поля под конкретную площадку
                if platform_key == "yandex":
                    st.text_input("Заголовок", key="yandex_headline", placeholder="До 56 символов")
                    remaining("headline", ss_get("yandex_headline", ""), LIMITS["yandex_headline"])
                    st.text_area("Текст", key="yandex_text", height=80, placeholder="До 81 символа")
                    remaining("text", ss_get("yandex_text", ""), LIMITS["yandex_text"])
                    st.markdown("Быстрые ссылки (опционально)")
                    fl = ss_get("yandex_fastlinks", ["", "", ""])
                    for i in range(3):
                        st.text_input(f"— ссылка {i+1}", key=f"yandex_fastlink_{i}", value=fl[i] if i < len(fl) else "")
                    st.session_state["yandex_fastlinks"] = [ss_get(f"yandex_fastlink_{i}", "") for i in range(3)]

                    st.markdown("Дополнительно (для оптимизации)")
                    st.text_input("Счетчик Яндекс.Метрики (ID)", key="yandex_metrika_id", placeholder="12345678")
                    st.text_area("Ключевые цели на странице", key="yandex_goals", height=80, placeholder="Напр.: view_vacancy, apply, employer_page...")

                elif platform_key == "vk":
                    st.text_area("Текст поста", key="vk_post_text", height=120, placeholder="1–2 ключевые выгоды + действие")
                    remaining("vk_post_text", ss_get("vk_post_text", ""), LIMITS["vk_post"])
                    c1, c2 = st.columns([1, 1])
                    with c1:
                        st.selectbox("CTA-кнопка (опц.)", ["Перейти", "Подробнее", "Откликнуться", "Смотреть вакансии", "Другое"], key="vk_cta")
                    with c2:
                        st.text_input("Если «Другое» — свой вариант", key="vk_cta_custom", placeholder="Напр.: Открыть")

                elif platform_key == "tgads":
                    st.text_area("Текст сообщения", key="tgads_message_text", height=100, placeholder="1–2 коротких предложения, CTA в конце")
                    remaining("tgads_message_text", ss_get("tgads_message_text", ""), LIMITS["tgads_text"])
                    st.selectbox("CTA", ["Подробнее", "Перейти", "Открыть"], key="tgads_cta")
                    st.caption("Подсказки: обращение на «вы», без CAPS LOCK и лишних эмодзи, без неподтвержденных обещаний.")

                else:  # tgseed
                    st.text_area("Ключевое сообщение / УТП (1–2 формулировки)", key="tgseed_key_message", height=70, placeholder="Коротко, это пойдет на креатив")
                    st.text_input("Текст на изображении (1 строка)", key="tgseed_image_text", placeholder="Короткий заголовок/УТП")
                    remaining("tgseed_image_text", ss_get("tgseed_image_text", ""), LIMITS["tg_seed_image_text"])
                    st.text_area("Текст поста (3–5 абзацев)", key="tgseed_post_text", height=140, placeholder="УТП + пояснение/доказательства + ссылка/CTA")
                    remaining("tgseed_post_text", ss_get("tgseed_post_text", ""), LIMITS["tg_seed_post"])

                    st.markdown("Смыслы поста (опционально)")
                    bullets = ss_get("tgseed_bullets", ["", "", "", "", ""])
                    for i in range(5):
                        st.text_input(f"— смысл {i+1}", key=f"tgseed_bullet_{i}", value=bullets[i] if i < len(bullets) else "")
                    st.session_state["tgseed_bullets"] = [ss_get(f"tgseed_bullet_{i}", "") for i in range(5)]

                    st.caption("Подсказка: пост 3–5 абзацев, главное — УТП + пояснение/доказательства + ссылка/CTA.")

            st.markdown("<div class='hr'></div>", unsafe_allow_html=True)

            # -------- КРЕАТИВЫ
            st.markdown("### Креативы")
            who_cre_key = f"who_creative_{platform_key}"
            consent_cre_key = f"consent_creative_{platform_key}"

            who_cre = st.radio(
                "Кто готовит креативы?",
                ["Клиент предоставит материалы", "Команда hh подготовит креативы"],
                index=1 if ss_get(who_cre_key, "hh") == "hh" else 0,
                key=f"radio_cre_{platform_key}",
            )
            st.session_state[who_cre_key] = "hh" if who_cre.startswith("Команда") else "client"

            if ss_get(who_cre_key) == "client":
                st.markdown(
                    """
- Требования к креативам: размеры/форматы/вес — подключим PDF (позже).  
- Сейчас: приложите ссылки на материалы/исходники/референсы.
""".strip()
                )
                st.text_area("Ссылки на материалы", key=f"{platform_key}_creative_links", height=80, placeholder="Drive/figma/папка/ссылки")
            else:
                st.checkbox("Согласен(на), чтобы команда hh подготовила креативы", key=consent_cre_key)
                st.radio(
                    "Опция",
                    ["Приложить референсы/исходники/креативы для ресайза", "Сгенерировать под мою задачу"],
                    key=f"{platform_key}_creative_option",
                )
                st.text_area(
                    "Если есть референсы/исходники — ссылки",
                    key=f"{platform_key}_creative_refs",
                    height=70,
                    placeholder="Ссылки (опционально)",
                )
                st.text_input(
                    "Если генерируем: что должно быть на креативе (1–2 строки)",
                    key=f"{platform_key}_creative_brief",
                    placeholder="Коротко: главный визуальный смысл/акцент/объект",
                )
                st.caption("Сноска: изображения будут сгенерированными (демо/эскизы).")

            st.markdown("<div class='hr'></div>", unsafe_allow_html=True)

        for key in selected:
            name = dict(PLATFORMS)[key]
            who_block(key, name)

        st.markdown("<div class='hr'></div>", unsafe_allow_html=True)

        c1, c2, c3 = st.columns([1, 1, 1])
        with c1:
            if st.button("← Назад", use_container_width=True):
                go_step(2)
        with c2:
            st.download_button(
                "📥 Скачать черновик заявки (txt)",
                data=make_brief_summary(),
                file_name=f"hh_segments_brief_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain",
                use_container_width=True,
            )
        with c3:
            if st.button("Далее →", type="primary", use_container_width=True):
                go_step(4)


# -------------------------
# STEP 4
# -------------------------
else:
    header_block("Экран 4. Демо-превью", "Покажем, как может выглядеть реклама + сгенерируем 5 вариантов.")

    selected = selected_platform_keys()
    if not selected:
        st.warning("Площадки не выбраны. Вернитесь на шаг 2.")
    else:
        st.markdown(
            """
<div class="card">
  <div class="card-title">Демо-пример</div>
  <div class="small-muted">
    Финальный вид зависит от модерации и конкретного формата. Здесь — быстрый мокап, чтобы согласовать направление.
  </div>
</div>
""",
            unsafe_allow_html=True,
        )

        st.markdown("<div class='hr'></div>", unsafe_allow_html=True)

        # Tabs по выбранным площадкам
        tab_names = [dict(PLATFORMS)[k] for k in selected]
        tabs = st.tabs(tab_names)

        def show_text_variants(platform_key: str):
            gen = ss_get("generated_texts", {}).get(platform_key)
            if gen:
                if gen.get("data") and isinstance(gen["data"], dict) and "variants" in gen["data"]:
                    variants = gen["data"]["variants"]
                    for i, v in enumerate(variants, start=1):
                        st.markdown(f"**Вариант {i}**")
                        st.json(v, expanded=False)
                else:
                    st.markdown(gen.get("raw", ""))
            else:
                st.info("Тексты ещё не генерировались.")

        def show_image(platform_key: str):
            img = ss_get("generated_images", {}).get(platform_key)
            if img:
                st.image(img, caption="Демо-мокап (пример)", use_column_width=True)
            else:
                st.info("Демо-картинка ещё не генерировалась.")

        def platform_demo_ui(platform_key: str):
            # быстрый “ввод клиента” как карточка
            st.markdown("### Тексты (как заполнено / или генерация)")
            who_text = ss_get(f"who_text_{platform_key}", "hh")
            if who_text == "client":
                st.markdown("<span class='badge'>Клиент готовит тексты</span>", unsafe_allow_html=True)

                if platform_key == "yandex":
                    st.markdown("**Заголовок:** " + (ss_get("yandex_headline") or "—"))
                    st.markdown("**Текст:** " + (ss_get("yandex_text") or "—"))
                    fl = [x for x in ss_get("yandex_fastlinks", []) if x.strip()]
                    st.markdown("**Быстрые ссылки:** " + (", ".join(fl) if fl else "—"))

                elif platform_key == "vk":
                    cta = ss_get("vk_cta", "Перейти")
                    if cta == "Другое" and ss_get("vk_cta_custom"):
                        cta = ss_get("vk_cta_custom")
                    st.markdown("**Пост:**")
                    st.write(ss_get("vk_post_text") or "—")
                    st.markdown("**CTA:** " + (cta or "—"))

                elif platform_key == "tgads":
                    st.write(ss_get("tgads_message_text") or "—")
                    st.caption("CTA: " + (ss_get("tgads_cta") or "—"))

                else:
                    st.markdown("**УТП:** " + (ss_get("tgseed_key_message") or "—"))
                    st.markdown("**Текст на изображении:** " + (ss_get("tgseed_image_text") or "—"))
                    st.markdown("**Пост:**")
                    st.write(ss_get("tgseed_post_text") or "—")

            else:
                st.markdown("<span class='badge'>Команда hh готовит тексты</span>", unsafe_allow_html=True)
                consent = ss_get(f"consent_text_{platform_key}", False)
                if not consent:
                    st.warning("Нужно согласие на подготовку текстов командой hh (шаг 3).")
                else:
                    if st.button("🤖 Сгенерировать 5 вариантов текстов", key=f"gen_texts_{platform_key}", type="primary", use_container_width=True):
                        try:
                            with st.spinner("Генерируем варианты..."):
                                res = generate_texts_for(platform_key)
                                st.session_state["generated_texts"][platform_key] = res
                                st.success("Готово.")
                                st.rerun()
                        except Exception as e:
                            st.error(str(e))

                    show_text_variants(platform_key)

            st.markdown("<div class='hr'></div>", unsafe_allow_html=True)

            st.markdown("### Демо-визуал (как может выглядеть)")
            who_cre = ss_get(f"who_creative_{platform_key}", "hh")
            if who_cre == "client":
                st.markdown("<span class='badge'>Клиент предоставляет материалы</span>", unsafe_allow_html=True)
                st.caption("Здесь можно показать только мокап-демо. Если нужны точные форматы — подключим PDF с требованиями.")
                # всё равно можно дать демо-картинку как ориентацию
                if st.button("🖼️ Сгенерировать демо-мокап", key=f"gen_img_{platform_key}", use_container_width=True):
                    try:
                        with st.spinner("Генерируем демо-картинку..."):
                            img = generate_image_for(platform_key)
                            st.session_state["generated_images"][platform_key] = img
                            st.success("Готово.")
                            st.rerun()
                    except Exception as e:
                        st.error(str(e))
                show_image(platform_key)
            else:
                st.markdown("<span class='badge'>Команда hh готовит креативы</span>", unsafe_allow_html=True)
                consent = ss_get(f"consent_creative_{platform_key}", False)
                if not consent:
                    st.warning("Нужно согласие на подготовку креативов командой hh (шаг 3).")
                else:
                    if st.button("🖼️ Сгенерировать демо-мокап", key=f"gen_img2_{platform_key}", type="primary", use_container_width=True):
                        try:
                            with st.spinner("Генерируем демо-картинку..."):
                                img = generate_image_for(platform_key)
                                st.session_state["generated_images"][platform_key] = img
                                st.success("Готово.")
                                st.rerun()
                        except Exception as e:
                            st.error(str(e))
                    show_image(platform_key)

            st.markdown("<div class='hr'></div>", unsafe_allow_html=True)

        for i, platform_key in enumerate(selected):
            with tabs[i]:
                platform_demo_ui(platform_key)

        st.markdown("<div class='hr'></div>", unsafe_allow_html=True)

        st.markdown(
            """
<div class="card">
  <div class="card-title">Финальный блок</div>
  <div class="small-muted">
    Если вам нравится направление — передаём в команду hh.
    В течение <b>2–3 рабочих дней</b> пришлём 5 вариантов на выбор для согласования.
  </div>
</div>
""",
            unsafe_allow_html=True,
        )

        c1, c2 = st.columns([1, 1])
        with c1:
            if st.button("← Назад", use_container_width=True):
                go_step(3)
        with c2:
            st.download_button(
                "📤 Скачать заявку и передать в команду hh (txt)",
                data=make_brief_summary(),
                file_name=f"hh_segments_brief_FINAL_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain",
                use_container_width=True,
            )
