export interface ApiFile {
  blob: Blob
  filename: string
}

interface ApiErrorPayload {
  detail?: string | {
    code?: string
    message?: string
    [key: string]: unknown
  }
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string | null
  readonly payload: unknown

  constructor(message: string, status: number, code: string | null, payload: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.payload = payload
  }
}

const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim() || '/api'
export const API_BASE_URL = configuredBaseUrl.replace(/\/$/, '')

function createUrl(path: string, params?: Record<string, string | number | boolean | null | undefined>): string {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  const base = /^https?:\/\//.test(API_BASE_URL) ? API_BASE_URL : `${window.location.origin}${API_BASE_URL}`
  const url = new URL(`${base}${normalizedPath}`)

  Object.entries(params ?? {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') url.searchParams.set(key, String(value))
  })
  return url.toString()
}

function errorMessage(payload: ApiErrorPayload | null, fallback: string): { message: string; code: string | null } {
  if (typeof payload?.detail === 'string') return { message: payload.detail, code: null }
  if (payload?.detail && typeof payload.detail === 'object') {
    return {
      message: typeof payload.detail.message === 'string' ? payload.detail.message : fallback,
      code: typeof payload.detail.code === 'string' ? payload.detail.code : null,
    }
  }
  return { message: fallback, code: null }
}

async function throwApiError(response: Response): Promise<never> {
  let payload: ApiErrorPayload | null = null
  try {
    payload = await response.json() as ApiErrorPayload
  } catch {
    payload = null
  }
  const fallback = `요청을 처리하지 못했습니다. (${response.status})`
  const parsed = errorMessage(payload, fallback)
  throw new ApiError(parsed.message, response.status, parsed.code, payload)
}

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {},
  params?: Record<string, string | number | boolean | null | undefined>,
): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.body !== undefined && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  headers.set('Accept', 'application/json')

  const response = await fetch(createUrl(path, params), { ...init, headers })
  if (!response.ok) return throwApiError(response)
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

function getDownloadFilename(response: Response, fallback: string): string {
  const disposition = response.headers.get('Content-Disposition') ?? ''
  const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1]
  if (encoded) {
    try {
      return decodeURIComponent(encoded)
    } catch {
      return encoded
    }
  }
  return disposition.match(/filename="?([^";]+)"?/i)?.[1] ?? fallback
}

export async function apiFile(
  path: string,
  params?: Record<string, string | number | boolean | null | undefined>,
): Promise<ApiFile> {
  const response = await fetch(createUrl(path, params), {
    headers: { Accept: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' },
  })
  if (!response.ok) return throwApiError(response)
  return {
    blob: await response.blob(),
    filename: getDownloadFilename(response, 'naver-land-export.xlsx'),
  }
}

export function saveApiFile(file: ApiFile): void {
  const objectUrl = URL.createObjectURL(file.blob)
  const anchor = document.createElement('a')
  anchor.href = objectUrl
  anchor.download = file.filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(objectUrl)
}
