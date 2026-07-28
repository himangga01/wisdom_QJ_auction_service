import type {
  AnalysisAcceptedApi,
  AnalysisCancelApi,
  AnalysisCreateApi,
  AnalysisResultApi,
  AnalysisStatusApi,
} from '../types/api'
import { apiRequest } from './client'

export function createAnalysis(request: AnalysisCreateApi): Promise<AnalysisAcceptedApi> {
  return apiRequest('/analyses', {
    method: 'POST',
    body: JSON.stringify(request),
  })
}

export function getAnalysis(runId: string): Promise<AnalysisStatusApi> {
  return apiRequest(`/analyses/${encodeURIComponent(runId)}`)
}

export function getAnalysisResult(runId: string): Promise<AnalysisResultApi> {
  return apiRequest(`/analyses/${encodeURIComponent(runId)}/result`)
}

export function cancelAnalysis(runId: string): Promise<AnalysisCancelApi> {
  return apiRequest(`/analyses/${encodeURIComponent(runId)}/cancel`, { method: 'POST' })
}
