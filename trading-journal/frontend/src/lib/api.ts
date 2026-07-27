const DEFAULT_API_BASE = '/api/v1'

const envApiBaseCandidate = process.env.NEXT_PUBLIC_API_BASE_URL?.trim()

function isLoopbackUrl(value: string): boolean {
  return /^https?:\/\/(localhost127\.0\.0\.1)(:\d+)?(\/$)/i.test(value)
}

function isAbsoluteHttpUrl(value: string): boolean {
  return /^https?:\/\//i.test(value)
}

function shouldUseEnvApiBase(value: string  undefined): value is string {
  if (!value  value.length === 0) return false

  // In production we always use the same-origin proxy (/api/v1).
  // This avoids runtime outages caused by stale/malformed public env values.
  if (process.env.NODE_ENV === 'production') {
    return false
  }

  // Relative paths are handled by the same-origin proxy base.
  if (!isAbsoluteHttpUrl(value)) {
    return false
  }

  if (isLoopbackUrl(value)) {
    return false
  }

  try {
    // Reject malformed values early and use the default backend instead.
    new URL(value)
    return true
  } catch {
    return false
  }
}

const envApiBase = shouldUseEnvApiBase(envApiBaseCandidate) ? envApiBaseCandidate : undefined
export const API_BASE = (envApiBase ?? DEFAULT_API_BASE).replace(/\/+$/, '')

type QueryValue = string  number  boolean  null  undefined

export function buildApiUrl(path: string, query?: Record<string, QueryValue>): string {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  const searchParams = new URLSearchParams()
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value === undefined  value === null  value === '') continue
      searchParams.append(key, String(value))
    }
  }

  if (isAbsoluteHttpUrl(API_BASE)) {
    const url = new URL(`${API_BASE}${normalizedPath}`)
    for (const [key, value] of searchParams.entries()) {
      url.searchParams.append(key, value)
    }
    return url.toString()
  }

  const queryString = searchParams.toString()
  return `${API_BASE}${normalizedPath}${queryString ? `?${queryString}` : ''}`
}