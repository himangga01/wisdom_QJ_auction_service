import { useQuery } from '@tanstack/react-query'
import { Bell } from 'lucide-react'
import { useEffect, useState } from 'react'
import { NavLink } from 'react-router-dom'
import {
  getUnreadNotificationCount,
  notificationKeys,
} from '../../api/notifications'
import { useAuth } from '../../state/AuthProvider'

export function NotificationBell() {
  const auth = useAuth()
  const [visible, setVisible] = useState(
    typeof document === 'undefined' || document.visibilityState === 'visible',
  )

  useEffect(() => {
    const onVisibilityChange = () => {
      setVisible(document.visibilityState === 'visible')
    }
    document.addEventListener('visibilitychange', onVisibilityChange)
    return () => document.removeEventListener('visibilitychange', onVisibilityChange)
  }, [])

  const countQuery = useQuery({
    queryKey: notificationKeys.unreadCount,
    queryFn: getUnreadNotificationCount,
    enabled: !auth.isDemo && visible,
    refetchInterval: !auth.isDemo && visible ? 30_000 : false,
  })

  if (auth.isDemo) return null
  const count = countQuery.data?.count ?? 0

  return (
    <NavLink
      to="/notifications"
      aria-label={count ? `읽지 않은 알림 ${count}개` : '알림'}
      className="relative grid size-9 place-items-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-900"
    >
      <Bell size={18} />
      {count ? (
        <span className="absolute -right-1 -top-1 min-w-5 rounded-full bg-rose-600 px-1 text-center text-[10px] font-black leading-5 text-white">
          {count > 99 ? '99+' : count}
        </span>
      ) : null}
    </NavLink>
  )
}
