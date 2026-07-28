import { ArrowRight, CircleMinus, CirclePlus, Equal, RefreshCcw } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { ApartmentSummary, ListingGroup } from '../../types/realEstate'
import { compareListingSnapshots, getListingsAt, type ListingChangePair } from '../../utils/listingHistory'
import { aggregateListingAdditionalInfo } from '../../utils/listingAdditionalInfo'
import { formatListingPrice, tradeTypeLabels } from '../../utils/formatters'

interface ListingComparisonBoardProps {
  apartment: ApartmentSummary
  beforeDate: string
  afterDate: string
  beforeListings?: ListingGroup[]
  afterListings?: ListingGroup[]
}

function Specs({ listing, changedFields = [] }: { listing: ListingGroup; changedFields?: ListingChangePair['changedFields'] }) {
  const additionalInformation = aggregateListingAdditionalInfo(listing)
  const specs = [
    ['호가', formatListingPrice(listing), changedFields.includes('price') || changedFields.includes('monthlyRent')],
    ['동·층', `${listing.building} · ${listing.floor}`, changedFields.includes('floor')],
    ['방향', listing.direction, changedFields.includes('direction')],
    ['전용면적', `${listing.exclusiveAreaM2}㎡`, false],
    ['방·욕실', additionalInformation.roomBathroomSummary, false],
    ['관리비', additionalInformation.managementFeeSummary, false],
    ['입주 가능', additionalInformation.moveInSummary, false],
    ['주요 옵션', additionalInformation.optionTags.join(', ') || '-', false],
    ['중개사 등록', `${listing.registrations.length}곳`, false],
  ]
  return <dl className="mt-3 space-y-2">{specs.map(([label, value, changed]) => <div key={String(label)} className={`flex items-center justify-between gap-3 rounded-lg px-3 py-2 text-sm ${changed ? 'bg-amber-100' : 'bg-slate-50'}`}><dt className="text-xs font-bold text-slate-400">{String(label)}</dt><dd className={`text-right font-extrabold ${changed ? 'text-amber-800' : 'text-slate-800'}`}>{String(value)}</dd></div>)}</dl>
}

function EmptySide({ label }: { label: string }) {
  return <div className="grid min-h-44 place-items-center rounded-xl border border-dashed border-slate-200 bg-slate-50 text-center"><div><CircleMinus className="mx-auto text-slate-300" size={24} /><p className="mt-2 text-xs font-bold text-slate-400">{label}에 없음</p></div></div>
}

function ComparisonCard({ apartment, type, before, after, changedFields }: { apartment: ApartmentSummary; type: 'added' | 'removed' | 'changed'; before?: ListingGroup; after?: ListingGroup; changedFields?: ListingChangePair['changedFields'] }) {
  const listing = after ?? before!
  const runQuery = listing.runId ? `?runId=${encodeURIComponent(listing.runId)}` : ''
  const config = type === 'added'
    ? { label: '새로 등록', icon: CirclePlus, tone: 'border-emerald-200 bg-emerald-50 text-emerald-700' }
    : type === 'removed'
      ? { label: '사라진 매물', icon: CircleMinus, tone: 'border-rose-200 bg-rose-50 text-rose-700' }
      : { label: '정보 변경', icon: RefreshCcw, tone: 'border-amber-200 bg-amber-50 text-amber-700' }
  const StatusIcon = config.icon

  return (
    <article className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 p-4">
        <div><p className="text-xs font-bold text-slate-400">{tradeTypeLabels[listing.tradeType]} · {listing.groupId}</p><h3 className="mt-1 font-black text-slate-950">{listing.building} · 전용 {listing.exclusiveAreaM2}㎡</h3></div>
        <span className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-extrabold ${config.tone}`}><StatusIcon size={14} /> {config.label}</span>
      </header>
      <div className="grid gap-3 p-4 md:grid-cols-[1fr_auto_1fr] md:items-center">
        <div><p className="mb-2 text-xs font-extrabold text-slate-500">비교 기준일</p>{before ? <Specs listing={before} changedFields={changedFields} /> : <EmptySide label="기준일" />}</div>
        <ArrowRight className="mx-auto hidden text-slate-300 md:block" size={18} />
        <div><p className="mb-2 text-xs font-extrabold text-slate-500">선택 조사일</p>{after ? <Specs listing={after} changedFields={changedFields} /> : <EmptySide label="선택일" />}</div>
      </div>
      <footer className="border-t border-slate-100 px-4 py-3 text-right"><Link to={`/apartments/${apartment.complexId}/listings/${listing.groupId}${runQuery}`} className="text-xs font-extrabold text-emerald-700">매물 상세 보기 →</Link></footer>
    </article>
  )
}

export function ListingComparisonBoard({ apartment, beforeDate, afterDate, beforeListings, afterListings }: ListingComparisonBoardProps) {
  const before = beforeListings ?? getListingsAt(apartment, beforeDate)
  const after = afterListings ?? getListingsAt(apartment, afterDate)
  const comparison = compareListingSnapshots(before, after)
  const differenceCount = comparison.added.length + comparison.removed.length + comparison.changed.length

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-4">
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4"><p className="text-xs font-bold text-emerald-700">새로 등록</p><p className="mt-1 text-2xl font-black text-emerald-900">{comparison.added.length}건</p></div>
        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4"><p className="text-xs font-bold text-amber-700">정보 변경</p><p className="mt-1 text-2xl font-black text-amber-900">{comparison.changed.length}건</p></div>
        <div className="rounded-2xl border border-rose-200 bg-rose-50 p-4"><p className="text-xs font-bold text-rose-700">사라진 매물</p><p className="mt-1 text-2xl font-black text-rose-900">{comparison.removed.length}건</p></div>
        <div className="rounded-2xl border border-slate-200 bg-white p-4"><p className="flex items-center gap-1 text-xs font-bold text-slate-500"><Equal size={13} /> 동일</p><p className="mt-1 text-2xl font-black text-slate-900">{comparison.unchanged.length}건</p></div>
      </div>

      {differenceCount ? (
        <div className="grid gap-4 xl:grid-cols-2">
          {comparison.added.map((listing) => <ComparisonCard key={`added-${listing.groupId}`} apartment={apartment} type="added" after={listing} />)}
          {comparison.changed.map((pair) => <ComparisonCard key={`changed-${pair.after.groupId}`} apartment={apartment} type="changed" before={pair.before} after={pair.after} changedFields={pair.changedFields} />)}
          {comparison.removed.map((listing) => <ComparisonCard key={`removed-${listing.groupId}`} apartment={apartment} type="removed" before={listing} />)}
        </div>
      ) : <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center text-sm font-semibold text-slate-400">두 조사일 사이에 달라진 매물이 없습니다.</div>}
    </div>
  )
}
