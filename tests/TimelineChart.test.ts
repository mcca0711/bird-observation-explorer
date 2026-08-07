// @vitest-environment jsdom

import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import TimelineChart from '../src/components/TimelineChart.vue'
import type { Observation } from '../src/data'

function makeObservation(id: string, date: string): Observation {
  return {
    id,
    scientificName: 'Branta canadensis',
    commonName: 'Canada Goose',
    date,
    countryCode: 'CA',
    province: 'Ontario',
    locality: 'Ottawa',
    protectedAreaName: null,
    insideProtectedArea: false,
    latitude: 45.42,
    longitude: -75.69,
  }
}

const observations: Observation[] = [
  makeObservation('1', '2024-01-10'),
  makeObservation('2', '2024-01-20'),
  makeObservation('3', '2024-02-15'),
]

describe('TimelineChart', () => {
  it('calculates monthly observation counts', () => {
    const wrapper = mount(TimelineChart, {
      props: {
        observations,
        speciesName: 'Canada Goose',
        selectedMonth: null,
      },
    })

    const labels = wrapper.findAll('title').map((title) => title.text())

    expect(labels).toContain('Jan: 2 sampled observations')

    expect(labels).toContain('Feb: 1 sampled observations')
  })

  it('reports the selected month', async () => {
    const wrapper = mount(TimelineChart, {
      props: {
        observations,
        speciesName: 'Canada Goose',
        selectedMonth: null,
      },
    })

    await wrapper.get('select').setValue('2')

    expect(wrapper.emitted('selectMonth')).toEqual([[2]])
  })

  it('clears the selected month', async () => {
    const wrapper = mount(TimelineChart, {
      props: {
        observations,
        speciesName: 'Canada Goose',
        selectedMonth: 2,
      },
    })

    await wrapper.get('button').trigger('click')

    expect(wrapper.emitted('selectMonth')).toEqual([[null]])
  })

  it('explains why no chart appears for all species', () => {
    const wrapper = mount(TimelineChart, {
      props: {
        observations,
        speciesName: null,
        selectedMonth: null,
      },
    })

    expect(wrapper.text()).toContain(
      'Choose a species to reveal its seasonal pattern',
    )

    expect(wrapper.find('svg').exists()).toBe(false)
  })

  it('reports all months tied for the peak count', () => {
    const tiedObservations = [
      makeObservation('1', '2024-06-10'),
      makeObservation('2', '2024-07-10'),
      makeObservation('3', '2024-10-10'),
    ]

    const wrapper = mount(TimelineChart, {
      props: {
        observations: tiedObservations,
        speciesName: 'Acadian Flycatcher',
        selectedMonth: null,
      },
    })

    expect(wrapper.text()).toContain(
      'Peak months Jun, Jul, and Oct with 1 record each.',
    )
  })
})
