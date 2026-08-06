<script setup lang="ts">
import { computed } from 'vue'
import {
  max,
  scaleBand,
  scaleLinear,
} from 'd3'

import type { Observation } from '../data'

const props = defineProps<{
  observations: Observation[]
  speciesName: string | null
  selectedMonth: number | null
}>()

const emit = defineEmits<{
  selectMonth: [month: number | null]
}>()

const monthNames = [
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'May',
  'Jun',
  'Jul',
  'Aug',
  'Sep',
  'Oct',
  'Nov',
  'Dec',
]

const chartLeft = 65
const chartRight = 935
const chartTop = 30
const chartBottom = 190

const monthlyCounts = computed(() => {
  const counts = monthNames.map(
    (label, index) => ({
      month: index + 1,
      label,
      count: 0,
    }),
  )

  for (const observation of props.observations) {
    const month = Number(
      observation.date.slice(5, 7),
    )

    if (month >= 1 && month <= 12) {
      counts[month - 1].count += 1
    }
  }

  return counts
})

const totalRecords = computed(() =>
  monthlyCounts.value.reduce(
    (total, item) =>
      total + item.count,
    0,
  ),
)

const representedMonthCount = computed(
  () =>
    monthlyCounts.value.filter(
      item => item.count > 0,
    ).length,
)

const highestCount = computed(
  () =>
    max(
      monthlyCounts.value,
      item => item.count,
    ) ?? 0,
)

const peakMonths = computed(() => {
  if (highestCount.value === 0) {
    return []
  }

  return monthlyCounts.value.filter(
    item =>
      item.count === highestCount.value,
  )
})

function formatMonthList(
  labels: string[],
): string {
  if (labels.length === 0) {
    return ''
  }

  if (labels.length === 1) {
    return labels[0]
  }

  if (labels.length === 2) {
    return `${labels[0]} and ${labels[1]}`
  }

  return (
    `${labels.slice(0, -1).join(', ')}, ` +
    `and ${labels.at(-1)}`
  )
}

const peakSummary = computed(() => {
  const labels = peakMonths.value.map(
    item => item.label,
  )

  const countLabel =
    highestCount.value === 1
      ? '1 record'
      : `${highestCount.value} records`

  if (labels.length === 1) {
    return (
      `Peak month ${labels[0]} ` +
      `with ${countLabel}.`
    )
  }

  return (
    `Peak months ${formatMonthList(labels)} ` +
    `with ${countLabel} each.`
  )
})

const xScale = computed(() =>
  scaleBand<number>()
    .domain(
      monthlyCounts.value.map(
        item => item.month,
      ),
    )
    .range([
      chartLeft,
      chartRight,
    ])
    .padding(0.28),
)

const yScale = computed(() =>
  scaleLinear()
    .domain([
      0,
      Math.max(
        1,
        highestCount.value,
      ),
    ])
    .nice()
    .range([
      chartBottom,
      chartTop,
    ]),
)

const yTicks = computed(() => {
  const highest = highestCount.value

  if (highest <= 5) {
    return Array.from(
      {
        length:
          Math.max(1, highest) + 1,
      },
      (_, index) => index,
    )
  }

  const step = Math.ceil(
    highest / 4,
  )

  const ticks: number[] = []

  for (
    let value = 0;
    value <= highest;
    value += step
  ) {
    ticks.push(value)
  }

  if (
    ticks[ticks.length - 1] !==
    highest
  ) {
    ticks.push(highest)
  }

  return ticks
})

function barX(month: number): number {
  return (
    xScale.value(month) ??
    chartLeft
  )
}

function barY(count: number): number {
  return yScale.value(count)
}

function barHeight(count: number): number {
  return (
    chartBottom -
    yScale.value(count)
  )
}

function selectMonth(
  month: number,
  count: number,
): void {
  if (count === 0) {
    return
  }

  emit(
    'selectMonth',
    props.selectedMonth === month
      ? null
      : month,
  )
}

function handleMonthChange(
  event: Event,
): void {
  const value = (
    event.target as HTMLSelectElement
  ).value

  emit(
    'selectMonth',
    value === 'all'
      ? null
      : Number(value),
  )
}
</script>

<template>
  <section
    class="border-t border-white/10 bg-slate-950 p-4 sm:p-5"
  >
    <div
      v-if="speciesName === null"
      class="grid min-h-[250px] place-items-center py-8"
    >
      <div class="max-w-xl text-center">
        <p
          class="text-xs font-medium uppercase tracking-[0.2em] text-emerald-400"
        >
          Seasonal exploration
        </p>

        <h2
          class="mt-3 text-xl font-semibold"
        >
          Choose a species to reveal its seasonal pattern
        </h2>

        <p
          class="mt-3 text-sm leading-6 text-slate-400"
        >
          The dataset uses a fixed monthly sampling limit, so an all-species
          chart would mostly reproduce that limit. Selecting one species shows
          how its sampled records are distributed across the year.
        </p>
      </div>
    </div>

    <template v-else>
      <div
        class="mb-4 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between"
      >
        <div>
          <p
            class="text-xs font-medium uppercase tracking-[0.18em] text-emerald-400"
          >
            Seasonal pattern
          </p>

          <h2
            class="mt-1 text-lg font-semibold"
          >
            {{ speciesName }}
          </h2>

          <p
            class="mt-1 text-sm text-slate-400"
          >
            {{
              totalRecords.toLocaleString()
            }}
            sampled records across
            {{
              representedMonthCount
            }}
            of 12 months
          </p>

          <p
            v-if="highestCount > 0"
            class="mt-1 text-sm text-slate-400"
          >
            {{ peakSummary }}
          </p>

          <p
            v-if="
              totalRecords > 0 &&
              totalRecords < 20
            "
            class="mt-2 max-w-xl text-sm text-amber-300"
          >
            This species has a small sample. Treat the visible pattern as
            limited evidence rather than a strong seasonal conclusion.
          </p>
        </div>

        <div
          class="flex flex-wrap items-end gap-3"
        >
          <label class="block">
            <span
              class="mb-1 block text-xs font-medium text-slate-400"
            >
              Filter map by month
            </span>

            <select
              :value="
                selectedMonth ?? 'all'
              "
              class="rounded-lg border border-white/10 bg-slate-900 px-3 py-2 text-sm text-slate-100"
              @change="
                handleMonthChange
              "
            >
              <option value="all">
                All months
              </option>

              <option
                v-for="(
                  month,
                  index
                ) in monthNames"
                :key="month"
                :value="index + 1"
              >
                {{ month }}
              </option>
            </select>
          </label>

          <button
            v-if="
              selectedMonth !== null
            "
            type="button"
            class="rounded-lg border border-white/10 px-3 py-2 text-sm hover:bg-white/5"
            @click="
              emit(
                'selectMonth',
                null,
              )
            "
          >
            Clear month
          </button>
        </div>
      </div>

      <svg
        viewBox="0 0 960 235"
        class="h-auto w-full"
        role="img"
        :aria-label="
          `Monthly sampled records for ${speciesName}`
        "
      >
        <desc>
          A bar chart showing the number of sampled observation records in each
          month.
        </desc>

        <text
          x="18"
          y="115"
          text-anchor="middle"
          transform="rotate(-90 18 115)"
          class="fill-slate-500 text-xs"
        >
          Sampled records
        </text>

        <g
          v-for="tick in yTicks"
          :key="tick"
        >
          <line
            :x1="chartLeft"
            :x2="chartRight"
            :y1="yScale(tick)"
            :y2="yScale(tick)"
            stroke="currentColor"
            class="text-white/10"
          />

          <text
            :x="chartLeft - 12"
            :y="
              yScale(tick) + 4
            "
            text-anchor="end"
            class="fill-slate-500 text-xs"
          >
            {{ tick }}
          </text>
        </g>

        <g
          v-for="item in monthlyCounts"
          :key="item.month"
          :role="
            item.count > 0
              ? 'button'
              : undefined
          "
          :tabindex="
            item.count > 0
              ? 0
              : -1
          "
          :aria-label="
            `${item.label}, ${item.count} sampled records`
          "
          :class="
            item.count > 0
              ? 'cursor-pointer'
              : ''
          "
          @click="
            selectMonth(
              item.month,
              item.count,
            )
          "
          @keydown.enter="
            selectMonth(
              item.month,
              item.count,
            )
          "
          @keydown.space.prevent="
            selectMonth(
              item.month,
              item.count,
            )
          "
        >
          <rect
            :x="barX(item.month)"
            :y="barY(item.count)"
            :width="
              xScale.bandwidth()
            "
            :height="
              barHeight(item.count)
            "
            rx="4"
            :class="
              item.month ===
              selectedMonth
                ? 'fill-amber-400'
                : 'fill-emerald-400 hover:fill-emerald-300'
            "
          >
            <title>
              {{ item.label }}:
              {{
                item.count.toLocaleString()
              }}
              sampled observations
            </title>
          </rect>

          <text
            v-if="item.count > 0"
            :x="
              barX(item.month) +
              xScale.bandwidth() / 2
            "
            :y="
              barY(item.count) - 9
            "
            text-anchor="middle"
            class="pointer-events-none fill-slate-300 text-xs"
          >
            {{
              item.count.toLocaleString()
            }}
          </text>

          <text
            :x="
              barX(item.month) +
              xScale.bandwidth() / 2
            "
            y="216"
            text-anchor="middle"
            class="pointer-events-none fill-slate-400 text-xs"
          >
            {{ item.label }}
          </text>
        </g>
      </svg>

      <p
        class="mt-2 text-xs text-slate-500"
      >
        Counts represent records in the controlled sample, not bird population
        size, abundance, or migration volume.
      </p>
    </template>
  </section>
</template>