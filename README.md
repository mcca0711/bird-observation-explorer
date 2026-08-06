# Bird Observation Explorer

An interactive geospatial application for exploring sampled 2024 eBird
observations across Canada and the United States.

[Live application](https://mcca0711.github.io/bird-observation-explorer/)

## Overview

Bird Observation Explorer combines ecological occurrence records, national park
system boundaries, browser-based analytics, and interactive visualization.

Users can:

- Explore geographic observation density
- Zoom from regional patterns to individual records
- Filter by country, species, month, and national park system context
- Inspect individual observation details
- Compare monthly records for a selected species
- Identify observations located inside mapped national park system areas

The bundled dataset contains 11,959 validated observation records. A GeoPandas
point-in-polygon analysis identified 296 records inside mapped Canadian or
United States national park system boundaries.

## Application architecture

```text
GBIF occurrence API
        |
        v
Python acquisition and validation
        |
        v
GeoPandas spatial join
        |
        v
GeoParquet snapshot
        |
        v
DuckDB WASM browser query
        |
        v
Vue filters and state
        |
        +------------------+
        |                  |
        v                  v
MapLibre and Deck.gl      D3 monthly chart
```

The browser does not repeatedly download and clean records from GBIF. Python
creates a validated GeoParquet snapshot before deployment, and DuckDB WASM
queries that snapshot directly inside the browser.

## Technology

### Frontend

- Vue 3
- TypeScript
- Vite
- Tailwind CSS
- MapLibre GL JS
- Deck.gl
- D3
- DuckDB WASM

### Data pipeline

- Python
- Requests
- pandas
- GeoPandas
- PyArrow
- GeoParquet

### Quality assurance

- pytest
- Vitest
- Vue Test Utils
- TypeScript compile checking
- GitHub Actions

## Geospatial processing

The Python pipeline:

1. Requests a controlled 2024 sample from the GBIF occurrence API
2. Restricts records to Canada and the United States
3. Validates coordinates, dates, identifiers, and country codes
4. Removes duplicate occurrence identifiers
5. Converts observation records into GeoPandas point geometry
6. Normalizes all spatial data to EPSG:4326
7. Performs a point-in-polygon spatial join
8. Preserves overlapping boundary names without duplicating observations
9. Writes the final dataset to GeoParquet
10. Validates the temporary output before atomically replacing the published file

Network requests use timeouts, retry limits, exponential backoff, page limits,
a descriptive user agent, and an overall record limit.

Only approved output fields are written to the published dataset.

## Visualization decisions

### Density-first map

At broad zoom levels, Deck.gl displays a heatmap so that regional concentration
can be understood without rendering thousands of competing markers.

Individual observations become selectable after the user zooms closer.

### Monthly bars

Monthly records are shown as bars because months are separate categories.

A smooth line could incorrectly imply continuous movement between months.
Whole-number axis labels are used because observation records cannot be
fractional.

Small samples receive a visible warning, and tied peak months are reported
together.

### National park system context

GeoPandas checks whether each observation point falls inside:

- Canadian national park, national park reserve, national urban park, or
  Saguenay–St. Lawrence Marine Park boundaries
- United States National Park Service unit boundaries

These boundaries do not represent every protected area in either country.

## Data sources

### Bird observations

EOD – eBird Observation Dataset
Cornell Lab of Ornithology, accessed through GBIF

- Dataset
  https://www.gbif.org/dataset/4fa7b334-ce0d-4e88-aaae-2e0c138d049e
- DOI
  https://doi.org/10.15468/aomfnb

### Canadian boundaries

National Parks and National Park Reserves of Canada Legislative Boundaries
Natural Resources Canada

https://open.canada.ca/data/en/dataset/9e1507cd-f25c-4c64-995b-6563bf9d65bd

Licensed under the Open Government Licence – Canada.

### United States boundaries

Administrative Boundaries of National Park System Units
National Park Service Land Resources Division

https://irma.nps.gov/DataStore/Reference/Profile/2316744

### Basemap

- OpenFreeMap
- OpenMapTiles
- OpenStreetMap contributors

Attribution is displayed directly beneath the map.

## Run locally

### Requirements

The project is tested with:

- Node.js 24
- npm 11
- Python 3.13

### Install frontend dependencies

```bash
npm ci
```

### Create the Python environment

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

macOS or Linux:

```bash
./.venv/bin/python -m pip install -r requirements.txt
```

### Start the application

```bash
npm run dev
```

The committed GeoParquet snapshot allows the application to run without
rebuilding the source data.

## Rebuild the dataset

Raw national park boundary downloads are intentionally excluded from Git
because they total approximately 97 MB.

Create the required directories:

```powershell
New-Item -ItemType Directory -Force data\reference\us
```

Download the Canadian GeoJSON:

```powershell
$canadaUrl = "https://proxyinternet.nrcan-rncan.gc.ca/arcgis/rest/services/CLSS-SATC/CLSS_Administrative_Boundaries/MapServer/1/query?where=1%3D1&outFields=*&returnGeometry=true&outSR=4326&f=geojson"

Invoke-WebRequest `
  -Uri $canadaUrl `
  -OutFile "data\reference\canada_national_parks.geojson"
```

Download the current public shapefile from the National Park Service reference
page:

https://irma.nps.gov/DataStore/Reference/Profile/2316744

Save the archive as:

```text
data/reference/us_national_parks.zip
```

Extract it:

```powershell
Expand-Archive `
  -Path data\reference\us_national_parks.zip `
  -DestinationPath data\reference\us `
  -Force
```

The pipeline expects this shapefile:

```text
data/reference/us/Administrative_Boundaries_of_National_Park_System_Units.shp
```

Build the GeoParquet snapshot:

```powershell
.\.venv\Scripts\python.exe scripts\build_dataset.py
```

Generated output:

```text
public/data/observations.parquet
```

## Testing

Run the Python tests:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Run the frontend tests:

```bash
npm test
```

Run the production build and TypeScript checks:

```bash
npm run build
```

The GitHub Actions workflow runs all three checks before deploying the
application.

## Data limitations

This project uses a controlled sample of reported observations.

The results do not represent:

- Complete eBird coverage
- Bird population size
- Species abundance
- Individual migration routes
- Every protected area in Canada or the United States

The acquisition pipeline applies a fixed monthly sampling limit. An
all-species monthly chart would mostly reflect that collection limit, so the
seasonal chart appears only after a species is selected.

Point-in-polygon results also depend on the accuracy of submitted coordinates
and the boundary datasets available when the snapshot was created.

## Project structure

```text
.github/workflows/
  deploy.yml

public/data/
  observations.parquet

scripts/
  build_dataset.py

src/
  components/
    ObservationMap.vue
    TimelineChart.vue
  App.vue
  data.ts
  main.ts
  style.css

tests/
  TimelineChart.test.ts
  test_build_dataset.py
```

## Deployment

Pushes to `main` trigger GitHub Actions.

The workflow:

1. Installs Python dependencies
2. Runs the Python tests
3. Installs frontend dependencies
4. Runs the frontend tests
5. Performs the production build
6. Publishes `dist` to GitHub Pages

## License

The application source code is licensed under the MIT License.

The observation data, boundary datasets, and basemap are not covered by the
MIT License. They remain subject to their original source terms and attribution
requirements.
