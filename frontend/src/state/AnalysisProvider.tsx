import { useQuery, useQueryClient } from '@tanstack/react-query'
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { cancelAnalysis, createAnalysis, getAnalysis, getAnalysisResult } from '../api/analyses'
import { apartmentKeys, getApartment, getApartments } from '../api/apartments'
import { ApiError } from '../api/client'
import { getHealth } from '../api/health'
import type { AnalysisCreateApi, AnalysisRunStage, AnalysisRunStatus, ApartmentSummaryApi } from '../types/api'
import {
  clearActiveAnalysisSession,
  readActiveAnalysisSession,
  writeActiveAnalysisSession,
} from './analysisRunSession'
import { useDemoAnalysis } from './DemoAnalysisContext'
import { DEMO_STEPS } from './useDemoDashboard'
import { runErrorMessage } from '../utils/runErrorMessages'

export const USE_DEMO_DATA = import.meta.env.VITE_USE_DEMO_DATA === 'true'

type AnalysisStatus = 'idle' | AnalysisRunStatus
type ResultHydrationStatus = 'idle' | 'loading' | 'ready' | 'error'

export interface AnalysisProviderValue {
  selectedApartment: ApartmentSummaryApi | null
  selectedApartmentId: string | null
  status: AnalysisStatus
  stage: AnalysisRunStage | null
  progress: number
  error: string
  isLoading: boolean
  isEmpty: boolean
  isDemo: boolean
  currentRunId: string | null
  isRestoringRun: boolean
  isCancelling: boolean
  notice: string
  browserStatus: 'ready' | 'unavailable' | 'not_required' | 'unknown'
  resultHydrationStatus: ResultHydrationStatus
  startAnalysis(request: AnalysisCreateApi): Promise<string>
  cancelQueuedAnalysis(): Promise<void>
  retryResultHydration(): void
  selectApartment(apartment: ApartmentSummaryApi): void
  refreshSelectedApartment(): Promise<void>
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
  if (error instanceof ApiError) {
    const stableMessage = runErrorMessage(error.code)
    if (stableMessage) return stableMessage
  }
  if (error instanceof ApiError) return error.message
  if (error instanceof TypeError) return 'API 서버에 연결할 수 없습니다. 서버 상태와 API 주소를 확인해 주세요.'
  return '요청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.'
}

function terminalError(status: AnalysisRunStatus | undefined, errorCode: string | null | undefined): string {
  const stableMessage = runErrorMessage(errorCode)
  if (stableMessage) return stableMessage
  if (status === 'blocked') return '네이버 부동산 접근이 차단되어 조사를 완료하지 못했습니다. 잠시 후 다시 시도해 주세요.'
  if (status === 'failed') return '조사 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.'
  if (status === 'cancelled') return '조사가 취소되었습니다.'
  return ''
}

export function AnalysisProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const demo = useDemoAnalysis()
  const restoredRunId = useRef(
    USE_DEMO_DATA ? null : readActiveAnalysisSession()?.runId ?? null,
  )
  const [selectedApartment, setSelectedApartment] = useState<ApartmentSummaryApi | null>(null)
  const [currentRunId, setCurrentRunId] = useState<string | null>(restoredRunId.current)
  const [acceptedStatus, setAcceptedStatus] = useState<AnalysisRunStatus | null>(null)
  const [submissionError, setSubmissionError] = useState('')
  const [notice, setNotice] = useState('')
  const [isRestoringRun, setIsRestoringRun] = useState(Boolean(restoredRunId.current))
  const [isCancelling, setIsCancelling] = useState(false)
  const [resultHydrationStatus, setResultHydrationStatus] =
    useState<ResultHydrationStatus>('idle')
  const [resultHydrationRetry, setResultHydrationRetry] = useState(0)
  const handledRunId = useRef<string | null>(null)
  const hydratingRunId = useRef<string | null>(null)

  const healthQuery = useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
    enabled: !USE_DEMO_DATA,
    refetchInterval: 5_000,
  })

  const initialApartmentQuery = useQuery({
    queryKey: apartmentKeys.page('', 1, 1),
    queryFn: () => getApartments({ page: 1, pageSize: 1 }),
    enabled: !USE_DEMO_DATA && selectedApartment === null,
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

  useEffect(() => {
    if (USE_DEMO_DATA || !isRestoringRun) return
    if (analysisQuery.data) {
      setIsRestoringRun(false)
      if (
        analysisQuery.data.status === 'queued'
        || analysisQuery.data.status === 'running'
      ) {
        setNotice('진행 중인 분석을 복원했습니다.')
      }
      return
    }
    if (!analysisQuery.error) return

    setIsRestoringRun(false)
    if (analysisQuery.error instanceof ApiError && analysisQuery.error.status === 404) {
      clearActiveAnalysisSession()
      setCurrentRunId(null)
      setAcceptedStatus(null)
      setNotice('저장된 분석 작업을 찾을 수 없어 새 분석을 시작할 수 있습니다.')
      setSubmissionError('')
      return
    }
    setSubmissionError(apiErrorMessage(analysisQuery.error))
  }, [analysisQuery.data, analysisQuery.error, isRestoringRun])

  useEffect(() => {
    if (USE_DEMO_DATA || selectedApartment) return
    const firstApartment = initialApartmentQuery.data?.items[0]
    if (firstApartment) setSelectedApartment(firstApartment)
  }, [initialApartmentQuery.data?.items, selectedApartment])

  useEffect(() => {
    const run = analysisQuery.data
    if (
      !run
      || !terminalStatuses.has(run.status)
      || handledRunId.current === run.runId
      || hydratingRunId.current === run.runId
    ) return

    if (run.status !== 'completed' && run.status !== 'partial') {
      handledRunId.current = run.runId
      setResultHydrationStatus('idle')
      clearActiveAnalysisSession()
      return
    }
    hydratingRunId.current = run.runId
    setResultHydrationStatus('loading')
    setSubmissionError('')
    void (async () => {
      const result = await getAnalysisResult(run.runId)
      const apartment = await getApartment(
        result.naverComplexId,
        run.sourceId,
        result.runId,
      )
      setSelectedApartment(apartment)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: apartmentKeys.all }),
        queryClient.invalidateQueries({ queryKey: ['dashboard'] }),
        queryClient.invalidateQueries({ queryKey: ['listings'] }),
      ])
      handledRunId.current = run.runId
      hydratingRunId.current = null
      setResultHydrationStatus('ready')
      clearActiveAnalysisSession()
    })().catch((error: unknown) => {
      hydratingRunId.current = null
      setResultHydrationStatus('error')
      setSubmissionError(apiErrorMessage(error))
    })
  }, [analysisQuery.data, queryClient, resultHydrationRetry])

  const startAnalysis = useCallback(async (request: AnalysisCreateApi): Promise<string> => {
    setSubmissionError('')
    setNotice('')
    if (USE_DEMO_DATA) {
      demo.startDemoAnalysis(request)
      return 'demo'
    }

    try {
      const accepted = await createAnalysis(request)
      handledRunId.current = null
      hydratingRunId.current = null
      setResultHydrationStatus('idle')
      writeActiveAnalysisSession(accepted.runId)
      setAcceptedStatus(accepted.status)
      setCurrentRunId(accepted.runId)
      return accepted.runId
    } catch (error) {
      setAcceptedStatus('failed')
      setSubmissionError(apiErrorMessage(error))
      throw error
    }
  }, [demo])

  const retryResultHydration = useCallback(() => {
    if (resultHydrationStatus !== 'error') return
    handledRunId.current = null
    hydratingRunId.current = null
    setResultHydrationRetry((value) => value + 1)
  }, [resultHydrationStatus])

  const cancelQueuedAnalysis = useCallback(async (): Promise<void> => {
    const runStatus = analysisQuery.data?.status ?? acceptedStatus
    if (!currentRunId || runStatus !== 'queued' || isCancelling) return

    setIsCancelling(true)
    setSubmissionError('')
    setNotice('')
    try {
      await cancelAnalysis(currentRunId)
      clearActiveAnalysisSession()
      setCurrentRunId(null)
      setAcceptedStatus('cancelled')
      setResultHydrationStatus('idle')
      setNotice('대기 중인 분석을 취소했습니다.')
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        await analysisQuery.refetch()
        setNotice(error.message)
      } else {
        setSubmissionError(apiErrorMessage(error))
      }
    } finally {
      setIsCancelling(false)
    }
  }, [
    acceptedStatus,
    analysisQuery,
    currentRunId,
    isCancelling,
  ])

  const refreshSelectedApartment = useCallback(async (): Promise<void> => {
    if (USE_DEMO_DATA || !selectedApartment) return
    const apartment = await getApartment(
      selectedApartment.complexId,
      selectedApartment.sourceId,
      undefined,
    )
    setSelectedApartment(apartment)
  }, [selectedApartment])

  const realStatus = analysisQuery.data?.status ?? acceptedStatus ?? 'idle'
  const status: AnalysisStatus = USE_DEMO_DATA ? demo.status : realStatus
  const progress = USE_DEMO_DATA
    ? Math.round((demo.progressStep / Math.max(DEMO_STEPS.length - 1, 1)) * 100)
    : (analysisQuery.data?.progress ?? 0)
  const queryError = analysisQuery.error ?? initialApartmentQuery.error ?? healthQuery.error
  const error = USE_DEMO_DATA
    ? demo.error
    : (
      submissionError
      || (queryError ? apiErrorMessage(queryError) : '')
      || terminalError(analysisQuery.data?.status, analysisQuery.data?.errorCode)
    )

  const value = useMemo<AnalysisProviderValue>(() => ({
    selectedApartment,
    selectedApartmentId: selectedApartment?.complexId ?? null,
    status,
    stage: USE_DEMO_DATA ? null : (analysisQuery.data?.stage ?? null),
    progress,
    error,
    isLoading: USE_DEMO_DATA ? false : analysisQuery.isLoading || initialApartmentQuery.isLoading,
    isEmpty: !USE_DEMO_DATA && !initialApartmentQuery.isLoading && (initialApartmentQuery.data?.total ?? 0) === 0,
    isDemo: USE_DEMO_DATA,
    currentRunId: USE_DEMO_DATA ? null : currentRunId,
    isRestoringRun: USE_DEMO_DATA ? false : isRestoringRun,
    isCancelling: USE_DEMO_DATA ? false : isCancelling,
    notice: USE_DEMO_DATA ? '' : notice,
    browserStatus: USE_DEMO_DATA
      ? 'not_required'
      : (healthQuery.data?.browser ?? 'unknown'),
    resultHydrationStatus: USE_DEMO_DATA ? 'idle' : resultHydrationStatus,
    startAnalysis,
    cancelQueuedAnalysis,
    retryResultHydration,
    selectApartment: setSelectedApartment,
    refreshSelectedApartment,
  }), [
    analysisQuery.data?.stage,
    analysisQuery.isLoading,
    cancelQueuedAnalysis,
    currentRunId,
    error,
    healthQuery.data?.browser,
    initialApartmentQuery.data?.total,
    initialApartmentQuery.isLoading,
    isCancelling,
    isRestoringRun,
    notice,
    progress,
    refreshSelectedApartment,
    resultHydrationStatus,
    retryResultHydration,
    selectedApartment,
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
