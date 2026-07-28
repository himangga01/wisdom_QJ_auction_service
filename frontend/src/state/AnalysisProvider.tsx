import { useQuery, useQueryClient } from '@tanstack/react-query'
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { createAnalysis, getAnalysis, getAnalysisResult } from '../api/analyses'
import { apartmentKeys, getApartments } from '../api/apartments'
import { ApiError } from '../api/client'
import type { AnalysisCreateApi, AnalysisRunStage, AnalysisRunStatus, ApartmentSummaryApi } from '../types/api'
import { DEMO_STEPS, useDemoDashboard } from './useDemoDashboard'

export const USE_DEMO_DATA = import.meta.env.VITE_USE_DEMO_DATA === 'true'

type AnalysisStatus = 'idle' | AnalysisRunStatus

interface AnalysisProviderValue {
  recentApartments: ApartmentSummaryApi[]
  selectedApartmentId: string | null
  status: AnalysisStatus
  stage: AnalysisRunStage | null
  progress: number
  error: string
  isLoading: boolean
  isEmpty: boolean
  isDemo: boolean
  currentRunId: string | null
  startAnalysis(request: AnalysisCreateApi): Promise<string>
  selectApartment(complexId: string): void
  refreshRecentApartments(): Promise<void>
}

const terminalStatuses = new Set<AnalysisRunStatus>([
  'completed',
  'partial',
  'failed',
  'blocked',
  'cancelled',
])

const AnalysisContext = createContext<AnalysisProviderValue | null>(null)

function apiErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.code === 'analysis_option_conflict') {
    return '동일한 URL의 분석이 이미 진행 중이며, 선택한 수집 옵션이 다릅니다. 진행 중인 분석이 완료된 뒤 다시 시도해 주세요.'
  }
  if (error instanceof ApiError) return error.message
  if (error instanceof TypeError) return 'API 서버에 연결할 수 없습니다. 서버 상태와 API 주소를 확인해 주세요.'
  return '요청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.'
}

function terminalError(status: AnalysisRunStatus | undefined, errorCode: string | null | undefined): string {
  if (status === 'blocked') return '네이버 부동산 접근이 차단되어 조사를 완료하지 못했습니다. 잠시 후 다시 시도해 주세요.'
  if (status === 'failed') return `조사 중 오류가 발생했습니다.${errorCode ? ` 오류 코드: ${errorCode}` : ''}`
  if (status === 'cancelled') return '조사가 취소되었습니다.'
  return ''
}

function asDemoSummaries(): ApartmentSummaryApi[] {
  return []
}

export function AnalysisProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const demo = useDemoDashboard()
  const [selectedApartmentId, setSelectedApartmentId] = useState<string | null>(null)
  const [currentRunId, setCurrentRunId] = useState<string | null>(null)
  const [acceptedStatus, setAcceptedStatus] = useState<AnalysisRunStatus | null>(null)
  const [submissionError, setSubmissionError] = useState('')
  const handledRunId = useRef<string | null>(null)

  const apartmentsQuery = useQuery({
    queryKey: apartmentKeys.page('', 1, 100),
    queryFn: () => getApartments(),
    enabled: !USE_DEMO_DATA,
    staleTime: 30_000,
  })

  const analysisQuery = useQuery({
    queryKey: ['analyses', currentRunId],
    queryFn: () => getAnalysis(currentRunId as string),
    enabled: !USE_DEMO_DATA && Boolean(currentRunId),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status && terminalStatuses.has(status) ? false : 1_000
    },
  })

  const recentApartments = USE_DEMO_DATA ? asDemoSummaries() : (apartmentsQuery.data?.items ?? [])

  useEffect(() => {
    if (USE_DEMO_DATA) {
      setSelectedApartmentId(demo.selectedApartmentId || null)
      return
    }
    if (!recentApartments.length) {
      setSelectedApartmentId(null)
      return
    }
    setSelectedApartmentId((current) => (
      current && recentApartments.some((apartment) => apartment.complexId === current)
        ? current
        : recentApartments[0].complexId
    ))
  }, [demo.selectedApartmentId, recentApartments])

  useEffect(() => {
    const run = analysisQuery.data
    if (!run || !terminalStatuses.has(run.status) || handledRunId.current === run.runId) return
    handledRunId.current = run.runId

    if (run.status !== 'completed' && run.status !== 'partial') return
    void (async () => {
      const result = await getAnalysisResult(run.runId)
      setSelectedApartmentId(result.naverComplexId)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: apartmentKeys.all }),
        queryClient.invalidateQueries({ queryKey: ['dashboard'] }),
        queryClient.invalidateQueries({ queryKey: ['listings'] }),
      ])
    })().catch((error: unknown) => setSubmissionError(apiErrorMessage(error)))
  }, [analysisQuery.data, queryClient])

  const startAnalysis = useCallback(async (request: AnalysisCreateApi): Promise<string> => {
    setSubmissionError('')
    if (USE_DEMO_DATA) {
      demo.startDemoAnalysis(request)
      return 'demo'
    }

    try {
      const accepted = await createAnalysis(request)
      handledRunId.current = null
      setAcceptedStatus(accepted.status)
      setCurrentRunId(accepted.runId)
      return accepted.runId
    } catch (error) {
      setAcceptedStatus('failed')
      setSubmissionError(apiErrorMessage(error))
      throw error
    }
  }, [demo])

  const refreshRecentApartments = useCallback(async (): Promise<void> => {
    if (USE_DEMO_DATA) return
    await apartmentsQuery.refetch()
  }, [apartmentsQuery])

  const realStatus = analysisQuery.data?.status ?? acceptedStatus ?? 'idle'
  const status: AnalysisStatus = USE_DEMO_DATA ? demo.status : realStatus
  const progress = USE_DEMO_DATA
    ? Math.round((demo.progressStep / Math.max(DEMO_STEPS.length - 1, 1)) * 100)
    : (analysisQuery.data?.progress ?? 0)
  const error = USE_DEMO_DATA
    ? demo.error
    : (submissionError || apiErrorMessage(analysisQuery.error ?? apartmentsQuery.error).replace(
      '요청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.',
      analysisQuery.error || apartmentsQuery.error ? '저장된 조사 데이터를 불러오지 못했습니다.' : '',
    ) || terminalError(analysisQuery.data?.status, analysisQuery.data?.errorCode))

  const value = useMemo<AnalysisProviderValue>(() => ({
    recentApartments,
    selectedApartmentId,
    status,
    stage: USE_DEMO_DATA ? null : (analysisQuery.data?.stage ?? null),
    progress,
    error,
    isLoading: USE_DEMO_DATA ? false : apartmentsQuery.isLoading,
    isEmpty: !apartmentsQuery.isLoading && recentApartments.length === 0,
    isDemo: USE_DEMO_DATA,
    currentRunId: USE_DEMO_DATA ? null : currentRunId,
    startAnalysis,
    selectApartment: setSelectedApartmentId,
    refreshRecentApartments,
  }), [
    analysisQuery.data?.stage,
    apartmentsQuery.isLoading,
    currentRunId,
    error,
    progress,
    recentApartments,
    refreshRecentApartments,
    selectedApartmentId,
    startAnalysis,
    status,
  ])

  return <AnalysisContext.Provider value={value}>{children}</AnalysisContext.Provider>
}

export function useAnalysis(): AnalysisProviderValue {
  const context = useContext(AnalysisContext)
  if (!context) throw new Error('useAnalysis must be used inside AnalysisProvider')
  return context
}
