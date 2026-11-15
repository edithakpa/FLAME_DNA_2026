
import random
from datetime import datetime


def generate_sensor_data(scenario="normal"):
    """
    Génère des mesures fictives pour FLAME DNA.

    Ces valeurs sont destinées à la démonstration.
    Elles ne représentent pas des seuils NASA validés.
    """

    scenarios = {
        "normal": {
            "temperature": (20, 27),
            "smoke": (0.00, 0.05),
            "oxygen": (20.5, 21.5),
            "airflow": (0.10, 0.30),
        },
        "anomaly": {
            "temperature": (35, 55),
            "smoke": (0.10, 0.35),
            "oxygen": (19, 24),
            "airflow": (0.05, 0.40),
        },
        "fire": {
            "temperature": (70, 110),
            "smoke": (0.60, 0.95),
            "oxygen": (17, 25),
            "airflow": (0.05, 0.50),
        },
    }

    if scenario not in scenarios:
        raise ValueError(
            f"Scénario inconnu : {scenario}"
        )

    config = scenarios[scenario]

    return {
        "timestamp": datetime.now().isoformat(
            timespec="seconds"
        ),
        "scenario": scenario,
        "temperature": round(
            random.uniform(*config["temperature"]), 2
        ),
        "smoke": round(
            random.uniform(*config["smoke"]), 3
        ),
        "oxygen": round(
            random.uniform(*config["oxygen"]), 2
        ),
        "airflow": round(
            random.uniform(*config["airflow"]), 3
        ),
    }
