
"""
FLAME DNA - NASA Experiments Store

Local SQLite database for NASA experiments
and their associated scientific datasets.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[3]

DATABASE_PATH = (
    BASE_DIR
    / "data"
    / "research_catalog"
    / "experiments"
    / "experiments.db"
)


def get_connection():

    DATABASE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row

    return connection


def initialize_experiments_database():

    with get_connection() as connection:

        connection.execute("""
            CREATE TABLE IF NOT EXISTS experiments (
                experiment_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                program TEXT,
                mission TEXT,
                objective TEXT,
                description TEXT,
                source_name TEXT,
                source_url TEXT,
                updated_at TEXT NOT NULL
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS datasets (
                dataset_id TEXT PRIMARY KEY,
                experiment_id TEXT NOT NULL,
                dataset_name TEXT NOT NULL,
                file_format TEXT,
                source_url TEXT,
                local_path TEXT,
                description TEXT,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(experiment_id)
                    REFERENCES experiments(experiment_id)
            )
        """)


def save_experiment(experiment):

    initialize_experiments_database()

    data = dict(experiment)

    data["updated_at"] = datetime.now(
        timezone.utc
    ).isoformat()

    with get_connection() as connection:

        connection.execute("""
            INSERT INTO experiments (
                experiment_id,
                name,
                program,
                mission,
                objective,
                description,
                source_name,
                source_url,
                updated_at
            )
            VALUES (
                :experiment_id,
                :name,
                :program,
                :mission,
                :objective,
                :description,
                :source_name,
                :source_url,
                :updated_at
            )
            ON CONFLICT(experiment_id)
            DO UPDATE SET
                name = excluded.name,
                program = excluded.program,
                mission = excluded.mission,
                objective = excluded.objective,
                description = excluded.description,
                source_name = excluded.source_name,
                source_url = excluded.source_url,
                updated_at = excluded.updated_at
        """, data)


def get_experiments():

    initialize_experiments_database()

    with get_connection() as connection:

        rows = connection.execute("""
            SELECT *
            FROM experiments
            ORDER BY name
        """).fetchall()

    return [dict(row) for row in rows]


def save_dataset(dataset):

    initialize_experiments_database()

    data = dict(dataset)

    data["updated_at"] = datetime.now(
        timezone.utc
    ).isoformat()

    with get_connection() as connection:

        connection.execute("""
            INSERT INTO datasets (
                dataset_id,
                experiment_id,
                dataset_name,
                file_format,
                source_url,
                local_path,
                description,
                updated_at
            )
            VALUES (
                :dataset_id,
                :experiment_id,
                :dataset_name,
                :file_format,
                :source_url,
                :local_path,
                :description,
                :updated_at
            )
            ON CONFLICT(dataset_id)
            DO UPDATE SET
                experiment_id = excluded.experiment_id,
                dataset_name = excluded.dataset_name,
                file_format = excluded.file_format,
                source_url = excluded.source_url,
                local_path = excluded.local_path,
                description = excluded.description,
                updated_at = excluded.updated_at
        """, data)


def get_datasets(experiment_id=None):

    initialize_experiments_database()

    with get_connection() as connection:

        if experiment_id:

            rows = connection.execute("""
                SELECT *
                FROM datasets
                WHERE experiment_id = ?
                ORDER BY dataset_name
            """, (experiment_id,)).fetchall()

        else:

            rows = connection.execute("""
                SELECT *
                FROM datasets
                ORDER BY dataset_name
            """).fetchall()

    return [dict(row) for row in rows]
