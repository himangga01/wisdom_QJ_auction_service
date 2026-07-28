import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../../state/AuthProvider'

export function ProtectedRoute({ admin = false }: { admin?: boolean }) {
  const auth = useAuth()
  const location = useLocation()

  if (auth.status === 'loading') {
    return (
      <main className="grid min-h-screen place-items-center bg-slate-50 px-5">
        <p role="status" className="text-sm font-bold text-slate-500">
          사용자 정보를 확인하고 있습니다.
        </p>
      </main>
    )
  }

  if (auth.status !== 'authenticated') {
    return (
      <Navigate
        to={auth.bootstrapRequired ? '/bootstrap' : '/login'}
        replace
        state={{ from: `${location.pathname}${location.search}${location.hash}` }}
      />
    )
  }

  if (admin && auth.user?.role !== 'admin') {
    return <Navigate to="/" replace />
  }

  return <Outlet />
}
