
"""FLAME DNA — demonstrator of a mission safety conversational agent.

No API key or local LLM server required. It combines simulated safety
monitoring, explicit rules, an event log, and NASA-document retrieval
powered by the existing local ML module (TF-IDF + LSA).

IMPORTANT: Demonstration ONLY. No spacecraft connection or certification.
"""

from __future__ import annotations

from datetime import datetime, timezone
import math
import re
import time
import unicodedata

import streamlit as st
from modules.nasa_ai_ml import (
    DB_PATH,
    build_index,
    find_references,
    pick_excerpts,
    valid_source_url,
)


SIMULATED_SCENARIOS = {
    "Normal": {
        "thermal": 0.18,
        "smoke": 0.12,
        "oxygen_deviation": 0.16,
        "airflow_deviation": 0.20,
    },
    "Anomaly": {
        "thermal": 0.71,
        "smoke": 0.48,
        "oxygen_deviation": 0.64,
        "airflow_deviation": 0.36,
    },
    "Fire (simulated)": {
        "thermal": 0.96,
        "smoke": 0.91,
        "oxygen_deviation": 0.84,
        "airflow_deviation": 0.74,
    },
}

DISPLAY_NAMES = {
    "thermal": "Thermal index",
    "smoke": "Smoke index",
    "oxygen_deviation": "Oxygen deviation",
    "airflow_deviation": "Airflow deviation",
}

# Thresholds only apply to demonstration indices, not physical sensor units.
DEMO_WARNING = 0.60
DEMO_CRITICAL = 0.80


def _normalize(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value).casefold())
    return "".join(c for c in text if not unicodedata.combining(c))


def simulated_readings(scenario: str, tick: int | None = None) -> dict[str, float]:
    """Return predictable 0–1 demonstration signals; never real telemetry."""
    if scenario not in SIMULATED_SCENARIOS:
        scenario = "Normal"
    if tick is None:
        tick = int(time.time() // 3)
    baseline = SIMULATED_SCENARIOS[scenario]
    return {
        name: round(min(1.0, max(0.0, value + 0.012 * math.sin(tick * 0.65 + i))), 3)
        for i, (name, value) in enumerate(baseline.items())
    }


def assess_demo_risk(readings: dict[str, float]) -> dict:
    """Explainable rule-based demo classification, not a validated detector."""
    significant = [
        name for name, value in readings.items()
        if value >= DEMO_WARNING
    ]
    critical = [
        name for name, value in readings.items()
        if value >= DEMO_CRITICAL
    ]

    if len(critical) >= 2 or (
        readings.get("thermal", 0) >= DEMO_CRITICAL
        and readings.get("smoke", 0) >= DEMO_CRITICAL
    ):
        severity = "CRITICAL"
    elif significant:
        severity = "WARNING"
    else:
        severity = "NORMAL"

    triggers = [f"{DISPLAY_NAMES[n]}: {readings[n]:.2f}" for n in significant]
    return {
        "severity": severity,
        "triggers": triggers,
        "readings": readings,
    }


def _update_event_log(scenario: str, report: dict) -> None:
    """Record a state transition once per Streamlit session."""
    signature = (scenario, report["severity"])
    previous = st.session_state.get("mission_agent_signature")
    if signature == previous:
        return

    st.session_state["mission_agent_signature"] = signature
    events = st.session_state.setdefault("mission_agent_events", [])
    events.append({
        "time_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "scenario": scenario,
        "severity": report["severity"],
        "signals": ", ".join(report["triggers"]) or "No elevated indices",
    })
    st.session_state["mission_agent_events"] = events[-100:]

    if report["severity"] == "CRITICAL":
        st.toast("Critical simulated safety alert", icon="🚨")
    elif report["severity"] == "WARNING":
        st.toast("Simulated anomaly detected", icon="⚠️")


def _safety_text(report: dict, french: bool = False) -> str:
    severity = report["severity"]
    triggers = ", ".join(report["triggers"]) or "Aucun indice au-dessus du seuil"

    if french:
        if severity == "CRITICAL":
            return (
                "🚨 **ALERTE CRITIQUE — simulation uniquement.** Plusieurs indices "
                f"dépassent les seuils de démonstration : {triggers}.\n\n"
                "**À envisager :** informer le centre de contrôle et suivre les "
                "procédures d'urgence officielles de la mission. Ce prototype "
                "ne confirme aucun incendie réel et ne donne pas d'ordre opérationnel."
            )
        if severity == "WARNING":
            return (
                "⚠️ **ANOMALIE — simulation uniquement.** Indices élevés : "
                f"{triggers}.\n\n"
                "**À envisager :** vérifier les relevés et signaler l'anomalie "
                "selon les procédures de mission. Aucun incendie n'est confirmé."
            )
        return (
            "✅ **ÉTAT NORMAL — simulation.** Aucun seuil de démonstration n'est "
            "dépassé. Cela ne garantit pas la sécurité d'un véritable vaisseau."
        )

    if severity == "CRITICAL":
        return (
            "🚨 **CRITICAL — simulated alert only.** Multiple demonstration "
            f"signals crossed the configured limits: {triggers}.\n\n"
            "**Suggested next step:** notify mission control and follow "
            "approved, mission-specific emergency procedures. "
            "The demonstration cannot diagnose an actual fire or prescribe "
            "operational spacecraft actions."
        )
    if severity == "WARNING":
        return (
            "⚠️ **WARNING — simulated anomaly.** Elevated demonstration "
            f"signals: {triggers}.\n\n"
            "**Suggested next step:** review the readings and report the "
            "anomaly through the mission's approved process. "
            "This result is not a confirmed fire detection."
        )
    return (
        "✅ **NORMAL — demonstration signals within configured limits.** "
        "No anomaly is currently flagged by these demonstration rules. "
        "This does not prove that a real spacecraft is safe."
    )


@st.cache_resource(show_spinner=False)
def _cached_nasa_index(modified_ns: int):
    return build_index(DB_PATH)


def _nasa_answer(question: str) -> str:
    try:
        index = _cached_nasa_index(DB_PATH.stat().st_mtime_ns)
        matches = find_references(question, index, limit=3)
    except Exception as error:
        return ("NASA research catalog unavailable: "
                f"{type(error).__name__}. The monitoring demonstration can still be used.")

    if not matches:
        return (
            "I could not find sufficiently relevant scientific evidence "
            "in the NASA abstracts stored in this catalog. "
            "Try keywords such as SAFFIRE, microgravity, ignition or combustion."
        )

    lines = [
        "**NASA research excerpts (not a generative scientific conclusion):**"
    ]
    with_excerpts = 0
    for i, (publication, _) in enumerate(matches, 1):
        excerpts = pick_excerpts(question, publication.get("abstract"), index, max_sentences=2)
        if not excerpts:
            continue
        with_excerpts += 1
        lines.append(f"**[{i}] {publication.get('title') or 'Untitled'}**")
        lines.extend(f"> {passage}" for passage in excerpts)
        url = valid_source_url(publication.get("source_url"))
        if url:
            lines.append(f"[NASA source {i}]({url})")
    if not with_excerpts:
        lines.append("Matching records exist, but their abstracts contain no extractable answer.")
    lines.append(
        "*These excerpts are from the indexed abstracts, not full NASA papers; "
        "they do not validate the simulated safety alerts.*"
    )
    return "\n\n".join(lines)


def respond_to_astronaut(question: str, report: dict) -> str:
    """Rule-based intent routing + local ML scientific search."""
    q = _normalize(question)
    french = bool(re.search(
        r"\b(bonjour|salut|quel|quelle|comment|pourquoi|dois|faire|fumee|"
        r"alerte|incendie|securite|probleme|risque|astronaute|peux|aide)\b", q
    ))

    if re.search(r"\b(bonjour|salut|hello|hi|help|aide)\b", q):
        return (
            "Bonjour ! Je peux signaler l'état des capteurs simulés, expliquer "
            "les alertes et rechercher les publications NASA. Demande-moi "
            "« Quel est le niveau d'alerte ? » ou pose une question scientifique."
            if french else
            "Hello! I can report simulated sensor status, explain alerts, "
            "and retrieve NASA research. Ask 'What is the alert level?' "
            "or a scientific question."
        )
    if re.search(
        r"\b(status|situation|etat|alert|alerte|warning|danger|risk|risque|"
        r"smoke|fumee|incendie|emergency|urgence|safe|securite|sensor|capteur|"
        r"surveillance|problem|probleme|feu)\b", q
    ):
        return _safety_text(report, french=french)
    if re.search(
        r"\b(procedure|protocol|protocole|dois.je|what should|que faire|"
        r"action|conduite|evacuate|evacuer)\b", q
    ):
        return _safety_text(report, french=french)
    return _nasa_answer(question)


def _send_message(question: str) -> None:
    question = question.strip()
    if not question:
        return
    report = st.session_state.get("mission_agent_current_report")
    if report is None:
        report = assess_demo_risk(simulated_readings("Normal"))
    history = st.session_state.setdefault("mission_agent_chat", [])
    history.append({"role": "user", "content": question})
    history.append({"role": "assistant", "content": respond_to_astronaut(question, report)})
    st.session_state["mission_agent_chat"] = history[-30:]


@st.fragment(run_every="3s")
def _live_demo(scenario: str) -> None:
    reading = simulated_readings(scenario)
    report = assess_demo_risk(reading)
    st.session_state["mission_agent_current_report"] = report
    _update_event_log(scenario, report)

    status = report["severity"]
    if status == "CRITICAL":
        st.error(_safety_text(report))
    elif status == "WARNING":
        st.warning(_safety_text(report))
    else:
        st.success(_safety_text(report))

    cols = st.columns(4)
    for column, (name, value) in zip(cols, reading.items()):
        column.metric(DISPLAY_NAMES[name], f"{value:.2f}")
    st.caption(
        "All four signals are synthetic indices from 0 to 1; thresholds "
        "are demo-only. Updated approximately every 3 seconds while the "
        "Streamlit session is active. No connection to spacecraft sensors."
    )


def render_mission_agent() -> None:
    st.subheader("FLAME DNA — Astronaut Safety Agent")
    st.caption(
        "Interactive mission-safety demonstration · Local ML document search "
        "+ explainable rule-based alerts · No external AI service"
    )
    st.info(
        "**Demonstration only.** No real spacecraft telemetry, no certified "
        "fire detection, and no autonomous control. Alerts appear inside this "
        "open Streamlit session; they are not 24/7 push notifications."
    )

    scenario = st.selectbox(
        "Mission scenario (simulated)",
        list(SIMULATED_SCENARIOS),
        key="mission_agent_scenario",
    )

    # Transmettre le scénario au système d'alertes
    st.session_state["flame_alert_scenario"] = scenario

    _live_demo(scenario)

    with st.expander("Mission event history"):
        events = st.session_state.get("mission_agent_events", [])
        if events:
            st.dataframe(list(reversed(events)), hide_index=True, width="stretch")
        else:
            st.write("No events yet.")

    st.markdown("### Talk to the safety agent")
    st.caption(
        "Examples: 'Is there a fire risk?', 'Quel est le niveau d'alerte ?', "
        "or 'What does NASA say about flames in microgravity?'"
    )

    st.session_state.setdefault("mission_agent_chat", [])
    if st.button("Clear conversation", key="mission_agent_clear"):
        st.session_state["mission_agent_chat"] = []

    for entry in st.session_state["mission_agent_chat"]:
        with st.chat_message(entry["role"]):
            st.markdown(entry["content"])

    question = st.chat_input("Ask the mission agent / Parlez à l'agent", key="mission_agent_input")
    if question:
        _send_message(question)
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            st.markdown(st.session_state["mission_agent_chat"][-1]["content"])
