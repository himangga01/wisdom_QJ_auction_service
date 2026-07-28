import { AlertTriangle, BedDouble, CalendarCheck2, Layers3, Sparkles, WalletCards } from 'lucide-react'
import type { ListingGroup } from '../../types/realEstate'
import { aggregateListingAdditionalInfo } from '../../utils/listingAdditionalInfo'

export function ListingAdditionalInfo({ listing }: { listing: ListingGroup }) {
  const information = aggregateListingAdditionalInfo(listing)
  const summaries = [
    [CalendarCheck2, '입주 가능일', information.moveInSummary],
    [WalletCards, '관리비', information.managementFeeSummary],
    [BedDouble, '방·욕실', information.roomBathroomSummary],
    [Layers3, '융자 정보', information.loanSummary],
  ]

  return (
    <section className="mt-4 rounded-2xl border border-emerald-200 bg-emerald-50/60 p-4 sm:p-5" aria-label="중개사 상세 취합 추가정보">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h4 className="flex items-center gap-2 font-black text-slate-950"><Sparkles className="text-emerald-600" size={18} /> 추가정보</h4>
          <p className="mt-1 text-xs leading-5 text-slate-500">중개사 {information.sourceCount}곳의 상세 내용을 표준화하고 중복을 제거한 결과입니다.</p>
        </div>
        <span className="rounded-full bg-white px-3 py-1.5 text-[11px] font-extrabold text-emerald-700 shadow-sm">자동 취합</span>
      </div>

      <div className="mt-4">
        <p className="text-[11px] font-extrabold text-slate-400">확인된 옵션·특징</p>
        {information.optionTags.length ? (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {information.optionTags.map((tag) => <span key={tag} className="rounded-lg border border-emerald-200 bg-white px-2.5 py-1.5 text-xs font-extrabold text-emerald-700">{tag}</span>)}
          </div>
        ) : <p className="mt-2 text-sm font-bold text-slate-400">추가 옵션 정보 없음</p>}
      </div>

      <dl className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        {summaries.map(([Icon, label, value]) => {
          const SummaryIcon = Icon as typeof CalendarCheck2
          return (
            <div key={String(label)} className="rounded-xl bg-white p-3.5 shadow-sm">
              <dt className="flex items-center gap-1.5 text-[11px] font-bold text-slate-400"><SummaryIcon size={13} /> {String(label)}</dt>
              <dd className="mt-1.5 text-xs font-extrabold leading-5 text-slate-800">{String(value)}</dd>
            </div>
          )
        })}
      </dl>

      {information.warningCount ? (
        <p className="mt-3 flex items-center gap-1.5 text-xs font-bold text-amber-700"><AlertTriangle size={14} /> 중개사별 설명이 서로 다른 항목 {information.warningCount}건은 펼친 상세 카드에서 확인할 수 있습니다.</p>
      ) : null}
    </section>
  )
}
