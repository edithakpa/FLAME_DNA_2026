"""FLAME DNA — two-part AI Assistant UI, without modifying other pages."""
import streamlit as st

from modules.nasa_ai_ml import render_nasa_ai
from modules.mission_agent import render_mission_agent


def render_flame_agent():
    research, safety = st.tabs([
        "NASA Research AI",
        "Astronaut Safety Agent (simulation)",
    ])
    with research:
        render_nasa_ai()
    with safety:
        render_mission_agent()
