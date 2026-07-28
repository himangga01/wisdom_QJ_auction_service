import { useQuery } from '@tanstack/react-query'
import { Clock3, MapPin } from 'lucide-react'
import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import { adaptDashboard } from '../adapters/realEstate'
import { apartmentKeys, getDashboard } from '../api/apartments'
import { DatasetRequired } from '../components/analysis/DatasetRequired'
import { DashboardApartmentPicker } from '../components/dashboard/DashboardApartmentPicker'
import { MarketCharts } from '../components/dashboard/MarketCharts'
import { useAnalysis } from '../state/AnalysisProvider'
import { useDemoAnalysis } from '../state/DemoAnalysisContext'
import { formatCollectedAt } from '../utils/formatters'

export function DashboardPage() {
  const analysis = useAnalysis()
  const demo = useDemoAnalysis()
  const selectedSummary = analysis.selectedApartment
  const sourceId = selectedSummary?.sourceId
  const dashboardQuery = useQuery({
    queryKey: apartmentKeys.dashboard(sourceId),
    queryFn: () => getDashboard(sourceId),
    enabled: !analysis.isDemo && Boolean(sourceId),
    staleTime: 30_000,
  })
  const realDataset = useMemo(
    () => dashboardQuery.data ? adaptDashboard(dashboardQuery.data) : null,
    [dashboardQuery.data],
  )
  const dataset = analysis.isDemo ? demo.dataset : realDataset
  const selectedApartment = analysis.isDemo
    ? dataset?.apartments.find((apartment) => apartment.complexId === demo.selectedApartmentId) ?? dataset?.apartments[0]
    : dataset?.apartments[0]
  const loading = analysis.isDemo ? false : analysis.isLoading || dashboardQuery.isLoading
  const queryError = dashboardQuery.error instanceof Error ? dashboardQuery.error.message : ''
  const latestCollectedAt = analysis.isDemo
    ? selectedApartment?.history.at(-1)?.collectedAt ?? dataset?.collectedAt
    : selectedSummary?.collectedAt ?? dataset?.collectedAt
  const apartmentCount = analysis.isDemo
    ? (demo.dataset?.apartments.length ?? 0)
    : (dashboardQuery.data?.apartmentCount ?? 0)

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-sm font-extrabold text-emerald-700">최근 아파트 조사 결과</p>
          <h1 className="mt-1 text-3xl font-black tracking-[-0.04em] text-slate-950">{selectedApartment?.complexName ?? '아파트를 선택해 주세요'}</h1>
          {selectedApartment ? <p className="mt-2 flex items-center gap-1.5 text-sm text-slate-500"><MapPin size={15} /> {selectedApartment.address}</p> : null}
          {latestCollectedAt ? <p className="mt-1 flex items-center gap-1.5 text-xs text-slate-400"><Clock3 size={14} /> 최근 조사 {formatCollectedAt(latestCollectedAt)}</p> : null}
        </div>
        {analysis.isDemo ? (
          <div className="w-full rounded-2xl border border-slate-200 bg-white p-4 shadow-sm lg:w-[360px]">
            <label htmlFor="dashboard-apartment" className="text-xs font-extrabold text-slate-500">분석 아파트 선택</label>
            <select
              id="dashboard-apartment"
              value={selectedApartment?.complexId ?? ''}
              onChange={(event) => demo.setSelectedApartmentId(event.target.value)}
              className="mt-2 h-11 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm font-extrabold text-slate-900 outline-none focus:border-emerald-500 focus:ring-4 focus:ring-emerald-100"
            >
              {(demo.dataset?.apartments ?? []).map((apartment) => <option key={apartment.complexId} value={apartment.complexId}>{apartment.complexName}</option>)}
            </select>
          </div>
        ) : (
          <DashboardApartmentPicker selectedApartment={selectedSummary} onSelect={analysis.selectApartment} />
        )}
      </header>

      <Link to="/apartments" className="inline-flex text-xs font-bold text-emerald-700">조사된 아파트 {apartmentCount.toLocaleString('ko-KR')}개 전체 보기 →</Link>

      {!dataset || !selectedApartment ? (
        <DatasetRequired isLoading={loading} error={analysis.error || queryError} />
      ) : (
        <MarketCharts apartment={selectedApartment} />
      )}
    </div>
  )
}
