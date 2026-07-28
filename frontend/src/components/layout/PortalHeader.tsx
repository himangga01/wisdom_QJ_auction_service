import { BarChart3, Building2, CalendarClock, Link2, LogOut, UserCog, UserRound } from 'lucide-react'
import { NavLink } from 'react-router-dom'
import { useAuth } from '../../state/AuthProvider'
import { RuntimeModeStatus } from './RuntimeModeStatus'
import { NotificationBell } from '../notifications/NotificationBell'

const navigation = [
  { to: '/', label: 'URL 조사', icon: Link2, end: true },
  { to: '/dashboard', label: '대시보드', icon: BarChart3 },
  { to: '/apartments', label: '조사 아파트', icon: Building2 },
  { to: '/schedules', label: '조사 스케줄', icon: CalendarClock },
]

export function PortalHeader() {
  const auth = useAuth()

  return (
    <header className="sticky top-0 z-40 border-b border-slate-200/80 bg-white/95 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-[1440px] items-center gap-7 px-5 lg:px-8">
        <NavLink to="/" className="flex shrink-0 items-center gap-2.5 text-slate-950 no-underline">
          <span className="grid size-9 place-items-center rounded-xl bg-emerald-600 text-white shadow-sm shadow-emerald-200">
            <BarChart3 size={19} strokeWidth={2.5} />
          </span>
          <strong className="text-xl font-black tracking-[-0.04em]">집계뷰</strong>
        </NavLink>

        <nav className="hidden items-center gap-1 md:flex" aria-label="주요 메뉴">
          {navigation.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex items-center gap-2 rounded-lg px-3.5 py-2 text-sm transition ${
                  isActive ? 'bg-slate-100 font-extrabold text-slate-950' : 'font-semibold text-slate-500 hover:bg-slate-50 hover:text-slate-800'
                }`
              }
            >
              <Icon size={16} /> {label}
            </NavLink>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-2">
          <RuntimeModeStatus />
          <NotificationBell />
          {auth.user?.role === 'admin' ? (
            <NavLink
              to="/admin/users"
              className="hidden items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-bold text-slate-600 hover:bg-slate-100 lg:flex"
            >
              <UserCog size={16} /> 사용자 관리
            </NavLink>
          ) : null}
          <NavLink
            to="/account"
            aria-label="계정 메뉴"
            className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-bold text-slate-700"
          >
            <UserRound size={16} />
            <span className="hidden max-w-32 truncate sm:inline">{auth.user?.displayName}</span>
          </NavLink>
          {!auth.isDemo ? (
            <button
              type="button"
              onClick={() => void auth.logout()}
              className="grid size-9 place-items-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-900"
              aria-label="로그아웃"
            >
              <LogOut size={17} />
            </button>
          ) : null}
        </div>
      </div>

      <nav className="flex gap-1 overflow-x-auto border-t border-slate-100 px-4 py-2 md:hidden" aria-label="모바일 주요 메뉴">
        {navigation.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              `flex shrink-0 items-center gap-1.5 rounded-lg px-3 py-2 text-xs ${isActive ? 'bg-slate-900 font-bold text-white' : 'font-semibold text-slate-500'}`
            }
          >
            <Icon size={14} /> {label}
          </NavLink>
        ))}
        {auth.user?.role === 'admin' ? (
          <NavLink
            to="/admin/users"
            className={({ isActive }) =>
              `flex shrink-0 items-center gap-1.5 rounded-lg px-3 py-2 text-xs ${isActive ? 'bg-slate-900 font-bold text-white' : 'font-semibold text-slate-500'}`
            }
          >
            <UserCog size={14} /> 사용자 관리
          </NavLink>
        ) : null}
      </nav>
    </header>
  )
}
