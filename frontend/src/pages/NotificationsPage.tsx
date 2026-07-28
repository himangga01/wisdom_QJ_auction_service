import { useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Bell, CheckCheck } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  buildNotificationHref,
  getNotifications,
  markAllNotificationsRead,
  markNotificationRead,
  notificationKeys,
} from '../api/notifications'
import { NotificationList } from '../components/notifications/NotificationList'
import type { NotificationItemApi } from '../types/api'

export function NotificationsPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [unreadOnly, setUnreadOnly] = useState(false)
  const notificationsQuery = useInfiniteQuery({
    queryKey: notificationKeys.page(unreadOnly),
    queryFn: ({ pageParam }) => getNotifications({
      cursor: pageParam,
      unreadOnly,
    }),
    initialPageParam: null as string | null,
    getNextPageParam: (page) => page.nextCursor ?? undefined,
  })
  const refreshCounts = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: notificationKeys.all }),
      queryClient.invalidateQueries({ queryKey: notificationKeys.unreadCount }),
    ])
  }
  const readMutation = useMutation({
    mutationFn: (notification: NotificationItemApi) => markNotificationRead(notification.id),
    onSuccess: refreshCounts,
  })
  const readAllMutation = useMutation({
    mutationFn: markAllNotificationsRead,
    onSuccess: refreshCounts,
  })
  const items = notificationsQuery.data?.pages.flatMap((page) => page.items) ?? []

  const openNotification = (notification: NotificationItemApi) => {
    if (!notification.readAt) readMutation.mutate(notification)
    navigate(buildNotificationHref(notification))
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="flex items-center gap-2 text-sm font-extrabold text-emerald-700">
            <Bell size={17} /> 조사 변경 알림
          </p>
          <h1 className="mt-1 text-3xl font-black tracking-[-0.04em] text-slate-950">알림</h1>
          <p className="mt-2 text-sm text-slate-500">신규·변경·삭제·복원된 매물을 확인합니다.</p>
        </div>
        <button
          type="button"
          onClick={() => readAllMutation.mutate()}
          disabled={readAllMutation.isPending}
          className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-extrabold text-slate-700 disabled:opacity-50"
        >
          <CheckCheck size={16} /> 모두 읽음
        </button>
      </header>

      <div className="inline-flex rounded-xl bg-slate-200/70 p-1" aria-label="알림 필터">
        <button type="button" onClick={() => setUnreadOnly(false)} className={`rounded-lg px-4 py-2 text-sm font-bold ${!unreadOnly ? 'bg-white text-slate-950 shadow-sm' : 'text-slate-500'}`}>전체</button>
        <button type="button" onClick={() => setUnreadOnly(true)} className={`rounded-lg px-4 py-2 text-sm font-bold ${unreadOnly ? 'bg-white text-slate-950 shadow-sm' : 'text-slate-500'}`}>읽지 않음</button>
      </div>

      {notificationsQuery.isPending ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-10 text-center text-sm font-bold text-slate-500">알림을 불러오는 중입니다.</div>
      ) : notificationsQuery.error ? (
        <div role="alert" className="rounded-2xl border border-rose-200 bg-rose-50 p-5 text-sm font-bold text-rose-700">
          {notificationsQuery.error instanceof Error ? notificationsQuery.error.message : '알림을 불러오지 못했습니다.'}
        </div>
      ) : (
        <NotificationList items={items} onSelect={openNotification} />
      )}

      {notificationsQuery.hasNextPage ? (
        <button
          type="button"
          onClick={() => void notificationsQuery.fetchNextPage()}
          disabled={notificationsQuery.isFetchingNextPage}
          className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-extrabold text-slate-700 disabled:opacity-50"
        >
          {notificationsQuery.isFetchingNextPage ? '불러오는 중...' : '더 보기'}
        </button>
      ) : null}
    </div>
  )
}
