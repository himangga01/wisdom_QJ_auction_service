import { useEffect, useRef, useState } from 'react'
import { demoDashboardDataset } from '../mocks/demoRealEstate'
import type { CrawlStatus, DashboardDataset } from '../types/realEstate'
import type {
  AnalysisCreateApi,
  InteractionDelayPresetApi,
} from '../types/api'

export const DEMO_STEPS = [
  'URL 확인',
  '매물 목록 구성',
  '중개사 등록 정리',
  '대시보드 생성',
] as const

export function isValidNaverLandUrl(value: string): boolean {
  try {
    const url = new URL(value)
    return url.protocol === 'https:' && url.hostname === 'fin.land.naver.com'
  } catch {
    return false
  }
}

function createDemoDataset(sourceUrl: string, collectBrokerDetails: boolean): DashboardDataset {
  const clonedDataset = structuredClone(demoDashboardDataset)
  return {
    ...clonedDataset,
    sourceUrl,
    apartments: clonedDataset.apartments.map((apartment) => ({
      ...apartment,
      listingGroups: apartment.listingGroups.map((group) => ({
        ...group,
        marketDetails: collectBrokerDetails ? group.marketDetails : undefined,
        registrations: group.registrations.map((registration) => {
          if (collectBrokerDetails) {
            return {
              ...registration,
              detailCollected: true,
            }
          }
          return {
            articleId: registration.articleId,
            realtorName: registration.realtorName,
            provider: registration.provider,
            detailCollected: false,
            description: registration.description,
            verifiedAt: registration.verifiedAt,
            articleUrl: registration.articleUrl,
            isNpay: registration.isNpay,
            optionTags: [],
            dataWarnings: [],
            marketDetails: undefined,
          }
        }),
      })),
    })),
  }
}

export function useDemoDashboard() {
  const [status, setStatus] = useState<CrawlStatus>('idle')
  const [progressStep, setProgressStep] = useState(0)
  const [error, setError] = useState('')
  const [dataset, setDataset] = useState<DashboardDataset | null>(null)
  const [selectedApartmentId, setSelectedApartmentId] = useState('')
  const [interactionDelayPreset, setInteractionDelayPreset] =
    useState<InteractionDelayPresetApi>('normal')
  const timers = useRef<number[]>([])

  const clearTimers = () => {
    timers.current.forEach((timer) => window.clearTimeout(timer))
    timers.current = []
  }

  useEffect(() => clearTimers, [])

  const startDemoAnalysis = ({
    sourceUrl,
    collectBrokerDetails,
    interactionDelayPreset: requestedDelayPreset,
  }: AnalysisCreateApi) => {
    clearTimers()
    setInteractionDelayPreset(requestedDelayPreset)

    if (!isValidNaverLandUrl(sourceUrl)) {
      setError('네이버 부동산 URL을 입력해 주세요.')
      setStatus('failed')
      setDataset(null)
      return
    }

    setError('')
    setStatus('running')
    setProgressStep(0)
    setDataset(null)

    DEMO_STEPS.slice(1).forEach((_, index) => {
      const timer = window.setTimeout(() => {
        setProgressStep(index + 1)
      }, (index + 1) * 220)
      timers.current.push(timer)
    })

    const completionTimer = window.setTimeout(() => {
      setStatus('completed')
      setDataset(createDemoDataset(sourceUrl, collectBrokerDetails))
      setSelectedApartmentId(demoDashboardDataset.apartments[0].complexId)
    }, 900)
    timers.current.push(completionTimer)
  }

  return {
    status,
    progressStep,
    error,
    dataset,
    selectedApartmentId,
    interactionDelayPreset,
    setSelectedApartmentId,
    startDemoAnalysis,
  }
}
