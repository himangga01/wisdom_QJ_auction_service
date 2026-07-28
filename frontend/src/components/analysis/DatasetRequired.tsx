import { AlertCircle, Link2, LoaderCircle } from 'lucide-react'
import { Link } from 'react-router-dom'

interface DatasetRequiredProps {
  isLoading?: boolean
  error?: string
}

export function DatasetRequired({ isLoading = false, error = '' }: DatasetRequiredProps) {
  if (isLoading) {
    return (
      <section className="mx-auto max-w-xl rounded-3xl border border-slate-200 bg-white px-6 py-14 text-center" aria-live="polite">
        <LoaderCircle className="mx-auto animate-spin text-emerald-600" size={30} />
        <h1 className="mt-4 text-xl font-black text-slate-900">저장된 조사 결과를 불러오는 중입니다</h1>
      </section>
    )
  }

  return (
    <section className="mx-auto max-w-xl rounded-3xl border border-dashed border-slate-300 bg-white px-6 py-14 text-center">
      <span className={`mx-auto grid size-12 place-items-center rounded-2xl ${error ? 'bg-rose-50 text-rose-600' : 'bg-slate-100 text-slate-500'}`}>
        {error ? <AlertCircle size={22} /> : <Link2 size={22} />}
      </span>
      <h1 className="mt-4 text-xl font-black text-slate-900">{error ? '조사 결과를 불러오지 못했습니다' : '먼저 URL 조사를 진행해 주세요'}</h1>
      <p className="mt-2 text-sm leading-6 text-slate-500">
        {error || '분석 결과가 준비되면 이 페이지에서 저장된 아파트 데이터를 확인할 수 있습니다.'}
      </p>
      <Link to="/" className="mt-6 inline-flex rounded-xl bg-slate-950 px-5 py-3 text-sm font-extrabold text-white">URL 입력 화면으로</Link>
    </section>
  )
}
