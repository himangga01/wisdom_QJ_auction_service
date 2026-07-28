import { ArrowRight, CircleHelp, CircleMinus, CirclePlus, Equal, RefreshCcw } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { ApartmentSummary, ListingGroup } from '../../types/realEstate'
import {
  compareListingSnapshots,
  getListingsAt,
  type ListingChangePair,
  type ListingChangedField,
} from '../../utils/listingHistory'
import { aggregateListingAdditionalInfo } from '../../utils/listingAdditionalInfo'
import { formatKoreanPrice, formatListingPrice, tradeTypeLabels } from '../../utils/formatters'
import { listingHref } from '../../utils/sourceLinks'

interface ListingComparisonBoardProps {
  apartment: ApartmentSummary
  beforeDate: string
  afterDate: string
  beforeListings?: ListingGroup[]
  afterListings?: ListingGroup[]
  beforeRunStatus?: string
  focusListingId?: string
}

type ComparisonCardType = 'added' | 'missing' | 'removed' | 'changed' | 'unobserved'

interface Specification {
  label: string
  value: string
  fields: ListingChangedField[]
}

function Specs({
  listing,
  changedFields = [],
}: {
  listing: ListingGroup
  changedFields?: ListingChangePair['changedFields']
}) {
  const information = aggregateListingAdditionalInfo(listing)
  const articleIds = [...new Set(listing.registrations.map((registration) => registration.articleId))]
    .sort()
    .join(', ')
  const specifications: Specification[] = [
    {
      label: '호가',
      value: formatListingPrice(listing),
      fields: ['price'],
    },
    {
      label: '보증금',
      value: listing.deposit !== undefined ? formatKoreanPrice(listing.deposit) : '-',
      fields: ['deposit'],
    },
    {
      label: '월세',
      value: listing.monthlyRent !== undefined
        ? `${Math.round(listing.monthlyRent / 10_000).toLocaleString('ko-KR')}만`
        : '-',
      fields: ['monthlyRent'],
    },
    {
      label: '동·층',
      value: `${listing.building} · ${listing.floor}`,
      fields: ['building', 'floor'],
    },
    {
      label: '방향',
      value: listing.direction,
      fields: ['direction'],
    },
    {
      label: '공급·전용면적',
      value: `${listing.supplyAreaM2}㎡ · ${listing.exclusiveAreaM2}㎡`,
      fields: ['supplyAreaM2', 'exclusiveAreaM2'],
    },
    {
      label: '방·욕실',
      value: information.roomBathroomSummary,
      fields: ['roomBathroom'],
    },
    {
      label: '관리비',
      value: information.managementFeeSummary,
      fields: ['managementFee'],
    },
    {
      label: '입주 가능',
      value: information.moveInSummary,
      fields: ['moveInDate'],
    },
    {
      label: '융자',
      value: information.loanSummary,
      fields: ['loan'],
    },
    {
      label: '주요 옵션',
      value: information.optionTags.join(', ') || '-',
      fields: ['optionTags'],
    },
    {
      label: '중개사 등록',
      value: `${information.sourceCount}곳`,
      fields: ['registrationCount'],
    },
    {
      label: '매물번호',
      value: articleIds || '-',
      fields: ['articleIds'],
    },
  ]

  return (
    <dl className="mt-3 space-y-2">
      {specifications.map((specification) => {
        const changed = specification.fields.some((field) => changedFields.includes(field))
        return (
          <div
            key={specification.label}
            className={`flex items-start justify-between gap-3 rounded-lg px-3 py-2 text-sm ${
              changed ? 'bg-amber-100' : 'bg-slate-50'
            }`}
          >
            <dt className="shrink-0 text-xs font-bold text-slate-400">{specification.label}</dt>
            <dd className={`break-all text-right font-extrabold ${changed ? 'text-amber-800' : 'text-slate-800'}`}>
              {specification.value}
            </dd>
          </div>
        )
      })}
    </dl>
  )
}

function EmptySide({ label, description }: { label: string; description?: string }) {
  return (
    <div className="grid min-h-44 place-items-center rounded-xl border border-dashed border-slate-200 bg-slate-50 text-center">
      <div className="px-4">
        <CircleMinus className="mx-auto text-slate-300" size={24} />
        <p className="mt-2 text-xs font-bold text-slate-500">{label}</p>
        {description ? <p className="mt-1 text-[11px] leading-5 text-slate-400">{description}</p> : null}
      </div>
    </div>
  )
}

function ComparisonCard({
  apartment,
  type,
  before,
  after,
  changedFields,
  focused = false,
}: {
  apartment: ApartmentSummary
  type: ComparisonCardType
  before?: ListingGroup
  after?: ListingGroup
  changedFields?: ListingChangePair['changedFields']
  focused?: boolean
}) {
  const listing = after ?? before!
  const config = {
    added: {
      label: '신규·재노출',
      icon: CirclePlus,
      tone: 'border-emerald-200 bg-emerald-50 text-emerald-700',
      empty: '기준일에 없음',
    },
    missing: {
      label: '일시 미노출',
      icon: CircleHelp,
      tone: 'border-sky-200 bg-sky-50 text-sky-700',
      empty: '선택 조사에서 미노출',
    },
    removed: {
      label: '삭제',
      icon: CircleMinus,
      tone: 'border-rose-200 bg-rose-50 text-rose-700',
      empty: '삭제가 확정됨',
    },
    changed: {
      label: '정보 변경',
      icon: RefreshCcw,
      tone: 'border-amber-200 bg-amber-50 text-amber-700',
      empty: '',
    },
    unobserved: {
      label: '확인 불가',
      icon: CircleHelp,
      tone: 'border-slate-200 bg-slate-100 text-slate-600',
      empty: '상태 판정 정보 없음',
    },
  }[type]
  const StatusIcon = config.icon
  const beforeSide = !before
    ? (
      <EmptySide
        label={type === 'unobserved' ? '기준일 확인 불가' : '기준일에 없음'}
        description={type === 'unobserved' ? '부분 조사에서 관측 여부를 확정할 수 없습니다.' : undefined}
      />
    )
    : before.status === 'missing'
      ? <EmptySide label="기준일에 일시 미노출" description="해당 조사에서 실제 관측되지 않은 상태입니다." />
      : before.status === 'removed'
        ? <EmptySide label="기준일에 삭제 상태" description="마지막 관측 사양은 상세 페이지에서 확인할 수 있습니다." />
        : <Specs listing={before} changedFields={changedFields} />
  const afterSide = after && !['missing', 'removed'].includes(type)
    ? <Specs listing={after} changedFields={changedFields} />
    : (
      <EmptySide
        label={config.empty}
        description={
          type === 'missing'
            ? '1회 미관측 상태이며 삭제로 확정하지 않습니다.'
            : type === 'unobserved'
              ? '부분 조사 등으로 상태를 확정할 수 없습니다.'
              : undefined
        }
      />
    )

  return (
    <article
      id={`listing-${listing.groupId}`}
      data-testid={`comparison-listing-${listing.groupId}`}
      data-focused={focused ? 'true' : 'false'}
      className={`overflow-hidden rounded-2xl border bg-white shadow-sm ${
        focused
          ? 'border-emerald-500 outline outline-4 outline-emerald-200'
          : 'border-slate-200'
      }`}
    >
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 p-4">
        <div>
          <p className="text-xs font-bold text-slate-400">{tradeTypeLabels[listing.tradeType]} · {listing.groupId}</p>
          <h3 className="mt-1 font-black text-slate-950">{listing.building} · 전용 {listing.exclusiveAreaM2}㎡</h3>
        </div>
        <span className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-extrabold ${config.tone}`}>
          <StatusIcon size={14} /> {config.label}
        </span>
      </header>
      <div className="grid gap-3 p-4 md:grid-cols-[1fr_auto_1fr] md:items-center">
        <div>
          <p className="mb-2 text-xs font-extrabold text-slate-500">비교 기준일</p>
          {beforeSide}
        </div>
        <ArrowRight className="mx-auto hidden text-slate-300 md:block" size={18} />
        <div>
          <p className="mb-2 text-xs font-extrabold text-slate-500">선택 조사일</p>
          {afterSide}
        </div>
      </div>
      <footer className="border-t border-slate-100 px-4 py-3 text-right">
        <Link
          to={listingHref(apartment.complexId, listing.groupId, {
            sourceId: apartment.sourceId,
            runId: listing.runId,
          })}
          className="text-xs font-extrabold text-emerald-700"
        >
          매물 상세 보기 →
        </Link>
      </footer>
    </article>
  )
}

export function ListingComparisonBoard({
  apartment,
  beforeDate,
  afterDate,
  beforeListings,
  afterListings,
  beforeRunStatus,
  focusListingId,
}: ListingComparisonBoardProps) {
  const before = beforeListings ?? getListingsAt(apartment, beforeDate)
  const after = afterListings ?? getListingsAt(apartment, afterDate)
  const beforeById = new Map(before.map((listing) => [listing.groupId, listing]))
  const comparison = compareListingSnapshots(before, after, { beforeRunStatus })
  const differenceCount = comparison.added.length
    + comparison.missing.length
    + comparison.removed.length
    + comparison.changed.length
    + comparison.unobserved.length

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4"><p className="text-xs font-bold text-emerald-700">신규·재노출</p><p className="mt-1 text-2xl font-black text-emerald-900">{comparison.added.length}건</p></div>
        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4"><p className="text-xs font-bold text-amber-700">정보 변경</p><p className="mt-1 text-2xl font-black text-amber-900">{comparison.changed.length}건</p></div>
        <div className="rounded-2xl border border-sky-200 bg-sky-50 p-4"><p className="text-xs font-bold text-sky-700">일시 미노출</p><p className="mt-1 text-2xl font-black text-sky-900">{comparison.missing.length}건</p></div>
        <div className="rounded-2xl border border-rose-200 bg-rose-50 p-4"><p className="text-xs font-bold text-rose-700">삭제</p><p className="mt-1 text-2xl font-black text-rose-900">{comparison.removed.length}건</p></div>
        <div className="rounded-2xl border border-slate-200 bg-white p-4"><p className="flex items-center gap-1 text-xs font-bold text-slate-500"><Equal size={13} /> 동일</p><p className="mt-1 text-2xl font-black text-slate-900">{comparison.unchanged.length}건</p></div>
        <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4"><p className="flex items-center gap-1 text-xs font-bold text-slate-500"><CircleHelp size={13} /> 확인 불가</p><p className="mt-1 text-2xl font-black text-slate-900">{comparison.unobserved.length}건</p></div>
      </div>

      {differenceCount ? (
        <div className="grid gap-4 xl:grid-cols-2">
          {comparison.added.map((listing) => <ComparisonCard key={`added-${listing.groupId}`} apartment={apartment} type="added" after={listing} focused={listing.groupId === focusListingId} />)}
          {comparison.changed.map((pair) => <ComparisonCard key={`changed-${pair.after.groupId}`} apartment={apartment} type="changed" before={pair.before} after={pair.after} changedFields={pair.changedFields} focused={pair.after.groupId === focusListingId} />)}
          {comparison.missing.map((listing) => <ComparisonCard key={`missing-${listing.groupId}`} apartment={apartment} type="missing" before={beforeById.get(listing.groupId)} after={listing} focused={listing.groupId === focusListingId} />)}
          {comparison.removed.map((listing) => <ComparisonCard key={`removed-${listing.groupId}`} apartment={apartment} type="removed" before={beforeById.get(listing.groupId)} after={listing} focused={listing.groupId === focusListingId} />)}
          {comparison.unobserved.map((pair) => {
            const listing = pair.after ?? pair.before!
            return <ComparisonCard key={`unobserved-${listing.groupId}`} apartment={apartment} type="unobserved" before={pair.before} after={pair.after} focused={listing.groupId === focusListingId} />
          })}
        </div>
      ) : (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center text-sm font-semibold text-slate-400">
          두 조사일 사이에 달라진 매물이 없습니다.
        </div>
      )}
    </div>
  )
}
