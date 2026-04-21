import { describe, it, expect } from 'vitest'
import { formatFqn } from '../utils/formatting'

describe('formatFqn', () => {
  it('joins database, schema, and name with dots', () => {
    expect(formatFqn({ database: 'analytics', schema: 'public', name: 'orders' })).toBe(
      'analytics.public.orders'
    )
  })

  it('joins database and schema when name is omitted', () => {
    expect(formatFqn({ database: 'analytics', schema: 'public' })).toBe('analytics.public')
  })

  it('drops empty database (dbt-glue / dbt-spark case)', () => {
    expect(formatFqn({ database: '', schema: 'my_schema', name: 'orders' })).toBe(
      'my_schema.orders'
    )
  })

  it('drops empty database with no name', () => {
    expect(formatFqn({ database: '', schema: 'my_schema' })).toBe('my_schema')
  })

  it('drops empty schema', () => {
    expect(formatFqn({ database: 'db', schema: '', name: 'orders' })).toBe('db.orders')
  })

  it('returns empty string when all segments are empty', () => {
    expect(formatFqn({ database: '', schema: '' })).toBe('')
  })

  it('treats null and undefined as empty', () => {
    expect(formatFqn({ database: null, schema: 'public', name: 'orders' })).toBe(
      'public.orders'
    )
    expect(formatFqn({ database: undefined, schema: 'public' })).toBe('public')
  })
})
