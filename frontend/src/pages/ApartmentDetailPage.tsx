import { useQueries, useQuery } from '@tanstack/react-query'
import { ArrowLeft, Building2, CalendarDays, Car, Clock3, Flame, Home, LayoutGrid, List as ListIcon, TableProperties } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { adaptApartmentDetail, adaptListing, adaptListingAbsence, adaptListingDetail } from '../adapters/realEstate'
import { apartmentKeys, getApartment, getApartmentListings, getListing } from '../api/apartments'
import { DatasetRequired } from '../components/analysis/DatasetRequired'
import { ApartmentHistoryChart } from '../components/research/ApartmentHistoryChart'
import { ListingComparisonBoard } from '../components/research/ListingComparisonBoard'
import { SnapshotListingCards, type ListingViewMode } from '../components/research/SnapshotListingCards'
import { useAnalysis } from '../state/AnalysisProvider'
import { useDemoAnalysis } from '../state/DemoAnalysisContext'
import type { ListingGroup, TradeType } from '../types/realEstate'
import { formatCollectedAt, formatKoreanPrice, tradeTypeLabels } from '../utils/formatters'
import { getListingsAt } from '../utils/listingHistory'

type TradeFilter = 'all' | TradeType

export function ApartmentDetailPage() {
  const { complexId } = useParams()
  const analysis = useAnalysis()
  const demo = useDemoAnalysis()
  const selectedSourceId = analysis.selectedApartment?.complexId === complexId
    ? analysis.selectedApartment.sourceId
    : undefined
  const apartmentQuery = useQuery({
    queryKey: apartmentKeys.detail(complexId ?? '', undefined, selectedSourceId),
    queryFn: () => getApartment(complexId as string, undefined, selectedSourceId),
    enabled: !analysis.isDemo && Boolean(complexId),
  })
  const demoApartment = demo.dataset?.apartments.find((item) => item.complexId === complexId)
  const apartmentBase = useMemo(
    () => analysis.isDemo ? demoApartment : (apartmentQuery.data ? adaptApartmentDetail(apartmentQuery.data) : undefined),
    [analysis.isDemo, apartmentQuery.data, demoApartment],
  )
  const dates = useMemo(() => apartmentBase?.history.map((point) => point.collectedAt) ?? [], [apartmentBase])
  const [selectedDate, setSelectedDate] = useState('')
  const [comparisonDate, setComparisonDate] = useState('')
  const [tradeFilter, setTradeFilter] = useState<TradeFilter>('all')
  const [listingViewMode, setListingViewMode] = useState<ListingViewMode>('card')

  useEffect(() => {
    const latest = dates.at(-1) ?? ''
    setSelectedDate(latest)
    setComparisonDate(dates.at(-2) ?? '')
    setTradeFilter('all')
    setListingViewMode('card')
  }, [complexId, dates])

  const effectiveSelectedDate = selectedDate || dates.at(-1) || ''
  const selectedIndex = dates.indexOf(effectiveSelectedDate)
  const effectiveComparisonDate = comparisonDate || (selectedIndex > 0 ? dates[selectedIndex - 1] : '')
  const comparisonOptions = dates.slice(0, Math.max(selectedIndex, 0))
  const selectedRunPoint = apartmentQuery.data?.history.find((point) => point.collectedAt === effectiveSelectedDate)
  const comparisonRunPoint = apartmentQuery.data?.history.find((point) => point.collectedAt === effectiveComparisonDate)
  const selectedRunId = selectedRunPoint?.runId
  const comparisonRunId = comparisonRunPoint?.runId
  const selectedApartmentQuery = useQuery({
    queryKey: apartmentKeys.detail(complexId ?? '', selectedRunId),
    queryFn: () => getApartment(complexId as string, selectedRunId),
    enabled: !analysis.isDemo && Boolean(complexId && selectedRunId),
  })
  const selectedListingsQuery = useQuery({
    queryKey: apartmentKeys.listings(complexId ?? '', selectedRunId),
    queryFn: () => getApartmentListings(complexId as string, { runId: selectedRunId }),
    enabled: !analysis.isDemo && Boolean(complexId && selectedRunId),
  })
  const comparisonListingsQuery = useQuery({
    queryKey: apartmentKeys.listings(complexId ?? '', comparisonRunId),
    queryFn: () => getApartmentListings(complexId as string, { runId: comparisonRunId }),
    enabled: !analysis.isDemo && Boolean(complexId && comparisonRunId),
  })
  const selectedListingRecords = useMemo(
    () => [
      ...(selectedListingsQuery.data?.items ?? []).map((listing) => ({
        groupId: listing.groupId,
        summary: listing,
        absence: undefined,
      })),
      ...(selectedListingsQuery.data?.absentItems ?? []).map((absence) => ({
        groupId: absence.groupId,
        summary: undefined,
        absence,
      })),
    ],
    [selectedListingsQuery.data?.absentItems, selectedListingsQuery.data?.items],
  )
  const comparisonListingRecords = useMemo(
    () => [
      ...(comparisonListingsQuery.data?.items ?? []).map((listing) => ({
        groupId: listing.groupId,
        summary: listing,
        absence: undefined,
      })),
      ...(comparisonListingsQuery.data?.absentItems ?? []).map((absence) => ({
        groupId: absence.groupId,
        summary: undefined,
        absence,
      })),
    ],
    [comparisonListingsQuery.data?.absentItems, comparisonListingsQuery.data?.items],
  )
  const selectedDetailQueries = useQueries({
    queries: selectedListingRecords.map((record) => ({
      queryKey: apartmentKeys.listing(record.groupId, selectedRunId),
      queryFn: () => getListing(record.groupId, selectedRunId),
      enabled: !analysis.isDemo,
    })),
  })
  const comparisonDetailQueries = useQueries({
    queries: comparisonListingRecords.map((record) => ({
      queryKey: apartmentKeys.listing(record.groupId, comparisonRunId),
      queryFn: () => getListing(record.groupId, comparisonRunId),
      enabled: !analysis.isDemo,
    })),
  })
  const selectedApiSnapshot = useMemo<ListingGroup[]>(
    () => selectedListingRecords.flatMap((record, index) => {
      if (!record.summary) return []
      const detail = selectedDetailQueries[index]?.data
      return [detail ? adaptListingDetail(detail) : adaptListing(record.summary)]
    }),
    [selectedDetailQueries, selectedListingRecords],
  )
  const selectedApiAbsences = useMemo<ListingGroup[]>(
    () => selectedListingRecords.flatMap((record, index) => {
      if (!record.absence) return []
      const detail = selectedDetailQueries[index]?.data
      if (!detail) return [adaptListingAbsence(record.absence, selectedRunId)]
      return [{
        ...adaptListingDetail(detail),
        status: record.absence.status,
        absenceDetectedAt: record.absence.detectedAt,
        removedAt: record.absence.removedAt ?? undefined,
      }]
    }),
    [selectedDetailQueries, selectedListingRecords],
  )
  const comparisonApiSnapshot = useMemo<ListingGroup[]>(
    () => comparisonListingRecords.flatMap((record, index) => {
      if (!record.summary) return []
      const detail = comparisonDetailQueries[index]?.data
      return [detail ? adaptListingDetail(detail) : adaptListing(record.summary)]
    }),
    [comparisonDetailQueries, comparisonListingRecords],
  )
  const comparisonApiAbsences = useMemo<ListingGroup[]>(
    () => comparisonListingRecords.flatMap((record, index) => {
      if (!record.absence) return []
      const detail = comparisonDetailQueries[index]?.data
      if (!detail) return [adaptListingAbsence(record.absence, comparisonRunId)]
      return [{
        ...adaptListingDetail(detail),
        status: record.absence.status,
        absenceDetectedAt: record.absence.detectedAt,
        removedAt: record.absence.removedAt ?? undefined,
      }]
    }),
    [comparisonDetailQueries, comparisonListingRecords],
  )
  const selectedSnapshot = analysis.isDemo && apartmentBase
    ? getListingsAt(apartmentBase, effectiveSelectedDate)
    : selectedApiSnapshot
  const selectedAbsentSnapshot = analysis.isDemo ? [] : selectedApiAbsences
  const comparisonSnapshot = analysis.isDemo && apartmentBase
    ? getListingsAt(apartmentBase, effectiveComparisonDate)
    : comparisonApiSnapshot
  const comparisonAbsentSnapshot = analysis.isDemo ? [] : comparisonApiAbsences
  const selectedComparisonSnapshot = [...selectedSnapshot, ...selectedAbsentSnapshot]
  const comparisonCombinedSnapshot = [...comparisonSnapshot, ...comparisonAbsentSnapshot]
  const apartment = useMemo(
    () => {
      if (analysis.isDemo) return apartmentBase
      const apartmentAtSelectedRun = selectedApartmentQuery.data ?? apartmentQuery.data
      return apartmentAtSelectedRun
        ? adaptApartmentDetail(apartmentAtSelectedRun, selectedSnapshot)
        : undefined
    },
    [analysis.isDemo, apartmentBase, apartmentQuery.data, selectedApartmentQuery.data, selectedSnapshot],
  )
  const visibleListings = selectedSnapshot.filter((listing) => tradeFilter === 'all' || listing.tradeType === tradeFilter)
  const visibleAbsentListings = selectedAbsentSnapshot.filter((listing) => tradeFilter === 'all' || listing.tradeType === tradeFilter)
  const comparisonDetailsLoading = [...selectedDetailQueries, ...comparisonDetailQueries].some((query) => query.isPending)
  const comparisonDetailsError = [...selectedDetailQueries, ...comparisonDetailQueries].some((query) => query.isError)

  if (analysis.isDemo && !demo.dataset) return <DatasetRequired />
  if (!analysis.isDemo && (apartmentQuery.isLoading || (selectedRunId && (selectedApartmentQuery.isLoading || selectedListingsQuery.isLoading)) || (comparisonRunId && comparisonListingsQuery.isLoading))) return <DatasetRequired isLoading />
  const queryError = apartmentQuery.error ?? selectedApartmentQuery.error ?? selectedListingsQuery.error ?? comparisonListingsQuery.error
  if (!analysis.isDemo && queryError) return <DatasetRequired error={queryError instanceof Error ? queryError.message : '아파트 상세를 불러오지 못했습니다.'} />
  if (!apartment) return <div className="rounded-2xl border border-slate-200 bg-white p-10 text-center"><h1 className="text-xl font-black">아파트를 찾을 수 없습니다</h1><Link to="/apartments" className="mt-4 inline-flex text-sm font-bold text-emerald-700">목록으로 돌아가기</Link></div>

  const selectResearchDate = (value: string) => {
    const index = dates.indexOf(value)
    setSelectedDate(value)
    setComparisonDate(index > 0 ? dates[index - 1] : '')
  }

  const getSnapshotMetrics = (tradeType: TradeType) => {
    const listings = selectedSnapshot.filter((listing) => listing.tradeType === tradeType)
    const averagePrice = listings.length ? listings.reduce((sum, listing) => sum + listing.price, 0) / listings.length : 0
    const averageMonthlyRent = listings.length ? listings.reduce((sum, listing) => sum + (listing.monthlyRent ?? 0), 0) / listings.length : 0
    return { count: listings.length, averagePrice, averageMonthlyRent }
  }
  const completeApartmentDetails = [
    ['세대수', apartment.details.householdCount > 0 ? `${apartment.details.householdCount.toLocaleString('ko-KR')}세대` : '-'],
    ['동 수', apartment.details.buildingCount > 0 ? `${apartment.details.buildingCount.toLocaleString('ko-KR')}개동` : '-'],
    ['사용승인일', apartment.details.approvalDate ?? (apartment.details.completedYear > 0 ? `${apartment.details.completedYear}년` : '-')],
    ['총 주차대수', apartment.details.parkingCount ? `${apartment.details.parkingCount.toLocaleString('ko-KR')}대` : '-'],
    ['세대당 주차', apartment.details.parkingPerHousehold > 0 ? `${apartment.details.parkingPerHousehold}대` : '-'],
    ['난방방식', apartment.details.heating || '-'],
    ['현관구조', apartment.details.entranceType || '-'],
    ['용적률', apartment.details.floorAreaRatio ? `${apartment.details.floorAreaRatio}%` : '-'],
    ['건폐율', apartment.details.buildingCoverageRatio ? `${apartment.details.buildingCoverageRatio}%` : '-'],
    ['관리사무소 전화', apartment.details.managementOfficePhone || '-'],
    ['시공사', apartment.details.builders?.length ? apartment.details.builders.join(', ') : '-'],
  ]

  return (
    <div className="space-y-6">
      <div>
        <Link to="/apartments" className="inline-flex items-center gap-1.5 text-sm font-bold text-slate-500 hover:text-slate-900"><ArrowLeft size={16} /> 조사 아파트 목록</Link>
        <div className="mt-5 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div><p className="text-sm font-extrabold text-emerald-700">아파트 조사 상세</p><h1 className="mt-1 text-3xl font-black tracking-[-0.04em] text-slate-950">{apartment.complexName}</h1><p className="mt-2 text-sm text-slate-500">{apartment.address}</p></div>
          <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-5 py-4"><p className="flex items-center gap-1.5 text-xs font-extrabold text-emerald-700"><Clock3 size={14} /> 현재 선택한 조사일</p><p className="mt-1 font-black text-slate-900">{formatCollectedAt(effectiveSelectedDate)}</p></div>
        </div>
      </div>

      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5" aria-label="단지 기본 정보">
        {[[Home, '세대수', apartment.details.householdCount > 0 ? `${apartment.details.householdCount.toLocaleString('ko-KR')}세대` : '-'], [Building2, '동 수', apartment.details.buildingCount > 0 ? `${apartment.details.buildingCount}개동` : '-'], [CalendarDays, '사용승인', apartment.details.approvalDate ?? (apartment.details.completedYear > 0 ? `${apartment.details.completedYear}년` : '-')], [Car, '주차', apartment.details.parkingCount ? `${apartment.details.parkingCount.toLocaleString('ko-KR')}대${apartment.details.parkingPerHousehold > 0 ? ` · 세대당 ${apartment.details.parkingPerHousehold}대` : ''}` : apartment.details.parkingPerHousehold > 0 ? `세대당 ${apartment.details.parkingPerHousehold}대` : '-'], [Flame, '난방', apartment.details.heating || '-']].map(([Icon, label, value]) => {
          const DetailIcon = Icon as typeof Home
          return <article key={String(label)} className="rounded-2xl border border-slate-200 bg-white p-4"><p className="flex items-center gap-2 text-xs font-bold text-slate-400"><DetailIcon size={15} /> {String(label)}</p><p className="mt-2 font-black text-slate-900">{String(value)}</p></article>
        })}
      </section>

      <details className="group rounded-2xl border border-slate-200 bg-white">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-5 py-4 text-sm font-extrabold text-slate-800">
          단지 기본정보 전체 보기
          <span className="text-xs font-bold text-slate-400 group-open:hidden">펼치기</span>
          <span className="hidden text-xs font-bold text-slate-400 group-open:inline">접기</span>
        </summary>
        <dl className="grid border-t border-slate-100 sm:grid-cols-2 lg:grid-cols-3">
          {completeApartmentDetails.map(([label, value]) => (
            <div key={label} className="border-b border-slate-100 px-5 py-4 last:border-b-0 sm:[&:nth-last-child(-n+2)]:border-b-0 lg:[&:nth-last-child(-n+3)]:border-b-0">
              <dt className="text-xs font-bold text-slate-400">{label}</dt>
              <dd className="mt-1.5 break-words text-sm font-extrabold text-slate-900">{value}</dd>
            </div>
          ))}
        </dl>
      </details>

      <section className="grid gap-3 lg:grid-cols-3" aria-label="선택 날짜 거래 유형별 현황">
        {(['sale', 'jeonse', 'monthly'] as TradeType[]).map((type) => {
          const trade = getSnapshotMetrics(type)
          const price = type === 'monthly' ? `${formatKoreanPrice(trade.averagePrice)} / ${Math.round(trade.averageMonthlyRent / 10_000)}만` : formatKoreanPrice(trade.averagePrice)
          return <article key={type} className="rounded-2xl border border-slate-200 bg-white p-5"><div className="flex items-center justify-between"><h2 className="font-extrabold text-slate-600">{tradeTypeLabels[type]}</h2><span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-bold text-slate-600">{trade.count}건</span></div><p className="mt-3 text-2xl font-black text-slate-950">{trade.count ? price : '-'}</p><p className="mt-1 text-xs text-slate-400">선택 조사일 평균 호가</p></article>
        })}
      </section>

      <article className="rounded-3xl border border-slate-200 bg-white p-5 sm:p-6">
        <h2 className="text-lg font-black text-slate-950">날짜별 매물 수</h2><p className="mt-1 text-xs text-slate-400">조사 회차마다 거래 유형별 노출 매물 수를 기록합니다.</p><div className="mt-4"><ApartmentHistoryChart apartment={apartment} /></div>
      </article>

      <section className="space-y-5" aria-labelledby="comparison-heading">
        <div className="rounded-3xl bg-slate-950 p-5 text-white sm:p-6">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div><p className="text-sm font-extrabold text-emerald-300">상품 사양 비교 방식</p><h2 id="comparison-heading" className="mt-1 text-2xl font-black">조사 날짜별 매물 비교</h2><p className="mt-2 text-sm text-slate-400">두 조사일의 동일 매물을 나란히 놓고 달라진 항목만 강조합니다.</p></div>
            <div className="grid gap-3 sm:grid-cols-2 lg:w-[610px]">
              <label className="text-xs font-bold text-slate-300">비교 기준일<select value={effectiveComparisonDate} onChange={(event) => setComparisonDate(event.target.value)} disabled={!comparisonOptions.length} className="mt-2 h-11 w-full rounded-xl border border-white/15 bg-white/10 px-3 text-sm font-extrabold text-white outline-none disabled:opacity-50">{comparisonOptions.map((date) => <option key={date} value={date} className="text-slate-900">{formatCollectedAt(date)}</option>)}</select></label>
              <label className="text-xs font-bold text-slate-300">선택 조사일<select value={effectiveSelectedDate} onChange={(event) => selectResearchDate(event.target.value)} className="mt-2 h-11 w-full rounded-xl border border-emerald-400 bg-white px-3 text-sm font-extrabold text-slate-950 outline-none">{dates.map((date) => <option key={date} value={date}>{formatCollectedAt(date)}</option>)}</select></label>
            </div>
          </div>
        </div>
        {!analysis.isDemo && comparisonDetailsLoading ? <div className="rounded-2xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm font-bold text-sky-700">중개사별 추가 상세정보를 불러오는 중입니다. 기본 매물 정보부터 먼저 표시합니다.</div> : null}
        {!analysis.isDemo && comparisonDetailsError ? <div role="alert" className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm font-bold text-amber-800">일부 중개사 상세정보를 불러오지 못해 해당 항목은 비교에서 제외했습니다.</div> : null}
        {effectiveComparisonDate ? <ListingComparisonBoard apartment={apartment} beforeDate={effectiveComparisonDate} afterDate={effectiveSelectedDate} beforeListings={comparisonCombinedSnapshot} afterListings={selectedComparisonSnapshot} beforeRunStatus={comparisonRunPoint?.status} /> : <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center text-sm font-semibold text-slate-400">이 날짜보다 이전 조사 기록이 없어 비교할 수 없습니다.</div>}
      </section>

      <section className="space-y-4" aria-labelledby="snapshot-list-heading">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div><p className="text-sm font-extrabold text-emerald-700">{formatCollectedAt(effectiveSelectedDate)}</p><h2 id="snapshot-list-heading" className="mt-1 text-xl font-black text-slate-950">선택 날짜 매물 {selectedSnapshot.length}건</h2><p className="mt-1 text-sm text-slate-500">해당 조사 시점에 실제로 확인된 매물 목록입니다.</p></div>
          <div className="flex flex-col gap-2 sm:items-end">
            <div className="inline-flex w-fit rounded-xl bg-slate-200/70 p-1" aria-label="거래 유형 필터">{(['all', 'sale', 'jeonse', 'monthly'] as TradeFilter[]).map((type) => <button key={type} type="button" onClick={() => setTradeFilter(type)} className={`rounded-lg px-3.5 py-2 text-sm font-bold ${tradeFilter === type ? 'bg-white text-slate-950 shadow-sm' : 'text-slate-500'}`}>{type === 'all' ? '전체' : tradeTypeLabels[type]}</button>)}</div>
            <div className="inline-flex w-fit rounded-xl border border-slate-200 bg-white p-1 shadow-sm" aria-label="매물 보기 방식">
              {([
                ['card', '카드', LayoutGrid],
                ['list', '리스트', ListIcon],
                ['table', '테이블', TableProperties],
              ] as Array<[ListingViewMode, string, typeof LayoutGrid]>).map(([mode, label, Icon]) => (
                <button key={mode} type="button" aria-pressed={listingViewMode === mode} onClick={() => setListingViewMode(mode)} className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-extrabold transition ${listingViewMode === mode ? 'bg-slate-950 text-white shadow-sm' : 'text-slate-500 hover:bg-slate-50 hover:text-slate-900'}`}><Icon size={14} /> {label}</button>
              ))}
            </div>
          </div>
        </div>
        {visibleListings.length ? <SnapshotListingCards apartment={apartment} listings={visibleListings} viewMode={listingViewMode} /> : <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center text-sm font-semibold text-slate-400">선택한 거래 유형의 매물이 없습니다.</div>}
      </section>

      {selectedAbsentSnapshot.length ? (
        <section className="space-y-4" aria-labelledby="snapshot-absence-heading">
          <div>
            <p className="text-sm font-extrabold text-sky-700">{formatCollectedAt(effectiveSelectedDate)}</p>
            <h2 id="snapshot-absence-heading" className="mt-1 text-xl font-black text-slate-950">일시 미노출·삭제 {selectedAbsentSnapshot.length}건</h2>
            <p className="mt-1 text-sm text-slate-500">일시 미노출은 1회 미관측 상태이며, 삭제는 연속된 완료 조사에서 미관측되어 확정된 상태입니다.</p>
          </div>
          {visibleAbsentListings.length ? (
            <SnapshotListingCards apartment={apartment} listings={visibleAbsentListings} viewMode={listingViewMode} />
          ) : (
            <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center text-sm font-semibold text-slate-400">선택한 거래 유형의 미노출·삭제 매물이 없습니다.</div>
          )}
        </section>
      ) : null}
    </div>
  )
}
