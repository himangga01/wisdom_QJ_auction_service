import type { HealthResponseApi } from '../types/api'
import { apiRequest } from './client'

export function getHealth(): Promise<HealthResponseApi> {
  return apiRequest('/health')
}
