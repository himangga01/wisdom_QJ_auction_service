import { ArrowRight, Link2, ShieldCheck } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import type {
  AnalysisCreateApi,
  AnalysisRunStage,
  InteractionDelayPresetApi,
} from '../../types/api'
import { CrawlProgress, type CrawlProgressStatus } from './CrawlProgress'
import { InteractionDelaySelector } from './InteractionDelaySelector'

interface UrlAnalysisPanelProps {
  status: CrawlProgressStatus
  stage?: AnalysisRunStage | null
  progress: number
  error: string
  onStart: (request: AnalysisCreateApi) => void | Promise<unknown>
}

const DEMO_URL = 'https://fin.land.naver.com/map?center=3zjA42-2AwLTK&zoom=17.1505204617303&layer=NobwRAlgJmBcYGMD2BbADgGwKYA8D6UWALgIYQZgA0YaJATiSgM5zjLrY4CSM8AjACYALAHYAzAFYwAX2pMs9BAAsACvUYtY4CEwBq5DCTgAzEhnnVSAIzhh6RCAmwzZ23nboOnWAsTIVqWgZmVg8vbB5bAQA2MQBOPgAOATihAAYZOQU6ZTVgzRBpaQBdIA'

export function UrlAnalysisPanel({ status, stage = null, progress, error, onStart }: UrlAnalysisPanelProps) {
  const [url, setUrl] = useState(DEMO_URL)
  const [collectBrokerDetails, setCollectBrokerDetails] = useState(true)
  const [interactionDelayPreset, setInteractionDelayPreset] =
    useState<InteractionDelayPresetApi>('normal')
  const busy = status === 'queued' || status === 'running'

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const sourceUrl = url.trim()
    if (!sourceUrl || busy) return
    void Promise.resolve(
      onStart({
        sourceUrl,
        collectBrokerDetails,
        interactionDelayPreset,
      }),
    ).catch(() => undefined)
  }

  return (
    <section className="mx-auto max-w-4xl overflow-hidden rounded-[28px] border border-slate-200 bg-white shadow-[0_18px_60px_rgba(15,23,42,0.06)]">
      <div className="p-6 sm:p-9 lg:p-11">
        <div className="flex items-center gap-2 text-sm font-extrabold text-emerald-700">
          <ShieldCheck size={17} /> URL 기반 매물 조사
        </div>
        <h1 className="mt-4 text-3xl font-black leading-tight tracking-[-0.045em] text-slate-950 sm:text-4xl">
          네이버 부동산 URL을 입력하세요
        </h1>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-500 sm:text-base">
          URL에 포함된 아파트의 매물을 조사해 단지별 현황과 변경 이력을 정리합니다.
        </p>

        <form className="mt-8" onSubmit={handleSubmit}>
          <label className="mb-2 block text-sm font-bold text-slate-700" htmlFor="naver-land-url">
            네이버 부동산 URL
          </label>
          <div className="flex flex-col gap-3 sm:flex-row">
            <div className="relative min-w-0 flex-1">
              <Link2 className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
              <input
                id="naver-land-url"
                value={url}
                onChange={(event) => setUrl(event.target.value)}
                className="h-13 w-full rounded-xl border border-slate-300 bg-white pl-11 pr-4 text-sm outline-none transition focus:border-emerald-500 focus:ring-4 focus:ring-emerald-100"
                placeholder="https://fin.land.naver.com/..."
                aria-describedby={error ? 'url-error' : undefined}
              />
            </div>
            <button
              type="submit"
              disabled={busy || !url.trim()}
              className="inline-flex h-13 items-center justify-center gap-2 rounded-xl bg-slate-950 px-6 text-sm font-extrabold text-white transition hover:bg-emerald-700 focus:outline-none focus:ring-4 focus:ring-emerald-200 disabled:cursor-wait disabled:bg-slate-400"
            >
              {status === 'queued' ? '요청 대기 중...' : status === 'running' ? '분석 중...' : '분석 시작'}
              <ArrowRight size={17} />
            </button>
          </div>
          <label className="mt-4 flex cursor-pointer items-start gap-3 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 transition has-[:focus-visible]:border-emerald-500 has-[:focus-visible]:ring-4 has-[:focus-visible]:ring-emerald-100 disabled:cursor-not-allowed disabled:opacity-60">
            <input
              type="checkbox"
              checked={collectBrokerDetails}
              onChange={(event) => setCollectBrokerDetails(event.target.checked)}
              disabled={busy}
              className="mt-0.5 h-4 w-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500 disabled:cursor-not-allowed"
            />
            <span>
              <span className="block text-sm font-bold text-slate-800">중개사 등록 물건 추가 상세정보 수집</span>
              <span className="mt-1 block text-sm leading-5 text-slate-500">각 중개사 매물의 시세·거래·비용·관리비·단지·입지 정보를 함께 수집합니다. 분석 시간이 더 걸릴 수 있습니다.</span>
            </span>
          </label>
          <div className="mt-5">
            <InteractionDelaySelector
              value={interactionDelayPreset}
              onChange={setInteractionDelayPreset}
              disabled={busy}
            />
          </div>
          {error ? <p id="url-error" role="alert" className="mt-2 text-sm font-semibold text-rose-600">{error}</p> : null}
        </form>

        <CrawlProgress status={status} stage={stage} progress={progress} />
      </div>
    </section>
  )
}
