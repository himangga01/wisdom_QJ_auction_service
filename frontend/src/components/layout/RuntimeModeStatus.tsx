import { Database, Sparkles } from 'lucide-react'
import { useAnalysis } from '../../state/AnalysisProvider'

export type RuntimeDataMode = 'demo' | 'server'

interface RuntimeModeStatusProps {
  variant?: 'badge' | 'footer'
}

export function RuntimeModeStatus({
  variant = 'badge',
}: RuntimeModeStatusProps) {
  const { isDemo } = useAnalysis()
  const mode: RuntimeDataMode = isDemo ? 'demo' : 'server'

  if (variant === 'footer') {
    return (
      <span>
        {mode === 'demo'
          ? '샘플 데이터로 동작하는 UX 미리보기입니다.'
          : '서버에 저장된 조사 데이터를 사용하는 모드입니다.'}
      </span>
    )
  }

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-extrabold ${
        mode === 'demo'
          ? 'border-amber-200 bg-amber-50 text-amber-700'
          : 'border-emerald-200 bg-emerald-50 text-emerald-700'
      }`}
    >
      {mode === 'demo' ? <Sparkles size={13} /> : <Database size={13} />}
      {mode === 'demo'
        ? 'DEMO · 샘플 데이터 모드'
        : '실데이터 · 서버 데이터 모드'}
    </span>
  )
}
