# app.py (Streamlit form for hh Сегменты)

import streamlit as st

# ✅ Инициализация состояния при первом запуске
if "nav_page" not in st.session_state:
    st.session_state["nav_page"] = "Старт"

# Функция отображения стартового экрана

def step_0_start():
    st.title("Заполнение заявки на изготовление материалов для hh Сегментов")
    st.markdown("Заполнение брифа займет до 5 минут.")
    st.selectbox("Коротко про hh Сегменты", ["Коротко про hh Сегменты"], key="about_hh")
    st.text_input("Что рекламируем*", key="what_advertised")
    st.text_area("Описание сегмента*", help="Это аудитория, на которую будет показываться реклама", key="segment_description")

# Экран 1 — Основная информация

def step_1_info():
    st.header("Основная информация")
    st.text_input("Посадочная ссылка", key="landing")
    st.text_input("Гео", key="geo")

# Экран 2 — Креативы и площадки

def step_2_formats():
    st.header("Креативы и площадки")
    st.markdown("Выберите рекламные площадки и форматы креативов")
    st.checkbox("Яндекс: изображение", key="yandex_img")
    st.checkbox("Яндекс: видео", key="yandex_video")
    st.checkbox("ВК: изображение", key="vk_img")
    st.checkbox("ВК: видео", key="vk_video")
    st.checkbox("ТГ Ads: текст", key="tg_text")
    st.checkbox("ТГ Ads: изображение", key="tg_img")
    st.checkbox("ТГ Ads: видео", key="tg_video")

# Экран 3 — Тексты и креативы

def step_3_creatives():
    st.header("Тексты и креативы")
    st.markdown("Заполните тексты/креативы по выбранным площадкам и форматам. Данные сохраняются автоматически.")
    if not any([st.session_state.get("yandex_img"), st.session_state.get("yandex_video"), st.session_state.get("vk_img"), st.session_state.get("vk_video"), st.session_state.get("tg_text"), st.session_state.get("tg_img"), st.session_state.get("tg_video")]):
        st.warning("Сначала выберите площадки на шаге 2.")
        return
    if st.session_state.get("yandex_img"):
        st.subheader("Яндекс: изображение")
        st.text_input("Заголовок", key="yandex_img_title")
        st.text_area("Текст", key="yandex_img_text")
    if st.session_state.get("tg_text"):
        st.subheader("ТГ Ads: текст")
        st.text_input("Заголовок", key="tg_text_title")
        st.text_area("Текст", key="tg_text_text")

# Экран 4 — Примерный вид объявлений

def step_4_preview():
    st.header("Примерный вид рекламных объявлений")
    st.markdown("Покажем, как может выглядеть реклама")
    if st.session_state.get("yandex_img"):
        st.markdown("**Яндекс: изображение** — Заголовок: " + st.session_state.get("yandex_img_title", "") + ", Текст: " + st.session_state.get("yandex_img_text", ""))
    if st.session_state.get("tg_text"):
        st.markdown("**ТГ Ads: текст** — Заголовок: " + st.session_state.get("tg_text_title", "") + ", Текст: " + st.session_state.get("tg_text_text", ""))

# Навигация по шагам
pages = {
    "Старт": step_0_start,
    "Основная информация": step_1_info,
    "Креативы и площадки": step_2_formats,
    "Тексты и креативы": step_3_creatives,
    "Примерный вид объявлений": step_4_preview
}

# Сайдбар
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/8/87/Hh.ru_logo.svg/320px-Hh.ru_logo.svg.png", width=120)
    st.title("hh Сегменты — заявка")
    st.caption("Форма → заявка → демо превью")
    st.markdown("---")
    st.radio("Навигация", list(pages.keys()), key="nav_page_ui")
    st.button("🔁 Перейти", on_click=lambda: st.session_state.update({"nav_page": st.session_state.nav_page_ui}))
    st.markdown("---")
    st.button("🔄 Сбросить форму", on_click=lambda: st.session_state.clear())

# Основной рендер страницы
selected_page = st.session_state.get("nav_page", "Старт")
pages[selected_page]()
