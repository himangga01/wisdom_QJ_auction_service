import {
  AlertTriangle,
  ArrowLeft,
  BadgeCheck,
  Building2,
  ChevronDown,
  CircleDollarSign,
  Clock3,
  ExternalLink,
  History,
  Landmark,
  MapPin,
  Phone,
  ReceiptText,
  Ruler,
  School,
  ShieldCheck,
  Train,
  Users,
  Wrench,
} from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { adaptApartmentDetail, adaptListingDetail } from '../adapters/realEstate'
import { apartmentKeys, getApartment, getListing } from '../api/apartments'
import { DatasetRequired } from '../components/analysis/DatasetRequired'
import { ChangeBadge } from '../components/research/ChangeBadge'
import { ListingAdditionalInfo } from '../components/research/ListingAdditionalInfo'
import { useAnalysis } from '../state/AnalysisProvider'
import { useDemoAnalysis } from '../state/DemoAnalysisContext'
import type { MarketDetailsApi } from '../types/api'
import type { BrokerRegistration } from '../types/realEstate'
import { formatArea, formatCollectedAt, formatListingPrice, formatKoreanPrice, tradeTypeLabels } from '../utils/formatters'

function formatWon(value: number): string {
  if (value >= 100_000_000) return formatKoreanPrice(value)
  return `${Math.round(value / 10_000).toLocaleString('ko-KR')}만원`
}

function DetailValue({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-slate-50 px-3.5 py-3">
      <dt className="text-[11px] font-bold text-slate-400">{label}</dt>
      <dd className="mt-1 text-sm font-extrabold text-slate-800">{value}</dd>
    </div>
  )
}

function structuredValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '-'
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value)
  if (Array.isArray(value)) return value.map(structuredValue).join(' · ') || '-'
  try {
    return JSON.stringify(value)
  } catch {
    return '-'
  }
}

function StructuredFields({ title, fields }: { title: string; fields: Record<string, unknown> }) {
  const entries = Object.entries(fields)
  if (!entries.length) return null
  return (
    <article className="rounded-3xl border border-slate-200 bg-white p-5 sm:p-6">
      <h2 className="text-lg font-black text-slate-950">{title}</h2>
      <dl className="mt-4 grid gap-2 sm:grid-cols-2">
        {entries.map(([key, value]) => <DetailValue key={key} label={key} value={structuredValue(value)} />)}
      </dl>
    </article>
  )
}

function ApiMarketDetails({ details }: { details: MarketDetailsApi }) {
  const sections: Array<[string, Record<string, unknown>]> = [
    ['대출·금융', details.finance],
    ['호가·실거래', details.transactions],
    ['거래 비용·세금', details.costs],
    ['관리비', details.maintenance],
    ['단지 상세', details.complex],
    ['생활권·교통·개발', details.location],
    ['기타 수집 필드', details.extraFields],
  ]
  return <section className="grid gap-4 xl:grid-cols-2">{sections.map(([title, fields]) => <StructuredFields key={title} title={title} fields={fields} />)}</section>
}

export function RegistrationCard({ registration }: { registration: BrokerRegistration }) {
  const details = [
    ['호가', registration.advertisedPrice ? formatKoreanPrice(registration.advertisedPrice) : '-'],
    ['3.3㎡당', registration.pricePer3Point3M2 ? formatWon(registration.pricePer3Point3M2) : '-'],
    ['관리비', registration.managementFee ? formatWon(registration.managementFee) : '-'],
    ['융자', registration.loanDescription ?? '-'],
    ['면적', registration.supplyAreaM2 && registration.exclusiveAreaM2 ? `공급 ${registration.supplyAreaM2}㎡ · 전용 ${registration.exclusiveAreaM2}㎡` : '-'],
    ['전용률', registration.exclusiveRate ? `${registration.exclusiveRate}%` : '-'],
    ['동·층', registration.floor ?? '-'],
    ['방·욕실', registration.roomCount && registration.bathroomCount ? `${registration.roomCount}개 · ${registration.bathroomCount}개` : '-'],
    ['방향·구조', [registration.direction, registration.structure].filter(Boolean).join(' · ') || '-'],
    ['입주 가능', registration.moveInDate ?? '-'],
    ['최초 게재', registration.firstPublishedAt ?? '-'],
    ['확인일', registration.verifiedAt],
  ]

  return (
    <article data-testid={`registration-${registration.articleId}`} className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
      <header className="border-b border-slate-100 bg-slate-50/70 p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-base font-black text-slate-950">{registration.realtorName}</h3>
              <span className="rounded-full bg-slate-200 px-2.5 py-1 text-[11px] font-extrabold text-slate-600">{registration.provider}</span>
              {registration.isNpay ? <span className="rounded-full bg-emerald-100 px-2.5 py-1 text-[11px] font-extrabold text-emerald-700">Npay 내부 상세</span> : null}
            </div>
            <p className="mt-1 text-xs font-bold text-slate-400">매물번호 {registration.articleId}</p>
          </div>
          <a href={registration.articleUrl} target="_blank" rel="noreferrer" className="inline-flex shrink-0 items-center gap-1.5 rounded-lg bg-slate-950 px-3 py-2 text-xs font-extrabold text-white hover:bg-emerald-700">
            {registration.isNpay ? 'Npay 상세 보기' : '원문 보기'} <ExternalLink size={13} />
          </a>
        </div>
      </header>

      <div className="space-y-5 p-5">
        <section>
          <p className="text-xs font-extrabold text-emerald-700">정제된 매물 소개</p>
          <p className="mt-2 text-sm leading-6 text-slate-700">{registration.description}</p>
          {registration.detailCollected && registration.optionTags?.length ? (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {registration.optionTags.map((tag) => <span key={tag} className="rounded-lg border border-emerald-100 bg-emerald-50 px-2.5 py-1.5 text-xs font-bold text-emerald-700">{tag}</span>)}
            </div>
          ) : null}
        </section>

        {registration.detailCollected ? (
          <>
            <dl className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
              {details.map(([label, value]) => <DetailValue key={label} label={label} value={value} />)}
            </dl>

            {registration.marketDetails ? <ApiMarketDetails details={registration.marketDetails} /> : null}

            {registration.dataWarnings?.map((warning) => (
              <div key={warning} className="flex gap-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs font-bold leading-5 text-amber-800">
                <AlertTriangle className="mt-0.5 shrink-0" size={15} /> {warning}
              </div>
            ))}

            {registration.extraFields && Object.keys(registration.extraFields).length ? (
              <section className="rounded-xl border border-slate-200 p-4">
                <h4 className="text-sm font-black text-slate-900">기타 수집 필드</h4>
                <dl className="mt-3 grid gap-2 sm:grid-cols-2">
                  {Object.entries(registration.extraFields).map(([key, value]) => <DetailValue key={key} label={key} value={structuredValue(value)} />)}
                </dl>
              </section>
            ) : null}

            {registration.realtor ? (
              <section className="rounded-xl border border-slate-200 p-4">
                <div className="flex items-center gap-2">
                  <BadgeCheck className="text-emerald-600" size={17} />
                  <h4 className="text-sm font-black text-slate-900">중개사 정보</h4>
                </div>
                <div className="mt-3 grid gap-3 text-xs sm:grid-cols-2">
                  <p className="text-slate-500"><strong className="block text-[11px] text-slate-400">대표자</strong><span className="mt-1 block font-extrabold text-slate-800">{registration.realtor.representativeName}</span></p>
                  <p className="text-slate-500"><strong className="block text-[11px] text-slate-400">등록번호</strong><span className="mt-1 block font-extrabold text-slate-800">{registration.realtor.registrationNumber}</span></p>
                  <p className="sm:col-span-2"><strong className="block text-[11px] text-slate-400">연락처</strong><span className="mt-1 flex flex-wrap gap-3 font-extrabold text-slate-800">{registration.realtor.phones.map((phone) => <span key={phone} className="inline-flex items-center gap-1"><Phone size={12} /> {phone}</span>)}</span></p>
                  <p className="sm:col-span-2"><strong className="block text-[11px] text-slate-400">주소</strong><span className="mt-1 block font-extrabold leading-5 text-slate-800">{registration.realtor.address}</span></p>
                  {registration.realtor.ownerVerifiedListingCount ? <p className="sm:col-span-2 text-slate-500">최근 3개월 집주인 확인 매물 <strong className="text-slate-900">{registration.realtor.ownerVerifiedListingCount.toLocaleString('ko-KR')}건</strong></p> : null}
                </div>
              </section>
            ) : null}
          </>
        ) : (
          <div className="flex gap-2 rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm font-bold leading-6 text-slate-600">
            <AlertTriangle className="mt-0.5 shrink-0 text-slate-400" size={17} />
            이 조사에서는 추가 상세정보를 수집하지 않았습니다.
          </div>
        )}
      </div>
    </article>
  )
}

export function ListingDetailPage() {
  const { complexId, listingId } = useParams()
  const [searchParams] = useSearchParams()
  const runId = searchParams.get('runId') ?? undefined
  const analysis = useAnalysis()
  const demo = useDemoAnalysis()
  const listingQuery = useQuery({
    queryKey: apartmentKeys.listing(listingId ?? '', runId),
    queryFn: () => getListing(listingId as string, runId),
    enabled: !analysis.isDemo && Boolean(listingId),
  })
  const apartmentQuery = useQuery({
    queryKey: apartmentKeys.detail(complexId ?? '', runId),
    queryFn: () => getApartment(complexId as string, runId),
    enabled: !analysis.isDemo && Boolean(complexId),
  })
  const demoApartment = demo.dataset?.apartments.find((item) => item.complexId === complexId)
  const demoListing = demoApartment?.listingGroups.find((item) => item.groupId === listingId)
  const realListing = listingQuery.data ? adaptListingDetail(listingQuery.data) : undefined
  const apartment = analysis.isDemo
    ? demoApartment
    : (apartmentQuery.data ? adaptApartmentDetail(apartmentQuery.data, realListing ? [realListing] : []) : undefined)
  const listing = analysis.isDemo ? demoListing : realListing

  if (analysis.isDemo && !demo.dataset) return <DatasetRequired />
  if (!analysis.isDemo && (listingQuery.isLoading || apartmentQuery.isLoading)) return <DatasetRequired isLoading />
  const queryError = listingQuery.error ?? apartmentQuery.error
  if (!analysis.isDemo && queryError) return <DatasetRequired error={queryError instanceof Error ? queryError.message : '매물 상세를 불러오지 못했습니다.'} />
  if (!apartment || !listing) return <div className="rounded-2xl border border-slate-200 bg-white p-10 text-center"><h1 className="text-xl font-black">매물을 찾을 수 없습니다</h1><Link to="/apartments" className="mt-4 inline-flex text-sm font-bold text-emerald-700">아파트 목록으로</Link></div>

  const market = analysis.isDemo ? listing.marketDetails : undefined
  const apiMarket = analysis.isDemo ? null : listingQuery.data?.marketDetails
  const hasDetailCollectedRegistration = listing.registrations.some((registration) => registration.detailCollected)
  const hasPerRegistrationMarket = listing.registrations.some((registration) => registration.detailCollected && Boolean(registration.marketDetails))
  const npayCount = listing.registrations.filter((registration) => registration.isNpay).length
  const apartmentFacts = [
    ['세대수', apartment.details.householdCount > 0 ? `${apartment.details.householdCount.toLocaleString('ko-KR')}세대` : '-'],
    ['동 수', apartment.details.buildingCount > 0 ? `${apartment.details.buildingCount.toLocaleString('ko-KR')}개동` : '-'],
    ['사용승인일', apartment.details.approvalDate ?? (apartment.details.completedYear > 0 ? `${apartment.details.completedYear}년` : '-')],
    ['총 주차대수', apartment.details.parkingCount ? `${apartment.details.parkingCount.toLocaleString('ko-KR')}대` : '-'],
    ['세대당 주차', apartment.details.parkingPerHousehold > 0 ? `${apartment.details.parkingPerHousehold}대` : '-'],
    ['난방방식', apartment.details.heating || '-'],
    ['현관구조', apartment.details.entranceType || '-'],
    ['용적률', apartment.details.floorAreaRatio ? `${apartment.details.floorAreaRatio}%` : '-'],
    ['건폐율', apartment.details.buildingCoverageRatio ? `${apartment.details.buildingCoverageRatio}%` : '-'],
    ['관리사무소 전화', apartment.details.managementOfficePhone || '-'],
    ['시공사', apartment.details.builders?.length ? apartment.details.builders.join(', ') : '-'],
  ]

  return (
    <div className="space-y-6">
      <div>
        <Link to={`/apartments/${apartment.complexId}`} className="inline-flex items-center gap-1.5 text-sm font-bold text-slate-500 hover:text-slate-900"><ArrowLeft size={16} /> {apartment.complexName}</Link>
        <div className="mt-5 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2"><ChangeBadge status={listing.status} /><span className="text-sm font-extrabold text-slate-500">{tradeTypeLabels[listing.tradeType]}</span><span className="rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-extrabold text-emerald-700">중개사 통합 매물</span></div>
            <h1 className={`mt-3 text-3xl font-black tracking-[-0.04em] ${
              listing.status === 'removed'
                ? 'text-rose-700 line-through'
                : listing.status === 'missing'
                  ? 'text-sky-800'
                  : 'text-slate-950'
            }`}>{listing.building} · {formatListingPrice(listing)}</h1>
            <p className="mt-2 text-sm text-slate-500">{formatArea(listing)} · {listing.floor} · {listing.direction}</p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white px-5 py-4">
            <p className="flex items-center gap-1.5 text-xs font-bold text-slate-400"><Clock3 size={14} /> 마지막 확인 시각</p>
            <p className="mt-1 font-black text-slate-900">{formatCollectedAt(listing.lastSeenAt)}</p>
          </div>
        </div>
      </div>

      {listing.status === 'removed' ? (
        <section className="rounded-2xl border border-rose-200 bg-rose-50 p-5">
          <h2 className="font-black text-rose-800">이 매물은 삭제 상태로 확인되었습니다</h2>
          <p className="mt-1 text-sm text-rose-700">마지막 노출: {formatCollectedAt(listing.lastSeenAt)} · 삭제 확인: {listing.removedAt ? formatCollectedAt(listing.removedAt) : '-'}</p>
        </section>
      ) : null}

      {listing.status === 'missing' ? (
        <section className="rounded-2xl border border-sky-200 bg-sky-50 p-5">
          <h2 className="font-black text-sky-800">선택한 조사에서 일시 미노출된 매물입니다</h2>
          <p className="mt-1 text-sm leading-6 text-sky-700">
            1회 미관측 상태로 아직 삭제로 확정하지 않습니다. 마지막 노출: {formatCollectedAt(listing.lastSeenAt)}
            {' · '}일시 미노출 확인: {listing.absenceDetectedAt ? formatCollectedAt(listing.absenceDetectedAt) : '-'}
          </p>
        </section>
      ) : null}

      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <article className="rounded-2xl border border-slate-200 bg-white p-5"><p className="flex items-center gap-2 text-xs font-bold text-slate-400"><Building2 size={15} /> 동·층</p><p className="mt-2 font-black text-slate-900">{listing.building} · {listing.floor}</p></article>
        <article className="rounded-2xl border border-slate-200 bg-white p-5"><p className="flex items-center gap-2 text-xs font-bold text-slate-400"><CircleDollarSign size={15} /> {listing.status === 'missing' || listing.status === 'removed' ? '마지막 호가' : '현재 호가'}</p><p className="mt-2 font-black text-slate-900">{formatListingPrice(listing)}</p>{listing.previousPrice ? <p className="mt-1 text-xs text-amber-600 line-through">이전 {formatKoreanPrice(listing.previousPrice)}</p> : null}</article>
        <article className="rounded-2xl border border-slate-200 bg-white p-5"><p className="flex items-center gap-2 text-xs font-bold text-slate-400"><Ruler size={15} /> 면적</p><p className="mt-2 font-black text-slate-900">전용 {listing.exclusiveAreaM2}㎡</p><p className="mt-1 text-xs text-slate-400">공급 {listing.supplyAreaM2}㎡</p></article>
        <article className="rounded-2xl border border-slate-200 bg-white p-5"><p className="flex items-center gap-2 text-xs font-bold text-slate-400"><History size={15} /> 최초 발견</p><p className="mt-2 font-black text-slate-900">{formatCollectedAt(listing.discoveredAt)}</p></article>
      </section>

      <ListingAdditionalInfo listing={listing} />

      <details className="group overflow-hidden rounded-3xl border border-slate-200 bg-white">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-4 p-5 outline-none focus-visible:ring-4 focus-visible:ring-inset focus-visible:ring-emerald-100 sm:p-6">
          <h2 className="flex items-center gap-2 text-lg font-black text-slate-950"><Building2 size={19} className="text-emerald-600" /> 단지 기본정보 전체 보기</h2>
          <span className="inline-flex items-center gap-1.5 text-xs font-extrabold text-slate-500">
            <span className="group-open:hidden">펼치기</span>
            <span className="hidden group-open:inline">접기</span>
            <ChevronDown className="transition-transform group-open:rotate-180" size={15} />
          </span>
        </summary>
        <dl className="grid gap-2 border-t border-slate-100 p-5 sm:grid-cols-2 sm:p-6 xl:grid-cols-3">
          {apartmentFacts.map(([label, value]) => <DetailValue key={label} label={label} value={value} />)}
        </dl>
      </details>

      <details className="group overflow-hidden rounded-3xl border border-slate-200 bg-white">
        <summary className="flex cursor-pointer list-none flex-wrap items-center justify-between gap-4 p-5 outline-none focus-visible:ring-4 focus-visible:ring-inset focus-visible:ring-emerald-100 sm:p-6">
          <div>
            <p className="text-sm font-extrabold text-emerald-700">중복 등록을 하나의 매물로 통합</p>
            <h2 className="mt-1 flex items-center gap-2 text-xl font-black text-slate-950"><Users size={20} /> 중개사 {listing.registrations.length}곳에서 등록했어요</h2>
            <p className="mt-1 text-sm text-slate-500">클릭하면 중개사별 가격, 관리비, 입주 조건과 옵션이 펼쳐집니다.</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {npayCount ? <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-3 py-2 text-xs font-extrabold text-emerald-700"><ShieldCheck size={14} /> Npay {npayCount}건</span> : null}
            <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-3 py-2 text-xs font-extrabold text-slate-600"><span className="group-open:hidden">상세 펼치기</span><span className="hidden group-open:inline">상세 접기</span> <ChevronDown className="transition-transform group-open:rotate-180" size={15} /></span>
          </div>
        </summary>
        <div className="border-t border-slate-100 p-5 sm:p-6">
          <div className="grid gap-4 xl:grid-cols-2">
            {listing.registrations.map((registration) => <RegistrationCard key={registration.articleId} registration={registration} />)}
          </div>
        </div>
      </details>

      {apiMarket && hasDetailCollectedRegistration && !hasPerRegistrationMarket ? <ApiMarketDetails details={apiMarket} /> : null}

      {market ? (
        <>
          <section className="grid gap-4 xl:grid-cols-2">
            <article className="rounded-3xl border border-slate-200 bg-white p-5 sm:p-6">
              <h2 className="flex items-center gap-2 text-lg font-black text-slate-950"><Landmark size={19} className="text-emerald-600" /> 대출·가격 지표</h2>
              <dl className="mt-4 grid gap-2 sm:grid-cols-2">
                <DetailValue label="대출 한도" value={`${formatKoreanPrice(market.loanLimit)} · LTV ${market.ltv}%`} />
                <DetailValue label="KB시세" value={formatKoreanPrice(market.kbMarketPrice)} />
                <DetailValue label="최저 금리" value={`${market.lowestMortgageRate}%`} />
                <DetailValue label="예상 월 원리금" value={`${market.estimatedMonthlyRepayment.toLocaleString('ko-KR')}원`} />
                <DetailValue label="동일면적 호가" value={`${market.sameAreaAskingRange} · ${market.sameAreaListingCount}건`} />
                <DetailValue label="매매·전세 갭" value={`${formatKoreanPrice(market.priceGap)} · 매매 ${formatKoreanPrice(market.averageSalePrice)} / 전세 ${formatKoreanPrice(market.averageJeonsePrice)}`} />
              </dl>
            </article>
            <article className="rounded-3xl border border-slate-200 bg-white p-5 sm:p-6">
              <h2 className="flex items-center gap-2 text-lg font-black text-slate-950"><CircleDollarSign size={19} className="text-emerald-600" /> 실거래가</h2>
              <div className="mt-4 grid grid-cols-2 gap-2"><DetailValue label="2년 내 최고" value={formatKoreanPrice(market.twoYearHigh)} /><DetailValue label="2년 내 최저" value={formatKoreanPrice(market.twoYearLow)} /></div>
              <div className="mt-3 divide-y divide-slate-100 rounded-xl border border-slate-200">
                {market.recentTransactions.map((transaction) => <div key={`${transaction.contractDate}-${transaction.floor}`} className="flex items-center justify-between gap-3 px-4 py-3 text-sm"><span className="font-bold text-slate-500">{transaction.contractDate} · {transaction.floor}</span><strong className="text-slate-900">{formatKoreanPrice(transaction.price)}</strong></div>)}
              </div>
            </article>
          </section>

          <section className="grid gap-4 lg:grid-cols-2">
            <article className="rounded-3xl border border-slate-200 bg-white p-5">
              <h2 className="flex items-center gap-2 font-black text-slate-950"><ReceiptText size={18} className="text-emerald-600" /> 거래 비용·세금</h2>
              <dl className="mt-4 space-y-2"><DetailValue label="중개보수" value={`최대 ${formatWon(market.brokerageFee)} · 상한 ${market.brokerageRate}%`} /><DetailValue label="취득세" value={`약 ${formatWon(market.acquisitionTax)}`} /><DetailValue label="재산세" value={`약 ${formatWon(market.propertyTax)}`} /><DetailValue label="종합부동산세" value={market.comprehensiveTax} /></dl>
            </article>
            <article className="rounded-3xl border border-slate-200 bg-white p-5">
              <h2 className="flex items-center gap-2 font-black text-slate-950"><Wrench size={18} className="text-emerald-600" /> 관리비 이력</h2>
              <dl className="mt-4 space-y-2"><DetailValue label={market.maintenance.referenceMonth} value={`${market.maintenance.referenceAmount.toLocaleString('ko-KR')}원`} /><DetailValue label="월 평균" value={`${market.maintenance.monthlyAverage.toLocaleString('ko-KR')}원`} /><DetailValue label="여름 평균" value={`${market.maintenance.summerAverage.toLocaleString('ko-KR')}원`} /><DetailValue label="겨울 평균" value={`${market.maintenance.winterAverage.toLocaleString('ko-KR')}원`} /></dl>
            </article>
          </section>

          <section className="rounded-3xl border border-slate-200 bg-white p-5 sm:p-6">
            <h2 className="flex items-center gap-2 text-lg font-black text-slate-950"><MapPin size={19} className="text-emerald-600" /> 생활권·교통·개발</h2>
            <div className="mt-4 grid gap-3 md:grid-cols-3">
              <div className="rounded-2xl bg-slate-50 p-4"><p className="flex items-center gap-2 text-xs font-extrabold text-slate-400"><Train size={15} /> 교통</p><p className="mt-2 text-sm font-bold leading-6 text-slate-800">{market.subway}</p><div className="mt-2 space-y-1 text-xs leading-5 text-slate-500">{market.buses.map((bus) => <p key={bus}>{bus}</p>)}</div></div>
              <div className="rounded-2xl bg-slate-50 p-4"><p className="flex items-center gap-2 text-xs font-extrabold text-slate-400"><School size={15} /> 배정 학교</p><p className="mt-2 text-sm font-bold leading-6 text-slate-800">{market.elementarySchool}</p></div>
              <div className="rounded-2xl bg-slate-50 p-4"><p className="flex items-center gap-2 text-xs font-extrabold text-slate-400"><MapPin size={15} /> 개발 예정</p><p className="mt-2 text-sm font-bold leading-6 text-slate-800">{market.development}</p></div>
            </div>
          </section>
        </>
      ) : null}
    </div>
  )
}
