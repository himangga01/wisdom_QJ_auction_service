import { Search, SlidersHorizontal } from 'lucide-react'

export type ApartmentSort = 'registrations' | 'price-low' | 'price-high'

interface ApartmentFilterBarProps {
  query: string
  sort: ApartmentSort
  resultCount: number
  onQueryChange: (value: string) => void
  onSortChange: (value: ApartmentSort) => void
}

export function ApartmentFilterBar({ query, sort, resultCount, onQueryChange, onSortChange }: ApartmentFilterBarProps) {
  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-4 sm:flex-row sm:items-center">
      <div className="relative min-w-0 flex-1">
        <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" size={17} />
        <label className="sr-only" htmlFor="complex-query">단지 검색</label>
        <input
          id="complex-query"
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder="단지명 또는 주소 검색"
          className="h-11 w-full rounded-xl border border-slate-200 bg-slate-50 pl-10 pr-4 text-sm outline-none transition focus:border-emerald-500 focus:bg-white focus:ring-4 focus:ring-emerald-100"
        />
      </div>
      <div className="flex items-center gap-2">
        <span className="hidden items-center gap-1.5 text-xs font-bold text-slate-400 sm:flex">
          <SlidersHorizontal size={15} /> {resultCount}개 단지
        </span>
        <label className="sr-only" htmlFor="apartment-sort">정렬</label>
        <select
          id="apartment-sort"
          value={sort}
          onChange={(event) => onSortChange(event.target.value as ApartmentSort)}
          className="h-11 flex-1 rounded-xl border border-slate-200 bg-white px-3 text-sm font-bold text-slate-700 outline-none focus:border-emerald-500 sm:flex-none"
        >
          <option value="registrations">중개사 등록 많은 순</option>
          <option value="price-low">최저가 낮은 순</option>
          <option value="price-high">최저가 높은 순</option>
        </select>
      </div>
    </div>
  )
}
