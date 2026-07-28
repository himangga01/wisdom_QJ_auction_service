import { ArrowRight, Building2, Clock3, MapPin, Search } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { DatasetRequired } from '../components/analysis/DatasetRequired'
import { ExcelDownloadButton } from '../components/export/ExcelDownloadButton'
import { ApartmentResearchTable } from '../components/research/ApartmentResearchTable'
import { useAnalysis } from '../state/AnalysisProvider'
import { useDemoAnalysis } from '../state/DemoAnalysisContext'
import type { ApartmentSummaryApi } from '../types/api'
import { formatCollectedAt } from '../utils/formatters'

const statusLabels: Record<string, string> = {
  completed: '완료',
  partial: '일부 완료',
  queued: '대기 중',
  running: '진행 중',
  failed: '실패',
  blocked: '차단됨',
  cancelled: '취소됨',
}

function RealApartmentTable({ apartments, onSelect }: { apartments: ApartmentSummaryApi[]; onSelect: (complexId: string) => void }) {
  return (
    <>
      <div className="hidden overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm md:block">
        <table className="w-full border-collapse text-left">
          <thead className="bg-slate-50 text-xs font-extrabold text-slate-500">
            <tr>
              <th className="px-5 py-4">아파트</th>
              <th className="px-4 py-4">최근 조사</th>
              <th className="px-4 py-4 text-center">매물 수</th>
              <th className="px-4 py-4">상태</th>
              <th className="w-14 px-4 py-4"><span className="sr-only">상세</span></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {apartments.map((apartment) => (
              <tr key={apartment.apartmentId} className="transition hover:bg-slate-50/70">
                <td className="px-5 py-5">
                  <Link onClick={() => onSelect(apartment.complexId)} to={`/apartments/${apartment.complexId}`} className="font-extrabold text-slate-950 hover:text-emerald-700">{apartment.complexName}</Link>
                  <p className="mt-1 flex items-center gap-1 text-xs text-slate-400"><MapPin size={12} /> {apartment.address || '-'}</p>
                </td>
                <td className="px-4 py-5 text-xs font-semibold text-slate-500">{formatCollectedAt(apartment.collectedAt)}</td>
                <td className="px-4 py-5 text-center text-sm font-black text-slate-800">{apartment.listingCount.toLocaleString('ko-KR')}건</td>
                <td className="px-4 py-5"><span className="rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-bold text-emerald-700">{statusLabels[apartment.latestStatus] ?? apartment.latestStatus}</span></td>
                <td className="px-4 py-5"><Link onClick={() => onSelect(apartment.complexId)} to={`/apartments/${apartment.complexId}`} aria-label={`${apartment.complexName} 상세 보기`} className="grid size-9 place-items-center rounded-full bg-slate-100 text-slate-500 hover:bg-emerald-600 hover:text-white"><ArrowRight size={16} /></Link></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="grid gap-3 md:hidden">
        {apartments.map((apartment) => (
          <Link key={apartment.apartmentId} onClick={() => onSelect(apartment.complexId)} to={`/apartments/${apartment.complexId}`} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-start justify-between gap-3">
              <div><h2 className="font-black text-slate-950">{apartment.complexName}</h2><p className="mt-1 text-xs text-slate-400">{apartment.address || '-'}</p></div>
              <ArrowRight className="text-slate-400" size={18} />
            </div>
            <div className="mt-4 flex items-center justify-between rounded-xl bg-slate-50 p-3">
              <span className="text-xs font-semibold text-slate-500">매물 <strong className="text-slate-900">{apartment.listingCount.toLocaleString('ko-KR')}건</strong></span>
              <span className="text-[11px] text-slate-400">{formatCollectedAt(apartment.collectedAt)}</span>
            </div>
          </Link>
        ))}
      </div>
    </>
  )
}

export function ApartmentsPage() {
  const analysis = useAnalysis()
  const demo = useDemoAnalysis()
  const [query, setQuery] = useState('')
  const normalized = query.trim().toLowerCase()
  const demoApartments = useMemo(
    () => (demo.dataset?.apartments ?? []).filter((apartment) => `${apartment.complexName} ${apartment.address}`.toLowerCase().includes(normalized)),
    [demo.dataset, normalized],
  )
  const realApartments = useMemo(
    () => analysis.recentApartments.filter((apartment) => `${apartment.complexName} ${apartment.address}`.toLowerCase().includes(normalized)),
    [analysis.recentApartments, normalized],
  )
  const total = analysis.isDemo ? (demo.dataset?.apartments.length ?? 0) : analysis.recentApartments.length

  if (analysis.isDemo && !demo.dataset) return <DatasetRequired />
  if (!analysis.isDemo && !analysis.recentApartments.length) {
    return <DatasetRequired isLoading={analysis.isLoading} error={analysis.error} />
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="flex items-center gap-2 text-sm font-extrabold text-emerald-700"><Building2 size={17} /> 조사 아파트</p>
          <h1 className="mt-1 text-3xl font-black tracking-[-0.04em] text-slate-950">저장된 아파트 {total}개</h1>
          {analysis.isDemo && demo.dataset ? <p className="mt-2 flex items-center gap-1.5 text-sm text-slate-500"><Clock3 size={15} /> 전체 조사 완료 {formatCollectedAt(demo.dataset.collectedAt)}</p> : null}
        </div>
        <ExcelDownloadButton dataset={analysis.isDemo ? demo.dataset ?? undefined : undefined} />
      </header>

      <div className="relative max-w-md">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" size={17} />
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          className="h-12 w-full rounded-xl border border-slate-300 bg-white pl-11 pr-4 text-sm outline-none focus:border-emerald-500 focus:ring-4 focus:ring-emerald-100"
          placeholder="아파트명 또는 주소 검색"
          aria-label="아파트 검색"
        />
      </div>

      {analysis.isDemo ? (
        demoApartments.length ? <ApartmentResearchTable apartments={demoApartments} /> : <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center text-sm font-semibold text-slate-400">검색 결과가 없습니다.</div>
      ) : realApartments.length ? (
        <RealApartmentTable apartments={realApartments} onSelect={analysis.selectApartment} />
      ) : (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center text-sm font-semibold text-slate-400">검색 결과가 없습니다.</div>
      )}
    </div>
  )
}
