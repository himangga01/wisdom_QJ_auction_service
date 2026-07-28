import type { InteractionDelayPresetApi } from './api'

export type CrawlStatus = 'idle' | 'running' | 'completed' | 'failed'

export type TradeType = 'sale' | 'jeonse' | 'monthly'

export type ListingChangeStatus = 'active' | 'new' | 'changed' | 'missing' | 'removed'

export interface RealtorProfile {
  representativeName: string
  officeName: string
  phones: string[]
  address: string
  registrationNumber: string
  ownerVerifiedListingCount: number
}

export interface StructuredMarketDetails {
  finance: Record<string, unknown>
  transactions: Record<string, unknown>
  costs: Record<string, unknown>
  maintenance: Record<string, unknown>
  complex: Record<string, unknown>
  location: Record<string, unknown>
  extraFields: Record<string, unknown>
}

export interface BrokerRegistration {
  articleId: string
  realtorName: string
  provider: string
  detailCollected: boolean
  description: string
  verifiedAt: string
  articleUrl: string
  firstPublishedAt?: string
  isNpay?: boolean
  advertisedPrice?: number
  pricePer3Point3M2?: number
  managementFee?: number
  loanDescription?: string
  supplyAreaM2?: number
  exclusiveAreaM2?: number
  exclusiveRate?: number
  floor?: string
  roomCount?: number
  bathroomCount?: number
  direction?: string
  structure?: string
  moveInDate?: string
  optionTags?: string[]
  realtor?: RealtorProfile
  dataWarnings?: string[]
  extraFields?: Record<string, unknown>
  marketDetails?: StructuredMarketDetails
}

export interface ListingAggregate {
  optionTags: string[]
  moveInSummary: string
  managementFeeSummary: string
  roomBathroomSummary: string
  loanSummary: string
  sourceCount: number
  warnings: string[]
}

export interface ListingMarketDetails {
  loanLimit: number
  ltv: number
  kbMarketPrice: number
  lowestMortgageRate: number
  estimatedMonthlyRepayment: number
  sameAreaAskingRange: string
  sameAreaListingCount: number
  averageSalePrice: number
  averageJeonsePrice: number
  priceGap: number
  twoYearHigh: number
  twoYearLow: number
  recentTransactions: Array<{
    contractDate: string
    floor: string
    price: number
  }>
  brokerageFee: number
  brokerageRate: number
  acquisitionTax: number
  propertyTax: number
  comprehensiveTax: string
  maintenance: {
    referenceMonth: string
    referenceAmount: number
    monthlyAverage: number
    summerAverage: number
    winterAverage: number
  }
  development: string
  elementarySchool: string
  subway: string
  buses: string[]
}

export interface ListingGroup {
  groupId: string
  runId?: string
  building: string
  tradeType: TradeType
  price: number
  rawPrice?: number | null
  deposit?: number
  monthlyRent?: number
  previousPrice?: number
  supplyAreaM2: number
  exclusiveAreaM2: number
  rawSupplyAreaM2?: number | null
  rawExclusiveAreaM2?: number | null
  floor: string
  direction: string
  status: ListingChangeStatus
  discoveredAt: string
  lastSeenAt: string
  absenceDetectedAt?: string
  removedAt?: string
  registrations: BrokerRegistration[]
  brokerRegistrationsLoaded?: boolean
  aggregate?: ListingAggregate
  marketDetails?: ListingMarketDetails
}

export interface ApartmentHistoryPoint {
  collectedAt: string
  saleCount: number
  jeonseCount: number
  monthlyCount: number
  addedCount: number
  removedCount: number
}

export interface ApartmentDetails {
  householdCount: number
  buildingCount: number
  completedYear: number
  parkingPerHousehold: number
  heating: string
  approvalDate?: string
  parkingCount?: number
  entranceType?: string
  floorAreaRatio?: number
  buildingCoverageRatio?: number
  managementOfficePhone?: string
  builders?: string[]
}

export interface ApartmentSummary {
  complexId: string
  complexName: string
  address: string
  details: ApartmentDetails
  listingGroups: ListingGroup[]
  history: ApartmentHistoryPoint[]
}

export interface DashboardDataset {
  analysisId: string
  sourceUrl: string
  collectedAt: string
  apartments: ApartmentSummary[]
}

export interface ScheduleDraft {
  enabled: boolean
  cadence: 'daily' | 'weekdays' | 'weekly'
  time: string
  notifyOnChange: boolean
  collectBrokerDetails: boolean
  interactionDelayPreset: InteractionDelayPresetApi
}
