from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import geopandas as gpd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

REQUEST_TIMEOUT_SECONDS = 90
MAX_DOWNLOAD_BYTES = 200 * 1024 * 1024


@dataclass(frozen=True)
class BoundarySource:
    name: str
    endpoint: str
    output_path: Path
    name_field: str
    params: dict[str, str]


SOURCES = (
    BoundarySource(
        name="Canadian park-system boundaries",
        endpoint=(
            "https://proxyinternet.nrcan-rncan.gc.ca/arcgis/rest/services/"
            "CLSS-SATC/CLSS_Administrative_Boundaries/MapServer/1/query"
        ),
        output_path=Path("data/reference/canada_national_parks.geojson"),
        name_field="adminAreaNameEng",
        params={
            "where": "1=1",
            "outFields": "adminAreaNameEng,distributionType",
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "geojson",
        },
    ),
    BoundarySource(
        name="United States park-system boundaries",
        endpoint=(
            "https://services1.arcgis.com/fBc8EJBxQRMcHlei/"
            "arcgis/rest/services/"
            "NPS_Land_Resources_Division_Boundary_and_Tract_Data_Service/"
            "FeatureServer/2/query"
        ),
        output_path=Path("data/reference/us_national_park_system.geojson"),
        name_field="UNIT_NAME",
        params={
            "where": "Status='Official'",
            "outFields": "UNIT_NAME,Status",
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "geojson",
        },
    ),
)


def create_session() -> requests.Session:
    retry_policy = Retry(
        total=4,
        connect=4,
        read=4,
        status=4,
        backoff_factor=1,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        respect_retry_after_header=True,
    )

    session = requests.Session()

    session.mount(
        "https://",
        HTTPAdapter(max_retries=retry_policy),
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


def validate_payload(
    payload: Any,
    source: BoundarySource,
) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        raise RuntimeError(f"{source.name} returned an invalid response.")

    if "error" in payload:
        raise RuntimeError(
            f"{source.name} returned an ArcGIS error: {payload['error']}"
        )

    if payload.get("type") != "FeatureCollection":
        raise RuntimeError(f"{source.name} did not return a GeoJSON FeatureCollection.")

    features = payload.get("features")

    if not isinstance(features, list) or not features:
        raise RuntimeError(f"{source.name} returned no features.")

    for feature in features:
        if not isinstance(feature, dict):
            raise RuntimeError(f"{source.name} contains an invalid feature.")

        properties = feature.get("properties")
        geometry = feature.get("geometry")

        if not isinstance(properties, dict):
            raise RuntimeError(f"{source.name} contains invalid properties.")

        name = properties.get(source.name_field)

        if name is None or not str(name).strip():
            raise RuntimeError(
                f"{source.name} contains a feature without {source.name_field}."
            )

        if not isinstance(geometry, dict):
            raise RuntimeError(f"{source.name} contains a feature without geometry.")

    return features


def validate_spatial_file(
    path: Path,
    source: BoundarySource,
) -> int:
    boundaries = gpd.read_file(path)

    if boundaries.empty:
        raise RuntimeError(f"{source.name} produced an empty dataset.")

    if source.name_field not in boundaries.columns:
        raise RuntimeError(f"{source.name} is missing {source.name_field}.")

    if boundaries.crs is None:
        raise RuntimeError(f"{source.name} has no coordinate system.")

    if boundaries.crs.to_epsg() != 4326:
        raise RuntimeError(f"{source.name} is not in EPSG:4326.")

    if boundaries.geometry.isna().any() or boundaries.geometry.is_empty.any():
        raise RuntimeError(f"{source.name} contains missing geometry.")

    geometry_types = set(boundaries.geometry.geom_type.unique())

    allowed_types = {"Polygon", "MultiPolygon"}

    if not geometry_types.issubset(allowed_types):
        unexpected = ", ".join(sorted(geometry_types))

        raise RuntimeError(
            f"{source.name} contains unexpected geometry types: {unexpected}"
        )

    return len(boundaries)


def download_source(
    session: requests.Session,
    source: BoundarySource,
) -> None:
    source.output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = source.output_path.with_suffix(".tmp.geojson")

    temporary_path.unlink(missing_ok=True)

    try:
        response = session.get(
            source.endpoint,
            params=source.params,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )

        response.raise_for_status()

        if len(response.content) > MAX_DOWNLOAD_BYTES:
            raise RuntimeError(f"{source.name} exceeded the download safety limit.")

        try:
            payload = response.json()
        except ValueError as error:
            raise RuntimeError(f"{source.name} did not return valid JSON.") from error

        features = validate_payload(
            payload,
            source,
        )

        with temporary_path.open(
            "w",
            encoding="utf-8",
        ) as output_file:
            json.dump(
                payload,
                output_file,
                ensure_ascii=False,
                separators=(",", ":"),
            )

        feature_count = validate_spatial_file(
            temporary_path,
            source,
        )

        if feature_count != len(features):
            raise RuntimeError(
                f"{source.name} feature count changed during validation."
            )

        os.replace(
            temporary_path,
            source.output_path,
        )

        print(f"Downloaded {feature_count} features to {source.output_path}")
    finally:
        temporary_path.unlink(missing_ok=True)


def download_reference_data() -> None:
    with create_session() as session:
        for source in SOURCES:
            download_source(
                session,
                source,
            )


if __name__ == "__main__":
    download_reference_data()
