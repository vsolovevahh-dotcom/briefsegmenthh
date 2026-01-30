# app.py (Streamlit form for hh Сегменты)

import streamlit as st

# ✅ Инициализация состояния при первом запуске
if "nav_page" not in st.session_state:
    st.session_state["nav_page"] = "Основная информация"

# Функция отображения стартового экрана
def step_0_start():
    st.title("Заполнение заявки на изготовление материалов для hh Сегментов")
    st.markdown("Заполнение брифа займет до 5 минут.")
    st.selectbox("Коротко про hh Сегменты", ["Коротко про hh Сегменты"], key="about_hh")
    st.text_input("Что рекламируем*", key="what_advertised")
    st.text_area("Описание сегмента*", help="Это аудитория, на которую будет показываться реклама", key="segment_description")

# Пример отображения следующего шага
def step_1_info():
    st.header("Основная информация")
    st.text_input("Посадочная ссылка", key="landing")
    st.text_input("Гео", key="geo")

# Навигация по шагам
pages = {
    "Старт": step_0_start,
    "Основная информация": step_1_info,
    # Добавить остальные шаги (Креативы и площадки, Тексты и креативы, Примерный вид объявлений)
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
