import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { getApartment, getApartmentListings } from '../api/apartments'
import { ApartmentDetailPage } from '../pages/ApartmentDetailPage'
import { useAnalysis } from '../state/AnalysisProvider'
import { useDemoAnalysis } from '../state/DemoAnalysisContext'
import type { ApartmentDetailApi } from '../types/api'

vi.mock('../state/AnalysisProvider', () => ({
  useAnalysis: vi.fn(),
}))

vi.mock('../state/DemoAnalysisContext', () => ({
  useDemoAnalysis: vi.fn(),
}))

vi.mock('../api/apartments', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/apartments')>()
  return {
    ...actual,
    getApartment: vi.fn(),
    getApartmentListings: vi.fn(),
    getListing: vi.fn(),
  }
})

vi.mock('../components/research/ApartmentHistoryChart', () => ({
  ApartmentHistoryChart: () => <div>history chart</div>,
}))
vi.mock('../components/research/ListingComparisonBoard', () => ({
  ListingComparisonBoard: () => <div>comparison board</div>,
}))
vi.mock('../components/research/SnapshotListingCards', () => ({
  SnapshotListingCards: () => <div>snapshot cards</div>,
}))

const DETAIL: ApartmentDetailApi = {
  apartmentId: 'apartment-1',
  complexId: 'complex-1',
  complexName: 'URL 선택 아파트',
  address: '서울',
  sourceId: 'source-b',
  sourceUrl: 'https://fin.land.naver.com/map?source=b',
  latestRunId: 'run-3',
  latestStatus: 'completed',
  collectedAt: '2026-07-29T03:00:00Z',
  details: {},
  listingCount: 0,
  availableRuns: [
    { runId: 'run-1', status: 'completed', collectedAt: '2026-07-29T01:00:00Z' },
    { runId: 'run-2', status: 'completed', collectedAt: '2026-07-29T02:00:00Z' },
    { runId: 'run-3', status: 'completed', collectedAt: '2026-07-29T03:00:00Z' },
  ],
  history: [
    { runId: 'run-1', status: 'completed', collectedAt: '2026-07-29T01:00:00Z', saleCount: 1, jeonseCount: 0, monthlyCount: 0, addedCount: 1, removedCount: 0 },
    { runId: 'run-2', status: 'completed', collectedAt: '2026-07-29T02:00:00Z', saleCount: 1, jeonseCount: 0, monthlyCount: 0, addedCount: 0, removedCount: 0 },
    { runId: 'run-3', status: 'completed', collectedAt: '2026-07-29T03:00:00Z', saleCount: 1, jeonseCount: 0, monthlyCount: 0, addedCount: 0, removedCount: 0 },
  ],
}

function LocationProbe() {
  const location = useLocation()
  return <output data-testid="location">{location.pathname}{location.search}</output>
}

function renderDetail(initialEntry: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route
            path="/apartments/:complexId"
            element={<><ApartmentDetailPage /><LocationProbe /></>}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('아파트 상세 source와 조사일 URL 계약', () => {
  const selectApartment = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useAnalysis).mockReturnValue({
      isDemo: false,
      selectedApartment: {
        ...DETAIL,
        sourceId: 'source-a',
        complexName: '기존 전역 선택',
      },
      selectApartment,
    } as unknown as ReturnType<typeof useAnalysis>)
    vi.mocked(useDemoAnalysis).mockReturnValue({
      dataset: null,
    } as unknown as ReturnType<typeof useDemoAnalysis>)
    vi.mocked(getApartment).mockResolvedValue(DETAIL)
    vi.mocked(getApartmentListings).mockImplementation(
      async (_complexId, options) => ({
        complexId: 'complex-1',
        runId: options.runId ?? 'run-3',
        collectedAt: DETAIL.collectedAt,
        items: [],
        absentItems: [],
      }),
    )
  })

  it('직접 URL source를 전역 선택에 반영하고 날짜 선택을 URL에 유지한다', async () => {
    const user = userEvent.setup()
    renderDetail(
      '/apartments/complex-1?sourceId=source-b&runId=run-3&compareRunId=run-1',
    )

    await waitFor(() => expect(selectApartment).toHaveBeenCalledWith(DETAIL))
    await user.selectOptions(
      await screen.findByLabelText('선택 조사일'),
      '2026-07-29T02:00:00Z',
    )

    await waitFor(() =>
      expect(screen.getByTestId('location')).toHaveTextContent(
        '/apartments/complex-1?sourceId=source-b&runId=run-2&compareRunId=run-1',
      ),
    )
  })

  it('URL의 runId가 해당 source 이력에 없으면 최신 결과로 위장하지 않는다', async () => {
    renderDetail(
      '/apartments/complex-1?sourceId=source-b&runId=missing-run',
    )

    expect(
      await screen.findByText('요청한 조사 기록을 찾을 수 없습니다.'),
    ).toBeInTheDocument()
    expect(getApartment).not.toHaveBeenCalledWith(
      'complex-1',
      'source-b',
      'missing-run',
    )
  })
})
