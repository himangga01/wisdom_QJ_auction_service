import { ChevronRight, MapPin } from 'lucide-react'
import type { ApartmentSummary } from '../../types/realEstate'
import { getApartmentMetrics } from '../../utils/dashboard'
import { formatKoreanPrice } from '../../utils/formatters'

interface ApartmentTableProps {
  apartments: ApartmentSummary[]
  onSelect: (apartment: ApartmentSummary) => void
}

export function ApartmentTable({ apartments, onSelect }: ApartmentTableProps) {
  return (
    <div className="hidden overflow-hidden rounded-2xl border border-slate-200 bg-white lg:block">
      <table className="w-full border-collapse text-left">
        <thead className="bg-slate-50 text-xs font-extrabold text-slate-500">
          <tr>
            <th className="px-5 py-4">아파트</th>
            <th className="px-4 py-4 text-center">대표 매물</th>
            <th className="px-4 py-4 text-center">중개사 등록</th>
            <th className="px-4 py-4">매매 가격</th>
            <th className="px-4 py-4">전용면적</th>
            <th className="px-4 py-4">최근 확인</th>
            <th className="w-14 px-4 py-4"><span className="sr-only">상세</span></th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {apartments.map((apartment) => {
            const metrics = getApartmentMetrics(apartment)
            return (
              <tr key={apartment.complexId} className="group transition hover:bg-emerald-50/40">
                <td className="px-5 py-5">
                  <button
                    type="button"
                    onClick={() => onSelect(apartment)}
                    aria-label={`${apartment.complexName} 상세 보기`}
                    className="text-left"
                  >
                    <strong className="block text-sm font-extrabold text-slate-900 group-hover:text-emerald-700">{apartment.complexName}</strong>
                    <span className="mt-1 flex items-center gap-1 text-xs text-slate-400"><MapPin size={12} />{apartment.address}</span>
                  </button>
                </td>
                <td className="px-4 py-5 text-center text-sm font-black tabular-nums text-slate-800">{metrics.groupCount}</td>
                <td className="px-4 py-5 text-center">
                  <span className="rounded-full bg-violet-50 px-2.5 py-1 text-xs font-extrabold text-violet-700">{metrics.registrationCount}건</span>
                </td>
                <td className="px-4 py-5 text-sm font-extrabold tabular-nums text-slate-900">
                  {formatKoreanPrice(metrics.minPrice)}
                  <span className="mx-1 text-slate-300">~</span>
                  {formatKoreanPrice(metrics.maxPrice)}
                </td>
                <td className="px-4 py-5 text-xs font-semibold text-slate-600">{metrics.areas.map((area) => `${area}㎡`).join(', ')}</td>
                <td className="px-4 py-5 text-xs font-semibold tabular-nums text-slate-500">{metrics.latestVerifiedAt.replaceAll('-', '.')}</td>
                <td className="px-4 py-5">
                  <button type="button" onClick={() => onSelect(apartment)} aria-label={`${apartment.complexName} 상세 열기`} className="grid size-8 place-items-center rounded-lg text-slate-400 transition group-hover:bg-white group-hover:text-emerald-600">
                    <ChevronRight size={18} />
                  </button>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
