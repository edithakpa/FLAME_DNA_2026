
"""
FLAME DNA - SAFFIRE Experiments Registration

Register the first three NASA SAFFIRE experiments
without inventing experimental measurements.
"""

from modules.research_catalog.experiments.experiment_store import (
    save_experiment,
    get_experiments,
)


SAFFIRE_EXPERIMENTS = [
    {
        "experiment_id": "SAFFIRE-I",
        "name": "Spacecraft Fire Safety Experiment I",
        "program": "NASA SAFFIRE",
        "mission": "SAFFIRE-I",
        "objective": (
            "Investigate large-scale flame spread "
            "in a spacecraft environment."
        ),
        "description": (
            "The first SAFFIRE experiment investigated "
            "flame propagation over a large material sample "
            "in microgravity aboard an uncrewed Cygnus "
            "cargo spacecraft."
        ),
        "source_name": "NASA",
        "source_url": (
            "https://www.nasa.gov/mission/saffire/"
        ),
    },
    {
        "experiment_id": "SAFFIRE-II",
        "name": "Spacecraft Fire Safety Experiment II",
        "program": "NASA SAFFIRE",
        "mission": "SAFFIRE-II",
        "objective": (
            "Investigate the flammability of different "
            "materials in microgravity."
        ),
        "description": (
            "SAFFIRE-II examined flame propagation "
            "across multiple material samples "
            "to support spacecraft fire safety research."
        ),
        "source_name": "NASA",
        "source_url": (
            "https://www.nasa.gov/mission/saffire/"
        ),
    },
    {
        "experiment_id": "SAFFIRE-III",
        "name": "Spacecraft Fire Safety Experiment III",
        "program": "NASA SAFFIRE",
        "mission": "SAFFIRE-III",
        "objective": (
            "Investigate large-scale flame spread "
            "under different ventilation conditions."
        ),
        "description": (
            "SAFFIRE-III extended the investigation "
            "of large-scale flame propagation "
            "in microgravity, including the influence "
            "of airflow conditions."
        ),
        "source_name": "NASA",
        "source_url": (
            "https://www.nasa.gov/mission/saffire/"
        ),
    },
]


def main():

    for experiment in SAFFIRE_EXPERIMENTS:
        save_experiment(experiment)

    experiments = get_experiments()

    print("NASA Experiments Registered:", len(experiments))

    for experiment in experiments:
        print(
            "-",
            experiment["experiment_id"],
            "|",
            experiment["name"],
        )


if __name__ == "__main__":
    main()
