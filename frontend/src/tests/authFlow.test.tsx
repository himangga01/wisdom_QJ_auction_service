import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider, useAuth } from '../state/AuthProvider'
import {
  ACTIVE_ANALYSIS_SESSION_KEY,
  writeActiveAnalysisSession,
} from '../state/analysisRunSession'

const adminAuth = {
  user: {
    id: '1e82d03f-8c33-4d03-bec3-e7656f1c8696',
    email: 'admin@example.com',
    displayName: '관리자',
    role: 'admin',
  },
  expiresAt: '2026-07-29T20:00:00+09:00',
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function AuthProbe() {
  const auth = useAuth()
  return (
    <>
      <p>{auth.status}</p>
      <p>{auth.user?.displayName ?? '사용자 없음'}</p>
      <button type="button" onClick={() => void auth.logout()}>
        로그아웃
      </button>
    </>
  )
}

function renderAuth(queryClient: QueryClient, child: ReactNode = <AuthProbe />) {
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>{child}</AuthProvider>
    </QueryClientProvider>,
  )
}

describe('AuthProvider', () => {
  beforeEach(() => {
    window.sessionStorage.clear()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('live 시작 시 bootstrap 상태와 현재 session을 확인한다', async () => {
    const fetchMock = vi.fn(async (input: string | URL | Request) => {
      const url = String(input)
      if (url.endsWith('/auth/bootstrap-status')) {
        return jsonResponse({ bootstrapRequired: false })
      }
      if (url.endsWith('/auth/me')) return jsonResponse(adminAuth)
      throw new Error(`unexpected request: ${url}`)
    })
    vi.stubGlobal('fetch', fetchMock)
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })

    renderAuth(queryClient)

    expect(await screen.findByText('관리자')).toBeInTheDocument()
    expect(screen.getByText('authenticated')).toBeInTheDocument()
    expect(
      fetchMock.mock.calls.some(([input]) =>
        String(input).endsWith('/auth/bootstrap-status'),
      ),
    ).toBe(true)
    expect(
      fetchMock.mock.calls.filter(([input]) =>
        String(input).endsWith('/auth/me'),
      ),
    ).toHaveLength(1)
  })

  it('같은 session 복원 시 진행 중인 run 복원 키를 유지한다', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: string | URL | Request) => {
        const url = String(input)
        if (url.endsWith('/auth/bootstrap-status')) {
          return jsonResponse({ bootstrapRequired: false })
        }
        if (url.endsWith('/auth/me')) return jsonResponse(adminAuth)
        throw new Error(`unexpected request: ${url}`)
      }),
    )
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })
    writeActiveAnalysisSession('62ee124a-8012-4cf5-828a-10c2c88037f6')

    renderAuth(queryClient)

    await screen.findByText('관리자')
    expect(
      window.sessionStorage.getItem(ACTIVE_ANALYSIS_SESSION_KEY),
    ).not.toBeNull()
  })

  it('logout 시 사용자 cache와 활성 run session을 모두 정리한다', async () => {
    const fetchMock = vi.fn(async (input: string | URL | Request) => {
      const url = String(input)
      if (url.endsWith('/auth/bootstrap-status')) {
        return jsonResponse({ bootstrapRequired: false })
      }
      if (url.endsWith('/auth/me')) return jsonResponse(adminAuth)
      if (url.endsWith('/auth/logout')) return new Response(null, { status: 204 })
      throw new Error(`unexpected request: ${url}`)
    })
    vi.stubGlobal('fetch', fetchMock)
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })
    queryClient.setQueryData(['apartments'], { items: ['private'] })
    writeActiveAnalysisSession('62ee124a-8012-4cf5-828a-10c2c88037f6')
    const user = userEvent.setup()
    renderAuth(queryClient)
    await screen.findByText('관리자')

    await user.click(screen.getByRole('button', { name: '로그아웃' }))

    await waitFor(() =>
      expect(screen.getByText('unauthenticated')).toBeInTheDocument(),
    )
    expect(queryClient.getQueryData(['apartments'])).toBeUndefined()
    expect(
      window.sessionStorage.getItem(ACTIVE_ANALYSIS_SESSION_KEY),
    ).toBeNull()
  })
})
