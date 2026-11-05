import { describe, it, expect } from 'vitest'
import { buildResourcePath, getResourcePageTypeFromId } from '../utils/resourceRoutes'

describe('resourceRoutes', () => {
  it('routes each resource type to its page', () => {
    expect(getResourcePageTypeFromId('model.p.orders')).toBe('model')
    expect(getResourcePageTypeFromId('seed.p.countries')).toBe('model')
    expect(getResourcePageTypeFromId('source.p.raw.orders')).toBe('source')
    expect(getResourcePageTypeFromId('exposure.p.dash')).toBe('exposure')
    expect(getResourcePageTypeFromId('metric.p.revenue')).toBe('metric')
  })

  it('builds an encoded metric path', () => {
    expect(buildResourcePath('metric.p.revenue')).toBe('/metric/metric.p.revenue')
  })
})
