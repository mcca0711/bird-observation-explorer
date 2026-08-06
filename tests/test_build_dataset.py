import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import box

from scripts.build_dataset import (
    add_protected_area_context,
    clean_records,
    validate_dataset,
)


def make_record(
    observation_id: str,
    country: str = "CA",
    latitude: float = 45.42,
    longitude: float = -75.69,
    event_date: str = "2024-05-10T12:00:00Z",
) -> dict:
    return {
        "gbifID": observation_id,
        "species": "Branta canadensis",
        "vernacularName": "Canada Goose",
        "eventDate": event_date,
        "countryCode": country,
        "decimalLatitude": latitude,
        "decimalLongitude": longitude,
        "stateProvince": "Ontario",
        "locality": "Ottawa",
        "individualCount": 3,
    }


def make_geodataframe(
    records: list[dict],
) -> gpd.GeoDataFrame:
    table = clean_records(records)

    dataset = gpd.GeoDataFrame(
        table,
        geometry=gpd.points_from_xy(
            table["longitude"],
            table["latitude"],
        ),
        crs="EPSG:4326",
    )

    dataset["protected_area_name"] = None
    dataset["inside_protected_area"] = False

    return dataset


def test_clean_records_accepts_only_valid_unique_ca_us_records() -> None:
    records = [
        make_record("1", country="CA"),
        make_record("1", country="CA"),
        make_record("2", country="US"),
        make_record("3", country="MX"),
        make_record("4", latitude=200),
        make_record(
            "5",
            event_date="not-a-date",
        ),
    ]

    cleaned = clean_records(records)

    assert len(cleaned) == 2

    assert set(
        cleaned["observation_id"]
    ) == {"1", "2"}

    assert set(
        cleaned["country_code"]
    ) == {"CA", "US"}


def test_validate_dataset_accepts_valid_geographic_data() -> None:
    dataset = make_geodataframe(
        [
            make_record(
                "1",
                country="CA",
            ),
            make_record(
                "2",
                country="US",
            ),
        ]
    )

    validate_dataset(dataset)

    assert dataset.crs is not None
    assert dataset.crs.to_epsg() == 4326


def test_validate_dataset_rejects_duplicate_ids() -> None:
    dataset = make_geodataframe(
        [
            make_record(
                "1",
                country="CA",
            ),
            make_record(
                "2",
                country="US",
            ),
        ]
    )

    dataset.loc[
        1,
        "observation_id",
    ] = "1"

    with pytest.raises(
        RuntimeError,
        match="duplicate IDs",
    ):
        validate_dataset(dataset)


def test_spatial_join_marks_observations_inside_protected_area() -> None:
    observations = make_geodataframe(
        [
            make_record(
                "inside",
                latitude=0,
                longitude=0,
            ),
            make_record(
                "outside",
                latitude=5,
                longitude=5,
            ),
        ]
    ).drop(
        columns=[
            "protected_area_name",
            "inside_protected_area",
        ]
    )

    protected_areas = gpd.GeoDataFrame(
        {
            "protected_area_name": [
                "Example National Park"
            ]
        },
        geometry=[
            box(
                -1,
                -1,
                1,
                1,
            )
        ],
        crs="EPSG:4326",
    )

    enriched = add_protected_area_context(
        observations,
        protected_areas,
    )

    inside = enriched.loc[
        enriched[
            "observation_id"
        ] == "inside"
    ].iloc[0]

    outside = enriched.loc[
        enriched[
            "observation_id"
        ] == "outside"
    ].iloc[0]

    assert len(enriched) == 2

    assert bool(
        inside["inside_protected_area"]
    )

    assert (
        inside["protected_area_name"]
        == "Example National Park"
    )

    assert not bool(
        outside["inside_protected_area"]
    )

    assert pd.isna(
        outside["protected_area_name"]
    )


def test_spatial_join_does_not_duplicate_overlapping_observations() -> None:
    observations = make_geodataframe(
        [
            make_record(
                "1",
                latitude=0,
                longitude=0,
            )
        ]
    ).drop(
        columns=[
            "protected_area_name",
            "inside_protected_area",
        ]
    )

    protected_areas = gpd.GeoDataFrame(
        {
            "protected_area_name": [
                "Beta Park",
                "Alpha Park",
            ]
        },
        geometry=[
            box(
                -1,
                -1,
                1,
                1,
            ),
            box(
                -2,
                -2,
                2,
                2,
            ),
        ],
        crs="EPSG:4326",
    )

    enriched = add_protected_area_context(
        observations,
        protected_areas,
    )

    assert len(enriched) == 1

    assert (
        enriched.iloc[0][
            "protected_area_name"
        ]
        == "Alpha Park; Beta Park"
    )