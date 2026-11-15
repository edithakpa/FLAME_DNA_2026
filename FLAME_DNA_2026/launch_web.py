import streamlit as st

st.set_page_config(
    page_title="FLAME DNA | FLAMENOVA TECH",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    #MainMenu, footer, header[data-testid="stHeader"] {
        display: none;
    }
    .block-container {
        padding: 0 !important;
        max-width: 100% !important;
    }
    [data-testid="stAppViewContainer"] {
        background: #101010;
    }
</style>
""", unsafe_allow_html=True)

st.iframe(
    "/app/static/index.html#/overview",
    width="stretch",
    height=950
)
