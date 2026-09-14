import type { Paginated } from '../types'

const TOKEN_KEY = 'merbag.access_token'

export class ApiError extends Error {
  status: number
  details?: unknown

  constructor(message: string, status: number, details?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.details = details
  }
}

export const authToken = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (token: string) => localStorage.setItem(TOKEN_KEY, token),
  clear: () => localStorage.removeItem(TOKEN_KEY),
}

type RequestOptions = Omit<RequestInit, 'body'> & { body?: unknown }

function errorMessage(payload: unknown, fallback: string) {
  if (typeof payload === 'string' && payload.trim()) return payload
  if (payload && typeof payload === 'object') {
    const candidate = payload as Record<string, unknown>
    if (typeof candidate.detail === 'string') return candidate.detail
    if (typeof candidate.message === 'string') return candidate.message
    if (Array.isArray(candidate.detail)) {
      return candidate.detail
        .map((item) => (item && typeof item === 'object' && 'msg' in item ? String(item.msg) : String(item)))
        .join(', ')
    }
  }
  return fallback
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const token = authToken.get()
  const headers = new Headers(options.headers)
  headers.set('Accept', 'application/json')
  if (options.body !== undefined) headers.set('Content-Type', 'application/json')
  if (token) headers.set('Authorization', `Bearer ${token}`)

  const response = await fetch(path.startsWith('/api') ? path : `/api${path}`, {
    ...options,
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  })

  if (response.status === 401) {
    authToken.clear()
    window.dispatchEvent(new Event('merbag:unauthorized'))
  }

  const text = await response.text()
  let payload: unknown
  try {
    payload = text ? JSON.parse(text) : undefined
  } catch {
    payload = text
  }

  if (!response.ok) {
    throw new ApiError(errorMessage(payload, `Request failed (${response.status})`), response.status, payload)
  }
  return payload as T
}

export function queryString(params: Record<string, string | number | boolean | null | undefined>) {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') query.set(key, String(value))
  })
  const result = query.toString()
  return result ? `?${result}` : ''
}

export function unwrapList<T>(payload: unknown): T[] {
  if (Array.isArray(payload)) return payload as T[]
  if (!payload || typeof payload !== 'object') return []
  const record = payload as Record<string, unknown>
  for (const key of ['items', 'results', 'data', 'prefixes', 'subnets', 'addresses', 'ip_addresses', 'devices', 'customers', 'routers', 'logs']) {
    if (Array.isArray(record[key])) return record[key] as T[]
  }
  return []
}

export function unwrapPage<T>(payload: unknown, fallbackPage = 1, fallbackSize = 25): Paginated<T> {
  const items = unwrapList<T>(payload)
  const record = payload && typeof payload === 'object' && !Array.isArray(payload) ? (payload as Record<string, unknown>) : {}
  const total = Number(record.total ?? record.count ?? items.length)
  const page = Number(record.page ?? record.current_page ?? fallbackPage)
  const pageSize = Number(record.page_size ?? record.per_page ?? fallbackSize)
  const pages = Number(record.pages ?? record.total_pages ?? Math.max(1, Math.ceil(total / pageSize)))
  return { items, total, page, page_size: pageSize, pages }
}

export function normalizeIp<T extends { address?: string; ip_address?: string }>(ip: T) {
  return { ...ip, address: ip.address || ip.ip_address || '' }
}
