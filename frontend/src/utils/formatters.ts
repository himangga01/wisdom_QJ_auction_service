import type { ListingChangeStatus, ListingGroup, TradeType } from '../types/realEstate'

export function formatKoreanPrice(value: number): string {
  if (!Number.isFinite(value) || value <= 0) return '-'
  const eok = Math.floor(value / 100_000_000)
  const manwon = Math.floor((value % 100_000_000) / 10_000)
  const parts: string[] = []

  if (eok > 0) parts.push(`${eok}억`)
  if (manwon > 0) parts.push(manwon.toLocaleString('ko-KR'))

  return parts.length > 0 ? parts.join(' ') : '0'
}

export function formatArea(group: ListingGroup): string {
  const supply = group.supplyAreaM2 > 0 ? `${group.supplyAreaM2}㎡` : '-'
  const exclusive = group.exclusiveAreaM2 > 0 ? `${group.exclusiveAreaM2}㎡` : '-'
  return `${supply} (전용 ${exclusive})`
}

export function formatCollectedAt(value: string): string {
  return new Intl.DateTimeFormat('ko-KR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

export const tradeTypeLabels: Record<TradeType, string> = {
  sale: '매매',
  jeonse: '전세',
  monthly: '월세',
}

export const listingStatusLabels: Record<ListingChangeStatus, string> = {
  active: '유지',
  new: '신규',
  changed: '정보 변경',
  missing: '일시 미노출',
  removed: '삭제',
}

export function formatListingPrice(group: ListingGroup): string {
  if (group.tradeType === 'monthly') {
    const monthlyRent = group.monthlyRent && group.monthlyRent > 0 ? `${group.monthlyRent / 10_000}만` : '-'
    return `${formatKoreanPrice(group.price)} / ${monthlyRent}`
  }
  return formatKoreanPrice(group.price)
}
