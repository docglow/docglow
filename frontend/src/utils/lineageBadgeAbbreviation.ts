import type { LineageBadgeConfig } from '../types'

function middleEllipsis(s: string, max: number): string {
  if (s.length <= max) return s
  const keep = max - 1
  const head = Math.ceil(keep * 0.55)
  const tail = Math.floor(keep * 0.45)
  return s.slice(0, head) + '…' + s.slice(-tail)
}

function smartAbbr(s: string, max: number): string {
  if (s.length <= max) return s
  return middleEllipsis(s, max)
}

function truncateStart(s: string, max: number): string {
  if (s.length <= max) return s
  if (max <= 1) return '…'
  return s.slice(0, max - 1) + '…'
}

export function applyBadgeAbbreviation(
  s: string,
  max: number,
  strategy: LineageBadgeConfig['abbreviation'],
): string {
  switch (strategy) {
    case 'none':     return s
    case 'truncate': return truncateStart(s, max)
    case 'middle':   return middleEllipsis(s, max)
    case 'smart':
    default:         return smartAbbr(s, max)
  }
}
