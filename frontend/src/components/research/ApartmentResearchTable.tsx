import { ArrowRight, MapPin } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { ApartmentSummary } from '../../types/realEstate'
import { getApartmentMetrics, getTradeMetrics } from '../../utils/dashboard'
import { formatCollectedAt } from '../../utils/formatters'

function ChangeSummary({ apartment }: { apartment: ApartmentSummary }) {
  const metrics = getApartmentMetrics(apartment)
  return (
    <div className="flex flex-wrap gap-1.5">
      {metrics.newCount ? <span className="rounded-full bg-emerald-50 px-2 py-1 text-xs font-bold text-emerald-700">신규 {metrics.newCount}</span> : null}
      {metrics.changedCount ? <span className="rounded-full bg-amber-50 px-2 py-1 text-xs font-bold text-amber-700">변경 {metrics.changedCount}</span> : null}
      {metrics.removedCount ? <span className="rounded-full bg-rose-50 px-2 py-1 text-xs font-bold text-rose-700">삭제 {metrics.removedCount}</span> : null}
      {!metrics.newCount && !metrics.changedCount && !metrics.removedCount ? <span className="text-xs text-slate-400">변경 없음</span> : null}
    </div>
  )
}

export function ApartmentResearchTable({ apartments }: { apartments: ApartmentSummary[] }) {
  return (
    <>
      <div className="hidden overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm md:block">
        <table className="w-full border-collapse text-left">
          <thead className="bg-slate-50 text-xs font-extrabold text-slate-500">
            <tr>
              <th className="px-5 py-4">아파트</th>
              <th className="px-4 py-4">최근 조사</th>
              <th className="px-4 py-4 text-center">매매</th>
              <th className="px-4 py-4 text-center">전세</th>
              <th className="px-4 py-4 text-center">월세</th>
              <th className="px-4 py-4">이번 조사 변경</th>
              <th className="w-14 px-4 py-4"><span className="sr-only">상세</span></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {apartments.map((apartment) => {
              const latest = apartment.history.at(-1)
              return (
                <tr key={apartment.complexId} className="transition hover:bg-slate-50/70">
                  <td className="px-5 py-5">
                    <Link to={`/apartments/${apartment.complexId}`} className="font-extrabold text-slate-950 hover:text-emerald-700">{apartment.complexName}</Link>
                    <p className="mt-1 flex items-center gap-1 text-xs text-slate-400"><MapPin size={12} /> {apartment.address}</p>
                  </td>
                  <td className="px-4 py-5 text-xs font-semibold text-slate-500">{latest ? formatCollectedAt(latest.collectedAt) : '-'}</td>
                  {(['sale', 'jeonse', 'monthly'] as const).map((tradeType) => (
                    <td key={tradeType} className="px-4 py-5 text-center text-sm font-black text-slate-800">{getTradeMetrics(apartment, tradeType).count}건</td>
                  ))}
                  <td className="px-4 py-5"><ChangeSummary apartment={apartment} /></td>
                  <td className="px-4 py-5"><Link to={`/apartments/${apartment.complexId}`} aria-label={`${apartment.complexName} 상세 보기`} className="grid size-9 place-items-center rounded-full bg-slate-100 text-slate-500 hover:bg-emerald-600 hover:text-white"><ArrowRight size={16} /></Link></td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <div className="grid gap-3 md:hidden">
        {apartments.map((apartment) => {
          const latest = apartment.history.at(-1)
          return (
            <Link key={apartment.complexId} to={`/apartments/${apartment.complexId}`} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="flex items-start justify-between gap-3">
                <div><h2 className="font-black text-slate-950">{apartment.complexName}</h2><p className="mt-1 text-xs text-slate-400">{apartment.address}</p></div>
                <ArrowRight className="text-slate-400" size={18} />
              </div>
              <div className="mt-4 grid grid-cols-3 rounded-xl bg-slate-50 p-3 text-center">
                {(['sale', 'jeonse', 'monthly'] as const).map((type, index) => (
                  <div key={type} className={index ? 'border-l border-slate-200' : ''}>
                    <p className="text-xs text-slate-400">{type === 'sale' ? '매매' : type === 'jeonse' ? '전세' : '월세'}</p>
                    <p className="mt-1 font-black text-slate-900">{getTradeMetrics(apartment, type).count}건</p>
                  </div>
                ))}
              </div>
              <div className="mt-4 flex items-center justify-between gap-3"><ChangeSummary apartment={apartment} /><span className="text-[11px] text-slate-400">{latest ? formatCollectedAt(latest.collectedAt) : '-'}</span></div>
            </Link>
          )
        })}
      </div>
    </>
  )
}
