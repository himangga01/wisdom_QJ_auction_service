import type { ApartmentSummary, ListingGroup } from '../types/realEstate'
import { aggregateListingAdditionalInfo } from './listingAdditionalInfo'

export type ListingChangedField =
  | 'price'
  | 'deposit'
  | 'monthlyRent'
  | 'building'
  | 'floor'
  | 'direction'
  | 'supplyAreaM2'
  | 'exclusiveAreaM2'
  | 'managementFee'
  | 'moveInDate'
  | 'roomBathroom'
  | 'loan'
  | 'optionTags'
  | 'registrationCount'
  | 'articleIds'

export interface ListingChangePair {
  before: ListingGroup
  after: ListingGroup
  changedFields: ListingChangedField[]
}

export interface ListingUnobservedPair {
  before?: ListingGroup
  after?: ListingGroup
}

export interface ListingComparison {
  added: ListingGroup[]
  missing: ListingGroup[]
  removed: ListingGroup[]
  changed: ListingChangePair[]
  unchanged: ListingGroup[]
  unobserved: ListingUnobservedPair[]
}

interface ListingComparisonOptions {
  beforeRunStatus?: string
  afterRunStatus?: string
}

function normalizedStrings(values: readonly string[]): string[] {
  return [...new Set(values.map((value) => value.trim()).filter(Boolean))].sort()
}

function sameStrings(left: readonly string[], right: readonly string[]): boolean {
  const normalizedLeft = normalizedStrings(left)
  const normalizedRight = normalizedStrings(right)
  return normalizedLeft.length === normalizedRight.length
    && normalizedLeft.every((value, index) => value === normalizedRight[index])
}

function normalizedText(value: string | undefined | null): string {
  return value?.trim().replace(/\s+/g, ' ') ?? ''
}

function detailCollectionAvailable(listing: ListingGroup): boolean {
  return listing.registrations.length > 0
    && listing.registrations.some((registration) => registration.detailCollected)
}

function rawNumber(
  listing: ListingGroup,
  key: 'rawPrice' | 'rawSupplyAreaM2' | 'rawExclusiveAreaM2',
  fallback: number,
): number | null {
  const value = listing[key]
  return value !== undefined ? value : fallback
}

function changedListingFields(before: ListingGroup, after: ListingGroup): ListingChangedField[] {
  const fields: ListingChangedField[] = []
  if (rawNumber(before, 'rawPrice', before.price) !== rawNumber(after, 'rawPrice', after.price)) fields.push('price')
  if ((before.deposit ?? null) !== (after.deposit ?? null)) fields.push('deposit')
  if ((before.monthlyRent ?? null) !== (after.monthlyRent ?? null)) fields.push('monthlyRent')
  if (normalizedText(before.building) !== normalizedText(after.building)) fields.push('building')
  if (normalizedText(before.floor) !== normalizedText(after.floor)) fields.push('floor')
  if (normalizedText(before.direction) !== normalizedText(after.direction)) fields.push('direction')
  if (rawNumber(before, 'rawSupplyAreaM2', before.supplyAreaM2) !== rawNumber(after, 'rawSupplyAreaM2', after.supplyAreaM2)) fields.push('supplyAreaM2')
  if (rawNumber(before, 'rawExclusiveAreaM2', before.exclusiveAreaM2) !== rawNumber(after, 'rawExclusiveAreaM2', after.exclusiveAreaM2)) fields.push('exclusiveAreaM2')

  const beforeRegistrationCount = before.aggregate?.sourceCount ?? before.registrations.length
  const afterRegistrationCount = after.aggregate?.sourceCount ?? after.registrations.length
  if (beforeRegistrationCount !== afterRegistrationCount) fields.push('registrationCount')

  const beforeRegistrationsLoaded = before.brokerRegistrationsLoaded !== false
  const afterRegistrationsLoaded = after.brokerRegistrationsLoaded !== false
  if (beforeRegistrationsLoaded && afterRegistrationsLoaded) {
    const beforeArticleIds = before.registrations.map((registration) => registration.articleId)
    const afterArticleIds = after.registrations.map((registration) => registration.articleId)
    if (!sameStrings(beforeArticleIds, afterArticleIds)) fields.push('articleIds')
  }

  if (detailCollectionAvailable(before) && detailCollectionAvailable(after)) {
    const beforeDetails = aggregateListingAdditionalInfo(before)
    const afterDetails = aggregateListingAdditionalInfo(after)
    if (normalizedText(beforeDetails.managementFeeSummary) !== normalizedText(afterDetails.managementFeeSummary)) fields.push('managementFee')
    if (normalizedText(beforeDetails.moveInSummary) !== normalizedText(afterDetails.moveInSummary)) fields.push('moveInDate')
    if (normalizedText(beforeDetails.roomBathroomSummary) !== normalizedText(afterDetails.roomBathroomSummary)) fields.push('roomBathroom')
    if (normalizedText(beforeDetails.loanSummary) !== normalizedText(afterDetails.loanSummary)) fields.push('loan')
    if (!sameStrings(beforeDetails.optionTags, afterDetails.optionTags)) fields.push('optionTags')
  }
  return fields
}

export function getListingsAt(apartment: ApartmentSummary, collectedAt: string): ListingGroup[] {
  const capturedTime = new Date(collectedAt).getTime()
  const latestTime = new Date(apartment.history.at(-1)?.collectedAt ?? collectedAt).getTime()

  return apartment.listingGroups
    .filter((listing) => {
      const discoveredTime = new Date(listing.discoveredAt).getTime()
      const removedTime = listing.removedAt ? new Date(listing.removedAt).getTime() : Number.POSITIVE_INFINITY
      return discoveredTime <= capturedTime && capturedTime < removedTime
    })
    .map((listing) => {
      const usePreviousPrice = listing.previousPrice !== undefined && capturedTime < latestTime
      return {
        ...listing,
        price: usePreviousPrice ? listing.previousPrice! : listing.price,
        status: 'active',
        lastSeenAt: collectedAt,
        registrations: listing.registrations.map((registration) => ({
          ...registration,
          verifiedAt: collectedAt.slice(0, 10),
        })),
      }
    })
}

export function compareListingSnapshots(
  before: ListingGroup[],
  after: ListingGroup[],
  options: ListingComparisonOptions = {},
): ListingComparison {
  const beforeById = new Map(before.map((listing) => [listing.groupId, listing]))
  const afterById = new Map(after.map((listing) => [listing.groupId, listing]))
  const added: ListingGroup[] = []
  const missing: ListingGroup[] = []
  const removed: ListingGroup[] = []
  const changed: ListingChangePair[] = []
  const unchanged: ListingGroup[] = []
  const unobserved: ListingUnobservedPair[] = []

  for (const afterListing of after) {
    const beforeListing = beforeById.get(afterListing.groupId)
    if (afterListing.status === 'missing') {
      missing.push(afterListing)
      continue
    }
    if (afterListing.status === 'removed') {
      removed.push(afterListing)
      continue
    }
    if (beforeListing?.status === 'missing' || beforeListing?.status === 'removed') {
      added.push(afterListing)
      continue
    }
    if (!beforeListing) {
      if (afterListing.status === 'new') added.push(afterListing)
      else if (options.beforeRunStatus === 'partial') unobserved.push({ after: afterListing })
      else added.push(afterListing)
      continue
    }

    const changedFields = changedListingFields(beforeListing, afterListing)
    if (changedFields.length) changed.push({ before: beforeListing, after: afterListing, changedFields })
    else unchanged.push(afterListing)
  }

  for (const beforeListing of before) {
    if (afterById.has(beforeListing.groupId)) continue
    if (beforeListing.removedAt) {
      removed.push({ ...beforeListing, status: 'removed' })
    } else {
      unobserved.push({ before: beforeListing })
    }
  }

  return { added, missing, removed, changed, unchanged, unobserved }
}
