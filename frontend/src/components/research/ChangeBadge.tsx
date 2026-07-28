import type { ListingChangeStatus } from '../../types/realEstate'
import { listingStatusLabels } from '../../utils/formatters'

const styles: Record<ListingChangeStatus, string> = {
  active: 'border-slate-200 bg-slate-50 text-slate-600',
  new: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  changed: 'border-amber-200 bg-amber-50 text-amber-700',
  removed: 'border-rose-200 bg-rose-50 text-rose-700',
}

export function ChangeBadge({ status }: { status: ListingChangeStatus }) {
  return (
    <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-extrabold ${styles[status]}`}>
      {listingStatusLabels[status]}
    </span>
  )
}
