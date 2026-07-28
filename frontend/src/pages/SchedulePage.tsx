import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CalendarCheck2, CalendarClock, Check, Clock3, Link2, PlayCircle, Trash2 } from 'lucide-react'
import { useEffect, useMemo, useState, type FormEvent } from 'react'
import {
  createSchedule,
  deleteSchedule,
  getScheduleRuns,
  getSchedules,
  patchSchedule,
  scheduleKeys,
} from '../api/schedules'
import {
  InteractionDelaySelector,
  interactionDelayPresetText,
} from '../components/analysis/InteractionDelaySelector'
import { useAnalysis } from '../state/AnalysisProvider'
import { useDemoAnalysis } from '../state/DemoAnalysisContext'
import type { ScheduleCadence } from '../types/api'
import type { ScheduleDraft } from '../types/realEstate'
import { formatCollectedAt } from '../utils/formatters'

const cadenceLabels: Record<ScheduleCadence, string> = {
  daily: '매일',
  weekdays: '평일',
  weekly: '매주 월요일',
}

const runStatusLabels: Record<string, string> = {
  queued: '대기 중',
  running: '진행 중',
  completed: '완료',
  partial: '일부 완료',
  failed: '실패',
  blocked: '접근 차단',
  cancelled: '취소',
}

function errorText(error: unknown): string {
  return error instanceof Error ? error.message : '스케줄 요청을 처리하지 못했습니다.'
}

export function SchedulePage() {
  const queryClient = useQueryClient()
  const analysis = useAnalysis()
  const demo = useDemoAnalysis()
  const selectedSource = useMemo(
    () => analysis.recentApartments.find((item) => item.complexId === analysis.selectedApartmentId) ?? analysis.recentApartments[0],
    [analysis.recentApartments, analysis.selectedApartmentId],
  )
  const [draft, setDraft] = useState<ScheduleDraft>({
    enabled: true,
    cadence: 'daily',
    time: '09:00',
    notifyOnChange: true,
    collectBrokerDetails: true,
    interactionDelayPreset: 'normal',
  })
  const [demoSaved, setDemoSaved] = useState(false)

  const schedulesQuery = useQuery({
    queryKey: scheduleKeys.all,
    queryFn: getSchedules,
    enabled: !analysis.isDemo,
  })
  const currentSchedule = schedulesQuery.data?.find((item) => item.sourceId === selectedSource?.sourceId)
  const runsQuery = useQuery({
    queryKey: scheduleKeys.runs(currentSchedule?.id ?? ''),
    queryFn: () => getScheduleRuns(currentSchedule!.id),
    enabled: !analysis.isDemo && Boolean(currentSchedule?.id),
  })

  useEffect(() => {
    if (!currentSchedule) return
    setDraft((current) => ({
      ...current,
      enabled: currentSchedule.enabled,
      cadence: currentSchedule.cadence,
      time: currentSchedule.timeOfDay.slice(0, 5),
      collectBrokerDetails: currentSchedule.collectBrokerDetails,
      interactionDelayPreset: currentSchedule.interactionDelayPreset,
    }))
  }, [currentSchedule])

  const saveMutation = useMutation({
    mutationFn: async () => {
      const payload = {
        cadence: draft.cadence,
        timeOfDay: draft.time,
        timezone: 'Asia/Seoul' as const,
        weekday: draft.cadence === 'weekly' ? 0 : null,
        enabled: draft.enabled,
        collectBrokerDetails: draft.collectBrokerDetails,
        interactionDelayPreset: draft.interactionDelayPreset,
      }
      if (currentSchedule) return patchSchedule(currentSchedule.id, payload)
      if (!selectedSource) throw new Error('먼저 URL 조사를 완료해 주세요.')
      return createSchedule({ ...payload, sourceId: selectedSource.sourceId })
    },
    onSuccess: async (saved) => {
      await queryClient.invalidateQueries({ queryKey: scheduleKeys.all })
      await queryClient.invalidateQueries({ queryKey: scheduleKeys.runs(saved.id) })
    },
  })
  const removeMutation = useMutation({
    mutationFn: () => deleteSchedule(currentSchedule!.id, !currentSchedule!.enabled),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: scheduleKeys.all })
    },
  })

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    if (analysis.isDemo) {
      setDemoSaved(true)
      window.setTimeout(() => setDemoSaved(false), 1800)
      return
    }
    saveMutation.mutate()
  }

  const sourceUrl = analysis.isDemo ? demo.dataset?.sourceUrl : selectedSource?.sourceUrl
  const pending = saveMutation.isPending || removeMutation.isPending
  const requestError = saveMutation.error ?? removeMutation.error ?? schedulesQuery.error ?? runsQuery.error
  const hasDisplaySchedule = analysis.isDemo || Boolean(currentSchedule)
  const displayEnabled = analysis.isDemo ? draft.enabled : Boolean(currentSchedule?.enabled)
  const displayCadence = analysis.isDemo ? draft.cadence : currentSchedule?.cadence
  const displayTime = analysis.isDemo ? draft.time : currentSchedule?.timeOfDay.slice(0, 5)
  const displayCollectBrokerDetails = analysis.isDemo ? draft.collectBrokerDetails : currentSchedule?.collectBrokerDetails
  const displayInteractionDelayPreset = analysis.isDemo ? draft.interactionDelayPreset : currentSchedule?.interactionDelayPreset
  const displayNextRun = analysis.isDemo ? '데모에서는 계산하지 않음' : (currentSchedule ? formatCollectedAt(currentSchedule.nextRunAt) : '-')

  return (
    <div className="space-y-6">
      <header>
        <p className="flex items-center gap-2 text-sm font-extrabold text-emerald-700"><CalendarClock size={17} /> 조사 자동화</p>
        <h1 className="mt-1 text-3xl font-black tracking-[-0.04em] text-slate-950">조사 스케줄</h1>
        <p className="mt-2 text-sm text-slate-500">같은 네이버 부동산 URL을 정해진 시각에 다시 조사하는 설정 화면입니다.</p>
      </header>

      {schedulesQuery.isLoading && !analysis.isDemo ? <div className="rounded-2xl border border-slate-200 bg-white p-5 text-sm font-bold text-slate-500">저장된 스케줄을 불러오는 중입니다.</div> : null}
      {requestError ? <div role="alert" className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm font-bold text-rose-700">{errorText(requestError)}</div> : null}

      <div className="grid gap-5 xl:grid-cols-[0.95fr_1.05fr]">
        <form onSubmit={handleSubmit} className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
          <div className="flex items-start justify-between gap-4">
            <div><h2 className="text-xl font-black text-slate-950">자동 조사 설정</h2><p className="mt-1 text-sm text-slate-500">{analysis.isDemo ? '데모 설정은 브라우저에서만 유지됩니다.' : '저장하면 서버 스케줄러가 다음 실행 시각을 계산합니다.'}</p></div>
            <button type="button" aria-pressed={draft.enabled} onClick={() => setDraft((current) => ({ ...current, enabled: !current.enabled }))} className={`relative h-7 w-12 rounded-full transition ${draft.enabled ? 'bg-emerald-600' : 'bg-slate-300'}`}><span className={`absolute top-1 size-5 rounded-full bg-white shadow transition ${draft.enabled ? 'left-6' : 'left-1'}`} /></button>
          </div>

          <div className="mt-7 space-y-5">
            <div>
              <label className="text-sm font-extrabold text-slate-700" htmlFor="schedule-url">조사 URL</label>
              <div className="relative mt-2"><Link2 className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" size={17} /><input id="schedule-url" readOnly value={sourceUrl ?? 'URL 조사 후 연결됩니다'} className="h-12 w-full truncate rounded-xl border border-slate-200 bg-slate-50 pl-11 pr-4 text-sm text-slate-500" /></div>
            </div>
            <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 transition has-[:focus-visible]:border-emerald-500 has-[:focus-visible]:ring-4 has-[:focus-visible]:ring-emerald-100">
              <input
                type="checkbox"
                checked={draft.collectBrokerDetails}
                onChange={(event) => setDraft((current) => ({ ...current, collectBrokerDetails: event.target.checked }))}
                className="mt-0.5 h-4 w-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
              />
              <span>
                <span className="block text-sm font-bold text-slate-800">중개사 등록 물건 추가 상세정보 수집</span>
                <span className="mt-1 block text-sm leading-5 text-slate-500">각 중개사 매물의 시세·거래·비용·관리비·단지·입지 정보를 함께 수집합니다. 조사 시간이 더 걸릴 수 있습니다.</span>
              </span>
            </label>
            <InteractionDelaySelector
              name="schedule-interaction-delay-preset"
              value={draft.interactionDelayPreset}
              onChange={(interactionDelayPreset) => setDraft((current) => ({
                ...current,
                interactionDelayPreset,
              }))}
              disabled={pending}
            />
            <fieldset>
              <legend className="text-sm font-extrabold text-slate-700">반복 주기</legend>
              <div className="mt-2 grid grid-cols-3 gap-2">{(['daily', 'weekdays', 'weekly'] as ScheduleCadence[]).map((cadence) => <button key={cadence} type="button" onClick={() => setDraft((current) => ({ ...current, cadence }))} className={`rounded-xl border px-3 py-3 text-sm font-bold ${draft.cadence === cadence ? 'border-emerald-500 bg-emerald-50 text-emerald-700' : 'border-slate-200 text-slate-500'}`}>{cadenceLabels[cadence]}</button>)}</div>
            </fieldset>
            <div>
              <label className="text-sm font-extrabold text-slate-700" htmlFor="schedule-time">조사 시작 시각</label>
              <input id="schedule-time" type="time" value={draft.time} onChange={(event) => setDraft((current) => ({ ...current, time: event.target.value }))} className="mt-2 h-12 w-full rounded-xl border border-slate-300 px-4 text-sm font-bold outline-none focus:border-emerald-500 focus:ring-4 focus:ring-emerald-100" />
            </div>
            <label className={`flex items-center justify-between gap-4 rounded-2xl border border-slate-200 p-4 ${analysis.isDemo ? 'cursor-pointer' : 'opacity-60'}`}>
              <span><strong className="block text-sm text-slate-800">변경 발생 알림</strong><small className="mt-1 block text-xs text-slate-400">{analysis.isDemo ? '신규·가격 변경·삭제 매물이 있을 때 알립니다.' : '현재 서버 API에는 알림 설정이 포함되어 있지 않습니다.'}</small></span>
              <input type="checkbox" disabled={!analysis.isDemo} checked={analysis.isDemo && draft.notifyOnChange} onChange={(event) => setDraft((current) => ({ ...current, notifyOnChange: event.target.checked }))} className="size-5 accent-emerald-600" />
            </label>
          </div>

          <button type="submit" disabled={pending || (!analysis.isDemo && !selectedSource)} className="mt-7 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-slate-950 px-5 py-3.5 text-sm font-extrabold text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:bg-slate-400">{demoSaved || saveMutation.isSuccess ? <><Check size={17} /> 저장되었습니다</> : pending ? '처리 중...' : '스케줄 저장'}</button>
          {!analysis.isDemo && currentSchedule ? <button type="button" disabled={pending} onClick={() => removeMutation.mutate()} className="mt-2 inline-flex w-full items-center justify-center gap-2 rounded-xl border border-rose-200 px-5 py-3 text-sm font-extrabold text-rose-700 hover:bg-rose-50 disabled:opacity-50"><Trash2 size={16} /> {currentSchedule.enabled ? '스케줄 비활성화' : '스케줄 삭제'}</button> : null}
        </form>

        <div className="space-y-5">
          <section className="rounded-3xl bg-slate-950 p-6 text-white sm:p-7">
            <p className="flex items-center gap-2 text-sm font-bold text-emerald-300"><CalendarCheck2 size={17} /> 현재 스케줄</p>
            {hasDisplaySchedule && displayCadence ? <div className="mt-5 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between"><div><p className="text-3xl font-black">{displayEnabled ? `${cadenceLabels[displayCadence]} ${displayTime}` : '자동 조사 꺼짐'}</p><p className="mt-2 text-sm text-slate-400">{displayCollectBrokerDetails ? '추가 상세 수집' : '기본 정보만 수집'} · {interactionDelayPresetText(displayInteractionDelayPreset ?? 'normal')} · 다음 예정: {displayNextRun}</p></div><span className={`w-fit rounded-full px-3 py-1.5 text-xs font-extrabold ${displayEnabled ? 'bg-emerald-500/20 text-emerald-300' : 'bg-white/10 text-slate-400'}`}>{displayEnabled ? '활성' : '비활성'}</span></div> : <p className="mt-5 text-sm font-bold text-slate-400">저장된 스케줄이 없습니다.</p>}
          </section>

          <section className="rounded-3xl border border-slate-200 bg-white p-5 sm:p-6">
            <h2 className="flex items-center gap-2 text-lg font-black text-slate-950"><Clock3 size={18} /> 최근 실행 내역</h2>
            <div className="mt-4 divide-y divide-slate-100">
              {analysis.isDemo ? <p className="py-6 text-center text-sm font-bold text-slate-400">데모 실행 이력은 제공하지 않습니다.</p> : runsQuery.isLoading ? <p className="py-6 text-center text-sm font-bold text-slate-400">실행 이력을 불러오는 중입니다.</p> : runsQuery.data?.items.length ? runsQuery.data.items.map((run) => {
                const date = run.finishedAt ?? run.startedAt ?? run.createdAt
                const successful = run.status === 'completed'
                const partial = run.status === 'partial'
                return <article key={run.runId} className="flex items-center gap-3 py-4"><span className={`grid size-9 place-items-center rounded-full ${successful ? 'bg-emerald-50 text-emerald-700' : partial ? 'bg-amber-50 text-amber-700' : 'bg-rose-50 text-rose-700'}`}><PlayCircle size={17} /></span><div className="min-w-0 flex-1"><p className="text-sm font-extrabold text-slate-800">{formatCollectedAt(date)} · {runStatusLabels[run.status] ?? run.status}</p><p className="mt-1 text-xs text-slate-400">{run.collectBrokerDetails ? '추가 상세 수집' : '기본 정보만 수집'} · {interactionDelayPresetText(run.interactionDelayPreset)} · 단계 {run.stage} · 진행률 {run.progress}%{run.errorCode ? ` · ${run.errorCode}` : ''}</p></div><span className={`rounded-full px-2.5 py-1 text-xs font-bold ${successful ? 'bg-emerald-50 text-emerald-700' : partial ? 'bg-amber-50 text-amber-700' : 'bg-rose-50 text-rose-700'}`}>{runStatusLabels[run.status] ?? run.status}</span></article>
              }) : <p className="py-6 text-center text-sm font-bold text-slate-400">최근 실행 이력이 없습니다.</p>}
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}
