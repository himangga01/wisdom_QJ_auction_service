import type {
  ApartmentDetailApi,
  ApartmentSummaryApi,
  BrokerRegistrationApi,
  DashboardResponseApi,
  ListingAbsenceApi,
  ListingDetailApi,
  ListingSummaryApi,
} from '../types/api'
import type {
  ApartmentDetails,
  ApartmentSummary,
  DashboardDataset,
  ListingChangeStatus,
  ListingGroup,
  TradeType,
} from '../types/realEstate'

function numberValue(source: Record<string, unknown>, keys: string[], fallback = 0): number {
  for (const key of keys) {
    const value = source[key]
    if (typeof value === 'number' && Number.isFinite(value)) return value
    if (typeof value === 'string' && value.trim() && Number.isFinite(Number(value))) return Number(value)
  }
  return fallback
}

function stringValue(source: Record<string, unknown>, keys: string[], fallback = '-'): string {
  for (const key of keys) {
    const value = source[key]
    if (typeof value === 'string' && value.trim()) return value
  }
  return fallback
}

function adaptDetails(details: Record<string, unknown>): ApartmentDetails {
  const approvalDate = stringValue(details, ['approvalDate', 'useApproveDate', '사용승인일', '승인일'], '') || undefined
  const explicitCompletedYear = numberValue(details, ['completedYear', 'completionYear', 'useApproveYear', '준공년도'])
  const approvalYear = approvalDate?.match(/(?:19|20)\d{2}/)?.[0]
  return {
    householdCount: numberValue(details, ['householdCount', 'totalHouseholdCount', '세대수']),
    buildingCount: numberValue(details, ['buildingCount', 'totalBuildingCount', '동수', '동 수']),
    completedYear: explicitCompletedYear || (approvalYear ? Number(approvalYear) : 0),
    parkingPerHousehold: numberValue(details, ['parkingPerHousehold', '세대당주차', '세대당 주차']),
    heating: stringValue(details, ['heating', 'heatingMethod', '난방', '난방방식']),
    approvalDate,
    parkingCount: numberValue(details, ['parkingCount', 'parking', '주차대수'], Number.NaN) || undefined,
    entranceType: stringValue(details, ['entranceType', 'entrance', '현관', '현관구조'], '') || undefined,
    floorAreaRatio: numberValue(details, ['floorAreaRatio', '용적률'], Number.NaN) || undefined,
    buildingCoverageRatio: numberValue(details, ['buildingCoverageRatio', '건폐율'], Number.NaN) || undefined,
    managementOfficePhone: stringValue(details, ['managementOfficePhone', 'managementOffice', '관리사무소'], '') || undefined,
    builders: (() => {
      const value = details.builders ?? details.builder ?? details['시공사']
      if (Array.isArray(value)) return value.filter((item): item is string => typeof item === 'string' && Boolean(item.trim()))
      return typeof value === 'string' && value.trim() ? [value] : undefined
    })(),
  }
}

function tradeType(value: string): TradeType {
  return value === 'jeonse' || value === 'monthly' ? value : 'sale'
}

function listingStatus(value: string): ListingChangeStatus {
  return value === 'new' || value === 'changed' || value === 'missing' || value === 'removed' ? value : 'active'
}

function adaptRegistration(registration: BrokerRegistrationApi) {
  const realtor = registration.realtor
  return {
    articleId: registration.articleId,
    realtorName: registration.realtorName || '-',
    provider: registration.provider,
    detailCollected: registration.detailCollected,
    description: registration.description,
    verifiedAt: registration.verifiedAt ?? '-',
    articleUrl: registration.articleUrl,
    firstPublishedAt: registration.firstPublishedAt ?? undefined,
    isNpay: registration.isNpay,
    advertisedPrice: registration.advertisedPrice ?? undefined,
    pricePer3Point3M2: registration.pricePer3Point3M2 ?? undefined,
    managementFee: registration.managementFee ?? undefined,
    loanDescription: registration.loanDescription ?? undefined,
    supplyAreaM2: registration.supplyAreaM2 ?? undefined,
    exclusiveAreaM2: registration.exclusiveAreaM2 ?? undefined,
    exclusiveRate: registration.exclusiveRate ?? undefined,
    floor: registration.floor ?? undefined,
    roomCount: registration.roomCount ?? undefined,
    bathroomCount: registration.bathroomCount ?? undefined,
    direction: registration.direction ?? undefined,
    structure: registration.structure ?? undefined,
    moveInDate: registration.moveInDate ?? undefined,
    optionTags: registration.optionTags,
    dataWarnings: registration.dataWarnings,
    extraFields: registration.extraFields,
    marketDetails: registration.marketDetails ?? undefined,
    realtor: realtor ? {
      representativeName: typeof realtor.representativeName === 'string' ? realtor.representativeName : '-',
      officeName: typeof realtor.officeName === 'string' ? realtor.officeName : '-',
      phones: Array.isArray(realtor.phones) ? realtor.phones.filter((phone): phone is string => typeof phone === 'string') : [],
      address: typeof realtor.address === 'string' ? realtor.address : '-',
      registrationNumber: typeof realtor.registrationNumber === 'string' ? realtor.registrationNumber : '-',
      ownerVerifiedListingCount: typeof realtor.ownerVerifiedListingCount === 'number' ? realtor.ownerVerifiedListingCount : 0,
    } : undefined,
  }
}

export function adaptListing(listing: ListingSummaryApi): ListingGroup {
  return {
    groupId: listing.groupId,
    runId: listing.runId,
    building: listing.building ?? '-',
    tradeType: tradeType(listing.tradeType),
    price: listing.price ?? listing.deposit ?? 0,
    rawPrice: listing.price,
    deposit: listing.deposit ?? undefined,
    monthlyRent: listing.monthlyRent ?? undefined,
    previousPrice: listing.previousPrice ?? undefined,
    supplyAreaM2: listing.supplyAreaM2 ?? 0,
    exclusiveAreaM2: listing.exclusiveAreaM2 ?? 0,
    rawSupplyAreaM2: listing.supplyAreaM2,
    rawExclusiveAreaM2: listing.exclusiveAreaM2,
    floor: listing.floor ?? '-',
    direction: listing.direction ?? '-',
    status: listingStatus(listing.status),
    discoveredAt: listing.discoveredAt,
    lastSeenAt: listing.lastSeenAt,
    removedAt: listing.removedAt ?? undefined,
    registrations: [],
    brokerRegistrationsLoaded: false,
    aggregate: {
      optionTags: listing.aggregate.optionTags,
      moveInSummary: listing.aggregate.moveInSummary,
      managementFeeSummary: listing.aggregate.managementFeeSummary,
      roomBathroomSummary: listing.aggregate.roomBathSummary,
      loanSummary: listing.aggregate.loanSummary,
      sourceCount: listing.aggregate.sourceCount,
      warnings: listing.aggregate.warnings,
    },
  }
}

export function adaptListingAbsence(absence: ListingAbsenceApi, selectedRunId?: string): ListingGroup {
  return {
    ...adaptListing({
      ...absence.lastSnapshot,
      status: absence.status,
      removedAt: absence.removedAt,
    }),
    runId: selectedRunId ?? absence.lastSnapshot.runId,
    absenceDetectedAt: absence.detectedAt,
    removedAt: absence.removedAt ?? undefined,
  }
}

export function adaptListingDetail(listing: ListingDetailApi): ListingGroup {
  return {
    ...adaptListing(listing),
    absenceDetectedAt: listing.absenceDetectedAt ?? undefined,
    registrations: listing.registrations.map(adaptRegistration),
    brokerRegistrationsLoaded: true,
  }
}

function adaptApartmentBase(apartment: ApartmentSummaryApi, listingGroups: ListingGroup[]): ApartmentSummary {
  return {
    complexId: apartment.complexId,
    complexName: apartment.complexName,
    address: apartment.address,
    sourceId: apartment.sourceId,
    details: adaptDetails(apartment.details),
    listingGroups,
    history: [],
  }
}

export function adaptApartmentDetail(apartment: ApartmentDetailApi, listingGroups: ListingGroup[] = []): ApartmentSummary {
  return {
    ...adaptApartmentBase(apartment, listingGroups),
    history: apartment.history.map((point) => ({
      collectedAt: point.collectedAt,
      saleCount: point.saleCount,
      jeonseCount: point.jeonseCount,
      monthlyCount: point.monthlyCount,
      addedCount: point.addedCount,
      removedCount: point.removedCount,
    })),
  }
}

export function adaptDashboard(response: DashboardResponseApi): DashboardDataset {
  const apartment: ApartmentSummary = {
    complexId: response.apartment.complexId,
    complexName: response.apartment.complexName,
    address: response.apartment.address,
    details: adaptDetails(response.apartment.details),
    listingGroups: response.listings.map(adaptListing),
    history: response.apartment.history.map((point) => ({
      collectedAt: point.collectedAt,
      saleCount: point.saleCount,
      jeonseCount: point.jeonseCount,
      monthlyCount: point.monthlyCount,
      addedCount: point.addedCount,
      removedCount: point.removedCount,
    })),
  }

  return {
    analysisId: response.runId,
    sourceUrl: response.sourceUrl,
    collectedAt: response.collectedAt,
    apartments: [apartment],
  }
}
