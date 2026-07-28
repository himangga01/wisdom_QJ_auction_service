import { useQuery } from '@tanstack/react-query'
import { Check, Search } from 'lucide-react'
import { useState } from 'react'
import { apartmentKeys, getApartments } from '../../api/apartments'
import type { ApartmentSummaryApi } from '../../types/api'

interface ExcelExportTargetSelectorProps {
  value: ApartmentSummaryApi | null
  onChange(apartment: ApartmentSummaryApi): void
  disabled?: boolean
}

export function ExcelExportTargetSelector({
  value,
  onChange,
  disabled = false,
}: ExcelExportTargetSelectorProps) {
  const [query, setQuery] = useState('')
  const targetQuery = useQuery({
    queryKey: apartmentKeys.exportTargets(query),
    queryFn: () => getApartments({ query, page: 1, pageSize: 20 }),
    enabled: !disabled,
    staleTime: 30_000,
  })

  return (
    <div className="w-full min-w-0 sm:w-80">
      <label
        htmlFor="excel-source-search"
        className="mb-1.5 block text-xs font-extrabold text-slate-600"
      >
        Excel 다운로드 원본
      </label>
      <div className="relative">
        <Search
          className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
          size={15}
        />
        <input
          id="excel-source-search"
          aria-label="Excel 원본 검색"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          disabled={disabled}
          placeholder="아파트명 또는 주소 검색"
          className="h-10 w-full rounded-lg border border-slate-300 bg-white pl-9 pr-3 text-sm outline-none focus:border-emerald-500 focus:ring-3 focus:ring-emerald-100"
        />
      </div>
      {value ? (
        <p className="mt-2 flex items-center gap-1.5 text-xs font-bold text-emerald-700">
          <Check size={13} /> 선택됨: {value.complexName}
        </p>
      ) : (
        <p className="mt-2 text-xs font-semibold text-slate-400">
          다운로드할 조사 원본을 선택해 주세요.
        </p>
      )}
      {targetQuery.data?.items.length ? (
        <div className="mt-2 max-h-44 overflow-y-auto rounded-xl border border-slate-200 bg-white p-1 shadow-sm">
          {targetQuery.data.items.map((apartment) => (
            <button
              key={apartment.sourceId}
              type="button"
              onClick={() => onChange(apartment)}
              className="block w-full rounded-lg px-3 py-2 text-left hover:bg-slate-50"
              aria-label={`${apartment.complexName} ${apartment.address} 선택`}
            >
              <span className="block text-sm font-extrabold text-slate-800">
                {apartment.complexName}
              </span>
              <span className="block text-xs text-slate-400">
                {apartment.address || '주소 정보 없음'}
              </span>
            </button>
          ))}
        </div>
      ) : null}
      {targetQuery.error ? (
        <p role="alert" className="mt-2 text-xs font-bold text-rose-600">
          Excel 원본을 불러오지 못했습니다.
        </p>
      ) : null}
    </div>
  )
}
