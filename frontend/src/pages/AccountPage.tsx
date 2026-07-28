import { useState, type FormEvent } from 'react'
import { ApiError } from '../api/client'
import { useAuth } from '../state/AuthProvider'

export function AccountPage() {
  const auth = useAuth()
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (newPassword !== confirmation) {
      setError('새 비밀번호가 서로 일치하지 않습니다.')
      return
    }
    setError('')
    setIsSubmitting(true)
    try {
      await auth.changePassword({ currentPassword, newPassword })
    } catch (requestError) {
      setError(
        requestError instanceof ApiError
          ? requestError.message
          : '비밀번호를 변경하지 못했습니다.',
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <section className="mx-auto max-w-3xl space-y-6">
      <div>
        <p className="text-sm font-extrabold text-emerald-700">내 계정</p>
        <h1 className="mt-1 text-3xl font-black tracking-[-0.04em]">계정 설정</h1>
      </div>

      <div className="rounded-3xl border border-slate-200 bg-white p-7 shadow-sm">
        <dl className="grid gap-5 sm:grid-cols-2">
          <div>
            <dt className="text-xs font-bold uppercase tracking-wide text-slate-400">표시 이름</dt>
            <dd className="mt-1 font-extrabold text-slate-900">{auth.user?.displayName}</dd>
          </div>
          <div>
            <dt className="text-xs font-bold uppercase tracking-wide text-slate-400">이메일</dt>
            <dd className="mt-1 font-semibold text-slate-700">{auth.user?.email}</dd>
          </div>
          <div>
            <dt className="text-xs font-bold uppercase tracking-wide text-slate-400">권한</dt>
            <dd className="mt-1 font-semibold text-slate-700">
              {auth.user?.role === 'admin' ? '관리자' : '일반 사용자'}
            </dd>
          </div>
        </dl>
      </div>

      {!auth.isDemo ? (
        <form className="rounded-3xl border border-slate-200 bg-white p-7 shadow-sm" onSubmit={submit}>
          <h2 className="text-xl font-black">비밀번호 변경</h2>
          <p className="mt-2 text-sm text-slate-500">
            변경이 완료되면 모든 세션이 종료되어 다시 로그인해야 합니다.
          </p>
          <div className="mt-6 grid gap-5">
            <label className="text-sm font-bold text-slate-700">
              현재 비밀번호
              <input
                type="password"
                autoComplete="current-password"
                required
                value={currentPassword}
                onChange={(event) => setCurrentPassword(event.target.value)}
                className="mt-2 w-full rounded-xl border border-slate-300 px-4 py-3 font-normal"
              />
            </label>
            <label className="text-sm font-bold text-slate-700">
              새 비밀번호
              <input
                type="password"
                autoComplete="new-password"
                minLength={12}
                maxLength={128}
                required
                value={newPassword}
                onChange={(event) => setNewPassword(event.target.value)}
                className="mt-2 w-full rounded-xl border border-slate-300 px-4 py-3 font-normal"
              />
            </label>
            <label className="text-sm font-bold text-slate-700">
              새 비밀번호 확인
              <input
                type="password"
                autoComplete="new-password"
                minLength={12}
                maxLength={128}
                required
                value={confirmation}
                onChange={(event) => setConfirmation(event.target.value)}
                className="mt-2 w-full rounded-xl border border-slate-300 px-4 py-3 font-normal"
              />
            </label>
          </div>
          {error ? (
            <p role="alert" className="mt-5 rounded-xl bg-rose-50 px-4 py-3 text-sm font-semibold text-rose-700">
              {error}
            </p>
          ) : null}
          <button
            type="submit"
            disabled={isSubmitting}
            className="mt-6 rounded-xl bg-slate-950 px-5 py-3 text-sm font-extrabold text-white disabled:opacity-50"
          >
            {isSubmitting ? '변경 중...' : '비밀번호 변경'}
          </button>
        </form>
      ) : (
        <p className="rounded-2xl bg-emerald-50 px-5 py-4 text-sm font-semibold text-emerald-800">
          데모 모드에서는 계정 정보가 브라우저 안에서만 사용됩니다.
        </p>
      )}
    </section>
  )
}
