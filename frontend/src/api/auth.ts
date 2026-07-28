import { apiRequest } from './client'

export type UserRole = 'admin' | 'member'

export interface AuthUser {
  id: string
  email: string
  displayName: string
  role: UserRole
}

export interface AuthResponse {
  user: AuthUser
  expiresAt: string
}

export interface BootstrapStatus {
  bootstrapRequired: boolean
}

export interface BootstrapRequest {
  email: string
  displayName: string
  password: string
  bootstrapToken: string
}

export interface LoginRequest {
  email: string
  password: string
}

export interface ChangePasswordRequest {
  currentPassword: string
  newPassword: string
}

export interface AdminUser extends AuthUser {
  isActive: boolean
  createdAt: string
  updatedAt: string
}

export interface AdminUserPage {
  items: AdminUser[]
  total: number
  page: number
  pageSize: number
}

export interface AdminUserCreate {
  email: string
  displayName: string
  password: string
  role: UserRole
}

export interface AdminUserPatch {
  displayName?: string
  role?: UserRole
  isActive?: boolean
}

export function getBootstrapStatus(): Promise<BootstrapStatus> {
  return apiRequest('/auth/bootstrap-status')
}

export function bootstrapAdmin(request: BootstrapRequest): Promise<AuthResponse> {
  const { bootstrapToken, ...body } = request
  return apiRequest('/auth/bootstrap', {
    method: 'POST',
    headers: { 'X-Bootstrap-Token': bootstrapToken },
    body: JSON.stringify(body),
  })
}

export function login(request: LoginRequest): Promise<AuthResponse> {
  return apiRequest('/auth/login', {
    method: 'POST',
    body: JSON.stringify(request),
  })
}

export function getCurrentAuth(): Promise<AuthResponse> {
  return apiRequest('/auth/me')
}

export function logout(): Promise<void> {
  return apiRequest('/auth/logout', { method: 'POST' })
}

export function changePassword(request: ChangePasswordRequest): Promise<void> {
  return apiRequest('/auth/change-password', {
    method: 'POST',
    body: JSON.stringify(request),
  })
}

export function getAdminUsers(params: {
  page: number
  pageSize: number
  query?: string
}): Promise<AdminUserPage> {
  return apiRequest('/admin/users', {}, params)
}

export function createAdminUser(request: AdminUserCreate): Promise<AdminUser> {
  return apiRequest('/admin/users', {
    method: 'POST',
    body: JSON.stringify(request),
  })
}

export function updateAdminUser(
  userId: string,
  request: AdminUserPatch,
): Promise<AdminUser> {
  return apiRequest(`/admin/users/${userId}`, {
    method: 'PATCH',
    body: JSON.stringify(request),
  })
}

export function setTemporaryPassword(
  userId: string,
  password: string,
): Promise<{ userId: string; sessionsRevoked: boolean }> {
  return apiRequest(`/admin/users/${userId}/temporary-password`, {
    method: 'POST',
    body: JSON.stringify({ password }),
  })
}
