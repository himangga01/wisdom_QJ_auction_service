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
  exportTargets: (query: string) => ['apartments', 'export-targets', query, 1, 20] as const,
  detail: (complexId: string, runId?: string, sourceId?: string) => ['apartments', 'detail', complexId, runId ?? 'latest', sourceId ?? 'any-source'] as const,
  history: (complexId: string, sourceId?: string) => ['apartments', 'history', complexId, sourceId ?? 'latest-source'] as const,
  listings: (complexId: string, runId?: string, sourceId?: string) => ['apartments', 'listings', complexId, runId ?? 'latest', sourceId ?? 'source'] as const,
  listing: (groupId: string, runId?: string, sourceId?: string) => ['listings', groupId, runId ?? 'latest', sourceId ?? 'source'] as const,
  dashboard: (sourceId?: string) => ['dashboard', sourceId ?? 'latest'] as const,
}

export function getApartments({
  query = '',
  page = 1,
  pageSize = 20,
}: {
  query?: string
  page?: number
  pageSize?: number
} = {}): Promise<ApartmentPageApi> {
  return apiRequest('/apartments', {}, { query, page, pageSize })
}

export function getApartment(complexId: string, sourceId: string, runId?: string): Promise<ApartmentDetailApi> {
  return apiRequest(`/apartments/${encodeURIComponent(complexId)}`, {}, { runId, sourceId })
}

export function getApartmentHistory(complexId: string, sourceId: string): Promise<ApartmentHistoryPointApi[]> {
  return apiRequest(`/apartments/${encodeURIComponent(complexId)}/history`, {}, { sourceId })
}

export function getApartmentListings(
  complexId: string,
  params: { sourceId: string; runId?: string; tradeType?: TradeTypeApi; status?: ListingStatusApi },
): Promise<ListingPageApi> {
  return apiRequest(`/apartments/${encodeURIComponent(complexId)}/listings`, {}, params)
}

export function getListing(groupId: string, sourceId: string, runId?: string): Promise<ListingDetailApi> {
  return apiRequest(`/listings/${encodeURIComponent(groupId)}`, {}, { runId, sourceId })
}

export function getDashboard(sourceId: string): Promise<DashboardResponseApi> {
  return apiRequest('/dashboard', {}, { sourceId })
}
