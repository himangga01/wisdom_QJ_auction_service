import { useQuery } from '@tanstack/react-query'
import { Building2, ChevronDown, LoaderCircle, Search } from 'lucide-react'
import { useEffect, useState } from 'react'
import { apartmentKeys, getApartments } from '../../api/apartments'
import type { ApartmentSummaryApi } from '../../types/api'

interface DashboardApartmentPickerProps {
  selectedApartment: ApartmentSummaryApi | null
  onSelect: (apartment: ApartmentSummaryApi) => void
}

const pageSize = 20

function appendUnique(apartments: ApartmentSummaryApi[], next: ApartmentSummaryApi[]): ApartmentSummaryApi[] {
  const known = new Set(apartments.map((apartment) => apartment.complexId))
  return [...apartments, ...next.filter((apartment) => {
    if (known.has(apartment.complexId)) return false
    known.add(apartment.complexId)
    return true
  })]
}

export function DashboardApartmentPicker({ selectedApartment, onSelect }: DashboardApartmentPickerProps) {
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(1)
  const [apartments, setApartments] = useState<ApartmentSummaryApi[]>([])
  const apartmentsQuery = useQuery({
    queryKey: apartmentKeys.page(query, page, pageSize),
    queryFn: () => getApartments({ query, page, pageSize }),
    staleTime: 30_000,
  })

  useEffect(() => {
    const result = apartmentsQuery.data
    if (!result) return
    setApartments((current) => page === 1 ? appendUnique([], result.items) : appendUnique(current, result.items))
  }, [apartmentsQuery.data, page])

  const handleQueryChange = (value: string) => {
    setQuery(value)
    setPage(1)
    setApartments([])
  }

  const total = apartmentsQuery.data?.total ?? apartments.length
  const hasMore = page * pageSize < total
  const selectedOutsideResults = selectedApartment && !apartments.some((apartment) => apartment.complexId === selectedApartment.complexId)

  return (
    <div className="w-full rounded-2xl border border-slate-200 bg-white p-4 shadow-sm lg:w-[360px]">
      <label htmlFor="dashboard-apartment-search" className="flex items-center gap-2 text-xs font-extrabold text-slate-500"><Building2 size={15} /> 분석 아파트 선택</label>
      {selectedOutsideResults ? (
        <button
          type="button"
          onClick={() => onSelect(selectedApartment)}
          className="mt-2 w-full rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-left text-sm font-extrabold text-emerald-800"
        >
          선택됨: {selectedApartment.complexName}
        </button>
      ) : null}
      <div className="relative mt-2">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
        <input
          id="dashboard-apartment-search"
          value={query}
          onChange={(event) => handleQueryChange(event.target.value)}
          placeholder="아파트명 또는 주소 검색"
          className="h-11 w-full rounded-xl border border-slate-300 bg-white pl-10 pr-3 text-sm font-bold text-slate-900 outline-none focus:border-emerald-500 focus:ring-4 focus:ring-emerald-100"
        />
      </div>
      <div className="mt-2 max-h-56 overflow-y-auto rounded-xl border border-slate-100">
        {apartmentsQuery.isLoading && apartments.length === 0 ? <div className="flex items-center justify-center gap-2 p-4 text-sm font-bold text-slate-500"><LoaderCircle className="animate-spin" size={16} /> 불러오는 중</div> : null}
        {!apartmentsQuery.isLoading && apartments.length === 0 ? <p className="p-4 text-sm font-semibold text-slate-400">검색 결과가 없습니다.</p> : null}
        {apartments.map((apartment) => {
          const isSelected = apartment.complexId === selectedApartment?.complexId
          return (
            <button
              key={apartment.complexId}
              type="button"
              onClick={() => onSelect(apartment)}
              aria-pressed={isSelected}
              className={`block w-full border-b border-slate-100 px-3 py-2.5 text-left last:border-b-0 ${isSelected ? 'bg-emerald-50' : 'hover:bg-slate-50'}`}
            >
              <span className="block text-sm font-extrabold text-slate-900">{apartment.complexName}</span>
              <span className="mt-0.5 block truncate text-xs text-slate-500">{apartment.address || '-'}</span>
            </button>
          )
        })}
      </div>
      {hasMore ? (
        <button
          type="button"
          onClick={() => setPage((current) => current + 1)}
          disabled={apartmentsQuery.isFetching}
          className="mt-2 inline-flex w-full items-center justify-center gap-1 rounded-xl border border-slate-300 px-3 py-2 text-xs font-extrabold text-slate-700 hover:border-emerald-500 hover:text-emerald-700 disabled:cursor-not-allowed disabled:text-slate-400"
        >
          {apartmentsQuery.isFetching ? <LoaderCircle className="animate-spin" size={14} /> : <ChevronDown size={14} />} 더 보기
        </button>
      ) : null}
    </div>
  )
}
