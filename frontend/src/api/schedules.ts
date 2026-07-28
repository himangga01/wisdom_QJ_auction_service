import type {
  ScheduleApi,
  ScheduleCreateApi,
  ScheduleDeleteApi,
  SchedulePatchApi,
  ScheduleRunsApi,
} from '../types/api'
import { apiRequest } from './client'

export const scheduleKeys = {
  all: ['schedules'] as const,
  runs: (scheduleId: string) => ['schedules', scheduleId, 'runs'] as const,
}

export function getSchedules(): Promise<ScheduleApi[]> {
  return apiRequest('/schedules')
}

export function createSchedule(payload: ScheduleCreateApi): Promise<ScheduleApi> {
  return apiRequest('/schedules', { method: 'POST', body: JSON.stringify(payload) })
}

export function patchSchedule(scheduleId: string, payload: SchedulePatchApi): Promise<ScheduleApi> {
  return apiRequest(`/schedules/${encodeURIComponent(scheduleId)}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export function deleteSchedule(scheduleId: string, hard = false): Promise<ScheduleDeleteApi> {
  return apiRequest(`/schedules/${encodeURIComponent(scheduleId)}`, { method: 'DELETE' }, { hard })
}

export function getScheduleRuns(scheduleId: string, limit = 20): Promise<ScheduleRunsApi> {
  return apiRequest(`/schedules/${encodeURIComponent(scheduleId)}/runs`, {}, { limit })
}
