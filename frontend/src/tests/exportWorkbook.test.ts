import * as XLSX from 'xlsx'
import { describe, expect, it } from 'vitest'
import { demoDashboardDataset } from '../mocks/demoRealEstate'
import { buildDashboardWorkbook } from '../utils/exportWorkbook'

describe('broker registration workbook export', () => {
  it('marks uncollected details and leaves all seven detail JSON cells blank', () => {
    const dataset = structuredClone(demoDashboardDataset)
    const registrations = dataset.apartments.flatMap((apartment) =>
      apartment.listingGroups.flatMap((group) => group.registrations),
    )
    const target = registrations[0]

    expect(target).toBeDefined()
    target!.marketDetails = {
      finance: { 대출: '표시 대상' },
      transactions: { 최근거래: '표시 대상' },
      costs: { 취득세: '표시 대상' },
      maintenance: { 관리비: '표시 대상' },
      complex: { 세대수: '표시 대상' },
      location: { 교통: '표시 대상' },
      extraFields: { 기타: '표시 대상' },
    }
    target!.detailCollected = false

    const workbook = buildDashboardWorkbook(dataset)
    const sheet = workbook.Sheets['중개사등록']
    const rows = XLSX.utils.sheet_to_json<Record<string, string>>(sheet, {
      defval: '',
    })
    const row = rows.find((item) => item.매물ID === target!.articleId)

    expect(row).toBeDefined()
    expect(row!.추가상세수집여부).toBe('N')
    expect(row!.물건별금융JSON).toBe('')
    expect(row!.물건별실거래JSON).toBe('')
    expect(row!.물건별비용세금JSON).toBe('')
    expect(row!.물건별관리비JSON).toBe('')
    expect(row!.물건별단지JSON).toBe('')
    expect(row!.물건별입지교통JSON).toBe('')
    expect(row!.물건별추가필드JSON).toBe('')
    expect(sheet['!cols']).toHaveLength(42)
  })
})
