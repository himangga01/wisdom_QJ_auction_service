import type {
  ApartmentDetailApi,
  ApartmentHistoryPointApi,
  ApartmentPageApi,
  DashboardResponseApi,
  ListingDetailApi,
  ListingPageApi,
  ListingStatusApi,
  TradeTypeApi,
} from '../types/api'
import { apiRequest } from './client'

export const apartmentKeys = {
  all: ['apartments'] as const,
  page: (query: string, page: number, pageSize: number) => ['apartments', 'page', query, page, pageSize] as const,
  detail: (complexId: string) => ['apartments', 'detail', complexId] as const,
  history: (complexId: string) => ['apartments', 'history', complexId] as const,
  listings: (complexId: string, runId?: string) => ['apartments', 'listings', complexId, runId ?? 'latest'] as const,
  listing: (groupId: string, runId?: string) => ['listings', groupId, runId ?? 'latest'] as const,
  dashboard: (sourceId?: string) => ['dashboard', sourceId ?? 'latest'] as const,
}

export function getApartments({
  query = '',
  page = 1,
  pageSize = 100,
}: {
  query?: string
  page?: number
  pageSize?: number
} = {}): Promise<ApartmentPageApi> {
  return apiRequest('/apartments', {}, { query, page, pageSize })
}

export function getApartment(complexId: string): Promise<ApartmentDetailApi> {
  return apiRequest(`/apartments/${encodeURIComponent(complexId)}`)
}

export function getApartmentHistory(complexId: string): Promise<ApartmentHistoryPointApi[]> {
  return apiRequest(`/apartments/${encodeURIComponent(complexId)}/history`)
}

export function getApartmentListings(
  complexId: string,
  params: { runId?: string; tradeType?: TradeTypeApi; status?: ListingStatusApi } = {},
): Promise<ListingPageApi> {
  return apiRequest(`/apartments/${encodeURIComponent(complexId)}/listings`, {}, params)
}

export function getListing(groupId: string, runId?: string): Promise<ListingDetailApi> {
  return apiRequest(`/listings/${encodeURIComponent(groupId)}`, {}, { runId })
}

export function getDashboard(sourceId?: string): Promise<DashboardResponseApi> {
  return apiRequest('/dashboard', {}, { sourceId })
}
