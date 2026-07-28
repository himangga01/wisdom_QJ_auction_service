import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  apiFile,
  apiRequest,
  registerUnauthorizedHandler,
} from '../api/client'

describe('인증 API client 계약', () => {
  beforeEach(() => {
    document.cookie = 'wisdom_csrf=csrf%20token; Path=/'
  })

  afterEach(() => {
    registerUnauthorizedHandler(null)
    vi.unstubAllGlobals()
    document.cookie = 'wisdom_csrf=; Max-Age=0; Path=/'
  })

  it('mutating 요청에 same-origin credentials와 CSRF header를 보낸다', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(null, { status: 204 }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await apiRequest<void>('/auth/logout', { method: 'POST' })

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(init.credentials).toBe('same-origin')
    expect(new Headers(init.headers).get('X-CSRF-Token')).toBe('csrf token')
  })

  it('파일 요청에도 same-origin credentials를 사용한다', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(new Blob(['file']), {
        status: 200,
        headers: { 'Content-Disposition': 'attachment; filename="result.xlsx"' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await apiFile('/exports/source.xlsx')

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(init.credentials).toBe('same-origin')
  })

  it('401 응답 시 전역 인증 만료 handler를 호출한다', async () => {
    const onUnauthorized = vi.fn()
    registerUnauthorizedHandler(onUnauthorized)
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            detail: {
              code: 'authentication_required',
              message: '인증이 필요합니다.',
            },
          }),
          {
            status: 401,
            headers: { 'Content-Type': 'application/json' },
          },
        ),
      ),
    )

    await expect(apiRequest('/apartments')).rejects.toMatchObject({
      status: 401,
      code: 'authentication_required',
    })
    expect(onUnauthorized).toHaveBeenCalledOnce()
  })
})
