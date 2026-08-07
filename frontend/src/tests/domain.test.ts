import { describe, expect, it } from 'vitest'
import { demoDashboardDataset } from '../mocks/demoRealEstate'
import { compareListingSnapshots, getListingsAt } from '../utils/listingHistory'
import { formatKoreanPrice } from '../utils/formatters'

describe('real-estate domain data', () => {
  it('formats won values as Korean sale prices', () => {
    expect(formatKoreanPrice(830_000_000)).toBe('8억 3,000')
    expect(formatKoreanPrice(698_000_000)).toBe('6억 9,800')
  })

  it('keeps listing groups separate from broker registrations', () => {
    const groups = demoDashboardDataset.apartments.flatMap(
      (apartment) => apartment.listingGroups,
    )
    const registrations = groups.flatMap((group) => group.registrations)

    expect(demoDashboardDataset.apartments).toHaveLength(3)
    expect(groups.length).toBeGreaterThan(8)
    expect(registrations.length).toBeGreaterThan(groups.length)
    expect(groups[0].registrations).toHaveLength(15)
  })

  it('compares listing snapshots between selected research dates', () => {
    const apartment = demoDashboardDataset.apartments[0]
    const previousDate = apartment.history.at(-2)!.collectedAt
    const selectedDate = apartment.history.at(-1)!.collectedAt

    const previous = getListingsAt(apartment, previousDate)
    const selected = getListingsAt(apartment, selectedDate)
    const comparison = compareListingSnapshots(previous, selected)

    expect(comparison.added.map((item) => item.groupId)).toContain('124735-sale-112')
    expect(comparison.removed.map((item) => item.groupId)).toContain('124735-sale-118')
    expect(comparison.changed.map((item) => item.after.groupId)).toContain('124735-sale-101')

    const unobservedBefore = {
      ...previous[0]!,
      groupId: 'unobserved-without-removed-at',
      removedAt: undefined,
    }
    const absenceComparison = compareListingSnapshots([unobservedBefore], [])

    expect(absenceComparison.removed).toHaveLength(0)
    expect(absenceComparison.unobserved.map((item) => item.before?.groupId))
      .toContain('unobserved-without-removed-at')
  })
})
