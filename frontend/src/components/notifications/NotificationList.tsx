import { BellRing, CheckCircle2 } from 'lucide-react'
import type { NotificationEventTypeApi, NotificationItemApi } from '../../types/api'
import { formatCollectedAt } from '../../utils/formatters'

const eventLabels: Record<NotificationEventTypeApi, string> = {
  new: '신규',
  changed: '변경',
  removed: '삭제',
  restored: '복원',
}

export function NotificationList({
  items,
  onSelect,
}: {
  items: NotificationItemApi[]
  onSelect: (notification: NotificationItemApi) => void
}) {
  if (!items.length) {
    return (
      <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center">
        <CheckCircle2 className="mx-auto text-emerald-500" size={28} />
        <p className="mt-3 text-sm font-bold text-slate-500">표시할 알림이 없습니다.</p>
      </div>
    )
  }

  return (
    <div className="divide-y divide-slate-100 overflow-hidden rounded-2xl border border-slate-200 bg-white">
      {items.map((item) => {
        const changedFields = Array.isArray(item.summary.changedFields)
          ? item.summary.changedFields.filter((field): field is string => typeof field === 'string')
          : []
        return (
          <button
            key={item.id}
            type="button"
            onClick={() => onSelect(item)}
            className={`flex w-full gap-4 px-5 py-5 text-left transition hover:bg-slate-50 ${
              item.readAt ? 'bg-white' : 'bg-emerald-50/50'
            }`}
          >
            <span className={`mt-0.5 grid size-10 shrink-0 place-items-center rounded-full ${
              item.readAt ? 'bg-slate-100 text-slate-500' : 'bg-emerald-100 text-emerald-700'
            }`}>
              <BellRing size={18} />
            </span>
            <span className="min-w-0 flex-1">
              <span className="flex flex-wrap items-center gap-2">
                <strong className="text-sm text-slate-950">{item.title}</strong>
                <span className="rounded-full bg-slate-100 px-2 py-1 text-[11px] font-extrabold text-slate-600">
                  {eventLabels[item.eventType]}
                </span>
                {!item.readAt ? <span className="size-2 rounded-full bg-rose-500" aria-label="읽지 않음" /> : null}
              </span>
              {changedFields.length ? (
                <span className="mt-2 block truncate text-xs text-slate-500">
                  변경 항목: {changedFields.join(', ')}
                </span>
              ) : null}
              <time className="mt-2 block text-xs font-semibold text-slate-400">
                {formatCollectedAt(item.createdAt)}
              </time>
            </span>
          </button>
        )
      })}
    </div>
  )
}
