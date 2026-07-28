import { ArrowLeft } from 'lucide-react'
import { Link } from 'react-router-dom'

export function NotFoundPage() {
  return (
    <section className="mx-auto max-w-xl rounded-3xl border border-slate-200 bg-white p-10 text-center shadow-sm">
      <p className="text-sm font-extrabold text-emerald-700">404</p>
      <h1 className="mt-2 text-3xl font-black text-slate-950">
        페이지를 찾을 수 없습니다
      </h1>
      <p className="mt-3 text-sm leading-6 text-slate-500">
        주소가 잘못되었거나 이동된 페이지입니다.
      </p>
      <Link
        to="/"
        className="mt-6 inline-flex items-center gap-2 rounded-xl bg-slate-950 px-5 py-3 text-sm font-extrabold text-white"
      >
        <ArrowLeft size={16} /> URL 조사로 돌아가기
      </Link>
    </section>
  )
}
