import { useQuery } from '@tanstack/react-query'
import { Building2, Clock3, MapPin } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { adaptDashboard } from '../adapters/realEstate'
import { apartmentKeys, getDashboard } from '../api/apartments'
import { DatasetRequired } from '../components/analysis/DatasetRequired'
import { MarketCharts } from '../components/dashboard/MarketCharts'
import { useAnalysis } from '../state/AnalysisProvider'
import { useDemoAnalysis } from '../state/DemoAnalysisContext'
import { formatCollectedAt } from '../utils/formatters'

export function DashboardPage() {
  const analysis = useAnalysis()
  const demo = useDemoAnalysis()
  const [selectedRealApartmentId, setSelectedRealApartmentId] = useState<string | null>(null)

  const recentApartments = useMemo(
    () => [...analysis.recentApartments].sort((left, right) => Date.parse(right.collectedAt) - Date.parse(left.collectedAt)),
    [analysis.recentApartments],
  )
  const effectiveSelectedId = selectedRealApartmentId ?? analysis.selectedApartmentId
  const selectedSummary = recentApartments.find((apartment) => apartment.complexId === effectiveSelectedId) ?? recentApartments[0]
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
  const options = analysis.isDemo ? (demo.dataset?.apartments ?? []) : recentApartments
  const loading = analysis.isDemo ? false : analysis.isLoading || dashboardQuery.isLoading
  const queryError = dashboardQuery.error instanceof Error ? dashboardQuery.error.message : ''

  if (!dataset || !selectedApartment) {
    return <DatasetRequired isLoading={loading} error={analysis.error || queryError} />
  }

  const selectApartment = (complexId: string) => {
    if (analysis.isDemo) {
      demo.setSelectedApartmentId(complexId)
      return
    }
    setSelectedRealApartmentId(complexId)
    analysis.selectApartment(complexId)
  }

  const latestCollectedAt = analysis.isDemo
    ? selectedApartment.history.at(-1)?.collectedAt ?? dataset.collectedAt
    : selectedSummary?.collectedAt ?? dataset.collectedAt

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-sm font-extrabold text-emerald-700">최근 아파트 조사 결과</p>
          <h1 className="mt-1 text-3xl font-black tracking-[-0.04em] text-slate-950">{selectedApartment.complexName}</h1>
          <p className="mt-2 flex items-center gap-1.5 text-sm text-slate-500"><MapPin size={15} /> {selectedApartment.address}</p>
          <p className="mt-1 flex items-center gap-1.5 text-xs text-slate-400"><Clock3 size={14} /> 최근 조사 {formatCollectedAt(latestCollectedAt)}</p>
        </div>
        <div className="w-full rounded-2xl border border-slate-200 bg-white p-4 shadow-sm lg:w-[360px]">
          <label htmlFor="dashboard-apartment" className="flex items-center gap-2 text-xs font-extrabold text-slate-500"><Building2 size={15} /> 분석 아파트 선택</label>
          <select
            id="dashboard-apartment"
            value={analysis.isDemo ? selectedApartment.complexId : selectedSummary?.complexId}
            onChange={(event) => selectApartment(event.target.value)}
            className="mt-2 h-11 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm font-extrabold text-slate-900 outline-none focus:border-emerald-500 focus:ring-4 focus:ring-emerald-100"
          >
            {options.map((apartment) => <option key={apartment.complexId} value={apartment.complexId}>{apartment.complexName}</option>)}
          </select>
          <Link to="/apartments" className="mt-2 inline-flex text-xs font-bold text-emerald-700">조사한 아파트 {options.length}개 전체 보기 →</Link>
        </div>
      </header>

      <MarketCharts apartment={selectedApartment} />
    </div>
  )
}
