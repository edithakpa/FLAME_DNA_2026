
"""
FLAME DNA - SAFFIRE-I Dataset Registration

Register existing SAFFIRE-I files in the
NASA experiments database.
"""

from pathlib import Path

from modules.research_catalog.experiments.experiment_store import (
    save_dataset,
    get_datasets,
)


BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = (
    BASE_DIR
    / "data"
    / "research_catalog"
    / "experiments"
    / "saffire_1"
)


FILES = [
    (
        "SAFFIRE-I-EXPERIMENTAL-TABLE",
        "experimental_table.csv",
        "Experimental sample conditions and metadata.",
    ),
    (
        "SAFFIRE-I-S2-TELEMETRY-XLSX",
        "Saffire-I Sample 2 Sensor Data Complete TM graphs.xlsx",
        "SAFFIRE-I Sample 2 sensor telemetry workbook.",
    ),
    (
        "SAFFIRE-I-SAMPLES-CLEAN",
        "saffire_samples_clean.csv",
        "Previously cleaned experimental sample table.",
    ),
    (
        "SAFFIRE-I-S2-TELEMETRY-CLEAN",
        "saffire_s2_telemetry_clean.csv",
        "Previously processed Sample 2 telemetry.",
    ),
    (
        "SAFFIRE-I-OTHER-RECORDS",
        "saffire_other_records.csv",
        "Records separated during sample data cleaning.",
    ),
]


def main():

    registered = 0

    for dataset_id, filename, description in FILES:

        file_path = DATA_DIR / filename

        if not file_path.is_file():
            print("MISSING:", filename)
            continue

        save_dataset({
            "dataset_id": dataset_id,
            "experiment_id": "SAFFIRE-I",
            "dataset_name": filename,
            "file_format": file_path.suffix.lower(),
            "source_url": None,
            "local_path": str(file_path.relative_to(BASE_DIR)),
            "description": description,
        })

        registered += 1
        print("REGISTERED:", filename)

    print()
    print("Files registered this run:", registered)
    print(
        "Total SAFFIRE-I datasets:",
        len(get_datasets("SAFFIRE-I")),
    )


if __name__ == "__main__":
    main()
