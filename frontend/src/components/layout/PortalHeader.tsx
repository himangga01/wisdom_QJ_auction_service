import { BarChart3, Building2, CalendarClock, Link2, Sparkles } from 'lucide-react'
import { NavLink } from 'react-router-dom'

const navigation = [
  { to: '/', label: 'URL 조사', icon: Link2, end: true },
  { to: '/dashboard', label: '대시보드', icon: BarChart3 },
  { to: '/apartments', label: '조사 아파트', icon: Building2 },
  { to: '/schedules', label: '조사 스케줄', icon: CalendarClock },
]

export function PortalHeader() {
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
          <span className="hidden text-xs font-medium text-slate-400 sm:inline">프런트엔드 UX 프리뷰</span>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-extrabold text-emerald-700">
            <Sparkles size={13} /> DEMO
          </span>
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
      </nav>
    </header>
  )
}
