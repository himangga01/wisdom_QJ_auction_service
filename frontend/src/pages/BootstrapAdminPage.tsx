import { useState, type FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { ApiError } from '../api/client'
import { useAuth } from '../state/AuthProvider'

export function BootstrapAdminPage() {
  const auth = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [password, setPassword] = useState('')
  const [bootstrapToken, setBootstrapToken] = useState('')
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  if (auth.status === 'loading') {
    return (
      <main className="grid min-h-screen place-items-center bg-slate-50 px-5">
        <p role="status" className="text-sm font-bold text-slate-500">초기 설정 상태를 확인하고 있습니다.</p>
      </main>
    )
  }
  if (auth.status === 'authenticated') return <Navigate to="/" replace />
  if (auth.bootstrapRequired === false) return <Navigate to="/login" replace />

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError('')
    setIsSubmitting(true)
    try {
      await auth.bootstrap({ email, displayName, password, bootstrapToken })
      navigate('/', { replace: true })
    } catch (requestError) {
      setError(
        requestError instanceof ApiError
          ? requestError.message
          : '최초 관리자 설정 요청을 처리하지 못했습니다.',
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className="grid min-h-screen place-items-center bg-slate-50 px-5 py-10">
      <section className="w-full max-w-lg rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
        <p className="text-sm font-extrabold text-emerald-700">집계뷰 시작하기</p>
        <h1 className="mt-2 text-3xl font-black tracking-[-0.04em] text-slate-950">최초 관리자 설정</h1>
        <p className="mt-3 text-sm leading-6 text-slate-500">
          운영자가 전달한 일회용 bootstrap token으로 첫 관리자 계정을 만듭니다.
        </p>

        <form className="mt-7 grid gap-5" onSubmit={submit}>
          <label className="text-sm font-bold text-slate-700">
            표시 이름
            <input
              required
              maxLength={120}
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              className="mt-2 w-full rounded-xl border border-slate-300 px-4 py-3 font-normal outline-none focus:border-emerald-600"
            />
          </label>
          <label className="text-sm font-bold text-slate-700">
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
          <label className="text-sm font-bold text-slate-700">
            비밀번호
            <input
              type="password"
              autoComplete="new-password"
              minLength={12}
              maxLength={128}
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="mt-2 w-full rounded-xl border border-slate-300 px-4 py-3 font-normal outline-none focus:border-emerald-600"
            />
          </label>
          <label className="text-sm font-bold text-slate-700">
            Bootstrap token
            <input
              type="password"
              autoComplete="off"
              required
              value={bootstrapToken}
              onChange={(event) => setBootstrapToken(event.target.value)}
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
            className="rounded-xl bg-slate-950 px-5 py-3 font-extrabold text-white disabled:opacity-50"
          >
            {isSubmitting ? '관리자 생성 중...' : '관리자 계정 생성'}
          </button>
        </form>
      </section>
    </main>
  )
}
