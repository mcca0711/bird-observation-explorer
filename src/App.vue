<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import ObservationMap from './components/ObservationMap.vue'
import TimelineChart from './components/TimelineChart.vue'
import { loadObservations, type Observation } from './data'

const observations = ref<Observation[]>([])

const selectedCountry = ref('all')
const selectedSpecies = ref('all')
const selectedProtectedArea = ref('all')
const selectedMonth = ref<number | null>(null)

const loading = ref(true)
const errorMessage = ref('')

const countryObservations = computed(() => {
  if (selectedCountry.value === 'all') {
    return observations.value
  }

  return observations.value.filter(
    (observation) => observation.countryCode === selectedCountry.value,
  )
})

const speciesOptions = computed(() => {
  const species = new Map<string, string>()

  for (const observation of countryObservations.value) {
    const label = observation.commonName
      ? `${observation.commonName} · ${observation.scientificName}`
      : observation.scientificName

    species.set(observation.scientificName, label)
  }

  return Array.from(species, ([value, label]) => ({
    value,
    label,
  })).sort((first, second) => first.label.localeCompare(second.label))
})

const selectedSpeciesName = computed(() => {
  if (selectedSpecies.value === 'all') {
    return null
  }

  const observation = observations.value.find(
    (item) => item.scientificName === selectedSpecies.value,
  )

  return (
    observation?.commonName ??
    observation?.scientificName ??
    selectedSpecies.value
  )
})

const speciesObservations = computed(() => {
  if (selectedSpecies.value === 'all') {
    return countryObservations.value
  }

  return countryObservations.value.filter(
    (observation) => observation.scientificName === selectedSpecies.value,
  )
})

const protectedAreaObservations = computed(() => {
  if (selectedProtectedArea.value === 'inside') {
    return speciesObservations.value.filter(
      (observation) => observation.insideProtectedArea,
    )
  }

  if (selectedProtectedArea.value === 'outside') {
    return speciesObservations.value.filter(
      (observation) => !observation.insideProtectedArea,
    )
  }

  return speciesObservations.value
})

const visibleObservations = computed(() => {
  if (selectedMonth.value === null) {
    return protectedAreaObservations.value
  }

  return protectedAreaObservations.value.filter(
    (observation) =>
      Number(observation.date.slice(5, 7)) === selectedMonth.value,
  )
})

const representedSpeciesCount = computed(
  () =>
    new Set(
      visibleObservations.value.map(
        (observation) => observation.scientificName,
      ),
    ).size,
)

const representedRegionsCount = computed(
  () =>
    new Set(
      visibleObservations.value
        .map((observation) => observation.province)
        .filter(Boolean),
    ).size,
)

const protectedAreaRecordCount = computed(
  () =>
    visibleObservations.value.filter(
      (observation) => observation.insideProtectedArea,
    ).length,
)

watch(selectedCountry, () => {
  selectedSpecies.value = 'all'
  selectedProtectedArea.value = 'all'
  selectedMonth.value = null
})

watch(selectedSpecies, () => {
  selectedMonth.value = null
})

watch(selectedProtectedArea, () => {
  selectedMonth.value = null
})

function clearFilters(): void {
  selectedCountry.value = 'all'
  selectedSpecies.value = 'all'
  selectedProtectedArea.value = 'all'
  selectedMonth.value = null
}

onMounted(async () => {
  try {
    observations.value = await loadObservations()
  } catch (error) {
    errorMessage.value =
      error instanceof Error
        ? error.message
        : 'The observation data could not be loaded.'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <main class="min-h-screen bg-slate-950 text-slate-100">
    <header class="border-b border-white/10 px-4 py-6 sm:px-6">
      <p
        class="text-xs font-semibold uppercase tracking-[0.25em] text-emerald-400"
      >
        Bird Observation Explorer
      </p>

      <h1 class="mt-2 text-2xl font-semibold sm:text-3xl">
        Explore sightings across place and time
      </h1>

      <p class="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
        Explore geographic concentration, national park context, and seasonal
        patterns in a controlled sample of 2024 eBird observations from Canada
        and the United States.
      </p>
    </header>

    <section class="grid grid-cols-1 lg:grid-cols-[300px_1fr]">
      <aside
        class="border-b border-white/10 bg-slate-900/60 p-5 lg:border-b-0 lg:border-r"
      >
        <h2 class="font-semibold">Explore the data</h2>

        <label class="mt-5 block">
          <span class="mb-2 block text-sm text-slate-300"> Country </span>

          <select
            v-model="selectedCountry"
            class="w-full rounded-lg border border-white/10 bg-slate-950 px-3 py-2 text-sm text-slate-100"
          >
            <option value="all">Canada and United States</option>

            <option value="CA">Canada</option>

            <option value="US">United States</option>
          </select>
        </label>

        <label class="mt-5 block">
          <span class="mb-2 block text-sm text-slate-300"> Species </span>

          <select
            v-model="selectedSpecies"
            class="w-full rounded-lg border border-white/10 bg-slate-950 px-3 py-2 text-sm text-slate-100"
          >
            <option value="all">All species</option>

            <option
              v-for="species in speciesOptions"
              :key="species.value"
              :value="species.value"
            >
              {{ species.label }}
            </option>
          </select>
        </label>

        <label class="mt-5 block">
          <span class="mb-2 block text-sm text-slate-300">
            National park status
          </span>

          <select
            v-model="selectedProtectedArea"
            class="w-full rounded-lg border border-white/10 bg-slate-950 px-3 py-2 text-sm text-slate-100"
          >
            <option value="all">All observations</option>

            <option value="inside">Inside mapped park-system areas</option>

            <option value="outside">Outside mapped park-system areas</option>
          </select>
        </label>

        <div
          class="mt-6 grid grid-cols-2 gap-3 border-t border-white/10 pt-5 lg:grid-cols-1"
        >
          <div class="rounded-xl border border-white/10 bg-slate-950/70 p-3">
            <p
              class="text-xs font-medium uppercase tracking-wide text-slate-500"
            >
              Visible records
            </p>

            <p class="mt-2 text-2xl font-semibold tabular-nums text-slate-50">
              {{ visibleObservations.length.toLocaleString() }}
            </p>
          </div>

          <div class="rounded-xl border border-white/10 bg-slate-950/70 p-3">
            <p
              class="text-xs font-medium uppercase tracking-wide text-slate-500"
            >
              Inside mapped park-system areas
            </p>

            <p class="mt-2 text-xl font-semibold tabular-nums text-slate-50">
              {{ protectedAreaRecordCount.toLocaleString() }}
            </p>
          </div>

          <div class="rounded-xl border border-white/10 bg-slate-950/70 p-3">
            <p
              class="text-xs font-medium uppercase tracking-wide text-slate-500"
            >
              Species represented
            </p>

            <p class="mt-2 text-xl font-semibold tabular-nums text-slate-50">
              {{ representedSpeciesCount.toLocaleString() }}
            </p>
          </div>

          <div class="rounded-xl border border-white/10 bg-slate-950/70 p-3">
            <p
              class="text-xs font-medium uppercase tracking-wide text-slate-500"
            >
              States and provinces
            </p>

            <p class="mt-2 text-xl font-semibold tabular-nums text-slate-50">
              {{ representedRegionsCount.toLocaleString() }}
            </p>
          </div>
        </div>

        <button
          type="button"
          class="mt-5 w-full rounded-lg border border-white/10 px-3 py-2 text-sm hover:bg-white/5"
          @click="clearFilters"
        >
          Clear filters
        </button>

        <p class="mt-6 text-xs leading-5 text-slate-500">
          National park matches were calculated by checking whether each
          observation point falls inside an official Canadian or United States
          national park boundary.
        </p>

        <p class="mt-3 text-xs leading-5 text-slate-500">
          Records are a controlled sample of reported sightings. They do not
          represent complete bird populations or individual migration routes.
        </p>
      </aside>

      <section class="min-w-0 bg-slate-900">
        <div v-if="loading" class="grid min-h-[500px] place-items-center">
          <p class="text-sm text-slate-400">Loading observations</p>
        </div>

        <div
          v-else-if="errorMessage"
          class="grid min-h-[500px] place-items-center p-6"
          role="alert"
        >
          <p class="text-sm text-red-300">
            {{ errorMessage }}
          </p>
        </div>

        <template v-else>
          <div
            v-if="visibleObservations.length === 0"
            class="grid min-h-[400px] place-items-center p-6"
          >
            <div class="text-center">
              <p class="font-medium text-slate-200">No observations found</p>

              <p class="mt-2 text-sm text-slate-400">
                Change or clear the current filters.
              </p>
            </div>
          </div>

          <ObservationMap v-else :observations="visibleObservations" />

          <TimelineChart
            :observations="protectedAreaObservations"
            :species-name="selectedSpeciesName"
            :selected-month="selectedMonth"
            @select-month="selectedMonth = $event"
          />
        </template>
      </section>
    </section>
  </main>
</template>
