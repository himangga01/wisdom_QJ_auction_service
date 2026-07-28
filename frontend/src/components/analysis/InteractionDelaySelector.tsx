import type { InteractionDelayPresetApi } from '../../types/api'

export const INTERACTION_DELAY_PRESET_OPTIONS = [
  { value: 'very_fast', label: '매우 빠름', range: '0.5초' },
  { value: 'fast', label: '빠름', range: '0.7~1.2초' },
  { value: 'normal', label: '기본', range: '1~2.5초' },
  { value: 'careful', label: '신중', range: '2~5초' },
  { value: 'very_careful', label: '매우 신중', range: '3~7초' },
] as const satisfies readonly {
  value: InteractionDelayPresetApi
  label: string
  range: string
}[]

export function interactionDelayPresetText(
  value: InteractionDelayPresetApi,
): string {
  const option = INTERACTION_DELAY_PRESET_OPTIONS.find(
    (candidate) => candidate.value === value,
  )
  return option ? `${option.label} · ${option.range}` : value
}

interface InteractionDelaySelectorProps {
  value: InteractionDelayPresetApi
  onChange: (value: InteractionDelayPresetApi) => void
  disabled?: boolean
  name?: string
}

export function InteractionDelaySelector({
  value,
  onChange,
  disabled = false,
  name = 'interaction-delay-preset',
}: InteractionDelaySelectorProps) {
  return (
    <fieldset disabled={disabled} className="min-w-0">
      <legend className="text-sm font-extrabold text-slate-700">
        Chrome 화면 탐색 속도
      </legend>
      <p className="mt-1 text-xs leading-5 text-slate-500">
        화면 이동·클릭·스크롤 사이에 적용할 대기 시간을 선택합니다.
      </p>
      <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-5">
        {INTERACTION_DELAY_PRESET_OPTIONS.map((option) => {
          const selected = option.value === value
          return (
            <label
              key={option.value}
              className={`flex min-h-16 cursor-pointer flex-col justify-center rounded-xl border px-3 py-2.5 transition ${
                selected
                  ? 'border-emerald-500 bg-emerald-50 text-emerald-800'
                  : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300'
              } ${disabled ? 'cursor-not-allowed opacity-60' : ''}`}
            >
              <span className="flex items-center gap-2">
                <input
                  type="radio"
                  name={name}
                  value={option.value}
                  checked={selected}
                  onChange={() => onChange(option.value)}
                  className="size-4 border-slate-300 text-emerald-600 focus:ring-emerald-500"
                />
                <span className="text-xs font-extrabold">{option.label}</span>
              </span>
              <span className="mt-1 pl-6 text-[11px] font-semibold text-slate-500">
                {option.range}
              </span>
            </label>
          )
        })}
      </div>
      {value === 'very_fast' ? (
        <p className="mt-2 text-xs font-bold text-amber-700">
          접근 제한 가능성이 높아질 수 있습니다.
        </p>
      ) : null}
    </fieldset>
  )
}
