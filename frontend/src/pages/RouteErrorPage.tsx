import { AlertTriangle } from 'lucide-react'
import { Link, isRouteErrorResponse, useRouteError } from 'react-router-dom'

export function RouteErrorPage() {
  const error = useRouteError()
  const notFound = isRouteErrorResponse(error) && error.status === 404

  return (
    <main className="grid min-h-screen place-items-center bg-slate-50 px-5">
      <section className="max-w-xl rounded-3xl border border-slate-200 bg-white p-10 text-center shadow-sm">
        <AlertTriangle className="mx-auto text-amber-500" size={36} />
        <h1 className="mt-4 text-2xl font-black text-slate-950">
          {notFound ? '페이지를 찾을 수 없습니다' : '화면을 불러오지 못했습니다'}
        </h1>
        <p className="mt-3 text-sm leading-6 text-slate-500">
          {notFound
            ? '요청한 경로를 확인해 주세요.'
            : '예상하지 못한 화면 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.'}
        </p>
        <Link
          to="/"
          className="mt-6 inline-flex rounded-xl bg-slate-950 px-5 py-3 text-sm font-extrabold text-white"
        >
          URL 조사로 돌아가기
        </Link>
      </section>
    </main>
  )
}
