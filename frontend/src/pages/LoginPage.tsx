import { useState, type FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { ApiError } from '../api/client'
import { useAuth } from '../state/AuthProvider'

export function LoginPage() {
  const auth = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  if (auth.status === 'loading') {
    return (
      <main className="grid min-h-screen place-items-center bg-slate-50 px-5">
        <p role="status" className="text-sm font-bold text-slate-500">사용자 정보를 확인하고 있습니다.</p>
      </main>
    )
  }
  if (auth.status === 'authenticated') return <Navigate to="/" replace />
  if (auth.bootstrapRequired) return <Navigate to="/bootstrap" replace />

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError('')
    setIsSubmitting(true)
    try {
      await auth.login({ email, password })
      const from = (location.state as { from?: string } | null)?.from
      navigate(from && from !== '/login' ? from : '/', { replace: true })
    } catch (requestError) {
      setError(
        requestError instanceof ApiError
          ? requestError.message
          : '로그인 요청을 처리하지 못했습니다.',
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className="grid min-h-screen place-items-center bg-slate-50 px-5 py-10">
      <section className="w-full max-w-md rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
        <p className="text-sm font-extrabold text-emerald-700">집계뷰</p>
        <h1 className="mt-2 text-3xl font-black tracking-[-0.04em] text-slate-950">로그인</h1>
        <p className="mt-3 text-sm leading-6 text-slate-500">
          관리자가 발급한 계정으로 로그인해 주세요.
        </p>

        <form className="mt-7 space-y-5" onSubmit={submit}>
          <label className="block text-sm font-bold text-slate-700">
            이메일
            <input
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="mt-2 w-full rounded-xl border border-slate-300 px-4 py-3 font-normal outline-none focus:border-emerald-600"
            />
          </label>
          <label className="block text-sm font-bold text-slate-700">
            비밀번호
            <input
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="mt-2 w-full rounded-xl border border-slate-300 px-4 py-3 font-normal outline-none focus:border-emerald-600"
            />
          </label>
          {error || auth.error ? (
            <p role="alert" className="rounded-xl bg-rose-50 px-4 py-3 text-sm font-semibold text-rose-700">
              {error || auth.error}
            </p>
          ) : null}
          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full rounded-xl bg-slate-950 px-5 py-3 font-extrabold text-white disabled:opacity-50"
          >
            {isSubmitting ? '로그인 중...' : '로그인'}
          </button>
        </form>
      </section>
    </main>
  )
}
