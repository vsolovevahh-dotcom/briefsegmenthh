import streamlit as st
import requests
import json
from datetime import datetime

# Конфигурация страницы
st.set_page_config(
    page_title="Генератор рекламных текстов",
    page_icon="🎯",
    layout="wide"
)

# Стили
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.2rem;
        text-align: center;
        color: #666;
        margin-bottom: 2rem;
    }
    .result-box {
        background-color: #f0f2f6;
        padding: 1.5rem;
        border-radius: 10px;
        margin: 1rem 0;
        border-left: 5px solid #1f77b4;
    }
    .variant-title {
        font-weight: bold;
        color: #1f77b4;
        font-size: 1.1rem;
        margin-bottom: 0.5rem;
    }
    .char-counter {
        font-size: 0.85rem;
        color: #888;
        font-style: italic;
    }
    </style>
""", unsafe_allow_html=True)

# Заголовок приложения
st.markdown('<div class="main-header">🎯 Генератор рекламных текстов</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Создание эффективных рекламных текстов для Яндекс.Директ (РСЯ) с помощью AI</div>', unsafe_allow_html=True)

# Инструкция
with st.expander("📖 Инструкция по использованию"):
    st.markdown("""
    ### Как пользоваться сервисом:
    
    1. **Загрузите контекст** - вставьте текст с вашей посадочной страницы в поле "Контекст"
    2. **Выберите модуль** - переключайтесь между вкладками в зависимости от типа рекламы
    3. **Заполните поля** - внесите необходимую информацию (используйте подсказки)
    4. **Сгенерируйте варианты** - нажмите кнопку генерации
    5. **Скачайте результаты** - сохраните понравившиеся варианты
    
    💡 **Совет:** Чем подробнее вы заполните поля, тем точнее будут сгенерированные тексты!
    """)

# Функция для вызова API OpenRouter
def generate_texts(system_prompt, user_context, module_data):
    """
    Генерация текстов через OpenRouter API
    """
    try:
        api_key = st.secrets["OPENROUTER_API_KEY"]
        
        # Формирование полного промпта
        full_prompt = f"""{system_prompt}

КОНТЕКСТ ПОСАДОЧНОЙ СТРАНИЦЫ:
{user_context if user_context else "Контекст не предоставлен"}

ДАННЫЕ КЛИЕНТА:
{module_data}

Создай ровно 5 вариантов рекламных текстов."""

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://streamlit.io",
            "X-Title": "Ad Text Generator"
        }
        
        payload = {
            "model": "google/gemini-2.0-flash-exp:free",
            "messages": [
                {
                    "role": "user",
                    "content": full_prompt
                }
            ],
            "temperature": 0.7,
            "max_tokens": 4000,
            "tools": [],
            "tool_choice": "none"
        }
        
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            return result['choices'][0]['message']['content']
        else:
            return f"Ошибка API: {response.status_code} - {response.text}"
            
    except Exception as e:
        return f"Ошибка при генерации: {str(e)}"

# Функция для создания файла с результатами
def create_download_file(results, module_name):
    """
    Создание текстового файла для скачивания
    """
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    content = f"""СГЕНЕРИРОВАННЫЕ РЕКЛАМНЫЕ ТЕКСТЫ
Модуль: {module_name}
Дата: {timestamp}

{'='*80}

{results}

{'='*80}

Сгенерировано с помощью AI-сервиса генерации рекламных текстов
"""
    return content

# Общий блок: Контекст посадочной страницы
st.markdown("---")
st.markdown("### 📄 Контекст посадочной страницы")
st.markdown("*Вставьте текст с вашей посадочной страницы. Этот контекст будет учитываться при генерации всех текстов.*")

context = st.text_area(
    "Контекст",
    height=150,
    placeholder="Вставьте описание посадочной страницы, ключевые преимущества, УТП и другую важную информацию...",
    label_visibility="collapsed"
)

st.markdown("---")

# Создание вкладок для модулей
tab1, tab2, tab3, tab4 = st.tabs([
    "📋 Общие данные",
    "💬 TG Ads (текст)",
    "🎨 TG Ads (медиа)",
    "📢 TG (посевы)"
])

# ============================================================================
# МОДУЛЬ 1: Общие данные (Яндекс, ВК, TG)
# ============================================================================
with tab1:
    st.markdown("## 📋 Общие данные (Яндекс, ВК, TG)")
    
    with st.expander("💡 Справочная информация"):
        st.markdown("""
        **Подсказки по заполнению:**
        
        - **Что рекламируем:** Кратко опишите продукт/услугу/кампанию (1-2 предложения)
        - **Цель кампании:** Например: трафик, лиды/заявки, отклики, узнаваемость
        - **Посадочная ссылка:** URL страницы (можно несколько с приоритетом)
        - **Гео:** Города или регионы таргетинга
        - **ЦА:** Опишите 1-3 сегмента целевой аудитории
        - **Оффер:** Ключевые выгоды, цифры, преимущества (3-5 пунктов)
        - **Ограничения:** Запрещенные слова/темы/образы + обязательные формулировки
        - **Файлы/материалы:** Ссылки на логотип, брендбук, референсы
        - **Апрув:** Кто утверждает и в какие сроки
        """)
    
    col1, col2 = st.columns(2)
    
    with col1:
        m1_product = st.text_input(
            "Что рекламируем (1-2 предложения)",
            key="m1_product",
            placeholder="Например: Онлайн-курс по Python для начинающих"
        )
        
        m1_goal = st.text_input(
            "Цель кампании",
            key="m1_goal",
            placeholder="Например: Получение заявок на бесплатный урок"
        )
        
        m1_url = st.text_input(
            "Посадочная ссылка",
            key="m1_url",
            placeholder="https://example.com/landing"
        )
        
        m1_geo = st.text_input(
            "Гео",
            key="m1_geo",
            placeholder="Москва, Санкт-Петербург, Россия"
        )
        
        m1_target = st.text_area(
            "ЦА (1-3 сегмента)",
            key="m1_target",
            height=100,
            placeholder="Например: Начинающие программисты 20-35 лет, желающие сменить профессию"
        )
    
    with col2:
        m1_offer = st.text_area(
            "Оффер / ключевые тезисы (3-5 пунктов)",
            key="m1_offer",
            height=120,
            placeholder="- Обучение с нуля за 3 месяца\n- Гарантия трудоустройства\n- Первый урок бесплатно"
        )
        
        m1_restrictions = st.text_area(
            "Ограничения / дисклеймеры",
            key="m1_restrictions",
            height=100,
            placeholder="Что нельзя использовать и что обязательно указать"
        )
        
        m1_files = st.text_input(
            "Файлы/материалы (ссылки)",
            key="m1_files",
            placeholder="https://drive.google.com/..."
        )
        
        m1_approval = st.text_input(
            "Апрув",
            key="m1_approval",
            placeholder="Иванов И.И., срок ответа: 2 рабочих дня"
        )
    
    st.markdown("---")
    
    if st.button("🎨 Сгенерировать варианты текстов", key="gen_m1", type="primary", use_container_width=True):
        if not m1_product:
            st.error("⚠️ Пожалуйста, заполните хотя бы поле 'Что рекламируем'")
        else:
            with st.spinner("🤖 Генерируем варианты текстов..."):
                # Формирование данных модуля
                module_data = f"""
Что рекламируем: {m1_product}
Цель кампании: {m1_goal}
Посадочная ссылка: {m1_url}
Гео: {m1_geo}
ЦА: {m1_target}
Оффер/тезисы: {m1_offer}
Ограничения: {m1_restrictions}
Файлы: {m1_files}
Апрув: {m1_approval}
"""
                
                system_prompt = """Ты — эксперт по созданию рекламных текстов для Яндекс.Директ (РСЯ).

ЗАДАЧА:
Создай ровно 5 вариантов рекламных текстов, которые:
- Информативны и точно отражают суть предложения
- Кликабельны и вызывают желание перейти
- Приятны к прочтению, без спама и агрессии
- Соответствуют требованиям Яндекс.Директ (РСЯ)
- Учитывают все ограничения и обязательные элементы

ФОРМАТ ОТВЕТА для каждого варианта:

**Вариант [номер]**

**Заголовок:** [текст до 56 символов]
**Текст объявления:** [текст до 81 символа]
**Обоснование:** [краткое пояснение выбора формулировки]

---

ВАЖНО: 
- НЕ используй поиск в интернете, работай только с предоставленным контекстом
- Строго соблюдай лимиты символов
- Каждый вариант должен быть уникальным"""
                
                result = generate_texts(system_prompt, context, module_data)
                
                st.markdown("### ✨ Сгенерированные варианты:")
                st.markdown(f'<div class="result-box">{result}</div>', unsafe_allow_html=True)
                
                # Кнопка скачивания
                download_content = create_download_file(result, "Общие данные")
                st.download_button(
                    label="📥 Скачать все варианты",
                    data=download_content,
                    file_name=f"ad_texts_general_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                    mime="text/plain",
                    use_container_width=True
                )

# ============================================================================
# МОДУЛЬ 2: TG Ads (текст)
# ============================================================================
with tab2:
    st.markdown("## 💬 TG Ads (текст)")
    
    with st.expander("💡 Справочная информация"):
        st.markdown("""
        **Подсказки по заполнению:**
        
        - **Что обязательно упомянуть:** Ключевые элементы (продукт/выгода/условие/гео)
        - **CTA:** Выберите призыв к действию или укажите свой вариант
        - **Стоп-слова:** Запрещенные формулировки и обязательные элементы
        """)
    
    m2_must_mention = st.text_area(
        "Что обязательно упомянуть в тексте (1-2 пункта)",
        key="m2_must_mention",
        height=100,
        placeholder="Например: Скидка 30%, доставка по Москве за 2 часа"
    )
    
    st.markdown("**CTA (призыв к действию)**")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        cta_1 = st.checkbox("Перейти", key="cta_1")
    with col2:
        cta_2 = st.checkbox("Узнать больше", key="cta_2")
    with col3:
        cta_3 = st.checkbox("Оставить заявку", key="cta_3")
    with col4:
        cta_custom = st.text_input("Другое:", key="cta_custom", placeholder="Ваш вариант")
    
    m2_stop_words = st.text_area(
        "Стоп-слова / запреты / обязательные формулировки",
        key="m2_stop_words",
        height=100,
        placeholder="Если нет — оставьте пустым"
    )
    
    st.markdown("---")
    
    if st.button("🎨 Сгенерировать варианты текстов", key="gen_m2", type="primary", use_container_width=True):
        if not m2_must_mention:
            st.error("⚠️ Пожалуйста, заполните поле 'Что обязательно упомянуть'")
        else:
            with st.spinner("🤖 Генерируем варианты текстов..."):
                # Формирование CTA
                cta_list = []
                if cta_1: cta_list.append("Перейти")
                if cta_2: cta_list.append("Узнать больше")
                if cta_3: cta_list.append("Оставить заявку")
                if cta_custom: cta_list.append(cta_custom)
                cta_text = ", ".join(cta_list) if cta_list else "Не указано"
                
                module_data = f"""
Что обязательно упомянуть: {m2_must_mention}
CTA (предпочтения): {cta_text}
Стоп-слова/запреты: {m2_stop_words}
"""
                
                system_prompt = """Ты — эксперт по созданию рекламных текстов для Telegram Ads.

ЗАДАЧА:
Создай ровно 5 вариантов текстов для рекламы в Telegram, которые:
- Естественно вписываются в ленту пользователя
- Содержат все обязательные элементы
- Имеют четкий и привлекательный CTA
- Соответствуют стилю общения в Telegram (дружелюбно, без агрессии)
- Учитывают все ограничения

ФОРМАТ ОТВЕТА для каждого варианта:

**Вариант [номер]**

**Текст объявления:** [текст 150-200 символов]
**CTA:** [призыв к действию]
**Обоснование:** [почему этот вариант эффективен]

---

ВАЖНО: 
- НЕ используй поиск в интернете
- Текст должен быть живым и человечным
- Избегай шаблонных фраз"""
                
                result = generate_texts(system_prompt, context, module_data)
                
                st.markdown("### ✨ Сгенерированные варианты:")
                st.markdown(f'<div class="result-box">{result}</div>', unsafe_allow_html=True)
                
                download_content = create_download_file(result, "TG Ads (текст)")
                st.download_button(
                    label="📥 Скачать все варианты",
                    data=download_content,
                    file_name=f"ad_texts_tg_text_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                    mime="text/plain",
                    use_container_width=True
                )

# ============================================================================
# МОДУЛЬ 3: TG Ads (медиа)
# ============================================================================
with tab3:
    st.markdown("## 🎨 TG Ads (медиа)")
    
    with st.expander("💡 Справочная информация"):
        st.markdown("""
        **Подсказки по заполнению:**
        
        - **Что нужно:** Выберите тип креатива (изображение и/или видео)
        - **Ключевое сообщение:** Главная мысль, которая должна быть на креативе
        - **Материалы бренда:** Ссылки на логотип, брендбук, исходники
        - **Визуальные предпочтения:** Стиль, цвета, наличие людей, референсы
        - **Ограничения:** Юридические требования, обязательные тексты
        """)
    
    st.markdown("**Что нужно создать:**")
    col1, col2 = st.columns(2)
    with col1:
        m3_image = st.checkbox("Premium Image", key="m3_image")
    with col2:
        m3_video = st.checkbox("Premium Video", key="m3_video")
    
    m3_message = st.text_area(
        "Ключевое сообщение / УТП (1-2 формулировки)",
        key="m3_message",
        height=100,
        placeholder="Например: Быстрая доставка за 2 часа. Скидка 30% на первый заказ"
    )
    
    m3_brand = st.text_input(
        "Материалы бренда (ссылки)",
        key="m3_brand",
        placeholder="Ссылки на логотип, брендбук, гайд, исходники"
    )
    
    m3_visual = st.text_area(
        "Визуальные предпочтения + референсы",
        key="m3_visual",
        height=100,
        placeholder="Стиль, наличие людей, фон/цвета, ссылки на референсы"
    )
    
    m3_legal = st.text_area(
        "Ограничения / дисклеймеры / юридические требования",
        key="m3_legal",
        height=100,
        placeholder="Обязательные тексты, условия, ограничения"
    )
    
    st.markdown("---")
    
    if st.button("🎨 Сгенерировать варианты текстов", key="gen_m3", type="primary", use_container_width=True):
        if not m3_message:
            st.error("⚠️ Пожалуйста, заполните поле 'Ключевое сообщение'")
        else:
            with st.spinner("🤖 Генерируем варианты текстов..."):
                media_types = []
                if m3_image: media_types.append("Premium Image")
                if m3_video: media_types.append("Premium Video")
                media_text = ", ".join(media_types) if media_types else "Не указано"
                
                module_data = f"""
Тип креатива: {media_text}
Ключевое сообщение/УТП: {m3_message}
Материалы бренда: {m3_brand}
Визуальные предпочтения: {m3_visual}
Ограничения/дисклеймеры: {m3_legal}
"""
                
                system_prompt = """Ты — эксперт по созданию концепций визуальной рекламы для Telegram Ads.

ЗАДАЧА:
Создай ровно 5 вариантов концепций медиа-креативов для Telegram, которые:
- Визуально привлекательны и останавливают скролл
- Четко передают ключевое сообщение
- Соответствуют брендбуку (если предоставлен)
- Учитывают визуальные предпочтения
- Соблюдают все юридические требования

ФОРМАТ ОТВЕТА для каждого варианта:

**Вариант [номер]**

**Описание визуала:** [что изображено на креативе, композиция, цвета]
**Текст на креативе:** [заголовок/УТП, до 10 слов]
**Сопроводительный текст:** [текст под креативом, 100-150 символов]
**Обоснование:** [почему эта концепция сработает]

---

ВАЖНО: 
- НЕ используй поиск в интернете
- Описывай визуал детально, чтобы дизайнер мог воплотить
- Текст на креативе должен быть крупным и читаемым"""
                
                result = generate_texts(system_prompt, context, module_data)
                
                st.markdown("### ✨ Сгенерированные варианты:")
                st.markdown(f'<div class="result-box">{result}</div>', unsafe_allow_html=True)
                
                download_content = create_download_file(result, "TG Ads (медиа)")
                st.download_button(
                    label="📥 Скачать все варианты",
                    data=download_content,
                    file_name=f"ad_texts_tg_media_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                    mime="text/plain",
                    use_container_width=True
                )

# ============================================================================
# МОДУЛЬ 4: TG (посевы)
# ============================================================================
with tab4:
    st.markdown("## 📢 TG (посевы)")
    
    with st.expander("💡 Справочная информация"):
        st.markdown("""
        **Подсказки по заполнению:**
        
        - **Текст на изображении:** Короткий заголовок/УТП (одна строка, без мелкого текста)
        - **Текст поста:** Укажите обязательные смыслы, ограничения, дисклеймеры
        - **Дополнительно:** Референсы, гайды, исходники (если нужно)
        """)
    
    m4_image_text = st.text_input(
        "Текст на изображении (УТП/заголовок — 1 строка)",
        key="m4_image_text",
        placeholder="Например: Скидка 50% на все курсы"
    )
    
    m4_post_text = st.text_area(
        "Текст поста (обязательные смыслы/ограничения)",
        key="m4_post_text",
        height=120,
        placeholder="Укажите, что обязательно должно быть в тексте поста, какие ограничения и дисклеймеры учесть"
    )
    
    m4_additional = st.text_area(
        "Дополнительно",
        key="m4_additional",
        height=100,
        placeholder="Референсы, гайды, исходники (ссылки)"
    )
    
    st.markdown("---")
    
    if st.button("🎨 Сгенерировать варианты текстов", key="gen_m4", type="primary", use_container_width=True):
        if not m4_image_text:
            st.error("⚠️ Пожалуйста, заполните поле 'Текст на изображении'")
        else:
            with st.spinner("🤖 Генерируем варианты текстов..."):
                module_data = f"""
Текст на изображении: {m4_image_text}
Требования к тексту поста: {m4_post_text}
Дополнительные материалы: {m4_additional}
"""
                
                system_prompt = """Ты — эксперт по созданию нативных рекламных постов для посевов в Telegram-каналах.

ЗАДАЧА:
Создай ровно 5 вариантов постов для посевов в Telegram, которые:
- Выглядят органично в ленте канала
- Не вызывают отторжения как реклама
- Содержат все обязательные элементы
- Мотивируют к действию естественным образом
- Соответствуют стилю общения в Telegram

ФОРМАТ ОТВЕТА для каждого варианта:

**Вариант [номер]**

**Текст на изображении:** [короткий заголовок]
**Текст поста:** [основной текст, 200-400 символов, с эмодзи]
**Обоснование:** [почему этот подход сработает для посева]

---

ВАЖНО: 
- НЕ используй поиск в интернете
- Пост должен быть нативным, не выглядеть как реклама
- Используй сторителлинг, где уместно
- Добавляй эмодзи для живости текста"""
                
                result = generate_texts(system_prompt, context, module_data)
                
                st.markdown("### ✨ Сгенерированные варианты:")
                st.markdown(f'<div class="result-box">{result}</div>', unsafe_allow_html=True)
                
                download_content = create_download_file(result, "TG (посевы)")
                st.download_button(
                    label="📥 Скачать все варианты",
                    data=download_content,
                    file_name=f"ad_texts_tg_seeding_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                    mime="text/plain",
                    use_container_width=True
                )

# Футер
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 2rem 0;'>
    <p>🤖 Powered by AI | Создано для эффективной рекламы</p>
    <p style='font-size: 0.85rem;'>Версия 1.0 | 2024</p>
</div>
""", unsafe_allow_html=True)
