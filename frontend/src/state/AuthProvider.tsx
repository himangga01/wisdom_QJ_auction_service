import { useQueryClient } from '@tanstack/react-query'
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import {
  bootstrapAdmin as requestBootstrapAdmin,
  changePassword as requestChangePassword,
  getBootstrapStatus,
  getCurrentAuth,
  login as requestLogin,
  logout as requestLogout,
  type AuthResponse,
  type AuthUser,
  type BootstrapRequest,
  type ChangePasswordRequest,
  type LoginRequest,
} from '../api/auth'
import { ApiError, registerUnauthorizedHandler } from '../api/client'
import { clearActiveAnalysisSession } from './analysisRunSession'

export const USE_DEMO_AUTH = import.meta.env.VITE_USE_DEMO_DATA === 'true'

const DEMO_AUTH: AuthResponse = {
  user: {
    id: 'demo-user',
    email: 'demo@local.invalid',
    displayName: '데모 사용자',
    role: 'member',
  },
  expiresAt: '9999-12-31T23:59:59Z',
}

export type AuthStatus = 'loading' | 'authenticated' | 'unauthenticated'

export interface AuthProviderValue {
  status: AuthStatus
  user: AuthUser | null
  expiresAt: string | null
  bootstrapRequired: boolean | null
  error: string
  isDemo: boolean
  login(request: LoginRequest): Promise<void>
  bootstrap(request: BootstrapRequest): Promise<void>
  logout(): Promise<void>
  changePassword(request: ChangePasswordRequest): Promise<void>
  retry(): Promise<void>
}

const AuthContext = createContext<AuthProviderValue | null>(null)

function authErrorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message
  if (error instanceof TypeError) {
    return 'API 서버에 연결할 수 없습니다. 서버 상태를 확인해 주세요.'
  }
  return '인증 정보를 확인하지 못했습니다. 잠시 후 다시 시도해 주세요.'
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [status, setStatus] = useState<AuthStatus>(
    USE_DEMO_AUTH ? 'authenticated' : 'loading',
  )
  const [user, setUser] = useState<AuthUser | null>(
    USE_DEMO_AUTH ? DEMO_AUTH.user : null,
  )
  const [expiresAt, setExpiresAt] = useState<string | null>(
    USE_DEMO_AUTH ? DEMO_AUTH.expiresAt : null,
  )
  const [bootstrapRequired, setBootstrapRequired] = useState<boolean | null>(
    USE_DEMO_AUTH ? false : null,
  )
  const [error, setError] = useState('')

  const clearPrivateState = useCallback(() => {
    void queryClient.cancelQueries()
    queryClient.clear()
    clearActiveAnalysisSession()
    setUser(null)
    setExpiresAt(null)
    setStatus('unauthenticated')
  }, [queryClient])

  const setAuthenticated = useCallback((
    response: AuthResponse,
    clearPreviousUserState = true,
  ) => {
    if (clearPreviousUserState) {
      queryClient.clear()
      clearActiveAnalysisSession()
    }
    setUser(response.user)
    setExpiresAt(response.expiresAt)
    setBootstrapRequired(false)
    setError('')
    setStatus('authenticated')
  }, [queryClient])

  const initialize = useCallback(async () => {
    if (USE_DEMO_AUTH) return
    setStatus('loading')
    setError('')

    try {
      const [bootstrapState, currentAuth] = await Promise.all([
        getBootstrapStatus(),
        getCurrentAuth().catch((requestError: unknown) => {
          if (requestError instanceof ApiError && requestError.status === 401) {
            return null
          }
          throw requestError
        }),
      ])
      setBootstrapRequired(bootstrapState.bootstrapRequired)
      if (currentAuth) {
        setAuthenticated(currentAuth, false)
      } else {
        setUser(null)
        setExpiresAt(null)
        setStatus('unauthenticated')
      }
    } catch (requestError) {
      clearPrivateState()
      setError(authErrorMessage(requestError))
    }
  }, [clearPrivateState, setAuthenticated])

  useEffect(() => {
    if (USE_DEMO_AUTH) return
    registerUnauthorizedHandler(clearPrivateState)
    void initialize()
    return () => registerUnauthorizedHandler(null)
  }, [clearPrivateState, initialize])

  const login = useCallback(async (request: LoginRequest) => {
    setError('')
    const response = await requestLogin(request)
    setAuthenticated(response)
  }, [setAuthenticated])

  const bootstrap = useCallback(async (request: BootstrapRequest) => {
    setError('')
    const response = await requestBootstrapAdmin(request)
    setAuthenticated(response)
  }, [setAuthenticated])

  const logout = useCallback(async () => {
    if (USE_DEMO_AUTH) return
    try {
      await requestLogout()
    } finally {
      clearPrivateState()
    }
  }, [clearPrivateState])

  const changePassword = useCallback(async (request: ChangePasswordRequest) => {
    await requestChangePassword(request)
    clearPrivateState()
  }, [clearPrivateState])

  const value = useMemo<AuthProviderValue>(() => ({
    status,
    user,
    expiresAt,
    bootstrapRequired,
    error,
    isDemo: USE_DEMO_AUTH,
    login,
    bootstrap,
    logout,
    changePassword,
    retry: initialize,
  }), [
    bootstrap,
    bootstrapRequired,
    changePassword,
    error,
    expiresAt,
    initialize,
    login,
    logout,
    status,
    user,
  ])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthProviderValue {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside AuthProvider')
  return context
}
