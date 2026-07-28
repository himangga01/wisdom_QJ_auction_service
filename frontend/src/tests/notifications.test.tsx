import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  buildNotificationHref,
  getNotifications,
  markNotificationRead,
} from '../api/notifications'
import { appRoutes } from '../app/router'
import { NotificationList } from '../components/notifications/NotificationList'
import { ListingComparisonBoard } from '../components/research/ListingComparisonBoard'
import { NotificationsPage } from '../pages/NotificationsPage'
import type { NotificationItemApi } from '../types/api'
import type { ApartmentSummary, ListingGroup } from '../types/realEstate'

vi.mock('../api/notifications', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/notifications')>()
  return {
    ...actual,
    getNotifications: vi.fn(),
    markNotificationRead: vi.fn(),
    markAllNotificationsRead: vi.fn(),
  }
})

describe('notification navigation', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })
  it('registers a dedicated notifications route', () => {
    const protectedRoutes = appRoutes[2]?.children?.[0]?.children ?? []
    expect(protectedRoutes.some((route) => route.path === 'notifications')).toBe(true)
  })

  it('shows unread notification state in the dedicated list', () => {
    const item = {
      id: 'notification-1',
      eventType: 'changed',
      title: '테스트 아파트 · 매물 정보 변경',
      summary: { changedFields: ['price'] },
      readAt: null,
      createdAt: '2026-07-29T00:00:00Z',
      link: {
        sourceId: 'source-1',
        complexId: '12345',
        runId: 'run-2',
        compareRunId: 'run-1',
        focusListingId: 'listing-1',
      },
    } satisfies NotificationItemApi

    render(<NotificationList items={[item]} onSelect={() => undefined} />)

    expect(screen.getByLabelText('읽지 않음')).toBeInTheDocument()
    expect(screen.getByText('변경 항목: price')).toBeInTheDocument()
  })

  it('preserves source, comparison runs, and focused listing in the target URL', () => {
    const notification = {
      link: {
        sourceId: 'source-1',
        complexId: '12345',
        runId: 'run-2',
        compareRunId: 'run-1',
        focusListingId: 'listing-1',
      },
    } as NotificationItemApi

    expect(buildNotificationHref(notification)).toBe(
      '/apartments/12345?sourceId=source-1&runId=run-2&compareRunId=run-1&focusListingId=listing-1',
    )
  })

  it('visually marks the listing requested by a notification', () => {
    const before = {
      groupId: 'listing-1',
      tradeType: 'sale',
      price: 700_000_000,
      building: '101동',
      supplyAreaM2: 84,
      exclusiveAreaM2: 59,
      floor: '10층',
      direction: '남향',
      status: 'active',
      discoveredAt: '2026-07-28T00:00:00Z',
      lastSeenAt: '2026-07-28T00:00:00Z',
      registrations: [],
    } as ListingGroup
    const after = { ...before, price: 710_000_000 }
    const apartment = {
      complexId: '12345',
      complexName: '테스트 아파트',
      address: '서울',
      sourceId: 'source-1',
      details: {
        householdCount: 0,
        buildingCount: 0,
        completedYear: 0,
        parkingPerHousehold: 0,
        heating: '',
      },
      listingGroups: [],
      history: [],
    } satisfies ApartmentSummary

    render(
      <MemoryRouter>
        <ListingComparisonBoard
          apartment={apartment}
          beforeDate="2026-07-28T00:00:00Z"
          afterDate="2026-07-29T00:00:00Z"
          beforeListings={[before]}
          afterListings={[after]}
          focusListingId="listing-1"
        />
      </MemoryRouter>,
    )

    expect(screen.getByTestId('comparison-listing-listing-1')).toHaveAttribute('data-focused', 'true')
  })

  it('opens the target even when marking the notification read fails', async () => {
    const user = userEvent.setup()
    const item = {
      id: 'notification-1',
      eventType: 'changed',
      title: '테스트 아파트 · 매물 정보 변경',
      summary: { changedFields: ['price'] },
      readAt: null,
      createdAt: '2026-07-29T00:00:00Z',
      link: {
        sourceId: 'source-1',
        complexId: '12345',
        runId: 'run-2',
        compareRunId: 'run-1',
        focusListingId: 'listing-1',
      },
    } satisfies NotificationItemApi
    vi.mocked(getNotifications).mockResolvedValue({
      items: [item],
      nextCursor: null,
    })
    vi.mocked(markNotificationRead).mockRejectedValue(
      new TypeError('network failed'),
    )
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/notifications']}>
          <Routes>
            <Route path="/notifications" element={<NotificationsPage />} />
            <Route path="/apartments/:complexId" element={<h1>target apartment</h1>} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    )

    await user.click(await screen.findByText(item.title))

    await waitFor(() =>
      expect(screen.getByRole('heading', { name: 'target apartment' })).toBeInTheDocument(),
    )
  })
})
