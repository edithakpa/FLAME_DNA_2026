"""FLAME DNA — repeated in-app safety notifications (demonstration).

Place in modules/flame_alert_center.py and call render_alert_center() once
in app.py after the sidebar page selector, before the page-specific branches.

Uses the existing synthetic Astronaut Safety Agent signals. No real spacecraft
telemetry, push notification, phone alert or validated fire detection.
"""

from __future__ import annotations

from datetime import datetime, timezone
import time

import streamlit as st

from modules.mission_agent import (
    SIMULATED_SCENARIOS,
    simulated_readings,
    assess_demo_risk,
)

# How often the app checks the simulated signals, and notification cooldowns.
CHECK_PERIOD = "3s"
REPEAT_SECONDS = {"CRITICAL": 12, "WARNING": 25}
MAX_HISTORY = 150


def _record_event(source: str, severity: str, event: str, message: str) -> None:
    history = st.session_state.setdefault("flame_alert_history", [])
    history.append({
        "Date (UTC)": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "Source": source,
        "Niveau": severity,
        "Événement": event,
        "Message": message,
    })
    st.session_state["flame_alert_history"] = history[-MAX_HISTORY:]


def publish_monitoring_alert(
    severity: str,
    message: str,
    source: str = "Real-Time Monitoring",
    incident_id: str = "monitoring",
) -> None:
    """Optional integration point for Real-Time Monitoring.

    Call on EACH sensor update, including severity='NORMAL' once resolved.
    Accepted severities: NORMAL, WARNING, CRITICAL.
    External data is used while updated within the last 10 seconds.
    """
    level = str(severity).upper().strip()
    if level not in {"NORMAL", "WARNING", "CRITICAL"}:
        raise ValueError("severity must be NORMAL, WARNING or CRITICAL")

    st.session_state["flame_external_alert"] = {
        "severity": level,
        "message": str(message).strip() or "Surveillance en cours.",
        "source": str(source),
        "incident_id": str(incident_id),
        "updated_at": time.monotonic(),
    }


def _snapshot(now: float) -> dict[str, str]:
    """Prioritize a recently published monitoring status, else use demo."""
    external = st.session_state.get("flame_external_alert")
    if external:
        age = now - external["updated_at"]
        if age <= 10:
            return dict(external)
        # A stopped feed must never be interpreted as a return to NORMAL.
        last_level = external["severity"]
        severity = "CRITICAL" if last_level == "CRITICAL" else "WARNING"
        return {
            "severity": severity,
            "message": (
                "Le flux de monitoring n'a pas été actualisé depuis "
                f"{int(age)} s (page inactive ou acquisition arrêtée). "
                "L'état réel est inconnu ; le dernier état connu était "
                f"{last_level}."
            ),
            "source": f"{external['source']} — données non actualisées",
            "incident_id": f"stale:{external['incident_id']}",
        }

    scenario = st.session_state.get(
        "flame_alert_scenario",
        st.session_state.get("mission_agent_scenario", "Normal"),
    )
    if scenario not in SIMULATED_SCENARIOS:
        scenario = "Normal"

    report = assess_demo_risk(simulated_readings(scenario))
    signals = ", ".join(report["triggers"])
    severity = report["severity"]
    if severity == "CRITICAL":
        message = f"Incendie possible (SIMULATION) — indices élevés : {signals}."
    elif severity == "WARNING":
        message = f"Anomalie simulée — indices élevés : {signals}."
    else:
        message = "Aucun dépassement des seuils de démonstration."

    return {
        "severity": severity,
        "message": message,
        "source": f"Astronaut Safety Agent — {scenario}",
        "incident_id": f"demo:{scenario}",
    }


@st.fragment(run_every=CHECK_PERIOD)
def render_alert_center() -> None:
    """Always-on (while session is active) alert bar for all 7 pages."""
    now = time.monotonic()
    status = _snapshot(now)
    severity = status["severity"]
    source = status["source"]
    message = status["message"]

    # Detect status changes; don't log the same transition every 3 seconds.
    signature = (source, status["incident_id"], severity)
    previous = st.session_state.get("flame_alert_signature")
    if signature != previous:
        st.session_state["flame_alert_signature"] = signature
        st.session_state["flame_alert_last_toast"] = -1e30
        # A new event reactivates its notifications.
        st.session_state["flame_alert_muted_until"] = 0.0
        _record_event(source, severity, "Changement d'état", message)
        if previous is not None and severity == "NORMAL":
            st.toast("✅ FLAME DNA : retour à l'état normal (simulation).", icon="✅")

    if severity == "NORMAL":
        st.caption("🔔 FLAME DNA Alert Center · Surveillance de démonstration active · État : NORMAL")
    else:
        if severity == "CRITICAL":
            st.error(f"🚨 **ALERTE CRITIQUE — {source}**\n\n{message}")
        else:
            st.warning(f"⚠️ **AVERTISSEMENT — {source}**\n\n{message}")

        st.caption(
            "Démonstration uniquement : aucune détection d'incendie réel. "
            "Consulter les procédures approuvées et le centre de contrôle en situation réelle."
        )

        muted_until = st.session_state.get("flame_alert_muted_until", 0.0)
        left, right = st.columns([1, 3])
        with left:
            if now < muted_until:
                if st.button("🔔 Réactiver", key="flame_alert_unmute"):
                    st.session_state["flame_alert_muted_until"] = 0.0
                    st.session_state["flame_alert_last_toast"] = -1e30
            else:
                if st.button("🔕 Silence 60 s", key="flame_alert_mute"):
                    st.session_state["flame_alert_muted_until"] = now + 60
                    muted_until = now + 60
        with right:
            if now < muted_until:
                st.caption("Rappels suspendus temporairement. Le bandeau d'alerte reste visible.")
            else:
                st.caption(
                    "Rappel toutes les 12 s en CRITICAL, "
                    "toutes les 25 s en WARNING."
                )

        interval = REPEAT_SECONDS[severity]
        last_toast = st.session_state.get("flame_alert_last_toast", -1e30)
        if now >= muted_until and (now - last_toast) >= interval:
            title = "🚨 INCENDIE POSSIBLE — SIMULATION" if severity == "CRITICAL" else "⚠️ ANOMALIE — SIMULATION"
            st.toast(f"{title}\n\n{message}", icon="🚨" if severity == "CRITICAL" else "⚠️")
            st.session_state["flame_alert_last_toast"] = now
            _record_event(source, severity, "Notification / rappel", message)

    with st.expander("🔔 Historique des alertes", expanded=False):
        if st.session_state.get("flame_external_alert"):
            if st.button("Réinitialiser la source Monitoring (test)", key="flame_alert_reset_feed"):
                st.session_state.pop("flame_external_alert", None)
                st.rerun(scope="fragment")
        history = st.session_state.get("flame_alert_history", [])
        if history:
            st.dataframe(list(reversed(history)), hide_index=True, width="stretch")
        else:
            st.caption("Aucune alerte enregistrée pour cette session.")
        st.caption("Historique conservé dans cette session uniquement (non persistant après redémarrage).")
