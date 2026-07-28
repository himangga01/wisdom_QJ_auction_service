import { ArrowRight, Building2, CheckCircle2, Clock3 } from 'lucide-react'
import { Link } from 'react-router-dom'
import { UrlAnalysisPanel } from '../components/analysis/UrlAnalysisPanel'
import { useAnalysis } from '../state/AnalysisProvider'
import { useDemoAnalysis } from '../state/DemoAnalysisContext'
import type { AnalysisCreateApi } from '../types/api'
import { formatCollectedAt } from '../utils/formatters'

export function AnalysisPage() {
  const analysis = useAnalysis()
  const demo = useDemoAnalysis()
  const status = analysis.isDemo ? demo.status : analysis.status
  const progress = analysis.isDemo
    ? Math.round((demo.progressStep / 3) * 100)
    : analysis.progress
  const selectedDemoApartment = demo.dataset?.apartments.find((apartment) => apartment.complexId === demo.selectedApartmentId)
  const selectedRealApartment = analysis.recentApartments.find((apartment) => apartment.complexId === analysis.selectedApartmentId)
  const selectedApartment = analysis.isDemo ? selectedDemoApartment : selectedRealApartment
  const collectedAt = analysis.isDemo ? demo.dataset?.collectedAt : selectedRealApartment?.collectedAt
  const completed = status === 'completed' || status === 'partial'

  const startAnalysis = (request: AnalysisCreateApi) => {
    if (analysis.isDemo) {
      demo.startDemoAnalysis(request)
      return
    }
    return analysis.startAnalysis(request)
  }

  return (
    <div className="py-5 lg:py-10">
      <UrlAnalysisPanel
        status={status}
        stage={analysis.isDemo ? null : analysis.stage}
        progress={progress}
        error={analysis.isDemo ? demo.error : analysis.error}
        onStart={startAnalysis}
      />

      {completed ? (
        <section className="mx-auto mt-5 max-w-4xl rounded-[24px] border border-emerald-200 bg-emerald-50/70 p-6 shadow-sm" aria-live="polite">
          <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="flex items-center gap-2 text-sm font-extrabold text-emerald-700">
                <CheckCircle2 size={18} /> {status === 'partial' ? '일부 결과 저장 완료' : '조사 완료'}
              </div>
              <h2 className="mt-2 text-xl font-black text-slate-950">분석 결과가 준비되었습니다</h2>
              <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-sm text-slate-600">
                {selectedApartment ? <span className="inline-flex items-center gap-1.5"><Building2 size={15} /> {selectedApartment.complexName}</span> : null}
                {collectedAt ? <span className="inline-flex items-center gap-1.5"><Clock3 size={15} /> {formatCollectedAt(collectedAt)}</span> : null}
              </div>
            </div>
            <Link
              to="/dashboard"
              className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl bg-slate-950 px-5 py-3 text-sm font-extrabold text-white transition hover:bg-emerald-700"
            >
              대시보드에서 결과 보기 <ArrowRight size={17} />
            </Link>
          </div>
        </section>
      ) : null}
    </div>
  )
}
