import { ChevronRight, MapPin } from 'lucide-react'
import type { ApartmentSummary } from '../../types/realEstate'
import { getApartmentMetrics } from '../../utils/dashboard'
import { formatKoreanPrice } from '../../utils/formatters'

interface ApartmentCardListProps {
  apartments: ApartmentSummary[]
  onSelect: (apartment: ApartmentSummary) => void
}

export function ApartmentCardList({ apartments, onSelect }: ApartmentCardListProps) {
  return (
    <div className="grid gap-3 lg:hidden">
      {apartments.map((apartment) => {
        const metrics = getApartmentMetrics(apartment)
        return (
          <button key={apartment.complexId} type="button" onClick={() => onSelect(apartment)} className="rounded-2xl border border-slate-200 bg-white p-5 text-left shadow-sm">
            <div className="flex items-start justify-between gap-4">
              <div>
                <strong className="text-base font-black text-slate-900">{apartment.complexName}</strong>
                <span className="mt-1 flex items-center gap-1 text-xs text-slate-400"><MapPin size={12} />{apartment.address}</span>
              </div>
              <ChevronRight className="text-slate-400" size={19} />
            </div>
            <p className="mt-5 text-lg font-black tabular-nums text-slate-950">{formatKoreanPrice(metrics.minPrice)} ~ {formatKoreanPrice(metrics.maxPrice)}</p>
            <div className="mt-4 flex flex-wrap gap-2 text-xs font-bold">
              <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-emerald-700">대표 {metrics.groupCount}개</span>
              <span className="rounded-full bg-violet-50 px-2.5 py-1 text-violet-700">중개사 {metrics.registrationCount}건</span>
              <span className="rounded-full bg-slate-100 px-2.5 py-1 text-slate-600">{metrics.areas.map((area) => `${area}㎡`).join(' · ')}</span>
            </div>
          </button>
        )
      })}
    </div>
  )
}
