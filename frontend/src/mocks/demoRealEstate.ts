import type {
  ApartmentSummary,
  BrokerRegistration,
  DashboardDataset,
  ListingGroup,
} from '../types/realEstate'

const realtorNames = [
  '아이파크캐슬공인중개사사무소',
  '병점역센트럴공인중개사사무소',
  '동탄한빛공인중개사사무소',
  '우리동네부동산공인중개사사무소',
  '롯데캐슬탑공인중개사사무소',
]

const providers = ['네이버부동산', '부동산R114', '매경부동산', '한국공인중개사협회']

const realtorProfiles = {
  top: {
    representativeName: '채선미',
    officeName: '탑아이파크캐슬공인중개사사무소',
    phones: ['031-235-5025', '010-7126-2441'],
    address: '경기 화성시 병점노을로 31 근린생활시설 1동 23호',
    registrationNumber: '41590-2021-10075',
    ownerVerifiedListingCount: 172,
  },
  topStation: {
    representativeName: '서영철',
    officeName: '탑병점역아이파크캐슬공인중개사사무소',
    phones: ['031-235-5025', '010-6450-2441'],
    address: '경기 화성시 병점노을로 31 병점역아이파크캐슬 상가',
    registrationNumber: '41590-2021-10060',
    ownerVerifiedListingCount: 122,
  },
  elephant: {
    representativeName: '김보미',
    officeName: '코끼리병점역IPARK캐슬공인중개사사무소',
    phones: ['031-233-7770', '010-5181-0578'],
    address: '경기 화성시 병점노을로 31 근린생활시설 1동 14호',
    registrationNumber: '41590-2021-10077',
    ownerVerifiedListingCount: 296,
  },
  lucky: {
    representativeName: '양혜정',
    officeName: '럭키아이파크캐슬공인중개사사무소',
    phones: ['031-236-9888', '010-4234-6843'],
    address: '경기 화성시 병점동 병점역아이파크캐슬 상가',
    registrationNumber: '41590-2018-10416',
    ownerVerifiedListingCount: 144,
  },
  first: {
    representativeName: '조형진',
    officeName: '일등아이파크캐슬공인중개사사무소',
    phones: ['031-236-1114', '010-4876-1114'],
    address: '경기 화성시 병점동 병점역아이파크캐슬 상가',
    registrationNumber: '41595-2026-00007',
    ownerVerifiedListingCount: 166,
  },
  stone: {
    representativeName: '석미영',
    officeName: '석아이파크캐슬공인중개사',
    phones: ['031-236-1112', '010-4944-6549'],
    address: '경기 화성시 병점구 병점동 881 근린생활시설 2동 2호',
    registrationNumber: '41590-2024-10012',
    ownerVerifiedListingCount: 154,
  },
  nest: {
    representativeName: '김영기',
    officeName: '병점역둥지공인중개사사무소',
    phones: ['031-231-1300', '010-2322-3432'],
    address: '경기 화성시 병점동 병점역아이파크캐슬 인근',
    registrationNumber: '41590-2024-10016',
    ownerVerifiedListingCount: 165,
  },
  complex: {
    representativeName: '박성기',
    officeName: '단지내병점역아이파크캐슬공인중개사사무소',
    phones: ['031-222-9955', '010-9900-3827'],
    address: '경기 화성시 병점노을로 31 상가 2동 101호',
    registrationNumber: '41590-2021-10061',
    ownerVerifiedListingCount: 103,
  },
  withJun: {
    representativeName: '김성원',
    officeName: '위드준카페부동산공인중개사사무소',
    phones: ['031-8043-0295', '010-4683-0295'],
    address: '경기 화성시 병점동 병점역아이파크캐슬 인근',
    registrationNumber: '41590-2025-20026',
    ownerVerifiedListingCount: 428,
  },
}

type ResearchedRegistrationInput = {
  articleId: string
  provider: string
  verifiedAt: string
  managementFee: number
  description: string
  optionTags: string[]
  realtor: (typeof realtorProfiles)[keyof typeof realtorProfiles]
  isNpay?: boolean
  moveInDate?: string
  loanDescription?: string
  dataWarnings?: string[]
}

function researched107Registration(input: ResearchedRegistrationInput): BrokerRegistration {
  return {
    articleId: input.articleId,
    realtorName: input.realtor.officeName,
    provider: input.provider,
    detailCollected: true,
    description: input.description,
    verifiedAt: input.verifiedAt,
    firstPublishedAt: input.verifiedAt,
    articleUrl: `https://fin.land.naver.com/articles/${input.articleId}`,
    isNpay: input.isNpay,
    advertisedPrice: 800_000_000,
    pricePer3Point3M2: 23_890_000,
    managementFee: input.managementFee,
    loanDescription: input.loanDescription ?? '상세 페이지에서 별도 표기 없음',
    supplyAreaM2: 110.68,
    exclusiveAreaM2: 84.98,
    exclusiveRate: 77,
    floor: '1/20층',
    roomCount: 3,
    bathroomCount: 2,
    direction: '남동향',
    structure: '단층',
    moveInDate: input.moveInDate ?? '즉시입주 협의',
    optionTags: input.optionTags,
    realtor: input.realtor,
    dataWarnings: input.dataWarnings,
  }
}

const researched107Registrations: BrokerRegistration[] = [
  researched107Registration({ articleId: '2639132873', provider: '아실', verifiedAt: '2026-07-21', managementFee: 290_000, description: '시스템에어컨 4대, 중문, 식기세척기, 미세방충망과 줄눈이 갖춰진 1층 매물입니다.', optionTags: ['시스템에어컨 4대', '중문', '식기세척기', '미세방충망', '줄눈'], realtor: realtorProfiles.top, isNpay: true }),
  researched107Registration({ articleId: '2639088577', provider: '부동산포스', verifiedAt: '2026-07-20', managementFee: 290_000, description: '시스템에어컨과 생활 옵션이 갖춰져 있으며 입주 일정은 협의할 수 있습니다.', optionTags: ['시스템에어컨 4대', '중문', '식기세척기', '미세방충망'], realtor: realtorProfiles.top }),
  researched107Registration({ articleId: '2638953132', provider: '이실장플러스', verifiedAt: '2026-07-20', managementFee: 250_000, description: '전자계약이 가능하고 시스템에어컨 4대와 식기세척기가 포함된 매물입니다.', optionTags: ['전자계약', '시스템에어컨 4대', '식기세척기'], realtor: realtorProfiles.elephant, loanDescription: '융자 없음' }),
  researched107Registration({ articleId: '2638915766', provider: '부동산렛츠', verifiedAt: '2026-07-20', managementFee: 300_000, description: '층간소음 부담이 적은 1층으로 중문, 식기세척기와 줄눈 시공이 확인됩니다.', optionTags: ['1층', '시스템에어컨 4대', '중문', '식기세척기', '줄눈'], realtor: realtorProfiles.lucky }),
  researched107Registration({ articleId: '2638768950', provider: '선방', verifiedAt: '2026-07-19', managementFee: 290_000, description: '시스템에어컨 4대와 식기세척기, 미세방충망이 포함된 매물입니다.', optionTags: ['시스템에어컨 4대', '중문', '식기세척기', '미세방충망'], realtor: realtorProfiles.topStation }),
  researched107Registration({ articleId: '2638686620', provider: '부동산뱅크', verifiedAt: '2026-07-18', managementFee: 250_000, description: '융자가 없고 전자계약이 가능한 1층 매물로 입주 일정 협의가 가능합니다.', optionTags: ['전자계약', '시스템에어컨 4대', '식기세척기'], realtor: realtorProfiles.elephant, loanDescription: '융자 없음' }),
  researched107Registration({ articleId: '2638552383', provider: '부동산포스', verifiedAt: '2026-07-17', managementFee: 250_000, description: '전자계약과 입주 협의가 가능하며 주요 생활 옵션이 포함되어 있습니다.', optionTags: ['전자계약', '시스템에어컨 4대', '식기세척기'], realtor: realtorProfiles.elephant, loanDescription: '융자 없음' }),
  researched107Registration({ articleId: '2638246829', provider: '부동산써브', verifiedAt: '2026-07-16', managementFee: 290_000, description: '아이와 생활하기 편한 1층이며 병점역과 가까운 동에 위치합니다.', optionTags: ['1층', '시스템에어컨 4대', '병점역 인접'], realtor: realtorProfiles.first }),
  researched107Registration({ articleId: '2638189562', provider: '알터', verifiedAt: '2026-07-15', managementFee: 280_000, description: '시스템에어컨 4대, 식기세척기, 중문, 미세방충망과 줄눈이 확인된 즉시입주 매물입니다.', optionTags: ['시스템에어컨 4대', '식기세척기', '중문', '미세방충망', '줄눈', '전자계약'], realtor: realtorProfiles.stone, moveInDate: '즉시입주' }),
  researched107Registration({ articleId: '2637706750', provider: '알터', verifiedAt: '2026-07-13', managementFee: 300_000, description: '주차가 편리한 동이며 트인 전망과 병점역 접근성이 장점입니다.', optionTags: ['시스템에어컨 3대', '중문', '트인 전망', '주차 편리'], realtor: realtorProfiles.lucky }),
  researched107Registration({ articleId: '2638321896', provider: '부동산뱅크', verifiedAt: '2026-07-16', managementFee: 260_000, description: '병점역과 가까운 로열동으로 전망이 좋고 주인 세대가 관리한 매물입니다.', optionTags: ['시스템에어컨 4대', '중문', '줄눈', '식기세척기', '주인거주'], realtor: realtorProfiles.nest, moveInDate: '2026-01-31 협의', dataWarnings: ['표시 호가는 8억원이지만 중개사 소개문에는 7억3천만원으로 기재되어 확인이 필요합니다.'] }),
  researched107Registration({ articleId: '2636024250', provider: '부동산포스', verifiedAt: '2026-07-04', managementFee: 280_000, description: '즉시입주가 가능한 1층 매물로 중문, 식기세척기와 미세방충망이 포함됩니다.', optionTags: ['1층', '시스템에어컨 4대', '중문', '식기세척기', '미세방충망'], realtor: realtorProfiles.stone, moveInDate: '즉시입주' }),
  researched107Registration({ articleId: '2636099471', provider: '부동산뱅크', verifiedAt: '2026-07-04', managementFee: 300_000, description: '병점역과 가까운 동의 주인거주 매물로 전자계약과 입주 협의가 가능합니다.', optionTags: ['시스템에어컨 4대', '중문', '미세방충망', '주인거주', '전자계약'], realtor: realtorProfiles.complex }),
  researched107Registration({ articleId: '2637277033', provider: '매경부동산', verifiedAt: '2026-07-10', managementFee: 330_000, description: '주인이 깨끗하게 거주한 선호동 1층 매물로 희소성이 있는 조건입니다.', optionTags: ['1층', '시스템에어컨 4대', '중문', '냉장고장', '주인거주'], realtor: realtorProfiles.withJun }),
  researched107Registration({ articleId: '2634111934', provider: '아실', verifiedAt: '2026-06-25', managementFee: 300_000, description: '병점역과 가까운 동에 위치하며 즉시입주와 전자계약이 가능한 주인거주 매물입니다.', optionTags: ['시스템에어컨 4대', '중문', '미세방충망', '주인거주', '전자계약'], realtor: realtorProfiles.complex, isNpay: true, moveInDate: '즉시입주' }),
]

const researched107MarketDetails = {
  loanLimit: 547_750_000,
  ltv: 70,
  kbMarketPrice: 782_500_000,
  lowestMortgageRate: 3.409,
  estimatedMonthlyRepayment: 2_431_903,
  sameAreaAskingRange: '8억 ~ 8억 1,900만원',
  sameAreaListingCount: 15,
  averageSalePrice: 715_000_000,
  averageJeonsePrice: 385_000_000,
  priceGap: 330_000_000,
  twoYearHigh: 850_000_000,
  twoYearLow: 590_000_000,
  recentTransactions: [
    { contractDate: '2026-07-18', floor: '17층', price: 849_000_000 },
    { contractDate: '2026-07-13', floor: '6층', price: 850_000_000 },
    { contractDate: '2026-07-11', floor: '2층', price: 700_000_000 },
  ],
  brokerageFee: 3_200_000,
  brokerageRate: 0.4,
  acquisitionTax: 20_240_000,
  propertyTax: 420_000,
  comprehensiveTax: '과세대상 아님',
  maintenance: {
    referenceMonth: '2026-05',
    referenceAmount: 235_541,
    monthlyAverage: 283_400,
    summerAverage: 276_030,
    winterAverage: 342_531,
  },
  development: '동탄도시철도 병점역 2027년 개통 예정 · 648m, 도보 약 10분',
  elementarySchool: '새봄초등학교(공립) · 약 599m, 도보 8분 · 전체동 배정',
  subway: '수도권 1호선 병점역 · 약 601m, 도보 12분',
  buses: ['일반 1000·200·205·206·220·34·46·720-3·H2', '마을 12·13A·17·38·55·56·H20', '직행좌석 1551·1551B'],
}

function makeRegistrations(prefix: string, count: number, verifiedAt: string): BrokerRegistration[] {
  return Array.from({ length: count }, (_, index) => {
    const articleId = `${prefix}${String(index + 1).padStart(2, '0')}`
    return {
      articleId,
      realtorName: realtorNames[index % realtorNames.length],
      provider: providers[index % providers.length],
      detailCollected: true,
      verifiedAt,
      description: index % 2 === 0 ? '채광과 통풍이 좋고 입주 일정 협의 가능합니다.' : '단지 중심부에 위치한 관리 상태 좋은 매물입니다.',
      articleUrl: `https://fin.land.naver.com/articles/${articleId}`,
    }
  })
}

function listing(
  group: Omit<ListingGroup, 'registrations'>,
  registrationCount: number,
  registrations?: BrokerRegistration[],
): ListingGroup {
  return {
    ...group,
    registrations: registrations ?? makeRegistrations(group.groupId.replaceAll('-', ''), registrationCount, group.lastSeenAt.slice(0, 10)),
  }
}

const apartments: ApartmentSummary[] = [
  {
    complexId: '124735',
    complexName: '병점역아이파크캐슬',
    address: '경기도 화성시 병점동 881',
    details: {
      householdCount: 2666,
      buildingCount: 27,
      completedYear: 2021,
      parkingPerHousehold: 1.3,
      heating: '지역난방 / 열병합',
      approvalDate: '2021-03-30',
      parkingCount: 3466,
      entranceType: '계단식',
      floorAreaRatio: 196,
      buildingCoverageRatio: 15,
      managementOfficePhone: '031-267-0597',
      builders: ['현대산업개발(주)', '롯데건설(주)'],
    },
    history: [
      { collectedAt: '2026-07-18T09:00:00+09:00', saleCount: 2, jeonseCount: 1, monthlyCount: 1, addedCount: 0, removedCount: 0 },
      { collectedAt: '2026-07-19T09:00:00+09:00', saleCount: 3, jeonseCount: 1, monthlyCount: 1, addedCount: 1, removedCount: 0 },
      { collectedAt: '2026-07-20T09:00:00+09:00', saleCount: 3, jeonseCount: 2, monthlyCount: 1, addedCount: 1, removedCount: 0 },
      { collectedAt: '2026-07-22T09:40:00+09:00', saleCount: 3, jeonseCount: 2, monthlyCount: 1, addedCount: 2, removedCount: 1 },
    ],
    listingGroups: [
      listing({
        groupId: '124735-sale-107', building: '107동', tradeType: 'sale', price: 800_000_000,
        supplyAreaM2: 110.68, exclusiveAreaM2: 84.98, floor: '1/20층', direction: '남동향', status: 'active',
        discoveredAt: '2026-06-25T11:20:00+09:00', lastSeenAt: '2026-07-22T09:40:00+09:00',
        marketDetails: researched107MarketDetails,
      }, 15, researched107Registrations),
      listing({
        groupId: '124735-sale-101', building: '101동', tradeType: 'sale', price: 698_000_000, previousPrice: 720_000_000,
        supplyAreaM2: 100, exclusiveAreaM2: 75.99, floor: '1/13층', direction: '남동향', status: 'changed',
        discoveredAt: '2026-07-04T10:10:00+09:00', lastSeenAt: '2026-07-22T09:40:00+09:00',
      }, 2),
      listing({
        groupId: '124735-sale-112', building: '112동', tradeType: 'sale', price: 920_000_000,
        supplyAreaM2: 110, exclusiveAreaM2: 84.98, floor: '20/23층', direction: '남동향', status: 'new',
        discoveredAt: '2026-07-22T09:40:00+09:00', lastSeenAt: '2026-07-22T09:40:00+09:00',
      }, 1),
      listing({
        groupId: '124735-sale-118', building: '118동', tradeType: 'sale', price: 760_000_000,
        supplyAreaM2: 79, exclusiveAreaM2: 59.89, floor: '15/22층', direction: '남동향', status: 'removed',
        discoveredAt: '2026-06-29T15:30:00+09:00', lastSeenAt: '2026-07-20T09:00:00+09:00', removedAt: '2026-07-22T09:40:00+09:00',
      }, 2),
      listing({
        groupId: '124735-jeonse-106', building: '106동', tradeType: 'jeonse', price: 430_000_000,
        supplyAreaM2: 110, exclusiveAreaM2: 84.98, floor: '9/20층', direction: '남향', status: 'active',
        discoveredAt: '2026-07-11T14:00:00+09:00', lastSeenAt: '2026-07-22T09:40:00+09:00',
      }, 3),
      listing({
        groupId: '124735-jeonse-109', building: '109동', tradeType: 'jeonse', price: 450_000_000,
        supplyAreaM2: 110, exclusiveAreaM2: 84.98, floor: '14/21층', direction: '남동향', status: 'new',
        discoveredAt: '2026-07-22T09:40:00+09:00', lastSeenAt: '2026-07-22T09:40:00+09:00',
      }, 2),
      listing({
        groupId: '124735-monthly-120', building: '120동', tradeType: 'monthly', price: 50_000_000, monthlyRent: 1_500_000,
        supplyAreaM2: 79, exclusiveAreaM2: 59.89, floor: '7/22층', direction: '남서향', status: 'active',
        discoveredAt: '2026-07-18T09:00:00+09:00', lastSeenAt: '2026-07-22T09:40:00+09:00',
      }, 2),
    ],
  },
  {
    complexId: '128004',
    complexName: '동탄역롯데캐슬',
    address: '경기도 화성시 오산동 1089',
    details: {
      householdCount: 940,
      buildingCount: 6,
      completedYear: 2021,
      parkingPerHousehold: 1.52,
      heating: '지역난방',
    },
    history: [
      { collectedAt: '2026-07-18T09:06:00+09:00', saleCount: 2, jeonseCount: 1, monthlyCount: 0, addedCount: 0, removedCount: 0 },
      { collectedAt: '2026-07-19T09:05:00+09:00', saleCount: 2, jeonseCount: 1, monthlyCount: 1, addedCount: 1, removedCount: 0 },
      { collectedAt: '2026-07-20T09:04:00+09:00', saleCount: 3, jeonseCount: 1, monthlyCount: 1, addedCount: 1, removedCount: 0 },
      { collectedAt: '2026-07-22T09:44:00+09:00', saleCount: 3, jeonseCount: 1, monthlyCount: 1, addedCount: 0, removedCount: 1 },
    ],
    listingGroups: [
      listing({
        groupId: '128004-sale-101', building: '101동', tradeType: 'sale', price: 1_620_000_000,
        supplyAreaM2: 109, exclusiveAreaM2: 84.7, floor: '31/49층', direction: '남향', status: 'active',
        discoveredAt: '2026-07-02T12:00:00+09:00', lastSeenAt: '2026-07-22T09:44:00+09:00',
      }, 5),
      listing({
        groupId: '128004-sale-104', building: '104동', tradeType: 'sale', price: 1_780_000_000, previousPrice: 1_820_000_000,
        supplyAreaM2: 132, exclusiveAreaM2: 102.3, floor: '38/49층', direction: '남서향', status: 'changed',
        discoveredAt: '2026-06-30T16:00:00+09:00', lastSeenAt: '2026-07-22T09:44:00+09:00',
      }, 3),
      listing({
        groupId: '128004-sale-105', building: '105동', tradeType: 'sale', price: 1_540_000_000,
        supplyAreaM2: 109, exclusiveAreaM2: 84.7, floor: '19/46층', direction: '동향', status: 'active',
        discoveredAt: '2026-07-20T09:04:00+09:00', lastSeenAt: '2026-07-22T09:44:00+09:00',
      }, 2),
      listing({
        groupId: '128004-jeonse-103', building: '103동', tradeType: 'jeonse', price: 720_000_000,
        supplyAreaM2: 109, exclusiveAreaM2: 84.7, floor: '22/49층', direction: '남동향', status: 'active',
        discoveredAt: '2026-07-13T09:30:00+09:00', lastSeenAt: '2026-07-22T09:44:00+09:00',
      }, 3),
      listing({
        groupId: '128004-monthly-102', building: '102동', tradeType: 'monthly', price: 100_000_000, monthlyRent: 2_700_000,
        supplyAreaM2: 109, exclusiveAreaM2: 84.7, floor: '15/49층', direction: '남향', status: 'active',
        discoveredAt: '2026-07-19T09:05:00+09:00', lastSeenAt: '2026-07-22T09:44:00+09:00',
      }, 2),
      listing({
        groupId: '128004-jeonse-106', building: '106동', tradeType: 'jeonse', price: 690_000_000,
        supplyAreaM2: 109, exclusiveAreaM2: 84.7, floor: '8/42층', direction: '남동향', status: 'removed',
        discoveredAt: '2026-07-08T10:00:00+09:00', lastSeenAt: '2026-07-20T09:04:00+09:00', removedAt: '2026-07-22T09:44:00+09:00',
      }, 1),
    ],
  },
  {
    complexId: '119330',
    complexName: '동탄역시범한화꿈에그린프레스티지',
    address: '경기도 화성시 청계동 520',
    details: {
      householdCount: 1817,
      buildingCount: 25,
      completedYear: 2015,
      parkingPerHousehold: 1.36,
      heating: '지역난방',
    },
    history: [
      { collectedAt: '2026-07-18T09:12:00+09:00', saleCount: 2, jeonseCount: 1, monthlyCount: 1, addedCount: 0, removedCount: 0 },
      { collectedAt: '2026-07-19T09:11:00+09:00', saleCount: 2, jeonseCount: 1, monthlyCount: 1, addedCount: 0, removedCount: 0 },
      { collectedAt: '2026-07-20T09:10:00+09:00', saleCount: 2, jeonseCount: 2, monthlyCount: 1, addedCount: 1, removedCount: 0 },
      { collectedAt: '2026-07-22T09:48:00+09:00', saleCount: 3, jeonseCount: 2, monthlyCount: 1, addedCount: 1, removedCount: 0 },
    ],
    listingGroups: [
      listing({
        groupId: '119330-sale-1421', building: '1421동', tradeType: 'sale', price: 1_180_000_000,
        supplyAreaM2: 111, exclusiveAreaM2: 84.9, floor: '18/25층', direction: '남동향', status: 'active',
        discoveredAt: '2026-06-18T13:00:00+09:00', lastSeenAt: '2026-07-22T09:48:00+09:00',
      }, 4),
      listing({
        groupId: '119330-sale-1423', building: '1423동', tradeType: 'sale', price: 1_260_000_000,
        supplyAreaM2: 111, exclusiveAreaM2: 84.9, floor: '23/25층', direction: '남향', status: 'new',
        discoveredAt: '2026-07-22T09:48:00+09:00', lastSeenAt: '2026-07-22T09:48:00+09:00',
      }, 2),
      listing({
        groupId: '119330-sale-1415', building: '1415동', tradeType: 'sale', price: 1_050_000_000,
        supplyAreaM2: 98, exclusiveAreaM2: 74.9, floor: '10/23층', direction: '남서향', status: 'active',
        discoveredAt: '2026-07-03T10:00:00+09:00', lastSeenAt: '2026-07-22T09:48:00+09:00',
      }, 2),
      listing({
        groupId: '119330-jeonse-1418', building: '1418동', tradeType: 'jeonse', price: 560_000_000, previousPrice: 580_000_000,
        supplyAreaM2: 111, exclusiveAreaM2: 84.9, floor: '12/25층', direction: '남동향', status: 'changed',
        discoveredAt: '2026-07-10T14:00:00+09:00', lastSeenAt: '2026-07-22T09:48:00+09:00',
      }, 3),
      listing({
        groupId: '119330-jeonse-1420', building: '1420동', tradeType: 'jeonse', price: 590_000_000,
        supplyAreaM2: 111, exclusiveAreaM2: 84.9, floor: '7/25층', direction: '남향', status: 'active',
        discoveredAt: '2026-07-20T09:10:00+09:00', lastSeenAt: '2026-07-22T09:48:00+09:00',
      }, 1),
      listing({
        groupId: '119330-monthly-1412', building: '1412동', tradeType: 'monthly', price: 70_000_000, monthlyRent: 1_800_000,
        supplyAreaM2: 98, exclusiveAreaM2: 74.9, floor: '16/23층', direction: '남서향', status: 'active',
        discoveredAt: '2026-07-18T09:12:00+09:00', lastSeenAt: '2026-07-22T09:48:00+09:00',
      }, 2),
    ],
  },
]

export const demoDashboardDataset: DashboardDataset = {
  analysisId: 'analysis-20260722-0940',
  sourceUrl: 'https://fin.land.naver.com/map?demo=true',
  collectedAt: '2026-07-22T09:48:00+09:00',
  apartments,
}
