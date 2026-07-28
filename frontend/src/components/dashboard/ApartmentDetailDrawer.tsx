import { Building2, CalendarCheck2, ChevronDown, ExternalLink, MapPin, UsersRound } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { ApartmentSummary } from '../../types/realEstate'
import { getApartmentMetrics } from '../../utils/dashboard'
import { formatArea, formatKoreanPrice } from '../../utils/formatters'
import { Drawer } from '../ui/Drawer'

interface ApartmentDetailDrawerProps {
  apartment: ApartmentSummary | null
  onClose: () => void
}

export function ApartmentDetailDrawer({ apartment, onClose }: ApartmentDetailDrawerProps) {
  const [expandedGroupId, setExpandedGroupId] = useState<string | null>(null)

  useEffect(() => {
    setExpandedGroupId(apartment?.listingGroups[0]?.groupId ?? null)
  }, [apartment])

  if (!apartment) return null
  const metrics = getApartmentMetrics(apartment)

  return (
    <Drawer open title={`${apartment.complexName} 상세`} onClose={onClose}>
      <section className="rounded-2xl bg-slate-950 p-5 text-white shadow-lg shadow-slate-300/50">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-xs font-bold text-emerald-300"><MapPin size={14} />{apartment.address}</div>
            <h3 className="mt-2 text-xl font-black tracking-tight">{apartment.complexName}</h3>
          </div>
          <span className="rounded-full bg-white/10 px-3 py-1 text-xs font-bold">DEMO</span>
        </div>
        <div className="mt-6 grid grid-cols-3 gap-2">
          {[
            ['대표 매물', `${metrics.groupCount}개`],
            ['중개사 등록', `${metrics.registrationCount}건`],
            ['최저 호가', formatKoreanPrice(metrics.minPrice)],
          ].map(([label, value]) => (
            <div key={label} className="rounded-xl bg-white/7 p-3">
              <p className="text-[11px] text-slate-400">{label}</p>
              <p className="mt-1 text-sm font-black tabular-nums">{value}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mt-5">
        <div className="mb-3 flex items-center justify-between">
          <div>
            <h3 className="font-black text-slate-900">대표 매물과 중개사 등록</h3>
            <p className="mt-1 text-xs text-slate-400">대표 매물을 펼치면 연결된 등록 원본을 볼 수 있습니다.</p>
          </div>
          <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-extrabold text-emerald-700">{metrics.registrationCount}건</span>
        </div>

        <div className="space-y-3">
          {apartment.listingGroups.map((group) => {
            const expanded = expandedGroupId === group.groupId
            return (
              <article key={group.groupId} className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
                <button
                  type="button"
                  onClick={() => setExpandedGroupId(expanded ? null : group.groupId)}
                  className="flex w-full items-start gap-4 p-4 text-left transition hover:bg-slate-50"
                  aria-expanded={expanded}
                >
                  <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-emerald-50 text-emerald-700"><Building2 size={18} /></span>
                  <span className="min-w-0 flex-1">
                    <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
                      <strong className="font-black text-slate-900">{group.building}</strong>
                      <strong className="font-black text-emerald-700">매매 {formatKoreanPrice(group.price)}</strong>
                    </span>
                    <span className="mt-1.5 block text-xs font-medium text-slate-500">{formatArea(group)} · {group.floor} · {group.direction}</span>
                    <span className="mt-2 inline-flex items-center gap-1 rounded-full bg-violet-50 px-2.5 py-1 text-[11px] font-extrabold text-violet-700">
                      <UsersRound size={12} /> 중개사 {group.registrations.length}곳에서 등록
                    </span>
                  </span>
                  <ChevronDown className={`mt-2 shrink-0 text-slate-400 transition ${expanded ? 'rotate-180' : ''}`} size={18} />
                </button>

                {expanded ? (
                  <div className="border-t border-slate-100 bg-slate-50/70 p-3 sm:p-4">
                    <div className="space-y-2.5">
                      {group.registrations.map((item) => (
                        <div key={item.articleId} className="rounded-xl border border-slate-200 bg-white p-4">
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <strong className="block truncate text-sm font-extrabold text-slate-900">{item.realtorName}</strong>
                              <span className="mt-1 inline-flex rounded-md bg-slate-100 px-2 py-0.5 text-[10px] font-bold text-slate-500">{item.provider}</span>
                            </div>
                            <span className="flex shrink-0 items-center gap-1 text-[11px] font-semibold text-slate-400"><CalendarCheck2 size={13} />{item.verifiedAt.replaceAll('-', '.')}</span>
                          </div>
                          <p className="mt-3 text-xs leading-5 text-slate-600">{item.description}</p>
                          <div className="mt-3 flex items-center justify-between border-t border-slate-100 pt-3">
                            <span className="text-[10px] font-medium text-slate-400">매물 ID {item.articleId}</span>
                            <button type="button" className="inline-flex items-center gap-1 text-xs font-extrabold text-slate-400" title="데모에서는 외부 페이지로 이동하지 않습니다">
                              상세 링크 <ExternalLink size={12} />
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}
              </article>
            )
          })}
        </div>
      </section>
    </Drawer>
  )
}
