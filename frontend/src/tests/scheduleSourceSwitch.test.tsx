import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  createSchedule,
  deleteSchedule,
  getScheduleRuns,
  getSchedules,
  patchSchedule,
} from '../api/schedules'
import {
  getNotificationPreference,
  patchNotificationPreference,
} from '../api/notifications'
import { SchedulePage } from '../pages/SchedulePage'
import { useAnalysis } from '../state/AnalysisProvider'
import { useDemoAnalysis } from '../state/DemoAnalysisContext'
import type { ApartmentSummaryApi, NotificationPreferenceApi } from '../types/api'

vi.mock('../state/AnalysisProvider', () => ({
  useAnalysis: vi.fn(),
}))

vi.mock('../state/DemoAnalysisContext', () => ({
  useDemoAnalysis: vi.fn(),
}))

vi.mock('../api/schedules', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/schedules')>()
  return {
    ...actual,
    getSchedules: vi.fn(),
    getScheduleRuns: vi.fn(),
    createSchedule: vi.fn(),
    patchSchedule: vi.fn(),
    deleteSchedule: vi.fn(),
  }
})

vi.mock('../api/notifications', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/notifications')>()
  return {
    ...actual,
    getNotificationPreference: vi.fn(),
    patchNotificationPreference: vi.fn(),
  }
})

function apartment(sourceId: string): ApartmentSummaryApi {
  return {
    apartmentId: `apartment-${sourceId}`,
    complexId: `complex-${sourceId}`,
    complexName: `아파트 ${sourceId}`,
    address: '서울',
    sourceId,
    sourceUrl: `https://fin.land.naver.com/map?source=${sourceId}`,
    latestRunId: `run-${sourceId}`,
    latestStatus: 'completed',
    collectedAt: '2026-07-29T00:00:00Z',
    details: {},
    listingCount: 1,
  }
}

describe('schedule source switch', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useDemoAnalysis).mockReturnValue({
      dataset: null,
    } as ReturnType<typeof useDemoAnalysis>)
    vi.mocked(getSchedules).mockResolvedValue([])
    vi.mocked(getScheduleRuns).mockResolvedValue({
      scheduleId: 'none',
      items: [],
    })
    vi.mocked(createSchedule).mockRejectedValue(new Error('not expected'))
    vi.mocked(patchSchedule).mockRejectedValue(new Error('not expected'))
    vi.mocked(deleteSchedule).mockRejectedValue(new Error('not expected'))
    vi.mocked(patchNotificationPreference).mockRejectedValue(
      new Error('not expected'),
    )
  })

  it('disables saving until the newly selected source preference has loaded', async () => {
    let selectedApartment = apartment('source-a')
    let resolveSourceB!: (value: NotificationPreferenceApi) => void
    const sourceBPreference = new Promise<NotificationPreferenceApi>((resolve) => {
      resolveSourceB = resolve
    })
    vi.mocked(getNotificationPreference).mockImplementation((sourceId) => {
      if (sourceId === 'source-a') {
        return Promise.resolve({
          sourceId,
          enabled: true,
          notifyNew: true,
          notifyChanged: false,
          notifyRemoved: true,
          notifyRestored: true,
        })
      }
      return sourceBPreference
    })
    vi.mocked(useAnalysis).mockImplementation(() => ({
      isDemo: false,
      selectedApartment,
    } as ReturnType<typeof useAnalysis>))

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })
    const view = render(
      <QueryClientProvider client={queryClient}>
        <SchedulePage />
      </QueryClientProvider>,
    )

    await waitFor(() =>
      expect(screen.getByRole('button', { name: '스케줄 저장' })).toBeEnabled(),
    )

    selectedApartment = apartment('source-b')
    view.rerender(
      <QueryClientProvider client={queryClient}>
        <SchedulePage />
      </QueryClientProvider>,
    )

    expect(screen.getByRole('button', { name: '스케줄 저장' })).toBeDisabled()

    resolveSourceB({
      sourceId: 'source-b',
      enabled: false,
      notifyNew: true,
      notifyChanged: true,
      notifyRemoved: true,
      notifyRestored: true,
    })
  })
})
