import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import {
  createAdminUser,
  getAdminUsers,
  setTemporaryPassword,
  updateAdminUser,
  type AdminUser,
  type UserRole,
} from '../api/auth'
import { ApiError } from '../api/client'

function messageFor(error: unknown): string {
  return error instanceof ApiError
    ? error.message
    : '사용자 요청을 처리하지 못했습니다.'
}

export function AdminUsersPage() {
  const queryClient = useQueryClient()
  const [page, setPage] = useState(1)
  const [query, setQuery] = useState('')
  const [email, setEmail] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState<UserRole>('member')
  const [temporaryPasswords, setTemporaryPasswords] = useState<Record<string, string>>({})
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')

  const usersQuery = useQuery({
    queryKey: ['admin', 'users', page, query],
    queryFn: () => getAdminUsers({ page, pageSize: 20, query }),
  })

  const refresh = () =>
    queryClient.invalidateQueries({ queryKey: ['admin', 'users'] })

  const createMutation = useMutation({
    mutationFn: createAdminUser,
    onSuccess: async () => {
      setEmail('')
      setDisplayName('')
      setPassword('')
      setRole('member')
      setError('')
      setNotice('사용자를 생성했습니다.')
      await refresh()
    },
    onError: (requestError) => setError(messageFor(requestError)),
  })

  const updateMutation = useMutation({
    mutationFn: ({ userId, patch }: {
      userId: string
      patch: { role?: UserRole; isActive?: boolean; displayName?: string }
    }) => updateAdminUser(userId, patch),
    onSuccess: async () => {
      setError('')
      setNotice('사용자 정보를 변경했습니다.')
      await refresh()
    },
    onError: (requestError) => setError(messageFor(requestError)),
  })

  const passwordMutation = useMutation({
    mutationFn: ({ userId, nextPassword }: {
      userId: string
      nextPassword: string
    }) => setTemporaryPassword(userId, nextPassword),
    onSuccess: (_, variables) => {
      setTemporaryPasswords((current) => ({ ...current, [variables.userId]: '' }))
      setError('')
      setNotice('임시 비밀번호를 설정하고 기존 세션을 종료했습니다.')
    },
    onError: (requestError) => setError(messageFor(requestError)),
  })

  const createUser = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setNotice('')
    createMutation.mutate({ email, displayName, password, role })
  }

  const users = usersQuery.data?.items ?? []
  const totalPages = Math.max(
    1,
    Math.ceil((usersQuery.data?.total ?? 0) / (usersQuery.data?.pageSize ?? 20)),
  )

  return (
    <section className="space-y-7">
      <div>
        <p className="text-sm font-extrabold text-emerald-700">관리자</p>
        <h1 className="mt-1 text-3xl font-black tracking-[-0.04em]">사용자 관리</h1>
        <p className="mt-2 text-sm text-slate-500">계정 생성, 권한·활성 상태 변경, 임시 비밀번호 설정을 관리합니다.</p>
      </div>

      <form className="grid gap-4 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm lg:grid-cols-5" onSubmit={createUser}>
        <input
          aria-label="새 사용자 표시 이름"
          placeholder="표시 이름"
          required
          value={displayName}
          onChange={(event) => setDisplayName(event.target.value)}
          className="rounded-xl border border-slate-300 px-4 py-3"
        />
        <input
          aria-label="새 사용자 이메일"
          type="email"
          placeholder="이메일"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          className="rounded-xl border border-slate-300 px-4 py-3"
        />
        <input
          aria-label="새 사용자 비밀번호"
          type="password"
          placeholder="12자 이상 비밀번호"
          minLength={12}
          maxLength={128}
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          className="rounded-xl border border-slate-300 px-4 py-3"
        />
        <select
          aria-label="새 사용자 권한"
          value={role}
          onChange={(event) => setRole(event.target.value as UserRole)}
          className="rounded-xl border border-slate-300 px-4 py-3"
        >
          <option value="member">일반 사용자</option>
          <option value="admin">관리자</option>
        </select>
        <button type="submit" disabled={createMutation.isPending} className="rounded-xl bg-slate-950 px-5 py-3 font-extrabold text-white disabled:opacity-50">
          사용자 생성
        </button>
      </form>

      <div className="flex flex-wrap items-center gap-3">
        <input
          aria-label="사용자 검색"
          placeholder="이메일 또는 표시 이름 검색"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value)
            setPage(1)
          }}
          className="min-w-72 rounded-xl border border-slate-300 bg-white px-4 py-3"
        />
        {notice ? <p role="status" className="text-sm font-semibold text-emerald-700">{notice}</p> : null}
        {error ? <p role="alert" className="text-sm font-semibold text-rose-700">{error}</p> : null}
      </div>

      <div className="overflow-x-auto rounded-3xl border border-slate-200 bg-white shadow-sm">
        <table className="w-full min-w-[900px] text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-5 py-4">사용자</th>
              <th className="px-5 py-4">권한</th>
              <th className="px-5 py-4">상태</th>
              <th className="px-5 py-4">임시 비밀번호</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {users.map((item: AdminUser) => (
              <tr key={item.id}>
                <td className="px-5 py-4">
                  <strong className="block text-slate-900">{item.displayName}</strong>
                  <span className="text-slate-500">{item.email}</span>
                </td>
                <td className="px-5 py-4">
                  <select
                    aria-label={`${item.displayName} 권한`}
                    value={item.role}
                    onChange={(event) =>
                      updateMutation.mutate({
                        userId: item.id,
                        patch: { role: event.target.value as UserRole },
                      })}
                    className="rounded-lg border border-slate-300 px-3 py-2"
                  >
                    <option value="member">일반 사용자</option>
                    <option value="admin">관리자</option>
                  </select>
                </td>
                <td className="px-5 py-4">
                  <button
                    type="button"
                    onClick={() =>
                      updateMutation.mutate({
                        userId: item.id,
                        patch: { isActive: !item.isActive },
                      })}
                    className={`rounded-full px-3 py-1.5 text-xs font-extrabold ${item.isActive ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-500'}`}
                  >
                    {item.isActive ? '활성' : '비활성'}
                  </button>
                </td>
                <td className="px-5 py-4">
                  <div className="flex gap-2">
                    <input
                      aria-label={`${item.displayName} 임시 비밀번호`}
                      type="password"
                      minLength={12}
                      maxLength={128}
                      value={temporaryPasswords[item.id] ?? ''}
                      onChange={(event) =>
                        setTemporaryPasswords((current) => ({
                          ...current,
                          [item.id]: event.target.value,
                        }))}
                      className="rounded-lg border border-slate-300 px-3 py-2"
                    />
                    <button
                      type="button"
                      disabled={(temporaryPasswords[item.id]?.length ?? 0) < 12}
                      onClick={() =>
                        passwordMutation.mutate({
                          userId: item.id,
                          nextPassword: temporaryPasswords[item.id] ?? '',
                        })}
                      className="rounded-lg bg-slate-900 px-3 py-2 text-xs font-bold text-white disabled:opacity-40"
                    >
                      설정
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {usersQuery.isLoading ? <p role="status" className="p-6 text-sm text-slate-500">사용자를 불러오는 중입니다.</p> : null}
        {!usersQuery.isLoading && users.length === 0 ? <p className="p-6 text-sm text-slate-500">조건에 맞는 사용자가 없습니다.</p> : null}
      </div>

      <div className="flex items-center justify-end gap-3 text-sm">
        <button type="button" disabled={page <= 1} onClick={() => setPage((value) => value - 1)} className="rounded-lg border border-slate-300 bg-white px-4 py-2 disabled:opacity-40">이전</button>
        <span>{page} / {totalPages}</span>
        <button type="button" disabled={page >= totalPages} onClick={() => setPage((value) => value + 1)} className="rounded-lg border border-slate-300 bg-white px-4 py-2 disabled:opacity-40">다음</button>
      </div>
    </section>
  )
}
