import { act, render, renderHook, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from '../App'
import { RegistrationCard } from '../pages/ListingDetailPage'
import { demoDashboardDataset } from '../mocks/demoRealEstate'
import { useDemoDashboard } from '../state/useDemoDashboard'

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
  it('renders the Korean real-estate dashboard shell', () => {
    renderApp()

    expect(screen.getByText('집계뷰')).toBeInTheDocument()
    expect(screen.getByLabelText('네이버 부동산 URL')).toBeInTheDocument()
    expect(
      screen.getByRole('checkbox', {
        name: /중개사 등록 물건 추가 상세정보 수집/,
      }),
    ).toBeChecked()
    expect(screen.getByRole('button', { name: '분석 시작' })).toBeInTheDocument()
    expect(screen.queryByText('단지별 평균 호가')).not.toBeInTheDocument()
  })

  it('rejects non-Naver real-estate URLs', async () => {
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

  it('completes the demo analysis flow for a valid URL', async () => {
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

  it('saves the selected Chrome delay preset in the demo schedule summary', async () => {
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
