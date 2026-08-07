<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { PickingInfo } from '@deck.gl/core'
import { HeatmapLayer } from '@deck.gl/aggregation-layers'
import { ScatterplotLayer } from '@deck.gl/layers'
import { MapboxOverlay } from '@deck.gl/mapbox'
import { Map, NavigationControl } from 'maplibre-gl'

import 'maplibre-gl/dist/maplibre-gl.css'

import type { Observation } from '../data'

const props = defineProps<{
  observations: Observation[]
}>()

const DETAIL_ZOOM = 5

const mapElement = ref<HTMLDivElement | null>(null)
const selectedObservation = ref<Observation | null>(null)
const detailView = ref(false)
const status = ref('Starting map')
const errorMessage = ref('')

let map: Map | null = null
let overlay: MapboxOverlay | null = null
let resizeObserver: ResizeObserver | null = null
let basemapWarningLogged = false

const validObservations = computed(() =>
  props.observations.filter(
    (observation) =>
      Number.isFinite(observation.longitude) &&
      Number.isFinite(observation.latitude) &&
      observation.longitude >= -180 &&
      observation.longitude <= 180 &&
      observation.latitude >= -90 &&
      observation.latitude <= 90,
  ),
)

function reportError(source: string, error: unknown): void {
  const message = error instanceof Error ? error.message : String(error)

  errorMessage.value = `${source}: ${message}`
  status.value = ''

  console.error(errorMessage.value, error)
}

function getCountryName(countryCode: string): string {
  if (countryCode === 'CA') {
    return 'Canada'
  }

  if (countryCode === 'US') {
    return 'United States'
  }

  return countryCode
}

function selectObservation(info: PickingInfo<Observation>): boolean {
  if (!info.object) {
    return false
  }

  selectedObservation.value = info.object
  updateLayers()

  return true
}

function clearSelectedObservation(): void {
  selectedObservation.value = null
  updateLayers()
}

function createDensityLayer(
  observations: Observation[],
): HeatmapLayer<Observation> {
  return new HeatmapLayer<Observation>({
    id: 'observation-density',
    data: observations,
    opacity: 0.68,

    getPosition: (observation) => [observation.longitude, observation.latitude],

    getWeight: 1,
    aggregation: 'SUM',
    radiusPixels: 34,
    intensity: 1,
    threshold: 0.012,

    colorRange: [
      [15, 23, 42, 0],
      [6, 78, 59, 65],
      [5, 150, 105, 120],
      [16, 185, 129, 175],
      [110, 231, 183, 220],
      [236, 253, 245, 250],
    ],

    onError: (error) => {
      reportError('Observation density', error)

      return true
    },
  })
}

function createPointLayer(
  observations: Observation[],
  detailed: boolean,
): ScatterplotLayer<Observation> {
  return new ScatterplotLayer<Observation>({
    id: 'bird-observations',
    data: observations,

    opacity: detailed ? 0.92 : 0.28,

    getPosition: (observation) => [observation.longitude, observation.latitude],

    getRadius: 7_000,
    radiusMinPixels: detailed ? 3 : 1.5,
    radiusMaxPixels: detailed ? 10 : 5,

    getFillColor: [16, 185, 129, 220],
    getLineColor: [255, 255, 255, 210],

    stroked: detailed,
    lineWidthMinPixels: 1,
    pickable: detailed,

    onClick: selectObservation,

    onError: (error) => {
      reportError('Observation points', error)

      return true
    },
  })
}

function createSelectedPointLayer(): ScatterplotLayer<Observation> | null {
  if (!selectedObservation.value) {
    return null
  }

  return new ScatterplotLayer<Observation>({
    id: 'selected-observation',
    data: [selectedObservation.value],

    getPosition: (observation) => [observation.longitude, observation.latitude],

    getRadius: 10_000,
    radiusMinPixels: 6,
    radiusMaxPixels: 14,

    getFillColor: [245, 158, 11, 255],
    getLineColor: [255, 255, 255, 255],

    stroked: true,
    lineWidthMinPixels: 2,
    pickable: false,
  })
}

function updateLayers(): void {
  if (!overlay || !map) {
    return
  }

  const observations = validObservations.value

  if (observations.length === 0) {
    reportError(
      'Observation data',
      new Error('No observations have valid coordinates.'),
    )

    return
  }

  errorMessage.value = ''

  detailView.value = map.getZoom() >= DETAIL_ZOOM

  if (!detailView.value) {
    selectedObservation.value = null
  }

  const layers = []

  if (!detailView.value) {
    layers.push(createDensityLayer(observations))
  }

  layers.push(createPointLayer(observations, detailView.value))

  const selectedPointLayer = createSelectedPointLayer()

  if (selectedPointLayer) {
    layers.push(selectedPointLayer)
  }

  overlay.setProps({ layers })

  status.value = `${observations.length.toLocaleString()} sampled observations`
}

function verifyMapSize(): boolean {
  if (!mapElement.value) {
    return false
  }

  const bounds = mapElement.value.getBoundingClientRect()

  if (bounds.width === 0 || bounds.height === 0) {
    reportError(
      'Map layout',
      new Error(
        `The map has invalid dimensions ` +
          `${bounds.width} × ${bounds.height}.`,
      ),
    )

    return false
  }

  return true
}

onMounted(() => {
  if (!mapElement.value) {
    reportError('Map setup', new Error('The map element was not found.'))

    return
  }

  if (!verifyMapSize()) {
    return
  }

  const touchFirstDevice = window.matchMedia(
    '(hover: none) and (pointer: coarse)',
  ).matches

  try {
    map = new Map({
      container: mapElement.value,

      style: 'https://tiles.openfreemap.org/styles/liberty',

      center: [-96, 48],
      zoom: 2.5,
      minZoom: 2,
      maxZoom: 12,

      scrollZoom: !touchFirstDevice,
      dragPan: !touchFirstDevice,
      doubleClickZoom: true,
      touchZoomRotate: true,
      keyboard: true,

      attributionControl: false,

      cancelPendingTileRequestsWhileZooming: false,

      maxTileCacheZoomLevels: 6,
    })

    map.addControl(
      new NavigationControl({
        showCompass: false,
      }),
      'top-right',
    )

    map.on('error', (event) => {
      if (basemapWarningLogged) {
        return
      }

      basemapWarningLogged = true

      console.warn('Some basemap resources could not be loaded.', event.error)
    })

    map.on('zoomend', updateLayers)

    map.once('load', () => {
      if (!map) {
        reportError(
          'Map setup',
          new Error('The map was removed before loading.'),
        )

        return
      }

      try {
        overlay = new MapboxOverlay({
          interleaved: false,
          layers: [],

          onError: (error) => {
            reportError('Deck.gl', error)
          },
        })

        map.addControl(overlay)
        map.resize()
        updateLayers()
      } catch (error) {
        reportError('Observation layers', error)
      }
    })

    resizeObserver = new ResizeObserver(() => {
      if (verifyMapSize()) {
        map?.resize()
      }
    })

    resizeObserver.observe(mapElement.value)
  } catch (error) {
    reportError('Map setup', error)
  }
})

watch(
  () => props.observations,
  () => {
    if (
      selectedObservation.value &&
      !props.observations.some(
        (observation) => observation.id === selectedObservation.value?.id,
      )
    ) {
      selectedObservation.value = null
    }

    updateLayers()
  },
)

onBeforeUnmount(() => {
  resizeObserver?.disconnect()

  if (map && overlay) {
    map.removeControl(overlay)
  }

  overlay = null

  map?.remove()
  map = null
})
</script>

<template>
  <section class="w-full">
    <div class="relative h-[380px] w-full sm:h-[480px] lg:h-[540px]">
      <div
        ref="mapElement"
        class="h-full w-full"
        aria-label="Interactive map of sampled bird observations"
      />

      <div
        v-if="!selectedObservation"
        class="absolute left-3 top-3 z-10 rounded-md border border-slate-200 bg-white/90 px-3 py-2 text-xs text-slate-700"
      >
        {{
          detailView
            ? 'Select a point for details'
            : 'Zoom to inspect individual observations'
        }}
      </div>

      <article
        v-if="selectedObservation"
        class="absolute left-3 top-3 z-10 w-[min(320px,calc(100%-4.5rem))] rounded-lg border border-slate-200 bg-white/95 p-4 text-slate-900"
        aria-live="polite"
      >
        <div class="flex items-start justify-between gap-3">
          <div>
            <p
              class="text-xs font-medium uppercase tracking-wide text-amber-700"
            >
              Selected observation
            </p>

            <h2 class="mt-1 font-semibold">
              {{
                selectedObservation.commonName ??
                selectedObservation.scientificName
              }}
            </h2>
          </div>

          <button
            type="button"
            class="rounded px-2 py-1 text-sm text-slate-500 hover:bg-slate-100 hover:text-slate-900"
            aria-label="Close observation details"
            @click="clearSelectedObservation"
          >
            Close
          </button>
        </div>

        <dl class="mt-3 space-y-3 text-sm">
          <div>
            <dt class="text-slate-500">Scientific name</dt>

            <dd class="italic">
              {{ selectedObservation.scientificName }}
            </dd>
          </div>

          <div>
            <dt class="text-slate-500">Date</dt>

            <dd>
              {{ selectedObservation.date }}
            </dd>
          </div>

          <div>
            <dt class="text-slate-500">Location</dt>

            <dd>
              {{
                [
                  selectedObservation.locality,
                  selectedObservation.province,
                  getCountryName(selectedObservation.countryCode),
                ]
                  .filter(Boolean)
                  .join(', ')
              }}
            </dd>
          </div>

          <div>
            <dt class="text-slate-500">Mapped park-system context</dt>

            <dd
              v-if="
                selectedObservation.insideProtectedArea &&
                selectedObservation.protectedAreaName
              "
              class="font-medium text-emerald-700"
            >
              {{ selectedObservation.protectedAreaName }}
            </dd>

            <dd v-else>Outside mapped park-system areas</dd>
          </div>
        </dl>
      </article>

      <div
        v-if="errorMessage"
        class="absolute bottom-3 left-3 z-10 max-w-md rounded-lg border border-red-400/30 bg-red-950/95 px-3 py-2 text-xs text-red-200"
        role="alert"
      >
        {{ errorMessage }}
      </div>

      <div
        v-else
        class="absolute bottom-3 left-3 z-10 hidden rounded-md bg-slate-950/90 px-3 py-2 text-xs text-white sm:block"
        aria-live="polite"
      >
        {{ status }}
      </div>

      <div
        class="absolute bottom-3 right-3 z-10 rounded-lg border border-slate-200 bg-white/90 px-3 py-2 text-xs text-slate-800"
        aria-label="Map legend"
      >
        <div class="flex items-center gap-2">
          <span
            class="h-3 w-3 rounded-full border border-emerald-200 bg-emerald-500"
          />

          <span>Sampled observation</span>
        </div>

        <div v-if="selectedObservation" class="mt-1 flex items-center gap-2">
          <span
            class="h-3 w-3 rounded-full border border-amber-200 bg-amber-500"
          />

          <span>Selected observation</span>
        </div>

        <div v-if="!detailView" class="mt-2">
          <p class="text-slate-500">Concentration</p>

          <div
            class="mt-1 h-2 w-28 rounded-full bg-gradient-to-r from-slate-900 via-emerald-600 to-emerald-100"
          />
        </div>
      </div>
    </div>

    <footer
      class="flex flex-wrap justify-end gap-x-1 border-t border-slate-800 bg-slate-950 px-3 py-1.5 text-[11px] text-slate-500"
    >
      <span>Map data</span>

      <a
        href="https://openfreemap.org/"
        target="_blank"
        rel="noreferrer"
        class="hover:text-slate-300"
      >
        © OpenFreeMap
      </a>

      <span>·</span>

      <a
        href="https://openmaptiles.org/"
        target="_blank"
        rel="noreferrer"
        class="hover:text-slate-300"
      >
        © OpenMapTiles
      </a>

      <span>·</span>

      <a
        href="https://www.openstreetmap.org/copyright"
        target="_blank"
        rel="noreferrer"
        class="hover:text-slate-300"
      >
        © OpenStreetMap contributors
      </a>
    </footer>
  </section>
</template>
