import type { BrokerRegistration, ListingGroup } from '../types/realEstate'

export interface AggregatedListingAdditionalInfo {
  optionTags: string[]
  moveInSummary: string
  managementFeeSummary: string
  roomBathroomSummary: string
  loanSummary: string
  sourceCount: number
  warningCount: number
}

const optionMatchers: Array<[RegExp, string]> = [
  [/식세기|식기\s*세척기/i, '식기세척기'],
  [/중문/i, '중문'],
  [/미세\s*방충망/i, '미세방충망'],
  [/줄눈/i, '줄눈'],
  [/전자\s*계약/i, '전자계약'],
  [/주인\s*거주/i, '주인거주'],
  [/트인\s*(전망|뷰)|조망\s*우수/i, '트인 전망'],
  [/주차\s*(편리|편한)/i, '주차 편리'],
  [/병점역\s*(인접|가까운)/i, '병점역 인접'],
  [/냉장고장/i, '냉장고장'],
  [/(^|\s)1층($|\s)|귀한\s*1층|선호\s*1층/i, '1층'],
]

const optionPriority = [
  '시스템에어컨',
  '중문',
  '식기세척기',
  '미세방충망',
  '줄눈',
  '전자계약',
  '주인거주',
  '1층',
  '트인 전망',
  '주차 편리',
  '병점역 인접',
  '냉장고장',
]

function normalizeText(value: string): string {
  return value.trim().replace(/\s+/g, ' ')
}

function extractAirConditionerTag(value: string): string | null {
  const match = value.match(/(?:시스템\s*에어컨|에어컨|시에)\s*(\d+)\s*대?/i)
  if (match) return `시스템에어컨 ${Number(match[1])}대`
  if (/(?:시스템\s*에어컨|에어컨|시에)/i.test(value)) return '시스템에어컨'
  return null
}

function canonicalizeTag(value: string): string {
  const normalized = normalizeText(value)
  const airConditioner = extractAirConditionerTag(normalized)
  if (airConditioner) return airConditioner

  const matched = optionMatchers.find(([pattern]) => pattern.test(normalized))
  return matched?.[1] ?? normalized
}

function extractDescriptionTags(registration: BrokerRegistration): string[] {
  const description = registration.description
  const tags: string[] = []
  const airConditioner = extractAirConditionerTag(description)
  if (airConditioner) tags.push(airConditioner)

  optionMatchers.forEach(([pattern, label]) => {
    if (pattern.test(description)) tags.push(label)
  })
  return tags
}

function summarizeCountedValues(values: string[], emptyLabel: string): string {
  if (!values.length) return emptyLabel

  const counts = new Map<string, number>()
  values.forEach((value) => counts.set(value, (counts.get(value) ?? 0) + 1))

  return [...counts.entries()]
    .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0], 'ko'))
    .map(([value, count]) => `${value} ${count}곳`)
    .join(' · ')
}

function normalizeMoveInDate(value: string): string {
  const normalized = normalizeText(value)
  if (/즉시.*협의|협의.*즉시/.test(normalized)) return '즉시입주 협의'
  if (/즉시/.test(normalized)) return '즉시입주'
  if (/협의/.test(normalized) && !/\d{4}/.test(normalized)) return '입주일 협의'
  return normalized
}

function inferMoveInDate(registration: BrokerRegistration): string | null {
  if (registration.moveInDate) return normalizeMoveInDate(registration.moveInDate)
  if (/즉시\s*입주/.test(registration.description)) return '즉시입주'
  if (/입주.*협의|협의.*입주/.test(registration.description)) return '입주일 협의'
  return null
}

function summarizeManagementFees(registrations: BrokerRegistration[]): string {
  const fees = registrations
    .map((registration) => registration.managementFee)
    .filter((fee): fee is number => typeof fee === 'number' && fee > 0)

  if (!fees.length) return '상세 페이지 미표기'

  const minimum = Math.min(...fees)
  const maximum = Math.max(...fees)
  const format = (value: number) => `${Math.round(value / 10_000).toLocaleString('ko-KR')}만원`
  return minimum === maximum ? format(minimum) : `${format(minimum)} ~ ${format(maximum)}`
}

function summarizeRooms(registrations: BrokerRegistration[]): string {
  const values = registrations
    .filter((registration) => registration.roomCount && registration.bathroomCount)
    .map((registration) => `방 ${registration.roomCount}개 · 욕실 ${registration.bathroomCount}개`)
  const uniqueValues = [...new Set(values)]
  return uniqueValues.length ? uniqueValues.join(' / ') : '상세 페이지 미표기'
}

function summarizeLoans(registrations: BrokerRegistration[]): string {
  const noLoanCount = registrations.filter((registration) => registration.loanDescription?.includes('융자 없음')).length
  const describedCount = registrations.filter((registration) => registration.loanDescription && !registration.loanDescription.includes('별도 표기 없음') && !registration.loanDescription.includes('융자 없음')).length
  const unreportedCount = registrations.length - noLoanCount - describedCount
  const parts: string[] = []

  if (noLoanCount) parts.push(`융자 없음 ${noLoanCount}곳`)
  if (describedCount) parts.push(`융자 정보 표기 ${describedCount}곳`)
  if (unreportedCount) parts.push(`미표기 ${unreportedCount}곳`)
  return parts.join(' · ') || '상세 페이지 미표기'
}

function aggregateOptionTags(registrations: BrokerRegistration[]): string[] {
  const normalizedTags = registrations.flatMap((registration) => [
    ...(registration.optionTags ?? []).map(canonicalizeTag),
    ...extractDescriptionTags(registration),
  ])

  const airConditionerCounts = normalizedTags
    .map((tag) => tag.match(/^시스템에어컨 (\d+)대$/)?.[1])
    .filter((count): count is string => Boolean(count))
    .map(Number)

  const uniqueTags = new Set(normalizedTags.filter((tag) => !tag.startsWith('시스템에어컨')))
  const result = [...uniqueTags]

  if (airConditionerCounts.length) {
    const minimum = Math.min(...airConditionerCounts)
    const maximum = Math.max(...airConditionerCounts)
    result.push(minimum === maximum ? `시스템에어컨 ${minimum}대` : `시스템에어컨 ${minimum}~${maximum}대`)
  } else if (normalizedTags.includes('시스템에어컨')) {
    result.push('시스템에어컨')
  }

  return result.sort((left, right) => {
    const leftIndex = optionPriority.findIndex((option) => left.startsWith(option))
    const rightIndex = optionPriority.findIndex((option) => right.startsWith(option))
    const normalizedLeft = leftIndex === -1 ? Number.MAX_SAFE_INTEGER : leftIndex
    const normalizedRight = rightIndex === -1 ? Number.MAX_SAFE_INTEGER : rightIndex
    return normalizedLeft - normalizedRight || left.localeCompare(right, 'ko')
  })
}

export function aggregateListingAdditionalInfo(listing: ListingGroup): AggregatedListingAdditionalInfo {
  if (listing.aggregate) {
    return {
      optionTags: listing.aggregate.optionTags,
      moveInSummary: listing.aggregate.moveInSummary || '상세 페이지 미표기',
      managementFeeSummary: listing.aggregate.managementFeeSummary || '상세 페이지 미표기',
      roomBathroomSummary: listing.aggregate.roomBathroomSummary || '상세 페이지 미표기',
      loanSummary: listing.aggregate.loanSummary || '상세 페이지 미표기',
      sourceCount: listing.aggregate.sourceCount,
      warningCount: listing.aggregate.warnings.length,
    }
  }

  const moveInDates = listing.registrations
    .map(inferMoveInDate)
    .filter((value): value is string => Boolean(value))

  return {
    optionTags: aggregateOptionTags(listing.registrations),
    moveInSummary: summarizeCountedValues(moveInDates, '상세 페이지 미표기'),
    managementFeeSummary: summarizeManagementFees(listing.registrations),
    roomBathroomSummary: summarizeRooms(listing.registrations),
    loanSummary: summarizeLoans(listing.registrations),
    sourceCount: listing.registrations.length,
    warningCount: listing.registrations.reduce((sum, registration) => sum + (registration.dataWarnings?.length ?? 0), 0),
  }
}
