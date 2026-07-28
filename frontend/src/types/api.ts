export type AnalysisRunStatus =
  | 'queued'
  | 'running'
  | 'completed'
  | 'partial'
  | 'failed'
  | 'blocked'
  | 'cancelled'

export type AnalysisRunStage =
  | 'url'
  | 'complex'
  | 'listings'
  | 'brokers'
  | 'details'
  | 'compare'
  | 'save'

export type TradeTypeApi = 'sale' | 'jeonse' | 'monthly'
export type ListingStatusApi = 'active' | 'new' | 'changed' | 'missing' | 'removed'
export type ScheduleCadence = 'daily' | 'weekdays' | 'weekly'
export type InteractionDelayPresetApi =
  | 'very_fast'
  | 'fast'
  | 'normal'
  | 'careful'
  | 'very_careful'
export type NotificationEventTypeApi = 'new' | 'changed' | 'removed' | 'restored'

export interface HealthResponseApi {
  status: 'ok' | 'degraded'
  database: 'connected' | 'disconnected'
  redis: 'connected' | 'disconnected' | 'not_required'
  browser: 'ready' | 'unavailable' | 'not_required'
}

export interface AnalysisCreateApi {
  sourceUrl: string
  collectBrokerDetails: boolean
  interactionDelayPreset: InteractionDelayPresetApi
}

export interface AnalysisAcceptedApi {
  runId: string
  sourceId: string
  status: AnalysisRunStatus
  collectBrokerDetails: boolean
  interactionDelayPreset: InteractionDelayPresetApi
}

export interface AnalysisStatusApi extends AnalysisAcceptedApi {
  stage: AnalysisRunStage
  progress: number
  errorCode: string | null
  startedAt: string | null
  finishedAt: string | null
}

export interface AnalysisResultApi {
  runId: string
  status: AnalysisRunStatus
  apartmentId: string
  naverComplexId: string
  name: string
  summary: Record<string, unknown>
}

export interface AnalysisCancelApi {
  runId: string
  status: 'cancelled'
}

export interface ApartmentRunApi {
  runId: string
  status: string
  collectedAt: string
}

export interface ApartmentHistoryPointApi {
  runId: string
  status: string
  collectedAt: string
  saleCount: number
  jeonseCount: number
  monthlyCount: number
  addedCount: number
  removedCount: number
}

export interface ApartmentSummaryApi {
  apartmentId: string
  complexId: string
  complexName: string
  address: string
  sourceId: string
  sourceUrl: string
  latestRunId: string
  latestStatus: string
  collectedAt: string
  details: Record<string, unknown>
  listingCount: number
}

export interface ApartmentDetailApi extends ApartmentSummaryApi {
  availableRuns: ApartmentRunApi[]
  history: ApartmentHistoryPointApi[]
}

export interface ApartmentPageApi {
  items: ApartmentSummaryApi[]
  page: number
  pageSize: number
  total: number
}

export interface ListingAggregateApi {
  optionTags: string[]
  moveInSummary: string
  managementFeeSummary: string
  roomBathSummary: string
  loanSummary: string
  sourceCount: number
  warnings: string[]
}

export interface ListingSummaryApi {
  groupId: string
  runId: string
  tradeType: string
  price: number | null
  deposit: number | null
  monthlyRent: number | null
  previousPrice: number | null
  building: string | null
  floor: string | null
  direction: string | null
  supplyAreaM2: number | null
  exclusiveAreaM2: number | null
  status: string
  discoveredAt: string
  lastSeenAt: string
  removedAt: string | null
  capturedAt: string
  aggregate: ListingAggregateApi
}

export interface ListingAbsenceApi {
  groupId: string
  status: 'missing' | 'removed'
  lastSnapshot: ListingSummaryApi
  detectedAt: string
  removedAt: string | null
}

export interface ListingPageApi {
  complexId: string
  runId: string
  collectedAt: string
  items: ListingSummaryApi[]
  absentItems: ListingAbsenceApi[]
}

export interface RealtorApi {
  officeName?: string | null
  representativeName?: string | null
  phones?: string[] | null
  address?: string | null
  registrationNumber?: string | null
  ownerVerifiedListingCount?: number | null
  [key: string]: unknown
}

export interface BrokerRegistrationApi {
  articleId: string
  realtorName: string
  provider: string
  isNpay: boolean
  detailCollected: boolean
  articleUrl: string
  advertisedPrice: number | null
  pricePer3Point3M2: number | null
  managementFee: number | null
  loanDescription: string | null
  supplyAreaM2: number | null
  exclusiveAreaM2: number | null
  exclusiveRate: number | null
  floor: string | null
  roomCount: number | null
  bathroomCount: number | null
  direction: string | null
  structure: string | null
  moveInDate: string | null
  description: string
  optionTags: string[]
  firstPublishedAt: string | null
  realtor: RealtorApi | null
  extraFields: Record<string, unknown>
  dataWarnings: string[]
  firstSeenAt: string
  lastSeenAt: string
  capturedAt: string
  verifiedAt: string | null
  marketDetails: MarketDetailsApi | null
}

export interface MarketDetailsApi {
  finance: Record<string, unknown>
  transactions: Record<string, unknown>
  costs: Record<string, unknown>
  maintenance: Record<string, unknown>
  complex: Record<string, unknown>
  location: Record<string, unknown>
  extraFields: Record<string, unknown>
}

export interface ListingDetailApi extends ListingSummaryApi {
  apartmentId: string
  complexId: string
  complexName: string
  absenceDetectedAt: string | null
  registrations: BrokerRegistrationApi[]
  marketDetails: MarketDetailsApi | null
}

export interface DashboardResponseApi {
  sourceId: string
  sourceUrl: string
  runId: string
  collectedAt: string
  apartmentCount: number
  apartment: ApartmentDetailApi
  listings: ListingSummaryApi[]
}

export interface ScheduleApi {
  id: string
  sourceId: string
  sourceUrl: string
  cadence: ScheduleCadence
  timeOfDay: string
  timezone: string
  weekday: number | null
  enabled: boolean
  collectBrokerDetails: boolean
  interactionDelayPreset: InteractionDelayPresetApi
  nextRunAt: string
}

export interface ScheduleCreateApi {
  sourceId?: string
  sourceUrl?: string
  cadence: ScheduleCadence
  timeOfDay: string
  timezone?: 'Asia/Seoul'
  weekday?: number | null
  enabled?: boolean
  collectBrokerDetails: boolean
  interactionDelayPreset: InteractionDelayPresetApi
}

export interface SchedulePatchApi {
  cadence?: ScheduleCadence
  timeOfDay?: string
  timezone?: 'Asia/Seoul'
  weekday?: number | null
  enabled?: boolean
  collectBrokerDetails?: boolean
  interactionDelayPreset?: InteractionDelayPresetApi
}

export interface ScheduleRunApi {
  runId: string
  status: AnalysisRunStatus
  stage: AnalysisRunStage
  progress: number
  errorCode: string | null
  collectBrokerDetails: boolean
  interactionDelayPreset: InteractionDelayPresetApi
  createdAt: string
  startedAt: string | null
  finishedAt: string | null
}

export interface ScheduleRunsApi {
  scheduleId: string
  items: ScheduleRunApi[]
}

export interface ScheduleDeleteApi {
  id: string
  action: 'disabled' | 'deleted'
}

export interface NotificationLinkApi {
  sourceId: string
  complexId: string
  runId: string
  compareRunId: string | null
  focusListingId: string
}

export interface NotificationItemApi {
  id: string
  eventType: NotificationEventTypeApi
  title: string
  summary: Record<string, unknown>
  readAt: string | null
  createdAt: string
  link: NotificationLinkApi
}

export interface NotificationPageApi {
  items: NotificationItemApi[]
  nextCursor: string | null
}

export interface NotificationUnreadCountApi {
  count: number
}

export interface NotificationReadAllApi {
  updatedCount: number
}

export interface NotificationPreferenceApi {
  sourceId: string
  enabled: boolean
  notifyNew: boolean
  notifyChanged: boolean
  notifyRemoved: boolean
  notifyRestored: boolean
}

export type NotificationPreferencePatchApi = Omit<NotificationPreferenceApi, 'sourceId'>
