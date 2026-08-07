import os
from datetime import datetime
from pathlib import Path
from time import sleep
from typing import Any

import geopandas as gpd
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

GBIF_URL = "https://api.gbif.org/v1/occurrence/search"
EBIRD_DATASET_KEY = "4fa7b334-ce0d-4e88-aaae-2e0c138d049e"

COUNTRIES = ("CA", "US")
YEAR = 2024

RECORDS_PER_MONTH = 500
PAGE_SIZE = 300
REQUEST_TIMEOUT_SECONDS = 30
REQUEST_DELAY_SECONDS = 0.25

MAX_TOTAL_RECORDS = len(COUNTRIES) * 12 * RECORDS_PER_MONTH

CANADA_PARKS_PATH = Path("data/reference/canada_national_parks.geojson")

US_PARKS_PATH = Path("data/reference/us_national_park_system.geojson")

OUTPUT_PATH = Path("public/data/observations.parquet")

TEMP_OUTPUT_PATH = Path("public/data/observations.tmp.parquet")

CLEAN_COLUMNS = [
    "observation_id",
    "scientific_name",
    "common_name",
    "observed_on",
    "country_code",
    "latitude",
    "longitude",
    "province",
    "locality",
    "individual_count",
]

FINAL_COLUMNS = [
    *CLEAN_COLUMNS,
    "protected_area_name",
    "inside_protected_area",
    "geometry",
]


def create_session() -> requests.Session:
    retry_policy = Retry(
        total=4,
        connect=4,
        read=4,
        status=4,
        backoff_factor=1,
        status_forcelist=(
            429,
            500,
            502,
            503,
            504,
        ),
        allowed_methods=("GET",),
        respect_retry_after_header=True,
    )

    session = requests.Session()

    session.mount(
        "https://",
        HTTPAdapter(
            max_retries=retry_policy,
            pool_connections=1,
            pool_maxsize=1,
        ),
    )

    session.headers.update(
        {
            "User-Agent": (
                "bird-observation-explorer/1.0 "
                "(https://github.com/mcca0711/"
                "bird-observation-explorer)"
            )
        }
    )

    return session


def fetch_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    with create_session() as session:
        for country in COUNTRIES:
            for month in range(1, 13):
                offset = 0
                downloaded = 0

                while downloaded < RECORDS_PER_MONTH:
                    limit = min(
                        PAGE_SIZE,
                        RECORDS_PER_MONTH - downloaded,
                    )

                    response = session.get(
                        GBIF_URL,
                        params={
                            "datasetKey": EBIRD_DATASET_KEY,
                            "country": country,
                            "year": YEAR,
                            "month": month,
                            "hasCoordinate": "true",
                            "occurrenceStatus": "PRESENT",
                            "basisOfRecord": "HUMAN_OBSERVATION",
                            "limit": limit,
                            "offset": offset,
                        },
                        timeout=REQUEST_TIMEOUT_SECONDS,
                    )

                    sleep(REQUEST_DELAY_SECONDS)
                    response.raise_for_status()

                    payload = response.json()

                    if not isinstance(payload, dict):
                        raise RuntimeError("GBIF returned an invalid response.")

                    batch = payload.get("results")

                    if not isinstance(batch, list):
                        raise RuntimeError(
                            "GBIF response did not contain a valid results list."
                        )

                    if not batch:
                        break

                    for record in batch:
                        if not isinstance(record, dict):
                            continue

                        record["_requested_country"] = country
                        records.append(record)

                    received = len(batch)
                    downloaded += received
                    offset += received

                    if len(records) > MAX_TOTAL_RECORDS:
                        raise RuntimeError(
                            "The download exceeded the configured safety limit."
                        )

                    if payload.get("endOfRecords", False):
                        break

                print(f"{country} month {month:02} downloaded {downloaded}")

    return records


def clean_records(
    records: list[dict[str, Any]],
) -> pd.DataFrame:
    cleaned: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for record in records:
        observation_id = str(record.get("gbifID", "")).strip()

        scientific_name = str(record.get("species", "")).strip()

        country_code = (
            str(record.get("countryCode") or record.get("_requested_country") or "")
            .strip()
            .upper()
        )

        try:
            latitude = float(record["decimalLatitude"])

            longitude = float(record["decimalLongitude"])

            observed_on = (
                datetime.fromisoformat(
                    str(record["eventDate"]).replace(
                        "Z",
                        "+00:00",
                    )
                )
                .date()
                .isoformat()
            )

        except (
            KeyError,
            TypeError,
            ValueError,
        ):
            continue

        if not observation_id:
            continue

        if not scientific_name:
            continue

        if observation_id in seen_ids:
            continue

        if country_code not in COUNTRIES:
            continue

        if not -90 <= latitude <= 90:
            continue

        if not -180 <= longitude <= 180:
            continue

        individual_count = record.get("individualCount")

        try:
            individual_count = int(individual_count)

            if individual_count < 1:
                individual_count = None

        except (
            TypeError,
            ValueError,
        ):
            individual_count = None

        seen_ids.add(observation_id)

        cleaned.append(
            {
                "observation_id": observation_id,
                "scientific_name": scientific_name,
                "common_name": (record.get("vernacularName") or None),
                "observed_on": observed_on,
                "country_code": country_code,
                "latitude": latitude,
                "longitude": longitude,
                "province": (record.get("stateProvince") or None),
                "locality": (record.get("locality") or None),
                "individual_count": individual_count,
            }
        )

    return pd.DataFrame(
        cleaned,
        columns=CLEAN_COLUMNS,
    )


def load_protected_areas() -> gpd.GeoDataFrame:
    sources = [
        (
            CANADA_PARKS_PATH,
            "adminAreaNameEng",
        ),
        (
            US_PARKS_PATH,
            "UNIT_NAME",
        ),
    ]

    protected_area_tables = []

    for path, name_column in sources:
        if not path.exists():
            raise RuntimeError(f"Protected-area file was not found: {path}")

        boundaries = gpd.read_file(path)

        if boundaries.crs is None:
            raise RuntimeError(f"Protected-area file has no CRS: {path}")

        if name_column not in boundaries.columns:
            raise RuntimeError(
                f"Expected column {name_column} was not found in {path}."
            )

        boundaries = boundaries[[name_column, "geometry"]].rename(
            columns={name_column: "protected_area_name"}
        )

        boundaries = boundaries.dropna(
            subset=[
                "protected_area_name",
                "geometry",
            ]
        )

        boundaries["protected_area_name"] = (
            boundaries["protected_area_name"].astype(str).str.strip()
        )

        boundaries = boundaries[
            boundaries["protected_area_name"].ne("") & ~boundaries.geometry.is_empty
        ]

        boundaries = boundaries.to_crs("EPSG:4326")

        protected_area_tables.append(boundaries)

    protected_areas = gpd.GeoDataFrame(
        pd.concat(
            protected_area_tables,
            ignore_index=True,
        ),
        geometry="geometry",
        crs="EPSG:4326",
    )

    if protected_areas.empty:
        raise RuntimeError("No protected-area boundaries were loaded.")

    return protected_areas


def combine_protected_area_names(
    names: pd.Series,
) -> str:
    unique_names = sorted({str(name).strip() for name in names if str(name).strip()})

    return "; ".join(unique_names)


def add_protected_area_context(
    observations: gpd.GeoDataFrame,
    protected_areas: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    if observations.crs is None:
        raise RuntimeError("Observation data has no CRS.")

    if protected_areas.crs is None:
        raise RuntimeError("Protected-area data has no CRS.")

    observations = observations.to_crs("EPSG:4326")

    protected_areas = protected_areas.to_crs("EPSG:4326")

    matches = gpd.sjoin(
        observations[
            [
                "observation_id",
                "geometry",
            ]
        ],
        protected_areas[
            [
                "protected_area_name",
                "geometry",
            ]
        ],
        how="left",
        predicate="within",
    )

    matched_names = (
        matches.dropna(subset=["protected_area_name"])
        .groupby("observation_id")["protected_area_name"]
        .agg(combine_protected_area_names)
    )

    enriched = observations.copy()

    enriched["protected_area_name"] = enriched["observation_id"].map(matched_names)

    enriched["protected_area_name"] = enriched["protected_area_name"].where(
        enriched["protected_area_name"].notna(),
        None,
    )

    enriched["inside_protected_area"] = enriched["protected_area_name"].notna()

    return enriched[FINAL_COLUMNS]


def validate_dataset(
    dataset: gpd.GeoDataFrame,
) -> None:
    if dataset.empty:
        raise RuntimeError("No valid observations were produced.")

    if len(dataset) > MAX_TOTAL_RECORDS:
        raise RuntimeError("The cleaned dataset exceeded the configured safety limit.")

    missing_columns = [
        column for column in FINAL_COLUMNS if column not in dataset.columns
    ]

    if missing_columns:
        raise RuntimeError(
            "The dataset is missing columns: " + ", ".join(missing_columns)
        )

    if dataset["observation_id"].duplicated().any():
        raise RuntimeError("The dataset contains duplicate IDs.")

    if not dataset["country_code"].isin(COUNTRIES).all():
        raise RuntimeError("The dataset contains an unexpected country code.")

    if (
        not dataset["latitude"]
        .between(
            -90,
            90,
        )
        .all()
    ):
        raise RuntimeError("The dataset contains invalid latitude.")

    if (
        not dataset["longitude"]
        .between(
            -180,
            180,
        )
        .all()
    ):
        raise RuntimeError("The dataset contains invalid longitude.")

    if dataset.crs is None:
        raise RuntimeError("The dataset has no coordinate system.")

    if dataset.crs.to_epsg() != 4326:
        raise RuntimeError("The dataset has the wrong coordinate system.")

    inside = dataset["inside_protected_area"]

    park_names = dataset["protected_area_name"].fillna("").astype(str).str.strip()

    if not inside.isin([True, False]).all():
        raise RuntimeError("Protected-area flags are invalid.")

    if (inside & park_names.eq("")).any():
        raise RuntimeError("A protected-area observation has no protected-area name.")

    if (~inside & park_names.ne("")).any():
        raise RuntimeError(
            "An observation outside protected areas has a protected-area name."
        )


def write_dataset(
    dataset: gpd.GeoDataFrame,
) -> None:
    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    TEMP_OUTPUT_PATH.unlink(
        missing_ok=True,
    )

    try:
        dataset.to_parquet(
            TEMP_OUTPUT_PATH,
            index=False,
            compression="zstd",
        )

        saved_dataset = gpd.read_parquet(TEMP_OUTPUT_PATH)

        validate_dataset(saved_dataset)

        if len(saved_dataset) != len(dataset):
            raise RuntimeError("The saved dataset row count does not match the source.")

        os.replace(
            TEMP_OUTPUT_PATH,
            OUTPUT_PATH,
        )

    finally:
        TEMP_OUTPUT_PATH.unlink(
            missing_ok=True,
        )


def build_dataset() -> None:
    raw_records = fetch_records()
    table = clean_records(raw_records)

    geographic_table = gpd.GeoDataFrame(
        table,
        geometry=gpd.points_from_xy(
            table["longitude"],
            table["latitude"],
        ),
        crs="EPSG:4326",
    )

    protected_areas = load_protected_areas()

    final_dataset = add_protected_area_context(
        geographic_table,
        protected_areas,
    )

    validate_dataset(final_dataset)
    write_dataset(final_dataset)

    country_counts = final_dataset["country_code"].value_counts().sort_index()

    protected_count = int(final_dataset["inside_protected_area"].sum())

    print()
    print(f"Created {OUTPUT_PATH}")

    print(f"Accepted {len(final_dataset)} observations")

    for country, count in country_counts.items():
        print(f"{country} {count}")

    print(f"Inside protected areas {protected_count}")


if __name__ == "__main__":
    build_dataset()
