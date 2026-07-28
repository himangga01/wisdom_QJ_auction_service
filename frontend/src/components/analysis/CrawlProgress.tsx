import { AlertTriangle, Check, LoaderCircle } from 'lucide-react'
import type { AnalysisRunStage, AnalysisRunStatus } from '../../types/api'

export type CrawlProgressStatus = 'idle' | AnalysisRunStatus

interface CrawlProgressProps {
  status: CrawlProgressStatus
  stage?: AnalysisRunStage | null
  progress: number
  isCancelling?: boolean
  onCancel?: () => void | Promise<void>
}

const steps = ['URL 확인', '매물 목록 수집', '중개사·상세 정보 정리', '결과 저장'] as const

const stageStep: Record<AnalysisRunStage, number> = {
  url: 0,
  complex: 0,
  listings: 1,
  brokers: 2,
  details: 2,
  compare: 3,
  save: 3,
}

export function CrawlProgress({
  status,
  stage = null,
  progress,
  isCancelling = false,
  onCancel,
}: CrawlProgressProps) {
  const visible = status === 'queued' || status === 'running' || status === 'completed' || status === 'partial'
  if (!visible) return null

  const complete = status === 'completed' || status === 'partial'
  const partial = status === 'partial'
  const safeProgress = complete ? 100 : Math.min(100, Math.max(0, progress))
  const activeStep = stage ? stageStep[stage] : Math.min(3, Math.floor(safeProgress / 25))
  const title = partial
    ? '일부 결과로 분석 완료'
    : complete
      ? '분석 완료'
      : status === 'queued'
        ? '분석 요청 대기 중'
        : '분석 진행 중'

  return (
    <div className="mt-6 rounded-2xl border border-slate-200 bg-slate-50 p-4" aria-live="polite">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-2 text-sm font-bold text-slate-800">
          {partial ? (
            <span className="grid size-6 place-items-center rounded-full bg-amber-500 text-white"><AlertTriangle size={14} /></span>
          ) : complete ? (
            <span className="grid size-6 place-items-center rounded-full bg-emerald-600 text-white"><Check size={14} /></span>
          ) : (
            <LoaderCircle className="animate-spin text-emerald-600" size={20} />
          )}
          <span>{title}</span>
        </div>
        <span className="text-xs font-semibold text-slate-500">{safeProgress}%</span>
      </div>

      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-slate-200" aria-hidden="true">
        <div className="h-full rounded-full bg-emerald-600 transition-[width] duration-300" style={{ width: `${safeProgress}%` }} />
      </div>

      <ol className="mt-4 grid gap-2 sm:grid-cols-4">
        {steps.map((step, index) => {
          const done = complete || index <= activeStep
          return (
            <li key={step} className="flex items-center gap-2 text-xs font-semibold">
              <span className={`grid size-5 place-items-center rounded-full ${done ? 'bg-emerald-600 text-white' : 'bg-slate-200 text-slate-400'}`}>
                {done ? <Check size={12} /> : index + 1}
              </span>
              <span className={done ? 'text-slate-700' : 'text-slate-400'}>{step}</span>
            </li>
          )
        })}
      </ol>
      {status === 'queued' && onCancel ? (
        <button
          type="button"
          onClick={() => void onCancel()}
          disabled={isCancelling}
          className="mt-4 rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-extrabold text-slate-700 hover:border-rose-300 hover:text-rose-700 disabled:cursor-wait disabled:text-slate-400"
        >
          {isCancelling ? '취소 중...' : '대기 중인 분석 취소'}
        </button>
      ) : null}
    </div>
  )
}
