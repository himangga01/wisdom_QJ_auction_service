import * as XLSX from 'xlsx'
import type { DashboardDataset } from '../types/realEstate'
import { getApartmentMetrics } from './dashboard'
import { formatListingPrice, formatKoreanPrice, listingStatusLabels, tradeTypeLabels } from './formatters'
import { aggregateListingAdditionalInfo } from './listingAdditionalInfo'

function stringifyJson(value: Record<string, unknown> | undefined): string {
  if (!value || Object.keys(value).length === 0) return ''
  return JSON.stringify(value)
}

export function buildDashboardWorkbook(dataset: DashboardDataset): XLSX.WorkBook {
  const apartmentRows = dataset.apartments.map((apartment) => {
    const metrics = getApartmentMetrics(apartment)
    return {
      단지ID: apartment.complexId,
      아파트명: apartment.complexName,
      주소: apartment.address,
      조사일시: dataset.collectedAt,
      현재매물수: metrics.groupCount,
      신규매물수: metrics.newCount,
      변경매물수: metrics.changedCount,
      삭제매물수: metrics.removedCount,
      중개사등록수: metrics.registrationCount,
      매매최저가: formatKoreanPrice(metrics.minPrice),
      매매최고가: formatKoreanPrice(metrics.maxPrice),
    }
  })

  const listingRows = dataset.apartments.flatMap((apartment) =>
    apartment.listingGroups.map((group) => {
      const additionalInformation = aggregateListingAdditionalInfo(group)
      return {
        단지ID: apartment.complexId,
        아파트명: apartment.complexName,
        대표매물ID: group.groupId,
        거래유형: tradeTypeLabels[group.tradeType],
        변경상태: listingStatusLabels[group.status],
        동: group.building,
        가격원: group.price,
        가격표시: formatListingPrice(group),
        월세원: group.monthlyRent ?? '',
        이전가격원: group.previousPrice ?? '',
        '공급면적㎡': group.supplyAreaM2,
        '전용면적㎡': group.exclusiveAreaM2,
        층: group.floor,
        방향: group.direction,
        중개사등록수: group.registrations.length,
        추가정보옵션: additionalInformation.optionTags.join(', '),
        입주가능일요약: additionalInformation.moveInSummary,
        관리비요약: additionalInformation.managementFeeSummary,
        방욕실요약: additionalInformation.roomBathroomSummary,
        융자요약: additionalInformation.loanSummary,
        상세정보주의건수: additionalInformation.warningCount,
        최초발견일시: group.discoveredAt,
        마지막확인일시: group.lastSeenAt,
        삭제확인일시: group.removedAt ?? '',
      }
    }),
  )

  const brokerRows = dataset.apartments.flatMap((apartment) =>
    apartment.listingGroups.flatMap((group) =>
      group.registrations.map((item) => {
        const marketDetails = item.detailCollected ? item.marketDetails : undefined
        return {
        단지ID: apartment.complexId,
        아파트명: apartment.complexName,
        대표매물ID: group.groupId,
        거래유형: tradeTypeLabels[group.tradeType],
        변경상태: listingStatusLabels[group.status],
        매물ID: item.articleId,
        동: group.building,
        가격표시: formatListingPrice(group),
        중개사명: item.realtorName,
        제공업체: item.provider,
        Npay내부상세: item.isNpay ? 'Y' : 'N',
        추가상세수집여부: item.detailCollected ? 'Y' : 'N',
        최초게재일: item.firstPublishedAt ?? '',
        확인일: item.verifiedAt,
        호가원: item.advertisedPrice ?? group.price,
        '3.3㎡당가격원': item.pricePer3Point3M2 ?? '',
        관리비원: item.managementFee ?? '',
        융자정보: item.loanDescription ?? '',
        '공급면적㎡': item.supplyAreaM2 ?? group.supplyAreaM2,
        '전용면적㎡': item.exclusiveAreaM2 ?? group.exclusiveAreaM2,
        전용률: item.exclusiveRate ?? '',
        층: item.floor ?? group.floor,
        방수: item.roomCount ?? '',
        욕실수: item.bathroomCount ?? '',
        방향: item.direction ?? group.direction,
        구조: item.structure ?? '',
        입주가능일: item.moveInDate ?? '',
        옵션: item.optionTags?.join(', ') ?? '',
        설명: item.description,
        대표자: item.realtor?.representativeName ?? '',
        중개사연락처: item.realtor?.phones.join(', ') ?? '',
        중개사주소: item.realtor?.address ?? '',
        중개사등록번호: item.realtor?.registrationNumber ?? '',
        최근3개월집주인확인수: item.realtor?.ownerVerifiedListingCount ?? '',
        확인필요사항: item.dataWarnings?.join(' / ') ?? '',
        상세URL: item.articleUrl,
        물건별금융JSON: stringifyJson(marketDetails?.finance),
        물건별실거래JSON: stringifyJson(marketDetails?.transactions),
        물건별비용세금JSON: stringifyJson(marketDetails?.costs),
        물건별관리비JSON: stringifyJson(marketDetails?.maintenance),
        물건별단지JSON: stringifyJson(marketDetails?.complex),
        물건별입지교통JSON: stringifyJson(marketDetails?.location),
        물건별추가필드JSON: stringifyJson(marketDetails?.extraFields),
      }
      }),
    ),
  )

  const marketRows = dataset.apartments.flatMap((apartment) =>
    apartment.listingGroups.flatMap((group) => {
      const detail = group.marketDetails
      if (!detail) return []
      return [{
        단지ID: apartment.complexId,
        아파트명: apartment.complexName,
        대표매물ID: group.groupId,
        대출한도원: detail.loanLimit,
        LTV: detail.ltv,
        KB시세원: detail.kbMarketPrice,
        최저금리: detail.lowestMortgageRate,
        예상월원리금원: detail.estimatedMonthlyRepayment,
        동일면적호가범위: detail.sameAreaAskingRange,
        동일면적매물수: detail.sameAreaListingCount,
        평균매매가원: detail.averageSalePrice,
        평균전세가원: detail.averageJeonsePrice,
        매매전세갭원: detail.priceGap,
        이년최고가원: detail.twoYearHigh,
        이년최저가원: detail.twoYearLow,
        최근실거래: detail.recentTransactions.map((item) => `${item.contractDate} ${item.floor} ${formatKoreanPrice(item.price)}`).join(' / '),
        중개보수원: detail.brokerageFee,
        중개보수상한율: detail.brokerageRate,
        취득세원: detail.acquisitionTax,
        재산세원: detail.propertyTax,
        종합부동산세: detail.comprehensiveTax,
        기준월관리비원: detail.maintenance.referenceAmount,
        월평균관리비원: detail.maintenance.monthlyAverage,
        여름평균관리비원: detail.maintenance.summerAverage,
        겨울평균관리비원: detail.maintenance.winterAverage,
        개발예정: detail.development,
        배정초등학교: detail.elementarySchool,
        지하철: detail.subway,
        버스: detail.buses.join(' / '),
      }]
    }),
  )

  const historyRows = dataset.apartments.flatMap((apartment) =>
    apartment.history.map((point) => ({
      단지ID: apartment.complexId,
      아파트명: apartment.complexName,
      조사일시: point.collectedAt,
      매매수: point.saleCount,
      전세수: point.jeonseCount,
      월세수: point.monthlyCount,
      신규수: point.addedCount,
      삭제수: point.removedCount,
    })),
  )

  const workbook = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet(apartmentRows), '아파트요약')
  XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet(listingRows), '매물현황')
  XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet(brokerRows), '중개사등록')
  XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet(marketRows), '상세지표')
  XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet(historyRows), '조사이력')

  workbook.Sheets['아파트요약']['!cols'] = Array(11).fill({ wch: 18 })
  workbook.Sheets['매물현황']['!cols'] = Array(24).fill({ wch: 18 })
  workbook.Sheets['중개사등록']['!cols'] = Array(42).fill({ wch: 20 })
  workbook.Sheets['상세지표']['!cols'] = Array(29).fill({ wch: 20 })
  workbook.Sheets['조사이력']['!cols'] = Array(8).fill({ wch: 18 })
  return workbook
}

export function downloadDashboardWorkbook(dataset: DashboardDataset): void {
  const date = dataset.collectedAt.slice(0, 10).replaceAll('-', '')
  XLSX.writeFile(buildDashboardWorkbook(dataset), `naver-land-research-${date}.xlsx`)
}
