import { useEffect, useState, type FormEvent } from 'react'

interface PaginationProps {
  page: number
  pageSize: number
  total: number
  onPageChange: (page: number) => void
  onPageSizeChange: (pageSize: number) => void
}

const pageSizes = [20, 50, 100]

export function Pagination({ page, pageSize, total, onPageChange, onPageSizeChange }: PaginationProps) {
  const lastPage = Math.max(1, Math.ceil(total / pageSize))
  const currentPage = Math.min(Math.max(page, 1), lastPage)
  const [targetPage, setTargetPage] = useState(String(currentPage))

  useEffect(() => {
    setTargetPage(String(currentPage))
  }, [currentPage])

  const moveToTargetPage = (event: FormEvent) => {
    event.preventDefault()
    const parsed = Number(targetPage)
    if (!Number.isInteger(parsed)) {
      setTargetPage(String(currentPage))
      return
    }
    onPageChange(Math.min(Math.max(parsed, 1), lastPage))
  }

  return (
    <nav className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-4 text-sm sm:flex-row sm:items-center sm:justify-between" aria-label="페이지 이동">
      <div className="flex items-center gap-2 text-slate-600">
        <span className="font-bold">전체 {total.toLocaleString('ko-KR')}개</span>
        <span className="text-slate-400">·</span>
        <span>{currentPage} / {lastPage} 페이지</span>
      </div>
      <div className="flex items-center gap-2">
        <label htmlFor="apartment-page-size" className="sr-only">페이지당 항목 수</label>
        <select
          id="apartment-page-size"
          value={pageSize}
          onChange={(event) => onPageSizeChange(Number(event.target.value))}
          className="h-10 rounded-lg border border-slate-300 bg-white px-2 text-sm font-bold text-slate-700 outline-none focus:border-emerald-500"
        >
          {pageSizes.map((size) => <option key={size} value={size}>{size}개씩</option>)}
        </select>
        <button
          type="button"
          onClick={() => onPageChange(currentPage - 1)}
          disabled={currentPage <= 1}
          className="h-10 rounded-lg border border-slate-300 px-3 font-bold text-slate-700 transition hover:border-emerald-500 hover:text-emerald-700 disabled:cursor-not-allowed disabled:border-slate-200 disabled:text-slate-300"
        >
          이전
        </button>
        <form onSubmit={moveToTargetPage} className="flex items-center gap-1">
          <label htmlFor="apartment-target-page" className="sr-only">이동할 페이지</label>
          <input
            id="apartment-target-page"
            type="number"
            min={1}
            max={lastPage}
            value={targetPage}
            onChange={(event) => setTargetPage(event.target.value)}
            className="h-10 w-16 rounded-lg border border-slate-300 px-2 text-center text-sm font-bold text-slate-700 outline-none focus:border-emerald-500"
          />
          <button type="submit" className="h-10 rounded-lg border border-slate-300 px-3 font-bold text-slate-700 hover:border-emerald-500 hover:text-emerald-700">이동</button>
        </form>
        <button
          type="button"
          onClick={() => onPageChange(currentPage + 1)}
          disabled={currentPage >= lastPage}
          className="h-10 rounded-lg border border-slate-300 px-3 font-bold text-slate-700 transition hover:border-emerald-500 hover:text-emerald-700 disabled:cursor-not-allowed disabled:border-slate-200 disabled:text-slate-300"
        >
          다음
        </button>
      </div>
    </nav>
  )
}
