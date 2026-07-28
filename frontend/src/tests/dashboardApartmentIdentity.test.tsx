import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { getApartments } from '../api/apartments'
import { DashboardApartmentPicker } from '../components/dashboard/DashboardApartmentPicker'
import type { ApartmentSummaryApi } from '../types/api'

vi.mock('../api/apartments', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/apartments')>()
  return { ...actual, getApartments: vi.fn() }
})

function apartment(sourceId: string, sourceUrl: string): ApartmentSummaryApi {
  return {
    apartmentId: 'shared-apartment',
    complexId: 'shared-complex',
    complexName: '같은 단지',
    address: '서울',
    sourceId,
    sourceUrl,
    latestRunId: `run-${sourceId}`,
    latestStatus: 'completed',
    collectedAt: '2026-07-29T00:00:00Z',
    details: {},
    listingCount: 1,
  }
}

describe('대시보드 source별 아파트 선택', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('같은 complexId라도 서로 다른 source를 숨기지 않고 독립 선택한다', async () => {
    const user = userEvent.setup()
    const first = apartment('source-1', 'https://fin.land.naver.com/map?first=1')
    const second = apartment('source-2', 'https://fin.land.naver.com/map?second=1')
    vi.mocked(getApartments).mockResolvedValue({
      items: [first, second],
      page: 1,
      pageSize: 20,
      total: 2,
    })
    const onSelect = vi.fn()
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })

    render(
      <QueryClientProvider client={queryClient}>
        <DashboardApartmentPicker selectedApartment={first} onSelect={onSelect} />
      </QueryClientProvider>,
    )

    expect(await screen.findByText(/source-2/)).toBeInTheDocument()
    const options = screen.getAllByRole('button', { name: /같은 단지/ })
    expect(options).toHaveLength(2)
    expect(screen.getByText(/source-1/)).toBeInTheDocument()

    await user.click(options[1])
    expect(onSelect).toHaveBeenCalledWith(second)
  })
})
