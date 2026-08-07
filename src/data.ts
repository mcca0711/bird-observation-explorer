import * as duckdb from '@duckdb/duckdb-wasm'

import mvpWasm from '@duckdb/duckdb-wasm/dist/duckdb-mvp.wasm?url'

export interface Observation {
  id: string
  scientificName: string
  commonName: string | null
  date: string
  countryCode: string
  province: string | null
  locality: string | null
  protectedAreaName: string | null
  insideProtectedArea: boolean
  latitude: number
  longitude: number
}

const MVP_WORKER_URL =
  `${import.meta.env.BASE_URL}` +
  'vendor/duckdb/duckdb-browser-mvp.worker-1.32.0.js'

export async function loadObservations(): Promise<Observation[]> {
  const worker = new Worker(MVP_WORKER_URL)

  const database = new duckdb.AsyncDuckDB(new duckdb.ConsoleLogger(), worker)

  try {
    await database.instantiate(mvpWasm, undefined)

    await database.registerFileURL(
      'observations.parquet',
      `${import.meta.env.BASE_URL}data/observations.parquet`,
      duckdb.DuckDBDataProtocol.HTTP,
      false,
    )

    const connection = await database.connect()

    try {
      const result = await connection.query(`
        SELECT
          observation_id,
          scientific_name,
          common_name,
          CAST(observed_on AS VARCHAR) AS observed_on,
          country_code,
          province,
          locality,
          protected_area_name,
          inside_protected_area,
          latitude,
          longitude
        FROM read_parquet('observations.parquet')
      `)

      return result.toArray().map((row) => {
        const value = row.toJSON()

        return {
          id: String(value.observation_id),

          scientificName: String(value.scientific_name),

          commonName: value.common_name ? String(value.common_name) : null,

          date: String(value.observed_on),

          countryCode: String(value.country_code),

          province: value.province ? String(value.province) : null,

          locality: value.locality ? String(value.locality) : null,

          protectedAreaName: value.protected_area_name
            ? String(value.protected_area_name)
            : null,

          insideProtectedArea: Boolean(value.inside_protected_area),

          latitude: Number(value.latitude),
          longitude: Number(value.longitude),
        }
      })
    } finally {
      await connection.close()
    }
  } finally {
    await database.terminate()
  }
}
