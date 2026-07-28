import type {
  ApartmentSummary,
  DashboardDataset,
  ListingChangeStatus,
  ListingGroup,
  TradeType,
} from '../types/realEstate'

export function getCurrentListings(apartment: ApartmentSummary): ListingGroup[] {
  return apartment.listingGroups.filter((listing) => listing.status !== 'removed')
}

export function getTradeMetrics(apartment: ApartmentSummary, tradeType: TradeType) {
  const listings = getCurrentListings(apartment).filter((listing) => listing.tradeType === tradeType)
  const averagePrice = listings.length
    ? listings.reduce((sum, listing) => sum + listing.price, 0) / listings.length
    : 0
  const averageMonthlyRent = listings.length
    ? listings.reduce((sum, listing) => sum + (listing.monthlyRent ?? 0), 0) / listings.length
    : 0

  return { count: listings.length, averagePrice, averageMonthlyRent }
}

export function getChangeCount(apartment: ApartmentSummary, status: ListingChangeStatus): number {
  return apartment.listingGroups.filter((listing) => listing.status === status).length
}

export function getApartmentMetrics(apartment: ApartmentSummary) {
  const groups = getCurrentListings(apartment)
  const saleGroups = groups.filter((group) => group.tradeType === 'sale')
  const prices = saleGroups.map((group) => group.price)
  const registrations = groups.flatMap((group) => group.registrations)
  const areas = [...new Set(groups.map((group) => group.exclusiveAreaM2))].sort((a, b) => a - b)
  const verifiedDates = registrations.map((item) => item.verifiedAt).sort().reverse()

  return {
    groupCount: groups.length,
    registrationCount: registrations.length,
    minPrice: prices.length ? Math.min(...prices) : 0,
    maxPrice: prices.length ? Math.max(...prices) : 0,
    averagePrice: prices.length ? prices.reduce((sum, price) => sum + price, 0) / prices.length : 0,
    areas,
    latestVerifiedAt: verifiedDates[0] ?? '-',
    newCount: getChangeCount(apartment, 'new'),
    changedCount: getChangeCount(apartment, 'changed'),
    removedCount: getChangeCount(apartment, 'removed'),
  }
}

export function getDashboardMetrics(dataset: DashboardDataset) {
  const groups = dataset.apartments.flatMap(getCurrentListings)
  const registrations = groups.flatMap((group) => group.registrations)
  const salePrices = groups.filter((group) => group.tradeType === 'sale').map((group) => group.price)

  return {
    apartmentCount: dataset.apartments.length,
    listingCount: groups.length,
    groupCount: groups.length,
    registrationCount: registrations.length,
    minPrice: salePrices.length ? Math.min(...salePrices) : 0,
    newCount: dataset.apartments.reduce((sum, apartment) => sum + getChangeCount(apartment, 'new'), 0),
    removedCount: dataset.apartments.reduce((sum, apartment) => sum + getChangeCount(apartment, 'removed'), 0),
  }
}
