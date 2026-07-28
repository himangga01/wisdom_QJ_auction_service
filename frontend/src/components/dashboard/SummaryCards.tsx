import type { LucideIcon } from 'lucide-react'
import { Building2, Home, Landmark, UsersRound } from 'lucide-react'
import type { DashboardDataset } from '../../types/realEstate'
import { getDashboardMetrics } from '../../utils/dashboard'
import { formatKoreanPrice } from '../../utils/formatters'

interface SummaryCardsProps {
  dataset: DashboardDataset
}

export function SummaryCards({ dataset }: SummaryCardsProps) {
  const metrics = getDashboardMetrics(dataset)
  const items: Array<{
    label: string
    value: string
    caption: string
    icon: LucideIcon
    tone: string
  }> = [
    {
      label: '분석 아파트',
      value: `${metrics.apartmentCount}개`,
      caption: 'URL 내 확인 단지',
      icon: Building2,
      tone: 'bg-blue-50 text-blue-600',
    },
    {
      label: '대표 매물',
      value: `${metrics.groupCount}개`,
      caption: '동일 물건 묶음 기준',
      icon: Home,
      tone: 'bg-emerald-50 text-emerald-600',
    },
    {
      label: '중개사 등록',
      value: `${metrics.registrationCount}건`,
      caption: '매물별 중개사 원본',
      icon: UsersRound,
      tone: 'bg-violet-50 text-violet-600',
    },
    {
      label: '최저 매매가',
      value: formatKoreanPrice(metrics.minPrice),
      caption: '전체 대표 매물 기준',
      icon: Landmark,
      tone: 'bg-amber-50 text-amber-600',
    },
  ]

  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {items.map(({ label, value, caption, icon: Icon, tone }) => (
        <article key={label} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm shadow-slate-200/30">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-sm font-bold text-slate-500">{label}</p>
              <p className="mt-2 text-2xl font-black tracking-tight text-slate-950 tabular-nums">{value}</p>
            </div>
            <span className={`grid size-10 place-items-center rounded-xl ${tone}`}>
              <Icon size={19} strokeWidth={2.3} />
            </span>
          </div>
          <p className="mt-4 border-t border-slate-100 pt-3 text-xs font-medium text-slate-400">{caption}</p>
        </article>
      ))}
    </div>
  )
}
