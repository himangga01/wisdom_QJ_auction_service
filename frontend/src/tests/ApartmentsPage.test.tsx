import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { downloadSourceExport } from '../api/exports'
import { getApartments } from '../api/apartments'
import { ApartmentsPage } from '../pages/ApartmentsPage'
import { useAnalysis } from '../state/AnalysisProvider'
import { useDemoAnalysis } from '../state/DemoAnalysisContext'
import type { ApartmentSummaryApi } from '../types/api'

vi.mock('../state/AnalysisProvider', () => ({
  useAnalysis: vi.fn(),
}))

vi.mock('../state/DemoAnalysisContext', () => ({
  useDemoAnalysis: vi.fn(),
}))

vi.mock('../api/apartments', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/apartments')>()
  return { ...actual, getApartments: vi.fn() }
})

vi.mock('../api/exports', () => ({
  downloadSourceExport: vi.fn(),
}))

const APARTMENT: ApartmentSummaryApi = {
  apartmentId: 'apartment-1',
  complexId: 'complex-1',
  complexName: '선택 아파트',
  address: '서울시',
  sourceId: 'source-explicit',
  sourceUrl: 'https://fin.land.naver.com/map?one=true',
  latestRunId: 'run-1',
  latestStatus: 'completed',
  collectedAt: '2026-07-29T00:00:00Z',
  details: {},
  listingCount: 3,
}

describe('아파트 Excel 대상 선택', () => {
  const selectApartment = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useAnalysis).mockReturnValue({
      isDemo: false,
      selectApartment,
    } as unknown as ReturnType<typeof useAnalysis>)
    vi.mocked(useDemoAnalysis).mockReturnValue({
      dataset: null,
    } as unknown as ReturnType<typeof useDemoAnalysis>)
    vi.mocked(getApartments).mockResolvedValue({
      items: [APARTMENT],
      page: 1,
      pageSize: 20,
      total: 1,
    })
    vi.mocked(downloadSourceExport).mockResolvedValue(undefined)
  })

  it('첫 source를 자동 선택하지 않고 사용자가 고른 전체 객체를 export 대상으로 사용한다', async () => {
    const user = userEvent.setup()
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <ApartmentsPage />
        </MemoryRouter>
      </QueryClientProvider>,
    )

    const downloadButton = await screen.findByRole('button', { name: /Excel 다운로드/ })
    expect(downloadButton).toBeDisabled()
    expect(selectApartment).not.toHaveBeenCalled()
    expect(
      screen.getAllByRole('link', { name: APARTMENT.complexName })[0],
    ).toHaveAttribute(
      'href',
      '/apartments/complex-1?sourceId=source-explicit',
    )

    await user.type(screen.getByLabelText('Excel 원본 검색'), '선택')
    await user.click(await screen.findByRole('button', { name: /선택 아파트.*서울시/ }))

    expect(selectApartment).toHaveBeenCalledWith(APARTMENT)
    expect(downloadButton).toBeEnabled()
    await user.click(downloadButton)

    await waitFor(() =>
      expect(downloadSourceExport).toHaveBeenCalledWith('source-explicit', {
        from: undefined,
        to: undefined,
      }),
    )
  })
})
