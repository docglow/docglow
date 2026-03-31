// @vitest-environment jsdom
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useTagFilterStore, readTagsFromUrl } from '../stores/tagFilterStore'

function setHash(hash: string) {
  window.location.hash = hash
}

describe('tagFilterStore', () => {
  beforeEach(() => {
    // Reset store to clean state between tests
    useTagFilterStore.setState({ selected: new Set(), mode: 'include' })
    setHash('#/')
    vi.spyOn(window.history, 'replaceState').mockImplementation(() => {})
  })

  describe('toggle', () => {
    it('adds a tag when not selected', () => {
      useTagFilterStore.getState().toggle('finance')

      const { selected } = useTagFilterStore.getState()
      expect(selected.has('finance')).toBe(true)
      expect(selected.size).toBe(1)
    })

    it('removes a tag when already selected', () => {
      useTagFilterStore.getState().toggle('finance')
      useTagFilterStore.getState().toggle('finance')

      const { selected } = useTagFilterStore.getState()
      expect(selected.has('finance')).toBe(false)
      expect(selected.size).toBe(0)
    })

    it('supports multiple tags', () => {
      useTagFilterStore.getState().toggle('finance')
      useTagFilterStore.getState().toggle('marketing')

      const { selected } = useTagFilterStore.getState()
      expect(selected.has('finance')).toBe(true)
      expect(selected.has('marketing')).toBe(true)
      expect(selected.size).toBe(2)
    })

    it('calls history.replaceState to persist to URL', () => {
      useTagFilterStore.getState().toggle('finance')

      expect(window.history.replaceState).toHaveBeenCalled()
      const lastCall = vi.mocked(window.history.replaceState).mock.lastCall!
      expect(lastCall[2]).toContain('tags=finance')
    })
  })

  describe('setMode', () => {
    it('changes mode to exclude', () => {
      useTagFilterStore.getState().setMode('exclude')
      expect(useTagFilterStore.getState().mode).toBe('exclude')
    })

    it('changes mode back to include', () => {
      useTagFilterStore.getState().setMode('exclude')
      useTagFilterStore.getState().setMode('include')
      expect(useTagFilterStore.getState().mode).toBe('include')
    })

    it('persists mode to URL when tags are selected', () => {
      useTagFilterStore.getState().toggle('finance')
      useTagFilterStore.getState().setMode('exclude')

      const lastCall = vi.mocked(window.history.replaceState).mock.lastCall!
      expect(lastCall[2]).toContain('tagMode=exclude')
    })

    it('omits tagMode from URL when mode is include (default)', () => {
      useTagFilterStore.getState().toggle('finance')
      useTagFilterStore.getState().setMode('include')

      const lastCall = vi.mocked(window.history.replaceState).mock.lastCall!
      const url = lastCall[2] as string
      expect(url).not.toContain('tagMode')
    })
  })

  describe('clear', () => {
    it('resets selected tags and mode', () => {
      useTagFilterStore.getState().toggle('finance')
      useTagFilterStore.getState().toggle('marketing')
      useTagFilterStore.getState().setMode('exclude')
      useTagFilterStore.getState().clear()

      const state = useTagFilterStore.getState()
      expect(state.selected.size).toBe(0)
      expect(state.mode).toBe('include')
    })

    it('clears tags from URL', () => {
      useTagFilterStore.getState().toggle('finance')
      useTagFilterStore.getState().clear()

      const lastCall = vi.mocked(window.history.replaceState).mock.lastCall!
      const url = lastCall[2] as string
      expect(url).not.toContain('tags=')
      expect(url).not.toContain('tagMode')
    })
  })

  describe('setFromParams', () => {
    it('sets tags and mode from arrays', () => {
      useTagFilterStore.getState().setFromParams(['a', 'b', 'c'], 'exclude')

      const state = useTagFilterStore.getState()
      expect(state.selected.size).toBe(3)
      expect(state.selected.has('a')).toBe(true)
      expect(state.selected.has('b')).toBe(true)
      expect(state.selected.has('c')).toBe(true)
      expect(state.mode).toBe('exclude')
    })
  })
})

describe('readTagsFromUrl', () => {
  it('returns empty state when no hash params', () => {
    setHash('#/')
    const result = readTagsFromUrl()
    expect(result).toEqual({ tags: [], mode: 'include' })
  })

  it('parses tags from URL', () => {
    setHash('#/?tags=finance,marketing')
    const result = readTagsFromUrl()
    expect(result.tags).toEqual(['finance', 'marketing'])
    expect(result.mode).toBe('include')
  })

  it('parses exclude mode from URL', () => {
    setHash('#/?tags=finance&tagMode=exclude')
    const result = readTagsFromUrl()
    expect(result.tags).toEqual(['finance'])
    expect(result.mode).toBe('exclude')
  })

  it('defaults to include for unknown tagMode values', () => {
    setHash('#/?tags=a&tagMode=invalid')
    const result = readTagsFromUrl()
    expect(result.mode).toBe('include')
  })

  it('filters out empty tag strings', () => {
    setHash('#/?tags=a,,b,')
    const result = readTagsFromUrl()
    expect(result.tags).toEqual(['a', 'b'])
  })

  it('handles hash with path and params', () => {
    setHash('#/lineage?tags=staging,production')
    const result = readTagsFromUrl()
    expect(result.tags).toEqual(['staging', 'production'])
  })
})
