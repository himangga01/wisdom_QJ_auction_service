import { ArrowRight, Users } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { ApartmentSummary, ListingGroup } from '../../types/realEstate'
import { formatArea, formatCollectedAt, formatListingPrice, formatKoreanPrice, tradeTypeLabels } from '../../utils/formatters'
import { ChangeBadge } from './ChangeBadge'

function PriceCell({ listing }: { listing: ListingGroup }) {
  return (
    <div className={listing.status === 'removed' ? 'text-rose-500 line-through' : 'text-slate-950'}>
      <strong className="text-base font-black">{formatListingPrice(listing)}</strong>
      {listing.previousPrice ? <p className="mt-1 text-xs font-semibold text-amber-600 line-through">이전 {formatKoreanPrice(listing.previousPrice)}</p> : null}
    </div>
  )
}

export function ListingResearchTable({ apartment, listings }: { apartment: ApartmentSummary; listings: ListingGroup[] }) {
  return (
    <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white">
      <table className="w-full min-w-[920px] border-collapse text-left">
        <thead className="bg-slate-50 text-xs font-extrabold text-slate-500">
          <tr>
            <th className="px-5 py-4">상태</th><th className="px-4 py-4">거래</th><th className="px-4 py-4">동·층</th><th className="px-4 py-4">호가</th><th className="px-4 py-4">면적·방향</th><th className="px-4 py-4">중개사 등록</th><th className="px-4 py-4">마지막 확인</th><th className="w-14 px-4 py-4"><span className="sr-only">상세</span></th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {listings.map((listing) => (
            <tr key={listing.groupId} className={listing.status === 'new' ? 'bg-emerald-50/45' : listing.status === 'changed' ? 'bg-amber-50/45' : listing.status === 'removed' ? 'bg-rose-50/55' : ''}>
              <td className="px-5 py-4"><ChangeBadge status={listing.status} /></td>
              <td className="px-4 py-4 text-sm font-extrabold text-slate-700">{tradeTypeLabels[listing.tradeType]}</td>
              <td className="px-4 py-4"><p className="font-extrabold text-slate-900">{listing.building}</p><p className="mt-1 text-xs text-slate-400">{listing.floor}</p></td>
              <td className="px-4 py-4"><PriceCell listing={listing} /></td>
              <td className="px-4 py-4"><p className="text-sm font-semibold text-slate-700">{formatArea(listing)}</p><p className="mt-1 text-xs text-slate-400">{listing.direction}</p></td>
              <td className="px-4 py-4"><span className="inline-flex items-center gap-1.5 text-sm font-bold text-slate-700"><Users size={15} /> {listing.registrations.length}곳</span></td>
              <td className="px-4 py-4"><p className="text-xs font-semibold text-slate-600">{formatCollectedAt(listing.lastSeenAt)}</p>{listing.removedAt ? <p className="mt-1 text-xs font-bold text-rose-600">삭제 확인 {formatCollectedAt(listing.removedAt)}</p> : null}</td>
              <td className="px-4 py-4"><Link to={`/apartments/${apartment.complexId}/listings/${listing.groupId}`} aria-label={`${listing.building} 매물 상세 보기`} className="grid size-9 place-items-center rounded-full bg-slate-100 text-slate-500 hover:bg-slate-900 hover:text-white"><ArrowRight size={16} /></Link></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
