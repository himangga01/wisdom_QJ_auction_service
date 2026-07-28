import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { cancelAnalysis, createAnalysis, getAnalysis, getAnalysisResult } from '../api/analyses'
import { getApartment, getApartments } from '../api/apartments'
import { getHealth } from '../api/health'
import { ApiError } from '../api/client'
import { AnalysisProvider, useAnalysis } from '../state/AnalysisProvider'
import {
  ACTIVE_ANALYSIS_SESSION_KEY,
  writeActiveAnalysisSession,
} from '../state/analysisRunSession'
import { DemoAnalysisProvider } from '../state/DemoAnalysisContext'
import type { AnalysisStatusApi } from '../types/api'

vi.mock('../api/analyses', () => ({
  createAnalysis: vi.fn(),
  getAnalysis: vi.fn(),
  getAnalysisResult: vi.fn(),
  cancelAnalysis: vi.fn(),
}))

vi.mock('../api/apartments', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/apartments')>()
  return {
    ...actual,
    getApartments: vi.fn(),
    getApartment: vi.fn(),
  }
})

vi.mock('../api/health', () => ({
  getHealth: vi.fn(),
}))

const RUN_ID = '7f43e80d-4d5f-4d68-b41b-0ed4e260cae4'

function status(statusValue: AnalysisStatusApi['status']): AnalysisStatusApi {
  return {
    runId: RUN_ID,
    sourceId: 'source-1',
    status: statusValue,
    collectBrokerDetails: true,
    interactionDelayPreset: 'normal',
    stage: 'listings',
    progress: statusValue === 'queued' ? 0 : 35,
    errorCode: null,
    startedAt: statusValue === 'queued' ? null : '2026-07-29T00:00:00Z',
    finishedAt: null,
  }
}

function RecoveryProbe() {
  const analysis = useAnalysis()
  return (
    <div>
      <span data-testid="status">{analysis.status}</span>
      <span data-testid="restoring">{String(analysis.isRestoringRun)}</span>
      <span data-testid="notice">{analysis.notice}</span>
      <span data-testid="error">{analysis.error}</span>
      <span data-testid="hydration">{analysis.resultHydrationStatus}</span>
      {analysis.resultHydrationStatus === 'error' ? (
        <button type="button" onClick={analysis.retryResultHydration}>
          결과 다시 불러오기
        </button>
      ) : null}
      {analysis.status === 'queued' ? (
        <button
          type="button"
          disabled={analysis.isCancelling}
          onClick={() => void analysis.cancelQueuedAnalysis()}
        >
          {analysis.isCancelling ? '취소 중...' : '대기 중인 분석 취소'}
        </button>
      ) : null}
      <button
        type="button"
        onClick={() =>
          void analysis.startAnalysis({
            sourceUrl: 'https://fin.land.naver.com/map?one=true',
            collectBrokerDetails: true,
            interactionDelayPreset: 'normal',
          })}
      >
        새 분석
      </button>
    </div>
  )
}

function renderRecovery() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <DemoAnalysisProvider>
        <AnalysisProvider>
          <RecoveryProbe />
        </AnalysisProvider>
      </DemoAnalysisProvider>
    </QueryClientProvider>,
  )
}

describe('활성 분석 복원', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.sessionStorage.clear()
    vi.mocked(getApartments).mockResolvedValue({
      items: [],
      page: 1,
      pageSize: 1,
      total: 0,
    })
    vi.mocked(getHealth).mockResolvedValue({
      status: 'ok',
      database: 'connected',
      redis: 'not_required',
      browser: 'ready',
    })
  })

  it('저장된 queued 실행을 복원하고 취소한 뒤 세션을 정리한다', async () => {
    const user = userEvent.setup()
    writeActiveAnalysisSession(RUN_ID)
    vi.mocked(getAnalysis).mockResolvedValue(status('queued'))
    vi.mocked(cancelAnalysis).mockResolvedValue({
      runId: RUN_ID,
      status: 'cancelled',
    })

    renderRecovery()

    expect(screen.getByTestId('restoring')).toHaveTextContent('true')
    expect(await screen.findByRole('button', { name: '대기 중인 분석 취소' })).toBeEnabled()
    expect(screen.getByTestId('restoring')).toHaveTextContent('false')

    await user.click(screen.getByRole('button', { name: '대기 중인 분석 취소' }))

    await waitFor(() => expect(cancelAnalysis).toHaveBeenCalledWith(RUN_ID))
    expect(screen.getByTestId('status')).toHaveTextContent('cancelled')
    expect(screen.getByTestId('notice')).toHaveTextContent('대기 중인 분석을 취소했습니다.')
    expect(window.sessionStorage.getItem(ACTIVE_ANALYSIS_SESSION_KEY)).toBeNull()
  })

  it('running 실행은 복원하지만 취소 동작을 노출하지 않는다', async () => {
    writeActiveAnalysisSession(RUN_ID)
    vi.mocked(getAnalysis).mockResolvedValue(status('running'))

    renderRecovery()

    await waitFor(() =>
      expect(screen.getByTestId('status')).toHaveTextContent('running'),
    )
    expect(screen.queryByRole('button', { name: '대기 중인 분석 취소' })).not.toBeInTheDocument()
    expect(window.sessionStorage.getItem(ACTIVE_ANALYSIS_SESSION_KEY)).not.toBeNull()
  })

  it('404 stale 실행은 정리하고 네트워크 오류는 복원 키를 유지한다', async () => {
    writeActiveAnalysisSession(RUN_ID)
    vi.mocked(getAnalysis).mockRejectedValueOnce(
      new ApiError('분석을 찾을 수 없습니다.', 404, null, null),
    )

    const firstRender = renderRecovery()

    await waitFor(() =>
      expect(screen.getByTestId('notice')).toHaveTextContent(
        '저장된 분석 작업을 찾을 수 없어 새 분석을 시작할 수 있습니다.',
      ),
    )
    expect(window.sessionStorage.getItem(ACTIVE_ANALYSIS_SESSION_KEY)).toBeNull()

    firstRender.unmount()
    writeActiveAnalysisSession(RUN_ID)
    vi.mocked(getAnalysis).mockRejectedValueOnce(new TypeError('network failed'))

    renderRecovery()

    await waitFor(() =>
      expect(screen.getByTestId('error')).toHaveTextContent(
        'API 서버에 연결할 수 없습니다.',
      ),
    )
    expect(window.sessionStorage.getItem(ACTIVE_ANALYSIS_SESSION_KEY)).not.toBeNull()
  })

  it('새로 승인된 실행을 즉시 저장하고 terminal 상태에서 정리한다', async () => {
    const user = userEvent.setup()
    vi.mocked(createAnalysis).mockResolvedValue(status('queued'))
    vi.mocked(getAnalysis)
      .mockResolvedValueOnce(status('queued'))
      .mockResolvedValueOnce(status('failed'))

    renderRecovery()
    await user.click(screen.getByRole('button', { name: '새 분석' }))

    await waitFor(() =>
      expect(window.sessionStorage.getItem(ACTIVE_ANALYSIS_SESSION_KEY)).not.toBeNull(),
    )
    await waitFor(() =>
      expect(screen.getByTestId('status')).toHaveTextContent('failed'),
      { timeout: 2_000 },
    )
    expect(window.sessionStorage.getItem(ACTIVE_ANALYSIS_SESSION_KEY)).toBeNull()
  })

  it('취소 409 응답이면 세션을 유지하고 최신 running 상태를 다시 조회한다', async () => {
    const user = userEvent.setup()
    writeActiveAnalysisSession(RUN_ID)
    vi.mocked(getAnalysis)
      .mockResolvedValueOnce(status('queued'))
      .mockResolvedValueOnce(status('running'))
    vi.mocked(cancelAnalysis).mockRejectedValue(
      new ApiError('이미 실행 중인 분석입니다.', 409, 'analysis_not_queued', null),
    )

    renderRecovery()
    await user.click(
      await screen.findByRole('button', { name: '대기 중인 분석 취소' }),
    )

    await waitFor(() =>
      expect(screen.getByTestId('status')).toHaveTextContent('running'),
    )
    expect(screen.getByTestId('notice')).toHaveTextContent(
      '이미 실행 중인 분석입니다.',
    )
    expect(window.sessionStorage.getItem(ACTIVE_ANALYSIS_SESSION_KEY)).not.toBeNull()
  })

  it('완료 결과를 source 범위로 불러온 뒤에만 복구 세션을 정리한다', async () => {
    writeActiveAnalysisSession(RUN_ID)
    vi.mocked(getAnalysis).mockResolvedValue(status('completed'))
    vi.mocked(getAnalysisResult).mockResolvedValue({
      runId: RUN_ID,
      status: 'completed',
      apartmentId: 'apartment-1',
      naverComplexId: 'complex-1',
      name: '완료 아파트',
      summary: {},
    })
    vi.mocked(getApartment).mockResolvedValue({
      apartmentId: 'apartment-1',
      complexId: 'complex-1',
      complexName: '완료 아파트',
      address: '서울',
      sourceId: 'source-1',
      sourceUrl: 'https://fin.land.naver.com/map?one=true',
      latestRunId: RUN_ID,
      latestStatus: 'completed',
      collectedAt: '2026-07-29T00:00:00Z',
      details: {},
      listingCount: 1,
      availableRuns: [],
      history: [],
    })

    renderRecovery()

    await waitFor(() =>
      expect(getApartment).toHaveBeenCalledWith(
        'complex-1',
        'source-1',
        RUN_ID,
      ),
    )
    expect(screen.getByTestId('hydration')).toHaveTextContent('ready')
    expect(window.sessionStorage.getItem(ACTIVE_ANALYSIS_SESSION_KEY)).toBeNull()
  })

  it('완료 결과 조회가 실패하면 세션과 완료 CTA를 보류하고 다시 불러올 수 있다', async () => {
    const user = userEvent.setup()
    writeActiveAnalysisSession(RUN_ID)
    vi.mocked(getAnalysis).mockResolvedValue(status('completed'))
    vi.mocked(getAnalysisResult).mockResolvedValue({
      runId: RUN_ID,
      status: 'completed',
      apartmentId: 'apartment-1',
      naverComplexId: 'complex-1',
      name: '완료 아파트',
      summary: {},
    })
    vi.mocked(getApartment)
      .mockRejectedValueOnce(new TypeError('network failed'))
      .mockResolvedValue({
        apartmentId: 'apartment-1',
        complexId: 'complex-1',
        complexName: '완료 아파트',
        address: '서울',
        sourceId: 'source-1',
        sourceUrl: 'https://fin.land.naver.com/map?one=true',
        latestRunId: RUN_ID,
        latestStatus: 'completed',
        collectedAt: '2026-07-29T00:00:00Z',
        details: {},
        listingCount: 1,
        availableRuns: [],
        history: [],
      })

    renderRecovery()

    await waitFor(() =>
      expect(screen.getByTestId('error')).toHaveTextContent(
        'API 서버에 연결할 수 없습니다.',
      ),
    )
    expect(screen.getByTestId('hydration')).toHaveTextContent('error')
    expect(window.sessionStorage.getItem(ACTIVE_ANALYSIS_SESSION_KEY)).not.toBeNull()

    await user.click(screen.getByRole('button', { name: '결과 다시 불러오기' }))

    await waitFor(() =>
      expect(screen.getByTestId('hydration')).toHaveTextContent('ready'),
    )
    expect(getApartment).toHaveBeenCalledTimes(2)
    expect(window.sessionStorage.getItem(ACTIVE_ANALYSIS_SESSION_KEY)).toBeNull()
  })
})
