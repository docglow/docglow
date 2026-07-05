import { describe, expect, it } from 'vitest'
import { applyBadgeAbbreviation } from '../utils/lineageBadgeAbbreviation'

describe('applyBadgeAbbreviation', () => {
  it('keeps smart abbreviations readable for long snake case labels', () => {
    const label = 'subscription_readiness_review_delivery_trust_report'
    const abbreviated = applyBadgeAbbreviation(label, 30, 'smart')

    expect(abbreviated).toBe('subscription_rea…_trust_report')
    expect(abbreviated).not.toContain('·')
  })

  it('preserves the configured explicit strategies', () => {
    const label = 'subscription_readiness_review_delivery_trust_report'

    expect(applyBadgeAbbreviation(label, 18, 'truncate')).toBe('subscription_read…')
    expect(applyBadgeAbbreviation(label, 18, 'middle')).toBe('subscripti…_report')
    expect(applyBadgeAbbreviation(label, 18, 'none')).toBe(label)
  })
})
