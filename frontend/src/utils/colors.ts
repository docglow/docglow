export type TestStatus = 'pass' | 'fail' | 'warn' | 'error' | 'not_run' | 'none'
export type ResourceType = 'model' | 'source' | 'seed' | 'snapshot' | 'exposure' | 'metric'

export function statusColor(status: TestStatus): string {
  switch (status) {
    case 'pass': return 'text-success'
    case 'fail':
    case 'error': return 'text-danger'
    case 'warn': return 'text-warning'
    case 'not_run':
    case 'none':
    default: return 'text-neutral'
  }
}

export function statusBgColor(status: TestStatus): string {
  switch (status) {
    case 'pass': return 'bg-success/10 text-success'
    case 'fail':
    case 'error': return 'bg-danger/10 text-danger'
    case 'warn': return 'bg-warning/10 text-warning'
    case 'not_run':
    case 'none':
    default: return 'bg-neutral/10 text-neutral'
  }
}

export function resourceColor(type: ResourceType): string {
  switch (type) {
    case 'model': return 'text-primary'
    case 'source': return 'text-success'
    case 'exposure': return 'text-warning'
    case 'seed': return 'text-neutral'
    case 'snapshot': return 'text-secondary'
    case 'metric': return 'text-secondary'
    default: return 'text-neutral'
  }
}

export function materializationLabel(mat: string): string {
  switch (mat) {
    case 'table': return 'Table'
    case 'view': return 'View'
    case 'incremental': return 'Incremental'
    case 'ephemeral': return 'Ephemeral'
    default: return mat || 'Unknown'
  }
}
