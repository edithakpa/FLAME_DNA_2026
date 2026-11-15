
import pandas as pd


EVENT_COLUMNS = [
    "Timestamp",
    "Event Type",
    "Severity",
    "Detection Source",
    "Description",
    "Temperature (°C)",
    "Smoke Index",
    "Oxygen (%)",
    "Airflow (m/s)",
]


def create_event_history():
    """Create an empty event history table."""
    return pd.DataFrame(columns=EVENT_COLUMNS)


def record_event(history, sensor_data, risk, ai_result):
    """
    Record AI anomalies and rule-based alerts.

    Events are generated from simulated data.
    """

    events = []

    timestamp = sensor_data["timestamp"]

    readings = {
        "Temperature (°C)": sensor_data["temperature"],
        "Smoke Index": sensor_data["smoke"],
        "Oxygen (%)": sensor_data["oxygen"],
        "Airflow (m/s)": sensor_data["airflow"],
    }

    # AI anomaly event
    if ai_result["is_anomaly"]:
        events.append({
            "Timestamp": timestamp,
            "Event Type": "AI Anomaly",
            "Severity": "Warning",
            "Detection Source": "Isolation Forest",
            "Description": "Unusual sensor pattern detected",
            **readings,
        })

    # Rule-based monitoring event
    if risk["status"] != "NORMAL":

        severity = (
            "Critical"
            if risk["level"] == 2
            else "Warning"
        )

        events.append({
            "Timestamp": timestamp,
            "Event Type": "Sensor Alert",
            "Severity": severity,
            "Detection Source": "Rule-Based Monitoring",
            "Description": (
                "Simulated fire alert"
                if severity == "Critical"
                else "Unusual sensor readings"
            ),
            **readings,
        })

    if not events:
        return history

    new_events = pd.DataFrame(events)

    return pd.concat(
        [history, new_events],
        ignore_index=True,
    )


def get_event_statistics(history):
    """Calculate event statistics."""

    if history.empty:
        return {
            "total_events": 0,
            "ai_anomalies": 0,
            "sensor_alerts": 0,
            "critical_alerts": 0,
        }

    return {
        "total_events": len(history),
        "ai_anomalies": int(
            (history["Event Type"] == "AI Anomaly").sum()
        ),
        "sensor_alerts": int(
            (history["Event Type"] == "Sensor Alert").sum()
        ),
        "critical_alerts": int(
            (history["Severity"] == "Critical").sum()
        ),
    }


def export_event_history(history):
    """Export event history as UTF-8 CSV."""

    return history.to_csv(
        index=False
    ).encode("utf-8-sig")
