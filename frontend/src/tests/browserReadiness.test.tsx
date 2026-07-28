import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { UrlAnalysisPanel } from '../components/analysis/UrlAnalysisPanel'
import { AnalysisPage } from '../pages/AnalysisPage'
import { useAnalysis } from '../state/AnalysisProvider'
import { useDemoAnalysis } from '../state/DemoAnalysisContext'
import { runErrorMessage } from '../utils/runErrorMessages'

vi.mock('../state/AnalysisProvider', () => ({
  useAnalysis: vi.fn(),
}))

vi.mock('../state/DemoAnalysisContext', () => ({
  useDemoAnalysis: vi.fn(),
}))

describe('Chrome 준비 상태', () => {
  it('Chrome unavailable 동안 실행을 막고 회복하면 입력을 보존한 채 활성화한다', async () => {
    const user = userEvent.setup()
    const onStart = vi.fn()
    const view = render(
      <UrlAnalysisPanel
        status="idle"
        progress={0}
        error=""
        browserUnavailable
        onStart={onStart}
      />,
    )

    await user.type(
      screen.getByLabelText('네이버 부동산 URL'),
      'https://fin.land.naver.com/map?ready=true',
    )

    expect(screen.getByRole('button', { name: '분석 시작' })).toBeDisabled()
    expect(
      screen.getByText(
        '수집용 Chrome에 연결할 수 없습니다. 실행 상태를 확인한 뒤 다시 시도해 주세요.',
      ),
    ).toBeInTheDocument()

    view.rerender(
      <UrlAnalysisPanel
        status="idle"
        progress={0}
        error=""
        browserUnavailable={false}
        onStart={onStart}
      />,
    )

    expect(screen.getByLabelText('네이버 부동산 URL')).toHaveValue(
      'https://fin.land.naver.com/map?ready=true',
    )
    expect(screen.getByRole('button', { name: '분석 시작' })).toBeEnabled()
  })

  it('안정 오류 코드를 사용자 문구로 변환한다', () => {
    expect(runErrorMessage('browser_unavailable')).toBe(
      '수집용 Chrome에 연결할 수 없습니다. 실행 상태를 확인한 뒤 다시 시도해 주세요.',
    )
    expect(runErrorMessage('browser_disconnected')).toBe(
      '조사 중 Chrome 연결이 끊겼습니다. Chrome이 준비되면 분석을 다시 시작해 주세요.',
    )
    expect(runErrorMessage('access_blocked')).toBe(
      '네이버에서 접근을 제한해 조사를 중단했습니다.',
    )
  })

  it('health 확인 전 unknown 상태에서는 분석 시작을 허용하지 않는다', async () => {
    const user = userEvent.setup()
    vi.mocked(useAnalysis).mockReturnValue({
      status: 'idle',
      progress: 0,
      stage: null,
      error: '',
      notice: '',
      isRestoringRun: false,
      isCancelling: false,
      browserStatus: 'unknown',
      isDemo: false,
      selectedApartment: null,
      startAnalysis: vi.fn(),
      cancelQueuedAnalysis: vi.fn(),
    } as unknown as ReturnType<typeof useAnalysis>)
    vi.mocked(useDemoAnalysis).mockReturnValue({
      dataset: null,
      selectedApartmentId: null,
      error: '',
    } as unknown as ReturnType<typeof useDemoAnalysis>)

    render(
      <MemoryRouter>
        <AnalysisPage />
      </MemoryRouter>,
    )
    await user.type(
      screen.getByLabelText('네이버 부동산 URL'),
      'https://fin.land.naver.com/map?ready=pending',
    )

    expect(screen.getByRole('button', { name: '분석 시작' })).toBeDisabled()
  })

  it('완료 run의 결과 아파트 hydration이 끝난 뒤에만 결과 CTA를 연다', () => {
    const selectedApartment = {
      complexId: 'old-complex',
      complexName: '이전 선택 아파트',
      collectedAt: '2026-07-29T00:00:00Z',
    }
    vi.mocked(useAnalysis).mockReturnValue({
      status: 'completed',
      progress: 100,
      stage: 'save',
      error: '',
      notice: '',
      isRestoringRun: false,
      isCancelling: false,
      browserStatus: 'ready',
      isDemo: false,
      selectedApartment,
      resultHydrationStatus: 'loading',
      startAnalysis: vi.fn(),
      cancelQueuedAnalysis: vi.fn(),
    } as unknown as ReturnType<typeof useAnalysis>)
    vi.mocked(useDemoAnalysis).mockReturnValue({
      dataset: null,
      selectedApartmentId: null,
      error: '',
    } as unknown as ReturnType<typeof useDemoAnalysis>)

    const view = render(
      <MemoryRouter>
        <AnalysisPage />
      </MemoryRouter>,
    )

    expect(
      screen.queryByRole('link', { name: '대시보드에서 결과 보기' }),
    ).not.toBeInTheDocument()
    expect(screen.queryByText('이전 선택 아파트')).not.toBeInTheDocument()

    vi.mocked(useAnalysis).mockReturnValue({
      ...vi.mocked(useAnalysis).mock.results.at(-1)?.value,
      resultHydrationStatus: 'ready',
    } as unknown as ReturnType<typeof useAnalysis>)
    view.rerender(
      <MemoryRouter>
        <AnalysisPage />
      </MemoryRouter>,
    )

    expect(
      screen.getByRole('link', { name: '대시보드에서 결과 보기' }),
    ).toBeInTheDocument()
  })
})
