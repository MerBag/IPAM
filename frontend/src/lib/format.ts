export function formatNumber(value: number | string | null | undefined) {
  if (value === null || value === undefined || value === '') return '—'
  const numeric = Number(value)
  return Number.isFinite(numeric) ? new Intl.NumberFormat().format(numeric) : String(value)
}

export function formatPercent(value: number | string | null | undefined) {
  if (value === null || value === undefined || value === '') return '0%'
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return '0%'
  const clamped = Math.min(100, Math.max(0, numeric))
  return `${new Intl.NumberFormat(undefined, { maximumFractionDigits: clamped > 0 && clamped < 10 ? 1 : 0 }).format(clamped)}%`
}

export function percentValue(value: number | string | null | undefined) {
  if (value === null || value === undefined || value === '') return 0
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return 0
  return Math.min(100, Math.max(0, numeric))
}

export function formatDate(value?: string | null, includeTime = true) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    ...(includeTime ? { hour: 'numeric', minute: '2-digit' } : {}),
  }).format(date)
}

export function initials(name?: string) {
  if (!name) return 'RN'
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0])
    .join('')
    .toUpperCase()
}

export function titleCase(value?: string) {
  if (!value) return 'Unknown'
  return value.replace(/[_-]/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}
