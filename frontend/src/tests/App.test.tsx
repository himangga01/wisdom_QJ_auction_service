import { act, render, renderHook, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from '../App'
import { RegistrationCard } from '../pages/ListingDetailPage'
import { demoDashboardDataset } from '../mocks/demoRealEstate'
import { useDemoDashboard } from '../state/useDemoDashboard'
import { USE_DEMO_DATA } from '../state/AnalysisProvider'
import { router } from '../app/router'

const VALID_DEMO_URL = 'https://fin.land.naver.com/map?demo=true'

function renderApp() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>,
  )
}

describe('App', () => {
  beforeEach(async () => {
    vi.stubGlobal('fetch', vi.fn(async (input: string | URL | Request) => {
      const url = String(input)
      if (url.endsWith('/auth/bootstrap-status')) {
        return new Response(JSON.stringify({ bootstrapRequired: false }), {
          headers: { 'Content-Type': 'application/json' },
        })
      }
      if (url.endsWith('/auth/me')) {
        return new Response(JSON.stringify({
          user: {
            id: '1e82d03f-8c33-4d03-bec3-e7656f1c8696',
            email: 'admin@example.com',
            displayName: '관리자',
            role: 'admin',
          },
          expiresAt: '2026-07-29T20:00:00+09:00',
        }), {
          headers: { 'Content-Type': 'application/json' },
        })
      }
      throw new TypeError(`test has no API fixture for ${url}`)
    }))
    await router.navigate('/')
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders the Korean real-estate dashboard shell', async () => {
    renderApp()

    expect(await screen.findByText('집계뷰')).toBeInTheDocument()
    expect(screen.getByLabelText('네이버 부동산 URL')).toHaveValue('')
    expect(
      screen.getByRole('checkbox', {
        name: /중개사 등록 물건 추가 상세정보 수집/,
      }),
    ).toBeChecked()
    expect(screen.getByRole('button', { name: '분석 시작' })).toBeInTheDocument()
    expect(
      screen.getByText(
        USE_DEMO_DATA
          ? 'DEMO · 샘플 데이터 모드'
          : '실데이터 · 서버 데이터 모드',
      ),
    ).toBeInTheDocument()
    expect(screen.queryByText('프런트엔드 UX 프리뷰')).not.toBeInTheDocument()
    expect(
      screen.queryByText(/실제 네이버 부동산 데이터와 연결되지 않은/),
    ).not.toBeInTheDocument()
    expect(screen.queryByText('단지별 평균 호가')).not.toBeInTheDocument()
  })

  it('shows a dedicated page for an unknown client route', async () => {
    renderApp()
    await router.navigate('/does-not-exist')

    expect(
      await screen.findByRole('heading', { name: '페이지를 찾을 수 없습니다' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'URL 조사로 돌아가기' })).toHaveAttribute(
      'href',
      '/',
    )
  })

  it.skipIf(!USE_DEMO_DATA)('rejects non-Naver real-estate URLs', async () => {
    const user = userEvent.setup()
    renderApp()

    const urlInput = screen.getByLabelText('네이버 부동산 URL')
    await user.clear(urlInput)
    await user.type(urlInput, 'https://example.com')
    await user.click(screen.getByRole('button', { name: '분석 시작' }))

    expect(screen.getByRole('alert')).toHaveTextContent(
      '네이버 부동산 URL을 입력해 주세요.',
    )
  })

  it.skipIf(!USE_DEMO_DATA)('completes the demo analysis flow for a valid URL', async () => {
    const user = userEvent.setup()
    renderApp()

    const detailOption = screen.getByRole('checkbox', {
      name: /중개사 등록 물건 추가 상세정보 수집/,
    })
    await user.clear(screen.getByLabelText('네이버 부동산 URL'))
    await user.type(screen.getByLabelText('네이버 부동산 URL'), VALID_DEMO_URL)
    await user.click(screen.getByRole('button', { name: '분석 시작' }))

    expect(screen.getByText('분석 진행 중')).toBeInTheDocument()
    expect(detailOption).toBeDisabled()
    expect(await screen.findByText('분석 완료', {}, { timeout: 3000 })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '분석 결과가 준비되었습니다' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '대시보드에서 결과 보기' })).toHaveAttribute('href', '/dashboard')
  })

  it('shows the explicit not-collected state without detail placeholders', () => {
    const registration = {
      ...demoDashboardDataset.apartments[0].listingGroups[0].registrations[0],
      detailCollected: false,
      optionTags: [],
      marketDetails: undefined,
    }

    render(<RegistrationCard registration={registration} />)

    expect(screen.getByText(registration.realtorName)).toBeInTheDocument()
    expect(screen.getByText(`매물번호 ${registration.articleId}`)).toBeInTheDocument()
    expect(screen.getByText(registration.description)).toBeInTheDocument()
    expect(
      screen.getByText('이 조사에서는 추가 상세정보를 수집하지 않았습니다.'),
    ).toBeInTheDocument()
    expect(screen.queryByText('3.3㎡당')).not.toBeInTheDocument()
  })

  it.skipIf(!USE_DEMO_DATA)('saves the selected Chrome delay preset in the demo schedule summary', async () => {
    const user = userEvent.setup()
    renderApp()

    await user.click(
      screen.getAllByRole('link', { name: '조사 스케줄' })[0],
    )

    expect(
      screen.getByRole('radio', { name: /기본.*1~2.5초/ }),
    ).toBeChecked()
    await user.click(
      screen.getByRole('radio', { name: /신중.*2~5초/ }),
    )
    await user.click(screen.getByRole('button', { name: '스케줄 저장' }))

    expect(screen.getByText(/신중 · 2~5초/)).toBeInTheDocument()
  })

  it('derives demo OFF and ON results without mutating the original dataset', async () => {
    const { result } = renderHook(() => useDemoDashboard())

    act(() => {
      result.current.startDemoAnalysis({
        sourceUrl: VALID_DEMO_URL,
        collectBrokerDetails: false,
        interactionDelayPreset: 'fast',
      })
    })
    expect(result.current.interactionDelayPreset).toBe('fast')
    await waitFor(() => expect(result.current.status).toBe('completed'), {
      timeout: 3000,
    })

    const offRegistration =
      result.current.dataset!.apartments[0].listingGroups[0].registrations[0]
    expect(offRegistration.detailCollected).toBe(false)
    expect(offRegistration.marketDetails).toBeUndefined()
    expect(
      demoDashboardDataset.apartments[0].listingGroups[0].registrations[0]
        .detailCollected,
    ).toBe(true)

    act(() => {
      result.current.startDemoAnalysis({
        sourceUrl: VALID_DEMO_URL,
        collectBrokerDetails: true,
        interactionDelayPreset: 'normal',
      })
    })
    expect(result.current.status).toBe('running')
    await waitFor(() => expect(result.current.status).toBe('completed'), {
      timeout: 3000,
    })

    expect(
      result.current.dataset!.apartments[0].listingGroups[0].registrations[0]
        .detailCollected,
    ).toBe(true)
  })
})
