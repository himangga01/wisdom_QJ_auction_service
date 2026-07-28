import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import { router } from '../app/router'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function renderApp() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>,
  )
}

describe('인증 route', () => {
  beforeEach(() => {
    window.sessionStorage.clear()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('session이 없으면 보호 화면 대신 로그인 화면을 연다', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: string | URL | Request) => {
        const url = String(input)
        if (url.endsWith('/auth/bootstrap-status')) {
          return jsonResponse({ bootstrapRequired: false })
        }
        if (url.endsWith('/auth/me')) {
          return jsonResponse(
            {
              detail: {
                code: 'authentication_required',
                message: '인증이 필요합니다.',
              },
            },
            401,
          )
        }
        throw new Error(`unexpected request: ${url}`)
      }),
    )
    await router.navigate('/')

    renderApp()

    expect(
      await screen.findByRole('heading', { name: '로그인' }),
    ).toBeInTheDocument()
  })

  it('최초 관리자 설정이 필요하면 bootstrap 화면을 연다', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: string | URL | Request) => {
        const url = String(input)
        if (url.endsWith('/auth/bootstrap-status')) {
          return jsonResponse({ bootstrapRequired: true })
        }
        if (url.endsWith('/auth/me')) {
          return jsonResponse(
            {
              detail: {
                code: 'authentication_required',
                message: '인증이 필요합니다.',
              },
            },
            401,
          )
        }
        throw new Error(`unexpected request: ${url}`)
      }),
    )
    await router.navigate('/')

    renderApp()

    expect(
      await screen.findByRole('heading', { name: '최초 관리자 설정' }),
    ).toBeInTheDocument()
  })
})
