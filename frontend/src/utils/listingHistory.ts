import type { ApartmentSummary, ListingGroup } from '../types/realEstate'

export interface ListingChangePair {
  before: ListingGroup
  after: ListingGroup
  changedFields: Array<'price' | 'monthlyRent' | 'floor' | 'direction'>
}

export interface ListingComparison {
  added: ListingGroup[]
  removed: ListingGroup[]
  changed: ListingChangePair[]
  unchanged: ListingGroup[]
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

export function compareListingSnapshots(before: ListingGroup[], after: ListingGroup[]): ListingComparison {
  const beforeById = new Map(before.map((listing) => [listing.groupId, listing]))
  const afterById = new Map(after.map((listing) => [listing.groupId, listing]))
  const added = after.filter((listing) => !beforeById.has(listing.groupId))
  const removed = before.filter((listing) => !afterById.has(listing.groupId))
  const changed: ListingChangePair[] = []
  const unchanged: ListingGroup[] = []

  for (const afterListing of after) {
    const beforeListing = beforeById.get(afterListing.groupId)
    if (!beforeListing) continue

    const changedFields: ListingChangePair['changedFields'] = []
    if (beforeListing.price !== afterListing.price) changedFields.push('price')
    if ((beforeListing.monthlyRent ?? 0) !== (afterListing.monthlyRent ?? 0)) changedFields.push('monthlyRent')
    if (beforeListing.floor !== afterListing.floor) changedFields.push('floor')
    if (beforeListing.direction !== afterListing.direction) changedFields.push('direction')

    if (changedFields.length) changed.push({ before: beforeListing, after: afterListing, changedFields })
    else unchanged.push(afterListing)
  }

  return { added, removed, changed, unchanged }
}
