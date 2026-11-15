
import numpy as np
import pandas as pd

from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler


# Sensor features used by the AI model
FEATURES = [
    "temperature",
    "smoke",
    "oxygen",
    "airflow",
]


def generate_training_data(n_samples=1000):
    """
    Generate synthetic baseline sensor readings.

    These values are illustrative and are not
    validated NASA fire-safety thresholds.
    """
    rng = np.random.default_rng(42)

    data = pd.DataFrame({
        "temperature": rng.uniform(
            20, 27, n_samples
        ),
        "smoke": rng.uniform(
            0.00, 0.05, n_samples
        ),
        "oxygen": rng.uniform(
            20.5, 21.5, n_samples
        ),
        "airflow": rng.uniform(
            0.10, 0.30, n_samples
        ),
    })

    return data


def train_anomaly_model():
    """
    Train an Isolation Forest on synthetic
    normal operating conditions.
    """
    training_data = generate_training_data()

    scaler = StandardScaler()
    scaled_data = scaler.fit_transform(
        training_data[FEATURES]
    )

    model = IsolationForest(
        n_estimators=150,
        contamination=0.01,
        random_state=42,
    )

    model.fit(scaled_data)

    return model, scaler


def detect_anomaly(sensor_data, model, scaler):
    """
    Evaluate one sensor reading.

    Returns an anomaly classification and
    an Isolation Forest decision score.
    """
    values = pd.DataFrame(
        [{
            feature: float(sensor_data[feature])
            for feature in FEATURES
        }]
    )

    scaled_values = scaler.transform(
        values[FEATURES]
    )

    prediction = int(
        model.predict(scaled_values)[0]
    )

    score = float(
        model.decision_function(scaled_values)[0]
    )

    is_anomaly = prediction == -1

    return {
        "is_anomaly": is_anomaly,
        "status": (
            "ANOMALY DETECTED"
            if is_anomaly
            else "NORMAL PATTERN"
        ),
        "anomaly_score": round(score, 4),
        "model": "Isolation Forest",
    }


if __name__ == "__main__":
    from modules.simulator import generate_sensor_data

    model, scaler = train_anomaly_model()

    for scenario in ["normal", "anomaly", "fire"]:
        data = generate_sensor_data(scenario)
        result = detect_anomaly(
            data, model, scaler
        )

        print(f"\nScenario: {scenario}")
        print(f"Sensor readings: {data}")
        print(f"AI result: {result}")
