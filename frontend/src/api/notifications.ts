import type {
  NotificationItemApi,
  NotificationPageApi,
  NotificationPreferenceApi,
  NotificationPreferencePatchApi,
  NotificationReadAllApi,
  NotificationUnreadCountApi,
} from '../types/api'
import { apiRequest } from './client'

export const notificationKeys = {
  all: ['notifications'] as const,
  page: (unreadOnly: boolean) => ['notifications', 'page', unreadOnly] as const,
  unreadCount: ['notifications', 'unread-count'] as const,
  preference: (sourceId: string) => ['notifications', 'preference', sourceId] as const,
}

export function getNotifications({
  cursor,
  limit = 20,
  unreadOnly = false,
}: {
  cursor?: string | null
  limit?: number
  unreadOnly?: boolean
} = {}): Promise<NotificationPageApi> {
  return apiRequest('/notifications', {}, { cursor, limit, unreadOnly })
}

export function getUnreadNotificationCount(): Promise<NotificationUnreadCountApi> {
  return apiRequest('/notifications/unread-count')
}

export function markNotificationRead(id: string, read = true): Promise<void> {
  return apiRequest(`/notifications/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    body: JSON.stringify({ read }),
  })
}

export function markAllNotificationsRead(): Promise<NotificationReadAllApi> {
  return apiRequest('/notifications/read-all', { method: 'POST' })
}

export function getNotificationPreference(sourceId: string): Promise<NotificationPreferenceApi> {
  return apiRequest(`/sources/${encodeURIComponent(sourceId)}/notification-preference`)
}

export function patchNotificationPreference(
  sourceId: string,
  preference: NotificationPreferencePatchApi,
): Promise<NotificationPreferenceApi> {
  return apiRequest(`/sources/${encodeURIComponent(sourceId)}/notification-preference`, {
    method: 'PATCH',
    body: JSON.stringify(preference),
  })
}

export function buildNotificationHref(notification: NotificationItemApi): string {
  const { link } = notification
  const query = new URLSearchParams({
    sourceId: link.sourceId,
    runId: link.runId,
  })
  if (link.compareRunId) query.set('compareRunId', link.compareRunId)
  query.set('focusListingId', link.focusListingId)
  return `/apartments/${encodeURIComponent(link.complexId)}?${query.toString()}`
}
