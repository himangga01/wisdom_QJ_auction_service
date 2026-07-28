import { ChevronDown, ExternalLink, ShieldCheck, Users } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { ApartmentSummary, ListingGroup } from '../../types/realEstate'
import { formatListingPrice, formatKoreanPrice, tradeTypeLabels } from '../../utils/formatters'
import { aggregateListingAdditionalInfo } from '../../utils/listingAdditionalInfo'
import { listingHref } from '../../utils/sourceLinks'
import { ChangeBadge } from './ChangeBadge'

export type ListingViewMode = 'card' | 'list' | 'table'

interface SnapshotListingCardsProps {
  apartment: ApartmentSummary
  listings: ListingGroup[]
  viewMode: ListingViewMode
}

function detailUrl(apartment: ApartmentSummary, listing: ListingGroup): string {
  return listingHref(apartment.complexId, listing.groupId, {
    sourceId: apartment.sourceId,
    runId: listing.runId,
  })
}

function registrationCount(listing: ListingGroup): number {
  return listing.aggregate?.sourceCount ?? listing.registrations.length
}

function CompactOptionTags({ listing, limit = 5 }: { listing: ListingGroup; limit?: number }) {
  const information = aggregateListingAdditionalInfo(listing)
  const visibleTags = information.optionTags.slice(0, limit)
  const remainingCount = information.optionTags.length - visibleTags.length

  if (!visibleTags.length) return <span className="text-xs font-bold text-slate-400">추가 옵션 없음</span>

  return (
    <div className="flex flex-wrap gap-1.5">
      {visibleTags.map((tag) => <span key={tag} className="rounded-md bg-emerald-50 px-2 py-1 text-[11px] font-extrabold text-emerald-700">{tag}</span>)}
      {remainingCount > 0 ? <span className="rounded-md bg-slate-100 px-2 py-1 text-[11px] font-extrabold text-slate-500">+{remainingCount}</span> : null}
    </div>
  )
}

function CompactRegistrationList({ listing }: { listing: ListingGroup }) {
  const npayCount = listing.registrations.filter((registration) => registration.isNpay).length

  return (
    <details className="group mt-4 border-t border-slate-100 pt-3">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 rounded-lg py-1 outline-none focus-visible:ring-4 focus-visible:ring-emerald-100">
        <span className="flex items-center gap-1.5 text-xs font-extrabold text-slate-600"><Users size={14} /> 중개사 {registrationCount(listing)}곳에서 등록했어요{npayCount ? <span className="text-emerald-700">· Npay {npayCount}</span> : null}</span>
        <ChevronDown className="shrink-0 text-slate-400 transition-transform group-open:rotate-180" size={15} />
      </summary>
      <div className="mt-3 max-h-72 space-y-2 overflow-y-auto pr-1">
        {listing.registrations.map((registration) => (
          <article key={registration.articleId} className="rounded-lg border border-slate-200 bg-slate-50/70 p-3">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate text-xs font-extrabold text-slate-800">{registration.realtorName}</p>
                <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[11px] font-bold text-slate-400"><span>{registration.provider}</span>{registration.isNpay ? <span className="inline-flex items-center gap-1 text-emerald-700"><ShieldCheck size={11} /> Npay</span> : null}<span>#{registration.articleId}</span></div>
              </div>
              <a href={registration.articleUrl} target="_blank" rel="noreferrer" className="inline-flex shrink-0 items-center gap-1 text-[11px] font-extrabold text-emerald-700">원문 <ExternalLink size={11} /></a>
            </div>
            <p className="mt-2 line-clamp-2 text-xs leading-5 text-slate-600">{registration.description}</p>
            <p className="mt-2 text-[11px] font-bold text-slate-500">관리비 {registration.managementFee ? `${Math.round(registration.managementFee / 10_000)}만원` : '-'} · 입주 {registration.moveInDate ?? '-'} · 확인 {registration.verifiedAt}</p>
          </article>
        ))}
      </div>
    </details>
  )
}

function CompactCard({ apartment, listing }: { apartment: ApartmentSummary; listing: ListingGroup }) {
  const information = aggregateListingAdditionalInfo(listing)

  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm transition hover:-translate-y-0.5 hover:border-emerald-200 hover:shadow-md">
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="rounded-full bg-slate-900 px-2.5 py-1 text-[11px] font-extrabold text-white">{tradeTypeLabels[listing.tradeType]}</span>
          <ChangeBadge status={listing.status} />
        </div>
        <span className="text-[11px] font-bold text-slate-400">{listing.groupId}</span>
      </div>

      <h3 className="mt-3 text-2xl font-black tracking-[-0.035em] text-slate-950">{formatListingPrice(listing)}</h3>
      {listing.previousPrice ? <p className="mt-0.5 text-xs font-bold text-amber-700">이전 <span className="line-through">{formatKoreanPrice(listing.previousPrice)}</span></p> : null}

      <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 border-y border-slate-100 py-3 text-xs">
        <div><dt className="text-slate-400">동·층</dt><dd className="mt-0.5 font-extrabold text-slate-800">{listing.building} · {listing.floor}</dd></div>
        <div><dt className="text-slate-400">전용면적</dt><dd className="mt-0.5 font-extrabold text-slate-800">{listing.exclusiveAreaM2}㎡</dd></div>
        <div><dt className="text-slate-400">방향</dt><dd className="mt-0.5 font-extrabold text-slate-800">{listing.direction}</dd></div>
        <div><dt className="text-slate-400">중개사</dt><dd className="mt-0.5 font-extrabold text-slate-800">{registrationCount(listing)}곳</dd></div>
      </dl>

      <section className="mt-3 rounded-xl bg-slate-50 p-3">
        <p className="text-[11px] font-extrabold text-slate-400">추가정보</p>
        <div className="mt-2"><CompactOptionTags listing={listing} /></div>
        <p className="mt-2 line-clamp-2 text-[11px] font-bold leading-5 text-slate-500">관리비 {information.managementFeeSummary} · 입주 {information.moveInSummary}</p>
      </section>

      <div className="mt-3 flex items-center justify-between gap-3">
        <span className="text-[11px] font-bold text-slate-400">공급 {listing.supplyAreaM2}㎡</span>
        <Link to={detailUrl(apartment, listing)} className="inline-flex items-center gap-1 text-xs font-extrabold text-emerald-700">상세 보기 →</Link>
      </div>

      <CompactRegistrationList listing={listing} />
    </article>
  )
}

function ListingRow({ apartment, listing }: { apartment: ApartmentSummary; listing: ListingGroup }) {
  const information = aggregateListingAdditionalInfo(listing)

  return (
    <article className="rounded-2xl border border-slate-200 bg-white px-4 py-3.5 shadow-sm">
      <div className="grid gap-3 lg:grid-cols-[minmax(190px,1.15fr)_minmax(120px,0.7fr)_minmax(110px,0.65fr)_minmax(230px,1.4fr)_auto] lg:items-center">
        <div>
          <div className="flex flex-wrap items-center gap-1.5"><span className="rounded-full bg-slate-900 px-2 py-1 text-[10px] font-extrabold text-white">{tradeTypeLabels[listing.tradeType]}</span><ChangeBadge status={listing.status} /></div>
          <p className="mt-1.5 text-lg font-black text-slate-950">{formatListingPrice(listing)}</p>
        </div>
        <div className="text-xs"><p className="font-extrabold text-slate-800">{listing.building} · {listing.floor}</p><p className="mt-1 text-slate-400">{listing.direction}</p></div>
        <div className="text-xs"><p className="font-extrabold text-slate-800">전용 {listing.exclusiveAreaM2}㎡</p><p className="mt-1 text-slate-400">공급 {listing.supplyAreaM2}㎡</p></div>
        <div><CompactOptionTags listing={listing} limit={6} /><p className="mt-1.5 line-clamp-1 text-[11px] font-bold text-slate-400">관리비 {information.managementFeeSummary} · 입주 {information.moveInSummary}</p></div>
        <Link to={detailUrl(apartment, listing)} className="inline-flex w-fit shrink-0 items-center rounded-lg bg-slate-950 px-3 py-2 text-xs font-extrabold text-white hover:bg-emerald-700">상세 보기</Link>
      </div>
      <CompactRegistrationList listing={listing} />
    </article>
  )
}

function ListingTable({ apartment, listings }: { apartment: ApartmentSummary; listings: ListingGroup[] }) {
  return (
    <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-sm">
      <table className="min-w-[1040px] w-full border-collapse text-left text-xs">
        <thead className="bg-slate-50 text-[11px] font-extrabold text-slate-500">
          <tr><th className="px-4 py-3">거래·호가</th><th className="px-4 py-3">동·층</th><th className="px-4 py-3">면적</th><th className="px-4 py-3">방향</th><th className="px-4 py-3">추가정보</th><th className="px-4 py-3">관리비·입주</th><th className="px-4 py-3">중개사</th><th className="px-4 py-3 text-right">상세</th></tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {listings.map((listing) => {
            const information = aggregateListingAdditionalInfo(listing)
            return (
              <tr key={listing.groupId} className="align-top hover:bg-emerald-50/30">
                <td className="px-4 py-3"><div className="flex items-center gap-1.5"><span className="font-extrabold text-slate-500">{tradeTypeLabels[listing.tradeType]}</span><ChangeBadge status={listing.status} /></div><strong className="mt-1 block text-sm text-slate-950">{formatListingPrice(listing)}</strong></td>
                <td className="px-4 py-3 font-extrabold text-slate-800">{listing.building}<span className="mt-1 block font-bold text-slate-400">{listing.floor}</span></td>
                <td className="px-4 py-3 font-extrabold text-slate-800">전용 {listing.exclusiveAreaM2}㎡<span className="mt-1 block font-bold text-slate-400">공급 {listing.supplyAreaM2}㎡</span></td>
                <td className="px-4 py-3 font-extrabold text-slate-800">{listing.direction}</td>
                <td className="max-w-64 px-4 py-3"><CompactOptionTags listing={listing} limit={4} /></td>
                <td className="px-4 py-3 font-bold leading-5 text-slate-600">{information.managementFeeSummary}<span className="block text-slate-400">{information.moveInSummary}</span></td>
                <td className="px-4 py-3 font-extrabold text-slate-800">{registrationCount(listing)}곳<span className="mt-1 block font-bold text-slate-400">Npay {listing.registrations.filter((registration) => registration.isNpay).length}건</span></td>
                <td className="px-4 py-3 text-right"><Link to={detailUrl(apartment, listing)} className="inline-flex rounded-lg border border-slate-200 px-3 py-2 font-extrabold text-emerald-700 hover:border-emerald-300">보기</Link></td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

export function SnapshotListingCards({ apartment, listings, viewMode }: SnapshotListingCardsProps) {
  if (viewMode === 'table') return <ListingTable apartment={apartment} listings={listings} />
  if (viewMode === 'list') return <div className="space-y-2.5">{listings.map((listing) => <ListingRow key={listing.groupId} apartment={apartment} listing={listing} />)}</div>

  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {listings.map((listing) => <CompactCard key={listing.groupId} apartment={apartment} listing={listing} />)}
    </div>
  )
}
